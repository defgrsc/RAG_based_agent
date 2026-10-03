from __future__ import annotations

import argparse
import io
import json
import logging
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable

from agent.graph import prepare_agent_context
from evals.bug_discovery.agent_adapter import (
    InProcessAgentAdapter,
    is_clarification,
    is_refusal,
)
from evals.bug_discovery.schemas import AgentSettings


HERE = Path(__file__).resolve().parent
DATASET_PATH = HERE / "generated_cases.json"
FAILURE_ORDER = (
    "REFERENCE_ERROR",
    "TOPIC_ERROR",
    "INTENT_ERROR",
    "ENTITY_ERROR",
    "HISTORY_SELECTION_ERROR",
    "RETRIEVAL_ERROR",
    "TOOL_ERROR",
    "GENERATION_ERROR",
    "LANGUAGE_ERROR",
    "REFUSAL_ERROR",
    "STATE_CONTAMINATION",
    "UNKNOWN",
)
LEAK_MARKERS = (
    "available nthu network information",
    "retrieved context",
    "retrieval result",
    "system prompt",
    "rag context",
    "coverage data",
    "檢索內容",
    "系統提示",
    "可用的清大網路資訊",
)


def failure(category: str, reason: str, **evidence: Any) -> dict[str, Any]:
    return {"category": category, "reason": reason, "evidence": evidence}


def _contains(text: str, marker: str) -> bool:
    return marker.casefold() in text.casefold()


def _language_ok(answer: str, language: str) -> bool:
    cjk = len(re.findall(r"[\u3400-\u9fff]", answer))
    latin = len(re.findall(r"[A-Za-z]", answer))
    if language == "zh-Hant":
        return cjk >= 2
    return cjk <= max(4, int((latin + cjk) * 0.08))


def _is_refusal(answer: str) -> bool:
    normalized = " ".join(answer.casefold().split())
    markers = (
        "不在服務範圍", "僅提供清華大學", "無法協助", "無法回答",
        "outside", "out of scope", "only assist with", "cannot help",
    )
    return is_refusal(answer) or any(marker in normalized for marker in markers)


