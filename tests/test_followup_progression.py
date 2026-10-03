import unittest

from agent.followups import build_progression_query
from agent.graph import prepare_agent_context
from agent.progression_policy import build_progression_response


def history(*items: tuple[str, str]) -> list[dict[str, str]]:
    return [{"role": role, "content": content} for role, content in items]


class FollowupStateTests(unittest.TestCase):
    def test_cross_test_result_keeps_problem_and_assistant_recommendation(self):
        state = prepare_agent_context(
            "I tried my roommate's network port and it works.",
            history(
                ("user", "My DormNet connection is not working."),
                ("assistant", "Please cross-test the same device on another port."),
            ),
            language="en",
        )
        self.assertEqual(state["current_topic"], "dorm_network")
        self.assertEqual(state["current_intent"], "troubleshooting")
        self.assertEqual(state["followup_type"], "action_result")
        self.assertIn("cross_test", state["previous_recommendations"])
        self.assertEqual(state["current_action_results"][0]["outcome"], "works")
        self.assertTrue(any(item["role"] == "assistant" for item in state["relevant_history"]))

    def test_plain_peer_answer_is_diagnostic_not_completed_action(self):
        state = prepare_agent_context(
            "My roommate can connect; only mine fails.",
            history(
                ("user", "DormNet is not working."),
                ("assistant", "Can your roommate connect?"),
            ),
            language="en",
        )
        self.assertEqual(state["followup_type"], "diagnostic_answer")
        self.assertEqual(
            state["current_action_results"][0],
            {
                "action": "peer_check",
                "outcome": "peer_works",
                "detail": "My roommate can connect; only mine fails.",
                "turn_id": 2,
            },
        )

    def test_partial_result_preserves_completed_failed_and_pending_checks(self):
        state = prepare_agent_context(
            "A works, B still fails on nthupeap, and I have not tried C yet.",
            history(
                ("user", "Campus Wi-Fi authentication keeps failing."),
                ("assistant", "Please test A, B, and C."),
            ),
            language="en",
        )
        result_pairs = {
            (item["action"], item["outcome"])
            for item in state["current_action_results"]
        }
        self.assertIn(("check_a", "works"), result_pairs)
        self.assertIn(("check_b", "still_fails"), result_pairs)
        self.assertIn(("check_c", "pending"), result_pairs)

    def test_successful_fix_sets_resolved(self):
        state = prepare_agent_context(
            "I corrected the settings and that fixed it.",
            history(
                ("user", "My NTHU VPN connection keeps failing."),
                ("assistant", "Please correct the VPN settings and reconnect."),
            ),
            language="en",
        )
        self.assertEqual(state["followup_type"], "action_result")
        self.assertEqual(state["resolution_status"], "resolved")

    def test_rejected_step_is_blocked_and_linked_to_reinstall(self):
        state = prepare_agent_context(
            "I cannot reinstall it right now. Is there another option?",
            history(
                ("user", "The VPN client will not open."),
                ("assistant", "Please reinstall the VPN client."),
            ),
            language="en",
        )
        self.assertEqual(state["followup_type"], "recommendation_rejected")
        self.assertEqual(state["resolution_status"], "blocked")
        self.assertEqual(state["current_action_results"][0]["action"], "reinstall")

    def test_application_continuation_switches_to_configuration(self):
        state = prepare_agent_context(
            "The application is complete. How do I log in now?",
            history(
                ("user", "How do I apply for a student email account?"),
                ("assistant", "Complete the student email application."),
            ),
            language="en",
        )
        self.assertEqual(state["current_topic"], "email")
        self.assertEqual(state["followup_type"], "continuation")
        self.assertEqual(state["current_intent"], "configuration")

    def test_long_chain_retains_progress_and_six_turn_window(self):
        chain = history(
            ("user", "Campus Wi-Fi authentication keeps failing."),
            ("assistant", "Please reconnect and tell me the result."),
            ("user", "I reconnected, but it still does not work."),
            ("assistant", "Please forget the saved Wi-Fi network."),
            ("user", "Why should I forget the network?"),
            ("assistant", "It clears stale settings; remove and re-add the network."),
            ("user", "I removed and re-added it, but authentication still fails."),
            ("assistant", "Please verify the account and 802.1X settings."),
        )
        state = prepare_agent_context(
            "I finished those steps. Who should I contact next?",
            chain,
            language="en",
        )
        progress = {
            (item["action"], item["outcome"])
            for item in state["troubleshooting_progress"]
        }
        self.assertIn(("reconnect", "still_fails"), progress)
        self.assertIn(("forget_network", "still_fails"), progress)
        self.assertEqual(state["current_topic"], "campus_wifi")
        self.assertLessEqual(len(set(state["relevant_turn_ids"][:-1])), 6)

    def test_ordinal_reference_does_not_leak_other_topic_assistant(self):
        state = prepare_agent_context(
            "第一個要去哪裡申請？",
            history(
                ("user", "宿網怎麼申請？"),
                ("assistant", "請依宿網申請流程辦理。"),
                ("user", "Wi-Fi 連不上？"),
                ("assistant", "請檢查 Wi-Fi 設定。"),
            ),
        )
        self.assertEqual(state["referenced_turn_ids"], [1])
        self.assertNotIn("Wi-Fi", state.get("pending_question") or "")
        self.assertNotIn("wifi", " ".join(state["previous_recommendations"]))


class ProgressionPolicyTests(unittest.TestCase):
    def test_query_contains_original_problem_and_latest_result(self):
        state = prepare_agent_context(
            "重新連過了，還是不行。",
            history(
                ("user", "校園 Wi-Fi 連不上。"),
                ("assistant", "請先重新連線。"),
            ),
        )
        query = build_progression_query(state["current_user_message"], state)
        self.assertIn("校園 Wi-Fi 連不上", query or "")
        self.assertIn("重新連過了", query or "")

    def test_policy_does_not_escalate_explanation_but_escalates_port_result(self):
        explanation = prepare_agent_context(
            "Why should I cross-test another port?",
            history(
                ("user", "DormNet is not working."),
                ("assistant", "Please cross-test another port."),
            ),
            language="en",
        )
        explanation_answer = build_progression_response(explanation)["answer"]
        self.assertNotIn("dorms@", explanation_answer)
        self.assertNotIn("contact", explanation_answer.casefold())

        escalation = prepare_agent_context(
            "I tried my roommate's network port and it works.",
            history(
                ("user", "DormNet is not working."),
                ("assistant", "Please cross-test another port."),
            ),
            language="en",
        )
        escalation_answer = build_progression_response(escalation)["answer"]
        self.assertIn("dorms@cc.nthu.edu.tw", escalation_answer)
        self.assertIn("cross-test result", escalation_answer)


if __name__ == "__main__":
    unittest.main()
