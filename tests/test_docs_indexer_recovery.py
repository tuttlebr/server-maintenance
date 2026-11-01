from unittest.mock import patch

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
