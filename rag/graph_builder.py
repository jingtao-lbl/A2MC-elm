"""
Graph builder for FATES knowledge graph.

Two-layer construction:
1. Layer 1: Auto-extract ALL parameters and outputs from CDL files
2. Layer 2: Overlay hand-curated relationships from YAML

This provides comprehensive coverage of FATES entities while
preserving the manually curated mechanistic relationships.

Author: Jing Tao with Claude
"""

import json
import os
import re
import yaml
from pathlib import Path
from typing import Optional, Dict, List, Any

from .knowledge_graph import FATESKnowledgeGraph


# =============================================================================
# Default paths
# =============================================================================
_RAG_DIR = Path(__file__).parent
_A2MC_ROOT = _RAG_DIR.parent
DEFAULT_CURATED_RELATIONSHIPS_PATH = _RAG_DIR / "data" / "curated_relationships.yaml"
DEFAULT_PARAM_CDL_PATH = _A2MC_ROOT / "docs" / "fates-knowledge-base" / "fates_params_info.cdl"
DEFAULT_OUTPUT_CDL_PATH = _A2MC_ROOT / "docs" / "fates-knowledge-base" / "elm_fates_output_info.cdl"

# Key mechanisms in FATES (fallback if YAML not found)
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

# Default PFT names (used when PFTs not in YAML or config)
DEFAULT_PFT_NAMES = {
    7: ("Arctic evergreen shrub", "Evergreen shrubs (e.g., Ledum, Vaccinium vitis-idaea)"),
    9: ("Arctic deciduous shrub", "Deciduous shrubs (e.g., Betula nana, Salix)"),
    10: ("Arctic graminoid", "Tundra grasses and sedges (e.g., Eriophorum, Carex)"),
}


# =============================================================================
# PFT list resolution
# =============================================================================

def _resolve_pft_list(pft_list: Optional[List[int]] = None) -> List[int]:
    """Resolve PFT list from argument, env var, or default.

    Resolution order:
    1. pft_list argument
    2. A2MC_PFTS environment variable (comma-separated)
    3. Default [7, 9, 10]
    """
    if pft_list is not None:
        return pft_list

    env_pfts = os.environ.get("A2MC_PFTS", "")
    if env_pfts:
        try:
            return [int(p.strip()) for p in env_pfts.split(",") if p.strip()]
        except ValueError:
            pass

    return [7, 9, 10]


# =============================================================================
# YAML loading helpers (unchanged from original)
# =============================================================================

