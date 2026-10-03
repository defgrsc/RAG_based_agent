from agent.intents import detect_explicit_intent, is_context_dependent_followup
from agent.followups import classify_followup_type
from agent.logging import log_classified_intent
from agent.state import AgentState, HistoryItem, Intent
from agent.topics import detect_explicit_topic


def _annotate_history_intents(history: list[HistoryItem]) -> list[HistoryItem]:
    annotated: list[HistoryItem] = []
    latest_by_topic: dict[str, Intent] = {}
    turn_intents: dict[int, Intent] = {}

    for item in history:
        enriched = dict(item)
        if item["role"] == "user":
            intent = detect_explicit_intent(item["content"])
            followup_type = classify_followup_type(
                item["content"],
                has_history=bool(annotated),
            )
            prior_intent = latest_by_topic.get(item["topic"], "unknown")
            if (
                followup_type not in {"new_question", "continuation"}
                and prior_intent != "unknown"
            ):
                intent = prior_intent
            if (
                intent == "unknown"
                and item["topic"] != "unknown"
                and is_context_dependent_followup(item["content"])
            ):
                intent = latest_by_topic.get(item["topic"], "unknown")
            turn_intents[item["turn_id"]] = intent
            if intent != "unknown" and item["topic"] != "unknown":
                latest_by_topic[item["topic"]] = intent
        else:
            intent = turn_intents.get(item["turn_id"], "unknown")
        enriched["intent"] = intent
        annotated.append(enriched)
    return annotated


def _referenced_intent(
    history: list[HistoryItem],
    referenced_turn_ids: list[int],
) -> Intent:
    referenced = set(referenced_turn_ids)
    return next(
        (
            item.get("intent", "unknown")
            for item in reversed(history)
            if item["role"] == "user"
            and item["turn_id"] in referenced
            and item.get("intent", "unknown") != "unknown"
        ),
        "unknown",
    )


def _latest_topic_intent(history: list[HistoryItem], topic: str) -> Intent:
    return next(
        (
            item.get("intent", "unknown")
            for item in reversed(history)
            if item["role"] == "user"
            and item["topic"] == topic
            and item.get("intent", "unknown") != "unknown"
        ),
        "unknown",
    )


def classify_intent(state: AgentState) -> dict:
    history = _annotate_history_intents(list(state.get("conversation_history", [])))
    explicit_intent = detect_explicit_intent(state.get("current_user_message", ""))
    explicit_topic = detect_explicit_topic(state.get("current_user_message", ""))[0]
    referenced_ids = list(state.get("referenced_turn_ids", []))
    inherited_intent = _referenced_intent(history, referenced_ids)
    if inherited_intent == "unknown" and state.get("relation") == "follow_up":
        inherited_intent = _latest_topic_intent(
            history,
            state.get("current_topic", "unknown"),
        )

    relation = state.get("relation", "new_topic")
    reference_status = state.get("reference_status", "none")
    referenced_topic = state.get("referenced_topic")
    followup_type = state.get("followup_type", "new_question")
    intent_source = "unknown"
    current_intent: Intent = "unknown"
    continuation_failure = followup_type == "continuation" and any(
        item.get("outcome") in {"disabled", "still_fails"}
        for item in state.get("current_action_results", [])
    )

    if (
        continuation_failure
        or (
            followup_type != "new_question"
            and (
                followup_type != "continuation"
                or inherited_intent == "troubleshooting"
            )
            and (
                explicit_intent not in {"troubleshooting", "comparison"}
                or (
                    explicit_intent == "comparison"
                    and followup_type == "diagnostic_answer"
                )
            )
            and inherited_intent != "unknown"
        )
    ):
        if continuation_failure:
            inherited_intent = "troubleshooting"
        current_intent = inherited_intent
        intent_source = "inherited"
    elif explicit_intent != "unknown":
        current_intent = explicit_intent
        intent_source = "explicit"
        if (
            explicit_intent != "comparison"
            and inherited_intent not in {"unknown", explicit_intent}
            and relation == "follow_up"
        ):
            # A generic account mention borrows the prior service topic, but the old
            # troubleshooting/application content is still excluded from history.
            if explicit_topic != "account":
                relation = "intent_switch"
            if (
                followup_type == "new_question"
                and state.get("reference_kind") == "implicit"
            ):
                referenced_ids = []
                referenced_topic = None
                reference_status = "none"
    elif inherited_intent != "unknown":
        current_intent = inherited_intent
        intent_source = "inherited"

    result = {
        "conversation_history": history,
        "current_intent": current_intent,
        "intent_source": intent_source,
        "relation": relation,
        "reference_status": reference_status,
        "referenced_topic": referenced_topic,
        "referenced_turn_ids": referenced_ids,
    }
    log_classified_intent({**state, **result})
    return result
