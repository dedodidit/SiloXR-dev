# Managerial Statistics Guide

This document explains the business-facing figures used by the SiloXR dashboard and decision layer.

## Principles

- All exposed figures should be traceable to observed inventory events, learned burn rates, forecast uncertainty, and explicit confidence scores.
- We avoid presenting single-point guesses as certain outcomes.
- Manager-facing exposure numbers are moderated by confidence so weak data does not look more precise than it is.

## Core Statistical Inputs

The system already learns and stores these operational statistics:

- `burn_rate_per_day`: estimated average daily demand
- `burn_rate_std_dev`: standard deviation of daily demand
- `confidence_score`: bounded confidence score from `0.0` to `1.0`
- `estimated_quantity`: current modeled stock on hand
- `lower_bound` / `upper_bound`: uncertainty band around forecast quantity

These are the statistical foundation for all forecast-driven figures.

## Forecast Uncertainty

The forecast engine projects daily stock using:

- central path: `estimated_quantity - mean demand`
- pessimistic path: `estimated_quantity - (mean demand + 1 sigma)`
- optimistic path: `estimated_quantity - max(mean demand - 1 sigma, 0)`

Confidence decays with forecast distance and demand variability using the coefficient of variation:

- `cv = burn_rate_std_dev / burn_rate_per_day`
- `day_confidence = base_confidence * exp(-decay_rate * day_offset)`

This means high-variance products lose forecast confidence faster than stable ones.

## Stockout Risk Score

The stockout risk score is no longer just a linear countdown. It now combines:

1. Stockout probability under a normal-demand approximation
2. Urgency of the likely stockout window
3. Confidence-based capping so low-confidence models do not overstate certainty

Probability component:

- `Demand_h ~ Normal(mu, sigma)`
- `mu = burn_rate_per_day * horizon`
- `sigma = burn_rate_std_dev * sqrt(horizon)`
- `P(stockout) = 1 - Phi((stock_on_hand - mu) / sigma)`

Final risk score:

- `risk = 0.7 * stockout_probability + 0.3 * urgency_score`
- capped by confidence before persistence

This keeps the score aligned with practical inventory risk instead of simple time-to-zero heuristics.

## Estimated Lost Sales

The dashboard and decisions use an expected-shortage model instead of:

- `lost_sales = daily_burn * days_to_stockout`

Expected shortage:

- `expected_shortage = E[max(Demand_h - stock_on_hand, 0)]`

For normally distributed demand:

- `expected_shortage = sigma * (phi(z) - z * (1 - Phi(z)))`
- `z = (stock_on_hand - mu) / sigma`

Where:

- `mu = burn_rate_per_day * horizon`
- `sigma = burn_rate_std_dev * sqrt(horizon)`

This is a standard first-order loss function from inventory theory.

We then apply a confidence multiplier so poor data does not inflate business exposure:

- `adjusted_lost_sales = expected_shortage * confidence_multiplier`

## Estimated Revenue Loss

Revenue at risk is derived directly from expected lost sales:

- `estimated_revenue_loss = expected_lost_sales * selling_price`

If `selling_price` is missing, the system does not fabricate a revenue estimate.

## Managerial Dashboard Signals

The manager pulse on the dashboard aggregates operational signals into four executive views:

- revenue at risk
- 7-day stockout pressure
- verification debt
- decision follow-through

These use existing persisted decision and product data. No parallel data model is introduced.

## Interpretation Guidance

- `critical` does not mean certainty. It means the modeled downside is large enough and near enough to deserve immediate attention.
- `warning` means meaningful risk or degraded data quality is present.
- `safe` means no material near-term issue is visible in the current signal set, not that the business is risk-free.

## Practical Limits

These figures are statistically grounded, but still depend on:

- event freshness
- correct stock counts
- realistic selling prices
- enough historical demand variation to estimate uncertainty

When data quality is weak, the system should prefer nudges to verify stock over aggressive commercial claims.
