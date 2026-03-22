# Enterprise Forecasting Readiness

This document defines what "enterprise-ready" means for SiloXR before machine learning is introduced.

## Current Standard

The system now relies on classical statistical forecasting and validation methods that are acceptable for production operational decisioning when historical data is still limited.

Implemented foundations:

- robust, recency-weighted demand estimation in [learning.py](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/apps/engine/learning.py)
- uncertainty-aware forecasting in [forecast.py](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/apps/engine/forecast.py)
- expected-shortage and revenue-at-risk estimation in [decision.py](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/apps/engine/decision.py)
- forecast validation endpoint in [views.py](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/apps/api/views.py)

## Statistical Methods In Use

### Demand Estimation

The learning engine now uses:

- zero-demand day retention
- winsorization of extreme daily-demand outliers
- exponential recency weighting
- weighted mean demand
- weighted standard deviation

This is stronger than a plain rolling average and better reflects how enterprise teams handle noisy operational demand before enough data exists for ML.

### Forecast Risk

The forecast engine uses:

- mean demand
- demand standard deviation
- probabilistic stockout approximation under a normal-demand assumption
- confidence-based risk caps
- explicit lower and upper forecast bounds

### Business Exposure

The decision engine uses:

- expected shortage
- confidence moderation
- selling-price multiplication only when price data exists

This prevents the dashboard from overstating commercial exposure when data quality is weak.

## Validation Metrics

The forecast accuracy endpoint is the governance layer for the statistical engine.

Supported metrics:

- `MAE`
- `MAPE`
- `WAPE`
- `RMSE`
- `MASE`
- signed bias
- bias percent
- interval coverage
- mean interval width
- calibration gap

These are the kinds of metrics expected in enterprise forecasting reviews.

## What Still Depends On Data Volume

The following should wait until more history has accumulated:

- machine learning demand models
- product-specific seasonality models trained automatically
- intermittent-demand model switching
- dynamic lead-time distributions
- causal models using promotions, holidays, weather, or macro signals

## Minimum Governance Expectation

Before management should rely heavily on the outputs, the system should accumulate enough resolved forecasts to evaluate:

- accuracy trend by product
- bias direction by product
- uncertainty coverage calibration
- portfolio-level WAPE and service-risk stability

## Practical Rule

Use the system as:

- a statistically grounded operational advisor today
- a machine-learning platform later, once enough resolved forecast history exists

Do not present any forecast layer as "AI" or "machine learning" until validation history supports that claim.
