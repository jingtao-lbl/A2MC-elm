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
    source use_cases/Kougarok/config/kougarok_config.sh
    python tools/your_script.py

Author: A2MC Framework
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


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
        """E3SM/FATES source code root"""
        return os.environ.get('A2MC_E3SM_ROOT',
            '/global/cfs/cdirs/m2467/jingtao/E3SM_FATES')

    @property
    def OUTPUT_ROOT(self) -> str:
        """Output root for simulation results"""
        return os.environ.get('A2MC_OUTPUT_ROOT',
            '/global/cfs/cdirs/m2467/jingtao')

    @property
    def SCRIPTS_DIR(self) -> str:
        """Scripts directory (where case scripts are generated)"""
        return os.environ.get('A2MC_SCRIPTS_DIR',
            '/pscratch/sd/j/jingtao/CaseScripts')

    @property
    def PARAM_DIR(self) -> str:
        """FATES parameter files directory"""
        return os.environ.get('A2MC_PARAM_DIR',
            '/dvs_ro/u1/j/jingtao/E3SM_Aid/FATES-ParameterFiles')

    @property
    def BASE_PARAM_FILE(self) -> str:
        """Base FATES parameter file (template)"""
        return os.environ.get('A2MC_BASE_PARAM_FILE',
            '/dvs_ro/u1/j/jingtao/FATES-DataParameterFiles/fates_params_api25.5.0_12pft_c230710.nc')

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
        - sobol: n_samples × (2 × n_params + 2)
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
            return self.N_SAMPLES * (2 * self.N_PARAMS + 2)
        else:
            return 0  # custom or unknown

    @property
    def SAMPLING_SCHEME(self) -> str:
        """Sampling scheme (morris, lhs, sobol, custom)"""
        return os.environ.get('A2MC_SAMPLING_SCHEME', 'morris')

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
    def AI_MODEL(self) -> str:
        """
        AI model to use for reasoning (Claude API).

        Examples:
        - claude-sonnet-4-20250514 (default, balanced)
        - claude-opus-4-20250514 (most capable)
        - claude-haiku-3-20240307 (fastest, cheapest)
        """
        return os.environ.get('A2MC_AI_MODEL', 'claude-sonnet-4-20250514')

    @property
    def AI_MAX_TOKENS(self) -> int:
        """Maximum tokens for AI responses"""
        return int(os.environ.get('A2MC_AI_MAX_TOKENS', '4096'))

    @property
    def AI_API_KEY_ENV(self) -> str:
        """
        Environment variable name containing the API key.
        Default: AI_API_KEY

        Users should set their API key in this env var.
        Supports any AI provider (Anthropic, OpenAI, etc.)
        """
        return os.environ.get('A2MC_AI_API_KEY_ENV', 'AI_API_KEY')

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

    def is_configured(self) -> bool:
        """Check if site configuration has been loaded"""
        return bool(self.SITE_NAME)

    def validate_paths(self) -> dict:
        """Validate that key paths exist"""
        paths_to_check = [
            ('ENSEMBLE_OUTPUT', self.ENSEMBLE_OUTPUT),
            ('EXTRACTED_DATA', self.EXTRACTED_DATA),
            ('CASE_SCRIPTS', self.CASE_SCRIPTS),
            ('PARAM_DIR', self.PARAM_DIR),
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
        print(f"  E3SM_ROOT:       {self.E3SM_ROOT}")
        print(f"  OUTPUT_ROOT:     {self.OUTPUT_ROOT}")
        print(f"  SCRIPTS_DIR:     {self.SCRIPTS_DIR}")
        print(f"  ENSEMBLE_OUTPUT: {self.ENSEMBLE_OUTPUT}")
        print(f"  EXTRACTED_DATA:  {self.EXTRACTED_DATA}")
        print(f"  CASE_SCRIPTS:    {self.CASE_SCRIPTS}")
        print("")
        print("Parameter Files:")
        print(f"  PARAM_DIR:          {self.PARAM_DIR}")
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
        print(f"  AI_MODEL:        {self.AI_MODEL}")
        print(f"  AI_MAX_TOKENS:   {self.AI_MAX_TOKENS}")
        print(f"  API_KEY_ENV:     {self.AI_API_KEY_ENV}")
        api_key = self.get_ai_api_key()
        print(f"  API_KEY_SET:     {'Yes' if api_key else 'No'}")
        print("=" * 60)


# Global config instance
config = A2MCConfig()


# Convenience function to get specific ensemble paths
def get_case_path(case_num: int, phase: str = 'TRANS') -> Path:
    """Get path to a specific case output directory"""
    case_name = f"{config.CASE_PREFIX}_PtCNPEn{case_num}_{phase}"
    return Path(config.ENSEMBLE_OUTPUT) / case_name / 'run'


def get_case_name(case_num: int, suffix: str = '', phase: str = 'TRANS') -> str:
    """Generate case name from case number"""
    if suffix:
        return f"{config.CASE_PREFIX}_PtCNPEn{case_num}_{suffix}_{phase}"
    return f"{config.CASE_PREFIX}_PtCNPEn{case_num}_{phase}"


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
