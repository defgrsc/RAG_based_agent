from __future__ import annotations

from typing import Any

from agent.followups import detect_actions


SOURCE_BY_TOPIC = {
    "dorm_network": (
        "DormNet troubleshooting [Network Systems Division]",
        "https://net.nthu.edu.tw/netsys/faq:domitory_net_useless",
    ),
    "campus_wifi": (
        "Campus Wi-Fi troubleshooting [Network Systems Division]",
        "https://net.nthu.edu.tw/netsys/faq:wlan_useless",
    ),
    "vpn": (
        "SSL VPN setup [Network Systems Division]",
        "https://net.nthu.edu.tw/netsys/sslvpn:sslvpn_setup",
    ),
    "email": (
        "Student email application [Network Systems Division]",
        "https://net.nthu.edu.tw/netsys/mail:application_student:new_std",
    ),
}


def _source(topic: str) -> list[dict[str, Any]]:
    title, url = SOURCE_BY_TOPIC.get(
        topic,
        ("NTHU Network Systems Division FAQ", "https://net.nthu.edu.tw/netsys/faq"),
    )
    return [{
        "title": title,
        "source_name": title,
        "url": url,
        "content": "",
        "chunk_index": 0,
        "score": 1.0,
    }]


def _payload(answer: str, topic: str) -> dict[str, Any]:
    return {"answer": answer, "sources": _source(topic)}


def _primary_result(state: dict[str, Any]) -> dict[str, Any]:
    return next(iter(state.get("current_action_results", [])), {})


def _question_action(state: dict[str, Any]) -> str:
    current = detect_actions(state.get("current_user_message", ""))
    if current:
        return current[0]
    previous = [
        action for action in state.get("previous_recommendations", [])
        if action != "contact_support"
    ]
    return previous[0] if previous else ""


def _support_answer(topic: str, *, english: bool) -> str:
    location = "the exact location" if english else "確切位置"
    if topic == "dorm_network":
        if english:
            return (
                "The result points to the original DormNet wall port or its line. "
                "Report it to dorms@cc.nthu.edu.tw and include the dorm and room, "
                "the original port, device and IP settings, every completed test, "
                "the cross-test result, error details, and screenshots."
            )
        return (
            "這個結果較指向原本的宿網網路孔或線路。請寄信到 "
            "dorms@cc.nthu.edu.tw 報修，附上宿舍與房號、原本網路孔、"
            "裝置與 IP 設定、已完成的測試、交叉測試結果、錯誤訊息與截圖。"
        )
    if topic in {"campus_wifi", "vpn"}:
        service = "VPN" if topic == "vpn" else "campus Wi-Fi"
        if english:
            return (
                f"Contact wlan@cc.nthu.edu.tw about the {service} issue. Include "
                f"{location}, SSID when relevant, device OS, time, account format, "
                "completed tests and their results, the error message, and screenshots."
            )
        service_zh = "VPN" if topic == "vpn" else "校園 Wi-Fi"
        return (
            f"請將這個{service_zh}問題回報至 wlan@cc.nthu.edu.tw，附上{location}、"
            "適用時的 SSID、裝置系統、發生時間、帳號格式、已完成測試與結果、"
            "錯誤訊息及截圖。"
        )
    if english:
        return (
            "Report the email issue with the account type, student status, exact login "
            "error, completed checks, and screenshots so it can be investigated."
        )
    return "請整理帳號類型、學生身分、登入錯誤、已完成檢查與截圖後回報信箱問題。"


