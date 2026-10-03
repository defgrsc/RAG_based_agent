from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def promote_failure(
    *,
    failure_id: str,
    failures_file: Path,
    regressions_file: Path,
    confirmed_by: str,
) -> dict:
    if not confirmed_by.strip():
        raise ValueError("confirmed_by is required; failures must be reviewed before promotion")

    failures = _read_jsonl(failures_file)
    selected = next(
        (item for item in failures if item.get("failure_id") == failure_id),
        None,
    )
    if selected is None:
        raise ValueError(f"Failure {failure_id!r} not found in {failures_file}")

    existing = _read_jsonl(regressions_file)
    duplicate = next(
        (item for item in existing if item.get("failure_id") == failure_id),
        None,
    )
    if duplicate:
        return duplicate

    record = {
        "format": "promptfoo-conversation-regression-v1",
        "failure_id": failure_id,
        "description": (
            f"{selected['scenario_id']}: {selected['failure_category']}"
        ),
        "vars": {
            "conversation": selected["conversation"],
            "session_isolation": True,
        },
        "expected": selected["expected"],
        "assert": [
            {
                "type": "python",
                "value": "evals.bug_discovery.promptfoo_assertions:assert_conversation",
            }
        ],
        "confirmed_by": confirmed_by,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "source_failure_dataset": str(failures_file),
    }
    regressions_file.parent.mkdir(parents=True, exist_ok=True)
    with regressions_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record
