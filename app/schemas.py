"""Strict API and persistence schemas for the TCO workbench."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
SourceText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Money = Annotated[float, Field(ge=0, le=1_000_000_000_000)]
PositiveUnits = Annotated[float, Field(ge=0, le=1_000_000_000)]
Percentage = Annotated[float, Field(ge=0, le=1000)]


class FrozenModel(BaseModel):
    """Base model with strict coercion, immutable fields, and closed shape."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class WorkloadInput(FrozenModel):
    """Workload demand and business-value assumptions."""

    workload_type: ShortText
    model_size_billion: Annotated[float, Field(gt=0, le=100_000)]
    training_runs_per_month: Annotated[int, Field(ge=0, le=1_000_000)]
    monthly_requests_million: PositiveUnits
    average_demand_units: PositiveUnits
    peak_demand_units: PositiveUnits
    annual_growth_pct: Annotated[float, Field(ge=-100, le=1000)]
    productivity_value_per_hour: Money
    downtime_hours_monthly: Annotated[float, Field(ge=0, le=744)]

    @model_validator(mode="after")
    def peak_covers_average(self) -> Self:
        """Reject an internally inconsistent demand profile."""
        if self.peak_demand_units < self.average_demand_units:
            raise ValueError("peak_demand_units must be at least average_demand_units")
        return self


class InfrastructureInput(FrozenModel):
    """Financial and operating assumptions for one infrastructure option."""

    label: ShortText
    infrastructure_type: ShortText
    accelerator_count: Annotated[int, Field(gt=0, le=1_000_000)]
    compute_hourly_cost: Money
    productive_utilization_pct: Annotated[float, Field(gt=0, le=100)]
    storage_tb: PositiveUnits
    storage_per_tb_month: Money
    network_egress_tb_month: PositiveUnits
    network_per_gb: Money
    power_kw: PositiveUnits
    pue: Annotated[float, Field(ge=1, le=5)]
    power_per_kwh: Money
    staff_fte: Annotated[float, Field(ge=0, le=100_000)]
    staff_annual_cost: Money
    operating_hours_year: Annotated[float, Field(ge=0, le=8784)]


class ScenarioInput(FrozenModel):
    """Complete user-authored comparison accepted at the HTTP boundary."""

    name: ShortText
    description: LongText
    fictional: bool
    comparison_type: ShortText
    workload: WorkloadInput
    current_infrastructure: InfrastructureInput
    proposed_infrastructure: InfrastructureInput
    migration_cost: Money
    implementation_cost: Money
    contract_years: Annotated[int, Field(ge=1, le=10)]
    assumption_sources: Annotated[
        Mapping[ShortText, SourceText] | tuple[SourceText, ...],
        Field(min_length=1, max_length=50),
    ]

    @field_validator("assumption_sources", mode="before")
    @classmethod
    def freeze_sources(cls, value: Any) -> Any:
        """Accept JSON arrays while storing the collection immutably."""
        return tuple(value) if isinstance(value, list) else value

    @field_validator("assumption_sources", mode="after")
    @classmethod
    def freeze_source_mapping(cls, value: Any) -> Any:
        """Prevent mutation of path-to-source provenance mappings."""
        return MappingProxyType(dict(value)) if isinstance(value, Mapping) else value

    @field_serializer("assumption_sources", when_used="json")
    def serialize_sources(self, value: Any) -> Any:
        """Return standard JSON objects and arrays at persistence boundaries."""
        return dict(value) if isinstance(value, Mapping) else value


class StoredAnalysis(FrozenModel):
    """One immutable evaluated version of a scenario."""

    scenario_id: str
    run_id: str
    version: Annotated[int, Field(ge=1)]
    created_at: datetime
    input: ScenarioInput
    result: dict[str, Any]
