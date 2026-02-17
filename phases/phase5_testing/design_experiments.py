#!/usr/bin/env python3
"""
Phase 5: Design Experiments - Create Modified Parameter Files

Creates modified FATES parameter files from experiment specifications.
Each experiment specifies a base parameter file and a set of modifications.

Uses shared tools:
    - tools/modify_fates_parameters.py → create_modified_parameter_file()
    - tools/modify_fates_parameters.py → verify_modifications()

Usage:
    # From Python
    from phases.phase5_testing import create_experiment_param_files
    updated = create_experiment_param_files(experiments, base_param_file, output_dir)

    # From CLI
    python phases/phase5_testing/design_experiments.py \\
        --experiments experiments.json \\
        --base-param-file /path/to/fates_params.nc \\
        --output-dir ./experiments/iter_4/
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path for tool imports
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from tools.modify_fates_parameters import (
    build_param_lookup, resolve_parameter_name,
    create_modified_parameter_file, verify_modifications,
)

logger = logging.getLogger(__name__)


def _resolve_case_param_file(case_id: str, param_dir: str = "",
                             param_pattern: str = "") -> Optional[str]:
    """Resolve the parameter file path for a specific ensemble case.

    Args:
        case_id: Case number (e.g., "2678")
        param_dir: Directory containing ensemble parameter files
        param_pattern: Filename pattern with {N} placeholder

    Returns:
        Path string if found, None otherwise
    """
    if not param_dir or not param_pattern:
        return None

    filename = param_pattern.replace("{N}", str(case_id))
    filepath = Path(param_dir) / filename
    if filepath.exists():
        return str(filepath)
    return None


def create_experiment_param_files(
    experiments: List[Dict],
    output_dir: str,
    verify: bool = True,
    param_dir: str = "",
    param_pattern: str = "",
    **kwargs,
) -> List[Dict]:
    """
    Create modified parameter files for each experiment.

    For each experiment:
    1. Resolve the case-specific parameter file from the ensemble
       (param_dir + param_pattern + base_case). Each experiment MUST
       have a base_case that maps to an existing ensemble parameter file.
    2. Apply modifications via modify_fates_parameters.create_modified_parameter_file()
    3. Optionally verify via modify_fates_parameters.verify_modifications()
    4. Return updated experiment dicts with param_file paths

    Args:
        experiments: List of experiment dicts. Each must have:
            - 'name': str - Experiment name (used in output filename)
            - 'base_case': str - Case ID whose param file to use as base
            - 'modifications': list of dicts with keys:
                - 'parameter': str - FATES parameter name
                - 'new_value': float - New value to set
                - 'old_value': float (optional) - Previous value for logging
                - 'pft': int (optional, default 0) - PFT index (1-based, 0=global)
                - 'organ': int (optional) - Organ index for 2D params
        output_dir: Directory for output parameter files
        verify: Run verification after creation (default True)
        param_dir: Directory with ensemble parameter files (A2MC_PARAM_DIR)
        param_pattern: Filename pattern with {N} placeholder (A2MC_PARAM_PATTERN)

    Returns:
        Updated experiment dicts with added fields:
            - 'param_file': str - Path to created parameter file
            - 'base_param_source': str - Which base file was used (case_XXXX)
            - 'verified': bool - Whether verification passed (if verify=True)
            - 'param_status': str - 'created', 'creation_failed', etc.

    Raises:
        FileNotFoundError: If param_dir/param_pattern not configured or
            case-specific parameter file not found
    """
    if not param_dir or not param_pattern:
        raise FileNotFoundError(
            "A2MC_PARAM_DIR and A2MC_PARAM_PATTERN must be configured. "
            "Experiments must be based on case-specific parameter files, "
            "not the default template."
        )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build parameter name lookup for shorthand → full name resolution
    param_list_file = os.environ.get('A2MC_PARAM_LIST_FILE', '')
    param_lookup = None
    if param_list_file and Path(param_list_file).exists():
        try:
            param_lookup = build_param_lookup(param_list_file)
            logger.info(f"Loaded parameter name lookup: {len(param_lookup)} entries from {Path(param_list_file).name}")
        except Exception as e:
            logger.warning(f"Could not build parameter lookup: {e}. Shorthand names will not be resolved.")
    else:
        logger.warning("A2MC_PARAM_LIST_FILE not set or not found. Shorthand parameter names will not be resolved.")

    updated_experiments = []

    for exp in experiments:
        exp = dict(exp)  # Don't modify the original
        name = exp.get("name", "unnamed")
        modifications = exp.get("modifications", [])
        base_case = exp.get("base_case", "")

        if not base_case:
            raise FileNotFoundError(
                f"Experiment '{name}' has no base_case. "
                f"Each experiment must specify which ensemble case to modify."
            )

        # Resolve case-specific parameter file
        case_file = _resolve_case_param_file(base_case, param_dir, param_pattern)
        if not case_file:
            expected = Path(param_dir) / param_pattern.replace("{N}", str(base_case))
            raise FileNotFoundError(
                f"Case {base_case} parameter file not found: {expected}\n"
                f"  param_dir: {param_dir}\n"
                f"  param_pattern: {param_pattern}"
            )

        base_path = Path(case_file)
        exp["base_param_source"] = f"case_{base_case}"
        logger.info(f"  Using case {base_case} param file: {base_path.name}")

        if not modifications:
            logger.warning(f"Experiment '{name}' has no modifications, skipping.")
            exp["param_status"] = "no_modifications"
            updated_experiments.append(exp)
            continue

        # Build output filename: base name stem + short experiment suffix
        # e.g., fates_params_..._En322.nc → fates_params_..._En322_exp1.nc
        base_stem = base_path.stem  # e.g., fates_params_api25.5.0_..._En322
        output_file = out_dir / f"{base_stem}_{name}.nc"

        try:
            # Convert experiment modification format to tool format
            # Tool expects: {'param', 'pft', 'value'/'percent', 'organ'}
            # Resolve shorthand names (e.g., 'vmax_ptase_10') to full FATES names
            tool_modifications = []
            for mod in modifications:
                raw_name = mod["parameter"]
                explicit_pft = mod.get("pft", None)
                explicit_organ = mod.get("organ", None)

                fates_name, pft, organ = resolve_parameter_name(
                    raw_name, pft=explicit_pft, organ=explicit_organ,
                    param_lookup=param_lookup,
                )

                if raw_name != fates_name:
                    organ_str = f", organ={organ}" if organ is not None else ""
                    logger.info(f"  Resolved '{raw_name}' → '{fates_name}' (PFT={pft}{organ_str})")

                tool_mod = {
                    "param": fates_name,
                    "pft": pft,
                    "value": mod["new_value"],
                }
                if organ is not None:
                    tool_mod["organ"] = organ
                tool_modifications.append(tool_mod)

            # Create modified file
            results = create_modified_parameter_file(
                input_file=str(base_path),
                output_file=str(output_file),
                modifications=tool_modifications,
                verbose=True
            )

            exp["param_file"] = str(output_file)
            exp["param_status"] = "created"
            logger.info(f"Created parameter file for '{name}': {output_file}")

            # Verify if requested
            if verify:
                expected = []
                for tool_mod, result in zip(tool_modifications, results):
                    expected.append({
                        "param": tool_mod["param"],
                        "pft": tool_mod["pft"],
                        "expected_value": result["new_value"]
                    })
                is_correct = verify_modifications(
                    str(output_file), expected, verbose=True
                )
                exp["verified"] = is_correct
                if not is_correct:
                    logger.warning(f"Verification FAILED for '{name}'")
            else:
                exp["verified"] = None

        except Exception as e:
            logger.error(f"Failed to create parameter file for '{name}': {e}")
            exp["param_file"] = None
            exp["param_status"] = "creation_failed"
            exp["error"] = str(e)

        updated_experiments.append(exp)

    # Summary
    created = sum(1 for e in updated_experiments if e.get("param_status") == "created")
    failed = sum(1 for e in updated_experiments if e.get("param_status") == "creation_failed")
    logger.info(f"\nParameter file creation: {created} created, {failed} failed, "
                f"{len(updated_experiments)} total")

    return updated_experiments


def design_experiment_sequence(hypothesis: Dict, screening_data: Dict) -> List[Dict]:
    """Design experiment sequence from hypothesis.

    Builds a list of experiment dicts (cumulative or factorial) from a
    hypothesis specification.  Extracted from orchestrator._design_experiment_sequence().

    Args:
        hypothesis: Hypothesis dict with 'parameters' (or 'parameters_to_test'),
            'design_type' (or 'experimental_design'), 'name', 'expected_outcome'.
        screening_data: Screening results; used to get base_case ID.

    Returns:
        List of experiment dicts, each with: name, hypothesis, base_case,
        modifications, expected_outcome.
    """
    import itertools

    design_type = hypothesis.get("design_type", hypothesis.get("experimental_design", "cumulative"))
    params = hypothesis.get("parameters", hypothesis.get("parameters_to_test", []))
    base_case = screening_data.get("best_case", {}).get("case_id", "2678")

    experiments = []

    if design_type == "cumulative":
        # Cumulative: exp1 = A, exp2 = A+B, exp3 = A+B+C
        cumulative_mods = []
        for i, param in enumerate(params):
            mod = {
                "parameter": param["name"],
                "old_value": param.get("current"),
                "new_value": param.get("proposed"),
            }
            if "pft" in param:
                mod["pft"] = param["pft"]
            if "organ" in param:
                mod["organ"] = param["organ"]
            cumulative_mods.append(mod)
            experiments.append({
                "name": f"exp{i+1}",
                "hypothesis": hypothesis.get('name', 'test'),
                "base_case": base_case,
                "modifications": cumulative_mods.copy(),
                "expected_outcome": hypothesis.get("expected_outcome",
                                                   hypothesis.get("expected_outcomes", ""))
            })

    elif design_type == "factorial":
        # Factorial: All combinations
        for r in range(1, len(params) + 1):
            for combo in itertools.combinations(range(len(params)), r):
                mods = []
                for i in combo:
                    mod = {
                        "parameter": params[i]["name"],
                        "old_value": params[i].get("current"),
                        "new_value": params[i].get("proposed"),
                    }
                    if "pft" in params[i]:
                        mod["pft"] = params[i]["pft"]
                    if "organ" in params[i]:
                        mod["organ"] = params[i]["organ"]
                    mods.append(mod)
                experiments.append({
                    "name": f"exp{len(experiments)+1}",
                    "hypothesis": hypothesis.get('name', 'test'),
                    "base_case": base_case,
                    "modifications": mods,
                    "expected_outcome": hypothesis.get("expected_outcome",
                                                       hypothesis.get("expected_outcomes", ""))
                })

    return experiments


def main():
    parser = argparse.ArgumentParser(
        description="Create modified FATES parameter files from experiment specifications"
    )
    parser.add_argument("--experiments", required=True,
                        help="JSON file with experiment specifications")
    parser.add_argument("--base-param-file", required=True,
                        help="Path to base FATES parameter file (.nc)")
    parser.add_argument("--output-dir", required=True,
                        help="Output directory for parameter files")
    parser.add_argument("--no-verify", action="store_true",
                        help="Skip verification after creation")

    args = parser.parse_args()

    # Load experiments
    with open(args.experiments) as f:
        experiments = json.load(f)

    if not isinstance(experiments, list):
        experiments = [experiments]

    # Create parameter files
    updated = create_experiment_param_files(
        experiments=experiments,
        base_param_file=args.base_param_file,
        output_dir=args.output_dir,
        verify=not args.no_verify
    )

    # Write updated experiments back
    output_file = Path(args.output_dir) / "experiments_with_params.json"
    with open(output_file, "w") as f:
        json.dump(updated, f, indent=2)
    print(f"\nUpdated experiments written to: {output_file}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
