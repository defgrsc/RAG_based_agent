from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


OUTPUT_PATH = Path(__file__).with_name("generated_cases.json")


def items(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()]


def expected_turn(
    user: str,
    language: str,
    topic: str,
    intent: str,
    *tags: str,
    entities: dict[str, str] | None = None,
    relation: str = "new_topic",
    reference_status: str = "none",
    referenced_turn_ids: list[int] | None = None,
    answer_any: list[str] | None = None,
    answer_forbids: list[str] | None = None,
    history_excludes: list[int] | None = None,
    allowed_retrieval_topics: list[str] | None = None,
    must_clarify: bool = False,
    must_refuse: bool = False,
) -> dict[str, Any]:
    return {
        "user": user,
        "language": language,
        "tags": list(tags),
        "expected": {
            "topic": topic,
            "intent": intent,
            "entities": entities or {},
            "relation": relation,
            "reference_status": reference_status,
            "referenced_turn_ids": referenced_turn_ids or [],
            "answer_contains_any": answer_any or [],
            "answer_forbids": answer_forbids or [],
            "relevant_history_excludes": history_excludes or [],
            "allowed_retrieval_topics": allowed_retrieval_topics or (
                [topic] if topic not in {"unknown", "account"} else []
            ),
            "must_clarify": must_clarify,
            "must_refuse": must_refuse,
        },
    }


ZH_GROUPS = [
    ("campus_wifi", "application", "application", items("Wi-Fi 帳號怎麼申請|校園無線要去哪辦|想開通學校 wifi|無線網路帳號申辦流程？|欸學校 WiFi 帳密要怎麼辦啊|第一次用 nthupeap，要先去哪註冊|eduroam 的清大帳號怎麼開|wify 帳號要去哪申請")),
    ("campus_wifi", "troubleshooting", "troubleshooting", items("wifi掛了怎辦|學校那個 Wi-Fi 一直斷欸|nthu-cc 連上但不能上網|eduroam 認證一直失敗|nthupeap 怎麼都登不進去|校園無線超慢，是壞了嗎|WiFi 訊號滿格但網頁載不動|連學校 wifi 一直轉圈圈|無線網路取得不到 IP|欸為啥 nthu-cc 登入頁死都不跳|wifi 剛剛能用現在掛惹|campus wifi 怪怪的會一直掉")),
    ("campus_wifi", "lookup", "coverage", items("人社有網路嗎|噢噢那人社院有網路嗎|台達勒，有 Wi-Fi 嗎|綜四有沒有無線|體育館有網路嗎|欸所以水木勒，有 wifi 嗎|總圖能上網嗎|風雲樓有沒有學校 Wi-Fi|小吃部 wifi 收得到嗎|教育館有無線網路嗎|物理館能連校園網路嗎|醫輔那邊有 Wi-Fi 嗎|旺宏館有網路嗎|台積館能不能上網|成功湖附近有校園 wifi 嗎|操場有無線嗎|所以化學館到底有沒有網路|請問綜合四館的 Wi-Fi 覆蓋狀況")),
    ("campus_wifi", "unknown", "credentials", items("校園 Wi-Fi 帳密是什麼|nthupeap 密碼填哪組|我是問 wifi 的帳號密碼啦|eduroam username 要打什麼|學校無線跟校務系統是同一組密碼嗎|nthu-cc 要用哪個 account|無線帳密忘了要去哪改|wifi 密碼改完多久生效")),
    ("dorm_network", "application", "application", items("我要怎麼申請宿網|宿舍網路去哪辦|欸新生住宿舍那個網路怎麼開|宿網怎申請|要住新齋，網路要先註冊嗎|第一次住校，DormNet 要去哪 sign up|學生宿舍有線網路如何申辦|想辦宿網帳號|宿舍房間的網路怎麼開通|DormNet application 在哪裡")),
    ("dorm_network", "troubleshooting", "troubleshooting", items("宿網最近超卡|DormNet 連不上怎麼辦|宿舍網路突然掛了|我房間網路一直斷|儒齋網路爛到不能用|宿網昨天好好的今天沒網路|網路線插宿舍孔但上不了網|宿網 IP 被禁用怎麼處理|宿舍 ethernet 顯示無法辨識|室友也連不上同一個網路孔|宿網設定完還是跑不動|宿舍網路孔好像壞掉了")),
    ("dorm_network", "configuration", "configuration", items("宿網 IP 要怎麼設|宿舍網路固定 IP 填哪|DormNet TCP/IP setting 怎麼弄|網路線接房間後電腦要設定什麼|分享器怎麼接宿網|router 的 WAN 要填什麼|宿舍有線網路可以用分享器嗎|辦完宿網後下一步怎麼連")),
    ("dorm_network", "lookup", "status", items("宿網狀態去哪查|我忘記宿網 IP 了|DormNet 目前有沒有異常|去哪看宿網有沒有被鎖|宿網申請進度怎麼查|我拿到的 DormNet IP 是多少")),
    ("dorm_network", "unknown", "credentials", items("宿網帳號密碼是哪組|DormNet password 忘了|我是問宿舍網路的帳密|宿網帳號跟 wifi 一樣嗎")),
    ("vpn", "configuration", "semantic_intent", items("VPN 怎麼用|清大 SSLVPN 要怎麼裝|我人在家怎麼連學校裡面的東西|在家要開只有校內 IP 才能看的網站|校外要存取校內資料庫怎辦|出國後想用 NTHU internal services|宿舍外面要怎麼取得 campus IP|Ivanti server 要填什麼|Pulse Secure 怎麼設定清大連線|人在公司但資源限制學校網段")),
    ("email", "application", "application", items("清大學生信箱怎麼申請|GAPP 帳號去哪開|Google Workspace 要怎麼辦|我想申請學校 email|學生 mail account 怎麼註冊|gapp 信箱申辦入口在哪")),
]


