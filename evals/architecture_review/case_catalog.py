from __future__ import annotations

from typing import Any


ANSWER_MARKERS = {
    "campus_wifi": ["Wi-Fi", "WiFi", "無線", "wireless", "SSID", "nthu"],
    "dorm_network": ["宿網", "宿舍", "DormNet", "dorm", "ethernet"],
    "vpn": ["VPN", "vpn"],
    "email": ["信箱", "email", "mail", "gapp", "GAPP"],
}


def _turn(
    user: str,
    language: str,
    topic: str,
    intent: str,
    *,
    relation: str = "new_topic",
    reference_status: str = "none",
    referenced_turn_ids: list[int] | None = None,
    entities: dict[str, str] | None = None,
    answer_forbids: list[str] | None = None,
    history_excludes: list[int] | None = None,
    must_clarify: bool = False,
) -> dict[str, Any]:
    return {
        "user": user,
        "language": language,
        "tags": ["multi_turn"],
        "expected": {
            "topic": topic,
            "intent": intent,
            "entities": entities or {},
            "relation": relation,
            "reference_status": reference_status,
            "referenced_turn_ids": referenced_turn_ids or [],
            "answer_contains_any": ANSWER_MARKERS.get(topic, []),
            "answer_forbids": answer_forbids or [],
            "relevant_history_excludes": history_excludes or [],
            "allowed_retrieval_topics": (
                [topic] if topic not in {"unknown", "account"} else []
            ),
            "must_clarify": must_clarify,
            "must_refuse": False,
        },
    }


TOPIC_SWITCHES = [
    ("zh-Hant", "校園 Wi-Fi 帳號怎麼申請？", "campus_wifi", "application", "先不管那個，宿網一直斷線怎麼辦？", "dorm_network", "troubleshooting", "Wi-Fi 申請"),
    ("en", "How do I register DormNet?", "dorm_network", "application", "Separate issue: eduroam keeps rejecting my login.", "campus_wifi", "troubleshooting", "DormNet application"),
    ("zh-Hant", "清大 VPN 要怎麼設定？", "vpn", "configuration", "另外，學生信箱要去哪申請？", "email", "application", "VPN"),
    ("en", "Where can I request a GAPP mailbox?", "email", "application", "Now my campus Wi-Fi has no internet.", "campus_wifi", "troubleshooting", "mailbox"),
    ("zh-Hant", "宿網 IP 要怎麼設？", "dorm_network", "configuration", "人在家要連校內資料庫，是不是用 VPN？", "vpn", "configuration", "宿網 IP"),
    ("en", "Does Delta Hall have Wi-Fi?", "campus_wifi", "lookup", "Different question: how do I activate my dorm room port?", "dorm_network", "application", "Delta Hall"),
    ("zh-Hant", "宿網狀態去哪查？", "dorm_network", "lookup", "Google Workspace 帳號怎麼申請？", "email", "application", "宿網狀態"),
    ("en", "nthupeap keeps dropping.", "campus_wifi", "troubleshooting", "Forget that for now—how do I set up NTHU VPN?", "vpn", "configuration", "nthupeap"),
]


INTENT_SWITCHES = [
    ("zh-Hant", "我要怎麼申請宿網？", "dorm_network", "application", "辦完之後 IP 要怎麼設定？", "configuration"),
    ("en", "How do I apply for campus Wi-Fi?", "campus_wifi", "application", "But now it keeps disconnecting.", "troubleshooting"),
    ("zh-Hant", "宿網一直斷線怎麼辦？", "dorm_network", "troubleshooting", "那正確的 IPv4 要怎麼設？", "configuration"),
    ("en", "Where can I check my DormNet status?", "dorm_network", "lookup", "I actually need to register it first.", "application"),
    ("zh-Hant", "清大 VPN 要怎麼安裝？", "vpn", "configuration", "可是裝好後一直連線失敗。", "troubleshooting"),
    ("en", "How do I configure nthupeap?", "campus_wifi", "configuration", "Where do I apply for the account first?", "application"),
    ("zh-Hant", "學生信箱帳號如何申請？", "email", "application", "但現在登入一直失敗。", "troubleshooting"),
    ("en", "DormNet is extremely slow.", "dorm_network", "troubleshooting", "After it is fixed, where can I check the assigned IP?", "lookup"),
]


