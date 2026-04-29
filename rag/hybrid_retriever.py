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

import os
from pathlib import Path
from typing import Optional, Union

from .retriever import FATESRetriever
from .knowledge_graph import FATESKnowledgeGraph
from .graph_builder import build_fates_graph, load_graph
from .loader import DEFAULT_KNOWLEDGE_BASES

# Compute A2MC root directory from module location
# rag/ is directly under A2MC/, so parent of this file's directory is A2MC root
_RAG_DIR = Path(__file__).parent.resolve()
_A2MC_ROOT = _RAG_DIR.parent


def _resolve_path(path: str, base: Path = _A2MC_ROOT) -> str:
    """Resolve a path relative to A2MC root if it's not absolute."""
    p = Path(path)
    if p.is_absolute():
        return str(p)
    return str(base / p)


def _resolve_rag_paths_from_env() -> tuple[str, str]:
    """Build (vector_persist_dir, graph_path) from A2MC env vars.

    Layout: `$A2MC_RAG_DIR/chroma_db/$A2MC_RAG_ACTIVE` and
    `$A2MC_RAG_DIR/graphs/$A2MC_RAG_ACTIVE.json`. `A2MC_RAG_DIR` defaults
    to `<repo>/rag`. `A2MC_RAG_ACTIVE` is required (per the version-association
    infrastructure); raises EnvironmentError if missing.
    """
    rag_dir = os.environ.get("A2MC_RAG_DIR")
    if not rag_dir:
        rag_dir = str(_A2MC_ROOT / "rag")
    active = os.environ.get("A2MC_RAG_ACTIVE")
    if not active:
        raise EnvironmentError(
            "A2MC_RAG_ACTIVE is not set and no explicit vector_persist_dir/"
            "graph_path was supplied. Set A2MC_RAG_ACTIVE to a registered "
            "milestone profile name (e.g., 'api-43-1' or 'api-31-0'), "
            "or pass the paths explicitly."
        )
    return (
        str(Path(rag_dir) / "chroma_db" / active),
        str(Path(rag_dir) / "graphs" / f"{active}.json"),
    )


