"""
Validación y testing para soluciones de optimización.
"""

try:
    from backend.validation.monte_carlo import MonteCarloValidator, SimulationResult, check_schedule_feasibility
except ImportError:
    from validation.monte_carlo import MonteCarloValidator, SimulationResult, check_schedule_feasibility

__all__ = ['MonteCarloValidator', 'SimulationResult', 'check_schedule_feasibility']
