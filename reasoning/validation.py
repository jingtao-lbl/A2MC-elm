#!/usr/bin/env python3
"""
Hypothesis & Experiment Validation Module

Two-layer validation for AI-generated hypotheses and experiment designs:

Layer 1 (Python, zero API cost):
  - Auto-fix wrong "current" values from actual base case data
  - Detect out-of-bounds proposed values, extreme magnitudes, PFT mismatches
  - Re-prompt Claude once if unfixable errors found

Layer 2 (AI self-review, ~800 tokens):
  - Only for synthesized experiments going to HPC (high stakes)
  - Quick plausibility check: conflicts? too aggressive? physically realistic?

Author: Jing Tao with Claude
Created: February 2026
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    """A single validation issue found in a parameter."""
    parameter: str
    check: str          # e.g. "current value", "bounds", "magnitude", "pft mismatch"
    severity: str       # "auto_fix", "warning", "error"
    detail: str         # Human-readable description
    old_value: object = None   # Value before fix (for auto_fix)
    new_value: object = None   # Value after fix (for auto_fix)


@dataclass
class ValidationResult:
    """Aggregated result of validating a hypothesis or experiment."""
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def n_auto_fixed(self) -> int:
        return sum(1 for i in self.issues if i.severity == "auto_fix")

    @property
    def n_warnings(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def n_errors(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def has_errors(self) -> bool:
        return self.n_errors > 0

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0

    def summary(self) -> str:
        return (f"{self.n_auto_fixed} auto-fixed, "
                f"{self.n_warnings} warning(s), "
                f"{self.n_errors} error(s)")

    def to_dict(self) -> Dict:
        return {
            'n_auto_fixed': self.n_auto_fixed,
            'n_warnings': self.n_warnings,
            'n_errors': self.n_errors,
            'issues': [
                {
                    'parameter': i.parameter,
                    'check': i.check,
                    'severity': i.severity,
                    'detail': i.detail,
                }
                for i in self.issues
            ],
        }


# ---------------------------------------------------------------------------
# Parameter bounds loader
# ---------------------------------------------------------------------------

def load_parameter_bounds(param_file: str = None) -> Dict[str, Dict]:
    """Parse the parameter list file into a lookup dict.

    Args:
        param_file: Path to the parameter list file (tab-separated).
                    If None, reads from A2MC_PARAM_LIST_FILE env var.

    Returns:
        Dict mapping shorthand name → {lower_bound, upper_bound, default, pft, fates_name}.
        Example: {'vmax_p_9': {'lower_bound': 5e-11, 'upper_bound': 5e-05,
                               'default': 5e-10, 'pft': 9, 'fates_name': 'fates_cnp_eca_vmax_p'}}
    """
    if not param_file:
        # Try config first, then env var
        try:
            from tools.config import config as a2mc_config
            param_file = getattr(a2mc_config, 'PARAM_LIST_FILE', None)
        except Exception:
            pass
        if not param_file:
            param_file = os.environ.get('A2MC_PARAM_LIST_FILE', '')

    if not param_file or not os.path.exists(param_file):
        logger.warning(f"Parameter list file not found: {param_file}")
        return {}

    bounds = {}
    with open(param_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('=') or line.startswith('No\t') or line.startswith('ELM'):
                continue
            parts = line.split('\t')
            if len(parts) >= 5 and parts[0].isdigit():
                fates_name = parts[1].strip() if len(parts) > 1 else ''
                shorthand = parts[2].strip() if len(parts) > 2 else ''
                try:
                    lower = float(parts[3])
                    upper = float(parts[4])
                except (ValueError, IndexError):
                    continue
                default = None
                if len(parts) > 5:
                    try:
                        default = float(parts[5])
                    except ValueError:
                        pass

                # Extract PFT from shorthand suffix (e.g., "vmax_p_9" → 9)
                pft = _extract_pft_from_shorthand(shorthand)
                # Extract organ from shorthand (e.g., "stoich_phos_leaf_9" → 1)
                organ = _extract_organ_from_shorthand(shorthand, pft)

                bounds[shorthand] = {
                    'lower_bound': lower,
                    'upper_bound': upper,
                    'default': default,
                    'pft': pft,
                    'organ': organ,
                    'fates_name': fates_name,
                }

    logger.info(f"Loaded bounds for {len(bounds)} parameters from {param_file}")
    return bounds


def _extract_pft_from_shorthand(shorthand: str) -> Optional[int]:
    """Extract PFT number from parameter shorthand suffix.

    Examples:
        'vmax_p_9' → 9
        'pid_kp_10' → 10
        'alpha_ptase_7' → 7
        'some_global_param' → None
    """
    match = re.search(r'_(\d+)$', shorthand)
    if match:
        return int(match.group(1))
    return None


# Organ names used in shorthand naming convention (e.g., stoich_phos_leaf_9)
_ORGAN_NAMES = {'leaf': 1, 'fineroot': 2, 'sapwood': 3, 'storage': 4}


def _extract_organ_from_shorthand(shorthand: str, pft: Optional[int]) -> Optional[int]:
    """Extract organ index from shorthand name.

    Organ name must immediately precede the PFT suffix.

    Examples:
        'stoich_phos_leaf_9' → 1 (leaf)
        'stoich_phos_fineroot_7' → 2 (fineroot)
        'alloc_storage_cushion_10' → None (storage is part of param name, not organ)
        'phos_retrans_7' → None (retrans has no organ in shorthand)
    """
    if pft is None:
        return None
    pft_suffix = f'_{pft}'
    for organ_name, organ_idx in _ORGAN_NAMES.items():
        if shorthand.endswith(f'_{organ_name}{pft_suffix}'):
            return organ_idx
    return None


def find_bounds_entry(
    fates_name: str,
    pft: Optional[int],
    organ: Optional[int],
    param_bounds: Dict[str, Dict],
) -> Optional[Dict]:
    """Find bounds entry for a FATES parameter by (fates_name, pft, organ).

    This resolves the naming mismatch between AI-generated parameters
    (which use FATES names like 'fates_stoich_phos' + pft + organ)
    and the bounds dict (keyed by shorthands like 'stoich_phos_leaf_9').

    Args:
        fates_name: Official FATES parameter name (e.g., 'fates_stoich_phos')
        pft: PFT number (1-indexed) or None for global params
        organ: Organ index (1=leaf, 2=fineroot, ...) or None
        param_bounds: Output of load_parameter_bounds()

    Returns:
        Bounds entry dict, or None if not found.
    """
    for shorthand, entry in param_bounds.items():
        if entry.get('fates_name') != fates_name:
            continue
        if pft is not None and entry.get('pft') != pft:
            continue
        if organ is not None and entry.get('organ') is not None:
            if entry['organ'] != organ:
                continue
        elif organ is not None and entry.get('organ') is None:
            # Organ requested but entry has no organ info — could still match
            # for retrans params where shorthand has no organ (e.g., phos_retrans_7)
            pass
        return entry
    return None


# ---------------------------------------------------------------------------
# Layer 1: Python validation (zero API cost)
# ---------------------------------------------------------------------------

def expand_retrans_parameters(hypothesis: Dict) -> int:
    """Expand retrans parameters tagged with _expand_retrans into leaf+fineroot entries.

    When a retranslocation parameter (fates_cnp_turnover_nitr_retrans or
    fates_cnp_turnover_phos_retrans) is proposed without an organ, validation
    marks it with ``_expand_retrans=True``.  This function replaces that single
    entry with two entries — one for organ=1 (leaf) and one for organ=2
    (fineroot) — both with the same proposed value.

    Mutates hypothesis['parameters'] in place.

    Returns:
        Number of parameters expanded (each counts as 1 → 2 entries).
    """
    params = hypothesis.get('parameters', [])
    if not params:
        return 0

    expanded_count = 0
    new_params = []
    for p in params:
        if p.pop('_expand_retrans', False):
            # Create leaf entry (organ=1)
            leaf_entry = dict(p)
            leaf_entry['organ'] = 1
            new_params.append(leaf_entry)
            # Create fineroot entry (organ=2)
            froot_entry = dict(p)
            froot_entry['organ'] = 2
            new_params.append(froot_entry)
            expanded_count += 1
            logger.info(f"Auto-expanded '{p.get('name', '?')}' PFT {p.get('pft', '?')} "
                        f"→ organ=1 (leaf) + organ=2 (fineroot), value={p.get('proposed', '?')}")
        else:
            new_params.append(p)

    if expanded_count:
        hypothesis['parameters'] = new_params
    return expanded_count


def validate_hypothesis_parameters(
    hypothesis: Dict,
    base_case_params: Dict[str, float],
    param_bounds: Dict[str, Dict],
) -> ValidationResult:
    """Validate and auto-fix parameters in a hypothesis dict.

    Checks each parameter in hypothesis['parameters'] for:
    - Wrong "current" value vs actual base case → auto-fix
    - Wrong "bounds" field → auto-fix
    - Proposed value out of bounds → error
    - PFT mismatch (suffix ≠ pft field) → error
    - Magnitude > 1000x change → error
    - Magnitude 100-1000x change → warning
    - Missing organ for organ-dependent params → error (or auto-expand for retrans)

    Auto-fixes mutate the hypothesis dict in place.

    Args:
        hypothesis: Dict with 'parameters' key (list of param dicts).
        base_case_params: Actual parameter values from ensemble, e.g.
                          {'vmax_p_9': 5e-05, ...}
        param_bounds: Output of load_parameter_bounds().

    Returns:
        ValidationResult with all issues found.
    """
    result = ValidationResult()
    params = hypothesis.get('parameters', [])
    if not params:
        return result

    for param in params:
        _validate_single_parameter(param, base_case_params, param_bounds, result)

    # --- Check: Duplicate parameter names without PFT disambiguation ---
    # When the same FATES name appears multiple times, each entry MUST have a
    # 'pft' field so downstream tools (param file creation, logging) can
    # distinguish them.
    from collections import Counter
    name_counts = Counter(p.get('name', '') for p in params)
    for param in params:
        pname = param.get('name', '')
        if name_counts[pname] > 1 and param.get('pft') is None:
            result.issues.append(ValidationIssue(
                parameter=pname,
                check="missing_pft",
                severity="warning",
                detail=(f"'{pname}' appears {name_counts[pname]} times but this entry "
                        f"has no 'pft' field — cannot disambiguate which PFT to modify"),
            ))

    # Auto-expand retrans parameters tagged by Check 6 (leaf + fineroot)
    n_expanded = expand_retrans_parameters(hypothesis)
    if n_expanded:
        logger.info(f"Auto-expanded {n_expanded} retranslocation parameter(s) to leaf+fineroot entries")

    if result.issues:
        logger.info(f"Hypothesis validation: {result.summary()}")

    return result


def validate_experiment_designs(
    experiments: List[Dict],
    base_case_params: Dict[str, float],
    param_bounds: Dict[str, Dict],
) -> List[ValidationResult]:
    """Validate a list of experiment designs (from synthesis).

    Args:
        experiments: List of experiment dicts, each with 'parameters' key.
        base_case_params: Actual parameter values from ensemble.
        param_bounds: Output of load_parameter_bounds().

    Returns:
        List of ValidationResult, one per experiment.
    """
    results = []
    for exp in experiments:
        vr = validate_hypothesis_parameters(exp, base_case_params, param_bounds)
        results.append(vr)
    return results


def _validate_single_parameter(
    param: Dict,
    base_case_params: Dict[str, float],
    param_bounds: Dict[str, Dict],
    result: ValidationResult,
):
    """Validate and auto-fix a single parameter dict. Mutates param in place."""
    name = param.get('name', '')
    if not name:
        return

    # Primary lookup by shorthand key
    bounds_info = param_bounds.get(name, {})
    # Fallback: if name is a FATES name (not found as shorthand), do reverse lookup
    # by (fates_name, pft, organ) to find the matching bounds entry
    if not bounds_info and name.startswith('fates_'):
        bounds_info = find_bounds_entry(
            name, param.get('pft'), param.get('organ'), param_bounds
        ) or {}

    actual_current = base_case_params.get(name)

    # --- Check 1: "current" value vs actual base case ---
    if actual_current is not None:
        stated_current = param.get('current')
        if stated_current is not None and stated_current != '':
            try:
                stated_val = float(stated_current)
                actual_val = float(actual_current)
                # Allow small floating-point tolerance
                if actual_val != 0:
                    rel_diff = abs(stated_val - actual_val) / abs(actual_val)
                else:
                    rel_diff = abs(stated_val - actual_val)
                if rel_diff > 0.01:  # >1% difference
                    result.issues.append(ValidationIssue(
                        parameter=name,
                        check="current value",
                        severity="auto_fix",
                        detail=f"{stated_val} → {actual_val} (actual from base case)",
                        old_value=stated_val,
                        new_value=actual_val,
                    ))
                    param['current'] = actual_val
            except (ValueError, TypeError):
                pass
        elif stated_current is None or stated_current == '':
            # Missing current value — fill it in
            param['current'] = actual_current

    # --- Check 2: "bounds" field vs parameter list ---
    if bounds_info:
        lower = bounds_info['lower_bound']
        upper = bounds_info['upper_bound']
        stated_bounds = param.get('bounds')
        if stated_bounds and isinstance(stated_bounds, (list, tuple)) and len(stated_bounds) == 2:
            try:
                sb_lower, sb_upper = float(stated_bounds[0]), float(stated_bounds[1])
                if (abs(sb_lower - lower) > 1e-15 or abs(sb_upper - upper) > 1e-15):
                    result.issues.append(ValidationIssue(
                        parameter=name,
                        check="bounds",
                        severity="auto_fix",
                        detail=f"[{sb_lower}, {sb_upper}] → [{lower}, {upper}] (actual bounds)",
                        old_value=stated_bounds,
                        new_value=[lower, upper],
                    ))
                    param['bounds'] = [lower, upper]
            except (ValueError, TypeError):
                pass
        elif not stated_bounds:
            # Fill in missing bounds
            param['bounds'] = [lower, upper]

    # --- Check 2b: Proposed value must be numeric ---
    proposed = param.get('proposed')
    if proposed is not None:
        try:
            float(proposed)
        except (ValueError, TypeError):
            result.issues.append(ValidationIssue(
                parameter=name,
                check="non_numeric_proposed",
                severity="error",
                detail=f"proposed value is not numeric: {str(proposed)[:80]}",
            ))

    # --- Check 3: Proposed value out of bounds ---
    # Out-of-bounds proposals are allowed — experiments can test any value.
    # Bounds are sampling ranges for Morris/Sobol, not hard physical limits.
    # Phase 6→Phase 0 can expand bounds based on experiment results.
    if proposed is not None and bounds_info:
        try:
            proposed_val = float(proposed)
            lower = bounds_info['lower_bound']
            upper = bounds_info['upper_bound']
            if proposed_val < lower or proposed_val > upper:
                result.issues.append(ValidationIssue(
                    parameter=name,
                    check="out of bounds",
                    severity="warning",
                    detail=f"proposed={proposed_val} outside [{lower}, {upper}]",
                ))
        except (ValueError, TypeError):
            pass

    # --- Check 4: PFT mismatch ---
    stated_pft = param.get('pft')
    if stated_pft is not None and bounds_info.get('pft') is not None:
        try:
            if int(stated_pft) != int(bounds_info['pft']):
                result.issues.append(ValidationIssue(
                    parameter=name,
                    check="pft mismatch",
                    severity="error",
                    detail=f"stated pft={stated_pft}, shorthand implies pft={bounds_info['pft']}",
                ))
        except (ValueError, TypeError):
            pass

    # --- Check 4b: No-op detection (proposed == current) ---
    current_val = param.get('current')
    if proposed is not None and current_val is not None:
        try:
            cur = float(current_val)
            prop = float(proposed)
            if cur != 0:
                rel_diff = abs(prop - cur) / abs(cur)
            else:
                rel_diff = abs(prop - cur)
            if rel_diff < 0.001:  # <0.1% difference = no-op
                result.issues.append(ValidationIssue(
                    parameter=name,
                    check="no-op",
                    severity="warning",
                    detail=f"proposed={prop} is unchanged from current={cur} (delta <0.1%)",
                ))
        except (ValueError, TypeError):
            pass

    # --- Check 5: Magnitude of change ---
    # Large changes are allowed — experiments are free to test any value.
    # Parameter bounds are best guesses; Phase 6→Phase 0 can expand them.
    # We only log informational warnings, never block or strip.
    if proposed is not None and current_val is not None:
        try:
            cur = float(current_val)
            prop = float(proposed)
            if cur != 0:
                ratio = abs(prop / cur)
                if ratio > 1000 or (ratio > 0 and ratio < 0.001):
                    result.issues.append(ValidationIssue(
                        parameter=name,
                        check="magnitude",
                        severity="info",
                        detail=f"{cur} → {prop} ({ratio:.1f}x change, >1000x)",
                    ))
                elif ratio > 100 or (ratio > 0 and ratio < 0.01):
                    result.issues.append(ValidationIssue(
                        parameter=name,
                        check="magnitude",
                        severity="info",
                        detail=f"{cur} → {prop} ({ratio:.1f}x change, 100-1000x)",
                    ))
        except (ValueError, TypeError):
            pass

    # --- Check 6: Missing organ for organ-dependent parameters ---
    # Parameters with (fates_plant_organs × fates_pft) dimensions require an organ field.
    #
    # Retranslocation params (nitr_retrans, phos_retrans) only apply to senescing
    # tissues: leaf (organ=1) and fineroot (organ=2).  When proposed without organ,
    # we mark for auto-expansion into two entries (same value, organ 1 + 2).
    # The actual duplication is done by expand_retrans_parameters() after validation.
    #
    # Other organ-dependent params (stoich, alloc_organ_priority) have different
    # values per organ, so a missing organ is a real error.
    ORGAN_DEPENDENT_PARAMS = {
        'fates_alloc_organ_priority',
        'fates_cnp_turnover_nitr_retrans',
        'fates_cnp_turnover_phos_retrans',
        'fates_stoich_nitr',
        'fates_stoich_phos',
    }
    RETRANS_PARAMS = {
        'fates_cnp_turnover_nitr_retrans',
        'fates_cnp_turnover_phos_retrans',
    }
    fates_name = name if name.startswith('fates_') else bounds_info.get('fates_name', '')
    if fates_name in ORGAN_DEPENDENT_PARAMS and param.get('organ') is None:
        if fates_name in RETRANS_PARAMS:
            # Auto-fixable: mark for leaf+fineroot expansion
            result.issues.append(ValidationIssue(
                parameter=name,
                check="retrans missing organ (auto-expand leaf+fineroot)",
                severity="auto_fix",
                detail=(f"'{fates_name}' retranslocation applies to senescing tissues only. "
                        f"Auto-expanding to organ=1 (leaf) + organ=2 (fineroot) with same value."),
            ))
            # Tag the param dict so expand_retrans_parameters() can find it
            param['_expand_retrans'] = True
        else:
            result.issues.append(ValidationIssue(
                parameter=name,
                check="missing organ",
                severity="error",
                detail=(f"'{fates_name}' is organ-dependent (fates_plant_organs × fates_pft). "
                        f"Must include 'organ': 1=leaf, 2=fineroot, 3=sapwood, 4=storage"),
            ))


# ---------------------------------------------------------------------------
# Re-prompt context builder
# ---------------------------------------------------------------------------

def build_reprompt_context(
    validation_result: ValidationResult,
    hypothesis: Dict,
    base_case_params: Dict[str, float],
    param_bounds: Dict[str, Dict],
) -> str:
    """Format validation errors into a re-prompt message for Claude.

    Only includes errors (not auto-fixes or warnings).

    Args:
        validation_result: Result from validate_hypothesis_parameters().
        hypothesis: The hypothesis dict (post auto-fix).
        base_case_params: Actual parameter values.
        param_bounds: Parameter bounds dict.

    Returns:
        A formatted string to append to the original prompt for a retry.
    """
    errors = [i for i in validation_result.issues if i.severity == "error"]
    if not errors:
        return ""

    lines = [
        "\n## VALIDATION ERRORS — Please fix and re-generate\n",
        "Your previous response had the following parameter errors:\n",
    ]
    for err in errors:
        lines.append(f"- **{err.parameter}** ({err.check}): {err.detail}")

    lines.append("\n## Corrections needed:")
    for err in errors:
        name = err.parameter
        if "out of bounds" in err.check:
            bi = param_bounds.get(name, {})
            lines.append(f"- `{name}`: proposed value must be within [{bi.get('lower_bound')}, {bi.get('upper_bound')}]")
        elif "pft mismatch" in err.check:
            bi = param_bounds.get(name, {})
            lines.append(f"- `{name}`: correct PFT is {bi.get('pft')}")
        elif "magnitude" in err.check:
            actual = base_case_params.get(name, '?')
            lines.append(f"- `{name}`: current value is {actual}; propose a value within reasonable magnitude (< 1000x change)")
        elif "missing organ" in err.check:
            lines.append(f"- `{name}`: MUST include `\"organ\"` field: 1=leaf, 2=fineroot, 3=sapwood, 4=storage. "
                         f"For stoich/priority params, specify the organ you want to change. "
                         f"For retranslocation params, provide TWO entries with organ=1 (leaf) "
                         f"and organ=2 (fineroot) with the same value.")

    lines.append("\nPlease regenerate the complete JSON with these corrections.")
    lines.append("Respond ONLY with the corrected JSON object.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Layer 2: AI self-review (short API call)
# ---------------------------------------------------------------------------

def ai_review_experiment(
    reasoning_module,
    experiment: Dict,
    base_case_params: Dict[str, float],
    param_bounds: Dict[str, Dict],
) -> Dict:
    """Run a short AI plausibility check on a synthesized experiment.

    Makes one short Claude API call (~800 tokens) to check for:
    - Conflicting parameter changes
    - Overly aggressive modifications
    - Physical realism concerns

    Args:
        reasoning_module: ReasoningModule instance (must have .query method).
        experiment: Experiment dict with 'name', 'parameters', etc.
        base_case_params: Actual parameter values.
        param_bounds: Parameter bounds dict.

    Returns:
        Dict with keys: 'approved' (bool), 'warnings' (list of str),
        'summary' (str). Returns a safe default if the API call fails.
    """
    params_table = []
    organ_names = {1: 'leaf', 2: 'fineroot', 3: 'sapwood', 4: 'storage'}
    for p in experiment.get('parameters', []):
        name = p.get('name', '?')
        current = p.get('current', '?')
        proposed = p.get('proposed', '?')
        bounds = param_bounds.get(name, {})
        if not bounds and name.startswith('fates_'):
            bounds = find_bounds_entry(
                name, p.get('pft'), p.get('organ'), param_bounds
            ) or {}
        lower = bounds.get('lower_bound', '?')
        upper = bounds.get('upper_bound', '?')
        # Include PFT and organ to disambiguate duplicate param names
        qualifier = ""
        pft = p.get('pft')
        organ = p.get('organ')
        if pft is not None:
            qualifier += f" PFT#{pft}"
        if organ is not None:
            qualifier += f" [{organ_names.get(organ, f'organ={organ}')}]"
        params_table.append(f"  - {name}{qualifier}: {current} → {proposed} (bounds: [{lower}, {upper}])")

    prompt = f"""Quick plausibility review of this ELM-FATES experiment before HPC submission.

