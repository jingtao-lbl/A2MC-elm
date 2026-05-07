# Mode-Aware Retrieval Verification Report

**Generated:** 2026-05-07T14:30:31+00:00

Doc 20 Phase A + Phase B verification. Runs the unittest fixture suite at `tests/test_mode_filters.py` plus a real-index smoke test (kb_source + mode-aware filter end-to-end) plus the Tier 4 mode-metadata validator (Doc 21 Chunk B.3.5).

---

## Fixture suite (`tests/test_mode_filters.py`)

- Tests run:   61
- Passed:      61
- Skipped:     0 (Phase B placeholders)
- Failures:    0
- Errors:      0

## Real-index smoke (active RAG profile)

| Test | Result | Detail |
|---|---|---|
| kb_source populated on all chunks (no MISSING/empty) | PASS | total=6328, fates=3272, elm=3056, missing/empty=0 |
| kb_source='fates' returns only FATES chunks | PASS | got 5 results, kb_sources={'fates'} |
| kb_source='elm' returns only ELM chunks | PASS | got 5 results, kb_sources={'elm'} |
| no filter returns mixed kb_sources | PASS | got 10 results, kb_sources={'elm', 'fates'} |
| ConfigMode default (bgc=sp -> ELM-only) -> kb_source_filter() == 'elm' | PASS | got 'elm' |
| ConfigMode(bgc_mode='fates') -> kb_source_filter() = None | PASS | got None |

**6/6 smoke tests pass.**

## Tier 4 mode-metadata validator (Doc 21 Chunk B.3.5)

- Verdict: **Green**
- OK:    81
- WARN:  0
- ERROR: 0

Asserts:
- (a) YAML-entity flags propagated to chunks + graph nodes
- (b) Path-prefix flags applied to wiki chunks
- (c) Precedence invariant (no chunk has both universal AND per-axis)
- (d) No-orphan invariant (every chunk has mode metadata)
- (e) Graph-chunk consistency for YAML-tagged entities

## Validator #1: snapshot (end-to-end integration)

- Verdict: **Green**
- Fixtures: 5/5 pass

Captures real Phase 3 prompt context for 5 ConfigMode fixtures and asserts mode block + filter both fire correctly.

## Validator #2: profile completeness (statistical coverage)

- Verdict: **Green**
- Chunks: 6328  |  Nodes: 3178

| Category | Severity | Summary |
|---|---|---|
| (a) Chunk-tagging distribution | OK | Within bounds |
| (b) Wiki-directory coverage | OK | All 13 path-prefix patterns matched expected chunks |
| (c) YAML-entity coverage | OK | All YAML entities have matching chunks |
| (d) Tier 2 axis distribution | OK | Tier 2 axes: 6 axes, distributions logged |
| (e) Golden chunk counts (per-mode) | OK | All 3 golden values within 50 tolerance |

## Validator #3: cross-milestone consistency

- Verdict: **Green**
- Profiles compared: canonical, api-43-1
- Drift: 0  |  Coverage warnings: 0

---

## Overall

- Fixtures:                 PASS
- Smoke:                    PASS
- Tier 4 (metadata):        Green
- Validator #1 (snapshot):  Green
- Validator #2 (coverage):  Green
- Validator #3 (x-milestone): Green
- Phase A+B status: **GREEN**