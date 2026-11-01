import unittest
from unittest.mock import patch

from backend.services import upload_progress as progress


class UploadProgressTests(unittest.TestCase):
    def setUp(self):
        self.store = progress.UploadProgress()

    def test_owner_scope_claim_once_and_no_sensitive_status(self):
        key = self.store.create("owner")
        with self.assertRaises(LookupError):
            self.store.get(key, "other")
        with self.assertRaises(LookupError):
            self.store.claim(key, "other")
        self.store.claim(key, "owner")
        with self.assertRaises(ValueError):
            self.store.claim(key, "owner")
        self.assertNotIn("owner", self.store.get(key, "owner"))

    def test_elapsed_and_last_completed_page_are_server_measured(self):
        with patch.object(progress.time, "monotonic", return_value=10) as clock:
            key = self.store.create("owner")
            self.store.claim(key, "owner")
            self.store.update(key, "rendering", 2, 2)
            self.store.update(key, "parsing", 0, 2)
            self.assertIsNone(self.store.get(key, "owner")["seconds_since_last_page"])
            clock.return_value = 20
            self.store.update(key, "parsing", 1, 2)
            clock.return_value = 25
            state = self.store.get(key, "owner")
            self.assertEqual((state["completed"], state["total"]), (1, 2))
            self.assertEqual(state["elapsed_seconds"], 15)
            self.assertEqual(state["seconds_since_last_page"], 5)
            self.store.update(key, "complete", document_id=42)
            clock.return_value = 35
            state = self.store.get(key, "owner")
            self.assertEqual(state["elapsed_seconds"], 15)
            self.assertEqual(state["document_id"], 42)

    def test_retention_does_not_expire_a_slow_active_page(self):
        with patch.object(progress.time, "monotonic", return_value=0) as clock:
            idle = self.store.create("owner")
            active = self.store.create("owner")
            self.store.claim(active, "owner")
            clock.return_value = progress.RETENTION_SECONDS + 1
            with self.assertRaises(LookupError):
                self.store.get(idle, "owner")
            self.assertEqual(self.store.get(active, "owner")["phase"], "validating")
            self.store.update(active, "failed", error="Parser timed out")
            clock.return_value *= 2
            with self.assertRaises(LookupError):
                self.store.get(active, "owner")

    def test_capacity_evicts_finished_records_but_not_active_work(self):
        with patch.object(progress, "MAX_UPLOADS", 1):
            key = self.store.create("owner")
            self.store.claim(key, "owner")
            with self.assertRaises(ValueError):
                self.store.create("owner")
            self.store.update(key, "complete", document_id=1)
            self.store.create("owner")
            with self.assertRaises(LookupError):
                self.store.get(key, "owner")
