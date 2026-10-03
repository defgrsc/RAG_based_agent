from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from deepeval.dataset import ConversationalGolden, Persona
from deepeval.simulator import (
    ConversationSimulator,
    SimulationTemplate,
    default_simulation_node,
)
from deepeval.simulator.controller import end, proceed
from deepeval.test_case import Turn

from evals.bug_discovery.agent_adapter import AgentAdapter
from evals.bug_discovery.models import CountingDeepEvalModel
from evals.bug_discovery.schemas import AgentTrace, Profile, ScenarioDefinition


@dataclass
class ScenarioVariant:
    scenario: ScenarioDefinition
    variant_index: int

    @property
    def execution_id(self) -> str:
        return f"{self.scenario.scenario_id}__v{self.variant_index}"


@dataclass
class GeneratedConversation:
    execution_id: str
    scenario: ScenarioDefinition
    variant_index: int
    session_id: str
    user_messages: list[str]
    assistant_messages: list[str]
    traces: list[AgentTrace]


class ScenarioSimulationTemplate(SimulationTemplate):
    """Use an LLM for wording while a scenario blueprint controls the trajectory."""

    @staticmethod
    def _prompt(
        golden: ConversationalGolden,
        turns: list[Turn],
        language: str,
    ) -> str:
        metadata = golden.additional_metadata or {}
        blueprints = metadata.get("turn_blueprints", [])
        turn_index = sum(turn.role == "user" for turn in turns)
        if turn_index >= len(blueprints):
            turn_index = max(0, len(blueprints) - 1)
        blueprint = blueprints[turn_index] if blueprints else {}
        previous = [
            {"role": turn.role, "content": turn.content}
            for turn in turns[-6:]
        ]
        return f"""
You are simulating a real NTHU student to test a campus information chatbot.
Generate ONLY user turn {turn_index + 1} in {language}. Follow the current
turn blueprint exactly, but invent a natural wording rather than copying an
example. Do not answer the campus question yourself. Do not reveal that this
is a test. The assistant's previous reply may affect tone, but must not change
the required topic, intent, reference target, or qualifier.

Persona:
{golden.persona.characteristics if golden.persona else "A concise student"}

Overall scenario:
{golden.scenario}

Current turn blueprint:
{json.dumps(blueprint, ensure_ascii=False, indent=2)}

Previous conversation:
{json.dumps(previous, ensure_ascii=False, indent=2)}

Return one JSON object with exactly one string field:
{{"simulated_input": "..."}}
""".strip()

    @staticmethod
    def simulate_first_user_turn(golden: ConversationalGolden, language: str) -> str:
        return ScenarioSimulationTemplate._prompt(golden, [], language)

    @staticmethod
    def simulate_user_turn(
        golden: ConversationalGolden,
        turns: list[Turn],
        language: str,
    ) -> str:
        return ScenarioSimulationTemplate._prompt(golden, turns, language)


def stop_after_blueprint(
    *,
    golden: ConversationalGolden,
    simulated_user_turns: int,
):
    target = len((golden.additional_metadata or {}).get("turn_blueprints", []))
    if simulated_user_turns >= target:
        return end("scenario blueprint complete")
    return proceed()


