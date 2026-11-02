import json
from unittest.mock import Mock, patch

import pytest

from backend.services import docs_indexer


def test_embedding_progress_counts_completed_batches_and_preserves_it_during_retry():
    with patch.object(docs_indexer, '_state', dict(docs_indexer._state)):
        docs_indexer._handle_ingester_line('Prepared 2992 Markdown chunk(s)', 0)
        docs_indexer._handle_ingester_line('Embedding batch 69/187', 2992)
        assert docs_indexer._state['progress'] == 68 * 16
        docs_indexer._handle_ingester_line('Retrying embedding batch after transient failure in 2s (attempt 2/5)', 2992)
        assert docs_indexer._state['phase'] == 'embedding'
        assert docs_indexer._state['progress'] == 68 * 16
        assert 'Retrying' in docs_indexer._state['message']
        docs_indexer._handle_ingester_line('Embedded batch 69/187 (1088 cached chunks reused)', 2992)
        assert docs_indexer._state['progress'] == 69 * 16
        docs_indexer._handle_ingester_line('Embedding batch 187/187', 2992)
        assert docs_indexer._state['progress'] < docs_indexer._state['total']


def test_ingester_uses_persistent_checkpoint_directory(tmp_path):
    with (
        patch.object(docs_indexer.settings, 'data_dir', tmp_path),
        patch.object(docs_indexer.subprocess, 'Popen', side_effect=RuntimeError('test stop')) as process,
        patch.object(docs_indexer, '_set'),
    ):
        docs_indexer._run_ingester(['fleet-doc-ingester'], tmp_path / 'sources')
    command = process.call_args.args[0]
    position = command.index('--embedding-cache-dir')
    assert command[position + 1] == str(tmp_path / 'embedding-checkpoints' / 'fleet_docs')


def test_local_reference_directory_is_stable_across_runs(tmp_path):
    urls = tmp_path / 'urls.txt'
    urls.write_text('https://example.com/docs/')
    paths = []
    with (
        patch.multiple(docs_indexer.settings, data_dir=tmp_path, docs_urls_file=urls, docs_markdown_dir=tmp_path / 'markdown'),
        patch.object(docs_indexer, '_embedding_api_key_configured', return_value=True),
        patch.object(docs_indexer, '_ingester_command', return_value=['fleet-doc-ingester']),
        patch.object(docs_indexer, 'prepare_index_sources', side_effect=lambda path: paths.append(path) or 1),
        patch.object(docs_indexer, '_run_ingester'),
        patch.object(docs_indexer, '_set'),
    ):
        docs_indexer._run_reindex_inner()
        docs_indexer._run_reindex_inner()
    assert paths[0].name == paths[1].name == 'context'
    assert paths[0].parent != paths[1].parent


@pytest.mark.parametrize('exit_code', [0, 1])
def test_skipped_sections_complete_with_warnings_only_after_successful_ingestion(tmp_path, exit_code):
    section = {'chunk': 2, 'source': 'Manual', 'heading': 'Rejected section', 'reason': 'HTTP 400 Bad Request'}
    lines = [
        'Prepared 18 Markdown chunk(s)',
        'Embedding batch 1/2',
        'Skipped embedding: ' + json.dumps(section),
        'Processed embedding batch 1/2 (0 cached chunks reused, 1 chunks skipped)',
        'Embedding batch 2/2',
        'Processed embedding batch 2/2 (0 cached chunks reused, 1 chunks skipped)',
        "Dropping existing Milvus collection 'fleet_docs'",
        "Creating Milvus collection 'fleet_docs' (dim=2)",
        'Inserting Milvus batch 1/1',
    ]
    if exit_code == 0:
        lines.append("Ingested 17 chunk(s) into Milvus collection 'fleet_docs'")
    else:
        lines.append('Error: Milvus unavailable')
    process = Mock(stdout=iter(lines))
    process.wait.return_value = exit_code
    with (
        patch.object(docs_indexer, '_state', dict(docs_indexer._state, running=True, skipped_count=0,
                                                skipped_sections=[], last_count=50, last_indexed_at='previous')),
        patch.object(docs_indexer.subprocess, 'Popen', return_value=process),
        patch.object(docs_indexer, '_peek_count', side_effect=AssertionError('Use actual ingested count')),
    ):
        docs_indexer._run_ingester(['fake-ingester'], tmp_path)
        state = docs_indexer._state
        assert not state['running']
        assert state['skipped_count'] == 1
        assert state['skipped_sections'] == [section]
        if exit_code == 0:
            assert state['phase'] == 'partial'
            assert state['error'] is None
            assert state['last_count'] == state['progress'] == state['total'] == 17
            assert 'skipped 1 rejected section.' in state['message']
            assert state['last_indexed_at'] != 'previous'
        else:
            assert state['phase'] == 'error'
            assert 'Milvus unavailable' in state['error']
            assert state['last_count'] == 50
            assert state['last_indexed_at'] == 'previous'


def test_skipped_detail_is_bounded_and_insertion_total_excludes_rejected_chunks():
    with patch.object(docs_indexer, '_state', dict(docs_indexer._state, skipped_count=0, skipped_sections=[])):
        total = docs_indexer._handle_ingester_line('Prepared 100 Markdown chunk(s)', 0)
        for chunk in range(1, 26):
            docs_indexer._handle_ingester_line('Skipped embedding: ' + json.dumps({
                'chunk': chunk, 'source': 'Manual', 'heading': f'Section {chunk}', 'reason': 'HTTP 400',
            }), total)
        assert docs_indexer._state['skipped_count'] == 25
        assert len(docs_indexer._state['skipped_sections']) == 20
        total = docs_indexer._handle_ingester_line('Dropping existing Milvus collection', total)
        assert total == 75
        total = docs_indexer._handle_ingester_line('Creating Milvus collection', total)
        assert total == 75
        assert docs_indexer._state['total'] == 75


def test_new_run_clears_previous_skips_before_worker_starts():
    with (
        patch.object(docs_indexer, '_state', dict(docs_indexer._state, running=False, phase='partial',
                                                skipped_count=5, skipped_sections=[{'chunk': 1}])),
        patch.object(docs_indexer.threading, 'Thread'),
    ):
        assert docs_indexer.start_reindex()
        assert docs_indexer._state['skipped_count'] == 0
        assert docs_indexer._state['skipped_sections'] == []
        assert docs_indexer._state['phase'] == 'loading'
