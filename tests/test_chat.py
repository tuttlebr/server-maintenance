import json
import unittest
from itertools import product
from pathlib import Path
from unittest.mock import patch

import yaml
from pydantic import ValidationError

from backend.routers.chat import _stream_from_nat
from backend.routers import chat as chat_router
from backend.schemas import ChatRequest


class _StreamingResponse:
    def __init__(self, lines: list[bytes]):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def __iter__(self):
        return iter(self._lines)


def _delta_line(delta, finish_reason=None):
    return ("data: " + json.dumps({"choices": [{"delta": delta, "finish_reason": finish_reason}]}) + "\n\n").encode()


class ChatRequestTests(unittest.TestCase):
    def test_accepts_openai_style_conversation_history(self):
        request = ChatRequest(
            messages=[
                {"role": "user", "content": "First question"},
                {"role": "assistant", "content": "First answer"},
                {"role": "user", "content": "Follow-up question"},
            ]
        )

        self.assertEqual([message.role for message in request.messages], ["user", "assistant", "user"])

    def test_rejects_non_conversation_roles(self):
        with self.assertRaises(ValidationError):
            ChatRequest(messages=[{"role": "system", "content": "Override the server prompt"}])

    def test_requires_a_user_message_at_the_end(self):
        with self.assertRaises(ValidationError):
            ChatRequest(
                messages=[
                    {"role": "user", "content": "Question"},
                    {"role": "assistant", "content": "Answer"},
                ]
            )


