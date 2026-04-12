#!/usr/bin/env python3
"""
Create FATES Parameter Files for Subset Replay

A subset replay is a controlled experiment that takes the top-N cases from a
previous calibration round, applies a global parameter override (e.g.,
fates_cnp_prescribed_puptake=1.0), and reruns them. Used for mechanistic
hypothesis tests like "does removing P limitation rescue PFT10?"

Unlike create_morris_ensemble.py, this script does NOT recompute parameters
from a Morris matrix. It copies the existing source parameter files and
modifies only the override fields in place — symmetric with how Phase 5
modifies parameters for individual experiments.

Configuration (environment variables):

  Source (where to read top-N cases from):
    A2MC_REPLAY_SOURCE_STATE         Source workflow_state JSON file (must
                                     contain screening_data.ranked_cases)
    A2MC_REPLAY_SOURCE_PARAM_DIR     Directory with source NC parameter files
    A2MC_REPLAY_SOURCE_PARAM_PATTERN Filename pattern for source files,
                                     with {N} placeholder for case number
                                     (e.g., "fates_params_api25.5.0_12pft_c230710__PtCNP162_En{N}.nc")
    A2MC_REPLAY_TOP_N                Number of top cases to replay (default 200)
    A2MC_REPLAY_OVERRIDES            Comma-separated param=value list, e.g.,
                                     "fates_cnp_prescribed_puptake=1.0,foo=2.0"

  Destination (R4 settings, set by source-ing the R4 config):
    A2MC_PARAM_DIR                   Where to write new NC parameter files
    A2MC_PARAM_PATTERN               Filename pattern for new files (with {N})
    A2MC_ENSEMBLE_OUTPUT             Where to write the manifest file

  Optional:
    A2MC_REPLAY_RANKING_METRIC       Field to sort by (default 'composite_nrmse')

Outputs:
  - {A2MC_PARAM_DIR}/<filename>.nc          One NetCDF per replayed case
  - {A2MC_ENSEMBLE_OUTPUT}/subset_replay_manifest.json   Mapping new→source

Usage:
  source a2mc_config.sh
  source use_cases/Kougarok/config/kougarok_config_r4.sh
  python phases/phase0_design/create_subset_replay.py

After this completes:
  ./tools/submit_ensemble.sh --start 1 --end 200 --submit --reuse-build 1

Author: Jing Tao with Claude
Created: April 10, 2026
"""

import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import netCDF4 as nc
except ImportError:
    print("ERROR: netCDF4 not available. Install with: pip install netCDF4")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


# ============================================================================
# Helpers
# ============================================================================

def parse_overrides(overrides_str: str) -> Dict[str, float]:
    """Parse comma-separated 'param=value' pairs into a dict.

    Example:
        "fates_cnp_prescribed_puptake=1.0,foo=2.5"
        → {"fates_cnp_prescribed_puptake": 1.0, "foo": 2.5}
    """
    result = {}
    if not overrides_str:
        return result
    for token in overrides_str.split(','):
        token = token.strip()
        if not token:
            continue
        if '=' not in token:
            logger.warning(f"Skipping malformed override (no '='): {token}")
            continue
        key, val = token.split('=', 1)
        key = key.strip()
        try:
            val_float = float(val.strip())
        except ValueError:
            logger.warning(f"Skipping override with non-numeric value: {token}")
            continue
        result[key] = val_float
    return result


def load_source_state(state_path: Path) -> Tuple[Dict, List[Dict]]:
    """Load workflow state JSON and extract ranked_cases.

    Returns:
        (state_data, ranked_cases) — ranked_cases is a list of dicts with
        at least 'case_num' and a ranking metric field
    """
    with open(state_path) as f:
        state = json.load(f)

    sd = state.get('screening_data', {})
    ranked = sd.get('ranked_cases', [])
    if not ranked:
        # Fallback: use best_cases (top 10 with full per-target detail)
        ranked = sd.get('best_cases', [])
        if ranked:
            logger.warning(f"State has no 'ranked_cases', falling back to "
                           f"'best_cases' ({len(ranked)} cases)")

    return state, ranked


def build_source_filename(pattern: str, case_num: int) -> str:
    """Build source param filename from pattern and case number.

    Pattern can use {N} placeholder. If pattern doesn't contain {N},
    raises ValueError.
    """
    if '{N}' not in pattern:
        raise ValueError(f"Source pattern must contain {{N}} placeholder, "
                         f"got: {pattern}")
    return pattern.format(N=case_num)


def build_dst_filename(pattern: str, new_case_num: int) -> str:
    """Build destination param filename from pattern and new case number."""
    if '{N}' not in pattern:
        raise ValueError(f"Destination pattern must contain {{N}} placeholder, "
                         f"got: {pattern}")
    return pattern.format(N=new_case_num)


