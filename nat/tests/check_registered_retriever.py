"""Run with the NAT runtime: python nat/tests/check_registered_retriever.py."""

import importlib.metadata
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import ValidationError

from fleet_rag.register import RerankedRetrieverConfig, reranked_retriever
from nat.retriever.models import Document, RetrieverOutput
from nat.builder.function import LambdaFunction


class RegisteredRetrieverTests(unittest.IsolatedAsyncioTestCase):
    async def test_entry_point_and_registered_function_execute_the_retrieval_chain(self):
        entries = [entry for entry in importlib.metadata.entry_points(group="nat.components") if entry.name == "fleet_rag"]
        self.assertEqual(len(entries), 1)
        entries[0].load()
        config = RerankedRetrieverConfig(retriever="fleet_retriever", topic="Docs", base_url="http://reranker/v1", top_k=1, candidate_k=40)
        retriever = SimpleNamespace(search=AsyncMock(return_value=RetrieverOutput(results=[
            Document(page_content="first", metadata={"source": "manual"}, document_id="1"),
            Document(page_content="second", metadata={"job_id": "job2"}, document_id="2"),
        ])))
        builder = SimpleNamespace(get_retriever=AsyncMock(return_value=retriever))
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
            "results": [{"index": 1, "relevance_score": 2}, {"index": 0, "relevance_score": 1}],
        })))
        with patch("fleet_rag.register.httpx.AsyncClient", return_value=client):
            async with reranked_retriever(config, builder) as info:
                function = LambdaFunction.from_info(config=config, info=info, instance_name="fleet_docs")
                result = await function.ainvoke({"query": "test"})
        self.assertIsInstance(result, RetrieverOutput)
        self.assertEqual(result.results[0].document_id, "2")
        self.assertEqual(result.results[0].metadata["job_id"], "job2")
        retriever.search.assert_awaited_once_with(query="test", top_k=40)

    def test_invalid_optional_settings_fail_at_validation(self):
        for values in ({"candidate_k": 0}, {"candidate_k": 513}, {"timeout": 0}, {"api_format": "chat"}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                RerankedRetrieverConfig(retriever="fleet_retriever", topic="Docs", base_url="http://reranker/v1", **values)


if __name__ == "__main__":
    unittest.main()
