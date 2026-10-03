from __future__ import annotations

from typing import Any


def turn(
    user: str,
    *,
    topic: str,
    intent: str,
    followup_type: str = "new_question",
    action: str | None = None,
    action_outcome: str | None = None,
    resolution_status: str = "in_progress",
    answer_contains_any: tuple[str, ...] = (),
    must_not_repeat_action: str | None = None,
    escalation: str = "optional",
) -> dict[str, Any]:
    if escalation == "optional" and (
        resolution_status == "resolved"
        or followup_type == "recommendation_question"
        or action_outcome in {"partial", "unavailable"}
    ):
        escalation = "forbidden"
    expected: dict[str, Any] = {
        "topic": topic,
        "intent": intent,
        "followup_type": followup_type,
        "resolution_status": resolution_status,
        "answer_contains_any": list(answer_contains_any),
        "must_not_refuse": topic != "unknown",
        "requires_previous_assistant": followup_type != "new_question",
        "escalation": escalation,
    }
    if action:
        expected["action"] = action
    if action_outcome:
        expected["action_outcome"] = action_outcome
    if must_not_repeat_action:
        expected["must_not_repeat_action"] = must_not_repeat_action
    return {"user": user, "expected": expected}


def conversation(
    test_id: str,
    language: str,
    category: str,
    service: str,
    turns: list[dict[str, Any]],
    *,
    long_chain: bool = False,
) -> dict[str, Any]:
    return {
        "test_id": test_id,
        "language": language,
        "category": category,
        "service": service,
        "long_chain": long_chain,
        "conversation": turns,
    }


