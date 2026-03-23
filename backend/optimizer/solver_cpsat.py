"""CP-SAT optimizer adapter for single-day abstract bus chaining."""

from __future__ import annotations

import time as time_module
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from models import BusSchedule, Route

from .config import OptimizerConfig
from .solver_interface import ProgressCallback, SolverInterface, SolverResult

try:  # pragma: no cover - runtime fallback in desktop/source modes
    from ortools.sat.python import cp_model

    CP_SAT_IMPORT_ERROR: Optional[str] = None
except Exception as exc:  # pragma: no cover - tested via availability flag
    cp_model = None
    CP_SAT_IMPORT_ERROR = str(exc)

try:  # pragma: no cover - import resolution differs in tests/runtime
    from optimizer_v6 import (
        CROSS_BLOCK_CAPACITY_BONUS,
        CROSS_BLOCK_FLEX_MINUTES,
        CROSS_BLOCK_SCHOOL_BONUS,
        CROSS_BLOCK_SMALL_SERVICE_BONUS,
        RouteJob,
        _entry_arrival_max,
        _entry_arrival_min,
        _exit_departure_max,
        _exit_departure_min,
        _job_capacity,
        _jobs_capacity_compatible,
        _make_item,
        _osrm_or_fallback_with_connection_buffer,
        _pair_priority_bonus,
        coords_valid,
        haversine_km,
        prepare_jobs,
    )
except ImportError:  # pragma: no cover
    from backend.optimizer_v6 import (
        CROSS_BLOCK_CAPACITY_BONUS,
        CROSS_BLOCK_FLEX_MINUTES,
        CROSS_BLOCK_SCHOOL_BONUS,
        CROSS_BLOCK_SMALL_SERVICE_BONUS,
        RouteJob,
        _entry_arrival_max,
        _entry_arrival_min,
        _exit_departure_max,
        _exit_departure_min,
        _job_capacity,
        _jobs_capacity_compatible,
        _make_item,
        _osrm_or_fallback_with_connection_buffer,
        _pair_priority_bonus,
        coords_valid,
        haversine_km,
        prepare_jobs,
    )

try:  # pragma: no cover
    from router_service import get_travel_time_matrix
except ImportError:  # pragma: no cover
    from backend.router_service import get_travel_time_matrix


@dataclass(frozen=True)
class EdgeMetric:
    """Transition candidate between two jobs."""

    src: int
    dst: int
    travel_minutes: int
    deadhead_km: float
    idle_gap_minutes: int
    score: int


