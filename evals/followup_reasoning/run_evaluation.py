from __future__ import annotations

import argparse
import io
import json
import logging
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.graph import prepare_agent_context
from evals.bug_discovery.agent_adapter import InProcessAgentAdapter, is_refusal
from evals.bug_discovery.schemas import AgentSettings


HERE = Path(__file__).resolve().parent
DATASET_PATH = HERE / "generated_cases.json"
FAILURE_ORDER = (
    "FOLLOWUP_RESOLUTION_ERROR",
    "ACTION_RESULT_ERROR",
    "TROUBLESHOOTING_STAGE_ERROR",
    "PREVIOUS_RECOMMENDATION_IGNORED",
    "DIAGNOSTIC_ANSWER_ERROR",
    "REPEATED_STEP_ERROR",
    "PREMATURE_ESCALATION",
    "MISSING_ESCALATION",
    "INCORRECT_REFUSAL",
    "ANSWER_CONTENT_ERROR",
)
ESCALATION_MARKERS = (
    "dorms@cc.nthu.edu.tw", "wlan@cc.nthu.edu.tw", "報修", "聯絡", "回報",
    "contact", "report", "support", "help desk",
)
REPEATED_ACTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "cross_test": (
        "請再做交叉測試", "再做一次交叉測試", "再測試室友",
        "try the cross-test again", "cross-test again",
        "try your roommate's port again",
    ),
    "reconnect": (
        "請重新連線", "再重新連線", "重新連線一次",
        "try reconnecting again", "reconnect again",
    ),
    "forget_network": (
        "請再忘記", "再移除一次", "forget the network again",
        "remove and re-add it again",
    ),
    "status_check": (
        "請再查狀態", "再檢查狀態頁", "check the status page again",
        "check status again",
    ),
    "reset_password": (
        "請重設密碼", "再重設一次", "reset the password again",
        "try another password reset",
    ),
    "server_check": (
        "再確認伺服器", "請重新確認伺服器", "check the server again",
        "verify the server again",
    ),
}
SCRIPTED_ACTIONS: dict[str, tuple[str, str]] = {
    "cross_test": (
        "請用同一台裝置測試另一個網路孔，並回報結果。",
        "Please test the same device on another network port and report the result.",
    ),
    "reconnect": (
        "請先中斷連線後重新連線，並告訴我結果。",
        "Please disconnect, reconnect, and tell me the result.",
    ),
    "reconfigure": ("請確認設定後重新連線。", "Please correct the settings and reconnect."),
    "peer_check": (
        "請問室友在相同環境下可以連線嗎？",
        "Can your roommate connect in the same environment?",
    ),
    "multiple_checks": (
        "請依序測試 A、B、C，並分別回報結果。",
        "Please test A, B, and C and report each result separately.",
    ),
    "forget_network": (
        "請先忘記已儲存的 Wi-Fi 網路，再重新加入。",
        "Please forget the saved Wi-Fi network and add it again.",
    ),
    "reinstall": ("請重新安裝 VPN 客戶端。", "Please reinstall the VPN client."),
    "application": (
        "請先完成申請，完成後告訴我。",
        "Please complete the application and tell me when it is done.",
    ),
    "credential_check": (
        "請確認同一組帳號是否能登入其他清大網路服務。",
        "Can the same account sign in to another NTHU network service?",
    ),
    "status_check": (
        "請先檢查服務狀態並回報結果。",
        "Please check the service status and report the result.",
    ),
    "reset_password": (
        "請先重設密碼，再測試登入。",
        "Please reset the password and test the login again.",
    ),
    "student_status_question": (
        "請問你是新生、在學生，還是教職員？",
        "Are you a new student, current student, or staff member?",
    ),
    "verify_activation": (
        "請先確認 VPN 功能是否已啟用。",
        "Please verify that VPN access is enabled.",
    ),
    "error_question": ("請提供錯誤畫面或錯誤訊息。", "What error message is displayed?"),
    "server_check": ("請確認 VPN 的伺服器欄位。", "Please verify the VPN server field."),
    "retry_after_wait": (
        "請等待設定生效後再試一次。",
        "Please wait for activation and then retry.",
    ),
    "account_correction": (
        "請改用正確的帳號類型再登入。",
        "Please use the correct account type and try again.",
    ),
    "contact_support": (
        "請整理已完成的測試與結果後聯絡支援。",
        "Please collect completed tests and results before contacting support.",
    ),
}


def failure(category: str, reason: str, **evidence: Any) -> dict[str, Any]:
    return {"category": category, "reason": reason, "evidence": evidence}


def normalize(text: str) -> str:
    return " ".join(text.casefold().replace("’", "'").split())


