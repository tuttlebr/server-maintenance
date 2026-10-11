import unittest
from pathlib import Path

import yaml

from backend.capabilities import OPERATIONS
from backend.services.ansible_runner import ALLOWED_PLAYBOOKS


ROOT = Path(__file__).parents[1]
PLAYBOOK_DIR = ROOT / "playbooks"
ACCESS_PLAYBOOKS = {
    "access_inspect.yml",
    "bulk_password_reset.yml",
    "change_password.yml",
    "manage_sudoers.yml",
    "remove_sudoers.yml",
    "remove_user.yml",
    "user_management.yml",
}


def imported_playbooks(playbook_name: str) -> set[str]:
    document = yaml.safe_load((PLAYBOOK_DIR / playbook_name).read_text()) or []
    return {
        Path(item["import_playbook"]).name
        for item in document
        if isinstance(item, dict) and item.get("import_playbook")
    }


class PlaybookCoverageTests(unittest.TestCase):
    def test_public_operations_are_limited_to_requested_maintenance(self):
        self.assertEqual({op.id for op in OPERATIONS}, {"system.packages.preview", "system.update", "containers.cleanup", "system.reboot", "storage.inspect", "gpu.inspect", "reachy.daemon.restart"})
        self.assertEqual({op.playbook for op in OPERATIONS if op.playbook}, {"package_preview.yml", "system_update.yml", "docker_cleanup.yml", "reboot.yml", "storage_analysis.yml", "gpu_usage.yml"})

    def test_service_workflows_have_no_cluster_api_or_scheduling_dependency(self):
        visited = set()

        def inspect(path):
            if path in visited:
                return
            visited.add(path)
            document = yaml.safe_load(path.read_text())

            def walk(value):
                if isinstance(value, list):
                    for item in value:
                        walk(item)
                elif isinstance(value, dict):
                    self.assertFalse(any(key.startswith('kubernetes.core.') for key in value), path)
                    for key, item in value.items():
                        if key in {'ansible.builtin.include_tasks', 'ansible.builtin.import_tasks', 'import_playbook'}:
                            inspect(path.parent / (item if isinstance(item, str) else item['file']))
                        else:
                            walk(item)
            walk(document)

        for playbook in ['package_preview.yml', 'system_update.yml', 'docker_cleanup.yml', 'recovery_check.yml', 'host_facts.yml', 'reboot.yml']:
            inspect(PLAYBOOK_DIR / playbook)

    def test_runner_allowlist_matches_top_level_playbooks(self):
        top_level = {path.name for path in PLAYBOOK_DIR.glob("*.yml")}
        self.assertEqual(top_level, ALLOWED_PLAYBOOKS)

    def test_disruptive_new_operations_require_confirmation(self):
        operations = {operation.id: operation for operation in OPERATIONS}
        self.assertEqual(operations["system.update"].risk, "high")
        self.assertEqual(operations["system.update"].confirmation, "confirm")
        self.assertEqual(operations["containers.cleanup"].confirmation, "confirm")
        self.assertEqual(operations["system.reboot"].risk, "high")
        self.assertEqual(operations["system.reboot"].confirmation, "confirm")
        self.assertEqual(operations["system.packages.preview"].confirmation, "none")

    def test_reachy_reset_is_fixed_to_the_app_environment(self):
        content = (PLAYBOOK_DIR / "reachy_app_reset.yml").read_text()
        self.assertIn("reachy_apps_venv_path: /venvs/apps_venv", content)
        self.assertIn("path: /venvs/mini_daemon", content)
        self.assertIn("state: absent", content)
        self.assertNotIn("rm -rf", content)

    def test_driver_action_does_not_run_a_full_system_upgrade(self):
        content = (PLAYBOOK_DIR / "driver_upgrade.yml").read_text()
        self.assertNotIn("upgrade: full", content)
        self.assertNotIn("upgrade: dist", content)
        self.assertNotIn("fwupdmgr upgrade", content)

    def test_bulk_reset_uses_system_uid_bounds(self):
        content = (PLAYBOOK_DIR / "bulk_password_reset.yml").read_text()
        self.assertIn("UID_MIN", content)
        self.assertIn("UID_MAX", content)
        self.assertIn("nobody", content)


if __name__ == "__main__":
    unittest.main()
