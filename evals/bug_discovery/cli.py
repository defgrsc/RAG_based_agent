from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.bug_discovery.loader import DEFAULT_CONFIG, DEFAULT_SCENARIO_DIR, PROJECT_ROOT
from evals.bug_discovery.regression import promote_failure
from evals.bug_discovery.runner import (
    estimate_calls,
    prepare_run,
    run_evaluation,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Automatic multi-turn Agent bug discovery"
    )
    root.add_argument("--config", default=str(DEFAULT_CONFIG))
    root.add_argument("--scenarios", default=str(DEFAULT_SCENARIO_DIR))
    subparsers = root.add_subparsers(dest="command", required=True)

    estimate = subparsers.add_parser("estimate", help="Show call budget without running models")
    estimate.add_argument("--profile", default="SMOKE")
    estimate.add_argument("--repeat", type=int)
    estimate.add_argument("--max-conversations", type=int)
    estimate.add_argument(
        "--evaluator",
        choices=("deterministic", "hybrid"),
    )

    run = subparsers.add_parser("run", help="Generate, execute, evaluate, and persist")
    run.add_argument("--profile", default="SMOKE")
    run.add_argument("--simulator", choices=("deepeval", "template"), default="deepeval")
    run.add_argument("--repeat", type=int)
    run.add_argument("--max-conversations", type=int)
    run.add_argument(
        "--evaluator",
        choices=("deterministic", "hybrid"),
    )
    run.add_argument("--adapter", choices=("inprocess", "http"))

    promote = subparsers.add_parser(
        "promote",
        help="Promote one reviewed failure to the Promptfoo regression interface",
    )
    promote.add_argument("--failure-id", required=True)
    promote.add_argument("--confirmed-by", required=True)
    promote.add_argument(
        "--failures-file",
        default=str(PROJECT_ROOT / "evals" / "failures" / "latest.jsonl"),
    )
    promote.add_argument(
        "--regressions-file",
        default=str(
            PROJECT_ROOT / "evals" / "regressions" / "promptfoo_cases.jsonl"
        ),
    )
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "estimate":
        _, profile_name, profile, variants = prepare_run(
            config_path=args.config,
            scenarios_path=args.scenarios,
            profile_name=args.profile,
            repeat=args.repeat,
            max_conversations=args.max_conversations,
            evaluator=args.evaluator,
        )
        print(
            json.dumps(
                {
                    "profile": profile_name,
                    **estimate_calls(variants, profile),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "promote":
        record = promote_failure(
            failure_id=args.failure_id,
            failures_file=Path(args.failures_file),
            regressions_file=Path(args.regressions_file),
            confirmed_by=args.confirmed_by,
        )
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return

    summary, run_dir = run_evaluation(
        config_path=args.config,
        scenarios_path=args.scenarios,
        profile_name=args.profile,
        simulator_provider=args.simulator,
        repeat=args.repeat,
        max_conversations=args.max_conversations,
        evaluator=args.evaluator,
        adapter_name=args.adapter,
    )
    print(
        json.dumps(
            {
                "run_directory": str(run_dir),
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
