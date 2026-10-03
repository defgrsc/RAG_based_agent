# NTHU Network AI Agent — Architecture, Skills, Tools, State, RAG, and Evaluation Review

Review date: 2026-08-29 (Asia/Taipei)

## 1. Executive conclusion

The repository already has a useful LangGraph context pipeline, deterministic fast answers, a local-first evaluation framework, dependency health probes, caches, and service-specific coverage data. The main architectural problem is not a missing prompt rule. It is split ownership:

- `main.py` owns many routing decisions before the compiled graph.
- the graph owns context, intent, history selection, retrieval, and generation only on the slow path;
- `fast_answers.py`, `guard.py`, `prompt.py`, `rag.py`, and legacy functions in `main.py` repeat topic/intent/policy knowledge;
- the state taxonomy loses important user-task distinctions;
- retrieval cannot reliably enforce service boundaries because most indexed payloads are untagged.

The executed baseline confirmed the first measurable bottleneck was bilingual intent classification: 154 intent failures, 133 of which collapsed a known expected intent to `unknown`. The first independently measured production change was therefore ordered bilingual intent evidence in `agent/intents.py`. No prompt, topic resolver, RAG, ingestion, fast-answer, or graph-routing production code was changed in that step.

Result after that first change on the same 275 conversations / 337 turns:

- turn pass rate: 37.98% → 54.30%;
- conversation pass rate: 30.18% → 47.27%;
- intent errors: 154 → 49 (-68.2%);
- 56 failed turns became passing; one previously passing turn failed because the final run hit the embedding fallback while its topic and intent were unchanged;
- full repository regression at that checkpoint: 130 passed, 24 subtests passed.

A separately scoped follow-up has now completed the ingestion side of Phase 1: schema-v2 metadata is present on all 217 active Qdrant points, the collection was rebuilt through staging, and eight service/task filter shadow cases had zero mismatches. Embedding ingestion was also batched at eight documents after the original all-at-once request timed out.

The current full regression is 139 passed plus 24 subtests. The metadata-v2 full evaluation measured 46.91% conversation pass and 54.01% turn pass, one case below the intent-final run; the changed case was a generation prompt-leak safety fallback with no retrieval filter, while direct retrieval returned five correct documents. Production hard filter enforcement remains the next independently measured change.

## 2. Review scope and method

This review used:

1. Static inspection of the entry point, LangGraph nodes, state types, semantic classifiers, guard, prompt, fast answers, RAG, Qdrant storage, ingestion, dependency health, and existing eval framework.
2. Read-only dependency probes against the configured local embedding, Qdrant, and LLM services.
3. Read-only Qdrant payload audit across all 217 active points.
4. A new deterministic evaluation catalog with separately authored Chinese and English prompts.
5. Real in-process calls to the production `chat()` handler; LangGraph, Qdrant, embedding, fast paths, and LLM were not mocked.
6. Per-turn assertions over state, reference resolution, selected history, retrieval domain, answer language, refusal behavior, contamination, and internal wording.
7. Baseline → one change → targeted tests → full tests → identical final evaluation.

The runner reuses the repository's existing DeepEval evaluation infrastructure for the real in-process adapter and trace schema. The cases in this review are explicitly authored rather than simulator-generated, so the required Chinese/English composition is deterministic and auditable. Promptfoo remains an export/assertion interface in the existing repository; no Promptfoo runner is configured here, so this review does not claim a Promptfoo execution.

The answer-content grader is deterministic and intentionally conservative. It checks service markers, refusals, clarifications, language, contamination, and leakage; it is not a general semantic LLM judge. State, route, document, error, and latency evidence is captured so false positives can be audited.

## 3. Current production architecture

### 3.1 Actual request flow

The public path in `main.py` does not simply call one graph:

```text
POST /chat
  → prepare_agent_context
      → resolve_context
      → classify_intent
      → select_history
  → unresolved-reference response
  → ordinal legacy fast path
  → clarification / location clarification
  → scope guard
  → structured/deterministic fast answers
  → answer cache
  → compiled LangGraph slow path
      → resolve_context (idempotent)
      → classify_intent
      → select_history
      → retrieve
      → generate
  → dependency/error fallback and response cleanup
```

