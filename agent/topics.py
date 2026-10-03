import re
from collections.abc import Iterable

from agent.semantics import (
    NETWORK_TERMS,
    extract_location_slot,
    is_campus_coverage_list_request,
    is_dorm_cross_test_failure,
    is_dorm_onboarding_request,
    is_remote_campus_access_request,
    is_wifi_network_name_request,
)
from agent.state import Topic


# Adding a service should normally require one entry here, not another routing branch.
TOPIC_KEYWORDS: dict[Topic, tuple[str, ...]] = {
    "campus_wifi": (
        "wi-fi", "wifi", "wireless", "wlan", "無線網路", "校園無線",
        "eduroam", "nthupeap", "nthu-cc", "tanetroaming", "校際漫遊",
    ),
    "dorm_network": (
        "宿網", "宿舍網路", "宿舍網路孔", "dormnet", "dorm network",
        "dormitory network", "residence hall network", "dorm ethernet", "dorm wall port", "dorm port",
    ),
    "vpn": (
        "ssl-vpn", "sslvpn", "vpn", "ivanti secure access", "pulse secure",
    ),
    "email": (
        "電子郵件", "學生信箱", "學校信箱", "信箱", "webmail", "e-mail",
        "email", "mailbox", "google workspace", "gapp",
    ),
    "account": (
        "帳號", "密碼", "account", "username", "password",
    ),
    "unknown": (),
}

SERVICE_TOPICS: tuple[Topic, ...] = (
    "campus_wifi",
    "dorm_network",
    "vpn",
    "email",
)

COMPARISON_TERMS = (
    "差別", "不同", "哪個比較", "vs", "versus", "compare", "difference",
)

CAMPUS_PUBLIC_PLACE_TERMS = (
    "公共區", "公共空間",
    "library", "campus building", "campus hall", "campus center",
)
CAMPUS_PUBLIC_NETWORK_TERMS = (
    "網路", "上網", "wi-fi", "wifi", "無線", "wireless", "連線",
)
EXTERNAL_PLACE_TERMS = (
    "校外", "外校", "其他學校", "別的學校", "台大", "臺大", "交大", "陽明交大",
    "公司", "家裡", "家中", "旅館", "飯店", "店家",
    "off campus", "off-campus", "another university", "hotel", "company",
)
DORM_PLACE_TERMS = (
    "宿舍", "寢室", "宿網", "dorm", "dormitory", "residence hall",
)

ZH_FOLLOW_UP_TERMS = (
    "那", "這個", "那個", "它", "剛剛", "前面", "上述", "第一個", "第二個",
    "第三個", "第1個", "第2個", "第3個", "去哪", "哪裡", "怎麼", "如何",
    "還是", "仍然", "也", "呢", "勒", "咧",
)
EN_FOLLOW_UP_TERMS = (
    "then", "that", "it", "previous", "earlier", "first", "second", "third",
    "where", "how", "still", "also",
)


def normalize_text(text: str) -> str:
    return " ".join(text.lower().replace("—", "-").split())


def _keyword_positions(text: str, keywords: Iterable[str]) -> list[int]:
    return [text.rfind(keyword) for keyword in keywords if keyword in text]


def is_campus_public_network_question(message: str) -> bool:
    """Classify public Wi-Fi only when this turn explicitly mentions networking."""
    normalized = normalize_text(message)
    if any(term in normalized for term in EXTERNAL_PLACE_TERMS):
        return False
    if any(term in normalized for term in DORM_PLACE_TERMS):
        return False
    if is_campus_coverage_list_request(message) or is_wifi_network_name_request(message):
        return True
    has_network_term = any(
        term in normalized
        for term in (*CAMPUS_PUBLIC_NETWORK_TERMS, *NETWORK_TERMS)
    )
    if not has_network_term:
        return False

    has_known_place = any(term in normalized for term in CAMPUS_PUBLIC_PLACE_TERMS)
    return has_known_place or extract_location_slot(message) is not None


