import re

from agent.followups import classify_followup_type
from agent.semantics import (
    is_account_scope_comparison_request,
    is_campus_coverage_list_request,
    is_dorm_cross_test_failure,
    is_dorm_onboarding_request,
    is_location_availability_ellipsis,
    is_network_availability_request,
    is_remote_campus_access_request,
    is_wifi_network_name_request,
)
from agent.state import Intent


INTENT_MARKERS: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    (
        "troubleshooting",
        (
            "連不上", "連不到", "上不了網", "不能用", "無法使用", "無法連線",
            "登入不了", "開不起來", "登不進", "認證失敗", "連線失敗", "一直斷", "斷線",
            "不穩", "很慢", "超慢", "很卡", "卡住", "跑不動", "掛了", "死掉",
            "沒反應", "怪怪", "故障", "異常", "錯誤", "失敗", "打不開", "開不了", "開不出來", "載不出來", "載不動", "動不了", "轉圈", "轉不出來",
            "不能上網", "沒網路", "沒有網路", "取得不到", "不跳", "掛惹",
            "被禁用", "網路爛", "網路孔壞", "壞掉",
            "not working", "fails", "failing", "keeps failing", "won't connect", "will not connect", "doesn't work", "does not work", "cannot connect",
            "can't connect", "cant connect", "failed", "failure", "unstable", "slow",
            "no internet", "zero internet", "nothing loads", "stopped working",
        ),
    ),
    (
        "application",
        (
            "申請", "申辦", "辦理", "開通", "重辦", "重新辦", "重新申請", "註冊",
            "啟用帳號", "開帳號", "辦帳號", "辦宿網", "去哪辦", "去哪裡辦", "哪裡辦", "要去哪辦",
            "想辦", "帳號怎麼開", "申請入口", "apply", "application", "register",
            "registration", "sign up", "signup", "reapply", "activate account",
        ),
    ),
    (
        "lookup",
        (
            "哪些", "清單", "查詢", "哪裡查", "去哪查", "查狀態", "看狀態",
            "狀態如何", "有哪幾個", "有什麼", "是多少", "忘記 ip", "覆蓋", "ssid",
            "lookup", "list", "check status", "where can i check",
        ),
    ),
    (
        "configuration",
        (
            "設定", "安裝", "下載", "怎麼裝", "如何裝", "怎麼用", "如何用", "怎麼連", "如何連",
            "使用方式", "登入方式", "連線方式", "要填什麼", "怎麼登入", "怎麼設",
            "如何設", "填哪", "怎麼接", "tcp/ip", "ipv4", "wan",
            "setup", "set up", "how do i log in", "how can i log in", "configure", "configuration", "install", "download",
            "how to use", "how do i use", "how to connect", "how do i connect",
            "static ip", "tcp/ip", "ipv4 values", "wan fields",
        ),
    ),
    (
        "general",
        (
            "是什麼", "有什麼差別", "差別", "比較", "介紹", "用途", "可以做什麼",
            "what is", "difference", "compare", "overview",
        ),
    ),
)


INTENT_PATTERNS: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    (
        "troubleshooting",
        (
            r"\b(?:keeps?\s+)?(?:drop(?:ping|s)?|disconnect(?:ing|s|ed)?|reject(?:s|ed|ing)?|laggy|crawling|dead|died|down|broken|disabled|unidentified)\b",
            r"\b(?:won't|will not|can't|cannot).{0,24}(?:authenticate|load|get online|get an? ip|connect|work)\b",
        ),
    ),
    (
        "application",
        (
            r"\b(?:where|how).{0,32}(?:apply|register|sign\s*up|request|activate|create)\b",
            r"\b(?:need|want).{0,24}(?:account|email address|network access|wired internet)\b",
            r"\bhow do (?:i|residents?|students?).{0,20}(?:get|open).{0,20}(?:dormnet|mailbox|email|account)\b",
            r"\bopen (?:an? )?(?:nthu|university|school|student).{0,12}(?:mailbox|email|account)\b",
            r"(?:帳號|帳密|宿網|信箱)(?:要|該|可以|能)?(?:怎麼|如何)(?:開|辦|申請|啟用)",
            r"(?:帳號|帳密|宿網|信箱).{0,4}(?:去哪|哪裡)(?:開|辦|申請)",
        ),
    ),
    (
        "lookup",
        (
            r"\b(?:check|retrieve|forgot|find).{0,28}(?:status|assigned .{0,8}ip|dormnet ip)\b",
            r"\b(?:status|outage|coverage|availability|available)\b",
            r"\b(?:does|is there|can i).{0,48}(?:wi-?fi|wireless|internet)\b",
            r"\b(?:wi-?fi|wireless)\s+(?:in|at|around|near)\b",
            r"\bwhere.{0,32}(?:check|find)\b",
            r"(?:有沒有|有|是否有).{0,6}(?:無線|wi-?fi)",
            r"(?:無線|wi-?fi).{0,8}(?:收得到|可用|覆蓋)",
        ),
    ),
    (
        "configuration",
        (
            r"\bsetup after application\b",
            r"\b(?:which|what).{0,18}server\b",
            r"\b(?:router|ethernet).{0,28}(?:fields?|settings?|setup|configure|wire|attach)\b",
            r"\b(?:off[- ]campus|from home|apartment|traveling|company office|off site).{0,64}(?:campus|nthu|school|internal)\b",
            r"\b(?:remote access|school-network access)\b",
            r"(?:校外|在家|家裡|公司|出國).{0,28}(?:校內|學校|internal|campus ?ip)",
        ),
    ),
)


