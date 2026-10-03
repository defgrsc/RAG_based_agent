import re
import unicodedata
from typing import Any

from campus_locations import match_campus_location_mention
from wireless_coverage import match_coverage_location_mention


OFF_CAMPUS_TERMS = (
    "校外", "不在校內", "家中", "家裡", "在家", "公司", "旅館", "飯店",
    "off campus", "off-campus", "from home", "at home", "outside campus",
)
CAMPUS_RESOURCE_TERMS = (
    "學校網路", "校內網路", "校園網路", "學校內網", "校內網", "內網",
    "校內資源", "校內服務", "校內 ip", "校內ip", "限校內", "僅限校內",
    "nthu network", "school network", "campus network", "internal resource",
    "internal service", "campus ip", "on-campus only", "campus-only",
)
ACCESS_ACTION_TERMS = (
    "連", "連線", "存取", "使用", "登入", "開啟", "進入", "造訪",
    "connect", "access", "use", "login", "log in", "open", "reach",
)
NETWORK_TERMS = (
    "網路", "上網", "wi-fi", "wifi", "無線", "wireless", "network", "internet",
)
CAMPUS_SCOPE_TERMS = (
    "清大", "學校", "校園", "校內", "nthu", "campus", "school",
)
COVERAGE_LIST_CUES = (
    "哪裡", "何處", "哪些地方", "什麼地方", "哪些區域", "where",
    "which location", "which area",
)
SSID_NAME_CUES = (
    "哪一個", "哪個", "哪些", "哪幾個", "名稱", "名字",
    "which", "what network", "network name",
)
AVAILABILITY_TERMS = (
    "有網路嗎", "有沒有網路", "是否有網路", "能上網嗎", "可以上網嗎",
    "有 wifi 嗎", "有wifi嗎", "有沒有 wifi", "有沒有wifi", "是否有 wifi",
    "有 wi-fi 嗎", "有wi-fi嗎", "有無線網路嗎", "有沒有無線網路",
    "是否有無線網路", "能不能上網", "可不可以上網",
    "have wifi", "have wi-fi", "have wireless", "have internet",
    "is wifi available", "is wi-fi available", "network coverage",
)

ACCOUNT_SCOPE_COMPARISON_TERMS = (
    "一樣", "相同", "同一個", "共用", "共同", "只要一個", "只需一個",
    "一個就好", "申請幾個", "申請幾次", "same account", "one account",
    "share an account", "apply once",
)
ACCOUNT_SCOPE_TERMS = (
    "申請", "帳號", "帳戶", "無線", "wi-fi", "wifi", "wireless", "account",
    "apply", "register",
)
ELLIPTICAL_NON_LOCATION_TERMS = {
    "那", "這", "這個", "那個", "它", "帳號", "密碼", "申請", "設定", "網路",
    "無線", "wifi", "wi-fi", "eduroam", "nthupeap", "nthucc", "nthu-cc",
}

CROSS_TEST_TERMS = (
    "交叉測試", "交叉檢查", "換人測試", "換裝置測試",
    "cross test", "cross-test",
)
CROSS_TEST_PEER_TERMS = (
    "室友", "同學", "別人", "其他人", "另一台電腦", "另一個裝置",
    "roommate", "classmate", "another computer", "another device",
)
CROSS_TEST_FAILURE_TERMS = (
    "也沒辦法連", "也不能連", "也連不上", "也無法上網", "也不能上網",
    "同樣不行", "一樣不行", "都不行", "都不能用", "還是不能用",
    "also cannot connect", "also can't connect", "also does not work",
)
DORM_ONBOARDING_TERMS = (
    "剛搬進宿舍", "剛搬入宿舍", "剛住進宿舍", "剛入住宿舍",
    "第一次住宿舍", "新住宿生", "宿舍新生",
    "moved into the dorm", "new dorm resident", "first time in the dorm",
)


def normalize_semantic_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower().replace("’", "'")
    return " ".join(normalized.split())


def has_explicit_network_term(message: str) -> bool:
    normalized = normalize_semantic_text(message)
    compact = normalized.replace(" ", "")
    return any(
        term in normalized or term.replace(" ", "") in compact
        for term in NETWORK_TERMS
    )


def _match_known_location(message: str) -> str | None:
    """Prefer the service-independent campus ontology, then ingested coverage names."""
    return (
        match_campus_location_mention(message)
        or match_coverage_location_mention(message)
    )


