import time
from collections.abc import Callable
from typing import Any

from agent.followups import format_progression_context
from agent.logging import log_final_answer
from agent.state import AgentState, history_for_legacy_functions


BuildContextFunction = Callable[[list[dict[str, Any]]], str]
FormatHistoryFunction = Callable[[list[dict[str, str]]], str]
GenerateFunction = Callable[[str, str, str, str], str]


def make_generate_node(
    build_context_fn: BuildContextFunction,
    format_history_fn: FormatHistoryFunction,
    generate_fn: GenerateFunction,
) -> Callable[[AgentState], dict]:
    def generate(state: AgentState) -> dict:
        documents = state.get("retrieved_docs", [])
        context = build_context_fn(documents)
        relevant_history = history_for_legacy_functions(state.get("relevant_history", []))
        history_context = format_history_fn(relevant_history)
        progression_context = format_progression_context(state)
        if progression_context:
            history_context = (
                f"{history_context}\n\nStructured troubleshooting progression:\n"
                f"{progression_context}"
            )
        start = time.perf_counter()
        answer = generate_fn(
            state.get("current_user_message", ""),
            context,
            history_context,
            state.get("language", "zh-Hant"),
        )
        duration = time.perf_counter() - start
        metadata = {**state.get("metadata", {}), "generation_seconds": duration}
        result: AgentState = {"answer": answer, "metadata": metadata}
        log_final_answer({**state, **result}, answer)
        return result

    return generate
