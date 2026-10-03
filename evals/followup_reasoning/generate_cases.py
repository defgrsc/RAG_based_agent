from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from evals.followup_reasoning.case_catalog import build_cases


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "generated_cases.json"


def main() -> None:
    cases = build_cases()
    payload = {
        "version": 1,
        "description": "Bilingual follow-up reasoning and troubleshooting progression suite.",
        "composition": {
            "conversations": len(cases),
            "user_turns": sum(len(case["conversation"]) for case in cases),
            "zh_conversations": sum(case["language"] == "zh-Hant" for case in cases),
            "en_conversations": sum(case["language"] == "en" for case in cases),
            "long_chains": sum(case["long_chain"] for case in cases),
            "categories": dict(Counter(case["category"] for case in cases)),
            "services": dict(Counter(case["service"] for case in cases)),
        },
        "cases": cases,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["composition"], ensure_ascii=False, indent=2))
    print(OUTPUT)


if __name__ == "__main__":
    main()
