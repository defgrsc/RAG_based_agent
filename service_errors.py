from __future__ import annotations

from typing import Any

import requests
from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, RateLimitError


def classify_dependency_error(exc: BaseException) -> str:
    if isinstance(exc, (requests.Timeout, APITimeoutError, TimeoutError)):
        return "timeout"
    if isinstance(exc, AuthenticationError):
        return "authentication"
    if isinstance(exc, RateLimitError):
        return "rate_limit"
    if isinstance(exc, (requests.ConnectionError, APIConnectionError, ConnectionError)):
        return "connection"
    if isinstance(exc, (requests.HTTPError, APIStatusError)):
        return "http_error"
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return "invalid_response"
    return "unavailable"


SERVICE_MESSAGES = {
    "embedding": "目前暫時無法取得完整資料，請稍後再試。",
    "qdrant": "目前暫時無法取得完整資料，請稍後再試。",
    "llm": "目前暫時無法產生完整回答，請稍後再試。",
}


class DependencyServiceError(RuntimeError):
    def __init__(
        self,
        service: str,
        *,
        operation: str,
        cause: BaseException,
        category: str | None = None,
    ) -> None:
        self.service = service
        self.operation = operation
        self.category = category or classify_dependency_error(cause)
        self.cause = cause
        super().__init__(f"{service} {operation} failed ({self.category})")

    def public_detail(self) -> dict[str, Any]:
        return {
            "code": f"{self.service}_unavailable",
            "service": self.service,
            "category": self.category,
            "message": SERVICE_MESSAGES.get(
                self.service,
                "外部服務目前無法使用，請稍後再試。",
            ),
        }


class EmbeddingServiceError(DependencyServiceError):
    def __init__(
        self,
        *,
        operation: str,
        cause: BaseException,
        category: str | None = None,
    ) -> None:
        super().__init__(
            "embedding",
            operation=operation,
            cause=cause,
            category=category,

        )

class LLMServiceError(DependencyServiceError):
    def __init__(self, *, operation: str, cause: BaseException) -> None:
        super().__init__("llm", operation=operation, cause=cause)


class QdrantServiceError(DependencyServiceError):
    def __init__(self, *, operation: str, cause: BaseException) -> None:
        super().__init__("qdrant", operation=operation, cause=cause)
