# backend/apps/engine/confidence.py

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from django.utils import timezone

from apps.core.statistics import compute_cv


@dataclass(frozen=True)
class ConfidenceComponents:
    """
    Decomposed confidence scores for auditability.
    Each component is 0.0–1.0. The final score is a weighted blend.
    """
    recency_score: float       # How recently was data collected?
    sample_score: float        # How many data points do we have?
    variance_score: float      # How consistent is consumption?
    correction_score: float    # How often do STOCK_COUNT events reveal drift?
    accuracy_score: float      # Historical forecast accuracy when available
    final_score: float         # Weighted blend — this is what gets stored
    data_stale: bool = False


class ConfidenceScorer:
    """
    Computes a confidence score (0.0–1.0) for a burn rate estimate.

    Weights reflect the real-world importance of each signal:
    - Recency is the strongest signal: stale data is dangerous
    - Variance matters: irregular patterns are harder to predict
    - Sample size matters but plateaus quickly
    - Correction penalty for repeated drift keeps the system honest
    """

    MAX_STALE_DAYS = 60
    STALE_DATA_THRESHOLD_DAYS = 14

    # Sample: reaches full confidence at this many events
    FULL_CONFIDENCE_SAMPLE = 30

    # Variance: coefficient of variation above this threshold = low confidence
    HIGH_VARIANCE_THRESHOLD = 1.5

    # Correction: each percentage point of average drift lowers score
    DRIFT_PENALTY_FACTOR = 0.5

    def compute(
        self,
        last_event_date: Optional[datetime],
        sample_event_count: int,
        burn_rate_std_dev: float,
        burn_rate_per_day: float,
        avg_drift_pct: float = 0.0,
        mape: Optional[float] = None,
        resolved_forecasts: int = 0,
    ) -> ConfidenceComponents:
        """
        Compute all confidence components and return a decomposed result.

        Args:
            last_event_date:     When the most recent SALE event occurred
            sample_event_count:  Number of events in the learning window
            burn_rate_std_dev:   Standard deviation of daily consumption
            burn_rate_per_day:   Mean daily consumption
            avg_drift_pct:       Average percentage drift revealed by STOCK_COUNT events
                                 (0.0 = perfect, 1.0 = 100% wrong on average)
        """
        recency = self._recency_score(last_event_date)
        data_score = self._sample_score(sample_event_count)
        variance = self._variance_score(burn_rate_std_dev, burn_rate_per_day)
        correction = self._correction_score(avg_drift_pct)
        accuracy = self._accuracy_score(mape)
        cv = max(0.0, min(1.0, compute_cv(burn_rate_per_day, burn_rate_std_dev)))
        cv_score = max(0.0, 1.0 - cv)
        days_since_last_event = self._days_since_last_event(last_event_date)
        data_stale = days_since_last_event is None or days_since_last_event > self.STALE_DATA_THRESHOLD_DAYS

        if resolved_forecasts == 0:
            final = (
                0.53 * cv_score +
                0.27 * data_score +
                0.20 * recency
            )
        else:
            final = (
                0.40 * cv_score +
                0.20 * data_score +
                0.15 * recency +
                0.25 * accuracy
            )

        # Drift still matters as a trust penalty, but it should not break the
        # new weighting contract.
        final *= max(0.55, correction)
        if data_stale:
            final *= 0.72

        # Hard floor: never report false certainty
        final = max(0.05, min(0.99, final))

        return ConfidenceComponents(
            recency_score=round(recency, 4),
            sample_score=round(data_score, 4),
            variance_score=round(variance, 4),
            correction_score=round(correction, 4),
            accuracy_score=round(accuracy, 4),
            final_score=round(final, 4),
            data_stale=data_stale,
        )

    def _days_since_last_event(self, last_event_date: Optional[datetime]) -> Optional[float]:
        if last_event_date is None:
            return None
        if timezone.is_naive(last_event_date):
            from django.utils.timezone import make_aware
            last_event_date = make_aware(last_event_date)
        return max(0.0, (timezone.now() - last_event_date).total_seconds() / 86400)

    def _recency_score(self, last_event_date: Optional[datetime]) -> float:
        """
        Exponential decay from 1.0 (today) to ~0.05 (MAX_STALE_DAYS ago).
        No data at all → 0.1 (we know nothing but don't claim zero).
        """
        if last_event_date is None:
            return 0.1

        days_ago = self._days_since_last_event(last_event_date) or 0.0

        # Exponential decay: score = e^(-k * days_ago)
        # k chosen so that score ≈ 0.05 at MAX_STALE_DAYS
        k = -math.log(0.05) / self.MAX_STALE_DAYS
        score = math.exp(-k * days_ago)
        return max(0.05, min(1.0, score))

    def _sample_score(self, count: int) -> float:
        """
        Logarithmic growth: 1 event ≈ 0.07, 10 events ≈ 0.60, 30+ events ≈ 1.0.
        Logarithmic because the marginal value of each additional event decreases.
        """
        if count <= 0:
            return 0.05
        score = math.log1p(count) / math.log1p(self.FULL_CONFIDENCE_SAMPLE)
        return max(0.05, min(1.0, score))

    def _variance_score(self, std_dev: float, mean: float) -> float:
        """
        Uses coefficient of variation (CV = std_dev / mean).
        Low CV (consistent sales) → high score.
        High CV (irregular sales) → low score.
        """
        if mean <= 0:
            return 0.1
        cv = compute_cv(mean, std_dev)
        # Linear decay: CV=0 → 1.0, CV=HIGH_VARIANCE_THRESHOLD → 0.1
        score = 1.0 - (cv / self.HIGH_VARIANCE_THRESHOLD) * 0.9
        return max(0.1, min(1.0, score))

    def _correction_score(self, avg_drift_pct: float) -> float:
        """
        Penalises a history of STOCK_COUNT events revealing large drift.
        avg_drift_pct=0.0 → score=1.0 (our estimates have been accurate)
        avg_drift_pct=1.0 → score=0.5 (we've been 100% wrong on average)
        """
        penalty = avg_drift_pct * self.DRIFT_PENALTY_FACTOR
        return max(0.1, min(1.0, 1.0 - penalty))

    def _accuracy_score(self, mape: Optional[float]) -> float:
        if mape is None:
            return 0.35
        normalized = max(0.0, min(1.0, 1.0 - float(mape)))
        return normalized
