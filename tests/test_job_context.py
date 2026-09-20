import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import Host, Job
from backend.services import job_context

FIRST = "11111111-1111-1111-1111-111111111111"
SECOND = "22222222-2222-2222-2222-222222222222"
MISSING = "99999999-9999-9999-9999-999999999999"


class JobContextTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.engine.dispose)
        self.enterContext(patch.object(job_context, "SessionLocal", self.sessions))
        self.enterContext(patch.object(job_context.settings, "data_dir", Path(self.temp.name)))
        now = datetime.now(timezone.utc)
        with self.sessions() as db:
            db.add_all([
                Host(id=1, hostname="node-1", display_name="Compute One"),
                Host(id=2, hostname="node-10"),
                Job(job_id=FIRST, playbook="storage_analysis.yml", target_hosts="node-1,node-2", status="failed",
                    created_at=now - timedelta(days=1), finished_at=now - timedelta(days=1),
                    recap="node-1 : ok=1 failed=1\nnode-2 : ok=5 failed=0", output_log="storage failure evidence"),
                Job(job_id=SECOND, playbook="host_facts.yml", target_hosts="node-10", status="success",
                    created_at=now, finished_at=now, output_log="other host output"),
            ])
            db.commit()

    def context(self, question, **kwargs):
        return job_context.get_job_context([{"role": "user", "content": question}], **kwargs)

    def test_explicit_old_job_beats_recent_jobs_and_includes_host_recap(self):
        text = self.context("Explain this run", job_id=FIRST)
        self.assertIn("storage failure evidence", text)
        self.assertIn("node-2 : ok=5 failed=0", text)
        self.assertNotIn(SECOND, text)

    def test_missing_explicit_job_does_not_substitute_latest_job(self):
        text = self.context(f"Explain job {MISSING}")
        self.assertIn("not found", text)
        self.assertNotIn(SECOND, text)
        self.assertNotIn(FIRST, text)

    def test_device_scope_matches_whole_host_in_multiple_targets(self):
        text = self.context("What happened?", device_id=1)
        self.assertIn(FIRST, text)
        self.assertNotIn(SECOND, text)

    def test_question_overrides_page_scope(self):
        text = self.context(f"Explain job {SECOND}", job_id=FIRST)
        self.assertIn(SECOND, text)
        self.assertNotIn(FIRST, text)

    def test_named_device_overrides_page_scope(self):
        text = self.context("How did Compute One do?", job_id=SECOND)
        self.assertIn(FIRST, text)
        self.assertNotIn(SECOND, text)

    def test_followup_refreshes_explicit_job_from_history(self):
        with self.sessions() as db:
            db.query(Job).filter_by(job_id=FIRST).update({"output_log": "fresh follow-up evidence"})
            db.commit()
        text = job_context.get_job_context([
            {"role": "user", "content": f"Explain {FIRST}"},
            {"role": "assistant", "content": "Earlier answer"},
            {"role": "user", "content": "What should I try next?"},
        ])
        self.assertIn("fresh follow-up evidence", text)
        self.assertNotIn(SECOND, text)

    def test_storage_query_selects_matching_playbook(self):
        text = self.context("Why did the latest storage run fail?")
        self.assertIn(FIRST, text)
        self.assertNotIn(SECOND, text)

    def test_followup_preserves_playbook_scope_without_a_job_id(self):
        text = job_context.get_job_context([
            {"role": "user", "content": "Why did the storage analysis fail?"},
            {"role": "assistant", "content": "The storage task failed."},
            {"role": "user", "content": "What should I try next?"},
        ])
        self.assertIn(FIRST, text)
        self.assertNotIn(SECOND, text)

    def test_new_fleet_question_resets_old_conversation_scope(self):
        text = job_context.get_job_context([
            {"role": "user", "content": f"Explain {FIRST}"},
            {"role": "assistant", "content": "Earlier answer"},
            {"role": "user", "content": "List recent jobs across the fleet"},
        ])
        self.assertIn(FIRST, text)
        self.assertIn(SECOND, text)

    def test_running_job_reads_current_file_on_each_request(self):
        with self.sessions() as db:
            db.query(Job).filter_by(job_id=FIRST).update({"status": "running", "output_log": None, "finished_at": None})
            db.commit()
        log = Path(self.temp.name) / "logs" / f"{FIRST}.log"
        log.parent.mkdir()
        log.write_text("TASK [Stage one]\nok: [node-1]")
        self.assertIn("Stage one", self.context("Progress?", job_id=FIRST))
        log.write_text("TASK [Stage two]\nchanged: [node-1]")
        text = self.context("Progress?", job_id=FIRST)
        self.assertIn("Stage two", text)
        self.assertIn("partial while running", text)

    def test_structured_results_and_json_secrets_are_sanitized(self):
        directory = Path(self.temp.name) / "job-results" / FIRST
        directory.mkdir(parents=True)
        (directory / "storage.json").write_text(json.dumps({
            "schema_version": 1, "report_type": "storage", "hostname": "node-1",
            "mounts": [{"mountpoint": "/data", "use_pct": 95}], "api_key": "artifact-secret",
        }))
        with self.sessions() as db:
            db.query(Job).filter_by(job_id=FIRST).update({
                "output_log": '{"ansible_password": "log-secret", "token": "another-secret", "Authorization": "Bearer bearer-secret"}',
                "error_summary": 'password="summary-secret"',
            })
            db.commit()
        text = self.context("Explain", job_id=FIRST)
        self.assertIn('"use_pct": 95', text)
        for secret in ("artifact-secret", "log-secret", "another-secret", "summary-secret", "bearer-secret"):
            self.assertNotIn(secret, text)

    def test_context_budget_and_failure_in_middle_of_huge_log(self):
        with self.sessions() as db:
            db.query(Job).filter_by(job_id=FIRST).update({"output_log": (
                "ok: [node-1] " + "x" * 1_000_000 + "\n"
                'TASK [Check storage]\nfatal: [node-1]: FAILED! => {\n"msg": "disk full"\n}\n'
                + "ok: [node-2]\n" * 50_000 + "PLAY RECAP\nnode-1 : failed=1\n"
            )})
            db.commit()
        text = self.context("Why did this fail?", job_id=FIRST)
        self.assertLessEqual(len(text), job_context.MAX_CONTEXT_CHARS)
        self.assertIn("TASK [Check storage]", text)
        self.assertIn("disk full", text)
        self.assertIn("PLAY RECAP", text)
        self.assertIn("omitted", text)

    def test_unknown_device_does_not_include_other_jobs(self):
        text = self.context("Explain", device_id=999)
        self.assertIn("not found", text)
        self.assertNotIn(FIRST, text)


if __name__ == "__main__":
    unittest.main()