def evaluate_turn(
    expected: dict[str, Any],
    state: dict[str, Any],
    trace: dict[str, Any],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    answer = str(trace.get("final_answer", ""))

    if trace.get("error"):
        failures.append(failure(
            "TOOL_ERROR",
            "The real agent call raised an error.",
            error=trace.get("error"),
            error_code=trace.get("error_code"),
            route=trace.get("api_path"),
        ))
        return failures

    for field, category in (("topic", "TOPIC_ERROR"), ("intent", "INTENT_ERROR")):
        actual = trace.get(field)
        wanted = expected.get(field)
        if wanted is not None and actual != wanted:
            failures.append(failure(category, f"{field} mismatch", expected=wanted, actual=actual))

    slots = state.get("semantic_slots", {})
    for key, wanted in expected.get("entities", {}).items():
        actual = slots.get(key)
        if actual != wanted:
            failures.append(failure(
                "ENTITY_ERROR", "semantic slot mismatch", slot=key,
                expected=wanted, actual=actual, semantic_slots=slots,
            ))

    reference_evidence: dict[str, Any] = {}
    for field in ("relation", "reference_status", "referenced_turn_ids"):
        wanted = expected.get(field)
        actual = trace.get(field)
        if wanted is not None and actual != wanted:
            reference_evidence[field] = {"expected": wanted, "actual": actual}
    if reference_evidence:
        failures.append(failure("REFERENCE_ERROR", "reference state mismatch", **reference_evidence))

    relevant_ids = trace.get("relevant_history_turn_ids", [])
    leaked_ids = sorted(set(relevant_ids) & set(expected.get("relevant_history_excludes", [])))
    if leaked_ids:
        failures.append(failure(
            "HISTORY_SELECTION_ERROR", "irrelevant turn selected",
            excluded_turn_ids=expected.get("relevant_history_excludes", []),
            actual_turn_ids=relevant_ids,
        ))

    documents = trace.get("retrieval_documents", [])
    observed_topics = sorted({
        doc.get("inferred_topic", "unknown")
        for doc in documents
        if doc.get("inferred_topic", "unknown") != "unknown"
    })
    allowed_topics = expected.get("allowed_retrieval_topics", [])
    wrong_topics = sorted(set(observed_topics) - set(allowed_topics)) if allowed_topics else []
    if wrong_topics:
        failures.append(failure(
            "RETRIEVAL_ERROR", "retrieval crossed service boundaries",
            allowed_topics=allowed_topics, observed_topics=observed_topics,
            documents=documents,
        ))

    refused = _is_refusal(answer)
    clarified = is_clarification(answer)
    if expected.get("must_refuse") and not refused:
        failures.append(failure("REFUSAL_ERROR", "out-of-scope request was not refused", answer=answer))
    if not expected.get("must_refuse") and expected.get("topic") not in {"unknown", None} and refused:
        failures.append(failure("REFUSAL_ERROR", "in-scope request was unnecessarily refused", answer=answer))
    if expected.get("must_clarify") and not clarified:
        failures.append(failure("REFERENCE_ERROR", "unresolved reference did not trigger clarification", answer=answer))

    if not answer.strip():
        failures.append(failure("GENERATION_ERROR", "empty answer"))
    elif not expected.get("must_refuse") and not expected.get("must_clarify"):
        required = expected.get("answer_contains_any", [])
        if required and not any(_contains(answer, marker) for marker in required):
            failures.append(failure(
                "GENERATION_ERROR", "answer lacks any expected service marker",
                expected_any=required, answer=answer,
            ))

    forbidden = [marker for marker in expected.get("answer_forbids", []) if _contains(answer, marker)]
    if forbidden:
        failures.append(failure(
            "STATE_CONTAMINATION", "answer contains content from an excluded topic/turn",
            matched=forbidden, answer=answer,
        ))

    leaks = [marker for marker in LEAK_MARKERS if _contains(answer, marker)]
    if leaks:
        failures.append(failure(
            "GENERATION_ERROR", "answer leaked internal implementation wording",
            matched=leaks, answer=answer,
        ))

    if answer.strip() and not _language_ok(answer, trace.get("language", state.get("language", "zh-Hant"))):
        failures.append(failure(
            "LANGUAGE_ERROR", "answer language does not match the current turn",
            expected_language=trace.get("language", state.get("language")), answer=answer,
        ))
    return failures


def primary_failure(failures: list[dict[str, Any]]) -> str | None:
    categories = {item["category"] for item in failures}
    return next((category for category in FAILURE_ORDER if category in categories), None)


def _rate(values: list[bool]) -> dict[str, Any]:
    passed = sum(values)
    total = len(values)
    return {
        "passed": passed,
        "total": total,
        "rate": round(passed / total, 4) if total else None,
    }


def _matching_turns(
    results: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any], dict[str, Any]], bool],
) -> list[dict[str, Any]]:
    return [
        turn
        for case in results
        for turn in case["turns"]
        if predicate(case, turn)
    ]


