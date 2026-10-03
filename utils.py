import re

OLD_VPN_DOWNLOAD_URL = "https://ndrive.niar.org.tw/navigate/a/#/s/folder/LDQyNzUxNCxuZHJpdmUubmlhci5vcmcudHcvc2csNDI3NTE0"
VPN_DOWNLOAD_URL = "https://ndrive.niar.org.tw/navigate/a/#/s/894C6D3B91C94C3EB0D0B4237BC47B426BL"


WIRELESS_REFERENCE_URLS = (
    "https://net.nthu.edu.tw/netsys/faq#wireless",
    "https://net.nthu.edu.tw/netsys/faq:wlan_auth",
    "https://net.nthu.edu.tw/netsys/faq:wlan_roaming",
)

WIRELESS_APPLICATION_REFERENCE_URLS = (
    "https://net.nthu.edu.tw/netsys/wireless:application",
    "https://net.nthu.edu.tw/netsys/wireless:application:ccxp",
)

WLAN_RANGE_REFERENCE_URLS = (
    "https://net.nthu.edu.tw/netsys/faq:wlan_range",
    "https://net.nthu.edu.tw/netsys/wireless:easy",
)

DORM_REFERENCE_URLS = (
    "https://net.nthu.edu.tw/netsys/faq#學生宿舍網路問題",
    "https://net.nthu.edu.tw/netsys/dormnet/",
)

DORM_APPLICATION_REFERENCE_URLS = (
    "https://net.nthu.edu.tw/netsys/faq:domitory_net_ua_apply",
    "https://net.nthu.edu.tw/netsys/faq:domitory_net_apply",
    "https://net.nthu.edu.tw/netsys/dormnet/",
)

DORM_TROUBLE_REFERENCE_URLS = (
    "https://net.nthu.edu.tw/netsys/faq:domitory_net_useless",
    "https://net.nthu.edu.tw/netsys/dormnet/",
)

DORM_IP_LOOKUP_REFERENCE_URLS = (
    "https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/MyApStatusM.pl",
    "https://net.nthu.edu.tw/netsys/faq:domitory_net_useless",
)

DORM_ROUTER_REFERENCE_URLS = (
    "https://net.nthu.edu.tw/netsys/faq:domitory_network_config2",
)

DORM_CONFIG_REFERENCE_URLS = (
    "https://net.nthu.edu.tw/netsys/faq:domitory_network_config",
)

VPN_REFERENCE_URLS = (
    "https://net.nthu.edu.tw/netsys/sslvpn:info",
    "https://net.nthu.edu.tw/netsys/sslvpn:sslvpn_setup",
    "https://net.nthu.edu.tw/netsys/wireless:application:ccxp",
)

EMAIL_REFERENCE_URLS = (
    "https://net.nthu.edu.tw/netsys/mail:application_student:new_std",
    "https://net.nthu.edu.tw/netsys/gapp#帳號申請流程",
    "https://net.nthu.edu.tw/netsys/faq",
)


def clean_outdated_time_info(text: str) -> str:
    text = re.sub(
        r"今年新生[（(][^）)]*(?:113|114)[^）)]*[）)][^。]*(?:2024|2025)[^。]*。?",
        "",
        text,
    )
    text = re.sub(r"申請時間未[^\n。]*。?", "", text)
    text = re.sub(
        r"(?m)^.*(?:今年新生|新生.*學號年份\s*(?:為|是)?\s*(?:113|114)|學號年份\s*(?:為|是)?\s*(?:113|114)|202[45]\s*年.*新生|2024\s*年\s*8\s*月\s*22\s*日).*(?:\n|$)",
        "",
        text,
    )
    return text.strip()


def clean_source_excerpt(text: str) -> str:
    return clean_outdated_time_info(text)


def is_wireless_related(text: str) -> bool:
    normalized = text.lower()
    return any(
        term in normalized
        for term in (
            "無線",
            "wifi",
            "wi-fi",
            "eduroam",
            "nthu-cc",
            "nthupeap",
            "tanetroaming",
            "校園網路",
        )
    )


def is_dorm_related(text: str) -> bool:
    normalized = text.lower()
    return any(term in text for term in ("宿網", "宿舍網路", "宿舍", "寢室", "學生宿舍")) or any(
        term in normalized for term in ("dormnet", "dormitory network", "dorm network", "dormitory room", "network wall port")
    )


