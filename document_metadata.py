from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any, Iterable


METADATA_SCHEMA_VERSION = 2
KNOWN_SERVICES = ("campus_wifi", "dorm_network", "vpn", "email")
KNOWN_TASKS = (
    "application",
    "troubleshooting",
    "configuration",
    "coverage",
    "credentials",
    "status",
    "lookup",
    "general",
)

SERVICE_URL_TERMS: dict[str, tuple[str, ...]] = {
    "campus_wifi": ("wireless", "wlan"),
    "dorm_network": ("dormnet", "dormitory", "domitory"),
    "vpn": ("sslvpn", "vpn", "juniper", "neoteris", "nc_windows"),
    "email": ("mail:", "/mail", "gapp", "smtp", "webmail"),
}
SERVICE_TEXT_TERMS: dict[str, tuple[str, ...]] = {
    "campus_wifi": (
        "校園無線", "無線網路", "nthu-cc", "nthupeap", "eduroam",
        "tanetroaming", "campus wi-fi", "campus wifi", "wireless network",
    ),
    "dorm_network": (
        "宿網", "宿舍網路", "宿舍網路孔", "dormnet", "dorm network",
        "dormitory network", "dorm ethernet",
    ),
    "vpn": (
        "ssl-vpn", "sslvpn", " vpn ", "ivanti", "pulse secure", "twaren",
        "校外連線", "校內資源",
    ),
    "email": (
        "學生信箱", "電子郵件", "webmail", "google workspace", "gapp",
        " smtp ", " imap ", " pop3 ", "mailbox",
    ),
}

TASK_URL_TERMS: dict[str, tuple[str, ...]] = {
    "coverage": ("wlan_range", "wireless:easy", "wireless:uniform", "coverage"),
    "application": ("application", "apply", "new_std", "gapp"),
    "troubleshooting": (
        "useless", "cannot", "failed", "failure", "error", "missing", "changed",
    ),
    "configuration": (
        "setup", "config", "install", "win10", "web_based", "network_tools", "smtp",
    ),
    "credentials": ("auth", "set_password", "password"),
    "status": ("service:status", "ipquery"),
    "lookup": ("search", "query"),
}
TASK_TEXT_TERMS: dict[str, tuple[str, ...]] = {
    "coverage": ("服務範圍", "涵蓋範圍", "coverage", "無線範圍"),
    "application": (
        "申請", "申辦", "register", "registration", "apply for",
    ),
    "troubleshooting": (
        "無法連線", "不能上網", "連不上", "故障", "排除", "troubleshoot",
        "cannot connect", "not working", "failed",
    ),
    "configuration": (
        "設定方式", "安裝", "tcp/ip", "固定 ip", "configuration", "configure",
        "installation", "setup",
    ),
    "credentials": (
        "帳號密碼", "認證", "authentication", "username", "password",
    ),
    "status": ("服務狀態", "網路狀態", "service status", "outage"),
    "lookup": ("查詢", "lookup", "where can i find"),
}


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    return f" {' '.join(normalized.split())} "


def _ordered_matches(
    haystack: str,
    rules: dict[str, tuple[str, ...]],
    order: Iterable[str],
) -> list[str]:
    return [
        label
        for label in order
        if any(term in haystack for term in rules.get(label, ()))
    ]


def infer_services(document: dict[str, Any]) -> list[str]:
    url = _normalize(str(document.get("url", "")))
    url_services = _ordered_matches(url, SERVICE_URL_TERMS, KNOWN_SERVICES)
    if url_services:
        return url_services

    text = _normalize(
        f"{document.get('title', '')} {document.get('content', '')}"
    )
    text_services = _ordered_matches(text, SERVICE_TEXT_TERMS, KNOWN_SERVICES)
    return text_services or ["general_network"]


def infer_tasks(document: dict[str, Any]) -> list[str]:
    url = _normalize(str(document.get("url", "")))
    url_tasks = _ordered_matches(url, TASK_URL_TERMS, KNOWN_TASKS)
    text = _normalize(
        f"{document.get('title', '')} {document.get('content', '')}"
    )
    text_tasks = _ordered_matches(text, TASK_TEXT_TERMS, KNOWN_TASKS)
    combined = set(url_tasks) | set(text_tasks)
    return [task for task in KNOWN_TASKS if task in combined] or ["general"]


