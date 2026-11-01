"""Registered retrieval wrappers: embed query, search Milvus, then rerank."""

from typing import Literal

import httpx
from pydantic import BaseModel, Field, SecretStr

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.component_ref import RetrieverRef
from nat.data_models.function import FunctionBaseConfig
from nat.retriever.models import RetrieverOutput

from .rerank import rerank_documents


class RerankedRetrieverConfig(FunctionBaseConfig, name="fleet_reranked_retriever"):
    retriever: RetrieverRef
    topic: str
    base_url: str
    api_key: SecretStr = SecretStr("")
    model_name: str = "nvidia/Nemotron-3.5-Rerank-8B-BF16"
    api_format: Literal["nim", "rerank"] = "rerank"
    candidate_k: int = Field(default=40, ge=1, le=512)
    top_k: int = Field(default=3, ge=1, le=512)
    timeout: float = Field(default=15, gt=0, le=120)


@register_function(config_type=RerankedRetrieverConfig)
async def reranked_retriever(config: RerankedRetrieverConfig, builder: Builder):
    retriever = await builder.get_retriever(config.retriever)

    class SearchInput(BaseModel):
        query: str = Field(description="The question to search for in the indexed evidence")

    async with httpx.AsyncClient(timeout=config.timeout, follow_redirects=False) as client:
        async def retrieve(query: str) -> RetrieverOutput:
            result = await retriever.search(query=query, top_k=max(config.top_k, config.candidate_k))
            documents = await rerank_documents(client, config, query, result.results)
            return RetrieverOutput(results=documents)

        yield FunctionInfo.from_fn(fn=retrieve, input_schema=SearchInput, description=config.topic)
