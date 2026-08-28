#!/usr/bin/env python3
"""
A2MC Configuration Module

Python interface to a2mc_config.sh settings. This module provides:
1. Access to environment variables set by sourcing a2mc_config.sh
2. Default values for HPC (NERSC Perlmutter)
3. Path validation utilities

Usage:
    from tools.config import config

    # Access paths
    output_root = config.OUTPUT_ROOT
    ensemble_output = config.ENSEMBLE_OUTPUT
    extracted_data = config.EXTRACTED_DATA

    # Or use get() with defaults
    log_dir = config.get('LOG_DIR', '/tmp/logs')

Before running Python scripts, source both configs:
    source a2mc_config.sh
    source use_cases/ELM-FATES_Kougarok/config/kougarok_config.sh
    python tools/your_script.py

Author: A2MC Framework
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def _required_env(name: str, what: str) -> str:
    """Return env var `name`, or raise with an actionable message.

    These are MACHINE/SITE settings, supplied by `a2mc_config.sh` +
    `use_cases/{site}/config/{site}_config.sh`. They used to fall back to the
    maintainer's own absolute paths, which failed three ways at once:

      - CLAUDE.md rule 8 (no hardcoded paths) — a default nobody else can use;
      - it SHIPPED: `scripts/sync_to_public.sh` genericizes host paths to `~`,
        so the public copy read `os.environ.get('A2MC_OUTPUT_ROOT', '~')` —
        and Python does NOT expand `~`, so an unconfigured public user silently
        got a directory literally named `~` instead of an error;
      - it hid the real problem. Falling back to a path that exists only on one
        machine turns "you forgot to source the configs" into a confusing
        wrong-directory failure much later, instead of a clear one here.

    Raising matches the existing `MODEL_PATH` precedent in this class.
    """
    v = os.environ.get(name, '')
    if not v:
        raise EnvironmentError(
            f"{name} is required but not set ({what}).\n"
            f"  Source the two config layers first, in this order:\n"
            f"    source a2mc_config.sh\n"
            f"    source use_cases/<site>/config/<site>_config.sh\n"
            f"  (the site config for the ACTIVE round is named by that site's "
            f"config/calibration_rounds.yaml -> round.config_file)"
        )
    return v


@dataclass
class A2MCConfig:
    """
    A2MC Configuration container.

    Reads from environment variables with A2MC_ prefix.
    All paths are HPC paths (NERSC Perlmutter).
    """

    # ========================
    # DIRECTORY PATHS
    # ========================

    @property
    def A2MC_ROOT(self) -> str:
        """A2MC framework root directory"""
        return os.environ.get('A2MC_ROOT',
            str(Path(__file__).parent.parent))

    @property
    def E3SM_ROOT(self) -> str:
        """E3SM/FATES source code root. Required — set by a2mc_config.sh."""
        return _required_env('A2MC_E3SM_ROOT', 'your E3SM/ELM-FATES source root')

    @property
    def OUTPUT_ROOT(self) -> str:
        """Output root for simulation results. Required — set by a2mc_config.sh."""
        return _required_env('A2MC_OUTPUT_ROOT', 'where simulation output should be written')

    @property
    def SCRIPTS_DIR(self) -> str:
        """Scripts dir (where case scripts are generated). Required — set by a2mc_config.sh."""
        return _required_env('A2MC_SCRIPTS_DIR', 'where generated case scripts should go')

    @property
    def PARAM_DIR(self) -> str:
        """Directory containing ensemble parameter files"""
        return os.environ.get('A2MC_PARAM_DIR', '')

    @property
    def BASE_PARAM_FILE(self) -> str:
        """Base FATES parameter file (template fallback)"""
        return os.environ.get('A2MC_BASE_PARAM_FILE', '')

    @property
    def PARAM_PATTERN(self) -> str:
        """Parameter file naming pattern with {N} placeholder for case number"""
        return os.environ.get('A2MC_PARAM_PATTERN', '')

    @property
    def ENSEMBLE_MATRIX_FILE(self) -> str:
        """Ensemble matrix file (parameter values from sampling design)"""
        return os.environ.get('A2MC_ENSEMBLE_MATRIX_FILE', '')

    @property
    def PARAM_LIST_FILE(self) -> str:
        """Parameter list file (names and bounds)"""
        return os.environ.get('A2MC_PARAM_LIST_FILE', '')

    @property
    def SALIB_PROBLEM_FILE(self) -> str:
        """SALib problem definition file"""
        return os.environ.get('A2MC_SALIB_PROBLEM_FILE', '')

    # ========================
    # RAG / VERSION ASSOCIATION
    # ========================

    @property
    def MODEL_PATH(self) -> str:
        """Absolute path to the user's E3SM/ELM-FATES checkout root.

        Required (not optional). Used by `tools/model_version.py` to detect
        ELM + FATES commits, which the RAG infrastructure uses to select the
        correct milestone profile. See docs/18 §4.1.
        """
        return _required_env('A2MC_MODEL_PATH', 'your E3SM/ELM-FATES checkout root')

    @property
    def RAG_DIR(self) -> str:
        """Root of the RAG storage tree. Defaults to <A2MC_ROOT>/rag."""
        return os.environ.get('A2MC_RAG_DIR', f'{self.A2MC_ROOT}/rag')

    @property
    def RAG_ACTIVE(self) -> str:
        """Active RAG profile name (e.g., 'api-43-1', 'api-31-0').

        Selected by the version-association infrastructure based on the
        user's MODEL_PATH. Required when reading or writing RAG artifacts.
        """
        v = os.environ.get('A2MC_RAG_ACTIVE', '')
        if not v:
            raise EnvironmentError(
                "A2MC_RAG_ACTIVE is required but not set. The orchestrator "
                "should set it via the alignment check at startup; if you "
                "are running RAG tools outside the orchestrator, set it "
                "explicitly to a registered milestone profile name."
            )
        return v

    @property
    def RAG_AUTO_REBUILD(self) -> bool:
        """If true, the orchestrator rebuilds the RAG silently when drift is
        detected. Default: false (drift causes WARN+abort)."""
        return os.environ.get('A2MC_RAG_AUTO_REBUILD', 'false').lower() in (
            'true', '1', 'yes', 'on'
        )

    # ========================
    # SIMULATION MODE (Phase A of Doc 20: Mode-aware RAG retrieval)
    # ========================

    @property
    def MODE(self) -> 'ConfigMode':
        """Detected simulation configuration. Composes a filter signature for RAG.

        Reads `A2MC_USE_FATES`, `A2MC_FATES_PARTEH_MODE`, `A2MC_USE_FATES_NOCOMP`,
        and parses `A2MC_ELM_OPTIONS` for `-nutrient`, `-nutrient_comp_pathway`,
        `-soil_decomp` flags.

        Defaults are conservative (FATES on, PARTEH=2 CNP, competition on,
        nutrient cnp, ECA pathway) so that legacy site configs without the
        mode env vars produce the same retrieval as before mode-awareness.
        """
        return ConfigMode.from_env()

    # ========================
    # ENSEMBLE PATHS
    # ========================

    @property
    def ENSEMBLE_NAME(self) -> str:
        """Current ensemble name"""
        return os.environ.get('A2MC_ENSEMBLE_NAME', '')

    @property
    def ENSEMBLE_OUTPUT(self) -> str:
        """Ensemble output directory"""
        return os.environ.get('A2MC_ENSEMBLE_OUTPUT',
            f'{self.OUTPUT_ROOT}/{self.ENSEMBLE_NAME}')

    @property
    def EXTRACTED_DATA(self) -> str:
        """Extracted monthly data directory"""
        return os.environ.get('A2MC_EXTRACTED_DATA',
            f'{self.ENSEMBLE_OUTPUT}/extracted_monthly_data')

    @property
    def FIGURES_DIR(self) -> str:
        """Directory for generated figures.

        Added because the screening/comparison plotters had no config-backed
        figures location and each hardcoded the maintainer's own
        `Figures_<ensemble>` directory instead. Derived from OUTPUT_ROOT so it
        follows the site wherever its output lives.
        """
        return os.environ.get('A2MC_FIGURES_DIR',
            f'{self.OUTPUT_ROOT}/Figures_{self.ENSEMBLE_NAME}')

    @property
    def CASE_SCRIPTS(self) -> str:
        """Case scripts directory"""
        return os.environ.get('A2MC_CASE_SCRIPTS', '')

    @property
    def LOG_DIR(self) -> str:
        """Log directory for ensemble status"""
        return os.environ.get('A2MC_LOG_DIR', self.CASE_SCRIPTS)

    # ========================
    # SITE CONFIGURATION
    # ========================

    @property
    def SITE_NAME(self) -> str:
        """Site name"""
        return os.environ.get('A2MC_SITE_NAME', '')

    @property
    def USE_CASE_DIR(self) -> str:
        """Use case directory"""
        return os.environ.get('A2MC_USE_CASE_DIR', '')

    @property
    def VALIDATION_FILE(self) -> str:
        """Validation targets file"""
        return os.environ.get('A2MC_VALIDATION_FILE', '')

    # ========================
    # ENSEMBLE CONFIGURATION
    # ========================

    @property
    def ENSEMBLE_PREFIX(self) -> str:
        """Case name prefix"""
        return os.environ.get('A2MC_ENSEMBLE_PREFIX', '')

    @property
    def CASE_PREFIX(self) -> str:
        """Alias for ENSEMBLE_PREFIX"""
        return self.ENSEMBLE_PREFIX

    @property
    def CASE_NAME_PATTERN(self) -> str:
        """Pattern for case directory names. Uses {N} for case number, {PHASE} for phase."""
        default = f"{self.ENSEMBLE_PREFIX}{{N}}_{{PHASE}}"
        return os.environ.get('A2MC_CASE_NAME_PATTERN', default)

    def make_case_name(self, case_num: int, phase: str = 'TRANS') -> str:
        """Build case directory name from case number and phase."""
        return self.CASE_NAME_PATTERN.format(N=case_num, PHASE=phase)

    @property
    def N_PARAMS(self) -> int:
        """Number of parameters"""
        return int(os.environ.get('A2MC_N_PARAMS', '100'))

    @property
    def N_TRAJECTORIES(self) -> int:
        """Number of trajectories (for morris scheme)"""
        return int(os.environ.get('A2MC_N_TRAJECTORIES', '30'))

    @property
    def N_SAMPLES(self) -> int:
        """Number of samples (for lhs/sobol schemes)"""
        return int(os.environ.get('A2MC_N_SAMPLES', '1000'))

    @property
    def TOTAL_ENSEMBLE(self) -> int:
        """
        Total ensemble size (auto-calculated based on scheme if not set).

        Formulas:
        - morris: n_trajectories × (n_params + 1)
        - lhs: n_samples
        - sobol: n_samples × (2 × n_params + 2)  [A2MC_SOBOL_SECOND_ORDER truthy, the default]
                 n_samples × (n_params + 2)      [A2MC_SOBOL_SECOND_ORDER in {0,false,False}]
        """
        explicit = os.environ.get('A2MC_TOTAL_ENSEMBLE', '')
        if explicit:
            return int(explicit)
        # Calculate based on scheme
        scheme = self.SAMPLING_SCHEME
        if scheme == 'morris':
            return self.N_TRAJECTORIES * (self.N_PARAMS + 1)
        elif scheme == 'lhs':
            return self.N_SAMPLES
        elif scheme == 'sobol':
            # Must agree with a2mc_config.sh's calculate_ensemble_size() and with
            # create_parameter_sample.py; all three read A2MC_SOBOL_SECOND_ORDER.
            return self.N_SAMPLES * ((2 * self.N_PARAMS + 2) if self.SOBOL_SECOND_ORDER
                                     else (self.N_PARAMS + 2))
        else:
            return 0  # custom or unknown

    @property
    def SAMPLING_SCHEME(self) -> str:
        """Sampling scheme (morris, lhs, sobol, custom)"""
        return os.environ.get('A2MC_SAMPLING_SCHEME', 'morris')

    @property
    def SOBOL_SECOND_ORDER(self) -> bool:
        """[sobol] Whether to compute second-order (S_ij) indices.

        The ONE parse of A2MC_SOBOL_SECOND_ORDER on the Python side, so TOTAL_ENSEMBLE and
        create_parameter_sample.py cannot disagree on what "0" means. Matches the shell's
        `case` in a2mc_config.sh: only 0/false/False are false.
        """
        return os.environ.get('A2MC_SOBOL_SECOND_ORDER', '1') not in ('0', 'false', 'False')

    # ========================
    # PHASE CONFIGURATION
    # ========================

    @property
    def ADSP_YEARS(self) -> int:
        return int(os.environ.get('A2MC_ADSP_YEARS', '200'))

    @property
    def RGSP_YEARS(self) -> int:
        return int(os.environ.get('A2MC_RGSP_YEARS', '200'))

    @property
    def TRANS_YEARS(self) -> int:
        return int(os.environ.get('A2MC_TRANS_YEARS', '119'))

    # ========================
    # AI CONFIGURATION
    # ========================

    @property
    def AI_PROVIDER(self) -> str:
        """
        AI provider: 'anthropic', 'openai', or 'cborg'.

        - anthropic: Uses Anthropic SDK, hits api.anthropic.com
        - openai:    Uses OpenAI SDK, hits api.openai.com
        - cborg:     Uses OpenAI SDK, hits api.cborg.lbl.gov (Berkeley Lab proxy)
        """
        return os.environ.get('A2MC_AI_PROVIDER', 'anthropic')

    @property
    def AI_MODEL(self) -> str:
        """
        AI model to use for reasoning. Auto-derived from provider if not set:
          anthropic → claude-opus-4-20250514
          openai    → gpt-4o
          cborg     → anthropic/claude-sonnet
        """
        explicit = os.environ.get('A2MC_AI_MODEL', '')
        if explicit:
            return explicit
        defaults = {
            'anthropic': 'claude-opus-4-20250514',
            'openai': 'gpt-4o',
            'cborg': 'anthropic/claude-sonnet',
        }
        return defaults.get(self.AI_PROVIDER, 'claude-opus-4-20250514')

    @property
    def AI_MAX_TOKENS(self) -> int:
        """Maximum tokens for AI responses"""
        return int(os.environ.get('A2MC_AI_MAX_TOKENS', '4096'))

    @property
    def AI_BASE_URL(self) -> Optional[str]:
        """
        Custom API base URL. Auto-set for cborg provider.

        Returns None to use SDK defaults for anthropic/openai providers.
        """
        url = os.environ.get('A2MC_AI_BASE_URL', '')
        if url:
            return url
        if self.AI_PROVIDER == 'cborg':
            return 'https://api.cborg.lbl.gov'
        return None

    @property
    def AI_API_KEY_ENV(self) -> str:
        """
        Environment variable name containing the API key.
        Auto-derived from provider if not explicitly set:
          anthropic → ANTHROPIC_API_KEY
          openai    → OPENAI_API_KEY
          cborg     → CBORG_API_KEY
        """
        explicit = os.environ.get('A2MC_AI_API_KEY_ENV', '')
        if explicit:
            return explicit
        defaults = {
            'anthropic': 'ANTHROPIC_API_KEY',
            'openai': 'OPENAI_API_KEY',
            'cborg': 'CBORG_API_KEY',
        }
        return defaults.get(self.AI_PROVIDER, 'AI_API_KEY')

    def get_ai_api_key(self) -> Optional[str]:
        """Get the AI API key from the configured environment variable"""
        return os.environ.get(self.AI_API_KEY_ENV)

    # ========================
    # MACHINE CONFIGURATION
    # ========================

    @property
    def MACHINE(self) -> str:
        return os.environ.get('A2MC_MACHINE', 'pm-cpu')

    @property
    def PROJECT(self) -> str:
        return os.environ.get('A2MC_PROJECT', 'm2467')

    @property
    def USER(self) -> str:
        return os.environ.get('A2MC_USER', os.environ.get('USER', 'jingtao'))

    # ========================
    # HELPER METHODS
    # ========================

    def get(self, key: str, default: str = '') -> str:
        """Get config value by key name (with or without A2MC_ prefix)"""
        # Try with prefix first
        if not key.startswith('A2MC_'):
            env_key = f'A2MC_{key}'
        else:
            env_key = key
            key = key[5:]  # Remove A2MC_ prefix

        # Check environment
        value = os.environ.get(env_key)
        if value:
            return value

        # Check if we have a property for it
        if hasattr(self, key):
            return getattr(self, key)

        return default

    def get_path(self, key: str, default: str = '') -> Path:
        """Get config value as Path object"""
        return Path(self.get(key, default))

    def phase_results_dir(self, phase_name: str) -> Path:
        """Get session-aware phase_results directory.

        Returns: {USE_CASE_DIR}/memory/phase_results/{session_id}/{phase_name}/

        If A2MC_SESSION_ID is not set (e.g., standalone script), falls back
        to the flat layout: {USE_CASE_DIR}/memory/phase_results/{phase_name}/
        """
        base = Path(self.USE_CASE_DIR) / "memory" / "phase_results"
        session_id = os.environ.get('A2MC_SESSION_ID', '')
        if session_id:
            return base / session_id / phase_name
        return base / phase_name

    def phase_topic_dir(self, stem: str, create: bool = True) -> Path:
        """Offline-agent per-topic artifact folder (docs/31).

        Returns (and by default creates) {USE_CASE_DIR}/memory/phase_results/{stem}/
        where stem = YYYYMMDDx_phase{N}_{name}_r{RR}[_c{EE}[_iter{II}]]_{descriptor}.

        Flat + date-led (the offline analog of the session-scoped phase_results_dir):
        the interactive agent has no A2MC_SESSION_ID and organizes by topic, not by run.
        Results (figures, CSVs, case lists, data) live here; reusable diagnostic scripts
        go to phases/phase3_diagnosis/generated/ instead.
        """
        d = Path(self.USE_CASE_DIR) / "memory" / "phase_results" / stem
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def is_configured(self) -> bool:
        """Check if site configuration has been loaded"""
        return bool(self.SITE_NAME)

    def _try(self, name: str) -> Optional[str]:
        """Read a property, returning None if its required env var is unset.

        Diagnostics must survive an unconfigured clone: `validate_paths` and
        `print_config` exist precisely to tell you what is missing, so they
        cannot be the thing that raises when something is missing.
        """
        try:
            return getattr(self, name)
        except EnvironmentError:
            return None

    def validate_paths(self) -> dict:
        """Validate that key paths exist"""
        paths_to_check = [
            ('ENSEMBLE_OUTPUT', self._try('ENSEMBLE_OUTPUT')),
            ('EXTRACTED_DATA', self._try('EXTRACTED_DATA')),
            ('CASE_SCRIPTS', self._try('CASE_SCRIPTS')),
            ('PARAM_DIR', self._try('PARAM_DIR')),
        ]

        results = {}
        for name, path in paths_to_check:
            if path:
                exists = Path(path).exists()
                results[name] = {'path': path, 'exists': exists}
            else:
                results[name] = {'path': '(not set)', 'exists': False}

        return results

    def print_config(self):
        """Print current configuration"""
        print("=" * 60)
        print("A2MC Python Configuration")
        print("=" * 60)

        if self.SITE_NAME:
            print(f"Site: {self.SITE_NAME}")
            print(f"Use Case Dir: {self.USE_CASE_DIR}")
        else:
            print("WARNING: No site configuration loaded!")
            print("  Run: source use_cases/{site}/config/{site}_config.sh")

        print("")
        print("HPC Paths:")
        for _n in ('E3SM_ROOT', 'OUTPUT_ROOT', 'SCRIPTS_DIR',
                   'ENSEMBLE_OUTPUT', 'EXTRACTED_DATA', 'CASE_SCRIPTS'):
            print(f"  {_n + ':':16} {self._try(_n) or '(not set — source the configs)'}")
        print("")
        print("Parameter Files:")
        print(f"  PARAM_DIR:          {self.PARAM_DIR}")
        print(f"  PARAM_PATTERN:      {self.PARAM_PATTERN}")
        print(f"  BASE_PARAM_FILE:    {self.BASE_PARAM_FILE}")
        print(f"  ENSEMBLE_MATRIX:    {self.ENSEMBLE_MATRIX_FILE}")
        print(f"  PARAM_LIST:         {self.PARAM_LIST_FILE}")
        print(f"  SALIB_PROBLEM:      {self.SALIB_PROBLEM_FILE}")
        print("")
        print("Ensemble Configuration:")
        print(f"  ENSEMBLE_NAME:   {self.ENSEMBLE_NAME}")
        print(f"  CASE_PREFIX:     {self.CASE_PREFIX}")
        print(f"  N_PARAMS:        {self.N_PARAMS}")
        print(f"  TOTAL_ENSEMBLE:  {self.TOTAL_ENSEMBLE}")
        print(f"  SAMPLING_SCHEME: {self.SAMPLING_SCHEME}")
        print("")
        print("AI Configuration:")
        print(f"  AI_PROVIDER:     {self.AI_PROVIDER}")
        print(f"  AI_MODEL:        {self.AI_MODEL}")
        print(f"  AI_MAX_TOKENS:   {self.AI_MAX_TOKENS}")
        base_url = self.AI_BASE_URL
        if base_url:
            print(f"  AI_BASE_URL:     {base_url}")
        print(f"  API_KEY_ENV:     {self.AI_API_KEY_ENV}")
        api_key = self.get_ai_api_key()
        print(f"  API_KEY_SET:     {'Yes' if api_key else 'No'}")
        print("=" * 60)


# Global config instance
# =============================================================================
# Mode dataclass (Doc 20: Mode-aware RAG retrieval)
# =============================================================================

# Bare boolean flags (no value follows) in ELM_OPTIONS.
# Source: components/elm/cime_config/config_component.xml compset modifiers
_BARE_BOOLEAN_FLAGS = frozenset({
    "crop", "dynamic_vegetation", "methane",
    "hydrstress", "topounit", "tw_irr_on",
    "no-megan", "no-drydep",
})


def _truthy(s: str) -> bool:
    """Standard string-to-bool, handles CIME's `.true.`/`.false.` too."""
    return str(s).lower() in ("true", "1", "yes", "on", ".true.")