INTENT_TIE_PRIORITY: dict[Intent, int] = {
    "troubleshooting": 5,
    "application": 4,
    "configuration": 3,
    "lookup": 2,
    "general": 1,
    "comparison": 0,
    "unknown": 0,
}

CONTEXTUAL_PREFIXES = (
    "那", "這", "它", "所以", "可是", "但是", "但", "啊", "欸", "誒",
    "不然", "然後", "還有", "順便", "what about", "how about",
    "and if", "but now", "then", "so ",
)
CONTEXTUAL_QUALIFIERS = (
    "換宿", "換寢室", "換了寢室", "換房間", "換了房間", "搬宿舍", "搬寢室", "搬房間", "新生",
    "已經辦", "辦完", "申請完", "弄好了", "換手機", "換電腦", "另一台",
    "moved dorm", "changed rooms", "new student", "already applied",
)


def normalize_intent_text(text: str) -> str:
    return " ".join(text.lower().replace("’", "'").split())


def _explicit_intent_evidence(normalized: str) -> Intent:
    compact = re.sub(r"\s+", "", normalized)
    evidence: list[tuple[int, int, int, Intent]] = []

    for intent, markers in INTENT_MARKERS:
        for marker in markers:
            compact_marker = marker.replace(" ", "")
            position = max(normalized.rfind(marker), compact.rfind(compact_marker))
            if position >= 0:
                evidence.append((
                    position + len(compact_marker),
                    len(compact_marker),
                    INTENT_TIE_PRIORITY[intent],
                    intent,
                ))

    for intent, patterns in INTENT_PATTERNS:
        for pattern in patterns:
            for match in re.finditer(pattern, normalized):
                evidence.append((
                    match.end(),
                    match.end() - match.start(),
                    INTENT_TIE_PRIORITY[intent],
                    intent,
                ))

    if not evidence:
        return "unknown"
    return max(evidence, key=lambda item: item[:3])[3]


def detect_explicit_intent(message: str) -> Intent:
    if is_account_scope_comparison_request(message):
        return "comparison"
    if is_dorm_cross_test_failure(message):
        return "troubleshooting"
    if is_dorm_onboarding_request(message):
        return "application"

    normalized = normalize_intent_text(message)
    if re.search(
        r"\b(?:fails?|failing|won't|will not|cannot|can't|doesn't|does not)\b",
        normalized,
    ):
        return "troubleshooting"
    explicit = _explicit_intent_evidence(normalized)
    if is_network_availability_request(message) and explicit == "troubleshooting":
        return "lookup"
    if explicit != "unknown":
        return explicit
    if is_campus_coverage_list_request(message) or is_wifi_network_name_request(message):
        return "lookup"
    if is_network_availability_request(message):
        return "lookup"
    if is_remote_campus_access_request(message):
        return "configuration"
    return "unknown"


def is_context_dependent_followup(message: str) -> bool:
    if classify_followup_type(message, has_history=True) != "new_question":
        return True
    if is_location_availability_ellipsis(message):
        return True
    normalized = normalize_intent_text(message).strip("？?!！。.")
    compact = re.sub(r"\s+", "", normalized)
    if len(compact) > 100:
        return False
    if normalized.startswith(CONTEXTUAL_PREFIXES):
        return True
    if any(marker.replace(" ", "") in compact for marker in CONTEXTUAL_QUALIFIERS):
        return True
    return compact.endswith(("呢", "咧", "勒", "怎么办", "怎麼辦")) and len(compact) <= 28