This means the graph is a partial workflow, not the sole orchestrator. In the final evaluation, routes were distributed across fast answer, embedding fallback, scope guard, reference clarification, clarification, unknown legacy routes, and only a small number of completed LangGraph paths.

### 3.2 Current graph and state

`agent/graph.py` provides a coherent five-node chain:

```text
resolve_context → classify_intent → select_history → retrieve → generate
```

`AgentState` carries current message, annotated history, topic, intent, relation, reference status/kind, referenced turns, semantic slots, selected history, retrieval query/filter/documents, answer, language, confidence, and metadata.

Strengths:

- reference state is explicit rather than hidden in prompt prose;
- turn IDs refer to user turns, making history assertions possible;
- history selection can exclude old intents on an intent switch;
- retrieval exposes a metadata-filter interface;
- graph nodes are independently testable and observable;
- raw history is converted to a bounded legacy format before prompt/rewrite calls.

Limitations:

- raw history is re-annotated on every request; there is no authoritative persisted turn frame;
- topic and intent are separate passes with duplicated re-annotation logic;
- the public intent taxonomy is lossy: coverage and status collapse to `lookup`; credentials often collapse to `unknown`;
- entities are a free-form `dict[str, str]`, so ownership, provenance, confidence, and lifecycle are unclear;
- `relation`, `reference_status`, and selected-history semantics can be changed by later nodes, which makes node contracts harder to reason about;
- caches and fast paths live outside the graph and can observe a different subset of state.

### 3.3 Prompt and deterministic routing

`prompt.py` is 240 lines and includes policy, service isolation, output rules, bilingual behavior, and retrieved examples. `fast_answers.py` is 3,245 lines and acts as a second knowledge/routing system. `main.py` is 1,789 lines and contains additional reference, rewrite, scope, fast-path, cache, and fallback decisions.

Consequences:

- adding a service or task can require coordinated edits in multiple files;
- behavior depends on which route wins rather than one explicit policy;
- prompt instructions cannot repair state or retrieval decisions made before generation;
- exact/substring fast answers hide slow-path defects during narrow tests;
- route-specific answers can diverge by language.

Prompt leakage is partially checked after generation, but fallback wording itself can expose implementation-shaped phrases such as “available NTHU network information.” Safety should be a response-verification contract, not only prompt text plus a post-hoc substring list.

### 3.4 Retrieval and ingestion

The graph passes `topic` and optional `metadata_filter` into `retrieve_context`. Qdrant serialization supports metadata filters. However:

- `retrieve_context` includes `topic` in the cache key but does not turn it into a filter;
- only the campus Wi-Fi coverage path automatically creates `{service: campus_wifi, intent: coverage}`;
- `chunk_pages()` emits only title, URL, chunk index, and content for normal crawled pages;
- priority chunks are appended after vector search and are not constrained by the Qdrant filter;
- page expansion can bring neighboring chunks without re-validating the active service/task boundary.

Actual Qdrant audit:

| Payload field | Tagged | Missing |
|---|---:|---:|
| `service` | 74 | 143 |
| `intent` | 74 | 143 |
| `language` | 0 | 217 |
| `source_type` | 74 | 143 |

All 74 tagged points are `service=campus_wifi`, `intent=coverage`, `source_type=official_coverage`. The remaining 143 crawled chunks cannot participate in enforceable service filtering. Therefore a correct classifier does not imply correct retrieval.

Follow-up status: the active metadata-v2 collection now has 217/217 points with `service`, `services`, `task`, `tasks`, `intent`, `language`, `source_type`, `document_type`, and schema version. This repairs index capability, but known-service filters are not yet automatically derived and enforced across vector search, priority chunks, and page expansion.

## 4. Failure modes and root causes

### 4.1 Baseline result

Dataset composition:

