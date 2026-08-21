#!/usr/bin/env python3
"""
Knowledge Extraction Module for A2MC

AI-powered extraction of knowledge from Markdown logs to update the memory system.
This module reads Markdown log files and uses Claude API to identify:
- Discoveries (mechanistic insights)
- Parameter patterns and relationships
- Failed approaches to avoid
- Cautions and recommendations

Works with:
- A2MC phase logs (use_cases/{site}/memory/logs/)
- Pre-A2MC research logs (for bootstrapping knowledge)

Templates:
    This extractor recognizes patterns from templates/logging/:
    - Named discoveries: "Perfect Storm", "Allocation Paradox", "Triple Bottleneck"
    - Mortality component analysis: Hydraulic vs C Starvation decomposition
    - Cross-PFT differential responses: Why one PFT died while another survived
    - Phenology-nutrient uptake interaction: Evergreen vs deciduous strategies
    - Multi-phase time series: ADSP → RGSP → TRANS tracking
    - Pool tracking: P/N/C investigations

The extracted knowledge is automatically added to site-specific memory:
    use_cases/{site}/memory/gained_knowledge/
    - discoveries.json
    - parameters.json
    - experiments.json
    - failed_approaches.json

Usage:
    from tools.extract_knowledge import KnowledgeExtractor

    # For A2MC phase logs
    extractor = KnowledgeExtractor(
        site_dir="use_cases/ELM-FATES_Kougarok"
    )
    extractor.extract_from_phase("diagnosis")

    # For bootstrapping from pre-A2MC logs
    extractor.extract_from_markdown_files([
        "/path/to/20251222a_PFT10_Diagnostic_Findings.md",
        "/path/to/20251223a_PUptake_Tests_Allocation_Paradox.md"
    ])

Author: Jing Tao
Created: January 2026
Updated: January 19, 2026 - Enhanced with template patterns (Perfect Storm, etc.)
"""

import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Union

# Add parent directory to path for imports
_parent_dir = str(Path(__file__).parent.parent)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

try:
    from memory import MemoryManager
except ImportError:
    from memory.manager import MemoryManager

try:
    from tools.phase_logger import PhaseLogger
except ImportError:
    PhaseLogger = None

logger = logging.getLogger(__name__)


