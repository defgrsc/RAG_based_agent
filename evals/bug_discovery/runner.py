from __future__ import annotations

import os
import subprocess
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.bug_discovery.agent_adapter import build_agent_adapter, is_refusal
from evals.bug_discovery.evaluator import (
    HybridSemanticEvaluator,
    evaluate_generated_conversation,
    failure,
    finalize_result,
)
from evals.bug_discovery.loader import (
    PROJECT_ROOT,
    load_config,
    load_scenarios,
    select_scenarios,
)
from evals.bug_discovery.models import build_model
from evals.bug_discovery.reporting import write_report
from evals.bug_discovery.schemas import (
    EvalConfig,
    FailureCategory,
    Profile,
)
from evals.bug_discovery.simulator import (
    DeepEvalScenarioSimulator,
    GeneratedConversation,
    ScenarioVariant,
    TemplateScenarioSimulator,
)


def build_variants(
    scenarios,
    profile: Profile,
) -> list[ScenarioVariant]:
    variants: list[ScenarioVariant] = []
    for scenario in scenarios:
        for variant_index in range(profile.variants_per_scenario):
            variants.append(
                ScenarioVariant(
                    scenario=scenario,
                    variant_index=variant_index,
                )
            )
    return variants[: profile.max_conversations]


def estimate_calls(variants: list[ScenarioVariant], profile: Profile) -> dict[str, int]:
    generated_turns = sum(
        min(len(variant.scenario.turns), profile.max_turns)
        for variant in variants
    )
    agent_turns = generated_turns * profile.consistency_runs
    evaluator_calls = (
        len(variants) * profile.consistency_runs
        if profile.evaluator == "hybrid"
        else 0
    )
    return {
        "conversations_generated": len(variants),
        "conversation_runs": len(variants) * profile.consistency_runs,
        "simulator_calls": generated_turns,
        "agent_turns": agent_turns,
        "agent_llm_calls_max": agent_turns,
        "evaluator_calls_max": evaluator_calls,
        "estimated_max_total": generated_turns + agent_turns + evaluator_calls,
    }


def _git_version() -> dict[str, Any]:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=PROJECT_ROOT,
                text=True,
            ).strip()
        )
        return {"git_sha": sha, "dirty_worktree": dirty}
    except Exception:
        return {"git_sha": "unknown", "dirty_worktree": None}


def model_config_snapshot(config: EvalConfig, simulator_name: str, evaluator_name: str) -> dict:
    from config import EMBEDDING_MODEL, MODEL_NAME
    from qdrant_store import get_active_collection_name

    return {
        **_git_version(),
        "pipeline_version": "0.1.0",
        "agent_model": MODEL_NAME,
        "embedding_model": EMBEDDING_MODEL,
        "qdrant_collection": get_active_collection_name(),
        "simulator_model": simulator_name,
        "evaluator_model": evaluator_name,
        "agent_adapter": config.agent.adapter,
    }


def replay_conversation(
    generated: GeneratedConversation,
    *,
    adapter,
    language: str,
    repeat_index: int,
) -> GeneratedConversation:
    session_id = str(uuid.uuid4())
    adapter.start_session(session_id)
    history: list[dict[str, str]] = []
    answers: list[str] = []
    traces = []
    for message in generated.user_messages:
        trace = adapter.run_turn(
            session_id=session_id,
            message=message,
            history=history,
            language=language,
        )
        answers.append(trace.final_answer)
        traces.append(trace)
        history.extend(
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": trace.final_answer},
            ]
        )
    adapter.end_session(session_id)
    return GeneratedConversation(
        execution_id=generated.execution_id,
        scenario=generated.scenario,
        variant_index=generated.variant_index,
        session_id=session_id,
        user_messages=list(generated.user_messages),
        assistant_messages=answers,
        traces=traces,
    )


def mark_inconsistent_outputs(results) -> None:
    groups = defaultdict(list)
    for result in results:
        groups[(result.scenario_id, result.variant_index)].append(result)

    for group in groups.values():
        valid = [result for result in group if result.simulation_valid]
        if len(valid) < 2:
            continue
        signatures = {
            (
                result.passed,
                str(result.primary_failure),
                tuple(
                    (
                        turn.actual.topic,
                        turn.actual.intent,
                        turn.actual.reference_status,
                        tuple(turn.actual.referenced_turn_ids),
                        is_refusal(turn.actual.final_answer),
                    )
                    for turn in result.turns
                ),
            )
            for result in valid
        }
        if len(signatures) <= 1:
            continue
        for result in valid:
            result.turns[-1].failures.append(
                failure(
                    FailureCategory.INCONSISTENT_OUTPUT,
                    "identical user messages produced inconsistent pass/fail or intermediate-state outcomes",
                    distinct_signatures=len(signatures),
                )
            )
            finalize_result(result)


