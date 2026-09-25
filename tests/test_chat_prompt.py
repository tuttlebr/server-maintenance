import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from backend.services import chat_prompt


class ChatPromptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config_path = Path(self.temp.name) / "config.yml"
        self.enterContext(patch.object(chat_prompt, "NAT_CONFIG_PATH", self.config_path))

    def test_reads_edits_verbatim_without_formatting_or_resolving_environment(self):
        for prompt in ("Initial policy\n", "New policy with {docs} and ${MISSING_VARIABLE}\n"):
            self.config_path.write_text(yaml.safe_dump({
                "workflow": {"system_prompt": prompt},
                "authentication": {"key": "${UNSET_API_KEY}"},
            }), encoding="utf-8")
            self.assertEqual(chat_prompt.load_system_prompt(), prompt)

    def test_missing_or_unreadable_config_has_no_alternate_policy(self):
        with self.assertRaisesRegex(RuntimeError, "Could not read.*nat/config.yml"):
            chat_prompt.load_system_prompt()
        self.config_path.mkdir()
        with self.assertRaisesRegex(RuntimeError, "Could not read.*nat/config.yml"):
            chat_prompt.load_system_prompt()

    def test_invalid_yaml_does_not_expose_config_contents(self):
        self.config_path.write_text("workflow: [sensitive-config-value", encoding="utf-8")
        with self.assertRaises(RuntimeError) as caught:
            chat_prompt.load_system_prompt()
        self.assertNotIn("sensitive-config-value", str(caught.exception))

    def test_requires_a_nonempty_string_prompt(self):
        for config in (None, [], {}, {"workflow": []}, {"workflow": {}}, *(
            {"workflow": {"system_prompt": value}} for value in (None, "", " \n", 1, [], {})
        )):
            with self.subTest(config=config):
                self.config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "non-empty workflow.system_prompt"):
                    chat_prompt.load_system_prompt()


if __name__ == "__main__":
    unittest.main()