def infer_language(document: dict[str, Any]) -> str:
    url = _normalize(str(document.get("url", "")))
    title = _normalize(str(document.get("title", "")))
    return "en" if "/netsys/en:" in url or title.startswith(" en:") else "zh-Hant"


def infer_source_type(document: dict[str, Any]) -> str:
    url = _normalize(str(document.get("url", "")))
def infer_source_type(document: dict[str, Any]) -> str:
    url = _normalize(str(document.get("url", "")))
    if re.search(r"(?:/|:)faq(?:[:/? ]|$)", url):
        return "official_faq"
    return "official_service_page"
def infer_document_type(document: dict[str, Any]) -> str:
    source_type = str(document.get("source_type") or infer_source_type(document))
    if source_type == "official_coverage":
        return "coverage_record"
    if source_type == "official_faq":
        return "faq_chunk"
    return "service_page_chunk"


def _as_labels(value: Any) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return list(dict.fromkeys(str(item) for item in value if str(item)))
    return []


def _legacy_intent(tasks: list[str]) -> str:
    if len(tasks) != 1:
        return "mixed"
    task = tasks[0]
    if task in {"status", "credentials"}:
        return "lookup"
    return task


def annotate_document(document: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(document)
    services = _as_labels(enriched.get("services"))
    existing_service = str(enriched.get("service") or "")
    if not services and existing_service and existing_service not in {"multi_service", "general_network"}:
        services = [existing_service]
    services = services or infer_services(enriched)

    tasks = _as_labels(enriched.get("tasks"))
    existing_task = str(enriched.get("task") or enriched.get("intent") or "")
    if not tasks and existing_task and existing_task != "mixed":
        tasks = [existing_task]
    tasks = tasks or infer_tasks(enriched)

    enriched.update(
        {
            "service": (
                existing_service
                or (services[0] if len(services) == 1 else "multi_service")
            ),
            "services": services,
            "task": str(enriched.get("task") or (tasks[0] if len(tasks) == 1 else "mixed")),
            "tasks": tasks,
            "intent": str(enriched.get("intent") or _legacy_intent(tasks)),
            "language": str(enriched.get("language") or infer_language(enriched)),
            "source_type": str(enriched.get("source_type") or infer_source_type(enriched)),
            "document_type": str(enriched.get("document_type") or infer_document_type(enriched)),
            "metadata_schema_version": METADATA_SCHEMA_VERSION,
        }
    )
    return enriched


def annotate_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [annotate_document(document) for document in documents]


def validate_document_metadata(documents: list[dict[str, Any]]) -> None:
    errors: list[str] = []
    for index, document in enumerate(documents):
        for field in (
            "service", "services", "task", "tasks", "intent", "language",
            "source_type", "document_type", "metadata_schema_version",
        ):
            if document.get(field) in (None, "", []):
                errors.append(f"document[{index}] missing {field}")
        if document.get("language") not in {"zh-Hant", "en"}:
            errors.append(f"document[{index}] invalid language={document.get('language')!r}")
        if document.get("metadata_schema_version") != METADATA_SCHEMA_VERSION:
            errors.append(
                f"document[{index}] invalid metadata_schema_version="
                f"{document.get('metadata_schema_version')!r}"
            )
    if errors:
        preview = "; ".join(errors[:20])
        raise ValueError(f"Document metadata validation failed: {preview}")


def summarize_document_metadata(documents: list[dict[str, Any]]) -> dict[str, Any]:
    service_counts = Counter(
        service
        for document in documents
        for service in _as_labels(document.get("services"))
    )
    task_counts = Counter(
        task
        for document in documents
        for task in _as_labels(document.get("tasks"))
    )
    language_counts = Counter(str(document.get("language")) for document in documents)
    return {
        "schema_version": METADATA_SCHEMA_VERSION,
        "documents": len(documents),
        "services": dict(service_counts),
        "tasks": dict(task_counts),
        "languages": dict(language_counts),
    }