def load_curated_relationships(yaml_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load curated relationships from YAML file."""
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
            None,
            param_data.get('controls', []),
            param_data.get('affects', []),
            param_data.get('related_to', [])
        ))
    return parameters


def extract_relationships_from_yaml(data: Dict[str, Any]) -> List[tuple]:
    """Extract relationships from YAML data."""
    relationships = []

    if 'mechanisms' in data:
        for mech_name, mech_data in data['mechanisms'].items():
            for param in mech_data.get('parameters', []):
                param_clean = param.split('#')[0].strip()
                relationships.append(
                    ("parameter", param_clean, "mechanism", mech_name, "controls")
                )
            for output in mech_data.get('affects', []):
                relationships.append(
                    ("mechanism", mech_name, "output", output, "affects")
                )

    if 'parameters' in data:
        for param_name, param_data in data['parameters'].items():
            for mech in param_data.get('controls', []):
                relationships.append(
                    ("parameter", param_name, "mechanism", mech, "controls")
                )
            for output in param_data.get('affects', []):
                relationships.append(
                    ("parameter", param_name, "output", output, "affects")
                )
            for related in param_data.get('related_to', []):
                relationships.append(
                    ("parameter", param_name, "parameter", related, "related_to")
                )

    if 'outputs' in data:
        for output_name, out_data in data['outputs'].items():
            for controller in out_data.get('controlled_by', []):
                if 'mechanisms' in data and controller in data['mechanisms']:
                    relationships.append(
                        ("mechanism", controller, "output", output_name, "affects")
                    )
            for param in out_data.get('key_parameters', []):
                relationships.append(
                    ("parameter", param, "output", output_name, "affects")
                )

    # Deduplicate
    seen = set()
    unique = []
    for rel in relationships:
        if rel not in seen:
            seen.add(rel)
            unique.append(rel)

    return unique


# =============================================================================
# Layer 1: Auto-extracted from CDL files
# =============================================================================

def _add_auto_extracted_parameters(
    kg: FATESKnowledgeGraph,
    param_cdl_path: str,
    pft_list: List[int],
    include_pft_specific: bool = True
) -> int:
    """Parse CDL, add all parameter nodes with metadata.

    For each parameter:
    1. Create base node with dimensions, units, description, category
    2. Create category node if not exists
    3. Create dimension nodes
    4. Create PFT-specific nodes for PFT-dimensioned parameters
    5. Add contains, belongs_to, has_dimension edges

    Returns number of base parameter nodes added.
    """
    from .parameter_parser import FATESParameterParser

    parser = FATESParameterParser(param_cdl_path)
    params = parser.parse()
    dims = parser.get_dimensions()

    # Add dimension nodes
    for dim_name, dim_size in dims.items():
        kg.add_dimension(dim_name, size=dim_size)

    count = 0
    for name, param in params.items():
        # Skip string/name parameters
        if param.is_string or name.endswith('_name'):
            continue

        # Add base parameter node
        kg.add_parameter(
            name,
            pft=None,
            category=param.category_key,
            description=param.long_name,
            units=param.units
        )
        count += 1

        # Add has_dimension edges
        for dim in param.dimensions:
            dim_id = kg._make_node_id(kg.DIMENSION, dim)
            param_id = kg._make_node_id(kg.PARAMETER, name)
            if dim_id in kg.graph:
                kg.add_relationship(param_id, dim_id, kg.HAS_DIMENSION)

        # Add PFT-specific nodes for PFT-dimensioned parameters
        if include_pft_specific and param.is_pft_specific:
            for pft_idx in pft_list:
                kg.add_parameter(
                    name,
                    pft=pft_idx,
                    category=param.category_key,
                    description=f"{param.long_name} (PFT#{pft_idx})" if param.long_name else f"(PFT#{pft_idx})",
                    units=param.units
                )

    return count


def _add_auto_extracted_outputs(
    kg: FATESKnowledgeGraph,
    output_cdl_path: str,
    include_elm: bool = True,
    elm_filter: Optional[List[str]] = None,
    elm_output_cdl_path: Optional[str] = None,
) -> int:
    """Parse output CDL, add all output variable nodes with metadata.

    For each output:
    1. Create node with dimensions, units, description, dimension_level, category
    2. Add has_dimension edges
    3. Filter ELM variables to key subset

    If elm_output_cdl_path is given (v2.96+), also parse that CDL and add
    its variables as ELM-side output nodes. Variables already added from
    the FATES CDL are NOT duplicated.

    Returns number of output nodes added.
    """
    from .output_parser import FATESOutputParser

    parser = FATESOutputParser(output_cdl_path)
    variables = parser.parse()

    # Add dimension nodes from output CDL (may add new ones)
    dims = parser.get_dimensions()
    for dim_name, dim_size in dims.items():
        dim_id = kg._make_node_id(kg.DIMENSION, dim_name)
        if dim_id not in kg.graph:
            kg.add_dimension(dim_name, size=dim_size)

    count = 0

    # Add FATES variables
    fates_vars = parser.get_fates_variables()
    for name, var in fates_vars.items():
        kg.add_output(name, var.long_name, var.units, var.dimension_level)
        count += 1

        # Add has_dimension edges
        output_id = kg._make_node_id(kg.OUTPUT, name)
        for dim in var.dimensions:
            if dim in ("time", "lndgrid", "gridcell"):
                continue  # Skip universal dimensions
            dim_id = kg._make_node_id(kg.DIMENSION, dim)
            if dim_id in kg.graph:
                kg.add_relationship(output_id, dim_id, kg.HAS_DIMENSION)

    # Add key ELM variables
    if include_elm:
        key_elm = parser.get_key_elm_variables()
        if elm_filter:
            key_elm = {k: v for k, v in key_elm.items() if k in elm_filter}
        for name, var in key_elm.items():
            kg.add_output(name, var.long_name, var.units, var.dimension_level)
            count += 1

            output_id = kg._make_node_id(kg.OUTPUT, name)
            for dim in var.dimensions:
                if dim in ("time", "lndgrid", "gridcell"):
                    continue
                dim_id = kg._make_node_id(kg.DIMENSION, dim)
                if dim_id in kg.graph:
                    kg.add_relationship(output_id, dim_id, kg.HAS_DIMENSION)

    # v2.96: Add ELM core output variables from the dedicated ELM CDL.
    # Skip names already added from the FATES CDL (FATES wins on dupe).
    if elm_output_cdl_path:
        elm_parser = FATESOutputParser(elm_output_cdl_path)
        elm_dims = elm_parser.get_dimensions()
        for dim_name, dim_size in elm_dims.items():
            dim_id = kg._make_node_id(kg.DIMENSION, dim_name)
            if dim_id not in kg.graph:
                kg.add_dimension(dim_name, size=dim_size)
        elm_all = elm_parser.parse()
        for name, var in elm_all.items():
            output_id = kg._make_node_id(kg.OUTPUT, name)
            if output_id in kg.graph:
                continue  # already added from FATES CDL
            kg.add_output(name, var.long_name, var.units, var.dimension_level)
            count += 1
            for dim in var.dimensions:
                if dim in ("time", "lndgrid", "gridcell"):
                    continue
                dim_id = kg._make_node_id(kg.DIMENSION, dim)
                if dim_id in kg.graph:
                    kg.add_relationship(output_id, dim_id, kg.HAS_DIMENSION)

    return count


# =============================================================================
# Layer 2: Curated overlay
# =============================================================================

def _overlay_curated_relationships(
    kg: FATESKnowledgeGraph,
    curated_data: Dict,
    pft_list: List[int],
    include_pft_specific: bool = True
) -> int:
    """Overlay curated relationships onto existing nodes.

    1. Add mechanism nodes (curated only)
    2. For each curated parameter: update description/notes on existing node
    3. Add controls, affects, related_to edges
    4. For curated outputs: update metadata on existing nodes
    5. PFT-specific edges for curated parameters
    6. Phase B: write applies_in_* metadata + inactive flag onto graph nodes

    Returns number of relationships added.
    """
    if not curated_data:
        return 0

    # Lazy import to avoid circular dependencies at module load time
    from tools.config import build_applies_in_flags

    def _write_mode_flags(node_id: str, entry: Dict) -> None:
        """Write applies_in_* + inactive metadata onto a graph node."""
        if node_id not in kg.graph:
            return
        applies_in = (entry or {}).get('applies_in')
        flags = build_applies_in_flags(applies_in)
        for k, v in flags.items():
            kg.graph.nodes[node_id][k] = v
        if (entry or {}).get('inactive'):
            kg.graph.nodes[node_id]['inactive'] = True

    # Add mechanisms from YAML
    mechanisms = extract_mechanisms_from_yaml(curated_data)
    for mech in mechanisms:
        kg.add_mechanism(
            mech["name"],
            mech.get("description"),
            mech.get("code_location"),
            mech.get("module")
        )

    # Phase B: tag mechanism nodes with applies_in_* metadata
    if 'mechanisms' in curated_data:
        for mech_name, mech_data in curated_data['mechanisms'].items():
            mech_id = kg._make_node_id(kg.MECHANISM, mech_name)
            _write_mode_flags(mech_id, mech_data)

    # Update parameter metadata from curated YAML
    if 'parameters' in curated_data:
        for param_name, param_data in curated_data['parameters'].items():
            param_id = kg._make_node_id(kg.PARAMETER, param_name)
            if param_id in kg.graph:
                # Update description with calibration notes if richer
                notes = param_data.get('calibration_notes', '')
                if notes:
                    existing_desc = kg.graph.nodes[param_id].get('description', '')
                    if len(notes) > len(existing_desc or ''):
                        kg.graph.nodes[param_id]['description'] = notes.split('\n')[0]
            # Phase B: tag with applies_in_* even if param node didn't exist before
            _write_mode_flags(param_id, param_data)
            # Also tag any PFT-specific child nodes
            if include_pft_specific:
                for pft_idx in pft_list:
                    pft_param_id = f"parameter:{param_name}:pft{pft_idx}"
                    _write_mode_flags(pft_param_id, param_data)

    # Update output metadata from curated YAML
    if 'outputs' in curated_data:
        for output_name, out_data in curated_data['outputs'].items():
            output_id = kg._make_node_id(kg.OUTPUT, output_name)
            if output_id in kg.graph:
                # Update with curated metadata
                if out_data.get('notes'):
                    kg.graph.nodes[output_id]['notes'] = out_data['notes']
                if out_data.get('category'):
                    kg.graph.nodes[output_id]['category'] = out_data['category']
            # Phase B: tag output node with applies_in_* metadata
            _write_mode_flags(output_id, out_data)

    # Add relationships
    relationships = extract_relationships_from_yaml(curated_data)
    added = 0

    for rel in relationships:
        src_type, src_name, tgt_type, tgt_name, relation = rel

        # Build node IDs
        src_id = f"{src_type}:{src_name}"
        tgt_id = f"{tgt_type}:{tgt_name}"

        # Only add if both nodes exist
        if src_id in kg.graph and tgt_id in kg.graph:
            kg.add_relationship(src_id, tgt_id, relation)
            added += 1

        # Also add PFT-specific relationships if applicable
        if include_pft_specific and src_type == "parameter":
            for pft_idx in pft_list:
                pft_src_id = f"parameter:{src_name}:pft{pft_idx}"
                if pft_src_id in kg.graph and tgt_id in kg.graph:
                    kg.add_relationship(pft_src_id, tgt_id, relation)
                    added += 1

    return added


# =============================================================================
# Main build function
# =============================================================================

def build_fates_graph(
    knowledge_base_path: Optional[str] = None,
    include_pft_specific: bool = True,
    curated_yaml_path: Optional[str] = None,
    param_cdl_path: Optional[str] = None,
    output_cdl_path: Optional[str] = None,
    pft_list: Optional[List[int]] = None,
    include_elm_outputs: bool = True,
    elm_output_cdl_path: Optional[str] = None,
) -> FATESKnowledgeGraph:
    """
    Build a complete FATES knowledge graph with two-layer construction.

    Layer 1: Auto-extracted parameters and outputs from CDL files
    Layer 2: Curated relationships from YAML overlay

    Args:
        knowledge_base_path: Path to knowledge base (for future doc parsing)
        include_pft_specific: Whether to create PFT-specific parameter nodes
        curated_yaml_path: Path to curated_relationships.yaml (uses default if None)
        param_cdl_path: Path to fates_params_info.cdl (auto-detected if None)
        output_cdl_path: Path to elm_fates_output_info.cdl (auto-detected if None)
        pft_list: List of PFT indices to include (default from env or [7, 9, 10])
        include_elm_outputs: Whether to include key ELM output variables

    Returns:
        Populated FATESKnowledgeGraph
    """
    kg = FATESKnowledgeGraph()
    pft_list = _resolve_pft_list(pft_list)

    print("Building FATES Knowledge Graph (two-layer construction)...")
    print(f"  PFTs: {pft_list}")

    # --- Resolve CDL paths ---
    if param_cdl_path is None:
        env_path = os.environ.get('A2MC_FATES_PARAM_DEF_FILE', '')
        if env_path and Path(env_path).exists():
            param_cdl_path = env_path
        elif DEFAULT_PARAM_CDL_PATH.exists():
            param_cdl_path = str(DEFAULT_PARAM_CDL_PATH)

    if output_cdl_path is None:
        env_path = os.environ.get('A2MC_FATES_OUTPUT_DEF_FILE', '')
        if env_path and Path(env_path).exists():
            output_cdl_path = env_path
        elif DEFAULT_OUTPUT_CDL_PATH.exists():
            output_cdl_path = str(DEFAULT_OUTPUT_CDL_PATH)

    # --- Add PFTs ---
    print("  Adding PFTs...")
    for pft_idx in pft_list:
        name, desc = DEFAULT_PFT_NAMES.get(pft_idx, (f"PFT{pft_idx}", f"Plant Functional Type {pft_idx}"))
        kg.add_pft(pft_idx, name, desc)

    # --- Layer 1: Auto-extracted from CDL files ---
    print("  Layer 1: Auto-extracting from CDL files...")

    if param_cdl_path:
        print(f"    Parameters: {Path(param_cdl_path).name}")
        param_count = _add_auto_extracted_parameters(
            kg, param_cdl_path, pft_list, include_pft_specific
        )
        print(f"    Added {param_count} base parameter nodes")
    else:
        print("    Warning: No parameter CDL file found")
        param_count = 0

    if output_cdl_path:
        print(f"    Outputs: {Path(output_cdl_path).name}")
        if elm_output_cdl_path:
            print(f"    ELM outputs: {Path(elm_output_cdl_path).name}")
        output_count = _add_auto_extracted_outputs(
            kg, output_cdl_path, include_elm=include_elm_outputs,
            elm_output_cdl_path=elm_output_cdl_path,
        )
        print(f"    Added {output_count} output nodes")
    else:
        print("    Warning: No output CDL file found")
        output_count = 0

    # --- Layer 2: Curated overlay from YAML ---
    print("  Layer 2: Overlaying curated relationships from YAML...")
    yaml_path = Path(curated_yaml_path) if curated_yaml_path else None
    curated_data = load_curated_relationships(yaml_path)

    if curated_data:
        rel_count = _overlay_curated_relationships(
            kg, curated_data, pft_list, include_pft_specific
        )
        print(f"    Added {rel_count} curated relationships")

        # Add any curated outputs/params not in CDL
        # (This handles outputs that exist in YAML but not in the CDL file)
        if 'outputs' in curated_data:
            curated_only = 0
            for name, out_data in curated_data['outputs'].items():
                output_id = kg._make_node_id(kg.OUTPUT, name)
                if output_id not in kg.graph:
                    kg.add_output(
                        name,
                        out_data.get('long_name', name),
                        out_data.get('units', ''),
                        out_data.get('dimension', 'site')
                    )
                    curated_only += 1
            if curated_only > 0:
                print(f"    Added {curated_only} curated-only output nodes")

        if 'parameters' in curated_data:
            curated_only = 0
            for param_name, param_data in curated_data['parameters'].items():
                param_id = kg._make_node_id(kg.PARAMETER, param_name)
                if param_id not in kg.graph:
                    cat = param_data.get('category', 'unknown')
                    notes = param_data.get('calibration_notes', '').split('\n')[0] if param_data.get('calibration_notes') else ''
                    kg.add_parameter(param_name, pft=None, category=cat, description=notes)
                    curated_only += 1
                    if include_pft_specific:
                        for pft_idx in pft_list:
                            kg.add_parameter(
                                param_name, pft=pft_idx, category=cat,
                                description=f"{notes} (PFT#{pft_idx})" if notes else f"(PFT#{pft_idx})"
                            )
            if curated_only > 0:
                print(f"    Added {curated_only} curated-only parameter nodes")
    else:
        print("    Warning: No curated relationships found")

    # --- PFT competition relationships ---
    # Add if both PFTs exist in graph
    for i, pft_a in enumerate(pft_list):
        for pft_b in pft_list[i+1:]:
            pft_a_id = kg._make_node_id(kg.PFT, f"PFT{pft_a}")
            pft_b_id = kg._make_node_id(kg.PFT, f"PFT{pft_b}")
            if pft_a_id in kg.graph and pft_b_id in kg.graph:
                kg.add_relationship(pft_a_id, pft_b_id, "competes_with")

    # --- Phase B default-permissive sweep ---
    # Every node must have either `applies_universal: True` OR per-axis flags.
    # Auto-extracted nodes (parameters/outputs not in curated YAML) and any
    # other untagged nodes get applies_universal: True so they pass any
    # ConfigMode filter.
    untagged = 0
    for nid, attrs in kg.graph.nodes(data=True):
        has_universal = attrs.get('applies_universal') is True
        has_per_axis = any(k.startswith('applies_in_') for k in attrs.keys())
        if not has_universal and not has_per_axis:
            kg.graph.nodes[nid]['applies_universal'] = True
            untagged += 1
    print(f"    Default-permissive sweep: tagged {untagged} previously-untagged nodes as universal")

    # --- Print stats ---
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

    Placeholder for more sophisticated NLP-based extraction.
    """
    base = Path(knowledge_base_path)
    param_pattern = re.compile(r'fates_\w+')
    code_pattern = re.compile(r'(\w+\.F90):(\d+)-(\d+)')

    for md_file in base.rglob("*.md"):
        try:
            with open(md_file, 'r') as f:
                content = f.read()
            params = set(param_pattern.findall(content))
            code_refs = code_pattern.findall(content)
        except Exception as e:
            print(f"  Warning: Could not parse {md_file}: {e}")

    return kg


def save_graph(
    kg: FATESKnowledgeGraph,
    output_path: str,
    metadata: Optional[dict] = None,
):
    """Save knowledge graph to file.

    Args:
        kg: The knowledge graph to save.
        output_path: Destination JSON path.
        metadata: Optional profile metadata dict (per `tools/rag_metadata.py`
            schema). If supplied, embedded at top-level `_metadata` key in the
            saved JSON. Used by the version-association infrastructure for
            drift detection and provenance.
    """
    kg.save(output_path)
    if metadata is not None:
        # Reopen the saved JSON and inject the _metadata key without recomputing
        # the node-link representation.
        with open(output_path, 'r') as f:
            data = json.load(f)
        data["_metadata"] = metadata
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Graph metadata block written: {metadata.get('profile_name', '<unnamed>')}")


def load_graph(input_path: str) -> FATESKnowledgeGraph:
    """Load knowledge graph from file."""
    kg = FATESKnowledgeGraph()
    kg.load(input_path)
    return kg


def load_graph_metadata(input_path: str) -> Optional[dict]:
    """Read just the `_metadata` block from a saved graph JSON. Returns None
    if not present (legacy graphs).
    """
    with open(input_path, 'r') as f:
        data = json.load(f)
    return data.get("_metadata")


if __name__ == "__main__":
    import sys

    # Build the graph from CDL + curated YAML
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
