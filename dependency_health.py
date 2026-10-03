from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from typing import Any

import requests

from config import DEPENDENCY_HEALTH_TIMEOUT_SECONDS
from llm import probe_embedding_service, probe_llm_service
from qdrant_store import collection_url, get_active_collection_name
from service_errors import (
    DependencyServiceError,
    EmbeddingServiceError,
    LLMServiceError,
    QdrantServiceError,
)


Probe = Callable[[float], dict[str, Any]]


def probe_qdrant_service(timeout_seconds: float) -> dict[str, Any]:
    collection = get_active_collection_name()
    try:
        response = requests.get(
            collection_url(collection_name=collection),
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        result = response.json().get("result", {})
        return {
            "collection": collection,
            "points_count": result.get("points_count"),
        }
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise QdrantServiceError(operation="collection_info", cause=exc) from exc


def _unexpected_probe_error(service: str, exc: BaseException) -> DependencyServiceError:
    error_types = {
        "embedding": EmbeddingServiceError,
        "qdrant": QdrantServiceError,
        "llm": LLMServiceError,
    }
    return error_types[service](operation="health_probe", cause=exc)


def _run_probe(service: str, probe: Probe, timeout_seconds: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        details = probe(timeout_seconds)
        return {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            **details,
        }
    except DependencyServiceError as exc:
        error = exc
    except Exception as exc:
        error = _unexpected_probe_error(service, exc)

    return {
        "status": "error",
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        **error.public_detail(),
    }


def run_dependency_checks(
    timeout_seconds: float = DEPENDENCY_HEALTH_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    probes: dict[str, Probe] = {
        "embedding": probe_embedding_service,
        "qdrant": probe_qdrant_service,
        "llm": probe_llm_service,
    }
    with ThreadPoolExecutor(max_workers=len(probes)) as executor:
        futures = {
            service: executor.submit(_run_probe, service, probe, timeout_seconds)
            for service, probe in probes.items()
        }
        dependencies = {
            service: futures[service].result()
            for service in probes
        }

    ready = all(item["status"] == "ok" for item in dependencies.values())
    return {
        "status": "ready" if ready else "degraded",
        "ready": ready,
        "timeout_seconds": timeout_seconds,
        "dependencies": dependencies,
    }
