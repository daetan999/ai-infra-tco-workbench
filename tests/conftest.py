"""Shared backend test fixtures."""

from collections.abc import Callable
from typing import Any

import pytest


@pytest.fixture
def scenario_payload() -> dict[str, Any]:
    """Return a valid bounded scenario payload."""
    infrastructure = {
        "label": "Current CPU estate",
        "infrastructure_type": "owned",
        "accelerator_count": 64,
        "compute_hourly_cost": 2.5,
        "productive_utilization_pct": 35.0,
        "storage_tb": 120.0,
        "storage_per_tb_month": 18.0,
        "network_egress_tb_month": 20.0,
        "network_per_gb": 0.04,
        "power_kw": 90.0,
        "pue": 1.6,
        "power_per_kwh": 0.12,
        "staff_fte": 2.0,
        "staff_annual_cost": 140000.0,
        "operating_hours_year": 8760.0,
    }
    proposed = {**infrastructure, "label": "Proposed GPU estate", "accelerator_count": 8}
    return {
        "name": "Inference modernization",
        "description": "Compare an owned CPU estate with a smaller GPU deployment.",
        "fictional": True,
        "comparison_type": "current_vs_proposed",
        "workload": {
            "workload_type": "inference",
            "model_size_billion": 70.0,
            "training_runs_per_month": 0,
            "monthly_requests_million": 45.0,
            "average_demand_units": 18.0,
            "peak_demand_units": 50.0,
            "annual_growth_pct": 25.0,
            "productivity_value_per_hour": 110.0,
            "downtime_hours_monthly": 5.0,
        },
        "current_infrastructure": infrastructure,
        "proposed_infrastructure": proposed,
        "migration_cost": 85000.0,
        "implementation_cost": 45000.0,
        "contract_years": 3,
        "assumption_sources": ["Fictional internal benchmark", "Public cloud list pricing"],
    }


@pytest.fixture
def evaluator() -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return a deterministic stand-in for the financial engine."""

    def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "summary": {
                "scenario_name": payload["name"],
                "three_year_savings": 123456.78,
                "recommendation": "proceed",
            },
            "annual_costs": [{"year": 1, "current": 500000.0, "proposed": 350000.0}],
        }

    return evaluate