class DeepEvalScenarioSimulator:
    def __init__(
        self,
        *,
        adapter: AgentAdapter,
        model: CountingDeepEvalModel,
        profile: Profile,
        language: str,
    ):
        self.adapter = adapter
        self.model = model
        self.profile = profile
        self.language = language
        self._started_sessions: set[str] = set()

    def _callback(self, input: str, turns: list[Turn], thread_id: str) -> Turn:
        if thread_id not in self._started_sessions:
            self.adapter.start_session(thread_id)
            self._started_sessions.add(thread_id)

        # DeepEval already appended the current user turn; /chat expects only prior turns.
        history = [
            {"role": turn.role, "content": turn.content}
            for turn in turns[:-1]
            if turn.role in {"user", "assistant"}
        ]
        trace = self.adapter.run_turn(
            session_id=thread_id,
            message=input,
            history=history,
            language=self.language,
        )
        retrieval_context = [
            document.content or document.title or document.url
            for document in trace.retrieval_documents
            if document.content or document.title or document.url
        ]
        return Turn(
            role="assistant",
            content=trace.final_answer or f"[AGENT_ERROR] {trace.error}",
            retrieval_context=retrieval_context or None,
            metadata={
                "session_id": thread_id,
                "agent_trace": trace.model_dump(mode="json"),
            },
        )

    def simulate(
        self,
        variants: list[ScenarioVariant],
    ) -> list[GeneratedConversation]:
        goldens: list[ConversationalGolden] = []
        by_execution_id = {variant.execution_id: variant for variant in variants}
        for variant in variants:
            scenario = variant.scenario
            persona = scenario.personas[variant.variant_index % len(scenario.personas)]
            blueprints = [
                turn.generation.model_dump(mode="json")
                for turn in scenario.turns[: self.profile.max_turns]
            ]
            goldens.append(
                ConversationalGolden(
                    name=variant.execution_id,
                    scenario=f"{scenario.description}\nRequired trajectory: "
                    + " → ".join(item["goal"] for item in blueprints),
                    expected_outcome=scenario.expected_outcome,
                    persona=Persona(characteristics=persona),
                    additional_metadata={
                        "scenario_id": scenario.scenario_id,
                        "variant_index": variant.variant_index,
                        "turn_blueprints": blueprints,
                    },
                )
            )

        simulator = ConversationSimulator(
            model_callback=self._callback,
            simulator_model=self.model,
            simulation_graph=default_simulation_node(
                template=ScenarioSimulationTemplate
            ),
            stopping_controller=stop_after_blueprint,
            async_mode=False,
            max_concurrent=1,
            language="Traditional Chinese" if self.language == "zh-Hant" else "English",
        )
        test_cases = simulator.simulate(
            conversational_goldens=goldens,
            max_user_simulations=self.profile.max_turns,
        )

        generated: list[GeneratedConversation] = []
        for test_case in test_cases:
            variant = by_execution_id[str(test_case.name)]
            user_messages: list[str] = []
            assistant_messages: list[str] = []
            traces: list[AgentTrace] = []
            session_id = ""
            for turn in test_case.turns:
                if turn.role == "user":
                    user_messages.append(turn.content)
                    continue
                assistant_messages.append(turn.content)
                metadata = turn.metadata or {}
                session_id = str(metadata.get("session_id") or session_id)
                raw_trace = metadata.get("agent_trace")
                if raw_trace:
                    traces.append(AgentTrace.model_validate(raw_trace))

            if session_id:
                self.adapter.end_session(session_id)
                self._started_sessions.discard(session_id)
            generated.append(
                GeneratedConversation(
                    execution_id=variant.execution_id,
                    scenario=variant.scenario,
                    variant_index=variant.variant_index,
                    session_id=session_id or str(uuid.uuid4()),
                    user_messages=user_messages,
                    assistant_messages=assistant_messages,
                    traces=traces,
                )
            )
        return generated


class TemplateScenarioSimulator:
    """No-LLM fallback for offline pipeline checks; DeepEval remains the default."""

    def __init__(self, *, adapter: AgentAdapter, language: str):
        self.adapter = adapter
        self.language = language

    def simulate(self, variants: list[ScenarioVariant]) -> list[GeneratedConversation]:
        generated: list[GeneratedConversation] = []
        for variant in variants:
            session_id = str(uuid.uuid4())
            self.adapter.start_session(session_id)
            history: list[dict[str, str]] = []
            user_messages: list[str] = []
            assistant_messages: list[str] = []
            traces: list[AgentTrace] = []
            for index, scenario_turn in enumerate(variant.scenario.turns):
                examples = scenario_turn.generation.examples
                message = (
                    examples[(variant.variant_index + index) % len(examples)]
                    if examples
                    else scenario_turn.generation.goal
                )
                trace = self.adapter.run_turn(
                    session_id=session_id,
                    message=message,
                    history=history,
                    language=self.language,
                )
                user_messages.append(message)
                assistant_messages.append(trace.final_answer)
                traces.append(trace)
                history.extend(
                    [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": trace.final_answer},
                    ]
                )
            self.adapter.end_session(session_id)
            generated.append(
                GeneratedConversation(
                    execution_id=variant.execution_id,
                    scenario=variant.scenario,
                    variant_index=variant.variant_index,
                    session_id=session_id,
                    user_messages=user_messages,
                    assistant_messages=assistant_messages,
                    traces=traces,
                )
            )
        return generated
