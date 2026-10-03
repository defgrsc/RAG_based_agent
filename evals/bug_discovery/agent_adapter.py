from __future__ import annotations

import ast
import io
import logging
import re
import time
from contextlib import redirect_stdout
from typing import Any, Protocol

import requests
from fastapi import HTTPException

from agent.graph import prepare_agent_context
from agent.state import history_for_legacy_functions
from agent.topics import ensure_topic_in_query, focus_message_on_topic
from evals.bug_discovery.schemas import AgentSettings, AgentTrace, RetrievedDocument


REFERENCE_MARKERS = (
    "第一", "第二", "第三", "前面", "剛才", "剛剛", "回到", "上一題",
    "那題", "那個問題", "previous", "earlier", "first question",
)
REFUSAL_MARKERS = (
    "無法回答", "資料不足", "無法提供", "不能回答", "僅提供", "不在服務範圍",
    "抱歉，本客服", "目前無法根據", "可靠回答",
    "i cannot answer", "i can't answer", "insufficient information",
)
CLARIFICATION_MARKERS = (
    "請問你指", "請補充", "請提供", "想問的是", "哪一個問題", "找不到",
    "無法判斷你指", "could you clarify", "please clarify", "which question",
)

INTENT_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "troubleshooting",
        (
            "連不上", "上不了網", "不能用", "無法", "失敗", "故障", "異常", "斷線", "很慢",
            "不穩", "載不出來", "載不動", "動不了", "轉圈", "轉不出來", "not working", "cannot connect", "can't connect", "failed", "slow",
        ),
    ),
    ("application", ("申請", "重新辦", "重辦", "辦宿", "辦理", "去哪裡辦", "apply", "application", "reapply")),
    ("lookup", ("查詢", "去哪裡查", "哪些", "清單", "ssid", "狀態", "lookup", "check status")),
    ("configuration", ("設定", "安裝", "怎麼用", "如何用", "使用", "setup", "configure", "install", "how to use")),
)

QUALIFIER_MARKERS: dict[str, tuple[str, ...]] = {
    "dorm_transfer": ("換宿", "換寢室", "換了寢室", "換房間", "換了房間", "搬宿", "搬寢室", "搬房間", "換到別"),
    "new_student": ("新生", "剛入學", "new student"),
    "already_applied": ("已經申請", "申請過", "辦過", "already applied"),
    "off_campus": ("校外", "家裡", "off campus", "off-campus"),
    "different_device": ("另一台", "不同裝置", "換手機", "換電腦", "different device"),
}

TOPIC_MARKERS: dict[str, tuple[str, ...]] = {
    "dorm_network": ("宿網", "宿舍網路", "dormnet", "dorm network", "dormitory network"),
    "campus_wifi": ("wi-fi", "wifi", "wlan", "無線網路", "nthu-cc", "nthupeap", "eduroam", "wireless"),
    "vpn": ("vpn", "ivanti", "pulse secure", "sslvpn"),
    "email": ("學生信箱", "電子郵件", "email", "gapp", "google workspace", "webmail"),
}


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


DEPENDENCY_ERROR_CODES = {
    "embedding_unavailable",
    "qdrant_unavailable",
    "llm_unavailable",
}


def _dependency_error_fields(detail: Any) -> dict[str, str]:
    if not isinstance(detail, dict):
        return {}
    code = str(detail.get("code") or "")
    if code not in DEPENDENCY_ERROR_CODES:
        return {}
    return {
        "error_code": code,
        "error_service": str(detail.get("service") or ""),
        "error_category": str(detail.get("category") or ""),
    }


def detect_intent(text: str) -> str:
    normalized = normalize(text)
    for intent, markers in INTENT_MARKERS:
        if any(marker in normalized for marker in markers):
            return intent
    return "unknown"


def detect_qualifiers(text: str) -> list[str]:
    normalized = normalize(text)
    return [
        qualifier
        for qualifier, markers in QUALIFIER_MARKERS.items()
        if any(marker in normalized for marker in markers)
    ]


def has_reference_cue(text: str) -> bool:
    normalized = normalize(text)
    return any(marker in normalized for marker in REFERENCE_MARKERS)


def reference_status(message: str, referenced_turn_ids: list[int]) -> str:
    if referenced_turn_ids:
        return "resolved"
    if has_reference_cue(message):
        return "unresolved"
    return "none"


def infer_document_topic(source: dict[str, Any]) -> str:
    haystack = normalize(
        " ".join(
            str(source.get(key, ""))
            for key in ("title", "source_name", "url", "content")
        )
    )
    hits = [
        topic
        for topic, markers in TOPIC_MARKERS.items()
        if any(marker in haystack for marker in markers)
    ]
    return hits[0] if len(hits) == 1 else "unknown"


def is_refusal(answer: str) -> bool:
    normalized = normalize(answer)
    return any(marker in normalized for marker in REFUSAL_MARKERS)