class CpSatOptimizerSolver(SolverInterface):
    """Minimum path cover solver over feasible temporal transitions."""

    name = "cp_sat"
    supports_warm_start = True

    def __init__(self) -> None:
        self._availability_error = CP_SAT_IMPORT_ERROR

    @property
    def is_available(self) -> bool:
        return cp_model is not None

    def optimize(
        self,
        routes: List[Route],
        config: OptimizerConfig,
        progress_callback: ProgressCallback = None,
        initial_schedule: Optional[List[BusSchedule]] = None,
    ) -> SolverResult:
        if cp_model is None:
            raise RuntimeError(f"CP-SAT backend unavailable: {self._availability_error or 'ortools not installed'}")

        started_at = time_module.perf_counter()
        jobs = self._prepare_day_jobs(routes)
        if not jobs:
            return SolverResult(
                schedule=[],
                diagnostics={
                    "solver_name": self.name,
                    "solver_status": "optimal",
                    "total_routes": 0,
                    "pre_split_buses": 0,
                    "best_buses": 0,
                    "split_count": 0,
                    "lower_bound_buses": 0,
                    "optimality_gap": 0.0,
                    "pairs_total": 0,
                    "pairs_pruned": 0,
                },
                solver_name=self.name,
                initial_schedule=initial_schedule,
            )

        if progress_callback:
            progress_callback("prepare", 10, f"Preparando modelo CP-SAT para {len(jobs)} rutas")

        transition_metrics, pairs_total = self._build_transition_metrics(jobs, config)
        if progress_callback:
            progress_callback("build_model", 25, f"Generando modelo con {len(transition_metrics)} transiciones viables")

        selected_edges, solver_status = self._solve_path_cover(
            jobs=jobs,
            transition_metrics=transition_metrics,
            config=config,
            initial_schedule=initial_schedule,
        )
        if progress_callback:
            progress_callback("build_schedule", 70, "Construyendo horario desde solucion CP-SAT")

        schedule, schedule_meta = self._build_schedule_from_edges(jobs, transition_metrics, selected_edges)
        best_buses = len(schedule)
        pre_split_buses = max(0, len(jobs) - len(selected_edges))
        split_count = max(0, best_buses - pre_split_buses)
        deadheads = [item.deadhead_minutes for bus in schedule for item in bus.items if item.deadhead_minutes > 0]

        diagnostics = {
            "solver_name": self.name,
            "solver_status": "optimal" if split_count == 0 and solver_status in {"OPTIMAL", "FEASIBLE"} else "feasible",
            "cp_sat_status": solver_status,
            "objective_mode": config.objective_mode,
            "objective_weights": config.objective_weights,
            "total_routes": len(jobs),
            "pre_split_buses": pre_split_buses,
            "best_buses": best_buses,
            "split_count": split_count,
            "lower_bound_buses": pre_split_buses,
            "optimality_gap": 0.0,
            "pairs_total": pairs_total,
            "pairs_pruned": max(0, pairs_total - len(transition_metrics)),
            "avg_positioning_minutes": round(sum(deadheads) / len(deadheads), 2) if deadheads else 0.0,
            "max_positioning_minutes": int(max(deadheads)) if deadheads else 0,
            "warm_start_available": bool(initial_schedule),
            "warm_start_used": bool(initial_schedule),
            "warm_start_bus_count": len(initial_schedule or []),
            "phase_time_sec": {
                "total": round(max(0.0, time_module.perf_counter() - started_at), 3),
            },
            "candidate_edge_count": len(transition_metrics),
            "capacity_splits": int(schedule_meta["capacity_splits"]),
            "time_window_splits": int(schedule_meta["time_window_splits"]),
        }
        return SolverResult(
            schedule=schedule,
            diagnostics=diagnostics,
            solver_name=self.name,
            initial_schedule=initial_schedule,
        )

    def _prepare_day_jobs(self, routes: List[Route]) -> List[RouteJob]:
        block_jobs = prepare_jobs(routes)
        jobs: List[RouteJob] = []
        for block in (1, 2, 3, 4):
            jobs.extend(sorted(block_jobs.get(block, []), key=lambda job: (job.scheduled_start_min, job.original_index)))
        return jobs

    def _job_start_bounds(self, job: RouteJob) -> Tuple[int, int]:
        if str(job.route_type or "").lower() == "entry":
            return (_entry_arrival_min(job) - int(job.duration_minutes), _entry_arrival_max(job) - int(job.duration_minutes))
        return (_exit_departure_min(job), _exit_departure_max(job))

    def _job_end_bounds(self, job: RouteJob) -> Tuple[int, int]:
        start_min, start_max = self._job_start_bounds(job)
        duration = int(job.duration_minutes)
        return (start_min + duration, start_max + duration)

    def _compute_travel_matrix(self, jobs: List[RouteJob]) -> List[List[Optional[int]]]:
        if not jobs:
            return []
        sources = [tuple(job.end_loc) for job in jobs]
        destinations = [tuple(job.start_loc) for job in jobs]
        try:
            matrix = get_travel_time_matrix(sources, destinations)
            if matrix:
                return matrix
        except Exception:
            pass
        return [[None for _ in jobs] for _ in jobs]

    def _build_transition_metrics(
        self,
        jobs: List[RouteJob],
        config: OptimizerConfig,
    ) -> Tuple[Dict[Tuple[int, int], EdgeMetric], int]:
        n = len(jobs)
        if n <= 1:
            return {}, 0
        matrix = self._compute_travel_matrix(jobs)
        total_pairs = n * (n - 1)
        transition_metrics: Dict[Tuple[int, int], EdgeMetric] = {}
        weights = config.objective_weights
        bus_weight = max(1, int(round(float(weights.get("buses", 1000.0)) * 100)))
        deadhead_weight = max(1, int(round(float(weights.get("deadhead_km", 10.0)) * 10)))
        gap_weight = max(1, int(round(float(weights.get("time_shift_minutes", 5.0)) * 4)))

        for src in range(n):
            src_job = jobs[src]
            _, src_end_latest = self._job_end_bounds(src_job)
            src_end_earliest, _ = self._job_end_bounds(src_job)
            for dst in range(n):
                if src == dst:
                    continue
                dst_job = jobs[dst]
                if (src_job.scheduled_start_min, src_job.original_index) >= (
                    dst_job.scheduled_start_min,
                    dst_job.original_index,
                ):
                    continue
                if not _jobs_capacity_compatible(src_job, dst_job):
                    continue
                dst_start_min, dst_start_max = self._job_start_bounds(dst_job)
                if src_end_earliest > dst_start_max + CROSS_BLOCK_FLEX_MINUTES:
                    continue

                osrm_minutes = None
                if matrix and src < len(matrix) and dst < len(matrix[src]):
                    osrm_minutes = matrix[src][dst]
                if not coords_valid(src_job.end_loc[0], src_job.end_loc[1]) or not coords_valid(
                    dst_job.start_loc[0], dst_job.start_loc[1]
                ):
                    travel_minutes = _osrm_or_fallback_with_connection_buffer(src_job.end_loc, dst_job.start_loc, None)
                else:
                    travel_minutes = _osrm_or_fallback_with_connection_buffer(
                        src_job.end_loc,
                        dst_job.start_loc,
                        osrm_minutes,
                    )

                if src_end_earliest + travel_minutes > dst_start_max + CROSS_BLOCK_FLEX_MINUTES:
                    continue

                nominal_gap = max(0, int(dst_job.scheduled_start_min) - (int(src_job.scheduled_end_min) + travel_minutes))
                deadhead_km = haversine_km(
                    float(src_job.end_loc[0]),
                    float(src_job.end_loc[1]),
                    float(dst_job.start_loc[0]),
                    float(dst_job.start_loc[1]),
                )
                pair_bonus = _pair_priority_bonus(src_job, dst_job)
                if src_job.school_name and dst_job.school_name and src_job.school_name == dst_job.school_name:
                    pair_bonus += CROSS_BLOCK_SCHOOL_BONUS
                pair_bonus += CROSS_BLOCK_CAPACITY_BONUS
                if _job_capacity(src_job) <= 9 and _job_capacity(dst_job) <= 9:
                    pair_bonus += CROSS_BLOCK_SMALL_SERVICE_BONUS
                score = (
                    bus_weight
                    - int(round(float(deadhead_km) * deadhead_weight))
                    - (nominal_gap * gap_weight)
                    + int(round(pair_bonus * 25.0))
                )
                transition_metrics[(src, dst)] = EdgeMetric(
                    src=src,
                    dst=dst,
                    travel_minutes=int(max(0, travel_minutes)),
                    deadhead_km=float(deadhead_km),
                    idle_gap_minutes=int(nominal_gap),
                    score=int(score),
                )

        return transition_metrics, total_pairs

    def _solve_path_cover(
        self,
        jobs: List[RouteJob],
        transition_metrics: Dict[Tuple[int, int], EdgeMetric],
        config: OptimizerConfig,
        initial_schedule: Optional[List[BusSchedule]],
    ) -> Tuple[Set[Tuple[int, int]], str]:
        if not transition_metrics:
            return set(), "OPTIMAL"

        model = cp_model.CpModel()
        edge_vars: Dict[Tuple[int, int], "cp_model.IntVar"] = {
            edge: model.NewBoolVar(f"edge_{src}_{dst}")
            for edge, (src, dst) in zip(transition_metrics.keys(), transition_metrics.keys())
        }

        incoming: Dict[int, List["cp_model.IntVar"]] = {idx: [] for idx in range(len(jobs))}
        outgoing: Dict[int, List["cp_model.IntVar"]] = {idx: [] for idx in range(len(jobs))}
        for (src, dst), var in edge_vars.items():
            outgoing[src].append(var)
            incoming[dst].append(var)

        for idx in range(len(jobs)):
            if incoming[idx]:
                model.Add(sum(incoming[idx]) <= 1)
            if outgoing[idx]:
                model.Add(sum(outgoing[idx]) <= 1)

        objective_terms = [
            int(metric.score) * edge_vars[(metric.src, metric.dst)]
            for metric in transition_metrics.values()
        ]
        model.Maximize(sum(objective_terms))

        if initial_schedule:
            warm_edges = self._warm_start_edges(jobs, initial_schedule, transition_metrics)
            for edge in warm_edges:
                var = edge_vars.get(edge)
                if var is not None:
                    model.AddHint(var, 1)

        solver = cp_model.CpSolver()
        if config.time_limit_seconds:
            solver.parameters.max_time_in_seconds = float(config.time_limit_seconds)
        solver.parameters.num_search_workers = 8
        status = solver.Solve(model)

        selected_edges: Set[Tuple[int, int]] = set()
        for edge, var in edge_vars.items():
            if solver.Value(var) > 0:
                selected_edges.add(edge)
        return selected_edges, solver.StatusName(status)

    def _warm_start_edges(
        self,
        jobs: List[RouteJob],
        initial_schedule: List[BusSchedule],
        transition_metrics: Dict[Tuple[int, int], EdgeMetric],
    ) -> Set[Tuple[int, int]]:
        route_to_index = {job.route.id: idx for idx, job in enumerate(jobs)}
        warm_edges: Set[Tuple[int, int]] = set()
        valid_edges = set(transition_metrics.keys())
        for bus in initial_schedule or []:
            ordered_items = sorted(bus.items, key=lambda item: (item.start_time.hour, item.start_time.minute))
            for current, nxt in zip(ordered_items, ordered_items[1:]):
                src = route_to_index.get(current.route_id)
                dst = route_to_index.get(nxt.route_id)
                if src is None or dst is None:
                    continue
                if (src, dst) in valid_edges:
                    warm_edges.add((src, dst))
        return warm_edges

    def _build_schedule_from_edges(
        self,
        jobs: List[RouteJob],
        transition_metrics: Dict[Tuple[int, int], EdgeMetric],
        selected_edges: Set[Tuple[int, int]],
    ) -> Tuple[List[BusSchedule], Dict[str, int]]:
        successors: Dict[int, int] = {src: dst for src, dst in selected_edges}
        predecessors: Dict[int, int] = {dst: src for src, dst in selected_edges}

        starts = [idx for idx in range(len(jobs)) if idx not in predecessors]
        visited: Set[int] = set()
        chains: List[List[int]] = []
        for start in sorted(starts, key=lambda idx: (jobs[idx].scheduled_start_min, jobs[idx].original_index)):
            chain: List[int] = []
            current = start
            chain_seen: Set[int] = set()
            while current not in chain_seen and current not in visited:
                chain_seen.add(current)
                visited.add(current)
                chain.append(current)
                if current not in successors:
                    break
                current = successors[current]
            if chain:
                chains.append(chain)
        for idx in range(len(jobs)):
            if idx not in visited:
                chains.append([idx])

        schedule: List[BusSchedule] = []
        capacity_splits = 0
        time_window_splits = 0

        def _finalize_bus(bus_id: str, chain_jobs: List[int], items: List[object]) -> None:
            if not items:
                return
            schedule.append(
                BusSchedule(
                    bus_id=bus_id,
                    items=list(items),
                    min_required_seats=max(int(_job_capacity(jobs[idx])) for idx in chain_jobs) if chain_jobs else None,
                )
            )

        bus_counter = 1
        for chain in chains:
            current_items: List[object] = []
            current_chain_jobs: List[int] = []
            previous_idx: Optional[int] = None
            previous_end: Optional[int] = None

            for idx in chain:
                job = jobs[idx]
                start_min, start_max = self._job_start_bounds(job)
                nominal_start = int(job.scheduled_start_min)
                deadhead = 0
                if previous_idx is not None and previous_end is not None:
                    deadhead = int(transition_metrics.get((previous_idx, idx), EdgeMetric(previous_idx, idx, 0, 0.0, 0, 0)).travel_minutes)
                    candidate_start = max(start_min, previous_end + deadhead)
                else:
                    candidate_start = start_min

                if current_chain_jobs and not self._chain_capacity_consistent(current_chain_jobs + [idx], jobs):
                    _finalize_bus(f"B{bus_counter:03d}", current_chain_jobs, current_items)
                    bus_counter += 1
                    current_items = []
                    current_chain_jobs = []
                    previous_idx = None
                    previous_end = None
                    capacity_splits += 1
                    candidate_start = start_min
                    deadhead = 0

                chosen_start = candidate_start
                if nominal_start >= chosen_start and nominal_start <= start_max:
                    chosen_start = nominal_start
                if chosen_start > start_max:
                    _finalize_bus(f"B{bus_counter:03d}", current_chain_jobs, current_items)
                    bus_counter += 1
                    current_items = []
                    current_chain_jobs = []
                    previous_idx = None
                    previous_end = None
                    time_window_splits += 1
                    chosen_start = min(max(start_min, nominal_start), start_max)
                    deadhead = 0

                chosen_end = chosen_start + int(job.duration_minutes)
                shift = int(job.time_minutes - chosen_end) if job.route_type == "entry" else int(chosen_start - job.time_minutes)
                current_items.append(_make_item(job, chosen_start, chosen_end, shift, deadhead))
                current_chain_jobs.append(idx)
                previous_idx = idx
                previous_end = chosen_end

            _finalize_bus(f"B{bus_counter:03d}", current_chain_jobs, current_items)
            bus_counter += 1

        return schedule, {
            "capacity_splits": capacity_splits,
            "time_window_splits": time_window_splits,
        }

    def _chain_capacity_consistent(self, chain: List[int], jobs: List[RouteJob]) -> bool:
        if not chain:
            return True
        low = 1
        high = 10_000
        for idx in chain:
            job_low, job_high = self._job_capacity_range(jobs[idx])
            low = max(low, job_low)
            high = min(high, job_high)
            if low > high:
                return False
        return True

    def _job_capacity_range(self, job: RouteJob) -> Tuple[int, int]:
        vehicle_min = int(getattr(job.route, "vehicle_capacity_min", 0) or 0)
        vehicle_max = int(getattr(job.route, "vehicle_capacity_max", 0) or 0)
        demand = max(1, int(_job_capacity(job)))
        if vehicle_min > 0 and vehicle_max > 0:
            return (min(vehicle_min, vehicle_max), max(vehicle_min, vehicle_max))
        if vehicle_min > 0:
            return (vehicle_min, max(vehicle_min, demand))
        if vehicle_max > 0:
            return (min(vehicle_max, demand), max(vehicle_max, demand))
        return (demand, max(demand, demand + 20))

