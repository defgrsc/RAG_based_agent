import time
from typing import Any

import requests

from config import RAG_CONTEXT_CHARS_PER_SOURCE, RAG_CONTEXT_TOTAL_CHARS, RAG_TOP_K
from llm import embed_texts
from qdrant_store import get_active_collection_name, get_chunks_by_url, search_similar
from response_cache import rag_cache, stable_key
from external_reranker import rerank_with_flashrank
from service_errors import QdrantServiceError


DOMAIN_KEYWORDS = {
    "wireless": ("無線", "wifi", "wi-fi", "wireless", "ssid", "nthu-cc", "nthupeap", "eduroam", "校際漫遊", "漫遊", "人社院", "資電館", "小吃部", "風雲樓", "水木生活中心", "醫輔大樓", "梅園", "公共區"),
    "dorm": ("宿舍", "宿網", "學生宿舍", "dorm", "宿舍網路", "分享器", "路由器", "router", "wifi 分享器", "wi-fi 分享器", "tcp/ip", "ip 設定", "連不上", "沒有宿網"),
    "vpn": ("vpn", "ssl vpn", "sslvpn", "twaren", "juniper", "network connect", "下載", "安裝", "設定"),
    "email": ("信箱", "email", "mail", "webmail", "電子郵件", "郵件", "寄信", "收信", "垃圾信", "郵件記錄器", "smtp", "imap", "pop3"),
}

