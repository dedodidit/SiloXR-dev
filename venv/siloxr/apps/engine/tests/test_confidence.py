from datetime import datetime, timedelta, timezone as dt_timezone

import apps.engine.confidence as confidence_module
from apps.engine.confidence import ConfidenceScorer

def test_confidence_scorer_uses_pre_accuracy_formula_when_no_resolved_forecasts(monkeypatch):
    scorer = ConfidenceScorer()
    now = datetime(2026, 3, 21, 12, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(confidence_module.timezone, "now", lambda: now)
    monkeypatch.setattr(confidence_module.timezone, "is_naive", lambda value: value.tzinfo is None)
    result = scorer.compute(
        last_event_date=now - timedelta(days=2),
        sample_event_count=3,
        burn_rate_std_dev=4.0,
        burn_rate_per_day=2.0,
        resolved_forecasts=0,
    )

    assert result.data_stale is False
    assert result.accuracy_score == 0.35
    assert result.final_score == 0.29


def test_confidence_scorer_flags_stale_data_when_history_is_old(monkeypatch):
    scorer = ConfidenceScorer()
    now = datetime(2026, 3, 21, 12, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(confidence_module.timezone, "now", lambda: now)
    monkeypatch.setattr(confidence_module.timezone, "is_naive", lambda value: value.tzinfo is None)
    result = scorer.compute(
        last_event_date=now - timedelta(days=20),
        sample_event_count=8,
        burn_rate_std_dev=1.5,
        burn_rate_per_day=5.0,
        mape=0.2,
        resolved_forecasts=5,
    )

    assert result.data_stale is True
    assert result.accuracy_score == 0.8
    assert result.final_score == 0.4775
