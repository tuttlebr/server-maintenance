import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import ContextDocument, Device
from backend.services.document_parser import ParserUnavailable
from backend.services.context_manager import (
    _render_uploaded_document,
    create_document,
    render_device_context,
)


class ContextManagerTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.device = Device(
            hostname="daedalus-02",
            display_name="daedalus-02",
            endpoint="192.0.2.20",
            kind="server",
            vendor="ASRock Rack",
            model="Server",
        )
        self.device.annotations = {"Motherboard model": "ROMED6U-2L2T"}
        self.db.add(self.device)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_upload_association_is_rendered_into_index_source(self):
        with patch("backend.services.context_manager.settings.context_upload_max_bytes", 1024):
            document = create_document(
                self.db,
                filename="owners-manual.txt",
                content_bytes=b"Safety and maintenance instructions for this motherboard.",
                title="ROMED6U-2L2T Owner's Manual",
                device_id=self.device.id,
                uploaded_by="admin",
            )

        rendered = _render_uploaded_document(document, self.device)
        self.assertIn("Associated device: daedalus-02", rendered)
        self.assertIn("Device Motherboard model: ROMED6U-2L2T", rendered)
        self.assertIn("Safety and maintenance instructions", rendered)

    def test_generated_device_context_includes_discovery_and_manual_facts(self):
        self.device.facts = {
            "motherboard": {"vendor": "ASRock Rack", "model": "ROMED6U-2L2T"},
            "bios": {"version": "P3.80"},
        }
        context = render_device_context([self.device])
        self.assertIn("Motherboard model: ROMED6U-2L2T", context)
        self.assertIn("Manual attributes", context)

    def test_parsed_upload_is_saved_as_text_and_duplicates_are_not_reparsed(self):
        kwargs = dict(filename="manual.pdf", content_bytes=b"PDF bytes", title=None, device_id=self.device.id, uploaded_by="admin")
        with patch("backend.services.context_manager.parse_document", return_value="## Page 1\n\nUse this procedure to maintain the motherboard.") as parse:
            document = create_document(self.db, **kwargs)
            self.assertEqual(document.title, "manual")
            self.assertEqual(document.content_type, "text/markdown")
            self.assertIn("Use this procedure", _render_uploaded_document(document, self.device))
            with self.assertRaises(FileExistsError):
                create_document(self.db, **kwargs)
            parse.assert_called_once()

    def test_failed_parser_saves_nothing_and_text_uploads_bypass_it(self):
        with patch("backend.services.context_manager.parse_document", side_effect=ParserUnavailable("Unavailable")) as parse:
            with self.assertRaises(ParserUnavailable):
                create_document(self.db, filename="manual.pdf", content_bytes=b"PDF", title=None, device_id=None, uploaded_by="admin")
            self.assertEqual(self.db.query(ContextDocument).count(), 0)
            create_document(self.db, filename="manual.md", content_bytes=b"# Manual\n\nInstructions for maintaining the fans.", title=None, device_id=None, uploaded_by="admin")
            parse.assert_called_once()

if __name__ == "__main__":
    unittest.main()