PRIORITY_PAGE_RULES = (
    {
        "question_terms": ("信箱", "email", "mail", "webmail", "電子郵件", "郵件", "寄信", "收信", "垃圾信", "郵件記錄器", "smtp", "imap", "pop3"),
        "intent_terms": ("申請", "設定", "怎麼", "如何", "無法", "不能", "忘記", "密碼", "容量", "轉寄", "垃圾信", "記錄", "查詢"),
        "url_terms": ("mail", "email", "smtp", "webmail", "portal:set_password", "mail_report", "check_mbox"),
        "boost": 1.45,
    },
    {
        "question_terms": ("宿舍網路", "宿網", "宿舍"),
        "intent_terms": ("申請", "怎麼", "如何", "帳號"),
        "url_terms": ("faq:domitory_net_ua_apply", "faq%3adomitory_net_ua_apply"),
        "boost": 1.2,
    },
    {
        "question_terms": ("宿舍網路", "宿網", "宿舍"),
        "intent_terms": ("申請", "怎麼", "如何", "登錄"),
        "url_terms": ("faq:domitory_net_apply", "faq%3adomitory_net_apply"),
        "boost": 1.35,
    },
    {
        "question_terms": ("分享器", "路由器", "router", "wifi 分享器", "wi-fi 分享器"),
        "intent_terms": ("宿舍", "宿網", "可以", "設定", "怎麼", "如何", "連"),
        "url_terms": ("faq:domitory_network_config2", "faq%3adomitory_network_config2"),
        "boost": 1.4,
    },
    {
        "question_terms": ("設定宿舍網路", "宿舍網路的 ip", "ip 設定", "tcp/ip", "設定 ip"),
        "intent_terms": ("設定", "怎麼", "如何"),
        "url_terms": ("faq:domitory_network_config", "faq%3adomitory_network_config"),
        "boost": 1.5,
    },
    {
        "question_terms": ("沒有宿網", "宿網連不上", "宿舍裡為什麼沒有網路", "無法上網", "連不上"),
        "intent_terms": ("為什麼", "怎麼", "如何", "連不上", "沒有"),
        "url_terms": ("faq:domitory_net_useless", "faq%3adomitory_net_useless", "dormnet/"),
        "boost": 1.2,
    },
    {
        "question_terms": ("無線", "wifi", "wi-fi", "校園無線", "校園網路"),
        "intent_terms": ("申請", "怎麼", "如何", "使用"),
        "url_terms": ("wireless:application", "wireless%3aapplication"),
        "boost": 0.9,
    },
    {
        "question_terms": ("無線", "wifi", "wi-fi", "校園無線", "校園網路"),
        "intent_terms": ("申請", "怎麼", "如何", "使用"),
        "url_terms": ("wireless:application:ccxp", "wireless%3aapplication%3accxp"),
        "boost": 1.1,
    },
    {
        "question_terms": ("無線", "wifi", "wi-fi", "校園無線", "校園網路", "eduroam", "nthupeap"),
        "intent_terms": ("使用", "連線", "認證", "怎麼", "如何"),
        "url_terms": ("faq:wlan_auth", "faq%3awlan_auth"),
        "boost": 0.9,
    },
    {
        "question_terms": ("無線", "wifi", "wi-fi", "校園無線", "校園網路"),
        "intent_terms": ("使用", "怎麼", "如何"),
        "url_terms": ("faq:wlan_roaming", "faq%3awlan_roaming"),
        "boost": 1.1,
    },
    {
        "question_terms": ("人社院", "資電館", "小吃部", "風雲樓", "水木生活中心", "水漾餐廳", "餐廳", "醫輔大樓", "遠距教室", "合勤演藝廳", "大草坪", "成功湖畔", "學生活動中心", "圖書館", "物理系", "統計所", "計科所", "數學系", "化學系", "動機系", "工工系", "化工系", "材料系", "醫環系", "工科系", "核工所", "人社", "生科院", "電機系", "資工系", "科管院", "清華學院", "公共區", "館", "院"),
        "intent_terms": ("網路", "上網", "wi-fi", "wifi", "無線", "有網路", "有沒有網路", "哪裡有網路"),
        "url_terms": ("faq:wlan_range", "faq%3awlan_range"),
        "boost": 1.8,
    },
    {
        "question_terms": ("範圍", "哪裡", "哪裡用", "全校", "覆蓋", "涵蓋", "公共區"),
        "intent_terms": ("無線", "wifi", "wi-fi", "校園無線", "校園網路", "可以用"),
        "url_terms": ("faq:wlan_range", "faq%3awlan_range"),
        "boost": 1.4,
    },
    {
        "question_terms": ("無線", "wifi", "wi-fi", "nthu-cc", "nthupeap", "eduroam", "tanetroaming"),
        "intent_terms": ("連不上", "不能用", "無法連線", "登入頁", "取得 ip", "認證失敗"),
        "url_terms": ("faq:wlan_useless", "faq%3awlan_useless"),
        "boost": 1.45,
    },
    {
        "question_terms": ("無線", "wifi", "wi-fi", "校園無線"),
        "intent_terms": ("忘記密碼", "改密碼", "變更密碼", "密碼", "重設"),
        "url_terms": ("wireless:set_passwd", "wireless%3aset_passwd"),
        "boost": 1.45,
    },
    {
        "question_terms": ("無法辨識的網路", "網路介面卡", "網卡", "乙太網路介面卡"),
        "intent_terms": ("宿網", "宿舍", "解決", "怎麼", "如何"),
        "url_terms": ("faq:domitory_network_adapter_reinstall", "faq%3adomitory_network_adapter_reinstall"),
        "boost": 1.35,
    },
    {
        "question_terms": ("狀態", "查詢", "流量", "速度", "埠狀態", "連線狀況"),
        "intent_terms": ("宿網", "宿舍", "怎麼", "如何", "查"),
        "url_terms": ("faq:domitory_net_status", "faq%3adomitory_net_status"),
        "boost": 1.15,
    },
    {
        "question_terms": ("校外", "外校", "別的學校", "漫遊", "校際", "eduroam"),
        "intent_terms": ("使用", "連線", "怎麼", "如何", "帳號格式"),
        "url_terms": ("faq:wlan_roaming", "faq%3awlan_roaming"),
        "boost": 1.2,
    },
    {
        "question_terms": ("vpn", "ssl-vpn", "sslvpn", "校外連", "校外連線", "校內資源", "學校網路"),
        "intent_terms": ("設定", "怎麼", "如何", "連", "連線", "下載", "安裝"),
        "url_terms": ("sslvpn:info", "sslvpn%3ainfo", "sslvpn:sslvpn_setup", "sslvpn%3asslvpn_setup"),
        "boost": 1.8,
    },
)


