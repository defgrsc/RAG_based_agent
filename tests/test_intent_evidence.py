import pytest

from agent.graph import prepare_agent_context
from agent.intents import detect_explicit_intent


@pytest.mark.parametrize(
    ("message", "expected"),
    (
        ("Where can graduate students register for NTHU wireless?", "application"),
        ("I registered earlier; how do I configure DormNet ethernet?", "configuration"),
        ("eduroam drops every few minutes", "troubleshooting"),
        ("宿舍網路整晚都沒網路", "troubleshooting"),
        ("宿網最近一直斷線要怎麼辦？", "troubleshooting"),
        ("wireless coverage around the auditorium", "lookup"),
        ("台達館有沒有無線訊號", "lookup"),
        ("材料館能不能上網？", "lookup"),
        ("Which password goes into nthupeap?", "unknown"),
        ("Which VPN server should I enter?", "configuration"),
        ("Remote access to an internal NTHU server", "configuration"),
    ),
)
def test_bilingual_intent_evidence_and_ordering(message: str, expected: str):
    assert detect_explicit_intent(message) == expected


def test_new_symptom_evidence_drives_same_topic_intent_switch():
    history = [
        {"role": "user", "content": "How do I register for campus Wi-Fi?"},
        {"role": "assistant", "content": "Use the wireless account application."},
    ]

    state = prepare_agent_context("But now it keeps disconnecting.", history, language="en")

    assert state["current_topic"] == "campus_wifi"
    assert state["current_intent"] == "troubleshooting"
    assert state["relation"] == "intent_switch"
    assert state["relevant_history"] == []


@pytest.mark.parametrize(
    "message",
    (
        "Where should I eat lunch?",
        "Does the academic system have my grades?",
        "清大停車證要去哪裡領？",
    ),
)
def test_non_network_requests_do_not_gain_an_intent(message: str):
    assert detect_explicit_intent(message) == "unknown"