def is_email_related(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in ("信箱", "email", "mail", "webmail", "電子郵件", "郵件", "寄信", "收信", "垃圾信", "郵件記錄器", "smtp", "imap", "pop3"))


def is_vpn_related(text: str) -> bool:
    normalized = text.lower()
    if any(term in normalized for term in ("ssl-vpn", "sslvpn", "twaren", "ivanti", "pulse secure")):
        return True
    if "vpn" in normalized:
        return any(term in normalized for term in ("設定", "連線", "校外", "校內資源", "啟用", "軟體", "下載", "伺服器"))
    return any(
        term in normalized
        for term in (
            "校外連",
            "校外連線",
            "校外連到學校",
            "校外連到校內",
            "校內資源",
        )
    )


def is_location_network_query(text: str) -> bool:
    return any(term in text for term in ("哪裡有網路", "哪裡有 wifi", "哪裡有 Wi-Fi", "有網路嗎", "有 Wi-Fi 嗎", "有wifi嗎", "有無線網路嗎"))


def is_application_related(text: str) -> bool:
    return any(term in text for term in ("申請", "帳號", "校務資訊", "線上服務"))


def is_troubleshooting_related(text: str) -> bool:
    return any(term in text for term in ("連不到", "不能用", "不通", "無法連", "沒網路", "斷線", "故障"))


def is_router_related(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in ("分享器", "路由器", "router", "wifi 分享器", "wi-fi 分享器"))


def is_dorm_config_related(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in ("設定宿舍網路", "宿舍網路的 ip", "宿舍網路 ip", "ip 怎麼設定", "tcp/ip", "ip 設定", "設定 ip"))


def is_dorm_ip_lookup_related(text: str) -> bool:
    normalized = text.lower().replace(" ", "")
    return "ip" in normalized and any(term in normalized for term in ("忘記", "忘了", "不記得", "查", "查詢", "查看", "看", "找", "狀態", "禁用", "封鎖", "停用"))


def select_reference_urls(text: str) -> tuple[str, ...]:
    if is_vpn_related(text):
        return VPN_REFERENCE_URLS
    if is_location_network_query(text):
        return WLAN_RANGE_REFERENCE_URLS
    if is_dorm_related(text):
        if is_dorm_ip_lookup_related(text):
            return DORM_IP_LOOKUP_REFERENCE_URLS
        if is_dorm_config_related(text):
            return DORM_CONFIG_REFERENCE_URLS
        if is_router_related(text):
            return DORM_ROUTER_REFERENCE_URLS
        if is_troubleshooting_related(text):
            return DORM_TROUBLE_REFERENCE_URLS
        if is_application_related(text):
            return DORM_APPLICATION_REFERENCE_URLS
        return DORM_REFERENCE_URLS
    if is_email_related(text):
        return EMAIL_REFERENCE_URLS
    if is_wireless_related(text):
        urls = list(WIRELESS_REFERENCE_URLS)
        if is_application_related(text):
            urls = list(WIRELESS_APPLICATION_REFERENCE_URLS) + urls
        return tuple(dict.fromkeys(urls[:3]))
    return ("https://net.nthu.edu.tw/netsys/faq",)


def bold_markdown_headings(text: str) -> str:
    text = re.sub(
        r"(?m)^#{2,4}\s+\*\*(.+?)\*\*\s*$",
        lambda match: f"**{match.group(1).strip()}**",
        text,
    )
    text = re.sub(
        r"(?m)^#{2,4}\s+([^\n#].*?)\s*$",
        lambda match: f"**{match.group(1).strip()}**",
        text,
    )
    return text


