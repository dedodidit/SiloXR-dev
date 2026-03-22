# Commercial And Bootstrap Policy

## Product Rule

SiloXR starts helping the user on day zero.

The system does not wait for long historical datasets before becoming useful. Instead it:

1. applies conservative business-type priors based on industry norms
2. produces day-zero forecasts and decisions from those priors
3. continuously replaces those assumptions with business-specific evidence as events accumulate

## Day-Zero Assumptions

Business-type assumptions are implemented in [bootstrap.py](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/apps/engine/bootstrap.py).

These priors define:

- target days of cover
- demand variability
- baseline confidence
- verification cadence
- assumption summary used in the dashboard

They are deliberately conservative and are meant to be superseded by first-party data.

## Commercial Access Rule

All users have access to the full decision system.

Commercial differentiation is not based on hiding predictions, forecasts, or decisions. It is based on usage cadence:

- Free: full system access with managed refresh frequency
- Pro: full system access with unlimited frequency

This policy is implemented in [usage.py](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/apps/core/usage.py).

## Operational Meaning

Free users can:

- view forecasts
- view decisions
- view alerts
- access the dashboard and manager pulse

But the system can rate-manage repeated live refreshes.

Pro users receive:

- the same system
- the same intelligence
- no refresh-frequency cap

## Dashboard Contract

The dashboard summary now returns:

- `usage_policy`
- `operating_assumption`

This lets the frontend explain:

- what assumption was used at the start
- whether the account is on managed cadence or unlimited refresh
