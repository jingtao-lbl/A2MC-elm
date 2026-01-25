"""
Hybrid Retriever combining vector search with knowledge graph traversal.

This is the GraphRAG implementation that provides:
1. Semantic search via vector embeddings (ChromaDB)
2. Structured relationships via knowledge graph (NetworkX)
3. Combined context for enhanced AI reasoning

The hybrid approach provides:
- Relevant documentation chunks (from vector search)
- Entity relationships (from graph traversal)
- Parameter-mechanism-output pathways
"""

from pathlib import Path
from typing import Optional

from .retriever import FATESRetriever
from .knowledge_graph import FATESKnowledgeGraph
from .graph_builder import build_fates_graph, load_graph


class HybridRetriever:
    """
    Hybrid retriever combining vector search and knowledge graph.

    This is the main GraphRAG interface for calibration context retrieval.
    """

    def __init__(
        self,
        knowledge_base_path: str = "docs/fates-knowledge-base",
        vector_persist_dir: str = "rag/chroma_db",
        graph_path: Optional[str] = "rag/fates_knowledge_graph.json",
        auto_build: bool = True
    ):
        """
        Initialize the hybrid retriever.

        Args:
            knowledge_base_path: Path to knowledge base directory
            vector_persist_dir: ChromaDB persistence directory
            graph_path: Path to saved knowledge graph (JSON)
            auto_build: Auto-build indexes if missing
        """
        self.kb_path = knowledge_base_path
        self.graph_path = graph_path

        # Initialize vector retriever
        self.vector_retriever = FATESRetriever(
            knowledge_base_path=knowledge_base_path,
            persist_dir=vector_persist_dir,
            auto_build=auto_build
        )

        # Initialize or load knowledge graph
        if graph_path and Path(graph_path).exists():
            print(f"Loading knowledge graph from: {graph_path}")
            self.knowledge_graph = load_graph(graph_path)
        else:
            print("Building knowledge graph...")
            self.knowledge_graph = build_fates_graph(
                knowledge_base_path=knowledge_base_path,
                include_pft_specific=True
            )
            if graph_path:
                self.knowledge_graph.save(graph_path)

    def get_context(
        self,
        query: str,
        n_vector_results: int = 5,
        graph_depth: int = 2,
        include_graph: bool = True
    ) -> dict:
        """
        Get context using both vector search and graph traversal.

        Args:
            query: Natural language query
            n_vector_results: Number of vector search results
            graph_depth: Depth for graph traversal
            include_graph: Whether to include graph context

        Returns:
            Dictionary with 'vector_context' and 'graph_context'
        """
        # Vector search
        vector_results = self.vector_retriever.vector_store.query(
            query, n_results=n_vector_results
        )

        vector_context = self._format_vector_results(vector_results)

        # Graph context (if enabled)
        graph_context = ""
        if include_graph:
            # Extract entities from query for graph lookup
            entities = self._extract_entities_from_query(query)
            graph_context = self._get_graph_context(entities, graph_depth)

        return {
            'vector_context': vector_context,
            'graph_context': graph_context,
            'combined': self._combine_contexts(vector_context, graph_context)
        }

    def get_calibration_context(
        self,
        parameters: list[str] = None,
        outputs: list[str] = None,
        mechanisms: list[str] = None,
        pft: Optional[int] = None,
        n_vector_results: int = 3,
        graph_depth: int = 2
    ) -> dict:
        """
        Get calibration-specific context.

        This is the main method for AI-assisted calibration, providing
        both documentation context and structural relationships.

        Args:
            parameters: List of parameter names
            outputs: List of output variable names
            mechanisms: List of mechanism names
            pft: PFT index to focus on
            n_vector_results: Vector results per query
            graph_depth: Graph traversal depth

        Returns:
            Dictionary with structured calibration context
        """
        context = {
            'parameters': {},
            'outputs': {},
            'mechanisms': {},
            'relationships': [],
            'documentation': "",
            'combined': ""
        }

        # Get vector context for calibration
        doc_context = self.vector_retriever.get_calibration_context(
            parameters=parameters,
            outputs=outputs,
            mechanisms=mechanisms,
            n_results_per_query=n_vector_results
        )
        context['documentation'] = doc_context

        # Get graph context for each parameter
        if parameters:
            for param in parameters:
                param_context = self._get_parameter_context(param, graph_depth)
                context['parameters'][param] = param_context

        # Get graph context for each output
        if outputs:
            for output in outputs:
                output_context = self._get_output_context(output, graph_depth)
                context['outputs'][output] = output_context

        # Get graph context for each mechanism
        if mechanisms:
            for mech in mechanisms:
                mech_context = self._get_mechanism_context(mech)
                context['mechanisms'][mech] = mech_context

        # Find relationships between specified entities
        if parameters and outputs:
            for param in parameters:
                for output in outputs:
                    path = self._find_causal_path(param, output)
                    if path:
                        context['relationships'].append({
                            'from': param,
                            'to': output,
                            'path': path
                        })

        # PFT-specific filtering
        if pft is not None:
            pft_params = self.knowledge_graph.get_pft_parameters(pft)
            context['pft_parameters'] = pft_params

        # Combine into formatted context
        context['combined'] = self._format_calibration_context(context)

        return context

    def get_parameter_info(self, param_name: str) -> dict:
        """
        Get comprehensive information about a parameter.

        Args:
            param_name: Parameter name

        Returns:
            Dictionary with parameter info, effects, and documentation
        """
        # Graph info
        param_id = f"parameter:{param_name}"
        node_data = self.knowledge_graph.get_node(param_id)

        # Effects from graph
        effects = self.knowledge_graph.get_parameter_effects(param_name)

        # Documentation from vector search
        doc_context = self.vector_retriever.get_parameter_documentation(param_name)

        return {
            'name': param_name,
            'node_data': node_data,
            'effects': effects,
            'documentation': doc_context
        }

    def get_mechanism_info(self, mechanism_name: str) -> dict:
        """
        Get comprehensive information about a mechanism.

        Args:
            mechanism_name: Mechanism name

        Returns:
            Dictionary with mechanism info, parameters, and documentation
        """
        # Graph info
        mech_id = f"mechanism:{mechanism_name}"
        node_data = self.knowledge_graph.get_node(mech_id)

        # Controlling parameters
        params = self.knowledge_graph.get_mechanism_parameters(mechanism_name)

        # Documentation
        doc_context = self.vector_retriever.get_mechanism_documentation(mechanism_name)

        return {
            'name': mechanism_name,
            'node_data': node_data,
            'controlling_parameters': params,
            'documentation': doc_context
        }

    def find_parameters_for_output(
        self,
        output_name: str,
        depth: int = 3
    ) -> list[dict]:
        """
        Find parameters that affect a specific output.

        Uses graph traversal to find causal relationships.

        Args:
            output_name: Output variable name
            depth: Traversal depth

        Returns:
            List of parameter info dictionaries
        """
        # Get parameters from graph
        param_names = self.knowledge_graph.get_related_parameters(output_name, depth)

        # Get info for each
        results = []
        for param in param_names:
            effects = self.knowledge_graph.get_parameter_effects(param)
            results.append({
                'parameter': param,
                'effects': effects
            })

        return results

    def _extract_entities_from_query(self, query: str) -> dict:
        """Extract FATES entities mentioned in query."""
        import re

        entities = {
            'parameters': [],
            'outputs': [],
            'mechanisms': [],
            'pfts': []
        }

        # Look for parameter patterns
        param_pattern = re.compile(r'fates_\w+', re.IGNORECASE)
        entities['parameters'] = param_pattern.findall(query.lower())

        # Look for output patterns
        output_pattern = re.compile(r'FATES_\w+', re.IGNORECASE)
        potential_outputs = output_pattern.findall(query.upper())
        entities['outputs'] = [o for o in potential_outputs if o not in entities['parameters']]

        # Look for PFT mentions
        pft_pattern = re.compile(r'PFT\s*#?\s*(\d+)', re.IGNORECASE)
        pft_matches = pft_pattern.findall(query)
        entities['pfts'] = [int(p) for p in pft_matches]

        # Look for mechanism keywords
        mechanism_keywords = {
            'pid': 'PID_Controller',
            'allocation': 'Storage_Allocation',
            'phenology': 'Cold_Phenology',
            'eca': 'ECA_Competition',
            'nutrient': 'ECA_Competition',
            'mortality': 'Carbon_Starvation',
            'photosynthesis': 'Photosynthesis',
            'root': 'Root_Distribution',
        }

        query_lower = query.lower()
        for keyword, mechanism in mechanism_keywords.items():
            if keyword in query_lower:
                if mechanism not in entities['mechanisms']:
                    entities['mechanisms'].append(mechanism)

        return entities

    def _get_graph_context(self, entities: dict, depth: int) -> str:
        """Get context from knowledge graph based on entities."""
        context_parts = []

        # Parameter context
        for param in entities.get('parameters', []):
            effects = self.knowledge_graph.get_parameter_effects(param)
            if effects:
                context_parts.append(
                    f"Parameter {param} effects:\n" +
                    "\n".join([f"  - {e['relation']} {e['target']}" for e in effects])
                )

        # Output context
        for output in entities.get('outputs', []):
            params = self.knowledge_graph.get_related_parameters(output, depth)
            if params:
                context_parts.append(
                    f"Parameters affecting {output}:\n" +
                    "\n".join([f"  - {p}" for p in params[:10]])
                )

        # Mechanism context
        for mech in entities.get('mechanisms', []):
            params = self.knowledge_graph.get_mechanism_parameters(mech)
            if params:
                context_parts.append(
                    f"Parameters controlling {mech}:\n" +
                    "\n".join([f"  - {p}" for p in params])
                )

        # PFT context
        for pft in entities.get('pfts', []):
            params = self.knowledge_graph.get_pft_parameters(pft)
            if params:
                context_parts.append(
                    f"PFT{pft} parameters:\n" +
                    "\n".join([f"  - {p}" for p in params[:10]])
                )

        return "\n\n".join(context_parts)

    def _get_parameter_context(self, param: str, depth: int) -> dict:
        """Get graph context for a parameter."""
        # Try both with and without PFT suffix
        effects = self.knowledge_graph.get_parameter_effects(param)

        # Get node data
        node = self.knowledge_graph.get_node(f"parameter:{param}")

        return {
            'effects': effects,
            'node_data': node,
            'category': node.get('category') if node else None,
            'pft': node.get('pft') if node else None
        }

    def _get_output_context(self, output: str, depth: int) -> dict:
        """Get graph context for an output."""
        params = self.knowledge_graph.get_related_parameters(output, depth)
        node = self.knowledge_graph.get_node(f"output:{output}")

        return {
            'affecting_parameters': params,
            'node_data': node
        }

    def _get_mechanism_context(self, mechanism: str) -> dict:
        """Get graph context for a mechanism."""
        params = self.knowledge_graph.get_mechanism_parameters(mechanism)
        node = self.knowledge_graph.get_node(f"mechanism:{mechanism}")

        return {
            'controlling_parameters': params,
            'node_data': node,
            'code_location': node.get('code_location') if node else None
        }

    def _find_causal_path(self, param: str, output: str) -> list[str]:
        """Find causal path from parameter to output."""
        path = self.knowledge_graph.find_path(
            param, "Parameter",
            output, "Output"
        )
        return path

    def _format_vector_results(self, results: list[dict]) -> str:
        """Format vector search results into context string."""
        if not results:
            return "No relevant documentation found."

        parts = []
        for i, r in enumerate(results, 1):
            source = r.get('source', 'unknown')
            content = r.get('content', '')
            relevance = r.get('relevance', 0)

            parts.append(f"[{i}] Source: {source} (relevance: {relevance:.2f})\n{content}")

        return "\n\n---\n\n".join(parts)

    def _combine_contexts(self, vector_context: str, graph_context: str) -> str:
        """Combine vector and graph contexts."""
        combined = []

        if graph_context:
            combined.append("## Knowledge Graph Context\n" + graph_context)

        if vector_context:
            combined.append("## Documentation Context\n" + vector_context)

        return "\n\n".join(combined)

    def _format_calibration_context(self, context: dict) -> str:
        """Format calibration context into readable string."""
        parts = []

        # Parameter info
        if context.get('parameters'):
            parts.append("## Parameter Information")
            for param, info in context['parameters'].items():
                if info.get('effects'):
                    effects_str = ", ".join([e['target'] for e in info['effects']])
                    parts.append(f"- **{param}**: affects {effects_str}")

        # Output info
        if context.get('outputs'):
            parts.append("\n## Output Dependencies")
            for output, info in context['outputs'].items():
                if info.get('affecting_parameters'):
                    params_str = ", ".join(info['affecting_parameters'][:5])
                    parts.append(f"- **{output}**: controlled by {params_str}")

        # Relationships
        if context.get('relationships'):
            parts.append("\n## Causal Pathways")
            for rel in context['relationships']:
                if rel['path']:
                    path_str = " -> ".join([p.split(':')[-1] for p in rel['path']])
                    parts.append(f"- {rel['from']} -> {rel['to']}: {path_str}")

        # Documentation
        if context.get('documentation'):
            parts.append("\n## Relevant Documentation")
            parts.append(context['documentation'][:2000])  # Limit length

        return "\n".join(parts)

    def get_stats(self) -> dict:
        """Get statistics about both retrievers."""
        vector_stats = self.vector_retriever.get_stats()
        graph_stats = self.knowledge_graph.get_stats()

        return {
            'vector_store': vector_stats,
            'knowledge_graph': graph_stats
        }