def parse_elm_options(elm_options: str) -> Dict[str, object]:
    """Parse a CIME options string into a flag-to-value dict.

    Handles both `-flag value` pairs and bare boolean flags (`-crop`,
    `-hydrstress`, etc.). Bare flags resolve to ``True``; paired flags
    resolve to their value string.

    Examples
    --------
    >>> parse_elm_options("-bgc fates -nutrient cnp -nutrient_comp_pathway eca")
    {'bgc': 'fates', 'nutrient': 'cnp', 'nutrient_comp_pathway': 'eca'}

    >>> parse_elm_options("-bgc bgc -nutrient cnp -methane -hydrstress")
    {'bgc': 'bgc', 'nutrient': 'cnp', 'methane': True, 'hydrstress': True}

    >>> parse_elm_options("-irrig .true. -tw_irr_on")
    {'irrig': '.true.', 'tw_irr_on': True}

    Empty / unset string produces empty dict.
    """
    if not elm_options:
        return {}
    tokens = elm_options.split()
    result: Dict[str, object] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-"):
            flag = tok.lstrip("-")
            # Decide bare vs paired: bare if next token is another flag, end
            # of string, or the flag is in the bare-flag whitelist.
            next_is_flag = (i + 1 >= len(tokens)) or tokens[i + 1].startswith("-")
            if next_is_flag or flag in _BARE_BOOLEAN_FLAGS:
                result[flag] = True
                i += 1
            else:
                result[flag] = tokens[i + 1]
                i += 2
        else:
            # Stray non-flag token (rare); skip.
            i += 1
    return result


