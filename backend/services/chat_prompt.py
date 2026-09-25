"""Load the shared Fleet Help policy without resolving unrelated NAT settings."""

from pathlib import Path

import yaml


NAT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "nat" / "config.yml"


def load_system_prompt() -> str:
    """Read the canonical prompt on each request; never substitute a second policy."""
    try:
        config = yaml.safe_load(NAT_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        # YAML errors can include source text; keep config contents out of SSE.
        raise RuntimeError("Could not read the Fleet Help system prompt from nat/config.yml") from exc

    workflow = config.get("workflow") if isinstance(config, dict) else None
    prompt = workflow.get("system_prompt") if isinstance(workflow, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        raise RuntimeError("nat/config.yml must define a non-empty workflow.system_prompt")
    return prompt
