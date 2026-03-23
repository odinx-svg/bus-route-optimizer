"""Adapter for the current optimizer_v6 PuLP-based backend."""

from __future__ import annotations

from typing import List, Optional

from models import BusSchedule, Route

from .config import OptimizerConfig
from .solver_interface import ProgressCallback, SolverInterface, SolverResult

try:
    from optimizer_v6 import get_last_optimization_diagnostics, optimize_v6
except ImportError:  # pragma: no cover - fallback for package execution
    from backend.optimizer_v6 import get_last_optimization_diagnostics, optimize_v6


class PulpOptimizerSolver(SolverInterface):
    """Current production solver wrapper around optimizer_v6."""

    name = "pulp_v6"
    supports_warm_start = False

    def optimize(
        self,
        routes: List[Route],
        config: OptimizerConfig,
        progress_callback: ProgressCallback = None,
        initial_schedule: Optional[List[BusSchedule]] = None,
    ) -> SolverResult:
        schedule = optimize_v6(
            routes,
            progress_callback=progress_callback,
            use_ml_assignment=config.use_ml_assignment,
            balance_load=config.balance_load,
            load_balance_hard_spread_limit=config.load_balance_hard_spread_limit,
            load_balance_target_band=config.load_balance_target_band,
            route_load_constraints=config.route_load_constraints,
        )
        diagnostics = dict(get_last_optimization_diagnostics() or {})
        diagnostics.update({
            "solver_name": self.name,
            "objective_mode": config.objective_mode,
            "objective_weights": config.objective_weights,
            "warm_start_available": bool(initial_schedule),
            "warm_start_used": False,
            "preferred_solver": config.preferred_solver,
        })
        if initial_schedule is not None:
            diagnostics["warm_start_bus_count"] = len(initial_schedule)
        return SolverResult(
            schedule=schedule,
            diagnostics=diagnostics,
            solver_name=self.name,
            initial_schedule=initial_schedule,
        )