@dataclass
class ConfigMode:
    """Active simulation configuration for retrieval filtering.

    Each field is a mode dimension. Defaults reflect ELM api-43-1's
    ``namelist_defaults.xml`` (a vanilla ELM run with no compset modifier:
    Satellite Phenology, no FATES, no biogeochemistry). Site configs like
    ``kougarok_config.sh`` OVERRIDE defaults via env vars; the schema
    represents the model's worldview, not one user's run.

    20 dimensions across 3 tiers:

    - Tier 1 (primary, 7): bgc_mode, use_fates (derived), parteh_mode,
      use_fates_nocomp, nutrient, nutrient_comp_pathway, soil_decomp
    - Tier 2 (FATES feature flags, 6): fates_spitfire_mode,
      use_fates_planthydro, use_fates_logging, use_fates_sp,
      use_fates_ed_prescribed_phys, use_fates_fixed_biogeog
    - Tier 3 (secondary compset modifiers, 7): crop, dynamic_vegetation,
      methane, hydrstress, topounit, irrig, solar_rad_scheme

    See ``docs/21_Mode_Aware_RAG_Phase_B_Implementation.md`` for the design.
    """
    # ----- Tier 1: primary dimensions (7) -----
    bgc_mode: str = "sp"                   # ELM default: 'sp' (namelist_defaults.xml:32)
    use_fates: bool = False                # Derived from bgc_mode == 'fates'
    parteh_mode: int = 1                   # ELM default: 1 (carbon-only; namelist_defaults.xml:2251)
    use_fates_nocomp: bool = False         # ELM default: false (namelist_defaults.xml:2278-2280)
    nutrient: str = ""                     # No global default; only set via -nutrient flag
    nutrient_comp_pathway: str = "rd"      # ELM default: 'rd' (namelist_defaults.xml:67)
    soil_decomp: str = ""                  # No global default; only set via -soil_decomp flag

    # ----- Tier 2: FATES feature flags (6) — direct wiki impact -----
    fates_spitfire_mode: int = 0           # 0=off, 1=lightning, 2=lightning+managed
    use_fates_planthydro: bool = False
    use_fates_logging: bool = False
    use_fates_sp: bool = False
    use_fates_ed_prescribed_phys: bool = False
    use_fates_fixed_biogeog: bool = False

    # ----- Tier 3: secondary compset modifiers (7) — scaffolding -----
    crop: bool = False
    dynamic_vegetation: bool = False
    methane: bool = False                  # Auto-derived: True iff bgc_mode == 'bgc'
    hydrstress: bool = False               # PHS
    topounit: bool = False                 # TGU
    irrig: bool = False                    # WFM
    solar_rad_scheme: str = ""             # '' (default) or 'top' (TOP)

    @classmethod
    def from_env(cls) -> "ConfigMode":
        """Build a ConfigMode from env vars (user intent), enriched by case dir.

        Resolution priority (v2.94+, corrected from v2.93):

        1. **User-provided env vars (PRIMARY)** — represent user INTENT. For
           each ConfigMode field, if the user explicitly set the corresponding
           ``A2MC_*`` env var or the flag in ``A2MC_ELM_OPTIONS``, use that
           value. This is what the user wants A2MC to calibrate against.
        2. **CIME case dir (ENRICHMENT)** — fills in fields the user did NOT
           explicitly set. Read from ``$A2MC_CASE_DIR`` or auto-detected from
           ``$A2MC_E3SM_ROOT/cime/scripts/$A2MC_CASE_NAME``. Provides Tier 2
           use_fates_* flags from ``lnd_in`` plus ELM-default values that CIME
           applied to the user's intent.
        3. **Dataclass defaults** — last-resort baseline (carbon-only PARTEH=1,
           etc., from ELM ``namelist_defaults.xml``). Used only if neither env
           vars nor case dir provide a value.
        4. **Raise** — if no source produces a valid ``bgc_mode`` (the
           irreducible minimum). No silent SP fallback.

        Why this order? See ``memory/feedback_env_vars_are_intent_case_dir_is_truth.md``.
        Env vars are user intent; case dir is downstream of that intent (intent
        + ELM defaults applied by CIME). The two CAN disagree (e.g., stale case
        from before the user changed env vars); we prefer env vars and warn.

        Constraints (raise ValueError on inconsistency):
        - ``bgc_mode == 'fates'`` ⇔ ``use_fates == True`` (derivation)
        - ``bgc_mode == 'fates'`` ⇒ ``dynamic_vegetation == False`` (FATES is its own DGVM)
        - ``bgc_mode == 'sp'`` ⇒ ``use_fates_sp == False``
        """
        elm_options = os.environ.get("A2MC_ELM_OPTIONS", "")
        opts = parse_elm_options(elm_options)

        # Try to load case dir for enrichment (NOT primary)
        case_mode = None
        try:
            from tools.case_parser import resolve_case_dir, case_to_config_mode
            case_dir = resolve_case_dir()
            if case_dir is not None:
                try:
                    case_mode = case_to_config_mode(case_dir)
                except ValueError as e:
                    # Don't crash — log via plain print since logger may not be set up
                    import warnings
                    warnings.warn(
                        f"Case dir at {case_dir} could not be parsed ({e}); "
                        "proceeding with env vars only.",
                        RuntimeWarning,
                    )
        except ImportError:
            pass  # case_parser unavailable; env vars only

        # Helper: prefer env-explicit > case_mode field > default
        def _env_or_case(env_value, case_attr: str, default):
            """Return env_value if not None, else case_mode field, else default."""
            if env_value is not None:
                return env_value
            if case_mode is not None:
                return getattr(case_mode, case_attr)
            return default

        # Helper: warn if env and case disagree on a field
        def _warn_conflict(field: str, env_val, case_val):
            if case_mode is None or env_val is None:
                return
            if env_val != case_val:
                import warnings
                warnings.warn(
                    f"ConfigMode: {field}={env_val!r} (env var) overrides "
                    f"{case_val!r} (case dir). Case dir may be stale; "
                    "rebuild the case to refresh.",
                    RuntimeWarning,
                )

        # ----- Tier 1: bgc_mode (REQUIRED — raise if missing from all sources) -----
        env_bgc_mode = opts.get("bgc") or os.environ.get("A2MC_BGC_MODE")
        bgc_mode = _env_or_case(env_bgc_mode, "bgc_mode", None)
        if not bgc_mode:
            raise ValueError(
                "ConfigMode.from_env() cannot resolve bgc_mode. Set ONE of:\n"
                "  1. A2MC_ELM_OPTIONS containing '-bgc <mode>' (recommended)\n"
                "  2. A2MC_BGC_MODE=<sp|cn|bgc|fates>\n"
                "  3. A2MC_CASE_DIR=/path/to/CIME/case (case dir auto-parsing)\n"
                "  4. A2MC_E3SM_ROOT + A2MC_CASE_NAME (auto-detect case dir)\n"
                "See docs/a2mc_reference/mode_aware_workflow.md for details."
            )
        bgc_mode = str(bgc_mode)
        if bgc_mode not in ("sp", "cn", "bgc", "fates"):
            raise ValueError(
                f"bgc_mode={bgc_mode!r} invalid; expected one of "
                "'sp', 'cn', 'bgc', 'fates'"
            )
        if env_bgc_mode and case_mode is not None:
            _warn_conflict("bgc_mode", str(env_bgc_mode), case_mode.bgc_mode)

        # use_fates: DERIVED from bgc_mode (with consistency check)
        derived_use_fates = (bgc_mode == "fates")
        env_use_fates = os.environ.get("A2MC_USE_FATES")
        if env_use_fates is not None:
            explicit = _truthy(env_use_fates)
            if explicit != derived_use_fates:
                raise ValueError(
                    f"A2MC_USE_FATES={env_use_fates!r} is inconsistent with "
                    f"bgc_mode={bgc_mode!r} (derives use_fates={derived_use_fates}). "
                    "Set bgc_mode='fates' to enable FATES; or remove A2MC_USE_FATES."
                )
        use_fates = derived_use_fates

        # parteh_mode: env > case > default 1
        env_parteh = os.environ.get("A2MC_FATES_PARTEH_MODE")
        parteh_mode = _env_or_case(
            int(env_parteh) if env_parteh is not None else None,
            "parteh_mode", 1,
        )
        if parteh_mode not in (1, 2):
            raise ValueError(
                f"parteh_mode={parteh_mode} invalid; expected 1 (carbon-only) or 2 (CNP)"
            )
        if env_parteh is not None and case_mode is not None:
            _warn_conflict("parteh_mode", int(env_parteh), case_mode.parteh_mode)

        # use_fates_nocomp: env > case > default false
        env_nocomp = os.environ.get("A2MC_USE_FATES_NOCOMP")
        use_fates_nocomp = _env_or_case(
            _truthy(env_nocomp) if env_nocomp is not None else None,
            "use_fates_nocomp", False,
        )

        # nutrient: env (ELM_OPTIONS) > case > default ''
        env_nutrient = opts.get("nutrient")
        nutrient = _env_or_case(env_nutrient, "nutrient", "")
        nutrient = str(nutrient)
        if nutrient and nutrient not in ("c", "cn", "cnp"):
            raise ValueError(
                f"nutrient={nutrient!r} invalid; expected '', 'c', 'cn', or 'cnp'"
            )

        # nutrient_comp_pathway: env > case > default 'rd' (ELM source default)
        env_pathway = opts.get("nutrient_comp_pathway")
        nutrient_comp_pathway = _env_or_case(env_pathway, "nutrient_comp_pathway", "rd")
        nutrient_comp_pathway = str(nutrient_comp_pathway)
        if nutrient_comp_pathway not in ("rd", "eca"):
            raise ValueError(
                f"nutrient_comp_pathway={nutrient_comp_pathway!r} invalid; "
                "expected 'rd' or 'eca'"
            )

        # soil_decomp: env > case > default ''
        env_decomp = opts.get("soil_decomp")
        soil_decomp = _env_or_case(env_decomp, "soil_decomp", "")
        soil_decomp = str(soil_decomp)
        if soil_decomp and soil_decomp not in ("ctc", "century"):
            raise ValueError(
                f"soil_decomp={soil_decomp!r} invalid; expected '', 'ctc', or 'century'"
            )

        # ----- Tier 2: FATES feature flags — env > case > default false -----
        env_spitfire = os.environ.get("A2MC_FATES_SPITFIRE_MODE")
        fates_spitfire_mode = _env_or_case(
            int(env_spitfire) if env_spitfire is not None else None,
            "fates_spitfire_mode", 0,
        )
        if fates_spitfire_mode not in (0, 1, 2):
            raise ValueError(
                f"fates_spitfire_mode={fates_spitfire_mode} invalid; expected 0, 1, or 2"
            )

        # Tier 2 booleans: env > case > default false
        def _bool_env_or_case(env_var: str, case_attr: str) -> bool:
            env_val = os.environ.get(env_var)
            if env_val is not None:
                return _truthy(env_val)
            if case_mode is not None:
                return getattr(case_mode, case_attr)
            return False

        use_fates_planthydro = _bool_env_or_case("A2MC_USE_FATES_PLANTHYDRO", "use_fates_planthydro")
        use_fates_logging = _bool_env_or_case("A2MC_USE_FATES_LOGGING", "use_fates_logging")
        use_fates_sp = _bool_env_or_case("A2MC_USE_FATES_SP", "use_fates_sp")
        use_fates_ed_prescribed_phys = _bool_env_or_case(
            "A2MC_USE_FATES_ED_PRESCRIBED_PHYS", "use_fates_ed_prescribed_phys",
        )
        use_fates_fixed_biogeog = _bool_env_or_case(
            "A2MC_USE_FATES_FIXED_BIOGEOG", "use_fates_fixed_biogeog",
        )

        # ----- Tier 3: ELM_OPTIONS bare flags > case > default false -----
        # For Tier 3, "explicit" means present in A2MC_ELM_OPTIONS; if absent
        # AND case_mode has a value, use case_mode. Tier 3 doesn't have
        # individual A2MC_* env vars (only ELM_OPTIONS).
        def _flag_env_or_case(opt_key: str, case_attr: str) -> bool:
            if opt_key in opts:
                return bool(opts[opt_key])
            if case_mode is not None:
                return getattr(case_mode, case_attr)
            return False

        crop = _flag_env_or_case("crop", "crop")
        dynamic_vegetation = _flag_env_or_case("dynamic_vegetation", "dynamic_vegetation")
        methane_explicit = _flag_env_or_case("methane", "methane")
        # Auto-pair: -bgc bgc implies methane
        methane = methane_explicit or (bgc_mode == "bgc")
        hydrstress = _flag_env_or_case("hydrstress", "hydrstress")
        topounit = _flag_env_or_case("topounit", "topounit")
        # -irrig is paired (-irrig .true.) but tw_irr_on is bare; conventionally
        # both go together. Treat irrig=true if either appears truthy in env,
        # else fall back to case dir.
        irrig_paired = opts.get("irrig", None)
        if irrig_paired is not None or "tw_irr_on" in opts:
            irrig = (
                bool(opts.get("tw_irr_on", False))
                or (isinstance(irrig_paired, str) and _truthy(irrig_paired))
                or (isinstance(irrig_paired, bool) and irrig_paired)
            )
        elif case_mode is not None:
            irrig = case_mode.irrig
        else:
            irrig = False

        env_solar = opts.get("solar_rad_scheme")
        solar_rad_scheme = _env_or_case(env_solar, "solar_rad_scheme", "")
        solar_rad_scheme = str(solar_rad_scheme)
        if solar_rad_scheme not in ("", "top"):
            raise ValueError(
                f"solar_rad_scheme={solar_rad_scheme!r} invalid; expected '' or 'top'"
            )

        # ----- Cross-axis constraints -----
        if bgc_mode == "fates" and dynamic_vegetation:
            raise ValueError(
                "bgc_mode='fates' is incompatible with dynamic_vegetation=True; "
                "FATES is its own DGVM."
            )
        if bgc_mode == "sp" and use_fates_sp:
            raise ValueError(
                "bgc_mode='sp' (ELM Satellite Phenology) is incompatible with "
                "use_fates_sp=True. Use one or the other."
            )

        return cls(
            bgc_mode=bgc_mode,
            use_fates=use_fates,
            parteh_mode=parteh_mode,
            use_fates_nocomp=use_fates_nocomp,
            nutrient=nutrient,
            nutrient_comp_pathway=nutrient_comp_pathway,
            soil_decomp=soil_decomp,
            fates_spitfire_mode=fates_spitfire_mode,
            use_fates_planthydro=use_fates_planthydro,
            use_fates_logging=use_fates_logging,
            use_fates_sp=use_fates_sp,
            use_fates_ed_prescribed_phys=use_fates_ed_prescribed_phys,
            use_fates_fixed_biogeog=use_fates_fixed_biogeog,
            crop=crop,
            dynamic_vegetation=dynamic_vegetation,
            methane=methane,
            hydrstress=hydrstress,
            topounit=topounit,
            irrig=irrig,
            solar_rad_scheme=solar_rad_scheme,
        )

    def to_prompt_block(self) -> str:
        """Render a compact block for the AI prompt declaring active mode.

        Renders all relevant axes (hides off-default Tier 2/3 unless True).
        Goes near the top of every Phase 3 / Phase 4 prompt so the LLM can
        self-correct on retrieved content that spans multiple modes.
        """
        # ELM-only branch (FATES off): much narrower content
        if not self.use_fates:
            lines = [
                "## Active Run Configuration",
                f"- bgc_mode: {self.bgc_mode} (FATES DISABLED; FATES parameters "
                "and mechanisms do NOT apply)",
            ]
            if self.nutrient:
                lines.append(f"- Nutrient cycling: {self.nutrient.upper()}")
            if self.nutrient_comp_pathway:
                lines.append(f"- Nutrient competition: {self.nutrient_comp_pathway.upper()}")
            if self.soil_decomp:
                lines.append(f"- Soil decomposition: {self.soil_decomp}")
            tier3 = self._tier3_active_summary()
            if tier3:
                lines.append(f"- Active modifiers: {tier3}")
            return "\n".join(lines)

        # FATES-on branch
        parteh_label = {
            1: "carbon-only allocation",
            2: "CNP allocation (nutrient cycling ON)",
        }.get(self.parteh_mode, f"unknown PARTEH={self.parteh_mode}")

        comp_label = "OFF (PFTs in separate patches; ECA/RD do NOT apply)" \
            if self.use_fates_nocomp \
            else f"ON ({self.nutrient_comp_pathway.upper() or '?'} pathway)"

        nutrient_note = ""
        if self.parteh_mode == 1:
            nutrient_note = " - CNP mechanisms (PID controller, nutrient " \
                            "uptake, stoichiometry) do NOT apply to this run"
        elif self.nutrient == "cn":
            nutrient_note = " - P-cycle parameters (fates_cnp_*ptase, " \
                            "FATES_PUPTAKE_*) do NOT apply"

        lines = [
            "## Active Run Configuration",
            f"- bgc_mode: {self.bgc_mode}, FATES: enabled (PARTEH={self.parteh_mode}, {parteh_label}){nutrient_note}",
            f"- Nutrient cycling: {self.nutrient.upper() or 'NONE'}",
            f"- Competition: {comp_label}",
        ]
        if self.soil_decomp:
            lines.append(f"- Soil decomposition: {self.soil_decomp}")

        # Tier 2 FATES feature flags (only show if active)
        tier2 = self._tier2_active_summary()
        if tier2:
            lines.append(f"- FATES features: {tier2}")
        # Tier 3 (only show if active)
        tier3 = self._tier3_active_summary()
        if tier3:
            lines.append(f"- Active modifiers: {tier3}")

        return "\n".join(lines)

    def _tier2_active_summary(self) -> str:
        """One-line summary of active Tier 2 FATES feature flags."""
        active = []
        if self.fates_spitfire_mode:
            active.append(f"spitfire={self.fates_spitfire_mode}")
        if self.use_fates_planthydro:
            active.append("planthydro")
        if self.use_fates_logging:
            active.append("logging")
        if self.use_fates_sp:
            active.append("sp")
        if self.use_fates_ed_prescribed_phys:
            active.append("prescribed_phys")
        if self.use_fates_fixed_biogeog:
            active.append("fixed_biogeog")
        return ", ".join(active)

    def _tier3_active_summary(self) -> str:
        """One-line summary of active Tier 3 secondary compset modifiers."""
        active = []
        if self.crop:
            active.append("crop")
        if self.dynamic_vegetation:
            active.append("dynamic_vegetation")
        if self.methane:
            active.append("methane")
        if self.hydrstress:
            active.append("hydrstress")
        if self.topounit:
            active.append("topounit")
        if self.irrig:
            active.append("irrig")
        if self.solar_rad_scheme:
            active.append(f"solar_rad_scheme={self.solar_rad_scheme}")
        return ", ".join(active)

    def kb_source_filter(self) -> Optional[str]:
        """Return 'elm' if FATES is off (filters retrieval to ELM-only chunks),
        None otherwise (no filter; both ELM and FATES content allowed).
        """
        return "elm" if not self.use_fates else None

    def to_dict(self) -> Dict:
        return {
            # Tier 1
            "bgc_mode": self.bgc_mode,
            "use_fates": self.use_fates,
            "parteh_mode": self.parteh_mode,
            "use_fates_nocomp": self.use_fates_nocomp,
            "nutrient": self.nutrient,
            "nutrient_comp_pathway": self.nutrient_comp_pathway,
            "soil_decomp": self.soil_decomp,
            # Tier 2
            "fates_spitfire_mode": self.fates_spitfire_mode,
            "use_fates_planthydro": self.use_fates_planthydro,
            "use_fates_logging": self.use_fates_logging,
            "use_fates_sp": self.use_fates_sp,
            "use_fates_ed_prescribed_phys": self.use_fates_ed_prescribed_phys,
            "use_fates_fixed_biogeog": self.use_fates_fixed_biogeog,
            # Tier 3
            "crop": self.crop,
            "dynamic_vegetation": self.dynamic_vegetation,
            "methane": self.methane,
            "hydrstress": self.hydrstress,
            "topounit": self.topounit,
            "irrig": self.irrig,
            "solar_rad_scheme": self.solar_rad_scheme,
        }

    def to_chroma_where(self) -> Dict:
        """Build a ChromaDB ``where`` clause for the active mode.

        Each axis contributes one ``$or`` branch: the chunk passes if it is
        either flagged as universal (``applies_universal: True``) OR has the
        matching axis flag for the current value (``applies_in_<axis>_<value>:
        True``). All axes combined with ``$and``.

        Iterates over ``ALL_AXIS_VALUES`` so all 20 axes are covered
        automatically.

        Example output for default ELM run (bgc_mode='sp', use_fates=False):

            {
              "$and": [
                {"$or": [{"applies_universal": True},
                         {"applies_in_bgc_mode_sp": True}]},
                {"$or": [{"applies_universal": True},
                         {"applies_in_use_fates_false": True}]},
                ... (one $or per axis)
              ]
            }
        """
        # Map axis name → current value, for all 20 axes
        active_values: Dict[str, object] = {
            # Tier 1
            "bgc_mode": self.bgc_mode,
            "use_fates": self.use_fates,
            "parteh_mode": self.parteh_mode,
            "use_fates_nocomp": self.use_fates_nocomp,
            "nutrient": self.nutrient,
            "nutrient_comp_pathway": self.nutrient_comp_pathway,
            "soil_decomp": self.soil_decomp,
            # Tier 2
            "fates_spitfire_mode": self.fates_spitfire_mode,
            "use_fates_planthydro": self.use_fates_planthydro,
            "use_fates_logging": self.use_fates_logging,
            "use_fates_sp": self.use_fates_sp,
            "use_fates_ed_prescribed_phys": self.use_fates_ed_prescribed_phys,
            "use_fates_fixed_biogeog": self.use_fates_fixed_biogeog,
            # Tier 3
            "crop": self.crop,
            "dynamic_vegetation": self.dynamic_vegetation,
            "methane": self.methane,
            "hydrstress": self.hydrstress,
            "topounit": self.topounit,
            "irrig": self.irrig,
            "solar_rad_scheme": self.solar_rad_scheme,
        }
        clauses = []
        for axis in ALL_AXIS_VALUES:
            value = active_values[axis]
            flag_key = f"applies_in_{axis}_{_axis_value_token(value)}"
            clauses.append({
                "$or": [
                    {"applies_universal": True},
                    {flag_key: True},
                ],
            })
        return {"$and": clauses}