def short_cases() -> list[dict[str, Any]]:
    zh = [
        conversation("followup_zh_001", "zh-Hant", "action_result", "dorm_network", [
            turn("宿網連不到網路怎麼辦？", topic="dorm_network", intent="troubleshooting"),
            turn(
                "我做交叉測試後，連室友的網路孔沒問題。",
                topic="dorm_network", intent="troubleshooting",
                followup_type="action_result", action="cross_test",
                action_outcome="works", answer_contains_any=("報修", "網路孔", "dorms@"),
                must_not_repeat_action="cross_test", escalation="required",
            ),
        ]),
        conversation("followup_zh_002", "zh-Hant", "failed_recommendation", "campus_wifi", [
            turn("校園 Wi-Fi 連不上。", topic="campus_wifi", intent="troubleshooting"),
            turn(
                "重新連過了，還是不行。",
                topic="campus_wifi", intent="troubleshooting",
                followup_type="action_result", action="reconnect",
                action_outcome="still_fails", answer_contains_any=("下一步", "忘記", "SSID", "設定"),
                must_not_repeat_action="reconnect",
            ),
        ]),
        conversation("followup_zh_003", "zh-Hant", "successful_recommendation", "vpn", [
            turn("VPN 一直連線失敗。", topic="vpn", intent="troubleshooting"),
            turn(
                "照你說的重新設定後好了，現在可以用了。",
                topic="vpn", intent="troubleshooting",
                followup_type="action_result", action="reconfigure",
                action_outcome="works", resolution_status="resolved",
                answer_contains_any=("恢復", "可以使用", "已解決", "正常"),
            ),
        ]),
        conversation("followup_zh_004", "zh-Hant", "diagnostic_answer", "dorm_network", [
            turn("宿舍網路不能用。", topic="dorm_network", intent="troubleshooting"),
            turn(
                "室友可以，只有我不行。",
                topic="dorm_network", intent="troubleshooting",
                followup_type="diagnostic_answer", action="peer_check",
                action_outcome="peer_works", answer_contains_any=("裝置", "網路孔", "交叉", "設定"),
            ),
        ]),
        conversation("followup_zh_005", "zh-Hant", "partial_result", "campus_wifi", [
            turn("Wi-Fi 認證失敗怎麼排查？", topic="campus_wifi", intent="troubleshooting"),
            turn(
                "A 重新連線可以做到，B 用 nthupeap 還是不行，C 重開機還沒試。",
                topic="campus_wifi", intent="troubleshooting",
                followup_type="action_result", action="multiple_checks",
                action_outcome="partial", answer_contains_any=("還沒", "重開機", "B", "nthupeap"),
            ),
        ]),
        conversation("followup_zh_006", "zh-Hant", "recommendation_why", "dorm_network", [
            turn("宿網突然不能用了。", topic="dorm_network", intent="troubleshooting"),
            turn(
                "為什麼要做交叉測試？",
                topic="dorm_network", intent="troubleshooting",
                followup_type="recommendation_question", action="cross_test",
                action_outcome="question", answer_contains_any=("確認", "區分", "判斷", "問題"),
            ),
        ]),
        conversation("followup_zh_007", "zh-Hant", "recommendation_how", "campus_wifi", [
            turn("校園無線一直認證失敗。", topic="campus_wifi", intent="troubleshooting"),
            turn(
                "你說忘記網路，要怎麼做？",
                topic="campus_wifi", intent="troubleshooting",
                followup_type="recommendation_question", action="forget_network",
                action_outcome="question", answer_contains_any=("Wi-Fi", "忘記", "移除", "設定"),
            ),
        ]),
        conversation("followup_zh_008", "zh-Hant", "recommendation_rejected", "vpn", [
            turn("VPN 客戶端開不起來。", topic="vpn", intent="troubleshooting"),
            turn(
                "我現在沒辦法重裝，有其他方法嗎？",
                topic="vpn", intent="troubleshooting",
                followup_type="recommendation_rejected", action="reinstall",
                action_outcome="unavailable", resolution_status="blocked",
                answer_contains_any=("可以先", "替代", "網頁", "檢查"),
            ),
        ]),
        conversation("followup_zh_009", "zh-Hant", "escalation", "dorm_network", [
            turn("宿網的網路孔疑似故障。", topic="dorm_network", intent="troubleshooting"),
            turn(
                "測過別的孔了，接下來要去哪裡報修？",
                topic="dorm_network", intent="troubleshooting",
                followup_type="continuation", action="cross_test",
                action_outcome="still_fails", answer_contains_any=("dorms@", "報修", "地點", "測試"),
                escalation="required",
            ),
        ]),
        conversation("followup_zh_010", "zh-Hant", "correction", "campus_wifi", [
            turn("圖書館的 Wi-Fi 很慢。", topic="campus_wifi", intent="troubleshooting"),
            turn(
                "不是圖書館，我說的是人社館。",
                topic="campus_wifi", intent="troubleshooting",
                followup_type="correction", action_outcome="provided",
                answer_contains_any=("人社", "Wi-Fi", "無線"),
            ),
        ]),
        conversation("followup_zh_011", "zh-Hant", "application_continuation", "email", [
            turn("學生信箱怎麼申請？", topic="email", intent="application"),
            turn(
                "申請完成了，接下來怎麼登入？",
                topic="email", intent="configuration",
                followup_type="continuation", action="application",
                action_outcome="completed", answer_contains_any=("登入", "信箱", "帳號"),
            ),
        ]),
        conversation("followup_zh_012", "zh-Hant", "diagnostic_answer", "vpn", [
            turn("VPN 驗證失敗。", topic="vpn", intent="troubleshooting"),
            turn(
                "帳號在無線網路可以登入，只有 VPN 不行。",
                topic="vpn", intent="troubleshooting",
                followup_type="diagnostic_answer", action="credential_check",
                action_outcome="credentials_work", answer_contains_any=("VPN", "設定", "伺服器", "啟用"),
            ),
        ]),
        conversation("followup_zh_013", "zh-Hant", "coverage_continuation", "campus_wifi", [
            turn("人社館有校園 Wi-Fi 嗎？", topic="campus_wifi", intent="lookup"),
            turn(
                "有的話那裡要怎麼連？",
                topic="campus_wifi", intent="configuration",
                followup_type="continuation", answer_contains_any=("nthu-cc", "nthupeap", "eduroam"),
            ),
        ]),
        conversation("followup_zh_014", "zh-Hant", "status_result", "dorm_network", [
            turn("宿網不能上網，先檢查什麼？", topic="dorm_network", intent="troubleshooting"),
            turn(
                "查過狀態頁了，顯示正常但我還是不能上網。",
                topic="dorm_network", intent="troubleshooting",
                followup_type="action_result", action="status_check",
                action_outcome="still_fails", answer_contains_any=("下一步", "交叉", "網路孔", "設定"),
                must_not_repeat_action="status_check",
            ),
        ]),
        conversation("followup_zh_015", "zh-Hant", "failed_recommendation", "email", [
            turn("學生信箱登入不了。", topic="email", intent="troubleshooting"),
            turn(
                "密碼重設過了還是登入失敗。",
                topic="email", intent="troubleshooting",
                followup_type="action_result", action="reset_password",
                action_outcome="still_fails", answer_contains_any=("帳號", "登入", "GApp", "信箱"),
                must_not_repeat_action="reset_password",
            ),
        ]),
        conversation("followup_zh_016", "zh-Hant", "diagnostic_answer", "email", [
            turn("我不知道該申請哪一種信箱。", topic="email", intent="application"),
            turn(
                "我是今年的新生。",
                topic="email", intent="application",
                followup_type="diagnostic_answer", action="student_status_question",
                action_outcome="new_student", answer_contains_any=("新生", "學生信箱", "申請"),
            ),
        ]),
        conversation("followup_zh_017", "zh-Hant", "recommendation_how", "vpn", [
            turn("VPN 連不上校內資源。", topic="vpn", intent="troubleshooting"),
            turn(
                "那要怎麼確認 VPN 功能有啟用？",
                topic="vpn", intent="troubleshooting",
                followup_type="recommendation_question", action="verify_activation",
                action_outcome="question", answer_contains_any=("校務資訊系統", "VPN", "啟用"),
            ),
        ]),
        conversation("followup_zh_018", "zh-Hant", "correction", "campus_wifi", [
            turn("水木有沒有網路？", topic="campus_wifi", intent="lookup"),
            turn(
                "我指的是水木生活中心，不是宿舍。",
                topic="campus_wifi", intent="lookup",
                followup_type="correction", action_outcome="provided",
                answer_contains_any=("水木生活中心", "無線", "Wi-Fi"),
            ),
        ]),
        conversation("followup_zh_019", "zh-Hant", "status_continuation", "dorm_network", [
            turn("宿網狀態要去哪裡查？", topic="dorm_network", intent="lookup"),
            turn(
                "我已經查到了，現在顯示被停用，下一步呢？",
                topic="dorm_network", intent="troubleshooting",
                followup_type="continuation", action="status_check",
                action_outcome="disabled", answer_contains_any=("停用", "原因", "聯絡", "dorms@"),
                escalation="required",
            ),
        ]),
        conversation("followup_zh_020", "zh-Hant", "action_result", "dorm_network", [
            turn("我的電腦在宿舍網路孔不能上網。", topic="dorm_network", intent="troubleshooting"),
            turn(
                "同一台電腦接室友的孔可以正常上網。",
                topic="dorm_network", intent="troubleshooting",
                followup_type="action_result", action="cross_test",
                action_outcome="works", answer_contains_any=("原本", "網路孔", "報修", "dorms@"),
                must_not_repeat_action="cross_test", escalation="required",
            ),
        ]),
    ]

    en = [
        conversation("followup_en_001", "en", "action_result", "dorm_network", [
            turn("My DormNet connection is not working.", topic="dorm_network", intent="troubleshooting"),
            turn(
                "I tried my roommate's network port and it works.",
                topic="dorm_network", intent="troubleshooting",
                followup_type="action_result", action="cross_test",
                action_outcome="works", answer_contains_any=("report", "port", "dorms@"),
                must_not_repeat_action="cross_test", escalation="required",
            ),
        ]),
        conversation("followup_en_002", "en", "failed_recommendation", "campus_wifi", [
            turn("Campus Wi-Fi will not connect.", topic="campus_wifi", intent="troubleshooting"),
            turn(
                "I reconnected, but it still does not work.",
                topic="campus_wifi", intent="troubleshooting",
                followup_type="action_result", action="reconnect",
                action_outcome="still_fails", answer_contains_any=("next", "forget", "SSID", "settings"),
                must_not_repeat_action="reconnect",
            ),
        ]),
        conversation("followup_en_003", "en", "successful_recommendation", "vpn", [
            turn("My NTHU VPN connection keeps failing.", topic="vpn", intent="troubleshooting"),
            turn(
                "I corrected the settings and that fixed it.",
                topic="vpn", intent="troubleshooting",
                followup_type="action_result", action="reconfigure",
                action_outcome="works", resolution_status="resolved",
                answer_contains_any=("working", "resolved", "fixed", "glad"),
            ),
        ]),
        conversation("followup_en_004", "en", "diagnostic_answer", "dorm_network", [
            turn("DormNet is down for me.", topic="dorm_network", intent="troubleshooting"),
            turn(
                "My roommate can connect; only mine fails.",
                topic="dorm_network", intent="troubleshooting",
                followup_type="diagnostic_answer", action="peer_check",
                action_outcome="peer_works", answer_contains_any=("device", "port", "cross-test", "settings"),
            ),
        ]),
        conversation("followup_en_005", "en", "partial_result", "campus_wifi", [
            turn("How should I diagnose Wi-Fi authentication failures?", topic="campus_wifi", intent="troubleshooting"),
            turn(
                "A works, B still fails on nthupeap, and I have not tried C yet.",
                topic="campus_wifi", intent="troubleshooting",
                followup_type="action_result", action="multiple_checks",
                action_outcome="partial", answer_contains_any=("not tried", "remaining", "C", "nthupeap"),
            ),
        ]),
        conversation("followup_en_006", "en", "recommendation_why", "dorm_network", [
            turn("DormNet suddenly stopped working.", topic="dorm_network", intent="troubleshooting"),
            turn(
                "Why should I cross-test another port?",
                topic="dorm_network", intent="troubleshooting",
                followup_type="recommendation_question", action="cross_test",
                action_outcome="question", answer_contains_any=("isolate", "determine", "identify", "port"),
            ),
        ]),
        conversation("followup_en_007", "en", "recommendation_how", "campus_wifi", [
            turn("Campus wireless authentication keeps failing.", topic="campus_wifi", intent="troubleshooting"),
            turn(
                "How do I forget the network?",
                topic="campus_wifi", intent="troubleshooting",
                followup_type="recommendation_question", action="forget_network",
                action_outcome="question", answer_contains_any=("Wi-Fi", "forget", "remove", "settings"),
            ),
        ]),
        conversation("followup_en_008", "en", "recommendation_rejected", "vpn", [
            turn("The VPN client will not open.", topic="vpn", intent="troubleshooting"),
            turn(
                "I cannot reinstall it right now. Is there another option?",
                topic="vpn", intent="troubleshooting",
                followup_type="recommendation_rejected", action="reinstall",
                action_outcome="unavailable", resolution_status="blocked",
                answer_contains_any=("instead", "alternative", "check", "browser"),
            ),
        ]),
        conversation("followup_en_009", "en", "escalation", "dorm_network", [
            turn("I think my DormNet wall port is broken.", topic="dorm_network", intent="troubleshooting"),
            turn(
                "I tested another port. Where should I report this?",
                topic="dorm_network", intent="troubleshooting",
                followup_type="continuation", action="cross_test",
                action_outcome="still_fails", answer_contains_any=("dorms@", "report", "location", "tests"),
                escalation="required",
            ),
        ]),
        conversation("followup_en_010", "en", "correction", "campus_wifi", [
            turn("The library Wi-Fi is very slow.", topic="campus_wifi", intent="troubleshooting"),
            turn(
                "I meant the Humanities and Social Sciences Building, not the library.",
                topic="campus_wifi", intent="troubleshooting",
                followup_type="correction", action_outcome="provided",
                answer_contains_any=("Humanities", "Wi-Fi", "wireless"),
            ),
        ]),
        conversation("followup_en_011", "en", "application_continuation", "email", [
            turn("How do I apply for a student email account?", topic="email", intent="application"),
            turn(
                "The application is complete. How do I log in now?",
                topic="email", intent="configuration",
                followup_type="continuation", action="application",
                action_outcome="completed", answer_contains_any=("log in", "email", "account"),
            ),
        ]),
        conversation("followup_en_012", "en", "diagnostic_answer", "vpn", [
            turn("VPN authentication fails.", topic="vpn", intent="troubleshooting"),
            turn(
                "The same account works for wireless; only VPN fails.",
                topic="vpn", intent="troubleshooting",
                followup_type="diagnostic_answer", action="credential_check",
                action_outcome="credentials_work", answer_contains_any=("VPN", "server", "enabled", "settings"),
            ),
        ]),
        conversation("followup_en_013", "en", "coverage_continuation", "campus_wifi", [
            turn("Is Wi-Fi available in the Humanities and Social Sciences Building?", topic="campus_wifi", intent="lookup"),
            turn(
                "If it is, how do I connect there?",
                topic="campus_wifi", intent="configuration",
                followup_type="continuation", answer_contains_any=("nthu-cc", "nthupeap", "eduroam"),
            ),
        ]),
        conversation("followup_en_014", "en", "status_result", "dorm_network", [
            turn("DormNet is offline. What should I check first?", topic="dorm_network", intent="troubleshooting"),
            turn(
                "The status page is normal, but I still cannot get online.",
                topic="dorm_network", intent="troubleshooting",
                followup_type="action_result", action="status_check",
                action_outcome="still_fails", answer_contains_any=("next", "cross-test", "port", "settings"),
                must_not_repeat_action="status_check",
            ),
        ]),
        conversation("followup_en_015", "en", "failed_recommendation", "email", [
            turn("I cannot log in to my student mailbox.", topic="email", intent="troubleshooting"),
            turn(
                "I already reset the password and login still fails.",
                topic="email", intent="troubleshooting",
                followup_type="action_result", action="reset_password",
                action_outcome="still_fails", answer_contains_any=("account", "login", "GApp", "mailbox"),
                must_not_repeat_action="reset_password",
            ),
        ]),
        conversation("followup_en_016", "en", "diagnostic_answer", "email", [
            turn("I am not sure which NTHU email account to apply for.", topic="email", intent="application"),
            turn(
                "I am a new student this year.",
                topic="email", intent="application",
                followup_type="diagnostic_answer", action="student_status_question",
                action_outcome="new_student", answer_contains_any=("new student", "student email", "apply"),
            ),
        ]),
        conversation("followup_en_017", "en", "recommendation_how", "vpn", [
            turn("VPN cannot reach an internal NTHU resource.", topic="vpn", intent="troubleshooting"),
            turn(
                "How do I verify that VPN access is enabled?",
                topic="vpn", intent="troubleshooting",
                followup_type="recommendation_question", action="verify_activation",
                action_outcome="question", answer_contains_any=("Academic Information", "VPN", "enable"),
            ),
        ]),
        conversation("followup_en_018", "en", "correction", "campus_wifi", [
            turn("Does Shui Mu have Wi-Fi?", topic="campus_wifi", intent="lookup"),
            turn(
                "I mean Shui Mu Life Center, not a dorm.",
                topic="campus_wifi", intent="lookup",
                followup_type="correction", action_outcome="provided",
                answer_contains_any=("Shui Mu Life Center", "Wi-Fi", "wireless"),
            ),
        ]),
        conversation("followup_en_019", "en", "status_continuation", "dorm_network", [
            turn("Where can I check DormNet status?", topic="dorm_network", intent="lookup"),
            turn(
                "I checked it. It says disabled. What should I do next?",
                topic="dorm_network", intent="troubleshooting",
                followup_type="continuation", action="status_check",
                action_outcome="disabled", answer_contains_any=("disabled", "reason", "contact", "dorms@"),
                escalation="required",
            ),
        ]),
        conversation("followup_en_020", "en", "action_result", "dorm_network", [
            turn("My computer cannot get online through my dorm wall port.", topic="dorm_network", intent="troubleshooting"),
            turn(
                "The same computer works normally on my roommate's port.",
                topic="dorm_network", intent="troubleshooting",
                followup_type="action_result", action="cross_test",
                action_outcome="works", answer_contains_any=("original", "port", "report", "dorms@"),
                must_not_repeat_action="cross_test", escalation="required",
            ),
        ]),
    ]
    return [*zh, *en]