# Extraction prompt template for Claude API
EXTRACTION_PROMPT = """You are an expert at extracting structured knowledge from scientific research logs.

## Log Content
{log_content}

## Task
Extract the following from this log:

### 1. Discoveries - New mechanistic insights or findings

Look especially for these NAMED PATTERN TYPES:

- **"Perfect Storm"**: Multi-factor cascading failures (e.g., drought + nutrient stress → vegetation collapse)
- **"Allocation Paradox"**: Counter-intuitive allocation behavior (e.g., higher vmax → lower uptake via PID feedback)
- **"Triple Bottleneck"**: Multiple simultaneous constraints (e.g., P-limited + light-limited + allocation imbalance)
- **Mortality Component Analysis**: Decomposition of mortality (Hydraulic vs C Starvation vs Fire)
- **Cross-PFT Differential Response**: Why one PFT died while another survived under same conditions
- **Phenology-Nutrient Uptake Interaction**: Evergreen (low/persistent) vs Deciduous (high/seasonal) strategies

For each discovery:
- Name: Memorable name (snake_case), use pattern names above if applicable
- Description: What was discovered
- Mechanism: How/why it works (include ASCII diagrams if present)
- Affects: Which outputs/PFTs/variables are affected
- Confidence: 0.0-1.0
- Pattern_type: One of [perfect_storm, allocation_paradox, triple_bottleneck, mortality_analysis, cross_pft_response, phenology_uptake, general]

### 2. Failed Approaches - Things that were tried and failed (DO NOT REPEAT)

- Approach: What was tried (be specific about parameters and directions)
- Why_failed: Why it didn't work (mechanism-based explanation)
- Severity: CRITICAL / HIGH / MEDIUM / LOW
- Alternatives: What to try instead
- Context: Under what conditions this fails (may work in other contexts)

### 3. Parameter Insights - Knowledge about specific parameters

- Parameter: FATES parameter name (fates_*)
- PFT: Which PFT(s) this applies to (or "all")
- Insight: What was learned
- Optimal_range: Recommended value range [min, max] if mentioned
- Interactions: Other parameters it interacts with
- Caution: Any warnings about this parameter

### 4. Cross-PFT Patterns - Differential responses between PFTs

- PFT_comparison: Which PFTs are compared
- Condition: Under what conditions (e.g., "1963-1968 drought")
- Differential_response: How each PFT responded differently
- Explanation: Why they responded differently (mechanism)

### 5. Multi-Phase Patterns - Patterns across simulation phases

- Phase_sequence: Which phases (ADSP, RGSP, TRANS)
- Variable_tracked: What variable was tracked
- Pattern: What pattern was observed
- Critical_event: Key turning point if any

## Response Format
Respond ONLY with valid JSON:
```json
{{
    "discoveries": [
        {{
            "name": "allocation_paradox",
            "description": "Higher uptake efficiency reduces total uptake via PID feedback",
            "mechanism": "vmax_p ↑ → stress ↓ → PID ↓ root alloc → total uptake ↓",
            "affects": ["froot_pft10", "P_uptake"],
            "confidence": 0.95,
            "pattern_type": "allocation_paradox"
        }}
    ],
    "failed_approaches": [
        {{
            "approach": "Doubling vmax_p alone for PFT#10",
            "why_failed": "Triggers Allocation Paradox - PID reduces root allocation",
            "severity": "HIGH",
            "alternatives": ["Combine with storage buffer", "Reduce PID Kp first"],
            "context": "Fails under nutrient stress conditions"
        }}
    ],
    "parameter_insights": [
        {{
            "parameter": "fates_cnp_pid_kp",
            "pft": "10",
            "insight": "Lower values prevent allocation overshoot under nutrient stress",
            "optimal_range": [0.2, 0.4],
            "interactions": ["fates_cnp_vmax_p", "fates_cnp_phos_store_ratio"],
            "caution": "Too low may cause slow response to changing conditions"
        }}
    ],
    "cross_pft_patterns": [
        {{
            "pft_comparison": ["PFT7", "PFT9", "PFT10"],
            "condition": "1963-1968 drought",
            "differential_response": "PFT7 died (98%), PFT9 survived, PFT10 thrived",
            "explanation": "Phenology-mediated nutrient uptake: evergreen (low/persistent) vs deciduous (high/seasonal)"
        }}
    ],
    "multi_phase_patterns": [
        {{
            "phase_sequence": ["ADSP", "RGSP", "TRANS"],
            "variable_tracked": "LITRP (Litter P)",
            "pattern": "Gradual accumulation then spike during drought",
            "critical_event": "1963-1968 drought trapped P in litter"
        }}
    ],
    "summary": "One-sentence summary of the main finding"
}}
```

If a category has no entries, use an empty array [].
Extract ONLY information explicitly stated in the log - do not infer or guess.
Pay special attention to named patterns, ASCII diagrams, and tables."""


