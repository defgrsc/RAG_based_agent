from __future__ import annotations

from pathlib import Path

import yaml

from evals.bug_discovery.schemas import EvalConfig, Profile, ScenarioDefinition, ScenarioFile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "evals" / "config.yaml"
DEFAULT_SCENARIO_DIR = PROJECT_ROOT / "evals" / "scenarios"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def load_config(path: str | Path = DEFAULT_CONFIG) -> EvalConfig:
    return EvalConfig.model_validate(_load_yaml(Path(path)))


def load_scenarios(path: str | Path = DEFAULT_SCENARIO_DIR) -> list[ScenarioDefinition]:
    target = Path(path)
    paths = sorted(target.glob("*.yaml")) if target.is_dir() else [target]
    scenarios: list[ScenarioDefinition] = []
    for scenario_path in paths:
        scenario_file = ScenarioFile.model_validate(_load_yaml(scenario_path))
        scenarios.extend(scenario_file.scenarios)

    ids = [scenario.scenario_id for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("scenario_id values must be unique across scenario files")
    return scenarios


def select_scenarios(
    scenarios: list[ScenarioDefinition],
    profile: Profile,
) -> list[ScenarioDefinition]:
    categories = set(profile.categories)
    selected = [
        scenario
        for scenario in scenarios
        if "*" in categories or scenario.category in categories
    ]
    if not selected:
        raise ValueError(f"No scenarios match categories: {sorted(categories)}")
    return selected
