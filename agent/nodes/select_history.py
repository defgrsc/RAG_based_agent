from agent.logging import log_selected_history
from agent.state import AgentState


MAX_RELEVANT_TURNS = 6


def select_history(state: AgentState) -> dict:
    if state.get("history_selected"):
        return {}

    history = state.get("conversation_history", [])
    current_topic = state.get("current_topic", "unknown")
    current_intent = state.get("current_intent", "unknown")
    referenced_turn_ids = state.get("referenced_turn_ids", [])

    followup_type = state.get("followup_type", "new_question")
    reference_kind = state.get("reference_kind", "none")

    if reference_kind in {"named", "ordinal"} and referenced_turn_ids:
        selected_turn_ids = list(dict.fromkeys(referenced_turn_ids))
    elif followup_type != "new_question" and current_topic != "unknown":
        matching_ids = [
            item["turn_id"]
            for item in history
            if item["role"] == "user" and item["topic"] == current_topic
        ]
        selected_turn_ids = list(dict.fromkeys(
            [*matching_ids, *referenced_turn_ids]
        ))[-MAX_RELEVANT_TURNS:]
    elif state.get("relation") == "intent_switch":
        selected_turn_ids = []
    elif referenced_turn_ids:
        selected_turn_ids = list(dict.fromkeys(referenced_turn_ids))
    elif state.get("relation") == "follow_up" and current_topic != "unknown":
        matching_ids = [
            item["turn_id"]
            for item in history
            if (
                item["role"] == "user"
                and item["topic"] == current_topic
                and (
                    current_intent == "unknown"
                    or item.get("intent", "unknown") == current_intent
                )
            )
        ]
        selected_turn_ids = list(dict.fromkeys(matching_ids))[-MAX_RELEVANT_TURNS:]
    else:
        selected_turn_ids = []

    selected_set = set(selected_turn_ids)
    relevant_history = [item for item in history if item["turn_id"] in selected_set]
    current_turn_id = state.get("current_turn_id", 1)
    relevant_turn_ids = [*selected_turn_ids, current_turn_id]
    result: AgentState = {
        "relevant_history": relevant_history,
        "relevant_turn_ids": relevant_turn_ids,
        "history_selected": True,
    }
    log_selected_history({**state, **result})
    return result
