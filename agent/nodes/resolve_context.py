from agent.followups import analyze_followup, derive_troubleshooting_progress
from agent.intents import is_context_dependent_followup
from agent.logging import log_resolved_context
from agent.semantics import (
    extract_semantic_slots,
    is_account_scope_comparison_request,
    is_location_availability_ellipsis,
    merge_semantic_slots,
)
from agent.state import AgentState, HistoryItem, Topic
from agent.topics import (
    detect_explicit_topic,
    has_backward_reference_cue,
    has_follow_up_cue,
    ordinal_reference_index,
)


def _annotate_history(raw_history: list[dict]) -> list[HistoryItem]:
    annotated: list[HistoryItem] = []
    turn_id = 0
    active_topic: Topic = "unknown"
    previous_assistant = ""
    seen_user = False

    for raw_item in raw_history:
        role = "assistant" if raw_item.get("role") == "assistant" else "user"
        content = " ".join(str(raw_item.get("content", "")).split())
        if not content:
            continue
        semantic_slots = extract_semantic_slots(content) if role == "user" else {}
        if role == "user":
            turn_id += 1
            followup = analyze_followup(
                content,
                previous_assistant=previous_assistant,
                has_history=seen_user,
            )
            explicit_topic, _ = detect_explicit_topic(content)
            if explicit_topic != "unknown":
                active_topic = explicit_topic
            elif (
                followup["followup_type"] == "new_question"
                and not has_follow_up_cue(content)
            ):
                active_topic = "unknown"
        elif turn_id == 0:
            continue

        annotated.append(
            {
                "role": role,
                "content": content,
                "turn_id": turn_id,
                "topic": active_topic,
                "semantic_slots": semantic_slots,
            }
        )
        if role == "assistant":
            previous_assistant = content
        else:
            seen_user = True
    return annotated


def _latest_meaningful_turn(user_turns: list[HistoryItem]) -> HistoryItem | None:
    return next(
        (item for item in reversed(user_turns) if item["topic"] != "unknown"),
        user_turns[-1] if user_turns else None,
    )



def resolve_context(state: AgentState) -> dict:
    if state.get("context_resolved"):
        return {}

    raw_history = list(state.get("conversation_history", []))
    history = _annotate_history(raw_history)
    user_turns = [item for item in history if item["role"] == "user"]
    current_message = state.get("current_user_message", "")
    current_turn_id = max((item["turn_id"] for item in history), default=0) + 1
    explicit_topic, confidence = detect_explicit_topic(current_message)
    current_slots = extract_semantic_slots(current_message)
    previous_topic = next(
        (item["topic"] for item in reversed(user_turns) if item["topic"] != "unknown"),
        "unknown",
    )

    previous_assistant = next(
        (
            str(item.get("content", ""))
            for item in reversed(raw_history)
            if item.get("role") == "assistant"
        ),
        "",
    )
    followup = analyze_followup(
        current_message,
        previous_assistant=previous_assistant,
        has_history=bool(user_turns),
    )
    structured_followup = followup["followup_type"] != "new_question"

    relation = "new_topic"
    topic: Topic = explicit_topic
    referenced_topic: Topic | None = None
    referenced_turn_ids: list[int] = []
    referenced_slots: dict[str, str] = {}
    semantic_slots = dict(current_slots)
    reference_status = "none"
    reference_kind = "none"

    ordinal_index = ordinal_reference_index(current_message)
    backward_reference = has_backward_reference_cue(current_message)
    contextual_followup = (
        is_context_dependent_followup(current_message) or structured_followup
    )
    account_scope_comparison = is_account_scope_comparison_request(current_message)

    referenced: HistoryItem | None = None
    if ordinal_index is not None:
        reference_kind = "ordinal"
        if ordinal_index <= len(user_turns):
            referenced = user_turns[ordinal_index - 1]
            confidence = 0.98
        else:
            reference_status = "unresolved"
            confidence = 0.2
    elif backward_reference:
        reference_kind = "named"
        if explicit_topic not in {"unknown", "account"}:
            referenced = next(
                (item for item in reversed(user_turns) if item["topic"] == explicit_topic),
                None,
            )
        else:
            referenced = _latest_meaningful_turn(user_turns)
        if referenced is None:
            reference_status = "unresolved"
            confidence = 0.25
    elif account_scope_comparison and explicit_topic != "unknown" and user_turns:
        reference_kind = "implicit"
        referenced = next(
            (item for item in reversed(user_turns) if item["topic"] == explicit_topic),
            None,
        )
        confidence = 0.92 if referenced is not None else confidence
    elif contextual_followup and explicit_topic not in {"unknown", "account"} and user_turns:
        reference_kind = "implicit"
        referenced = next(
            (item for item in reversed(user_turns) if item["topic"] == explicit_topic),
            None,
        )
        if referenced is not None:
            confidence = 0.9
    elif explicit_topic != "unknown":
        if explicit_topic == "account" and previous_topic != "unknown" and contextual_followup:
            reference_kind = "implicit"
            referenced = next(
                (item for item in reversed(user_turns) if item["topic"] == previous_topic),
                None,
            )
        else:
            topic = explicit_topic
    elif contextual_followup and user_turns:
        reference_kind = "implicit"
        referenced = _latest_meaningful_turn(user_turns)

    if referenced is not None:
        relation = "follow_up"
        topic = referenced["topic"]
        referenced_topic = referenced["topic"]
        referenced_turn_ids = [referenced["turn_id"]]
        referenced_slots = dict(referenced.get("semantic_slots", {}))
        if topic == "campus_wifi" and is_location_availability_ellipsis(current_message):
            current_slots["question_focus"] = "network_availability"
        semantic_slots = merge_semantic_slots(referenced_slots, current_slots)
        reference_status = "resolved"
        if reference_kind == "implicit":
            confidence = 0.84 if topic != "unknown" else 0.45

    if topic != "unknown":
        exact_reference = reference_kind in {"named", "ordinal"}
        linked_previous_assistant = next(
            (
                item["content"]
                for item in reversed(history)
                if item["role"] == "assistant"
                and item["topic"] == topic
                and (
                    not exact_reference
                    or item["turn_id"] in referenced_turn_ids
                )
            ),
            "",
        )
        followup = analyze_followup(
            current_message,
            previous_assistant=linked_previous_assistant,
            has_history=bool(user_turns),
        )

    progress_source = (
        history
        if topic == "unknown"
        else [item for item in history if item["topic"] == topic]
    )
    troubleshooting_progress = derive_troubleshooting_progress(progress_source)
    current_action_results = [
        {**item, "turn_id": current_turn_id}
        for item in followup["current_action_results"]
    ]
    troubleshooting_progress.extend(current_action_results)

    result: AgentState = {
        "conversation_history": history,
        "current_turn_id": current_turn_id,
        "relation": relation,
        "followup_type": followup["followup_type"],
        "current_topic": topic,
        "reference_status": reference_status,
        "reference_kind": reference_kind,
        "referenced_topic": referenced_topic,
        "referenced_turn_ids": referenced_turn_ids,
        "current_slots": current_slots,
        "referenced_slots": referenced_slots,
        "semantic_slots": semantic_slots,
        "previous_recommendations": followup["previous_recommendations"],
        "pending_question": followup["pending_question"],
        "current_action_results": current_action_results,
        "troubleshooting_progress": troubleshooting_progress,
        "resolution_status": followup["resolution_status"],
        "confidence": confidence,
        "context_resolved": True,
    }
    log_resolved_context({**state, **result})
    return result
