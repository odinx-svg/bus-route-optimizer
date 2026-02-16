"""
ML-assisted route assignment scoring.

This module provides a lightweight logistic model (pure Python) to score
route-to-route compatibility probabilities using operational features derived
from timing and travel constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Iterable, List, Sequence, Tuple


@dataclass
class PairFeatureRow:
    """Training sample for a route pair transition."""

    pair: Tuple[int, int]
    features: List[float]
    label: int


class OnlineLogisticModel:
    """
    Minimal logistic regression with SGD.

    Pure Python implementation to avoid introducing heavy dependencies.
    """

    def __init__(self, feature_size: int, lr: float = 0.08, l2: float = 0.0005, epochs: int = 60):
        self.lr = lr
        self.l2 = l2
        self.epochs = epochs
        self.weights: List[float] = [0.0] * feature_size
        self.bias: float = 0.0
        self.constant_probability: float | None = None

    @staticmethod
    def _sigmoid(x: float) -> float:
        if x >= 0:
            z = math.exp(-x)
            return 1.0 / (1.0 + z)
        z = math.exp(x)
        return z / (1.0 + z)

    def train(self, rows: Sequence[PairFeatureRow]) -> None:
        if not rows:
            self.constant_probability = 0.5
            return

        positives = sum(1 for row in rows if row.label == 1)
        negatives = len(rows) - positives
        if positives == 0:
            self.constant_probability = 0.05
            return
        if negatives == 0:
            self.constant_probability = 0.95
            return

        for _ in range(self.epochs):
            for row in rows:
                x = row.features
                y = float(row.label)
                z = self.bias
                for j in range(len(self.weights)):
                    z += self.weights[j] * x[j]
                p = self._sigmoid(z)
                error = p - y

                for j in range(len(self.weights)):
                    grad = (error * x[j]) + (self.l2 * self.weights[j])
                    self.weights[j] -= self.lr * grad

                self.bias -= self.lr * error

    def predict_proba(self, features: Sequence[float]) -> float:
        if self.constant_probability is not None:
            return self.constant_probability

        z = self.bias
        for j in range(len(self.weights)):
            z += self.weights[j] * features[j]
        return self._sigmoid(z)


def _safe_ratio(a: float, b: float, cap: float = 3.0) -> float:
    if b <= 0:
        return 1.0
    return min(cap, a / b)


def _feature_vector(
    *,
    travel_time: float,
    time_gap: float,
    buffer_minutes: float,
    same_school: int,
    route_type_match: int,
    duration_ratio: float,
    is_entry: int,
) -> List[float]:
    """
    Build normalized features.

    Scaling keeps values in compact ranges for stable SGD.
    """
    return [
        travel_time / 60.0,
        time_gap / 60.0,
        buffer_minutes / 30.0,
        float(same_school),
        float(route_type_match),
        duration_ratio / 3.0,
        float(is_entry),
    ]


def _build_pair_rows(
    jobs: Sequence[Any],
    travel_times: Dict[Tuple[int, int], int],
    *,
    is_entry: bool,
    min_buffer_minutes: float,
    max_early_arrival_minutes: int,
    max_exit_shift_minutes: int,
    min_start_hour: int,
) -> List[PairFeatureRow]:
    rows: List[PairFeatureRow] = []
    n = len(jobs)

    for i in range(n):
        for j in range(n):
            if i == j:
                continue

            tt = float(travel_times.get((i, j), 999))
            a = jobs[i]
            b = jobs[j]

            if is_entry:
                earliest_a = max(
                    int(a.time_minutes) - int(max_early_arrival_minutes),
                    (int(min_start_hour) * 60) + int(a.duration_minutes),
                )
                required_arrival_b = earliest_a + tt + float(b.duration_minutes)
                buffer = float(b.time_minutes) - required_arrival_b
                gap = float(b.time_minutes) - earliest_a
            else:
                earliest_end_a = (int(a.time_minutes) - int(max_exit_shift_minutes)) + int(a.duration_minutes)
                latest_start_b = int(b.time_minutes) + int(max_exit_shift_minutes)
                buffer = float(latest_start_b - (earliest_end_a + tt))
                gap = float(latest_start_b - earliest_end_a)

            same_school = 1 if getattr(a, "school_name", "") == getattr(b, "school_name", "") else 0
            route_type_match = 1 if getattr(a, "route_type", "") == getattr(b, "route_type", "") else 0
            duration_ratio = _safe_ratio(float(getattr(b, "duration_minutes", 0)), float(getattr(a, "duration_minutes", 0)))

            features = _feature_vector(
                travel_time=tt,
                time_gap=gap,
                buffer_minutes=buffer,
                same_school=same_school,
                route_type_match=route_type_match,
                duration_ratio=duration_ratio,
                is_entry=1 if is_entry else 0,
            )

            label = 1 if buffer >= float(min_buffer_minutes) else 0
            rows.append(PairFeatureRow(pair=(i, j), features=features, label=label))

    return rows


def build_ml_pair_scores(
    jobs: Sequence[Any],
    travel_times: Dict[Tuple[int, int], int],
    *,
    is_entry: bool,
    min_buffer_minutes: float = 5.0,
    max_early_arrival_minutes: int = 0,
    max_exit_shift_minutes: int = 0,
    min_start_hour: int = 6,
) -> Dict[Tuple[int, int], float]:
    """
    Train and infer pairwise compatibility scores for assignment edges.

    Returns probabilities in [0, 1] for each candidate pair (i, j).
    """
    rows = _build_pair_rows(
        jobs,
        travel_times,
        is_entry=is_entry,
        min_buffer_minutes=min_buffer_minutes,
        max_early_arrival_minutes=max_early_arrival_minutes,
        max_exit_shift_minutes=max_exit_shift_minutes,
        min_start_hour=min_start_hour,
    )

    if not rows:
        return {}

    model = OnlineLogisticModel(feature_size=len(rows[0].features))
    model.train(rows)

    scores: Dict[Tuple[int, int], float] = {}
    for row in rows:
        p = model.predict_proba(row.features)
        # clamp numerically
        scores[row.pair] = max(0.0, min(1.0, float(p)))
    return scores

