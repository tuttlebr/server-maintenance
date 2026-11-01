import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.auth import get_current_user
from backend.database import Base, get_db
from backend.models import ContextDocument
from backend.routers.context import router
from backend.services.document_parser import ParserUnavailable
from backend.services.upload_progress import UploadProgress


class ContextRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: "admin"
        self.client = TestClient(app)
        self.app = app
        self.progress = patch("backend.routers.context.uploads", UploadProgress())
        self.progress.start()
        self.addCleanup(self.progress.stop)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_status_exposes_capability_and_limits_without_endpoint_or_key(self):
        with (
            patch("backend.routers.context.docs_indexer.get_status", return_value={}),
            patch("backend.routers.context.settings.parser_base_url", "http://private-parser/v1"),
            patch("backend.routers.context.settings.context_upload_max_bytes", 30 * 1024 * 1024),
            patch("backend.routers.context.settings.parser_timeout_seconds", 1800),
        ):
            response = self.client.get("/api/v2/context/status")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["parser_enabled"])
        self.assertEqual(response.json()["upload_max_bytes"], 30 * 1024 * 1024)
        self.assertNotIn("private-parser", response.text)
        self.assertEqual(response.json()["parser_timeout_seconds"], 1800)

    def test_progress_is_pollable_during_parsing_and_complete_after_save(self):
        key = self.client.post("/api/v2/context/uploads").json()["upload_id"]
        entered, release = threading.Event(), threading.Event()

        def parse(content, extension, progress):
            progress("parsing", 1, 2)
            entered.set()
            if not release.wait(5):
                raise AssertionError("Test failed to release parser")
            progress("parsing", 2, 2)
            return "## Page 1\n\nDocumented maintenance instructions for the fans."

        with patch("backend.services.context_manager.parse_document", side_effect=parse), ThreadPoolExecutor() as pool:
            future = pool.submit(self.client.post, "/api/v2/context/documents", data={"upload_id": key}, files={"file": ("manual.pdf", b"pdf-content", "application/pdf")})
            try:
                self.assertTrue(entered.wait(5))
                response = self.client.get(f"/api/v2/context/uploads/{key}")
                self.assertEqual(response.status_code, 200)
                state = response.json()
                self.assertEqual((state["phase"], state["completed"], state["total"]), ("parsing", 1, 2))
                self.assertIsNone(state["document_id"])
            finally:
                release.set()
            response = future.result(timeout=5)
        self.assertEqual(response.status_code, 201, response.text)
        state = self.client.get(f"/api/v2/context/uploads/{key}").json()
        self.assertEqual(state["phase"], "complete")
        self.assertEqual(state["document_id"], response.json()["id"])
        self.assertEqual(self.db.query(ContextDocument).count(), 1)

    def test_failed_upload_and_validation_have_terminal_status_and_save_nothing(self):
        for filename, parser_error, expected in [("manual.pdf", ParserUnavailable("Timed out on page 15"), 502), ("bad.exe", None, 422)]:
            key = self.client.post("/api/v2/context/uploads").json()["upload_id"]
            with patch("backend.services.context_manager.parse_document", side_effect=parser_error):
                response = self.client.post("/api/v2/context/documents", data={"upload_id": key}, files={"file": (filename, b"data")})
            self.assertEqual(response.status_code, expected)
            state = self.client.get(f"/api/v2/context/uploads/{key}").json()
            self.assertEqual(state["phase"], "failed")
            self.assertEqual(state["error"], response.json()["detail"])
            self.assertIsNone(state["document_id"])
        self.assertEqual(self.db.query(ContextDocument).count(), 0)

    def test_progress_ids_cannot_be_reused_or_accessed_by_another_user(self):
        key = self.client.post("/api/v2/context/uploads").json()["upload_id"]
        self.app.dependency_overrides[get_current_user] = lambda: "other"
        self.assertEqual(self.client.get(f"/api/v2/context/uploads/{key}").status_code, 404)
        payload = dict(data={"upload_id": key}, files={"file": ("manual.txt", b"Maintenance instructions for the cooling fans.")})
        self.assertEqual(self.client.post("/api/v2/context/documents", **payload).status_code, 404)
        self.app.dependency_overrides[get_current_user] = lambda: "admin"
        self.assertEqual(self.client.post("/api/v2/context/documents", **payload).status_code, 201)
        self.assertEqual(self.client.post("/api/v2/context/documents", **payload).status_code, 409)

    def test_save_failure_rolls_back_and_never_reports_complete(self):
        key = self.client.post("/api/v2/context/uploads").json()["upload_id"]
        with patch.object(self.db, "commit", side_effect=RuntimeError("Database unavailable")):
            with self.assertRaises(RuntimeError):
                self.client.post("/api/v2/context/documents", data={"upload_id": key}, files={"file": ("manual.txt", b"Maintenance instructions for the cooling fans.")})
        state = self.client.get(f"/api/v2/context/uploads/{key}").json()
        self.assertEqual(state["phase"], "failed")
        self.assertIsNone(state["document_id"])
        self.assertEqual(self.db.query(ContextDocument).count(), 0)

    def test_parser_upload_and_error_handling(self):
        with patch("backend.services.context_manager.parse_document", return_value="## Page 1\n\nDocumented maintenance instructions for the fans."):
            response = self.client.post("/api/v2/context/documents", files={"file": ("manual.pdf", b"pdf-content", "application/pdf")})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["original_filename"], "manual.pdf")
        self.assertEqual(self.db.query(ContextDocument).count(), 1)
        with patch("backend.services.context_manager.parse_document", side_effect=ParserUnavailable("Parser unavailable")):
            response = self.client.post("/api/v2/context/documents", files={"file": ("other.pdf", b"other-content", "application/pdf")})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.db.query(ContextDocument).count(), 1)

    def test_disabled_parser_still_allows_plain_text_uploads(self):
        with patch("backend.routers.context.settings.parser_base_url", ""):
            response = self.client.post("/api/v2/context/documents", files={"file": ("manual.pdf", b"pdf-content", "application/pdf")})
            self.assertEqual(response.status_code, 422)
            response = self.client.post("/api/v2/context/documents", files={"file": ("manual.txt", b"Documented maintenance instructions for the fans.", "text/plain")})
            self.assertEqual(response.status_code, 201, response.text)
