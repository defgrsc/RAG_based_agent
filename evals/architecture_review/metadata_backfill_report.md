# Metadata Backfill and Staging Reindex Report

Date: 2026-08-29 (Asia/Taipei)

## Outcome

The active Qdrant collection now contains 217 metadata-schema-v2 points. Every point has non-empty scalar and list service/task fields, language, source/document type, legacy intent compatibility, and schema version. The new collection is green and the prior active collection is retained for rollback.

This change makes service/task isolation enforceable at the index layer. It does not yet force those filters in production retrieval.

## Change scope

- Added `document_metadata.py` as the ingestion metadata contract.
- Annotated and validated documents before embedding or Qdrant mutation.
- Added URL-first service classification, content-assisted task classification, language/source/document type, multi-value `services` and `tasks`, and schema version 2.
- Preserved and completed existing structured wireless coverage metadata.
- Added embedding batches with cardinality validation; one failed batch prevents Qdrant upsert and activation.
- Kept staging activation and the previous collection as the rollback boundary.

No production retrieval filter, prompt, graph routing, fast answer, or answer-generation policy was changed.

## Metadata completeness

| Field | Before | After |
|---|---:|---:|
| `service` | 74/217 (34.10%) | 217/217 (100%) |
| `services` | 0/217 | 217/217 (100%) |
| `task` | 0/217 | 217/217 (100%) |
| `tasks` | 0/217 | 217/217 (100%) |
| `intent` | 74/217 (34.10%) | 217/217 (100%) |
| `language` | 0/217 | 217/217 (100%) |
| `source_type` | 74/217 (34.10%) | 217/217 (100%) |
| `document_type` | 0/217 | 217/217 (100%) |
| `metadata_schema_version=2` | 0/217 | 217/217 (100%) |

Post-activation validation found zero missing fields, zero non-list `services`/`tasks`, and zero wrong schema versions.

## Staging rebuild

- Previous active: `nthu_netsys_docs__1787924232138133628`
- New active: `nthu_netsys_docs__1787959330377891262`
- Status: green
- Pages/chunks: 70 / 217
- Old collection: retained

The original ingestion sent all 217 chunks in one embedding request. It timed out at both 3 and 30 seconds. A first 32-document batch also exceeded the production 3-second limit with real 800-character chunks. Measurements on the longest live chunks showed 4 documents at 0.96 seconds and 8 at 1.76 seconds, so the final default is 8.

The successful rebuild used 28 batches. The slowest observed batch was 2.066 seconds; total embedding time was 36.090 seconds. Activation occurred only after all batches and the staging upsert succeeded.

## Filtered retrieval shadow

Eight read-only vector-search cases covered:

- each of `campus_wifi`, `dorm_network`, `vpn`, and `email`;
- Wi-Fi + coverage;
- DormNet + configuration;
- VPN + configuration;
- email + application.

All eight returned at least one hit and had zero service/task metadata mismatches. This validates Qdrant's array-field filter behavior, but production `retrieve_context` still does not derive and enforce these filters for every known service.

## Full evaluation regression check

| Metric | Intent-final collection | Metadata-v2 collection | Delta |
|---|---:|---:|---:|
| conversation pass | 130/275 (47.27%) | 129/275 (46.91%) | -1 / -0.36 pp |
| turn pass | 183/337 (54.30%) | 182/337 (54.01%) | -1 / -0.29 pp |
| retrieval isolation | 212/216 (98.15%) | 213/217 (98.16%) | +0.01 pp |

Turn comparison: 182 stayed passing, 154 stayed failing, zero became passing, and one regressed.

The only changed case was `zh_single_014` (“校園無線超慢，是壞了嗎”). Topic remained `campus_wifi`, intent remained `troubleshooting`, and no metadata filter was applied. A direct production retrieval rerun returned five documents, led by `faq:wlan_useless`, with correct metadata. The end-to-end answer instead matched `fallback_for_prompt_leak()`: generation triggered the prompt-leak detector, which intentionally cleared response sources. The observed -1 is therefore a generation/safety-path result, not evidence of metadata-filter recall loss.

## Tests and decision

- Targeted: 56 passed, 22 subtests passed.
- Full: 139 passed, 24 subtests passed.
- Existing warning only: Starlette/httpx deprecation.

Keep the metadata contract, staged reindex, and embedding batching. The Phase 1 ingestion gate is complete. The next independently measured change should enforce service/task filters across vector search, priority pages, and page expansion, with an explicit plan for comparison/multi-service questions.
