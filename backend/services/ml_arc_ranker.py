"""
ML arc ranking helper.

The exact solver remains the source of truth for feasibility.
This module only prioritizes feasible candidate arcs to speed up search.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

try:
    from services.ml_assignment_service import build_ml_pair_scores
except ImportError:
    from backend.services.ml_assignment_service import build_ml_pair_scores


@dataclass
class ArcCandidate:
    from_idx: int
    to_idx: int
    score: float
    feasible: bool = True


def rank_candidate_arcs(
    jobs: Sequence[Any],
    travel_times: Dict[Tuple[int, int], int],
    *,
    is_entry: bool,
    min_buffer_minutes: float = 5.0,
    max_early_arrival_minutes: int = 5,
    max_exit_shift_minutes: int = 5,
    min_start_hour: int = 6,
) -> List[ArcCandidate]:
    """
    Return feasible arcs sorted by ML score descending.

    Notes:
    - No feasibility is relaxed here.
    - Returned arcs are only a ranking aid for the optimizer.
    """
    pair_scores = build_ml_pair_scores(
        jobs=jobs,
        travel_times=travel_times,
        is_entry=is_entry,
        min_buffer_minutes=min_buffer_minutes,
        max_early_arrival_minutes=max_early_arrival_minutes,
        max_exit_shift_minutes=max_exit_shift_minutes,
        min_start_hour=min_start_hour,
    )

    arcs = [
        ArcCandidate(from_idx=i, to_idx=j, score=float(score), feasible=True)
        for (i, j), score in pair_scores.items()
    ]
    arcs.sort(key=lambda arc: arc.score, reverse=True)
    return arcs

