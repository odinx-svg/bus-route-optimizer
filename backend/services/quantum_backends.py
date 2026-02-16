"""
Quantum-inspired QUBO solvers.

Phase 1 uses a simulated annealing backend to provide a production-safe
alternative before integrating external quantum hardware providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Dict, List, Optional, Set, Tuple

try:
    from services.qubo_encoder import QuboProblem, evaluate_qubo_energy
except ImportError:
    from backend.services.qubo_encoder import QuboProblem, evaluate_qubo_energy


@dataclass
class QuboSolution:
    active_indexes: List[int]
    energy: float
    iterations: int
    accepted_moves: int


def _initial_one_hot_solution(problem: QuboProblem, rng: Random) -> Set[int]:
    active: Set[int] = set()
    for _, indexes in problem.route_to_var_indexes.items():
        if not indexes:
            continue
        active.add(rng.choice(indexes))
    return active


def _neighbor_one_hot(problem: QuboProblem, active: Set[int], rng: Random) -> Set[int]:
    next_active = set(active)
    route_ids = list(problem.route_to_var_indexes.keys())
    if not route_ids:
        return next_active

    route_id = rng.choice(route_ids)
    candidates = problem.route_to_var_indexes.get(route_id, [])
    if len(candidates) <= 1:
        return next_active

    current_index = next((idx for idx in candidates if idx in next_active), None)
    if current_index is None:
        current_index = rng.choice(candidates)
        next_active.add(current_index)
        return next_active

    alternatives = [idx for idx in candidates if idx != current_index]
    chosen = rng.choice(alternatives)
    next_active.remove(current_index)
    next_active.add(chosen)
    return next_active


def solve_qubo_simulated_annealing(
    problem: QuboProblem,
    *,
    max_iterations: int = 3500,
    start_temperature: float = 6.0,
    end_temperature: float = 0.05,
    seed: Optional[int] = None,
) -> QuboSolution:
    """
    Solve QUBO using simulated annealing with one-hot neighborhood moves.
    """
    rng = Random(seed)
    current = _initial_one_hot_solution(problem, rng)
    current_energy = evaluate_qubo_energy(problem.q, list(current))

    best = set(current)
    best_energy = current_energy
    accepted_moves = 0

    if max_iterations <= 0:
        return QuboSolution(
            active_indexes=sorted(best),
            energy=best_energy,
            iterations=0,
            accepted_moves=0,
        )

    for step in range(max_iterations):
        fraction = step / max(1, max_iterations - 1)
        temperature = start_temperature * ((end_temperature / start_temperature) ** fraction)

        candidate = _neighbor_one_hot(problem, current, rng)
        candidate_energy = evaluate_qubo_energy(problem.q, list(candidate))
        delta = candidate_energy - current_energy

        accept = False
        if delta <= 0:
            accept = True
        elif temperature > 0:
            threshold = rng.random()
            try_prob = pow(2.718281828, -delta / temperature)
            accept = threshold < try_prob

        if accept:
            current = candidate
            current_energy = candidate_energy
            accepted_moves += 1
            if current_energy < best_energy:
                best = set(current)
                best_energy = current_energy

    return QuboSolution(
        active_indexes=sorted(best),
        energy=best_energy,
        iterations=max_iterations,
        accepted_moves=accepted_moves,
    )
