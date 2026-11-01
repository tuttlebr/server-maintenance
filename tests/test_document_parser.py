import asyncio
import base64
import io
import json
import unittest
from unittest.mock import patch

import httpx
from PIL import Image
import pypdfium2 as pdfium

from backend.services import document_parser as parser


def page_image():
    output = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(output, format="PNG")
    return output.getvalue()


def pdf_document(pages=2):
    output = io.BytesIO()
    with pdfium.PdfDocument.new() as document:
        for _ in range(pages):
            page = document.new_page(100, 100)
            page.close()
        document.save(output)
    return output.getvalue()


class DocumentParserTests(unittest.TestCase):
    def setUp(self):
        self.settings = patch.multiple(
            parser.settings, parser_base_url="http://parser/v1/", parser_api_key="",
            parser_model="nvidia/Nemotron-3.5-Parse", parser_api_format="openai",
            parser_max_pages=20, parser_timeout_seconds=100,
        )
        self.settings.start()
        self.addCleanup(self.settings.stop)

    def parse_with(self, handler, content=None, extension=".png"):
        client_type = httpx.AsyncClient
        def client_factory(**kwargs):
            return client_type(transport=httpx.MockTransport(handler), **kwargs)
        with patch.object(parser.httpx, "AsyncClient", side_effect=client_factory):
            return parser.parse_document(content or page_image(), extension)

    def test_openai_request_contains_image_model_and_control_prompt(self):
        def handler(request):
            self.assertEqual(request.url.path, "/v1/chat/completions")
            self.assertNotIn("authorization", request.headers)
            body = json.loads(request.content)
            self.assertEqual(body["model"], "nvidia/Nemotron-3.5-Parse")
            self.assertEqual(body["messages"][0]["content"][0]["text"], parser.TASK_PROMPT)
            self.assertTrue(body["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,"))
            return httpx.Response(200, json={"choices": [{"message": {"content": "# Maintenance\n\nCheck fans and airflow."}, "finish_reason": "stop"}]})
        result = self.parse_with(handler)
        self.assertIn("## Page 1", result)
        self.assertIn("Check fans and airflow.", result)

    def test_nim_multipart_request_and_pdf_page_order(self):
        self.calls = 0
        def handler(request):
            self.calls += 1
            self.assertEqual(request.url.path, "/v1/parse")
            self.assertEqual(request.headers["authorization"], "Bearer parser-key")
            self.assertIn("multipart/form-data", request.headers["content-type"])
            self.assertIn(b'name="document"', request.content)
            return httpx.Response(200, json={"content": f"Page content {self.calls}", "finish_reason": "stop"})
        with patch.multiple(parser.settings, parser_api_format="nim", parser_api_key="parser-key"):
            result = self.parse_with(handler, pdf_document(), ".pdf")
        self.assertEqual(self.calls, 2)
        self.assertLess(result.index("Page content 1"), result.index("Page content 2"))

    def test_layout_cleanup_keeps_table_content(self):
        text = "</s><s><x_0.1><y_0.2>\\begin{tabular}{ll}Fan & OK\\end{tabular}<x_0.8><y_0.9><class_Table><pad>"
        self.assertEqual(parser.readable_content(text), r"\begin{tabular}{ll}Fan & OK\end{tabular}")

    def test_nv_ingest_json_request_and_markdown_response(self):
        def handler(request):
            self.assertEqual(request.url.path, "/v1/parse")
            self.assertEqual(request.headers["authorization"], "Bearer parser-key")
            self.assertEqual(request.headers["content-type"], "application/json")
            body = json.loads(request.content)
            self.assertEqual(set(body), {"image"})
            with Image.open(io.BytesIO(base64.b64decode(body["image"], validate=True))) as image:
                self.assertEqual(image.format, "PNG")
            return httpx.Response(200, json={
                "markdown": "# Maintenance\n\nCheck fans and airflow.",
                "blocks": [], "warnings": [], "model": "nvidia/Nemotron-3.5-Parse",
            })
        with patch.multiple(parser.settings, parser_api_format="nv-ingest", parser_api_key="parser-key"):
            result = self.parse_with(handler)
        self.assertEqual(result, "## Page 1\n\n# Maintenance\n\nCheck fans and airflow.")

    def test_nv_ingest_rejects_failed_empty_and_malformed_responses(self):
        with patch.object(parser.settings, "parser_api_format", "nv-ingest"):
            for status, body in (
                (422, {"detail": "Page exceeds the parser output limit"}),
                (200, {"markdown": ""}),
                (200, {"markdown": None}),
                (200, {"markdown": ["invalid"]}),
                (200, {"markdown": "partial", "finish_reason": "length"}),
                (200, {"content": "wrong API format"}),
                (200, None),
            ):
                with self.subTest(status=status, body=body), self.assertRaises(parser.ParserUnavailable):
                    self.parse_with(lambda request: httpx.Response(status, json=body))

    def test_http_failures_report_status_without_leaking_upstream_details(self):
        with self.assertLogs(parser.logger, level="WARNING") as logs:
            with self.assertRaisesRegex(parser.ParserUnavailable, "HTTP 500 for page 1") as caught:
                self.parse_with(lambda request: httpx.Response(500, text="private upstream details"))
        self.assertIn("HTTP 500", logs.output[0])
        self.assertNotIn("private upstream details", str(caught.exception) + str(logs.output))

    def test_disabled_parser_rejects_before_rendering(self):
        with patch.object(parser.settings, "parser_base_url", " "), patch.object(parser, "render_pages") as render:
            with self.assertRaisesRegex(ValueError, "PARSER_BASE_URL"):
                parser.parse_document(b"file", ".pdf")
        render.assert_not_called()

    def test_invalid_pdf_and_too_many_pages_fail_before_inference(self):
        with self.assertRaisesRegex(ValueError, "invalid or password-protected"):
            parser.render_pages(b"not a pdf", ".pdf")
        with patch.object(parser.settings, "parser_max_pages", 1):
            with self.assertRaisesRegex(ValueError, "1–1 pages"):
                parser.render_pages(pdf_document(), ".pdf")

    def test_invalid_and_oversized_images_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid or too large"):
            parser.render_pages(b"not an image", ".png")
        with patch.object(parser, "MAX_IMAGE_PIXELS", 10), self.assertRaisesRegex(ValueError, "million pixels"):
            parser.render_pages(page_image(), ".png")

    def test_partial_malformed_empty_and_failed_responses_reject_upload(self):
        for status, body in (
            (503, {"secret": "private upstream error"}),
            (200, {"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]}),
            (200, {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]}),
            (200, {"choices": []}),
        ):
            with self.subTest(body=body), self.assertRaises(parser.ParserUnavailable) as caught:
                self.parse_with(lambda request: httpx.Response(status, json=body))
            self.assertNotIn("secret", str(caught.exception))

    def test_time_budget_and_concurrency_are_bounded(self):
        with patch.object(parser.time, "monotonic", side_effect=[0, 101]):
            with self.assertRaisesRegex(parser.ParserUnavailable, "timed out"):
                self.parse_with(lambda request: self.fail("Expired request must not be sent"))
        with patch.object(parser._PARSE_SLOTS, "acquire", return_value=False):
            with self.assertRaisesRegex(parser.ParserUnavailable, "busy"):
                parser.parse_document(page_image(), ".png")

    def test_total_deadline_interrupts_slow_responses(self):
        async def slow_response(request):
            await asyncio.sleep(1)
            self.fail("The total deadline must interrupt the response")
        with patch.object(parser.settings, "parser_timeout_seconds", 0.02):
            with self.assertRaises(parser.ParserUnavailable):
                self.parse_with(slow_response)

    def test_progress_counts_only_successful_pages_and_stops_at_failure(self):
        events = []
        calls = 0

        async def request(page, remaining):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise httpx.ReadTimeout("private request detail")
            return {"choices": [{"message": {"content": "Maintenance instructions for the fans."}, "finish_reason": "stop"}]}

        with patch.object(parser, "_request_page", side_effect=request):
            with self.assertRaisesRegex(parser.ParserUnavailable, "timed out for page 2"):
                parser.parse_document(pdf_document(), ".pdf", lambda *event: events.append(event))
        self.assertIn(("rendering", 0, 2), events)
        self.assertIn(("rendering", 2, 2), events)
        self.assertEqual([event for event in events if event[0] == "parsing"], [
            ("parsing", 0, 2), ("parsing", 1, 2),
        ])

    def test_long_model_budget_is_configurable_and_forwarded(self):
        from backend.config import Settings

        settings = Settings(_env_file=None, parser_timeout_seconds=1800)
        self.assertEqual(settings.parser_timeout_seconds, 1800)

        async def request(page, remaining):
            self.assertGreater(remaining, 1700)
            return {"choices": [{"message": {"content": "Maintenance instructions for the fans."}, "finish_reason": "stop"}]}

        with patch.object(parser.settings, "parser_timeout_seconds", 1800), patch.object(parser, "_request_page", side_effect=request):
            self.assertIn("Maintenance", parser.parse_document(page_image(), ".png"))
