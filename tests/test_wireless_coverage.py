import time
from unittest.mock import patch

import pytest

from agent.graph import prepare_agent_context
from agent.nodes.retrieve import make_retrieve_node
from agent.state import history_for_legacy_functions
from main import ChatHistoryItem, ChatRequest, chat, standalone_question_for_state
from response_cache import clear_all_caches
from wireless_coverage import (
    PUBLIC_COVERAGE_URL,
    UNIFORM_COVERAGE_URL,
    build_coverage_documents,
    lookup_coverage,
)


def _raw_history(history: list[ChatHistoryItem]) -> list[dict[str, str]]:
    return [{"role": item.role, "content": item.content} for item in history]


def _trace(message: str, history: list[ChatHistoryItem]):
    state = prepare_agent_context(message, _raw_history(history))
    relevant = history_for_legacy_functions(state.get("relevant_history", []))
    standalone = standalone_question_for_state(message, state, relevant)
    return state, standalone


def test_library_to_education_comparison_answers_account_scope_first():
    history = [
        ChatHistoryItem(role="user", content="圖書館那邊的網路怎麼申請啊"),
        ChatHistoryItem(role="assistant", content="請從校務資訊系統申請無線網路帳號。"),
    ]
    message = "教育館那邊的網路申請跟圖書館一樣嗎？還是我總共只需要申請一個就好？"

    state, standalone = _trace(message, history)
    assert state["relation"] == "follow_up"
    assert state["current_topic"] == "campus_wifi"
    assert state["current_intent"] == "comparison"
    assert state["current_slots"]["location"] == "教育館"
    assert state["referenced_slots"]["location"] == "圖書館"
    assert "教育館" in standalone
    assert "圖書館" in standalone
    assert "同一個帳號" in standalone

    clear_all_caches()
    with patch("main.get_compiled_agent_graph") as graph:
        started = time.perf_counter()
        response = chat(ChatRequest(message=message, history=history))
        elapsed = time.perf_counter() - started

    graph.assert_not_called()
    answer = response["answer"]
    assert elapsed < 5
    assert answer.startswith("是的。")
    assert "只需要申請一個校園無線網路帳號" in answer
    assert "nthupeap" in answer
    assert answer.index("只需要申請一個") < answer.index("**申請無線網路帳號**")
    assert UNIFORM_COVERAGE_URL in {source["url"] for source in response["sources"]}


def test_location_followup_chain_updates_only_location_slot():
    history: list[ChatHistoryItem] = []
    cases = (
        ("人社院有網路嗎？", "人文社會學院", "nthupeap", "人社院有網路嗎？"),
        ("體育館呢？", "體育館", "eduroam", "體育館有哪些校園無線網路可以使用？"),
        ("台達呢？", "台達館", "nthu-mse", "台達館有哪些校園無線網路可以使用？"),
        ("梅園呢？", "梅園", "梅園入口處區域", "梅園有哪些校園無線網路可以使用？"),
    )

    clear_all_caches()
    with patch("main.get_compiled_agent_graph") as graph:
        for message, location, answer_marker, expected_standalone in cases:
            state, standalone = _trace(message, history)
            assert state["current_topic"] == "campus_wifi"
            assert state["current_intent"] == "lookup"
            assert state["semantic_slots"]["location"] == location
            assert standalone == expected_standalone

            started = time.perf_counter()
            response = chat(ChatRequest(message=message, history=history))
            assert time.perf_counter() - started < 5
            assert answer_marker in response["answer"]
            history.extend(
                [
                    ChatHistoryItem(role="user", content=message),
                    ChatHistoryItem(role="assistant", content=response["answer"]),
                ]
            )

    graph.assert_not_called()


@pytest.mark.parametrize(
    ("message", "location", "answer_marker", "source_url"),
    (
        ("體育館有網路嗎？", "體育館", "TANetRoaming", PUBLIC_COVERAGE_URL),
        ("台達館有網路嗎？", "台達館", "台達館 B1F,4F", UNIFORM_COVERAGE_URL),
        ("李存敏館可以上網嗎？", "李存敏館", "nthu-nes", UNIFORM_COVERAGE_URL),
        ("創新育成大樓有沒有無線網路？", "創新育成大樓", "nthu-cii", UNIFORM_COVERAGE_URL),
    ),
)
def test_standalone_official_locations_use_structured_coverage(
    message: str,
    location: str,
    answer_marker: str,
    source_url: str,
):
    state, _ = _trace(message, [])
    assert state["current_topic"] == "campus_wifi"
    assert state["current_intent"] == "lookup"
    assert state["semantic_slots"]["location"] == location

    clear_all_caches()
    with patch("main.get_compiled_agent_graph") as graph:
        started = time.perf_counter()
        response = chat(ChatRequest(message=message))
        elapsed = time.perf_counter() - started

    graph.assert_not_called()
    assert elapsed < 5
    assert answer_marker in response["answer"]
    assert source_url in {source["url"] for source in response["sources"]}


