"""Immutable domain contracts for deterministic infrastructure finance analysis."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

JsonMapping = dict[str, Any]


def _json_value(value: Any) -> Any:
    """Convert immutable domain values to JSON-compatible primitive values."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class Workload:
    workload_type: str
    model_size_billion: Decimal
    training_runs_per_month: Decimal
    monthly_requests_million: Decimal
    average_demand_units: Decimal
    peak_demand_units: Decimal
    annual_growth_pct: Decimal
    productivity_value_per_hour: Decimal
    downtime_hours_monthly: Decimal


@dataclass(frozen=True, slots=True)
class Infrastructure:
    label: str
    infrastructure_type: str
    accelerator_count: Decimal
    compute_hourly_cost: Decimal
    productive_utilization_pct: Decimal
    storage_tb: Decimal
    storage_per_tb_month: Decimal
    network_egress_tb_month: Decimal
    network_per_gb: Decimal
    power_kw: Decimal
    pue: Decimal
    power_per_kwh: Decimal
    staff_fte: Decimal
    staff_annual_cost: Decimal
    operating_hours_year: Decimal


@dataclass(frozen=True, slots=True)
class ScenarioInput:
    name: str
    description: str
    comparison_type: str
    workload: Workload
    current_infrastructure: Infrastructure
    proposed_infrastructure: Infrastructure
    migration_cost: Decimal
    implementation_cost: Decimal
    contract_years: int
    assumption_sources: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class AnnualCostBreakdown:
    year: int
    growth_factor: Decimal
    compute: Decimal
    storage: Decimal
    network: Decimal
    energy: Decimal
    staffing: Decimal
    transition: Decimal
    recurring_total: Decimal
    total: Decimal


@dataclass(frozen=True, slots=True)
class UnitEconomics:
    horizon_years: int
    recurring_cost: Decimal
    cost_per_training_run: Decimal | None
    cost_per_million_requests: Decimal | None
    cost_per_productive_accelerator_hour: Decimal | None


@dataclass(frozen=True, slots=True)
class StateTCO:
    label: str
    infrastructure_type: str
    annual_costs: tuple[AnnualCostBreakdown, ...]
    tco_3_year: Decimal
    tco_5_year: Decimal
    unit_economics_3_year: UnitEconomics
    unit_economics_5_year: UnitEconomics


@dataclass(frozen=True, slots=True)
class ScenarioComparison:
    comparison_type: str
    savings_3_year: Decimal
    savings_5_year: Decimal
    savings_3_year_pct: Decimal | None
    savings_5_year_pct: Decimal | None
    productivity_value_3_year: Decimal
    productivity_value_5_year: Decimal
    net_value_3_year: Decimal
    net_value_5_year: Decimal
    roi_3_year_pct: Decimal | None
    roi_5_year_pct: Decimal | None
    payback_months: Decimal | None
    break_even_within_5_years: bool
    disclaimer: str


@dataclass(frozen=True, slots=True)
class SensitivityCase:
    dimension: str
    case: str
    assumption_value: Decimal
    proposed_tco_5_year: Decimal
    savings_5_year: Decimal
    net_value_5_year: Decimal
    roi_5_year_pct: Decimal | None


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    score: Decimal
    level: str
    source_coverage_pct: Decimal
    contract_coverage_pct: Decimal
    sourced_assumptions: int
    material_assumptions: int
    rationale: str


@dataclass(frozen=True, slots=True)
class CalculationLineage:
    output_path: str
    formula: str
    input_paths: tuple[str, ...]
    source_refs: tuple[str, ...]
    derived_value: Decimal | int | bool | str | None
    note: str


@dataclass(frozen=True, slots=True)
class ExecutiveSummary:
    scenario_name: str
    current_tco_3_year: Decimal
    proposed_tco_3_year: Decimal
    current_tco_5_year: Decimal
    proposed_tco_5_year: Decimal
    savings_5_year: Decimal
    productivity_value_5_year: Decimal
    net_value_5_year: Decimal
    roi_5_year_pct: Decimal | None
    payback_months: Decimal | None
    confidence_level: str
    recommendation: str
    disclaimer: str


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    name: str
    description: str
    comparison_type: str
    current: StateTCO
    proposed: StateTCO
    comparison: ScenarioComparison
    sensitivities: tuple[SensitivityCase, ...]
    confidence: ConfidenceAssessment
    lineage: tuple[CalculationLineage, ...]
    executive_summary: ExecutiveSummary

    def to_dict(self) -> JsonMapping:
        """Return a JSON-serializable copy while preserving internal Decimal math."""
        return _json_value(asdict(self))
