from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class FailureCategory(StrEnum):
    CONTEXT_CONTAMINATION = "CONTEXT_CONTAMINATION"
    REFERENCE_RESOLUTION_ERROR = "REFERENCE_RESOLUTION_ERROR"
    TOPIC_CLASSIFICATION_ERROR = "TOPIC_CLASSIFICATION_ERROR"
    INTENT_CLASSIFICATION_ERROR = "INTENT_CLASSIFICATION_ERROR"
    QUERY_REWRITE_ERROR = "QUERY_REWRITE_ERROR"
    WRONG_DOMAIN_RETRIEVAL = "WRONG_DOMAIN_RETRIEVAL"
    UNNECESSARY_REFUSAL = "UNNECESSARY_REFUSAL"
    ANSWER_GENERATION_ERROR = "ANSWER_GENERATION_ERROR"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    INCONSISTENT_OUTPUT = "INCONSISTENT_OUTPUT"
    UNKNOWN = "UNKNOWN"


class GenerationConstraints(BaseModel):
    goal: str
    examples: list[str] = Field(default_factory=list)
    must_include_any: list[str] = Field(default_factory=list)
    must_include_all: list[str] = Field(default_factory=list)
    must_include_groups: list[list[str]] = Field(default_factory=list)
    must_not_include: list[str] = Field(default_factory=list)
    style_notes: list[str] = Field(default_factory=list)


class ExpectedTurn(BaseModel):
    topic: str | None = None
    intent: str | None = None
    relation: str | None = None
    reference_status: str | None = None
    referenced_turn_ids: list[int] | None = None
    relevant_history_excludes: list[int] = Field(default_factory=list)
    qualifiers: list[str] = Field(default_factory=list)
    standalone_contains_all: list[str] = Field(default_factory=list)
    standalone_contains_any: list[str] = Field(default_factory=list)
    standalone_forbids: list[str] = Field(default_factory=list)
    allowed_retrieval_topics: list[str] = Field(default_factory=list)
    must_answer: bool = True
    must_clarify: bool = False


class ScenarioTurn(BaseModel):
    generation: GenerationConstraints
    expected: ExpectedTurn


class ScenarioDefinition(BaseModel):
    scenario_id: str = Field(pattern=r"^[a-z0-9_]+$")
    category: str
    description: str
    expected_outcome: str
    personas: list[str] = Field(min_length=1)
    semantic_criteria: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    turns: list[ScenarioTurn] = Field(min_length=1)


class ScenarioFile(BaseModel):
    version: int = 1
    scenarios: list[ScenarioDefinition]

    @model_validator(mode="after")
    def unique_ids(self) -> "ScenarioFile":
        ids = [scenario.scenario_id for scenario in self.scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError("scenario_id values must be unique")
        return self


class Profile(BaseModel):
    categories: list[str]
    variants_per_scenario: int = Field(ge=1)
    max_conversations: int = Field(ge=1)
    max_turns: int = Field(ge=1)
    consistency_runs: int = Field(ge=1)
    max_concurrent: int = Field(ge=1)
    evaluator: Literal["deterministic", "hybrid"] = "hybrid"


class ModelSettings(BaseModel):
    provider: Literal["openai_compatible", "ollama"]
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(ge=32)
    timeout_seconds: float = Field(gt=0)


class AgentSettings(BaseModel):
    adapter: Literal["inprocess", "http"]
    base_url: str
    timeout_seconds: float = Field(gt=0)
    language: Literal["zh-Hant", "en"]
    clear_cache_between_conversations: bool = True


class OutputSettings(BaseModel):
    directory: str
    failures_directory: str
    regressions_file: str


class EvalConfig(BaseModel):
    version: int = 1
    local_first: dict[str, bool]
    agent: AgentSettings
    simulator_model: ModelSettings
    evaluator_model: ModelSettings
    profiles: dict[str, Profile]
    output: OutputSettings


class RetrievedDocument(BaseModel):
    point_id: str | None = None
    title: str = ""
    url: str = ""
    content: str = ""
    score: float | None = None
    inferred_topic: str = "unknown"


class AgentTrace(BaseModel):
    session_id: str
    turn_id: int
    reference_status: str
    referenced_turn_ids: list[int]
    topic: str
    intent: str
    intent_source: str = "eval_observer"
    qualifiers: list[str]
    relation: str
    standalone_query: str
    retrieval_query: str
    relevant_history_turn_ids: list[int]
    retrieval_documents: list[RetrievedDocument]
    final_answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    api_path: str = "unknown"
    latency_seconds: float = 0.0
    error: str | None = None
    error_code: str | None = None
    error_service: str | None = None
    error_category: str | None = None


class AssertionFailure(BaseModel):
    category: FailureCategory
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class EvaluatedTurn(BaseModel):
    turn_id: int
    user_message: str
    assistant_message: str
    expected: ExpectedTurn
    actual: AgentTrace
    simulation_valid: bool = True
    simulation_issues: list[str] = Field(default_factory=list)
    failures: list[AssertionFailure] = Field(default_factory=list)


class ConversationResult(BaseModel):
    execution_id: str
    scenario_id: str
    category: str
    variant_index: int
    repeat_index: int = 0
    session_id: str
    expected_outcome: str
    semantic_criteria: list[str] = Field(default_factory=list)
    turns: list[EvaluatedTurn]
    simulation_valid: bool = True
    passed: bool = True
    primary_failure: FailureCategory | None = None
    secondary_failures: list[FailureCategory] = Field(default_factory=list)
    semantic_score: float | None = None
    semantic_reason: str | None = None

    def conversation(self) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for turn in self.turns:
            messages.append({"role": "user", "content": turn.user_message})
            messages.append({"role": "assistant", "content": turn.assistant_message})
        return messages