def is_clarification(answer: str) -> bool:
    normalized = normalize(answer)
    return any(marker in normalized for marker in CLARIFICATION_MARKERS)


def _route_from_stdout(output: str, answer: str) -> str:
    markers = (
        ("path=prompt_leak_fallback", "prompt_leak_fallback"),
        ("Reference Clarification Hit", "reference_clarification"),
        ("Ordinal Follow-up Hit", "ordinal_fast_path"),
        ("Clarification Hit", "clarification"),
        ("Embedding Fallback Hit", "embedding_fallback"),
        ("Follow-up Progression Hit", "followup_progression"),
        ("Fast Answer Hit", "fast_answer"),
        ("Answer Cache Hit", "answer_cache"),
        ("Active Chat Requests", "langgraph"),
    )
    for marker, route in markers:
        if marker in output:
            return route
    if is_refusal(answer):
        return "scope_guard"
    return "unknown"


def _score(source: dict[str, Any]) -> float | None:
    value = source.get("external_rerank_score", source.get("rerank_score", source.get("score")))
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _logged_retrieval_documents(output: str) -> list[RetrievedDocument]:
    for line in reversed(output.splitlines()):
        if not line.startswith("[Retrieval]") or " docs=" not in line:
            continue
        try:
            raw_documents = ast.literal_eval(line.split(" docs=", 1)[1])
        except (SyntaxError, ValueError):
            return []
        documents: list[RetrievedDocument] = []
        for item in raw_documents:
            if not isinstance(item, dict):
                continue
            source = {
                "point_id": item.get("id"),
                "title": item.get("title") or "",
                "score": item.get("score"),
            }
            documents.append(
                RetrievedDocument(
                    point_id=str(source["point_id"]) if source["point_id"] else None,
                    title=str(source["title"]),
                    score=_score(source),
                    inferred_topic=infer_document_topic(source),
                )
            )
        return documents
    return []


class AgentAdapter(Protocol):
    def start_session(self, session_id: str) -> None: ...

    def end_session(self, session_id: str) -> None: ...

    def run_turn(
        self,
        *,
        session_id: str,
        message: str,
        history: list[dict[str, str]],
        language: str,
    ) -> AgentTrace: ...


class BaseAgentAdapter:
    def _preflight(
        self,
        *,
        session_id: str,
        message: str,
        history: list[dict[str, str]],
        language: str,
    ) -> tuple[dict[str, Any], str, str]:
        # These are the exact cheap LangGraph context nodes used by /chat.
        state = prepare_agent_context(message, history, language=language)
        relevant_history = history_for_legacy_functions(state.get("relevant_history", []))

        from main import standalone_question_for_state

        standalone = standalone_question_for_state(message, state, relevant_history)
        retrieval_query = standalone
        topic = state.get("current_topic", "unknown")
        retrieval_query = ensure_topic_in_query(
            focus_message_on_topic(retrieval_query, topic),
            topic,
        )
        return state, standalone, retrieval_query

    def _trace(
        self,
        *,
        session_id: str,
        message: str,
        state: dict[str, Any],
        standalone: str,
        retrieval_query: str,
        response: dict[str, Any],
        route: str,
        latency: float,
        error: str | None = None,
        error_code: str | None = None,
        error_service: str | None = None,
        error_category: str | None = None,
    ) -> AgentTrace:
        sources = list(response.get("sources", []))
        documents = [
            RetrievedDocument(
                point_id=str(source.get("point_id")) if source.get("point_id") else None,
                title=str(source.get("title") or source.get("source_name") or ""),
                url=str(source.get("url") or ""),
                content=str(source.get("content") or "")[:1600],
                score=_score(source),
                inferred_topic=infer_document_topic(source),
            )
            for source in sources
        ]
        referenced_ids = list(state.get("referenced_turn_ids", []))
        answer = str(response.get("answer", ""))
        return AgentTrace(
            session_id=session_id,
            turn_id=int(state.get("current_turn_id", 1)),
            reference_status=str(state.get("reference_status", reference_status(message, referenced_ids))),
            referenced_turn_ids=referenced_ids,
            topic=str(state.get("current_topic", "unknown")),
            intent=str(state.get("current_intent", detect_intent(standalone))),
            intent_source=str(state.get("intent_source", "eval_observer")),
            qualifiers=detect_qualifiers(f"{message} {standalone}"),
            relation=str(state.get("relation", "new_topic")),
            standalone_query=standalone,
            retrieval_query=retrieval_query,
            relevant_history_turn_ids=list(state.get("relevant_turn_ids", [])),
            retrieval_documents=documents,
            final_answer=answer,
            sources=sources,
            api_path=route,
            latency_seconds=latency,
            error=error,
            error_code=error_code,
            error_service=error_service,
            error_category=error_category,
        )


