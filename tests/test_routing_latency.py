import time
from unittest.mock import Mock, patch

import pytest
import requests

from agent.graph import prepare_agent_context
from main import ChatHistoryItem, ChatRequest, chat
from response_cache import clear_all_caches, rag_cache
from service_errors import EmbeddingServiceError


INTERNAL_ERROR_TERMS = (
    "embedding",
    "qdrant",
    "model",
    "140.114.",
)


def _assert_no_internal_error(answer: str) -> None:
    normalized = answer.lower()
    assert not any(term in normalized for term in INTERNAL_ERROR_TERMS)

@pytest.mark.parametrize(
    ("message", "expected_topic"),
    (
        ("先不管宿網那題，我現在比較急的是 GAPP 帳號怎麼申請？", "email"),
        ("校園 Wi-Fi 先放著，我比較想問 VPN 要怎麼裝。", "vpn"),
    ),
)
def test_degree_adverb_does_not_trigger_service_comparison(message: str, expected_topic: str):
    state = prepare_agent_context(message, [])
    assert state["current_topic"] == expected_topic


def test_explicit_service_comparison_remains_ambiguous():
    state = prepare_agent_context("宿網跟校園 Wi-Fi 哪個比較適合我？", [])
    assert state["current_topic"] == "unknown"


@pytest.mark.parametrize(
    "message",
    (
        "交叉測試後室友也沒辦法連，這樣我要怎麼辦",
        "換裝置測試之後，同學的電腦也連不上，下一步呢？",
        "我請別人用另一台電腦交叉檢查，結果同樣不行",
    ),
)
def test_completed_cross_test_enters_escalation_without_repeating_checks(message: str):
    state = prepare_agent_context(message, [])
    assert state["current_topic"] == "dorm_network"
    assert state["current_intent"] == "troubleshooting"
    assert state["semantic_slots"]["troubleshooting_stage"] == "cross_test_failed"

    clear_all_caches()
    with patch("main.get_compiled_agent_graph") as graph:
        started = time.perf_counter()
        response = chat(ChatRequest(message=message))
        elapsed = time.perf_counter() - started

    graph.assert_not_called()
    assert elapsed < 5
    assert "dorms@cc.nthu.edu.tw" in response["answer"]
    assert "不需要再重複" in response["answer"]
    assert "先查狀態" not in response["answer"]
    assert "**做交叉測試**" not in response["answer"]
    assert response["sources"]
    _assert_no_internal_error(response["answer"])


def test_cross_test_evidence_survives_followup_query_rewrite():
    history = [
        ChatHistoryItem(role="user", content="宿網連不上怎麼辦？"),
        ChatHistoryItem(role="assistant", content="請先查狀態並做交叉測試。"),
    ]
    message = "交叉測試後室友也沒辦法連，這樣我要怎麼辦"

    with patch("main.get_compiled_agent_graph") as graph:
        response = chat(ChatRequest(message=message, history=history))

    graph.assert_not_called()
    assert "dorms@cc.nthu.edu.tw" in response["answer"]
    assert "先查狀態" not in response["answer"]


@pytest.mark.parametrize(
    ("message", "topic", "intent", "answer_marker"),
    (
        ("圖書館那邊的網路怎麼申請啊", "campus_wifi", "application", "申請無線網路帳號"),
        ("在總圖想上網，無線帳號要去哪辦？", "campus_wifi", "application", "無線區域網路帳號"),
        ("我剛搬進宿舍，要怎麼用宿舍網路？", "dorm_network", "application", "宿網申請共分成"),
        ("我是新住宿生，宿舍網路要怎麼開始用？", "dorm_network", "application", "宿網申請共分成"),
    ),
)
def test_unfamiliar_paraphrases_use_structured_fast_path(
    message: str,
    topic: str,
    intent: str,
    answer_marker: str,
):
    state = prepare_agent_context(message, [])
    assert state["current_topic"] == topic
    assert state["current_intent"] == intent

    clear_all_caches()
    with patch("main.get_compiled_agent_graph") as graph:
        started = time.perf_counter()
        response = chat(ChatRequest(message=message))
        elapsed = time.perf_counter() - started

    graph.assert_not_called()
    assert elapsed < 5
    assert answer_marker in response["answer"]
    assert response["sources"]
    _assert_no_internal_error(response["answer"])


def test_embedding_failure_returns_safe_answer_instead_of_internal_503():
    graph = Mock()
    graph.invoke.side_effect = EmbeddingServiceError(
        operation="embed",
        cause=requests.Timeout("private endpoint"),
    )

    clear_all_caches()
    with patch("main.get_compiled_agent_graph", return_value=graph):
        started = time.perf_counter()
        response = chat(ChatRequest(message="宿網的流量限制與停權規則是什麼？"))
        elapsed = time.perf_counter() - started

    assert elapsed < 5
    assert "稍後再試" in response["answer"]
    assert response["sources"]
    _assert_no_internal_error(response["answer"])


def test_embedding_circuit_breaker_avoids_repeated_calls():
    from llm import embed_texts, reset_embedding_circuit_breaker

    reset_embedding_circuit_breaker()
    try:
        with patch(
            "llm._embed_texts_unchecked",
            side_effect=requests.Timeout("endpoint unavailable"),
        ) as embedding_call:
            with pytest.raises(EmbeddingServiceError):
                embed_texts(["first"], timeout_seconds=0.01)
            with pytest.raises(EmbeddingServiceError) as second:
                embed_texts(["second"], timeout_seconds=0.01)

        assert embedding_call.call_count == 1
        assert second.value.category == "circuit_open"
    finally:
        reset_embedding_circuit_breaker()


def test_retrieval_uses_one_embedding_call_and_zero_llm_calls():
    from rag import retrieve_context

    rag_cache.clear()
    with (
        patch("rag.embed_texts", return_value=[[0.1, 0.2]]) as embedding,
        patch("rag.get_priority_chunks", return_value=[]),
        patch("rag.search_similar", return_value=[]) as search,
        patch("rag.expand_page_chunks", return_value=[]),
        patch("rag.rerank_results", return_value=[]),
        patch("rag.rerank_with_flashrank", return_value=[]),
        patch("llm._chat_completion") as llm_call,
    ):
        result = retrieve_context(
            "latency-regression-unique-query",
            topic="dorm_network",
        )

    assert result == []
    assert embedding.call_count == 1
    assert search.call_count == 1
    llm_call.assert_not_called()
