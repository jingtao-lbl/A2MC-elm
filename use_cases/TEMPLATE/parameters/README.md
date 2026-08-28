# `parameters/` — the parameter lists and the sampled design matrices

**One parameter list and one matrix per round.** The list declares what is calibrated and within what bounds; the matrix is the sample drawn from it. Column `j` of the matrix is row `j` of the list, and nothing re-derives that mapping at analysis time.

## Skills to use when working in this folder

| doing what | skill |
|---|---|
| designing a round's list and sampling it | **`phase0-design`** |
| refining bounds from published ranges | **`literature-review`** (its PARAMETER-BOUNDS mode) |
| checking what a parameter actually does | `phase3-diagnosis` — and the model's own source, never the name |

## The schema

`parameter_list_template.csv` is the canonical explicit-column form. The loader is `tools/param_spec.py`; it requires a name column (`param_name`, canonical — `fates_name` is accepted as a legacy alias), `pft`, `lower`, `upper`, and a default column (`default`, or `default_api43`). Everything downstream derives from this file, so the header is a contract, not a style choice.

```bash
python tools/validate_param_list.py     # every name exists in the model param file; organ dims agree
```

## The rules that bite

- **A bound needs a source, not an envelope.** `bound_source` records where a range came from — `measured:` · `literature:` · `database:` · `prior_round:` · `provisional:`. A naive default ±50% is not a bound source, and a provisional bound should say so rather than pass as evidence.
- **Case *N* is design-matrix row *N−1*.** Adjacent rows of a structured design agree in most columns, so an off-by-one returns the right value most of the time and a silently wrong one otherwise. A spot check will not reveal it — verify the mapping, do not sample it.
- **Never infer a parameter's effect from its name.** Trace read → internal variable → equation in the model source before setting a bound or designing a test; a parameter's `long_name` and units can be wrong.
- **Derive the PFT count from the base parameter file**, never hardcode it. The calibrated PFT ids are a separate thing from how many the file holds, and PFT ids are not stable across model versions — map by functional type and verify against the base file's own names.

## Verify before submitting

```bash
python tools/validate_param_list.py
python tools/validate_submission_plan.py    # param files exist, no unresolved tokens, no queue collisions
```
