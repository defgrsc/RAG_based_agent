# Architecture review artifacts

- `architecture_review.md` — current architecture, failure analysis, proposed Skills/Tools/State/graph, roadmap, risks, and implemented-change scope.
- `before_after_report.md` — final metric and regression comparison.
- `generated_cases.json` — 275 conversations / 337 turns.
- `baseline_results.json` — full baseline traces and summary.
- `baseline_failed_cases.json` — reproducible baseline failures.
- `after_final_results.json` — full final traces and summary.
- `after_final_failed_cases.json` — reproducible final failures.
- `dependency_and_metadata_audit.json` — dependency health and Qdrant payload completeness evidence.
- `metadata_backfill_baseline.json` / `metadata_backfill_after.json` — before/after index-schema and staging evidence.
- `metadata_backfill_report.md` — metadata contract, batching, activation, filter-shadow, and regression interpretation.
- `metadata_after_results.json` — full 337-turn run against the metadata-v2 collection.
- `generate_cases.py` / `case_catalog.py` — deterministic evaluation-set source.
- `run_evaluation.py` — real in-process evaluator and report generator.
- `runs/` — immutable per-label copies, including an intermediate after run retained to show circuit-breaker/latency variance.

`evaluation_report.md` is the generated baseline summary. `after_final_evaluation_report.md` covers the intent change, and `metadata_after_evaluation_report.md` covers the metadata-v2 collection. Narrative interpretation is in `architecture_review.md`, `before_after_report.md`, and `metadata_backfill_report.md`.
