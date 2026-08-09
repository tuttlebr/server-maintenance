import asyncio
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.capabilities import (
    NVIDIA_DRIVER_MANAGE,
    REACHY_DAEMON_RESTART,
    REACHY_HEALTH,
    REACHY_LOGS_READ,
    REACHY_SOFTWARE_UPDATE,
)
from backend.database import Base
from backend.models import Device, ManagedUser, UserHostAssociation
from backend.routers.devices import delete_device
from backend.routers.operations import list_operations, run_operation
from backend.schemas import DeviceAnnotationsUpdate, DeviceCreate, OperationRunRequest
from backend.services.device_discovery import enrich_from_scan, initial_profile, probe_reachy


class DeviceSchemaTests(unittest.TestCase):
    def test_ssh_device_requires_remote_user(self):
        with self.assertRaises(ValidationError):
            DeviceCreate(name="compute-01", endpoint="192.0.2.10", transport="ssh")

    def test_password_auth_requires_password(self):
        with self.assertRaises(ValidationError):
            DeviceCreate(
                name="compute-01",
                endpoint="192.0.2.10",
                transport="ssh",
                ssh_user="fleetadmin",
                passwordless_ssh=False,
            )

    def test_reachy_defaults_to_documented_daemon_port(self):
        payload = DeviceCreate(
            name="reachy-lab",
            endpoint="reachy-mini.local",
            transport="reachy_daemon",
        )
        self.assertEqual(payload.daemon_port, 8000)
        self.assertIsNone(payload.ssh_user)

    def test_manual_device_attributes_are_trimmed_and_validated(self):
        payload = DeviceAnnotationsUpdate(
            annotations={" Motherboard model ": " ASRock Rack ROMED6U-2L2T "}
        )
        self.assertEqual(payload.annotations, {"Motherboard model": "ASRock Rack ROMED6U-2L2T"})


class CapabilityDiscoveryTests(unittest.TestCase):
    def test_reachy_profile_exposes_management_without_motion(self):
        capabilities = set(initial_profile("reachy_daemon")["capabilities"])
        self.assertEqual(
            capabilities,
            {
                REACHY_HEALTH,
                REACHY_LOGS_READ,
                REACHY_DAEMON_RESTART,
                REACHY_SOFTWARE_UPDATE,
            },
        )
        self.assertFalse(any("move" in item or "motor" in item or "torque" in item for item in capabilities))

    def test_portable_scan_enriches_nvidia_server_by_capability(self):
        device = Device(hostname="compute-01", kind="generic", machine_type="unknown")
        enrich_from_scan(
            device,
            {
                "system_vendor": "Dell Inc.",
                "product_name": "PowerEdge R760xa",
                "architecture": "x86_64",
                "os_family": "Debian",
                "gpu_model": "NVIDIA L40S",
                "gpu_vendor": "NVIDIA",
                "fabric_manager_available": False,
                "mig_available": False,
                "kubernetes_available": True,
            },
        )
        self.assertEqual(device.kind, "server")
        self.assertEqual(device.machine_type, "gpu_node")
        self.assertIn(NVIDIA_DRIVER_MANAGE, device.capabilities)
        self.assertEqual(device.vendor, "Dell Inc.")

    def test_scan_captures_detailed_hardware_without_replacing_manual_attributes(self):
        device = Device(hostname="daedalus-02", kind="generic", machine_type="unknown")
        device.annotations = {"rack": "basement"}
        enrich_from_scan(
            device,
            {
                "system_vendor": "To Be Filled By O.E.M.",
                "product_name": "Server",
                "motherboard_vendor": "ASRock Rack",
                "motherboard_model": "ROMED6U-2L2T",
                "bios_version": "P3.80",
                "cpu_model": "AMD EPYC 7443P 24-Core Processor",
                "cpu_sockets": 1,
                "cpu_cores": 24,
                "cpu_vcpus": 48,
            },
        )
        self.assertEqual(device.facts["motherboard"]["model"], "ROMED6U-2L2T")
        self.assertEqual(device.facts["cpu"]["vcpus"], 48)
        self.assertEqual(device.annotations, {"rack": "basement"})

    def test_reachy_probe_never_calls_a_motion_endpoint(self):
        with patch(
            "backend.services.device_discovery.reachy_request",
            return_value={"daemon": {"state": "running"}},
        ) as request:
            result = probe_reachy("reachy-mini.local", 8000)
        self.assertTrue(result["reachable"])
        paths = [call.args[2] for call in request.call_args_list]
        self.assertEqual(paths[0], "/api/state/full")
        self.assertEqual(
            set(paths),
            {"/api/state/full", "/api/daemon/status", "/update/available"},
        )


class OperationEligibilityTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_catalog_only_shows_operations_supported_by_the_fleet(self):
        device = Device(
            hostname="reachy-lab",
            display_name="Reachy Lab",
            endpoint="reachy-mini.local",
            transport="reachy_daemon",
            kind="robot",
            machine_type="unknown",
        )
        device.capabilities = initial_profile("reachy_daemon")["capabilities"]
        self.db.add(device)
        self.db.commit()

        operation_ids = {operation.id for operation in list_operations(self.db, "admin")}
        self.assertEqual(
            operation_ids,
            {
                REACHY_HEALTH,
                REACHY_LOGS_READ,
                REACHY_DAEMON_RESTART,
                REACHY_SOFTWARE_UPDATE,
            },
        )

    def test_capability_check_blocks_linux_operation_on_robot(self):
        device = Device(
            hostname="reachy-lab",
            endpoint="reachy-mini.local",
            transport="reachy_daemon",
            kind="robot",
            machine_type="unknown",
        )
        device.capabilities = initial_profile("reachy_daemon")["capabilities"]
        self.db.add(device)
        self.db.commit()

        with self.assertRaisesRegex(HTTPException, "not supported"):
            asyncio.run(
                run_operation(
                    "system.reboot",
                    OperationRunRequest(device_ids=[device.id]),
                    self.db,
                    "admin",
                )
            )

    def test_removing_device_cleans_access_associations(self):
        device = Device(hostname="compute-01", transport="ssh", kind="server")
        user = ManagedUser(username="operator", email="operator@example.com")
        self.db.add_all([device, user])
        self.db.commit()
        self.db.add(UserHostAssociation(user_id=user.id, host_id=device.id))
        self.db.commit()

        with patch("backend.routers.devices.regenerate_inventory"):
            delete_device(device.id, self.db, "admin")

        self.assertIsNone(self.db.query(Device).filter(Device.id == device.id).first())
        self.assertEqual(self.db.query(UserHostAssociation).count(), 0)


if __name__ == "__main__":
    unittest.main()