def remove_ccxp_login_urls(text: str, question: str = "") -> str:
    keep_ccxp_url = ("宿網" in question or "宿舍網路" in question) and "申請" in question
    if keep_ccxp_url:
        return text
    text = re.sub(
        r"(登入(?:「)?校務資訊系統(?:」)?)[，,、 ]*網址為\s*<?https://www\.ccxp\.nthu\.edu\.tw/ccxp/INQUIRE/?>?[。.]?",
        r"\1。",
        text,
    )
    text = re.sub(
        r"(登入(?:「)?校務資訊系統(?:」)?)[：:]\s*<?https://www\.ccxp\.nthu\.edu\.tw/ccxp/INQUIRE/?>?",
        r"\1",
        text,
    )
    text = re.sub(
        r"(校務資訊系統)[：:]\s*<?https://www\.ccxp\.nthu\.edu\.tw/ccxp/INQUIRE/?>?",
        r"\1",
        text,
    )
    text = re.sub(
        r"(?m)^\s*<?https://www\.ccxp\.nthu\.edu\.tw/ccxp/INQUIRE/?>?\s*$\n?",
        "",
        text,
    )
    return text


def find_broken_nthu_urls(text: str) -> list[str]:
    urls = re.findall(r"https://[^\s<>)）]+", text)
    broken_urls = []
    for url in urls:
        clean_url = url.rstrip("。。，,.;；")
        if not clean_url.startswith("https://net.n"):
            continue
        if not clean_url.startswith("https://net.nthu.edu.tw"):
            broken_urls.append(clean_url)
            continue
        if not clean_url.startswith("https://net.nthu.edu.tw/netsys/"):
            broken_urls.append(clean_url)
    return broken_urls


def replace_broken_nthu_urls(text: str, question: str = "") -> str:
    if "https://net.n" not in text:
        return text

    has_broken_url = bool(
        find_broken_nthu_urls(text)
        or re.search(r"\[[^\]]*https://net\.n[^\]]*\]\(https://net\.n[^)]*\)", text)
    )
    if not has_broken_url:
        return text

    combined = f"{question}\n{text}"
    urls = select_reference_urls(combined)
    reference_block = "詳細可參考：\n" + "\n".join(urls)

    if "詳細可參考：" in text:
        text = text.split("詳細可參考：", 1)[0].rstrip() + "\n\n" + reference_block
    else:
        text = f"{text.rstrip()}\n\n{reference_block}"

    text = re.sub(
        r"\[[^\]]*https://net\.n[^\]]*\]\(https://net\.n[^)]*\)",
        urls[0],
        text,
    )

    def replace_url(match: re.Match[str]) -> str:
        url = match.group(0).rstrip("。。，,.;；")
        if url.startswith("https://net.n") and not url.startswith("https://net.nthu.edu.tw/netsys/"):
            return urls[0]
        return match.group(0)

    return re.sub(r"https://[^\s<>)）]+", replace_url, text)


