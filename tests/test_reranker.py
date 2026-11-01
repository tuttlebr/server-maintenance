import unittest
from types import SimpleNamespace

import httpx
from pydantic import BaseModel, SecretStr

from nat.fleet_rag.rerank import ranked_indices, rerank_documents


class Document(BaseModel):
    page_content: str
    metadata: dict
    document_id: str


class RerankerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = SimpleNamespace(
            base_url="http://reranker/v1/", model_name="model", api_key=SecretStr(""),
            api_format="rerank", top_k=1, timeout=15,
        )
        self.documents = [
            Document(page_content="first", metadata={"source": "manual", "heading": "Intro", "distance": 0.1}, document_id="a"),
            Document(page_content="second", metadata={"source": "job", "job_id": "job-2", "distance": 0.2}, document_id="b"),
        ]

    async def call(self, handler, documents=None):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await rerank_documents(client, self.config, "question", self.documents if documents is None else documents)

    async def test_rerank_uses_response_indices_preserves_metadata_and_limits_results(self):
        import json
        def handler(request):
            self.assertEqual(request.url.path, "/v1/rerank")
            self.assertNotIn("authorization", request.headers)
            self.assertEqual(json.loads(request.content)["documents"], ["first", "second"])
            return httpx.Response(200, json={"results": [
                {"index": 0, "relevance_score": -2}, {"index": 1, "relevance_score": 3},
            ]})
        result = await self.call(handler)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].document_id, "b")
        self.assertEqual(result[0].metadata["job_id"], "job-2")
        self.assertEqual(result[0].metadata["distance"], 0.2)
        self.assertEqual(result[0].metadata["rerank_score"], 3)
        self.assertNotIn("rerank_score", self.documents[1].metadata)

    async def test_nim_request_and_auth(self):
        import json
        self.config.api_format = "nim"
        self.config.api_key = SecretStr("dedicated")
        def handler(request):
            self.assertEqual(request.url.path, "/v1/ranking")
            self.assertEqual(request.headers["authorization"], "Bearer dedicated")
            payload = json.loads(request.content)
            self.assertEqual(payload["query"], {"text": "question"})
            self.assertEqual(payload["passages"], [{"text": "first"}, {"text": "second"}])
            return httpx.Response(200, json={"rankings": [{"index": 1, "logit": 1}, {"index": 0, "logit": 0}]})
        self.assertEqual((await self.call(handler))[0].document_id, "b")

    async def test_outage_and_malformed_responses_fall_back_to_vector_order(self):
        for status, payload in ((503, {}), (200, {}), (200, {"results": []}), (200, None)):
            with self.subTest(status=status, payload=payload):
                result = await self.call(lambda request: httpx.Response(status, json=payload))
                self.assertEqual(result, self.documents[:1])

    async def test_timeout_falls_back_and_empty_search_does_not_call_model(self):
        def timeout(request):
            raise httpx.ReadTimeout("secret provider detail")
        self.assertEqual(await self.call(timeout), self.documents[:1])
        def unexpected(request):
            self.fail("Empty search must not invoke reranker")
        self.assertEqual(await self.call(unexpected, []), [])

    def test_invalid_rankings_are_rejected(self):
        for rows in (
            [{"index": 0, "logit": 1}, {"index": 0, "logit": 2}],
            [{"index": -1, "logit": 1}, {"index": 1, "logit": 2}],
            [{"index": 0, "logit": float("nan")}, {"index": 1, "logit": 2}],
            [{"index": True, "logit": 1}, {"index": 0, "logit": 2}],
            [{"index": 0, "logit": 1}, {"index": 4, "logit": 2}],
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                ranked_indices({"rankings": rows}, 2, "nim")
