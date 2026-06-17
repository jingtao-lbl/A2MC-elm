#!/usr/bin/env python3
"""Validate auto-generated ELM-FATES ensemble restart scripts.

Checks that a restart script produced by tools/diagnose_ensemble_status.py
is internally consistent and that every filesystem entity it references
exists, so it is safe to execute. Catches the kinds of bugs that otherwise
require manual review:

  - user_nl_elm last line is `finidat = ...` (so `sed -i '$ d'` deletes the
    correct line)
  - the restart .nc file pointed to by each `finidat = ...` exists (continue
    mode); fresh-start finidat exists in the previous phase's run dir
  - chained TRANS / RGSP case dirs exist for ADSP / RGSP restarts
  - STOP_N + RUN_STARTDATE_year == phase end year, auto-detected from a
    completed sibling case (or supplied via --rgsp-end / --trans-end)
  - chained phase wiring: a chained TRANS uses `--dependency=afterok:$JOBID_RGSP_<N>`
    that matches a $JOBID_RGSP_<N> set earlier in the same case block
  - batch args present (`-q` queue and `--mem=`)
  - script case set == incomplete_cases_<TS>.txt case set (when supplied)

Usage:
    # auto-discover incomplete_cases_<TS>.txt alongside the script
    python tools/validate_restart_script.py /path/to/restart_incomplete_<TS>.sh

    # with explicit cross-reference
    python tools/validate_restart_script.py restart_incomplete_<TS>.sh \\
        --incomplete-cases incomplete_cases_<TS>.txt

    # override auto-detected phase end years
    python tools/validate_restart_script.py restart_incomplete_<TS>.sh \\
        --rgsp-end 401 --trans-end 2020

Exit code 0 = all checks pass, 1 = any check fails.
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------- parsing ----------

CASE_HEADER_RE = re.compile(r"^#\s*Case\s+(\d+):\s*Restart from\s+(\w+)\s*\((\w+)\)")
PHASES_RE = re.compile(r"^#\s*Phases to submit:\s*(.+)$")
PHASE_SECTION_RE = re.compile(r"^#\s*---\s*(\w+)\s*Phase\s*---")
CD_RE = re.compile(r"^\s*cd\s+(\S+)")
STOP_N_RE = re.compile(r"xmlchange\s+STOP_N=(\d+)")
RUN_STARTDATE_RE = re.compile(r"xmlchange\s+RUN_STARTDATE=(\d{4})-(\d{2})-(\d{2})")
FINIDAT_RE = re.compile(r"finidat\s*=\s*'([^']+)'")
RESTART_YEAR_RE = re.compile(r"\.elm\.r\.(\d{4})-\d{2}-\d{2}-\d{5}\.nc$")
SUBMIT_BATCH_RE = re.compile(r"case\.submit\s+--batch-args=\"([^\"]+)\"")
DEPENDENCY_RE = re.compile(r"--dependency=afterok:\$JOBID_(\w+)_(\d+)")
JOBID_ASSIGN_RE = re.compile(r"JOBID_(\w+)_(\d+)=")
# Count `sed -i '$ d'` (trailing-line deletes) per phase block. ADSP-continue
# deletes 2 (finidat='' + nyears_ad_carbon_only=K, the AD-carbon-only line) and
# re-appends finidat (+ nyears iff restart_year<=K); RGSP/TRANS delete 1 (finidat).
SED_DELETE_RE = re.compile(r"sed\s+-i\s+'\$\s*d'")


@dataclass
class PhaseBlock:
    phase: str                    # ADSP / RGSP / TRANS
    case_dir: Optional[str] = None
    stop_n: Optional[int] = None
    run_startdate_year: Optional[int] = None
    finidat: Optional[str] = None
    batch_args: Optional[str] = None
    dependency: Optional[tuple] = None   # (phase_dep, case_dep)
    is_dependency_target: bool = False   # this phase defines JOBID_<P>_<N>
    sed_deletes: int = 0                  # count of `sed -i '$ d'` trailing-line deletes
                                          # (1 = RGSP/TRANS finidat; 2 = ADSP finidat+nyears_ad_carbon_only)


@dataclass
class CaseBlock:
    case_num: int
    primary_phase: str            # phase recorded in the header
    mode: str                     # continue / fresh
    chain: list                   # list of phase names from "Phases to submit:"
    phases: dict = field(default_factory=dict)   # phase_name -> PhaseBlock


def parse_script(path: Path) -> list:
    cases = []
    current_case = None
    current_phase = None

    for raw in path.read_text().splitlines():
        line = raw.rstrip()

        m = CASE_HEADER_RE.match(line)
        if m:
            if current_case is not None:
                cases.append(current_case)
            current_case = CaseBlock(
                case_num=int(m.group(1)),
                primary_phase=m.group(2),
                mode=m.group(3),
                chain=[],
            )
            current_phase = None
            continue

        if current_case is None:
            continue

        m = PHASES_RE.match(line)
        if m:
            current_case.chain = [p.strip() for p in re.split(r"[→>,]+", m.group(1)) if p.strip()]
            continue

        m = PHASE_SECTION_RE.match(line)
        if m:
            current_phase = m.group(1)
            current_case.phases[current_phase] = PhaseBlock(phase=current_phase)
            continue

        if current_phase is None:
            continue
        pb = current_case.phases[current_phase]

        n_sed = len(SED_DELETE_RE.findall(line))
        if n_sed:
            pb.sed_deletes += n_sed
            continue

        m = CD_RE.match(line)
        if m and pb.case_dir is None:
            pb.case_dir = m.group(1)
            continue
        m = STOP_N_RE.search(line)
        if m:
            pb.stop_n = int(m.group(1))
            continue
        m = RUN_STARTDATE_RE.search(line)
        if m:
            pb.run_startdate_year = int(m.group(1))
            continue
        m = FINIDAT_RE.search(line)
        if m and pb.finidat is None:
            pb.finidat = m.group(1)
            continue
        m = SUBMIT_BATCH_RE.search(line)
        if m:
            pb.batch_args = m.group(1)
            m2 = DEPENDENCY_RE.search(m.group(1))
            if m2:
                pb.dependency = (m2.group(1), int(m2.group(2)))
            continue
        m = JOBID_ASSIGN_RE.search(line)
        if m and int(m.group(2)) == current_case.case_num and m.group(1) == current_phase:
            pb.is_dependency_target = True

    if current_case is not None:
        cases.append(current_case)
    return cases


# ---------- helpers ----------

def detect_phase_end_year(ensemble_output: Path, phase: str) -> Optional[int]:
    """Find the canonical end year of `phase` by scanning a completed case.

    Looks for a case where `<case>_<phase>/run/<case>_<phase>.elm.r.<YEAR>-01-01-00000.nc`
    exists for the highest YEAR — that's the end-year used in this ensemble.
    """
    if not ensemble_output.is_dir():
        return None
    pattern = re.compile(rf"\.elm\.r\.(\d{{4}})-01-01-00000\.nc$")
    years = set()
    # sample up to 50 case dirs for the phase
    sampled = 0
    for entry in sorted(ensemble_output.iterdir()):
        if not entry.is_dir() or not entry.name.endswith(f"_{phase}"):
            continue
        run_dir = entry / "run"
        if not run_dir.is_dir():
            continue
        for f in run_dir.iterdir():
            m = pattern.search(f.name)
            if m:
                years.add(int(m.group(1)))
        sampled += 1
        if sampled >= 50:
            break
    return max(years) if years else None


def check(passed: bool, msg: str, errors: list, warnings: list, level="error"):
    """Record a check; print PASS/FAIL with msg."""
    if passed:
        print(f"  PASS  {msg}")
    else:
        marker = "FAIL" if level == "error" else "WARN"
        print(f"  {marker}  {msg}")
        (errors if level == "error" else warnings).append(msg)


# ---------- validation ----------

def validate(cases, args, end_years, incomplete_set):
    errors, warnings = [], []

    if incomplete_set is not None:
        script_set = {c.case_num for c in cases}
        missing = incomplete_set - script_set
        extra = script_set - incomplete_set
        if missing:
            errors.append(f"Cases in incomplete_cases not in script: {sorted(missing)}")
            print(f"FAIL  cases in incomplete_cases_<TS>.txt missing from script: {sorted(missing)}")
        if extra:
            errors.append(f"Cases in script not in incomplete_cases: {sorted(extra)}")
            print(f"FAIL  cases in script not in incomplete_cases_<TS>.txt: {sorted(extra)}")
        if not missing and not extra:
            print(f"PASS  script case set matches incomplete_cases_<TS>.txt ({len(script_set)} cases)")

    for case in cases:
        print(f"\n=== Case {case.case_num}: {case.primary_phase} ({case.mode}), chain={'→'.join(case.chain)} ===")

        # chain integrity
        if not case.chain:
            check(False, "no 'Phases to submit' line found", errors, warnings)
        for ph in case.chain:
            if ph not in case.phases:
                check(False, f"chain mentions {ph} but no '--- {ph} Phase ---' block", errors, warnings)

        # for each phase block in this case
        for ph_name, pb in case.phases.items():
            print(f"  -- {ph_name} --")
            # case dir
            if pb.case_dir is None:
                check(False, "no cd <case_dir> line", errors, warnings)
            else:
                check(Path(pb.case_dir).is_dir(), f"case dir exists: {pb.case_dir}", errors, warnings)
                nl = Path(pb.case_dir) / "user_nl_elm"
                if nl.is_file():
                    nonblank = [l.strip() for l in nl.read_text().splitlines() if l.strip()]
                    nd = pb.sed_deletes
                    # The restart script does `sed -i '$ d'` nd times to strip the trailing
                    # finidat (RGSP/TRANS, nd=1) or finidat + nyears_ad_carbon_only (ADSP
                    # continue-past-carbon-only, nd=2) BEFORE re-appending. Validate that the
                    # nd lines about to be deleted are exactly those expected — not real config.
                    if nd == 0:
                        # No trailing-line deletion in this block (fresh cold start) — nothing
                        # to validate about the current user_nl_elm tail.
                        check(True, "no user_nl_elm `sed '$ d'` in this block (fresh/cold start)",
                              errors, warnings)
                    elif nd == 1:
                        last = nonblank[-1] if nonblank else ""
                        check(last.startswith("finidat"),
                              f"user_nl_elm last line is `finidat` (1 sed-delete) "
                              f"(got: {last[:60]!r})", errors, warnings)
                    else:  # nd >= 2: ADSP carbon-only-mode continue (double-sed)
                        tail = nonblank[-nd:] if len(nonblank) >= nd else nonblank
                        last = nonblank[-1] if nonblank else ""
                        # (a) pristine pre-restart: the nd lines to be deleted are exactly
                        #     finidat (='') + nyears_ad_carbon_only=K (last line = nyears).
                        pristine = (len(tail) == nd
                                    and any(t.startswith("finidat") for t in tail)
                                    and any(t.startswith("nyears_ad_carbon_only") for t in tail))
                        # (b) already-restarted (validator run mid-flight, after this case was
                        #     processed): nyears already stripped, real finidat .nc appended as
                        #     last line. Valid state — the double-sed already fired correctly.
                        already_restarted = last.startswith("finidat") and ".nc" in last
                        check(pristine or already_restarted,
                              f"user_nl_elm ADSP carbon-only tail is either pristine "
                              f"[finidat, nyears_ad_carbon_only] (pre-restart) or [finidat=<.nc>] "
                              f"(already restarted) (got last {nd}: {tail})",
                              errors, warnings)
                else:
                    check(False, f"user_nl_elm missing at {nl}", errors, warnings)

            # STOP_N / RUN_STARTDATE present
            check(pb.stop_n is not None, "STOP_N parsed", errors, warnings)
            check(pb.run_startdate_year is not None, "RUN_STARTDATE parsed", errors, warnings)

            # finidat
            if pb.finidat is None:
                check(False, "no finidat = '...' line", errors, warnings)
            else:
                check(Path(pb.finidat).is_file(),
                      f"finidat .nc exists: {pb.finidat}", errors, warnings)
                # restart-year embedded in finidat path matches RUN_STARTDATE for continue mode
                m = RESTART_YEAR_RE.search(pb.finidat)
                if m and pb.run_startdate_year is not None and ph_name == case.primary_phase and case.mode == "continue":
                    fyear = int(m.group(1))
                    check(fyear == pb.run_startdate_year,
                          f"finidat year ({fyear}) == RUN_STARTDATE year ({pb.run_startdate_year})",
                          errors, warnings)

            # STOP_N math: end_year(ph) == RUN_STARTDATE_year + STOP_N
            end_year = end_years.get(ph_name)
            if end_year is not None and pb.stop_n is not None and pb.run_startdate_year is not None:
                computed = pb.run_startdate_year + pb.stop_n
                check(computed == end_year,
                      f"STOP_N math: {pb.run_startdate_year} + {pb.stop_n} == {end_year} (expected end of {ph_name})",
                      errors, warnings)
            elif end_year is None:
                check(False, f"no expected end year known for {ph_name} (use --{ph_name.lower()}-end)",
                      errors, warnings, level="warning")

            # batch args
            if pb.batch_args is None:
                check(False, "no case.submit --batch-args=... found", errors, warnings)
            else:
                check("-q " in pb.batch_args, f"queue specified in batch args ({pb.batch_args!r})", errors, warnings)
                check("--mem=" in pb.batch_args, f"memory specified in batch args", errors, warnings)

            # dependency wiring
            if pb.dependency is not None:
                dep_phase, dep_case = pb.dependency
                check(dep_case == case.case_num,
                      f"dependency on JOBID_{dep_phase}_{dep_case} matches current case {case.case_num}",
                      errors, warnings)
                target_pb = case.phases.get(dep_phase)
                check(target_pb is not None and target_pb.is_dependency_target,
                      f"dependency target $JOBID_{dep_phase}_{dep_case} is assigned earlier in this case block",
                      errors, warnings)

    return errors, warnings


# ---------- main ----------

def main():
    p = argparse.ArgumentParser(description="Validate auto-generated FATES ensemble restart script")
    p.add_argument("script", type=Path, help="Path to restart_incomplete_<TS>.sh")
    p.add_argument("--incomplete-cases", type=Path, default=None,
                   help="Path to incomplete_cases_<TS>.txt (auto-discovered if omitted)")
    p.add_argument("--ensemble-output", type=Path, default=None,
                   help="Path to ensemble output dir for auto-detecting phase end years "
                        "(default: $A2MC_ENSEMBLE_OUTPUT)")
    p.add_argument("--adsp-end", type=int, default=None,
                   help="Override expected end year for ADSP")
    p.add_argument("--rgsp-end", type=int, default=None,
                   help="Override expected end year for RGSP")
    p.add_argument("--trans-end", type=int, default=None,
                   help="Override expected end year for TRANS")
    args = p.parse_args()

    if not args.script.is_file():
        print(f"ERROR: script not found: {args.script}", file=sys.stderr)
        sys.exit(2)

    # auto-discover incomplete_cases_<TS>.txt
    if args.incomplete_cases is None:
        m = re.search(r"restart_incomplete_(\d{8}_\d{6})\.sh$", args.script.name)
        if m:
            cand = args.script.parent / f"incomplete_cases_{m.group(1)}.txt"
            if cand.is_file():
                args.incomplete_cases = cand
                print(f"Found incomplete_cases: {cand}")

    incomplete_set = None
    if args.incomplete_cases is not None and args.incomplete_cases.is_file():
        incomplete_set = set()
        for ln in args.incomplete_cases.read_text().splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            try:
                incomplete_set.add(int(ln.split(",", 1)[0]))
            except ValueError:
                pass

    # auto-detect phase end years
    ensemble_output = args.ensemble_output or (
        Path(os.environ["A2MC_ENSEMBLE_OUTPUT"]) if "A2MC_ENSEMBLE_OUTPUT" in os.environ else None
    )
    end_years = {"ADSP": args.adsp_end, "RGSP": args.rgsp_end, "TRANS": args.trans_end}
    if ensemble_output is not None and ensemble_output.is_dir():
        print(f"Detecting phase end years from {ensemble_output}")
        for ph in ("ADSP", "RGSP", "TRANS"):
            if end_years[ph] is None:
                detected = detect_phase_end_year(ensemble_output, ph)
                if detected is not None:
                    end_years[ph] = detected
                    print(f"  detected {ph} end year = {detected}")
                else:
                    print(f"  could not detect {ph} end year")

    print(f"\nParsing {args.script}")
    cases = parse_script(args.script)
    print(f"Found {len(cases)} case blocks")

    # phase-count summary
    counts = defaultdict(int)
    submissions = 0
    for c in cases:
        counts[c.primary_phase] += 1
        submissions += len(c.phases)
    print("\n=== Phase summary ===")
    for ph in ("ADSP", "RGSP", "TRANS"):
        print(f"  {ph} restarts: {counts[ph]}")
    print(f"  total SLURM submissions (across chain): {submissions}")

    errors, warnings = validate(cases, args, end_years, incomplete_set)

    print("\n=== Result ===")
    print(f"  errors:   {len(errors)}")
    print(f"  warnings: {len(warnings)}")
    if errors:
        print("\nERRORS:")
        for e in errors:
            print(f"  - {e}")
    if warnings:
        print("\nWARNINGS:")
        for w in warnings:
            print(f"  - {w}")
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
