from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from typing import Any, TypeVar

import requests
from pydantic import BaseModel

from evals.bug_discovery.schemas import ModelSettings


try:
    from deepeval.models import DeepEvalBaseLLM
except ImportError as exc:  # pragma: no cover - exercised by installation check
    raise RuntimeError(
        "DeepEval is not installed. Run: ./venv/bin/pip install -r evals/requirements.txt"
    ) from exc


SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _json_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"Model did not return a JSON object: {cleaned[:300]}")
    return cleaned[start : end + 1]


class CountingDeepEvalModel(DeepEvalBaseLLM):
    def __init__(self, model_name: str, settings: ModelSettings, role: str):
        self.model_name = model_name
        self.settings = settings
        self.role = role
        self.call_count = 0
        self._count_lock = threading.Lock()
        super().__init__(model=model_name)

    def _increment(self) -> None:
        with self._count_lock:
            self.call_count += 1

    def get_model_name(self) -> str:
        return f"{self.role}:{self.model_name}"

    def supports_temperature(self) -> bool:
        return True

    def supports_structured_outputs(self) -> bool:
        return True

    async def a_generate(self, prompt: str, schema: type[SchemaT] | None = None) -> str | SchemaT:
        return await asyncio.to_thread(self.generate, prompt, schema)


class OpenAICompatibleModel(CountingDeepEvalModel):
    def __init__(
        self,
        *,
        model_name: str,
        base_url: str,
        api_key: str,
        settings: ModelSettings,
        role: str,
    ):
        self.base_url = base_url
        self.api_key = api_key
        super().__init__(model_name=model_name, settings=settings, role=role)

    def load_model(self):
        from openai import OpenAI

        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.settings.timeout_seconds,
        )

    def _completion(self, prompt: str, *, json_mode: bool):
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Follow the user instruction exactly. When JSON is requested, "
                        "return one valid JSON object and no markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
        }
        if json_mode:
            # Qwen/vLLM may otherwise spend the budget in reasoning_content.
            kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            return self.model.chat.completions.create(**kwargs)
        except Exception:
            if not json_mode:
                raise
            kwargs.pop("response_format", None)
            return self.model.chat.completions.create(**kwargs)

    def generate(self, prompt: str, schema: type[SchemaT] | None = None) -> str | SchemaT:
        effective_prompt = prompt
        if schema is not None:
            effective_prompt += (
                "\n\nReturn JSON matching this schema exactly:\n"
                + json.dumps(schema.model_json_schema(), ensure_ascii=False)
            )
        attempts = 3 if schema is not None else 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            self._increment()
            response = self._completion(
                effective_prompt,
                json_mode=schema is not None,
            )
            message = response.choices[0].message
            content = message.content or ""
            if not content:
                for field in ("reasoning", "reasoning_content"):
                    content = getattr(message, field, None) or (
                        getattr(message, "model_extra", None) or {}
                    ).get(field, "")
                    if content:
                        break
            if schema is None:
                return content
            try:
                return schema.model_validate_json(_json_text(content))
            except Exception as exc:
                last_error = exc
                effective_prompt += (
                    f"\n\nAttempt {attempt + 1} was empty or invalid. "
                    "Return only the required JSON object now."
                )
        raise ValueError(
            f"Structured output failed after {attempts} attempts: {last_error}"
        )


class OllamaModel(CountingDeepEvalModel):
    def __init__(
        self,
        *,
        model_name: str,
        base_url: str,
        settings: ModelSettings,
        role: str,
    ):
        self.base_url = base_url.rstrip("/")
        super().__init__(model_name=model_name, settings=settings, role=role)

    def load_model(self):
        return requests.Session()

    def generate(self, prompt: str, schema: type[SchemaT] | None = None) -> str | SchemaT:
        self._increment()
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": self.settings.temperature,
                "num_predict": self.settings.max_tokens,
            },
        }
        if schema is not None:
            payload["format"] = schema.model_json_schema()
        response = self.model.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.settings.timeout_seconds,
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        if schema is None:
            return content
        return schema.model_validate_json(_json_text(content))


def build_model(settings: ModelSettings, *, role: str) -> CountingDeepEvalModel:
    if settings.provider == "ollama":
        model_name = os.getenv("OLLAMA_MODEL") or os.getenv("MODEL_NAME")
        if not model_name:
            raise ValueError("Set OLLAMA_MODEL (or MODEL_NAME) for the Ollama evaluator")
        return OllamaModel(
            model_name=model_name,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            settings=settings,
            role=role,
        )

    from config import MODEL_NAME, OPENAI_API_KEY, OPENAI_BASE_URL

    if not MODEL_NAME or not OPENAI_BASE_URL:
        raise ValueError(
            "MODEL_NAME and OPENAI_BASE_URL are required for openai_compatible evaluation"
        )
    return OpenAICompatibleModel(
        model_name=MODEL_NAME,
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY or "local-no-key",
        settings=settings,
        role=role,
    )
