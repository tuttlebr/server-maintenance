"""Chat router — proxies to NeMo Agent Toolkit or falls back to direct LLM."""

import asyncio
import json
import logging
import re
import threading
import urllib.error
import urllib.request

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from backend.auth import get_current_user
from backend.config import settings
from backend.schemas import ChatRequest
from backend.services import chat_prompt, context_manager, docs_indexer, docs_loader, job_context

router = APIRouter(prefix="/api/v2/chat", tags=["assistant"])
logger = logging.getLogger(__name__)

# Human-readable labels for the agent's tool calls. Extend as new tools are added.
TOOL_STATUS = {
    "fleet_docs": "Searching indexed knowledge sources",
    "fleet_job_logs": "Searching indexed job history",
    "dynamo_mcp_server__searchDocs": "Searching NVIDIA Dynamo documentation",
    "aiperf_mcp_server__searchDocs": "Searching NVIDIA AIPerf documentation",
    "nvcf_mcp_server__searchDocs": "Searching NVIDIA Cloud Functions documentation",
    "dsx_mcp_server__searchDocs": "Searching NVIDIA DSX documentation",
}


def _is_social_turn(query: str) -> bool:
    """Skip automatic context only for unambiguous standalone social messages."""
    text = " ".join(query.casefold().split()).strip(".! ")
    return text in {
        "hi", "hello", "hey", "hi there", "hello there", "hey there",
        "good morning", "good afternoon", "good evening",
        "thanks", "thank you", "thanks a lot", "ok", "okay", "got it",
        "bye", "goodbye",
    }


def _humanize_tool(name: str) -> str:
    return TOOL_STATUS.get(name.replace(".", "__"), "Checking a reference source")


def _final_answer(text: str) -> str:
    """Remove explicit leading reasoning envelopes and reject raw tool routing."""
    text = text.strip()
    while re.match(r"^<(think|analysis)>", text):
        reasoning = re.match(r"^<(think|analysis)>.*?</\1>\s*", text, re.DOTALL)
        if not reasoning:
            raise RuntimeError("Fleet Help did not return a final answer. Please retry.")
        text = text[reasoning.end():]
    if not text or re.match(r"^(?:to=[\w.-]+|</?(?:tool_call|function_calls|invoke)(?:\s|>))", text):
        raise RuntimeError("Fleet Help did not return a final answer. Please retry.")
    return text


def _nat_available() -> bool:
    """Check if NAT is reachable."""
    if not settings.nat_base_url:
        return False
    try:
        url = settings.nat_base_url.rstrip("/") + "/health"
        with urllib.request.urlopen(url, timeout=3):
            pass
        return True
    except Exception:
        return False


def _direct_llm_available() -> bool:
    return bool(
        settings.ai_helper_api_key
        and settings.ai_helper_model
        and settings.ai_helper_base_url
    )


@router.get("/status")
def chat_status(user: str = Depends(get_current_user)):
    if settings.nat_base_url:
        if _nat_available():
            return {"available": True, "mode": "nat"}
    if _direct_llm_available():
        return {"available": True, "mode": "direct"}
    return {"available": False, "mode": "none"}


def _completion_chunks(response):
    """Both providers must acknowledge completion; EOF alone is not success."""
    for raw_line in response:
        line = raw_line.decode("utf-8").strip()
        if not line or line.startswith((":", "event:", "id:", "retry:", "intermediate_data:")):
            continue
        data = line[5:].lstrip() if line.startswith("data:") else line
        if data == "[DONE]":
            return
        try:
            chunk = json.loads(data)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Chat provider returned invalid stream data") from exc
        if not isinstance(chunk, dict):
            raise RuntimeError("Chat provider returned an invalid response")
        if chunk.get("error") or chunk.get("code") == "workflow_error":
            error = chunk.get("error")
            message = error.get("message") if isinstance(error, dict) else error
            raise RuntimeError(f"Chat provider failed: {message or chunk.get('message') or 'Unknown error'}")
        yield chunk
    raise RuntimeError("Chat provider disconnected before completion. Please retry.")


def _stream_from_nat(messages: list[dict]):
    """Stream chat completions from NeMo Agent Toolkit.

    Yields dicts that the SSE endpoint forwards to the client:
      - Status events for requested searches, without raw names or arguments.
      - Final answer text only after the workflow acknowledges completion.
    """
    url = settings.nat_base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": settings.ai_helper_model,
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
    }
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

    # NAT 1.9 reuses indexes across agent rounds without emitting tool_calls
    # finish markers. A new call ID starts fresh state even at the same index.
    tool_state: dict[int, dict] = {}
    answer_parts: list[str] = []
    preparing = True

    yield {"type": "status", "text": "Preparing response"}
    with urllib.request.urlopen(req, timeout=120) as resp:
        for chunk in _completion_chunks(resp):
            try:
                choice = chunk.get("choices", [{}])[0]
                delta = choice.get("delta", {})

                tool_calls = delta.get("tool_calls") or []
                if tool_calls:
                    # NAT mixes every agent turn into one stream without turn
                    # boundaries. Text preceding a tool call is not the final
                    # answer and must never reach the browser or chat history.
                    answer_parts.clear()
                for tc in tool_calls:
                    idx = tc.get("index", 0)
                    state = tool_state.get(idx)
                    if state is None or (tc.get("id") and tc["id"] != state["id"]):
                        state = {"id": tc.get("id"), "name": None, "announced": False}
                        tool_state[idx] = state
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        state["name"] = fn["name"]
                    # Announce the call as soon as we know the tool name.
                    if state["name"] and not state["announced"]:
                        state["announced"] = True
                        preparing = False
                        yield {"type": "status", "text": _humanize_tool(state["name"]), "activity": "search"}

                if choice.get("finish_reason") == "tool_calls":
                    tool_state.clear()

                content = delta.get("content")
                if isinstance(content, str) and content and not tool_calls:
                    if not preparing:
                        preparing = True
                        yield {"type": "status", "text": "Preparing response"}
                    answer_parts.append(content)

            except (json.JSONDecodeError, IndexError, KeyError):
                continue

    answer = _final_answer("".join(answer_parts))
    yield {"type": "content", "content": answer}


