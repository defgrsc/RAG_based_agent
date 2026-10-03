import json
import unittest
from unittest.mock import Mock, patch

import requests
from fastapi import HTTPException

from dependency_health import run_dependency_checks
from service_errors import EmbeddingServiceError, LLMServiceError, QdrantServiceError


class DependencyErrorTests(unittest.TestCase):
    @patch("llm.requests.post", side_effect=requests.Timeout("private endpoint timed out"))
    @patch("llm.EMBEDDING_PROVIDER", "ollama")
    def test_ollama_timeout_is_identified_as_embedding_failure(self, _post):
        from llm import embed_texts

        with self.assertRaises(EmbeddingServiceError) as raised:
            embed_texts(["測試"], timeout_seconds=0.1)

        detail = raised.exception.public_detail()
        self.assertEqual(detail["code"], "embedding_unavailable")
        self.assertEqual(detail["service"], "embedding")
        self.assertEqual(detail["category"], "timeout")
        self.assertNotIn("private endpoint", json.dumps(detail, ensure_ascii=False))


class DependencyHealthTests(unittest.TestCase):
    @patch(
        "dependency_health.probe_llm_service",
        return_value={
            "model": "test-model",
            "available_models": 1,
            "configured_model_found": True,
        },
    )
    @patch(
        "dependency_health.probe_qdrant_service",
        return_value={"collection": "test-collection", "points_count": 12},
    )
    @patch(
        "dependency_health.probe_embedding_service",
        return_value={
            "provider": "openai",
            "model": "test-embedding",
            "dimensions": 768,
        },
    )
    def test_all_dependency_probes_ready(self, _embedding, _qdrant, _llm):
        result = run_dependency_checks(timeout_seconds=0.2)

        self.assertTrue(result["ready"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["dependencies"]["embedding"]["status"], "ok")
        self.assertEqual(result["dependencies"]["qdrant"]["points_count"], 12)
        self.assertTrue(result["dependencies"]["llm"]["configured_model_found"])

    @patch(
        "dependency_health.probe_llm_service",
        return_value={
            "model": "test-model",
            "available_models": 1,
            "configured_model_found": True,
        },
    )
    @patch(
        "dependency_health.probe_qdrant_service",
        return_value={"collection": "test-collection", "points_count": 12},
    )
    @patch("dependency_health.probe_embedding_service")
    def test_one_failed_probe_marks_readiness_degraded(self, embedding, _qdrant, _llm):
        embedding.side_effect = EmbeddingServiceError(
            operation="embed",
            cause=requests.Timeout("do not expose this"),
        )

        result = run_dependency_checks(timeout_seconds=0.2)

        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "degraded")
        failed = result["dependencies"]["embedding"]
        self.assertEqual(failed["status"], "error")
        self.assertEqual(failed["code"], "embedding_unavailable")
        self.assertEqual(failed["category"], "timeout")
        self.assertNotIn("do not expose this", json.dumps(result, ensure_ascii=False))

    @patch("dependency_health.requests.get")
    def test_qdrant_probe_checks_the_active_collection(self, get):
        from dependency_health import probe_qdrant_service

        response = Mock()
        response.json.return_value = {"result": {"points_count": 31}}
        response.raise_for_status.return_value = None
        get.return_value = response

        result = probe_qdrant_service(0.25)

        self.assertEqual(result["points_count"], 31)
        self.assertIn("collection", result)
        self.assertEqual(get.call_args.kwargs["timeout"], 0.25)


class DependencyEndpointTests(unittest.TestCase):
    @patch("main.run_dependency_checks")
    def test_dependency_endpoint_uses_503_when_degraded(self, checks):
        from main import dependency_health

        checks.return_value = {
            "status": "degraded",
            "ready": False,
            "timeout_seconds": 5,
            "dependencies": {},
        }

        response = dependency_health()
        payload = json.loads(response.body)

        self.assertEqual(response.status_code, 503)
        self.assertFalse(payload["ready"])

    @patch("main.answer_cache.get", return_value=None)
    @patch("main.get_fast_answer", return_value=None)
    @patch("main.get_compiled_agent_graph")
    def test_chat_falls_back_for_embedding_and_reports_other_failures(
        self,
        compiled_graph,
        _fast_answer,
        _cache,
    ):
        from main import ChatRequest, chat

        compiled_graph.return_value.invoke.side_effect = EmbeddingServiceError(
            operation="embed",
            cause=requests.Timeout(),
        )
        response = chat(ChatRequest(message="宿網的流量限制與停權規則是什麼？"))

        answer = response["answer"]
        sources = response["sources"]
        self.assertIn("稍後再試", answer)
        self.assertTrue(sources)
        self.assertNotIn("Embedding", answer)
        self.assertNotIn("model", answer.lower())
        self.assertNotIn("URL", answer)

        cases = (
            (
                QdrantServiceError(operation="retrieve", cause=requests.ConnectionError()),
                "qdrant",
            ),
            (
                LLMServiceError(operation="generate", cause=requests.ConnectionError()),
                "llm",
            ),
        )
        for error, service in cases:
            with self.subTest(service=service):
                compiled_graph.return_value.invoke.side_effect = error

                with self.assertRaises(HTTPException) as raised:
                    chat(ChatRequest(message="宿網的流量限制與停權規則是什麼？"))

                self.assertEqual(raised.exception.status_code, 503)
                self.assertEqual(raised.exception.detail["code"], f"{service}_unavailable")
                self.assertEqual(raised.exception.detail["service"], service)


if __name__ == "__main__":
    unittest.main()