def test_unlisted_location_is_honest_and_does_not_claim_wifi():
    message = "星際探索館有網路嗎？"
    assert lookup_coverage("星際探索館")["match_level"] == "none"

    clear_all_caches()
    with patch("main.get_compiled_agent_graph") as graph:
        response = chat(ChatRequest(message=message))

    graph.assert_not_called()
    assert "目前查不到" in response["answer"]
    assert "無法直接確認" in response["answer"]
    assert not response["answer"].startswith("有，")
    assert {source["url"] for source in response["sources"]} == {
        UNIFORM_COVERAGE_URL,
        PUBLIC_COVERAGE_URL,
    }


def test_meiyuan_partial_match_does_not_expand_coverage():
    result = lookup_coverage("梅園")
    assert result["match_level"] == "partial"

    response = chat(ChatRequest(message="梅園有網路嗎？"))
    assert "目前只能確認" in response["answer"]
    assert "體育館戶外廣場(梅園入口處區域)" in response["answer"]
    assert "不代表「梅園」的其他區域也有 Wi-Fi" in response["answer"]


def test_coverage_ingestion_keeps_location_and_ssids_in_same_document():
    documents = build_coverage_documents()
    assert len(documents) == 74
    assert all(document["service"] == "campus_wifi" for document in documents)
    assert all(document["intent"] == "coverage" for document in documents)
    assert all(document["location"] in document["content"] for document in documents)
    assert all(document["location_keys"] for document in documents)

    delta = [document for document in documents if document["location"].startswith("台達館")]
    assert len(delta) == 3
    assert all("SSID：" in document["content"] for document in delta)


def test_retrieval_node_applies_coverage_metadata_filter():
    captured = {}

    def retrieve(query, *, language, topic, metadata_filter):
        captured.update(
            query=query,
            language=language,
            topic=topic,
            metadata_filter=metadata_filter,
        )
        return []

    node = make_retrieve_node(retrieve, lambda message, history: message)
    result = node(
        {
            "current_user_message": "台達呢？",
            "standalone_query": "台達有哪些校園無線網路可以使用？",
            "current_topic": "campus_wifi",
            "current_intent": "lookup",
            "semantic_slots": {"location": "台達"},
            "language": "zh-Hant",
            "relevant_history": [],
            "metadata": {},
        }
    )

    assert captured["metadata_filter"] == {
        "service": "campus_wifi",
        "intent": "coverage",
    }
    assert result["retrieval_filter"] == captured["metadata_filter"]
INTERNAL_IMPLEMENTATION_TERMS = (
    "coverage",
    "rag",
    "retrieval",
    "embedding",
    "這兩份資料",
    "根據這兩份",
)


def _assert_user_facing_answer(answer: str) -> None:
    normalized = answer.lower()
    assert all(term not in normalized for term in INTERNAL_IMPLEMENTATION_TERMS)


@pytest.mark.parametrize("_repeat", range(3))
@pytest.mark.parametrize(
    "message",
    (
        "人社院有網路嗎？",
        "噢噢那人社院有網路嗎？",
    ),
)
def test_colloquial_prefix_does_not_pollute_location_entity(
    message: str,
    _repeat: int,
):
    state, _ = _trace(message, [])
    assert state["current_topic"] == "campus_wifi"
    assert state["current_intent"] == "lookup"
    assert state["current_slots"]["location"] == "人文社會學院"
    assert state["semantic_slots"]["question_focus"] == "network_availability"

    clear_all_caches()
    with patch("main.get_compiled_agent_graph") as graph:
        started = time.perf_counter()
        response = chat(ChatRequest(message=message, session_id=f"colloquial-{_repeat}"))
        elapsed = time.perf_counter() - started

    graph.assert_not_called()
    assert elapsed < 5
    assert "nthupeap" in response["answer"]
    _assert_user_facing_answer(response["answer"])