| Segment | Conversations | Notes |
|---|---:|---|
| Chinese single turn | 110 | colloquial, typos, shorthand, ambiguous and out-of-scope cases |
| English single turn | 110 | independently authored, not row-by-row translations |
| Adversarial multi-turn | 35 | topic/intent switches, location ellipsis, backward/unresolved references, discourse overrides |
| Bilingual multi-turn | 20 | answer language follows the current turn |
| Total | 275 | 337 turns |

Baseline required metrics:

| Metric | Result |
|---|---:|
| conversation pass rate | 30.18% |
| turn pass rate | 37.98% |
| single-turn accuracy | 31.82% |
| Chinese single-turn accuracy | 49.09% |
| English single-turn accuracy | 14.55% |
| multi-turn success rate | 49.57% |
| topic-switch accuracy | 87.50% |
| intent-switch accuracy | 37.50% |
| backward-reference accuracy | 80.00% |
| retrieval-isolation correctness | 97.69% over 216 observed retrieval/source turns |
| bilingual consistency | 20.00% |

Baseline failure counts (all labels, not only primary):

| Failure | Count | Root cause summary |
|---|---:|---|
| `INTENT_ERROR` | 154 | sparse bilingual markers, fixed precedence, inherited `unknown` |
| `GENERATION_ERROR` | 99 | dependency fallbacks, wrong-domain answers, missing service evidence |
| `TOPIC_ERROR` | 75 | English/domain paraphrases and generic account terms collapse to `unknown/account` |
| `REFERENCE_ERROR` | 28 | implicit location/intent follow-ups and unresolved/backward-reference edge cases |
| `REFUSAL_ERROR` | 16 | in-scope questions rejected or out-of-scope responses not clearly refused |
| `RETRIEVAL_ERROR` | 5 | cross-service sources despite expected service boundary |
| `ENTITY_ERROR` | 3 | canonical location slot mismatch |
| `HISTORY_SELECTION_ERROR` | 3 | excluded turn selected |
| `STATE_CONTAMINATION` | 1 | excluded earlier content appeared in answer |

No baseline turn raised a recorded tool/dependency exception. However, 72 turns used the embedding fallback. A post-run health probe showed all dependencies ready. The 30-second embedding circuit breaker can amplify one transient failure across a fast batch; this is a stability issue distinct from classifier correctness.

### 4.2 Why the first change was intent classification

Of 154 intent failures, 133 (86.4%) were expected known intents that became `unknown`:

- troubleshooting → unknown: 45;
- lookup → unknown: 41;
- configuration → unknown: 25;
- application → unknown: 22.

The flat first-match rule also created deterministic precedence errors:

- a registration question containing “where”, “campus”, and “wireless” could be consumed by the coverage-list shortcut before `register`;
- “I registered; how do I configure …” could remain application because application markers were checked before configuration;
- generic English `which` incorrectly converted credential questions into lookup.

This was the largest measured state defect, had a narrow ownership boundary, and could be changed without touching prompt, retrieval, ingestion, or answer content.

## 5. Recommended Skill architecture

“Skill” here means a reusable domain capability with an explicit contract. It is not a prompt fragment and not a hidden branch in `main.py`.

| Skill | Responsibility | Inputs | Outputs | Invoke when |
|---|---|---|---|---|
| `ScopePolicySkill` | decide supported NTHU network scope | current turn, candidate service, entities | in/out/clarify + reason code | every turn before tools |
| `SemanticFrameSkill` | extract service, task, language, entities, confidence | normalized current turn only | immutable `TurnFrame` | every user turn |
| `ReferenceResolutionSkill` | resolve implicit, named, ordinal, and backward references | current frame + structured prior frames | relation, referenced IDs, inherited slots | reference cue or incomplete frame |
| `HistorySelectionSkill` | select minimal relevant turns | resolved frame + turn store | selected IDs + exclusion reasons | before rewrite/retrieval/generation |
| `QueryPlanningSkill` | build standalone retrieval plan | resolved frame + selected turns | query, filters, tool choice | answer is not deterministic |
| `CoverageLookupSkill` | exact campus coverage lookup | canonical location/SSID scope | structured coverage facts + citations | coverage/status task |
| `RetrievalPolicySkill` | enforce service/task/language/source boundaries | retrieval plan + index capabilities | approved search contract | before vector search |
| `EvidenceValidationSkill` | reject or down-rank wrong-domain/weak evidence | frame + retrieved documents | accepted/rejected docs + reason | after every retrieval tool |
| `AnswerCompositionSkill` | compose answer from validated evidence | frame, evidence, language/style | draft answer + claim/source map | when evidence is sufficient |
| `ResponseSafetySkill` | verify language, scope, citations, leakage, contamination | frame, draft, selected turns | final/repair/refuse | every response |
| `DependencyFallbackSkill` | produce task-aware degraded responses | frame + typed dependency error | safe response + retry guidance | typed tool failure |

