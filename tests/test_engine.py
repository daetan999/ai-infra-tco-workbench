"""Behavioral specification for the deterministic TCO engine."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError
from decimal import Decimal
from urllib.parse import quote

import pytest

from app.domain import ScenarioInput
from app.engine import calculate_analysis, evaluate_financial_scenario, parse_scenario


def scenario_payload() -> dict[str, object]:
    """Return a compact scenario whose formulas are easy to audit by hand."""
    return {
        "name": "Build or rent",
        "description": "Deterministic comparison",
        "fictional": True,
        "comparison_type": "current_vs_proposed",
        "workload": workload(),
        "current_infrastructure": infrastructure(
            label="Current",
            infrastructure_type="cloud",
            compute_hourly_cost=10,
            productive_utilization_pct=50,
            storage_per_tb_month=100,
            network_egress_tb_month=1,
            network_per_gb=0.1,
            power_kw=10,
            pue=1.2,
            power_per_kwh=0.2,
            staff_fte=1,
        ),
        "proposed_infrastructure": infrastructure(
            label="Proposed",
            infrastructure_type="owned",
            compute_hourly_cost=6,
            productive_utilization_pct=80,
            storage_per_tb_month=80,
            network_egress_tb_month=0.5,
            network_per_gb=0.05,
            power_kw=8,
            pue=1.1,
            power_per_kwh=0.15,
            staff_fte=0.5,
        ),
        "migration_cost": 10_000,
        "implementation_cost": 5_000,
        "contract_years": 5,
        "assumption_sources": {
            "current_infrastructure.compute_hourly_cost": "Current invoice",
            "proposed_infrastructure.compute_hourly_cost": "Vendor quote Q3",
            "annual_growth_pct": "Capacity plan",
        },
    }


def workload() -> dict[str, object]:
    return {
        "workload_type": "mixed",
        "model_size_billion": 7,
        "training_runs_per_month": 2,
        "monthly_requests_million": 100,
        "average_demand_units": 5,
        "peak_demand_units": 10,
        "annual_growth_pct": 10,
        "productivity_value_per_hour": 100,
        "downtime_hours_monthly": 10,
    }


def infrastructure(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "label": "Infrastructure",
        "infrastructure_type": "cloud",
        "accelerator_count": 2,
        "compute_hourly_cost": 10,
        "productive_utilization_pct": 50,
        "storage_tb": 1,
        "storage_per_tb_month": 100,
        "network_egress_tb_month": 1,
        "network_per_gb": 0.1,
        "power_kw": 10,
        "pue": 1.2,
        "power_per_kwh": 0.2,
        "staff_fte": 1,
        "staff_annual_cost": 50_000,
        "operating_hours_year": 1_000,
    }
    return {**values, **overrides}


def test_annual_cost_breakdown_and_tco_apply_growth_and_one_time_costs() -> None:
    result = calculate_analysis(scenario_payload())

    current_year_1 = result.current.annual_costs[0]
    assert current_year_1.compute == Decimal("20000.00")
    assert current_year_1.storage == Decimal("1200.00")
    assert current_year_1.network == Decimal("1200.00")
    assert current_year_1.energy == Decimal("2400.00")
    assert current_year_1.staffing == Decimal("50000.00")
    assert current_year_1.total == Decimal("74800.00")
    assert result.current.tco_3_year == Decimal("232088.00")
    assert result.current.tco_5_year == Decimal("401406.48")

    proposed_year_1 = result.proposed.annual_costs[0]
    assert proposed_year_1.transition == Decimal("15000.00")
    assert proposed_year_1.total == Decimal("54580.00")
    assert result.proposed.tco_3_year == Decimal("138259.80")
    assert result.proposed.tco_5_year == Decimal("229012.36")


def test_comparison_roi_net_value_and_payback_are_modeled_not_guaranteed() -> None:
    result = calculate_analysis(scenario_payload())
    comparison = result.comparison

    assert comparison.savings_3_year == Decimal("93828.20")
    assert comparison.savings_5_year == Decimal("172394.12")
    assert comparison.productivity_value_5_year == Decimal("73261.20")
    assert comparison.net_value_5_year == Decimal("245655.32")
    assert comparison.roi_5_year_pct == Decimal("107.27")
    assert comparison.payback_months == Decimal("3.8")
    assert comparison.break_even_within_5_years is True
    assert "not guarantees" in comparison.disclaimer.lower()


def test_unit_economics_cover_training_inference_and_productive_hours() -> None:
    proposed = calculate_analysis(scenario_payload()).proposed
    units = proposed.unit_economics_3_year

    assert units.cost_per_training_run == Decimal("1551.61")
    assert units.cost_per_million_requests == Decimal("31.03")
    assert units.cost_per_productive_accelerator_hour == Decimal("25.68")
    assert units.recurring_cost == Decimal("123259.80")


def test_zero_non_applicable_workload_metrics_return_no_unit_cost() -> None:
    payload = scenario_payload()
    payload["workload"] = {
        **payload["workload"],  # type: ignore[arg-type]
        "training_runs_per_month": 0,
        "monthly_requests_million": 0,
    }

    result = calculate_analysis(payload)

    assert result.current.unit_economics_3_year.cost_per_training_run is None
    assert result.current.unit_economics_3_year.cost_per_million_requests is None


def test_non_positive_modeled_benefits_have_no_payback() -> None:
    payload = scenario_payload()
    payload["workload"] = {
        **payload["workload"],  # type: ignore[arg-type]
        "productivity_value_per_hour": 0,
        "downtime_hours_monthly": 0,
    }
    payload["proposed_infrastructure"] = {
        **payload["proposed_infrastructure"],  # type: ignore[arg-type]
        "compute_hourly_cost": 30,
        "staff_fte": 2,
    }

    result = calculate_analysis(payload)
    comparison = result.comparison

    assert comparison.net_value_5_year < 0
    assert comparison.roi_5_year_pct < 0
    assert comparison.payback_months is None
    assert comparison.break_even_within_5_years is False
    assert result.executive_summary.recommendation.startswith(
        "Modeled results do not show a financial advantage"
    )


def test_sensitivities_cover_all_requested_dimensions_and_order_risk() -> None:
    sensitivities = calculate_analysis(scenario_payload()).sensitivities
    grouped = {
        dimension: [case for case in sensitivities if case.dimension == dimension]
        for dimension in {case.dimension for case in sensitivities}
    }

    assert set(grouped) == {"utilization", "price", "growth", "energy"}
    assert all(
        [case.case for case in cases] == ["low", "base", "high"] for cases in grouped.values()
    )
    assert grouped["price"][0].proposed_tco_5_year < grouped["price"][2].proposed_tco_5_year
    assert grouped["growth"][0].proposed_tco_5_year < grouped["growth"][2].proposed_tco_5_year
    assert grouped["energy"][0].proposed_tco_5_year < grouped["energy"][2].proposed_tco_5_year
    assert (
        grouped["utilization"][0].proposed_tco_5_year
        > grouped["utilization"][2].proposed_tco_5_year
    )


def test_growth_sensitivity_recalculates_both_sides_of_the_comparison() -> None:
    payload = scenario_payload()
    high_growth = next(
        case
        for case in calculate_analysis(payload).sensitivities
        if case.dimension == "growth" and case.case == "high"
    )
    payload["workload"] = {
        **payload["workload"],  # type: ignore[arg-type]
        "annual_growth_pct": 15,
    }
    independently_recalculated = calculate_analysis(payload).comparison

    assert high_growth.savings_5_year == independently_recalculated.savings_5_year
    assert high_growth.net_value_5_year == independently_recalculated.net_value_5_year


def test_utilization_sensitivity_floors_low_case_at_one_percent() -> None:
    payload = scenario_payload()
    payload["proposed_infrastructure"] = {
        **payload["proposed_infrastructure"],  # type: ignore[arg-type]
        "productive_utilization_pct": 5,
    }

    utilization = [
        case
        for case in calculate_analysis(payload).sensitivities
        if case.dimension == "utilization"
    ]

    assert utilization[0].assumption_value == Decimal("1.0000")
    assert utilization[0].proposed_tco_5_year > utilization[1].proposed_tco_5_year


def test_confidence_and_lineage_surface_source_provenance_for_outputs() -> None:
    result = calculate_analysis(scenario_payload())
    lineages = {item.output_path: item for item in result.lineage}

    assert result.confidence.level == "Low"
    assert result.confidence.source_coverage_pct > 0
    assert "current.annual_costs[1].compute" in lineages
    assert "proposed.tco_5_year" in lineages
    assert "comparison.roi_5_year_pct" in lineages
    assert "sensitivities.price.low.proposed_tco_5_year" in lineages
    assert "executive_summary.net_value_5_year" in lineages
    assert "Current invoice" in lineages["current.annual_costs[1].compute"].source_refs


def test_confidence_labels_weight_authoritative_source_coverage() -> None:
    payload = scenario_payload()

    def result_for(confidence: str):
        metadata = quote(json.dumps({"value": "$10", "confidence": confidence}))
        payload["assumption_sources"] = {
            "current_infrastructure.compute_hourly_cost": (
                f"Current invoice | workbench-meta:{metadata}"
            )
        }
        return calculate_analysis(payload)

    low = result_for("low")
    high = result_for("high")

    assert high.confidence.score > low.confidence.score
    assert high.confidence.source_coverage_pct > low.confidence.source_coverage_pct
    assert "workbench-meta" not in high.lineage[1].source_refs[1]


@pytest.mark.parametrize(
    ("confidence_label", "expected_level", "expected_posture", "expected_recommendation"),
    (
        (
            "medium",
            "Medium",
            "CONDITIONAL_REVIEW",
            "The model supports conditional review.",
        ),
        (
            "high",
            "High",
            "DECISION_REVIEW_READY",
            "Evidence coverage supports decision review",
        ),
    ),
)
def test_evidence_confidence_controls_the_decision_posture(
    confidence_label: str,
    expected_level: str,
    expected_posture: str,
    expected_recommendation: str,
) -> None:
    payload = scenario_payload()
    metadata = quote(json.dumps({"value": "verified", "confidence": confidence_label}))
    source = f"Review evidence | workbench-meta:{metadata}"
    sources: dict[str, str] = {}
    for section in ("workload", "current_infrastructure", "proposed_infrastructure"):
        values = payload[section]
        assert isinstance(values, dict)
        sources.update(
            {
                f"{section}.{field}": source
                for field, value in values.items()
                if isinstance(value, (int, float)) and value != 0
            }
        )
    sources.update(
        {
            "migration_cost": source,
            "implementation_cost": source,
            "contract_years": source,
        }
    )
    payload["assumption_sources"] = sources

    summary = calculate_analysis(payload).executive_summary

    assert summary.confidence_level == expected_level
    assert summary.decision_posture == expected_posture
    assert summary.recommendation.startswith(expected_recommendation)


def test_result_is_immutable_deterministic_and_does_not_mutate_input() -> None:
    payload = scenario_payload()
    original = deepcopy(payload)

    first = calculate_analysis(payload)
    second = calculate_analysis(payload)

    assert first == second
    assert payload == original
    assert isinstance(parse_scenario(payload), ScenarioInput)
    with pytest.raises(FrozenInstanceError):
        first.current.tco_3_year = Decimal("0")  # type: ignore[misc]
    with pytest.raises(TypeError):
        first.current.annual_costs[0] = first.current.annual_costs[1]  # type: ignore[index]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("migration_cost",), -1),
        (("contract_years",), 0),
        (("contract_years",), 11),
        (("workload", "annual_growth_pct"), -101),
        (("current_infrastructure", "productive_utilization_pct"), 0),
        (("current_infrastructure", "productive_utilization_pct"), 101),
        (("proposed_infrastructure", "compute_hourly_cost"), True),
        (("proposed_infrastructure", "pue"), 6),
        (("proposed_infrastructure", "operating_hours_year"), 8785),
    ],
)
def test_invalid_financial_inputs_fail_fast(path: tuple[str, ...], value: object) -> None:
    payload = scenario_payload()
    target = payload
    for part in path[:-1]:
        target = target[part]  # type: ignore[assignment,index]
    target[path[-1]] = value

    with pytest.raises(ValueError):
        calculate_analysis(payload)


def test_decimal_rounding_is_explicit_half_up() -> None:
    payload = scenario_payload()
    payload["current_infrastructure"] = infrastructure(
        accelerator_count=1,
        compute_hourly_cost=0.005,
        operating_hours_year=1,
        storage_tb=0,
        network_egress_tb_month=0,
        power_kw=0,
        staff_fte=0,
    )

    current_year_1 = calculate_analysis(payload).current.annual_costs[0]

    assert current_year_1.compute == Decimal("0.01")


def test_executive_summary_exposes_decision_ready_metrics() -> None:
    result = calculate_analysis(scenario_payload())
    summary = result.executive_summary

    assert summary.scenario_name == "Build or rent"
    assert summary.current_tco_3_year == result.current.tco_3_year
    assert summary.proposed_tco_5_year == result.proposed.tco_5_year
    assert summary.net_value_5_year == result.comparison.net_value_5_year
    assert summary.decision_posture == "VALIDATION_REQUIRED"
    assert summary.recommendation == (
        "Evidence is insufficient for investment approval. Validate the highest-impact "
        "assumptions before using this comparison to select an option."
    )
    assert summary.required_next_action == (
        "Resolve the priority evidence gaps and rerun the comparison before investment review."
    )
    assert len(summary.priority_evidence_gaps) == 3
    assert "proposed_infrastructure.accelerator_count" in summary.priority_evidence_gaps
    assert len(summary.strongest_sensitivities) == 3
    assert summary.strongest_sensitivities[0] in {"utilization", "price", "growth", "energy"}
    assert result.to_dict()["comparison"]["savings_5_year"] == 172394.12


def test_public_adapter_returns_a_json_serializable_mapping() -> None:
    response = evaluate_financial_scenario(scenario_payload())

    assert response["name"] == "Build or rent"
    assert response["comparison"]["savings_5_year"] == 172394.12  # type: ignore[index]
    assert json.loads(json.dumps(response))["executive_summary"]["scenario_name"] == "Build or rent"