def retrieve_context(
    question: str,
    limit: int = RAG_TOP_K,
    language: str = "zh-Hant",
    topic: str = "unknown",
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    active_collection = get_active_collection_name()
    cache_key = stable_key(
        {
            "question": question,
            "limit": limit,
            "language": language,
            "topic": topic,
            "metadata_filter": metadata_filter,
            "collection": active_collection,
        }
    )
    cached_results = rag_cache.get(cache_key)
    if cached_results is not None:
        print("RAG Cache Hit: true")
        return cached_results

    query_vector = embed_texts([question])[0]
    retrieval_started = time.perf_counter()
    try:
        priority_chunks = get_priority_chunks(question, language=language)
        effective_limit = max(limit, 7) if priority_chunks else limit
        candidates = search_similar(
            query_vector,
            max(effective_limit * 4, 20),
            metadata_filter=metadata_filter,
        )
        candidates.extend(priority_chunks)
        expanded_candidates = expand_page_chunks(candidates)
    except QdrantServiceError:
        raise
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise QdrantServiceError(
            operation="retrieve",
            cause=exc,
        ) from exc
    finally:
        print(
            f"Retrieval Backend Time: {time.perf_counter() - retrieval_started:.3f}s"
        )

    keyword_ranked = rerank_results(question, expanded_candidates, language=language)

    try:
        results = rerank_with_flashrank(question, keyword_ranked, effective_limit)
    except Exception as exc:
        print(f"External Reranker Skip: {exc}")
        results = keyword_ranked[:effective_limit]

    rag_cache.set(cache_key, results)
    return results


def expand_page_chunks(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded = []
    seen = set()

    for item in results:
        base_score = float(item.get("score") or 0)
        page_chunks = get_chunks_by_url(item.get("url", ""))

        for candidate in [item, *page_chunks]:
            key = candidate.get("point_id") or (candidate.get("url"), candidate.get("chunk_index"))
            if key in seen:
                continue

            candidate = {**candidate}
            candidate["score"] = max(float(candidate.get("score") or 0), base_score - 0.02)
            seen.add(key)
            expanded.append(candidate)

    return expanded


def get_priority_chunks(question: str, language: str = "zh-Hant") -> list[dict[str, Any]]:
    normalized_question = question.lower()
    urls = []

    if language == "en":
        urls.append("https://net.nthu.edu.tw/netsys/en:faq")
        if any(term in normalized_question for term in ("dorm", "dormitory", "ethernet", "residence hall")):
            urls.extend([
                "https://net.nthu.edu.tw/netsys/en:faq:domitory_net_apply",
                "https://net.nthu.edu.tw/netsys/en:faq:domitory_net_ua_apply",
                "https://net.nthu.edu.tw/netsys/en:faq:domitory_network_config",
                "https://net.nthu.edu.tw/netsys/en:faq:dormitory_shortuse",
            ])
        if any(term in normalized_question for term in ("wi-fi", "wifi", "wireless", "eduroam", "nthupeap", "nthu-cc", "tanetroaming")):
            urls.extend([
                "https://net.nthu.edu.tw/netsys/en:wireless:application",
                "https://net.nthu.edu.tw/netsys/en:wireless:main",
                "https://net.nthu.edu.tw/netsys/en:faq:wlan_range",
                "https://net.nthu.edu.tw/netsys/en:faq:wlan_auth",
                "https://net.nthu.edu.tw/netsys/en:faq:wlan_roaming",
                "https://net.nthu.edu.tw/netsys/en:faq:wlan_getip",
                "https://net.nthu.edu.tw/netsys/en:faq:wlan_useless",
            ])
        if any(term in normalized_question for term in ("mail", "email", "e-mail", "webmail", "mailbox", "google", "gapp")):
            urls.extend([
                "https://net.nthu.edu.tw/netsys/en:mail:application_student:new_std",
                "https://net.nthu.edu.tw/netsys/en:gapp#account_application_procedure",
                "https://net.nthu.edu.tw/netsys/en:faq",
            ])

    has_dorm_context = any(term in normalized_question for term in ("宿舍網路", "宿網", "宿舍"))
    has_dorm_config_context = has_dorm_context and any(term in normalized_question for term in ("設定宿舍網路", "宿舍網路的 ip", "宿舍網路 ip", "ip 設定", "設定 ip", "tcp/ip", "網路設定"))
    if has_dorm_context and not has_dorm_config_context and any(term in normalized_question for term in ("申請", "怎麼", "如何", "帳號", "沒有宿網")):
        urls.extend(
            [
                "https://net.nthu.edu.tw/netsys/faq:domitory_net_ua_apply",
                "https://net.nthu.edu.tw/netsys/faq:domitory_net_apply",
            ]
        )

    if any(term in normalized_question for term in ("分享器", "路由器", "router", "wifi 分享器", "wi-fi 分享器")):
        urls.extend(
            [
                "https://net.nthu.edu.tw/netsys/faq:domitory_network_config2",
                "https://net.nthu.edu.tw/netsys/faq:domitory_network_config",
            ]
        )

    if has_dorm_config_context:
        urls.insert(0, "https://net.nthu.edu.tw/netsys/faq:domitory_network_config")

    if has_dorm_context and any(term in normalized_question for term in ("連不上", "沒有網路", "沒有宿網", "不通", "無法上網")):
        urls.extend(
            [
                "https://net.nthu.edu.tw/netsys/dormnet/",
                "https://net.nthu.edu.tw/netsys/faq:domitory_net_useless",
                "https://net.nthu.edu.tw/netsys/faq:domitory_network_config",
            ]
        )

    has_email_context = any(term in normalized_question for term in ("信箱", "email", "mail", "webmail", "電子郵件", "郵件", "寄信", "收信", "垃圾信", "郵件記錄器", "smtp", "imap", "pop3"))
    if has_email_context:
        urls.extend([
            "https://net.nthu.edu.tw/netsys/mail:application_student:new_std",
            "https://net.nthu.edu.tw/netsys/gapp#帳號申請流程",
            "https://net.nthu.edu.tw/netsys/faq",
        ])

    has_wireless_context = any(term in normalized_question for term in ("無線", "wifi", "wi-fi", "校園無線", "校園網路", "nthu-cc", "nthupeap", "eduroam", "tanetroaming", "wireless", "wlan"))
    has_wireless_trouble_context = has_wireless_context and any(term in normalized_question for term in (
        "連不上", "連不到", "不能用", "無法連線", "無法使用", "登入頁", "認證失敗", "取得 ip", "取得不到 ip",
        "分配不到", "還是不行", "仍不行", "沒用", "很慢", "很差", "不穩", "斷線", "cannot", "can't", "cant",
        "not work", "notworking", "does not work", "failed", "login page", "authentication", "ip", "slow", "unstable", "disconnect",
    ))
    if has_wireless_trouble_context:
        urls.extend(
            [
                "https://net.nthu.edu.tw/netsys/faq:wlan_useless",
                "https://net.nthu.edu.tw/netsys/faq:wlan_auth",
                "https://net.nthu.edu.tw/netsys/faq:wlan_range",
            ]
        )
        if language == "en":
            urls.extend(
                [
                    "https://net.nthu.edu.tw/netsys/en:faq:wlan_useless",
                    "https://net.nthu.edu.tw/netsys/en:faq:wlan_auth",
                    "https://net.nthu.edu.tw/netsys/en:faq:wlan_range",
                ]
            )

    has_vpn_context = any(term in normalized_question for term in ("vpn", "ssl-vpn", "sslvpn", "校外連", "校外連線", "校外連到學校", "校外連到校內", "校內資源", "twaren", "ivanti", "pulse secure"))
    if has_vpn_context:
        urls.extend(
            [
                "https://net.nthu.edu.tw/netsys/sslvpn:info",
                "https://net.nthu.edu.tw/netsys/sslvpn:sslvpn_setup",
                "https://net.nthu.edu.tw/netsys/wireless:application:ccxp",
            ]
        )

    if not has_vpn_context and any(term in normalized_question for term in ("無線", "wifi", "wi-fi", "校園無線", "校園網路")) and any(
        term in normalized_question for term in ("使用", "申請", "怎麼", "如何", "連線")
    ):
        urls.extend(
            [
                "https://net.nthu.edu.tw/netsys/faq:wlan_auth",
                "https://net.nthu.edu.tw/netsys/faq:wlan_roaming",
                "https://net.nthu.edu.tw/netsys/wireless:application",
                "https://net.nthu.edu.tw/netsys/wireless:application:ccxp",
            ]
        )

    location_terms = ("人社院", "資電館", "小吃部", "風雲樓", "水木生活中心", "水漾餐廳", "餐廳", "醫輔大樓", "遠距教室", "合勤演藝廳", "大草坪", "成功湖畔", "學生活動中心", "圖書館", "公共區", "館", "院")
    location_intent_terms = ("哪裡有網路", "哪裡有 wifi", "哪裡有 wi-fi", "有網路嗎", "有 wifi 嗎", "有 wi-fi 嗎", "網路範圍", "無線範圍")
    if (
        any(term in normalized_question for term in location_intent_terms)
        or (
            any(term in normalized_question for term in location_terms)
            and any(term in normalized_question for term in ("網路", "上網", "wifi", "wi-fi", "無線"))
        )
    ):
        urls.extend(["https://net.nthu.edu.tw/netsys/faq:wlan_range", "https://net.nthu.edu.tw/netsys/wireless:easy"])

    chunks = []
    for url in urls:
        chunks.extend(get_chunks_by_url(url, limit=5))

    if has_dorm_config_context:
        chunks.append(
            {
                "title": "faq:domitory_network_config [網路系統組]",
                "source_name": "宿網 TCP/IP 設定",
                "url": "https://net.nthu.edu.tw/netsys/faq:domitory_network_config",
                "content": "宿網 IP 設定不是自動取得 DHCP。已申請宿舍網路後，每日 10 時與 16 時系統處理完畢後即可使用。電腦直接接宿舍網路線時，進入乙太網路設定，編輯 IP 指派，將自動 DHCP 改為手動，開啟 IPv4，填入申請宿網後取得的 TCP/IP 設定後儲存。若使用分享器，應改問分享器怎麼連宿舍網路。",
                "chunk_index": 0,
                "score": 1.0,
                "point_id": "synthetic-dorm-network-config",
            }
        )

    if any(term in normalized_question for term in ("分享器", "路由器", "router", "wifi 分享器", "wi-fi 分享器")) and has_dorm_context:
        chunks.append(
            {
                "title": "faq:domitory_network_config2 [網路系統組]",
                "source_name": "faq:domitory_network_config2 [網路系統組]",
                "url": "https://net.nthu.edu.tw/netsys/faq:domitory_network_config2",
                "content": "分享器可以連宿舍網路。設定時 WAN 端接宿舍網路孔，進入分享器管理介面後，在 WAN 或網際網路設定中選擇固定 IP，填入申請宿舍網路後取得的 TCP/IP 設定資訊。",
                "chunk_index": 0,
                "score": 1.0,
                "point_id": "synthetic-dorm-router-network-config2",
            }
        )

    if has_wireless_trouble_context:
        if language == "en":
            chunks.append(
                {
                    "title": "en:faq:wlan_useless [Network Systems Division]",
                    "source_name": "en:faq:wlan_useless [Network Systems Division]",
                    "url": "https://net.nthu.edu.tw/netsys/en:faq:wlan_useless",
                    "content": "When NTHU campus Wi-Fi cannot connect or does not work, check authentication, IP settings, and signal/location. For nthu-cc or TANetRoaming, connect to the SSID and open a browser to trigger the login page. For nthupeap or eduroam, forget the saved Wi-Fi profile and reconnect with the wireless account and password. Use automatic IP assignment for Wi-Fi. If the issue persists, report the location, floor, SSID, device OS, error message, and screenshots to wlan@cc.nthu.edu.tw.",
                    "chunk_index": 0,
                    "score": 1.0,
                    "point_id": "synthetic-en-wlan-useless",
                }
            )
        else:
            chunks.append(
                {
                    "title": "faq:wlan_useless [網路系統組]",
                    "source_name": "faq:wlan_useless [網路系統組]",
                    "url": "https://net.nthu.edu.tw/netsys/faq:wlan_useless",
                    "content": "校園無線網路無法連線或不能使用時，應從認證問題、IP 問題與其他問題檢查。使用 nthu-cc 或 TANetRoaming 網頁認證時，請確認已連上正確 SSID，並開啟瀏覽器導出認證頁；若頁面未出現，可重新啟動 Wi-Fi 或檢查瀏覽器憑證問題。使用 nthupeap 或 eduroam 時，請確認帳號密碼與裝置設定，可忘記 Wi-Fi 後重新連線。無線網路 IP 應設為自動取得；若仍無法連線，請提供位置、樓層、SSID、裝置系統、錯誤訊息與截圖給 wlan@cc.nthu.edu.tw。",
                    "chunk_index": 0,
                    "score": 1.0,
                    "point_id": "synthetic-wlan-useless",
                }
            )

    if has_vpn_context:
        chunks.append(
            {
                "title": "sslvpn:info [網路系統組]",
                "source_name": "VPN 連線設定",
                "url": "https://net.nthu.edu.tw/netsys/sslvpn:info",
                "content": "校外連線至學校校內網路需使用 VPN。使用前請先申請並啟用校園無線區域網路帳號的 VPN 功能：登入校務資訊系統，在左方選單中點選計通中心相關服務裡的網路系統組線上服務，選擇無線區域網路帳號，填入資訊並在 VPN 設定欄勾選啟用，完成後帳號約 10 分鐘內生效。VPN 連線軟體可使用 Ivanti Secure Access Client 或 Pulse Secure。下載網址不同資料夾代表不同版本，擇一下載，下載網址 https://ndrive.niar.org.tw/navigate/a/#/s/894C6D3B91C94C3EB0D0B4237BC47B426BL，載點登入密碼 nchc。安裝後啟動 VPN 軟體，點選加號，名稱與伺服器欄皆填入 nthu.twaren.net，點選連線，輸入校園無線區域網路帳號及密碼驗證；帳號格式為 XXXXXXX@wlan.nthu.edu.tw。",
                "chunk_index": 0,
                "score": 1.0,
                "point_id": "synthetic-sslvpn-setup",
            }
        )

    if any(term in normalized_question for term in ("哪裡有網路", "哪裡有 wifi", "哪裡有 wi-fi", "有網路嗎", "有 wifi 嗎", "有 wi-fi 嗎", "網路範圍", "無線範圍")):
        chunks.append(
            {
                "title": "wireless:easy [網路系統組]",
                "source_name": "wireless:easy [網路系統組]",
                "url": "https://net.nthu.edu.tw/netsys/wireless:easy",
                "content": "無線上網三步驟：先確認可用的無線上網區域，再選取可靠的無線網路基地台，最後輸入校園無線網路帳號。公共區可使用 nthu-cc、TANetRoaming、nthupeap、eduroam；部分系所單位有各自 SSID。申請 WiFi 時設定無線網路帳號密碼即可，VPN 可視個人需求開啟。若使用 eduroam，需先在裝置 Wi-Fi 設定中點選 eduroam 連線並輸入無線網路帳號密碼，設定一次後每次到該網域附近時會自動連線。",
                "chunk_index": 0,
                "score": 1.0,
                "point_id": "synthetic-wireless-easy-range",
            }
        )

    if "梅園" in normalized_question and any(term in normalized_question for term in ("網路", "上網", "wifi", "wi-fi", "無線")):
        chunks.append(
            {
                "title": "wireless:wlan-cover-color.jpg",
                "source_name": "無線網路覆蓋圖",
                "url": "https://net.nthu.edu.tw/netsys/_media/wireless:wlan-cover-color.jpg?cache=",
                "content": "無線網路覆蓋圖以紅色範圍標示校園無線網路覆蓋位置。根據使用者校正，梅園不在目前可確認的紅色覆蓋範圍內，因此梅園沒有清大校園無線網路覆蓋。",
                "chunk_index": 0,
                "score": 1.0,
                "point_id": "synthetic-wlan-cover-mei-garden",
            }
        )

    return chunks


def rerank_results(question: str, results: list[dict[str, Any]], language: str = "zh-Hant") -> list[dict[str, Any]]:
    normalized_question = question.lower()
    question_terms = expand_question_terms(question)

    for item in results:
        haystack = " ".join(
            [
                str(item.get("title", "")),
                str(item.get("url", "")),
                str(item.get("content", "")),
            ]
        ).lower()
        keyword_hits = sum(1 for term in question_terms if term in haystack)
        title_url_hits = sum(
            1
            for term in question_terms
            if term in str(item.get("title", "")).lower() or term in str(item.get("url", "")).lower()
        )

        item["rerank_score"] = float(item.get("score") or 0) + keyword_hits * 0.08 + title_url_hits * 0.15
        item["rerank_score"] += priority_page_boost(normalized_question, str(item.get("url", "")).lower())

        is_english_source = "/netsys/en:" in str(item.get("url", "")).lower() or "/netsys/en%3a" in str(item.get("url", "")).lower()
        if language == "en":
            item["rerank_score"] += 2.5 if is_english_source else -1.25
        elif is_english_source:
            item["rerank_score"] -= 0.8

        if is_setup_question(normalized_question) and "status" in str(item.get("url", "")).lower():
            item["rerank_score"] -= 0.35

        if any(term in normalized_question for term in ("vpn", "ssl-vpn", "sslvpn", "校外連", "校內資源")):
            if any(term in haystack for term in ("sslvpn:info", "sslvpn:sslvpn_setup", "ivanti", "pulse secure", "twaren", "nthu.twaren.net", "vpn 設定")):
                item["rerank_score"] += 1.0
            if any(term in haystack for term in ("wlan_auth", "domitory_network_config", "宿網 tcp/ip")):
                item["rerank_score"] -= 0.8

    return sorted(results, key=lambda item: item.get("rerank_score", 0), reverse=True)


def is_setup_question(normalized_question: str) -> bool:
    return any(term in normalized_question for term in ("設定", "安裝", "申請", "登入", "下載", "怎麼", "如何"))


def priority_page_boost(normalized_question: str, normalized_url: str) -> float:
    boost = 0.0

    if "net.nthu.edu.tw/netsys/faq" in normalized_url or "/netsys/faq" in normalized_url:
        boost += 0.35

    if "net.nthu.edu.tw/netsys/dormnet" in normalized_url or "/netsys/dormnet" in normalized_url:
        boost += 0.35

    for rule in PRIORITY_PAGE_RULES:
        has_question_term = any(term in normalized_question for term in rule["question_terms"])
        has_intent_term = any(term in normalized_question for term in rule["intent_terms"])
        has_url_term = any(term in normalized_url for term in rule["url_terms"])
        if has_question_term and has_intent_term and has_url_term:
            boost += float(rule["boost"])

    if "faq:email:application" in normalized_url and any(term in normalized_question for term in ("申請", "信箱", "電子郵件", "email", "mail")):
        boost += 1.5

    if "service:portal:set_password" in normalized_url and any(term in normalized_question for term in ("密碼", "忘記", "更改", "變更")):
        boost += 1.2

    if "mail:webmail" in normalized_url and any(term in normalized_question for term in ("webmail", "登入", "使用", "收信")):
        boost += 1.2

    if "dormnet/" in normalized_url and any(term in normalized_question for term in ("申請", "怎麼", "如何")):
        boost -= 0.25

    return boost


def expand_question_terms(question: str) -> set[str]:
    normalized_question = question.lower()
    terms = {token for token in normalized_question.replace("？", " ").replace("?", " ").split() if token}

    for keyword_group in DOMAIN_KEYWORDS.values():
        if any(keyword in normalized_question for keyword in keyword_group):
            terms.update(keyword_group)

    if any(term in normalized_question for term in ("vpn", "ssl-vpn", "sslvpn", "校外連", "校內資源")):
        terms.update(("vpn", "ssl-vpn", "sslvpn", "twaren", "ivanti", "pulse secure", "nthu.twaren.net", "校園無線區域網路帳號"))

    if any(term in normalized_question for term in ("信箱", "email", "mail", "webmail", "電子郵件", "郵件", "寄信", "收信", "垃圾信", "郵件記錄器", "smtp", "imap", "pop3")):
        terms.update(("信箱", "電子郵件", "郵件", "webmail", "mail", "smtp", "郵件記錄器", "垃圾信", "轉寄", "密碼", "容量"))

    if "校園" in question and "網路" in question:
        terms.update(("校園網路", "無線", "wireless", "nthu-cc", "nthupeap", "eduroam", "校際漫遊"))

    if any(term in question for term in ("人社院", "資電館", "小吃部", "風雲樓", "水木生活中心", "餐廳", "醫輔大樓", "公共區")) and "網路" in question:
        terms.update(("無線", "校園無線", "wifi", "wi-fi", "wlan_range", "nthu-cc", "nthupeap", "eduroam"))

    if "宿舍" in question and "網路" in question:
        terms.update(("宿舍網路", "宿網", "學生宿舍", "宿網帳號", "分享器", "路由器", "router", "tcp/ip", "ip 設定", "手動", "固定 ip"))

    return terms


def truncate_text(text: str, limit: int) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def build_rag_context(results: list[dict[str, Any]]) -> str:
    parts = []
    total_chars = 0

    for i, item in enumerate(results, start=1):
        content = truncate_text(str(item.get("content", "")), RAG_CONTEXT_CHARS_PER_SOURCE)
        block = f"""
[資料 {i}]
來源：{item.get("source_name", "")}
標題：{item.get("title", "")}
網址：{item.get("url", "")}
內容：{content}
"""
        if total_chars + len(block) > RAG_CONTEXT_TOTAL_CHARS and parts:
            break
        parts.append(block)
        total_chars += len(block)

    return "".join(parts)
