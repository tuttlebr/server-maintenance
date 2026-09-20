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
    def test_every_top_level_playbook_is_ui_reachable(self):
        top_level = {path.name for path in PLAYBOOK_DIR.glob("*.yml")}
        direct = {operation.playbook for operation in OPERATIONS if operation.playbook}
        direct.update(ACCESS_PLAYBOOKS)
        reachable = set(direct)
        pending = list(direct)
        while pending:
            current = pending.pop()
            if current not in top_level:
                continue
            for imported in imported_playbooks(current):
                if imported not in reachable:
                    reachable.add(imported)
                    pending.append(imported)
        self.assertEqual(top_level, reachable)

    def test_runner_allowlist_matches_top_level_playbooks(self):
        top_level = {path.name for path in PLAYBOOK_DIR.glob("*.yml")}
        self.assertEqual(top_level, ALLOWED_PLAYBOOKS)

    def test_disruptive_new_operations_require_confirmation(self):
        operations = {operation.id: operation for operation in OPERATIONS}
        self.assertEqual(operations["system.update"].risk, "high")
        self.assertEqual(operations["system.bootstrap"].confirmation, "typed-target")
        self.assertEqual(operations["firmware.update"].confirmation, "typed-target")
        self.assertEqual(operations["firmware.inspect"].risk, "low")
        self.assertEqual(operations["reachy.apps.reset"].risk, "high")
        self.assertEqual(operations["reachy.apps.reset"].confirmation, "typed-target")

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
