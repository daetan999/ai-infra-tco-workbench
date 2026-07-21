"""Pure Decimal-based TCO, ROI, payback, and sensitivity calculations."""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from urllib.parse import unquote

from pydantic import ValidationError

from app.domain import (
    AnalysisResult,
    AnnualCostBreakdown,
    CalculationLineage,
    ConfidenceAssessment,
    ExecutiveSummary,
    Infrastructure,
    ScenarioComparison,
    ScenarioInput,
    SensitivityCase,
    StateTCO,
    UnitEconomics,
    Workload,
)
from app.schemas import ScenarioInput as ScenarioContract

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
MONEY = Decimal("0.01")
PERCENT = Decimal("0.01")
PAYBACK_MONTH = Decimal("0.1")
FACTOR = Decimal("0.0001")
MONTHS_PER_YEAR = Decimal("12")
GB_PER_TB = Decimal("1000")
DISCLAIMER = "Modeled estimates are decision-support inputs, not guarantees or financial advice."
SOURCE_METADATA = " | workbench-meta:"
CONFIDENCE_WEIGHTS = {"low": Decimal("0.3"), "medium": Decimal("0.65"), "high": ONE}

WORKLOAD_FIELDS = (
    "model_size_billion",
    "training_runs_per_month",
    "monthly_requests_million",
    "average_demand_units",
    "peak_demand_units",
    "annual_growth_pct",
    "productivity_value_per_hour",
    "downtime_hours_monthly",
)
INFRASTRUCTURE_FIELDS = (
    "accelerator_count",
    "compute_hourly_cost",
    "productive_utilization_pct",
    "storage_tb",
    "storage_per_tb_month",
    "network_egress_tb_month",
    "network_per_gb",
    "power_kw",
    "pue",
    "power_per_kwh",
    "staff_fte",
    "staff_annual_cost",
    "operating_hours_year",
)


def _round(value: Decimal, quantum: Decimal = MONEY) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _text(data: Mapping[str, Any], key: str, path: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}.{key} must be a non-empty string")
    return value.strip()


def _number(
    data: Mapping[str, Any],
    key: str,
    path: str,
    minimum: Decimal = ZERO,
    maximum: Decimal | None = None,
) -> Decimal:
    value = data.get(key)
    if isinstance(value, bool):
        raise ValueError(f"{path}.{key} must be a number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{path}.{key} must be a number") from exc
    if not result.is_finite() or result < minimum:
        raise ValueError(f"{path}.{key} must be at least {minimum}")
    if maximum is not None and result > maximum:
        raise ValueError(f"{path}.{key} must be at most {maximum}")
    return result


def _mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be a mapping")
    return value


def _parse_workload(data: Mapping[str, Any]) -> Workload:
    path = "workload"
    values = {
        key: _number(data, key, path) for key in WORKLOAD_FIELDS if key != "annual_growth_pct"
    }
    growth = _number(data, "annual_growth_pct", path, Decimal("-100"))
    return Workload(
        workload_type=_text(data, "workload_type", path),
        annual_growth_pct=growth,
        **values,
    )


def _parse_infrastructure(data: Mapping[str, Any], path: str) -> Infrastructure:
    values = {key: _number(data, key, path) for key in INFRASTRUCTURE_FIELDS}
    utilization = _number(data, "productive_utilization_pct", path, ONE, HUNDRED)
    if values["pue"] <= ZERO:
        raise ValueError(f"{path}.pue must be greater than zero")
    return Infrastructure(
        label=_text(data, "label", path),
        infrastructure_type=_text(data, "infrastructure_type", path),
        **{**values, "productive_utilization_pct": utilization},
    )


def _parse_sources(value: Any) -> tuple[tuple[str, str], ...]:
    if isinstance(value, Mapping):
        pairs = ((str(key).strip(), str(source).strip()) for key, source in value.items())
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        pairs = ((f"source_{index}", str(source).strip()) for index, source in enumerate(value, 1))
    else:
        raise ValueError("assumption_sources must be a mapping or sequence of source labels")
    return tuple(sorted((key, source) for key, source in pairs if key and source))


