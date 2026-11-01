"""Resolve optional integrations before NAT validates its config."""

import os
from pathlib import Path

import yaml


def prepare_config(config: dict, environ) -> dict:
    # An explicit endpoint opts in. Model defaults alone must never enable calls.
    base_url = environ.get("RERANK_BASE_URL", "").strip().rstrip("/")
    if base_url:
        for name in ("fleet_docs", "fleet_job_logs"):
            function = config["functions"][name]
            retriever = config["retrievers"][function["retriever"]]
            function.update(
                _type="fleet_reranked_retriever",
                base_url=base_url,
                api_key=environ.get("RERANK_API_KEY", "").strip(),
                model_name=environ.get("RERANK_MODEL", "").strip() or "nvidia/Nemotron-3.5-Rerank-8B-BF16",
                api_format=environ.get("RERANK_API_FORMAT", "").strip() or "rerank",
                candidate_k=int(environ.get("RERANK_CANDIDATE_K") or 40),
                top_k=retriever["top_k"],
                timeout=float(environ.get("RERANK_TIMEOUT_SECONDS") or 15),
            )
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
    path = Path("/tmp/fleet-nat-config.yml")
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(yaml.safe_dump(config, sort_keys=False))
