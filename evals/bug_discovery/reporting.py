from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.bug_discovery.schemas import ConversationResult, FailureCategory


REGRESSION_CANDIDATE_CATEGORIES = {
    FailureCategory.CONTEXT_CONTAMINATION,
    FailureCategory.REFERENCE_RESOLUTION_ERROR,
    FailureCategory.TOPIC_CLASSIFICATION_ERROR,
    FailureCategory.INTENT_CLASSIFICATION_ERROR,
    FailureCategory.QUERY_REWRITE_ERROR,
    FailureCategory.WRONG_DOMAIN_RETRIEVAL,
    FailureCategory.UNNECESSARY_REFUSAL,
}


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _failure_id(result: ConversationResult) -> str:
    material = json.dumps(
        {
            "scenario_id": result.scenario_id,
            "user_messages": [turn.user_message for turn in result.turns],
            "primary": result.primary_failure,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def consistency_stats(results: list[ConversationResult]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[ConversationResult]] = defaultdict(list)
    for result in results:
        groups[(result.scenario_id, result.variant_index)].append(result)

    rows: list[dict[str, Any]] = []
    for (scenario_id, variant_index), group in sorted(groups.items()):
        evaluated = [item for item in group if item.simulation_valid]
        failed = [item for item in evaluated if not item.passed]
        categories = Counter(
            str(item.primary_failure) for item in failed if item.primary_failure
        )
        refusal_count = sum(
            item.primary_failure == FailureCategory.UNNECESSARY_REFUSAL
            or FailureCategory.UNNECESSARY_REFUSAL in item.secondary_failures
            for item in failed
        )
        contamination_count = sum(
            item.primary_failure == FailureCategory.CONTEXT_CONTAMINATION
            or FailureCategory.CONTEXT_CONTAMINATION in item.secondary_failures
            for item in failed
        )
        wrong_answer_count = sum(
            item.primary_failure == FailureCategory.ANSWER_GENERATION_ERROR
            or FailureCategory.ANSWER_GENERATION_ERROR in item.secondary_failures
            for item in failed
        )
        answer_hashes = {
            hashlib.sha256(
                "\n".join(turn.assistant_message for turn in item.turns).encode("utf-8")
            ).hexdigest()[:12]
            for item in evaluated
        }
        rows.append(
            {
                "scenario_id": scenario_id,
                "variant_index": variant_index,
                "runs": len(group),
                "evaluated_runs": len(evaluated),
                "success_rate": _rate(len(evaluated) - len(failed), len(evaluated)),
                "wrong_answer_rate": _rate(wrong_answer_count, len(evaluated)),
                "unnecessary_refusal_rate": _rate(refusal_count, len(evaluated)),
                "context_contamination_rate": _rate(contamination_count, len(evaluated)),
                "failure_categories": dict(categories),
                "unique_answer_hashes": len(answer_hashes),
            }
        )
    return rows


def build_summary(
    results: list[ConversationResult],
    *,
    profile_name: str,
    model_config: dict[str, Any],
    model_calls: dict[str, Any],
) -> dict[str, Any]:
    valid = [result for result in results if result.simulation_valid]
    invalid = [result for result in results if not result.simulation_valid]
    failed = [result for result in valid if not result.passed]
    passed = [result for result in valid if result.passed]
    breakdown = Counter(
        str(result.primary_failure)
        for result in failed
        if result.primary_failure is not None
    )
    symptom_breakdown = Counter(
        str(category)
        for result in failed
        for category in (
            [result.primary_failure] + list(result.secondary_failures)
            if result.primary_failure is not None
            else result.secondary_failures
        )
    )

    def affected(category: FailureCategory) -> int:
        return sum(
            result.primary_failure == category
            or category in result.secondary_failures
            for result in failed
        )

    regression_candidates = [
        _failure_id(result)
        for result in failed
        if result.primary_failure in REGRESSION_CANDIDATE_CATEGORIES
    ]
    return {
        "profile": profile_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_conversations": len(results),
        "evaluated_conversations": len(valid),
        "passed": len(passed),
        "failed": len(failed),
        "invalid_simulations": len(invalid),
        "success_rate": _rate(len(passed), len(valid)),
        "failure_breakdown": dict(sorted(breakdown.items())),
        "all_failure_symptoms": dict(sorted(symptom_breakdown.items())),
        "rates": {
            "wrong_answer_rate": _rate(
                affected(FailureCategory.ANSWER_GENERATION_ERROR), len(valid)
            ),
            "unnecessary_refusal_rate": _rate(
                affected(FailureCategory.UNNECESSARY_REFUSAL), len(valid)
            ),
            "context_contamination_rate": _rate(
                affected(FailureCategory.CONTEXT_CONTAMINATION), len(valid)
            ),
            "dependency_unavailable_rate": _rate(
                affected(FailureCategory.DEPENDENCY_UNAVAILABLE), len(valid)
            ),
        },
        "model_config": model_config,
        "model_calls": model_calls,
        "consistency": consistency_stats(results),
        "regression_candidate_failure_ids": regression_candidates,
    }


def failure_record(
    result: ConversationResult,
    *,
    timestamp: str,
    model_config: dict[str, Any],
    consistency: dict[str, Any] | None,
) -> dict[str, Any]:
    failed_turns = [turn for turn in result.turns if turn.failures]
    return {
        "failure_id": _failure_id(result),
        "scenario_id": result.scenario_id,
        "category": result.category,
        "execution_id": result.execution_id,
        "variant_index": result.variant_index,
        "repeat_index": result.repeat_index,
        "session_id": result.session_id,
        "conversation": result.conversation(),
        "expected": {
            "outcome": result.expected_outcome,
            "semantic_criteria": result.semantic_criteria,
            "turns": [turn.expected.model_dump(mode="json") for turn in result.turns],
        },
        "actual": {
            "turns": [turn.actual.model_dump(mode="json") for turn in result.turns],
            "semantic_score": result.semantic_score,
            "semantic_reason": result.semantic_reason,
        },
        "langgraph_intermediate_state": [
            {
                "turn_id": turn.turn_id,
                "reference_status": turn.actual.reference_status,
                "referenced_turn_ids": turn.actual.referenced_turn_ids,
                "topic": turn.actual.topic,
                "intent": turn.actual.intent,
                "intent_source": turn.actual.intent_source,
                "qualifiers": turn.actual.qualifiers,
                "standalone_query": turn.actual.standalone_query,
                "relevant_history_turn_ids": turn.actual.relevant_history_turn_ids,
                "retrieval_documents": [
                    document.model_dump(mode="json")
                    for document in turn.actual.retrieval_documents
                ],
                "final_answer": turn.actual.final_answer,
                "api_path": turn.actual.api_path,
            }
            for turn in result.turns
        ],
        "failure_category": str(result.primary_failure),
        "secondary_symptoms": [str(item) for item in result.secondary_failures],
        "assertions": [
            item.model_dump(mode="json")
            for turn in failed_turns
            for item in turn.failures
        ],
        "timestamp": timestamp,
        "model_config_version": model_config,
        "consistency": consistency,
        "regression_candidate": result.primary_failure
        in REGRESSION_CANDIDATE_CATEGORIES,
        "review_status": "unreviewed",
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def write_report(
    results: list[ConversationResult],
    *,
    project_root: Path,
    run_id: str,
    profile_name: str,
    output_directory: str,
    failures_directory: str,
    model_config: dict[str, Any],
    model_calls: dict[str, Any],
) -> tuple[dict[str, Any], Path]:
    summary = build_summary(
        results,
        profile_name=profile_name,
        model_config=model_config,
        model_calls=model_calls,
    )
    run_dir = project_root / output_directory / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    timestamp = summary["timestamp"]

    consistency_index = {
        (row["scenario_id"], row["variant_index"]): row
        for row in summary["consistency"]
    }
    failures = [
        failure_record(
            result,
            timestamp=timestamp,
            model_config=model_config,
            consistency=consistency_index.get(
                (result.scenario_id, result.variant_index)
            ),
        )
        for result in results
        if result.simulation_valid and not result.passed
    ]
    invalid = [
        {
            "scenario_id": result.scenario_id,
            "execution_id": result.execution_id,
            "conversation": result.conversation(),
            "issues": [
                issue
                for turn in result.turns
                for issue in turn.simulation_issues
            ],
            "timestamp": timestamp,
        }
        for result in results
        if not result.simulation_valid
    ]

    (run_dir / "results.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "conversations": [
                    result.model_dump(mode="json") for result in results
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_jsonl(run_dir / "failures.jsonl", failures)
    _write_jsonl(run_dir / "invalid_simulations.jsonl", invalid)

    failure_dir = project_root / failures_directory
    _write_jsonl(failure_dir / f"{run_id}.jsonl", failures)
    _write_jsonl(failure_dir / "latest.jsonl", failures)
    _write_jsonl(failure_dir / "invalid_simulations.jsonl", invalid)

    breakdown_lines = (
        [
            f"- {category}: {count}"
            for category, count in summary["failure_breakdown"].items()
        ]
        or ["- None"]
    )
    symptom_lines = (
        [
            f"- {category}: {count}"
            for category, count in summary["all_failure_symptoms"].items()
        ]
        or ["- None"]
    )
    report = [
        f"# Automatic Agent Bug Discovery — {profile_name}",
        "",
        f"- Run ID: {run_id}",
        f"- Total conversations: {summary['total_conversations']}",
        f"- Evaluated: {summary['evaluated_conversations']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Invalid simulations: {summary['invalid_simulations']}",
        f"- Success rate: {summary['success_rate']:.2%}",
        "",
        "## Failure breakdown",
        "",
        *breakdown_lines,
        "",
        "## All failure symptoms (primary + secondary)",
        "",
        *symptom_lines,
        "",
        "## Rates",
        "",
        f"- Wrong answer rate: {summary['rates']['wrong_answer_rate']:.2%}",
        f"- Unnecessary refusal rate: {summary['rates']['unnecessary_refusal_rate']:.2%}",
        f"- Context contamination rate: {summary['rates']['context_contamination_rate']:.2%}",
        "",
        "## Model calls",
        "",
        f"- Simulator calls: {model_calls.get('simulator_actual', 0)}",
        f"- Evaluator calls: {model_calls.get('evaluator_actual', 0)}",
        f"- Agent generation-path turns: {model_calls.get('agent_generation_path_turns', 0)}",
        f"- Estimated maximum total calls: {model_calls.get('estimated_max_total', 0)}",
        "",
        "## Regression candidates",
        "",
        *(
            [f"- {item}" for item in summary["regression_candidate_failure_ids"]]
            or ["- None"]
        ),
        "",
        "Raw results and traces are in results.json; machine-readable failures are in failures.jsonl.",
        "",
    ]
    (run_dir / "report.md").write_text("\n".join(report), encoding="utf-8")
    return summary, run_dir