def long_cases() -> list[dict[str, Any]]:
    return [
        conversation("followup_zh_long_001", "zh-Hant", "long_troubleshooting", "dorm_network", [
            turn("宿網完全連不上。", topic="dorm_network", intent="troubleshooting"),
            turn("室友可以上網。", topic="dorm_network", intent="troubleshooting", followup_type="diagnostic_answer", action="peer_check", action_outcome="peer_works", answer_contains_any=("裝置", "網路孔", "交叉")),
            turn("你說的交叉測試要怎麼做？", topic="dorm_network", intent="troubleshooting", followup_type="recommendation_question", action="cross_test", action_outcome="question", answer_contains_any=("同一台", "室友", "網路孔")),
            turn("測完了，我的電腦接室友的孔可以。", topic="dorm_network", intent="troubleshooting", followup_type="action_result", action="cross_test", action_outcome="works", answer_contains_any=("原本", "網路孔", "報修"), must_not_repeat_action="cross_test", escalation="required"),
            turn("報修時要把剛才的測試結果寫進去嗎？", topic="dorm_network", intent="troubleshooting", followup_type="continuation", action="contact_support", action_outcome="question", answer_contains_any=("測試結果", "地點", "dorms@"), escalation="required"),
        ], long_chain=True),
        conversation("followup_zh_long_002", "zh-Hant", "long_troubleshooting", "campus_wifi", [
            turn("校園 Wi-Fi 一直連不上。", topic="campus_wifi", intent="troubleshooting"),
            turn("重新連線試過了，沒有改善。", topic="campus_wifi", intent="troubleshooting", followup_type="action_result", action="reconnect", action_outcome="still_fails", answer_contains_any=("下一步", "忘記", "設定"), must_not_repeat_action="reconnect"),
            turn("為什麼要忘記這個網路？", topic="campus_wifi", intent="troubleshooting", followup_type="recommendation_question", action="forget_network", action_outcome="question", answer_contains_any=("設定", "重新", "認證")),
            turn("忘記後重加了，仍然認證失敗。", topic="campus_wifi", intent="troubleshooting", followup_type="action_result", action="forget_network", action_outcome="still_fails", answer_contains_any=("帳號", "密碼", "802.1X", "協助"), must_not_repeat_action="forget_network"),
            turn("這些都試完了，下一步該聯絡誰？", topic="campus_wifi", intent="troubleshooting", followup_type="continuation", action="contact_support", action_outcome="question", answer_contains_any=("wlan@", "地點", "SSID", "測試"), escalation="required"),
        ], long_chain=True),
        conversation("followup_zh_long_003", "zh-Hant", "long_troubleshooting", "vpn", [
            turn("VPN 安裝後連不上。", topic="vpn", intent="troubleshooting"),
            turn("錯誤畫面顯示伺服器無法連線。", topic="vpn", intent="troubleshooting", followup_type="diagnostic_answer", action="error_question", action_outcome="provided", answer_contains_any=("伺服器", "nthu.twaren.net", "設定")),
            turn("那伺服器欄位要怎麼改？", topic="vpn", intent="troubleshooting", followup_type="recommendation_question", action="server_check", action_outcome="question", answer_contains_any=("nthu.twaren.net", "名稱", "伺服器")),
            turn("改成正確伺服器了，但第一次還是失敗。", topic="vpn", intent="troubleshooting", followup_type="action_result", action="server_check", action_outcome="still_fails", answer_contains_any=("帳號", "啟用", "等待", "VPN"), must_not_repeat_action="server_check"),
            turn("等了十分鐘再連就好了。", topic="vpn", intent="troubleshooting", followup_type="action_result", action="retry_after_wait", action_outcome="works", resolution_status="resolved", answer_contains_any=("恢復", "可以", "正常", "已解決")),
        ], long_chain=True),
        conversation("followup_zh_long_004", "zh-Hant", "long_troubleshooting", "email", [
            turn("新生信箱登入失敗。", topic="email", intent="troubleshooting"),
            turn("我是今年入學的新生。", topic="email", intent="troubleshooting", followup_type="diagnostic_answer", action="student_status_question", action_outcome="new_student", answer_contains_any=("新生", "信箱", "帳號")),
            turn("密碼已經重設過了，還是不行。", topic="email", intent="troubleshooting", followup_type="action_result", action="reset_password", action_outcome="still_fails", answer_contains_any=("帳號", "GApp", "登入"), must_not_repeat_action="reset_password"),
            turn("更正一下，我用的是 GApp，不是舊學生信箱。", topic="email", intent="troubleshooting", followup_type="correction", action_outcome="provided", answer_contains_any=("GApp", "Google", "帳號")),
            turn("改用正確的 GApp 帳號後可以登入了。", topic="email", intent="troubleshooting", followup_type="action_result", action="account_correction", action_outcome="works", resolution_status="resolved", answer_contains_any=("可以登入", "已解決", "正常")),
        ], long_chain=True),
        conversation("followup_zh_long_005", "zh-Hant", "long_troubleshooting", "campus_wifi", [
            turn("人社館 Wi-Fi 很慢。", topic="campus_wifi", intent="troubleshooting"),
            turn("要怎麼確認是裝置還是現場網路？", topic="campus_wifi", intent="troubleshooting", followup_type="recommendation_question", action="cross_test", action_outcome="question", answer_contains_any=("另一台", "地點", "SSID", "比較")),
            turn("換另一台裝置也一樣慢。", topic="campus_wifi", intent="troubleshooting", followup_type="action_result", action="cross_test", action_outcome="still_fails", answer_contains_any=("現場", "SSID", "時間", "範圍"), must_not_repeat_action="cross_test"),
            turn("狀態頁看起來正常。", topic="campus_wifi", intent="troubleshooting", followup_type="action_result", action="status_check", action_outcome="completed", answer_contains_any=("地點", "SSID", "時間", "回報"), must_not_repeat_action="status_check"),
            turn("那我要回報哪些資訊？", topic="campus_wifi", intent="troubleshooting", followup_type="continuation", action="contact_support", action_outcome="question", answer_contains_any=("wlan@", "人社", "SSID", "時間"), escalation="required"),
        ], long_chain=True),
        conversation("followup_en_long_001", "en", "long_troubleshooting", "dorm_network", [
            turn("DormNet does not work at all.", topic="dorm_network", intent="troubleshooting"),
            turn("My roommate can get online.", topic="dorm_network", intent="troubleshooting", followup_type="diagnostic_answer", action="peer_check", action_outcome="peer_works", answer_contains_any=("device", "port", "cross-test")),
            turn("How do I perform the cross-test you mentioned?", topic="dorm_network", intent="troubleshooting", followup_type="recommendation_question", action="cross_test", action_outcome="question", answer_contains_any=("same device", "roommate", "port")),
            turn("I tested it. My computer works on my roommate's port.", topic="dorm_network", intent="troubleshooting", followup_type="action_result", action="cross_test", action_outcome="works", answer_contains_any=("original", "port", "report"), must_not_repeat_action="cross_test", escalation="required"),
            turn("Should I include that test result in the repair report?", topic="dorm_network", intent="troubleshooting", followup_type="continuation", action="contact_support", action_outcome="question", answer_contains_any=("test result", "location", "dorms@"), escalation="required"),
        ], long_chain=True),
        conversation("followup_en_long_002", "en", "long_troubleshooting", "campus_wifi", [
            turn("Campus Wi-Fi keeps failing to connect.", topic="campus_wifi", intent="troubleshooting"),
            turn("I already reconnected and it did not help.", topic="campus_wifi", intent="troubleshooting", followup_type="action_result", action="reconnect", action_outcome="still_fails", answer_contains_any=("next", "forget", "settings"), must_not_repeat_action="reconnect"),
            turn("Why should I forget the network?", topic="campus_wifi", intent="troubleshooting", followup_type="recommendation_question", action="forget_network", action_outcome="question", answer_contains_any=("settings", "fresh", "authentication")),
            turn("I removed and re-added it, but authentication still fails.", topic="campus_wifi", intent="troubleshooting", followup_type="action_result", action="forget_network", action_outcome="still_fails", answer_contains_any=("account", "password", "802.1X", "support"), must_not_repeat_action="forget_network"),
            turn("I finished those steps. Who should I contact next?", topic="campus_wifi", intent="troubleshooting", followup_type="continuation", action="contact_support", action_outcome="question", answer_contains_any=("wlan@", "location", "SSID", "tests"), escalation="required"),
        ], long_chain=True),
        conversation("followup_en_long_003", "en", "long_troubleshooting", "vpn", [
            turn("VPN will not connect after installation.", topic="vpn", intent="troubleshooting"),
            turn("The error says the server cannot be reached.", topic="vpn", intent="troubleshooting", followup_type="diagnostic_answer", action="error_question", action_outcome="provided", answer_contains_any=("server", "nthu.twaren.net", "settings")),
            turn("How do I change the server field?", topic="vpn", intent="troubleshooting", followup_type="recommendation_question", action="server_check", action_outcome="question", answer_contains_any=("nthu.twaren.net", "name", "server")),
            turn("The server is correct now, but the first retry still failed.", topic="vpn", intent="troubleshooting", followup_type="action_result", action="server_check", action_outcome="still_fails", answer_contains_any=("account", "enabled", "wait", "VPN"), must_not_repeat_action="server_check"),
            turn("I waited ten minutes and now it works.", topic="vpn", intent="troubleshooting", followup_type="action_result", action="retry_after_wait", action_outcome="works", resolution_status="resolved", answer_contains_any=("working", "resolved", "fixed", "great")),
        ], long_chain=True),
        conversation("followup_en_long_004", "en", "long_troubleshooting", "email", [
            turn("My new-student email login fails.", topic="email", intent="troubleshooting"),
            turn("I am a new student this year.", topic="email", intent="troubleshooting", followup_type="diagnostic_answer", action="student_status_question", action_outcome="new_student", answer_contains_any=("new student", "email", "account")),
            turn("I reset the password already, and it still fails.", topic="email", intent="troubleshooting", followup_type="action_result", action="reset_password", action_outcome="still_fails", answer_contains_any=("account", "GApp", "login"), must_not_repeat_action="reset_password"),
            turn("Correction: I use GApp, not the legacy student mailbox.", topic="email", intent="troubleshooting", followup_type="correction", action_outcome="provided", answer_contains_any=("GApp", "Google", "account")),
            turn("Using the correct GApp account fixed the login.", topic="email", intent="troubleshooting", followup_type="action_result", action="account_correction", action_outcome="works", resolution_status="resolved", answer_contains_any=("working", "resolved", "login")),
        ], long_chain=True),
        conversation("followup_en_long_005", "en", "long_troubleshooting", "campus_wifi", [
            turn("Wi-Fi is very slow in the Humanities and Social Sciences Building.", topic="campus_wifi", intent="troubleshooting"),
            turn("How can I tell whether it is my device or the local network?", topic="campus_wifi", intent="troubleshooting", followup_type="recommendation_question", action="cross_test", action_outcome="question", answer_contains_any=("another device", "location", "SSID", "compare")),
            turn("A second device is slow there too.", topic="campus_wifi", intent="troubleshooting", followup_type="action_result", action="cross_test", action_outcome="still_fails", answer_contains_any=("location", "SSID", "time", "area"), must_not_repeat_action="cross_test"),
            turn("The status page looks normal.", topic="campus_wifi", intent="troubleshooting", followup_type="action_result", action="status_check", action_outcome="completed", answer_contains_any=("location", "SSID", "time", "report"), must_not_repeat_action="status_check"),
            turn("What information should I report?", topic="campus_wifi", intent="troubleshooting", followup_type="continuation", action="contact_support", action_outcome="question", answer_contains_any=("wlan@", "Humanities", "SSID", "time"), escalation="required"),
        ], long_chain=True),
    ]


def build_cases() -> list[dict[str, Any]]:
    cases = [*short_cases(), *long_cases()]
    assert len(cases) == 50
    assert sum(case["language"] == "zh-Hant" for case in cases) == 25
    assert sum(case["language"] == "en" for case in cases) == 25
    assert sum(case["long_chain"] for case in cases) == 10
    assert all(2 <= len(case["conversation"]) <= 5 for case in cases)
    return cases
