"""Omit unconfigured optional MCP integrations before NAT validates its config."""

import os
from pathlib import Path

import yaml


def prepare_config(config: dict, environ) -> dict:
    for name, prefix in (("k8s_mcp_server", "KUBERNETES"), ("unifi_mcp_server", "UNIFI")):
        if environ.get(f"{prefix}_MCP_SERVER", "").strip() and environ.get(f"{prefix}_MCP_TOKEN", "").strip():
            continue
        config.get("function_groups", {}).pop(name, None)
        config.get("authentication", {}).pop(name, None)
        workflow = config.get("workflow", {})
        if "tool_names" in workflow:
            workflow["tool_names"] = [tool for tool in workflow["tool_names"] if tool != name]
    return config


if __name__ == "__main__":
    config = prepare_config(yaml.safe_load(Path("config.yml").read_text()), os.environ)
    Path("/tmp/fleet-nat-config.yml").write_text(yaml.safe_dump(config, sort_keys=False))
