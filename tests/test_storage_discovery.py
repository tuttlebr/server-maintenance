import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).parents[1] / "playbooks" / "files" / "storage_discovery.py"
SPEC = importlib.util.spec_from_file_location("storage_discovery", SCRIPT_PATH)
storage_discovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(storage_discovery)


class StorageDiscoveryTests(unittest.TestCase):
    def test_subprocess_output_works_with_python36_arguments(self):
        popen = subprocess.Popen

        # Python 3.6 has universal_newlines, but no text keyword on Popen.
        def python36_popen(argv, stdout, stderr, universal_newlines=False):
            return popen(argv, stdout=stdout, stderr=stderr, universal_newlines=universal_newlines)

        with patch.object(storage_discovery.subprocess, "Popen", side_effect=python36_popen):
            result = storage_discovery._run([sys.executable, "-c", "print('storage output')"], 5)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "storage output\n")

    def test_jetson_mmc_inventory_with_legacy_or_missing_tools(self):
        mountinfo = (
            "36 25 179:1 / / rw,relatime - ext4 /dev/mmcblk0p1 rw\n"
            "37 36 179:1 / /mnt/root-alias rw,relatime - ext4 /dev/mmcblk0p1 rw\n"
        )
        read_proc = storage_discovery._mounts_from_proc
        for findmnt_missing in (False, True):
            with self.subTest(findmnt_missing=findmnt_missing):
                def run(argv, **kwargs):
                    if argv[0] == "findmnt":
                        if findmnt_missing:
                            raise FileNotFoundError("findmnt unavailable")
                        return subprocess.CompletedProcess(argv, 1, "", "findmnt: unrecognized option '--json'")
                    if argv[:2] == ["df", "-Pk"]:
                        return subprocess.CompletedProcess(
                            argv, 0, "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
                            "/dev/mmcblk0p1 1048576 524288 524288 50% /\n",
                        )
                    if argv[0] == "lsblk":
                        raise FileNotFoundError("lsblk unavailable")
                    self.assertEqual(argv[:2], ["df", "-B1"])
                    return subprocess.CompletedProcess(argv, 1, "", "df: unrecognized option '--output'")

                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as fixture:
                    fixture.write(mountinfo)
                    fixture.flush()
                    with patch.object(storage_discovery.subprocess, "run", side_effect=run):
                        with patch.object(storage_discovery, "_mounts_from_proc", side_effect=lambda: read_proc(fixture.name)):
                            inventory = storage_discovery.build_storage_inventory(storage_discovery.discover_mounts())

                self.assertEqual(len(inventory), 1)
                self.assertEqual(inventory[0]["source"], "/dev/mmcblk0p1")
                self.assertEqual(inventory[0]["mountpoints"], ["/", "/mnt/root-alias"])
                self.assertEqual(inventory[0]["type"], "local")
                self.assertTrue(inventory[0]["accessible"])
                self.assertEqual(inventory[0]["total_mb"], 1024)
                self.assertEqual(inventory[0]["use_pct"], 50)

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


if __name__ == "__main__":
    unittest.main()
