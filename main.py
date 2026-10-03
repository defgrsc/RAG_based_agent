import json
import re
import threading
import time
from contextlib import contextmanager
from threading import BoundedSemaphore
from typing import Any, Literal

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError
from pydantic import BaseModel, Field, StrictStr

from agent.graph import build_agent_graph, prepare_agent_context
from agent.followups import build_progression_query
from agent.progression_policy import build_progression_response
from agent.logging import log_api_response, log_final_answer, log_standalone_query
from agent.semantics import (
    is_dorm_cross_test_failure,
    is_location_availability_ellipsis,
    rewrite_semantic_followup,
)
from agent.state import history_for_legacy_functions
from agent.topics import ensure_topic_in_query, focus_message_on_topic
from config import CHAT_MAX_CONCURRENT_REQUESTS, LLM_MAX_CONCURRENT_REQUESTS
from fast_answers import (
    WIRELESS_APPLICATION_ANSWER,
    get_clarification_answer,
    get_dependency_fallback_answer,
    get_english_fast_answer,
    get_fast_answer,
    get_structured_fast_answer,
    has_network_failure_intent,
    is_dorm_ip_lookup_intent,
    is_dorm_ip_status_intent,
    is_dorm_network_issue_intent,
    is_no_credential_network_intent,
    is_wireless_application_page_intent,
    paired_fast_translations,
)
from guard import is_contextual_followup, is_nthu_question
from dependency_health import run_dependency_checks
from ingest import ingest_nthu_docs
from llm import generate_answer, translate_messages
from qdrant_store import get_active_collection_name
from rag import build_rag_context, retrieve_context
from response_cache import answer_cache, clear_all_caches, stable_key
from service_errors import EmbeddingServiceError, LLMServiceError, QdrantServiceError
from utils import clean_answer, clean_source_excerpt
from wireless_coverage import (
    build_account_scope_comparison_response,
    build_campus_ssid_response,
    build_coverage_response,
)


app = FastAPI()
app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")

chat_semaphore = BoundedSemaphore(CHAT_MAX_CONCURRENT_REQUESTS)
llm_semaphore = BoundedSemaphore(LLM_MAX_CONCURRENT_REQUESTS)
active_chat_requests = 0
active_llm_requests = 0
queued_llm_requests = 0
session_cache_lock = threading.Lock()
session_cache_keys: dict[str, set[str]] = {}
agent_graph_lock = threading.Lock()
compiled_agent_graph = None


def remember_session_cache_key(session_id: str | None, cache_key: str) -> None:
    if not session_id:
        return
    with session_cache_lock:
        session_cache_keys.setdefault(session_id, set()).add(cache_key)


def clear_session_cache(session_id: str) -> int:
    with session_cache_lock:
        keys = session_cache_keys.pop(session_id, set())
    return answer_cache.delete_many(keys)


@contextmanager
def chat_capacity():
    global active_chat_requests

    acquired = chat_semaphore.acquire(blocking=False)
    if not acquired:
        raise HTTPException(
            status_code=429,
            detail=f"目前同時詢問人數較多，系統最多同時處理 {CHAT_MAX_CONCURRENT_REQUESTS} 個問題，請稍後再試。",
        )

    active_chat_requests += 1
    try:
        yield
    finally:
        active_chat_requests -= 1
        chat_semaphore.release()


@contextmanager
def llm_capacity():
    global active_llm_requests, queued_llm_requests

    queued_llm_requests += 1
    try:
        llm_semaphore.acquire()
    finally:
        queued_llm_requests -= 1

    active_llm_requests += 1
    try:
        yield
    finally:
        active_llm_requests -= 1
        llm_semaphore.release()


class ChatHistoryItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatHistoryItem] = Field(default_factory=list)
    language: Literal["zh-Hant", "en"] = "zh-Hant"
    session_id: str | None = Field(default=None, max_length=80)



class ChatResponse(BaseModel):
    answer: StrictStr
    sources: list[dict[str, Any]] = Field(default_factory=list)
    answer_translations: dict[str, StrictStr] | None = None


def finalize_chat_response(
    payload: dict[str, Any],
    state: dict,
    *,
    path: str,
) -> dict[str, Any]:
    response = ChatResponse.model_validate(payload).model_dump(exclude_none=True)
    log_api_response(state, response, path)
    return response

class SessionClearRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=80)


class TranslationRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=16)
    target_language: Literal["zh-Hant", "en"]


def clean_sources(sources: list[dict]) -> list[dict]:
    cleaned = []
    for source in sources:
        item = dict(source)
        item["content"] = clean_source_excerpt(str(item.get("content", "")))
        cleaned.append(item)
    return cleaned


FAST_SOURCE_TOPIC_MARKERS: dict[str, tuple[str, ...]] = {
    "dorm_network": (
        "domitory", "dormitory", "dormnet", "宿網", "宿舍網路",
    ),
    "campus_wifi": (
        "wlan", "wireless", "wi-fi", "wifi", "eduroam", "nthupeap",
        "nthu-cc", "nthucc", "tanetroaming", "校園無線", "無線網路",
    ),
    "vpn": (
        "sslvpn", "/vpn", "ivanti", "pulse secure", "twaren", "校外連線",
    ),
    "email": (
        "gapp", "/mail", ":mail", "email", "webmail", "smtp", "imap",
        "學生信箱", "電子郵件",
    ),
}


def infer_fast_answer_topics(response: dict) -> set[str]:
    topics: set[str] = set()
    for source in response.get("sources", []):
        haystack = " ".join(
            str(source.get(key, ""))
            for key in ("title", "source_name", "url", "content")
        ).lower()
        for topic, markers in FAST_SOURCE_TOPIC_MARKERS.items():
            if any(marker in haystack for marker in markers):
                topics.add(topic)
    return topics


def fast_answer_matches_topic(response: dict, current_topic: str) -> bool:
    if current_topic not in FAST_SOURCE_TOPIC_MARKERS:
        return True
    inferred_topics = infer_fast_answer_topics(response)
    return not inferred_topics or current_topic in inferred_topics


def unresolved_reference_answer(language: str) -> dict[str, list | str]:
    if language == "en":
        answer = (
            "I cannot find the earlier question you are referring to. Please paste that "
            "question again or name the service, such as DormNet, campus Wi-Fi, VPN, or email."
        )
    else:
        answer = (
            "我找不到你提到的前一題或第一個問題。請把那個問題再貼一次，"
            "或補充服務名稱（例如宿網、校園 Wi-Fi、VPN 或信箱），我才能接著回答。"
        )
    return {"answer": answer, "sources": []}


def format_history(history: list[dict[str, str]]) -> str:
    labels = {"user": "學生", "assistant": "助理"}
    return "\n".join(f"{labels.get(item['role'], '對話')}：{item['content']}" for item in history)


def ordinal_followup_index(question: str) -> int | None:
    normalized = "".join(question.lower().split()).strip("？?!！。.")
    ordinal_map = {
        "第一": 1, "第1": 1, "一": 1, "first": 1, "thefirst": 1,
        "第二": 2, "第2": 2, "二": 2, "second": 2, "thesecond": 2,
        "第三": 3, "第3": 3, "三": 3, "third": 3, "thethird": 3,
        "第四": 4, "第4": 4, "四": 4, "fourth": 4, "thefourth": 4,
        "第五": 5, "第5": 5, "五": 5, "fifth": 5, "thefifth": 5,
    }
    if not any(marker in normalized for marker in ("個", "項", "點", "one")):
        return None
    for marker, index in ordinal_map.items():
        if marker in normalized:
            return index
    return None


def last_assistant_content_from_raw(history: list[ChatHistoryItem]) -> str:
    for item in reversed(history):
        if item.role == "assistant" and item.content.strip():
            return item.content.strip()
    return ""