@pytest.mark.parametrize("_repeat", range(3))
def test_campus_coverage_location_followup_chain(_repeat: int):
    clear_all_caches()
    history: list[ChatHistoryItem] = []

    q1 = "學校哪裡有網路？"
    q1_state, _ = _trace(q1, history)
    assert q1_state["current_topic"] == "campus_wifi"
    assert q1_state["current_intent"] == "lookup"
    assert "location" not in q1_state["current_slots"]
    assert q1_state["semantic_slots"]["coverage_scope"] == "campus"
    assert q1_state["semantic_slots"]["question_focus"] == "coverage_list"

    with patch("main.get_compiled_agent_graph") as graph:
        q1_response = chat(
            ChatRequest(message=q1, history=history, session_id=f"coverage-chain-{_repeat}")
        )
        history.extend(
            (
                ChatHistoryItem(role="user", content=q1),
                ChatHistoryItem(role="assistant", content=q1_response["answer"]),
            )
        )

        q2 = "台達有嗎？"
        q2_state, q2_standalone = _trace(q2, history)
        assert q2_state["relation"] == "follow_up"
        assert q2_state["current_topic"] == "campus_wifi"
        assert q2_state["current_intent"] == "lookup"
        assert q2_state["current_slots"]["location"] == "台達館"
        assert q2_state["semantic_slots"]["question_focus"] == "network_availability"
        assert q2_standalone == "台達館有校園無線網路嗎？"
        q2_response = chat(
            ChatRequest(message=q2, history=history, session_id=f"coverage-chain-{_repeat}")
        )
        history.extend(
            (
                ChatHistoryItem(role="user", content=q2),
                ChatHistoryItem(role="assistant", content=q2_response["answer"]),
            )
        )

        q3 = "體育館有嗎？"
        q3_state, q3_standalone = _trace(q3, history)
        assert q3_state["relation"] == "follow_up"
        assert q3_state["current_topic"] == "campus_wifi"
        assert q3_state["current_intent"] == "lookup"
        assert q3_state["current_slots"]["location"] == "體育館"
        assert q3_state["semantic_slots"]["question_focus"] == "network_availability"
        assert q3_standalone == "體育館有校園無線網路嗎？"
        q3_response = chat(
            ChatRequest(message=q3, history=history, session_id=f"coverage-chain-{_repeat}")
        )

    graph.assert_not_called()
    assert "台達館" in q2_response["answer"]
    assert "體育館" in q3_response["answer"]
    for response in (q1_response, q2_response, q3_response):
        _assert_user_facing_answer(response["answer"])


@pytest.mark.parametrize("_repeat", range(3))
def test_campus_wifi_name_query_uses_structured_ssid_data(_repeat: int):
    message = "清大的無線網路是哪一個？"
    state, standalone = _trace(message, [])
    assert state["current_topic"] == "campus_wifi"
    assert state["current_intent"] == "lookup"
    assert state["semantic_slots"]["coverage_scope"] == "campus"
    assert state["semantic_slots"]["question_focus"] == "ssid_list"
    assert standalone == message

    clear_all_caches()
    with patch("main.get_compiled_agent_graph") as graph:
        started = time.perf_counter()
        response = chat(ChatRequest(message=message, session_id=f"ssid-list-{_repeat}"))
        elapsed = time.perf_counter() - started

    graph.assert_not_called()
    assert elapsed < 5
    assert "eduroam" in response["answer"]
    assert "nthupeap" in response["answer"]
    assert "目前暫時無法取得完整資料" not in response["answer"]
    _assert_user_facing_answer(response["answer"])


def test_ssid_query_applies_coverage_metadata_filter_without_location():
    captured = {}

    def retrieve(query, *, language, topic, metadata_filter):
        captured.update(
            query=query,
            language=language,
            topic=topic,
            metadata_filter=metadata_filter,
        )
        return []

    node = make_retrieve_node(retrieve, lambda message, history: message)
    result = node(
        {
            "current_user_message": "清大的 Wi-Fi 名稱有哪些？",
            "standalone_query": "清大的 Wi-Fi 名稱有哪些？",
            "current_topic": "campus_wifi",
            "current_intent": "lookup",
            "semantic_slots": {
                "coverage_scope": "campus",
                "question_focus": "ssid_list",
            },
            "language": "zh-Hant",
            "relevant_history": [],
            "metadata": {},
        }
    )

    assert captured["metadata_filter"] == {
        "service": "campus_wifi",
        "intent": "coverage",
    }
    assert result["retrieval_filter"] == captured["metadata_filter"]
