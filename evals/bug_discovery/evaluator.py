from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from evals.bug_discovery.agent_adapter import is_clarification, is_refusal, normalize
from evals.bug_discovery.models import CountingDeepEvalModel
from evals.bug_discovery.schemas import (
    AssertionFailure,
    ConversationResult,
    EvaluatedTurn,
    FailureCategory,
    ScenarioDefinition,
)
from evals.bug_discovery.simulator import GeneratedConversation


PRIMARY_PRECEDENCE = (
    FailureCategory.REFERENCE_RESOLUTION_ERROR,
    FailureCategory.TOPIC_CLASSIFICATION_ERROR,
    FailureCategory.INTENT_CLASSIFICATION_ERROR,
    FailureCategory.CONTEXT_CONTAMINATION,
    FailureCategory.QUERY_REWRITE_ERROR,
    FailureCategory.WRONG_DOMAIN_RETRIEVAL,
    FailureCategory.UNNECESSARY_REFUSAL,
    FailureCategory.ANSWER_GENERATION_ERROR,
    FailureCategory.DEPENDENCY_UNAVAILABLE,
    FailureCategory.INCONSISTENT_OUTPUT,
    FailureCategory.UNKNOWN,
)


class SemanticDecision(BaseModel):
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    category: Literal[
        "UNNECESSARY_REFUSAL",
        "ANSWER_GENERATION_ERROR",
        "UNKNOWN",
    ] = "ANSWER_GENERATION_ERROR"
    reason: str


def _contains(text: str, marker: str) -> bool:
    return normalize(marker) in normalize(text)


def validate_simulated_message(message: str, scenario_turn) -> list[str]:
    generation = scenario_turn.generation
    issues: list[str] = []
    if generation.must_include_any and not any(
        _contains(message, marker) for marker in generation.must_include_any
    ):
        issues.append(f"missing any of {generation.must_include_any}")
    for group in generation.must_include_groups:
        if group and not any(_contains(message, marker) for marker in group):
            issues.append(
                f"missing one marker from required group {group}"
            )
    for marker in generation.must_include_all:
        if not _contains(message, marker):
            issues.append(f"missing required marker {marker!r}")
    for marker in generation.must_not_include:
        if _contains(message, marker):
            issues.append(f"contains forbidden marker {marker!r}")
    return issues


def failure(
    category: FailureCategory,
    reason: str,
    **evidence,
) -> AssertionFailure:
    return AssertionFailure(category=category, reason=reason, evidence=evidence)