def is_location_availability_ellipsis(message: str) -> bool:
    """Detect location + ``有嗎`` syntax; the service must come from context."""
    compact = re.sub(r"\s+", "", normalize_semantic_text(message)).strip("？?!！。.,，")
    return (
        _match_known_location(message) is not None
        and re.search(r"(?:也)?有嗎$", compact) is not None
        and not has_explicit_network_term(message)
    )


def is_campus_coverage_list_request(message: str) -> bool:
    normalized = normalize_semantic_text(message)
    compact = normalized.replace(" ", "")

    def contains_any(terms: tuple[str, ...]) -> bool:
        return any(term in normalized or term.replace(" ", "") in compact for term in terms)

    return (
        contains_any(CAMPUS_SCOPE_TERMS)
        and contains_any(NETWORK_TERMS)
        and contains_any(COVERAGE_LIST_CUES)
    )


def is_wifi_network_name_request(message: str) -> bool:
    normalized = normalize_semantic_text(message)
    compact = normalized.replace(" ", "")
    has_wireless = any(
        term in normalized or term.replace(" ", "") in compact
        for term in ("無線網路", "校園無線", "wi-fi", "wifi", "wireless", "ssid")
    )
    has_name_question = any(
        term in normalized or term.replace(" ", "") in compact
        for term in SSID_NAME_CUES
    )
    return has_wireless and has_name_question


def is_remote_campus_access_request(message: str) -> bool:
    """Require an origin, a campus target, and an access action.

    A location word such as ``在家`` is not enough on its own to infer VPN.
    """
    normalized = normalize_semantic_text(message)
    compact = normalized.replace(" ", "")

    def contains_any(terms: tuple[str, ...]) -> bool:
        return any(term in normalized or term.replace(" ", "") in compact for term in terms)

    return (
        contains_any(OFF_CAMPUS_TERMS)
        and contains_any(CAMPUS_RESOURCE_TERMS)
        and contains_any(ACCESS_ACTION_TERMS)
    )


def is_network_availability_request(message: str) -> bool:
    normalized = normalize_semantic_text(message)
    compact = normalized.replace(" ", "")
    explicit_availability = any(
        term in normalized or term.replace(" ", "") in compact
        for term in AVAILABILITY_TERMS
    )
    return (
        explicit_availability
        or is_location_availability_ellipsis(message)
        or is_campus_coverage_list_request(message)
    )


def is_explicit_network_availability_request(message: str) -> bool:
    """Return true only when this turn itself names network availability."""
    return (
        is_network_availability_request(message)
        and not is_location_availability_ellipsis(message)
    )


def is_account_scope_comparison_request(message: str) -> bool:
    """Detect account/application-scope comparisons without naming locations."""
    normalized = normalize_semantic_text(message)
    compact = normalized.replace(" ", "")

    def contains_any(terms: tuple[str, ...]) -> bool:
        return any(term in normalized or term.replace(" ", "") in compact for term in terms)

    return (
        contains_any(ACCOUNT_SCOPE_COMPARISON_TERMS)
        and contains_any(ACCOUNT_SCOPE_TERMS)
    )


def is_dorm_cross_test_failure(message: str) -> bool:
    normalized = normalize_semantic_text(message)
    compact = normalized.replace(" ", "")

    def contains_any(terms: tuple[str, ...]) -> bool:
        return any(term in normalized or term.replace(" ", "") in compact for term in terms)

    return (
        contains_any(CROSS_TEST_TERMS)
        and contains_any(CROSS_TEST_PEER_TERMS)
        and contains_any(CROSS_TEST_FAILURE_TERMS)
    )


def is_dorm_onboarding_request(message: str) -> bool:
    normalized = normalize_semantic_text(message)
    compact = normalized.replace(" ", "")
    has_onboarding = any(
        term in normalized or term.replace(" ", "") in compact
        for term in DORM_ONBOARDING_TERMS
    )
    has_network = any(
        term in normalized or term.replace(" ", "") in compact
        for term in (*NETWORK_TERMS, "宿網", "宿舍網路", "dormnet")
    )
    return has_onboarding and has_network