class HybridRetriever:
    """
    Hybrid retriever combining vector search and knowledge graph.

    This is the main GraphRAG interface for calibration context retrieval.
    """

    def __init__(
        self,
        knowledge_base_path: Union[str, list[str]] = None,
        vector_persist_dir: Optional[str] = None,
        graph_path: Optional[str] = None,
        auto_build: bool = True
    ):
        """
        Initialize the hybrid retriever.

        Args:
            knowledge_base_path: Path(s) to knowledge base directory(ies).
                                 Can be a single path string or list of paths.
                                 If None, uses DEFAULT_KNOWLEDGE_BASES (FATES + ELM).
            vector_persist_dir: ChromaDB persistence directory. If None,
                                derived from `$A2MC_RAG_DIR/chroma_db/$A2MC_RAG_ACTIVE`.
            graph_path: Path to saved knowledge graph (JSON). If None,
                        derived from `$A2MC_RAG_DIR/graphs/$A2MC_RAG_ACTIVE.json`.
            auto_build: Auto-build indexes if missing
        """
        # Handle default and resolve paths
        if knowledge_base_path is None:
            kb_paths = [_resolve_path(p) for p in DEFAULT_KNOWLEDGE_BASES]
        elif isinstance(knowledge_base_path, str):
            kb_paths = [_resolve_path(knowledge_base_path)]
        else:
            kb_paths = [_resolve_path(p) for p in knowledge_base_path]

        # Resolve env-driven paths if not given. Both must resolve from the
        # same active profile to avoid mismatch.
        if vector_persist_dir is None and graph_path is None:
            vector_persist_dir, graph_path = _resolve_rag_paths_from_env()
        elif vector_persist_dir is None:
            vector_persist_dir, _ = _resolve_rag_paths_from_env()
        elif graph_path is None:
            _, graph_path = _resolve_rag_paths_from_env()

        vector_persist_dir = _resolve_path(vector_persist_dir)
        if graph_path:
            graph_path = _resolve_path(graph_path)

        self.kb_paths = kb_paths
        self.kb_path = kb_paths[0] if len(kb_paths) == 1 else kb_paths  # backward compat
        self.graph_path = graph_path

        # Initialize vector retriever with multiple knowledge bases
        self.vector_retriever = FATESRetriever(
            knowledge_base_path=kb_paths,
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

    def get_parameter_definitions(
        self,
        param_names: list[str],
        include_related: bool = True,
        include_docs: bool = True,
        max_related: int = 5
    ) -> str:
        """Get formatted parameter context for specific parameters.

        Combines graph metadata + graph edges + vector search docs.

        Args:
            param_names: List of parameter names to look up
            include_related: Include related parameters from graph
            include_docs: Include documentation from vector search
            max_related: Max related parameters to include

        Returns:
            Formatted parameter context string
        """
        parts = []

        for param_name in param_names:
            # Get graph metadata
            param_id = f"parameter:{param_name}"
            node = self.knowledge_graph.get_node(param_id)

            if node:
                dims = []
                # Get dimensions from has_dimension edges
                for neighbor in self.knowledge_graph.graph.successors(param_id):
                    n_data = self.knowledge_graph.graph.nodes.get(neighbor, {})
                    edge_data = self.knowledge_graph.graph.edges.get((param_id, neighbor), {})
                    if edge_data.get('relation_type') == 'has_dimension':
                        dims.append(n_data.get('name', neighbor))

                dims_str = ', '.join(dims) if dims else 'scalar'
                units = node.get('units', '')
                desc = node.get('description', '')
                cat = node.get('category', '')

                line = f"- **{param_name}** ({dims_str}) [{units}]"
                if desc:
                    line += f"\n  {desc}"

                # Get effects
                effects = self.knowledge_graph.get_parameter_effects(param_name)
                mechanisms = [e['target'] for e in effects if e.get('target_type') == 'Mechanism']
                outputs = [e['target'] for e in effects if e.get('target_type') == 'Output']
                related = [e['target'] for e in effects if e.get('relation') == 'related_to']

                if mechanisms:
                    line += f"\n  Controls: {', '.join(mechanisms)}"
                if outputs:
                    line += f"\n  Affects: {', '.join(outputs[:5])}"
                if include_related and related:
                    line += f"\n  Related: {', '.join(related[:max_related])}"

                parts.append(line)
            else:
                # Try vector search as fallback
                parts.append(f"- **{param_name}** (not in knowledge graph)")

        # Add documentation if requested
        doc_section = ""
        if include_docs and param_names:
            try:
                doc_results = self.vector_retriever.query_parameters(
                    ' '.join(param_names[:5]),
                    n_results=3
                )
                if doc_results:
                    doc_parts = []
                    for r in doc_results[:3]:
                        doc_parts.append(r['content'])
                    doc_section = "\n\n### Parameter Documentation\n" + "\n\n".join(doc_parts)
            except Exception:
                pass

        result = "### Parameters Under Analysis\n" + "\n\n".join(parts)
        if doc_section:
            result += doc_section

        return result

    def get_output_definitions(
        self,
        output_names: list[str],
        include_controlling_params: bool = True,
        include_docs: bool = True
    ) -> str:
        """Get formatted output variable context for specific outputs.

        Args:
            output_names: List of output variable names
            include_controlling_params: Include controlling parameters from graph
            include_docs: Include documentation from vector search

        Returns:
            Formatted output variable context string
        """
        parts = []

        for output_name in output_names:
            node = self.knowledge_graph.get_node(f"output:{output_name}")

            if node:
                units = node.get('units', '')
                desc = node.get('description', '')
                level = node.get('level', '')

                line = f"- **{output_name}** ({level}) [{units}]"
                if desc:
                    line += f" - {desc}"

                # Get controlling parameters
                if include_controlling_params:
                    params = self.knowledge_graph.get_related_parameters(output_name, depth=2)
                    # Deduplicate
                    unique_params = list(dict.fromkeys(params))
                    if unique_params:
                        line += f"\n  Key parameters: {', '.join(unique_params[:8])}"

                parts.append(line)
            else:
                parts.append(f"- **{output_name}** (not in knowledge graph)")

        result = "### Output Variables\n" + "\n\n".join(parts)
        return result

    def get_targeted_context(
        self,
        param_names: list[str] = None,
        output_names: list[str] = None,
        mechanisms: list[str] = None,
        pft: int = None,
        include_docs: bool = True
    ) -> str:
        """Unified method replacing raw text injection.

        Returns formatted block with only relevant parameter/output context
        from the knowledge graph and vector store.

        Args:
            param_names: Parameter names to look up
            output_names: Output variable names to look up
            mechanisms: Mechanism names to look up
            pft: PFT index for additional context
            include_docs: Include documentation from vector search

        Returns:
            Formatted context string for inclusion in AI prompts
        """
        sections = []
        sections.append("## FATES Parameter & Output Context (Targeted)\n")

        # Parameter definitions
        if param_names:
            param_context = self.get_parameter_definitions(
                param_names, include_related=True,
                include_docs=include_docs
            )
            sections.append(param_context)

        # Output definitions
        if output_names:
            output_context = self.get_output_definitions(
                output_names,
                include_controlling_params=True,
                include_docs=False  # Avoid duplicate doc retrieval
            )
            sections.append(output_context)

        # Mechanism context
        if mechanisms:
            mech_parts = []
            for mech_name in mechanisms:
                mech_node = self.knowledge_graph.get_node(f"mechanism:{mech_name}")
                if mech_node:
                    desc = mech_node.get('description', '')
                    params = self.knowledge_graph.get_mechanism_parameters(mech_name)
                    unique_params = list(dict.fromkeys(params))
                    line = f"- **{mech_name}**: {desc}"
                    if unique_params:
                        line += f"\n  Parameters: {', '.join(unique_params[:8])}"
                    mech_parts.append(line)
            if mech_parts:
                sections.append("### Mechanisms\n" + "\n\n".join(mech_parts))

        # PFT context
        if pft is not None:
            pft_params = self.knowledge_graph.get_pft_parameters(pft)
            if pft_params:
                unique_pft_params = list(dict.fromkeys(pft_params))
                sections.append(
                    f"### PFT{pft} Parameters ({len(unique_pft_params)} total)\n"
                    f"First 15: {', '.join(unique_pft_params[:15])}"
                )

        # Relevant documentation (general, not specific to params/outputs)
        if include_docs and (param_names or output_names or mechanisms):
            query_terms = []
            if param_names:
                query_terms.extend(param_names[:3])
            if output_names:
                query_terms.extend(output_names[:3])
            if mechanisms:
                query_terms.extend(mechanisms[:2])

            try:
                doc_results = self.vector_retriever.vector_store.query(
                    ' '.join(query_terms),
                    n_results=3
                )
                if doc_results:
                    doc_parts = []
                    for r in doc_results[:3]:
                        doc_parts.append(
                            f"[{r['source']}] (relevance: {r['relevance']:.2f})\n"
                            f"{r['content'][:500]}"
                        )
                    sections.append(
                        "### Relevant Documentation\n" + "\n\n---\n\n".join(doc_parts)
                    )
            except Exception:
                pass

        return "\n\n".join(sections)

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
    vector_persist_dir: str = None,
    graph_path: str = None,
    rebuild: bool = False
) -> HybridRetriever:
    """
    Factory function to create a hybrid retriever.

    Args:
        knowledge_base_path: Path to knowledge base
        vector_persist_dir: ChromaDB directory. If None, derived from
                            $A2MC_RAG_DIR/chroma_db/$A2MC_RAG_ACTIVE.
        graph_path: Knowledge graph JSON path. If None, derived from
                    $A2MC_RAG_DIR/graphs/$A2MC_RAG_ACTIVE.json.
        rebuild: If True, rebuild both indexes

    Returns:
        Configured HybridRetriever
    """
    if rebuild and vector_persist_dir is not None:
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
