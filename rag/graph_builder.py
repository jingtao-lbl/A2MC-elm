"""
Graph builder for FATES knowledge graph.

Constructs the knowledge graph by:
1. Loading curated relationships from YAML (rag/data/curated_relationships.yaml)
2. Adding predefined FATES entities (parameters, outputs, mechanisms)
3. Building the complete graph structure

This provides structured knowledge about how FATES components
relate to each other for enhanced retrieval during calibration.
"""

import re
import yaml
from pathlib import Path
from typing import Optional, Dict, List, Any

from .knowledge_graph import FATESKnowledgeGraph


# =============================================================================
# Default path for curated relationships
# =============================================================================
DEFAULT_CURATED_RELATIONSHIPS_PATH = Path(__file__).parent / "data" / "curated_relationships.yaml"


# =============================================================================
# Fallback definitions (used if YAML not found)
# =============================================================================

# PFT definitions for Kougarok Arctic tundra
DEFAULT_PFTS = [
    (7, "Arctic evergreen shrub", "Evergreen shrubs (e.g., Ledum, Vaccinium vitis-idaea)"),
    (9, "Arctic deciduous shrub", "Deciduous shrubs (e.g., Betula nana, Salix)"),
    (10, "Arctic graminoid", "Tundra grasses and sedges (e.g., Eriophorum, Carex)"),
]

# Key mechanisms in FATES (fallback)
DEFAULT_MECHANISMS = [
    {
        "name": "PID_Controller",
        "description": "Adaptive leaf-to-fineroot allocation based on C:N:P stoichiometry",
        "code_location": "PRTAllometricCNPMod.F90:1596-1650",
        "module": "PRTAllometricCNPMod.F90"
    },
    {
        "name": "ECA_Competition",
        "description": "Equilibrium Chemistry Approximation for nutrient uptake competition",
        "code_location": "FatesSoilBGCFluxMod.F90:401-600",
        "module": "FatesSoilBGCFluxMod.F90"
    },
]


