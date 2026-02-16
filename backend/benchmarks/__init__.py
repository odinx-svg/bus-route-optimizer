"""
Sistema de benchmarks para comparar algoritmos de optimización.
"""

try:
    from backend.benchmarks.suite import BenchmarkSuite, BenchmarkResult
    from backend.benchmarks.metrics import (
        calculate_efficiency_metrics,
        calculate_robustness_metrics,
        calculate_multi_objective_score,
        EfficiencyMetrics,
        RobustnessMetrics
    )
except ImportError:
    from benchmarks.suite import BenchmarkSuite, BenchmarkResult
    from benchmarks.metrics import (
        calculate_efficiency_metrics,
        calculate_robustness_metrics,
        calculate_multi_objective_score,
        EfficiencyMetrics,
        RobustnessMetrics
    )

__all__ = [
    'BenchmarkSuite',
    'BenchmarkResult',
    'calculate_efficiency_metrics',
    'calculate_robustness_metrics',
    'calculate_multi_objective_score',
    'EfficiencyMetrics',
    'RobustnessMetrics'
]
