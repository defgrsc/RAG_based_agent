from __future__ import annotations

import re
import unicodedata
from typing import Any


FOLLOWUP_TYPES = {
    "new_question",
    "action_result",
    "diagnostic_answer",
    "recommendation_question",
    "recommendation_rejected",
    "correction",
    "continuation",
}

ACTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "multiple_checks",
        (
            r"\ba\b.{0,80}\bb\b.{0,80}\bc\b",
            r"\btest(?:ed|ing)?s+a\b.{0,80}\bb\b.{0,80}\bc\b",
        ),
    ),
    (
        "account_correction",
        (
            r"(?:正確|改用).{0,16}(?:gapp|帳號)",
            r"(?:correct|right).{0,16}(?:gapp|account)",
        ),
    ),
    (
        "retry_after_wait",
        (
            r"(?:等|等待).{0,12}(?:分鐘|生效).{0,20}(?:再連|好了|可以)",
            r"(?:waited|wait).{0,20}(?:minutes?|activation).{0,20}(?:works?|retry)",
        ),
    ),
    (
        "forget_network",
        (
            r"(?:忘記|移除|刪除).{0,12}(?:wi-?fi|無線|網路|設定)",
            r"(?:forget|forgot|remove|removed|delete|deleted).{0,16}(?:wi-?fi|wireless|network)",
            r"forget.{0,80}(?:profile|setting)",
            r"(?:removed|forgot).{0,16}(?:re-added|added it again)",
            r"(?:忘記|移除)(?:後|之後).{0,12}(?:重加|重新加入)",
        ),
    ),
    (
        "server_check",
        (
            r"(?:伺服器|server).{0,16}(?:欄位|設定|確認|正確|改)",
            r"(?:check|verify|change|correct).{0,16}(?:server|server field)",
            r"(?:server|server field).{0,16}(?:correct|right|change|set|use)",
            r"(?:伺服器|server).{0,12}(?:填入|填|設為)",
        ),
    ),
    (
        "cross_test",
        (
            r"交叉測試",
            r"(?:測過|測試過).{0,12}(?:別的|另一個|其他).{0,8}(?:孔|網路孔)",
            r"(?:同一台|我的|自己).{0,24}(?:室友|另一個|其他).{0,16}(?:孔|網路孔|裝置)",
            r"(?:室友|另一個|其他).{0,16}(?:孔|網路孔).{0,20}(?:可以|正常|測)",
            r"(?:roommate|another|other|second).{0,20}(?:network |wall |ethernet )?port",
            r"(?:same|my|second|another).{0,20}(?:computer|device).{0,32}(?:port|slow|works?)",
            r"(?:另一台|第二台).{0,12}(?:裝置|電腦)",
            r"(?:裝置|電腦).{0,24}(?:現場|當地|位置).{0,12}(?:網路|wi-?fi)",
            r"(?:移動|換到).{0,24}(?:位置|走廊|公共區).{0,20}(?:測試|再測)",
            r"(?:device|computer).{0,32}(?:local|on-site|location).{0,16}(?:network|wi-?fi)",
            r"move to.{0,100}test again",
            r"cross[- ]?test",
        ),
    ),
    (
        "peer_check",
        (
            r"(?:室友|同學|別人).{0,16}(?:可以|正常|能上網|能連)",
            r"(?:roommate|classmate|others?).{0,16}(?:can connect|works?|get online)",
        ),
    ),
    (
        "status_check",
        (
            r"(?:狀態頁|狀態).{0,16}(?:查|顯示|正常|停用|看)",
            r"(?:查|看).{0,12}(?:狀態頁|服務狀態)",
            r"(?:status page|service status).{0,20}(?:check|checked|normal|disabled|looks?)",
        ),
    ),
    (
        "reset_password",
        (
            r"(?:重設|更改|改).{0,8}密碼",
            r"密碼.{0,8}(?:重設|更改|改)",
            r"(?:reset|change|changed).{0,12}password",
        ),
    ),
    (
        "student_status_question",
        (
            r"(?:今年|剛入學|我是).{0,10}新生",
            r"\b(?:i am|i'm).{0,12}(?:a )?new student\b",
        ),
    ),
    (
        "credential_check",
        (
            r"(?:同一|這組|帳號).{0,24}(?:無線|其他).{0,16}(?:可以|能).{0,8}登入",
            r"(?:same account|account).{0,24}(?:works?|signs? in).{0,20}(?:wireless|other)",
        ),
    ),
    (
        "verify_activation",
        (
            r"(?:確認|檢查).{0,12}vpn.{0,8}(?:啟用|開通)",
            r"(?:verify|check).{0,12}vpn.{0,12}(?:enabled|activated|access)",
            r"vpn.{0,16}(?:enabled|activated|啟用|開通)",
        ),
    ),
    (
        "error_question",
        (
            r"(?:錯誤|畫面|訊息).{0,16}(?:顯示|寫|說)",
            r"(?:error|message|screen).{0,16}(?:says?|shows?|display)",
        ),
    ),
    (
        "reinstall",
        (
            r"(?:重新安裝|重裝|移除後重裝)",
            r"(?:reinstall|install again)",
        ),
    ),
    (
        "reconfigure",
        (
            r"(?:重新設定|改好設定|修正設定|照你說的.*設定)",
            r"(?:corrected|fixed|changed|redid).{0,12}(?:the )?settings",
            r"(?:reconfigure|configured again)",
        ),
    ),
    (
        "reconnect",
        (
            r"(?:重新連線|重連|斷線後重連|重新連過)",
            r"(?:reconnect|reconnected|disconnected and reconnected)",
        ),
    ),
    (
        "application",
        (
            r"(?:申請|註冊).{0,12}(?:完成|好了|辦完)",
            r"(?:application|registration).{0,12}(?:complete|completed|done)",
        ),
    ),
    (
        "contact_support",
        (
            r"(?:聯絡|報修|寄信|找誰|提供哪些資料|提供什麼資訊)",
            r"(?:contact|support|repair report|what information|what details)",
            r"(?:where|who).{0,16}(?:report|contact)",
        ),
    ),
)

