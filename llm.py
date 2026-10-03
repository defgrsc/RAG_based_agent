import json
import re
import threading
import time

import requests
from openai import OpenAI, OpenAIError

from config import (
    EMBEDDING_REQUEST_TIMEOUT_SECONDS,
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_CIRCUIT_BREAKER_SECONDS,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    LLM_ENABLE_THINKING,
    LLM_REQUEST_TIMEOUT_SECONDS,
    MODEL_NAME,
    LLM_CONTINUATION_MAX_TOKENS,
    LLM_MAX_TOKENS,
    LLM_REASONING_EFFORT,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
)
from prompt import SYSTEM_PROMPT, build_user_prompt
from service_errors import EmbeddingServiceError, LLMServiceError
from utils import clean_answer


chat_client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    timeout=LLM_REQUEST_TIMEOUT_SECONDS,
    max_retries=1,
)

embedding_client = OpenAI(
    api_key=EMBEDDING_API_KEY,
    base_url=EMBEDDING_BASE_URL,
    timeout=EMBEDDING_REQUEST_TIMEOUT_SECONDS,
    max_retries=0,
)

_embedding_circuit_lock = threading.Lock()
_embedding_unavailable_until = 0.0


def reset_embedding_circuit_breaker() -> None:
    global _embedding_unavailable_until
    with _embedding_circuit_lock:
        _embedding_unavailable_until = 0.0


def _embedding_circuit_is_open() -> bool:
    with _embedding_circuit_lock:
        return time.monotonic() < _embedding_unavailable_until


def _record_embedding_failure() -> None:
    global _embedding_unavailable_until
    with _embedding_circuit_lock:
        _embedding_unavailable_until = max(
            _embedding_unavailable_until,
            time.monotonic() + EMBEDDING_CIRCUIT_BREAKER_SECONDS,
        )


def _record_embedding_success() -> None:
    reset_embedding_circuit_breaker()


def _chat_completion(messages: list[dict[str, str]], *, max_tokens: int, temperature: float = 0.2):
    extra_body = {
        "chat_template_kwargs": {"enable_thinking": LLM_ENABLE_THINKING},
    }
    if LLM_ENABLE_THINKING and LLM_REASONING_EFFORT:
        extra_body["reasoning_effort"] = LLM_REASONING_EFFORT

    return chat_client.chat.completions.create(
        model=MODEL_NAME,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body=extra_body,
        messages=messages,
    )


def _message_text(message) -> str:
    """Return vLLM output whether the model used content or a reasoning field."""
    content = getattr(message, "content", None)
    if content:
        return content

    for field in ("reasoning", "reasoning_content"):
        value = getattr(message, field, None)
        if not value:
            model_extra = getattr(message, "model_extra", None) or {}
            value = model_extra.get(field)
        if value:
            return value

    return ""


def _looks_truncated(answer: str, finish_reason: str | None) -> bool:
    if finish_reason == "length":
        return True

    stripped = answer.strip()
    if not stripped:
        return False

    if re.search(r"(?:\n|^)(?:詳細可參?|詳細可參考[:：]?)\s*$", stripped):
        return True

    if stripped.endswith(("，", "、", "：", ":", "（", "(", "「", "『")):
        return True

    return False


def embed_texts(
    texts: list[str],
    *,
    timeout_seconds: float | None = None,
    bypass_circuit_breaker: bool = False,
) -> list[list[float]]:
    if not texts:
        return []
    if not bypass_circuit_breaker and _embedding_circuit_is_open():
        print("Embedding Time: 0.000s (circuit_open)")
        raise EmbeddingServiceError(
            operation="circuit_breaker",
            cause=ConnectionError("Embedding circuit breaker is open"),
            category="circuit_open",
        )

    started = time.perf_counter()
    try:
        vectors = _embed_texts_unchecked(
            texts,
            timeout_seconds=timeout_seconds or EMBEDDING_REQUEST_TIMEOUT_SECONDS,
        )
        if len(vectors) != len(texts) or any(not vector for vector in vectors):
            raise ValueError("Embedding response count or vector content mismatch")
    except EmbeddingServiceError as exc:
        error = exc
    except (OpenAIError, requests.RequestException, ValueError, KeyError, TypeError) as exc:
        error = EmbeddingServiceError(operation="embed", cause=exc)
    else:
        _record_embedding_success()
        print(f"Embedding Time: {time.perf_counter() - started:.3f}s")
        return vectors

    _record_embedding_failure()
    print(
        f"Embedding Time: {time.perf_counter() - started:.3f}s "
        f"(failed:{error.category})"
    )
    raise error from error.cause


