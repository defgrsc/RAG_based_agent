import unittest
from unittest.mock import patch

from agent.graph import build_agent_graph, prepare_agent_context


def conversation(*user_messages: str) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for message in user_messages:
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": f"回答：{message}"})
    return history


class ContextResolutionTests(unittest.TestCase):
    def test_case_1_current_wifi_overrides_dorm_history(self):
        state = prepare_agent_context(
            "Wi-Fi 連不上怎麼辦？",
            conversation("宿網怎麼申請？"),
        )
        self.assertEqual(state["current_topic"], "campus_wifi")
        self.assertEqual(state["relation"], "new_topic")
        self.assertEqual(state["relevant_turn_ids"], [2])
        self.assertEqual(state["relevant_history"], [])

    def test_case_2_current_vpn_overrides_wifi_history(self):
        state = prepare_agent_context(
            "VPN 怎麼設定？",
            conversation("Wi-Fi 連不上？"),
        )
        self.assertEqual(state["current_topic"], "vpn")
        self.assertEqual(state["relation"], "new_topic")

    def test_case_3_ordinal_reference_returns_to_first_topic(self):
        state = prepare_agent_context(
            "第一個要去哪裡申請？",
            conversation("宿網怎麼申請？", "Wi-Fi 連不上？"),
        )
        self.assertEqual(state["current_topic"], "dorm_network")
        self.assertEqual(state["relation"], "follow_up")
        self.assertEqual(state["referenced_turn_ids"], [1])
        self.assertEqual(state["relevant_turn_ids"], [1, 3])
        self.assertEqual({item["turn_id"] for item in state["relevant_history"]}, {1})

    def test_ordinal_application_intent_beats_assistant_ip_mentions(self):
        from main import rewrite_graph_query

        state = prepare_agent_context(
            "那剛剛第一個要去哪裡申請？",
            conversation("宿網怎麼申請？", "Wi-Fi 連不上？"),
        )
        relevant = [
            {"role": item["role"], "content": item["content"]}
            for item in state["relevant_history"]
        ]
        relevant[1]["content"] += " 申請完成後會取得 IP 設定資訊，也可查詢 IP。"
        self.assertEqual(
            rewrite_graph_query(state["current_user_message"], relevant),
            "宿舍網路怎麼申請？",
        )

    def test_case_4_implicit_follow_up_uses_latest_topic(self):
        state = prepare_agent_context(
            "那要去哪裡申請？",
            conversation("宿網怎麼申請？"),
        )
        self.assertEqual(state["current_topic"], "dorm_network")
        self.assertEqual(state["relation"], "follow_up")
        self.assertEqual(state["referenced_turn_ids"], [1])

    def test_generic_account_follow_up_keeps_the_service_topic(self):
        state = prepare_agent_context(
            "那帳號要怎麼申請呢？",
            conversation("Wi-Fi 連不上？"),
        )
        self.assertEqual(state["current_topic"], "campus_wifi")
        self.assertEqual(state["relation"], "follow_up")

    def test_english_substrings_do_not_create_false_follow_up(self):
        state = prepare_agent_context(
            "security policy",
            conversation("Wi-Fi 連不上？"),
        )
        self.assertEqual(state["current_topic"], "unknown")
        self.assertEqual(state["relation"], "new_topic")

    def test_full_history_is_retained_before_relevant_prompt_truncation(self):
        long_answer = "甲" * 2000
        state = prepare_agent_context(
            "那要去哪裡申請？",
            [
                {"role": "user", "content": "宿網怎麼申請？"},
                {"role": "assistant", "content": long_answer},
            ],
        )
        self.assertEqual(state["conversation_history"][1]["content"], long_answer)

    def test_case_5_explicit_wifi_is_not_dorm_troubleshooting(self):
        state = prepare_agent_context(
            "Wi-Fi 也連不上。",
            conversation("宿網連不上。"),
        )
        self.assertEqual(state["current_topic"], "campus_wifi")
        self.assertEqual(state["relation"], "new_topic")
        self.assertEqual(state["relevant_history"], [])

    def test_public_building_network_issue_overrides_dorm_history(self):
        for question in (
            "最近在圖書館網路很差欸為什麼",
            "最近在教育館網路很差欸為什麼",
            "教育館網路很差欸為什麼",
        ):
            with self.subTest(question=question):
                state = prepare_agent_context(
                    question,
                    conversation("宿網連不上怎麼辦？"),
                )
                self.assertEqual(state["current_topic"], "campus_wifi")
                self.assertEqual(state["relation"], "new_topic")
                self.assertEqual(state["referenced_turn_ids"], [])
                self.assertEqual(state["relevant_history"], [])

    def test_new_topic_does_not_reuse_old_same_topic_history(self):
        state = prepare_agent_context(
            "最近在教育館網路很差欸為什麼",
            conversation("Wi-Fi 帳號怎麼申請？", "宿網連不上怎麼辦？"),
        )
        self.assertEqual(state["current_topic"], "campus_wifi")
        self.assertEqual(state["relation"], "new_topic")
        self.assertEqual(state["relevant_history"], [])

    def test_public_buildings_share_specific_wireless_troubleshooting(self):
        from fast_answers import get_fast_answer

        for place in ("圖書館", "教育館"):
            with self.subTest(place=place):
                response = get_fast_answer(f"最近在{place}網路很差欸為什麼")
                self.assertIsNotNone(response)
                answer = response["answer"]
                self.assertIn("確認連線來源", answer)
                self.assertIn("設備干擾或距離過遠", answer)
                self.assertIn("IP 或認證狀態異常", answer)
                self.assertNotIn("宿網", answer)

    def test_chat_public_building_issue_isolated_from_dorm_history(self):
        from main import ChatHistoryItem, ChatRequest, chat

        history = [
            ChatHistoryItem(role="user", content="宿網連不上怎麼辦？"),
            ChatHistoryItem(role="assistant", content="請檢查宿網 IP、網路線與宿舍網路孔。"),
        ]
        for place in ("圖書館", "教育館"):
            with self.subTest(place=place):
                response = chat(
                    ChatRequest(
                        message=f"最近在{place}網路很差欸為什麼",
                        history=history,
                        language="zh-Hant",
                    )
                )
                self.assertIn("確認連線來源", response["answer"])
                self.assertIn("IP 或認證狀態異常", response["answer"])
                self.assertNotIn("宿網", response["answer"])


