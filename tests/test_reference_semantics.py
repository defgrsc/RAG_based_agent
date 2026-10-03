from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agent.graph import prepare_agent_context
from agent.state import history_for_legacy_functions
from main import (
    ChatRequest,
    app,
    chat,
    finalize_chat_response,
    standalone_question_for_state,
)


def conversation(*questions: str) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for question in questions:
        history.extend(
            (
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"回答：{question}"},
            )
        )
    return history


def standalone(message: str, history: list[dict[str, str]]) -> tuple[dict, str]:
    state = prepare_agent_context(message, history)
    relevant = history_for_legacy_functions(state.get("relevant_history", []))
    return state, standalone_question_for_state(message, state, relevant)


@pytest.mark.parametrize("_repeat", range(2))
def test_remote_campus_access_is_standalone_vpn_semantics(_repeat: int):
    state, query = standalone("如果我要在家連學校網路可以嗎？", [])

    assert state["reference_status"] == "none"
    assert state["referenced_turn_ids"] == []
    assert state["current_topic"] == "vpn"
    assert state["current_intent"] == "configuration"
    assert state["semantic_slots"] == {
        "access_origin": "off_campus",
        "resource_scope": "campus_internal",
    }
    assert query == "如果我要在家連學校網路可以嗎？"


def test_home_location_alone_does_not_imply_vpn():
    state, _ = standalone("我在家 Wi-Fi 很慢", [])
    assert state["reference_status"] == "none"
    assert state["current_topic"] != "vpn"


@pytest.mark.parametrize("_repeat", range(2))
def test_standalone_location_availability_has_no_reference(_repeat: int):
    state, query = standalone("梅園有網路嗎？", [])

    assert state["reference_status"] == "none"
    assert state["referenced_turn_ids"] == []
    assert state["current_topic"] == "campus_wifi"
    assert state["current_intent"] == "lookup"
    assert state["semantic_slots"]["location"] == "梅園"
    assert query == "梅園有網路嗎？"


@pytest.mark.parametrize("_repeat", range(2))
def test_location_followup_replaces_slot_and_inherits_intent(_repeat: int):
    state, query = standalone("台達館呢？", conversation("梅園有網路嗎？"))

    assert state["reference_status"] == "resolved"
    assert state["referenced_turn_ids"] == [1]
    assert state["current_topic"] == "campus_wifi"
    assert state["current_intent"] == "lookup"
    assert state["referenced_slots"]["location"] == "梅園"
    assert state["current_slots"]["location"] == "台達館"
    assert state["semantic_slots"]["location"] == "台達館"
    assert query == "台達館有哪些校園無線網路可以使用？"


def test_only_explicit_missing_reference_is_unresolved():
    state, _ = standalone("回到第一個問題", [])
    assert state["reference_status"] == "unresolved"
    assert state["referenced_turn_ids"] == []


@pytest.mark.parametrize("_repeat", range(2))
def test_ordinal_return_preserves_dorm_application_and_transfer(_repeat: int):
    state, query = standalone(
        "回到第一個問題，如果我是換宿的呢？",
        conversation("宿網怎麼申請？", "學生信箱怎麼申請？"),
    )

    assert state["reference_status"] == "resolved"
    assert state["referenced_turn_ids"] == [1]
    assert state["current_topic"] == "dorm_network"
    assert state["current_intent"] == "application"
    assert state["semantic_slots"]["dorm_transfer"] == "true"
    assert "重新申請" in query
    assert "連不上" not in query



@pytest.mark.parametrize("repeat", range(2))
def test_full_chat_regressions_are_stable(repeat: int):
    home = chat(ChatRequest(message="如果我要在家連學校網路可以嗎？", session_id=f"home-{repeat}"))
    mei = chat(ChatRequest(message="梅園有網路嗎？", session_id=f"mei-{repeat}"))
    delta = chat(
        ChatRequest(
            message="台達館呢？",
            history=conversation("梅園有網路嗎？"),
            session_id=f"delta-{repeat}",
        )
    )
    unresolved = chat(ChatRequest(message="回到第一個問題"))
    dorm = chat(
        ChatRequest(
            message="回到第一個問題，如果我是換宿的呢？",
            history=conversation("宿網怎麼申請？", "學生信箱怎麼申請？"),
            session_id=f"dorm-{repeat}",
        )
    )

    for response in (home, mei, delta, unresolved, dorm):
        assert isinstance(response["answer"], str)
        assert isinstance(response["sources"], list)

    assert "VPN" in home["answer"]
    assert "梅園" in mei["answer"] and "找不到前一題" not in mei["answer"]
    assert "台達館" in delta["answer"] and "校園無線網路" in delta["answer"]
    assert "找不到" in unresolved["answer"]
    assert dorm["answer"].startswith("換宿後的宿網申請流程")
    assert "交叉測試" not in dorm["answer"]

@pytest.mark.parametrize("path", ("langgraph", "clarification", "scope_guard"))
def test_chat_response_schema_is_identical_across_paths(path: str):
    response = finalize_chat_response(
        {"answer": "文字回答", "sources": []},
        {"current_user_message": "測試"},
        path=path,
    )
    assert response == {"answer": "文字回答", "sources": []}
    assert isinstance(response["answer"], str)
    assert isinstance(response["sources"], list)


def test_fastapi_json_schema_matches_for_normal_clarification_and_refusal():
    payloads = (
        {"message": "如果我要在家連學校網路可以嗎？"},
        {"message": "回到第一個問題"},
        {"message": "今天吃什麼？"},
    )
    with TestClient(app) as client:
        for payload in payloads:
            response = client.post("/chat", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data["answer"], str)
            assert isinstance(data["sources"], list)


def test_chat_response_schema_rejects_object_answer():
    with pytest.raises(ValidationError):
        finalize_chat_response(
            {"answer": {"message": "不應被轉字串"}, "sources": []},
            {},
            path="langgraph",
        )


def test_frontend_extracts_structured_error_and_never_stringifies_answer_object():
    source = Path("frontend/app.js").read_text(encoding="utf-8")
    assert 'typeof detail.message === "string"' in source
    assert 'typeof data.answer !== "string"' in source
    assert 'const lines = String(text || "")' not in source
    assert 'new Error(data.detail || t("serviceError"))' not in source