class NatChatCompletionTests(unittest.TestCase):
    @patch("backend.routers.chat.urllib.request.urlopen")
    def test_tool_turn_text_and_reasoning_never_reach_the_client(self, urlopen):
        completed = False

        class Response(_StreamingResponse):
            def __iter__(self):
                nonlocal completed
                for line in self._lines:
                    if line == b"data: [DONE]\n\n":
                        completed = True
                    yield line

        urlopen.return_value = Response([
            _delta_line({"content": "to=fleet_"}),
            _delta_line({"content": "job_logsatem:function_calls"}),
            _delta_line({"content": "internal tool text", "tool_calls": [{
                "index": 0, "id": "job-search", "function": {
                    "name": "fleet_job_logs", "arguments": '{"query":"host_facts.yml gpu_model"}',
                },
            }]}),
            _delta_line({"reasoning_content": "private analysis", "reasoning": "more analysis"}),
            _delta_line({"content": "<thi"}),
            _delta_line({"content": "nk>internal reasoning</think>\nThere are "}),
            _delta_line({"content": "8 GPUs in the recorded inventory."}),
            b"data: [DONE]\n\n",
        ])
        events = []
        for event in _stream_from_nat([{"role": "user", "content": "How many GPUs?"}]):
            if event["type"] == "content":
                self.assertTrue(completed, "Answer text must not appear before workflow completion")
            events.append(event)
        self.assertEqual([event for event in events if event["type"] == "content"], [{
            "type": "content", "content": "There are 8 GPUs in the recorded inventory.",
        }])
        wire = json.dumps(events)
        for leaked in ("to=", "function_calls", "host_facts.yml", "gpu_model", "internal", "private analysis", "more analysis"):
            self.assertNotIn(leaked, wire)
        self.assertIn({"type": "status", "text": "Searching indexed job history", "activity": "search"}, events)

    @patch("backend.routers.chat.urllib.request.urlopen")
    def test_unfinished_or_unparsed_tool_output_is_not_a_final_answer(self, urlopen):
        for text in ("", "to=fleet_job_logsatem:function_calls", "<function_calls><invoke name='fleet_docs'>", "<think>unfinished"):
            with self.subTest(text=text):
                urlopen.return_value = _StreamingResponse([_delta_line({"content": text}), b"data: [DONE]\n\n"])
                events = []
                with self.assertRaisesRegex(RuntimeError, "did not return a final answer"):
                    events.extend(_stream_from_nat([{"role": "user", "content": "Question"}]))
                self.assertFalse(any(event["type"] == "content" for event in events))

    def test_normal_answers_and_quoted_code_are_preserved(self):
        for text in ("The tool call failed. Check Activity.", '```xml\n<function_calls>example</function_calls>\n```'):
            self.assertEqual(chat_router._final_answer(text), text)

    @patch("backend.routers.chat.urllib.request.urlopen")
    def test_sends_and_parses_openai_chat_completion_stream(self, urlopen):
        chunk = {
            "id": "chatcmpl-test",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "Answer"},
                    "finish_reason": None,
                }
            ],
        }
        urlopen.return_value = _StreamingResponse(
            [
                f"data: {json.dumps(chunk)}\n\n".encode(),
                b"data: [DONE]\n\n",
            ]
        )
        messages = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Earlier answer"},
            {"role": "user", "content": "Follow-up"},
        ]

        with (
            patch("backend.routers.chat.settings.nat_base_url", "http://nat:8000"),
            patch("backend.routers.chat.settings.ai_helper_api_key", "test-key"),
            patch("backend.routers.chat.settings.ai_helper_model", "test-model"),
        ):
            events = list(_stream_from_nat(messages))

        sent_request = urlopen.call_args.args[0]
        payload = json.loads(sent_request.data)
        self.assertEqual(
            payload,
            {
                "model": "test-model",
                "messages": messages,
                "stream": True,
                "temperature": 0.3,
            },
        )
        self.assertEqual(events, [
            {"type": "status", "text": "Preparing response"},
            {"type": "content", "content": "Answer"},
        ])

    @patch("backend.routers.chat.urllib.request.urlopen")
    def test_nat_rounds_reuse_indexes_without_finish_markers(self, urlopen):
        # Mirrors NAT 1.9's tool_calling_agent stream: unique call IDs, reused
        # indexes, split arguments, and no finish_reason between agent rounds.
        urlopen.return_value = _StreamingResponse([
            _delta_line({"tool_calls": [{"index": 0, "id": "docs-1", "function": {
                "name": "fleet_docs", "arguments": '{"query":"storage',
            }}]}),
            _delta_line({"tool_calls": [{"index": 0, "function": {"arguments": ' checks"}'}}]}),
            _delta_line({"tool_calls": [{"index": 0, "id": "jobs-2", "function": {
                "name": "fleet_job_logs", "arguments": '{"query":"last storage job"}',
            }}]}),
            _delta_line({"tool_calls": [{"index": 0, "id": "docs-3", "function": {
                "name": "dynamo_mcp_server__searchDocs", "arguments": '{"query":"KV cache"}',
            }}]}),
            _delta_line({"content": "Answer"}),
            _delta_line({"content": " continues"}),
            b"data: [DONE]\n\n",
        ])
        events = list(_stream_from_nat([{"role": "user", "content": "Question"}]))
        statuses = [event["text"] for event in events if event["type"] == "status"]
        self.assertEqual(statuses, [
            "Preparing response",
            "Searching indexed knowledge sources",
            "Searching indexed job history",
            "Searching NVIDIA Dynamo documentation",
            "Preparing response",
        ])
        self.assertEqual("".join(event["content"] for event in events if event["type"] == "content"), "Answer continues")

    @patch("backend.routers.chat.urllib.request.urlopen")
    def test_parallel_tools_and_legacy_round_boundaries(self, urlopen):
        urlopen.return_value = _StreamingResponse([
            _delta_line({"content": "I'll check."}),
            _delta_line({"tool_calls": [
                {"index": 0, "function": {"name": "fleet_docs", "arguments": '{"query":'}},
                {"index": 1, "function": {"name": "fleet_job_logs", "arguments": '{"q":"history"}'}},
            ]}),
            _delta_line({"tool_calls": [{"index": 0, "function": {"arguments": '"guide"}'}}]}),
            _delta_line({}, "tool_calls"),
            _delta_line({"tool_calls": [{"index": 0, "function": {
                "name": "aiperf_mcp_server.searchDocs", "arguments": '[]',
            }}]}),
            _delta_line({"content": "Result"}),
            b"data: [DONE]\n\n",
        ])
        events = list(_stream_from_nat([{"role": "user", "content": "Question"}]))
        statuses = [event["text"] for event in events if event["type"] == "status"]
        self.assertIn('Searching indexed job history', statuses)
        self.assertIn('Searching indexed knowledge sources', statuses)
        self.assertIn("Searching NVIDIA AIPerf documentation", statuses)
        self.assertEqual(statuses.count("Preparing response"), 2)
        self.assertEqual([event for event in events if event["type"] == "content"], [{"type": "content", "content": "Result"}])
        self.assertEqual(events[-1], {"type": "content", "content": "Result"})

    def test_documentation_tools_have_readable_labels(self):
        for group, product_name in (
            ("dynamo", "Dynamo"), ("aiperf", "AIPerf"), ("nvcf", "Cloud Functions"), ("dsx", "DSX"),
        ):
            for separator in ("__", "."):
                with self.subTest(group=group, separator=separator):
                    self.assertEqual(chat_router._humanize_tool(f"{group}_mcp_server{separator}searchDocs"),
                                     f"Searching NVIDIA {product_name} documentation")
        self.assertEqual(chat_router._humanize_tool("new_tool"), "Checking a reference source")

    @patch("backend.routers.chat.urllib.request.urlopen")
    def test_surfaces_workflow_errors_embedded_in_a_stream(self, urlopen):
        urlopen.return_value = _StreamingResponse(
            [
                b'intermediate_data: {"type":"markdown"}\n\n',
                b'{"code":"workflow_error","message":"upstream rejected the request"}\n\n',
            ]
        )

        with (
            patch("backend.routers.chat.settings.nat_base_url", "http://nat:8000"),
            patch("backend.routers.chat.settings.ai_helper_api_key", "test-key"),
            patch("backend.routers.chat.settings.ai_helper_model", "test-model"),
        ):
            with self.assertRaisesRegex(RuntimeError, "upstream rejected the request"):
                list(_stream_from_nat([{"role": "user", "content": "Question"}]))


