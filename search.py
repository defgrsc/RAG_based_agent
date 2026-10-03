from typing import Any
from urllib.parse import urlparse

import requests

from config import NTHU_NETSYS_BASE_URL, SEARXNG_URL, SEARCH_LIMIT


CONTENT_LIMIT = 200


def normalize_path(path: str) -> str:
    return path if path.endswith("/") else f"{path}/"


def is_allowed_domain(url: str) -> bool:
    parsed_url = urlparse(url)
    parsed_base = urlparse(NTHU_NETSYS_BASE_URL)

    if parsed_url.scheme not in {"http", "https"}:
        return False

    if parsed_url.hostname != parsed_base.hostname:
        return False

    base_path = normalize_path(parsed_base.path or "/")
    url_path = normalize_path(parsed_url.path or "/")
    return url_path.startswith(base_path)


def format_source_name(title: str, url: str) -> str:
    if title:
        return title

    hostname = urlparse(url).hostname
    return hostname or url


def search_web(query: str, limit: int = SEARCH_LIMIT) -> list[dict[str, Any]]:
    search_query = f"{query} site:net.nthu.edu.tw/netsys"

    response = requests.get(
        SEARXNG_URL,
        params={
            "q": search_query,
            "format": "json",
        },
        timeout=10,
    )
    response.raise_for_status()

    results = []
    for item in response.json().get("results", []):
        url = item.get("url", "")
        if not is_allowed_domain(url):
            continue

        title = item.get("title", "")
        results.append(
            {
                "title": title,
                "source_name": format_source_name(title, url),
                "url": url,
                "content": item.get("content", "")[:CONTENT_LIMIT],
            }
        )

        if len(results) >= limit:
            break

    return results


def build_context(results: list[dict[str, Any]]) -> str:
    context = ""

    for i, item in enumerate(results, start=1):
        context += f"""
[資料 {i}]
來源：{item["source_name"]}
標題：{item["title"]}
網址：{item["url"]}
內容：{item["content"]}
"""

    return context