class ContextAndIntentRegressionTests(unittest.TestCase):
    def test_colloquial_ordinal_wordings_resolve_the_first_user_turn(self):
        for wording in (
            "第一題那個要去哪辦？",
            "第1題可以再講一次嗎？",
            "最前面那題咧？",
            "回到第一個問題啦",
        ):
            with self.subTest(wording=wording):
                state = prepare_agent_context(
                    wording,
                    conversation("宿網怎麼申請？", "GAPP 帳號怎麼申請？"),
                )
                self.assertEqual(state["current_topic"], "dorm_network")
                self.assertEqual(state["reference_status"], "resolved")
                self.assertEqual(state["referenced_turn_ids"], [1])

    def test_named_topic_return_preserves_application_intent_and_transfer(self):
        from main import rewrite_graph_query

        state = prepare_agent_context(
            "先回宿網那題啦，我剛換房間，這個要重辦嗎？",
            conversation("宿網怎麼申請？", "GAPP 帳號怎麼申請？"),
        )
        relevant = [
            {"role": item["role"], "content": item["content"]}
            for item in state["relevant_history"]
        ]

        self.assertEqual(state["current_topic"], "dorm_network")
        self.assertEqual(state["current_intent"], "application")
        self.assertEqual(state["relation"], "follow_up")
        self.assertEqual(state["referenced_turn_ids"], [1])
        self.assertEqual(
            rewrite_graph_query(state["current_user_message"], relevant),
            "換宿後宿網需要重新申請嗎？",
        )

    def test_exact_known_topic_return_is_application_not_troubleshooting(self):
        from main import rewrite_graph_query

        state = prepare_agent_context(
            "回到第一個問題，如果我是換宿的呢？",
            conversation("宿網怎麼申請？", "學生信箱怎麼申請？"),
        )
        relevant = [
            {"role": item["role"], "content": item["content"]}
            for item in state["relevant_history"]
        ]

        self.assertEqual(state["reference_status"], "resolved")
        self.assertEqual(state["referenced_turn_ids"], [1])
        self.assertEqual(state["current_intent"], "application")
        rewritten = rewrite_graph_query(state["current_user_message"], relevant)
        self.assertIn("重新申請", rewritten)
        self.assertNotIn("連不上", rewritten)

    def test_colloquial_same_topic_intent_switch_drops_application_history(self):
        from agent.topics import ensure_topic_in_query

        state = prepare_agent_context(
            "啊我都辦完了，結果現在上不了網欸",
            conversation("宿網要怎麼申請？"),
        )

        self.assertEqual(state["current_topic"], "dorm_network")
        self.assertEqual(state["current_intent"], "troubleshooting")
        self.assertEqual(state["relation"], "intent_switch")
        self.assertEqual(state["reference_status"], "none")
        self.assertEqual(state["referenced_turn_ids"], [])
        self.assertEqual(state["relevant_history"], [])
        self.assertEqual(
            ensure_topic_in_query(state["current_user_message"], state["current_topic"]),
            "宿網：啊我都辦完了，結果現在上不了網欸",
        )

    def test_unresolved_colloquial_reference_clarifies_before_scope_guard(self):
        from main import ChatRequest, chat

        state = prepare_agent_context("欸前面那個到底怎麼弄啦？", [])
        self.assertEqual(state["reference_status"], "unresolved")
        self.assertEqual(state["referenced_turn_ids"], [])

        response = chat(ChatRequest(message="欸前面那個到底怎麼弄啦？"))
        self.assertIn("找不到", response["answer"])
        self.assertIn("再貼一次", response["answer"])
        self.assertEqual(response["sources"], [])

    def test_dismissed_dorm_clause_cannot_select_dorm_fast_answer(self):
        from fast_answers import get_fast_answer
        from main import fast_answer_matches_topic, infer_fast_answer_topics
        from agent.topics import focus_message_on_topic

        question = "宿網先放一邊啦，我現在是要問 GAPP 帳號怎麼申請"
        state = prepare_agent_context(question, conversation("宿網連不上？"))
        focused = focus_message_on_topic(question, state["current_topic"])
        raw_response = get_fast_answer(question)
        focused_response = get_fast_answer(focused)

        self.assertEqual(state["current_topic"], "email")
        self.assertEqual(state["relation"], "new_topic")
        self.assertEqual(focused, "我現在是要問 GAPP 帳號怎麼申請")
        self.assertEqual(infer_fast_answer_topics(raw_response), {"dorm_network"})
        self.assertFalse(fast_answer_matches_topic(raw_response, "email"))
        self.assertIn("email", infer_fast_answer_topics(focused_response))
        self.assertTrue(fast_answer_matches_topic(focused_response, "email"))

        for alternate in (
            "前面宿網擺一邊，我想辦的是 GAPP。",
            "宿網先不管，換問 GAPP 怎麼申請。",
            "先把宿網略過，我現在要處理 GAPP。",
            "先不講宿網那題了，那 GAPP 帳號要去哪裡申請咧？",
        ):
            with self.subTest(alternate=alternate):
                alternate_state = prepare_agent_context(alternate, conversation("宿網連不上？"))
                self.assertEqual(alternate_state["current_topic"], "email")
                self.assertEqual(alternate_state["relation"], "new_topic")
                self.assertEqual(alternate_state["reference_status"], "none")

    def test_colloquial_gapp_application_variants_use_email_fast_answer(self):
        from fast_answers import get_fast_answer
        from main import ChatRequest, chat, infer_fast_answer_topics
        from agent.topics import focus_message_on_topic

        cases = (
            ("那 Google Workspace 要去哪申請？", []),
            ("前面宿網擺一邊，我想辦的是 GAPP。", conversation("宿網連不上？")),
            ("GAPP 要去哪辦？", []),
        )
        for message, history in cases:
            with self.subTest(message=message):
                state = prepare_agent_context(message, history)
                focused = focus_message_on_topic(message, state["current_topic"])
                fast_response = get_fast_answer(focused)

                self.assertEqual(state["current_topic"], "email")
                self.assertEqual(state["current_intent"], "application")
                self.assertIsNotNone(fast_response)
                self.assertIn("email", infer_fast_answer_topics(fast_response))
                response = chat(ChatRequest(message=message, history=history))
                self.assertIn("gapp", response["answer"].lower())
                self.assertTrue(response["sources"])

    def test_deepeval_discovered_oral_failures_stay_on_fast_paths(self):
        from main import ChatRequest, chat, resolve_contextual_followup_question

        application_message = "欸，宿網要去哪裡辦啊？"
        application_state = prepare_agent_context(application_message, [])
        self.assertEqual(application_state["current_intent"], "application")
        application_response = chat(ChatRequest(message=application_message))
        self.assertIn("宿網申請共分成", application_response["answer"])
        self.assertTrue(application_response["sources"])

        dorm_history = conversation("欸，宿網要去哪辦啊？")
        dorm_message = "啊我都弄好了，結果還是上不了網欸。"
        dorm_state = prepare_agent_context(dorm_message, dorm_history)
        self.assertEqual(dorm_state["current_topic"], "dorm_network")
        self.assertEqual(dorm_state["current_intent"], "troubleshooting")
        self.assertEqual(dorm_state["relation"], "intent_switch")
        dorm_response = chat(ChatRequest(message=dorm_message, history=dorm_history))
        self.assertIn("狀態", dorm_response["answer"])
        self.assertNotIn("宿網申請共分成", dorm_response["answer"])
        bare_dorm_message = "宿網好像有點問題，我是要問宿網故障的事。"
        bare_dorm_state = prepare_agent_context(bare_dorm_message, [])
        self.assertEqual(bare_dorm_state["current_intent"], "troubleshooting")
        bare_dorm_response = chat(ChatRequest(message=bare_dorm_message))
        self.assertIn("狀態", bare_dorm_response["answer"])

        wifi_message = "我手機上的 Wi-Fi 訊號明明滿格，但是網頁完全載不出來，動都動不了。"
        wifi_state = prepare_agent_context(wifi_message, [])
        self.assertEqual(wifi_state["current_topic"], "campus_wifi")
        self.assertEqual(wifi_state["current_intent"], "troubleshooting")
        wifi_response = chat(ChatRequest(message=wifi_message))
        self.assertIn("認證問題", wifi_response["answer"])
        self.assertTrue(wifi_response["sources"])

        spinning_message = "手機 Wi-Fi 顯示連上了，但打開網頁一直轉圈轉不出來。"
        spinning_state = prepare_agent_context(spinning_message, [])
        self.assertEqual(spinning_state["current_intent"], "troubleshooting")
        spinning_response = chat(ChatRequest(message=spinning_message))
        self.assertIn("認證問題", spinning_response["answer"])
        self.assertTrue(spinning_response["sources"])

        closed_page_message = "手機顯示 Wi-Fi 已連線，為什麼網頁還是完全打不開？"
        closed_page_state = prepare_agent_context(closed_page_message, [])
        self.assertEqual(closed_page_state["current_intent"], "troubleshooting")
        closed_page_response = chat(ChatRequest(message=closed_page_message))
        self.assertIn("認證問題", closed_page_response["answer"])
        self.assertTrue(closed_page_response["sources"])

        ssid_message = "清大校園無線網路有哪些 SSID 可以連？"
        ssid_state = prepare_agent_context(ssid_message, [])
        self.assertEqual(ssid_state["current_intent"], "lookup")
        ssid_response = chat(ChatRequest(message=ssid_message))
        self.assertIn("nthu-cc", ssid_response["answer"])
        self.assertIn("eduroam", ssid_response["answer"])
        self.assertTrue(ssid_response["sources"])

        transfer_history = conversation(
            "宿網要去哪辦啊？",
            "GAPP 帳號怎麼申請？",
        )
        transfer_message = (
            "好啦，那我們先回到宿網那題咧，我剛換了房間，這個要重辦嗎？"
        )
        transfer_state = prepare_agent_context(transfer_message, transfer_history)
        relevant_history = [
            {"role": item["role"], "content": item["content"]}
            for item in transfer_state["relevant_history"]
        ]
        standalone = resolve_contextual_followup_question(
            transfer_message, relevant_history
        )
        self.assertEqual(transfer_state["current_topic"], "dorm_network")
        self.assertEqual(transfer_state["current_intent"], "application")
        self.assertEqual(transfer_state["referenced_turn_ids"], [1])
        self.assertEqual(standalone, "換宿後宿網需要重新申請嗎？")
        transfer_response = chat(
            ChatRequest(message=transfer_message, history=transfer_history)
        )
        self.assertIn("換宿", transfer_response["answer"])
        self.assertTrue(transfer_response["sources"])

    def test_unseen_slang_still_classifies_service_and_intent(self):
        cases = (
            ("欸宿網到底要去哪辦啦", "dorm_network", "application"),
            ("學校那個 wifi 掛了欸", "campus_wifi", "troubleshooting"),
            ("清大 VPN 要怎麼裝啊", "vpn", "configuration"),
            ("GAPP 有哪些帳號功能？", "email", "lookup"),
        )
        for message, topic, intent in cases:
            with self.subTest(message=message):
                state = prepare_agent_context(message, [])
                self.assertEqual(state["current_topic"], topic)
                self.assertEqual(state["current_intent"], intent)
                self.assertEqual(state["relation"], "new_topic")