def prepare_run(
    *,
    config_path: str | Path,
    scenarios_path: str | Path,
    profile_name: str,
    repeat: int | None = None,
    max_conversations: int | None = None,
    evaluator: str | None = None,
    adapter: str | None = None,
):
    config = load_config(config_path)
    key = profile_name.upper()
    if key not in config.profiles:
        raise ValueError(f"Unknown profile {profile_name!r}; choose {sorted(config.profiles)}")
    profile = config.profiles[key].model_copy(deep=True)
    updates = {}
    if repeat is not None:
        updates["consistency_runs"] = repeat
    if max_conversations is not None:
        updates["max_conversations"] = max_conversations
    if evaluator is not None:
        updates["evaluator"] = evaluator
    if updates:
        profile = profile.model_copy(update=updates)
    if adapter is not None:
        config.agent = config.agent.model_copy(update={"adapter": adapter})

    scenarios = select_scenarios(load_scenarios(scenarios_path), profile)
    variants = build_variants(scenarios, profile)
    return config, key, profile, variants


def run_evaluation(
    *,
    config_path: str | Path,
    scenarios_path: str | Path,
    profile_name: str,
    simulator_provider: str = "deepeval",
    repeat: int | None = None,
    max_conversations: int | None = None,
    evaluator: str | None = None,
    adapter_name: str | None = None,
) -> tuple[dict[str, Any], Path]:
    config, profile_key, profile, variants = prepare_run(
        config_path=config_path,
        scenarios_path=scenarios_path,
        profile_name=profile_name,
        repeat=repeat,
        max_conversations=max_conversations,
        evaluator=evaluator,
        adapter=adapter_name,
    )
    estimates = estimate_calls(variants, profile)
    adapter = build_agent_adapter(config.agent)

    simulator_model = None
    if simulator_provider == "deepeval":
        simulator_model = build_model(config.simulator_model, role="simulator")
        simulator = DeepEvalScenarioSimulator(
            adapter=adapter,
            model=simulator_model,
            profile=profile,
            language=config.agent.language,
        )
    elif simulator_provider == "template":
        simulator = TemplateScenarioSimulator(
            adapter=adapter,
            language=config.agent.language,
        )
    else:
        raise ValueError("simulator_provider must be 'deepeval' or 'template'")

    evaluator_model = (
        build_model(config.evaluator_model, role="evaluator")
        if profile.evaluator == "hybrid"
        else None
    )
    semantic_evaluator = (
        HybridSemanticEvaluator(evaluator_model) if evaluator_model else None
    )

    generated_conversations = simulator.simulate(variants)
    results = []
    for generated in generated_conversations:
        for repeat_index in range(profile.consistency_runs):
            observed = (
                generated
                if repeat_index == 0
                else replay_conversation(
                    generated,
                    adapter=adapter,
                    language=config.agent.language,
                    repeat_index=repeat_index,
                )
            )
            result = evaluate_generated_conversation(
                observed,
                repeat_index=repeat_index,
            )
            if semantic_evaluator:
                semantic_evaluator.evaluate(result)
            results.append(result)

    mark_inconsistent_outputs(results)
    simulator_name = (
        simulator_model.get_model_name()
        if simulator_model is not None
        else "template:no-llm"
    )
    evaluator_name = (
        evaluator_model.get_model_name()
        if evaluator_model is not None
        else "deterministic-only"
    )
    snapshot = model_config_snapshot(config, simulator_name, evaluator_name)
    model_calls = {
        **estimates,
        "simulator_actual": simulator_model.call_count if simulator_model else 0,
        "evaluator_actual": evaluator_model.call_count if evaluator_model else 0,
        "agent_generation_path_turns": sum(
            turn.actual.api_path == "langgraph"
            for result in results
            for turn in result.turns
        ),
    }
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + f"_{profile_key.lower()}"
    )
    return write_report(
        results,
        project_root=PROJECT_ROOT,
        run_id=run_id,
        profile_name=profile_key,
        output_directory=config.output.directory,
        failures_directory=config.output.failures_directory,
        model_config=snapshot,
        model_calls=model_calls,
    )