def contains_any(text: str, markers: list[str] | tuple[str, ...]) -> bool:
    normalized = normalize(text)
    return any(normalize(marker) in normalized for marker in markers)


def scripted_assistant(next_turn: dict[str, Any] | None, language: str) -> str:
    if not next_turn:
        return "請提供目前結果。" if language == "zh-Hant" else "Please provide the current result."
    action = next_turn["expected"].get("action")
    zh, en = SCRIPTED_ACTIONS.get(
        action,
        (
            "請提供目前結果，我會根據結果繼續下一步。",
            "Please provide the current result so I can continue.",
        ),
    )
    return zh if language == "zh-Hant" else en


def state_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "topic": state.get("current_topic"),
        "intent": state.get("current_intent"),
        "relation": state.get("relation"),
        "followup_type": state.get("followup_type"),
        "reference_status": state.get("reference_status"),
        "referenced_turn_ids": state.get("referenced_turn_ids", []),
        "relevant_turn_ids": state.get("relevant_turn_ids", []),
        "selected_history": [
            {
                "role": item.get("role"),
                "turn_id": item.get("turn_id"),
                "content": str(item.get("content", ""))[:240],
            }
            for item in state.get("relevant_history", [])
        ],
        "previous_recommendations": state.get("previous_recommendations", []),
        "pending_question": state.get("pending_question"),
        "current_action_results": state.get("current_action_results", []),
        "troubleshooting_progress": state.get("troubleshooting_progress", []),
        "resolution_status": state.get("resolution_status"),
        "standalone_query": state.get("standalone_query"),
        "semantic_slots": state.get("semantic_slots", {}),
    }


def find_action_result(state: dict[str, Any], action: str | None) -> dict[str, Any] | None:
    results = state.get("current_action_results", [])
    if not action:
        return results[0] if results else None
    return next(
        (
            item for item in results
            if item.get("action") in {action, "previous_recommendation", "multiple_checks"}
        ),
        None,
    )