# =============================================================================
# Axis value enumerations (for graph_builder, validator, and to_chroma_where)
# =============================================================================

# Enumerates the legal values for each of the 20 mode dimensions.
# Source: tools/config.py:ConfigMode docstring + ELM api-43-1
# namelist_defaults.xml + components/elm/cime_config/config_component.xml.
#
# Used by:
#   - rag/graph_builder.py: to write `applies_in_<axis>_<value>` flags
#     for ALL values per axis (set False for unlisted, True for listed)
#   - tools/yaml_wiki_validator.py (Dim F): to reject typos and out-of-enum
#     values in YAML `applies_in:` blocks
#   - tools/config.py:ConfigMode.to_chroma_where(): to iterate over axes
ALL_AXIS_VALUES: Dict[str, List] = {
    # ----- Tier 1 (7 primary) -----
    "bgc_mode": ["sp", "cn", "bgc", "fates"],
    "use_fates": [True, False],
    "parteh_mode": [1, 2],
    "use_fates_nocomp": [True, False],
    "nutrient": ["", "c", "cn", "cnp"],
    "nutrient_comp_pathway": ["rd", "eca"],
    "soil_decomp": ["", "ctc", "century"],
    # ----- Tier 2 (6 FATES feature flags) -----
    "fates_spitfire_mode": [0, 1, 2],
    "use_fates_planthydro": [True, False],
    "use_fates_logging": [True, False],
    "use_fates_sp": [True, False],
    "use_fates_ed_prescribed_phys": [True, False],
    "use_fates_fixed_biogeog": [True, False],
    # ----- Tier 3 (7 secondary compset modifiers) -----
    "crop": [True, False],
    "dynamic_vegetation": [True, False],
    "methane": [True, False],
    "hydrstress": [True, False],
    "topounit": [True, False],
    "irrig": [True, False],
    "solar_rad_scheme": ["", "top"],
}