class KnowledgeExtractor:
    """
    Extracts knowledge from Markdown logs using AI analysis.

    This class orchestrates the knowledge extraction process:
    1. Read Markdown logs from site-specific directories or arbitrary paths
    2. Send to Claude API for analysis
    3. Extract structured knowledge
    4. Update site-specific memory with new entries
    """

    def __init__(self,
                 site_dir: str = None,
                 api_key: str = None,
                 auto_save: bool = True):
        """
        Initialize the knowledge extractor.

        Args:
            site_dir: Site use_case directory (e.g., "use_cases/ELM-FATES_Kougarok")
            api_key: Claude API key (uses AI_API_KEY env var if not provided)
            auto_save: Whether to automatically save extracted knowledge
        """
        self.auto_save = auto_save

        # Resolve site directory
        if site_dir:
            self.site_dir = Path(site_dir)
        else:
            self.site_dir = Path(os.environ.get('A2MC_USE_CASE_DIR', 'use_cases/ELM-FATES_Kougarok'))

        # Memory directories
        self.log_dir = self.site_dir / "memory" / "logs"
        self.memory_dir = self.site_dir / "memory" / "gained_knowledge"

        # Ensure directories exist
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # Initialize memory manager
        self.memory = MemoryManager(str(self.memory_dir))

        # Initialize phase logger for reading phase logs
        if PhaseLogger:
            try:
                self.phase_logger = PhaseLogger(
                    site_dir=str(self.site_dir),
                    site_name=self.site_dir.name
                )
            except Exception as e:
                logger.warning(f"Could not initialize PhaseLogger: {e}")
                self.phase_logger = None
        else:
            self.phase_logger = None

        # Resolve AI provider settings
        self.provider = os.environ.get('A2MC_AI_PROVIDER', 'anthropic')
        explicit_model = os.environ.get('A2MC_AI_MODEL', '')
        if explicit_model:
            self.model = explicit_model
        else:
            _model_defaults = {
                'anthropic': 'claude-opus-4-20250514',
                'openai': 'gpt-4o',
                'cborg': 'anthropic/claude-sonnet',
            }
            self.model = _model_defaults.get(self.provider, 'claude-opus-4-20250514')

        # Resolve API key (explicit arg > config-derived env var)
        if api_key:
            self.api_key = api_key
        else:
            # Derive key env var name from provider
            key_env = os.environ.get('A2MC_AI_API_KEY_ENV', '')
            if not key_env:
                key_defaults = {
                    'anthropic': 'ANTHROPIC_API_KEY',
                    'openai': 'OPENAI_API_KEY',
                    'cborg': 'CBORG_API_KEY',
                }
                key_env = key_defaults.get(self.provider, 'AI_API_KEY')
            self.api_key = os.environ.get(key_env)

        # Initialize AI client based on provider
        self._client = None
        self._sdk = None
        if self.api_key:
            try:
                if self.provider == 'anthropic':
                    import anthropic
                    kwargs = {'api_key': self.api_key}
                    base_url = os.environ.get('A2MC_AI_BASE_URL', '')
                    if base_url:
                        kwargs['base_url'] = base_url
                    self._client = anthropic.Anthropic(**kwargs)
                    self._sdk = 'anthropic'
                elif self.provider in ('openai', 'cborg'):
                    import openai
                    kwargs = {'api_key': self.api_key}
                    base_url = os.environ.get('A2MC_AI_BASE_URL', '')
                    if base_url:
                        kwargs['base_url'] = base_url
                    elif self.provider == 'cborg':
                        kwargs['base_url'] = 'https://api.cborg.lbl.gov'
                    self._client = openai.OpenAI(**kwargs)
                    self._sdk = 'openai'
                else:
                    logger.warning(f"Unknown AI provider: {self.provider}")
            except ImportError as e:
                logger.warning(f"Required SDK not installed for provider '{self.provider}': {e}")
            except Exception as e:
                logger.warning(f"Could not initialize AI client: {e}")

        logger.info(f"KnowledgeExtractor initialized (site={self.site_dir.name}, "
                   f"provider={self.provider}, api={'available' if self._client else 'not available'})")

    def extract_from_phase(self, phase: Union[int, str]) -> Dict[str, List[Dict]]:
        """
        Extract knowledge from a specific phase's latest log.

        Args:
            phase: Phase number or name (e.g., 3 or "diagnosis")

        Returns:
            Dict with extracted knowledge by category
        """
        if not self.phase_logger:
            logger.error("PhaseLogger not available")
            return self._empty_result()

        # Get latest log path
        log_path = self.phase_logger.get_latest_log(phase)
        if not log_path or not log_path.exists():
            logger.info(f"No logs found for phase {phase}")
            return self._empty_result()

        return self.extract_from_markdown_file(log_path)

    def extract_from_markdown_file(self, file_path: Union[str, Path]) -> Dict[str, List[Dict]]:
        """
        Extract knowledge from a single Markdown file.

        Args:
            file_path: Path to Markdown file

        Returns:
            Dict with extracted knowledge
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return self._empty_result()

        # Read file content
        content = file_path.read_text(encoding='utf-8')
        logger.info(f"Extracting from: {file_path.name} ({len(content)} chars)")

        # Extract using AI
        knowledge = self._extract_with_ai(content, source=file_path.name)

        # Auto-save if enabled
        if self.auto_save and knowledge:
            self._save_knowledge(knowledge, source=file_path.name)

        return knowledge

    def extract_from_markdown_files(self, file_paths: List[Union[str, Path]]) -> Dict[str, List[Dict]]:
        """
        Extract knowledge from multiple Markdown files.

        Args:
            file_paths: List of paths to Markdown files

        Returns:
            Combined dict with extracted knowledge
        """
        all_knowledge = self._empty_result()

        for file_path in file_paths:
            knowledge = self.extract_from_markdown_file(file_path)
            for category, entries in knowledge.items():
                if category in all_knowledge and isinstance(entries, list):
                    all_knowledge[category].extend(entries)

        return all_knowledge

    def bootstrap_from_curated_list(self, curated_file: str, source_dir: str) -> Dict[str, List[Dict]]:
        """
        Bootstrap knowledge from a curated list of log files.

        Args:
            curated_file: Path to curated_list.txt
            source_dir: Directory containing the log files

        Returns:
            Combined extracted knowledge
        """
        curated_path = Path(curated_file)
        source_path = Path(source_dir)

        if not curated_path.exists():
            logger.error(f"Curated list not found: {curated_path}")
            return self._empty_result()

        # Parse curated list
        file_names = []
        with open(curated_path) as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#') or ':' in line:
                    continue
                if line.endswith('.md'):
                    file_names.append(line)

        # Build full paths
        file_paths = []
        for name in file_names:
            full_path = source_path / name
            if full_path.exists():
                file_paths.append(full_path)
            else:
                logger.warning(f"File not found: {full_path}")

        logger.info(f"Found {len(file_paths)} files to process from curated list")

        return self.extract_from_markdown_files(file_paths)

    def _extract_with_ai(self, content: str, source: str = "unknown") -> Dict[str, List[Dict]]:
        """
        Use Claude API to extract knowledge from log content.

        Args:
            content: Markdown content to analyze
            source: Source identifier for logging

        Returns:
            Extracted knowledge dict
        """
        if not self._client:
            logger.error("Claude API client not available")
            return self._empty_result()

        # Truncate very long content
        max_chars = 50000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[TRUNCATED]"

        prompt = EXTRACTION_PROMPT.format(log_content=content)

        try:
            if self._sdk == 'anthropic':
                response = self._client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                response_text = response.content[0].text.strip()
            else:  # openai SDK (openai / cborg providers)
                response = self._client.chat.completions.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                response_text = response.choices[0].message.content.strip()

            # Parse JSON from response
            json_str = response_text
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            knowledge = json.loads(json_str)

            # Add source to each entry
            all_categories = [
                'discoveries', 'failed_approaches', 'parameter_insights',
                'cross_pft_patterns', 'multi_phase_patterns'
            ]
            for category in all_categories:
                for entry in knowledge.get(category, []):
                    entry['source'] = source
                    entry['extracted_at'] = datetime.now().isoformat()

            # Log extraction summary
            n_discoveries = len(knowledge.get('discoveries', []))
            n_failed = len(knowledge.get('failed_approaches', []))
            n_params = len(knowledge.get('parameter_insights', []))
            n_cross_pft = len(knowledge.get('cross_pft_patterns', []))
            n_multi_phase = len(knowledge.get('multi_phase_patterns', []))

            logger.info(f"Extracted from {source}: "
                       f"{n_discoveries} discoveries, "
                       f"{n_failed} failed approaches, "
                       f"{n_params} parameter insights, "
                       f"{n_cross_pft} cross-PFT patterns, "
                       f"{n_multi_phase} multi-phase patterns")

            return knowledge

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response_text[:500]}...")
            return self._empty_result()
        except Exception as e:
            logger.error(f"API call failed: {e}")
            return self._empty_result()

    def _save_knowledge(self, knowledge: Dict, source: str = "extraction"):
        """Save extracted knowledge to memory."""
        # Save discoveries (enhanced with pattern_type)
        for disc in knowledge.get('discoveries', []):
            try:
                # Build metadata dict for pattern_type and other extras
                metadata = {}
                if disc.get('pattern_type'):
                    metadata['pattern_type'] = disc['pattern_type']
                if disc.get('source'):
                    metadata['source'] = disc['source']

                self.memory.add_discovery(
                    name=disc.get('name', f"discovery_{datetime.now().strftime('%Y%m%d%H%M%S')}"),
                    description=disc.get('description', ''),
                    mechanism=disc.get('mechanism', ''),
                    affects=disc.get('affects', []),
                    confidence=disc.get('confidence', 0.7),
                    metadata=metadata
                )
            except Exception as e:
                logger.warning(f"Failed to save discovery: {e}")

        # Save failed approaches (enhanced with context)
        for fa in knowledge.get('failed_approaches', []):
            try:
                self.memory.add_failed_approach(
                    approach=fa.get('approach', ''),
                    experiment_id=source,
                    why_failed=fa.get('why_failed', ''),
                    severity=fa.get('severity', 'MEDIUM'),
                    alternatives=fa.get('alternatives', []),
                    context=fa.get('context', '')
                )
            except Exception as e:
                logger.warning(f"Failed to save failed approach: {e}")

        # Save parameter insights (enhanced with pft, optimal_range, caution)
        for param in knowledge.get('parameter_insights', []):
            try:
                param_name = param.get('parameter', '')
                if param_name:
                    # Build bounds from optimal_range if available
                    bounds = param.get('bounds') or param.get('optimal_range')
                    if isinstance(bounds, list) and len(bounds) == 2:
                        bounds = {'min': bounds[0], 'max': bounds[1]}

                    # Convert pft field to parameter_pft list
                    pft_val = param.get('pft')
                    parameter_pft = None
                    if pft_val is not None:
                        try:
                            parameter_pft = [int(pft_val)]
                        except (ValueError, TypeError):
                            pass

                    self.memory.add_parameter_info(
                        param_name,
                        parameter_pft=parameter_pft,
                        affects_pfts=param.get('affects_pfts'),
                        insights=[param.get('insight', '')],
                        bounds=bounds,
                        interactions=param.get('interactions', []),
                        source=source,
                        caution=param.get('caution')
                    )
            except Exception as e:
                logger.warning(f"Failed to save parameter insight: {e}")

        # Save cross-PFT patterns as discoveries with special pattern_type
        for pattern in knowledge.get('cross_pft_patterns', []):
            try:
                name = f"cross_pft_{'_'.join(pattern.get('pft_comparison', ['unknown']))}"
                description = f"{pattern.get('differential_response', '')} under {pattern.get('condition', 'unknown conditions')}"
                self.memory.add_discovery(
                    name=name.lower().replace(' ', '_'),
                    description=description,
                    mechanism=pattern.get('explanation', ''),
                    affects=pattern.get('pft_comparison', []),
                    confidence=0.8,
                    metadata={'pattern_type': 'cross_pft_response', 'condition': pattern.get('condition')}
                )
            except Exception as e:
                logger.warning(f"Failed to save cross-PFT pattern: {e}")

        # Save multi-phase patterns as discoveries
        for pattern in knowledge.get('multi_phase_patterns', []):
            try:
                name = f"multi_phase_{pattern.get('variable_tracked', 'unknown').replace(' ', '_')}"
                description = f"{pattern.get('pattern', '')} across {', '.join(pattern.get('phase_sequence', []))}"
                self.memory.add_discovery(
                    name=name.lower(),
                    description=description,
                    mechanism=pattern.get('critical_event', ''),
                    affects=[pattern.get('variable_tracked', '')],
                    confidence=0.75,
                    metadata={'pattern_type': 'multi_phase', 'phases': pattern.get('phase_sequence')}
                )
            except Exception as e:
                logger.warning(f"Failed to save multi-phase pattern: {e}")

        logger.info(f"Saved knowledge from {source}")

    def _empty_result(self) -> Dict[str, List[Dict]]:
        """Return empty result structure."""
        return {
            'discoveries': [],
            'failed_approaches': [],
            'parameter_insights': [],
            'cross_pft_patterns': [],
            'multi_phase_patterns': [],
            'summary': ''
        }

    def extract_all_phases(self) -> Dict[str, List[Dict]]:
        """
        Extract knowledge from all phase logs.

        Returns:
            Combined knowledge from all phases
        """
        all_knowledge = self._empty_result()

        for phase_num in range(7):
            knowledge = self.extract_from_phase(phase_num)
            for category, entries in knowledge.items():
                if category in all_knowledge and isinstance(entries, list):
                    all_knowledge[category].extend(entries)

        return all_knowledge

    def generate_knowledge_report(self, output_file: str = None) -> str:
        """
        Generate a human-readable report of all extracted knowledge.

        Args:
            output_file: Optional file path to write report

        Returns:
            Report as string
        """
        report = []
        report.append("=" * 80)
        report.append("A2MC KNOWLEDGE EXTRACTION REPORT")
        report.append(f"Site: {self.site_dir.name}")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        report.append("")

        # Discoveries by pattern type
        discoveries = self.memory.discoveries.get('discoveries', [])
        report.append(f"## DISCOVERIES ({len(discoveries)} total)")
        report.append("-" * 40)

        # Group by pattern type
        pattern_types = {}
        for disc in discoveries:
            ptype = disc.get('metadata', {}).get('pattern_type', 'general')
            if ptype not in pattern_types:
                pattern_types[ptype] = []
            pattern_types[ptype].append(disc)

        # Report by pattern type
        for ptype, discs in pattern_types.items():
            report.append(f"\n### {ptype.upper().replace('_', ' ')} ({len(discs)})")
            for disc in discs[-5:]:  # Show last 5 per type
                report.append(f"  - **{disc.get('name', 'Unknown')}**")
                desc = disc.get('description', '')[:100]
                report.append(f"    {desc}{'...' if len(disc.get('description', '')) > 100 else ''}")
                report.append(f"    Confidence: {disc.get('confidence', 'N/A')}")
                if disc.get('mechanism'):
                    mech = disc['mechanism'][:60]
                    report.append(f"    Mechanism: {mech}...")
                report.append("")

        # Failed approaches
        failed = self.memory.failed_approaches.get('failed_approaches', [])
        report.append(f"\n## FAILED APPROACHES - DO NOT REPEAT ({len(failed)} total)")
        report.append("-" * 40)
        for fa in failed[-10:]:
            approach = fa.get('approach', 'Unknown')[:80]
            report.append(f"  - **{approach}**")
            why = fa.get('why_failed', '')[:80]
            report.append(f"    Why: {why}")
            report.append(f"    Severity: {fa.get('severity', 'unknown')}")
            if fa.get('context'):
                report.append(f"    Context: {fa['context'][:60]}")
            if fa.get('alternatives'):
                report.append(f"    Alternatives: {', '.join(fa['alternatives'][:3])}")
            report.append("")

        # Parameter knowledge
        params = self.memory.parameters.get('parameters', {})
        report.append(f"\n## PARAMETER KNOWLEDGE ({len(params)} parameters)")
        report.append("-" * 40)
        for param, info in list(params.items())[:15]:
            report.append(f"  - **{param}**")
            if info.get('insights'):
                report.append(f"    Insight: {info['insights'][0][:80]}...")
            if info.get('bounds'):
                report.append(f"    Range: {info['bounds']}")
            if info.get('interactions'):
                report.append(f"    Interacts with: {', '.join(info['interactions'][:3])}")
            if info.get('caution'):
                report.append(f"    ⚠️ Caution: {info['caution'][:60]}")
            report.append("")

        report_str = "\n".join(report)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_str)
            logger.info(f"Wrote knowledge report to: {output_file}")

        return report_str


# Convenience functions
def extract_knowledge(site_dir: str = None, phase: Optional[str] = None) -> Dict:
    """
    Convenience function to extract knowledge.

    Args:
        site_dir: Site use_case directory
        phase: Optional specific phase to extract from

    Returns:
        Extracted knowledge dict
    """
    extractor = KnowledgeExtractor(site_dir=site_dir)

    if phase:
        return extractor.extract_from_phase(phase)
    else:
        return extractor.extract_all_phases()


def bootstrap_knowledge(curated_file: str, source_dir: str, site_dir: str) -> Dict:
    """
    Bootstrap knowledge from pre-A2MC logs.

    Args:
        curated_file: Path to curated_list.txt
        source_dir: Directory containing log files
        site_dir: Target site directory for saving knowledge

    Returns:
        Extracted knowledge dict
    """
    extractor = KnowledgeExtractor(site_dir=site_dir)
    return extractor.bootstrap_from_curated_list(curated_file, source_dir)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = argparse.ArgumentParser(description="Extract knowledge from A2MC logs")
    parser.add_argument("--site-dir", default="use_cases/ELM-FATES_Kougarok",
                       help="Site use_case directory")
    parser.add_argument("--phase", type=str, help="Specific phase to extract from")
    parser.add_argument("--bootstrap", action="store_true",
                       help="Bootstrap from pre-A2MC logs")
    parser.add_argument("--curated-file", type=str,
                       help="Path to curated_list.txt for bootstrap")
    parser.add_argument("--source-dir", type=str,
                       help="Directory containing log files for bootstrap")
    parser.add_argument("--report", action="store_true",
                       help="Generate knowledge report")
    parser.add_argument("--files", nargs="+",
                       help="Specific Markdown files to extract from")

    args = parser.parse_args()

    extractor = KnowledgeExtractor(site_dir=args.site_dir)

    def print_extraction_summary(knowledge: Dict):
        """Print extraction summary."""
        print(f"\nExtracted:")
        print(f"  - {len(knowledge.get('discoveries', []))} discoveries")
        print(f"  - {len(knowledge.get('failed_approaches', []))} failed approaches")
        print(f"  - {len(knowledge.get('parameter_insights', []))} parameter insights")
        print(f"  - {len(knowledge.get('cross_pft_patterns', []))} cross-PFT patterns")
        print(f"  - {len(knowledge.get('multi_phase_patterns', []))} multi-phase patterns")

        # Show discovery pattern types
        discoveries = knowledge.get('discoveries', [])
        if discoveries:
            pattern_counts = {}
            for d in discoveries:
                ptype = d.get('pattern_type', 'general')
                pattern_counts[ptype] = pattern_counts.get(ptype, 0) + 1
            print(f"\n  Discovery patterns:")
            for ptype, count in pattern_counts.items():
                print(f"    - {ptype}: {count}")

    if args.bootstrap and args.curated_file and args.source_dir:
        print(f"\nBootstrapping knowledge from: {args.curated_file}")
        knowledge = extractor.bootstrap_from_curated_list(args.curated_file, args.source_dir)
        print_extraction_summary(knowledge)

    elif args.files:
        print(f"\nExtracting from {len(args.files)} files...")
        knowledge = extractor.extract_from_markdown_files(args.files)
        print_extraction_summary(knowledge)

    elif args.phase:
        print(f"\nExtracting from phase: {args.phase}")
        knowledge = extractor.extract_from_phase(args.phase)
        print_extraction_summary(knowledge)
        print(f"\nFull extraction result:")
        print(json.dumps(knowledge, indent=2))

    if args.report:
        print("\n" + extractor.generate_knowledge_report())