def load_curated_relationships(yaml_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load curated relationships from YAML file.

    Args:
        yaml_path: Path to YAML file. Uses default if None.

    Returns:
        Dictionary with categories, mechanisms, outputs, parameters
    """
    if yaml_path is None:
        yaml_path = DEFAULT_CURATED_RELATIONSHIPS_PATH

    if not yaml_path.exists():
        print(f"  Warning: Curated relationships file not found: {yaml_path}")
        return {}

    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    return data or {}


def extract_mechanisms_from_yaml(data: Dict[str, Any]) -> List[Dict]:
    """Extract mechanism definitions from YAML data."""
    mechanisms = []

    if 'mechanisms' not in data:
        return DEFAULT_MECHANISMS

    for name, mech_data in data['mechanisms'].items():
        mechanisms.append({
            "name": name,
            "description": mech_data.get('description', ''),
            "code_location": mech_data.get('code_reference', ''),
            "module": mech_data.get('code_reference', '').split('::')[0] if mech_data.get('code_reference') else None,
            "parameters": mech_data.get('parameters', []),
            "affects": mech_data.get('affects', []),
            "notes": mech_data.get('notes', '')
        })

    return mechanisms


def extract_outputs_from_yaml(data: Dict[str, Any]) -> List[tuple]:
    """Extract output variable definitions from YAML data."""
    outputs = []

    if 'outputs' not in data:
        return []

    for name, out_data in data['outputs'].items():
        outputs.append((
            name,
            out_data.get('long_name', name),
            out_data.get('units', ''),
            out_data.get('dimension', 'site'),
            out_data.get('category', 'unknown'),
            out_data.get('controlled_by', []),
            out_data.get('key_parameters', []),
            out_data.get('notes', '')
        ))

    return outputs


def extract_parameters_from_yaml(data: Dict[str, Any]) -> Dict[str, List[tuple]]:
    """Extract parameter definitions from YAML data."""
    parameters = {}

    if 'parameters' not in data:
        return {}

    for name, param_data in data['parameters'].items():
        category = param_data.get('category', 'unknown')
        if category not in parameters:
            parameters[category] = []

        parameters[category].append((
            name,
            param_data.get('calibration_notes', '').split('\n')[0] if param_data.get('calibration_notes') else '',
            None,  # units not typically in curated file
            param_data.get('controls', []),
            param_data.get('affects', []),
            param_data.get('related_to', [])
        ))

    return parameters


def extract_relationships_from_yaml(data: Dict[str, Any]) -> List[tuple]:
    """
    Extract relationships from YAML data.

    Builds relationships from:
    - mechanisms.parameters -> mechanism (controls)
    - mechanisms.affects -> output (affects)
    - parameters.controls -> mechanism (controls)
    - parameters.affects -> output (affects)
    - outputs.controlled_by -> mechanism/category (affected_by)
    - outputs.key_parameters -> parameter (affected_by)
    """
    relationships = []

    # From mechanisms
    if 'mechanisms' in data:
        for mech_name, mech_data in data['mechanisms'].items():
            # Parameters that control this mechanism
            for param in mech_data.get('parameters', []):
                # Clean param name (remove comments)
                param_clean = param.split('#')[0].strip()
                relationships.append(
                    ("parameter", param_clean, "mechanism", mech_name, "controls")
                )

            # Outputs affected by this mechanism
            for output in mech_data.get('affects', []):
                relationships.append(
                    ("mechanism", mech_name, "output", output, "affects")
                )

    # From parameters
    if 'parameters' in data:
        for param_name, param_data in data['parameters'].items():
            # Mechanisms controlled by this parameter
            for mech in param_data.get('controls', []):
                relationships.append(
                    ("parameter", param_name, "mechanism", mech, "controls")
                )

            # Outputs affected by this parameter
            for output in param_data.get('affects', []):
                relationships.append(
                    ("parameter", param_name, "output", output, "affects")
                )

            # Related parameters
            for related in param_data.get('related_to', []):
                relationships.append(
                    ("parameter", param_name, "parameter", related, "related_to")
                )

    # From outputs
    if 'outputs' in data:
        for output_name, out_data in data['outputs'].items():
            # Mechanisms/categories that control this output
            for controller in out_data.get('controlled_by', []):
                # Check if it's a mechanism or category
                if 'mechanisms' in data and controller in data['mechanisms']:
                    relationships.append(
                        ("mechanism", controller, "output", output_name, "affects")
                    )
                elif 'categories' in data and controller in data['categories']:
                    # Link via category's mechanisms
                    pass  # Category relationships handled separately

            # Parameters that directly affect this output
            for param in out_data.get('key_parameters', []):
                relationships.append(
                    ("parameter", param, "output", output_name, "affects")
                )

    # Remove duplicates while preserving order
    seen = set()
    unique_relationships = []
    for rel in relationships:
        if rel not in seen:
            seen.add(rel)
            unique_relationships.append(rel)

    return unique_relationships


def build_fates_graph(
    knowledge_base_path: Optional[str] = None,
    include_pft_specific: bool = True,
    curated_yaml_path: Optional[str] = None
) -> FATESKnowledgeGraph:
    """
    Build a complete FATES knowledge graph.

    Args:
        knowledge_base_path: Path to knowledge base (for future doc parsing)
        include_pft_specific: Whether to create PFT-specific parameter nodes
        curated_yaml_path: Path to curated_relationships.yaml (uses default if None)

    Returns:
        Populated FATESKnowledgeGraph
    """
    kg = FATESKnowledgeGraph()

    print("Building FATES Knowledge Graph...")

    # Load curated relationships from YAML
    yaml_path = Path(curated_yaml_path) if curated_yaml_path else None
    curated_data = load_curated_relationships(yaml_path)

    if curated_data:
        print(f"  Loaded curated relationships from YAML")
    else:
        print(f"  Using fallback definitions (no YAML found)")

    # Add PFTs (always use defaults for now)
    print("  Adding PFTs...")
    for pft_idx, name, desc in DEFAULT_PFTS:
        kg.add_pft(pft_idx, name, desc)

    # Add mechanisms from YAML
    print("  Adding mechanisms...")
    mechanisms = extract_mechanisms_from_yaml(curated_data)
    for mech in mechanisms:
        kg.add_mechanism(
            mech["name"],
            mech.get("description"),
            mech.get("code_location"),
            mech.get("module")
        )

    # Add outputs from YAML
    print("  Adding outputs...")
    outputs = extract_outputs_from_yaml(curated_data)
    print(f"    Found {len(outputs)} output variables in YAML")
    for output_tuple in outputs:
        name, desc, units, level = output_tuple[:4]
        kg.add_output(name, desc, units, level)

    # Add parameters from YAML
    print("  Adding parameters...")
    parameters = extract_parameters_from_yaml(curated_data)
    param_count = sum(len(p) for p in parameters.values())
    print(f"    Found {param_count} parameters in YAML")

    for category, params in parameters.items():
        for param_tuple in params:
            param_name = param_tuple[0]
            desc = param_tuple[1] if len(param_tuple) > 1 else ''
            units = param_tuple[2] if len(param_tuple) > 2 else None

            # Add base parameter (shared across PFTs or PFT=None)
            kg.add_parameter(
                param_name,
                pft=None,
                category=category,
                description=desc,
                units=units
            )

            # Add PFT-specific versions if requested
            if include_pft_specific:
                for pft_idx, _, _ in DEFAULT_PFTS:
                    kg.add_parameter(
                        param_name,
                        pft=pft_idx,
                        category=category,
                        description=f"{desc} (PFT#{pft_idx})" if desc else f"(PFT#{pft_idx})",
                        units=units
                    )

    # Add relationships from YAML
    print("  Adding relationships...")
    relationships = extract_relationships_from_yaml(curated_data)
    print(f"    Found {len(relationships)} relationships in YAML")

    added_rels = 0
    for rel in relationships:
        src_type, src_name, tgt_type, tgt_name, relation = rel

        # Handle PFT nodes specially
        if src_type == "pft":
            src_id = f"pft:{src_name}"
        else:
            src_id = f"{src_type}:{src_name}"

        if tgt_type == "pft":
            tgt_id = f"pft:{tgt_name}"
        else:
            tgt_id = f"{tgt_type}:{tgt_name}"

        # Only add if both nodes exist
        if src_id in kg.graph and tgt_id in kg.graph:
            kg.add_relationship(src_id, tgt_id, relation)
            added_rels += 1

        # Also add PFT-specific relationships if applicable
        if include_pft_specific and src_type == "parameter":
            for pft_idx, _, _ in DEFAULT_PFTS:
                pft_src_id = f"parameter:{src_name}:pft{pft_idx}"
                if pft_src_id in kg.graph and tgt_id in kg.graph:
                    kg.add_relationship(pft_src_id, tgt_id, relation)
                    added_rels += 1

    print(f"    Added {added_rels} relationships to graph")

    # Add PFT competition relationships
    kg.add_relationship("pft:PFT7", "pft:PFT9", "competes_with")
    kg.add_relationship("pft:PFT9", "pft:PFT10", "competes_with")

    # Print stats
    stats = kg.get_stats()
    print(f"\nGraph built:")
    print(f"  Total nodes: {stats['total_nodes']}")
    print(f"  Total edges: {stats['total_edges']}")
    print(f"  Nodes by type: {stats['nodes_by_type']}")
    print(f"  Edges by type: {stats['edges_by_type']}")

    return kg


def extract_entities_from_docs(
    knowledge_base_path: str,
    kg: FATESKnowledgeGraph
) -> FATESKnowledgeGraph:
    """
    Extract additional entities and relationships from documentation.

    This is a placeholder for more sophisticated NLP-based extraction.
    Currently just looks for parameter mentions and code references.

    Args:
        knowledge_base_path: Path to knowledge base
        kg: Existing knowledge graph to augment

    Returns:
        Augmented knowledge graph
    """
    base = Path(knowledge_base_path)

    # Pattern to find parameter mentions
    param_pattern = re.compile(r'fates_\w+')

    # Pattern to find code references
    code_pattern = re.compile(r'(\w+\.F90):(\d+)-(\d+)')

    # Track discovered relationships
    discovered = []

    # Scan markdown files
    for md_file in base.rglob("*.md"):
        try:
            with open(md_file, 'r') as f:
                content = f.read()

            # Find parameters mentioned
            params = set(param_pattern.findall(content))

            # Find code locations
            code_refs = code_pattern.findall(content)

            # Store for potential relationship extraction
            # (This would be expanded with NLP in production)

        except Exception as e:
            print(f"  Warning: Could not parse {md_file}: {e}")

    return kg


def save_graph(kg: FATESKnowledgeGraph, output_path: str):
    """Save knowledge graph to file."""
    kg.save(output_path)


def load_graph(input_path: str) -> FATESKnowledgeGraph:
    """Load knowledge graph from file."""
    kg = FATESKnowledgeGraph()
    kg.load(input_path)
    return kg


if __name__ == "__main__":
    import sys

    # Build the graph from curated YAML
    kg = build_fates_graph(include_pft_specific=True)

    # Save to file
    output_path = Path(__file__).parent / "fates_knowledge_graph.json"
    save_graph(kg, str(output_path))
    print(f"\nSaved graph to: {output_path}")

    # Test some queries
    print("\n" + "=" * 50)
    print("Testing Knowledge Graph Queries")
    print("=" * 50)

    print("\n1. Parameters affecting FATES_FROOTC:")
    params = kg.get_related_parameters("FATES_FROOTC", depth=3)
    for p in params[:10]:
        print(f"   - {p}")

    print("\n2. Effects of fates_cnp_pid_kp:")
    effects = kg.get_parameter_effects("fates_cnp_pid_kp")
    for e in effects:
        print(f"   - {e['relation']} -> {e['target']}")

    print("\n3. Parameters controlling PID_Controller:")
    mech_params = kg.get_mechanism_parameters("PID_Controller")
    for p in mech_params:
        print(f"   - {p}")
