import json
import urllib.request
import urllib.error

from backend.config import settings

ERROR_PROMPT = """You are an expert Ansible and Linux systems administrator analyzing failed automation jobs on NVIDIA DGX systems (DGX Spark and DGX Workstation).

Given an Ansible playbook error output, provide a concise analysis in exactly this JSON format:
{
  "error_summary": "One sentence describing what went wrong",
  "nodes_affected": "Comma-separated list of hostnames that failed",
  "recommended_action": "Clear, actionable steps to resolve the issue",
  "additional_information": "Any relevant context about the error (common causes, NVIDIA-specific notes, etc.)"
}

Keep each field concise — under 200 characters for summary and nodes, under 500 for recommended_action and additional_information. Be specific and actionable, not generic."""

SUCCESS_PROMPT = """You are an expert Ansible and Linux systems administrator analyzing completed automation jobs on NVIDIA DGX systems (DGX Spark and DGX Workstation).

Given a successful Ansible playbook output, provide a concise summary in exactly this JSON format:
{
  "summary": "One sentence describing what was accomplished",
  "nodes_affected": "Comma-separated list of hostnames that were changed",
  "changes_made": "Concise description of the key changes applied",
  "additional_information": "Any notable observations — skipped tasks, warnings, items worth monitoring, or follow-up recommendations"
}

Keep each field concise — under 200 characters for summary and nodes, under 500 for changes_made and additional_information. Focus on what actually changed, not what was skipped or already in the desired state."""


def is_configured() -> bool:
    return bool(settings.ai_helper_api_key and settings.ai_helper_model and settings.ai_helper_base_url)


def analyze_job(playbook: str, output: str, recap: str | None = None, status: str = "failed") -> dict | None:
    """Call the AI helper to analyze a job. Returns parsed analysis dict or None on failure."""
    if not is_configured():
        return None

    system_prompt = ERROR_PROMPT if status == "failed" else SUCCESS_PROMPT

    user_content = f"Playbook: {playbook}\nStatus: {status}\n\n"
    if recap:
        user_content += f"PLAY RECAP:\n{recap}\n\n"
    user_content += f"Output (last 3000 chars):\n{output[-3000:]}"

    payload = {
        "model": settings.ai_helper_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
    }

    url = settings.ai_helper_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.ai_helper_api_key}",
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        content = data["choices"][0]["message"]["content"]

        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        return json.loads(content)
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError):
        return None