def _stream_from_llm(messages: list[dict], query: str):
    """Stream chat completions from AI Helper with docs context.

    Emits the same {"type": ...} envelope shape as _stream_from_nat so the
    SSE endpoint can forward both paths uniformly.
    """
    system_msg = chat_prompt.load_system_prompt()
    grounded_messages = messages
    if not _is_social_turn(query):
        yield {"type": "status", "text": "Looking up local reference context"}
        docs_context = "\n\n---\n\n".join(
            filter(
                None,
                [
                    docs_loader.get_relevant_sections(query, max_chars=18000),
                    context_manager.get_relevant_context(query, max_chars=18000),
                ],
            )
        )
        # Reference data belongs to this user turn, never to the shared system policy.
        grounded_messages = messages[:-1] + [{
            **messages[-1],
            "content": (
                "<fleet_reference_context>\n"
                + (docs_context or "No matching reference context was found.")
                + "\n</fleet_reference_context>\n\n"
                + messages[-1]["content"]
            ),
        }]
    full_messages = [{"role": "system", "content": system_msg}] + grounded_messages

    url = settings.ai_helper_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.ai_helper_model,
        "messages": full_messages,
        "stream": True
    }
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
    yield {"type": "status", "text": "Preparing response"}
    answer_parts: list[str] = []
    with urllib.request.urlopen(req, timeout=120) as resp:
        for chunk in _completion_chunks(resp):
            try:
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if isinstance(content, str) and content:
                    answer_parts.append(content)
            except (json.JSONDecodeError, IndexError, KeyError):
                continue
    yield {"type": "content", "content": _final_answer("".join(answer_parts))}


@router.post("")
async def chat(body: ChatRequest, user: str = Depends(get_current_user)):
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    query = messages[-1]["content"] if messages else ""

    use_nat = settings.nat_base_url and await asyncio.to_thread(_nat_available)

    def produce_events():
        try:
            grounded_messages = messages
            if not _is_social_turn(query):
                yield {"type": "status", "text": "Loading recent activity context"}
                try:
                    evidence = job_context.get_job_context(
                        messages, job_id=body.job_id, device_id=body.device_id,
                    )
                except Exception:
                    logger.exception("Could not load job evidence for chat")
                    evidence = "Job evidence is unavailable for this request."
                grounded_messages = messages[:-1] + [{
                    "role": "user",
                    "content": (
                        "<fleet_job_evidence>\n" + evidence + "\n</fleet_job_evidence>\n\n"
                        "User question:\n" + query
                    ),
                }]
            generator = _stream_from_nat(grounded_messages) if use_nat else _stream_from_llm(grounded_messages, query)
            # yield-from propagates close() to the provider on disconnect.
            yield from generator
        except Exception as exc:
            yield {"type": "error", "message": str(exc)}

    async def event_stream():
        producer = produce_events()
        stopped = threading.Event()
        producer_lock = threading.Lock()
        finished = object()

        def next_event():
            with producer_lock:
                if stopped.is_set():
                    return finished
                try:
                    return next(producer, finished)
                finally:
                    # Cancellation may arrive during a blocking provider read.
                    # The worker that owns the generator closes it when that
                    # read returns, without consuming another event.
                    if stopped.is_set():
                        producer.close()

        try:
            # Read only when the client consumes an event. No detached producer
            # or unbounded queue survives a disconnected or slow client.
            while True:
                item = await run_in_threadpool(next_event)
                if item is finished:
                    break
                yield f"data: {json.dumps(item)}\n\n"
                if item.get("type") == "error":
                    return
            yield "event: done\ndata: {}\n\n"
        finally:
            stopped.set()
            if producer_lock.acquire(blocking=False):
                try:
                    producer.close()
                finally:
                    producer_lock.release()

    if not use_nat and not _direct_llm_available():
        raise HTTPException(status_code=503, detail="Chat is not configured. Set AI_HELPER or NAT_BASE_URL environment variables.")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# --- Documentation index management ---

@router.get("/index-status")
def index_status(user: str = Depends(get_current_user)):
    """Current state of the docs index (entity count, last reindex, progress)."""
    return docs_indexer.get_status()


@router.post("/reindex-docs")
def reindex_docs(user: str = Depends(get_current_user)):
    """Trigger a fresh reindex of the docs collection. Returns 409 if one is running."""
    started = docs_indexer.start_reindex()
    if not started:
        raise HTTPException(status_code=409, detail="A reindex is already in progress")
    return {"detail": "Reindex started"}
