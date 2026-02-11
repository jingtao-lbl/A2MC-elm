#!/usr/bin/env python3
"""
Promote a generated diagnostic script to the permanent inventory.

This script:
1. Lists available generated scripts in phases/phase3_diagnosis/generated/
2. Copies selected script to phases/phase3_diagnosis/
3. Updates DIAGNOSTIC_TOOLS_INVENTORY in reasoning.py
4. Optionally updates __init__.py exports

Usage:
    # List available scripts
    python tools/promote_diagnostic_script.py --list

    # Promote a specific script (dry-run first)
    python tools/promote_diagnostic_script.py --script test_p_cycling.py --dry-run

    # Promote for real
    python tools/promote_diagnostic_script.py --script test_p_cycling.py

    # Promote with custom tool name and category
    python tools/promote_diagnostic_script.py --script test_p_cycling.py \
        --tool-name analyze_p_cycling --category "Nutrient Pool Analysis"

Author: Jing Tao with Claude
Created: February 2026
"""

import os
import re
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime


# Paths relative to A2MC root
A2MC_ROOT = Path(__file__).parent.parent
GENERATED_DIR = A2MC_ROOT / "phases" / "phase3_diagnosis" / "generated"
DIAGNOSIS_DIR = A2MC_ROOT / "phases" / "phase3_diagnosis"
REASONING_FILE = A2MC_ROOT / "reasoning" / "prompts.py"


def list_generated_scripts():
    """List all generated scripts with their metadata."""
    scripts = []

    for f in GENERATED_DIR.glob("*.py"):
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
        "function_name": "test_hypothesis"
    }

    try:
        content = script_path.read_text()

        # Check for test_hypothesis function
        if "def test_hypothesis(" in content:
            metadata["has_test_function"] = True

        # Extract docstring
        docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(1).strip()
            # First line is usually description
            lines = docstring.split("\n")
            if lines:
                metadata["description"] = lines[0].strip()

        # Look for metadata comments
        for line in content.split("\n")[:30]:  # Check first 30 lines
            if line.startswith("# Hypothesis:"):
                metadata["hypothesis"] = line.replace("# Hypothesis:", "").strip()
            elif line.startswith("# Created:"):
                metadata["created"] = line.replace("# Created:", "").strip()
            elif line.startswith("# Description:"):
                metadata["description"] = line.replace("# Description:", "").strip()

    except Exception as e:
        print(f"Warning: Could not parse {script_path}: {e}")

    return metadata


def generate_tool_name(script_name: str) -> str:
    """Generate a tool name from script filename."""
    # Remove timestamp suffix if present (e.g., _20260209_143022.py)
    name = re.sub(r'_\d{8}_\d{6}\.py$', '', script_name)
    # Remove .py if still present
    name = name.replace('.py', '')
    return name