LOCATION_CHAINS = [
    (
        _turn("人社院有校園 Wi-Fi 嗎？", "zh-Hant", "campus_wifi", "lookup", entities={"location": "人文社會學院"}),
        _turn("那體育館呢？", "zh-Hant", "campus_wifi", "lookup", relation="follow_up", reference_status="resolved", referenced_turn_ids=[1], entities={"location": "體育館"}, answer_forbids=["人文社會學院"]),
    ),
    (
        _turn("Does Delta Hall have campus wireless?", "en", "campus_wifi", "lookup"),
        _turn("What about the Main Library?", "en", "campus_wifi", "lookup", relation="follow_up", reference_status="resolved", referenced_turn_ids=[1], answer_forbids=["Delta Hall"]),
    ),
    (
        _turn("總圖能連 Wi-Fi 嗎？", "zh-Hant", "campus_wifi", "lookup", entities={"location": "總圖書館"}),
        _turn("台積館咧？", "zh-Hant", "campus_wifi", "lookup", relation="follow_up", reference_status="resolved", referenced_turn_ids=[1], entities={"location": "台積館"}, answer_forbids=["總圖書館"]),
        _turn("那成功湖附近呢？", "zh-Hant", "campus_wifi", "lookup", relation="follow_up", reference_status="resolved", referenced_turn_ids=[2], entities={"location": "成功湖"}, answer_forbids=["台積館"]),
    ),
    (
        _turn("Is Wi-Fi available in the Physics Building?", "en", "campus_wifi", "lookup"),
        _turn("And the gym?", "en", "campus_wifi", "lookup", relation="follow_up", reference_status="resolved", referenced_turn_ids=[1], answer_forbids=["Physics Building"]),
        _turn("How about General Building IV?", "en", "campus_wifi", "lookup", relation="follow_up", reference_status="resolved", referenced_turn_ids=[2], answer_forbids=["gym"]),
    ),
    (
        _turn("風雲樓有無線網路嗎？", "zh-Hant", "campus_wifi", "lookup", entities={"location": "風雲樓"}),
        _turn("水木呢？", "zh-Hant", "campus_wifi", "lookup", relation="follow_up", reference_status="resolved", referenced_turn_ids=[1], entities={"location": "水木生活中心"}, answer_forbids=["風雲樓"]),
    ),
]


BACKWARD_REFERENCES = [
    ("zh-Hant", "校園 Wi-Fi 帳號去哪申請？", "campus_wifi", "application", "宿網 IPv4 怎麼設？", "dorm_network", "configuration", "回到第一個問題，申請入口在哪？", "IPv4"),
    ("en", "How do I configure NTHU VPN?", "vpn", "configuration", "Where do I apply for student email?", "email", "application", "Back to the first question: which server do I enter?", "student email"),
    ("zh-Hant", "宿網一直斷線。", "dorm_network", "troubleshooting", "體育館有 Wi-Fi 嗎？", "campus_wifi", "lookup", "第二個問題先放著，回到第一題怎麼排除？", "體育館"),
    ("en", "nthupeap will not authenticate.", "campus_wifi", "troubleshooting", "How can I register DormNet?", "dorm_network", "application", "For the first issue, what should I check next?", "DormNet"),
    ("zh-Hant", "GAPP 信箱要怎麼申請？", "email", "application", "VPN 在家怎麼用？", "vpn", "configuration", "回頭看第一個問題，帳號在哪裡開？", "VPN"),
]


CREDENTIAL_REFERENCES = [
    ("zh-Hant", "校園 Wi-Fi 要去哪申請？", "campus_wifi", "application", "那帳號密碼是哪一組？", "宿網"),
    ("en", "How do I register DormNet?", "dorm_network", "application", "Does it use the same password as Wi-Fi?", "campus wireless"),
    ("zh-Hant", "nthupeap 認證一直失敗。", "campus_wifi", "troubleshooting", "我是問無線帳密忘記了要去哪改。", "宿網"),
    ("en", "DormNet says unidentified network.", "dorm_network", "troubleshooting", "What account should I use for that?", "campus wireless"),
]


UNRESOLVED_REFERENCES = [
    ("zh-Hant", "宿網怎麼申請？", "dorm_network", "application", "回到第五個問題。"),
    ("en", "How do I set up campus Wi-Fi?", "campus_wifi", "configuration", "Go back to the fourth question."),
]


DISCOURSE_OVERRIDES = [
    ("zh-Hant", "宿網怎麼申請？", "dorm_network", "application", "先不管宿網，校園 Wi-Fi 一直斷線。", "campus_wifi", "troubleshooting", "宿網申請"),
    ("en", "Campus Wi-Fi is slow.", "campus_wifi", "troubleshooting", "Set that aside; I need to apply for DormNet.", "dorm_network", "application", "campus Wi-Fi is slow"),
    ("zh-Hant", "VPN 要怎麼裝？", "vpn", "configuration", "不用管 VPN 了，我是要查宿網狀態。", "dorm_network", "lookup", "VPN"),
]


