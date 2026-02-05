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
import sys
from pathlib import Path
from typing import Dict, List

# Add project root to path for tool imports
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from tools.modify_fates_parameters import create_modified_parameter_file, verify_modifications

logger = logging.getLogger(__name__)


def create_experiment_param_files(
    experiments: List[Dict],
    base_param_file: str,
    output_dir: str,
    verify: bool = True
) -> List[Dict]:
    """
    Create modified parameter files for each experiment.

    For each experiment:
    1. Copy base param file to output_dir with experiment-specific name
    2. Apply modifications via modify_fates_parameters.create_modified_parameter_file()
    3. Optionally verify via modify_fates_parameters.verify_modifications()
    4. Return updated experiment dicts with param_file paths

    Args:
        experiments: List of experiment dicts. Each must have:
            - 'name': str - Experiment name (used in output filename)
            - 'modifications': list of dicts with keys:
                - 'parameter': str - FATES parameter name
                - 'new_value': float - New value to set
                - 'old_value': float (optional) - Previous value for logging
                - 'pft': int (optional, default 0) - PFT index (1-based, 0=global)
                - 'organ': int (optional) - Organ index for 2D params
        base_param_file: Path to base FATES parameter file (.nc)
        output_dir: Directory for output parameter files
        verify: Run verification after creation (default True)

    Returns:
        Updated experiment dicts with added fields:
            - 'param_file': str - Path to created parameter file
            - 'verified': bool - Whether verification passed (if verify=True)
            - 'param_status': str - 'created', 'creation_failed', etc.
    """
    base_path = Path(base_param_file)
    out_dir = Path(output_dir)

    if not base_path.exists():
        raise FileNotFoundError(f"Base parameter file not found: {base_param_file}")

    out_dir.mkdir(parents=True, exist_ok=True)

    updated_experiments = []

    for exp in experiments:
        exp = dict(exp)  # Don't modify the original
        name = exp.get("name", "unnamed")
        modifications = exp.get("modifications", [])

        if not modifications:
            logger.warning(f"Experiment '{name}' has no modifications, skipping.")
            exp["param_status"] = "no_modifications"
            updated_experiments.append(exp)
            continue

        # Build output filename
        output_file = out_dir / f"fates_params_{name}.nc"

        try:
            # Convert experiment modification format to tool format
            # Tool expects: {'param', 'pft', 'value'/'percent', 'organ'}
            tool_modifications = []
            for mod in modifications:
                tool_mod = {
                    "param": mod["parameter"],
                    "pft": mod.get("pft", 0),
                    "value": mod["new_value"],
                }
                if "organ" in mod:
                    tool_mod["organ"] = mod["organ"]
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
                for mod, result in zip(modifications, results):
                    expected.append({
                        "param": mod["parameter"],
                        "pft": mod.get("pft", 0),
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
