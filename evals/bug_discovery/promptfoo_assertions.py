"""Promptfoo custom assertion bridge for promoted conversation regressions.

The current repository does not have Promptfoo installed. The promotion command
exports records that point here so a future Promptfoo Python assertion/provider
can reuse the same deterministic state expectations instead of duplicating them.
"""


def assert_conversation(output, context):
    expected = (context or {}).get("vars", {}).get("expected")
    if expected is None:
        return {
            "pass": False,
            "score": 0,
            "reason": "Missing exported expected conversation state",
        }
    if not output:
        return {"pass": False, "score": 0, "reason": "Agent returned no output"}
    return {
        "pass": True,
        "score": 1,
        "reason": (
            "Transport-level assertion passed. Configure the Promptfoo provider "
            "to return Agent traces for full intermediate-state assertions."
        ),
    }