Skills should be pure or side-effect-free where possible. External effects belong in Tools. Each Skill should log its input state version, output, confidence, reason codes, and latency.

## 6. Recommended Tool contracts

Tools should return typed data and typed errors; they should not decide conversation policy.

### `qdrant_search`

Input:

```json
{
  "query": "string",
  "embedding": "vector",
  "filters": {
    "service": "campus_wifi|dorm_network|vpn|email",
    "task": "application|troubleshooting|configuration|coverage|credentials|status|general",
    "language": "zh-Hant|en|any",
    "source_type": ["official_page", "official_coverage"]
  },
  "top_k": 8,
  "index_schema_version": 2
}
```

Output: documents with point ID, URL, chunk ID, service/task/language/source metadata, vector score, rerank score, and filter-match evidence. Untagged chunks must be explicit (`metadata_status=legacy`) rather than silently accepted.

Errors: `embedding_unavailable`, `vector_store_unavailable`, `schema_version_mismatch`, `no_eligible_documents`.

### `coverage_lookup`

Input: canonical location, optional SSID, language. Output: exact/alias/no-match status, records, supported SSIDs, official source URLs. This deterministic tool should run before vector retrieval for coverage tasks.

### `official_page_lookup`

Input: service, task, language, optional URL allowlist. Output: approved page chunks only. Priority pages become an explicit tool result subject to the same policy, instead of being appended behind the filter.

### `dependency_probe`

Input: services and deadline. Output: status, latency, model/collection/schema identity. Probe results are observability data; user answers consume typed errors from the attempted tool, not hidden health assumptions.

## 7. Recommended state redesign

Use versioned, authoritative frames instead of repeatedly inferring meaning from raw text.

```text
ConversationState v2
├── session_id
├── turns[]
│   ├── turn_id
│   ├── raw_user_text
│   ├── language
│   ├── frame
│   │   ├── service
│   │   ├── task
│   │   ├── entities[] {name, value, source, confidence}
│   │   ├── scope_status
│   │   └── classifier_version
│   ├── relation {type, referenced_turn_ids, confidence, reason}
│   └── response_summary
├── active_frame
├── selection {included_ids, excluded_ids, reasons}
├── retrieval_plan {query, filters, tool, schema_version}
├── evidence {accepted_docs, rejected_docs, reasons}
├── response {draft, final, language, claim_source_map}
└── diagnostics {route, skill_timings, tool_timings, typed_errors}
```

Rules:

1. Raw history is immutable evidence, not the state store.
2. Every user turn gets one frame; later nodes enrich rather than reclassify it independently.
3. Inheritance is field-level and records provenance (`current`, `turn:N`, or `default`).
4. Topic/service switch clears incompatible task/entity/history fields by policy.
5. Intent/task switch retains service but excludes previous-task history unless explicitly referenced.
6. Retrieval filters derive only from the resolved frame and index schema capabilities.
7. Answer generation sees validated evidence and selected summaries, not all raw history.

## 8. Recommended target graph

```text
normalize_turn
  → semantic_frame
  → resolve_reference
  → apply_scope_policy
      ├── out_of_scope → compose_refusal → verify_response
      ├── unresolved   → compose_clarification → verify_response
      └── supported
           → select_history
           → plan_action
               ├── deterministic_tool → validate_evidence
               └── retrieval_tool     → validate_evidence
           → compose_answer
           → verify_response
               ├── repair once
               └── final
```

