import pytest

from agent.graph import prepare_agent_context
from agent.state import history_for_legacy_functions
from campus_locations import (
    load_campus_locations,
    location_names_for,
    match_campus_location_mention,
    resolve_campus_location,
)
from main import ChatRequest, chat, standalone_question_for_state
from wireless_coverage import lookup_coverage


def _standalone(message: str, history: list[dict[str, str]]) -> tuple[dict, str]:
    state = prepare_agent_context(message, history)
    relevant = history_for_legacy_functions(state.get("relevant_history", []))
    return state, standalone_question_for_state(message, state, relevant)


@pytest.mark.parametrize(
    ("alias", "canonical"),
    (
        ("綜四", "綜合四館"),
        ("綜四館", "綜合四館"),
        ("人社院", "人文社會學院"),
        ("計通中心", "計算機與通訊中心"),
        ("生科館", "生命科學館"),
        ("動機館", "動力機械工程學系館"),
        ("總圖", "總圖書館"),
        ("台達", "台達館"),
    ),
)
def test_aliases_resolve_to_canonical_location(alias: str, canonical: str):
    assert resolve_campus_location(alias)["canonical"] == canonical
    assert match_campus_location_mention(f"噢那我現在在{alias}附近") == canonical
    assert canonical in location_names_for(alias)


def test_every_reference_location_is_matchable_by_its_canonical_name():
    records = load_campus_locations()
    assert len(records) == 78
    assert len({record["canonical"] for record in records}) == len(records)
    for record in records:
        canonical = record["canonical"]
        assert match_campus_location_mention(f"請問{canonical}怎麼走？") == canonical


@pytest.mark.parametrize("message", ("我在綜四", "噢那計通中心怎麼走？", "學齋有嗎？"))
def test_location_alone_does_not_infer_a_service(message: str):
    state, _ = _standalone(message, [])
    assert state["current_topic"] == "unknown"
    assert "location" in state["current_slots"]
    assert "question_focus" not in state["current_slots"]


def test_ambiguous_location_question_asks_for_service_instead_of_guessing():
    response = chat(ChatRequest(message="綜四有嗎？"))
    assert "綜合四館" in response["answer"]
    assert "還不確定是在問哪一種服務" in response["answer"]
    assert "Wi-Fi" in response["answer"]
    assert response["sources"] == []


@pytest.mark.parametrize("_repeat", range(3))
def test_location_ellipsis_inherits_wifi_only_from_conversation(_repeat: int):
    history = [
        {"role": "user", "content": "學校哪裡有網路？"},
        {"role": "assistant", "content": "校園多處有無線網路。"},
    ]
    state, query = _standalone("綜四有嗎？", history)

    assert state["relation"] == "follow_up"
    assert state["current_topic"] == "campus_wifi"
    assert state["current_intent"] == "lookup"
    assert state["current_slots"] == {
        "location": "綜合四館",
        "question_focus": "network_availability",
    }
    assert query == "綜合四館有校園無線網路嗎？"


@pytest.mark.parametrize(
    ("message", "topic", "intent", "location"),
    (
        ("我在綜四，VPN 連不上", "vpn", "troubleshooting", "綜合四館"),
        ("學齋的宿網怎麼設定", "dorm_network", "configuration", "學齋"),
        ("我在人社院，學生信箱登不進去", "email", "troubleshooting", "人文社會學院"),
    ),
)
def test_explicit_service_wins_over_location(
    message: str,
    topic: str,
    intent: str,
    location: str,
):
    state, _ = _standalone(message, [])
    assert state["current_topic"] == topic
    assert state["current_intent"] == intent
    assert state["current_slots"]["location"] == location


def test_canonical_alias_expands_for_official_coverage_lookup():
    result = lookup_coverage("人文社會學院")
    assert result["match_level"] == "exact"
    assert any("nthupeap" in record["ssids"] for record in result["records"])
