import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.capabilities import (
    FIRMWARE_INSPECT,
    FIRMWARE_UPDATE,
    NVIDIA_DRIVER_MANAGE,
    REACHY_APP_RESET,
    REACHY_DAEMON_RESTART,
    REACHY_HEALTH,
    REACHY_LOGS_READ,
    REACHY_SOFTWARE_UPDATE,
    SYSTEM_REBOOT,
)
from backend.database import Base
from backend.models import Device, ManagedUser, UserHostAssociation
from backend.routers.devices import (
    configure_device_ssh,
    delete_device,
    device_response,
    update_device,
)
from backend.routers.operations import list_operations, run_operation
from backend.schemas import (
    DeviceAnnotationsUpdate,
    DeviceCreate,
    DeviceKeyApproval,
    DeviceSshEnrollmentRequest,
    DeviceUpdate,
    OperationRunRequest,
)
from backend.services.ansible_runner import PlaybookRequestError, _resolve_targets
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

    def test_reachy_ssh_password_auth_requires_password(self):
        with self.assertRaises(ValidationError):
            DeviceSshEnrollmentRequest(
                ssh_user="pollen",
                passwordless_ssh=False,
                approval=DeviceKeyApproval(
                    fingerprint="SHA256:" + "A" * 43,
                ),
            )

    def test_manual_device_attributes_are_trimmed_and_validated(self):
        payload = DeviceAnnotationsUpdate(
            annotations={" Motherboard model ": " ASRock Rack ROMED6U-2L2T "}
        )
        self.assertEqual(payload.annotations, {"Motherboard model": "ASRock Rack ROMED6U-2L2T"})

    def test_device_response_exposes_safe_csv_connection_fields(self):
        device = Device(
            id=7,
            hostname="compute-01",
            display_name="Friendly lab server",
            endpoint="192.0.2.10",
            transport="ssh",
            kind="server",
            ansible_user="fleetadmin",
            encrypted_ansible_password="fernet:ciphertext",
            encrypted_ansible_become_password="fernet:other-ciphertext",
        )

        payload = device_response(device).model_dump()

        self.assertEqual(payload["inventory_name"], "compute-01")
        self.assertEqual(payload["ssh_user"], "fleetadmin")
        self.assertFalse(payload["passwordless_ssh"])
        self.assertIsNone(payload["daemon_port"])
        self.assertNotIn("ssh_password", payload)
        self.assertNotIn("become_password", payload)

    def test_reachy_response_exposes_effective_daemon_port(self):
        device = Device(
            id=8,
            hostname="reachy-lab",
            endpoint="reachy-mini.local",
            transport="reachy_daemon",
            kind="robot",
        )

        payload = device_response(device)

        self.assertEqual(payload.daemon_port, 8000)
        self.assertIsNone(payload.ssh_user)
        self.assertTrue(payload.passwordless_ssh)

    def test_reachy_response_exposes_configured_ssh_maintenance_user(self):
        device = Device(
            id=9,
            hostname="reachy-lab",
            endpoint="reachy-mini.local",
            transport="reachy_daemon",
            kind="robot",
            ansible_user="pollen",
        )

        payload = device_response(device)

        self.assertEqual(payload.ssh_user, "pollen")
        self.assertTrue(payload.passwordless_ssh)


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

    def test_scan_exposes_firmware_actions_only_when_tools_are_available(self):
        device = Device(hostname="compute-02", kind="server", machine_type="cpu_node")
        enrich_from_scan(
            device,
            {
                "system_vendor": "Dell Inc.",
                "product_name": "PowerEdge",
                "architecture": "x86_64",
                "os_family": "Debian",
                "firmware_tool_available": True,
                "firmware_update_available": False,
            },
        )
        self.assertIn(FIRMWARE_INSPECT, device.capabilities)
        self.assertNotIn(FIRMWARE_UPDATE, device.capabilities)

    def test_scan_identifies_reachy_ssh_reset_capability(self):
        device = Device(hostname="reachy-ssh", kind="generic", machine_type="unknown")
        enrich_from_scan(
            device,
            {
                "architecture": "aarch64",
                "reachy_mini_available": True,
            },
        )

        self.assertEqual(device.kind, "robot")
        self.assertEqual(device.vendor, "Pollen Robotics")
        self.assertEqual(device.model, "Reachy Mini Wireless")
        self.assertIn(REACHY_APP_RESET, device.capabilities)

    def test_scan_identifies_branded_dgx_spark(self):
        device = Device(hostname="spark-01", kind="generic", machine_type="unknown")

        enrich_from_scan(
            device,
            {
                "system_vendor": "NVIDIA Corporation",
                "product_name": "GX10",
                "product_version": "1.0",
                "architecture": "aarch64",
                "gpu_model": "NVIDIA GB10",
                "gpu_vendor": "NVIDIA",
                "dgx_name": "DGX Spark",
                "dgx_pretty_name": "NVIDIA DGX Spark",
                "dgx_platform": "GX10",
                "dgx_swbuild_version": "7.5.0",
            },
        )

        self.assertEqual(device.kind, "edge")
        self.assertEqual(device.machine_type, "dgx_spark")
        self.assertEqual(device.vendor, "NVIDIA Corporation")
        self.assertEqual(device.model, "GX10")
        self.assertEqual(
            device.facts["dgx"],
            {
                "name": "DGX Spark",
                "pretty_name": "NVIDIA DGX Spark",
                "platform": "GX10",
                "swbuild_version": "7.5.0",
            },
        )

    def test_scan_identifies_oem_gx10_as_dgx_spark(self):
        device = Device(hostname="daedalus-06", kind="generic", machine_type="unknown")

        enrich_from_scan(
            device,
            {
                "system_vendor": "ASUSTeK COMPUTER INC.",
                "product_name": "GX10",
                "product_version": "5.36_GX10DGX",
                "architecture": "aarch64",
                "gpu_model": "NVIDIA GB10",
                "gpu_vendor": "NVIDIA",
            },
        )

        self.assertEqual(device.kind, "edge")
        self.assertEqual(device.machine_type, "dgx_spark")
        self.assertEqual(device.vendor, "ASUSTeK COMPUTER INC.")
        self.assertEqual(device.model, "GX10")
        self.assertEqual(device.facts["product_version"], "5.36_GX10DGX")
        self.assertEqual(device.facts["dgx"]["name"], "DGX Spark")

    def test_generic_arm_nvidia_system_with_dgx_hint_is_not_dgx_spark(self):
        device = Device(hostname="arm-devkit", kind="generic", machine_type="unknown")

        enrich_from_scan(
            device,
            {
                "system_vendor": "NVIDIA Corporation",
                "product_name": "ARM AI Developer Kit",
                "product_version": "DGX-compatible engineering sample",
                "architecture": "aarch64",
                "gpu_model": "NVIDIA RTX 6000 Ada Generation",
                "gpu_vendor": "NVIDIA",
            },
        )

        self.assertEqual(device.kind, "edge")
        self.assertEqual(device.machine_type, "gpu_node")
        self.assertNotIn("dgx", device.facts)

    def test_dgx_spark_detection_rejects_substrings_and_split_names(self):
        cases = (
            ({
                "system_vendor": "Example Corp.",
                "product_name": "Not a DGX Spark",
                "architecture": "x86_64",
                "gpu_model": "AMD Radeon Pro",
                "gpu_vendor": "AMD",
            }, "generic", "gpu_node"),
            ({
                "system_vendor": "Example Corp.",
                "product_name": "ARM Developer Kit",
                "architecture": "aarch64",
                "gpu_model": "NVIDIA GB10",
                "gpu_vendor": "NVIDIA",
                "dgx_name": "DGX Spark compatible",
            }, "edge", "gpu_node"),
            ({
                "system_vendor": "Example Corp.",
                "product_name": "ARM Developer Kit",
                "architecture": "aarch64",
                "gpu_model": "NVIDIA GB10",
                "gpu_vendor": "NVIDIA",
                "dgx_name": "DGX",
                "dgx_pretty_name": "Spark",
            }, "edge", "gpu_node"),
            ({
                "system_vendor": "Example Corp.",
                "product_name": "ARM Developer Kit",
                "architecture": "aarch64",
                "gpu_model": "NVIDIA GB10",
                "gpu_vendor": "NVIDIA",
                "dgx_name": "NVIDIA DGX Spark",
                "dgx_pretty_name": "DGX Spark",
            }, "edge", "gpu_node"),
        )

        for index, (report, expected_kind, expected_machine_type) in enumerate(cases):
            with self.subTest(index=index):
                device = Device(
                    hostname=f"not-spark-{index}",
                    kind="generic",
                    machine_type="unknown",
                )
                enrich_from_scan(device, report)
                self.assertEqual(device.kind, expected_kind)
                self.assertEqual(device.machine_type, expected_machine_type)

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

    def test_visible_reboot_action_forces_the_selected_reboot(self):
        device = Device(hostname="compute-01", transport="ssh", kind="server")
        device.capabilities = [SYSTEM_REBOOT]
        self.db.add(device)
        self.db.commit()

        runner = AsyncMock(return_value="job-1")
        with patch("backend.routers.operations.run_playbook", runner):
            result = asyncio.run(
                run_operation(
                    "system.reboot",
                    OperationRunRequest(device_ids=[device.id]),
                    self.db,
                    "admin",
                )
            )

        self.assertEqual(result["job_id"], "job-1")
        self.assertEqual(runner.await_args.kwargs["extra_vars"], {"force_reboot": True})

    def test_configured_reachy_exposes_and_runs_app_reset(self):
        device = Device(
            hostname="reachy-lab",
            endpoint="reachy-mini.local",
            transport="reachy_daemon",
            kind="robot",
            machine_type="unknown",
            ansible_user="pollen",
        )
        device.capabilities = [
            *initial_profile("reachy_daemon")["capabilities"],
            REACHY_APP_RESET,
        ]
        self.db.add(device)
        self.db.commit()

        operation_ids = {operation.id for operation in list_operations(self.db, "admin")}
        self.assertIn(REACHY_APP_RESET, operation_ids)

        runner = AsyncMock(return_value="job-reset")
        with patch("backend.routers.operations.run_playbook", runner):
            result = asyncio.run(
                run_operation(
                    REACHY_APP_RESET,
                    OperationRunRequest(device_ids=[device.id]),
                    self.db,
                    "admin",
                )
            )

        self.assertEqual(result["job_id"], "job-reset")
        self.assertEqual(runner.await_args.kwargs["playbook"], "reachy_app_reset.yml")
        self.assertEqual(runner.await_args.kwargs["hosts"], ["reachy-lab"])

    def test_reachy_ssh_setup_adds_reset_capability(self):
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
        payload = DeviceSshEnrollmentRequest(
            ssh_user="pollen",
            approval=DeviceKeyApproval(fingerprint="SHA256:" + "A" * 43),
        )

        with (
            patch("backend.routers.devices._verify_ssh_access"),
            patch("backend.routers.devices.encrypt_secret", return_value=None),
            patch("backend.routers.devices.regenerate_inventory"),
        ):
            response = configure_device_ssh(device.id, payload, self.db, "admin")

        self.assertEqual(response.ssh_user, "pollen")
        self.assertIn(REACHY_APP_RESET, response.capabilities)

    def test_runner_only_allows_dual_transport_reachy_for_reset_playbook(self):
        device = Device(
            hostname="reachy-lab",
            transport="reachy_daemon",
            ansible_user="pollen",
            kind="robot",
        )
        device.capabilities = [REACHY_APP_RESET]
        self.db.add(device)
        self.db.commit()

        hosts, targets = _resolve_targets(
            self.db,
            ["reachy-lab"],
            False,
            "reachy_app_reset.yml",
        )
        self.assertEqual(hosts, ["reachy-lab"])
        self.assertEqual(targets, ["reachy-lab"])
        with self.assertRaises(PlaybookRequestError):
            _resolve_targets(self.db, ["reachy-lab"], False, "host_facts.yml")

    def test_changing_reachy_endpoint_revokes_verified_ssh_access(self):
        device = Device(
            hostname="reachy-lab",
            endpoint="old-reachy.local",
            transport="reachy_daemon",
            ansible_user="pollen",
            kind="robot",
        )
        device.capabilities = [REACHY_APP_RESET]
        self.db.add(device)
        self.db.commit()

        with patch("backend.routers.devices.regenerate_inventory"):
            response = update_device(
                device.id,
                DeviceUpdate(endpoint="new-reachy.local"),
                self.db,
                "admin",
            )

        self.assertIsNone(response.ssh_user)
        self.assertNotIn(REACHY_APP_RESET, response.capabilities)

    def test_generic_update_cannot_bypass_reachy_ssh_verification(self):
        device = Device(
            hostname="reachy-lab",
            endpoint="reachy-mini.local",
            transport="reachy_daemon",
            kind="robot",
        )
        self.db.add(device)
        self.db.commit()

        with self.assertRaisesRegex(HTTPException, "verified Reachy SSH setup"):
            update_device(
                device.id,
                DeviceUpdate(ssh_user="pollen"),
                self.db,
                "admin",
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
