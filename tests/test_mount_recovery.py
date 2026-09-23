"""Exercise mount recovery with real awk and isolated fstab/findmnt fixtures."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).parents[1]
ANSIBLE = shutil.which("ansible-playbook")
AWK = shutil.which("awk")
FSTAB = """# /etc/fstab: static file system information.
# These are the filesystems that are always mounted on boot.
   # override any of these by copying the appropriate line.
\t# <file system> <mount point> <type> <options> <dump> <pass>

/dev/root / ext4 defaults 0 1
/dev/data /srv/required ext4 defaults,errors=remount-ro 0 2
/dev/network /srv/network nfs defaults,_netdev 0 0
/swapfile swap swap defaults 0 0
/dev/manual /srv/manual ext4 noauto 0 0
/dev/removable /srv/removable ext4 defaults,nofail 0 0
/dev/optional /srv/optional ext4 defaults,nofail,rw 0 0
server:/share /srv/auto nfs x-systemd.automount,defaults 0 0
"""
MOUNTED = "/\n/srv/required\n/srv/network\n"


@pytest.mark.skipif(not ANSIBLE or not AWK, reason="ansible-playbook and awk are required")
@pytest.mark.parametrize("mounted,verify_rc,mounted_rc,expected_rc,expected_message", [
    (MOUNTED, 0, 0, 0, "All assertions passed"),
    ("/\n/srv/network\n", 0, 0, 2, "Required mounts are missing: /srv/required"),
    (MOUNTED, 1, 0, 2, "Invalid fstab fixture"),
    (MOUNTED, 0, 1, 2, "Mounted-filesystem query failed"),
])
def test_mount_recovery(tmp_path, mounted, verify_rc, mounted_rc, expected_rc, expected_message):
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    fstab = tmp_path / "fstab"
    fstab.write_text(FSTAB)
    # Execute the production awk program, substituting only the input file.
    awk = fakebin / "awk"
    awk.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "assert sys.argv[-1] == '/etc/fstab'\n"
        f"os.execv({AWK!r}, [{AWK!r}, *sys.argv[1:-1], {str(fstab)!r}])\n"
    )
    awk.chmod(0o700)
    findmnt = fakebin / "findmnt"
    findmnt.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "if sys.argv[1:] == ['--verify', '--tab-file', '/etc/fstab']:\n"
        f"    sys.stderr.write('Invalid fstab fixture' if {verify_rc} else '')\n"
        f"    sys.exit({verify_rc})\n"
        "assert sys.argv[1:] == ['-rno', 'TARGET']\n"
        f"sys.stdout.write({mounted!r})\n"
        f"sys.stderr.write('Mounted-filesystem query failed' if {mounted_rc} else '')\n"
        f"sys.exit({mounted_rc})\n"
    )
    findmnt.chmod(0o700)
    playbook = tmp_path / "mounts.yml"
    playbook.write_text(yaml.safe_dump([{
        "name": "Verify required mounts",
        "hosts": "localhost", "connection": "local", "gather_facts": False,
        "vars": {
            "ansible_python_interpreter": sys.executable,
            "ansible_facts": {"service_mgr": "test", "os_family": "test"},
        },
        "environment": {"PATH": f"{fakebin}:{os.environ.get('PATH', '')}"},
        "tasks": [{
            "name": "Run production health verification",
            "ansible.builtin.include_tasks": str(ROOT / "playbooks/tasks/verify_host_health.yml"),
        }],
    }]))
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\nretry_files_enabled = False\n")
    result = subprocess.run(
        [ANSIBLE, "-i", "localhost,", str(playbook)], capture_output=True, text=True, timeout=30,
        env={**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_NOCOLOR": "1"},
    )
    output = result.stdout + result.stderr
    assert result.returncode == expected_rc, output
    assert "changed=0" in result.stdout, output
    assert expected_message in output
