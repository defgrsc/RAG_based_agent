from pathlib import Path

from evals.bug_discovery.evaluator import evaluate_generated_conversation, validate_simulated_message
from evals.bug_discovery.loader import load_config, load_scenarios, select_scenarios
from evals.bug_discovery.runner import build_variants, estimate_calls
from evals.bug_discovery.schemas import AgentTrace, FailureCategory
from evals.bug_discovery.simulator import GeneratedConversation


REQUIRED_CATEGORIES = {
    "topic_switching",
    "return_to_previous_topic",
    "intent_switching",
    "qualifier_modification",
    "ambiguous_reference",
    "explicit_topic_override",
    "unnecessary_refusal",
    "rephrasing_fuzz",
}


def trace(**updates) -> AgentTrace:
    values = {
        "session_id": "session-a",
        "turn_id": 1,
        "reference_status": "none",
        "referenced_turn_ids": [],
        "topic": "vpn",
        "intent": "configuration",
        "qualifiers": [],
        "relation": "new_topic",
        "standalone_query": "清大 VPN 要怎麼用？",
        "retrieval_query": "清大 VPN 要怎麼用？",
        "relevant_history_turn_ids": [1],
        "retrieval_documents": [],
        "final_answer": "請依清大網路系統組 VPN 說明設定。",
        "api_path": "fast_answer",
    }
    values.update(updates)
    return AgentTrace(**values)


def test_colloquial_generation_constraints_reject_semantic_drift():
    scenarios = {scenario.scenario_id: scenario for scenario in load_scenarios()}
    named = scenarios["colloquial_named_return_with_room_change"]
    dismissed = scenarios["colloquial_dismiss_old_service"]

    assert validate_simulated_message(
        "哎，宿網那題，我剛換了房間，請問要重新申請嗎？",
        named.turns[0],
    )
    assert not validate_simulated_message("宿網要去哪辦啊？", named.turns[0])

    final_issues = validate_simulated_message(
        "先回宿網那題啦，這個要重辦嗎？",
        named.turns[2],
    )
    assert any("required group" in issue for issue in final_issues)
    assert not validate_simulated_message(
        "先回宿網那題啦，我換了房間，這個要重辦嗎？",
        named.turns[2],
    )

    assert validate_simulated_message(
        "宿網一直斷線，先不管這個，我要問 GAPP。",
        dismissed.turns[0],
    )


def test_required_scenario_categories_exist():
    scenarios = load_scenarios()
    categories = {scenario.category for scenario in scenarios}
    assert REQUIRED_CATEGORIES.issubset(categories)
    assert "colloquial_unseen" in categories


def test_smoke_budget_is_bounded_and_config_driven():
    config = load_config()
    profile = config.profiles["SMOKE"]
    variants = build_variants(select_scenarios(load_scenarios(), profile), profile)
    estimate = estimate_calls(variants, profile)

    assert estimate["conversations_generated"] == 5
    assert estimate["simulator_calls"] <= 15
    assert estimate["estimated_max_total"] == 23


def test_reference_failure_is_classified_before_answer_quality():
    scenario = next(
        scenario
        for scenario in load_scenarios()
        if scenario.scenario_id == "unresolved_reference_without_history"
    )
    generated = GeneratedConversation(
        execution_id="unresolved_reference_without_history__v0",
        scenario=scenario,
        variant_index=0,
        session_id="session-a",
        user_messages=["回到第一個問題，如果我是換宿的呢？"],
        assistant_messages=["抱歉，本客服僅提供國立清華大學網路系統組相關資訊。"],
        traces=[
            trace(
                topic="unknown",
                intent="unknown",
                reference_status="unresolved",
                standalone_query="回到第一個問題，如果我是換宿的呢？",
                retrieval_query="回到第一個問題，如果我是換宿的呢？",
                relevant_history_turn_ids=[1],
                final_answer="抱歉，本客服僅提供國立清華大學網路系統組相關資訊。",
                api_path="scope_guard",
            )
        ],
    )

    result = evaluate_generated_conversation(generated)

    assert not result.passed
    assert result.primary_failure == FailureCategory.REFERENCE_RESOLUTION_ERROR


