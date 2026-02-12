#!/usr/bin/env python3
"""
Promote a generated diagnostic script to the permanent inventory.

For ensemble-level hypothesis tests (test_*.py with test_hypothesis()):
  Just copies to phases/phase3_diagnosis/ — auto-discovered at runtime.
  No manual inventory or __init__.py edits needed (v2.18+ dynamic dispatch).

For other diagnostic scripts (analyze_*.py, check_*.py, etc.):
  Copies to phases/phase3_diagnosis/ and updates DIAGNOSTIC_TOOLS_INVENTORY
  in reasoning/prompts.py. You also need to manually add imports to __init__.py.

Usage:
    # List available scripts
    python tools/promote_diagnostic_script.py --list

    # Promote an ensemble test (just copies — auto-discovered)
    python tools/promote_diagnostic_script.py --script test_p_cycling_20260212_123456.py

    # Dry-run first
    python tools/promote_diagnostic_script.py --script test_p_cycling_20260212_123456.py --dry-run

    # Promote a non-test script with explicit category
    python tools/promote_diagnostic_script.py --script analyze_water_stress.py \
        --tool-name analyze_water_stress --category "Mortality & Collapse Analysis"

Author: Jing Tao with Claude
Created: February 2026
"""

import re
import sys
import argparse
import shutil
from pathlib import Path


# Paths relative to A2MC root
A2MC_ROOT = Path(__file__).parent.parent
GENERATED_DIR = A2MC_ROOT / "phases" / "phase3_diagnosis" / "generated"
DIAGNOSIS_DIR = A2MC_ROOT / "phases" / "phase3_diagnosis"
REASONING_FILE = A2MC_ROOT / "reasoning" / "prompts.py"


def list_generated_scripts():
    """List all generated scripts with their metadata."""
    scripts = []

    for f in sorted(GENERATED_DIR.glob("*.py")):
        if f.name.startswith("_") or f.name == "__init__.py":
            continue

        metadata = extract_script_metadata(f)
        scripts.append({
            "filename": f.name,
            "path": f,
            **metadata
        })

    return scripts


def extract_script_metadata(script_path: Path) -> dict:
    """Extract metadata from a generated script."""
    metadata = {
        "description": "",
        "hypothesis": "",
        "created": "",
        "has_test_function": False,
        "is_ensemble_test": False,
        "function_name": "test_hypothesis"
    }

    try:
        content = script_path.read_text()

        # Check for test_hypothesis function
        if "def test_hypothesis(" in content:
            metadata["has_test_function"] = True

        # An ensemble test is a test_*.py with test_hypothesis()
        if (script_path.stem.startswith("test_")
                and metadata["has_test_function"]):
            metadata["is_ensemble_test"] = True

        # Extract docstring
        docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(1).strip()
            for line in docstring.split("\n"):
                line = line.strip()
                if line.startswith("Description:"):
                    metadata["description"] = line.replace("Description:", "").strip()
                elif line.startswith("Hypothesis:"):
                    metadata["hypothesis"] = line.replace("Hypothesis:", "").strip()
            # Fallback: first line of docstring
            if not metadata["description"]:
                first_line = docstring.split("\n")[0].strip().rstrip(".")
                if first_line and not first_line.startswith("Auto-generated"):
                    metadata["description"] = first_line

        # Look for metadata comments
        for line in content.split("\n")[:30]:  # Check first 30 lines
            if line.startswith("# Hypothesis:"):
                metadata["hypothesis"] = line.replace("# Hypothesis:", "").strip()
            elif line.startswith("# Created:"):
                metadata["created"] = line.replace("# Created:", "").strip()
            elif line.startswith("# Description:"):
                if not metadata["description"]:
                    metadata["description"] = line.replace("# Description:", "").strip()

    except Exception as e:
        print(f"Warning: Could not parse {script_path}: {e}")

    return metadata


def generate_tool_name(script_name: str) -> str:
    """Generate a tool name from script filename (strips timestamp suffix)."""
    # Remove timestamp suffix if present (e.g., _20260209_143022.py)
    name = re.sub(r'_\d{8}_\d{6}\.py$', '', script_name)
    # Remove .py if still present
    name = name.replace('.py', '')
    return name


def generate_inventory_entry(tool_name: str, description: str, use_when: str) -> str:
    """Generate a table row for DIAGNOSTIC_TOOLS_INVENTORY."""
    return f"| `{tool_name}` | {description} | {use_when} |"


