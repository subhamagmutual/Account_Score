"""
Validation module for cross-population analysis.

Provides tools for:
- Population comparison (distributions, statistics)
- Score portability validation
- Cross-population testing
"""

from .population_comparison import PopulationComparator

__all__ = [
    'PopulationComparator',
]
