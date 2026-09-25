import copy
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from nat.prepare_config import prepare_config
from nat import ingest


class NatConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load((Path(__file__).parents[1] / "nat" / "config.yml").read_text())

    def test_unconfigured_optional_mcp_integrations_are_removed(self):
        config = prepare_config(copy.deepcopy(self.config), {})
        self.assertNotIn("k8s_mcp_server", config["function_groups"])
        self.assertNotIn("unifi_mcp_server", config["authentication"])
        self.assertIn("fleet_job_logs", config["workflow"]["tool_names"])
        self.assertIn("dynamo_mcp_server", config["function_groups"])

    def test_configured_optional_integrations_are_preserved(self):
        env = {"KUBERNETES_MCP_SERVER": "http://example.test/mcp", "KUBERNETES_MCP_TOKEN": "test"}
        config = prepare_config(copy.deepcopy(self.config), env)
        self.assertIn("k8s_mcp_server", config["function_groups"])
        self.assertIn("k8s_mcp_server", config["authentication"])
        self.assertNotIn("unifi_mcp_server", config["function_groups"])

    def test_agent_supports_history_system_prompt_and_streaming(self):
        self.assertEqual(self.config["workflow"]["_type"], "tool_calling_agent")
        self.assertEqual(self.config["llms"]["fleet_llm"]["api_type"], "chat_completion")

    def test_prepared_config_preserves_the_canonical_system_prompt(self):
        config = prepare_config(copy.deepcopy(self.config), {})
        runtime_config = yaml.safe_load(yaml.safe_dump(config, sort_keys=False))
        self.assertEqual(runtime_config["workflow"]["system_prompt"], self.config["workflow"]["system_prompt"])

    def test_embedding_outage_leaves_empty_docs_collection_ready(self):
        collection = MagicMock(num_entities=0)
        def fail_embeddings(texts):
            collection.load.assert_called_once()
            raise RuntimeError("embedding service unavailable")
        with (
            patch.object(ingest, "wait_for_milvus"),
            patch.object(ingest, "EMBED_DIM", 2048),
            patch.object(ingest, "API_KEY", "test-key"),
            patch.object(ingest, "ensure_job_log_collection"),
            patch.object(ingest.utility, "has_collection", return_value=False),
            patch.object(ingest, "create_collection", return_value=collection),
            patch.object(ingest.os.path, "exists", return_value=True),
            patch.object(ingest, "load_and_split_docs", return_value=[{"text": "test guidance"}]),
            patch.object(ingest, "embed_texts", side_effect=fail_embeddings),
        ):
            with self.assertRaisesRegex(RuntimeError, "embedding service unavailable"):
                ingest.main()
        collection.insert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