def find_inventory_insert_point(content: str, category: str) -> tuple:
    """Find where to insert a new tool in the inventory."""
    # Look for the category header
    category_pattern = rf"### {re.escape(category)}\s*\n\s*\|[^\n]+\|\s*\n\s*\|[-\s|]+\|\s*\n"
    match = re.search(category_pattern, content)

    if match:
        # Find the end of this category's table
        table_start = match.end()
        # Find next section or end of table
        next_section = re.search(r'\n###|\n"""', content[table_start:])
        if next_section:
            insert_pos = table_start + next_section.start()
        else:
            insert_pos = table_start
        return insert_pos, True

    return -1, False


def update_reasoning_inventory(tool_name: str, description: str, category: str,
                                use_when: str, dry_run: bool = False) -> bool:
    """Update DIAGNOSTIC_TOOLS_INVENTORY in reasoning/prompts.py."""
    try:
        content = REASONING_FILE.read_text()

        # Check if tool already exists
        if f"`{tool_name}`" in content:
            print(f"Warning: Tool '{tool_name}' already exists in inventory")
            return False

        # Generate new entry
        new_entry = generate_inventory_entry(tool_name, description, use_when)

        # Find insert point
        insert_pos, found_category = find_inventory_insert_point(content, category)

        if not found_category:
            print(f"Warning: Category '{category}' not found in inventory")
            print("Available categories: Parameter Analysis, PFT Limitation Analysis, "
                  "Mortality & Collapse Analysis, Nutrient Pool Analysis, "
                  "Nutrient Mass Balance, Target Comparison, "
                  "Hypothesis Testing, Carbon Balance Analysis")
            print(f"\nYou may need to manually add the entry to {REASONING_FILE}")
            print(f"Entry to add:\n{new_entry}")
            return False

        # Insert the new entry
        new_content = content[:insert_pos] + new_entry + "\n" + content[insert_pos:]

        if dry_run:
            print(f"\n[DRY RUN] Would add to {category}:")
            print(f"  {new_entry}")
        else:
            REASONING_FILE.write_text(new_content)
            print(f"Updated DIAGNOSTIC_TOOLS_INVENTORY in {REASONING_FILE.name}")

        return True

    except Exception as e:
        print(f"Error updating {REASONING_FILE}: {e}")
        return False


def promote_script(script_name: str, tool_name: str = None, category: str = None,
                   description: str = None, use_when: str = None,
                   dry_run: bool = False) -> bool:
    """Promote a generated script to the permanent inventory."""

    # Find the script
    script_path = GENERATED_DIR / script_name
    if not script_path.exists():
        # Try with .py extension
        script_path = GENERATED_DIR / f"{script_name}.py"
        if not script_path.exists():
            print(f"Error: Script not found: {script_name}")
            print(f"Looked in: {GENERATED_DIR}")
            return False

    # Extract metadata
    metadata = extract_script_metadata(script_path)

    # Generate defaults
    if not tool_name:
        tool_name = generate_tool_name(script_path.name)

    if not description:
        description = metadata["description"] or "Custom diagnostic script"

    if not use_when:
        use_when = metadata["hypothesis"] or "Custom analysis needed"

    # Destination path
    dest_name = f"{tool_name}.py"
    dest_path = DIAGNOSIS_DIR / dest_name

    # Determine if this is an ensemble test (auto-discovered) or a regular tool
    is_ensemble_test = metadata["is_ensemble_test"]

    print(f"\n{'='*60}")
    print(f"Promoting: {script_path.name}")
    print(f"{'='*60}")
    print(f"  Source:      {script_path}")
    print(f"  Destination: {dest_path}")
    print(f"  Tool name:   {tool_name}")
    if is_ensemble_test:
        print(f"  Type:        Ensemble test (auto-discovered)")
    else:
        print(f"  Type:        Regular diagnostic tool")
        print(f"  Category:    {category or '(will infer)'}")
    print(f"  Description: {description}")
    if not is_ensemble_test:
        print(f"  Use when:    {use_when}")
    print(f"{'='*60}")

    if dest_path.exists():
        print(f"\nWarning: {dest_path} already exists!")
        if not dry_run:
            response = input("Overwrite? [y/N]: ")
            if response.lower() != 'y':
                return False

    if dry_run:
        print(f"\n[DRY RUN] Would perform the following actions:")
        print(f"  1. Copy {script_path.name} -> {dest_name}")
        if is_ensemble_test:
            print(f"  (No further steps — ensemble tests are auto-discovered at runtime)")
        else:
            if not category:
                category = _infer_category(tool_name)
            print(f"  2. Update DIAGNOSTIC_TOOLS_INVENTORY in {REASONING_FILE.name}")
            print(f"     Category: {category}")
            print(f"  3. Manually update phases/phase3_diagnosis/__init__.py")
        print(f"\nRun without --dry-run to execute.")
    else:
        # Copy the script
        shutil.copy2(script_path, dest_path)
        print(f"\nCopied script to {dest_path}")

        if is_ensemble_test:
            print(f"\nPromotion complete!")
            print(f"\nThis is an ensemble test (test_*.py with test_hypothesis()).")
            print(f"It will be auto-discovered at runtime — no further edits needed.")
            print(f"\nNext steps:")
            print(f"  1. Review the promoted script: {dest_path}")
            print(f"  2. Commit the changes")
        else:
            # Non-ensemble scripts need manual inventory + __init__.py updates
            if not category:
                category = _infer_category(tool_name)
            update_reasoning_inventory(tool_name, description, category, use_when, dry_run=False)

            print(f"\nPromotion complete!")
            print(f"\nNext steps:")
            print(f"  1. Review the promoted script: {dest_path}")
            print(f"  2. Add imports to phases/phase3_diagnosis/__init__.py")
            print(f"  3. Commit the changes")

    return True