def remove_source_phrases(text: str) -> str:
    replacements = (
        ("根據 FAQ，", ""),
        ("根據FAQ，", ""),
        ("根據 FAQ", ""),
        ("根據FAQ", ""),
        ("FAQ 顯示，", ""),
        ("FAQ顯示，", ""),
        ("FAQ 將", ""),
        ("FAQ將", ""),
        ("資料中 FAQ", "資料"),
        ("無線網路範圍 FAQ", "無線網路範圍資料"),
        ("這類問題是在問校園無線網路涵蓋範圍，請以「無線上網的範圍」資料為主，不需要提宿網。", ""),
        ("這類問題是在問校園無線網路涵蓋範圍，不需要申請宿網，也不用提宿舍網路。", ""),
        ("這是宿舍網路（宿網）突然無法連線的問題，不是校園無線網路問題。", "宿網突然連不到時，"),
        ("這是宿舍網路（宿網）突然無法連線的問題，", "宿網突然連不到時，"),
        ("不是校園無線網路問題。", ""),
        ("這題應該判斷為宿舍網路（宿網）問題，和校園無線網路的處理方式不同。", "宿網問題可先照下面方向檢查。"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def limit_reference_urls(text: str, question: str = "") -> str:
    marker = "詳細可參考："
    if marker not in text:
        return text

    body, refs = text.split(marker, 1)
    found = []
    for url in re.findall(r"https://[^\s<>)）]+", refs):
        clean_url = url.rstrip("。。，,.;；")
        if (
            clean_url.startswith("https://net.nthu.edu.tw/netsys/")
            or clean_url.startswith("https://dormnet.nthu.edu.tw/")
        ) and clean_url not in found:
            found.append(clean_url)

    if found and len(found) <= 3:
        selected = found
    else:
        combined = f"{question}\n{text}"
        intent_text = question or text
        if is_vpn_related(intent_text):
            selected = list(VPN_REFERENCE_URLS)
        elif is_location_network_query(intent_text):
            selected = list(WLAN_RANGE_REFERENCE_URLS)
        elif is_dorm_related(intent_text) and is_dorm_config_related(intent_text):
            selected = list(DORM_CONFIG_REFERENCE_URLS)
        elif is_dorm_related(intent_text) and is_router_related(intent_text):
            selected = list(DORM_ROUTER_REFERENCE_URLS)
        elif is_dorm_related(intent_text) and is_application_related(intent_text):
            selected = list(DORM_APPLICATION_REFERENCE_URLS)
        else:
            selected = list(select_reference_urls(combined))[:3]
    return body.rstrip() + "\n\n" + marker + "\n" + "\n".join(selected)


def ensure_reference_urls(text: str, question: str = "") -> str:
    complete_marker = "詳細可參考："
    if complete_marker in text:
        tail = text.split(complete_marker, 1)[1]
        if re.search(r"https://net\.nthu\.edu\.tw/netsys/|https://dormnet\.nthu\.edu\.tw/", tail):
            return text
        body = text.split(complete_marker, 1)[0].rstrip()
    elif "詳細可參考" in text:
        body = text.split("詳細可參考", 1)[0].rstrip()
    elif re.search(r"(?:\n|^)(?:詳細可參?|詳細)\s*$", text):
        body = re.sub(r"(?:\n|^)(?:詳細可參?|詳細)\s*$", "", text).rstrip()
    else:
        return text

    urls = select_reference_urls(question or text)[:3]
    return body + "\n\n詳細可參考：\n" + "\n".join(urls)


def normalize_student_mailbox_format(text: str) -> str:
    text = text.replace("學生信箱（@oz.nthu.edu.tw 及 @m??.nthu.edu.tw 格式）", "學生信箱（@m入學年度.nthu.edu.tw 格式）")
    text = text.replace("學生信箱（@oz.nthu.edu.tw 及 @m??.nthu.edu.tw）", "學生信箱（@m入學年度.nthu.edu.tw 格式）")
    text = text.replace("@oz.nthu.edu.tw 及 @m??.nthu.edu.tw", "@m入學年度.nthu.edu.tw")
    text = text.replace("@oz.nthu.edu.tw or the applicable @m??.nthu.edu.tw domain", "@m admission-year.nthu.edu.tw format")
    return text


def normalize_account_and_ccxp_steps(text: str, question: str = "") -> str:
    text = text.replace("u940001@wlan.nthu.edu.tw", "s學號@wlan.nthu.edu.tw")
    text = re.sub(r"例如帳號名稱為\s*u940001\s*[，,]則其帳號格式為\s*s學號@wlan\.nthu\.edu\.tw", "例如 `s學號@wlan.nthu.edu.tw`", text)
    text = re.sub(r"帳號為學號[，,、 ]*預設密碼為身分證字號[，,。 ]*", "", text)
    text = re.sub(r"(?m)^\s*\d+\.\s*輸入學號與預設密碼[^\n。]*[。.]?\n?", "", text)
    text = re.sub(r"(?m)^.*預設密碼[^\n。]*身分證字號[^\n。]*[。.]?\n?", "", text)
    text = re.sub(r"輸入帳號、密碼及驗證碼登入系統[，,。 ]*", "登入系統", text)
    text = text.replace("，輸入後登入", "")
    text = text.replace("輸入後登入。", "")
    text = re.sub(r"輸入該系統的帳號密碼[^。\n]*。?", "", text)
    text = text.replace("進入「網路系統組線上服務」", "在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」")
    text = text.replace("進入『網路系統組線上服務』", "在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」")
    text = text.replace("點選「網路系統組線上服務」", "在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」")
    text = text.replace("於左方點選“網路系統組線上服務”", "在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」")
    text = text.replace("於左方點選「網路系統組線上服務」", "在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」")
    text = remove_ccxp_login_urls(text, question=question)
    return text


def normalize_dorm_config_answer(text: str, question: str = "") -> str:
    combined = f"{question}\n{text}"
    question_text = question or ""
    if "申請" in question_text and not any(term in question_text for term in ("IP", "ip", "TCP/IP", "tcp", "設定")):
        return text
    if not (is_dorm_related(combined) and is_dorm_config_related(question_text or combined)):
        return text
    text = re.sub(r"(?ms)\n*\*\*申請宿舍網路帳號\*\*.*?(?=\n\*\*裝置設定|\n###|\n詳細可參考|$)", "", text)
    text = re.sub(r"(?m)^.*自動取得.*(?:DHCP|IP).*\n?", "", text)
    text = text.replace("裝置設定與連線", "宿網 IP 設定")
    return text


def normalize_wireless_auth_labels(text: str, question: str = "") -> str:
    combined = f"{question}\n{text}"
    if not is_wireless_related(combined):
        return text
    text = text.replace("Web-based 認證方式：", "**瀏覽器登入（Web-based 認證）**\n")
    text = text.replace("Web-based 認證：", "**瀏覽器登入（Web-based 認證）**\n")
    text = text.replace("802.1X + PEAP 認證方式：", "**WiFi 登入（設定一次即可）（802.1X + PEAP）**\n")
    text = text.replace("802.1X + PEAP 認證：", "**WiFi 登入（設定一次即可）（802.1X + PEAP）**\n")
    text = re.sub(r"(?m)^(?!\*\*)瀏覽器登入（Web-based 認證）\s*$", "**瀏覽器登入（Web-based 認證）**", text)
    text = re.sub(r"(?m)^(?!\*\*)自動登入（設定一次即可）（802\.1X \+ PEAP）\s*$", "**WiFi 登入（設定一次即可）**\n**（802.1X + PEAP）**", text)
    text = text.replace("**WiFi 登入（設定一次即可）（802.1X + PEAP）**", "**WiFi 登入（設定一次即可）**\n**（802.1X + PEAP）**")
    text = text.replace("**自動登入（設定一次即可）（802.1X + PEAP）**", "**WiFi 登入（設定一次即可）**\n**（802.1X + PEAP）**")
    text = text.replace("設定完成後，裝置會自動連線", "之後裝置就會自動連線，不需要每次重新登入")
    text = text.replace("設定完成後裝置會自動連線", "之後裝置就會自動連線，不需要每次重新登入")
    text = re.sub(r"(?m)^.*安全類型選擇[「『].*?PEAP.*?(?:MSCHAPV2|MS-CHAPv2).*?[。.]?\n?", "", text)
    text = re.sub(r"(?m)^.*驗證方式選擇[「『].*?(?:MSCHAPV2|MS-CHAPv2).*?[。.]?\n?", "", text)
    text = text.replace("設定無線網路帳號密碼，並勾選「啟用」VPN 設定（如需校外連線）。", "設定無線網路帳號密碼。VPN 可視個人需求開啟。")
    text = text.replace("設定無線網路帳號密碼，並勾選「啟用」VPN 設定（如需校外連線）", "設定無線網路帳號密碼。VPN 可視個人需求開啟")
    text = re.sub(
        r"若使用 eduroam，需先在裝置 Wi-Fi 設定中完成 802\.1X \+ PEAP 認證設定（安全類型選 PEAP、驗證方式選 MSCHAPV2），設定一次後每次會自動連線（802\.1X 認證）。",
        "若使用 eduroam，需先在裝置 Wi-Fi 設定中點選 eduroam 連線並輸入無線網路帳號密碼，設定一次後每次到該網域附近時會自動連線。",
        text,
    )
    return text


def normalize_vpn_download_links(text: str) -> str:
    return text.replace(OLD_VPN_DOWNLOAD_URL, VPN_DOWNLOAD_URL)

def normalize_vpn_truncated_answer(text: str, question: str = "") -> str:
    if not is_vpn_related(question or text):
        return text

    if "For details:" in text and "https://net.nthu.edu.tw/netsys/en:" in text:
        return text

    has_reference_url = all(url in text for url in VPN_REFERENCE_URLS)
    if has_reference_url:
        return text

    help_block = (
        "**尋求幫助**\n"
        "若申請或連線時遇到問題，請向無線網路服務信箱 wlan@cc.nthu.edu.tw "
        "提供裝置系統、VPN 軟體名稱、帳號格式、錯誤訊息與相關截圖，以便技術人員協助。"
    )
    reference_block = "詳細可參考：\n" + "\n".join(VPN_REFERENCE_URLS)

    if "**尋求幫助**" in text:
        text = text.split("**尋求幫助**", 1)[0].rstrip() + "\n\n" + help_block
    elif "尋求幫助" in text:
        text = text.split("尋求幫助", 1)[0].rstrip() + "\n\n" + help_block

    if "詳細可參考" in text:
        text = re.split(r"詳細可參考[:：]?", text, maxsplit=1)[0].rstrip()

    return text.rstrip() + "\n\n" + reference_block


def normalize_contact_details(text: str, question: str = "") -> str:
    """Enforce support-address routing and remove placeholder contacts."""
    text = re.sub(r"(?m)^.*待定.*(?:\n|$)", "", text)
    dorm_support = any(term in question for term in ("宿網", "宿舍網路", "宿舍有線", "宿舍網路孔", "網路孔")) or any(
        term in question.lower() for term in ("dormnet", "dormitory network", "dorm network", "network wall port")
    )
    wireless_or_vpn_support = is_wireless_related(question) or is_vpn_related(question)
    # Multi-service questions may intentionally include both WLAN and DormNet contacts.
    # In that case keep the answer-specific addresses instead of globally rewriting them.
    if dorm_support and not wireless_or_vpn_support:
        text = text.replace("wlan@cc.nthu.edu.tw", "dorms@cc.nthu.edu.tw")
    elif wireless_or_vpn_support and not dorm_support:
        text = text.replace("dorms@cc.nthu.edu.tw", "wlan@cc.nthu.edu.tw")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def remove_email_help_section(text: str, question: str = "") -> str:
    if not is_email_related(question) or is_dorm_related(question) or is_wireless_related(question) or is_vpn_related(question):
        return text
    text = re.sub(
        r"(?ms)\n*\*\*尋求幫助\*\*.*?(?=\n\*\*[^\n]+\*\*|\n詳細可參考[:：]?|$)",
        "",
        text,
    )
    text = re.sub(r"(?m)^.*(?:wlan|dorms)@cc\.nthu\.edu\.tw.*(?:\n|$)", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clean_answer(text: str, question: str = "") -> str:
    text = re.sub(r".*</think>", "", text, flags=re.DOTALL)
    text = text.replace("Thinking Process:", "")
    text = re.sub(r"(?m)^\s*[-*•]\s+", "", text)
    text = remove_source_phrases(text)
    text = normalize_account_and_ccxp_steps(text, question=question)
    text = normalize_student_mailbox_format(text)
    text = re.sub(r"(Web-based 認證)（適合[^）]*）", r"\1", text)
    text = re.sub(r"(802\.1X \+ PEAP 認證)（適合[^）]*）", r"\1", text)
    text = clean_outdated_time_info(text)
    text = re.sub(r'(?m)^\s*\d+\.\s*若申請頁面顯示[「"].*(?:\n|$)', "", text)
    text = re.sub(r'(?m)^\s*若申請頁面顯示[「"].*(?:\n|$)', "", text)
    text = text.replace("這種方式適合連線名稱為", "對應的 Wi-Fi 名稱是")
    text = text.replace("這種方式適合連線名稱", "對應的 Wi-Fi 名稱")
    text = text.replace("在手機或電腦的 Wi-Fi 設定裡", "在裝置的 Wi-Fi 設定裡")
    text = text.replace("在手機或電腦的 Wi-Fi 設定中", "在裝置的 Wi-Fi 設定中")
    text = text.replace("無線網路服務信箱提供", "無線網路服務信箱 wlan@cc.nthu.edu.tw 提供")
    text = text.replace("無線網路服務信箱提供以下資訊", "無線網路服務信箱 wlan@cc.nthu.edu.tw 提供以下資訊")
    text = normalize_dorm_config_answer(text, question=question)
    text = normalize_wireless_auth_labels(text, question=question)
    text = normalize_vpn_download_links(text)
    text = normalize_vpn_truncated_answer(text, question=question)
    text = normalize_contact_details(text, question=question)
    text = remove_email_help_section(text, question=question)
    text = replace_broken_nthu_urls(text, question=question)
    text = limit_reference_urls(text, question=question)
    text = ensure_reference_urls(text, question=question)
    text = bold_markdown_headings(text)
    return text.strip()
