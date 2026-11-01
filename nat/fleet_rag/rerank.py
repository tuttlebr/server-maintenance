"""HTTP reranking with strict index validation and metadata preservation."""

import asyncio
import logging
import math

import httpx

logger = logging.getLogger(__name__)


def ranked_indices(payload: dict, count: int, api_format: str) -> list[tuple[int, float]]:
    rows = payload.get("rankings" if api_format == "nim" else "results")
    if not isinstance(rows, list) or len(rows) != count:
        raise ValueError("Reranker must return one score per candidate")
    ranking = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid reranker result")
        index = row.get("index")
        score = row.get("logit" if api_format == "nim" else "relevance_score")
        if type(index) is not int or not 0 <= index < count or index in seen:
            raise ValueError("Invalid or duplicate reranker index")
        if type(score) not in (int, float) or not math.isfinite(score):
            raise ValueError("Invalid reranker score")
        seen.add(index)
        ranking.append((index, float(score)))
    return sorted(ranking, key=lambda item: (-item[1], item[0]))


async def rerank_documents(client, config, query, documents):
    """Return original document objects in score order, or vector order on failure."""
    if not documents:
        return []
    texts = [document.page_content for document in documents]
    body = {"model": config.model_name}
    if config.api_format == "nim":
        body.update(query={"text": query}, passages=[{"text": text} for text in texts], truncate="END")
    else:
        body.update(query=query, documents=texts, top_n=len(texts))
    headers = {"Authorization": f"Bearer {config.api_key.get_secret_value()}"} if config.api_key.get_secret_value() else {}
    try:
        path = "/ranking" if config.api_format == "nim" else "/rerank"
        async with asyncio.timeout(config.timeout):
            response = await client.post(config.base_url.rstrip("/") + path, json=body, headers=headers)
        response.raise_for_status()
        ranking = ranked_indices(response.json(), len(documents), config.api_format)
    except (TimeoutError, httpx.HTTPError, ValueError, TypeError, AttributeError):
        # Never log response bodies, queries, URLs, or credentials.
        logger.warning("Reranking unavailable; returning vector-search order")
        return documents[:config.top_k]
    return [
        documents[index].model_copy(update={
            "metadata": {**documents[index].metadata, "rerank_score": score},
        })
        for index, score in ranking[:config.top_k]
    ]
