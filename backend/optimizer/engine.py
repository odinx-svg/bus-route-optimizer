"""High-level optimizer engine that selects a solver backend and prepares warm starts."""

from __future__ import annotations

from typing import Dict, List, Optional

from models import BusSchedule, Route

from .config import OptimizerConfig
from .greedy_builder import build_greedy_schedule
from .selection import analyze_solver_selection
from .solver_interface import ProgressCallback, SolverResult
from .solver_cpsat import CpSatOptimizerSolver
from .solver_pulp import PulpOptimizerSolver


class OptimizerEngine:
    """Orchestrates warm-start creation and solver backend selection."""

    def __init__(self) -> None:
        self._pulp_solver = PulpOptimizerSolver()
        self._cp_sat_solver = CpSatOptimizerSolver()
        self._last_result: Optional[SolverResult] = None

    def _select_solver(self, config: OptimizerConfig, route_count: int):
        selection = analyze_solver_selection(
            config,
            route_count=route_count,
            cp_sat_available=self._cp_sat_solver.is_available,
        )
        solver_name = selection.get("selected_solver")
        solver = self._cp_sat_solver if solver_name == self._cp_sat_solver.name else self._pulp_solver
        return solver, selection

    def optimize(
        self,
        routes: List[Route],
        config: Optional[OptimizerConfig] = None,
        progress_callback: ProgressCallback = None,
    ) -> SolverResult:
        runtime_config = config or OptimizerConfig()
        initial_schedule = None
        if runtime_config.enable_greedy_warm_start and routes:
            initial_schedule = build_greedy_schedule(routes)
        solver, selection = self._select_solver(runtime_config, len(routes))
        result = solver.optimize(
            routes,
            runtime_config,
            progress_callback=progress_callback,
            initial_schedule=initial_schedule,
        )
        result.diagnostics.setdefault("requested_solver", runtime_config.preferred_solver)
        result.diagnostics.setdefault("selected_solver", solver.name)
        result.diagnostics.setdefault("solver_selection_reason", selection.get("reason_code"))
        result.diagnostics.setdefault("solver_selection_label", selection.get("reason_label"))
        result.diagnostics.setdefault("solver_selection_detail", selection.get("reason_detail"))
        result.diagnostics.setdefault("solver_selection", dict(selection))
        result.diagnostics.setdefault("solver_fallback_used", bool(selection.get("fallback_used")))
        result.diagnostics.setdefault("cp_sat_available", bool(self._cp_sat_solver.is_available))
        if initial_schedule is not None:
            result.diagnostics.setdefault("greedy_seed", {
                "bus_count": len(initial_schedule),
                "route_count": sum(len(bus.items) for bus in initial_schedule),
            })
        self._last_result = result
        return result

    def get_last_diagnostics(self) -> Dict[str, object]:
        if self._last_result is None:
            return {}
        return dict(self._last_result.diagnostics or {})