EN_GROUPS = [
    ("campus_wifi", "application", "application", items("Where do new students register for campus wireless?|I need a WiFi account for NTHU—how do I get one?|Can I sign up for nthupeap online?|setting up my first campus wireless account|where's the eduroam account application?|Do I have to register before using campus Wi-Fi?|Need access to the school WLAN, account setup?|how can a visiting student apply for NTHU wifi")),
    ("campus_wifi", "troubleshooting", "troubleshooting", items("campus wifi keeps dropping on my phone|nthu-cc says connected but nothing loads|eduroam rejects my login every time|wireless is crawling in class|full WiFi bars, zero internet|can't get an IP address on NTHU wireless|the nthu-cc portal never pops up|my laptop keeps losing campus Wi-Fi|wifi worked this morning and is dead now|nthupeap won't authenticate|campus wireless is super laggy|why does every page spin forever on wifi")),
    ("campus_wifi", "lookup", "coverage", items("Does Delta Hall have Wi-Fi?|wireless coverage in the gym?|Can I get online inside the Humanities and Social Sciences Building?|Is there campus wifi around the track?|Does the Main Library have wireless service?|Wi-Fi availability at Fengyun Building|Any NTHU wireless in the cafeteria?|Can I use campus WiFi in Chemistry Building?|Is the TSMC Building covered?|Does the Physics Building have internet?|wireless at the student activity center|Is there Wi-Fi near Cheng Kung Lake?|Can I connect in General Building IV?|Does the sports complex have campus wireless?|WiFi in EECS Building?|Is wireless available at Shui Mu Life Center?|Which SSIDs are available around campus?|Where on campus can I find NTHU Wi-Fi?")),
    ("campus_wifi", "unknown", "credentials", items("Which password goes into nthupeap?|Is my WiFi login the same as the academic system?|I forgot the campus wireless password|what username should I use for eduroam|Need the account and password for NTHU Wi-Fi|Where can I reset my wireless credentials?|Does nthu-cc use my student portal password?|How long until a changed WiFi password works?")),
    ("dorm_network", "application", "application", items("How do residents get DormNet?|Where is the dorm ethernet registration?|first night in the residence hall—how do I activate wired internet?|Need to sign up for my room's network port|DormNet application steps for a freshman|How can I register dormitory internet?|moving into Xin Zhai, do I apply for network access?|where do I create a dorm network account|I need wired internet in my dorm room|is there a DormNet signup page")),
    ("dorm_network", "troubleshooting", "troubleshooting", items("DormNet has been painfully slow since last night|my dorm ethernet suddenly stopped working|No internet from the wall jack|DormNet disconnects every few minutes|the static IP worked yesterday but not today|my roommate also can't use this port|wired network in Ru Zhai is down|DormNet says unidentified network|I finished setup but still can't get online|could the dorm wall port be broken?|DormNet IP is disabled|ethernet in my room just died")),
    ("dorm_network", "configuration", "configuration", items("How should I enter the DormNet static IP?|Dorm ethernet TCP/IP settings|What goes in the router WAN fields for DormNet?|Can I attach my own router to the dorm port?|I registered; how do I configure my laptop's ethernet?|which IPv4 values do I use for dorm internet|DormNet setup after application|how to wire a router in my residence hall room")),
    ("dorm_network", "lookup", "status", items("Where can I check DormNet status?|I forgot my assigned DormNet IP|How do I see whether my dorm IP is blocked?|Is there a DormNet outage right now?|Where is the dorm network application status page?|How can I retrieve my room's assigned IP?")),
    ("dorm_network", "unknown", "credentials", items("Which credentials does DormNet use?|forgot my dorm network password|I mean the DormNet username, not WiFi|Does dorm internet share the wireless account?")),
    ("vpn", "configuration", "semantic_intent", items("I'm off campus and a journal only accepts campus IPs|How can I reach an internal NTHU server from my apartment?|Need school-network access while traveling|What do I use for campus-only resources from home?|Set up NTHU VPN on a new laptop|Which server goes into Ivanti?|Pulse Secure configuration for Tsing Hua|Remote access to an on-campus database|I'm at a company office but the service requires an NTHU address|How do I appear to be on the campus network from off site?")),
    ("email", "application", "application", items("How do I open an NTHU student mailbox?|Where can I request a GAPP account?|Need a university email address|Google Workspace signup for NTHU students|Is there an application for student mail?|How can I activate my school email?")),
]