CORRECTION_PATTERNS = (
    r"(?:不是|不對).{0,40}(?:是|我說|我指)",
    r"(?:更正|修正一下|我指的是)",
    r"\b(?:i mean|i meant|correction|not .{0,32},? (?:i mean|it is|it's))\b",
)
REJECTION_PATTERNS = (
    r"(?:現在|目前)?.{0,8}(?:沒辦法|無法|不能).{0,24}(?:測|重裝|安裝|做|試)",
    r"\b(?:cannot|can't|unable to).{0,24}(?:test|try|reinstall|install|do that).{0,24}(?:right now|now)?\b",
)
RECOMMENDATION_QUESTION_PATTERNS = (
    r"(?:為什麼|為何).{0,32}(?:要|需|測|做|忘記|確認)",
    r"(?:你說|剛才|上述|那個|這個).{0,24}(?:怎麼|如何|為什麼)",
    r"(?:怎麼|如何).{0,24}(?:交叉測試|忘記網路|確認|改|測)",
    r"\bwhy (?:should|do|would|is)\b",
    r"\bhow (?:do|should|can) i (?:do that|perform|forget|verify|change)\b",
    r"\bhow can i tell\b",
)
CONTINUATION_PATTERNS = (
    r"(?:接下來|下一步|然後呢|現在呢|該怎麼辦|要去哪|聯絡誰|找誰)",
    r"(?:有的話|如果有|申請完成).{0,24}(?:怎麼|如何|接下來|登入|連)",
    r"(?:報修|回報).{0,24}(?:要|應該|哪些|什麼|寫)",
    r"\b(?:what|where|who).{0,24}(?:next|report|contact|include|information|details)\b",
    r"\b(?:what should i do next|where should i report|who should i contact)\b",
    r"\bif (?:it is|so).{0,24}how do i connect\b",
    r"\b(?:application is complete|finished those steps).{0,24}(?:how|what|who)\b",
    r"\bshould i include.{0,32}(?:report|result)\b",
)
DIAGNOSTIC_PATTERNS = (
    r"(?:室友|同學|別人).{0,20}(?:可以|正常|能連|能上網).{0,20}(?:只有我|我不行)?",
    r"(?:我是|今年).{0,12}新生",
    r"(?:錯誤|畫面|訊息).{0,16}(?:顯示|寫|說)",
    r"(?:帳號|同一組).{0,24}(?:可以|能).{0,12}(?:登入|使用).{0,24}(?:只有|vpn)",
    r"\b(?:my roommate|roommate).{0,20}(?:can connect|works?|get online)\b",
    r"\b(?:i am|i'm).{0,12}(?:a )?new student\b",
    r"\b(?:the )?(?:error|message|screen).{0,16}(?:says?|shows?|display)\b",
    r"\b(?:same account|account).{0,24}(?:works?|signs? in).{0,24}(?:only|vpn|wireless)\b",
)
ACTION_RESULT_PATTERNS = (
    r"(?:試過|測過|測完|做完|做了|查過|看過|已經|完成|改成|改用|重設過|換了)",
    r"(?:好了|可以用了|可以登入|正常上網|沒問題|仍然|還是|一樣|沒有改善|沒改善|不行|失敗|還沒試|顯示正常|看起來正常)",
    r"\b(?:tried|tested|checked|already|completed|finished|corrected|changed|reset|waited)\b",
    r"\b(?:still|did not help|does not work|doesn't work|works? now|works? normally|fixed it|fixed the|that fixed|have not tried|haven't tried|looks? normal|says? disabled|slow there too)\b",
)
PARTIAL_PATTERNS = (
    r"(?:a|Ａ).{0,24}(?:b|Ｂ).{0,24}(?:c|Ｃ).{0,24}(?:還沒|未試)",
    r"\ba\b.{0,80}\bb\b.{0,80}(?:(?:not tried|have not tried|haven't tried).{0,16}\bc\b|\bc\b.{0,24}(?:not tried|have not tried|haven't tried))",
)
UNAVAILABLE_PATTERNS = (
    r"(?:沒辦法|無法|不能).{0,24}(?:測|試|重裝|安裝|做)",
    r"\b(?:cannot|can't|unable to).{0,24}(?:test|try|reinstall|install|do)\b",
)
STILL_FAILS_PATTERNS = (
    r"(?:還是|仍然|依然|一樣).{0,12}(?:不行|失敗|不能|無法|連不上|上不了網|不能上網|沒網路|慢)",
    r"(?:沒有|沒).{0,8}(?:改善|用|成功)",
    r"\b(?:still|continues? to).{0,16}(?:fail|failed|fails|failing|not work|doesn't work|cannot|can't|slow)\b",
    r"\b(?:did not|didn't).{0,12}(?:help|work|fix)\b",
    r"\bslow (?:there )?too\b",
)
WORKS_PATTERNS = (
    r"(?:好了|修好了|可以用了|可以登入|正常上網|沒問題|恢復正常)",
    r"(?:接|連).{0,20}(?:室友|另一個|其他).{0,12}(?:孔|網路孔).{0,12}(?:可以|正常)",
    r"\b(?:it works|now it works|that fixed it|fixed the|works normally|can get online|can log in|works? (?:normally )?on .{0,24}port)\b",
)


