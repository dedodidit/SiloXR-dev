# backend/apps/engine/tasks.py

"""
Celery task definitions for all three engines + feedback.

Execution order for the nightly job:
  1. run_daily_engine_sweep  (Learning → Forecast → Decision for all products)
  2. run_nightly_feedback_sweep  (Feedback for all products)

These are separate tasks so each can be monitored, retried,
and scheduled independently.
"""

import logging

logger = logging.getLogger(__name__)


def run_learning_task(product_id: str) -> dict:
    from apps.inventory.models import Product
    from apps.engine.learning import LearningEngine
    try:
        product = Product.objects.get(id=product_id, is_active=True)
        result  = LearningEngine().run(product)
        return {
            "status":     "ok",
            "burn_rate":  result.burn_rate_per_day,
            "confidence": result.confidence_score,
        }
    except Product.DoesNotExist:
        return {"status": "skipped", "reason": "product_not_found"}
    except Exception as exc:
        logger.error("Learning task failed for %s: %s", product_id, exc, exc_info=True)
        raise


def run_forecast_task(product_id: str) -> dict:
    from apps.inventory.models import Product
    from apps.engine.forecast import ForecastEngine
    try:
        product = Product.objects.get(id=product_id, is_active=True)
        result  = ForecastEngine().run(product)
        return {
            "status":          "ok",
            "days_to_stockout": result.days_until_stockout,
            "stockout_risk":   result.stockout_risk_score,
            "confidence":      result.confidence_score,
        }
    except Product.DoesNotExist:
        return {"status": "skipped", "reason": "product_not_found"}
    except Exception as exc:
        logger.error("Forecast task failed for %s: %s", product_id, exc, exc_info=True)
        raise


def run_feedback_task(product_id: str) -> dict:
    from apps.inventory.models import Product
    from apps.engine.feedback import FeedbackEngine
    try:
        product = Product.objects.get(id=product_id, is_active=True)
        signal  = FeedbackEngine().run(product)
        if signal is None:
            return {"status": "skipped", "reason": "no_resolvable_snapshots"}
        return {
            "status":        "ok",
            "actionable":    signal.actionable,
            "rate_factor":   signal.rate_adjustment_factor,
            "conf_penalty":  signal.confidence_penalty,
            "summary":       signal.summary,
        }
    except Product.DoesNotExist:
        return {"status": "skipped", "reason": "product_not_found"}
    except Exception as exc:
        logger.error("Feedback task failed for %s: %s", product_id, exc, exc_info=True)
        raise


def run_daily_engine_sweep() -> dict:
    """
    Runs nightly at 02:00.
    Learning for all active products → Forecast → Decision (Pro only).
    Signals handle the per-product chain; this just kicks off learning.
    """
    from apps.engine.learning  import LearningEngine
    from apps.engine.forecast  import ForecastEngine

    learn_results    = LearningEngine().run_for_all_active()
    forecast_results = ForecastEngine().run_for_all_active()

    return {
        "learned":              len(learn_results),
        "forecasted":           len(forecast_results),
        "learn_skipped":        sum(1 for r in learn_results    if r.skipped),
        "forecast_skipped":     sum(1 for r in forecast_results if r.skipped),
        "avg_confidence":       (
            sum(r.confidence_score for r in learn_results) / len(learn_results)
            if learn_results else 0.0
        ),
        "stockouts_within_7d":  sum(
            1 for r in forecast_results if r.is_stockout_imminent
        ),
    }


def run_nightly_feedback_sweep() -> dict:
    """
    Runs nightly at 03:00, after the engine sweep completes.
    Resolves past forecasts, computes errors, applies corrections.
    """
    from apps.engine.feedback import FeedbackEngine

    signals = FeedbackEngine().run_for_all_active()

    return {
        "evaluated":        len(signals),
        "actionable":       sum(1 for s in signals if s.actionable),
        "rate_corrections": sum(
            1 for s in signals
            if s.actionable and s.rate_adjustment_factor != 1.0
        ),
        "conf_penalties":   sum(
            1 for s in signals
            if s.actionable and s.confidence_penalty > 0
        ),
        "avg_mape": (
            sum(s.accuracy.mape for s in signals if s.accuracy)
            / max(1, sum(1 for s in signals if s.accuracy))
        ),
    }