def test_context_contamination_is_visible_in_intermediate_state():
    scenario = next(
        scenario
        for scenario in load_scenarios()
        if scenario.scenario_id == "explicit_wifi_override_after_dorm_failure"
    )
    generated = GeneratedConversation(
        execution_id="explicit_wifi_override_after_dorm_failure__v0",
        scenario=scenario,
        variant_index=0,
        session_id="session-a",
        user_messages=["宿網連不上怎麼辦？", "Wi-Fi 也連不上。"],
        assistant_messages=["宿網回答", "Wi-Fi 回答"],
        traces=[
            trace(
                topic="dorm_network",
                intent="troubleshooting",
                standalone_query="宿網連不上怎麼辦？",
                retrieval_query="宿網連不上怎麼辦？",
            ),
            trace(
                turn_id=2,
                topic="campus_wifi",
                intent="troubleshooting",
                standalone_query="Wi-Fi 也連不上。",
                retrieval_query="Wi-Fi 也連不上。",
                relevant_history_turn_ids=[1, 2],
            ),
        ],
    )

    result = evaluate_generated_conversation(generated)

    assert FailureCategory.CONTEXT_CONTAMINATION in {
        item.category for item in result.turns[1].failures
    }


def test_dependency_outage_is_not_classified_as_agent_logic_bug():
    from evals.bug_discovery.reporting import REGRESSION_CANDIDATE_CATEGORIES

    scenario = next(
        scenario
        for scenario in load_scenarios()
        if scenario.scenario_id == "colloquial_vpn_install"
    )
    generated = GeneratedConversation(
        execution_id="colloquial_vpn_install__infra",
        scenario=scenario,
        variant_index=0,
        session_id="session-infra",
        user_messages=["清大 VPN 那個要怎麼裝啊？"],
        assistant_messages=[""],
        traces=[
            trace(
                topic="vpn",
                intent="configuration",
                final_answer="",
                api_path="error",
                error="HTTPException: 503",
                error_code="embedding_unavailable",
                error_service="embedding",
                error_category="timeout",
            )
        ],
    )

    result = evaluate_generated_conversation(generated)

    assert not result.passed
    assert result.primary_failure == FailureCategory.DEPENDENCY_UNAVAILABLE
    assert result.primary_failure not in REGRESSION_CANDIDATE_CATEGORIES


def test_adapter_extracts_only_known_dependency_error_codes():
    from evals.bug_discovery.agent_adapter import _dependency_error_fields

    assert _dependency_error_fields(
        {
            "code": "qdrant_unavailable",
            "service": "qdrant",
            "category": "connection",
        }
    ) == {
        "error_code": "qdrant_unavailable",
        "error_service": "qdrant",
        "error_category": "connection",
    }
    assert _dependency_error_fields({"code": "unrelated_error"}) == {}


def test_no_paid_or_confident_cloud_key_is_required():
    text = Path("evals/config.yaml").read_text(encoding="utf-8")
    assert "CONFIDENT_API_KEY" not in text
    assert "provider: openai_compatible" in text


def test_ssid_lookup_beats_generic_use_word():
    from evals.bug_discovery.agent_adapter import detect_intent

    assert detect_intent("有哪些 SSID 開放給學生使用？") == "lookup"


def test_retrieval_logger_restores_docs_removed_by_fallback():
    from evals.bug_discovery.agent_adapter import _logged_retrieval_documents

    log = (
        "[Retrieval] query='SSID' topic_hint=campus_wifi metadata_filter=None "
        "docs=[{'id': 'doc-1', 'title': 'faq:wlan_useless [網路系統組]', "
        "'score': 1.2}]"
    )
    documents = _logged_retrieval_documents(log)

    assert len(documents) == 1
    assert documents[0].point_id == "doc-1"
    assert documents[0].inferred_topic == "campus_wifi"