class GraphWorkflowTests(unittest.TestCase):
    def test_graph_uses_only_referenced_history_and_preserves_filter_interface(self):
        calls: dict = {}

        def rewrite(message, relevant_history):
            calls["rewrite_history"] = relevant_history
            return f"{relevant_history[0]['content']}；{message}"

        def retrieve(query, *, language, topic, metadata_filter):
            calls["retrieve"] = (query, language, topic, metadata_filter)
            return [
                {
                    "point_id": "doc-1",
                    "title": "宿網申請",
                    "url": "https://example.test/dorm",
                    "content": "宿網申請資料",
                    "score": 0.9,
                }
            ]

        def build_context(documents):
            return documents[0]["content"]

        def format_history(history):
            calls["generation_history"] = history
            return "\n".join(item["content"] for item in history)

        def generate(message, context, history_context, language):
            calls["generate"] = (message, context, history_context, language)
            return "完成"

        graph = build_agent_graph(
            retrieve_fn=retrieve,
            rewrite_fn=rewrite,
            build_context_fn=build_context,
            format_history_fn=format_history,
            generate_fn=generate,
        )
        result = graph.invoke(
            {
                "current_user_message": "第一個要去哪裡申請？",
                "conversation_history": conversation("宿網怎麼申請？", "Wi-Fi 連不上？"),
                "language": "zh-Hant",
                "retrieval_filter": {"service": "dorm_network"},
                "metadata": {},
            }
        )

        self.assertEqual(result["answer"], "完成")
        self.assertEqual(result["current_topic"], "dorm_network")
        self.assertEqual(calls["retrieve"][2:], ("dorm_network", {"service": "dorm_network"}))
        self.assertNotIn("Wi-Fi 連不上？", calls["generate"][2])
        self.assertEqual({item["turn_id"] for item in result["relevant_history"]}, {1})


class QdrantFilterInterfaceTests(unittest.TestCase):
    @patch("qdrant_store.requests.post")
    def test_search_serializes_metadata_filter(self, post):
        from qdrant_store import search_similar

        post.return_value.json.return_value = {"result": []}
        search_similar([0.1, 0.2], 5, metadata_filter={"service": "dorm_network"})

        request_body = post.call_args.kwargs["json"]
        self.assertEqual(
            request_body["filter"],
            {"must": [{"key": "service", "match": {"value": "dorm_network"}}]},
        )


if __name__ == "__main__":
    unittest.main()