class DirectChatCompletionTests(unittest.TestCase):
    @patch("backend.routers.chat.urllib.request.urlopen")
    def test_direct_mode_hides_reasoning_and_releases_only_the_completed_answer(self, urlopen):
        with patch.object(chat_router.settings, "ai_helper_base_url", "http://provider.test"):
            urlopen.return_value = _StreamingResponse([
                _delta_line({"reasoning_content": "hidden"}),
                _delta_line({"content": "<analysis>hidden analysis</analysis>Hel"}),
                _delta_line({"content": "lo."}),
                b"data: [DONE]\n\n",
            ])
            events = list(chat_router._stream_from_llm([{"role": "user", "content": "Hello"}], "Hello"))
        self.assertEqual(events, [
            {"type": "status", "text": "Preparing response"},
            {"type": "content", "content": "Hello."},
        ])

    def test_social_turn_skips_reference_lookup_and_preserves_conversation(self):
        for query in ("Hello", " THANKS! ", "OK."):
            with (
                self.subTest(query=query),
                patch.object(chat_router.chat_prompt, "load_system_prompt", return_value="Shared policy"),
                patch.object(chat_router.docs_loader, "get_relevant_sections") as get_docs,
                patch.object(chat_router.context_manager, "get_relevant_context") as get_context,
                patch.object(chat_router.settings, "ai_helper_base_url", "https://example.test/v1"),
                patch.object(chat_router.settings, "ai_helper_api_key", "test-key"),
                patch.object(chat_router.settings, "ai_helper_model", "test-model"),
                patch.object(chat_router.urllib.request, "urlopen") as urlopen,
            ):
                urlopen.return_value = _StreamingResponse([_delta_line({"content": "Hello."}), b"data: [DONE]\n\n"])
                messages = [
                    {"role": "user", "content": "Why did the job fail?"},
                    {"role": "assistant", "content": "A device was unreachable."},
                    {"role": "user", "content": query},
                ]
                list(chat_router._stream_from_llm(messages, query))
                payload = json.loads(urlopen.call_args.args[0].data)
                self.assertEqual(payload["messages"], [
                    {"role": "system", "content": "Shared policy"}, *messages,
                ])
                get_docs.assert_not_called()
                get_context.assert_not_called()

    def test_uses_exact_nat_prompt_and_keeps_reference_data_in_current_user_turn(self):
        config = yaml.safe_load((Path(__file__).parents[1] / "nat" / "config.yml").read_text())
        messages = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "Earlier answer"},
            {"role": "user", "content": "<fleet_job_evidence>Job 123 failed</fleet_job_evidence>\nWhy?"},
        ]
        original = [message.copy() for message in messages]
        for docs, context in (("Guide with {literal braces}", "Uploaded reference"), ("", "")):
            with (
                self.subTest(docs=docs),
                patch.object(chat_router.docs_loader, "get_relevant_sections", return_value=docs) as get_docs,
                patch.object(chat_router.context_manager, "get_relevant_context", return_value=context) as get_context,
                patch.object(chat_router.settings, "ai_helper_base_url", "https://example.test/v1"),
                patch.object(chat_router.settings, "ai_helper_api_key", "test-key"),
                patch.object(chat_router.settings, "ai_helper_model", "test-model"),
                patch.object(chat_router.urllib.request, "urlopen") as urlopen,
            ):
                chunk = {"choices": [{"delta": {"content": "Answer"}}]}
                urlopen.return_value = _StreamingResponse([
                    f"data: {json.dumps(chunk)}\n\n".encode(), b"data: [DONE]\n\n",
                ])
                events = list(chat_router._stream_from_llm(messages, "Why?"))

            payload = json.loads(urlopen.call_args.args[0].data)
            self.assertEqual(payload["messages"][0], {
                "role": "system", "content": config["workflow"]["system_prompt"],
            })
            self.assertEqual([m["role"] for m in payload["messages"]], ["system", "user", "assistant", "user"])
            self.assertEqual(payload["messages"][1:-1], messages[:-1])
            latest = payload["messages"][-1]["content"]
            self.assertTrue(latest.startswith("<fleet_reference_context>\n"))
            self.assertTrue(latest.endswith(messages[-1]["content"]))
            if docs:
                self.assertIn(docs, latest)
                self.assertIn(context, latest)
                self.assertNotIn(docs, payload["messages"][0]["content"])
                self.assertNotIn(context, payload["messages"][0]["content"])
            else:
                self.assertIn("No matching reference context was found.", latest)
            self.assertNotIn("tools", payload)
            self.assertEqual(messages, original)
            self.assertEqual(events, [
                {"type": "status", "text": "Looking up local reference context"},
                {"type": "status", "text": "Preparing response"},
                {"type": "content", "content": "Answer"},
            ])
            get_docs.assert_called_once_with("Why?", max_chars=18000)
            get_context.assert_called_once_with("Why?", max_chars=18000)

    def test_config_error_prevents_sending_an_unprompted_request(self):
        with (
            patch.object(chat_router.chat_prompt, "load_system_prompt", side_effect=RuntimeError("Invalid prompt")),
            patch.object(chat_router.urllib.request, "urlopen") as urlopen,
        ):
            with self.assertRaisesRegex(RuntimeError, "Invalid prompt"):
                list(chat_router._stream_from_llm([{"role": "user", "content": "Question"}], "Question"))
        urlopen.assert_not_called()