def parse_scenario(payload: Mapping[str, Any]) -> ScenarioInput:
    """Validate and copy an untrusted input mapping into immutable domain objects."""
    if not isinstance(payload, Mapping):
        raise ValueError("scenario payload must be a mapping")
    try:
        payload = ScenarioContract.model_validate(payload).model_dump(mode="json")
    except ValidationError as error:
        raise ValueError("scenario payload violates the canonical input contract") from error
    contract = _number(payload, "contract_years", "scenario", ONE)
    if contract != contract.to_integral_value():
        raise ValueError("scenario.contract_years must be a whole number")
    return ScenarioInput(
        name=_text(payload, "name", "scenario"),
        description=_text(payload, "description", "scenario"),
        comparison_type=_text(payload, "comparison_type", "scenario"),
        workload=_parse_workload(_mapping(payload, "workload")),
        current_infrastructure=_parse_infrastructure(
            _mapping(payload, "current_infrastructure"), "current_infrastructure"
        ),
        proposed_infrastructure=_parse_infrastructure(
            _mapping(payload, "proposed_infrastructure"), "proposed_infrastructure"
        ),
        migration_cost=_number(payload, "migration_cost", "scenario"),
        implementation_cost=_number(payload, "implementation_cost", "scenario"),
        contract_years=int(contract),
        assumption_sources=_parse_sources(payload.get("assumption_sources", {})),
    )


def _growth_factor(workload: Workload, year: int) -> Decimal:
    return (ONE + workload.annual_growth_pct / HUNDRED) ** (year - 1)


def _annual_cost(
    infrastructure: Infrastructure,
    workload: Workload,
    year: int,
    transition: Decimal,
    capacity_multiplier: Decimal = ONE,
) -> AnnualCostBreakdown:
    growth = _growth_factor(workload, year)
    compute = (
        infrastructure.accelerator_count
        * infrastructure.compute_hourly_cost
        * infrastructure.operating_hours_year
        * growth
        * capacity_multiplier
    )
    storage = infrastructure.storage_tb * infrastructure.storage_per_tb_month * 12 * growth
    network = (
        infrastructure.network_egress_tb_month
        * GB_PER_TB
        * infrastructure.network_per_gb
        * 12
        * growth
    )
    energy = (
        infrastructure.power_kw
        * infrastructure.pue
        * infrastructure.power_per_kwh
        * infrastructure.operating_hours_year
        * growth
        * capacity_multiplier
    )
    components = tuple(_round(value) for value in (compute, storage, network, energy))
    staffing = _round(infrastructure.staff_fte * infrastructure.staff_annual_cost)
    recurring = _round(sum(components, staffing))
    one_time = _round(transition if year == 1 else ZERO)
    return AnnualCostBreakdown(
        year,
        _round(growth, FACTOR),
        *components,
        staffing,
        one_time,
        recurring,
        _round(recurring + one_time),
    )


