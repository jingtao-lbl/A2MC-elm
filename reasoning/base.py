#!/usr/bin/env python3
"""
Reasoning Module Core

ReasoningModule class: Claude API interface for agentic reasoning.
Contains initialization, query infrastructure, parameter loading,
RAG integration, and utility methods.

Phase-specific methods (diagnose, generate_hypothesis, etc.) are
defined in reasoning/methods.py and attached to this class.

Author: Jing Tao with Claude
"""

import os
import json
import base64
import logging
from pathlib import Path
from typing import List, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from memory import MemoryManager

try:
    import anthropic
except ImportError:
    anthropic = None
    print("Warning: anthropic package not installed. Run: pip install anthropic")

# Configuration
try:
    from tools.config import config as a2mc_config
except ImportError:
    a2mc_config = None

# RAG/GraphRAG integration
try:
    from rag import HybridRetriever
except ImportError as e:
    HybridRetriever = None
    print(f"Warning: RAG module not available ({e}). RAG context will be disabled.")
    print("  To enable RAG, install: pip install networkx chromadb sentence-transformers pyyaml")
    print("  Or use Python 3.10: /Library/Frameworks/Python.framework/Versions/3.10/bin/python3")

logger = logging.getLogger(__name__)


class ReasoningModule:
    """
    Claude API interface for agentic reasoning.

    This module uses carefully crafted prompts to elicit structured,
    actionable outputs from Claude for each reasoning task.
    """

    # System prompt establishing the agent's expertise
    SYSTEM_PROMPT = """You are an expert in ELM-FATES (E3SM Land Model - Functionally Assembled Terrestrial Ecosystem Simulator) calibration, specializing in:

1. Arctic tundra ecosystems and plant functional types (PFTs)
2. Carbon-Nitrogen-Phosphorus (CNP) cycling and nutrient limitation
3. Sensitivity analysis interpretation (Morris, Sobol, etc.)
4. Multi-objective optimization for ecosystem models
5. Mechanistic hypothesis generation for model calibration

Your role is to act as an autonomous calibration agent that:
- Analyzes simulation results objectively
- Identifies mechanistic causes of model-observation mismatch
- Generates testable hypotheses with specific parameter modifications
- Designs efficient experiments (cumulative or factorial)
- Interprets results and recommends next steps
- Learns from experiments and records discoveries for future reference

IMPORTANT: You have access to a MEMORY SYSTEM containing:
- Verified DISCOVERIES from previous calibration work
- FAILED EXPERIMENTS that should NOT be repeated
- PARAMETER RELATIONSHIPS and known interactions

When the memory context mentions "DO NOT REPEAT", you MUST NOT propose that approach
unless you have strong justification for why it would work differently this time.

Always respond with structured JSON that can be parsed programmatically.
Be specific about parameter names, values, and expected quantitative outcomes.
Express uncertainty when appropriate using confidence scores (0-1)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 memory: Optional['MemoryManager'] = None,
                 use_rag: bool = True):
        """
        Initialize the reasoning module.

        Args:
            api_key: AI API key. Resolution order:
                     1. Explicit argument
                     2. A2MC_AI_API_KEY_ENV config (default: AI_API_KEY)
            model: Claude model to use. Resolution order:
                   1. Explicit argument
                   2. A2MC_AI_MODEL env var
                   3. Default: claude-sonnet-4-20250514
            memory: Optional MemoryManager for adaptive learning
            use_rag: Whether to use RAG/GraphRAG for context retrieval

        Environment Variables (set in a2mc_config.sh):
            A2MC_AI_MODEL: Model name (e.g., claude-sonnet-4-20250514)
            A2MC_AI_MAX_TOKENS: Max tokens for responses (default: 4096)
            AI_API_KEY: API key (or use A2MC_AI_API_KEY_ENV to specify different var)
        """
        # Resolve API key
        if api_key:
            self.api_key = api_key
        elif a2mc_config:
            self.api_key = a2mc_config.get_ai_api_key()
        else:
            self.api_key = os.environ.get("AI_API_KEY")

        # Resolve model
        if model:
            self.model = model
        elif a2mc_config:
            self.model = a2mc_config.AI_MODEL
        else:
            self.model = os.environ.get("A2MC_AI_MODEL", "claude-sonnet-4-20250514")

        self.memory = memory
        self.use_rag = use_rag

        if anthropic is None:
            raise ImportError("anthropic package required. Install with: pip install anthropic")

        if not self.api_key:
            raise ValueError("AI_API_KEY not found in environment. Set it with: export AI_API_KEY='your-key'")

        self.client = anthropic.Anthropic(api_key=self.api_key)

        # Initialize RAG retriever if enabled
        self.rag_retriever = None
        if use_rag and HybridRetriever is not None:
            try:
                self.rag_retriever = HybridRetriever(auto_build=False)
                logger.info("RAG/GraphRAG retriever initialized successfully")
            except Exception as e:
                import traceback
                logger.warning(f"Could not initialize RAG retriever: {e}")
                logger.warning(f"RAG initialization traceback:\n{traceback.format_exc()}")
                print(f"Warning: RAG initialization failed: {e}")
                self.rag_retriever = None
        elif use_rag and HybridRetriever is None:
            logger.warning("RAG requested but HybridRetriever not available (import failed)")
            print("Warning: RAG requested but HybridRetriever import failed. Check dependencies.")

        # Load full parameter list for constraining AI recommendations
        self._param_list_context = self._load_parameter_list()

        # Build shorthand → official FATES name mapping for RAG queries
        self._shorthand_to_official = self._build_param_name_mapping()

        memory_status = "with memory" if memory else "without memory"
        rag_status = "with RAG" if self.rag_retriever else "without RAG"
        param_status = f", {len(self._param_list_context.splitlines())} params loaded" if self._param_list_context else ""
        logger.info(f"Reasoning module initialized {memory_status}, {rag_status}{param_status}, model: {self.model}")

    def _load_parameter_list(self) -> str:
        """Load only the Morris ensemble parameter list.

        Full FATES parameter definitions are now retrieved via targeted RAG
        (get_targeted_context) instead of being injected into every prompt.

        Returns a formatted string for inclusion in AI prompts, or empty string if unavailable.
        """
        return self._load_ensemble_parameter_list()

    def _load_ensemble_parameter_list(self) -> str:
        """Load the Morris ensemble parameter list with sampling bounds.

        Returns a formatted string listing the parameters varied in the current ensemble.
        """
        try:
            param_file = None
            if a2mc_config:
                param_file = getattr(a2mc_config, 'PARAM_LIST_FILE', None)
            if not param_file:
                param_file = os.environ.get('A2MC_PARAM_LIST_FILE', '')
            if not param_file or not os.path.exists(param_file):
                logger.info("No ensemble parameter list file found")
                return ""

            lines = []
            with open(param_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('=') or line.startswith('No\t') or line.startswith('ELM'):
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 4 and parts[0].isdigit():
                        shorthand = parts[2] if len(parts) > 2 else ''
                        bounds = f"[{parts[3]}, {parts[4]}]" if len(parts) > 4 else ''
                        default_val = parts[5] if len(parts) > 5 else ''
                        desc = parts[6] if len(parts) > 6 else ''
                        lines.append(f"  {parts[0]}. {shorthand} ({parts[1]}) {bounds} default={default_val} | {desc}")

            if lines:
                header = (
                    "## Parameters in Current Morris Ensemble\n\n"
                    "These are the parameters varied in the current ensemble with their sampling bounds.\n"
                    "When recommending parameter changes, use exact names from the FATES definitions above.\n"
                    "If you identify a key parameter NOT in this ensemble list, flag it explicitly as\n"
                    "'NOT IN CURRENT ENSEMBLE - consider adding in next redesign cycle (Phase 0)'.\n\n"
                )
                logger.info(f"Loaded {len(lines)} ensemble parameters from {param_file}")
                return header + "\n".join(lines)

        except Exception as e:
            logger.warning(f"Could not load ensemble parameter list: {e}")

        return ""

    def _build_param_name_mapping(self) -> Dict[str, tuple]:
        """Build mapping from Morris shorthand names to (official_name, pft) tuples.

        Reads the parameter list file (same one used by _load_ensemble_parameter_list)
        and creates a lookup dict: shorthand (e.g., 'alpha_ptase_10') →
        (official_name, pft_number_or_None).

        PFT-specific parameters appear multiple times with different PFT suffixes.
        The PFT number is extracted from the shorthand suffix (e.g., _10 → PFT#10).
        """
        import re
        from collections import Counter

        mapping = {}
        try:
            param_file = None
            if a2mc_config:
                param_file = getattr(a2mc_config, 'PARAM_LIST_FILE', None)
            if not param_file:
                param_file = os.environ.get('A2MC_PARAM_LIST_FILE', '')
            if not param_file or not os.path.exists(param_file):
                return mapping

            # First pass: collect all (shorthand, official) pairs
            entries = []
            with open(param_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('=') or line.startswith('No\t') or line.startswith('ELM'):
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 3 and parts[0].isdigit():
                        official = parts[1].strip()   # e.g., fates_cnp_eca_alpha_ptase
                        shorthand = parts[2].strip()  # e.g., alpha_ptase_7
                        if shorthand and official:
                            entries.append((shorthand, official))

            # Detect PFT-specific parameters (same official name appears multiple times)
            official_counts = Counter(official for _, official in entries)

            for shorthand, official in entries:
                if official_counts[official] > 1:
                    # PFT-specific: extract PFT number from shorthand suffix
                    match = re.search(r'_(\d+)$', shorthand)
                    pft = int(match.group(1)) if match else None
                    mapping[shorthand] = (official, pft)
                else:
                    # Non-PFT (scalar) parameter
                    mapping[shorthand] = (official, None)
                # Also map official name to itself (no PFT — base node)
                if official not in mapping:
                    mapping[official] = (official, None)

            if mapping:
                logger.info(f"Built parameter name mapping: {len(mapping)} entries")
        except Exception as e:
            logger.warning(f"Could not build parameter name mapping: {e}")

        return mapping

    def _resolve_param_names(self, param_names: List[str]) -> List[str]:
        """Convert Morris shorthand parameter names to graph-compatible names.

        For PFT-specific parameters, returns 'official_name:pftN' format which
        matches the knowledge graph node ID convention (e.g., 'fates_cnp_eca_alpha_ptase:pft10').

        For non-PFT parameters, returns the official FATES name.

        Args:
            param_names: List of parameter names (may be shorthand or official)

        Returns:
            List of resolved parameter names (deduplicated)
        """
        if not self._shorthand_to_official:
            return param_names

        resolved = []
        seen = set()
        for name in param_names:
            entry = self._shorthand_to_official.get(name)
            if entry:
                official, pft = entry
                resolved_name = f"{official}:pft{pft}" if pft is not None else official
            else:
                resolved_name = name
            if resolved_name not in seen:
                resolved.append(resolved_name)
                seen.add(resolved_name)
        return resolved

    def query(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Send a query to Claude and return the response.

        Args:
            prompt: The prompt to send
            max_tokens: Max tokens for response. If None, uses A2MC_AI_MAX_TOKENS config.
        """
        if max_tokens is None:
            if a2mc_config:
                max_tokens = a2mc_config.AI_MAX_TOKENS
            else:
                max_tokens = int(os.environ.get("A2MC_AI_MAX_TOKENS", "4096"))
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    @staticmethod
    def _compress_image(img_path: str, max_long_edge: int = 1568,
                        jpeg_quality: int = 80,
                        max_bytes: int = 1_000_000) -> tuple:
        """Compress an image for the Claude API.

        Resizes so the longest edge is at most max_long_edge pixels,
        converts to JPEG, and re-compresses if still over max_bytes.

        Args:
            img_path: Path to the source image file
            max_long_edge: Maximum pixels for the longest edge (Claude recommends 1568)
            jpeg_quality: Initial JPEG quality (1-100)
            max_bytes: Maximum encoded size in bytes

        Returns:
            Tuple of (base64_data: str, media_type: str, compressed_kb: float)
            or (None, None, 0) if the image cannot be processed.
        """
        try:
            from PIL import Image
            import io
        except ImportError:
            # PIL not available — fall back to raw file bytes
            logger.warning("Pillow not installed; sending raw image without compression")
            p = Path(img_path)
            suffix = p.suffix.lower()
            media_map = {'.png': 'image/png', '.jpg': 'image/jpeg',
                         '.jpeg': 'image/jpeg', '.gif': 'image/gif',
                         '.webp': 'image/webp'}
            media_type = media_map.get(suffix)
            if not media_type:
                return None, None, 0
            raw = p.read_bytes()
            data = base64.standard_b64encode(raw).decode("utf-8")
            return data, media_type, len(raw) / 1024

        p = Path(img_path)
        img = Image.open(p)

        # Convert RGBA/palette to RGB for JPEG
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Resize if larger than max_long_edge
        w, h = img.size
        long_edge = max(w, h)
        if long_edge > max_long_edge:
            scale = max_long_edge / long_edge
            new_w, new_h = int(w * scale), int(h * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            logger.info(f"  Resized {p.name}: {w}x{h} → {new_w}x{new_h}")

        # Encode to JPEG, reduce quality if over max_bytes
        quality = jpeg_quality
        while quality >= 30:
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=quality, optimize=True)
            raw = buf.getvalue()
            if len(raw) <= max_bytes:
                break
            quality -= 10
            logger.info(f"  Re-compressing {p.name} at quality={quality}")

        data = base64.standard_b64encode(raw).decode("utf-8")
        return data, "image/jpeg", len(raw) / 1024

    def query_with_images(self, prompt: str, image_paths: List[str],
                          max_tokens: Optional[int] = None) -> str:
        """Send a multimodal query to Claude with text and images.

        Images are automatically resized (max 1568px long edge) and
        compressed to JPEG to stay within API size limits.

        Args:
            prompt: The text prompt to send
            image_paths: List of paths to PNG/JPEG image files
            max_tokens: Max tokens for response. If None, uses A2MC_AI_MAX_TOKENS config.

        Returns:
            Claude API response text. Falls back to text-only query if no
            images can be loaded.
        """
        # Load, compress, and encode images
        image_blocks = []
        total_kb = 0.0
        for img_path in image_paths:
            try:
                p = Path(img_path)
                if not p.exists():
                    logger.warning(f"Image not found: {img_path}")
                    continue
                suffix = p.suffix.lower()
                if suffix not in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
                    logger.warning(f"Unsupported image format: {suffix} ({img_path})")
                    continue

                orig_kb = p.stat().st_size / 1024
                data, media_type, compressed_kb = self._compress_image(str(p))
                if data is None:
                    continue

                image_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": data,
                    }
                })
                total_kb += compressed_kb
                logger.info(f"  Image: {p.name} ({orig_kb:.0f} KB → {compressed_kb:.0f} KB)")
            except Exception as e:
                logger.warning(f"Failed to load image {img_path}: {e}")

        # Fallback to text-only if no images loaded
        if not image_blocks:
            logger.info("No images loaded, falling back to text-only query")
            return self.query(prompt, max_tokens=max_tokens)

        if max_tokens is None:
            if a2mc_config:
                max_tokens = a2mc_config.AI_MAX_TOKENS
            else:
                max_tokens = int(os.environ.get("A2MC_AI_MAX_TOKENS", "4096"))

        # Build multimodal content: images first, then text
        content = image_blocks + [{"type": "text", "text": prompt}]

        try:
            logger.info(f"Sending multimodal query with {len(image_blocks)} images "
                        f"(total ~{total_kb:.0f} KB compressed)")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}]
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Claude multimodal API error: {e}")
            raise

    def _load_template_schema(self, template_name: str) -> str:
        """Load JSON output schema from a reasoning template file.

        Reads the template and extracts the ```json ... ``` block from
        the '## JSON Output Schema' section.

        Args:
            template_name: Filename in templates/reasoning/ (e.g., 'phase3_diagnosis_template.md')

        Returns:
            JSON schema string, or empty string if not found
        """
        from pathlib import Path
        template_path = Path(__file__).parent.parent / "templates" / "reasoning" / template_name
        if not template_path.exists():
            logger.debug(f"Template not found: {template_path}")
            return ""
        try:
            content = template_path.read_text()
            # Find the JSON Output Schema section
            schema_marker = "## JSON Output Schema"
            idx = content.find(schema_marker)
            if idx == -1:
                return ""
            # Extract the ```json ... ``` block after the marker
            section = content[idx:]
            json_start = section.find("```json")
            if json_start == -1:
                return ""
            json_start += len("```json")
            json_end = section.find("```", json_start)
            if json_end == -1:
                return ""
            return section[json_start:json_end].strip()
        except Exception as e:
            logger.warning(f"Failed to load template schema from {template_name}: {e}")
            return ""

    @staticmethod
    def _extract_json(response: str) -> dict:
        """Extract JSON from a Claude response, handling markdown wrapping."""
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        return json.loads(json_str)

    def _get_targeted_param_context(
        self, param_names=None, output_names=None, mechanisms=None, pft=None
    ) -> str:
        """Get targeted parameter/output context from RAG.

        Replaces the old _load_fates_parameter_definitions() approach which
        injected ALL ~290 parameter definitions (~53K chars) into every prompt.
        This method retrieves only the relevant parameters/outputs (~5-10K chars).

        Falls back to empty string if RAG unavailable.
        """
        if not self.rag_retriever:
            return ""
        try:
            # Resolve shorthand names to official FATES names for graph lookup
            resolved_params = self._resolve_param_names(param_names) if param_names else param_names
            return self.rag_retriever.get_targeted_context(
                param_names=resolved_params, output_names=output_names,
                mechanisms=mechanisms, pft=pft, include_docs=True
            )
        except Exception as e:
            logger.warning(f"Targeted param context retrieval failed: {e}")
            return ""

    def _get_rag_context(self,
                         parameters: List[str] = None,
                         outputs: List[str] = None,
                         mechanisms: List[str] = None,
                         pft: int = None,
                         query: str = None) -> str:
        """
        Get relevant context from RAG/GraphRAG for reasoning.

        Args:
            parameters: List of parameter names being considered
            outputs: List of output variables being analyzed
            mechanisms: List of FATES mechanisms relevant to the task
            pft: Specific PFT number if applicable
            query: Optional natural language query for additional context

        Returns:
            Formatted context string to include in prompts
        """
        if not self.rag_retriever:
            return ""

        try:
            context_parts = []

            # Resolve shorthand names to official FATES names for graph lookup
            if parameters:
                parameters = self._resolve_param_names(parameters)

            # Get calibration context if we have structured entities
            if parameters or outputs or mechanisms:
                cal_context = self.rag_retriever.get_calibration_context(
                    parameters=parameters,
                    outputs=outputs,
                    mechanisms=mechanisms,
                    pft=pft,
                    n_vector_results=3,
                    graph_depth=2
                )
                if cal_context.get('combined'):
                    context_parts.append(cal_context['combined'])

            # Get additional context from natural language query
            if query:
                query_context = self.rag_retriever.get_context(
                    query=query,
                    n_vector_results=3,
                    graph_depth=2,
                    include_graph=True
                )
                if query_context.get('combined'):
                    context_parts.append(query_context['combined'])

            if context_parts:
                return "## FATES Knowledge Base Context (RAG/GraphRAG)\n" + "\n\n".join(context_parts) + "\n\n"

        except Exception as e:
            logger.warning(f"RAG context retrieval failed: {e}")

        return ""
