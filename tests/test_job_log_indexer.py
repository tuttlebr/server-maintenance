import asyncio
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
from backend.services import ansible_runner, job_log_indexer


def _test_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


class JobLogDocumentTests(unittest.TestCase):
    def test_job_documents_include_terminal_metadata_and_redact_common_secrets(self):
        now = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
        job = Job(
            job_id="failed-job",
            playbook="driver_upgrade.yml",
            target_hosts="dgx-01",
            status="failed",
            started_at=now - timedelta(minutes=2),
            finished_at=now,
            duration_seconds=120,
            triggered_by="admin",
            error_summary="Authorization: Bearer abc123",
            recap="dgx-01 : ok=2 failed=1",
            output_log='password="fleet secret"\n-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----',
        )

        documents = job_log_indexer.build_job_documents(job)
        text = "\n".join(document.text for document in documents)

        self.assertIn("Terminal status: failed", text)
        self.assertIn("driver_upgrade.yml", text)
        self.assertIn("dgx-01", text)
        self.assertNotIn("abc123", text)
        self.assertNotIn("fleet secret", text)
        self.assertNotIn("BEGIN PRIVATE KEY", text)
        self.assertIn("***REDACTED***", text)

    def test_fleet_snapshot_uses_newest_completed_job_for_each_host(self):
        sessions = _test_session_factory()
        db = sessions()
        now = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
        db.add_all(
            [
                Host(hostname="dgx-01", status="online", last_seen=now),
                Host(hostname="dgx-02", status="unknown"),
                Host(hostname="dgx-03", status="unknown"),
                Job(
                    job_id="older-failure",
                    playbook="preflight_check.yml",
                    target_hosts="dgx-01,dgx-02",
                    status="failed",
                    created_at=now - timedelta(hours=3),
                    finished_at=now - timedelta(hours=3),
                ),
                Job(
                    job_id="newer-success",
                    playbook="host_facts.yml",
                    target_hosts="dgx-01",
                    status="success",
                    created_at=now - timedelta(hours=2),
                    finished_at=now - timedelta(hours=2),
                ),
                Job(
                    job_id="newest-cancel",
                    playbook="driver_upgrade.yml",
                    target_hosts="dgx-02",
                    status="cancelled",
                    created_at=now - timedelta(hours=1),
                    finished_at=now - timedelta(hours=1),
                ),
            ]
        )
        db.commit()

        text = "\n".join(
            document.text
            for document in job_log_indexer.build_fleet_snapshot_documents(db)
        )
        db.close()

        self.assertIn("success=1, failed=0, cancelled=1, no completed job=1", text)
        self.assertIn("dgx-01: latest job=success", text)
        self.assertIn("job_id=newer-success", text)
        self.assertIn("dgx-02: latest job=cancelled", text)
        self.assertIn("dgx-03: no completed job", text)
        self.assertNotIn("dgx-01: latest job=failed", text)


class CompletedJobIngestionTests(unittest.TestCase):
    def test_failed_job_is_sent_to_index_with_fleet_snapshot(self):
        sessions = _test_session_factory()
        db = sessions()
        now = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
        db.add(Host(hostname="dgx-01", status="unknown"))
        db.add(
            Job(
                job_id="failed-job",
                playbook="preflight_check.yml",
                target_hosts="dgx-01",
                status="failed",
                finished_at=now,
                created_at=now,
                output_log="fatal: host unreachable",
            )
        )
        db.commit()
        captured = []

        with (
            patch.object(job_log_indexer, "SessionLocal", sessions),
            patch.object(
                job_log_indexer, "_embedding_api_configured", return_value=True
            ),
            patch.object(
                job_log_indexer, "_index_documents", side_effect=captured.append
            ),
        ):
            indexed = job_log_indexer.ingest_completed_job("failed-job")
        db.close()

        self.assertTrue(indexed)
        self.assertEqual(len(captured), 1)
        self.assertTrue(
            any(document.job_id == "failed-job" for document in captured[0])
        )
        self.assertTrue(
            any(
                document.job_id == job_log_indexer.SNAPSHOT_JOB_ID
                for document in captured[0]
            )
        )


class RunnerIngestionHookTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_indexes_a_failed_terminal_outcome(self):
        sessions = _test_session_factory()
        db = sessions()
        db.add(Host(hostname="dgx-01", ansible_user="fleet"))
        db.commit()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(ansible_runner, "SessionLocal", sessions),
                patch.object(ansible_runner.settings, "data_dir", root),
                patch.object(ansible_runner, "_run_playbook_streaming", return_value=2),
                patch.object(
                    ansible_runner.job_log_indexer,
                    "ingest_completed_job",
                    return_value=True,
                ) as ingest,
            ):
                job_id = await ansible_runner.run_playbook(
                    db,
                    "preflight_check.yml",
                    hosts=["dgx-01"],
                )
                for _ in range(100):
                    if ingest.called:
                        break
                    await asyncio.sleep(0.01)

        db.expire_all()
        job = db.query(Job).filter(Job.job_id == job_id).one()
        db.close()

        self.assertEqual(job.status, "failed")
        ingest.assert_called_once_with(job_id)


if __name__ == "__main__":
    unittest.main()
