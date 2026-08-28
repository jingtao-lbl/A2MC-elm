#!/usr/bin/env python3
"""restart_experiment_case.py — restart a single ad-hoc (offline-testing-workflow) case that
timed out mid-phase, without the numbered-ensemble machinery `diagnose_ensemble_status.py` and
the `restart-failed-jobs` skill assume.

WHY THIS EXISTS
---------------
`generate_phase_submit_command()` in `diagnose_ensemble_status.py` already has the correct
restart-year / STOP_N / forcing-cycle-snap-back / name-targeted-namelist-edit logic — but it
derives the case name and output root from the numbered Morris ensemble's
`A2MC_CASE_NAME_PATTERN` (`{N}_{PHASE}` only) and `A2MC_ENSEMBLE_OUTPUT`, neither of which match
a suffixed offline-testing-workflow experiment case (e.g.
`Kougarok_ELM-FATES_PtCNPEn2939_p169v6rffixADRGnone_ADSP`). Before this tool, restarting such a
case meant hand-computing everything and hand-typing the xmlchange/sed/case.setup/case.submit
sequence per case — done live 2026-08-14 for `ADRGnone` ADSP (TIMEOUT at year 111/200; see
`memory/dev_logs/20260814h_Restart_Generator_Targets_Namelist_Lines_By_Name.md`), which is also
where the underlying `sed -i '$ d'` positional-deletion bug this tool avoids was found and fixed.

WHAT IT DOES
------------
Given just a case's CIME scripts directory, this tool is self-contained:
  - case name       = the directory's own basename
  - phase           = parsed from the case name's `_ADSP`/`_RGSP`/`_TRANS` suffix
  - output root      = read from the case's own `env_build.xml` (`CIME_OUTPUT_ROOT`) --
                       NOT from `A2MC_ENSEMBLE_OUTPUT`, which is the wrong tree for an
                       ad-hoc experiment
  - forcing-cycle length = read from the case's own `env_run.xml`
                       (`DATM_CLMNCEP_YR_END - DATM_CLMNCEP_YR_START + 1`) -- NOT hardcoded or
                       taken from `A2MC_SPINUP_START_YEAR`/`_END_YEAR`, since a different
                       experiment or a different site's forcing window need not be 20 years
                       (PI, 2026-08-14)
  - last completed year = scanned from the case's own restart files on disk
                       (`diagnose_ensemble_status.get_restart_files`, size-filtered against
                       0-byte placeholders)

`--start-year`/`--end-year` fall back to `diagnose_ensemble_status.PHASES`'s defaults for the
detected phase (ADSP/RGSP start at year 1/201, TRANS at 1901, matching this project's ADSP->RGSP
internal-calendar-continuation convention) -- override them explicitly if a different experiment
uses a different convention. There is deliberately no single shared "PHASES" table duplicated
here; importing `diagnose_ensemble_status.PHASES` keeps one source of truth.

Cycle-snap-back applies to ADSP/RGSP only, never TRANS (TRANS writes a restart file every single
year, so there is no partially-replayed-forcing-cycle risk to snap back from).

The namelist edit targets lines BY NAME, matching the 2026-08-14 fix: `finidat` is always removed
before the new one is appended; `nyears_ad_carbon_only` is additionally removed for ADSP only (it
never appears in RGSP/TRANS namelists). Any other manually-appended line (e.g. a one-off
experiment's namelist flag with no `--write-script` CLI support yet) is left untouched regardless
of its position in the file.

DOWNSTREAM CHAIN REPAIR (automatic)
------------------------------------
Restarting a phase (or manually re-chaining one) creates a NEW job ID. Any already-queued
downstream phase submitted against the OLD job ID is now stale -- left alone, it strands on
`DependencyNeverSatisfied` once the old job's terminal state resolves. Found live 2026-08-16:
restarting `RGnone_RGSP` left the already-queued `RGnone_TRANS` chained to the dead old RGSP job
for ~30 hours, undetected by any monitor filter, until a routine status check surfaced it -- see
`memory/dev_logs/reflection/20260816a_Reflection_Restart_Tool_Left_A_Zombie_Its_Own_Docstring_Warned_About.md`.

After a successful `--execute`, this tool now walks the ENTIRE downstream chain automatically --
not just the immediate next phase. For each downstream phase that already has a job queued: cancel
it and resubmit with `--dependency=afterok:<the phase before it's new job ID>`, then continue to
the next phase down using THAT resubmission's own new job ID. Stops when a downstream phase has no
queued job (nothing stale to fix) or is already `RUNNING` (never touched -- something else already
resolved it, or it is genuinely running; cancelling a live job would be destructive, so the cascade
stops and reports rather than guessing).

This also covers the case a same-phase restart doesn't: a chain repair done as a plain, un-tooled
`./case.submit --dependency=afterok:$NEW_JOBID` (exactly what this tool's cascade itself does one
hop at a time) creates its own new job ID, which can leave a FURTHER-downstream phase stale the
same way. Run the cascade standalone against any case whose job ID just changed, however that
happened:

    python3 tools/restart_experiment_case.py --rechain-downstream \\
        --case-dir <path/to/the/phase/whose/job/ID/just/changed> --new-jobid <ITS_NEW_JOBID>

This is the same cascade `--execute` triggers automatically; exposed standalone so a manual
resubmit outside this tool is not a coverage gap.

Usage
-----
    # Preview only (default) -- prints the exact commands, runs nothing
    python3 tools/restart_experiment_case.py --case-dir <path/to/case>

    # Actually execute (xmlchange, sed, case.setup, case.submit)
    python3 tools/restart_experiment_case.py --case-dir <path/to/case> --execute

    # Save the generated plan as a durable script -- per offline-testing-workflow convention,
    # point this at the experiment's OWN phase_results/{stem}/, never repo-relative tmp/:
    python3 tools/restart_experiment_case.py --case-dir <path> --execute \\
        --output-script use_cases/<site>/memory/phase_results/{stem}/restart_<case_name>_<YYYYMMDD>.sh

    # Override phase/year defaults for a differently-configured experiment
    python3 tools/restart_experiment_case.py --case-dir <path> --phase ADSP \\
        --start-year 1 --end-year 200 --execute

    # Pass a SLURM dependency through to case.submit (rare for a same-phase restart; more useful
    # if you are ALSO using this tool as a plain resubmit-with-dependency helper)
    python3 tools/restart_experiment_case.py --case-dir <path> --dependency 56993596 --execute

    # Standalone downstream-chain repair -- e.g. after a manual, un-tooled resubmit changed a
    # phase's job ID and you need every already-queued phase below it re-chained:
    python3 tools/restart_experiment_case.py --rechain-downstream \\
        --case-dir <path/to/that/phase> --new-jobid <ITS_NEW_JOBID>

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnose_ensemble_status import PHASES, get_restart_files  # noqa: E402

_PHASE_SUFFIX_RE = re.compile(r"_(ADSP|RGSP|TRANS)$")

# The a2mc_env Python is required for CIME's own scripts (xmlchange, case.setup, case.submit) --
# the bare system python3 on Perlmutter is 3.6, and CIME requires 3.9+. Found live 2026-08-14:
# ./xmlchange failed with a RuntimeError under the bare interpreter. Prepending this to PATH for
# the subprocess calls avoids that trap for whoever runs --execute next.
_A2MC_ENV_BIN = os.path.expanduser("~/a2mc_env/bin")


def _xml_value(path: Path, entry_id: str) -> str | None:
    """Read `value="..."` for `id="<entry_id>"` from a CIME env_*.xml file, or None if absent."""
    if not path.is_file():
        return None
    m = re.search(rf'id="{re.escape(entry_id)}"[^>]*value="([^"]*)"', path.read_text())
    return m.group(1) if m else None


def _find_output_root(case_dir: Path) -> str:
    """CIME_OUTPUT_ROOT lives in env_build.xml for cases seen so far; check env_case.xml and
    env_run.xml too in case a different CIME vintage moves it (verified empirically 2026-08-14:
    absent from those two for the case this tool was built against)."""
    for fname in ("env_build.xml", "env_case.xml", "env_run.xml"):
        val = _xml_value(case_dir / fname, "CIME_OUTPUT_ROOT")
        if val:
            return val.rstrip("/")
    raise RuntimeError(
        f"CIME_OUTPUT_ROOT not found in env_build.xml/env_case.xml/env_run.xml under {case_dir}")


def _read_nl_int(user_nl_elm: Path, key: str) -> int | None:
    """Current integer value of a `key = value` line in user_nl_elm, or None if absent.

    Read BEFORE any edit -- used to decide whether an ADSP restart is still inside the
    carbon-only window, which the window's own boundary (not the restart mechanism) decides.
    """
    if not user_nl_elm.is_file():
        return None
    m = re.search(rf"^{re.escape(key)}\s*=\s*(\d+)", user_nl_elm.read_text(), re.M)
    return int(m.group(1)) if m else None


def _find_forcing_cycle_length(case_dir: Path) -> int:
    start = _xml_value(case_dir / "env_run.xml", "DATM_CLMNCEP_YR_START")
    end = _xml_value(case_dir / "env_run.xml", "DATM_CLMNCEP_YR_END")
    if start is None or end is None:
        raise RuntimeError(f"DATM_CLMNCEP_YR_START/END not found in {case_dir}/env_run.xml")
    return int(end) - int(start) + 1


def _detect_phase(case_name: str) -> str:
    m = _PHASE_SUFFIX_RE.search(case_name)
    if not m:
        raise RuntimeError(
            f"Could not detect phase from case name {case_name!r} "
            f"(expected a trailing _ADSP/_RGSP/_TRANS) -- pass --phase explicitly")
    return m.group(1)


def _downstream_phase(phase: str) -> str | None:
    """The phase whose prev_phase is `phase`, or None if `phase` is terminal (TRANS).

    Derived from PHASES rather than a hardcoded ADSP->RGSP->TRANS chain, so a differently
    configured experiment's phase ordering (via PHASES itself, imported from
    diagnose_ensemble_status) is respected automatically.
    """
    for p, info in PHASES.items():
        if info.get("prev_phase") == phase:
            return p
    return None


def _cime_env() -> dict:
    """Env for CIME subprocess calls (xmlchange/case.setup/case.submit), with a2mc_env's Python
    prepended to PATH -- the bare system python3 on Perlmutter is 3.6, and CIME requires 3.9+."""
    env = os.environ.copy()
    if os.path.isdir(_A2MC_ENV_BIN):
        env["PATH"] = f"{_A2MC_ENV_BIN}:{env.get('PATH', '')}"
    else:
        print(f"# WARNING: {_A2MC_ENV_BIN} not found; relying on the ambient PATH's python3 "
              f"being >=3.9 for CIME.", file=sys.stderr)
    return env


def _queued_job_for_case(case_name: str) -> tuple[str, str] | None:
    """The (job_id, state) currently queued under this case name (matching CIME's
    `run.<case_name>` job naming), or None if nothing is queued. Best-effort -- a squeue failure
    is treated as "nothing queued" rather than raised, since chain repair must never block on a
    transient scheduler hiccup."""
    try:
        out = subprocess.run(
            ["squeue", "-u", os.environ.get("USER", ""), "-h", "-n", f"run.{case_name}",
             "-o", "%A %T"],
            capture_output=True, text=True, timeout=15)
    except Exception:
        return None
    lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    if not lines:
        return None
    parts = lines[0].split()
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def rechain_downstream_cascade(case_dir: Path, phase: str, new_jobid: str,
                                queue: str, memory: str) -> None:
    """Walk the ENTIRE downstream chain from `phase`, cancelling and resubmitting any already-
    queued downstream job with a corrected --dependency=afterok, propagating each newly-created
    job ID to the next hop. Stops when a downstream phase has no queued job (chain repair
    complete) or is already RUNNING (never cancel a live job -- stop and report instead of
    guessing why). See the module docstring's "DOWNSTREAM CHAIN REPAIR" section for the incident
    this closes.
    """
    current_phase = phase
    current_jobid = new_jobid
    prefix = case_dir.name[: -(len(phase) + 1)]  # strip the trailing _ADSP/_RGSP/_TRANS

    while True:
        downstream = _downstream_phase(current_phase)
        if downstream is None:
            print(f"# Chain repair complete -- {current_phase} has no downstream phase.",
                  file=sys.stderr)
            return

        downstream_case = f"{prefix}_{downstream}"
        found = _queued_job_for_case(downstream_case)
        if found is None:
            print(f"# No {downstream_case} job currently queued -- chain repair complete.",
                  file=sys.stderr)
            return

        downstream_jobid, downstream_state = found
        if downstream_state != "PENDING":
            print(f"# {downstream_case} (job {downstream_jobid}) is {downstream_state}, not "
                  f"PENDING -- NOT touching it (only a stale-dependency PENDING job is safe to "
                  f"cancel+resubmit here). Chain repair stops at this hop; verify its dependency "
                  f"manually if you're unsure it's correct.", file=sys.stderr)
            return

        downstream_dir = case_dir.parent / downstream_case
        print(f"# Re-chaining {downstream_case}: cancelling stale job {downstream_jobid}, "
              f"resubmitting with --dependency=afterok:{current_jobid}", file=sys.stderr)
        subprocess.run(["scancel", downstream_jobid], check=True, timeout=30)

        batch_args = f"-q {queue} --mem={memory} --dependency=afterok:{current_jobid}"
        result = subprocess.run(
            ["./case.submit", f"--batch-args={batch_args}"],
            cwd=downstream_dir, env=_cime_env(), capture_output=True, text=True)
        output = (result.stdout or "") + (result.stderr or "")
        print(output, end="")
        if result.returncode != 0:
            print(f"# ERROR: resubmitting {downstream_case} failed (exit {result.returncode}) -- "
                  f"chain repair stops here. {downstream_case} is now CANCELLED and NOT "
                  f"resubmitted; fix and resubmit it by hand.", file=sys.stderr)
            return

        m = re.search(r"Submitted job id is (\d+)", output)
        if not m:
            print(f"# ERROR: could not parse a new job ID for {downstream_case} from "
                  f"case.submit's output -- chain repair stops here even though the submit "
                  f"itself appeared to succeed. Check `squeue` for {downstream_case} by hand.",
                  file=sys.stderr)
            return

        current_jobid = m.group(1)
        current_phase = downstream
        print(f"# {downstream_case} resubmitted as job {current_jobid}\n", file=sys.stderr)


def _check_restart_staleness(run_dir: str, case_name: str, years: list[int]) -> None:
    """Refuse to restart from a leftover restart file belonging to a SUPERSEDED run segment.

    `get_restart_files()` globs `*.elm.r.*.nc`, filters only on file SIZE, and returns years
    sorted BY YEAR. It has no notion of which run segment wrote a file. So a stale
    high-numbered restart left in `run/` by an earlier, abandoned attempt outranks every file
    the CURRENT segment has written, and `years[-1]` silently selects it.

    Motivating near-miss, 2026-08-21 (stated precisely, because the existing size filter DID
    hold here): ADRGnone_RGSP had a year-0401 restart dated 2026-08-12 sitting beside
    0211-0251 written 2026-08-20/21 by the live segment. It did NOT mis-select, because that
    0401 file is 0 bytes -- an earlier attempt crashed mid-write -- and `get_restart_files`
    drops sub-1KB placeholders. So this guard fixes nothing that was broken that day.

    What it covers is the adjacent case the size filter cannot see: a stale restart that was
    written SUCCESSFULLY by a superseded segment. Had that 08-12 attempt reached 0401 cleanly
    instead of crashing, the file would have been a valid 4.7 MB restart, `years[-1]` would
    have been 401, and the tool would have resumed from a 7-day-old state 145 model-years
    ahead of the live run -- or aborted with a confusing "may already be complete" when STOP_N
    went <= 0. Re-running a case to a shorter end year than a previous attempt reaches exactly
    that state. This guard is therefore DEFENSIVE, not incident-driven.

    The signal is unambiguous and needs no threshold tuning: within ONE segment, a higher
    restart year is always written LATER. Year order and mtime order agreeing is an invariant;
    a inversion means more than one segment's files are present.
    """
    stamped = {}
    for y in years:
        f = Path(f"{run_dir}/run/{case_name}.elm.r.{y:04d}-01-01-00000.nc")
        if f.is_file():
            stamped[y] = f.stat().st_mtime
    if len(stamped) < 2:
        return

    newest_year = max(stamped)
    latest_written = max(stamped, key=lambda y: stamped[y])
    if newest_year == latest_written:
        return  # year order and mtime order agree -- single coherent segment

    import datetime as _dt

    def _fmt(y):
        return (f"    year {y:04d}  written "
                f"{_dt.datetime.fromtimestamp(stamped[y]):%Y-%m-%d %H:%M}")

    raise RuntimeError(
        f"Restart files in {run_dir}/run/ come from MORE THAN ONE run segment -- refusing to "
        f"guess which one to continue.\n"
        f"  highest-numbered restart (what would have been picked):\n{_fmt(newest_year)}\n"
        f"  most-recently-written restart (what the live segment actually reached):\n"
        f"{_fmt(latest_written)}\n"
        f"Within a single segment a higher year is always written later, so this inversion "
        f"means year {newest_year:04d} is a leftover from a superseded attempt.\n"
        f"Fix by either (a) re-running with --restart-year {latest_written} to continue the "
        f"live segment, or (b) moving the stale file out of run/ if it is genuinely obsolete.\n"
        f"Do NOT simply delete it without checking which segment it belongs to.")


def build_restart_plan(case_dir: Path, phase: str | None, start_year: int | None,
                        end_year: int | None, dependency: str | None,
                        queue: str, memory: str,
                        restart_year_override: int | None = None) -> list[str]:
    case_name = case_dir.name
    if phase is None:
        phase = _detect_phase(case_name)
    if phase not in PHASES:
        raise RuntimeError(f"Unknown phase {phase!r}; must be one of {sorted(PHASES)}")

    output_root = _find_output_root(case_dir)
    run_dir = f"{output_root}/{case_name}"
    years = get_restart_files(run_dir)
    if not years:
        raise RuntimeError(f"No valid (non-placeholder) restart files found under {run_dir}/run/")

    if restart_year_override is not None:
        if restart_year_override not in years:
            raise RuntimeError(
                f"--restart-year {restart_year_override} has no restart file on disk "
                f"(years present: {years})")
        last_year = restart_year_override
    else:
        _check_restart_staleness(run_dir, case_name, years)
        last_year = years[-1]

    phase_info = PHASES[phase]
    start = start_year if start_year is not None else phase_info["start_year"]
    end = end_year if end_year is not None else phase_info["end_year"]

    batch_args = f"-q {queue} --mem={memory}"
    if dependency:
        batch_args += f" --dependency=afterok:{dependency}"

    restart_year = last_year
    if phase in ("ADSP", "RGSP"):
        cycle_len = _find_forcing_cycle_length(case_dir)
        elapsed = restart_year - start
        aligned_elapsed = (elapsed // cycle_len) * cycle_len
        aligned_year = start + aligned_elapsed

        # No progress beyond the FIRST forcing cycle: aligned_year == start, so the "continue"
        # plan would discard everything and resume at the case's own original start point --
        # numerically identical to a fresh run, but reached via the continue-mode namelist
        # surgery (xmlchange + sed + finidat-append), which only adds risk (repeated edits,
        # possible duplicate/stale lines) for zero benefit over the case's already-correct
        # as-created state. PI, 2026-08-14: in this range, just resubmit unchanged.
        if aligned_year == start:
            print(f"# No progress beyond the first {cycle_len}-year forcing cycle (last restart "
                  f"year {last_year}, start {start}) -- resubmitting as-is, no namelist changes.",
                  file=sys.stderr)
            return [
                f"cd {case_dir}",
                f"# Bare resubmit -- case is already correctly configured from creation time",
                f'./case.submit --batch-args="{batch_args}"',
            ]

        if aligned_year != restart_year:
            print(f"# Cycle-snap-back: last restart year {last_year} is not aligned to the "
                  f"{cycle_len}-year forcing cycle (start={start}); resuming from {aligned_year} "
                  f"instead (discards years {aligned_year}-{last_year} of completed-but-"
                  f"not-cycle-safe progress).", file=sys.stderr)
            restart_year = aligned_year

    stop_n = end - restart_year + 1
    if stop_n <= 0:
        raise RuntimeError(
            f"Computed STOP_N={stop_n} <= 0 (restart_year={restart_year}, end_year={end}) -- "
            f"this case may already be complete for this phase.")

    restart_yearstr = f"{restart_year:04d}"
    restart_file = f"{run_dir}/run/{case_name}.elm.r.{restart_yearstr}-01-01-00000.nc"
    if not Path(restart_file).is_file():
        raise RuntimeError(
            f"Computed finidat target does not exist on disk: {restart_file}\n"
            f"(restart years actually on disk: {years})")

    sed_targets = ["/^finidat/d"]
    dropped_note = None
    if phase == "ADSP":
        # Keep nyears_ad_carbon_only if the restart point is still WITHIN the carbon-only
        # window -- removing it would silently end carbon-only mode early on this segment.
        # Only drop it once restart_year is past the window (matching the existing convention
        # of omitting it once carbon-only has already closed). PI, 2026-08-14; example: last
        # restart year 31 snaps back to 21 (20-year cycle), which is still <= a 30-year
        # carbon-only window -- keep the line, do not remove it.
        k = _read_nl_int(case_dir / "user_nl_elm", "nyears_ad_carbon_only")
        if k is None or restart_year > k:
            sed_targets.append("/^nyears_ad_carbon_only/d")
            # Record the value being dropped. Dropping it is correct (see above), but the
            # generated script is a durable artifact that a reader may consult on its own,
            # and after the sed nothing in the case dir still says what the carbon-only
            # window WAS. That matters here specifically: the carbon-only phase meets plant
            # nutrient demand by supplement regardless of suplphos, so its length is part of
            # the case's nutrient protocol, not an incidental spin-up knob
            # (curated: ad_carbon_only_injects_phosphorus).
            if k is not None:
                dropped_note = (f"# NOTE: dropping nyears_ad_carbon_only = {k} (restart year "
                                f"{restart_year} is past the carbon-only window). The case was RUN "
                                f"with {k}; see its run_*.sh for the authoritative protocol.")
        else:
            print(f"# Keeping nyears_ad_carbon_only = {k} -- restart year {restart_year} is "
                  f"still within the carbon-only window.", file=sys.stderr)
    sed_cmd = f"sed -i '{'; '.join(sed_targets)}' ./user_nl_elm"

    return [
        f"cd {case_dir}",
        f"# Continue {phase} from year {restart_year} (last completed: {last_year}) "
        f"-> STOP_N={stop_n}, RUN_STARTDATE={restart_yearstr}-01-01",
        f"./xmlchange STOP_N={stop_n}",
        f"./xmlchange RUN_STARTDATE={restart_yearstr}-01-01",
        *([dropped_note] if dropped_note else []),
        sed_cmd,
        f"echo \"finidat = '{restart_file}'\" >> user_nl_elm",
        "./case.setup",
        f'./case.submit --batch-args="{batch_args}"',
    ]


def write_script(commands: list[str], output_script: Path) -> None:
    """Persist the generated plan as a durable, executable script.

    Per offline-testing-workflow's artifact-placement rule, this belongs in the experiment's own
    `use_cases/<site>/memory/phase_results/{stem}/`, NOT repo-relative `tmp/` (that convention is
    for ensemble-scale monitor/submitter logs only) -- the caller decides the path; this function
    just writes it and does not default or guess a location, per CLAUDE.md rule 8 (no hardcoded
    paths).
    """
    output_script.parent.mkdir(parents=True, exist_ok=True)
    script_text = "#!/usr/bin/env bash\nset -e\n" + "\n".join(commands) + "\n"
    output_script.write_text(script_text)
    output_script.chmod(0o755)
    print(f"# Plan saved to {output_script}", file=sys.stderr)


def run_commands(commands: list[str]) -> str:
    """Execute the plan as a single shell, using CIME-compatible env (see `_cime_env()`).

    Streams output live (as before) while also capturing it, so the new job ID can be parsed
    from `case.submit`'s "Submitted job id is N" line afterward for the downstream-rechain cascade.
    Returns the full captured stdout+stderr text.
    """
    script = "set -e\n" + "\n".join(commands) + "\n"
    proc = subprocess.Popen(["bash", "-c", script], env=_cime_env(), stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines = []
    for line in proc.stdout:
        print(line, end="")
        lines.append(line)
    proc.wait()
    output = "".join(lines)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, ["bash", "-c", script], output=output)
    return output


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Restart a single ad-hoc offline-testing-workflow case from its own last "
                    "valid restart file.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--case-dir", required=True, type=Path,
                    help="The case's CIME scripts directory (contains env_run.xml, user_nl_elm, "
                         "case.submit).")
    ap.add_argument("--phase", choices=sorted(PHASES),
                    help="Override phase detection (default: parsed from the case name's "
                         "_ADSP/_RGSP/_TRANS suffix).")
    ap.add_argument("--start-year", type=int, help="Override the phase's start year.")
    ap.add_argument("--end-year", type=int, help="Override the phase's end year.")
    ap.add_argument("--restart-year", type=int,
                    help="Continue from THIS restart year instead of the highest one on disk. "
                         "Required when run/ holds restart files from more than one segment "
                         "(the staleness guard raises and names the year to pass).")
    ap.add_argument("--dependency", help="SLURM job ID for --dependency=afterok:<id>.")
    ap.add_argument("--queue", default=os.environ.get("A2MC_QUEUE", "shared"))
    ap.add_argument("--memory", default=os.environ.get("A2MC_MEMORY", "16G"))
    ap.add_argument("--execute", action="store_true",
                    help="Actually run the commands. Default is dry-run (print only).")
    ap.add_argument("--output-script", type=Path,
                    help="Save the generated plan as a durable, executable script at this path. "
                         "Per offline-testing-workflow convention, point this at the experiment's "
                         "own use_cases/<site>/memory/phase_results/{stem}/ -- never repo-relative "
                         "tmp/, which is the ensemble-scale convention, not this one's.")
    ap.add_argument("--rechain-downstream", action="store_true",
                    help="Standalone mode: skip the restart plan entirely and just cascade-repair "
                         "the downstream chain below --case-dir, treating --new-jobid as its "
                         "current job ID. For a chain repair needed after a manual, un-tooled "
                         "resubmit (or to re-run the cascade if it stopped partway).")
    ap.add_argument("--new-jobid",
                    help="Required with --rechain-downstream: the job ID --case-dir's phase is "
                         "now running under, to chain the downstream phase(s) against.")
    args = ap.parse_args()

    case_dir = args.case_dir.resolve()
    if not case_dir.is_dir():
        print(f"ERROR: not a directory: {case_dir}", file=sys.stderr)
        return 2

    if args.rechain_downstream:
        if not args.new_jobid:
            print("ERROR: --rechain-downstream requires --new-jobid.", file=sys.stderr)
            return 2
        phase_used = args.phase if args.phase else _detect_phase(case_dir.name)
        rechain_downstream_cascade(case_dir, phase_used, args.new_jobid, args.queue, args.memory)
        return 0

    try:
        commands = build_restart_plan(
            case_dir, args.phase, args.start_year, args.end_year,
            args.dependency, args.queue, args.memory, args.restart_year)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("\n".join(commands))

    if args.output_script:
        write_script(commands, args.output_script)
    elif args.execute:
        print("# WARNING: --execute with no --output-script -- this run leaves no durable record "
              "under phase_results/{stem}/. Consider re-running with --output-script.",
              file=sys.stderr)

    if args.execute:
        print("\n# Executing...", file=sys.stderr)
        output = run_commands(commands)
        m = re.search(r"Submitted job id is (\d+)", output)
        new_jobid = m.group(1) if m else None
        phase_used = args.phase if args.phase else _detect_phase(case_dir.name)
        if new_jobid:
            rechain_downstream_cascade(case_dir, phase_used, new_jobid, args.queue, args.memory)
        else:
            print("# WARNING: could not parse a new job ID from case.submit's output -- "
                  "skipping the downstream-chain cascade. If a downstream phase is already "
                  "queued, check it by hand or re-run with --rechain-downstream --new-jobid "
                  "<id> once you know the new job ID.", file=sys.stderr)
    else:
        print("\n# Dry run only -- pass --execute to actually run these commands.",
              file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