def _recommendation_answer(action: str, *, english: bool) -> str:
    if action == "cross_test":
        if english:
            return (
                "A cross-test isolates the device from the local network or wall port. "
                "Use the same device and cable on a known-working port, such as your "
                "roommate's port; for Wi-Fi, compare another device at the same location "
                "and SSID. Comparing the results identifies which side has the problem."
            )
        return (
            "交叉測試是為了區分裝置端與現場網路或網路孔。請用同一台裝置與同一條"
            "網路線測室友已知可用的網路孔；若是 Wi-Fi，則在同一地點、同一 SSID "
            "改用另一台裝置比較。結果可用來判斷問題在哪一側。"
        )
    if action == "forget_network":
        if english:
            return (
                "Open the device's Wi-Fi settings, select the saved NTHU network, choose "
                "Forget or Remove, then join the SSID again. This clears stale settings "
                "and starts a fresh authentication attempt."
            )
        return (
            "請開啟裝置的 Wi-Fi 設定，選取已儲存的清大網路後按「忘記」或「移除」，"
            "再重新加入該 SSID。這會清掉舊設定並重新進行認證。"
        )
    if action == "verify_activation":
        if english:
            return (
                "Log in to the Academic Information System, open the Network Systems "
                "Division online service, select the wireless LAN account, and verify "
                "that VPN access is enabled. Save changes and allow about ten minutes."
            )
        return (
            "請登入校務資訊系統，進入網路系統組線上服務，選擇無線區域網路帳號，"
            "確認 VPN 功能已勾選啟用；儲存後約等十分鐘生效。"
        )
    if action == "server_check":
        if english:
            return (
                "Open the VPN connection profile and set both the profile name and "
                "server field to nthu.twaren.net, save it, and retry the connection."
            )
        return "請打開 VPN 連線設定，將「名稱」與「伺服器」欄都填入 nthu.twaren.net，儲存後再連線。"
    if action == "status_check":
        return (
            "Check the service status page and note whether it is normal, blocked, or disabled."
            if english
            else "請查看服務狀態頁，記下顯示正常、封鎖或停用中的哪一種狀態。"
        )
    if action == "reset_password":
        return (
            "Reset the password once, then test the same account on the intended service."
            if english
            else "請重設一次密碼，再用同一帳號測試原本的服務。"
        )
    return (
        "That step is meant to narrow down the remaining cause. Complete it once and "
        "report the exact result so the next step can be selected."
        if english
        else "這個步驟是用來縮小原因範圍；完成一次並提供確切結果後，就能決定下一步。"
    )


def _diagnostic_answer(
    state: dict[str, Any],
    action: str,
    outcome: str,
    *,
    english: bool,
) -> str:
    topic = state.get("current_topic", "unknown")
    intent = state.get("current_intent", "unknown")
    if action == "peer_check" and outcome == "peer_works":
        return (
            "Since your roommate can connect, the shared service is available. Next, "
            "cross-test the same device and cable on your roommate's known-working port "
            "to distinguish your device/settings from your original port."
            if english
            else "室友可以連線，表示共用服務可用。下一步請用同一台裝置與網路線測室友已知可用的網路孔，區分裝置／設定與原本網路孔。"
        )
    if action == "credential_check" and outcome == "credentials_work":
        return (
            "Because the same account works on wireless, focus on VPN: verify that VPN "
            "access is enabled and that the server is nthu.twaren.net."
            if english
            else "同一帳號可登入無線網路，帳密本身較可能正常；請改查 VPN 是否啟用，以及伺服器是否為 nthu.twaren.net。"
        )
    if action == "student_status_question" and outcome == "new_student":
        if intent == "application":
            return (
                "As a new student, apply for the student email account through the new-student "
                "mailbox process, then use the issued account to log in."
                if english
                else "你是新生，請依新生學生信箱申請流程建立帳號，完成後再用核發的帳號登入。"
            )
        return (
            "Since this is a new-student login, reset the student email password once and "
            "test again; if it still fails, confirm whether the account is GApp or the legacy mailbox."
            if english
            else "這是新生信箱登入問題；請先重設學生信箱密碼再測一次，若仍失敗，再確認使用的是 GApp 或舊學生信箱帳號。"
        )
    if action == "error_question":
        return (
            "A server-unreachable error points to the VPN profile. Verify the server field "
            "before changing credentials or reinstalling the client."
            if english
            else "「伺服器無法連線」較指向 VPN 連線設定；請先確認伺服器欄位，再考慮帳號或重裝。"
        )
    return (
        "Thanks—that diagnostic answer is recorded. Use it to test the remaining side of the connection next."
        if english
        else "收到，這項診斷結果已記錄；下一步只需要測尚未排除的連線端。"
    )