def evaluate_turn(turn: EvaluatedTurn) -> None:
    expected = turn.expected
    actual = turn.actual
    failures = turn.failures

    if actual.error_code and actual.error_code.endswith("_unavailable"):
        failures.append(
            failure(
                FailureCategory.DEPENDENCY_UNAVAILABLE,
                "External dependency was unavailable; this is not classified as an Agent logic bug",
                code=actual.error_code,
                service=actual.error_service,
                error_category=actual.error_category,
            )
        )
        return

    if actual.error:
        failures.append(
            failure(FailureCategory.UNKNOWN, "Agent call raised an error", error=actual.error)
        )
        return

    if expected.topic is not None and actual.topic != expected.topic:
        failures.append(
            failure(
                FailureCategory.TOPIC_CLASSIFICATION_ERROR,
                "topic mismatch",
                expected=expected.topic,
                actual=actual.topic,
            )
        )

    if (
        expected.reference_status is not None
        and actual.reference_status != expected.reference_status
    ):
        failures.append(
            failure(
                FailureCategory.REFERENCE_RESOLUTION_ERROR,
                "reference status mismatch",
                expected=expected.reference_status,
                actual=actual.reference_status,
            )
        )
    if (
        expected.referenced_turn_ids is not None
        and actual.referenced_turn_ids != expected.referenced_turn_ids
    ):
        failures.append(
            failure(
                FailureCategory.REFERENCE_RESOLUTION_ERROR,
                "referenced turn ids mismatch",
                expected=expected.referenced_turn_ids,
                actual=actual.referenced_turn_ids,
            )
        )
    if expected.relation is not None and actual.relation != expected.relation:
        failures.append(
            failure(
                FailureCategory.REFERENCE_RESOLUTION_ERROR,
                "conversation relation mismatch",
                expected=expected.relation,
                actual=actual.relation,
            )
        )

    if expected.intent is not None and actual.intent != expected.intent:
        failures.append(
            failure(
                FailureCategory.INTENT_CLASSIFICATION_ERROR,
                "intent mismatch",
                expected=expected.intent,
                actual=actual.intent,
                source=actual.intent_source,
            )
        )

    missing_qualifiers = sorted(set(expected.qualifiers) - set(actual.qualifiers))
    if missing_qualifiers:
        failures.append(
            failure(
                FailureCategory.QUERY_REWRITE_ERROR,
                "qualifier missing from observed standalone query",
                missing=missing_qualifiers,
                actual=actual.qualifiers,
            )
        )

    contaminated_ids = sorted(
        set(expected.relevant_history_excludes)
        & set(actual.relevant_history_turn_ids)
    )
    if contaminated_ids:
        failures.append(
            failure(
                FailureCategory.CONTEXT_CONTAMINATION,
                "irrelevant prior turns were selected",
                forbidden_turn_ids=expected.relevant_history_excludes,
                selected_turn_ids=actual.relevant_history_turn_ids,
            )
        )

    standalone = normalize(actual.standalone_query)
    for marker in expected.standalone_contains_all:
        if normalize(marker) not in standalone:
            failures.append(
                failure(
                    FailureCategory.QUERY_REWRITE_ERROR,
                    "standalone query is missing a required concept",
                    marker=marker,
                    standalone_query=actual.standalone_query,
                )
            )
    if expected.standalone_contains_any and not any(
        normalize(marker) in standalone for marker in expected.standalone_contains_any
    ):
        failures.append(
            failure(
                FailureCategory.QUERY_REWRITE_ERROR,
                "standalone query is missing all alternative required concepts",
                markers=expected.standalone_contains_any,
                standalone_query=actual.standalone_query,
            )
        )
    forbidden = [
        marker
        for marker in expected.standalone_forbids
        if normalize(marker) in standalone
    ]
    if forbidden:
        failures.append(
            failure(
                FailureCategory.QUERY_REWRITE_ERROR,
                "standalone query contains forbidden prior intent/topic concepts",
                forbidden=forbidden,
                standalone_query=actual.standalone_query,
            )
        )

    inferred_topics = {
        document.inferred_topic
        for document in actual.retrieval_documents
        if document.inferred_topic != "unknown"
    }
    if (
        expected.allowed_retrieval_topics
        and inferred_topics
        and inferred_topics.isdisjoint(expected.allowed_retrieval_topics)
    ):
        failures.append(
            failure(
                FailureCategory.WRONG_DOMAIN_RETRIEVAL,
                "all identifiable retrieval documents belong to another service",
                allowed=expected.allowed_retrieval_topics,
                actual=sorted(inferred_topics),
            )
        )

    refused = is_refusal(actual.final_answer)
    if expected.must_answer and refused:
        failures.append(
            failure(
                FailureCategory.UNNECESSARY_REFUSAL,
                "answerable scenario was refused",
                api_path=actual.api_path,
                retrieval_document_count=len(actual.retrieval_documents),
            )
        )
    if expected.must_clarify and not is_clarification(actual.final_answer):
        failures.append(
            failure(
                FailureCategory.REFERENCE_RESOLUTION_ERROR,
                "unresolved reference did not produce a clarification request",
                final_answer=actual.final_answer[:400],
            )
        )
    if expected.must_answer and not actual.final_answer.strip():
        failures.append(
            failure(
                FailureCategory.ANSWER_GENERATION_ERROR,
                "Agent returned an empty answer",
            )
        )


def finalize_result(result: ConversationResult) -> None:
    categories: list[FailureCategory] = []
    for turn in result.turns:
        for item in turn.failures:
            if item.category not in categories:
                categories.append(item.category)

    result.simulation_valid = all(turn.simulation_valid for turn in result.turns)
    if not result.simulation_valid:
        result.passed = False
        result.primary_failure = None
        result.secondary_failures = []
        return

    result.passed = not categories
    if not categories:
        result.primary_failure = None
        result.secondary_failures = []
        return

    result.primary_failure = next(
        (category for category in PRIMARY_PRECEDENCE if category in categories),
        FailureCategory.UNKNOWN,
    )
    result.secondary_failures = [
        category for category in categories if category != result.primary_failure
    ]