def _infer_category(tool_name: str) -> str:
    """Infer inventory category from tool name."""
    name_lower = tool_name.lower()
    if any(x in name_lower for x in ['nutrient', 'uptake', 'nitrogen', 'phosphorus', 'p_', 'n_']):
        return "Nutrient Pool Analysis"
    elif any(x in name_lower for x in ['mortality', 'collapse', 'storm']):
        return "Mortality & Collapse Analysis"
    elif any(x in name_lower for x in ['allocation', 'limitation', 'pft']):
        return "PFT Limitation Analysis"
    elif any(x in name_lower for x in ['param', 'edge', 'bound']):
        return "Parameter Analysis"
    elif any(x in name_lower for x in ['carbon', 'gpp', 'npp']):
        return "Carbon Balance Analysis"
    elif any(x in name_lower for x in ['budget', 'balance', 'closure']):
        return "Nutrient Mass Balance"
    else:
        return "Target Comparison"  # Default


def main():
    parser = argparse.ArgumentParser(
        description="Promote generated diagnostic scripts to permanent inventory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ensemble tests (test_*.py with test_hypothesis()) are auto-discovered
at runtime — promotion just copies the file, no other edits needed.

Other scripts require manual DIAGNOSTIC_TOOLS_INVENTORY and __init__.py updates.

Examples:
    # List available scripts
    python tools/promote_diagnostic_script.py --list

    # Promote an ensemble test (auto-discovered, just copy)
    python tools/promote_diagnostic_script.py --script test_p_cycling_20260212_123456.py

    # Dry run
    python tools/promote_diagnostic_script.py --script test_p_cycling_20260212_123456.py --dry-run

    # Promote a non-test script with explicit settings
    python tools/promote_diagnostic_script.py --script analyze_water_stress.py \\
        --tool-name analyze_water_stress \\
        --category "Mortality & Collapse Analysis" \\
        --description "Analyze water stress and hydraulic failure risk" \\
        --use-when "Suspect drought or hydraulic limitation"
"""
    )

    parser.add_argument("--list", action="store_true",
                        help="List available generated scripts")
    parser.add_argument("--script", type=str,
                        help="Script filename to promote")
    parser.add_argument("--tool-name", type=str,
                        help="Name for the tool (default: derived from filename)")
    parser.add_argument("--category", type=str,
                        help="Inventory category (for non-ensemble scripts)")
    parser.add_argument("--description", type=str,
                        help="Tool description (default: from script docstring)")
    parser.add_argument("--use-when", type=str,
                        help="When to use this tool (for non-ensemble scripts)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without executing")

    args = parser.parse_args()

    if args.list:
        scripts = list_generated_scripts()
        if not scripts:
            print(f"No generated scripts found in {GENERATED_DIR}")
            print("\nGenerated scripts are created when Claude writes custom")
            print("hypothesis tests during Phase 3/4 diagnosis.")
            return 0

        print(f"\nGenerated scripts in {GENERATED_DIR}:\n")
        print("-" * 70)
        for s in scripts:
            tag = "[ensemble]" if s['is_ensemble_test'] else "[regular]"
            print(f"  {tag} {s['filename']}")
            if s['description']:
                print(f"    Description: {s['description']}")
            if s['hypothesis']:
                print(f"    Hypothesis:  {s['hypothesis']}")
            if s['created']:
                print(f"    Created:     {s['created']}")
            if s['is_ensemble_test']:
                print(f"    Promotion:   Just copy — auto-discovered at runtime")
            else:
                print(f"    Promotion:   Copy + update inventory + update __init__.py")
            print()
        print("-" * 70)
        print(f"\nTo promote a script:")
        print(f"  python tools/promote_diagnostic_script.py --script <filename> --dry-run")
        return 0

    if args.script:
        success = promote_script(
            script_name=args.script,
            tool_name=args.tool_name,
            category=args.category,
            description=args.description,
            use_when=args.use_when,
            dry_run=args.dry_run
        )
        return 0 if success else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
