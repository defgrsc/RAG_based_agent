from typing import Any, Literal, NotRequired, TypedDict


Topic = Literal[
    "campus_wifi",
    "dorm_network",
    "vpn",
    "email",
    "account",
    "unknown",
]
Intent = Literal[
    "application",
    "troubleshooting",
    "comparison",
    "configuration",
    "lookup",
    "general",
    "unknown",
]
Relation = Literal["new_topic", "follow_up", "intent_switch"]
ReferenceStatus = Literal["none", "resolved", "unresolved"]
ReferenceKind = Literal["none", "ordinal", "named", "implicit"]
FollowupType = Literal[
    "new_question",
    "action_result",
    "diagnostic_answer",
    "recommendation_question",
    "recommendation_rejected",
    "correction",
    "continuation",
]
ResolutionStatus = Literal["in_progress", "resolved", "blocked"]


class RawHistoryItem(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class HistoryItem(RawHistoryItem):
    turn_id: int
    topic: Topic
    intent: NotRequired[Intent]
    semantic_slots: NotRequired[dict[str, str]]


class ActionResult(TypedDict):
    action: str
    outcome: str
    detail: str
    turn_id: NotRequired[int]


class AgentState(TypedDict, total=False):
    current_user_message: str
    conversation_history: list[RawHistoryItem | HistoryItem]
    current_turn_id: int
    relation: Relation
    followup_type: FollowupType
    current_topic: Topic
    current_intent: Intent
    intent_source: Literal["explicit", "inherited", "unknown"]
    reference_status: ReferenceStatus
    reference_kind: ReferenceKind
    referenced_topic: Topic | None
    referenced_turn_ids: list[int]
    current_slots: dict[str, str]
    referenced_slots: dict[str, str]
    semantic_slots: dict[str, str]
    previous_recommendations: list[str]
    pending_question: str | None
    current_action_results: list[ActionResult]
    troubleshooting_progress: list[ActionResult]
    resolution_status: ResolutionStatus
    relevant_history: list[HistoryItem]
    relevant_turn_ids: list[int]
    standalone_query: str
    retrieval_query: str
    retrieval_filter: dict[str, Any] | None
    retrieved_docs: list[dict[str, Any]]
    answer: str
    language: Literal["zh-Hant", "en"]
    confidence: float
    metadata: dict[str, Any]
    context_resolved: bool
    history_selected: bool


def history_for_legacy_functions(history: list[HistoryItem]) -> list[dict[str, str]]:
    """Drop graph-only fields before calling the existing rewrite/prompt helpers."""
    return [
        {"role": item["role"], "content": item["content"][:1200]}
        for item in history
    ]
