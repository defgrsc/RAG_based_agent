import os
import time
import uuid
from pathlib import Path
from typing import Any

import requests

from config import QDRANT_COLLECTION, QDRANT_URL


STATE_DIR = Path(__file__).resolve().parent / "runtime"
ACTIVE_COLLECTION_FILE = STATE_DIR / "active_qdrant_collection.txt"


def get_active_collection_name() -> str:
    try:
        value = ACTIVE_COLLECTION_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return QDRANT_COLLECTION

    return value or QDRANT_COLLECTION


def set_active_collection_name(collection_name: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = ACTIVE_COLLECTION_FILE.with_suffix(".tmp")
    temp_path.write_text(collection_name, encoding="utf-8")
    os.replace(temp_path, ACTIVE_COLLECTION_FILE)


def collection_url(path: str = "", collection_name: str | None = None) -> str:
    base = QDRANT_URL.rstrip("/")
    collection = collection_name or get_active_collection_name()
    suffix = f"/{path.lstrip('/')}" if path else ""
    return f"{base}/collections/{collection}{suffix}"


def create_collection(vector_size: int, collection_name: str | None = None) -> None:
    response = requests.put(
        collection_url(collection_name=collection_name),
        json={
            "vectors": {
                "size": vector_size,
                "distance": "Cosine",
            }
        },
        timeout=20,
    )
    response.raise_for_status()


def ensure_collection(vector_size: int, collection_name: str | None = None) -> None:
    response = requests.get(collection_url(collection_name=collection_name), timeout=10)
    if response.status_code == 200:
        return

    create_collection(vector_size, collection_name=collection_name)


def delete_collection(collection_name: str) -> None:
    response = requests.delete(collection_url(collection_name=collection_name), timeout=20)
    if response.status_code not in {200, 404}:
        response.raise_for_status()


def recreate_collection(vector_size: int, collection_name: str | None = None) -> None:
    collection = collection_name or get_active_collection_name()
    delete_collection(collection)
    create_collection(vector_size, collection_name=collection)


def next_staging_collection_name() -> str:
    return f"{QDRANT_COLLECTION}__{time.time_ns()}"


def build_points(documents: list[dict[str, Any]], vectors: list[list[float]]) -> list[dict[str, Any]]:
    points = []

    for document, vector in zip(documents, vectors):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document['url']}#{document['chunk_index']}"))
        payload = {**document, "point_id": point_id}
        points.append(
            {
                "id": point_id,
                "vector": vector,
                "payload": payload,
            }
        )

    return points


def upsert_points(collection_name: str, documents: list[dict[str, Any]], vectors: list[list[float]]) -> None:
    response = requests.put(
        collection_url("points", collection_name=collection_name),
        params={"wait": "true"},
        json={"points": build_points(documents, vectors)},
        timeout=60,
    )
    response.raise_for_status()


def upsert_documents(documents: list[dict[str, Any]], vectors: list[list[float]], replace: bool = False) -> str:
    if not documents:
        return get_active_collection_name()

    vector_size = len(vectors[0])

    if replace:
        staging_collection = next_staging_collection_name()
        try:
            create_collection(vector_size, collection_name=staging_collection)
            upsert_points(staging_collection, documents, vectors)
            set_active_collection_name(staging_collection)
            return staging_collection
        except Exception:
            delete_collection(staging_collection)
            raise

    active_collection = get_active_collection_name()
    ensure_collection(vector_size, collection_name=active_collection)
    upsert_points(active_collection, documents, vectors)
    return active_collection


def search_similar(
    vector: list[float],
    limit: int,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    request_body: dict[str, Any] = {
        "vector": vector,
        "limit": limit,
        "with_payload": True,
    }
    if metadata_filter:
        must_conditions = []
        for key, value in metadata_filter.items():
            match = {"any": value} if isinstance(value, list) else {"value": value}
            must_conditions.append({"key": key, "match": match})
        request_body["filter"] = {"must": must_conditions}

    response = requests.post(
        collection_url("points/search"),
        json=request_body,
        timeout=20,
    )
    response.raise_for_status()

    results = []
    for point in response.json().get("result", []):
        payload = point.get("payload", {})
        payload["score"] = point.get("score")
        payload["source_name"] = payload.get("title") or payload.get("url")
        payload["point_id"] = payload.get("point_id") or point.get("id")
        results.append(payload)

    return results


def get_chunks_by_url(url: str, limit: int = 10) -> list[dict[str, Any]]:
    response = requests.post(
        collection_url("points/scroll"),
        json={
            "filter": {
                "must": [
                    {
                        "key": "url",
                        "match": {"value": url},
                    }
                ]
            },
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        },
        timeout=20,
    )
    response.raise_for_status()

    chunks = []
    for point in response.json().get("result", {}).get("points", []):
        payload = point.get("payload", {})
        payload["score"] = payload.get("score") or 0
        payload["source_name"] = payload.get("title") or payload.get("url")
        payload["point_id"] = payload.get("point_id") or point.get("id")
        chunks.append(payload)

    return sorted(chunks, key=lambda item: item.get("chunk_index", 0))
