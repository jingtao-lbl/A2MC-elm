# [Site Name] - A2MC Use Case

**Location:** [City/Region, Country]
**Coordinates:** [Lat, Lon]
**Ecosystem:** [e.g., Arctic tundra, Boreal forest, Temperate grassland]
**Status:** [Planning / Active / Complete]

---

## Folder map — and which skill governs each

**Every folder has its own `README.md` naming the skills to use when working in it.** Read that one before touching anything in the folder; this table is only the index.

| folder | purpose | skills that govern it |
|---|---|---|
| [`config/`](config/README.md) | what a session **sources** — case + round configs, the round ledger | `phase0-design` · `onboard-case` · `model-evolution` |
| [`parameters/`](parameters/README.md) | per-round parameter lists and sampled design matrices | `phase0-design` · `literature-review` |
| [`validation/`](validation/README.md) | `targets.yaml` — everything scored, and what is deliberately not | `onboard-case` · `phase6-refinement` · `plotting` |
| [`case_template/`](case_template/README.md) | the reference case scripts a case is built from | `phase0-design` · `offline-testing-workflow` |
| [`scripts/`](scripts/README.md) | the case's long-lived scripts and script **templates** | `plotting` · `scientific-analysis` · `compare-calibration-rounds` |
| [`memory/logs/`](memory/logs/README.md) | the phase logs — the 3→4→5→6→3 reasoning chain | **`calibration-log`** · the phase skills |
| [`memory/phase_results/`](memory/phase_results/README.md) | self-documenting artifact folders, one per phase, sharing the log's stem | `plotting` · `calibration-log` |
| [`memory/model_evolution/`](memory/model_evolution/README.md) | changes to the MODEL's source, and which round ran which binary | **`model-evolution`** · `add-fates-parameter` · `summarize-calibration-round` |
| [`memory/gained_knowledge/`](memory/gained_knowledge/README.md) | the curated KB — and the human gate in front of it | **`curate-knowledge`** · `inject-knowledge` |
| [`reports/`](reports/README.md) | project-team-facing synthesis, tracing back to the logs and artifacts | **`write-report`** · `summarize-calibration-round` |

**Above all of them:** `calibration-goal` drives the loop, and `calibration-discipline` says when a phase is actually finished rather than merely done.

## Overview

Brief description of the site and calibration goals.

---

## Target PFTs

| PFT Index | Name | Description |
|-----------|------|-------------|
| PFT#X | [Name] | [Description] |
| PFT#Y | [Name] | [Description] |

---

## Validation Targets

### Biomass Targets

| Variable | PFT | Observed (g C/m²) | Uncertainty | Source |
|----------|-----|-------------------|-------------|--------|
| Leaf | PFT#X | XX.X | ±20% | [Citation] |
| Fine Root | PFT#X | XX.X | ±20% | [Citation] |

### Ecosystem Targets

| Variable | Observed | Uncertainty | Source |
|----------|----------|-------------|--------|
| LAI (peak) | X.X | ±20% | [Citation] |
| GPP (annual) | XXX | ±20% | [Citation] |

---

## Data Sources

- **Biomass data:** [Source/Citation]
- **Climate forcing:** [Source]
- **Soil data:** [Source]

---

## Configuration

Key site-specific parameters:

```yaml
site:
  name: "[Site Name]"
  lat: XX.XX
  lon: XX.XX

pfts:
  - index: X
    name: "[PFT Name]"

morris:
  n_trajectories: 30
  n_params: 162
```

---

## Key Findings

Document discoveries and lessons learned during calibration.

### Discovery 1: [Name]

**Description:** ...

**Mechanism:** ...

**Affected parameters:** ...

---

## Files

| File | Description |
|------|-------------|
| `config.yaml` | Site configuration |
| `validation/targets.yaml` | Calibration targets + obs↔sim time matching + cost config (snapshot or time series). See `docs/24_Generic_Obs_Comparison_Plan.md` |
| `validation_targets.json` | Target values for calibration |

---

## References

- [Relevant publications]
- [Data sources]