def summarize(results: list[dict[str, Any]], composition: dict[str, Any]) -> dict[str, Any]:
    turns = [turn for case in results for turn in case["turns"]]
    primary_counts = Counter(
        turn["primary_failure"] for turn in turns if turn["primary_failure"]
    )
    all_counts = Counter(
        item["category"] for turn in turns for item in turn["failures"]
    )
    single = _matching_turns(results, lambda case, _turn: case["kind"] == "single_turn")
    multi = _matching_turns(results, lambda case, _turn: case["kind"] != "single_turn")
    zh_single = _matching_turns(results, lambda case, _turn: case["test_id"].startswith("zh_single_"))
    en_single = _matching_turns(results, lambda case, _turn: case["test_id"].startswith("en_single_"))
    topic_switch = _matching_turns(results, lambda case, turn: "topic_switch" in case["tags"] and turn["turn_id"] > 1)
    intent_switch = _matching_turns(results, lambda case, turn: "intent_switch" in case["tags"] and turn["turn_id"] > 1)
    backward = _matching_turns(results, lambda case, turn: "backward_reference" in case["tags"] and turn["turn_id"] > 2)
    retrieval = [
        turn for turn in turns
        if turn["actual"]["retrieval_documents"]
        and turn["expected"].get("allowed_retrieval_topics")
    ]
    bilingual = _matching_turns(results, lambda case, turn: case["kind"] == "bilingual_multi_turn" and turn["turn_id"] > 1)
    latencies = [turn["actual"]["latency_seconds"] for turn in turns]
    routes = Counter(turn["actual"]["api_path"] for turn in turns)
    return {
        "composition": composition,
        "conversation_pass_rate": _rate([case["passed"] for case in results]),
        "turn_pass_rate": _rate([turn["passed"] for turn in turns]),
        "metrics": {
            "single_turn_accuracy": _rate([turn["passed"] for turn in single]),
            "zh_single_turn_accuracy": _rate([turn["passed"] for turn in zh_single]),
            "en_single_turn_accuracy": _rate([turn["passed"] for turn in en_single]),
            "multi_turn_success_rate": _rate([turn["passed"] for turn in multi]),
            "topic_switch_accuracy": _rate([
                not any(item["category"] in {"TOPIC_ERROR", "REFERENCE_ERROR", "HISTORY_SELECTION_ERROR", "STATE_CONTAMINATION"} for item in turn["failures"])
                for turn in topic_switch
            ]),
            "intent_switch_accuracy": _rate([
                not any(item["category"] in {"INTENT_ERROR", "REFERENCE_ERROR", "HISTORY_SELECTION_ERROR", "STATE_CONTAMINATION"} for item in turn["failures"])
                for turn in intent_switch
            ]),
            "backward_reference_accuracy": _rate([
                not any(item["category"] in {"REFERENCE_ERROR", "TOPIC_ERROR", "HISTORY_SELECTION_ERROR", "STATE_CONTAMINATION"} for item in turn["failures"])
                for turn in backward
            ]),
            "retrieval_isolation_correctness": _rate([
                not any(item["category"] == "RETRIEVAL_ERROR" for item in turn["failures"])
                for turn in retrieval
            ]),
            "bilingual_consistency": _rate([
                not any(item["category"] in {"LANGUAGE_ERROR", "TOPIC_ERROR", "INTENT_ERROR", "REFERENCE_ERROR"} for item in turn["failures"])
                for turn in bilingual
            ]),
        },
        "failure_distribution": {
            "primary": dict(primary_counts.most_common()),
            "all": dict(all_counts.most_common()),
        },
        "routes": dict(routes.most_common()),
        "latency_seconds": {
            "mean": round(statistics.mean(latencies), 4) if latencies else None,
            "median": round(statistics.median(latencies), 4) if latencies else None,
            "max": round(max(latencies), 4) if latencies else None,
        },
    }