def evaluate_generated_conversation(
    generated: GeneratedConversation,
    *,
    repeat_index: int = 0,
) -> ConversationResult:
    scenario = generated.scenario
    evaluated_turns: list[EvaluatedTurn] = []
    expected_turns = scenario.turns
    observed_count = min(
        len(generated.user_messages),
        len(generated.assistant_messages),
        len(generated.traces),
        len(expected_turns),
    )

    for index in range(observed_count):
        scenario_turn = expected_turns[index]
        simulation_issues = validate_simulated_message(
            generated.user_messages[index], scenario_turn
        )
        evaluated = EvaluatedTurn(
            turn_id=index + 1,
            user_message=generated.user_messages[index],
            assistant_message=generated.assistant_messages[index],
            expected=scenario_turn.expected,
            actual=generated.traces[index],
            simulation_valid=not simulation_issues,
            simulation_issues=simulation_issues,
        )
        if evaluated.simulation_valid:
            evaluate_turn(evaluated)
        evaluated_turns.append(evaluated)

    if observed_count != len(expected_turns):
        # This is a simulator quality issue, not an Agent failure.
        placeholder_count = len(expected_turns) - observed_count
        if evaluated_turns:
            evaluated_turns[-1].simulation_valid = False
            evaluated_turns[-1].simulation_issues.append(
                f"turn count mismatch: expected {len(expected_turns)}, observed {observed_count}"
            )
        elif placeholder_count:
            raise ValueError(
                f"Simulator returned no complete turns for {scenario.scenario_id}"
            )

    result = ConversationResult(
        execution_id=generated.execution_id,
        scenario_id=scenario.scenario_id,
        category=scenario.category,
        variant_index=generated.variant_index,
        repeat_index=repeat_index,
        session_id=generated.session_id,
        expected_outcome=scenario.expected_outcome,
        semantic_criteria=scenario.semantic_criteria,
        turns=evaluated_turns,
    )
    finalize_result(result)
    return result


class HybridSemanticEvaluator:
    """One local LLM judge call, only after deterministic checks pass."""

    def __init__(self, model: CountingDeepEvalModel):
        self.model = model

    def evaluate(self, result: ConversationResult) -> None:
        if not result.simulation_valid or not result.passed or not result.semantic_criteria:
            return

        transcript = result.conversation()
        traces = [
            {
                "turn_id": turn.turn_id,
                "topic": turn.actual.topic,
                "intent": turn.actual.intent,
                "standalone_query": turn.actual.standalone_query,
                "retrieval_titles": [
                    document.title for document in turn.actual.retrieval_documents
                ],
            }
            for turn in result.turns
        ]
        prompt = f"""
Judge this NTHU campus information conversation. Use only the scenario,
criteria, transcript, and observed retrieval titles below. Do not invent
unwritten university policy. Pass when the response follows the requested
topic/intent and addresses the expected behavior. Fail only for a clear
semantic answer defect or unnecessary refusal.

Expected outcome:
{result.expected_outcome}

Criteria:
{json.dumps(result.semantic_criteria, ensure_ascii=False)}

Transcript:
{json.dumps(transcript, ensure_ascii=False)}

Intermediate observations:
{json.dumps(traces, ensure_ascii=False)}

Return the required JSON decision.
""".strip()
        try:
            decision = self.model.generate(prompt, schema=SemanticDecision)
        except Exception as exc:
            result.semantic_reason = f"semantic evaluator error (not counted as Agent failure): {exc}"
            return

        result.semantic_score = decision.score
        result.semantic_reason = decision.reason
        if decision.passed:
            return

        category = FailureCategory(decision.category)
        result.turns[-1].failures.append(
            failure(
                category,
                f"semantic evaluator: {decision.reason}",
                score=decision.score,
                model=self.model.get_model_name(),
            )
        )
        finalize_result(result)