def normalize_followup_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return " ".join(normalized.split())


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def detect_actions(text: str) -> list[str]:
    normalized = normalize_followup_text(text)
    actions: list[str] = []
    for action, patterns in ACTION_PATTERNS:
        if _matches(normalized, patterns):
            actions.append(action)
    return actions


def extract_recommendations(assistant_text: str) -> list[str]:
    return detect_actions(assistant_text)


def extract_pending_question(assistant_text: str) -> str | None:
    text = " ".join(assistant_text.split())
    if not text:
        return None
    question_cues = (
        "？", "?", "請問", "請提供", "請告訴", "can your", "could you",
        "what error", "are you", "please provide", "please tell",
    )
    if any(cue in text.casefold() for cue in question_cues):
        return text[-500:]
    return None


def classify_followup_type(
    message: str,
    *,
    has_history: bool,
) -> str:
    if not has_history:
        return "new_question"
    normalized = normalize_followup_text(message)
    if _matches(normalized, CORRECTION_PATTERNS):
        return "correction"
    if _matches(normalized, REJECTION_PATTERNS) and (
        "其他" in normalized
        or "替代" in normalized
        or "another" in normalized
        or "alternative" in normalized
        or "instead" in normalized
    ):
        return "recommendation_rejected"
    if _matches(normalized, RECOMMENDATION_QUESTION_PATTERNS):
        return "recommendation_question"
    if _matches(normalized, CONTINUATION_PATTERNS):
        return "continuation"
    actions = detect_actions(message)
    diagnostic = _matches(normalized, DIAGNOSTIC_PATTERNS)
    if diagnostic and "cross_test" not in actions:
        return "diagnostic_answer"
    if _matches(normalized, ACTION_RESULT_PATTERNS) or (
        actions
        and (
            _matches(normalized, WORKS_PATTERNS)
            or _matches(normalized, STILL_FAILS_PATTERNS)
        )
    ):
        return "action_result"
    return "new_question"


