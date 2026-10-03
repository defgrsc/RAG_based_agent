import time
from collections.abc import Callable
from typing import Any

from agent.logging import log_retrieval
from agent.state import AgentState, Topic, history_for_legacy_functions
from agent.topics import ensure_topic_in_query, focus_message_on_topic


RetrieveFunction = Callable[..., list[dict[str, Any]]]
RewriteFunction = Callable[[str, list[dict[str, str]]], str]


def make_retrieve_node(
    retrieve_fn: RetrieveFunction,
    rewrite_fn: RewriteFunction,
) -> Callable[[AgentState], dict]:
    def retrieve(state: AgentState) -> dict:
        relevant_history = history_for_legacy_functions(state.get("relevant_history", []))
        query = state.get("standalone_query", "")
        if not query:
            query = rewrite_fn(state.get("current_user_message", ""), relevant_history)
        topic: Topic = state.get("current_topic", "unknown")
        query = focus_message_on_topic(query, topic)
        query = ensure_topic_in_query(query, topic)
        metadata_filter = state.get("retrieval_filter")
        semantic_slots = state.get("semantic_slots", {})
        coverage_focus = semantic_slots.get("question_focus") in {
            "coverage_list",
            "ssid_list",
        }
        if (
            metadata_filter is None
            and topic == "campus_wifi"
            and state.get("current_intent") in {"lookup", "comparison"}
            and (semantic_slots.get("location") or coverage_focus)
        ):
            metadata_filter = {"service": "campus_wifi", "intent": "coverage"}

        start = time.perf_counter()
        documents = retrieve_fn(
            query,
            language=state.get("language", "zh-Hant"),
            topic=topic,
            metadata_filter=metadata_filter,
        )
        duration = time.perf_counter() - start
        metadata = {**state.get("metadata", {}), "retrieval_seconds": duration}
        result: AgentState = {
            "retrieval_query": query,
            "retrieval_filter": metadata_filter,
            "retrieved_docs": documents,
            "metadata": metadata,
        }
        log_retrieval({**state, **result})
        return result

    return retrieve