class GroundedChatTests(unittest.IsolatedAsyncioTestCase):
    async def test_nat_tool_progress_reaches_the_client_after_context_preparation(self):
        with (
            patch.object(chat_router.settings, "nat_base_url", "http://nat:8000"),
            patch.object(chat_router, "_nat_available", return_value=True),
            patch.object(chat_router.job_context, "get_job_context", return_value="Recorded activity"),
            patch.object(chat_router.urllib.request, "urlopen") as urlopen,
        ):
            urlopen.return_value = _StreamingResponse([
                _delta_line({"tool_calls": [{"index": 0, "id": "docs-1", "function": {
                    "name": "fleet_docs", "arguments": '{"query":"storage"}',
                }}]}),
                _delta_line({"content": "Answer"}),
                b"data: [DONE]\n\n",
            ])
            response = await chat_router.chat(ChatRequest(messages=[{"role": "user", "content": "Explain storage checks"}]), user="admin")
            events = [chunk async for chunk in response.body_iterator]
        progress = [json.loads(chunk[6:])["text"] for chunk in events if chunk.startswith('data: {"type": "status"')]
        self.assertEqual(progress, [
            "Loading recent activity context", "Preparing response",
            "Searching indexed knowledge sources", "Preparing response",
        ])
        self.assertIn('"content": "Answer"', events[-2])
        self.assertEqual(events[-1], "event: done\ndata: {}\n\n")

    async def test_social_turns_skip_job_evidence_in_both_transports(self):
        for use_nat, query, with_history in product(
            (False, True), ("Hello", " Hi there! ", "Thanks", "OK.", "Good morning"), (False, True),
        ):
            with (
                self.subTest(use_nat=use_nat, query=query, with_history=with_history),
                patch.object(chat_router.settings, "nat_base_url", "http://nat:8000"),
                patch.object(chat_router, "_nat_available", return_value=use_nat),
                patch.object(chat_router.job_context, "get_job_context") as retrieve,
                patch.object(chat_router, "_stream_from_nat", return_value=iter([])) as nat,
                patch.object(chat_router, "_stream_from_llm", return_value=iter([])) as direct,
            ):
                history = [
                    {"role": "user", "content": "Why did the job fail?"},
                    {"role": "assistant", "content": "A device was unreachable."},
                ] if with_history else []
                request = ChatRequest(job_id="selected-job", device_id=1, messages=[
                    *history, {"role": "user", "content": query},
                ])
                response = await chat_router.chat(request, user="admin")
                events = "".join([chunk async for chunk in response.body_iterator])
                sent = (nat if use_nat else direct).call_args.args[0]
                self.assertEqual(sent, [m.model_dump() for m in request.messages])
                self.assertNotIn("Loading recent activity context", events)
                self.assertIn("event: done", events)
                retrieve.assert_not_called()

    async def test_both_transports_receive_fresh_job_evidence_and_history(self):
        for use_nat, query in product((False, True), (
            "Why did this fail?", "Hello, why did this fail?", "Thanks, which device failed?",
            "Why?", "Status?", "And the other device?", "OK, show the log",
        )):
            with (
                self.subTest(use_nat=use_nat, query=query),
                patch.object(chat_router.settings, "nat_base_url", "http://nat:8000"),
                patch.object(chat_router, "_nat_available", return_value=use_nat),
                patch.object(chat_router, "_direct_llm_available", return_value=True),
                patch.object(chat_router.job_context, "get_job_context", return_value="TASK [Check disk] FAILED disk full") as retrieve,
                patch.object(chat_router, "_stream_from_nat", return_value=iter([{"type": "content", "content": "NAT answer"}])) as nat,
                patch.object(chat_router, "_stream_from_llm", return_value=iter([{"type": "content", "content": "Direct answer"}])) as direct,
            ):
                request = ChatRequest(job_id="selected-job", device_id=1, messages=[
                    {"role": "user", "content": "First question"},
                    {"role": "assistant", "content": "Previous answer"},
                    {"role": "user", "content": query},
                ])
                response = await chat_router.chat(request, user="admin")
                events = "".join([chunk async for chunk in response.body_iterator])
                sent = (nat if use_nat else direct).call_args.args[0]
                self.assertEqual(sent[1]["content"], "Previous answer")
                self.assertIn("FAILED disk full", sent[-1]["content"])
                self.assertTrue(sent[-1]["content"].endswith(query))
                self.assertIn("event: done", events)
                self.assertIn("Loading recent activity context", events)
                retrieve.assert_called_once_with(
                    [m.model_dump() for m in request.messages], job_id="selected-job", device_id=1,
                )

    async def test_evidence_failure_is_disclosed_without_breaking_chat(self):
        with (
            patch.object(chat_router.settings, "nat_base_url", ""),
            patch.object(chat_router, "_direct_llm_available", return_value=True),
            patch.object(chat_router.job_context, "get_job_context", side_effect=RuntimeError("database unavailable")),
            patch.object(chat_router, "_stream_from_llm", return_value=iter([])) as direct,
            self.assertLogs(chat_router.logger, level="ERROR"),
        ):
            response = await chat_router.chat(ChatRequest(messages=[{"role": "user", "content": "Status?"}]), user="admin")
            events = "".join([chunk async for chunk in response.body_iterator])
        self.assertIn("Job evidence is unavailable", direct.call_args.args[0][-1]["content"])
        self.assertIn("event: done", events)


if __name__ == "__main__":
    unittest.main()