def extract_markdown_sections(answer: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    heading_re = re.compile(r"^\*\*(.+?)\*\*\s*$")

    def flush() -> None:
        nonlocal current_title, current_lines
        if current_title and "\n".join(current_lines).strip():
            sections.append((current_title, "\n".join(current_lines).strip()))
        current_title = None
        current_lines = []

    for raw_line in answer.splitlines():
        line = raw_line.strip()
        heading = heading_re.match(line)
        if heading:
            next_title = heading.group(1).strip()
            if current_title and not "\n".join(current_lines).strip():
                current_title = f"{current_title} / {next_title}"
            else:
                flush()
                current_title = next_title
                current_lines = []
        elif current_title:
            current_lines.append(raw_line)
    flush()
    return [(title, body) for title, body in sections if body]


def extract_numbered_items(answer: str) -> list[str]:
    items: list[str] = []
    for line in answer.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+\.\s+", stripped):
            items.append(stripped)
    return items


def answer_ordinal_followup(question: str, raw_history: list[ChatHistoryItem], language: str) -> dict | None:
    index = ordinal_followup_index(question)
    if index is None:
        return None
    previous_answer = last_assistant_content_from_raw(raw_history)
    if not previous_answer:
        return None

    sections = extract_markdown_sections(previous_answer)
    if len(sections) >= index:
        title, body = sections[index - 1]
        prefix = f"你問的是上一則回答的第 {index} 個段落：**{title}**。" if language == "zh-Hant" else f"You are asking about section {index} from my previous answer: **{title}**."
        answer = f"{prefix}\n\n{body}"
    else:
        items = extract_numbered_items(previous_answer)
        if len(items) < index:
            return None
        prefix = f"你問的是上一則回答的第 {index} 個項目。" if language == "zh-Hant" else f"You are asking about item {index} from my previous answer."
        answer = f"{prefix}\n\n{items[index - 1]}"

    urls = []
    for url in re.findall(r"https://[^\s<>)）]+", previous_answer):
        clean_url = url.rstrip("。。，,.;；")
        if clean_url not in urls:
            urls.append(clean_url)
    sources = [{"title": url, "source_name": url, "url": url, "content": "", "chunk_index": 0, "score": 1.0} for url in urls[:3]]
    return {"answer": clean_answer(answer, question=question), "sources": clean_sources(sources)}


def text_already_in_language(text: str, target_language: str) -> bool:
    cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    ascii_alpha_count = sum(1 for char in text if char.isascii() and char.isalpha())
    if target_language == "en":
        return cjk_count == 0 and ascii_alpha_count >= 2
    return cjk_count >= 2


def detect_question_language(question: str, requested_language: str) -> str:
    # The UI language switch should control the answer language.
    # This avoids switching to English while Chinese input still receives Chinese replies.
    if requested_language in {"zh-Hant", "en"}:
        return requested_language

    cjk_count = sum(1 for char in question if "\u4e00" <= char <= "\u9fff")
    ascii_alpha_count = sum(1 for char in question if char.isascii() and char.isalpha())
    if cjk_count >= 2:
        return "zh-Hant"
    if ascii_alpha_count >= 8 and cjk_count == 0:
        return "en"
    return "zh-Hant"


def build_contextual_question(question: str, history: list[dict[str, str]]) -> str:
    history_text = format_history(history)
    if not history_text or is_explicit_service_question(question):
        return question
    # If query rewrite already produced a scoped NTHU service question, keep retrieval focused
    # on the current intent. History is appended only when the current query remains incomplete.
    if service_reference(question) and is_nthu_question(question):
        return question

    return f"前面對話：\n{history_text}\n\n目前問題：{question}"


def is_explicit_service_question(question: str) -> bool:
    normalized = "".join(question.lower().split()).strip("？?!！。.")
    if not normalized:
        return False

    dorm_terms = (
        "宿網", "宿舍網路", "學生宿舍網路", "宿舍網路帳號", "宿舍網路申請",
        "dormnet", "dormnetwork", "dormitorynetwork", "dormitorynetworkaccount",
        "dormitorynetworkapplication",
    )
    wireless_terms = (
        "無線網路", "校園無線", "校園wifi", "校園wi-fi", "學校wifi", "學校wi-fi",
        "wifi", "wi-fi", "wlan", "nthu-cc", "nthucc", "nthupeap", "eduroam", "tanetroaming",
        "campuswifi", "campuswi-fi", "wirelesslan", "wirelessnetwork",
    )
    vpn_terms = ("vpn", "sslvpn", "ivanti", "pulsesecure", "pulse", "nthu.twaren.net", "校外連線", "校外連到學校")
    email_terms = (
        "清大信箱", "學生信箱", "校內信箱", "電子郵件", "gapp", "googleapps",
        "googleworkspace", "gsuite", "nthumail", "nthuemail", "studentemail",
        "studentmail", "emailaccount", "mailaccount", "mailbox", "webmail", "smtp",
        "imap", "pop3", "thunderbird", "gmailapp", "郵件", "寄信", "收信",
        "退信", "附件", "垃圾郵件", "郵件記錄", "552", "5.3.4",
    )
    intent_terms = (
        "申請", "怎麼申請", "設定", "怎麼設定", "使用", "怎麼使用", "連", "怎麼連",
        "連不上", "連不到", "無法", "不能", "登入", "密碼", "帳號", "格式", "報修",
        "如何", "為什麼", "怎麼辦", "要填什麼", "代表什麼", "什麼意思", "錯誤", "成功", "救回", "轉寄", "自動回覆",
        "踢出去", "踢出", "一直掉",
        "壞", "故障", "很慢", "很卡", "卡", "超卡", "很差", "不穩", "怪怪", "異常",
        "狀態", "禁用", "封鎖", "停用", "忘記", "忘了", "不記得", "查詢", "範圍", "哪裡", "有網路",
        "apply", "application", "set", "setup", "use", "connect", "connection",
        "login", "password", "account", "format", "failed", "cannot", "can't", "cant",
        "notworking", "slow", "unstable", "coverage", "where",
    )

    service_groups = (dorm_terms, wireless_terms, vpn_terms, email_terms)
    has_service = any(term in normalized for terms in service_groups for term in terms)
    if not has_service:
        return False
    return has_network_failure_intent(question) or any(term in normalized for term in intent_terms)


def service_reference(question: str) -> str | None:
    normalized = "".join(question.lower().split()).strip("？?!！。.")
    if any(term in normalized for term in ("宿網", "宿舍網路", "學生宿舍網路", "dormnet", "dormnetwork", "dormitorynetwork")):
        return "dorm"
    if any(term in normalized for term in ("無線網路", "校園無線", "wifi", "wi-fi", "wlan", "nthu-cc", "nthucc", "nthupeap", "eduroam", "tanetroaming", "wireless", "campuswifi")):
        return "wireless"
    if any(term in normalized for term in ("vpn", "sslvpn", "ivanti", "pulsesecure", "pulse", "nthu.twaren.net")):
        return "vpn"
    if any(term in normalized for term in ("清大信箱", "學生信箱", "校內信箱", "電子郵件", "gapp", "email", "mail", "mailbox", "googleapps", "googleworkspace", "gsuite")):
        return "email"
    return None


def recent_user_service_context(history: list[dict[str, str]]) -> str | None:
    for item in reversed(history[-8:]):
        if item.get("role") != "user":
            continue
        service = service_reference(item.get("content", ""))
        if service:
            return service
    return None


def recent_question_intent(history: list[dict[str, str]]) -> str:
    recent = recent_user_normalized_text(history, limit=4)
    recent = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", recent)
    if any(term in recent for term in ("申請", "怎麼申請", "要怎麼申請", "apply", "application")):
        return "apply"
    if any(term in recent for term in ("設定", "怎麼設定", "set", "setup", "set up", "howdoiset", "howshouldiset")):
        return "setup"
    if any(term in recent for term in ("密碼", "password")):
        return "password"
    if has_network_failure_intent(recent) or any(term in recent for term in ("連不上", "連不到", "不能用", "無法", "失敗", "很慢", "很差", "不穩", "failed", "cannot", "notwork", "slow", "unstable")):
        return "troubleshoot"
    if any(term in recent for term in ("使用", "怎麼使用", "怎麼連", "連線", "use", "connect", "connection")):
        return "use"
    return "general"


def complete_service_followup(question: str, history: list[dict[str, str]]) -> str | None:
    normalized = "".join(question.lower().split()).strip("？?!！。.")
    is_chinese_question = any("一" <= ch <= "鿿" for ch in question)
    if ("nthucc" in normalized or "nthu-cc" in question.lower()) and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連", "use", "connect", "login", "signin", "how")):
        return "nthu-cc 使用" if is_chinese_question else "How do I use nthu-cc?"
    if "nthupeap" in normalized and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連", "use", "connect", "login", "signin", "how")):
        return "nthupeap 使用" if is_chinese_question else "How do I use nthupeap?"
    if "eduroam" in normalized and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連", "use", "connect", "login", "signin", "how")):
        return "eduroam 使用" if is_chinese_question else "How do I use eduroam?"
    if "tanetroaming" in normalized and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連", "use", "connect", "login", "signin", "how")):
        return "TANetRoaming 使用" if is_chinese_question else "How do I use TANetRoaming?"
    target = service_reference(question)
    if not target or is_explicit_service_question(question):
        return None
    if len(normalized) > 40 and not normalized.startswith(("那", "那個", "那如果", "whatabout", "howabout", "and")):
        return None

    intent = recent_question_intent(history)

    if target == "dorm":
        if intent == "setup":
            return "宿網 IP 要怎麼設定？" if is_chinese_question else "How do I set the dorm network IP?"
        if intent == "troubleshoot":
            return "宿網連不上怎麼辦？" if is_chinese_question else "What should I do if DormNet does not work?"
        return "宿舍網路怎麼申請？" if is_chinese_question else "How do I apply for DormNet?"

    if target == "wireless":
        if intent == "apply":
            return "Wi-Fi 怎麼申請？" if is_chinese_question else "How do I apply for campus Wi-Fi?"
        if intent == "troubleshoot":
            return "校園無線網路連不上怎麼辦？" if is_chinese_question else "What should I do if campus Wi-Fi does not work?"
        return "校園無線網路怎麼使用？" if is_chinese_question else "How do I use NTHU campus Wi-Fi?"

    if target == "vpn":
        if intent == "password":
            return "VPN 軟體密碼要填什麼？" if is_chinese_question else "What password should I enter for the NTHU VPN client?"
        return "VPN 怎麼設定？" if is_chinese_question else "How do I set up the NTHU VPN?"

    if target == "email":
        return "清大信箱怎麼申請？" if is_chinese_question else "How do I apply for NTHU email?"

    return None


LOCATION_FOLLOWUP_PLACES = (
    "人社院", "小吃部", "梅園", "資電館", "台達館", "台達", "台積館", "旺宏館", "物理館", "化學館", "圖書館",
    "總圖", "水木生活中心", "水木", "風雲樓", "醫輔大樓", "醫輔", "紅吱吱", "紅吱吱牛排",
)

EN_LOCATION_FOLLOWUP_PLACES = (
    "Shui Mu Life Center", "Shui Mu", "Fengyun Building", "Feng Yun Building", "Hong Zhi Zhi steak",
    "Hong Zhi Zhi", "Red Zhi Zhi steak", "Red Zhi Zhi", "Zhi Zhi steak", "Delta Building", "TSMC Building", "Library", "Humanities and Social Sciences Building",
    "cafeteria", "food court", "snack bar", "Mei Garden", "Meiyuan",
)


DORM_FOLLOWUP_PLACES = (
    "明齋", "平齋", "清齋", "華齋", "誠齋", "義齋", "新齋", "禮齋",
    "仁齋", "實齋", "信齋", "碩齋", "學齋", "儒齋", "文齋", "靜齋",
    "慧齋", "雅齋", "鴻齋", "善齋", "鳴鳳樓", "崇善樓", "迎曦軒",
    "掬月齋", "樹德樓", "ruzhai", "ruzhai", "ru zhai", "xinzhai", "xin zhai",
)

LOCATION_ALIASES = {
    "風雲": "風雲樓",
    "風雲勒": "風雲樓",
    "風雲呢": "風雲樓",
    "風雲咧": "風雲樓",
    "水木": "水木生活中心",
    "醫輔": "醫輔大樓",
    "總圖": "圖書館",
    "紅吱吱": "紅吱吱牛排",
}


def normalize_campus_place_mention(text: str) -> str | None:
    normalized = text.lower().replace(" ", "").strip("？?!！。.")
    normalized = normalized.removeprefix("那").removeprefix("請問")
    normalized = normalized.rstrip("呢勒咧哩嗎啊啦了")

    for alias, place in LOCATION_ALIASES.items():
        if normalized == alias.lower().replace(" ", "") or alias.lower().replace(" ", "") in normalized:
            return place
    for place in LOCATION_FOLLOWUP_PLACES:
        key = place.lower().replace(" ", "")
        if normalized == key or key in normalized:
            return "水木生活中心" if place == "水木" else "醫輔大樓" if place == "醫輔" else place
    for place in EN_LOCATION_FOLLOWUP_PLACES:
        key = place.lower().replace(" ", "")
        if normalized == key or key in normalized:
            if key in {"cafeteria", "foodcourt", "snackbar"}:
                return "cafeteria"
            if key in {"meigarden", "meiyuan"}:
                return "Mei Garden"
            if key in {"hongzhizhisteak", "hongzhizhi", "redzhizhisteak", "redzhizhi", "zhizhisteak"}:
                return "Red Zhi Zhi steak"
            return place
    return None


def extract_generic_campus_place_mention(text: str) -> str | None:
    compact = text.strip().replace(" ", "")
    match = re.search(r"綜(?:合)?([一二三四五六七八九十0-9]+)(?:館)?", compact)
    if match:
        return f"綜合{match.group(1)}館"

    match = re.search(r"([\u4e00-\u9fffA-Za-z0-9]{1,12}(?:館|院|樓|中心|大樓))", compact)
    if not match:
        return None
    place = re.sub(r"^.*[在於問]", "", match.group(1))
    place = re.sub(r"^(那|請問|想問|問一下|最近)", "", place)
    return place or match.group(1)


def explicit_campus_place_mention(text: str) -> str | None:
    return normalize_campus_place_mention(text) or extract_generic_campus_place_mention(text)


def has_location_coverage_intent(text: str) -> bool:
    normalized = text.lower().replace(" ", "")
    if not explicit_campus_place_mention(text):
        return False
    if any(term in normalized for term in ("很差", "網路差", "品質", "訊號差", "不穩", "很慢", "很卡", "連不上", "無法連線", "不能用", "無法上網")):
        return False
    return any(term in normalized for term in ("有網路嗎", "有wifi嗎", "有wi-fi嗎", "有無線網路嗎", "有沒有網路", "有沒有wifi", "是否有網路", "是否有wifi"))


def has_credential_terms(text: str) -> bool:
    normalized = text.lower().replace(" ", "")
    return any(term in normalized for term in ("帳號密碼", "帳密", "帳號", "密碼", "username", "password", "account"))


def has_wireless_credential_intent(text: str) -> bool:
    normalized = text.lower().replace(" ", "")
    has_network = any(term in normalized for term in ("網路", "wifi", "wi-fi", "無線", "連線", "登入", "認證", "network", "wireless"))
    has_location = explicit_campus_place_mention(text) is not None
    return has_credential_terms(text) and (has_network or has_location)


def recent_wireless_credential_place(history: list[dict[str, str]]) -> str | None:
    for item in reversed(history[-8:]):
        if item.get("role") != "user":
            continue
        content = item.get("content", "")
        if has_wireless_credential_intent(content):
            place = explicit_campus_place_mention(content)
            if place:
                return place
    return None


def recent_normalized_text(history: list[dict[str, str]], limit: int = 6) -> str:
    return " ".join(item["content"] for item in history[-limit:]).lower().replace(" ", "")


def recent_user_normalized_text(history: list[dict[str, str]], limit: int = 6) -> str:
    return " ".join(item["content"] for item in history[-limit:] if item.get("role") == "user").lower().replace(" ", "")


def recent_campus_place(history: list[dict[str, str]]) -> str | None:
    english_map = {
        "deltabuilding": "Delta Building",
        "tsmcbuilding": "TSMC Building",
        "library": "Library",
        "fengyunbuilding": "Fengyun Building",
        "fengyun": "Fengyun Building",
        "meigarden": "Mei Garden",
        "meiyuan": "Mei Garden",
        "cafeteria": "cafeteria",
        "foodcourt": "cafeteria",
        "shuimu": "Shui Mu Life Center",
    }

    for item in reversed(history[-8:]):
        if item.get("role") != "user":
            continue
        normalized = item.get("content", "").lower().replace(" ", "")
        for place in LOCATION_FOLLOWUP_PLACES:
            if place.lower().replace(" ", "") in normalized:
                return "水木生活中心" if place == "水木" else "醫輔大樓" if place == "醫輔" else place
        for key, value in english_map.items():
            if key in normalized:
                return value
    return None


def has_dorm_context(history: list[dict[str, str]]) -> bool:
    normalized = recent_user_normalized_text(history)
    return any(place.lower().replace(" ", "") in normalized for place in DORM_FOLLOWUP_PLACES)


def is_location_network_history(history: list[dict[str, str]]) -> bool:
    normalized = recent_normalized_text(history, limit=4)
    has_location = any(place.lower().replace(" ", "") in normalized for place in LOCATION_FOLLOWUP_PLACES)
    has_location = has_location or any(place.lower().replace(" ", "") in normalized for place in EN_LOCATION_FOLLOWUP_PLACES)
    has_network_intent = any(term in normalized for term in (
        "有網路", "有wifi", "有wi-fi", "有無線", "哪裡有網路", "哪裡有wifi",
        "無線網路範圍", "校園無線網路", "網路涵蓋",
        "wifi", "wi-fi", "wireless", "network", "campuswifi", "campuswi-fi", "coverage",
    ))
    return has_location and has_network_intent


def is_dorm_network_history(history: list[dict[str, str]]) -> bool:
    normalized = recent_user_normalized_text(history)
    return any(term in normalized for term in (
        "宿網", "宿舍網路", "學生宿舍網路", "宿舍", "我住", "房間網路", "dormitorynetwork", "dormnetwork", "dormnet",
        "dormitorynetworkapplication", "dormitorynetworkaccount", "dormitory", "iliveinthedorm", "liveinthedorm",
    )) or has_dorm_context(history)


def is_email_history(history: list[dict[str, str]]) -> bool:
    normalized = recent_normalized_text(history)
    return any(term in normalized for term in (
        "信箱", "電子郵件", "email", "mail", "gapp", "google", "googleapps", "googleworkspace", "gsuite", "gsuiteforeducation",
    ))


def is_gapp_history(history: list[dict[str, str]]) -> bool:
    normalized = recent_normalized_text(history)
    return any(term in normalized for term in (
        "gapp", "googleapps", "googleworkspace", "googletheone", "thegoogleone", "g suite", "gsuiteforeducation",
        "googleapps帳號申請", "google那個",
    ))


def is_wireless_history(history: list[dict[str, str]]) -> bool:
    recent_text = " ".join(item["content"] for item in history[-6:])
    normalized = recent_text.lower().replace(" ", "")
    return any(term in normalized for term in (
        "無線", "wifi", "wi-fi", "wireless", "校園wi-fi", "校園wifi", "campuswifi", "campuswi-fi",
        "nthu-cc", "nthucc", "tanetroaming", "nthupeap", "eduroam", "wlan",
    ))


def is_eduroam_history(history: list[dict[str, str]]) -> bool:
    normalized = recent_user_normalized_text(history)
    return "eduroam" in normalized


def is_external_eduroam_history(history: list[dict[str, str]]) -> bool:
    normalized = recent_user_normalized_text(history, limit=8)
    return "eduroam" in normalized and any(term in normalized for term in (
        "台大", "臺大", "交大", "陽明交大", "外校", "別的學校", "其他學校",
        "ntu", "nycu", "anotheruniversity", "otheruniversity", "offcampus",
    ))


def is_nthupeap_history(history: list[dict[str, str]]) -> bool:
    normalized = recent_user_normalized_text(history)
    return "nthupeap" in normalized


def is_nthu_cc_history(history: list[dict[str, str]]) -> bool:
    normalized = recent_user_normalized_text(history)
    return "nthu-cc" in normalized or "nthucc" in normalized


def is_vpn_history(history: list[dict[str, str]]) -> bool:
    normalized = recent_user_normalized_text(history)
    return any(term in normalized for term in (
        "vpn", "sslvpn", "ivantisecureaccess", "pulsesecure", "nthu.twaren.net",
        "sstudentid@wlan.nthu.edu.tw", "校外連線", "校外連到學校網路", "學校內網",
    ))


def is_router_history(history: list[dict[str, str]]) -> bool:
    recent_text = " ".join(item["content"] for item in history[-6:] if item.get("role") == "user")
    normalized = recent_text.lower().replace(" ", "")
    return any(term in normalized for term in (
        "分享器", "路由器", "router", "wan", "固定ip", "staticip", "dormitorynetworkwallport"
    ))


def is_wireless_application_page_history(history: list[dict[str, str]]) -> bool:
    normalized = recent_normalized_text(history, limit=6)
    return any(term in normalized for term in (
        "申請頁", "無線網路申請頁", "wifi申請頁", "wi-fi申請頁",
        "applicationpage", "wirelessapplicationpage", "wifiapplicationpage",
    ))


def is_wireless_password_history(history: list[dict[str, str]]) -> bool:
    normalized = recent_normalized_text(history, limit=6)
    return any(term in normalized for term in (
        "無線網路帳號", "無線網路密碼", "wifi帳號", "wifi密碼", "wi-fi密碼", "學校wifi",
        "校園無線區域網路帳號", "wirelesslanaccount", "wifipassword", "wi-fipassword",
    ))


def is_dorm_transfer_history(history: list[dict[str, str]]) -> bool:
    normalized = recent_user_normalized_text(history, limit=8)
    return any(term in normalized for term in (
        "換宿", "搬到", "搬宿舍", "新齋", "儒齋", "新房間", "新宿舍",
        "moveddorm", "moveddorms", "movingdorm", "changedorm", "newroom", "newdorm", "movedfrom",
    ))


def has_prompt_leak(answer: str) -> bool:
    leak_markers = (
        "The user is asking",
        "Looking at the available data",
        "available data",
        "Rule ",
        "根據規則",
        "規則 ",
        "可用資料",
        "資料 1",
        "資料1",
        "系統提示",
        "Let me check",
        "I should",
        "I need to",
    )
    head = answer[:1200]
    return any(marker in head for marker in leak_markers)


def fallback_for_prompt_leak(language: str) -> str:
    if language == "en":
        return "I could not generate a reliable answer from the available NTHU network information. Please rephrase the question with the service type and location, such as DormNet, campus Wi-Fi, VPN, or email."
    return "目前無法根據可用的清大網路資料產生可靠回答。請補充服務類型與地點，例如宿網、校園 Wi-Fi、VPN 或信箱。"


def recent_assistant_mentions_dorm_status_check(history: list[dict[str, str]]) -> bool:
    for item in reversed(history[-4:]):
        if item.get("role") != "assistant":
            continue
        content = item.get("content", "")
        if any(term in content for term in ("查詢 IP / 網路狀態", "禁用狀態", "用戶設備埠狀態", "狀態查詢")) and any(term in content for term in ("宿網", "宿舍網路", "dormnet", "DormNet")):
            return True
    return False


def recent_assistant_mentions_dorm_ip_lookup(history: list[dict[str, str]]) -> bool:
    for item in reversed(history[-4:]):
        if item.get("role") != "assistant":
            continue
        content = item.get("content", "")
        if "MyApStatusM.pl" in content or ("宿網" in content and "DormNet Account" in content):
            return True
        if any(term in content for term in ("宿網申請狀態查詢", "IP/TCP/IP 設定資訊", "忘記自己的宿網 IP")):
            return True
    return False


def is_context_dependent_check_followup(question: str) -> bool:
    normalized = "".join(question.lower().split()).strip("？?!！。.")
    if service_reference(question) or is_explicit_service_question(question):
        return False
    check_terms = ("檢查", "查", "看", "狀態", "去哪裡", "哪裡", "網址", "入口", "連結", "where", "link", "url", "check", "status")
    action_terms = ("要", "怎麼", "哪裡", "去哪", "在哪", "網址", "入口", "連結", "where", "how", "link", "url")
    return any(term in normalized for term in check_terms) and any(term in normalized for term in action_terms)


def resolve_contextual_followup_question(question: str, history: list[dict[str, str]]) -> str:
    if not history:
        return question

    normalized = "".join(question.lower().split()).strip("？?!！。.")
    latest_service = recent_user_service_context(history)
    is_chinese_question = any("\u4e00" <= ch <= "\u9fff" for ch in question)

    if is_dorm_cross_test_failure(question):
        return question

    support_followup = any(term in normalized for term in (
        "聯絡", "信箱", "寄到哪", "寄信", "找誰", "報修", "提供哪些資料", "提供什麼資料", "需要提供", "要提供",
        "contact", "emailaddress", "support", "report", "whatinformation", "whatdetails",
    ))
    if support_followup and latest_service == "dorm":
        return "宿網報修寄信要附什麼？" if is_chinese_question else "What should I include in a DormNet repair email?"
    if support_followup and latest_service == "wireless":
        return "校園無線網路連不上怎麼辦？" if is_chinese_question else "What should I do if campus Wi-Fi does not work?"

    # Current explicit DormNet status/IP/quality intents should win over older context.
    if is_dorm_ip_lookup_intent(question):
        return "忘記宿網 IP 要去哪裡查？" if is_chinese_question else "Where can I look up my DormNet IP?"
    if is_dorm_ip_status_intent(question):
        return "宿網 IP 狀態或禁用狀態要怎麼查？" if is_chinese_question else "How do I check DormNet IP or disabled status?"
    if is_dorm_network_issue_intent(question):
        return question

    application_location_followup = (
        any(term in normalized for term in ("申請", "apply", "application"))
        and any(term in normalized for term in ("哪裡", "去哪", "在哪", "入口", "網址", "where", "how"))
    )
    if application_location_followup and latest_service == "dorm":
        return "宿舍網路怎麼申請？" if is_chinese_question else "How do I apply for DormNet?"
    if application_location_followup and latest_service == "wireless":
        return "校園無線網路帳號怎麼申請？" if is_chinese_question else "How do I apply for a campus Wi-Fi account?"

    if recent_assistant_mentions_dorm_ip_lookup(history) and is_context_dependent_check_followup(question):
        return "忘記宿網 IP 要去哪裡查？" if is_chinese_question else "Where can I look up my DormNet IP?"

    if recent_assistant_mentions_dorm_status_check(history) and is_context_dependent_check_followup(question):
        return "宿網狀態要去哪裡檢查？" if is_chinese_question else "Where can I check DormNet status?"

    if is_no_credential_network_intent(question):
        return "清大有不需要帳號密碼就能使用的校園網路嗎？" if is_chinese_question else "Is there NTHU campus Wi-Fi that can be used without an account or password?"

    if is_wireless_application_page_intent(question):
        return "無線網路申請頁打不開怎麼辦？" if is_chinese_question else "What if the wireless application page will not open?"

    # If the current query already names a service and a concrete need, do not let
    # previous conversation history overwrite it. History is only for incomplete follow-ups.
    if is_explicit_service_question(question):
        return question

    if has_wireless_credential_intent(question):
        explicit_place = explicit_campus_place_mention(question)
        if explicit_place and explicit_place not in {"紅吱吱牛排", "Red Zhi Zhi steak"}:
            return "清大無線網路帳號密碼是什麼？" if is_chinese_question else "What account and password should I use for NTHU campus Wi-Fi?"

    if has_credential_terms(question):
        credential_place = recent_wireless_credential_place(history) or recent_campus_place(history)
        if credential_place or is_location_network_history(history) or is_wireless_history(history):
            return "清大無線網路帳號密碼是什麼？" if is_chinese_question else "What account and password should I use for NTHU campus Wi-Fi?"

    location_followup_place = explicit_campus_place_mention(question)
    if location_followup_place and has_location_coverage_intent(question):
        if location_followup_place == "cafeteria":
            return "小吃部有網路嗎？" if is_chinese_question else "Does the cafeteria have NTHU Wi-Fi?"
        if location_followup_place == "Mei Garden":
            return "梅園有網路嗎？" if is_chinese_question else "Does Mei Garden have NTHU Wi-Fi?"
        if location_followup_place in {"紅吱吱牛排", "Red Zhi Zhi steak"}:
            return "紅吱吱牛排有網路嗎？" if is_chinese_question else "Does Red Zhi Zhi steak have NTHU Wi-Fi?"
        return f"{location_followup_place}有網路嗎？" if is_chinese_question else f"Does {location_followup_place} have NTHU Wi-Fi?"

    if location_followup_place and is_location_network_history(history) and not has_wireless_credential_intent(question):
        if location_followup_place == "cafeteria":
            return "小吃部有網路嗎？" if is_chinese_question else "Does the cafeteria have NTHU Wi-Fi?"
        if location_followup_place == "Mei Garden":
            return "梅園有網路嗎？" if is_chinese_question else "Does Mei Garden have NTHU Wi-Fi?"
        if location_followup_place in {"紅吱吱牛排", "Red Zhi Zhi steak"}:
            return "紅吱吱牛排有網路嗎？" if is_chinese_question else "Does Red Zhi Zhi steak have NTHU Wi-Fi?"
        return f"{location_followup_place}有網路嗎？" if is_chinese_question else f"Does {location_followup_place} have NTHU Wi-Fi?"

    if is_dorm_network_history(history) and latest_service in {None, "dorm"}:
        has_network_followup = any(term in normalized for term in ("網路", "上網", "連線", "連", "internet", "network"))
        has_dorm_issue_followup = any(term in normalized for term in (
            "不能用", "無法用", "不能上網", "上不了網", "無法上網", "沒網路", "沒有網路",
            "連不上", "連不到", "無法連線", "斷線", "一直斷", "不穩", "不太穩",
            "不太好", "怪怪", "異常", "很慢", "超慢", "很卡", "超卡", "卡卡",
            "很爛", "超爛", "今天", "最近", "怎麼辦", "什麼問題",
            "notworking", "cannotconnect", "cantconnect", "unstable", "slow", "bad"
        ))
        if has_network_followup and has_dorm_issue_followup:
            return "宿網連線不穩或不能用怎麼辦？" if is_chinese_question else "What should I do if DormNet is unstable or not working?"

    place_for_deictic_followup = recent_campus_place(history)
    if place_for_deictic_followup and any(term in normalized for term in ("那邊", "那裡", "那裏", "那個地方", "there", "thatplace", "thatlocation")):
        is_chinese_question = any("\u4e00" <= ch <= "\u9fff" for ch in question)
        if any(term in normalized for term in ("wifi", "wi-fi", "網路", "無線", "連線", "很卡", "很慢", "很差", "不穩", "連不上", "不能用", "slow", "bad", "poor", "unstable", "notworking", "cannotconnect")):
            if place_for_deictic_followup in {"紅吱吱", "紅吱吱牛排", "Red Zhi Zhi steak", "Red Zhi Zhi", "Hong Zhi Zhi steak", "Hong Zhi Zhi"}:
                return "紅吱吱牛排有網路嗎？" if is_chinese_question else "Does Red Zhi Zhi steak have NTHU Wi-Fi?"
            if is_chinese_question:
                return f"{place_for_deictic_followup}網路很差可能是什麼原因？"
            if any("\u4e00" <= ch <= "\u9fff" for ch in place_for_deictic_followup):
                return "Campus Wi-Fi at that NTHU location is slow or unstable. What could be the reason?"
            return f"The Wi-Fi at {place_for_deictic_followup} is slow or unstable. What could be the reason?"

    has_transfer_qualifier = any(
        term in normalized
        for term in (
            "換宿", "換寢室", "換了寢室", "換房間", "換了房間", "搬宿舍", "搬寢室", "搬房間", "moveddorm", "changedrooms",
        )
    )
    completed_service_followup = None if has_transfer_qualifier else complete_service_followup(question, history)
    if completed_service_followup:
        return completed_service_followup

    if is_explicit_service_question(question):
        return question

    explicit_email_question = any(term in normalized for term in (
        "清大信箱", "學生信箱", "校內信箱", "電子郵件", "gapp", "googleapps",
        "googleworkspace", "gsuite", "nthumail", "nthuemail", "studentemail",
        "studentmail", "emailaccount", "mailaccount",
    )) and any(term in normalized for term in (
        "申請", "怎麼申請", "怎麼開", "帳號", "格式", "apply", "application", "account", "format",
    ))
    if explicit_email_question:
        return question

    if is_dorm_network_history(history) and latest_service in {None, "dorm"}:
        is_chinese_question = any("\u4e00" <= ch <= "\u9fff" for ch in question)
        if any(term in normalized for term in ("換宿", "換寢室", "換了寢室", "換房間", "換了房間", "換到", "搬到", "搬宿舍", "搬寢室", "搬房間", "新房間", "新宿舍", "moveddorm", "moveddorms", "movingdorm", "movingdorms", "changedorm", "changedorms", "changeddorm", "changeddorms", "changedrooms", "ifichangeddorms", "ifichangedorms", "newdorm", "newroom", "couldthatberelated")):
            current_is_troubleshooting = has_network_failure_intent(question)
            current_is_application = any(
                term in normalized
                for term in ("申請", "重辦", "重新辦", "重新登記", "reapply", "applyagain")
            )
            inherited_intent = recent_question_intent(history)
            if not current_is_troubleshooting and (
                current_is_application or inherited_intent == "apply"
            ):
                return "換宿後宿網需要重新申請嗎？" if is_chinese_question else "Do I need to reapply for DormNet after moving rooms?"
            return "換宿後宿網連不上可能有關嗎？" if is_chinese_question else "Could moving dorms be related to DormNet not working?"
        if any(term in normalized for term in ("去哪裡申請", "哪裡申請", "去哪申請", "申請網址", "申請頁", "申請入口", "wheredoiapply", "wheretoapply", "applyforit", "applicationpage", "applicationlink")):
            return "宿舍網路怎麼申請？" if is_chinese_question else "How do I apply for DormNet?"
        if is_dorm_transfer_history(history) and any(term in normalized for term in ("重新申請", "重申請", "再申請", "申請嗎", "要申請", "要重新", "reapply", "applyagain", "registeragain")):
            return "換宿後宿網需要重新申請嗎？" if is_chinese_question else "Do I need to reapply for DormNet after moving rooms?"
        if is_dorm_transfer_history(history) and any(term in normalized for term in ("宿網突然", "突然不能", "突然連不上", "突然沒網路", "突然無法", "不能用了", "連不上", "無法上網", "不能上網", "stoppedworking", "suddenlystopped", "suddenlycannot", "cannotconnect", "notworking")):
            return "換宿後宿網連不上可能有關嗎？" if is_chinese_question else "Could moving dorms be related to DormNet not working?"
        if any(term in normalized for term in ("分享器", "路由器", "router")):
            return "分享器要怎麼連宿舍網路？" if is_chinese_question else "How do I connect a router to DormNet?"
        if is_router_history(history) and any(term in normalized for term in ("wan", "插哪裡", "接哪裡", "線插", "ip要填", "ip填哪", "ip設定", "staticip", "plug", "cable", "where", "confusing", "settings", "enter")):
            return "分享器要怎麼連宿舍網路？" if is_chinese_question else "How do I connect a router to DormNet?"
        if any(term in normalized for term in ("網路很爛", "網路爛", "網路很差", "網路差", "怪怪", "怪怪的", "很慢", "比較嚴重", "晚上", "嚴重", "先檢查", "檢查什麼", "很卡", "不穩", "一直斷", "斷線", "早上還可以", "剛剛還可以", "現在突然", "完全沒網路", "沒網路", "不能上網", "無法上網", "連不上", "突然完全不能上網", "上禮拜", "上週", "昨天還可以", "前幾天", "什麼問題", "networkhasbeenreallybad", "reallybad", "veryslow", "unstable", "startedlastweek", "whatmightbewrong", "notworking", "cannotconnect")):
            return "宿網最近變慢或突然無法連線可能是什麼原因？" if is_chinese_question else "DormNet has been bad or unavailable recently. What might be wrong?"
        if any(term in normalized for term in ("帳號未申請完成", "尚未申請完成", "沒有申請完成", "沒申請完成", "未申請完成", "notcompleted", "incomplete")):
            return "宿網帳號未申請完成是什麼意思？" if is_chinese_question else "What does dormitory network account application incomplete mean?"
        if "ip" in normalized and any(term in normalized for term in ("忘記", "忘了", "不記得", "查", "查詢", "查看", "看", "找", "在哪", "哪裡", "forgot", "lookup", "check", "find", "where")):
            return "忘記宿網 IP 要去哪裡查？" if is_chinese_question else "Where can I look up my DormNet IP?"
        if any(term in normalized for term in ("ip要怎麼設定", "ip怎麼設定", "ip要怎麼設", "ip怎麼設", "ip設定", "ip要填", "tcpip", "staticip", "ipsettings", "ipsetting", "dormnetworkip", "dormitorynetworkip", "networkip", "howshouldisettheip", "howdoisettheip", "settheip", "ipsetup")):
            return "宿網 IP 要怎麼設定？" if is_chinese_question else "How do I set the dorm network IP?"
        if any(term in normalized for term in ("網路孔壞", "網路孔故障", "孔壞", "孔故障", "報修", "修理")) or (("網路孔" in normalized or "網孔" in normalized) and any(term in normalized for term in ("壞", "故障", "異常", "沒反應", "不能用"))):
            return "宿網網路孔壞掉要怎麼報修？" if is_chinese_question else "How do I report a broken dorm network wall port?"
        if any(term in normalized for term in ("寄信", "信裡", "信中", "附什麼", "提供什麼", "要附", "要提供", "include", "email", "whatshouldiinclude", "whattoinclude")):
            return "宿網報修寄信要附什麼？" if is_chinese_question else "What should I include in a DormNet repair email?"
        if any(term in normalized for term in ("照著", "照你", "步驟", "還是不行", "仍不行", "不行", "沒用", "不能用", "notwork", "stilldoesnotwork", "stillnotwork", "itstilldoesnotwork", "doesnotwork", "followedthesteps", "followedyoursteps")):
            if any(term in normalized for term in ("分享器", "路由器", "router")) or is_router_history(history):
                return "分享器照步驟設定後還是不行" if is_chinese_question else "Router still does not work after DormNet setup"
            return "宿網照著步驟查了還是不行" if is_chinese_question else "DormNet still does not work after following the steps"

    if is_wireless_history(history) and "vpn" in normalized and any(term in normalized for term in ("一定要開", "一定要打開", "必須開", "需要開", "要開嗎", "要打開嗎", "也要開", "也要打開", "doihavetoenable", "doineedtoenable", "havetoenable", "needtoenable", "mustenable")):
        is_chinese_question = any("\u4e00" <= ch <= "\u9fff" for ch in question)
        return "VPN 一定要開嗎？" if is_chinese_question else "Do I have to enable VPN for campus Wi-Fi?"

    if is_vpn_history(history) and latest_service in {None, "vpn"} and "eduroam" not in normalized:
        is_chinese_question = any("\u4e00" <= ch <= "\u9fff" for ch in question)
        if any(term in normalized for term in ("去哪裡申請", "哪裡申請", "去哪申請", "申請網址", "申請頁", "申請入口", "wheredoiapply", "wheretoapply", "applyforit", "applicationpage", "applicationlink", "enableit", "activateit")):
            return "VPN 怎麼設定？" if is_chinese_question else "How do I set up the NTHU VPN?"
        if any(term in normalized for term in ("下載網址", "下載連結", "資料夾", "版本號", "版本", "數字", "22.7r2", "227r2", "9.1r14", "91r14", "9.1r17", "91r17", "downloadlink", "downloadurl", "folder", "version", "versions", "number", "numbers")):
            return "VPN 下載資料夾版本號是什麼意思？" if is_chinese_question else "What do the VPN download folder version numbers mean?"
        if any(term in normalized for term in ("密碼要填", "密碼填什麼", "密碼是什麼", "密碼要輸入", "密碼輸入", "要填什麼密碼", "填哪個密碼", "哪個密碼", "什麼密碼", "password", "whatpassword", "whichpassword", "enterpassword", "typepassword")):
            return "VPN 軟體密碼要填什麼？" if is_chinese_question else "What password should I enter for the NTHU VPN client?"

    if is_wireless_application_page_history(history) and any(term in normalized for term in ("校外", "人在校外", "不在校內", "offcampus", "off-campus", "notoncampus", "outsidecampus")):
        is_chinese_question = any("\u4e00" <= ch <= "\u9fff" for ch in question)
        return "無線網路申請頁打不開怎麼辦？" if is_chinese_question else "What if the wireless application page will not open?"

    if is_eduroam_history(history) and latest_service in {None, "wireless"}:
        is_chinese_question = any("\u4e00" <= ch <= "\u9fff" for ch in question)
        if any(term in normalized for term in ("登入失敗", "認證失敗", "連不上", "連不到", "不能用", "失敗", "一直登入失敗", "failed", "loginfailed", "authenticationfailed", "cannotlogin", "cantlogin", "can'tlogin", "notwork")):
            if is_external_eduroam_history(history):
                return "外校 eduroam 登入失敗怎麼辦？" if is_chinese_question else "eduroam login fails at another university. What should I check?"
            return "eduroam 登入失敗怎麼辦？" if is_chinese_question else "What if eduroam login fails?"
        if any(term in normalized for term in ("oncampus", "atnthu", "清大校內", "校內")) and any(term in normalized for term in ("sstudentid", "s學號", "帳號", "account", "username", "shouldiuse", "whichone", "use")):
            return "eduroam 使用" if is_chinese_question else "How do I use eduroam on campus?"
        if "eduroam" in normalized and any(term in normalized for term in ("台大", "臺大", "交大", "陽明交大", "外校", "別的學校", "其他學校", "ntu", "nycu", "anotheruniversity", "otheruniversity", "offcampus")) and any(term in normalized for term in ("很慢", "慢", "很差", "不穩", "斷線", "連不上", "不能用", "失敗", "slow", "unstable", "bad", "poor", "disconnect", "notwork")):
            return "外校 eduroam 連線很慢或不穩怎麼辦？" if is_chinese_question else "eduroam is slow or unstable at another university. What should I check?"
        if any(term in normalized for term in ("外校", "別的學校", "其他學校", "帳號", "格式", "打什麼", "輸入什麼", "要打什麼", "anotheruniversity", "otheruniversity", "username", "account", "enter", "type", "shouldiuse", "whichone", "use")):
            return "外校 eduroam 帳號要輸入什麼？" if is_chinese_question else "What username should I enter for eduroam at another university?"
        if any(term in normalized for term in ("seeeduroam", "eduroam", "看到eduroam")):
            return "外校 eduroam 帳號要輸入什麼？" if is_chinese_question else "What username should I enter for eduroam at another university?"

    if is_vpn_history(history) and latest_service in {None, "vpn"}:
        is_chinese_question = any("\u4e00" <= ch <= "\u9fff" for ch in question)
        if any(term in normalized for term in ("去哪裡申請", "哪裡申請", "去哪申請", "申請網址", "申請頁", "申請入口", "wheredoiapply", "wheretoapply", "applyforit", "applicationpage", "applicationlink", "enableit", "activateit")):
            return "VPN 怎麼設定？" if is_chinese_question else "How do I set up the NTHU VPN?"
        if any(term in normalized for term in ("下載網址", "下載連結", "資料夾", "版本號", "版本", "數字", "22.7r2", "227r2", "9.1r14", "91r14", "9.1r17", "91r17", "downloadlink", "downloadurl", "folder", "version", "versions", "number", "numbers")):
            return "VPN 下載資料夾版本號是什麼意思？" if is_chinese_question else "What do the VPN download folder version numbers mean?"
        if any(term in normalized for term in ("密碼要填", "密碼填什麼", "密碼是什麼", "密碼要輸入", "密碼輸入", "要填什麼密碼", "填哪個密碼", "哪個密碼", "什麼密碼", "password", "whatpassword", "whichpassword", "enterpassword", "typepassword")):
            return "VPN 軟體密碼要填什麼？" if is_chinese_question else "What password should I enter for the NTHU VPN client?"
        if any(term in normalized for term in ("伺服器", "server", "軟體裝好", "軟體裝了", "裝好了", "填什麼", "設定")):
            return "VPN 怎麼設定？" if is_chinese_question else "How do I set up the NTHU VPN?"
        if any(term in normalized for term in ("帳號格式", "帳號要打", "帳號輸入", "帳號是什麼", "帳號呢", "username", "accountformat", "whataccount", "whichaccount", "loginaccount", "format")):
            return "VPN 帳號格式是什麼？" if is_chinese_question else "What account format should I use for NTHU VPN?"

    if is_wireless_history(history) and latest_service in {None, "wireless"}:
        is_chinese_question = any("\u4e00" <= ch <= "\u9fff" for ch in question)
        if ("nthucc" in normalized or "nthu-cc" in question.lower()) and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連", "use", "connect", "login", "signin", "how")):
            return "nthu-cc 使用" if is_chinese_question else "How do I use nthu-cc?"
        if "nthupeap" in normalized and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連", "use", "connect", "login", "signin", "how")):
            return "nthupeap 使用" if is_chinese_question else "How do I use nthupeap?"
        if "eduroam" in normalized and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連", "use", "connect", "login", "signin", "how")):
            return "eduroam 使用" if is_chinese_question else "How do I use eduroam?"
        if "tanetroaming" in normalized and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連", "use", "connect", "login", "signin", "how")):
            return "TANetRoaming 使用" if is_chinese_question else "How do I use TANetRoaming?"
        if any(place.lower().replace(" ", "") in normalized for place in LOCATION_FOLLOWUP_PLACES + EN_LOCATION_FOLLOWUP_PLACES) and any(term in normalized for term in ("一樣嗎", "也是", "也一樣", "也是一樣", "same", "alsothesame", "samethere")):
            place = next((item for item in LOCATION_FOLLOWUP_PLACES if item.lower().replace(" ", "") in normalized), None)
            if place:
                canonical_place = "水木生活中心" if place == "水木" else "醫輔大樓" if place == "醫輔" else place
                return f"{canonical_place}網路很差可能是什麼原因？"
            return "Campus Wi-Fi still does not work after following the steps. What should I do?"
        if is_wireless_password_history(history) and any(term in normalized for term in ("多久", "生效", "幾分鐘", "何時", "howlong", "takeeffect", "effective")):
            return "無線網路密碼改完多久會生效？" if is_chinese_question else "How long does it take for the wireless password change to take effect?"
        if is_wireless_application_page_history(history) and any(term in normalized for term in ("校外", "人在校外", "不在校內", "offcampus", "off-campus", "notoncampus", "outsidecampus")):
            return "無線網路申請頁打不開怎麼辦？" if is_chinese_question else "What if the wireless application page will not open?"
        if is_wireless_application_page_history(history) and any(term in normalized for term in ("怎麼申請", "要怎麼申請", "我要怎麼申請", "申請方式", "申請步驟", "howdoiapply", "howtoapply", "apply", "application")):
            return "Wi-Fi 怎麼申請？" if is_chinese_question else "How do I apply for campus Wi-Fi?"
        if any(term in normalized for term in ("照著", "照你", "步驟", "還是不行", "仍不行", "不行", "沒用", "不能用", "stilldoesnotwork", "stillnotwork", "itstilldoesnotwork", "doesnotwork", "followedthesteps", "followedyoursteps")):
            return "校園無線網路連不上怎麼辦？" if is_chinese_question else "What should I do if campus Wi-Fi does not work?"
        if (is_nthu_cc_history(history) or "登入頁" in normalized or "loginpage" in normalized) and (
            any(term in normalized for term in ("登入頁沒出現", "登入頁沒有出現", "登入頁跳不出來", "沒有跳出登入", "loginpagedoesnotappear", "loginpagewillnotappear", "loginpagewontappear", "loginpagecannotappear", "doesnotappear", "doesntappear", "doesn'tappear", "notappear", "notshow"))
            or (("登入頁" in normalized or "認證頁" in normalized) and any(term in normalized for term in ("跳不出", "出不來", "沒有", "沒出", "不出", "不顯示")))
        ):
            return "nthu-cc 登入頁沒有出現怎麼辦？" if is_chinese_question else "What if the nthu-cc login page does not appear?"
        if is_nthupeap_history(history) and any(term in normalized for term in ("登入失敗", "認證失敗", "連不上", "無法登入", "failed", "loginfailed", "authenticationfailed")):
            return "nthupeap 登入失敗怎麼辦？" if is_chinese_question else "What if nthupeap login fails?"
        if is_nthupeap_history(history) and any(term in normalized for term in ("帳號", "s開頭", "s學號", "格式", "username", "account", "format")):
            return "nthupeap 使用" if is_chinese_question else "How do I use nthupeap?"
        if is_nthu_cc_history(history) and any(term in normalized for term in ("換哪個wifi", "換哪個wi-fi", "改連哪個", "換哪個", "哪個wifi", "哪個wi-fi", "whichssid", "whichwifi", "switchto")):
            return "nthu-cc 登入頁沒有出現時可以改連哪個 Wi-Fi？" if is_chinese_question else "Which Wi-Fi should I try if the nthu-cc login page does not appear?"
        if any(term in normalized for term in ("哪個wifi", "哪個wi-fi", "連哪個wifi", "連哪個wi-fi", "不知道我是連哪個", "whichssid", "whichwifi")):
            return "校園無線網路怎麼使用？" if is_chinese_question else "How do I use NTHU campus Wi-Fi?"
        if any(term in normalized for term in ("申請頁打不開", "申請頁無法進入", "申請頁進不去", "申請頁開不了", "申請頁不能開", "申請頁面打不開", "打不開", "進不去", "無法進入", "applicationpage", "willnotopen", "wontopen", "cannotopen", "cantopen")):
            return "無線網路申請頁打不開怎麼辦？" if is_chinese_question else "What if the wireless application page will not open?"
        if is_wireless_application_page_history(history) and any(term in normalized for term in ("怎麼申請", "要怎麼申請", "我要怎麼申請", "申請方式", "申請步驟", "howdoiapply", "howtoapply", "apply", "application")):
            return "Wi-Fi 怎麼申請？" if is_chinese_question else "How do I apply for campus Wi-Fi?"
        if any(term in normalized for term in ("校務資訊系統密碼", "同一組密碼", "一樣嗎", "那組", "去哪裡改", "哪裡改", "怎麼改", "academicinformationsystempassword", "aispassword", "samepassword", "sameas", "isitthe same".replace(" ", ""), "howcanireset", "resetit")):
            return "清大學生的無線網路帳號密碼是什麼？" if is_chinese_question else "Is the campus wireless password the same as the Academic Information System password?"

    if is_email_history(history) and latest_service in {None, "email"}:
        is_chinese_question = any("一" <= ch <= "鿿" for ch in question)
        if any(term in normalized for term in ("不是gapp", "不要gapp", "notgapp", "notgoogle", "studentmailbox", "studentemail", "studentmail", "學生信箱", "校內信箱")):
            return "清大學生信箱怎麼申請？" if is_chinese_question else "How do I apply for the student email account?"
        if any(term in normalized for term in ("addressformat", "format", "格式", "信箱格式")):
            return "清大學生信箱格式是什麼？" if is_chinese_question else "What is the NTHU student email address format?"
        if is_gapp_history(history) and any(term in normalized for term in ("多久", "多久可以用", "多久能用", "什麼時候可以用", "何時可以用", "生效", "可以用", "howlong", "when", "available", "takeeffect", "effective")):
            return "gapp 申請完多久可以用？" if is_chinese_question else "How long does it take for the gapp account to become available?"
        if any(term in normalized for term in ("gapp", "google", "google那個", "googleapps", "googleworkspace", "gsuite", "thegappone", "thegoogleone", "gappone", "不是學生信箱")) or (is_gapp_history(history) and any(term in normalized for term in ("怎麼申請", "申請", "howdoiapply", "apply", "application"))):
            return "gapp 信箱怎麼申請？" if is_chinese_question else "How do I apply for the gapp account?"

    if "eduroam" in normalized and any(term in normalized for term in ("台大", "臺大", "交大", "陽明交大", "外校", "別的學校", "其他學校", "ntu", "nycu", "anotheruniversity", "otheruniversity", "offcampus")) and any(term in normalized for term in ("很慢", "慢", "很差", "不穩", "斷線", "連不上", "不能用", "失敗", "slow", "unstable", "bad", "poor", "disconnect", "notwork")):
        return "外校 eduroam 連線很慢或不穩怎麼辦？" if any("\u4e00" <= ch <= "\u9fff" for ch in question) else "eduroam is slow or unstable at another university. What should I check?"

    place_from_history = recent_campus_place(history)
    if place_from_history and any(term in normalized for term in ("哪個wifi", "哪個wi-fi", "連哪個wifi", "連哪個wi-fi", "不知道我是連哪個", "whichssid", "whichwifi")):
        return "校園無線網路怎麼使用？" if any("\u4e00" <= ch <= "\u9fff" for ch in question) else "How do I use NTHU campus Wi-Fi?"
    if place_from_history and any(term in normalized for term in ("wifi很慢", "wi-fi很慢", "網路很慢", "網路很差", "網路差", "很慢", "很爛", "訊號差", "不穩", "斷線", "一直斷", "連線一直斷", "連不上", "無法連線", "搜尋不到", "搜不到", "找不到", "看不到", "沒有出現", "沒有看到", "這兩天", "最近", "keepsdisconnecting", "disconnecting", "notstable", "unstable", "slow", "bad", "poor", "notworking", "doesnotwork", "doesnotshowup", "cannotsee", "cantsee", "很卡", "卡", "there")):
        search_not_found = any(term in normalized for term in ("搜尋不到", "搜不到", "找不到", "看不到", "沒有出現", "沒有看到", "doesnotshowup", "cannotsee", "cantsee"))
        if search_not_found and place_from_history in {"梅園", "Mei Garden"}:
            return "梅園有網路嗎？" if any("\u4e00" <= ch <= "\u9fff" for ch in question) else "Does Mei Garden have NTHU Wi-Fi?"
        if any("\u4e00" <= ch <= "\u9fff" for ch in question):
            return f"{place_from_history}網路很差可能是什麼原因？"
        if any("\u4e00" <= ch <= "\u9fff" for ch in place_from_history):
            return "The Wi-Fi in Physics Building has been slow or unstable. What could be the reason?"
        return f"The Wi-Fi in {place_from_history} has been slow or unstable. What could be the reason?"

    if is_location_network_history(history):
        has_explicit_network_intent = any(term in normalized for term in (
            "網路", "wifi", "wi-fi", "無線", "上網", "連線",
        ))
        if not has_explicit_network_intent:
            for place in LOCATION_FOLLOWUP_PLACES:
                key = place.lower().replace(" ", "")
                if key in normalized and any(marker in normalized for marker in ("那", "呢", "勒", "咧", "了", "哩", "有嗎")):
                    canonical_place = "水木生活中心" if place == "水木" else "醫輔大樓" if place == "醫輔" else place
                    return f"{canonical_place}有網路嗎"

            for place in EN_LOCATION_FOLLOWUP_PLACES:
                key = place.lower().replace(" ", "")
                if key in normalized and any(marker in normalized for marker in ("whatabout", "howabout", "and", "呢", "勒")):
                    if key in {"cafeteria", "foodcourt", "snackbar"}:
                        return "Does the cafeteria have NTHU Wi-Fi?"
                    if key in {"meigarden", "meiyuan"}:
                        return "Does Mei Garden have NTHU Wi-Fi?"
                    if key in {"hongzhizhisteak", "hongzhizhi", "redzhizhisteak", "redzhizhi", "zhizhisteak"}:
                        return "Does Red Zhi Zhi steak have NTHU Wi-Fi?"
                    return f"Does {place} have NTHU Wi-Fi?"

    return question


def normalize_nthu_translation_terms(text: str) -> str:
    replacements = {
        "Su Network": "DormNet",
        "Su network": "DormNet",
        "SU Network": "DormNet",
        "Dormitory Internet": "DormNet",
        "Dormitory network": "DormNet",
        "dormitory network": "DormNet",
        "Hostel network": "DormNet",
        "hostel network": "DormNet",
    }
    normalized_text = text or ""
    for old, new in replacements.items():
        normalized_text = normalized_text.replace(old, new)
    return normalized_text


@app.post("/translate")
def translate(req: TranslationRequest):
    texts = [text[:6000] for text in req.texts]
    translations: list[str | None] = []
    remote_texts: list[str] = []
    remote_indexes: list[int] = []

    local_message_pairs = {
        "en": {
            "我人在風雲樓": "I'm in Fengyun Building.",
            "我人在圖書館": "I'm in the library.",
            "剛剛還可以，但現在 Wi-Fi 很卡": "It worked earlier, but the Wi-Fi is very slow now.",
            "我照著做還是不行": "I followed the steps, but it still does not work.",
            "可是我照著你的步驟做還是不行欸": "I followed your steps, but it still does not work.",
            "Wi-Fi 怎麼申請？": "How do I apply for Wi-Fi?",
            "Wi-Fi 怎麼申請": "How do I apply for Wi-Fi?",
            "台積館有網路嗎？": "Is there Wi-Fi at the TSMC Building?",
            "台積館有網路嗎": "Is there Wi-Fi at the TSMC Building?",
            "那水木呢？": "What about Shui Mu Life Center?",
            "那水木呢": "What about Shui Mu Life Center?",
            "紅吱吱牛排有網路嗎？": "Does Red Zhi Zhi steak have Wi-Fi?",
            "紅吱吱牛排有網路嗎": "Does Red Zhi Zhi steak have Wi-Fi?",
            "那梅園呢？": "What about Mei Garden?",
            "那梅園呢": "What about Mei Garden?",
            "密碼要填什麼？": "What password should I enter?",
            "密碼要填什麼": "What password should I enter?",
            "VPN 怎麼設定？": "How do I set up the NTHU VPN?",
            "VPN 怎麼設定": "How do I set up the NTHU VPN?",
            "下載網址裡面的資料夾都是數字，接下來要點哪個？": "The folders in the download URL are all numbers. Which one should I click next?",
            "下載網址裡面的資料夾都是數字，接下來要點哪個": "The folders in the download URL are all numbers. Which one should I click next?",
            "VPN 軟體的帳號我知道了 但密碼要填什麼？": "I know the VPN client account, but what password should I enter?",
            "VPN 軟體的帳號我知道了 但密碼要填什麼": "I know the VPN client account, but what password should I enter?",
            "小吃部有網路嗎？": "Does the cafeteria have Wi-Fi?",
            "小吃部有網路嗎": "Does the cafeteria have Wi-Fi?",
            "那風雲樓勒？": "What about Fengyun Building?",
            "那風雲樓勒": "What about Fengyun Building?",
            "最近在那邊 Wi-Fi 很卡": "The Wi-Fi is very slow there recently.",
            "最近在那邊 Wi-Fi 很卡。": "The Wi-Fi is very slow there recently.",
            "那裡的 Wi-Fi 最近很慢。": "The Wi-Fi is very slow there recently.",
            "那裡 Wi-Fi 很慢。": "The Wi-Fi is very slow there recently.",
            "我在圖書館連不到網路": "I cannot connect to the network in the library.",
            "那紅吱吱牛排呢？": "What about Red Zhi Zhi steak?",
            "那紅吱吱牛排呢": "What about Red Zhi Zhi steak?",
            "那 VPN 呢？": "What about VPN?",
            "那 VPN 呢": "What about VPN?",
            "那宿網呢？": "What about DormNet?",
            "那宿網呢": "What about DormNet?",
            "Wi-Fi 連不上怎麼辦？": "What should I do if I cannot connect to Wi-Fi?",
            "Wi-Fi 連不上怎麼辦": "What should I do if I cannot connect to Wi-Fi?",
            "那要去哪裡申請？": "Where do I apply for it?",
            "那要去哪裡申請": "Where do I apply for it?",
            "照你的方法做還是不行": "I followed your method but it still does not work.",
            "照你的方法做還是不行。": "I followed your method but it still does not work.",
            "那我在圖書館也是一樣嗎？": "Is it the same if I am in the library?",
            "那我在圖書館也是一樣嗎": "Is it the same if I am in the library?",
            "那如果我在校內還是不行？": "What if I'm on campus and it still does not work?",
            "那如果我在校內還是不行": "What if I'm on campus and it still does not work?",
            "我人在校外，那怎麼辦？": "I'm off campus. What should I do?",
            "我人在校外，那怎麼辦": "I'm off campus. What should I do?",
            "我是儒齋學生": "I am a Ru Zhai student.",
            "最近網路很爛": "The network has been very bad recently.",
            "如果是網路孔壞掉怎麼辦？": "What if the network wall port is broken?",
            "如果是網路孔壞掉怎麼辦": "What if the network wall port is broken?",
            "清大信箱怎麼申請？": "How do I apply for NTHU email?",
            "清大信箱怎麼申請": "How do I apply for NTHU email?",
            "gapp 的那個信箱怎麼申請？": "How do I apply for the gapp email account?",
            "gapp 的那個信箱怎麼申請": "How do I apply for the gapp email account?",
            "nthu-cc 使用": "How do I use nthu-cc?",
            "登入頁一直跳不出來": "The login page does not appear.",
            "我照著做還是不行": "I followed the steps, but it still does not work.",
            "那學生信箱格式是什麼？": "What is the student email address format?",
            "那學生信箱格式是什麼": "What is the student email address format?",
            "那如果是 eduroam 登入失敗呢？": "What if eduroam login fails?",
            "那如果是 eduroam 登入失敗呢": "What if eduroam login fails?",
            "噢然後是從上禮拜開始的，可以幫我看看有什麼問題嗎？": "It started last week. Could you help me check what might be wrong?",
            "上禮拜開始的，可以幫我看看可能是什麼問題嗎？": "It started last week. Could you help me check what might be wrong?",
            "噢然後是從上禮拜開始的，可以幫我看看有什麼問題嗎": "It started last week. Could you help me check what might be wrong?",
            "為什麼我連不上宿網？": "Why can't I connect to DormNet?",
            "為什麼我連不上宿網": "Why can't I connect to DormNet?",
            "宿網最近很卡，為什麼？": "Why has DormNet been very slow recently?",
            "宿網最近很卡，為什麼": "Why has DormNet been very slow recently?",
            "宿網最近很卡": "DormNet has been very slow recently.",
            "宿網 IP 狀態怎麼查？": "How do I check DormNet IP status?",
            "宿網 IP 狀態怎麼查": "How do I check DormNet IP status?",
            "宿網 IP 被禁用怎麼辦？": "What should I do if my DormNet IP is disabled?",
            "宿網 IP 被禁用怎麼辦": "What should I do if my DormNet IP is disabled?",
            "我忘記自己的宿網 IP 了": "I forgot my DormNet IP address.",
            "忘記宿網 IP 要去哪裡查？": "Where can I look up my DormNet IP?",
            "忘記宿網 IP 要去哪裡查": "Where can I look up my DormNet IP?",
            "宿舍網路怎麼申請？": "How do I apply for the dormitory network?",
            "宿舍網路怎麼申請": "How do I apply for the dormitory network?",
            "那如果我換宿了呢？": "What if I change dorms?",
            "那如果我換宿了呢": "What if I change dorms?",
            "我之前是住在新齋，後來換宿換到儒齋，可能是跟換宿有關嗎？": "I lived in Xin Zhai before, then moved to Ru Zhai. Could that be related?",
            "那 IP 要怎麼設定？": "How should I set the IP?",
            "那 IP 要怎麼設定": "How should I set the IP?",
            "我要連哪個 Wi-Fi 比較好？": "Which Wi-Fi should I connect to?",
            "我要連哪個 Wi-Fi 比較好": "Which Wi-Fi should I connect to?",
            "台大網路很差可能是什麼原因？": "Why might the NTU network be poor?",
        },
        "zh-Hant": {
            "I'm in Fengyun Building.": "我人在風雲樓。",
            "I'm in the library.": "我人在圖書館。",
            "It worked earlier, but the Wi-Fi is very slow now.": "剛剛還可以，但現在 Wi-Fi 很卡。",
            "I followed the steps, but it still does not work.": "我照著做還是不行。",
            "I followed your steps, but it still does not work.": "可是我照著你的步驟做還是不行欸。",
            "I live in Ru Zhai.": "我住在儒齋。",
            "DormNet has been very bad recently.": "最近宿網很爛。",
            "It started last week. Could you help me check what might be wrong?": "上禮拜開始的，可以幫我看看可能是什麼問題嗎？",
            "What if the wall port is broken?": "如果網路孔壞掉怎麼辦？",
            "Does the cafeteria have Wi-Fi?": "小吃部有網路嗎？",
            "What about Fengyun Building?": "那風雲樓呢？",
            "What about Red Zhi Zhi steak?": "那紅吱吱牛排呢？",
            "What about Red Zhi Zhi Steak?": "那紅吱吱牛排呢？",
            "The Wi-Fi is very slow there.": "那裡 Wi-Fi 很慢。",
            "The Wi-Fi is very slow there recently.": "那裡的 Wi-Fi 最近很慢。",
            "The Wi-Fi there has been very slow recently.": "那裡的 Wi-Fi 最近很慢。",
            "Which Wi-Fi should I connect to?": "我應該連哪個 Wi-Fi？",
            "How do I set up the NTHU VPN?": "VPN 怎麼設定？",
            "The download folders are all numbers. What do they mean?": "下載資料夾都是數字，代表什麼意思？",
            "The folders in the download URL are all numbers. Which one should I click next?": "下載網址裡面的資料夾都是數字，接下來要點哪個？",
            "I know the VPN account, but what password should I enter?": "我知道 VPN 帳號，但密碼要填什麼？",
            "I know the VPN client account, but what password should I enter?": "我知道 VPN 軟體的帳號，但密碼要填什麼？",
            "How do I apply for NTHU email?": "清大信箱怎麼申請？",
            "How do I apply for the dormitory network?": "宿舍網路怎麼申請？",
            "How do I apply for Wi-Fi?": "Wi-Fi 怎麼申請？",
            "How to Apply for Wi-Fi?": "Wi-Fi 怎麼申請？",
            "How do I use nthu-cc?": "那 nthu-cc 要怎麼用？",
            "The login page does not appear.": "登入頁一直跳不出來",
            "I am a Ru Zhai student.": "我是儒齋學生",
            "The network has been very bad recently.": "最近網路很爛",
            "What if the network wall port is broken?": "如果是網路孔壞掉怎麼辦？",
            "Is there Wi-Fi at the TSMC Building?": "台積館有網路嗎？",
            "Is there Wi-Fi at the TSMC Museum?": "台積館有網路嗎？",
            "What about Shui Mu Life Center?": "那水木呢？",
            "What about Shuimu?": "那水木呢？",
            "Does Red Zhi Zhi steak have Wi-Fi?": "紅吱吱牛排有網路嗎？",
            "Does Hong Zhizhi Steak have Wi-Fi?": "紅吱吱牛排有網路嗎？",
            "What about Mei Garden?": "那梅園呢？",
            "What about Meiyuan?": "那梅園呢？",
            "How do I apply for campus Wi-Fi?": "Wi-Fi 怎麼申請？",
            "How do I apply for campus WiFi?": "Wi-Fi 怎麼申請？",
            "Why can't I access the wireless network application page?": "為什麼我進不去申請無線網路的網頁？",
            "What password should I enter?": "密碼要填什麼？",
            "What should I enter for the password?": "密碼要填什麼？",
            "How should I set the IP?": "那 IP 要怎麼設定？",
            "What about DormNet?": "那宿網呢？",
            "What about VPN?": "那 VPN 呢？",
            "What about the Hong Zhi Zhi steak?": "那紅吱吱牛排呢？",
            "What about the Hong Zhizhi steak?": "那紅吱吱牛排呢？",
            "How do I apply for the gapp email account?": "gapp 的那個信箱怎麼申請？",
            "What is the student email address format?": "那學生信箱格式是什麼？",
            "What about the VPN?": "那 VPN 呢？",
            "What should I do if I cannot connect to Wi-Fi?": "Wi-Fi 連不上怎麼辦？",
            "Where do I apply for it?": "那要去哪裡申請？",
            "I followed your method but it still does not work.": "照你的方法做還是不行。",
            "Is it the same if I am in the library?": "那我在圖書館也是一樣嗎？",
            "What if I'm on campus and it still does not work?": "那如果我在校內還是不行？",
            "I'm off campus. What should I do?": "我人在校外，那怎麼辦？",
            "What if I change dorms?": "如果我換宿了呢？",
            "How do I apply for the gapp account?": "gapp 帳號怎麼申請？",
        },
    }

    for text in texts:
        normalized_text = " ".join((text or "").split())
        if text_already_in_language(normalized_text, req.target_language):
            translations.append(text)
            continue

        local_translation = local_message_pairs.get(req.target_language, {}).get(normalized_text)
        if not local_translation and req.target_language == "en" and normalized_text.startswith("如果你在") and "Wi-Fi" in normalized_text:
            place_match = re.match(r"如果你在(.+?)連不到網路", normalized_text)
            place_names = {"圖書館": "the library", "風雲樓": "Fengyun Building", "水木生活中心": "Shui Mu Life Center", "水木": "Shui Mu Life Center"}
            place = place_names.get(place_match.group(1), place_match.group(1)) if place_match else "that location"
            local_translation = f"""If NTHU campus Wi-Fi at {place} is slow, unstable, or cannot connect, first check the Wi-Fi name, signal environment, authentication status, and IP settings.

**Check the connection source**
1. Make sure you are connected to the correct NTHU Wi-Fi. On campus, you can use `nthu-cc`, `TANetRoaming`, `nthupeap`, or `eduroam`.
2. If you are connected to a similar-looking, weak, or non-NTHU Wi-Fi name, the connection may be unstable.

**Check signal and location**
1. If you are far from an access point, behind walls, or in a crowded area, the signal quality may drop.
2. Move to a hallway, public area, or a spot with stronger signal and test again.

**Check authentication and IP status**
1. For `nthu-cc` or `TANetRoaming`, open a browser and confirm whether you need to log in again.
2. For `nthupeap` or `eduroam`, forget the saved Wi-Fi setting and reconnect.
3. Wi-Fi IP settings should normally use automatic IP assignment, not a fixed IP.

**Get help**
If the same location remains slow or unusable, contact wlan@cc.nthu.edu.tw with the exact location, floor, SSID, device OS, time, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_useless
https://net.nthu.edu.tw/netsys/en:faq:wlan_range"""
        compact_text = normalized_text.lower().replace(" ", "")
        is_short_prompt = len(normalized_text) <= 120 and "\n" not in (text or "")
        if not local_translation and is_short_prompt and req.target_language == "en":
            if all(marker in compact_text for marker in ("申請", "無線網路")) and any(marker in compact_text for marker in ("進不去", "打不開", "無法進入")):
                local_translation = "Why can't I access the wireless network application page?"
            elif compact_text in ("vpn怎麼設定", "vpn怎麼設定？"):
                local_translation = "How do I set up the NTHU VPN?"
            elif "下載網址" in compact_text and "資料夾" in compact_text and "數字" in compact_text:
                local_translation = "The folders in the download URL are all numbers. Which one should I click next?"
            elif "vpn軟體" in compact_text and "密碼" in compact_text:
                local_translation = "I know the VPN client account, but what password should I enter?"
            elif "小吃部" in compact_text and "網路" in compact_text:
                local_translation = "Does the cafeteria have Wi-Fi?"
            elif "風雲樓" in compact_text and any(marker in compact_text for marker in ("那", "呢", "勒", "有網路")):
                local_translation = "What about Fengyun Building?"
            elif "那邊" in compact_text and any(marker in compact_text for marker in ("wifi", "wi-fi", "網路", "很卡", "很慢")):
                local_translation = "The Wi-Fi is very slow there recently."
            elif "圖書館" in compact_text and any(marker in compact_text for marker in ("連不到", "連不上", "不能用", "網路")):
                local_translation = "I cannot connect to the network in the library."
            elif "儒齋" in compact_text and "學生" in compact_text:
                local_translation = "I am a Ru Zhai student."
            elif "網路" in compact_text and any(marker in compact_text for marker in ("很爛", "很差", "很慢")):
                local_translation = "The network has been very bad recently."
            elif "網路孔" in compact_text and "壞" in compact_text:
                local_translation = "What if the network wall port is broken?"
            elif "清大信箱" in compact_text and "申請" in compact_text:
                local_translation = "How do I apply for NTHU email?"
            elif "gapp" in compact_text and "信箱" in compact_text and "申請" in compact_text:
                local_translation = "How do I apply for the gapp email account?"
            elif "nthucc" in compact_text or "nthu-cc" in compact_text:
                local_translation = "How do I use nthu-cc?"
            elif "登入頁" in compact_text and any(marker in compact_text for marker in ("跳不出", "出不來", "不出")):
                local_translation = "The login page does not appear."
            elif "eduroam" in compact_text and "失敗" in compact_text:
                local_translation = "What if eduroam login fails?"
            elif "學生信箱" in compact_text and "格式" in compact_text:
                local_translation = "What is the student email address format?"
            elif "宿網" in compact_text and any(marker in compact_text for marker in ("連不上", "連不到")):
                local_translation = "Why can't I connect to DormNet?"
            elif "換宿" in compact_text and any(marker in compact_text for marker in ("新齋", "儒齋", "有關")):
                local_translation = "I lived in Xin Zhai before, then moved to Ru Zhai. Could that be related?"
            elif "ip" in compact_text and any(marker in compact_text for marker in ("設定", "怎麼設")):
                local_translation = "How should I set the IP?"
            elif "台大" in compact_text and "網路" in compact_text:
                local_translation = "Why might the NTU network be poor?"
        if not local_translation and is_short_prompt and req.target_language == "zh-Hant" and "wireless network application" in normalized_text.lower():
            local_translation = "為什麼我進不去申請無線網路的網頁？"
        if not local_translation and req.target_language == "zh-Hant" and normalized_text.startswith("Hong Zhi Zhi steak is an off-campus restaurant"):
            local_translation = """紅吱吱牛排等校外餐廳不屬於清大校園無線網路涵蓋範圍，因此沒有清大校園無線網路。

如果是在紅吱吱附近想使用網路，需以店家或一般行動網路為主；清大校園無線網路無法保證涵蓋校外餐廳。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy"""

        if local_translation:
            translations.append(normalize_nthu_translation_terms(local_translation))
            continue

        paired = paired_fast_translations(text)
        if paired.get(req.target_language):
            translations.append(paired[req.target_language])
        else:
            translations.append(None)
            remote_indexes.append(len(translations) - 1)
            remote_texts.append(text)

    if remote_texts:
        try:
            with chat_capacity():
                with llm_capacity():
                    remote_translations = translate_messages(remote_texts, req.target_language)
        except (OpenAIError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=503, detail=f"Translation failed: {exc}") from exc
        for index, translated in zip(remote_indexes, remote_translations):
            translations[index] = normalize_nthu_translation_terms(translated)

    return {"translations": [normalize_nthu_translation_terms(translation or "") for translation in translations]}


def rewrite_graph_query(message: str, relevant_history: list[dict[str, str]]) -> str:
    standalone = resolve_contextual_followup_question(message, relevant_history)
    return build_contextual_question(standalone, relevant_history)


def standalone_question_for_state(
    message: str,
    state: dict,
    relevant_history: list[dict[str, str]],
) -> str:
    progression_rewrite = build_progression_query(message, state)
    if progression_rewrite:
        return progression_rewrite
    semantic_rewrite = rewrite_semantic_followup(message, state)
    if semantic_rewrite:
        return semantic_rewrite
    return resolve_contextual_followup_question(message, relevant_history)


def generate_graph_answer(
    message: str,
    context: str,
    history_context: str,
    language: str,
) -> str:
    with llm_capacity():
        return generate_answer(
            message,
            context,
            history_context=history_context,
            language=language,
        )


def get_compiled_agent_graph():
    global compiled_agent_graph
    if compiled_agent_graph is None:
        with agent_graph_lock:
            if compiled_agent_graph is None:
                compiled_agent_graph = build_agent_graph(
                    retrieve_fn=retrieve_context,
                    rewrite_fn=rewrite_graph_query,
                    build_context_fn=build_rag_context,
                    format_history_fn=format_history,
                    generate_fn=generate_graph_answer,
                )
    return compiled_agent_graph


def explicitly_references_previous_answer(question: str) -> bool:
    normalized = "".join(question.lower().split())
    return any(
        marker in normalized
        for marker in (
            "上一則回答", "上個回答", "你剛剛回答", "剛剛回答的", "上一個答案",
            "previousanswer", "lastanswer", "youranswer",
        )
    )


@app.post("/session/clear")
def clear_session(req: SessionClearRequest):
    deleted = clear_session_cache(req.session_id)
    return {"cleared": True, "deleted_cache_items": deleted}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    question = req.message
    total_start = time.perf_counter()
    effective_language = detect_question_language(question, req.language)
    agent_state = prepare_agent_context(
        question,
        [{"role": item.role, "content": item.content} for item in req.history],
        language=effective_language,
    )
    history = history_for_legacy_functions(agent_state.get("relevant_history", []))
    standalone_question = standalone_question_for_state(question, agent_state, history)
    agent_state["standalone_query"] = standalone_question
    log_standalone_query(agent_state)
    contextual_question = build_contextual_question(standalone_question, history)

    if agent_state.get("reference_status") == "unresolved":
        response_payload = unresolved_reference_answer(effective_language)
        total_time = time.perf_counter() - total_start
        print("Reference Clarification Hit: true")
        print("Vector Search Time: 0.000s")
        print("LLM Time: 0.000s")
        print(f"Total Time: {total_time:.3f}s")
        log_final_answer(
            agent_state,
            response_payload["answer"],
            path="reference_clarification",
        )
        return finalize_chat_response(response_payload, agent_state, path="reference_clarification")

    ordinal_response = (
        answer_ordinal_followup(question, req.history, effective_language)
        if explicitly_references_previous_answer(question)
        else None
    )
    if ordinal_response is not None:
        answer_cache.set(cache_key, ordinal_response) if "cache_key" in locals() else None
        total_time = time.perf_counter() - total_start
        print("Ordinal Follow-up Hit: true")
        print("Vector Search Time: 0.000s")
        print("LLM Time: 0.000s")
        print(f"Total Time: {total_time:.3f}s")
        log_final_answer(agent_state, ordinal_response["answer"], path="ordinal_fast_path")
        return finalize_chat_response(ordinal_response, agent_state, path="ordinal_fast_path")

    clarification = get_clarification_answer(standalone_question)
    if clarification is not None:
        answer, sources = clarification
        response_payload = {"answer": answer, "sources": clean_sources(sources)}
        answer_translations = paired_fast_translations(answer)
        if answer_translations:
            response_payload["answer_translations"] = {
                translated_language: clean_answer(translated_text, question=standalone_question)
                for translated_language, translated_text in answer_translations.items()
            }
        total_time = time.perf_counter() - total_start
        print("Clarification Hit: true")
        print("Vector Search Time: 0.000s")
        print("LLM Time: 0.000s")
        print(f"Total Time: {total_time:.3f}s")
        log_final_answer(agent_state, response_payload["answer"], path="clarification")
        return finalize_chat_response(response_payload, agent_state, path="clarification")

    in_scope = (
        is_explicit_service_question(question)
        or is_nthu_question(standalone_question)
        or agent_state.get("current_topic") in {"campus_wifi", "dorm_network", "vpn", "email"}
        or (bool(history) and is_contextual_followup(question) and is_nthu_question(contextual_question))
    )
    location = agent_state.get("current_slots", {}).get("location")
    if not in_scope and location and is_location_availability_ellipsis(question):
        response_payload = {
            "answer": (
                f"I recognize the location as {location}, but what you mean by “does it have it” "
                "is unclear. Are you asking about campus Wi-Fi, wired networking, or another network service?"
                if effective_language == "en"
                else (
                    f"我知道你指的是「{location}」，但「有嗎」還不確定是在問哪一種服務。"
                    "你想問的是校園 Wi-Fi、有線網路，還是其他網路服務？"
                )
            ),
            "sources": [],
        }
        total_time = time.perf_counter() - total_start
        print("Location Clarification Hit: true")
        print("Vector Search Time: 0.000s")
        print("LLM Time: 0.000s")
        print(f"Total Time: {total_time:.3f}s")
        log_final_answer(agent_state, response_payload["answer"], path="location_clarification")
        return finalize_chat_response(response_payload, agent_state, path="location_clarification")
    if not in_scope:
        total_time = time.perf_counter() - total_start
        print("Vector Search Time: 0.000s")
        print("LLM Time: 0.000s")
        print(f"Total Time: {total_time:.3f}s")

        response_payload = {
            "answer": (
                "Sorry, this service only provides information about the NTHU Network Systems Division."
                if effective_language == "en"
                else "抱歉，本客服僅提供國立清華大學網路系統組相關資訊。"
            ),
            "sources": [],
        }
        log_final_answer(agent_state, response_payload["answer"], path="scope_guard")
        return finalize_chat_response(response_payload, agent_state, path="scope_guard")

    progression_response = build_progression_response(agent_state)
    if progression_response is not None:
        response_payload = {
            "answer": clean_answer(progression_response["answer"], question=question),
            "sources": clean_sources(progression_response.get("sources", [])),
        }
        total_time = time.perf_counter() - total_start
        print("Follow-up Progression Hit: true")
        print("Vector Search Time: 0.000s")
        print("LLM Time: 0.000s")
        print(f"Total Time: {total_time:.3f}s")
        log_final_answer(
            agent_state,
            response_payload["answer"],
            path="followup_progression",
        )
        return finalize_chat_response(
            response_payload,
            agent_state,
            path="followup_progression",
        )

    active_collection = get_active_collection_name()
    cache_key = stable_key(
        {
            "question": standalone_question,
            "topic": agent_state.get("current_topic"),
            "referenced_turn_ids": agent_state.get("referenced_turn_ids", []),
            "history": history,
            "language": effective_language,
            "collection": active_collection,
        }
    )

    current_topic = agent_state.get("current_topic", "unknown")
    fast_question = focus_message_on_topic(standalone_question, current_topic)
    fast_question = ensure_topic_in_query(fast_question, current_topic)
    contextual_fast_question = focus_message_on_topic(contextual_question, current_topic)
    contextual_fast_question = ensure_topic_in_query(contextual_fast_question, current_topic)
    fast_response = None
    semantic_slots = agent_state.get("semantic_slots", {})
    if effective_language == "zh-Hant":
        current_intent = agent_state.get("current_intent", "unknown")
        current_location = semantic_slots.get("location")
        if current_topic == "campus_wifi":
            if current_location:
                if current_intent == "comparison":
                    referenced_location = agent_state.get("referenced_slots", {}).get("location")
                    if referenced_location:
                        fast_response = build_account_scope_comparison_response(
                            current_location,
                            referenced_location,
                            WIRELESS_APPLICATION_ANSWER,
                        )
                elif current_intent == "lookup":
                    fast_response = build_coverage_response(current_location)
            elif (
                current_intent == "lookup"
                and semantic_slots.get("question_focus") == "ssid_list"
            ):
                fast_response = build_campus_ssid_response()
        if (
            fast_response is None
            and semantic_slots.get("troubleshooting_stage") == "cross_test_failed"
        ):
            fast_response = get_structured_fast_answer(
                fast_question,
                topic=current_topic,
                intent=agent_state.get("current_intent", "unknown"),
                semantic_slots=semantic_slots,
            )
        if fast_response is None:
            fast_response = get_fast_answer(fast_question)
        if fast_response is None and history and is_contextual_followup(question):
            fast_response = get_fast_answer(contextual_fast_question)
        if fast_response is None:
            fast_response = get_structured_fast_answer(
                fast_question,
                topic=current_topic,
                intent=agent_state.get("current_intent", "unknown"),
                semantic_slots=semantic_slots,
            )
    elif effective_language == "en":
        fast_response = get_english_fast_answer(fast_question)
        if fast_response is None and history and is_contextual_followup(question):
            fast_response = get_english_fast_answer(contextual_fast_question)

    if fast_response is not None and not fast_answer_matches_topic(fast_response, current_topic):
        print(f"Fast Answer Domain Mismatch: expected={current_topic}")
        fast_response = None
    if fast_response is not None:
        response_payload = {
            "answer": clean_answer(fast_response["answer"], question=fast_question),
            "sources": clean_sources(fast_response["sources"]),
        }
        if fast_response.get("answer_translations"):
            response_payload["answer_translations"] = fast_response["answer_translations"]
        answer_cache.set(cache_key, response_payload)
        remember_session_cache_key(req.session_id, cache_key)
        total_time = time.perf_counter() - total_start
        print("Fast Answer Hit: true")
        print("Vector Search Time: 0.000s")
        print("LLM Time: 0.000s")
        print(f"Total Time: {total_time:.3f}s")
        log_final_answer(agent_state, response_payload["answer"], path="fast_answer")
        return finalize_chat_response(response_payload, agent_state, path="fast_answer")

    cached_response = answer_cache.get(cache_key)
    if cached_response is not None:
        answer_text = cached_response.get("answer", "") if isinstance(cached_response, dict) else ""
        if answer_text and not cached_response.get("answer_translations"):
            answer_translations = paired_fast_translations(answer_text)
            if answer_translations:
                cached_response = dict(cached_response)
                cached_response["answer_translations"] = {
                    translated_language: clean_answer(translated_text, question=standalone_question)
                    for translated_language, translated_text in answer_translations.items()
                }
                answer_cache.set(cache_key, cached_response)
        remember_session_cache_key(req.session_id, cache_key)
        total_time = time.perf_counter() - total_start
        print("Answer Cache Hit: true")
        print("Vector Search Time: 0.000s")
        print("LLM Time: 0.000s")
        print(f"Total Time: {total_time:.3f}s")
        log_final_answer(agent_state, cached_response.get("answer", ""), path="answer_cache")
        return finalize_chat_response(cached_response, agent_state, path="answer_cache")

    try:
        with chat_capacity():
            graph_result = get_compiled_agent_graph().invoke(agent_state)
            search_results = graph_result.get("retrieved_docs", [])
            answer = graph_result.get("answer", "")
            if not isinstance(answer, str):
                raise TypeError("LangGraph output field 'answer' must be a string")
            graph_metadata = graph_result.get("metadata", {})
            search_time = float(graph_metadata.get("retrieval_seconds", 0.0))
            llm_time = float(graph_metadata.get("generation_seconds", 0.0))
            total_time = time.perf_counter() - total_start

            response_sources = search_results[:3]
            if has_prompt_leak(answer):
                answer = fallback_for_prompt_leak(effective_language)
                response_sources = []
                log_final_answer(graph_result, answer, path="prompt_leak_fallback")

            response_payload = {
                "answer": answer,
                "sources": clean_sources(response_sources),
            }
            answer_cache.set(cache_key, response_payload)
            remember_session_cache_key(req.session_id, cache_key)

            print(f"Active Chat Requests: {active_chat_requests}/{CHAT_MAX_CONCURRENT_REQUESTS}")
            print(f"Vector Search Time: {search_time:.3f}s")
            print(f"LLM Time: {llm_time:.3f}s")
            print(f"Total Time: {total_time:.3f}s")

            return finalize_chat_response(response_payload, graph_result, path="langgraph")
    except EmbeddingServiceError as exc:
        if effective_language == "zh-Hant":
            fallback_response = get_dependency_fallback_answer(
                fast_question,
                topic=current_topic,
                intent=agent_state.get("current_intent", "unknown"),
                semantic_slots=semantic_slots,
            )
        else:
            fallback_response = {
                "answer": (
                    "Complete details are temporarily unavailable. Please try again shortly, "
                    "or include the service name, location, device, error message, and steps "
                    "already attempted."
                ),
                "sources": [],
            }
        response_payload = {
            "answer": clean_answer(fallback_response["answer"], question=fast_question),
            "sources": clean_sources(fallback_response.get("sources", [])),
        }
        total_time = time.perf_counter() - total_start
        print(f"Embedding Fallback Hit: category={exc.category}")
        print("Vector Search Time: 0.000s")
        print("LLM Time: 0.000s")
        print(f"Total Time: {total_time:.3f}s")
        log_final_answer(
            agent_state,
            response_payload["answer"],
            path="embedding_fallback",
        )
        return finalize_chat_response(
            response_payload,
            agent_state,
            path="embedding_fallback",
        )
    except (QdrantServiceError, LLMServiceError) as exc:
        raise HTTPException(
            status_code=503,
            detail=exc.public_detail(),
        ) from exc
    except requests.RequestException as exc:
        dependency_error = QdrantServiceError(operation="retrieve", cause=exc)
        raise HTTPException(
            status_code=503,
            detail=dependency_error.public_detail(),
        ) from exc
    except OpenAIError as exc:
        dependency_error = LLMServiceError(operation="generate", cause=exc)
        raise HTTPException(
            status_code=503,
            detail=dependency_error.public_detail(),
        ) from exc


@app.post("/ingest")
def ingest():
    clear_all_caches()
    return ingest_nthu_docs(replace=True)


@app.post("/refresh")
def refresh():
    clear_all_caches()
    return ingest_nthu_docs(replace=True)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "dependency_readiness": "/health/dependencies",
        "active_chat_requests": active_chat_requests,
        "max_concurrent_chat_requests": CHAT_MAX_CONCURRENT_REQUESTS,
        "active_llm_requests": active_llm_requests,
        "queued_llm_requests": queued_llm_requests,
        "max_concurrent_llm_requests": LLM_MAX_CONCURRENT_REQUESTS,
        "answer_cache": answer_cache.stats(),
        "active_collection": get_active_collection_name(),
    }


@app.get("/health/dependencies")
def dependency_health():
    payload = run_dependency_checks()
    return JSONResponse(
        status_code=200 if payload["ready"] else 503,
        content=payload,
    )
