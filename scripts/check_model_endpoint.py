"""Run one synthetic inference check via the client installed in its Fleet container."""

import asyncio
import io
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError


class CheckFailed(Exception):
    """An operator-facing error safe to print without credentials or response bodies."""


def embeddings():
    from backend.config import settings
    from backend.services.job_log_indexer import _embed_texts

    if not (settings.embed_base_url or settings.ai_helper_base_url):
        return None
    try:
        (vector,) = _embed_texts(["The Moon orbits Earth."])
    except RuntimeError as exc:
        if isinstance(exc.__cause__, HTTPError):
            raise CheckFailed(f"HTTP {exc.__cause__.code}") from None
        raise
    except URLError as exc:
        raise CheckFailed(f"connection failed ({type(exc.reason).__name__})") from None
    except ValueError as exc:
        raise CheckFailed("invalid embedding response (check the returned vector and EMBED_DIM)") from exc
    return f"received one validated {len(vector)}-dimensional vector"


def parser():
    from PIL import Image, ImageDraw, ImageFont
    from backend.services.document_parser import ParserUnavailable, parse_document, parser_enabled

    if not parser_enabled():
        return None
    image = Image.new("RGB", (800, 240), "white")
    ImageDraw.Draw(image).text((64, 68), "ORBIT 724", fill="black", font=ImageFont.load_default(size=72))
    png = io.BytesIO()
    image.save(png, format="PNG")
    try:
        text = parse_document(png.getvalue(), ".png")
    except ParserUnavailable as exc:
        raise CheckFailed(str(exc)) from None
    if not re.search(r"\bORBIT\s+724\b", text, re.IGNORECASE):
        raise CheckFailed("parser response did not contain the text on the test image")
    return "read ORBIT 724 from the test image"


async def reranker():
    if not os.environ.get("RERANK_BASE_URL", "").strip():
        return None

    import httpx
    import yaml
    from fleet_rag.register import RerankedRetrieverConfig
    from fleet_rag.rerank import rerank_documents
    from nat.retriever.models import Document
    from prepare_config import prepare_config

    # The NAT entrypoint may still be ingesting docs when Compose reports it started.
    config = prepare_config(yaml.safe_load(Path("/app/config.yml").read_text()), os.environ)
    retriever = RerankedRetrieverConfig.model_validate(config["functions"]["fleet_docs"])
    documents = [
        Document(document_id="bread", page_content="Yeast makes bread dough rise.", metadata={}),
        Document(document_id="moon", page_content="The Moon is Earth's natural satellite.", metadata={}),
    ]

    async def check_status(response):
        if not response.is_success:
            raise CheckFailed(f"HTTP {response.status_code}")

    async with httpx.AsyncClient(timeout=retriever.timeout, event_hooks={"response": [check_status]}) as client:
        ranked = await rerank_documents(client, retriever, "What is Earth's natural satellite?", documents)
    if not ranked or any("rerank_score" not in doc.metadata for doc in ranked):
        raise CheckFailed("reranker unavailable or invalid response (Fleet used vector order)")
    if ranked[0].document_id != "moon":
        raise CheckFailed("the relevant passage did not rank first")
    return "ranked the relevant passage first"


def main(endpoint):
    try:
        if endpoint == "reranker":
            result = asyncio.run(reranker())
        else:
            result = {"embeddings": embeddings, "parser": parser}[endpoint]()
    except Exception as exc:
        # SDK exceptions can include API keys, full URLs, or upstream bodies.
        detail = str(exc) if isinstance(exc, CheckFailed) else type(exc).__name__
        print(f"FAIL {endpoint}: {detail}", file=sys.stderr)
        return 1
    if result is None:
        print(f"SKIP {endpoint}: no endpoint configured")
    else:
        print(f"PASS {endpoint}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