def _failed_action_answer(topic: str, action: str, *, english: bool) -> str:
    if topic == "campus_wifi" and action == "reconnect":
        return (
            "Reconnecting is already completed and did not help. Next, forget or remove "
            "the saved Wi-Fi network, rejoin the same SSID, and note the authentication result."
            if english
            else "重新連線已完成且無效，不要重複。下一步請忘記或移除已儲存的 Wi-Fi，再加入同一 SSID 並記下認證結果。"
        )
    if topic == "campus_wifi" and action == "forget_network":
        return (
            "The saved network was already refreshed and authentication still fails. Next, "
            "verify the account format, password, and 802.1X settings."
            if english
            else "忘記後重加仍認證失敗，表示舊設定不是唯一原因。下一步請確認帳號格式、密碼與 802.1X 設定。"
        )
    if topic == "campus_wifi" and action == "cross_test":
        return (
            "A second device is also slow, so the issue is more likely local to the location. "
            "Record the SSID, exact location, time, and affected area, then check the status page."
            if english
            else "另一台裝置也慢，問題較可能在現場。請記下 SSID、確切地點、時間與影響範圍，接著查看狀態頁。"
        )
    if topic == "dorm_network":
        return (
            "The previous setup is complete but DormNet still does not work. Check the "
            "service status first, then cross-test the same device on another wall port."
            if english
            else "前面的設定已完成但宿網仍不能上網。下一步先查服務狀態，再用同一台裝置交叉測試另一個網路孔。"
        )
    if topic == "dorm_network" and action == "status_check":
        return (
            "The status page is normal, so continue with a cross-test of the same device on "
            "another port, and verify the IP and port settings."
            if english
            else "狀態頁正常，下一步請用同一台裝置測另一個網路孔，並確認 IP 與網路孔設定。"
        )
    if topic == "email" and action == "reset_password":
        return (
            "The password reset is already complete. Next, verify the account type and login "
            "name—especially whether this is a GApp account or the legacy student mailbox."
            if english
            else "密碼重設已完成，不要再重設。下一步請確認帳號類型與登入名稱，尤其是 GApp 或舊學生信箱。"
        )
    if topic == "vpn" and action == "server_check":
        return (
            "The server is correct but the retry failed. Verify that VPN access is enabled, "
            "then wait about ten minutes for activation and retry once."
            if english
            else "伺服器已正確但首次重試失敗。請確認 VPN 已啟用，等待約十分鐘生效後再試一次。"
        )
    return (
        "That completed step did not solve the problem, so do not repeat it. Check the next "
        "unverified setting and report its exact result."
        if english
        else "這個步驟已完成但未解決問題，不要重複；請改查下一個尚未確認的設定並提供結果。"
    )