def extract_location_slot(message: str) -> str | None:
    """Extract a place using ingested entities before the conservative syntax fallback."""
    compact = re.sub(r"\s+", "", message).strip("？?!！。.,，")
    if not compact:
        return None

    known_location = _match_known_location(message)
    if known_location:
        return known_location

    if is_campus_coverage_list_request(message):
        return None

    building_match = re.search(
        r"([\u4e00-\u9fffA-Za-z0-9·-]{1,16}?(?:大樓|中心|館|院|樓))",
        compact,
    )
    if building_match:
        place = re.sub(r"^.*(?:最近在|目前在|現在在|請問在|想問|問一下|在|於|到|去)", "", building_match.group(1))
        return place or building_match.group(1)

    if is_network_availability_request(message):
        availability_match = re.search(
            r"(?:最近在|目前在|現在在|請問在|想問|問一下|在|於|到|去)?"
            r"([\u4e00-\u9fffA-Za-z0-9·-]{1,16}?)"
            r"(?:有沒有|是否有|有)(?:清大|校園|學校)?(?:網路|無線網路|wi-?fi)",
            compact,
            flags=re.IGNORECASE,
        )
        if availability_match:
            place = availability_match.group(1).strip("那這個此")
            if place not in {"學校", "校園", "清大"}:
                return place

    elliptical_match = re.fullmatch(
        r"([\u4e00-\u9fffA-Za-z0-9·-]{1,16})(?:呢|咧|勒)",
        compact,
        flags=re.IGNORECASE,
    )
    if elliptical_match:
        candidate = elliptical_match.group(1).lower()
        if candidate not in ELLIPTICAL_NON_LOCATION_TERMS:
            return elliptical_match.group(1)
    return None


def extract_semantic_slots(message: str) -> dict[str, str]:
    slots: dict[str, str] = {}
    location = extract_location_slot(message)
    if location:
        slots["location"] = location
        if is_explicit_network_availability_request(message):
            slots["question_focus"] = "network_availability"
    if is_campus_coverage_list_request(message):
        slots["coverage_scope"] = "campus"
        slots["question_focus"] = "coverage_list"
    if is_wifi_network_name_request(message):
        slots["coverage_scope"] = "campus"
        slots["question_focus"] = "ssid_list"
    if is_remote_campus_access_request(message):
        slots["access_origin"] = "off_campus"
        slots["resource_scope"] = "campus_internal"
    normalized = normalize_semantic_text(message)
    if any(term in normalized for term in ("換宿", "換寢室", "換房間", "搬宿舍", "moved dorm", "changed rooms")):
        slots["dorm_transfer"] = "true"
    if is_dorm_cross_test_failure(message):
        slots["troubleshooting_stage"] = "cross_test_failed"
    if is_dorm_onboarding_request(message):
        slots["dorm_onboarding"] = "true"
    if is_account_scope_comparison_request(message):
        slots["question_focus"] = "account_scope_comparison"
        slots["account_scope"] = "single_or_per_location"
    return slots


def merge_semantic_slots(
    referenced_slots: dict[str, str] | None,
    current_slots: dict[str, str] | None,
) -> dict[str, str]:
    """Carry prior slots forward while letting the current turn replace them."""
    return {**(referenced_slots or {}), **(current_slots or {})}


def rewrite_semantic_followup(message: str, state: dict[str, Any]) -> str | None:
    """Complete an elliptical location follow-up from its inherited semantic frame."""
    if state.get("relation") != "follow_up":
        return None
    if state.get("current_intent") == "comparison":
        current_location = state.get("current_slots", {}).get("location")
        referenced_location = state.get("referenced_slots", {}).get("location")
        if current_location and referenced_location:
            has_cjk = any("\u4e00" <= character <= "\u9fff" for character in message)
            if has_cjk:
                return (
                    f"{current_location}與{referenced_location}的校園無線網路"
                    "是否使用同一個帳號，只需要申請一次嗎？"
                )
            return (
                f"Do {current_location} and {referenced_location} use the same "
                "campus Wi-Fi account, requiring only one application?"
            )
    slots = state.get("semantic_slots", {})
    current_slots = state.get("current_slots", {})
    if not current_slots.get("location") or not slots.get("location"):
        return None
    if state.get("current_topic") != "campus_wifi" or state.get("current_intent") != "lookup":
        return None
    if is_network_availability_request(message) and not is_location_availability_ellipsis(message):
        return None

    location = slots["location"]
    has_cjk = any("\u4e00" <= character <= "\u9fff" for character in message)
    if has_cjk:
        if is_location_availability_ellipsis(message):
            return f"{location}有校園無線網路嗎？"
        return f"{location}有哪些校園無線網路可以使用？"
    return f"Does {location} have NTHU Wi-Fi?"