def detect_explicit_topic(message: str) -> tuple[Topic, float]:
    """Classify only service words present in the current message."""
    normalized = normalize_text(message)
    if is_remote_campus_access_request(message):
        return "vpn", 0.98
    if is_dorm_cross_test_failure(message) or is_dorm_onboarding_request(message):
        return "dorm_network", 0.98

    hits: list[tuple[int, Topic]] = []

    for topic in SERVICE_TOPICS:
        positions = _keyword_positions(normalized, TOPIC_KEYWORDS[topic])
        if positions:
            hits.append((max(positions), topic))

    # "宿舍 Wi-Fi" describes the dorm service, while a later standalone Wi-Fi mention
    # (for example "Wi-Fi 也連不上") remains campus_wifi.
    if re.search(r"(?:宿舍|寢室|dorm|residence hall).{0,12}(?:wi-?fi|wireless|網路)", normalized):
        hits.append((len(normalized), "dorm_network"))
    if is_campus_public_network_question(message):
        hits.append((len(normalized) + 1, "campus_wifi"))

    distinct_topics = {topic for _, topic in hits}
    if len(distinct_topics) > 1 and any(term in normalized for term in COMPARISON_TERMS):
        return "unknown", 0.65
    if hits:
        _, topic = max(hits, key=lambda item: item[0])
        return topic, 0.99

    account_positions = _keyword_positions(normalized, TOPIC_KEYWORDS["account"])
    if account_positions:
        return "account", 0.9
    return "unknown", 0.25


def has_follow_up_cue(message: str) -> bool:
    normalized = normalize_text(message).strip("？?!！。.")
    if len(normalized) > 80:
        return False
    if any(term in normalized for term in ZH_FOLLOW_UP_TERMS):
        return True
    return any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in EN_FOLLOW_UP_TERMS)


def has_backward_reference_cue(message: str) -> bool:
    """Detect an intentional return to an earlier user question."""
    normalized = re.sub(r"\s+", "", normalize_text(message))
    if any(
        marker in normalized
        for marker in (
            "先不管", "不用管", "擺一邊", "放一邊", "先略過", "先跳過",
            "先不談", "先不講", "先不說", "先不聊", "先不提",
            "先放著", "先擱著", "setaside", "nevermind",
        )
    ):
        return False
    return any(
        marker in normalized
        for marker in (
            "回到", "回頭", "先回", "再回", "前面", "剛才", "剛剛", "上一題",
            "上個問題", "那一題", "那題", "那個問題", "原本那題", "一開始那題",
            "goback", "backto", "earlierquestion", "previousquestion", "thequestionbefore",
        )
    )


def ordinal_reference_index(message: str) -> int | None:
    normalized = re.sub(r"\s+", "", normalize_text(message))
    ordinal_patterns = (
        (1, ("第一個", "第1個", "第一項", "第1項", "第一題", "第1題", "第一個問題", "最前面那題", "thefirst", "firstone", "firstquestion")),
        (2, ("第二個", "第2個", "第二項", "第2項", "第二題", "第2題", "第二個問題", "thesecond", "secondone", "secondquestion")),
        (3, ("第三個", "第3個", "第三項", "第3項", "第三題", "第3題", "第三個問題", "thethird", "thirdone", "thirdquestion")),
        (4, ("第四個", "第4個", "第四項", "第4項", "第四題", "第4題", "第四個問題", "thefourth", "fourthone", "fourthquestion")),
        (5, ("第五個", "第5個", "第五項", "第5項", "第五題", "第5題", "第五個問題", "thefifth", "fifthone", "fifthquestion")),
    )
    for index, patterns in ordinal_patterns:
        if any(pattern in normalized for pattern in patterns):
            return index
    return None


def focus_message_on_topic(message: str, topic: Topic) -> str:
    """Drop a dismissed earlier-service clause when a later clause names the active topic."""
    if topic in {"unknown", "account"}:
        return message
    parts = [part.strip() for part in re.split(r"[，,；;。\n]+", message) if part.strip()]
    if len(parts) < 2:
        return message

    matching_indexes = [
        index
        for index, part in enumerate(parts)
        if detect_explicit_topic(part)[0] == topic
    ]
    if not matching_indexes:
        return message
    last_match = matching_indexes[-1]
    earlier_topics = {
        detect_explicit_topic(part)[0]
        for part in parts[:last_match]
    } - {"unknown", "account", topic}
    if not earlier_topics:
        return message
    return "，".join(parts[last_match:])


def ensure_topic_in_query(message: str, topic: Topic) -> str:
    """Make a context-derived service explicit without reintroducing old turn text."""
    if topic not in SERVICE_TOPICS:
        return message
    normalized = normalize_text(message)
    if any(keyword in normalized for keyword in TOPIC_KEYWORDS[topic]):
        return message
    is_english = (
        not any("\u4e00" <= char <= "\u9fff" for char in message)
        and any(char.isascii() and char.isalpha() for char in message)
    )
    labels = {
        "dorm_network": ("DormNet", "宿網"),
        "campus_wifi": ("NTHU campus Wi-Fi", "校園 Wi-Fi"),
        "vpn": ("NTHU VPN", "清大 VPN"),
        "email": ("NTHU email", "清大信箱"),
    }
    english_label, chinese_label = labels[topic]
    label = english_label if is_english else chinese_label
    return f"{label}：{message}"
