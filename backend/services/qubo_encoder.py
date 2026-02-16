"""
QUBO encoder for hybrid route assignment refinement.

This module encodes a reduced route-to-bus reassignment subproblem into a QUBO
formulation that can be solved by a quantum-inspired backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


QuboMatrix = Dict[Tuple[int, int], float]


@dataclass
class QuboVariable:
    """Decision variable x_i for assigning one route to one candidate bus/slot."""

    index: int
    route_id: str
    source_bus_id: Optional[str]
    target_bus_id: str
    insertion_index: int
    candidate_cost: float
    metadata: Dict[str, Any]


@dataclass
class QuboProblem:
    """Container for a QUBO optimization problem."""

    q: QuboMatrix
    variables: List[QuboVariable]
    route_to_var_indexes: Dict[str, List[int]]
    metadata: Dict[str, Any]


def _add_q(q: QuboMatrix, i: int, j: int, value: float) -> None:
    """Add value to QUBO entry preserving upper-triangular keys."""
    a, b = (i, j) if i <= j else (j, i)
    q[(a, b)] = q.get((a, b), 0.0) + float(value)


def build_assignment_qubo(
    route_candidates: Dict[str, List[Dict[str, Any]]],
    assignment_penalty: float = 900.0,
    bus_conflict_penalty: float = 250.0,
) -> QuboProblem:
    """
    Build a QUBO for selecting exactly one candidate assignment per route.

    Args:
        route_candidates:
            Mapping route_id -> list of candidate dicts:
            {
              "target_bus_id": str,
              "source_bus_id": Optional[str],
              "insertion_index": int,
              "cost": float,
              "window_start_min": int,
              "window_end_min": int,
              ...
            }
        assignment_penalty:
            Lambda for one-hot assignment constraints.
        bus_conflict_penalty:
            Penalty for selecting candidates that overlap in the same bus.
    """
    q: QuboMatrix = {}
    variables: List[QuboVariable] = []
    route_to_var_indexes: Dict[str, List[int]] = {}

    for route_id, candidates in route_candidates.items():
        indexes: List[int] = []
        for candidate in candidates:
            idx = len(variables)
            variable = QuboVariable(
                index=idx,
                route_id=route_id,
                source_bus_id=candidate.get("source_bus_id"),
                target_bus_id=str(candidate.get("target_bus_id")),
                insertion_index=int(candidate.get("insertion_index", 0)),
                candidate_cost=float(candidate.get("cost", 0.0)),
                metadata=dict(candidate),
            )
            variables.append(variable)
            indexes.append(idx)
            _add_q(q, idx, idx, variable.candidate_cost)
        route_to_var_indexes[route_id] = indexes

    # One-hot constraints: for each route, exactly one variable selected.
    # penalty * (sum(x_i)-1)^2 = penalty * (sum x_i + 2 sum_{i<j} x_i x_j - 2 sum x_i + 1)
    # => linear -penalty; pair +2*penalty
    for _, indexes in route_to_var_indexes.items():
        if not indexes:
            continue
        for i in indexes:
            _add_q(q, i, i, -assignment_penalty)
        for p in range(len(indexes)):
            for r in range(p + 1, len(indexes)):
                _add_q(q, indexes[p], indexes[r], 2.0 * assignment_penalty)

    # Soft conflict penalty on same target bus + overlapping windows.
    for i in range(len(variables)):
        vi = variables[i]
        w1s = int(vi.metadata.get("window_start_min", -1))
        w1e = int(vi.metadata.get("window_end_min", -1))
        for j in range(i + 1, len(variables)):
            vj = variables[j]
            if vi.route_id == vj.route_id:
                continue
            if vi.target_bus_id != vj.target_bus_id:
                continue
            w2s = int(vj.metadata.get("window_start_min", -1))
            w2e = int(vj.metadata.get("window_end_min", -1))
            if w1s < 0 or w1e < 0 or w2s < 0 or w2e < 0:
                continue
            overlaps = not (w1e <= w2s or w2e <= w1s)
            if overlaps:
                _add_q(q, i, j, bus_conflict_penalty)

    metadata = {
        "num_variables": len(variables),
        "num_routes": len(route_candidates),
        "assignment_penalty": assignment_penalty,
        "bus_conflict_penalty": bus_conflict_penalty,
    }
    return QuboProblem(
        q=q,
        variables=variables,
        route_to_var_indexes=route_to_var_indexes,
        metadata=metadata,
    )


def evaluate_qubo_energy(q: QuboMatrix, active_indexes: List[int]) -> float:
    """Compute E = x'Qx for a binary selection vector represented by active indexes."""
    active = set(active_indexes)
    energy = 0.0
    for (i, j), value in q.items():
        if i in active and j in active:
            energy += value
    return energy