def create_hybrid_retriever(
    knowledge_base_path: str = "docs/fates-knowledge-base",
    vector_persist_dir: str = "rag/chroma_db",
    graph_path: str = "rag/fates_knowledge_graph.json",
    rebuild: bool = False
) -> HybridRetriever:
    """
    Factory function to create a hybrid retriever.

    Args:
        knowledge_base_path: Path to knowledge base
        vector_persist_dir: ChromaDB directory
        graph_path: Knowledge graph JSON path
        rebuild: If True, rebuild both indexes

    Returns:
        Configured HybridRetriever
    """
    if rebuild:
        import shutil

        # Remove vector store
        if Path(vector_persist_dir).exists():
            shutil.rmtree(vector_persist_dir)

        # Remove graph
        if Path(graph_path).exists():
            Path(graph_path).unlink()

    return HybridRetriever(
        knowledge_base_path=knowledge_base_path,
        vector_persist_dir=vector_persist_dir,
        graph_path=graph_path,
        auto_build=True
    )


if __name__ == "__main__":
    print("Creating Hybrid Retriever (GraphRAG)...")

    retriever = HybridRetriever(auto_build=True)

    print("\n" + "=" * 60)
    print("Testing Hybrid Retriever")
    print("=" * 60)

    # Test 1: General query
    print("\n1. General query: 'PID controller allocation leaf to fineroot'")
    result = retriever.get_context("PID controller allocation leaf to fineroot")
    print("\nGraph context:")
    print(result['graph_context'][:500] if result['graph_context'] else "None")
    print("\nVector context preview:")
    print(result['vector_context'][:500] + "...")

    # Test 2: Calibration context
    print("\n2. Calibration context for PFT10 optimization")
    cal_result = retriever.get_calibration_context(
        parameters=['fates_cnp_pid_kp', 'fates_alloc_storage_cushion'],
        outputs=['FATES_LEAFC', 'FATES_FROOTC'],
        mechanisms=['PID_Controller'],
        pft=10
    )
    print("\nCombined context preview:")
    print(cal_result['combined'][:1000] + "...")

    # Test 3: Find parameters for output
    print("\n3. Parameters affecting FATES_FROOTC:")
    params = retriever.find_parameters_for_output("FATES_FROOTC")
    for p in params[:5]:
        print(f"   - {p['parameter']}")

    # Print stats
    print("\n" + "=" * 60)
    print("Retriever Statistics")
    print("=" * 60)
    stats = retriever.get_stats()
    print(f"\nVector store: {stats['vector_store']['total_documents']} documents")
    print(f"Knowledge graph: {stats['knowledge_graph']['total_nodes']} nodes, "
          f"{stats['knowledge_graph']['total_edges']} edges")
