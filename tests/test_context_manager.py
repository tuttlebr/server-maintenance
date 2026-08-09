import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import Device
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

if __name__ == "__main__":
    unittest.main()
