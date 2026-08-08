import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.routers import maintenance


SCRIPT_PATH = Path(__file__).parents[1] / "playbooks" / "files" / "storage_discovery.py"
SPEC = importlib.util.spec_from_file_location("storage_discovery", SCRIPT_PATH)
storage_discovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(storage_discovery)


class StorageDiscoveryTests(unittest.TestCase):
    def test_inventory_classifies_and_deduplicates_filesystems(self):
        mounts = [
            {
                "target": "/",
                "source": "/dev/sda2",
                "fstype": "ext4",
                "options": "rw",
                "maj:min": "8:2",
            },
            {
                "target": "/srv/root-bind",
                "source": "/dev/sda2",
                "fstype": "ext4",
                "options": "rw,bind",
                "maj:min": "8:2",
            },
            {
                "target": "/datasets",
                "source": "/dev/md0",
                "fstype": "xfs",
                "options": "rw",
                "maj:min": "9:0",
            },
            {
                "target": "/shared",
                "source": "nas.example:/exports/team",
                "fstype": "nfs4",
                "options": "rw",
                "maj:min": "0:52",
            },
            {
                "target": "/mnt/shared-alias",
                "source": "nas.example:/exports/team/",
                "fstype": "nfs4",
                "options": "rw",
                "maj:min": "0:83",
            },
            {
                "target": "/windows",
                "source": "//fileserver/engineering",
                "fstype": "cifs",
                "options": "rw",
                "maj:min": "0:61",
            },
            {
                "target": "/var/lib/kubelet/pods/volume",
                "source": "nas.example:/exports/team",
                "fstype": "nfs4",
                "options": "rw",
                "maj:min": "0:52",
            },
        ]
        usage = {
            target: {
                "total_mb": 1000,
                "used_mb": 500,
                "avail_mb": 500,
                "use_pct": 50,
            }
            for target in ("/", "/srv/root-bind", "/datasets", "/shared", "/mnt/shared-alias", "/windows")
        }

        with patch.object(storage_discovery, "filesystem_usage", side_effect=usage.get):
            inventory = storage_discovery.build_storage_inventory(mounts)

        self.assertEqual([item["mountpoint"] for item in inventory], ["/", "/datasets", "/shared", "/windows"])
        self.assertEqual([item["type"] for item in inventory], ["local", "raid", "nfs", "smb"])
        self.assertEqual(inventory[0]["mountpoints"], ["/", "/srv/root-bind"])
        self.assertEqual(inventory[2]["mountpoints"], ["/shared", "/mnt/shared-alias"])

    def test_proc_mountinfo_fallback_decodes_paths(self):
        line = "36 25 8:2 / /data\\040pool rw,relatime - ext4 /dev/sda2 rw\n"
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as mountinfo:
            mountinfo.write(line)
            mountinfo.flush()
            mounts = storage_discovery._mounts_from_proc(mountinfo.name)

        self.assertEqual(mounts[0]["target"], "/data pool")
        self.assertEqual(mounts[0]["major_minor"], "8:2")

    def test_normalized_mount_keeps_device_identity(self):
        normalized = storage_discovery._normalized_mount(
            {
                "target": "/data",
                "source": "/dev/sda2",
                "fstype": "ext4",
                "major_minor": "8:2",
            }
        )

        self.assertEqual(storage_discovery._filesystem_id(normalized), "device:8:2")


class StorageReportDeduplicationTests(unittest.TestCase):
    def test_mount_deduplication_merges_aliases(self):
        mounts = maintenance._dedupe_storage_mounts(
            [
                {
                    "filesystem_id": "device:8:2",
                    "mountpoint": "/",
                    "mountpoints": ["/"],
                },
                {
                    "filesystem_id": "device:8:2",
                    "mountpoint": "/srv/root-bind",
                },
                {
                    "filesystem_id": "nfs:nfs4:nas:/team",
                    "mountpoint": "/shared",
                },
            ]
        )

        self.assertEqual(len(mounts), 2)
        self.assertEqual(mounts[0]["mountpoints"], ["/", "/srv/root-bind"])

    def test_cached_reports_keep_only_newest_report_per_host(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            scan_dir = Path(temporary_dir) / "scans"
            scan_dir.mkdir()
            (scan_dir / "storage_old-name.json").write_text(
                json.dumps({"hostname": "node-01", "timestamp": "2026-08-01T00:00:00Z"})
            )
            (scan_dir / "storage_node-01.json").write_text(
                json.dumps({"hostname": "node-01", "timestamp": "2026-08-02T00:00:00Z"})
            )

            with patch.object(maintenance.settings, "data_dir", Path(temporary_dir)):
                reports = maintenance._read_cached_reports("storage")

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0][1]["timestamp"], "2026-08-02T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