def evaluate_state(expected: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    followup_type = expected["followup_type"]
    if followup_type == "new_question":
        return failures
    if (
        state.get("current_topic") != expected["topic"]
        or state.get("current_intent") != expected["intent"]
        or state.get("relation") not in {"follow_up", "intent_switch"}
        or state.get("followup_type") != followup_type
    ):
        failures.append(failure(
            "FOLLOWUP_RESOLUTION_ERROR",
            "follow-up type, topic, intent, or relation mismatch",
            expected={
                "topic": expected["topic"], "intent": expected["intent"],
                "relation": "follow_up|intent_switch", "followup_type": followup_type,
            },
            actual={
                "topic": state.get("current_topic"), "intent": state.get("current_intent"),
                "relation": state.get("relation"), "followup_type": state.get("followup_type"),
            },
        ))
    if expected.get("requires_previous_assistant") and not any(
        item.get("role") == "assistant"
        for item in state.get("relevant_history", [])
    ):
        failures.append(failure(
            "PREVIOUS_RECOMMENDATION_IGNORED",
            "selected history omitted the previous assistant answer",
            selected_history=state_snapshot(state)["selected_history"],
        ))

    action = expected.get("action")
    outcome = expected.get("action_outcome")
    result = find_action_result(state, action)
    if followup_type == "recommendation_question":
        if action and action not in state.get("previous_recommendations", []):
            failures.append(failure(
                "PREVIOUS_RECOMMENDATION_IGNORED",
                "question about a recommendation was not linked to that recommendation",
                expected_action=action,
                actual=state.get("previous_recommendations", []),
            ))
    elif followup_type == "diagnostic_answer":
        if result is None or result.get("outcome") != outcome:
            failures.append(failure(
                "DIAGNOSTIC_ANSWER_ERROR",
                "diagnostic answer was not represented as a structured result",
                expected_action=action, expected_outcome=outcome,
                actual=state.get("current_action_results", []),
            ))
    elif (
        followup_type in {
            "action_result", "recommendation_rejected", "correction",
        }
        or outcome in {"completed", "disabled", "still_fails"}
    ):
        if result is None or (outcome and result.get("outcome") != outcome):
            failures.append(failure(
                "ACTION_RESULT_ERROR",
                "action/result was not represented correctly",
                expected_action=action, expected_outcome=outcome,
                actual=state.get("current_action_results", []),
            ))

    expected_resolution = expected.get("resolution_status")
    if expected_resolution and state.get("resolution_status") != expected_resolution:
        failures.append(failure(
            "TROUBLESHOOTING_STAGE_ERROR",
            "resolution status mismatch",
            expected=expected_resolution,
            actual=state.get("resolution_status"),
        ))
    return failures


def evaluate_answer(expected: dict[str, Any], answer: str) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if expected["followup_type"] == "new_question":
        return failures
    if expected.get("must_not_refuse") and is_refusal(answer):
        failures.append(failure("INCORRECT_REFUSAL", "valid in-scope follow-up was refused", answer=answer))
    required = expected.get("answer_contains_any", [])
    if required and not contains_any(answer, required):
        failures.append(failure(
            "ANSWER_CONTENT_ERROR", "answer lacks progression-specific evidence",
            expected_any=required, answer=answer,
        ))
    action = expected.get("must_not_repeat_action")
    patterns = REPEATED_ACTION_PATTERNS.get(action or "", ())
    if patterns and contains_any(answer, patterns):
        failures.append(failure(
            "REPEATED_STEP_ERROR",
            "answer repeated a completed or failed step as the next action",
            action=action,
            matched=[marker for marker in patterns if normalize(marker) in normalize(answer)],
            answer=answer,
        ))
    escalation = expected.get("escalation", "optional")
    has_escalation = contains_any(answer, ESCALATION_MARKERS)
    if escalation == "required" and not has_escalation:
        failures.append(failure("MISSING_ESCALATION", "answer should escalate", answer=answer))
    if escalation == "forbidden" and has_escalation:
        failures.append(failure("PREMATURE_ESCALATION", "answer escalated too early", answer=answer))
    return failures


def primary_failure(failures: list[dict[str, Any]]) -> str | None:
    categories = {item["category"] for item in failures}
    return next((category for category in FAILURE_ORDER if category in categories), None)


def rate(values: list[bool]) -> dict[str, Any]:
    passed = sum(values)
    total = len(values)
    return {"passed": passed, "total": total, "rate": round(passed / total, 4) if total else None}


def summarize(results: list[dict[str, Any]], composition: dict[str, Any]) -> dict[str, Any]:
    turns = [turn for case in results for turn in case["turns"]]
    followups = [turn for turn in turns if turn["expected"]["followup_type"] != "new_question"]
    action_results = [turn for turn in followups if turn["expected"]["followup_type"] == "action_result"]
    diagnostics = [turn for turn in followups if turn["expected"]["followup_type"] == "diagnostic_answer"]
    repeat_eligible = [turn for turn in followups if turn["expected"].get("must_not_repeat_action")]
    escalation_eligible = [
        turn for turn in followups
        if turn["expected"].get("escalation") in {"required", "forbidden"}
    ]
    progression = [turn for turn in followups if turn["expected"]["intent"] == "troubleshooting"]

    def without(turn: dict[str, Any], categories: set[str]) -> bool:
        return not any(item["category"] in categories for item in turn["failures"])

    return {
        "composition": composition,
        "conversation_pass_rate": rate([case["passed"] for case in results]),
        "turn_pass_rate": rate([turn["passed"] for turn in turns]),
        "metrics": {
            "followup_resolution_pass_rate": rate([
                without(turn, {"FOLLOWUP_RESOLUTION_ERROR"}) for turn in followups
            ]),
            "action_result_understanding_pass_rate": rate([
                without(turn, {"ACTION_RESULT_ERROR"}) for turn in action_results
            ]),
            "troubleshooting_progression_pass_rate": rate([
                without(turn, {
                    "FOLLOWUP_RESOLUTION_ERROR", "ACTION_RESULT_ERROR",
                    "TROUBLESHOOTING_STAGE_ERROR", "REPEATED_STEP_ERROR",
                    "PREMATURE_ESCALATION", "MISSING_ESCALATION", "INCORRECT_REFUSAL",
                })
                for turn in progression
            ]),
            "previous_recommendation_awareness_pass_rate": rate([
                without(turn, {"PREVIOUS_RECOMMENDATION_IGNORED"}) for turn in followups
            ]),
            "diagnostic_answer_handling_pass_rate": rate([
                without(turn, {"DIAGNOSTIC_ANSWER_ERROR"}) for turn in diagnostics
            ]),
            "repeated_step_error_rate": rate([
                any(item["category"] == "REPEATED_STEP_ERROR" for item in turn["failures"])
                for turn in repeat_eligible
            ]),
            "incorrect_refusal_rate": rate([
                any(item["category"] == "INCORRECT_REFUSAL" for item in turn["failures"])
                for turn in followups
            ]),
            "escalation_accuracy": rate([
                without(turn, {"PREMATURE_ESCALATION", "MISSING_ESCALATION"})
                for turn in escalation_eligible
            ]),
        },
        "failure_distribution": dict(Counter(
            item["category"] for turn in turns for item in turn["failures"]
        )),
        "primary_failure_distribution": dict(Counter(
            turn["primary_failure"] for turn in turns if turn["primary_failure"]
        )),
        "routes": dict(Counter(turn["actual"].get("api_path", "state_only") for turn in turns)),
    }


def execute(
    dataset: dict[str, Any],
    *,
    label: str,
    state_only: bool,
    limit: int | None,
) -> list[dict[str, Any]]:
    settings = AgentSettings(
        adapter="inprocess", base_url="http://127.0.0.1:8000",
        timeout_seconds=120, language="zh-Hant",
        clear_cache_between_conversations=False,
    )
    adapter = None if state_only else InProcessAgentAdapter(settings)
    cases = dataset["cases"][:limit] if limit else dataset["cases"]
    results: list[dict[str, Any]] = []
    for case_index, case in enumerate(cases, start=1):
        session_id = f"followup-{label}-{case['test_id']}"
        language = case["language"]
        history: list[dict[str, str]] = []
        turns: list[dict[str, Any]] = []
        if adapter:
            adapter.start_session(session_id)
        try:
            definitions = case["conversation"]
            for index, definition in enumerate(definitions):
                user = definition["user"]
                expected = definition["expected"]
                quiet = io.StringIO()
                logging.disable(logging.CRITICAL)
                try:
                    with redirect_stdout(quiet), redirect_stderr(quiet):
                        state = prepare_agent_context(user, history, language=language)
                        if adapter:
                            trace = adapter.run_turn(
                                session_id=session_id, message=user,
                                history=history, language=language,
                            )
                            actual = trace.model_dump(mode="json")
                        else:
                            actual = {
                                "api_path": "state_only", "final_answer": "",
                                "sources": [], "error": None,
                            }
                finally:
                    logging.disable(logging.NOTSET)
                failures = evaluate_state(expected, state)
                if not state_only:
                    failures.extend(evaluate_answer(expected, str(actual.get("final_answer", ""))))
                turns.append({
                    "turn_id": index + 1, "user": user, "expected": expected,
                    "state": state_snapshot(state), "actual": actual,
                    "failures": failures, "primary_failure": primary_failure(failures),
                    "passed": not failures,
                })
                assistant = (
                    str(actual.get("final_answer", ""))
                    if adapter
                    else scripted_assistant(
                        definitions[index + 1] if index + 1 < len(definitions) else None,
                        language,
                    )
                )
                history.extend([
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": assistant},
                ])
        finally:
            if adapter:
                adapter.end_session(session_id)
        results.append({
            "test_id": case["test_id"], "language": language,
            "category": case["category"], "service": case["service"],
            "long_chain": case["long_chain"], "turns": turns,
            "passed": all(turn["passed"] for turn in turns),
            "primary_failure": next(
                (
                    category for category in FAILURE_ORDER
                    if any(turn["primary_failure"] == category for turn in turns)
                ),
                None,
            ),
        })
        if case_index % 10 == 0 or case_index == len(cases):
            print(
                f"[{label}] {case_index}/{len(cases)} conversations; "
                f"passed={sum(item['passed'] for item in results)}"
            )
    return results


def render_report(label: str, summary: dict[str, Any]) -> str:
    lines = [
        f"# Follow-up Reasoning Evaluation — {label}", "",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}", "",
        "## Outcome", "",
        f"- Conversations: {summary['composition']['conversations']}",
        f"- User turns: {summary['composition']['user_turns']}",
        f"- Conversation pass rate: {summary['conversation_pass_rate']['rate']}",
        f"- Turn pass rate: {summary['turn_pass_rate']['rate']}", "",
        "## Follow-up metrics", "",
        "| Metric | Passed / Errors | Total | Rate |",
        "|---|---:|---:|---:|",
    ]
    for name, metric in summary["metrics"].items():
        lines.append(f"| {name} | {metric['passed']} | {metric['total']} | {metric['rate']} |")
    lines.extend(["", "## Failure distribution", "", "| Failure | Count |", "|---|---:|"])
    for name, count in summary["failure_distribution"].items():
        lines.append(f"| {name} | {count} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--state-only", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    results = execute(
        dataset, label=args.label, state_only=args.state_only, limit=args.limit,
    )
    composition = dict(dataset["composition"])
    if args.limit:
        selected = dataset["cases"][:args.limit]
        composition.update({
            "conversations": len(selected),
            "user_turns": sum(len(case["conversation"]) for case in selected),
            "zh_conversations": sum(case["language"] == "zh-Hant" for case in selected),
            "en_conversations": sum(case["language"] == "en" for case in selected),
            "long_chains": sum(case["long_chain"] for case in selected),
        })
    summary = summarize(results, composition)
    payload = {
        "label": args.label,
        "evaluated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "state_only": args.state_only, "summary": summary, "results": results,
    }
    result_path = HERE / f"{args.label}_results.json"
    report_path = HERE / f"{args.label}_report.md"
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    report_path.write_text(render_report(args.label, summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(result_path)
    print(report_path)


if __name__ == "__main__":
    main()
