"""Fictional, deterministic demo scenarios for local exploration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .repository import AnalysisRepository
from .schemas import ScenarioInput

Evaluator = Callable[[dict[str, Any]], dict[str, Any]]


def _infrastructure(
    label: str,
    kind: str,
    accelerators: int,
    hourly_cost: float,
    utilization: float = 48.0,
) -> dict:
    return {
        "label": label,
        "infrastructure_type": kind,
        "accelerator_count": accelerators,
        "compute_hourly_cost": hourly_cost,
        "productive_utilization_pct": utilization,
        "storage_tb": 180.0,
        "storage_per_tb_month": 20.0,
        "network_egress_tb_month": 24.0,
        "network_per_gb": 0.05,
        "power_kw": 120.0,
        "pue": 1.45,
        "power_per_kwh": 0.13,
        "staff_fte": 2.5,
        "staff_annual_cost": 150000.0,
        "operating_hours_year": 8760.0,
    }


def _scenario(name: str, comparison: str, current: dict, proposed: dict) -> ScenarioInput:
    return ScenarioInput.model_validate(
        {
            "name": name,
            "description": (
                f"Fictional demonstration comparing {current['label']} "
                f"and {proposed['label']}."
            ),
            "fictional": True,
            "comparison_type": comparison,
            "workload": {
                "workload_type": "mixed AI serving",
                "model_size_billion": 70.0,
                "training_runs_per_month": 2,
                "monthly_requests_million": 60.0,
                "average_demand_units": 32.0,
                "peak_demand_units": 85.0,
                "annual_growth_pct": 30.0,
                "productivity_value_per_hour": 125.0,
                "downtime_hours_monthly": 6.0,
            },
            "current_infrastructure": current,
            "proposed_infrastructure": proposed,
            "migration_cost": 120000.0,
            "implementation_cost": 65000.0,
            "contract_years": 3,
            "assumption_sources": ["Fictional benchmark", "Illustrative list pricing"],
        }
    )


def demo_scenarios() -> tuple[ScenarioInput, ScenarioInput, ScenarioInput]:
    """Return exactly three clearly fictional comparison scenarios."""
    return (
        _scenario(
            "CPU-to-GPU inference modernization",
            "current_vs_proposed",
            _infrastructure("CPU inference estate", "owned", 96, 2.4),
            _infrastructure("GPU inference estate", "owned", 12, 4.8),
        ),
        _scenario(
            "Cloud GPU vs owned infrastructure",
            "cloud_vs_owned",
            _infrastructure("Cloud GPU reservation", "cloud", 24, 8.6),
            _infrastructure("Owned GPU cluster", "owned", 24, 3.1),
        ),
        _scenario(
            "Shared serving utilization",
            "dedicated_vs_shared",
            _infrastructure("Dedicated model pools", "owned", 32, 4.2, 35.0),
            _infrastructure("Shared serving platform", "owned", 20, 4.2, 72.0),
        ),
    )


def seed_demo_data(repository: AnalysisRepository, evaluator: Evaluator) -> int:
    """Seed an empty repository once and report the inserted count."""
    if repository.list_latest():
        return 0
    scenarios = demo_scenarios()
    for scenario in scenarios:
        payload = scenario.model_dump(mode="json")
        repository.create(scenario, evaluator(payload))
    return len(scenarios)
