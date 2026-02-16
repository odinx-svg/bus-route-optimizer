from dataclasses import dataclass
from typing import Dict, Tuple

try:
    from backend.services.ml_assignment_service import build_ml_pair_scores
except ImportError:
    from services.ml_assignment_service import build_ml_pair_scores


@dataclass
class DummyJob:
    time_minutes: int
    duration_minutes: int
    school_name: str
    route_type: str


def test_ml_pair_scores_returns_probabilities_for_pairs():
    jobs = [
        DummyJob(time_minutes=480, duration_minutes=20, school_name="A", route_type="entry"),
        DummyJob(time_minutes=520, duration_minutes=20, school_name="A", route_type="entry"),
        DummyJob(time_minutes=500, duration_minutes=25, school_name="B", route_type="entry"),
    ]
    tt: Dict[Tuple[int, int], int] = {
        (0, 1): 5,
        (0, 2): 30,
        (1, 0): 8,
        (1, 2): 14,
        (2, 0): 12,
        (2, 1): 10,
    }

    scores = build_ml_pair_scores(
        jobs,
        tt,
        is_entry=True,
        min_buffer_minutes=5.0,
        max_early_arrival_minutes=0,
        max_exit_shift_minutes=0,
        min_start_hour=6,
    )

    assert len(scores) == 6
    assert all(0.0 <= value <= 1.0 for value in scores.values())


def test_ml_pair_scores_prioritizes_healthier_buffer_transitions():
    jobs = [
        DummyJob(time_minutes=480, duration_minutes=20, school_name="A", route_type="entry"),
        DummyJob(time_minutes=520, duration_minutes=20, school_name="A", route_type="entry"),  # large buffer from 0
        DummyJob(time_minutes=500, duration_minutes=25, school_name="B", route_type="entry"),  # insufficient from 0
    ]
    tt: Dict[Tuple[int, int], int] = {
        (0, 1): 5,
        (0, 2): 30,
        (1, 0): 10,
        (1, 2): 10,
        (2, 0): 10,
        (2, 1): 10,
    }

    scores = build_ml_pair_scores(
        jobs,
        tt,
        is_entry=True,
        min_buffer_minutes=5.0,
        max_early_arrival_minutes=0,
        max_exit_shift_minutes=0,
        min_start_hour=6,
    )

    assert scores[(0, 1)] > scores[(0, 2)]

