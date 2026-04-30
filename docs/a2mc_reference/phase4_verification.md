# Phase 4 Verification Report

**Generated:** 2026-04-30T19:03:46+00:00

Per docs/18 §16 content-correctness gates plus end-to-end smoke tests of the milestone-tier infrastructure.

---

## Manifest summary

- Manifest path: `/Users/jingtao/Desktop/Work/NGEE-Arctic/Kougarok/Program/A2MC/rag/milestones.json`
- Registered milestones: 2

- **api-43-1** — `sci.1.91.1_api.43.1.0` (epoch 43.1)  [canonical, local]
- **api-31-0** — `sci.1.68.2_api.31.0.0` (epoch 31.0)  [legacy, local]

## api-31-0 content gates

**7 / 7 gates pass.**

### Detail

| Gate | Source | Result | Detail |
|---|---|---|---|
| fates_phen_gddthresh_a resolves | param_file | ✓ | present |
| fates_phen_gddthresh_b resolves | param_file | ✓ | present |
| fates_phen_gddthresh_c resolves | param_file | ✓ | present |
| fates_nonhydro_smpsc unit = mm | param_file | ✓ | unit = 'mm' |
| fates_nonhydro_smpso unit = mm | param_file | ✓ | unit = 'mm' |
| fates_fire_crown_kill resolves | graph | ✓ | found as node 'parameter:fates_fire_crown_kill' |
| fates_cnp_nfix NOT found (renamed to nfix1) | param_file | ✓ | correctly absent |

## api-43-1 content gates

**8 / 8 gates pass.**

### Detail

| Gate | Source | Result | Detail |
|---|---|---|---|
| fates_phen_gddthresh_a default = -68 | param_file | ✓ | default = -68.0 |
| fates_phen_gddthresh_b default = 638 | param_file | ✓ | default = 638.0 |
| fates_phen_gddthresh_c default = -0.01 | param_file | ✓ | default = -0.01 |
| fates_nonhydro_smpsc resolves | param_file | ✓ | present |
| fates_nonhydro_smpso resolves | param_file | ✓ | present |
| fates_fire_crown_kill resolves | graph | ✓ | found as node 'parameter:fates_fire_crown_kill' |
| fates_cnp_nfix1 resolves | param_file | ✓ | present |
| fates_cnp_eca_km_nh4 resolves (api-43 rename) | param_file | ✓ | present |

## End-to-end smoke tests

| Test | Result | Detail |
|---|---|---|
| manifest has both milestones | ✓ | 2 registered |
| HybridRetriever loads api-43-1 via env vars | ✓ | 6326 docs, 3178 graph nodes |
| HybridRetriever loads api-31-0 (profile switch) | ✓ | 2581 docs, 1295 graph nodes |
| Loader resolves wiki via explicit wiki_subdir (no symlink) | ✓ | 66 docs loaded |
| fates-codebase-wiki symlink removed | ✓ | absent |
| elm-codebase-wiki symlink removed | ✓ | absent |
| Selector matches api-43-1 user to api-43-1 milestone | ✓ | profile=api-43-1, mode=exact_epoch |
| Selector matches api-31 user to api-31-0 milestone | ✓ | profile=api-31-0, mode=exact_epoch |
| Per-milestone YAMLs exist and differ correctly | ✓ | api-31-0 has fates_cnp_km_nh4 (pre-3.5) |

---

## Overall

- api-31-0: 7/7
- api-43-1: 8/8
- smoke tests: 9/9