LOCATION_EXPECTATIONS = {
    "人社": "人文社會學院", "台達": "台達館", "綜四": "綜合四館",
    "體育館": "體育館", "水木": "水木生活中心", "總圖": "總圖書館",
    "風雲樓": "風雲樓", "小吃部": "小吃部", "教育館": "教育館",
    "物理館": "物理館", "醫輔": "醫輔大樓", "旺宏館": "旺宏館",
    "台積館": "台積館", "成功湖": "成功湖", "操場": "操場",
    "化學館": "化學館", "綜合四館": "綜合四館",
}


ANSWER_MARKERS = {
    "campus_wifi": ["Wi-Fi", "WiFi", "無線", "wireless", "SSID", "nthu"],
    "dorm_network": ["宿網", "宿舍", "DormNet", "dorm", "ethernet"],
    "vpn": ["VPN", "vpn"],
    "email": ["信箱", "email", "mail", "gapp", "GAPP"],
}


def build_monolingual_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for prefix, language, groups in (("zh", "zh-Hant", ZH_GROUPS), ("en", "en", EN_GROUPS)):
        number = 1
        for topic, intent, category, questions in groups:
            for question in questions:
                entities: dict[str, str] = {}
                if language == "zh-Hant" and category == "coverage":
                    for marker, canonical in LOCATION_EXPECTATIONS.items():
                        if marker in question:
                            entities = {"location": canonical}
                            break
                cases.append({
                    "test_id": f"{prefix}_single_{number:03d}",
                    "kind": "single_turn",
                    "language_group": language,
                    "tags": ["single_turn", language, topic, category],
                    "conversation": [expected_turn(
                        question, language, topic, intent, topic, category,
                        entities=entities,
                        answer_any=ANSWER_MARKERS[topic],
                    )],
                })
                number += 1

        edge_cases = (
            items("那個怎麼弄|所以勒|回到第一個問題|剛剛那個去哪裡看|今天午餐吃什麼|清大停車證怎麼辦|台大 Wi-Fi 很慢|我在家 Wi-Fi 很慢")
            if language == "zh-Hant" else
            items("what about that|so now what|go back to my first question|where do I check the thing from before|What's good for lunch?|How do I get a parking permit?|NTU WiFi is slow|My home WiFi is slow")
        )
        for index, question in enumerate(edge_cases):
            clarify = index in {2, 3}
            refuse = index in {4, 5, 6, 7}
            intent = "lookup" if index == 3 else ("troubleshooting" if index >= 6 else "unknown")
            cases.append({
                "test_id": f"{prefix}_single_{number:03d}",
                "kind": "single_turn",
                "language_group": language,
                "tags": ["single_turn", language, "out_of_scope" if refuse else "ambiguous"],
                "conversation": [expected_turn(
                    question, language, "unknown", intent,
                    "out_of_scope" if refuse else "ambiguous",
                    reference_status="unresolved" if clarify else "none",
                    must_clarify=clarify,
                    must_refuse=refuse,
                )],
            })
            number += 1
        assert number - 1 == 110, (prefix, number - 1)
    return cases


def build_dataset() -> dict[str, Any]:
    from evals.architecture_review.case_catalog import (
        build_adversarial_cases,
        build_bilingual_cases,
    )

    cases = [
        *build_monolingual_cases(),
        *build_adversarial_cases(),
        *build_bilingual_cases(),
    ]
    composition = {
        "total_conversations": len(cases),
        "total_turns": sum(len(case["conversation"]) for case in cases),
        "zh_single_turn": sum(case["test_id"].startswith("zh_single_") for case in cases),
        "en_single_turn": sum(case["test_id"].startswith("en_single_") for case in cases),
        "adversarial_multi_turn": sum(case["kind"] == "adversarial_multi_turn" for case in cases),
        "bilingual_multi_turn": sum(case["kind"] == "bilingual_multi_turn" for case in cases),
    }
    assert composition["zh_single_turn"] >= 100
    assert composition["en_single_turn"] >= 100
    assert composition["adversarial_multi_turn"] >= 30
    assert composition["bilingual_multi_turn"] >= 20
    return {
        "version": 1,
        "generated_on": date.today().isoformat(),
        "design_note": "Chinese and English single-turn prompts were authored as separate colloquial sets, not translated row-by-row.",
        "current_intent_taxonomy_note": "coverage/status map to lookup; credentials may map to unknown. The architecture report evaluates this observability gap separately.",
        "composition": composition,
        "cases": cases,
    }


def main() -> None:
    dataset = build_dataset()
    OUTPUT_PATH.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(dataset["composition"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
