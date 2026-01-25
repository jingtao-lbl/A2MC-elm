"""
Phase 0: Sampling Design

Generate parameter ensemble using Morris, Sobol, or LHS sampling.

Scripts:
    create_morris_ensemble.py - Generate Morris OAT sampling design
"""

# Lazy imports to avoid dependency issues
def get_morris_generator():
    """Get MorrisEnsembleGenerator class."""
    from .create_morris_ensemble import MorrisEnsembleGenerator
    return MorrisEnsembleGenerator