def markdown_report(label: str, summary: dict[str, Any], results: list[dict[str, Any]]) -> str:
    lines = [
        f"# Architecture Review Evaluation — {label}",
        "",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        "## Dataset and outcome",
        "",
        f"- Conversations: {summary['composition']['total_conversations']}",
        f"- Turns: {summary['composition']['total_turns']}",
        f"- Conversation pass rate: {summary['conversation_pass_rate']['rate']}",
        f"- Turn pass rate: {summary['turn_pass_rate']['rate']}",
        "",
        "## Required metrics",
        "",
        "| Metric | Passed | Total | Rate |",
        "|---|---:|---:|---:|",
    ]
    for name, metric in summary["metrics"].items():
        lines.append(f"| {name} | {metric['passed']} | {metric['total']} | {metric['rate']} |")
    lines.extend([
        "",
        "## Failure distribution",
        "",
        "| Primary failure | Count |",
        "|---|---:|",
    ])
    for category, count in summary["failure_distribution"]["primary"].items():
        lines.append(f"| {category} | {count} |")
    lines.extend(["", "## Representative failures", ""])
    failed_turns = [
        (case, turn)
        for case in results for turn in case["turns"] if not turn["passed"]
    ]
    for case, turn in failed_turns[:20]:
        lines.extend([
            f"### {case['test_id']} / turn {turn['turn_id']} — {turn['primary_failure']}",
            "",
            f"- User: {turn['user']}",
            f"- Actual state: topic={turn['actual']['topic']}, intent={turn['actual']['intent']}, relation={turn['actual']['relation']}, reference={turn['actual']['reference_status']} {turn['actual']['referenced_turn_ids']}",
            f"- Route: {turn['actual']['api_path']}",
            f"- Failures: {', '.join(item['category'] for item in turn['failures'])}",
            f"- Answer: {turn['actual']['final_answer'][:500]}",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def execute(dataset: dict[str, Any], label: str, limit: int | None) -> list[dict[str, Any]]:
    settings = AgentSettings(
        adapter="inprocess",
        base_url="http://127.0.0.1:8000",
        timeout_seconds=120,
        language="zh-Hant",
        clear_cache_between_conversations=False,
    )
    adapter = InProcessAgentAdapter(settings)
    cases = dataset["cases"][:limit] if limit else dataset["cases"]
    results: list[dict[str, Any]] = []
    for case_index, case in enumerate(cases, start=1):
        session_id = f"arch-{label}-{case['test_id']}"
        history: list[dict[str, str]] = []
        turns: list[dict[str, Any]] = []
        adapter.start_session(session_id)
        try:
            for turn_id, definition in enumerate(case["conversation"], start=1):
                user = definition["user"]
                language = definition["language"]
                quiet = io.StringIO()
                logging.disable(logging.CRITICAL)
                try:
                    with redirect_stdout(quiet), redirect_stderr(quiet):
                        state = prepare_agent_context(user, history, language=language)
                        trace = adapter.run_turn(
                            session_id=session_id,
                            message=user,
                            history=history,
                            language=language,
                        )
                finally:
                    logging.disable(logging.NOTSET)
                actual = trace.model_dump(mode="json")
                actual["language"] = language
                expected = definition["expected"]
                failures = evaluate_turn(expected, state, actual)
                turns.append({
                    "turn_id": turn_id,
                    "user": user,
                    "language": language,
                    "expected": expected,
                    "actual_state": {
                        "semantic_slots": state.get("semantic_slots", {}),
                        "current_slots": state.get("current_slots", {}),
                        "referenced_slots": state.get("referenced_slots", {}),
                        "intent_source": state.get("intent_source"),
                        "reference_kind": state.get("reference_kind"),
                        "relevant_turn_ids": state.get("relevant_turn_ids", []),
                        "retrieval_filter": state.get("retrieval_filter"),
                    },
                    "actual": actual,
                    "failures": failures,
                    "primary_failure": primary_failure(failures),
                    "passed": not failures,
                })
                history.extend([
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": actual["final_answer"]},
                ])
        finally:
            adapter.end_session(session_id)
        case_failures = [turn["primary_failure"] for turn in turns if turn["primary_failure"]]
        results.append({
            "test_id": case["test_id"],
            "kind": case["kind"],
            "language_group": case["language_group"],
            "tags": case["tags"],
            "turns": turns,
            "passed": all(turn["passed"] for turn in turns),
            "primary_failure": case_failures[0] if case_failures else None,
        })
        if case_index % 10 == 0 or case_index == len(cases):
            passed = sum(result["passed"] for result in results)
            print(f"[{label}] {case_index}/{len(cases)} conversations; passed={passed}", flush=True)
    return results


def write_outputs(
    label: str,
    dataset: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    effective_composition = dict(dataset["composition"])
    effective_composition["total_conversations"] = len(results)
    effective_composition["total_turns"] = sum(len(case["turns"]) for case in results)
    summary = summarize(results, effective_composition)
    payload = {
        "label": label,
        "evaluated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dataset": str(DATASET_PATH.relative_to(HERE.parent.parent)),
        "summary": summary,
        "results": results,
    }
    failed = [case for case in results if not case["passed"]]
    run_dir = HERE / "runs" / label
    run_dir.mkdir(parents=True, exist_ok=True)
    report = markdown_report(label, summary, results)
    (run_dir / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "failed_cases.json").write_text(json.dumps(failed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "evaluation_report.md").write_text(report, encoding="utf-8")
    prefix = "baseline" if label == "baseline" else label
    (HERE / f"{prefix}_results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / f"{prefix}_failed_cases.json").write_text(json.dumps(failed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / f"{prefix}_evaluation_report.md").write_text(report, encoding="utf-8")
    if label == "baseline":
        (HERE / "failed_cases.json").write_text(json.dumps(failed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (HERE / "evaluation_report.md").write_text(report, encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    results = execute(dataset, args.label, args.limit)
    summary = write_outputs(args.label, dataset, results)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
