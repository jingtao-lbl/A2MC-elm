# `validation/` — the targets, and what is NOT a target

**`targets.yaml` is the calibration surface: everything scored, and nothing else.** Every number the calibration optimises against is declared here, so a target added casually changes what "converged" means for the whole round.

## Skills to use when working in this folder

| doing what | skill |
|---|---|
| setting up a new case's targets | **`onboard-case`** |
| the sim-vs-obs figure covering every scored target | **`plotting`**, with `phase2-screening` or `phase6-refinement` |
| scoring a variant set against these | **`phase6-refinement`** |
| observations still pending | wire the **structure** with `observed: null` — the red preflight gate is the deliverable, not a placeholder number |

## The schema

Each entry under `targets:` is keyed `PFT<id>_<vartype>` (e.g. `PFT10_leaf`, `PFT10_fineroot`) and carries:

| key | meaning |
|---|---|
| `pft` | the PFT id this target scores |
| `variable` | the **model output variable name**, exactly as the model registers it (`FATES_LEAFC_SZPF`) |
| `observed` | the measured value — or `null` while the observation is pending |
| `uncertainty` / `uncertainty_type` | e.g. `0.2` / `relative` |
| `units`, `description` | for the reader and the figure captions |

File-level keys (`site`, `observation_date`, `time_year`, `time_month`, `pfts`) fix **when and where** the observation applies. They are not decoration: scoring a target against the wrong window is the most common way to produce a confident wrong number.

## Known traps

- **Never invent a `variable` name.** It must be a name the model actually registers, not a plausible one. A name that does not resolve scores nothing and warns about nothing.
- **ELM uses a 365-day no-leap calendar.** Do not assume Gregorian dates line up; read the model's own time axis.
- **A partially covered window is an ERROR, not a smaller sample.** Early termination is caused by instability, so the surviving tail is biased toward the blow-up. Census the record before scoring anything.
- **Say which window a number came from.** Spin-up years are not comparable to a transient-period target, and naming the window is the cheapest way to keep that straight.
- **Do not score an input.** Anything the run's initial state is built from is not a calibration target; scoring it rewards the input rather than the model.

## Verify

```bash
python tools/check_setup_ready.py     # targets present and structurally sound before Phase 0
```

Observations and their provenance live in `data/` — see its own README.

## What is in here today (Kougarok)

`targets.yaml` is the scored surface. `load_targets.py` is the loader that reads it — a **library** imported by several tools, so it lives here beside the file it loads rather than in `scripts/`. Observations and their provenance are under `data/`, which has its own README.

- `load_targets.py`
- `targets.yaml`