def generate_inventory_entry(tool_name: str, description: str, category: str, use_when: str) -> str:
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
    """Update DIAGNOSTIC_TOOLS_INVENTORY in reasoning.py."""
    try:
        content = REASONING_FILE.read_text()

        # Check if tool already exists
        if f"`{tool_name}`" in content:
            print(f"Warning: Tool '{tool_name}' already exists in inventory")
            return False

        # Generate new entry
        new_entry = generate_inventory_entry(tool_name, description, category, use_when)

        # Find insert point
        insert_pos, found_category = find_inventory_insert_point(content, category)

        if not found_category:
            print(f"Warning: Category '{category}' not found in inventory")
            print("Available categories: Parameter Analysis, PFT Limitation Analysis, "
                  "Mortality & Collapse Analysis, Nutrient Pool Analysis, Target Comparison")
            print("\nYou may need to manually add the entry to reasoning.py")
            print(f"Entry to add:\n{new_entry}")
            return False

        # Insert the new entry
        new_content = content[:insert_pos] + new_entry + "\n" + content[insert_pos:]

        if dry_run:
            print(f"\n[DRY RUN] Would add to {category}:")
            print(f"  {new_entry}")
        else:
            REASONING_FILE.write_text(new_content)
            print(f"Updated DIAGNOSTIC_TOOLS_INVENTORY in reasoning.py")

        return True

    except Exception as e:
        print(f"Error updating reasoning.py: {e}")
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

    if not metadata["has_test_function"]:
        print(f"Warning: Script does not have a test_hypothesis() function")
        response = input("Continue anyway? [y/N]: ")
        if response.lower() != 'y':
            return False

    # Generate defaults
    if not tool_name:
        tool_name = generate_tool_name(script_path.name)

    if not description:
        description = metadata["description"] or "Custom diagnostic script"

    if not category:
        # Try to infer category from script name/content
        name_lower = tool_name.lower()
        if any(x in name_lower for x in ['nutrient', 'uptake', 'nitrogen', 'phosphorus', 'p_', 'n_']):
            category = "Nutrient Pool Analysis"
        elif any(x in name_lower for x in ['mortality', 'collapse', 'storm']):
            category = "Mortality & Collapse Analysis"
        elif any(x in name_lower for x in ['allocation', 'limitation', 'pft']):
            category = "PFT Limitation Analysis"
        elif any(x in name_lower for x in ['param', 'edge', 'bound']):
            category = "Parameter Analysis"
        else:
            category = "Target Comparison"  # Default

    if not use_when:
        use_when = metadata["hypothesis"] or "Custom analysis needed"

    # Destination path
    dest_name = f"{tool_name}.py"
    dest_path = DIAGNOSIS_DIR / dest_name

    print(f"\n{'='*60}")
    print(f"Promoting: {script_path.name}")
    print(f"{'='*60}")
    print(f"  Source:      {script_path}")
    print(f"  Destination: {dest_path}")
    print(f"  Tool name:   {tool_name}")
    print(f"  Category:    {category}")
    print(f"  Description: {description}")
    print(f"  Use when:    {use_when}")
    print(f"{'='*60}")

    if dest_path.exists():
        print(f"\nWarning: {dest_path} already exists!")
        if not dry_run:
            response = input("Overwrite? [y/N]: ")
            if response.lower() != 'y':
                return False

    if dry_run:
        print("\n[DRY RUN] Would perform the following actions:")
        print(f"  1. Copy {script_path.name} -> {dest_name}")
        print(f"  2. Update DIAGNOSTIC_TOOLS_INVENTORY in reasoning.py")
        print(f"\nRun without --dry-run to execute.")
    else:
        # Copy the script
        shutil.copy2(script_path, dest_path)
        print(f"\nCopied script to {dest_path}")

        # Update inventory
        update_reasoning_inventory(tool_name, description, category, use_when, dry_run=False)

        print(f"\nPromotion complete!")
        print(f"\nNext steps:")
        print(f"  1. Review the promoted script: {dest_path}")
        print(f"  2. Update phases/phase3_diagnosis/__init__.py if needed")
        print(f"  3. Test the new tool in a diagnosis run")
        print(f"  4. Commit the changes")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Promote generated diagnostic scripts to permanent inventory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List available scripts
    python tools/promote_diagnostic_script.py --list

    # Dry run (preview changes)
    python tools/promote_diagnostic_script.py --script test_p_cycling.py --dry-run

    # Promote with defaults
    python tools/promote_diagnostic_script.py --script test_p_cycling.py

    # Promote with custom settings
    python tools/promote_diagnostic_script.py --script test_p_cycling.py \\
        --tool-name analyze_p_cycling_efficiency \\
        --category "Nutrient Pool Analysis" \\
        --description "Analyze P cycling efficiency across ensemble" \\
        --use-when "Suspect P limitation or cycling issues"
"""
    )

    parser.add_argument("--list", action="store_true",
                        help="List available generated scripts")
    parser.add_argument("--script", type=str,
                        help="Script filename to promote")
    parser.add_argument("--tool-name", type=str,
                        help="Name for the tool (default: derived from filename)")
    parser.add_argument("--category", type=str,
                        help="Inventory category (default: inferred from script)")
    parser.add_argument("--description", type=str,
                        help="Tool description (default: from script docstring)")
    parser.add_argument("--use-when", type=str,
                        help="When to use this tool (default: from script metadata)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without executing")

    args = parser.parse_args()

    if args.list:
        scripts = list_generated_scripts()
        if not scripts:
            print(f"No generated scripts found in {GENERATED_DIR}")
            print("\nGenerated scripts are created when Claude writes custom")
            print("hypothesis tests during Phase 3 diagnosis.")
            return 0

        print(f"\nGenerated scripts in {GENERATED_DIR}:\n")
        print("-" * 70)
        for s in scripts:
            print(f"  {s['filename']}")
            if s['description']:
                print(f"    Description: {s['description']}")
            if s['hypothesis']:
                print(f"    Hypothesis:  {s['hypothesis']}")
            if s['created']:
                print(f"    Created:     {s['created']}")
            print(f"    Has test_hypothesis(): {'Yes' if s['has_test_function'] else 'No'}")
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
