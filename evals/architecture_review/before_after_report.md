# Before / After Regression Report

Date: 2026-08-29

## Change under test

Exactly one production behavior changed: `agent/intents.py` now ranks bilingual current-turn intent evidence by position and specificity instead of returning the first matching intent group. The public state schema and intent taxonomy are unchanged.

No changes were made to topic classification, reference resolution, history selection, RAG, ingestion, prompt, fast answers, generation, or scope policy.

## Test population

- 275 conversations
- 337 turns
- 110 independently authored Chinese single-turn cases
- 110 independently authored English single-turn cases
- 35 adversarial multi-turn conversations
- 20 bilingual multi-turn conversations
- real in-process production handler; no graph, retrieval, embedding, or LLM mocks

## Outcome

| Metric | Baseline | Final | Delta |
|---|---:|---:|---:|
| conversations passed | 83/275 | 130/275 | +47 |
| turns passed | 128/337 | 183/337 | +55 net |
| conversation pass rate | 30.18% | 47.27% | +17.09 pp |
| turn pass rate | 37.98% | 54.30% | +16.32 pp |
| Chinese single-turn | 49.09% | 65.45% | +16.36 pp |
| English single-turn | 14.55% | 30.91% | +16.36 pp |
| multi-turn success | 49.57% | 65.81% | +16.24 pp |
| topic-switch accuracy | 87.50% | 87.50% | 0.00 pp |
| intent-switch accuracy | 37.50% | 62.50% | +25.00 pp |
| backward-reference accuracy | 80.00% | 100.00% | +20.00 pp |
| retrieval isolation | 97.69% | 98.15% | +0.46 pp |
| bilingual consistency | 20.00% | 40.00% | +20.00 pp |

## Failure delta

| Failure label | Baseline | Final | Delta |
|---|---:|---:|---:|
| `INTENT_ERROR` | 154 | 49 | -105 |
| `TOPIC_ERROR` | 75 | 75 | 0 |
| `REFERENCE_ERROR` | 28 | 25 | -3 |
| `HISTORY_SELECTION_ERROR` | 3 | 1 | -2 |
| `RETRIEVAL_ERROR` | 5 | 4 | -1 |
| `GENERATION_ERROR` | 99 | 102 | +3 |
| `REFUSAL_ERROR` | 16 | 16 | 0 |
| `ENTITY_ERROR` | 3 | 3 | 0 |
| `STATE_CONTAMINATION` | 1 | 1 | 0 |

Final intent mismatch residuals are led by lookup → unknown (14), troubleshooting → unknown (8), configuration → unknown (7), and application → unknown (5). These should not be addressed by adding a second production change in this review.

## Turn-level regression audit

- 56 turns changed from fail to pass.
- 127 remained pass.
- 153 remained fail.
- 1 changed from pass to fail.

The one regression was `zh_single_084` (“DormNet password 忘了”). Topic and intent were unchanged (`campus_wifi`, `unknown`). The baseline route completed LangGraph; the final route hit `embedding_fallback`. It is a dependency/run-path variance, not an observed regression in the changed classifier.

## Test-suite regression

- targeted intent + adjacent graph tests: 39 passed, 22 subtests passed after refinement;
- full repository: 130 passed, 24 subtests passed;
- one existing Starlette/httpx deprecation warning;
- no failing unit/integration tests.

## Latency and stability caveat

Baseline mean latency was 0.5065 s. An intermediate after run reached 1.3651 s with 47 embedding fallbacks and 37 completed LangGraph calls. The final run measured 0.2645 s with 77 embedding fallbacks and only 7 completed LangGraph calls. These differences are dominated by the 30-second embedding circuit breaker and slow-path route mix, so the classifier change must not be credited with a latency improvement.

Keep correctness and burst-stability runs separate:

- correctness: start each evaluation process with a closed breaker and report all fallback routes;
- stability: intentionally preserve breaker state under a defined request rate and grade degraded-answer quality.

## Decision

The intent change should be kept. It removed 68.2% of intent failures, improved both languages by the same 16.36 percentage points in single-turn accuracy, improved multi-turn intent switches, and produced no observed state regression. Remaining topic, generation, and metadata-isolation defects require separate changes with separate baselines.