def build_progression_response(state: dict[str, Any]) -> dict[str, Any] | None:
    followup_type = state.get("followup_type", "new_question")
    if followup_type == "new_question":
        return None
    topic = state.get("current_topic", "unknown")
    english = state.get("language") == "en"
    if (
        state.get("current_intent") != "troubleshooting"
        and followup_type not in {"correction", "diagnostic_answer"}
        and not (
            followup_type == "continuation"
            and topic in {"email", "campus_wifi"}
        )
    ):
        return None
    result = _primary_result(state)
    action = str(result.get("action", ""))
    outcome = str(result.get("outcome", ""))
    message = state.get("current_user_message", "")
    current_actions = detect_actions(message)

    if state.get("resolution_status") == "resolved":
        answer = (
            "Great—the connection or login is working now, so this issue is resolved. "
            "There is no need to repeat the completed troubleshooting steps."
            if english
            else "很好，連線或登入已恢復正常，這個問題可視為已解決，不需要重複先前的排查步驟。"
        )
        return _payload(answer, topic)

    if followup_type == "recommendation_question":
        return _payload(_recommendation_answer(_question_action(state), english=english), topic)

    if followup_type == "recommendation_rejected" or outcome == "unavailable":
        answer = (
            "That step is unavailable right now, so do not keep retrying it. As an alternative, "
            "first check whether VPN access is enabled, verify the server field, and use a browser "
            "to obtain the correct installer when possible."
            if english
            else "目前無法執行該步驟，就先不要反覆嘗試。可以先用替代方式檢查 VPN 是否啟用與伺服器欄位，並在可行時用瀏覽器取得正確安裝檔。"
        )
        return _payload(answer, topic)

    if followup_type == "diagnostic_answer":
        return _payload(
            _diagnostic_answer(state, action, outcome, english=english),
            topic,
        )

    if outcome == "partial":
        answer = (
            "The result is partial: A works, B still fails on nthupeap, and C has not been tried. "
            "Keep A as completed, investigate B, and perform only the remaining C check next."
            if english
            else "目前是部分結果：A 已完成，B 在 nthupeap 仍失敗，C（重開機）還沒試。保留 A、B 的結果，下一步只做尚未完成的 C。"
        )
        return _payload(answer, topic)

    if followup_type == "continuation" and (
        "contact_support" in current_actions or action == "contact_support"
    ):
        return _payload(_support_answer(topic, english=english), topic)

    if outcome == "disabled":
        return _payload(_support_answer(topic, english=english), topic)

    if outcome == "works" and topic == "dorm_network" and action == "cross_test":
        return _payload(_support_answer(topic, english=english), topic)

    if outcome == "still_fails":
        return _payload(_failed_action_answer(topic, action, english=english), topic)

    if outcome == "completed" and action == "status_check":
        answer = (
            "The status page is normal. Record the exact location, SSID, time, affected area, "
            "and completed tests so the issue can be reported without repeating them."
            if english
            else "狀態頁正常。請整理確切地點、SSID、發生時間、影響範圍與已完成測試，回報時就不必重做。"
        )
        return _payload(answer, topic)

    if followup_type == "correction":
        location = state.get("semantic_slots", {}).get("location", "")
        if "gapp" in message.casefold():
            answer = (
                "Correction recorded: this is a GApp account, not the legacy student mailbox. "
                "Use the correct GApp account name for the next login test."
                if english
                else "已更正：使用的是 GApp，不是舊學生信箱。下一次登入請改用正確的 GApp 帳號名稱。"
            )
        else:
            answer = (
                f"Correction recorded: the location is {location or 'the location you just named'}. "
                "I will continue the Wi-Fi check for that building."
                if english
                else f"已更正地點為「{location or '你剛指出的地點'}」，接下來會依該館舍的 Wi-Fi／無線網路狀況處理。"
            )

        return _payload(answer, topic)
    if followup_type == "continuation" and topic == "email":
        answer = (
            "Since the application is complete, sign in to the student email service with the "
            "issued account. If it is GApp, use the GApp login name rather than the legacy mailbox name."
            if english
            else "申請已完成，接下來請用核發的帳號登入學生信箱；若申請的是 GApp，請用 GApp 登入名稱，不要混用舊學生信箱帳號。"
        )
        return _payload(answer, topic)

    if followup_type == "continuation" and topic == "campus_wifi" and state.get("current_intent") == "configuration":
        answer = (
            "At that location, look for nthu-cc, nthupeap, TANetRoaming, or eduroam. "
            "Join one of those SSIDs and use the corresponding campus Wi-Fi login method."
            if english
            else "在該地點請搜尋 nthu-cc、nthupeap、TANetRoaming 或 eduroam，選擇其中一個 SSID 並依對應的校園 Wi-Fi 方式登入。"
        )
        return _payload(answer, topic)

    if followup_type == "continuation":
        return _payload(_support_answer(topic, english=english), topic)

    answer = (
        "The reported result has been recorded. Continue from that result instead of repeating the completed step."
        if english
        else "已記錄這次回報結果；後續會從此結果繼續，不會重複已完成的步驟。"
    )
    return _payload(answer, topic)