def _embed_texts_unchecked(
    texts: list[str],
    *,
    timeout_seconds: float,
) -> list[list[float]]:
    if EMBEDDING_PROVIDER == "ollama":
        return embed_texts_with_ollama(texts, timeout_seconds=timeout_seconds)

    client = embedding_client.with_options(timeout=timeout_seconds, max_retries=0)
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def embed_texts_with_ollama(
    texts: list[str],
    *,
    timeout_seconds: float = EMBEDDING_REQUEST_TIMEOUT_SECONDS,
) -> list[list[float]]:
    base_url = EMBEDDING_BASE_URL.rstrip("/")

    response = requests.post(
        f"{base_url}/api/embed",
        json={
            "model": EMBEDDING_MODEL,
            "input": texts,
        },
        timeout=timeout_seconds,
    )
    if response.status_code != 404:
        response.raise_for_status()
        data = response.json()
        if "embeddings" in data:
            return data["embeddings"]

    vectors = []
    for text in texts:
        response = requests.post(
            f"{base_url}/api/embeddings",
            json={
                "model": EMBEDDING_MODEL,
                "prompt": text,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        if "embedding" not in data:
            raise ValueError(f"Ollama embedding response missing embedding: {data}")

        vectors.append(data["embedding"])

    return vectors


def probe_embedding_service(timeout_seconds: float) -> dict[str, int | str]:
    vectors = embed_texts(
        ["NTHU dependency health probe"],
        timeout_seconds=timeout_seconds,
        bypass_circuit_breaker=True,
    )
    return {
        "provider": EMBEDDING_PROVIDER,
        "model": EMBEDDING_MODEL,
        "dimensions": len(vectors[0]),
    }


def probe_llm_service(timeout_seconds: float) -> dict[str, int | str | bool]:
    try:
        response = chat_client.with_options(
            timeout=timeout_seconds,
            max_retries=0,
        ).models.list()
        model_ids = {
            str(item.id)
            for item in getattr(response, "data", [])
            if getattr(item, "id", None)
        }
        if model_ids and MODEL_NAME not in model_ids:
            raise ValueError(f"Configured model is not advertised: {MODEL_NAME}")
        return {
            "model": MODEL_NAME,
            "available_models": len(model_ids),
            "configured_model_found": not model_ids or MODEL_NAME in model_ids,
        }
    except LLMServiceError:
        raise
    except (OpenAIError, ValueError, KeyError, TypeError) as exc:
        raise LLMServiceError(operation="model_list", cause=exc) from exc


def generate_answer(question: str, context: str, history_context: str = "", language: str = "zh-Hant") -> str:
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": build_user_prompt(question, context, history_context=history_context, language=language),
        },
    ]
    response = _chat_completion(messages, max_tokens=LLM_MAX_TOKENS)

    choice = response.choices[0]
    answer = _message_text(choice.message)
    finish_reason = getattr(choice, "finish_reason", None)

    if _looks_truncated(answer, finish_reason):
        continuation_messages = [
            *messages,
            {
                "role": "assistant",
                "content": answer,
            },
            {
                "role": "user",
                "content": (
                    ("The previous answer was truncated. Continue only the unfinished portion without repeating it; "
                     "if the For details section is missing, add 1 to 3 complete and relevant URLs. Use English only.")
                    if language == "en"
                    else ("上一則回答被截斷。請只接續未完成的部分，不要重複已經寫過的內容；"
                          "若缺少「詳細可參考」，請補完整 1 到 3 個最相關且完整的網址。")
                ),
            },
        ]
        continuation = _chat_completion(
            continuation_messages,
            max_tokens=LLM_CONTINUATION_MAX_TOKENS,
            temperature=0.1,
        )
        continuation_text = _message_text(continuation.choices[0].message)
        if continuation_text.strip():
            answer = answer.rstrip() + "\n" + continuation_text.lstrip()

    return clean_answer(answer, question=question)


def _translate_messages_once(texts: list[str], target_language: str) -> list[str]:
    target_name = "English" if target_language == "en" else "Traditional Chinese"
    payload = json.dumps(texts, ensure_ascii=False)
    response = _chat_completion(
        [
            {
                "role": "system",
                "content": (
                    f"Translate each JSON array item into {target_name}. Preserve Markdown structure, "
                    "numbering, bold markers, inline code, complete URLs, email addresses, account formats, "
                    "SSIDs, and proper nouns. Translate every heading and structural label too; never leave text "
                    "from the source language mixed into the translation. Return only a valid JSON array of translated strings in the "
                    "same order and with the same number of items."
                ),
            },
            {"role": "user", "content": payload},
        ],
        max_tokens=max(1200, min(12000, len(payload) * 2 + 800)),
        temperature=0.1,
    )
    content = _message_text(response.choices[0].message).strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
    try:
        translated = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", content)
        if not match:
            raise
        translated = json.loads(match.group(0))
    if not isinstance(translated, list) or len(translated) != len(texts):
        raise ValueError("Translation response item count mismatch")
    return [str(item) for item in translated]


def translate_messages(texts: list[str], target_language: str) -> list[str]:
    if not texts:
        return []

    try:
        return _translate_messages_once(texts, target_language)
    except Exception:
        if len(texts) == 1:
            # Last-resort fallback: keep the row renderable instead of failing the whole language switch.
            return [texts[0]]

    if len(texts) == 2:
        return translate_messages([texts[0]], target_language) + translate_messages([texts[1]], target_language)

    mid = len(texts) // 2
    return translate_messages(texts[:mid], target_language) + translate_messages(texts[mid:], target_language)
