"""Optimizer package for pluggable solver orchestration."""

from .config import OptimizerConfig
from .engine import OptimizerEngine
from .greedy_builder import build_greedy_schedule
from .solver_interface import SolverResult

__all__ = [
    "OptimizerConfig",
    "OptimizerEngine",
    "SolverResult",
    "build_greedy_schedule",
]
