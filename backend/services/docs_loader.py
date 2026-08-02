"""Loads DGX documentation and provides keyword-based section retrieval.

Used as a fallback when NeMo Agent Toolkit is not available.
"""

import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"

_sections: list[dict] = []


def _load_docs():
    """Load and split all markdown docs into sections at startup."""
    global _sections
    if _sections:
        return

    if not DOCS_DIR.exists():
        return

    for md_file in sorted(DOCS_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        source = _doc_title(text) or md_file.stem.replace("-", " ").title()

        # Split by ## headings
        parts = re.split(r"(?=^## )", text, flags=re.MULTILINE)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Extract heading
            lines = part.split("\n", 1)
            heading = lines[0].lstrip("#").strip() if lines[0].startswith("#") else "Introduction"
            content = lines[1].strip() if len(lines) > 1 else part
            if len(content) < 20:
                continue
            _sections.append({
                "source": source,
                "heading": heading,
                "content": part,
            })


def get_relevant_sections(query: str, max_chars: int = 30000) -> str:
    """Return doc sections most relevant to query, up to max_chars."""
    _load_docs()
    if not _sections:
        return ""

    query_terms = set(re.findall(r"\w+", query.lower()))

    scored = []
    for section in _sections:
        text_lower = (section["heading"] + " " + section["content"]).lower()
        text_terms = set(re.findall(r"\w+", text_lower))
        overlap = len(query_terms & text_terms)
        if overlap > 0:
            scored.append((overlap, section))

    scored.sort(key=lambda x: x[0], reverse=True)

    result_parts = []
    total = 0
    for _score, section in scored:
        entry = f"[{section['source']}] {section['heading']}\n{section['content']}"
        if total + len(entry) > max_chars:
            break
        result_parts.append(entry)
        total += len(entry)

    return "\n\n---\n\n".join(result_parts)


def _doc_title(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip() or None
    return None
