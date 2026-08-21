"""
Memory Manager for A2MC Adaptive Memory System

Provides the main interface for:
- Querying relevant discoveries and experiment history
- Recording new experiments and their outcomes
- Adding new discoveries (curated or auto-discovered)
- Checking do-not-repeat approaches
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .store import load_json, save_json

logger = logging.getLogger(__name__)

# Write-mode gate for curated Tier-3 Adaptive Memory.
#   "interactive" — human-in-the-loop (offline agent + curation tools): curated
#                   writes (discoveries / failed_approaches / experiments) land in
#                   the curated JSONs as before.
#   "propose"     — autonomous online agent (orchestrator): the same writes are
#                   routed to a staging file (auto_discovered_pending.json) for
#                   human review + promotion, never the curated JSONs.
# Rationale + history: memory/dev_logs/20260612d_Memory_Write_Gate_Interactive_Only_Curated.md
WRITE_MODES = ("interactive", "propose")
PENDING_FILENAME = "auto_discovered_pending.json"


class MemoryManager:
    """
    Adaptive memory system for A2MC calibration framework.

    Provides persistent storage and retrieval of:
    - Discoveries: Mechanistic insights from calibration work
    - Experiments: History of experiments with outcomes
    - Parameters: Parameter relationships and constraints
    - Failed approaches: DO NOT REPEAT list

    Attributes:
        data_dir: Path to data directory
        discoveries: Dict of discovery entries
        experiments: Dict with "experiments" list
        parameters: Dict of parameter entries
        failed_approaches: Dict with "failed_approaches" list
    """

    def __init__(self, data_dir: str, write_mode: Optional[str] = None):
        """
        Initialize memory manager.

        Args:
            data_dir: Path to data directory containing JSON files
            write_mode: Curated-write gate, "interactive" or "propose". If None,
                resolves from env A2MC_MEMORY_WRITE_MODE, else defaults to
                "interactive". In "propose" mode, curated writes
                (add_discovery / add_failed_approach / record_experiment) are
                routed to the staging file instead of the curated JSONs.
                See WRITE_MODES and memory/dev_logs/20260612d_*.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        resolved_mode = (write_mode
                         or os.environ.get("A2MC_MEMORY_WRITE_MODE")
                         or "interactive")
        if resolved_mode not in WRITE_MODES:
            logger.warning(
                f"Unknown memory write_mode {resolved_mode!r}; "
                f"falling back to 'interactive'. Valid: {WRITE_MODES}"
            )
            resolved_mode = "interactive"
        self.write_mode = resolved_mode

        # Load all data stores
        self.discoveries = load_json(
            self.data_dir / "discoveries.json",
            default={}
        )
        self.experiments = load_json(
            self.data_dir / "experiments.json",
            default={"experiments": []}
        )
        self.parameters = load_json(
            self.data_dir / "parameters.json",
            default={"parameters": {}}
        )
        self.failed_approaches = load_json(
            self.data_dir / "failed_approaches.json",
            default={"failed_approaches": []}
        )

        n_disc = sum(1 for v in self.discoveries.values() if isinstance(v, dict))
        logger.info(f"MemoryManager initialized with {n_disc} discoveries, "
                   f"{len(self.experiments.get('experiments', []))} experiments "
                   f"(write_mode={self.write_mode})")

    # ==================== QUERY METHODS ====================

    def get_relevant_context(self, failing_targets: Optional[List[str]] = None,
                            max_chars: int = 8000,
                            targets: Optional[List[str]] = None,
                            parameters: Optional[List[str]] = None,
                            verified_only: bool = False) -> str:
        """
        Get discoveries and lessons relevant to current failures or parameters.

        Args:
            failing_targets: List of target names that are failing
                            (e.g., ["froot_pft10", "leaf_pft10"])
                            Deprecated: use 'targets' instead
            max_chars: Maximum characters in returned context
            targets: List of target/output variable names
            parameters: List of parameter names to find relevant knowledge for
            verified_only: When True, only curated/verified knowledge shapes the output —
                discoveries with verified=True and experiments with source="curated". The
                read-side complement to the write gate; G6 / Q4 (read-side `verified_only`)
                capability. NOTE: capability only — NOT yet wired to the diagnosis call site,
                because the current baseline is all verified=False (enabling it would empty
                the discoveries). Activate after the baseline verified-flip (Q8). Default
                False keeps the legacy unfiltered behavior (backward-compatible).

        Returns:
            Formatted string with relevant discoveries and warnings
        """
        # Support both old and new argument names
        target_list = targets or failing_targets or []

        sections = []

        # 1. Find relevant discoveries (verified first, then auto-discovered)
        relevant_discoveries = self._find_relevant_discoveries(target_list)

        # Also find discoveries by parameters if provided
        if parameters:
            param_discoveries = self._find_discoveries_by_parameters(parameters)
            # Merge without duplicates
            existing_names = {name for name, _ in relevant_discoveries}
            for name, disc in param_discoveries:
                if name not in existing_names:
                    relevant_discoveries.append((name, disc))

        # Read-side gate: only verified discoveries shape the answer when requested.
        if verified_only:
            relevant_discoveries = [(n, d) for (n, d) in relevant_discoveries
                                    if d.get("verified") is True]

        if relevant_discoveries:
            sections.append("## Relevant Discoveries from Previous Calibration\n")

            # Sort: verified first, then by confidence
            sorted_disc = sorted(
                relevant_discoveries,
                key=lambda x: (not x[1].get("verified", False),
                              -x[1].get("confidence", 0))
            )

            for name, disc in sorted_disc[:5]:  # Limit to top 5
                verified_str = "VERIFIED" if disc.get("verified") else "needs review"
                conf = disc.get("confidence", "?")
                sections.append(f"### {name} (confidence: {conf}, {verified_str})")
                sections.append(f"**Description:** {disc.get('description', 'N/A')}")

                if disc.get("mechanism"):
                    # Truncate long mechanisms
                    mech = disc["mechanism"]
                    if len(mech) > 300:
                        mech = mech[:300] + "..."
                    sections.append(f"**Mechanism:** {mech}")

                if disc.get("affects_pfts"):
                    sections.append(f"**Affected PFTs:** {', '.join(f'PFT#{p}' for p in disc['affects_pfts'])}")

                if disc.get("affects"):
                    sections.append(f"**Affected variables:** {', '.join(disc['affects'])}")

                if disc.get("implications"):
                    sections.append("**Implications:**")
                    for imp in disc["implications"][:3]:
                        sections.append(f"- {imp}")

                if disc.get("do_not_repeat"):
                    sections.append("**DO NOT REPEAT:**")
                    for dnr in disc["do_not_repeat"]:
                        sections.append(f"- {dnr}")

                sections.append("")

        # 2. Find failed experiments for these targets
        failed_experiments = self._find_failed_experiments(target_list)

        # Also find failed experiments by parameters if provided
        if parameters:
            param_failed = self.get_failed_experiments(parameters)
            # Merge without duplicates
            existing_ids = {e.get('id') for e in failed_experiments}
            for exp in param_failed:
                if exp.get('id') not in existing_ids:
                    failed_experiments.append(exp)

        # Read-side gate: only curated experiment records when requested.
        if verified_only:
            failed_experiments = [e for e in failed_experiments
                                  if e.get("source") == "curated"]

        if failed_experiments:
            sections.append("## Failed Experiments (DO NOT REPEAT)\n")

            for exp in failed_experiments[:5]:  # Limit to 5
                sections.append(f"### {exp.get('id', 'Unknown')}")

                if exp.get("modifications"):
                    mods_str = ", ".join(
                        f"{m.get('parameter', '?')}: {m.get('old_value', '?')} -> {m.get('new_value', '?')}"
                        for m in exp["modifications"][:3]
                    )
                    sections.append(f"**Modifications:** {mods_str}")

                sections.append(f"**Outcome:** {exp.get('outcome', 'FAILED')}")

                if exp.get("lesson"):
                    sections.append(f"**Lesson:** {exp['lesson']}")

                if exp.get("repeat_warning"):
                    sections.append(f"**WARNING:** {exp['repeat_warning']}")

                sections.append("")

        # 3. Add failed approaches summary
        if self.failed_approaches.get("failed_approaches"):
            sections.append("## Approaches to Avoid\n")
            for fa in self.failed_approaches["failed_approaches"][:5]:
                sections.append(f"- **{fa.get('approach', '?')}**: {fa.get('why_failed', 'Failed')}")
            sections.append("")

        # 4. Add parameter-specific knowledge if parameters provided
        if parameters:
            param_knowledge_sections = []
            for param in parameters[:10]:  # Limit to 10 parameters
                param_lower = self._strip_pft_suffix(param.lower())
                for p_name, p_data in self.parameters.get("parameters", {}).items():
                    if param_lower in p_name.lower() or p_name.lower() in param_lower:
                        # Build header with PFT context
                        header = f"### {p_name}"
                        pft_info = p_data.get("parameter_pft")
                        if pft_info:
                            header += f" (PFT {', '.join(f'#{p}' for p in pft_info)})"
                        param_knowledge_sections.append(header)

                        # Show insights (Schema A: list of strings)
                        for ins in p_data.get("insights", [])[:3]:
                            param_knowledge_sections.append(f"- {ins}")

                        # Show knowledge entries (Schema B: list of dicts)
                        for k in p_data.get("knowledge", [])[:3]:
                            param_knowledge_sections.append(
                                f"- [{k.get('type', '?')}] {k.get('content', '')}"
                            )

                        # Show cautions
                        for c in p_data.get("cautions", [])[:2]:
                            param_knowledge_sections.append(f"- **CAUTION:** {c}")

                        param_knowledge_sections.append("")

            if param_knowledge_sections:
                sections.append("## Parameter-Specific Knowledge\n")
                sections.extend(param_knowledge_sections)

        context = "\n".join(sections)

        # Truncate if too long
        if len(context) > max_chars:
            context = context[:max_chars] + "\n\n[Context truncated...]"

        return context

    def get_failed_experiments(self, parameters: List[str]) -> List[Dict]:
        """
        Get experiments that failed when modifying specified parameters.

        Args:
            parameters: List of parameter names being considered

        Returns:
            List of failed experiment records
        """
        failed = []
        param_set = set(p.lower() for p in parameters)

        for exp in self.experiments.get("experiments", []):
            if exp.get("outcome") not in ["FAILED", "catastrophic_collapse"]:
                continue

            # Check if any modification involves these parameters
            for mod in exp.get("modifications", []):
                param_name = mod.get("parameter", "").lower()
                if any(p in param_name for p in param_set):
                    failed.append(exp)
                    break

        return failed

    def get_parameter_cautions(self, parameters: List[str]) -> Dict[str, List[str]]:
        """
        Get cautions/warnings for specific parameters.

        Args:
            parameters: List of parameter names

        Returns:
            Dict mapping parameter names to list of cautions
        """
        cautions = {}

        for param in parameters:
            param_lower = param.lower()
            param_cautions = []

            # Check parameter definitions (strip PFT suffix for matching)
            stripped = self._strip_pft_suffix(param_lower)
            for p_name, p_data in self.parameters.get("parameters", {}).items():
                if stripped in p_name.lower() or p_name.lower() in stripped:
                    param_cautions.extend(p_data.get("cautions", []))

            # Check discoveries that implicate this parameter
            for name, disc in self._discovery_entries().items():
                params_involved = [p.lower() for p in disc.get("parameters_involved", [])]
                if any(param_lower in p for p in params_involved):
                    if disc.get("do_not_repeat"):
                        param_cautions.extend(
                            f"[{name}] {dnr}" for dnr in disc["do_not_repeat"]
                        )

            if param_cautions:
                cautions[param] = param_cautions

        return cautions

    def check_do_not_repeat(self, proposed_modifications: List[Dict]) -> List[Dict]:
        """
        Check if proposed modifications match any failed approaches.

        Args:
            proposed_modifications: List of {parameter, old_value, new_value}

        Returns:
            List of matching failed approaches with warnings
        """
        warnings = []

        for mod in proposed_modifications:
            param = mod.get("parameter", "").lower()
            new_value = mod.get("new_value")
            old_value = mod.get("old_value")

            # Calculate multiplier if both values are numeric
            multiplier = None
            if isinstance(new_value, (int, float)) and isinstance(old_value, (int, float)):
                if old_value != 0:
                    multiplier = new_value / old_value

            # Check failed approaches
            for fa in self.failed_approaches.get("failed_approaches", []):
                approach_lower = fa.get("approach", "").lower()

                # Simple pattern matching
                if param in approach_lower:
                    # Check for similar multipliers (e.g., "10x increase")
                    if multiplier and multiplier > 5 and "10" in approach_lower:
                        warnings.append({
                            "modification": mod,
                            "matched_approach": fa,
                            "warning": fa.get("why_failed", "Previously failed")
                        })

        return warnings

    def get_discovery(self, name: str) -> Optional[Dict]:
        """Get a specific discovery by name."""
        return self.discoveries.get(name)

    def get_all_discoveries(self, verified_only: bool = False) -> Dict[str, Dict]:
        """Get all discoveries, optionally filtering to verified only."""
        entries = self._discovery_entries()
        if verified_only:
            return {k: v for k, v in entries.items()
                   if v.get("verified", False)}
        return entries

    # ==================== UPDATE METHODS ====================

    def record_experiment(self, experiment: Dict, results: Dict,
                         outcome: str, lesson: Optional[str] = None) -> str:
        """
        Record an experiment and its outcome.

        Args:
            experiment: Experiment specification with name, modifications, etc.
            results: Actual results from simulation
            outcome: One of: success, partial_success, no_effect, degradation,
                     catastrophic_collapse, FAILED
            lesson: Optional lesson extracted (can be added later)

        Returns:
            Experiment ID
        """
        exp_id = experiment.get("name", f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

        record = {
            "id": exp_id,
            "source": "auto_discovered",
            "date": datetime.now().isoformat(),
            "base_case": experiment.get("base_case"),
            "hypothesis": experiment.get("hypothesis"),
            "modifications": experiment.get("modifications", []),
            "results": results,
            "outcome": outcome,
            "lesson": lesson,
            "do_not_repeat": outcome in ["FAILED", "catastrophic_collapse"]
        }

        # Add warning for catastrophic failures
        if outcome == "catastrophic_collapse":
            record["repeat_warning"] = "CATASTROPHIC FAILURE - DO NOT REPEAT"

        # Write-mode gate: autonomous online agent proposes; only the interactive
        # (human-in-the-loop) agent writes curated knowledge. Routing to staging
        # here also suppresses the catastrophic add_failed_approach cascade below.
        # See 20260612d.
        if self.write_mode == "propose":
            self._stage("experiment", exp_id, record)
            return exp_id

        # Update existing entry with same ID (avoid duplicates), or append new
        existing_idx = None
        for i, existing in enumerate(self.experiments["experiments"]):
            if existing.get("id") == exp_id:
                existing_idx = i
                break
        if existing_idx is not None:
            self.experiments["experiments"][existing_idx] = record
            logger.debug(f"Updated existing experiment record: {exp_id}")
        else:
            self.experiments["experiments"].append(record)
        self._save("experiments.json", self.experiments)

        logger.info(f"Recorded experiment: {exp_id} (outcome: {outcome})")

        # Auto-add to failed approaches if catastrophic
        if outcome == "catastrophic_collapse":
            self.add_failed_approach(
                approach=self._summarize_modifications(experiment.get("modifications", [])),
                experiment_id=exp_id,
                why_failed=lesson or "Catastrophic failure",
                severity="catastrophic",
                alternatives=[]
            )

        return exp_id

    def update_experiment_lesson(self, experiment_id: str, lesson: str) -> bool:
        """
        Update the lesson for an existing experiment.

        Args:
            experiment_id: ID of experiment to update
            lesson: Lesson learned from experiment

        Returns:
            True if experiment found and updated
        """
        for exp in self.experiments.get("experiments", []):
            if exp.get("id") == experiment_id:
                exp["lesson"] = lesson
                self._save("experiments.json", self.experiments)
                logger.info(f"Updated lesson for experiment: {experiment_id}")
                return True

        logger.warning(f"Experiment not found: {experiment_id}")
        return False

    def add_discovery(self, name: str, description: str, mechanism: str,
                     affects: List[str], implications: Optional[List[str]] = None,
                     parameters_involved: Optional[List[str]] = None,
                     do_not_repeat: Optional[List[str]] = None,
                     source: str = "auto_discovered",
                     confidence: float = 0.6,
                     references: Optional[List[str]] = None,
                     verified: Optional[bool] = None,
                     verified_by: str = "") -> None:
        """
        Add a new discovery to memory.

        Args:
            name: Short identifier (e.g., "allocation_paradox")
            description: One-line description
            mechanism: Detailed mechanistic explanation
            affects: List of outputs affected (e.g., ["froot_pft10"])
            implications: List of actionable implications
            parameters_involved: List of related parameters
            do_not_repeat: List of approaches to avoid
            source: "curated" or "auto_discovered"
            confidence: 0-1 confidence score (default 0.6 for auto)
            references: List of reference file paths
            verified: Explicit verified flag (docs/33 §3b). When None, defaults to
                source == "curated" (legacy behavior). A diagnosis/hypothesis is NOT
                verified until a Phase-5 test confirms it — pass verified=True ONLY
                with a verified_by link (feedback_no_kb_injection_before_verified_test).
            verified_by: The Phase-5 test / experiment id / topic-stem that verified this
                finding. Required for verified=True; recorded for provenance.
        """
        # docs/33 §3b gate: an EXPLICIT verified=True must cite what verified it.
        # verified=None keeps legacy behavior (source == "curated") so existing callers
        # are grandfathered; the gate applies to the updated promote/inject paths that pass
        # verified explicitly.
        if verified is True and not verified_by:
            raise ValueError(
                f"add_discovery('{name}'): verified=True requires a verified_by link "
                f"(a Phase-5 test / experiment id). A diagnosis or hypothesis is a "
                f"hypothesis until a test confirms it — pass verified_by, or write it "
                f"unverified (verified=False). See feedback_no_kb_injection_before_verified_test."
            )
        is_verified = verified if verified is not None else (source == "curated")
        entry = {
            "source": source,
            "confidence": confidence,
            "verified": is_verified,
            "verified_by": verified_by,
            "date_added": datetime.now().isoformat(),
            "description": description,
            "mechanism": mechanism,
            "affects": affects,
            "implications": implications or [],
            "parameters_involved": parameters_involved or [],
            "do_not_repeat": do_not_repeat or [],
            "references": references or []
        }

        # Write-mode gate: autonomous online agent proposes; only the interactive
        # (human-in-the-loop) agent writes curated knowledge. See 20260612d.
        if self.write_mode == "propose":
            self._stage("discovery", name, entry)
            return

        self.discoveries[name] = entry
        self._save("discoveries.json", self.discoveries)
        logger.info(f"Added discovery: {name} (source: {source}, confidence: {confidence})")

    def add_failed_approach(self, approach: str, experiment_id: str,
                           why_failed: str, severity: str,
                           alternatives: List[str]) -> None:
        """
        Add an approach to the do-not-repeat list.

        Args:
            approach: Description of the approach
            experiment_id: ID of experiment that revealed this
            why_failed: Explanation of why it failed
            severity: "catastrophic", "degradation", "no_effect"
            alternatives: List of alternative approaches to try
        """
        record = {
            "approach": approach,
            "experiment_id": experiment_id,
            "why_failed": why_failed,
            "severity": severity,
            "alternatives": alternatives,
            "date_added": datetime.now().isoformat()
        }

        # Write-mode gate: autonomous online agent proposes; only the interactive
        # (human-in-the-loop) agent writes curated knowledge. See 20260612d.
        if self.write_mode == "propose":
            self._stage("failed_approach", approach, record)
            return

        # Dedupe: update existing entry with same (approach, experiment_id) pair
        # to prevent duplicates when Phase 6 re-runs after a crash
        existing_idx = None
        for i, existing in enumerate(self.failed_approaches["failed_approaches"]):
            if (existing.get("approach") == approach and
                existing.get("experiment_id") == experiment_id):
                existing_idx = i
                break

        if existing_idx is not None:
            self.failed_approaches["failed_approaches"][existing_idx] = record
            logger.debug(f"Updated existing failed approach: {approach[:60]}")
        else:
            self.failed_approaches["failed_approaches"].append(record)
            logger.info(f"Added failed approach: {approach}")
        self._save("failed_approaches.json", self.failed_approaches)

    def update_discovery_verification(self, name: str, verified: bool,
                                      new_confidence: Optional[float] = None) -> bool:
        """
        Mark a discovery as verified (or not) by user.

        Args:
            name: Discovery name
            verified: Whether discovery is verified
            new_confidence: Optional new confidence score

        Returns:
            True if discovery found and updated
        """
        if name not in self.discoveries:
            logger.warning(f"Discovery not found: {name}")
            return False

        self.discoveries[name]["verified"] = verified
        if new_confidence is not None:
            self.discoveries[name]["confidence"] = new_confidence

        self._save("discoveries.json", self.discoveries)
        logger.info(f"Updated verification for {name}: verified={verified}")
        return True

    def add_parameter_info(self, name: str, parameter_pft: Optional[List[int]] = None,
                           affects_pfts: Optional[List[int]] = None, **attributes) -> None:
        """
        Add or update parameter information.

        Args:
            name: Parameter name (official FATES name, no PFT suffix)
            parameter_pft: List of PFT IDs whose knob was turned (e.g., [10])
            affects_pfts: List of PFT IDs that respond to changes (e.g., [7, 9, 10])
            **attributes: Parameter attributes (insights, bounds, interactions, etc.)
        """
        if name not in self.parameters["parameters"]:
            self.parameters["parameters"][name] = {}

        entry = self.parameters["parameters"][name]
        if parameter_pft is not None:
            entry["parameter_pft"] = parameter_pft
        if affects_pfts is not None:
            entry["affects_pfts"] = affects_pfts
        entry.update(attributes)
        self._save("parameters.json", self.parameters)

    def add_parameter_knowledge(self, parameter: str, knowledge_type: str,
                                 content: str, confidence: float = 0.7,
                                 source: str = "auto_discovered") -> None:
        """
        Add knowledge entry for a specific parameter.

        Used by sensitivity analysis and other AI methods to record
        parameter-specific insights.

        Args:
            parameter: Parameter name (e.g., "fates_cnp_pid_kp")
            knowledge_type: Type of knowledge (e.g., "sensitivity", "interaction",
                           "calibration_advice", "caution")
            content: Description of the knowledge
            confidence: Confidence score 0-1
            source: Source of knowledge ("auto_discovered", "curated", "sensitivity_analysis")
        """
        if parameter not in self.parameters["parameters"]:
            self.parameters["parameters"][parameter] = {
                "knowledge": [],
                "cautions": []
            }

        param_data = self.parameters["parameters"][parameter]

        # Ensure knowledge list exists
        if "knowledge" not in param_data:
            param_data["knowledge"] = []

        # Add knowledge entry
        entry = {
            "type": knowledge_type,
            "content": content,
            "confidence": confidence,
            "source": source,
            "date_added": datetime.now().isoformat()
        }
        param_data["knowledge"].append(entry)

        # If this is a caution, also add to cautions list
        if knowledge_type == "caution":
            if "cautions" not in param_data:
                param_data["cautions"] = []
            param_data["cautions"].append(content)

        self._save("parameters.json", self.parameters)
        logger.info(f"Added {knowledge_type} knowledge for parameter: {parameter}")

    # ==================== PERSISTENCE ====================

    def _save(self, filename: str, data: Any) -> None:
        """Save data to JSON file."""
        save_json(self.data_dir / filename, data)

    def _stage(self, kind: str, key: str, entry: Dict[str, Any]) -> None:
        """
        Append a proposed curated entry to the staging file instead of writing
        the curated JSON. Used in write_mode="propose" (autonomous online agent).
        The interactive agent reviews + promotes via tools/review_pending_knowledge.py.
        """
        path = self.data_dir / PENDING_FILENAME
        pending = load_json(path, default={"pending": []})
        pending["pending"].append({
            "kind": kind,                 # "discovery" | "failed_approach" | "experiment"
            "key": key,                   # discovery name / approach / experiment id
            "staged_at": datetime.now().isoformat(),
            "session": os.environ.get("A2MC_SESSION_ID", ""),
            "verified": False,
            "promoted": False,
            "entry": entry,
        })
        save_json(path, pending)
        logger.info(
            f"[propose mode] staged {kind} '{key}' -> {PENDING_FILENAME} "
            f"(NOT written to curated KB; awaiting human review/promotion)"
        )

    def save_all(self) -> None:
        """Save all data stores to disk."""
        self._save("discoveries.json", self.discoveries)
        self._save("experiments.json", self.experiments)
        self._save("parameters.json", self.parameters)
        self._save("failed_approaches.json", self.failed_approaches)
        logger.info("Saved all memory stores")

    def reload(self) -> None:
        """Reload all data from disk."""
        self.discoveries = load_json(self.data_dir / "discoveries.json", default={})
        self.experiments = load_json(self.data_dir / "experiments.json",
                                     default={"experiments": []})
        self.parameters = load_json(self.data_dir / "parameters.json",
                                    default={"parameters": {}})
        self.failed_approaches = load_json(self.data_dir / "failed_approaches.json",
                                           default={"failed_approaches": []})
        logger.info("Reloaded all memory stores")

    # ==================== STATS ====================

    def stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "discoveries": {
                "total": len(self._discovery_entries()),
                "verified": sum(1 for d in self._discovery_entries().values()
                               if d.get("verified")),
                "auto_discovered": sum(1 for d in self._discovery_entries().values()
                                      if d.get("source") == "auto_discovered")
            },
            "experiments": {
                "total": len(self.experiments.get("experiments", [])),
                "failed": sum(1 for e in self.experiments.get("experiments", [])
                             if e.get("outcome") in ["FAILED", "catastrophic_collapse"]),
                "successful": sum(1 for e in self.experiments.get("experiments", [])
                                 if e.get("outcome") == "success")
            },
            "parameters": len(self.parameters.get("parameters", {})),
            "failed_approaches": len(self.failed_approaches.get("failed_approaches", []))
        }

    # ==================== PRIVATE HELPERS ====================

    @staticmethod
    def _strip_pft_suffix(name: str) -> str:
        """Strip a trailing PFT suffix from a parameter name, for key matching.

        Stored knowledge keys are bare parameter names (`fates_cnp_pid_kp`); PFT
        specificity lives in separate fields, never in the key. A *query* may still
        arrive suffixed (`fates_cnp_pid_kp_10`), so normalize it before lookup.

        Matches any trailing `_<digits>`, deliberately: the previous form hardcoded
        `_(?:7|9|10)$` — the api-31 arctic PFT ids — so on api-43, whose arctic PFTs
        are 10/11/12, queries for PFT 11 and 12 silently failed to match while 10
        worked only because the two eras happen to share it. PFT ids are not stable
        across model versions, so enumerating them here is always wrong for some
        version (`feedback_verify_pft_identity_across_versions`,
        `feedback_derive_pft_count_never_hardcode`).

        Safe against real names: no parameter in the api-43 list, and no stored key,
        ends in `_<digits>` (checked 2026-08-19 — 0 of 58 names, 0 of 49 keys).
        """
        import re
        return re.sub(r'_\d+$', '', name)

    def _discovery_entries(self) -> Dict[str, Dict]:
        """Return discovery entries as {name: dict}, handling both storage formats.

        discoveries.json supports two formats:
        1. Array format: {"discoveries": [{id, name, ...}, ...]}
           - Used by generic knowledge (memory/gained_knowledge/discoveries.json)
           - Keyed by 'id' field (e.g., 'suplphos_rgsp_for_p_limitation')
        2. Flat format: {"discovery_name": {source, confidence, ...}, ...}
           - Used by site-specific knowledge (use_cases/{site}/.../discoveries.json)
           - Key is the discovery name itself

        Both formats may coexist in the same file. Metadata fields (strings, lists)
        at the top level are filtered out.
        """
        entries = {}
        # Handle array format: "discoveries" key containing a list of dicts
        disc_array = self.discoveries.get("discoveries", [])
        if isinstance(disc_array, list):
            for item in disc_array:
                if isinstance(item, dict) and item.get("id"):
                    entries[item["id"]] = item
        # Handle flat format: top-level keys that are dicts (skip metadata strings)
        for k, v in self.discoveries.items():
            if k.startswith("_") or k == "discoveries":
                continue
            if isinstance(v, dict):
                entries[k] = v
        return entries

    def _find_relevant_discoveries(self, targets: List[str]) -> List[tuple]:
        """Find discoveries relevant to given targets.

        Maps validation target names (e.g., 'PFT10_fineroot') to FATES variable
        families (FATES_FROOTC, FATES_FROOTC_PF, FATES_FROOTC_SZPF) for matching
        against discovery 'affects' fields that use official FATES/ELM variable names.
        Also filters by 'affects_pfts' when both discovery and targets specify PFTs.
        """
        relevant = []
        if not targets:
            return relevant

        target_set = set(t.lower() for t in targets)
        target_vars = set()   # FATES variable names (lowered)
        target_pfts = set()   # PFT IDs (1-indexed ints)

        # Map validation targets to FATES variable families
        try:
            from tools.fates_output_variables import resolve_target_name, get_variable_family
            import re
            for t in targets:
                match = re.match(r"PFT(\d+)_(\w+)", t)
                if match:
                    pft_id = int(match.group(1))
                    target_pfts.add(pft_id)
                    var_type = match.group(2).lower()
                    try:
                        canonical = resolve_target_name(var_type)
                        family = get_variable_family(canonical)
                        for var in [family.site_var, family.pft_var, family.szpf_var]:
                            if var:
                                target_vars.add(var.lower())
                    except KeyError:
                        pass
        except ImportError:
            pass

        # Combine original target names + resolved FATES variable names
        all_search_terms = target_set | target_vars

        for name, disc in self._discovery_entries().items():
            affects = [a.lower() for a in disc.get("affects", [])]
            # Check variable name match (substring matching for flexibility)
            var_match = any(
                t in affects or any(t in a for a in affects)
                for t in all_search_terms
            )
            if not var_match:
                continue

            # Filter by affects_pfts if both sides specify PFTs
            disc_pfts = disc.get("affects_pfts")
            if disc_pfts and target_pfts:
                if not target_pfts.intersection(disc_pfts):
                    continue

            relevant.append((name, disc))

        return relevant

    def _find_discoveries_by_parameters(self, parameters: List[str]) -> List[tuple]:
        """Find discoveries that involve specified parameters."""
        relevant = []
        if not parameters:
            return relevant

        param_set = set(p.lower() for p in parameters)

        for name, disc in self._discovery_entries().items():
            params_involved = [p.lower() for p in disc.get("parameters_involved", [])]
            # Check if any of the specified parameters are involved
            if any(any(p in pi or pi in p for pi in params_involved) for p in param_set):
                relevant.append((name, disc))

        return relevant

    def _find_failed_experiments(self, targets: List[str]) -> List[Dict]:
        """Find failed experiments related to given targets."""
        failed = []
        target_set = set(t.lower() for t in targets)

        for exp in self.experiments.get("experiments", []):
            if exp.get("outcome") not in ["FAILED", "catastrophic_collapse"]:
                continue

            # Check if experiment results include these targets
            results = exp.get("results", {})
            if any(t.lower() in results for t in targets):
                failed.append(exp)
                continue

            # Check if modifications affect related parameters
            for mod in exp.get("modifications", []):
                param = mod.get("parameter", "").lower()
                if any(t.split("_")[-1] in param for t in target_set):  # e.g., "pft10" in param
                    failed.append(exp)
                    break

        return failed

    def _summarize_modifications(self, modifications: List[Dict]) -> str:
        """Create a summary string of modifications."""
        if not modifications:
            return "Unknown modifications"

        summaries = []
        for mod in modifications[:3]:
            param = mod.get("parameter", "?")
            old_val = mod.get("old_value", "?")
            new_val = mod.get("new_value", "?")

            # Calculate multiplier for numeric values
            if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
                if old_val != 0:
                    mult = new_val / old_val
                    if mult > 1:
                        summaries.append(f"{param} increased {mult:.1f}x")
                    else:
                        summaries.append(f"{param} decreased to {mult:.2f}x")
                else:
                    summaries.append(f"{param}: {old_val} -> {new_val}")
            else:
                summaries.append(f"{param}: {old_val} -> {new_val}")

        return "; ".join(summaries)
