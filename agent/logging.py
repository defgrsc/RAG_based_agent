import logging
from typing import Any

from agent.state import AgentState


logger = logging.getLogger("nthu_agent.langgraph")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def log_resolved_context(state: AgentState) -> None:
    logger.info(
        "[LangGraph] current_message=%r relation=%s topic=%s intent=%s "
        "reference_status=%s referenced_turn_ids=%s confidence=%.2f",
        state.get("current_user_message", ""),
        state.get("relation", "new_topic"),
        state.get("current_topic", "unknown"),
        state.get("current_intent", "unknown"),
        state.get("reference_status", "none"),
        state.get("referenced_turn_ids", []),
        state.get("confidence", 0.0),
    )
    logger.info(
        "[LangGraph] current_slots=%s referenced_slots=%s semantic_slots=%s",
        state.get("current_slots", {}),
        state.get("referenced_slots", {}),
        state.get("semantic_slots", {}),
    )


def log_selected_history(state: AgentState) -> None:
    logger.info(
        "[LangGraph] relevant_turn_ids=%s",
        state.get("relevant_turn_ids", []),
    )


    log_selected_history_details(state)

def log_retrieval(state: AgentState) -> None:
    documents: list[dict[str, Any]] = []
    for item in state.get("retrieved_docs", []):
        documents.append(
            {
                "id": item.get("point_id"),
                "title": item.get("title") or item.get("source_name"),
                "score": item.get("external_rerank_score", item.get("rerank_score", item.get("score"))),
            }
        )
    logger.info(
        "[Retrieval] query=%r topic_hint=%s metadata_filter=%s docs=%s",
        state.get("retrieval_query", ""),
        state.get("current_topic", "unknown"),
        state.get("retrieval_filter"),
        documents,
    )


def log_final_answer(state: AgentState, answer: str, path: str = "langgraph") -> None:
    logger.info("[LangGraph] path=%s final_answer=%r", path, answer)


def log_selected_history_details(state: AgentState) -> None:
    logger.info(
        "[LangGraph] selected_history=%s",
        [
            {
                "turn_id": item.get("turn_id"),
                "role": item.get("role"),
                "topic": item.get("topic"),
                "intent": item.get("intent"),
                "semantic_slots": item.get("semantic_slots", {}),
                "content": item.get("content", "")[:240],
            }
            for item in state.get("relevant_history", [])
        ],
    )


def log_classified_intent(state: AgentState) -> None:
    logger.info(
        "[LangGraph] classified topic=%s intent=%s intent_source=%s relation=%s "
        "reference_status=%s referenced_turn_ids=%s",
        state.get("current_topic", "unknown"),
        state.get("current_intent", "unknown"),
        state.get("intent_source", "unknown"),
        state.get("relation", "new_topic"),
        state.get("reference_status", "none"),
        state.get("referenced_turn_ids", []),
    )


def log_standalone_query(state: AgentState) -> None:
    logger.info(
        "[LangGraph] standalone_query=%r",
        state.get("standalone_query", ""),
    )


def log_api_response(state: AgentState, response: dict[str, Any], path: str) -> None:
    logger.info(
        "[API] path=%s response_type=%s answer_type=%s sources_type=%s",
        path,
        type(response).__name__,
        type(response.get("answer")).__name__,
        type(response.get("sources")).__name__,
    )
