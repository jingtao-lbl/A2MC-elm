# `config/` — the case-level configuration, what a session SOURCES

**Everything here is live configuration that a working session sources.** A file in this folder should be one you might legitimately source today.

## Skills to use when working in this folder

| doing what | skill |
|---|---|
| **running anything at all** — the source order below is step 0 of it | `phase0-design` and the phase skills |
| opening a round (writing `_r<N>.sh`) | `phase0-design` |
| creating a case from scratch | `onboard-case` |
| a model-source change that changes the binary a round ran | `model-evolution` |

## The source order — ONE command

```bash
source use_cases/{Model}_{Case}/config/<case>_config.sh         # or the round wrapper, <case>_config_r<N>.sh
```

**Since 2026-08-26 the case config auto-sources the machine config** (`a2mc_config.sh`) when it has not been sourced yet, so the single command above is enough. Sourcing the machine config first still works and makes the bootstrap a no-op.

The layering order is unchanged and still matters: **machine defaults, then case overrides, then a round wrapper's overrides.**

Two properties of the bootstrap worth knowing, because they are the parts that could bite:

- **The path it discovers locates `a2mc_config.sh` only — it never becomes `A2MC_ROOT`,** which still comes from the machine config itself. `BASH_SOURCE` is a bash builtin and is **empty under zsh**; an earlier version that derived paths from it silently collapsed them to the wrong directory. Under zsh the bootstrap searches upward from the current directory instead.
- **It still fails loudly if it cannot find the file.** The `:?` guard remains as the backstop, so a shell is never left half-configured.

**Pick the round's config deliberately.** When a case has several round wrappers, the active one is named by `config_file` in `calibration_rounds.yaml` — read it there rather than guessing from the highest number.

**A case-level override must be unconditional.** Writing `: "${VAR:=x}"` in the case config is **inert** once the machine config has already set `VAR`; the case layer must assign bare (`VAR=x`) to actually override.

**Check rather than assume** — verify the chain resolved before trusting anything downstream:

```bash
echo "$A2MC_MAX_EXPERIMENTS $A2MC_MAX_SKIP_TESTING $A2MC_CONFIDENCE_THRESHOLD"   # none empty
python tools/check_setup_ready.py                                                 # the chain resolves
```

## `calibration_rounds.yaml` — generated first, then filled by the agent

| when | what | who |
|---|---|---|
| opening a round | generate the block, then fill `rationale` / `changes_from_previous` | `phase0-design` |
| creating the case | generate round 1 **last**, after the parameter list exists | `onboard-case` |
| a model source change lands | that round's `fates_source` — `patches`, and `binary` naming the archived build | `model-evolution` supplies it |
| closing a round | `outcome`, `status`, and the round's `fates_source.binary` claim | `summarize-calibration-round` |

Derive it, never hand-author it:

```bash
python tools/generate_calibration_rounds.py --round N --write
python tools/check_calibration_rounds.py
```

**Per-round `fates_source` is the point of the file** — it is what makes a cross-round comparison honest, and nothing else in the case records which build a round ran. `python tools/binary_archive_manifest.py --verify` cross-checks each round's `binary` claim against the manifest (check M7) and **prints how many claims it checked**, so a pass over zero claims is visible rather than silent. Two rounds run on different binaries are not comparable just because the numbers line up.

## What is in here today (Kougarok)

The live chain is `kougarok_config.sh` (which auto-sources `a2mc_config.sh`) plus `calibration_rounds.yaml`, whose round-1 `config_file` names the config actually in force. `binary_archive_manifest.json` records which executable each archived build is, so a round can state what it ran.

- `binary_archive_manifest.json`
- `calibration_rounds.yaml`
- `calibration_rounds_template.yaml`
- `kougarok_config.sh`
