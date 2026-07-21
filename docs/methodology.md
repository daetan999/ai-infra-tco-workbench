# Financial methodology

The engine compares a current-state and proposed-state infrastructure profile over explicit three-
and five-year horizons. Monetary outputs use decimal arithmetic and a single documented rounding
boundary.

## Annual cost model

For each state and year:

```text
compute = accelerator count × operating hours × hourly compute price
storage = storage TB × monthly price per TB × 12
network = monthly egress TB × 1,000 GB/TB × price per GB × 12
energy = power kW × PUE × operating hours × price per kWh
staffing = FTE × annual loaded cost
annual run rate = compute + storage + network + energy + staffing
```

Workload growth is applied explicitly to demand-linked costs. One-time migration and implementation
costs apply only to the proposed case and are visible separately.

## Unit economics and business-case measures

```text
cost per training run = annual run rate / annual training runs
cost per million requests = annual run rate / annual request volume in millions
cost per productive accelerator hour = annual run rate / productive accelerator hours
TCO savings = current-state TCO - proposed-state TCO
modeled productivity value = avoided downtime hours × productivity value per hour
net value = TCO savings + modeled productivity value
ROI = net value / proposed-state TCO
payback = one-time investment / positive monthly operating benefit
```

An unavailable denominator produces an explicit unavailable result rather than a fabricated zero.
Payback is unavailable when the proposed run rate does not create a positive operating benefit.

## Sensitivity analysis

Utilization, compute price, demand growth, and energy price are varied independently around the base
case. These are deterministic scenario ranges, not probability distributions or forecasts.

## Provenance

Inputs are classified as `user_input`, `public_default`, or `illustrative_assumption`. Engine outputs
are classified as `derived_calculation`. Confidence reflects provenance coverage and input
completeness; it does not certify pricing, performance, or ROI.