class InProcessAgentAdapter(BaseAgentAdapter):
    """Call the real FastAPI handler in-process; no LangGraph/RAG/LLM mocks."""

    def __init__(self, settings: AgentSettings):
        self.settings = settings
        self._active_sessions: set[str] = set()

    def start_session(self, session_id: str) -> None:
        from main import clear_all_caches, clear_session_cache

        clear_session_cache(session_id)
        if self.settings.clear_cache_between_conversations:
            # Profiles default to max_concurrent=1 so this does not disturb another run.
            clear_all_caches()
        self._active_sessions.add(session_id)

    def end_session(self, session_id: str) -> None:
        from main import clear_session_cache

        clear_session_cache(session_id)
        self._active_sessions.discard(session_id)

    def run_turn(
        self,
        *,
        session_id: str,
        message: str,
        history: list[dict[str, str]],
        language: str,
    ) -> AgentTrace:
        from agent.logging import logger as agent_logger
        from main import ChatHistoryItem, ChatRequest, chat

        if session_id not in self._active_sessions:
            self.start_session(session_id)
        state, standalone, retrieval_query = self._preflight(
            session_id=session_id,
            message=message,
            history=history,
            language=language,
        )
        request = ChatRequest(
            message=message,
            history=[ChatHistoryItem(**item) for item in history],
            language=language,
            session_id=session_id,
        )
        captured = io.StringIO()
        log_capture = io.StringIO()
        log_handler = logging.StreamHandler(log_capture)
        log_handler.setFormatter(logging.Formatter("%(message)s"))
        started = time.perf_counter()
        try:
            agent_logger.addHandler(log_handler)
            with redirect_stdout(captured):
                response = chat(request)
            latency = time.perf_counter() - started
            answer = str(response.get("answer", ""))
            observed_logs = captured.getvalue() + "\n" + log_capture.getvalue()
            route = _route_from_stdout(observed_logs, answer)
            trace = self._trace(
                session_id=session_id,
                message=message,
                state=state,
                standalone=standalone,
                response=response,
                retrieval_query=retrieval_query,
                route=route,
                latency=latency,
            )
            if not trace.retrieval_documents:
                trace.retrieval_documents = _logged_retrieval_documents(observed_logs)
            return trace
        except Exception as exc:
            latency = time.perf_counter() - started
            dependency_fields = _dependency_error_fields(
                exc.detail if isinstance(exc, HTTPException) else None
            )
            response = {"answer": "", "sources": []}
            return self._trace(
                session_id=session_id,
                message=message,
                state=state,
                standalone=standalone,
                response=response,
                retrieval_query=retrieval_query,
                route="error",
                latency=latency,
                error=f"{type(exc).__name__}: {exc}",
                **dependency_fields,
            )
        finally:
            agent_logger.removeHandler(log_handler)


class HttpAgentAdapter(BaseAgentAdapter):
    """Call a separately running FastAPI instance."""

    def __init__(self, settings: AgentSettings):
        self.settings = settings
        self.client = requests.Session()

    def start_session(self, session_id: str) -> None:
        self.client.post(
            f"{self.settings.base_url.rstrip('/')}/session/clear",
            json={"session_id": session_id},
            timeout=self.settings.timeout_seconds,
        )

    def end_session(self, session_id: str) -> None:
        self.start_session(session_id)

    def run_turn(
        self,
        *,
        session_id: str,
        message: str,
        history: list[dict[str, str]],
        language: str,
    ) -> AgentTrace:
        state, standalone, retrieval_query = self._preflight(
            session_id=session_id,
            message=message,
            history=history,
            language=language,
        )
        started = time.perf_counter()
        dependency_fields: dict[str, str] = {}
        try:
            response = self.client.post(
                f"{self.settings.base_url.rstrip('/')}/chat",
                json={
                    "message": message,
                    "history": history,
                    "language": language,
                    "session_id": session_id,
                },
                timeout=self.settings.timeout_seconds,
            )
            if response.status_code >= 400:
                try:
                    error_payload = response.json()
                except (requests.JSONDecodeError, ValueError):
                    error_payload = {}
                dependency_fields = _dependency_error_fields(
                    error_payload.get("detail")
                    if isinstance(error_payload, dict)
                    else None
                )
            response.raise_for_status()
            payload = response.json()
            error = None
        except Exception as exc:
            payload = {"answer": "", "sources": []}
            error = f"{type(exc).__name__}: {exc}"
        return self._trace(
            session_id=session_id,
            message=message,
            state=state,
            standalone=standalone,
            response=payload,
            route="http_api" if error is None else "error",
            retrieval_query=retrieval_query,
            latency=time.perf_counter() - started,
            error=error,
            **dependency_fields,
        )


def build_agent_adapter(settings: AgentSettings) -> AgentAdapter:
    if settings.adapter == "http":
        return HttpAgentAdapter(settings)
    return InProcessAgentAdapter(settings)