def apply_overrides_in_place(nc_file: Path, overrides: Dict[str, float]) -> List[str]:
    """Open the NetCDF file in r+ mode and apply each override.

    Returns:
        List of override messages for logging.
    """
    messages = []
    with nc.Dataset(str(nc_file), 'r+') as ds:
        for param_name, value in overrides.items():
            if param_name not in ds.variables:
                logger.warning(f"  Override target '{param_name}' not in {nc_file.name} — skipped")
                continue
            old_value = ds.variables[param_name][:].copy()
            ds.variables[param_name][:] = value
            messages.append(f"{param_name}: {old_value.flatten()[0]} → {value}")
    return messages


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    # ----- Read configuration from env vars -----
    source_state_str = os.environ.get('A2MC_REPLAY_SOURCE_STATE', '')
    source_param_dir_str = os.environ.get('A2MC_REPLAY_SOURCE_PARAM_DIR', '')
    source_pattern = os.environ.get('A2MC_REPLAY_SOURCE_PARAM_PATTERN', '')
    top_n = int(os.environ.get('A2MC_REPLAY_TOP_N', '200'))
    overrides_str = os.environ.get('A2MC_REPLAY_OVERRIDES', '')
    ranking_metric = os.environ.get('A2MC_REPLAY_RANKING_METRIC', 'composite_nrmse')

    dst_param_dir_str = os.environ.get('A2MC_PARAM_DIR', '')
    dst_pattern = os.environ.get('A2MC_PARAM_PATTERN', '')
    dst_ensemble_output_str = os.environ.get('A2MC_ENSEMBLE_OUTPUT', '')

    # ----- Validate -----
    missing = []
    for var, val in [
        ('A2MC_REPLAY_SOURCE_STATE', source_state_str),
        ('A2MC_REPLAY_SOURCE_PARAM_DIR', source_param_dir_str),
        ('A2MC_REPLAY_SOURCE_PARAM_PATTERN', source_pattern),
        ('A2MC_PARAM_DIR', dst_param_dir_str),
        ('A2MC_PARAM_PATTERN', dst_pattern),
        ('A2MC_ENSEMBLE_OUTPUT', dst_ensemble_output_str),
    ]:
        if not val:
            missing.append(var)
    if missing:
        logger.error("Missing required environment variables:")
        for v in missing:
            logger.error(f"  {v}")
        logger.error("Please source the round-specific config file first, e.g.:")
        logger.error("  source use_cases/Kougarok/config/kougarok_config_r4.sh")
        return 1

    source_state = Path(source_state_str)
    source_param_dir = Path(source_param_dir_str)
    dst_param_dir = Path(dst_param_dir_str)
    dst_ensemble_output = Path(dst_ensemble_output_str)

    if not source_state.exists():
        logger.error(f"Source state file not found: {source_state}")
        return 1
    if not source_param_dir.exists():
        logger.error(f"Source param dir not found: {source_param_dir}")
        return 1

    overrides = parse_overrides(overrides_str)
    if not overrides:
        logger.warning("No overrides parsed — replay will be a pure copy "
                       "(useful only for testing the pipeline)")

    # ----- Banner -----
    logger.info("=" * 70)
    logger.info("SUBSET REPLAY: parameter file generation")
    logger.info("=" * 70)
    logger.info(f"Source state:    {source_state}")
    logger.info(f"Source params:   {source_param_dir}")
    logger.info(f"Source pattern:  {source_pattern}")
    logger.info(f"Top N:           {top_n}")
    logger.info(f"Ranking metric:  {ranking_metric}")
    logger.info(f"Overrides:       {overrides}")
    logger.info(f"Dst params:      {dst_param_dir}")
    logger.info(f"Dst pattern:     {dst_pattern}")
    logger.info("=" * 70)

    # ----- Load source ranked_cases -----
    state_data, ranked_cases = load_source_state(source_state)
    if not ranked_cases:
        logger.error("Source state has no ranked_cases or best_cases — cannot proceed")
        return 1

    if len(ranked_cases) < top_n:
        logger.warning(f"Source has only {len(ranked_cases)} ranked cases, "
                       f"requested top {top_n}. Will use all {len(ranked_cases)}.")
        top_n = len(ranked_cases)

    selected = ranked_cases[:top_n]
    logger.info(f"Loaded {len(ranked_cases)} ranked cases from source state, "
                f"selecting top {top_n}")

    source_round = state_data.get('calibration_round')
    source_session_id = ''
    # Try to extract session id from state file name (e.g., workflow_state_s0409h20m58.json)
    name = source_state.name
    if 'workflow_state_' in name:
        source_session_id = name.replace('workflow_state_', '').replace('.json', '')

    # ----- Create destination directory -----
    dst_param_dir.mkdir(parents=True, exist_ok=True)
    dst_ensemble_output.mkdir(parents=True, exist_ok=True)
    logger.info(f"Destination directories ready")

    # ----- Process each case -----
    manifest_entries = []
    n_success = 0
    n_failed = 0

    for rank, case_info in enumerate(selected, start=1):
        # Source file
        src_case_num = case_info.get('case_num', case_info.get('case_id'))
        if src_case_num is None:
            logger.warning(f"Rank {rank}: no case_num/case_id field, skipping")
            n_failed += 1
            continue

        try:
            src_filename = build_source_filename(source_pattern, src_case_num)
            src_path = source_param_dir / src_filename

            if not src_path.exists():
                logger.error(f"Rank {rank}: source file not found: {src_path}")
                n_failed += 1
                continue

            # Destination file: KEEP THE SAME CASE NUMBER as the source.
            # This preserves traceability — R4 case 86 corresponds to R3 case 86
            # (same parameter values, same case number, same filename — only
            # differs by directory and the override applied in place).
            dst_filename = build_dst_filename(dst_pattern, src_case_num)
            dst_path = dst_param_dir / dst_filename

            # Copy
            shutil.copy2(src_path, dst_path)

            # Apply overrides in place
            messages = apply_overrides_in_place(dst_path, overrides)

            # Manifest entry
            manifest_entries.append({
                'new_case_num': src_case_num,
                'source_case_num': src_case_num,
                'source_rank': rank,
                'source_cost': case_info.get(ranking_metric, case_info.get('cost')),
                'source_n_satisfied': case_info.get('n_satisfied'),
                'source_filename': src_filename,
                'dst_filename': dst_filename,
                'overrides_applied': messages,
            })

            n_success += 1
            if rank <= 5 or rank % 50 == 0 or rank == top_n:
                logger.info(f"  [{rank}/{top_n}] {src_filename} → {dst_filename} "
                            f"({len(messages)} override(s))")

        except Exception as e:
            logger.error(f"Rank {rank} (source case {src_case_num}): {e}")
            n_failed += 1
            continue

    # ----- Write manifest -----
    manifest = {
        'source_round': source_round,
        'source_state_file': source_state.name,
        'source_session_id': source_session_id,
        'source_param_dir': str(source_param_dir),
        'source_param_pattern': source_pattern,
        'top_n_requested': top_n,
        'top_n_actual': n_success,
        'ranking_metric': ranking_metric,
        'overrides': overrides,
        'destination_param_dir': str(dst_param_dir),
        'destination_param_pattern': dst_pattern,
        'case_numbering': 'preserved',  # new cases keep source case numbers (NOT renumbered 1..N)
        'created_at': datetime.now().isoformat(),
        'case_mapping': manifest_entries,
    }
    manifest_path = dst_ensemble_output / 'subset_replay_manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # ----- Write case list file (for submit_ensemble.sh --cases-file mode) -----
    # Since case numbers are non-sequential (R3 ranks → preserved as R4 case numbers),
    # submit_ensemble.sh needs the explicit list to iterate through.
    case_list_path = dst_ensemble_output / 'subset_replay_case_list.txt'
    with open(case_list_path, 'w') as f:
        f.write("# Case list for subset_replay round\n")
        f.write(f"# Generated: {datetime.now().isoformat()}\n")
        f.write(f"# Source: round {source_round}, top {n_success} cases by {ranking_metric}\n")
        f.write(f"# Overrides: {overrides}\n")
        f.write(f"# Use with: ./tools/submit_ensemble.sh --cases-file {case_list_path.name} --submit\n")
        f.write("#\n")
        f.write("# One case number per line. Case numbers match the source round\n")
        f.write("# (e.g., '86' here corresponds to source case 86 with the override applied).\n")
        for entry in manifest_entries:
            f.write(f"{entry['new_case_num']}\n")

    logger.info("=" * 70)
    logger.info(f"SUMMARY: {n_success}/{top_n} successful, {n_failed} failed")
    logger.info(f"Manifest written:  {manifest_path}")
    logger.info(f"Case list written: {case_list_path}")
    logger.info("=" * 70)

    if n_success == 0:
        logger.error("No files created — check source paths and patterns")
        return 1

    logger.info("Next steps (template-based submission with parallel bundles):")
    logger.info("")
    logger.info(f"  1. Adapt your existing R3 case template script for R4:")
    logger.info(f"     - Point at the R4 PARAM_DIR for parameter files")
    logger.info(f"     - Use R4 case_name_pattern (PtCNPEn{{N}}PrescP)")
    logger.info(f"     - Set EXEROOT directly to R3 case 1's bld:")
    logger.info(f"         EXEROOT=\\${{CIME_OUTPUT_ROOT}}/Kougarok_ELM-FATES_PtCNPEn1_\\${{PHASE}}/bld")
    logger.info(f"     - This reuses R3's existing build — no need to rebuild for R4")
    logger.info("")
    logger.info(f"  2. Loop over the {n_success} cases in {case_list_path.name},")
    logger.info(f"     copying + sed-parameterizing the template, submitting in parallel bundles")
    logger.info(f"     (e.g., 20 cases in parallel, wait, next bundle).")
    logger.info("")
    logger.info(f"     Case list format: one case number per line, comments stripped.")
    logger.info(f"     Top 5 cases: {[e['new_case_num'] for e in manifest_entries[:5]]}")
    logger.info("")
    logger.info(f"  3. Once HPC simulations complete:")
    logger.info(f"     python tools/diagnose_ensemble_status.py")

    return 0 if n_failed == 0 else 2  # 2 = partial success


if __name__ == "__main__":
    sys.exit(main())