Cache and dependency fallback should be graph nodes/edges with explicit state, not invisible returns around the graph. Fast answers should become deterministic Skills/Tools selected by `plan_action`, not a separate 3,245-line router.

## 9. Implemented changes

### 9.1 Bilingual intent evidence

Changed production file: `agent/intents.py` only.

Behavioral change:

- collect evidence from all current-turn bilingual markers and generic patterns;
- choose the latest, most specific evidence rather than the first intent group;
- keep special comparison/cross-test/onboarding semantics;
- move coverage-list fallback after explicit registration/configuration evidence;
- remove generic English `which` as a lookup signal;
- protect interrogative availability (`能不能上網`) from negative-substring troubleshooting matches;
- retain the existing public intent taxonomy and graph interface.

Added regression file: `tests/test_intent_evidence.py`.

Not changed:

- topic classification;
- reference resolution;
- state schema;
- history selection;
- retrieval filters or metadata;
- ingestion;
- prompt;
- fast answers;
- answer generation;
- scope guard.

### 9.2 Ingestion metadata contract and staged reindex

Changed production files: `document_metadata.py`, `ingest.py`, and `config.py`.

- annotate normal crawled chunks and structured coverage records with metadata schema v2;
- classify service primarily from URL namespace, with content-based multi-service support for generic pages;
- classify tasks from URL and content evidence;
- add language, source type, document type, scalar compatibility fields, and list-valued service/task fields;
- validate all documents before embedding or Qdrant mutation;
- embed in ordered batches of eight and reject vector-count mismatches;
- rebuild a staging collection and activate only after a successful upsert.

Production retrieval policy, graph routing, prompt, fast answers, and generation were not changed. The previous collection remains available for rollback.

## 10. First-change before/after results

| Metric | Baseline | Final | Delta |
|---|---:|---:|---:|
| conversation pass rate | 30.18% | 47.27% | +17.09 pp |
| turn pass rate | 37.98% | 54.30% | +16.32 pp |
| single-turn accuracy | 31.82% | 48.18% | +16.36 pp |
| Chinese single-turn | 49.09% | 65.45% | +16.36 pp |
| English single-turn | 14.55% | 30.91% | +16.36 pp |
| multi-turn success | 49.57% | 65.81% | +16.24 pp |
| topic-switch accuracy | 87.50% | 87.50% | 0.00 pp |
| intent-switch accuracy | 37.50% | 62.50% | +25.00 pp |
| backward-reference accuracy | 80.00% | 100.00% | +20.00 pp |
| retrieval isolation | 97.69% | 98.15% | +0.46 pp |
| bilingual consistency | 20.00% | 40.00% | +20.00 pp |

Failure-label deltas:

| Failure | Baseline | Final | Delta |
|---|---:|---:|---:|
| intent | 154 | 49 | -105 |
| topic | 75 | 75 | 0 |
| reference | 28 | 25 | -3 |
| retrieval | 5 | 4 | -1 |
| history selection | 3 | 1 | -2 |
| entity | 3 | 3 | 0 |
| refusal | 16 | 16 | 0 |
| state contamination | 1 | 1 | 0 |
| generation | 99 | 102 | +3 |

Per-turn comparison: 56 fixed, 127 stayed passing, 153 stayed failing, one regressed. The one regression had unchanged `topic=campus_wifi` and unchanged `intent=unknown`; its route changed from LangGraph to embedding fallback, so it is not an observed intent-state regression.

Latency cannot be attributed cleanly to this classifier change because circuit-breaker state changed the number of completed LangGraph calls. Baseline mean was 0.5065 s; an intermediate after run was 1.3651 s with 47 embedding fallbacks; the final run was 0.2645 s with 77 embedding fallbacks. Report route mix and fallback counts alongside latency in CI.

### 10.1 Metadata follow-up result

| Metric | Intent-final | Metadata v2 | Delta |
|---|---:|---:|---:|
| metadata completeness | mixed, 0–34.10% | 100% on all required fields | acceptance met |
| filtered shadow cases | not enforceable for most chunks | 8/8, zero mismatches | acceptance met |
| conversation pass rate | 47.27% | 46.91% | -0.36 pp |
| turn pass rate | 54.30% | 54.01% | -0.29 pp |
| retrieval isolation | 98.15% | 98.16% | +0.01 pp |