def build_adversarial_cases() -> list[dict[str, Any]]:
    categorized: list[tuple[str, list[dict[str, Any]]]] = []
    for lang, u1, t1, i1, u2, t2, i2, forbidden in TOPIC_SWITCHES:
        categorized.append(("topic_switch", [
            _turn(u1, lang, t1, i1),
            _turn(u2, lang, t2, i2, history_excludes=[1], answer_forbids=[forbidden]),
        ]))
    for lang, u1, topic, i1, u2, i2 in INTENT_SWITCHES:
        categorized.append(("intent_switch", [
            _turn(u1, lang, topic, i1),
            _turn(u2, lang, topic, i2, relation="intent_switch", history_excludes=[1]),
        ]))
    categorized.extend(("location_ellipsis", list(script)) for script in LOCATION_CHAINS)
    for lang, u1, t1, i1, u2, t2, i2, u3, forbidden in BACKWARD_REFERENCES:
        categorized.append(("backward_reference", [
            _turn(u1, lang, t1, i1),
            _turn(u2, lang, t2, i2),
            _turn(u3, lang, t1, i1, relation="follow_up", reference_status="resolved", referenced_turn_ids=[1], history_excludes=[2], answer_forbids=[forbidden]),
        ]))
    for lang, u1, topic, intent, u2, forbidden in CREDENTIAL_REFERENCES:
        categorized.append(("credential_reference", [
            _turn(u1, lang, topic, intent),
            _turn(u2, lang, topic, intent, relation="follow_up", reference_status="resolved", referenced_turn_ids=[1], answer_forbids=[forbidden]),
        ]))
    for lang, u1, topic, intent, u2 in UNRESOLVED_REFERENCES:
        categorized.append(("unresolved_reference", [
            _turn(u1, lang, topic, intent),
            _turn(u2, lang, "unknown", "unknown", reference_status="unresolved", must_clarify=True),
        ]))
    for lang, u1, t1, i1, u2, t2, i2, forbidden in DISCOURSE_OVERRIDES:
        categorized.append(("discourse_override", [
            _turn(u1, lang, t1, i1),
            _turn(u2, lang, t2, i2, history_excludes=[1], answer_forbids=[forbidden]),
        ]))

    cases = [
        {
            "test_id": f"adversarial_{index:03d}",
            "kind": "adversarial_multi_turn",
            "language_group": "mixed_monolingual",
            "tags": ["multi_turn", "adversarial", category],
            "conversation": conversation,
        }
        for index, (category, conversation) in enumerate(categorized, start=1)
    ]
    assert len(cases) == 35, len(cases)
    return cases


BILINGUAL_SPECS = [
    ("校園 Wi-Fi 帳號怎麼申請？", "And which password should I use?", "campus_wifi", "application"),
    ("宿網 IP 要怎麼設定？", "What if it still cannot connect?", "dorm_network", "configuration", "troubleshooting"),
    ("清大 VPN 怎麼裝？", "Where do I download it?", "vpn", "configuration"),
    ("人社院有 Wi-Fi 嗎？", "What about the gym?", "campus_wifi", "lookup"),
    ("學生信箱去哪申請？", "Does it use my school password?", "email", "application"),
    ("宿網怎麼申請？", "How do I check the application status?", "dorm_network", "application", "lookup"),
    ("nthupeap 一直斷線。", "What should I troubleshoot first?", "campus_wifi", "troubleshooting"),
    ("校外怎麼連校內資料庫？", "Which VPN server should I enter?", "vpn", "configuration"),
    ("DormNet 帳號忘了。", "Where can I reset that account?", "dorm_network", "unknown"),
    ("總圖有無線網路嗎？", "And Delta Hall?", "campus_wifi", "lookup"),
    ("How do I register campus wireless?", "那申請入口在哪裡？", "campus_wifi", "application"),
    ("DormNet keeps disconnecting.", "那要先檢查什麼？", "dorm_network", "troubleshooting"),
    ("How do I install NTHU VPN?", "那伺服器位址填什麼？", "vpn", "configuration"),
    ("Does the Main Library have Wi-Fi?", "那體育館呢？", "campus_wifi", "lookup"),
    ("Where can I request student email?", "那密碼跟校務系統一樣嗎？", "email", "application"),
    ("How can I check my DormNet IP?", "那如果被鎖要怎麼辦？", "dorm_network", "lookup", "troubleshooting"),
    ("nthupeap rejects my login.", "那帳號要去哪重設？", "campus_wifi", "troubleshooting"),
    ("I need an NTHU IP from home.", "那 VPN 怎麼連？", "vpn", "configuration"),
    ("Which account does DormNet use?", "那跟無線網路是同一組嗎？", "dorm_network", "unknown"),
    ("Is there Wi-Fi in Delta Hall?", "那人社院呢？", "campus_wifi", "lookup"),
]


def build_bilingual_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index, spec in enumerate(BILINGUAL_SPECS, start=1):
        first, second, topic, first_intent, *second_intent = spec
        first_language = "zh-Hant" if index <= 10 else "en"
        second_language = "en" if first_language == "zh-Hant" else "zh-Hant"
        next_intent = second_intent[0] if second_intent else first_intent
        relation = "intent_switch" if next_intent != first_intent and next_intent != "unknown" else "follow_up"
        cases.append({
            "test_id": f"bilingual_{index:03d}",
            "kind": "bilingual_multi_turn",
            "language_group": "bilingual",
            "tags": ["multi_turn", "bilingual", "language_switch"],
            "conversation": [
                _turn(first, first_language, topic, first_intent),
                _turn(
                    second,
                    second_language,
                    topic,
                    next_intent,
                    relation=relation,
                    reference_status="resolved" if relation == "follow_up" else "none",
                    referenced_turn_ids=[1] if relation == "follow_up" else [],
                    history_excludes=[1] if relation == "intent_switch" else [],
                ),
            ],
        })
    assert len(cases) == 20
    return cases
