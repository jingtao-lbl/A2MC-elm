#!/usr/bin/env python3
"""
Populate experiment entries into workflow_state.json for Phase 6 resume.

Two modes:
  1. --log-file: Parse Phase 5 experiment design log, inject entries into state
  2. --evaluate: Evaluate extracted NC files and populate results in state

Usage:
    # Step 1: Populate entries from experiment design log
    python tools/populate_experiments.py \
        --state-file use_cases/Kougarok/memory/workflow_state.json \
        --log-file use_cases/Kougarok/memory/logs/phase5_testing/r02_c00_iter06_20260226_125323_Experiment_Design.md

    # Step 2: Extract simulation outputs (on HPC)
    python tools/extract_monthly_variables_FATES.py --cases 322_c0_exp1 322_c0_exp2 ...

    # Step 3: Evaluate extracted results and update state
    python tools/populate_experiments.py \
        --state-file use_cases/Kougarok/memory/workflow_state.json \
        --evaluate

    # Step 4: Resume workflow at Phase 6
    python orchestrator.py --resume

Author: Jing Tao with Claude
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def parse_experiment_design_log(log_path: str) -> Dict:
    """
    Parse a Phase 5 experiment design log to extract experiment details.

    Returns dict with:
        - hypothesis_name: str
        - mechanism: str
        - design_type: str
        - base_case: str
        - iteration: int
        - calibration_round: int
        - experiments: List[Dict] with name, param_file, modifications
    """
    text = Path(log_path).read_text()

    # --- Extract metadata from JSON blocks ---
    metadata = {}
    iteration_context = {}
    for block in re.findall(r'```json\s*\n(.*?)\n```', text, re.DOTALL):
        try:
            parsed = json.loads(block)
            if 'n_experiments' in parsed and 'base_case' in parsed:
                metadata = parsed
            if 'calibration_round' in parsed and 'phase_name' in parsed:
                iteration_context = parsed
        except json.JSONDecodeError:
            continue

    # --- Extract hypothesis info ---
    hypothesis_name = ""
    mechanism = ""
    design_type = "cumulative"
    base_case = ""

    m = re.search(r'\*\*Name:\*\*\s*(.+)', text)
    if m:
        hypothesis_name = m.group(1).strip()
    m = re.search(r'\*\*Mechanism:\*\*\s*(.+)', text)
    if m:
        mechanism = m.group(1).strip()
    m = re.search(r'\*\*Design:\*\*\s*(.+)', text)
    if m:
        design_type = m.group(1).strip()
    m = re.search(r'\*\*Base Case:\*\*\s*(.+)', text)
    if m:
        base_case = m.group(1).strip()

    # --- Extract per-experiment details ---
    experiments = []
    # Split by ### experiment headers
    exp_sections = re.split(r'### (c\d+_exp\d+)', text)
    # exp_sections: ['preamble', 'c0_exp1', 'content1', 'c0_exp2', 'content2', ...]
    for i in range(1, len(exp_sections), 2):
        exp_name = exp_sections[i]
        exp_content = exp_sections[i + 1] if i + 1 < len(exp_sections) else ""

        # Extract parameter file
        param_file = ""
        m = re.search(r'\*\*Parameter file:\*\*\s*`([^`]+)`', exp_content)
        if m:
            param_file = m.group(1)

        # Extract modifications from table
        modifications = []
        # Table format: | `param_name` | PFT | Old Value | New Value | Change |
        for row in re.finditer(
            r'\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\|]+)\|',
            exp_content
        ):
            param_name = row.group(1).strip()
            pft = int(row.group(2).strip())
            old_val_str = row.group(3).strip()
            new_val_str = row.group(4).strip()

            try:
                old_value = float(old_val_str)
            except ValueError:
                old_value = old_val_str
            try:
                new_value = float(new_val_str)
            except ValueError:
                new_value = new_val_str

            modifications.append({
                "parameter": param_name,
                "pft": pft,
                "old_value": old_value,
                "new_value": new_value,
            })

        experiments.append({
            "name": exp_name,
            "param_file": param_file,
            "modifications": modifications,
        })

    iteration = metadata.get('iteration', iteration_context.get('iteration', 1))
    calibration_round = iteration_context.get('calibration_round', 1)

    return {
        "hypothesis_name": hypothesis_name,
        "mechanism": mechanism,
        "design_type": design_type,
        "base_case": base_case,
        "iteration": iteration,
        "calibration_round": calibration_round,
        "session_id": iteration_context.get('session_id', ''),
        "experiments": experiments,
    }


def build_experiment_entries(
    parsed: Dict,
    case_name_pattern: Optional[str] = None,
) -> List[Dict]:
    """
    Build experiment dicts matching the structure expected by state['experiments'].

    Each entry mirrors what orchestrator._run_testing() would produce.
    """
    base_case = parsed["base_case"]
    hypothesis_name = parsed["hypothesis_name"]
    iteration = parsed["iteration"]

    entries = []
    for exp in parsed["experiments"]:
        # Build case name: e.g., Kougarok_ELM-FATES_PtCNPEn322_c0_exp1
        case_id = f"{base_case}_{exp['name']}"
        case_name = ""
        if case_name_pattern:
            case_name = case_name_pattern.format(N=case_id, PHASE='TRANS')

        entry = {
            "name": exp["name"],
            "base_case": base_case,
            "hypothesis": hypothesis_name,
            "modifications": exp["modifications"],
            "iteration": iteration,
            "param_file": exp.get("param_file", ""),
            "case_name": case_name,
            "status": "completed",
            "job_status": "COMPLETED",
            "submission_status": "submitted",
            "extraction_status": "pending",
            "results": {},
        }
        entries.append(entry)

    return entries


def evaluate_experiments_in_state(
    state_file: str,
    dry_run: bool = False,
) -> None:
    """
    Evaluate extracted NC files for experiments with pending results.

    Finds experiments in state with extraction_status="pending" or empty
    results, locates their extracted NC files, and runs evaluate_case()
    to populate targets_met, composite_cost, per_target metrics, etc.

    Requires numpy/netCDF4 (runs on HPC where these are available).
    """
    import os
    from pathlib import Path

    with open(state_file, 'r') as f:
        state = json.load(f)

    experiments = state.get("experiments", [])
    if not experiments:
        print("  No experiments in state file")
        return

    # Find experiments needing evaluation
    pending = [
        e for e in experiments
        if e.get("extraction_status") == "pending"
        or (e.get("status") == "completed" and not e.get("results"))
    ]
    if not pending:
        print("  No experiments need evaluation (all already have results)")
        return

    print(f"\n  Found {len(pending)} experiments needing evaluation")

    # Load evaluation tools
    from tools.evaluate_case import evaluate_case, find_extracted_nc

    # Load validation targets
    targets = None
    try:
        from phases.phase2_screening.screen_ensemble import load_kougarok_targets
        targets = load_kougarok_targets()
    except ImportError:
        pass

    if not targets:
        print("  ERROR: Could not load validation targets")
        return

    # Build search directories for NC files
    search_dirs = []
    try:
        from tools.config import config as a2mc_config
        extracted_dir = Path(a2mc_config.EXTRACTED_DATA)
        if extracted_dir.exists():
            search_dirs.append(extracted_dir)
    except (ImportError, AttributeError):
        pass
    output_root = os.environ.get("A2MC_OUTPUT_ROOT", "")
    if output_root:
        search_dirs.append(Path(output_root))

    if not search_dirs:
        print("  ERROR: No search directories configured for NC files.")
        print("  Set A2MC_EXTRACTED_DATA or source a2mc_config.sh + site config")
        return

    print(f"  Searching for NC files in: {[str(d) for d in search_dirs]}")

    # Compute obs index
    year_start = 1901
    obs_year = int(os.environ.get('A2MC_OBS_YEAR', '2016'))
    obs_month = int(os.environ.get('A2MC_OBS_MONTH', '7'))
    obs_idx = (obs_year - year_start) * 12 + obs_month - 1

    # Evaluate each pending experiment
    n_evaluated = 0
    n_not_found = 0
    for exp in pending:
        case_name = exp.get("case_name", "")
        name = exp.get("name", "unknown")

        if not case_name:
            print(f"    {name}: SKIP (no case_name)")
            continue

        nc_file = find_extracted_nc(case_name, search_dirs)
        if nc_file is None:
            print(f"    {name}: NC file not found for {case_name}")
            n_not_found += 1
            continue

        print(f"    {name}: evaluating {nc_file.name}...")
        results = evaluate_case(nc_file, targets, obs_idx)

        exp["results"] = results
        exp["extraction_status"] = "extracted"
        n_met = results.get("targets_met", 0)
        n_total = results.get("total_targets", 0)
        cost = results.get("composite_cost", float("inf"))
        print(f"      -> {n_met}/{n_total} targets met, RMSRE={cost:.4f}")

        # Print per-target details
        for tname, m in results.get("per_target", {}).items():
            status = "OK" if m.get("within_20pct") else "MISS"
            print(f"         {tname}: sim={m['simulated']:.1f} obs={m['observed']:.1f} "
                  f"RE={m['relative_error']:.3f} [{status}]")
        n_evaluated += 1

    print(f"\n  Evaluated: {n_evaluated}/{len(pending)}")
    if n_not_found > 0:
        print(f"  Not found: {n_not_found} (run extract_monthly_variables_FATES.py first)")

    if n_evaluated == 0:
        print("  No experiments evaluated — state file unchanged")
        return

    if dry_run:
        print(f"\n  [DRY RUN] Would update {n_evaluated} experiment results in state")
        return

    # Save updated state
    state["updated_at"] = datetime.now().isoformat()
    backup_path = state_file + ".bak"
    shutil.copy2(state_file, backup_path)
    print(f"  Backup saved: {backup_path}")

    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)
    print(f"  State file updated with evaluation results: {state_file}")


def find_latest_experiment_log(use_cases_dir: str = "use_cases") -> Optional[str]:
    """Auto-detect the most recent Phase 5 experiment design log."""
    pattern = "**/memory/logs/phase5_testing/*_Experiment_Design.md"
    logs = sorted(Path(use_cases_dir).glob(pattern), key=lambda p: p.stat().st_mtime)
    return str(logs[-1]) if logs else None


def populate_state(
    state_file: str,
    experiment_entries: List[Dict],
    target_phase: str = "refinement",
    dry_run: bool = False,
) -> Dict:
    """
    Inject experiment entries into workflow state and set phase to refinement.

    Returns the modified state dict.
    """
    with open(state_file, 'r') as f:
        state = json.load(f)

    # Check for duplicates
    existing_names = {e.get("name") for e in state.get("experiments", [])}
    new_entries = [e for e in experiment_entries if e["name"] not in existing_names]
    skipped = len(experiment_entries) - len(new_entries)

    if skipped > 0:
        print(f"  Skipping {skipped} experiments already in state")

    # Add experiments
    if "experiments" not in state:
        state["experiments"] = []
    state["experiments"].extend(new_entries)

    # Set phase to refinement
    old_phase = state.get("current_phase", "unknown")
    state["current_phase"] = target_phase

    # Record phase transition
    if "phase_history" not in state:
        state["phase_history"] = []
    state["phase_history"].append({
        "timestamp": datetime.now().isoformat(),
        "iteration": state.get("iteration", 1),
        "from": old_phase,
        "to": target_phase,
        "reason": f"Manual: populated {len(new_entries)} experiments via populate_experiments.py"
    })

    state["updated_at"] = datetime.now().isoformat()

    if not dry_run:
        # Backup
        backup_path = state_file + ".bak"
        shutil.copy2(state_file, backup_path)
        print(f"  Backup saved: {backup_path}")

        # Write
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
        print(f"  State file updated: {state_file}")

    return state


def main():
    parser = argparse.ArgumentParser(
        description="Populate experiment entries into workflow state for Phase 6 resume")
    parser.add_argument('--state-file', type=str, required=True,
                        help='Path to workflow_state.json')
    parser.add_argument('--log-file', type=str, default=None,
                        help='Path to Phase 5 experiment design log (auto-detects if omitted)')
    parser.add_argument('--evaluate', action='store_true',
                        help='Evaluate extracted NC files and populate results in state')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying state file')
    args = parser.parse_args()

    if not Path(args.state_file).exists():
        print(f"ERROR: State file not found: {args.state_file}")
        sys.exit(1)

    # --- Mode 1: Evaluate existing experiments ---
    if args.evaluate:
        print(f"\nEvaluating experiments in: {args.state_file}")
        evaluate_experiments_in_state(
            state_file=args.state_file,
            dry_run=args.dry_run,
        )
        if not args.dry_run:
            print(f"\nNext steps:")
            print(f"  1. (Optional) Plot comparison:")
            print(f"     python phases/phase6_refinement/plot_experiment_comparison.py --baseline <BASE> --experiments <CASES>")
            print(f"  2. Resume workflow:")
            print(f"     python orchestrator.py --resume")
        return

    # --- Mode 2: Populate entries from experiment design log ---
    log_file = args.log_file
    if not log_file:
        log_file = find_latest_experiment_log()
        if not log_file:
            print("ERROR: No experiment design log found. Use --log-file to specify.")
            sys.exit(1)
        print(f"Auto-detected log: {log_file}")

    if not Path(log_file).exists():
        print(f"ERROR: Log file not found: {log_file}")
        sys.exit(1)

    # Parse log
    print(f"\nParsing experiment design log: {log_file}")
    parsed = parse_experiment_design_log(log_file)

    print(f"  Hypothesis: {parsed['hypothesis_name']}")
    print(f"  Base case: {parsed['base_case']}")
    print(f"  Design: {parsed['design_type']}")
    print(f"  Iteration: {parsed['iteration']}")
    print(f"  Experiments: {len(parsed['experiments'])}")

    # Get case name pattern
    case_name_pattern = None
    try:
        import os
        os.environ.setdefault('A2MC_DIR', str(Path(__file__).resolve().parent.parent))
        from tools.config import config as a2mc_config
        case_name_pattern = a2mc_config.CASE_NAME_PATTERN
    except (ImportError, AttributeError):
        import os
        case_name_pattern = os.environ.get('A2MC_CASE_NAME_PATTERN', '')

    # Build experiment entries
    entries = build_experiment_entries(parsed, case_name_pattern=case_name_pattern)

    # Display experiments
    print(f"\nExperiment entries to add:")
    for entry in entries:
        n_mods = len(entry['modifications'])
        print(f"  {entry['name']}: {n_mods} modification(s), param_file={entry['param_file']}")
        for mod in entry['modifications']:
            print(f"    {mod['parameter']} (PFT{mod['pft']}): {mod['old_value']} -> {mod['new_value']}")

    if args.dry_run:
        print(f"\n[DRY RUN] Would add {len(entries)} experiments and set phase to 'refinement'")
        print("[DRY RUN] No changes made.")
    else:
        print(f"\nPopulating state file...")
        populate_state(
            state_file=args.state_file,
            experiment_entries=entries,
            target_phase="refinement",
            dry_run=False,
        )

    # Print next steps
    base = parsed['base_case']
    exp_names = [e['name'] for e in entries]
    case_ids = [f"{base}_{name}" for name in exp_names]
    cases_str = " ".join(case_ids)

    print(f"\nNext steps on Perlmutter:")
    print(f"  1. Extract simulation outputs:")
    print(f"     python tools/extract_monthly_variables_FATES.py --cases {cases_str}")
    print(f"  2. Evaluate results and update state:")
    print(f"     python tools/populate_experiments.py --state-file {args.state_file} --evaluate")
    print(f"  3. (Optional) Plot comparison:")
    print(f"     python phases/phase6_refinement/plot_experiment_comparison.py --baseline {base} --experiments {cases_str}")
    print(f"  4. Resume workflow:")
    print(f"     python orchestrator.py --resume")


if __name__ == '__main__':
    main()