def _divide(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    return None if denominator <= ZERO else _round(numerator / denominator)


def _unit_economics(
    annual_costs: tuple[AnnualCostBreakdown, ...],
    workload: Workload,
    infrastructure: Infrastructure,
    years: int,
) -> UnitEconomics:
    recurring = _round(sum((item.recurring_total for item in annual_costs[:years]), ZERO))
    factors = sum((_growth_factor(workload, year) for year in range(1, years + 1)), ZERO)
    training_runs = workload.training_runs_per_month * MONTHS_PER_YEAR * factors
    requests = workload.monthly_requests_million * MONTHS_PER_YEAR * factors
    productive_hours = (
        infrastructure.accelerator_count
        * infrastructure.operating_hours_year
        * infrastructure.productive_utilization_pct
        / HUNDRED
        * years
    )
    return UnitEconomics(
        horizon_years=years,
        recurring_cost=recurring,
        cost_per_training_run=_divide(recurring, training_runs),
        cost_per_million_requests=_divide(recurring, requests),
        cost_per_productive_accelerator_hour=_divide(recurring, productive_hours),
    )


def _state_tco(
    infrastructure: Infrastructure,
    workload: Workload,
    transition: Decimal = ZERO,
    capacity_multiplier: Decimal = ONE,
) -> StateTCO:
    annual = tuple(
        _annual_cost(infrastructure, workload, year, transition, capacity_multiplier)
        for year in range(1, 6)
    )
    return StateTCO(
        label=infrastructure.label,
        infrastructure_type=infrastructure.infrastructure_type,
        annual_costs=annual,
        tco_3_year=_round(sum((item.total for item in annual[:3]), ZERO)),
        tco_5_year=_round(sum((item.total for item in annual), ZERO)),
        unit_economics_3_year=_unit_economics(annual, workload, infrastructure, 3),
        unit_economics_5_year=_unit_economics(annual, workload, infrastructure, 5),
    )


def _productivity_values(workload: Workload) -> tuple[Decimal, ...]:
    annual_base = workload.productivity_value_per_hour * workload.downtime_hours_monthly * 12
    return tuple(_round(annual_base * _growth_factor(workload, year)) for year in range(1, 6))


def _percentage(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    return None if denominator == ZERO else _round(numerator / denominator * HUNDRED, PERCENT)


def _payback(
    current: StateTCO,
    proposed: StateTCO,
    productivity: tuple[Decimal, ...],
    investment: Decimal,
) -> Decimal | None:
    remaining = investment
    elapsed_months = ZERO
    benefits = tuple(
        current.annual_costs[index].recurring_total
        - proposed.annual_costs[index].recurring_total
        + productivity[index]
        for index in range(5)
    )
    if remaining == ZERO and any(benefit > ZERO for benefit in benefits):
        return ZERO.quantize(PAYBACK_MONTH)
    for benefit in benefits:
        if benefit > ZERO and benefit >= remaining:
            return _round(elapsed_months + remaining / benefit * 12, PAYBACK_MONTH)
        remaining -= benefit
        elapsed_months += 12
    return None


def _comparison(
    scenario: ScenarioInput,
    current: StateTCO,
    proposed: StateTCO,
) -> ScenarioComparison:
    productivity = _productivity_values(scenario.workload)
    savings_3 = _round(current.tco_3_year - proposed.tco_3_year)
    savings_5 = _round(current.tco_5_year - proposed.tco_5_year)
    productivity_3 = _round(sum(productivity[:3], ZERO))
    productivity_5 = _round(sum(productivity, ZERO))
    net_3 = _round(savings_3 + productivity_3)
    net_5 = _round(savings_5 + productivity_5)
    investment = scenario.migration_cost + scenario.implementation_cost
    payback = _payback(current, proposed, productivity, investment)
    return ScenarioComparison(
        scenario.comparison_type,
        savings_3,
        savings_5,
        _percentage(savings_3, current.tco_3_year),
        _percentage(savings_5, current.tco_5_year),
        productivity_3,
        productivity_5,
        net_3,
        net_5,
        _percentage(net_3, proposed.tco_3_year),
        _percentage(net_5, proposed.tco_5_year),
        payback,
        payback is not None and payback <= Decimal("60"),
        DISCLAIMER,
    )


def _sensitivity_case(
    scenario: ScenarioInput,
    current: StateTCO,
    dimension: str,
    case: str,
    value: Decimal,
) -> SensitivityCase:
    proposed_infra = scenario.proposed_infrastructure
    workload = scenario.workload
    capacity_multiplier = ONE
    if dimension == "price":
        proposed_infra = replace(proposed_infra, compute_hourly_cost=value)
    elif dimension == "growth":
        workload = replace(workload, annual_growth_pct=value)
    elif dimension == "energy":
        proposed_infra = replace(proposed_infra, power_per_kwh=value)
    elif dimension == "utilization" and value > ZERO:
        capacity_multiplier = proposed_infra.productive_utilization_pct / value
        proposed_infra = replace(proposed_infra, productive_utilization_pct=value)
    transition = scenario.migration_cost + scenario.implementation_cost
    proposed = _state_tco(proposed_infra, workload, transition, capacity_multiplier)
    comparison_current = (
        _state_tco(scenario.current_infrastructure, workload) if dimension == "growth" else current
    )
    adjusted_scenario = replace(scenario, workload=workload, proposed_infrastructure=proposed_infra)
    comparison = _comparison(adjusted_scenario, comparison_current, proposed)
    return SensitivityCase(
        dimension,
        case,
        _round(value, FACTOR),
        proposed.tco_5_year,
        comparison.savings_5_year,
        comparison.net_value_5_year,
        comparison.roi_5_year_pct,
    )


def _sensitivity_values(scenario: ScenarioInput) -> tuple[tuple[str, tuple[Decimal, ...]], ...]:
    infrastructure = scenario.proposed_infrastructure
    growth = scenario.workload.annual_growth_pct
    utilization = infrastructure.productive_utilization_pct
    return (
        ("utilization", (max(ONE, utilization - 10), utilization, min(HUNDRED, utilization + 10))),
        (
            "price",
            tuple(
                infrastructure.compute_hourly_cost * factor
                for factor in (Decimal("0.9"), ONE, Decimal("1.1"))
            ),
        ),
        ("growth", (max(Decimal("-100"), growth - 5), growth, growth + 5)),
        (
            "energy",
            tuple(
                infrastructure.power_per_kwh * factor
                for factor in (Decimal("0.8"), ONE, Decimal("1.2"))
            ),
        ),
    )


def _sensitivities(scenario: ScenarioInput, current: StateTCO) -> tuple[SensitivityCase, ...]:
    labels = ("low", "base", "high")
    return tuple(
        _sensitivity_case(scenario, current, dimension, label, value)
        for dimension, values in _sensitivity_values(scenario)
        for label, value in zip(labels, values, strict=True)
    )


def _material_assumptions(scenario: ScenarioInput) -> tuple[str, ...]:
    workload = tuple(
        f"workload.{field}"
        for field in WORKLOAD_FIELDS
        if getattr(scenario.workload, field) != ZERO
    )
    infrastructure = tuple(
        f"{prefix}.{field}"
        for prefix, value in (
            ("current_infrastructure", scenario.current_infrastructure),
            ("proposed_infrastructure", scenario.proposed_infrastructure),
        )
        for field in INFRASTRUCTURE_FIELDS
        if getattr(value, field) != ZERO
    )
    transition = tuple(
        field
        for field in ("migration_cost", "implementation_cost")
        if getattr(scenario, field) != ZERO
    )
    return (*workload, *infrastructure, *transition, "contract_years")


def _source_details(source: str) -> tuple[str, Decimal]:
    clean, marker, encoded = source.rpartition(SOURCE_METADATA)
    if not marker:
        return source, CONFIDENCE_WEIGHTS["medium"]
    try:
        confidence = str(json.loads(unquote(encoded)).get("confidence", "medium")).lower()
    except (json.JSONDecodeError, TypeError, ValueError):
        confidence = "medium"
    return clean.strip() or "Unverified hypothesis", CONFIDENCE_WEIGHTS.get(
        confidence, CONFIDENCE_WEIGHTS["medium"]
    )


def _source_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _find_source(path: str, sources: Mapping[str, str]) -> tuple[str, Decimal] | None:
    accepted = {_source_key(path), _source_key(path.rsplit(".", 1)[-1])}
    for key, source in sources.items():
        if _source_key(key) in accepted:
            return _source_details(source)
    return None


def _confidence(scenario: ScenarioInput) -> ConfidenceAssessment:
    sources = dict(scenario.assumption_sources)
    material = _material_assumptions(scenario)
    matches = tuple(_find_source(path, sources) for path in material)
    sourced = sum(match is not None for match in matches)
    weighted = sum((match[1] for match in matches if match is not None), start=ZERO)
    coverage = _round(weighted / Decimal(len(material)) * HUNDRED, PERCENT)
    contract_coverage = _round(min(Decimal(scenario.contract_years) / 5, ONE) * HUNDRED, PERCENT)
    score = _round(coverage * Decimal("0.8") + contract_coverage * Decimal("0.2"), PAYBACK_MONTH)
    level = "High" if score >= 80 else "Medium" if score >= 50 else "Low"
    rationale = (
        f"{sourced} of {len(material)} material assumptions have confidence-weighted sources; "
        f"pricing is contract-covered for {scenario.contract_years} year(s) of the "
        "five-year horizon."
    )
    return ConfidenceAssessment(
        score, level, coverage, contract_coverage, sourced, len(material), rationale
    )


def _source_refs(scenario: ScenarioInput, paths: tuple[str, ...]) -> tuple[str, ...]:
    sources = dict(scenario.assumption_sources)
    return tuple(
        source[0] if (source := _find_source(path, sources)) else f"Unreferenced user input: {path}"
        for path in paths
    )


def _line(
    scenario: ScenarioInput,
    path: str,
    formula: str,
    inputs: tuple[str, ...],
    value: Decimal | int | bool | str | None,
    note: str = "Derived deterministically with Decimal arithmetic and explicit rounding.",
) -> CalculationLineage:
    return CalculationLineage(path, formula, inputs, _source_refs(scenario, inputs), value, note)


def _annual_lineage_spec(
    prefix: str,
) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    formulas = {
        "growth_factor": "(1 + annual_growth_pct / 100) ** (year - 1)",
        "compute": "accelerator_count x compute_hourly_cost x operating_hours_year x growth",
        "storage": "storage_tb x storage_per_tb_month x 12 x growth",
        "network": "network_egress_tb_month x 1,000 x network_per_gb x 12 x growth",
        "energy": "power_kw x pue x power_per_kwh x operating_hours_year x growth",
        "staffing": "staff_fte x staff_annual_cost",
        "transition": "migration_cost + implementation_cost in proposed year 1; otherwise 0",
        "recurring_total": "compute + storage + network + energy + staffing",
        "total": "recurring_total + transition",
    }
    paths = {
        "growth_factor": ("workload.annual_growth_pct",),
        "compute": (
            f"{prefix}.accelerator_count",
            f"{prefix}.compute_hourly_cost",
            f"{prefix}.operating_hours_year",
            "workload.annual_growth_pct",
        ),
        "storage": (
            f"{prefix}.storage_tb",
            f"{prefix}.storage_per_tb_month",
            "workload.annual_growth_pct",
        ),
        "network": (
            f"{prefix}.network_egress_tb_month",
            f"{prefix}.network_per_gb",
            "workload.annual_growth_pct",
        ),
        "energy": (
            f"{prefix}.power_kw",
            f"{prefix}.pue",
            f"{prefix}.power_per_kwh",
            f"{prefix}.operating_hours_year",
            "workload.annual_growth_pct",
        ),
        "staffing": (f"{prefix}.staff_fte", f"{prefix}.staff_annual_cost"),
        "transition": ("migration_cost", "implementation_cost"),
        "recurring_total": ("derived annual components",),
        "total": ("derived recurring total", "derived transition cost"),
    }
    return formulas, paths


def _annual_lineage(
    scenario: ScenarioInput, state_name: str, state: StateTCO
) -> tuple[CalculationLineage, ...]:
    formulas, paths = _annual_lineage_spec(f"{state_name}_infrastructure")
    return tuple(
        _line(
            scenario,
            f"{state_name}.annual_costs[{annual.year}].{field}",
            formulas[field],
            paths[field],
            getattr(annual, field),
        )
        for annual in state.annual_costs
        for field in formulas
    )


def _state_summary_lineage(
    scenario: ScenarioInput, state_name: str, state: StateTCO
) -> tuple[CalculationLineage, ...]:
    entries: tuple[tuple[str, str, Decimal | None], ...] = (
        ("tco_3_year", "sum annual total for years 1-3", state.tco_3_year),
        ("tco_5_year", "sum annual total for years 1-5", state.tco_5_year),
    )
    for years, units in ((3, state.unit_economics_3_year), (5, state.unit_economics_5_year)):
        entries += (
            (
                f"unit_economics_{years}_year.recurring_cost",
                "sum recurring annual costs",
                units.recurring_cost,
            ),
            (
                f"unit_economics_{years}_year.cost_per_training_run",
                "recurring cost ÷ total training runs",
                units.cost_per_training_run,
            ),
            (
                f"unit_economics_{years}_year.cost_per_million_requests",
                "recurring cost ÷ total requests in millions",
                units.cost_per_million_requests,
            ),
            (
                f"unit_economics_{years}_year.cost_per_productive_accelerator_hour",
                "recurring cost ÷ productive accelerator hours",
                units.cost_per_productive_accelerator_hour,
            ),
        )
    return tuple(
        _line(
            scenario,
            f"{state_name}.{path}",
            formula,
            (f"{state_name}.annual_costs", "workload"),
            value,
        )
        for path, formula, value in entries
    )


def _comparison_lineage(
    scenario: ScenarioInput, comparison: ScenarioComparison
) -> tuple[CalculationLineage, ...]:
    formulas = {
        "savings_3_year": "current 3-year TCO - proposed 3-year TCO",
        "savings_5_year": "current 5-year TCO - proposed 5-year TCO",
        "savings_3_year_pct": "3-year savings / current 3-year TCO x 100",
        "savings_5_year_pct": "5-year savings / current 5-year TCO x 100",
        "productivity_value_3_year": (
            "sum productivity value per hour x downtime hours x 12 x growth"
        ),
        "productivity_value_5_year": (
            "sum productivity value per hour x downtime hours x 12 x growth"
        ),
        "net_value_3_year": "3-year TCO savings + 3-year modeled productivity value",
        "net_value_5_year": "5-year TCO savings + 5-year modeled productivity value",
        "roi_3_year_pct": "3-year net value / proposed 3-year TCO x 100",
        "roi_5_year_pct": "5-year net value / proposed 5-year TCO x 100",
        "payback_months": "transition investment / cumulative modeled monthly operating benefit",
        "break_even_within_5_years": "payback months exists and is no more than 60",
    }
    inputs = (
        "current derived TCO",
        "proposed derived TCO",
        "workload.productivity_value_per_hour",
        "workload.downtime_hours_monthly",
        "workload.annual_growth_pct",
    )
    return tuple(
        _line(scenario, f"comparison.{field}", formula, inputs, getattr(comparison, field))
        for field, formula in formulas.items()
    )


def _sensitivity_lineage(
    scenario: ScenarioInput, sensitivities: tuple[SensitivityCase, ...]
) -> tuple[CalculationLineage, ...]:
    return tuple(
        _line(
            scenario,
            f"sensitivities.{case.dimension}.{case.case}.{field}",
            f"recalculate proposed case after varying only {case.dimension}",
            (f"proposed_infrastructure.{case.dimension}", "all base scenario assumptions"),
            getattr(case, field),
            "One-factor deterministic sensitivity; not a forecast or probability distribution.",
        )
        for case in sensitivities
        for field in (
            "assumption_value",
            "proposed_tco_5_year",
            "savings_5_year",
            "net_value_5_year",
            "roi_5_year_pct",
        )
    )


def _closing_lineage(
    scenario: ScenarioInput,
    confidence: ConfidenceAssessment,
    summary: ExecutiveSummary,
) -> tuple[CalculationLineage, ...]:
    confidence_items = (
        ("score", confidence.score),
        ("source_coverage_pct", confidence.source_coverage_pct),
        ("contract_coverage_pct", confidence.contract_coverage_pct),
        ("sourced_assumptions", confidence.sourced_assumptions),
        ("material_assumptions", confidence.material_assumptions),
        ("level", confidence.level),
        ("rationale", confidence.rationale),
    )
    summary_fields = (
        "current_tco_3_year",
        "proposed_tco_3_year",
        "current_tco_5_year",
        "proposed_tco_5_year",
        "savings_5_year",
        "productivity_value_5_year",
        "net_value_5_year",
        "roi_5_year_pct",
        "payback_months",
        "confidence_level",
        "recommendation",
    )
    confidence_lines = tuple(
        _line(
            scenario,
            f"confidence.{field}",
            "source coverage weighted 80% + contract coverage weighted 20%",
            ("assumption_sources", "contract_years"),
            value,
        )
        for field, value in confidence_items
    )
    summary_lines = tuple(
        _line(
            scenario,
            f"executive_summary.{field}",
            "copy or interpret the corresponding modeled result",
            ("derived analysis result",),
            getattr(summary, field),
        )
        for field in summary_fields
    )
    return confidence_lines + summary_lines


def _lineage(
    scenario: ScenarioInput,
    current: StateTCO,
    proposed: StateTCO,
    comparison: ScenarioComparison,
    sensitivities: tuple[SensitivityCase, ...],
    confidence: ConfidenceAssessment,
    summary: ExecutiveSummary,
) -> tuple[CalculationLineage, ...]:
    return (
        _annual_lineage(scenario, "current", current)
        + _annual_lineage(scenario, "proposed", proposed)
        + _state_summary_lineage(scenario, "current", current)
        + _state_summary_lineage(scenario, "proposed", proposed)
        + _comparison_lineage(scenario, comparison)
        + _sensitivity_lineage(scenario, sensitivities)
        + _closing_lineage(scenario, confidence, summary)
    )


def _executive_summary(
    scenario: ScenarioInput,
    current: StateTCO,
    proposed: StateTCO,
    comparison: ScenarioComparison,
    confidence: ConfidenceAssessment,
) -> ExecutiveSummary:
    if comparison.net_value_5_year > ZERO:
        recommendation = "Modeled financial advantage for the proposed infrastructure."
    else:
        recommendation = (
            "Modeled results do not show a financial advantage for the proposed infrastructure."
        )
    return ExecutiveSummary(
        scenario.name,
        current.tco_3_year,
        proposed.tco_3_year,
        current.tco_5_year,
        proposed.tco_5_year,
        comparison.savings_5_year,
        comparison.productivity_value_5_year,
        comparison.net_value_5_year,
        comparison.roi_5_year_pct,
        comparison.payback_months,
        confidence.level,
        recommendation,
        DISCLAIMER,
    )


def calculate_analysis(payload: Mapping[str, Any]) -> AnalysisResult:
    """Calculate an immutable, deterministic five-year financial analysis."""
    scenario = parse_scenario(payload)
    current = _state_tco(scenario.current_infrastructure, scenario.workload)
    transition = scenario.migration_cost + scenario.implementation_cost
    proposed = _state_tco(scenario.proposed_infrastructure, scenario.workload, transition)
    comparison = _comparison(scenario, current, proposed)
    sensitivities = _sensitivities(scenario, current)
    confidence = _confidence(scenario)
    summary = _executive_summary(scenario, current, proposed, comparison, confidence)
    lineage = _lineage(scenario, current, proposed, comparison, sensitivities, confidence, summary)
    return AnalysisResult(
        scenario.name,
        scenario.description,
        scenario.comparison_type,
        current,
        proposed,
        comparison,
        sensitivities,
        confidence,
        lineage,
        summary,
    )


def evaluate_financial_scenario(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Stable JSON-serializable adapter used by API, persistence, and export layers."""
    return calculate_analysis(payload).to_dict()
