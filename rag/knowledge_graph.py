"""
Knowledge Graph for FATES entities and relationships.

Provides a graph-based representation of FATES model components
for enhanced retrieval and reasoning during calibration.

Node Types:
- Parameter: FATES parameters (e.g., fates_cnp_pid_kp)
- Output: Model output variables (e.g., FATES_LEAFC)
- Mechanism: Model processes (e.g., PID_Controller, ECA_Competition)
- PFT: Plant Functional Types (e.g., PFT7, PFT9, PFT10)
- Module: Source code modules (e.g., PRTAllometricCNPMod.F90)

Edge Types:
- controls: Parameter controls a mechanism
- affects: Mechanism affects an output
- modifies: Parameter modifies an output
- belongs_to: Parameter belongs to a PFT
- implemented_in: Mechanism is implemented in a module
- competes_with: PFT competes with another PFT
- depends_on: Output depends on another output
"""

import json
from pathlib import Path
from typing import Optional, Any

try:
    import networkx as nx
except ImportError:
    raise ImportError("networkx is required. Install with: pip install networkx")


class FATESKnowledgeGraph:
    """
    Knowledge graph for FATES model entities and relationships.

    Uses NetworkX DiGraph for efficient graph operations.
    """

    # Node type constants
    PARAMETER = "Parameter"
    OUTPUT = "Output"
    MECHANISM = "Mechanism"
    PFT = "PFT"
    MODULE = "Module"
    CATEGORY = "Category"

    # Edge type constants
    CONTROLS = "controls"
    AFFECTS = "affects"
    MODIFIES = "modifies"
    BELONGS_TO = "belongs_to"
    IMPLEMENTED_IN = "implemented_in"
    COMPETES_WITH = "competes_with"
    DEPENDS_ON = "depends_on"
    CONTAINS = "contains"

    def __init__(self):
        """Initialize an empty knowledge graph."""
        self.graph = nx.DiGraph()
        self._node_index = {}  # Quick lookup by type

    def _make_node_id(self, node_type: str, name: str) -> str:
        """Create a unique node ID."""
        return f"{node_type.lower()}:{name}"

    def add_parameter(
        self,
        name: str,
        pft: Optional[int] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
        units: Optional[str] = None,
        bounds: Optional[tuple] = None,
        code_location: Optional[str] = None
    ) -> str:
        """
        Add a parameter node to the graph.

        Args:
            name: Official FATES parameter name (e.g., 'fates_cnp_pid_kp')
            pft: PFT index if PFT-specific (7, 9, 10)
            category: Parameter category (e.g., 'cnp', 'allocation')
            description: Parameter description
            units: Parameter units
            bounds: (lower, upper) bounds tuple
            code_location: Source code location

        Returns:
            Node ID

        Note:
            Parameter names use the official FATES convention (e.g., fates_cnp_vmax_no3)
            PFT is stored as an attribute, not part of the name.
            Node ID format: parameter:{name} (shared) or parameter:{name}:pft{N} (PFT-specific)
        """
        # Create node ID - include PFT if specified for unique identification
        if pft is not None:
            node_id = f"{self.PARAMETER.lower()}:{name}:pft{pft}"
        else:
            node_id = self._make_node_id(self.PARAMETER, name)

        self.graph.add_node(
            node_id,
            node_type=self.PARAMETER,
            name=name,
            pft=pft,
            category=category,
            description=description,
            units=units,
            bounds=bounds,
            code_location=code_location
        )

        # Index by type
        if self.PARAMETER not in self._node_index:
            self._node_index[self.PARAMETER] = set()
        self._node_index[self.PARAMETER].add(node_id)

        # Add edges
        if pft is not None:
            pft_id = self._make_node_id(self.PFT, f"PFT{pft}")
            if pft_id not in self.graph:
                self.add_pft(pft)
            self.add_relationship(node_id, pft_id, self.BELONGS_TO)

        if category:
            cat_id = self._make_node_id(self.CATEGORY, category)
            if cat_id not in self.graph:
                self.add_category(category)
            self.add_relationship(cat_id, node_id, self.CONTAINS)

        return node_id

    def add_output(
        self,
        name: str,
        description: Optional[str] = None,
        units: Optional[str] = None,
        level: Optional[str] = None  # 'site', 'pft', 'szpf'
    ) -> str:
        """
        Add an output variable node.

        Args:
            name: Output variable name (e.g., 'FATES_LEAFC')
            description: Variable description
            units: Variable units
            level: Aggregation level ('site', 'pft', 'szpf')

        Returns:
            Node ID
        """
        node_id = self._make_node_id(self.OUTPUT, name)

        self.graph.add_node(
            node_id,
            node_type=self.OUTPUT,
            name=name,
            description=description,
            units=units,
            level=level
        )

        if self.OUTPUT not in self._node_index:
            self._node_index[self.OUTPUT] = set()
        self._node_index[self.OUTPUT].add(node_id)

        return node_id

    def add_mechanism(
        self,
        name: str,
        description: Optional[str] = None,
        code_location: Optional[str] = None,
        module: Optional[str] = None
    ) -> str:
        """
        Add a mechanism/process node.

        Args:
            name: Mechanism name (e.g., 'PID_Controller')
            description: Mechanism description
            code_location: Source code location (file:lines)
            module: Module name (e.g., 'PRTAllometricCNPMod.F90')

        Returns:
            Node ID
        """
        node_id = self._make_node_id(self.MECHANISM, name)

        self.graph.add_node(
            node_id,
            node_type=self.MECHANISM,
            name=name,
            description=description,
            code_location=code_location,
            module=module
        )

        if self.MECHANISM not in self._node_index:
            self._node_index[self.MECHANISM] = set()
        self._node_index[self.MECHANISM].add(node_id)

        # Link to module if specified
        if module:
            mod_id = self._make_node_id(self.MODULE, module)
            if mod_id not in self.graph:
                self.add_module(module)
            self.add_relationship(node_id, mod_id, self.IMPLEMENTED_IN)

        return node_id

    def add_pft(
        self,
        pft_index: int,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """
        Add a PFT node.

        Args:
            pft_index: PFT index (e.g., 7, 9, 10)
            name: PFT name (e.g., 'Arctic evergreen shrub')
            description: PFT description

        Returns:
            Node ID
        """
        node_id = self._make_node_id(self.PFT, f"PFT{pft_index}")

        self.graph.add_node(
            node_id,
            node_type=self.PFT,
            index=pft_index,
            name=name or f"PFT{pft_index}",
            description=description
        )

        if self.PFT not in self._node_index:
            self._node_index[self.PFT] = set()
        self._node_index[self.PFT].add(node_id)

        return node_id

    def add_module(
        self,
        name: str,
        description: Optional[str] = None,
        path: Optional[str] = None
    ) -> str:
        """
        Add a source code module node.

        Args:
            name: Module name (e.g., 'PRTAllometricCNPMod.F90')
            description: Module description
            path: Full path in repository

        Returns:
            Node ID
        """
        node_id = self._make_node_id(self.MODULE, name)

        self.graph.add_node(
            node_id,
            node_type=self.MODULE,
            name=name,
            description=description,
            path=path
        )

        if self.MODULE not in self._node_index:
            self._node_index[self.MODULE] = set()
        self._node_index[self.MODULE].add(node_id)

        return node_id

    def add_category(
        self,
        name: str,
        description: Optional[str] = None
    ) -> str:
        """
        Add a parameter category node.

        Args:
            name: Category name (e.g., 'cnp', 'allocation')
            description: Category description

        Returns:
            Node ID
        """
        node_id = self._make_node_id(self.CATEGORY, name)

        self.graph.add_node(
            node_id,
            node_type=self.CATEGORY,
            name=name,
            description=description
        )

        if self.CATEGORY not in self._node_index:
            self._node_index[self.CATEGORY] = set()
        self._node_index[self.CATEGORY].add(node_id)

        return node_id

    def add_relationship(
        self,
        source: str,
        target: str,
        relation_type: str,
        weight: float = 1.0,
        **attrs
    ):
        """
        Add a directed edge between nodes.

        Args:
            source: Source node ID
            target: Target node ID
            relation_type: Type of relationship
            weight: Edge weight (default 1.0)
            **attrs: Additional edge attributes
        """
        self.graph.add_edge(
            source,
            target,
            relation_type=relation_type,
            weight=weight,
            **attrs
        )

    def get_node(self, node_id: str) -> Optional[dict]:
        """Get node attributes by ID."""
        if node_id in self.graph:
            return dict(self.graph.nodes[node_id])
        return None

    def get_nodes_by_type(self, node_type: str) -> list[dict]:
        """Get all nodes of a specific type."""
        if node_type not in self._node_index:
            return []

        return [
            {**self.graph.nodes[nid], 'id': nid}
            for nid in self._node_index[node_type]
        ]

    def get_related_parameters(
        self,
        output_name: str,
        depth: int = 2
    ) -> list[str]:
        """
        Find parameters that affect an output.

        Uses BFS to traverse backwards through mechanisms
        to find controlling parameters.

        Args:
            output_name: Output variable name
            depth: Maximum traversal depth

        Returns:
            List of parameter names
        """
        output_id = self._make_node_id(self.OUTPUT, output_name)
        if output_id not in self.graph:
            return []

        related = []
        visited = set()
        queue = [(output_id, 0)]

        while queue:
            node, d = queue.pop(0)
            if node in visited or d > depth:
                continue
            visited.add(node)

            node_data = self.graph.nodes.get(node, {})
            if node_data.get('node_type') == self.PARAMETER:
                related.append(node_data.get('name', node))

            # Traverse predecessors (nodes pointing to this node)
            for pred in self.graph.predecessors(node):
                queue.append((pred, d + 1))

        return related

    def get_parameter_effects(self, param_name: str) -> list[dict]:
        """
        Find what a parameter affects.

        Args:
            param_name: Parameter name

        Returns:
            List of effect dictionaries with target and relation info
        """
        param_id = self._make_node_id(self.PARAMETER, param_name)
        if param_id not in self.graph:
            return []

        effects = []
        for neighbor in self.graph.successors(param_id):
            edge_data = self.graph.edges[param_id, neighbor]
            node_data = self.graph.nodes[neighbor]

            effects.append({
                'target': node_data.get('name', neighbor),
                'target_type': node_data.get('node_type'),
                'relation': edge_data.get('relation_type'),
                'weight': edge_data.get('weight', 1.0)
            })

        return effects

    def get_mechanism_parameters(self, mechanism_name: str) -> list[str]:
        """
        Get parameters that control a mechanism.

        Args:
            mechanism_name: Mechanism name

        Returns:
            List of parameter names
        """
        mech_id = self._make_node_id(self.MECHANISM, mechanism_name)
        if mech_id not in self.graph:
            return []

        params = []
        for pred in self.graph.predecessors(mech_id):
            node_data = self.graph.nodes.get(pred, {})
            if node_data.get('node_type') == self.PARAMETER:
                params.append(node_data.get('name', pred))

        return params

    def get_pft_parameters(self, pft_index: int) -> list[str]:
        """
        Get all parameters for a specific PFT.

        Args:
            pft_index: PFT index (e.g., 10)

        Returns:
            List of parameter names
        """
        pft_id = self._make_node_id(self.PFT, f"PFT{pft_index}")
        if pft_id not in self.graph:
            return []

        params = []
        for pred in self.graph.predecessors(pft_id):
            node_data = self.graph.nodes.get(pred, {})
            if node_data.get('node_type') == self.PARAMETER:
                params.append(node_data.get('name', pred))

        return params

    def find_path(
        self,
        source_name: str,
        source_type: str,
        target_name: str,
        target_type: str
    ) -> list[str]:
        """
        Find shortest path between two nodes.

        Args:
            source_name: Source node name
            source_type: Source node type
            target_name: Target node name
            target_type: Target node type

        Returns:
            List of node IDs in path, or empty if no path
        """
        source_id = self._make_node_id(source_type, source_name)
        target_id = self._make_node_id(target_type, target_name)

        try:
            # Use undirected view for path finding
            path = nx.shortest_path(
                self.graph.to_undirected(),
                source_id,
                target_id
            )
            return path
        except nx.NetworkXNoPath:
            return []

    def get_subgraph(
        self,
        center_node: str,
        radius: int = 2
    ) -> 'FATESKnowledgeGraph':
        """
        Extract a subgraph around a center node.

        Args:
            center_node: Center node ID
            radius: Number of hops from center

        Returns:
            New FATESKnowledgeGraph with subgraph
        """
        if center_node not in self.graph:
            return FATESKnowledgeGraph()

        # Get nodes within radius using BFS
        nodes = set([center_node])
        frontier = set([center_node])

        for _ in range(radius):
            new_frontier = set()
            for node in frontier:
                new_frontier.update(self.graph.predecessors(node))
                new_frontier.update(self.graph.successors(node))
            frontier = new_frontier - nodes
            nodes.update(frontier)

        # Create subgraph
        subgraph = FATESKnowledgeGraph()
        subgraph.graph = self.graph.subgraph(nodes).copy()

        # Rebuild index
        for node_id in subgraph.graph.nodes:
            node_type = subgraph.graph.nodes[node_id].get('node_type')
            if node_type:
                if node_type not in subgraph._node_index:
                    subgraph._node_index[node_type] = set()
                subgraph._node_index[node_type].add(node_id)

        return subgraph

    def get_stats(self) -> dict:
        """Get graph statistics."""
        stats = {
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'nodes_by_type': {},
            'edges_by_type': {}
        }

        # Count nodes by type
        for node_type, nodes in self._node_index.items():
            stats['nodes_by_type'][node_type] = len(nodes)

        # Count edges by type
        for _, _, data in self.graph.edges(data=True):
            rel_type = data.get('relation_type', 'unknown')
            stats['edges_by_type'][rel_type] = stats['edges_by_type'].get(rel_type, 0) + 1

        return stats

    def save(self, path: str):
        """
        Save graph to JSON file.

        Args:
            path: Output file path
        """
        data = nx.node_link_data(self.graph)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Graph saved to: {path}")

    def load(self, path: str):
        """
        Load graph from JSON file.

        Args:
            path: Input file path
        """
        with open(path, 'r') as f:
            data = json.load(f)
        self.graph = nx.node_link_graph(data)

        # Rebuild index
        self._node_index = {}
        for node_id in self.graph.nodes:
            node_type = self.graph.nodes[node_id].get('node_type')
            if node_type:
                if node_type not in self._node_index:
                    self._node_index[node_type] = set()
                self._node_index[node_type].add(node_id)

        print(f"Graph loaded from: {path}")
        print(f"  Nodes: {self.graph.number_of_nodes()}")
        print(f"  Edges: {self.graph.number_of_edges()}")


if __name__ == "__main__":
    # Test the knowledge graph
    kg = FATESKnowledgeGraph()

    # Add some test nodes
    kg.add_pft(10, "Arctic graminoid", "Tundra grasses and sedges")
    kg.add_pft(9, "Arctic deciduous shrub", "Deciduous shrubs")
    kg.add_pft(7, "Arctic evergreen shrub", "Evergreen shrubs")

    # Add mechanisms
    kg.add_mechanism(
        "PID_Controller",
        "Adaptive leaf-to-fineroot allocation",
        "PRTAllometricCNPMod.F90:1596-1650",
        "PRTAllometricCNPMod.F90"
    )
    kg.add_mechanism(
        "ECA_Competition",
        "Equilibrium Chemistry Approximation for nutrient uptake",
        "FatesSoilBGCFluxMod.F90:401-600",
        "FatesSoilBGCFluxMod.F90"
    )

    # Add parameters
    kg.add_parameter(
        "fates_cnp_pid_kp_10",
        pft=10,
        category="cnp",
        description="PID proportional gain for PFT10"
    )
    kg.add_parameter(
        "fates_alloc_storage_cushion_10",
        pft=10,
        category="allocation",
        description="Storage cushion for PFT10"
    )

    # Add outputs
    kg.add_output("FATES_LEAFC", "Leaf carbon", "g C m-2", "site")
    kg.add_output("FATES_FROOTC", "Fine root carbon", "g C m-2", "site")
    kg.add_output("FATES_L2FR", "Leaf to fine root ratio", "unitless", "site")

    # Add relationships
    kg.add_relationship("parameter:fates_cnp_pid_kp_10", "mechanism:PID_Controller", kg.CONTROLS)
    kg.add_relationship("mechanism:PID_Controller", "output:FATES_L2FR", kg.AFFECTS)
    kg.add_relationship("output:FATES_L2FR", "output:FATES_FROOTC", kg.AFFECTS)
    kg.add_relationship("output:FATES_L2FR", "output:FATES_LEAFC", kg.AFFECTS)

    # Print stats
    print("\nKnowledge Graph Statistics:")
    stats = kg.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Test queries
    print("\nParameters affecting FATES_FROOTC:")
    params = kg.get_related_parameters("FATES_FROOTC")
    for p in params:
        print(f"  - {p}")

    print("\nEffects of fates_cnp_pid_kp_10:")
    effects = kg.get_parameter_effects("fates_cnp_pid_kp_10")
    for e in effects:
        print(f"  - {e['relation']} -> {e['target']} ({e['target_type']})")

    print("\nParameters for PFT10:")
    pft_params = kg.get_pft_parameters(10)
    for p in pft_params:
        print(f"  - {p}")
