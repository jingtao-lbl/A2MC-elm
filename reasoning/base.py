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
import re
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

try:
    import openai as openai_module
except ImportError:
    openai_module = None

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
                 generic_memory: Optional['MemoryManager'] = None,
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
        # Resolve provider
        if a2mc_config:
            self.provider = a2mc_config.AI_PROVIDER
            self.base_url = a2mc_config.AI_BASE_URL
        else:
            self.provider = os.environ.get('A2MC_AI_PROVIDER', 'anthropic')
            self.base_url = os.environ.get('A2MC_AI_BASE_URL', '') or None

        # Resolve API key
        if api_key:
            self.api_key = api_key
        elif a2mc_config:
            self.api_key = a2mc_config.get_ai_api_key()
        else:
            self.api_key = os.environ.get("AI_API_KEY")

        # Resolve model (auto-derive from provider if not set)
        if model:
            self.model = model
        elif a2mc_config:
            self.model = a2mc_config.AI_MODEL
        else:
            explicit = os.environ.get("A2MC_AI_MODEL", "")
            if explicit:
                self.model = explicit
            else:
                _model_defaults = {
                    'anthropic': 'claude-opus-4-20250514',
                    'openai': 'gpt-4o',
                    'cborg': 'anthropic/claude-sonnet',
                }
                self.model = _model_defaults.get(self.provider, 'claude-opus-4-20250514')

        self.memory = memory
        self.generic_memory = generic_memory
        self.use_rag = use_rag

        if not self.api_key:
            key_env = a2mc_config.AI_API_KEY_ENV if a2mc_config else 'AI_API_KEY'
            raise ValueError(f"API key not found. Set it with: export {key_env}='your-key'")

        # Create client based on provider
        if self.provider == 'anthropic':
            if anthropic is None:
                raise ImportError("anthropic package required. Install: pip install anthropic")
            kwargs = {'api_key': self.api_key}
            if self.base_url:
                kwargs['base_url'] = self.base_url
            self.client = anthropic.Anthropic(**kwargs)
            self._sdk = 'anthropic'
        elif self.provider in ('openai', 'cborg'):
            if openai_module is None:
                raise ImportError("openai package required. Install: pip install openai")
            kwargs = {'api_key': self.api_key}
            if self.base_url:
                kwargs['base_url'] = self.base_url
            elif self.provider == 'cborg':
                kwargs['base_url'] = 'https://api.cborg.lbl.gov'
            self.client = openai_module.OpenAI(**kwargs)
            self._sdk = 'openai'
        else:
            raise ValueError(f"Unknown AI provider: {self.provider}. "
                             f"Supported: anthropic, openai, cborg")

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
        logger.info(f"Reasoning module initialized {memory_status}, {rag_status}{param_status}, "
                    f"provider: {self.provider}, model: {self.model}")

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

    def _load_base_case_parameters(self, case_id: int) -> Dict[str, float]:
        """Read actual parameter values for a specific Morris ensemble case.

        Lightweight reader that reads only the needed line from the ensemble
        matrix file, without requiring numpy. Uses the same parameter list file
        as _load_ensemble_parameter_list to get shorthand names.

        Args:
            case_id: Case number (1-indexed, e.g., 322)

        Returns:
            Dict mapping shorthand parameter name to value, e.g.:
            {'vmax_p_9': 5.0e-05, 'pid_kp_10': 0.001, ...}
            Returns empty dict if files not found or case_id invalid.
        """
        try:
            # Get file paths from config
            ensemble_file = None
            param_file = None
            if a2mc_config:
                ensemble_file = getattr(a2mc_config, 'ENSEMBLE_MATRIX_FILE', None)
                param_file = getattr(a2mc_config, 'PARAM_LIST_FILE', None)
            if not ensemble_file:
                ensemble_file = os.environ.get('A2MC_ENSEMBLE_MATRIX_FILE', '')
            if not param_file:
                param_file = os.environ.get('A2MC_PARAM_LIST_FILE', '')

            if not ensemble_file or not os.path.exists(ensemble_file):
                logger.info(f"Ensemble matrix file not found: {ensemble_file}")
                return {}
            if not param_file or not os.path.exists(param_file):
                logger.info(f"Parameter list file not found: {param_file}")
                return {}

            # Read parameter shorthand names from param list file
            param_names = []
            with open(param_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('=') or line.startswith('No\t') or line.startswith('ELM'):
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 3 and parts[0].isdigit():
                        param_names.append(parts[2].strip())  # shorthand name

            if not param_names:
                logger.warning("No parameter names found in parameter list file")
                return {}

            # Read only the target line from ensemble matrix (0-indexed line = case_id - 1)
            target_line_idx = case_id - 1
            if target_line_idx < 0:
                logger.warning(f"Invalid case_id {case_id} (must be >= 1)")
                return {}

            values_line = None
            with open(ensemble_file) as f:
                for i, line in enumerate(f):
                    if i == target_line_idx:
                        values_line = line.strip()
                        break

            if values_line is None:
                logger.warning(f"Case {case_id} not found in ensemble file (only {i+1} lines)")
                return {}

            # Parse values (space or tab delimited)
            values = values_line.split()
            n_params = min(len(param_names), len(values))
            result = {}
            for j in range(n_params):
                try:
                    result[param_names[j]] = float(values[j])
                except (ValueError, IndexError):
                    continue

            logger.info(f"Read {len(result)} parameter values for case #{case_id}")
            return result

        except Exception as e:
            logger.warning(f"Could not read base case parameters for case {case_id}: {e}")
            return {}

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

        Uses streaming to avoid the 10-minute timeout on long requests
        (e.g., multimodal diagnosis with many images + large max_tokens).

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
            if self._sdk == 'anthropic':
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=self.SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}]
                ) as stream:
                    return stream.get_final_text()
            else:  # openai SDK (openai / cborg providers)
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI API error ({self.provider}): {e}")
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

        try:
            logger.info(f"Sending multimodal query with {len(image_blocks)} images "
                        f"(total ~{total_kb:.0f} KB compressed)")

            if self._sdk == 'anthropic':
                # Anthropic format: image blocks + text block
                content = image_blocks + [{"type": "text", "text": prompt}]
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=self.SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": content}]
                ) as stream:
                    return stream.get_final_text()
            else:  # openai SDK (openai / cborg providers)
                # OpenAI vision format: convert Anthropic image blocks to data URLs
                oai_content = []
                for block in image_blocks:
                    src = block["source"]
                    data_url = f"data:{src['media_type']};base64,{src['data']}"
                    oai_content.append({
                        "type": "image_url",
                        "image_url": {"url": data_url}
                    })
                oai_content.append({"type": "text", "text": prompt})
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": oai_content}
                    ]
                )
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI multimodal API error ({self.provider}): {e}")
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
        """Extract JSON from a Claude response, handling markdown wrapping.

        Five-tier repair strategy (each progressively more aggressive):
        1. Direct parse (fast path for valid JSON)
        2. Escape literal newlines/tabs inside JSON strings
        3. Remove trailing commas before } or ]
        4. Fix unescaped double quotes inside JSON strings
        5. Repair truncated JSON (close open brackets/braces)
        """
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]

        # Tier 1: Direct parse
        first_err = None
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            first_err = e

        # Tier 2: Escape literal newlines/tabs inside JSON strings.
        # Claude sometimes produces multi-line string values which are
        # invalid JSON (strings must use \n, not literal newlines).
        fixed = ReasoningModule._escape_newlines_in_strings(json_str)
        if fixed != json_str:
            try:
                result = json.loads(fixed)
                logger.warning("Fixed literal newlines in JSON string values")
                return result
            except json.JSONDecodeError:
                pass
        else:
            fixed = json_str

        # Tier 3: Remove trailing commas (e.g., {"a": 1,} → {"a": 1}).
        no_trailing = re.sub(r',(\s*[}\]])', r'\1', fixed)
        if no_trailing != fixed:
            try:
                result = json.loads(no_trailing)
                logger.warning("Fixed trailing commas in JSON")
                return result
            except json.JSONDecodeError:
                pass
        else:
            no_trailing = fixed

        # Tier 4: Fix unescaped double quotes inside JSON strings.
        # Claude sometimes puts Python code or quoted text in JSON string
        # values without escaping the quotes — e.g., "he said "hello""
        # which should be "he said \"hello\"". This causes "Expecting ','
        # delimiter" because the parser thinks the string ended early.
        quote_fixed = ReasoningModule._fix_unescaped_quotes(no_trailing)
        if quote_fixed != no_trailing:
            try:
                result = json.loads(quote_fixed)
                logger.warning("Fixed unescaped double quotes in JSON string values")
                return result
            except json.JSONDecodeError:
                pass

        # Tier 5: Attempt truncated JSON repair (close open structures)
        repaired = ReasoningModule._repair_truncated_json(json_str)
        if repaired is not None:
            logger.warning("Repaired truncated JSON response (likely max_tokens cutoff)")
            return repaired

        # All repairs failed — log context around the error position
        pos = first_err.pos if hasattr(first_err, 'pos') else None
        if pos is not None:
            start = max(0, pos - 200)
            end = min(len(json_str), pos + 200)
            context = json_str[start:end]
            marker_pos = pos - start
            logger.error(
                f"JSON parse error at char {pos}. Context (char {start}-{end}):\n"
                f"{context}\n"
                f"{' ' * marker_pos}^ ERROR HERE"
            )
        else:
            logger.error(f"JSON parse failed. First 500 chars: {json_str[:500]}")
        logger.error(f"Full response length: {len(json_str)} chars")

        raise first_err

    @staticmethod
    def _escape_newlines_in_strings(json_str: str) -> str:
        """Escape literal newlines and tabs inside JSON string values.

        Walks the JSON character by character, tracking whether we're inside
        a quoted string. Replaces literal \\n and \\t with \\\\n and \\\\t
        only when inside strings. Leaves structural whitespace untouched.
        """
        result = []
        in_string = False
        escaped = False
        for ch in json_str:
            if escaped:
                result.append(ch)
                escaped = False
                continue
            if ch == '\\' and in_string:
                result.append(ch)
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string:
                if ch == '\n':
                    result.append('\\n')
                    continue
                if ch == '\t':
                    result.append('\\t')
                    continue
                if ch == '\r':
                    result.append('\\r')
                    continue
            result.append(ch)
        return ''.join(result)

    @staticmethod
    def _fix_unescaped_quotes(json_str: str) -> str:
        """Fix unescaped double quotes inside JSON string values.

        Walks character by character, tracking in-string state. When a "
        inside a string is NOT followed by a JSON structural token
        (: , } ] or whitespace then one of these), it's likely an embedded
        quote from Python code or natural language — replace with \\".

        Common cause: Claude embeds Python scripts in script_code fields
        with unescaped quotes, e.g.:
            "script_code": "x = df[df["col"] > 0]"
        should be:
            "script_code": "x = df[df[\\"col\\"] > 0]"
        """
        result = []
        i = 0
        n = len(json_str)
        in_string = False

        while i < n:
            ch = json_str[i]

            if not in_string:
                result.append(ch)
                if ch == '"':
                    in_string = True
                i += 1
                continue

            # Inside a string
            if ch == '\\':
                # Escape sequence — copy verbatim
                result.append(ch)
                i += 1
                if i < n:
                    result.append(json_str[i])
                    i += 1
                continue

            if ch != '"':
                result.append(ch)
                i += 1
                continue

            # ch == '"' inside a string — structural close or embedded quote?
            # Look ahead past whitespace to see what follows
            j = i + 1
            while j < n and json_str[j] in ' \t\n\r':
                j += 1

            if j >= n:
                # End of input — must be structural close
                result.append('"')
                in_string = False
                i += 1
                continue

            next_ch = json_str[j]

            if next_ch in ':,':
                # Colon or comma after quote — always structural
                result.append('"')
                in_string = False
                i += 1
                continue

            if next_ch in '}]':
                # Bracket/brace after quote — could be JSON structural close
                # OR Python code like df["col"] > 0. Check what follows the
                # } or ] to confirm: if it's another structural token or EOF,
                # it's real JSON; otherwise it's embedded code.
                k = j + 1
                while k < n and json_str[k] in ' \t\n\r':
                    k += 1
                if k >= n or json_str[k] in ':,}]':
                    # Proper JSON continuation → structural close
                    result.append('"')
                    in_string = False
                else:
                    # More content follows (e.g., "> 0]") → embedded quote
                    result.append('\\"')
                i += 1
                continue

            if next_ch == '"':
                # Two consecutive quotes. Look past the second to decide:
                # if the char after the second quote is structural → first
                # quote is the real string close; otherwise → embedded quotes.
                k = j + 1
                while k < n and json_str[k] in ' \t\n\r':
                    k += 1
                if k >= n or json_str[k] in ':,}]':
                    # Second quote followed by structural → close string
                    result.append('"')
                    in_string = False
                else:
                    # Both quotes are embedded
                    result.append('\\"')
                i += 1
                continue

            # Next char is a letter, digit, etc. — this quote is embedded
            result.append('\\"')
            i += 1

        return ''.join(result)

    @staticmethod
    def _repair_truncated_json(json_str: str):
        """Try to repair truncated JSON by closing open brackets/braces.

        Returns parsed dict/list on success, None on failure.
        """
        # Also try with escaped newlines first
        s = ReasoningModule._escape_newlines_in_strings(json_str)
        s = s.rstrip()

        # Strip trailing incomplete fragments back to last valid value char
        # Valid value endings: } ] " digits true/false/null
        while s and s[-1] not in ('}', ']', '"', '0', '1', '2', '3', '4',
                                   '5', '6', '7', '8', '9', 'e', 'l', 'n',
                                   '{', '['):
            s = s[:-1]
        if not s:
            return None
        # Remove trailing comma if present
        s = s.rstrip().rstrip(',')
        # Close any unterminated string
        in_string = False
        escaped = False
        for ch in s:
            if escaped:
                escaped = False
                continue
            if ch == '\\':
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
        if in_string:
            s += '"'
        # Close open brackets/braces
        stack = []
        in_str = False
        esc = False
        for ch in s:
            if esc:
                esc = False
                continue
            if ch == '\\' and in_str:
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch in ('{', '['):
                stack.append('}' if ch == '{' else ']')
            elif ch in ('}', ']'):
                if stack:
                    stack.pop()
        # Append closing characters in reverse order
        s += ''.join(reversed(stack))
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None

    def _get_targeted_param_context(
        self, param_names=None, output_names=None, mechanisms=None, pft=None
    ) -> str:
        """Get targeted parameter/output context from RAG.

        Replaces the old _load_fates_parameter_definitions() approach which
        injected ALL ~290 parameter definitions (~53K chars) into every prompt.
        This method retrieves only the relevant parameters/outputs (~5-10K chars).

        Reads simulation mode (Doc 20 Phase A + Phase B) and applies:
          - kb_source filter for ELM-only runs (Phase A)
          - mode-aware where clause filtering chunks tagged inapplicable to
            the active mode (Phase B)

        Falls back to empty string if RAG unavailable.
        """
        if not self.rag_retriever:
            return ""
        config_mode = self._get_active_config_mode()
        kb_source = config_mode.kb_source_filter() if config_mode else None
        try:
            # Resolve shorthand names to official FATES names for graph lookup
            resolved_params = self._resolve_param_names(param_names) if param_names else param_names
            return self.rag_retriever.get_targeted_context(
                param_names=resolved_params, output_names=output_names,
                mechanisms=mechanisms, pft=pft, include_docs=True,
                kb_source=kb_source,
                config_mode=config_mode,
            )
        except Exception as e:
            logger.warning(f"Targeted param context retrieval failed: {e}")
            return ""

    def _get_active_config_mode(self):
        """Read ConfigMode from env (Phase B). Cached per call.

        Returns None if ConfigMode cannot be parsed (e.g., invalid env state).
        Callers handle None gracefully (no filtering applied).
        """
        try:
            from tools.config import ConfigMode
            return ConfigMode.from_env()
        except Exception as e:
            logger.warning(f"ConfigMode.from_env() failed: {e}; skipping mode filter")
            return None

    def _mode_kb_source_filter(self) -> Optional[str]:
        """Read ConfigMode from env and return kb_source filter (or None).

        Phase A backward-compat shim. New code should use
        ``_get_active_config_mode()`` and call ``.kb_source_filter()`` on
        the result; this preserves the old call sites unchanged.
        """
        config_mode = self._get_active_config_mode()
        return config_mode.kb_source_filter() if config_mode else None

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

        # Phase B: read ConfigMode once per call; pass through to all RAG calls
        config_mode = self._get_active_config_mode()
        kb_source_filter = config_mode.kb_source_filter() if config_mode else None

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
                    graph_depth=2,
                    config_mode=config_mode,
                )
                if cal_context.get('combined'):
                    context_parts.append(cal_context['combined'])

            # Get additional context from natural language query
            if query:
                query_context = self.rag_retriever.get_context(
                    query=query,
                    n_vector_results=3,
                    graph_depth=2,
                    include_graph=True,
                    kb_source=kb_source_filter,
                    config_mode=config_mode,
                )
                if query_context.get('combined'):
                    context_parts.append(query_context['combined'])

            if context_parts:
                return "## FATES Knowledge Base Context (RAG/GraphRAG)\n" + "\n\n".join(context_parts) + "\n\n"

        except Exception as e:
            logger.warning(f"RAG context retrieval failed: {e}")

        return ""