The single turn regression used no metadata filter. Its answer was replaced by `fallback_for_prompt_leak()`; direct production retrieval returned five correct documents. See `metadata_backfill_report.md` and `metadata_backfill_after.json` for the full audit.

## 11. Remaining priorities and phased roadmap

### Phase 0 — contracts and observability

- freeze `TurnFrame`, relation, selection, retrieval-plan, and typed-error schemas;
- log reason codes and classifier/tool versions;
- add state-only shadow evaluation so answer nondeterminism cannot hide routing regressions;
- report fallback and circuit-breaker state as first-class metrics.

### Phase 1 — ingestion metadata and retrieval isolation

Completed:

- classify/backfill every chunk with service, task, language, source/document type, and schema version;
- reindex into a staging collection and atomically activate only after completeness checks;
- validate Qdrant service/task array filters with eight focused shadow cases and zero mismatches;
- retain the previous collection for rollback.

Remaining:

- require service/task filters for known resolved frames;
- subject priority pages and page expansion to the same validation policy;
- represent comparison and multi-service questions explicitly instead of disabling isolation.

Acceptance status: metadata completeness and focused filter correctness are met. Production enforcement and a repeated recall/non-regression gate remain open.

### Phase 2 — one orchestrator

- move scope, clarification, deterministic tools, cache, retrieval, generation, safety, and dependency fallback into explicit graph nodes;
- deprecate duplicate legacy reference/intent routing in `main.py` only after shadow parity;
- preserve old routes behind a versioned rollback flag.

### Phase 3 — deterministic knowledge cleanup

- split `fast_answers.py` into typed deterministic Skills/Tools keyed by service/task;
- move factual content into versioned official-source records;
- make prompt responsible for composition, not routing or factual policy storage.

### Phase 4 — evaluation and CI

- run state-only tests on every change;
- run targeted real-agent scenarios on pull requests;
- run the 337-turn suite on scheduled/local release gates;
- add repeated runs for nondeterministic generation and dependency stability;
- add semantic grading only as a secondary judge with captured rationales.

### Phase 5 — prompt reduction

- reduce prompt to role, evidence use, language/style, citation, and safety;
- remove rules already guaranteed by frame, policy, retrieval, and response-verification Skills.

## 12. Migration and rollback risks

- Metadata enforcement before backfill can produce zero recall. Use staging collections and completeness gates.
- A new state schema can break caches and session continuity. Version cache keys and dual-write old/new state during shadow mode.
- Consolidating routes can change latency and deterministic answers. Compare route parity and keep a per-session rollback flag.
- Stronger topic filters can reject multi-service comparison questions. Represent comparison as an explicit multi-service plan rather than disabling isolation globally.
- Repeated evaluation can trigger the embedding circuit breaker and distort language segments. Reset only for isolated correctness tests; retain a separate burst/stability suite that does not reset it.
- Prompt reduction before tool/state guarantees are in place will reduce behavior. Prompt slimming must be last, not first.

## 13. Reproduction

```bash
./venv/bin/python -m evals.architecture_review.generate_cases
./venv/bin/python -m evals.architecture_review.run_evaluation --label baseline
./venv/bin/pytest -q tests/test_intent_evidence.py tests/test_agent_graph.py
./venv/bin/pytest -q
./venv/bin/python -m evals.architecture_review.run_evaluation --label after_final
./venv/bin/python -c 'from ingest import ingest_nthu_docs; ingest_nthu_docs(replace=True)'
./venv/bin/pytest -q tests/test_document_metadata.py tests/test_wireless_coverage.py tests/test_agent_graph.py
./venv/bin/python -m evals.architecture_review.run_evaluation --label metadata_after
```

Artifacts are in this directory. `baseline_results.json`, `after_final_results.json`, and `metadata_after_results.json` contain complete turn traces; the failed-case files contain the reproducible failure subsets.