Experiment: {experiment.get('name', 'Unknown')}
Mechanism: {experiment.get('mechanism', 'Unknown')}

Parameter changes:
{chr(10).join(params_table)}

Check for:
1. Do any parameter changes conflict with each other?
2. Are any changes overly aggressive (could destabilize the model)?
3. Are the changes physically realistic for an Arctic tundra ecosystem?

Respond in JSON:
{{"approved": true/false, "warnings": ["list of concerns if any"], "summary": "one-line assessment"}}"""

    try:
        response = reasoning_module.query(prompt, max_tokens=512)
        import json
        # Try to extract JSON from response
        data = reasoning_module._extract_json(response)
        result = {
            'approved': data.get('approved', True),
            'warnings': data.get('warnings', []),
            'summary': data.get('summary', 'Review completed'),
        }
        logger.info(f"AI review of '{experiment.get('name', '?')}': "
                    f"{'APPROVED' if result['approved'] else 'FLAGGED'} — {result['summary']}")
        return result
    except Exception as e:
        logger.warning(f"AI self-review failed for '{experiment.get('name', '?')}': {e}")
        return {
            'approved': True,
            'warnings': [f"AI review failed: {e}"],
            'summary': 'Review unavailable (API error)',
        }


# ---------------------------------------------------------------------------
# Formatting for phase logger
# ---------------------------------------------------------------------------

def format_validation_for_log(validation_result: ValidationResult) -> str:
    """Format validation results as a Markdown section for phase logger.

    Returns:
        Markdown string with a table of issues and a summary line.
        Returns empty string if no issues.
    """
    if validation_result.is_clean:
        return ""

    lines = ["## Parameter Validation Report\n"]
    lines.append("| Parameter | Check | Status | Detail |")
    lines.append("|-----------|-------|--------|--------|")

    for issue in validation_result.issues:
        status_map = {
            'auto_fix': 'AUTO-FIXED',
            'warning': 'WARNING',
            'error': 'ERROR',
        }
        status = status_map.get(issue.severity, issue.severity.upper())
        # Escape pipe characters in detail
        detail = issue.detail.replace('|', '\\|')
        lines.append(f"| {issue.parameter} | {issue.check} | {status} | {detail} |")

    lines.append(f"\n**Summary:** {validation_result.summary()}")
    return "\n".join(lines)


def format_ai_review_for_log(ai_review: Dict) -> str:
    """Format AI self-review result as a Markdown section.

    Args:
        ai_review: Dict with 'approved', 'warnings', 'summary'.

    Returns:
        Markdown string, or empty string if no review data.
    """
    if not ai_review:
        return ""

    lines = ["## AI Self-Review\n"]
    approved = ai_review.get('approved', True)
    lines.append(f"**Approved:** {'Yes' if approved else 'No'}")
    lines.append(f"**Summary:** {ai_review.get('summary', 'N/A')}")

    warnings = ai_review.get('warnings', [])
    if warnings:
        lines.append("\n**Warnings:**")
        for w in warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)
