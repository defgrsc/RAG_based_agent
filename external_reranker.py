from typing import Any

import requests

from config import RERANKER_ENABLED, RERANKER_TIMEOUT, RERANKER_TOP_N, RERANKER_URL


def is_enabled() -> bool:
    return RERANKER_ENABLED and bool(RERANKER_URL)


def build_document(item: dict[str, Any], index: int) -> dict[str, str]:
    text = "\n".join(
        part
        for part in (
            str(item.get("title", "")).strip(),
            str(item.get("url", "")).strip(),
            str(item.get("content", "")).strip(),
        )
        if part
    )
    return {"id": str(index), "text": text[:4000]}


def extract_result_id(result: dict[str, Any]) -> str | None:
    for key in ("id", "document_id", "doc_id", "index"):
        value = result.get(key)
        if value is not None:
            return str(value)

    document = result.get("document")
    if isinstance(document, dict):
        value = document.get("id")
        if value is not None:
            return str(value)

    return None


def extract_score(result: dict[str, Any]) -> float | None:
    for key in ("score", "relevance_score", "rerank_score"):
        value = result.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def normalize_response(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("results", "data", "reranked", "documents"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def rerank_with_flashrank(question: str, results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if not is_enabled() or not results:
        return results[:limit]

    documents = [build_document(item, index) for index, item in enumerate(results)]
    response = requests.post(
        RERANKER_URL,
        json={
            "query": question,
            "documents": documents,
            "top_n": min(max(limit, RERANKER_TOP_N), len(documents)),
        },
        timeout=RERANKER_TIMEOUT,
    )
    response.raise_for_status()

    by_id = {str(index): item for index, item in enumerate(results)}
    ordered = []
    seen = set()

    for rank, result in enumerate(normalize_response(response.json())):
        result_id = extract_result_id(result)
        if result_id not in by_id or result_id in seen:
            continue

        item = {**by_id[result_id]}
        score = extract_score(result)
        if score is not None:
            item["external_rerank_score"] = score
            item["rerank_score"] = score
        item["external_rerank_rank"] = rank
        ordered.append(item)
        seen.add(result_id)

        if len(ordered) >= limit:
            break

    if not ordered:
        return results[:limit]

    for index, item in enumerate(results):
        result_id = str(index)
        if result_id not in seen:
            ordered.append(item)
        if len(ordered) >= limit:
            break

    return ordered[:limit]