def _outcome_for(
    message: str,
    followup_type: str,
    actions: list[str],
) -> str | None:
    normalized = normalize_followup_text(message)
    if _matches(normalized, PARTIAL_PATTERNS):
        return "partial"
    if _matches(normalized, UNAVAILABLE_PATTERNS):
        return "unavailable"
    if re.search(r"(?:顯示|狀態).{0,8}停用|\b(?:says?|status).{0,8}disabled\b", normalized):
        return "disabled"
    if "student_status_question" in actions:
        return "new_student"
    if "credential_check" in actions:
        return "credentials_work"
    if followup_type == "diagnostic_answer" and "peer_check" in actions:
        return "peer_works"
    if _matches(normalized, STILL_FAILS_PATTERNS):
        return "still_fails"
    if _matches(normalized, WORKS_PATTERNS):
        return "works"
    if "peer_check" in actions:
        return "peer_works"
    if "application" in actions:
        return "completed"
    if followup_type == "recommendation_rejected":
        return "unavailable"
    if followup_type == "recommendation_question":
        return "question"
    if followup_type in {"diagnostic_answer", "correction"}:
        return "provided"
    if "status_check" in actions and re.search(r"(?:正常|normal|looks? normal)", normalized):
        return "completed"
    if (
        followup_type == "continuation"
        and "cross_test" in actions
        and "contact_support" in actions
    ):
        return "still_fails"
    if followup_type == "continuation" and "contact_support" in actions:
        return "question"
    return None


def _resolution_status(
    message: str,
    *,
    outcome: str | None,
    actions: list[str],
) -> str:
    if outcome == "unavailable":
        return "blocked"
    normalized = normalize_followup_text(message)
    resolved_cues = (
        r"(?:好了|修好了|恢復正常|現在可以用了|可以登入了)",
        r"\b(?:that fixed it|now it works|fixed the (?:login|connection)|works now|resolved)\b",
    )
    target_only = (
        "cross_test" in actions
        and re.search(r"(?:室友|另一個|其他|roommate|another|other).{0,24}(?:孔|port)", normalized)
    )
    if outcome == "works" and _matches(normalized, resolved_cues) and not target_only:
        return "resolved"
    return "in_progress"


def _partial_results(message: str) -> list[dict[str, str]]:
    normalized = normalize_followup_text(message)
    if not _matches(normalized, PARTIAL_PATTERNS):
        return []
    return [
        {"action": "check_a", "outcome": "works", "detail": message},
        {"action": "check_b", "outcome": "still_fails", "detail": message},
        {"action": "check_c", "outcome": "pending", "detail": message},
    ]


