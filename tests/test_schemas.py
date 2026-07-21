"""Schema validation and immutability tests."""

import json

import pytest
from pydantic import ValidationError

from app.schemas import ScenarioInput


def test_scenario_is_strict_frozen_and_deeply_immutable(scenario_payload: dict) -> None:
    scenario = ScenarioInput.model_validate(scenario_payload)

    with pytest.raises(ValidationError):
        scenario.name = "Changed"
    with pytest.raises(TypeError):
        scenario.assumption_sources[0] = "Changed"
    assert isinstance(scenario.assumption_sources, tuple)


def test_schema_rejects_unknown_and_coerced_values(scenario_payload: dict) -> None:
    scenario_payload["unknown"] = "not accepted"
    scenario_payload["contract_years"] = "3"

    with pytest.raises(ValidationError) as error:
        ScenarioInput.model_validate(scenario_payload)

    locations = {item["loc"] for item in error.value.errors()}
    assert ("unknown",) in locations
    assert ("contract_years",) in locations


def test_schema_enforces_numeric_and_cross_field_bounds(scenario_payload: dict) -> None:
    scenario_payload["workload"]["average_demand_units"] = 51.0
    scenario_payload["workload"]["peak_demand_units"] = 50.0
    scenario_payload["proposed_infrastructure"]["pue"] = 0.9

    with pytest.raises(ValidationError) as error:
        ScenarioInput.model_validate(scenario_payload)

    messages = " ".join(item["msg"] for item in error.value.errors())
    assert "peak_demand_units" in messages
    assert "greater than or equal to 1" in messages


@pytest.mark.parametrize("field", ["accelerator_count", "productive_utilization_pct"])
def test_active_infrastructure_requires_positive_capacity(
    scenario_payload: dict, field: str
) -> None:
    scenario_payload["current_infrastructure"][field] = 0

    with pytest.raises(ValidationError) as error:
        ScenarioInput.model_validate(scenario_payload)

    assert ("current_infrastructure", field) in {item["loc"] for item in error.value.errors()}


def test_schema_accepts_json_assumption_source_arrays(scenario_payload: dict) -> None:
    validated = ScenarioInput.model_validate_json(json.dumps(scenario_payload))

    assert validated.assumption_sources == (
        "Fictional internal benchmark",
        "Public cloud list pricing",
    )


def test_schema_accepts_bounded_contraction_and_source_mapping(scenario_payload: dict) -> None:
    scenario_payload["workload"]["annual_growth_pct"] = -25.0
    scenario_payload["assumption_sources"] = {
        "workload.annual_growth_pct": "Approved capacity plan"
    }

    validated = ScenarioInput.model_validate(scenario_payload)

    assert validated.workload.annual_growth_pct == -25.0
    assert validated.assumption_sources == {"workload.annual_growth_pct": "Approved capacity plan"}
