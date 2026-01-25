#!/usr/bin/env python3
"""
Seed A2MC Memory from User-Curated YAML File

This script converts a user-provided YAML file with curated discoveries
and failed experiments into the JSON format used by the memory system.

Usage:
    python seed_memory_from_yaml.py --input curated_knowledge.yaml --output ../memory/data

The YAML file should follow this structure:

    discoveries:
      - name: allocation_paradox
        description: "..."
        mechanism: "..."
        affects: [froot_pft10, leaf_pft10]
        parameters_involved: [fates_cnp_vmax_p, fates_cnp_pid_kp]
        implications: ["Do not...", "Consider..."]
        do_not_repeat: ["vmax_p x 10"]
        confidence: 0.95

    failed_experiments:
      - id: test3a_vmax_p_10x
        base_case: "2678"
        hypothesis: "Increase P uptake"
        modifications:
          - parameter: fates_cnp_vmax_p_10
            old_value: 5e-06
            new_value: 5e-05
        outcome: catastrophic_collapse
        lesson: "Triggers allocation paradox"
        repeat_warning: "CATASTROPHIC"

    failed_approaches:
      - approach: "Increase vmax_p 10x for single PFT"
        experiment_id: test3a_vmax_p_10x
        why_failed: "Triggers allocation paradox via PID controller"
        severity: catastrophic
        alternatives: ["Increase vmax_p moderately (2-3x)"]
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

try:
    import yaml
except ImportError:
    print("Error: PyYAML required. Install with: pip install pyyaml")
    sys.exit(1)


def load_yaml(filepath: str) -> dict:
    """Load YAML file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def convert_discoveries(yaml_discoveries: list) -> dict:
    """Convert YAML discoveries to JSON format."""
    discoveries = {}

    for disc in yaml_discoveries:
        name = disc.pop("name")

        # Set defaults for curated entries
        discoveries[name] = {
            "source": "curated",
            "confidence": disc.get("confidence", 0.90),
            "verified": True,
            "date_added": datetime.now().isoformat(),
            "date_discovered": disc.get("date_discovered"),
            "description": disc.get("description", ""),
            "mechanism": disc.get("mechanism", ""),
            "affects": disc.get("affects", []),
            "implications": disc.get("implications", []),
            "parameters_involved": disc.get("parameters_involved", []),
            "do_not_repeat": disc.get("do_not_repeat", []),
            "references": disc.get("references", [])
        }

    return discoveries


def convert_experiments(yaml_experiments: list) -> dict:
    """Convert YAML experiments to JSON format."""
    experiments = {"experiments": []}

    for exp in yaml_experiments:
        record = {
            "id": exp.get("id", f"exp_{len(experiments['experiments'])}"),
            "source": "curated",
            "date": exp.get("date", datetime.now().isoformat()),
            "base_case": exp.get("base_case"),
            "hypothesis": exp.get("hypothesis"),
            "modifications": exp.get("modifications", []),
            "results": exp.get("results", {}),
            "outcome": exp.get("outcome", "FAILED"),
            "lesson": exp.get("lesson"),
            "do_not_repeat": exp.get("outcome") in ["FAILED", "catastrophic_collapse"],
            "repeat_warning": exp.get("repeat_warning")
        }
        experiments["experiments"].append(record)

    return experiments


def convert_failed_approaches(yaml_approaches: list) -> dict:
    """Convert YAML failed approaches to JSON format."""
    approaches = {"failed_approaches": []}

    for fa in yaml_approaches:
        record = {
            "approach": fa.get("approach", ""),
            "experiment_id": fa.get("experiment_id"),
            "why_failed": fa.get("why_failed", ""),
            "severity": fa.get("severity", "catastrophic"),
            "alternatives": fa.get("alternatives", []),
            "date_added": datetime.now().isoformat()
        }
        approaches["failed_approaches"].append(record)

    return approaches


def save_json(filepath: str, data: dict) -> None:
    """Save data to JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Seed A2MC memory from curated YAML file"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input YAML file with curated knowledge"
    )
    parser.add_argument(
        "--output", "-o",
        default="../memory/data",
        help="Path to output directory (default: ../memory/data)"
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge with existing data instead of overwriting"
    )

    args = parser.parse_args()

    # Resolve paths
    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load YAML
    print(f"Loading: {input_path}")
    curated = load_yaml(str(input_path))

    # Convert and save discoveries
    if "discoveries" in curated:
        discoveries = convert_discoveries(curated["discoveries"])
        print(f"  Converted {len(discoveries)} discoveries")

        if args.merge and (output_dir / "discoveries.json").exists():
            existing = json.load(open(output_dir / "discoveries.json"))
            # Remove metadata keys
            existing = {k: v for k, v in existing.items() if not k.startswith("_")}
            existing.update(discoveries)
            discoveries = existing

        save_json(output_dir / "discoveries.json", discoveries)

    # Convert and save experiments
    if "failed_experiments" in curated:
        experiments = convert_experiments(curated["failed_experiments"])
        print(f"  Converted {len(experiments['experiments'])} experiments")

        if args.merge and (output_dir / "experiments.json").exists():
            existing = json.load(open(output_dir / "experiments.json"))
            existing_ids = {e["id"] for e in existing.get("experiments", [])}
            for exp in experiments["experiments"]:
                if exp["id"] not in existing_ids:
                    existing["experiments"].append(exp)
            experiments = existing

        save_json(output_dir / "experiments.json", experiments)

    # Convert and save failed approaches
    if "failed_approaches" in curated:
        approaches = convert_failed_approaches(curated["failed_approaches"])
        print(f"  Converted {len(approaches['failed_approaches'])} failed approaches")

        if args.merge and (output_dir / "failed_approaches.json").exists():
            existing = json.load(open(output_dir / "failed_approaches.json"))
            existing_set = {fa["approach"] for fa in existing.get("failed_approaches", [])}
            for fa in approaches["failed_approaches"]:
                if fa["approach"] not in existing_set:
                    existing["failed_approaches"].append(fa)
            approaches = existing

        save_json(output_dir / "failed_approaches.json", approaches)

    print("\nSeeding complete!")
    print(f"Memory data saved to: {output_dir.absolute()}")


if __name__ == "__main__":
    main()