def analyze_followup(
    message: str,
    *,
    previous_assistant: str = "",
    has_history: bool,
) -> dict[str, Any]:
    followup_type = classify_followup_type(message, has_history=has_history)
    actions = detect_actions(message)
    previous_recommendations = extract_recommendations(previous_assistant)
    if followup_type in {
        "action_result", "recommendation_question", "recommendation_rejected",
    } and not actions and previous_recommendations:
        actions = [previous_recommendations[-1]]
    outcome = _outcome_for(message, followup_type, actions)
    action_results = _partial_results(message)
    if outcome and followup_type not in {"recommendation_question"}:
        action_results.insert(0, {
            "action": actions[0] if actions else "previous_recommendation",
            "outcome": outcome,
            "detail": message,
        })
    return {
        "followup_type": followup_type,
        "previous_recommendations": previous_recommendations,
        "pending_question": extract_pending_question(previous_assistant),
        "current_action_results": action_results,
        "resolution_status": _resolution_status(
            message,
            outcome=outcome,
            actions=actions,
        ),
    }


def derive_troubleshooting_progress(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    progress: list[dict[str, Any]] = []
    previous_assistant = ""
    seen_user = False
    turn_id = 0
    for item in history:
        role = "assistant" if item.get("role") == "assistant" else "user"
        content = str(item.get("content", ""))
        if role == "assistant":
            previous_assistant = content
            continue
        turn_id += 1
        analysis = analyze_followup(
            content,
            previous_assistant=previous_assistant,
            has_history=seen_user,
        )
        for result in analysis["current_action_results"]:
            progress.append({**result, "turn_id": turn_id})
        seen_user = True
    return progress


def build_progression_query(message: str, state: dict[str, Any]) -> str | None:
    if (
        state.get("followup_type", "new_question") == "new_question"
        or state.get("current_intent") != "troubleshooting"
    ):
        return None
    topic = state.get("current_topic", "unknown")
    labels = {
        "dorm_network": ("宿網", "DormNet"),
        "campus_wifi": ("校園 Wi-Fi", "NTHU campus Wi-Fi"),
        "vpn": ("清大 VPN", "NTHU VPN"),
        "email": ("清大信箱", "NTHU email"),
    }
    relevant = state.get("relevant_history", [])
    original_problem = next(
        (
            str(item.get("content", ""))
            for item in relevant
            if item.get("role") == "user"
        ),
        "",
    )
    is_english = state.get("language") == "en"
    label = labels.get(topic, ("清大網路", "NTHU network"))[1 if is_english else 0]
    if is_english:
        return (
            f"{label} follow-up. Original problem: {original_problem or label}. "
            f"Latest user update: {message}. Continue from the reported result "
            "without repeating completed steps."
        )
    return (
        f"{label}追問。原始問題：{original_problem or label}。"
        f"使用者最新回報：{message}。請根據已回報結果繼續下一步，"
        "不要重複已完成的步驟。"
    )


def format_progression_context(state: dict[str, Any]) -> str:
    followup_type = state.get("followup_type", "new_question")
    if followup_type == "new_question":
        return ""
    lines = [f"Follow-up type: {followup_type}"]
    recommendations = state.get("previous_recommendations", [])
    if recommendations:
        lines.append(f"Previous recommendations: {', '.join(recommendations)}")
    pending = state.get("pending_question")
    if pending:
        lines.append(f"Previous assistant question: {pending}")
    progress = state.get("troubleshooting_progress", [])
    if progress:
        rendered = "; ".join(
            f"turn {item.get('turn_id')}: {item.get('action')}={item.get('outcome')}"
            for item in progress
        )
        lines.append(f"Reported progress: {rendered}")
    lines.append(f"Resolution status: {state.get('resolution_status', 'in_progress')}")
    return "\n".join(lines)