# FATES-specific axes — tagging any of these without also tagging
# `use_fates: [true]` is brittle; the validator Dim F emits a warning.
FATES_SPECIFIC_AXES = frozenset({
    "parteh_mode",
    "use_fates_nocomp",
    "nutrient",
    "nutrient_comp_pathway",
    "fates_spitfire_mode",
    "use_fates_planthydro",
    "use_fates_logging",
    "use_fates_sp",
    "use_fates_ed_prescribed_phys",
    "use_fates_fixed_biogeog",
})


def _axis_value_token(value: object) -> str:
    """Render an axis value as the token used in ``applies_in_<axis>_<value>``.

    - bool → 'true' / 'false' (lowercased)
    - int → str(int)
    - str → the string itself; '' → 'empty'
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value if value else "empty"
    return str(value)


def build_applies_in_flags(applies_in: Optional[Dict]) -> Dict[str, bool]:
    """Build chunk/node metadata flags from a YAML ``applies_in:`` block.

    Default-permissive design with two mutually exclusive states:

    - **Untagged** (``applies_in`` is None or empty dict): emits
      ``{"applies_universal": True}`` only. The chunk passes any
      ``ConfigMode.to_chroma_where()`` clause via the universal $or branch.

    - **Tagged**: per-axis flags. For each axis listed in ``applies_in``,
      write ``applies_in_<axis>_<v>: True`` for v in the listed values and
      ``False`` for v not in the listed values. For each of the 20 axes
      NOT mentioned in ``applies_in``, write ``True`` for all values
      (universal w.r.t. that axis). NO ``applies_universal`` flag.

    The metadata is suitable for ChromaDB chunk metadata or NetworkX node
    attrs. Boolean values; key names use the ``applies_in_<axis>_<token>``
    convention from ``_axis_value_token()``.

    Returns
    -------
    dict[str, bool]
        Flag dict ready to merge into chunk/node metadata.
    """
    if not applies_in:
        return {"applies_universal": True}

    flags: Dict[str, bool] = {}
    for axis, values in ALL_AXIS_VALUES.items():
        if axis in applies_in:
            listed = applies_in[axis] or []
            for v in values:
                key = f"applies_in_{axis}_{_axis_value_token(v)}"
                flags[key] = (v in listed)
        else:
            # Axis not mentioned: universal w.r.t. this axis (all values pass)
            for v in values:
                key = f"applies_in_{axis}_{_axis_value_token(v)}"
                flags[key] = True
    return flags


config = A2MCConfig()


# Convenience function to get specific ensemble paths
def get_case_path(case_num: int, phase: str = 'TRANS') -> Path:
    """Get path to a specific case output directory"""
    case_name = config.make_case_name(case_num, phase)
    return Path(config.ENSEMBLE_OUTPUT) / case_name / 'run'


def get_case_name(case_num: int, suffix: str = '', phase: str = 'TRANS') -> str:
    """Generate case name from case number"""
    if suffix:
        # For suffixed names, insert suffix before phase
        base = config.make_case_name(case_num, phase)
        # Replace _{PHASE} with _{suffix}_{PHASE}
        return base.replace(f"_{phase}", f"_{suffix}_{phase}")
    return config.make_case_name(case_num, phase)


def get_extracted_data_path(case_name: str) -> Path:
    """Get path to extracted monthly data for a case"""
    return Path(config.EXTRACTED_DATA) / f"{case_name}_all_variables_monthly.nc"


if __name__ == '__main__':
    # Test the config
    config.print_config()

    print("\nPath validation:")
    for name, info in config.validate_paths().items():
        status = "EXISTS" if info['exists'] else "MISSING"
        print(f"  {name}: {status}")
        print(f"    {info['path']}")
