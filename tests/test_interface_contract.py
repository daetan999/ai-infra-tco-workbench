"""Browser interface contracts that should survive internal UI refactors."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
INDEX = ROOT / "templates" / "index.html"
SCRIPT = ROOT / "static" / "app.js"
STYLES = ROOT / "static" / "styles.css"
FAVICON = ROOT / "static" / "favicon.svg"
REQUIRED_FORM_FIELDS = {
    "name",
    "description",
    "comparison_type",
    "workload.workload_type",
    "workload.model_size_billion",
    "workload.training_runs_per_month",
    "workload.monthly_requests_million",
    "workload.average_demand_units",
    "workload.peak_demand_units",
    "workload.annual_growth_pct",
    "workload.productivity_value_per_hour",
    "workload.downtime_hours_monthly",
    "current.label",
    "current.infrastructure_type",
    "current.accelerator_count",
    "current.compute_hourly_cost",
    "current.productive_utilization_pct",
    "current.storage_tb",
    "current.storage_per_tb_month",
    "current.network_egress_tb_month",
    "current.network_per_gb",
    "current.power_kw",
    "current.pue",
    "current.power_per_kwh",
    "current.staff_fte",
    "current.staff_annual_cost",
    "current.operating_hours_year",
    "proposed.label",
    "proposed.infrastructure_type",
    "proposed.accelerator_count",
    "proposed.compute_hourly_cost",
    "proposed.productive_utilization_pct",
    "proposed.storage_tb",
    "proposed.storage_per_tb_month",
    "proposed.network_egress_tb_month",
    "proposed.network_per_gb",
    "proposed.power_kw",
    "proposed.pue",
    "proposed.power_per_kwh",
    "proposed.staff_fte",
    "proposed.staff_annual_cost",
    "proposed.operating_hours_year",
    "migration_cost",
    "implementation_cost",
    "contract_years",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture
def stored_analysis_response() -> dict[str, object]:
    """Mirror the saved-analysis envelope consumed by a real browser session."""
    return {
        "success": True,
        "data": {
            "scenario_id": "245da36b-8a7d-43be-aa9e-f21433dcbc6e",
            "created_at": "2026-07-21T04:00:00Z",
            "input": {
                "name": "Fictional accelerator decision",
                "assumption_sources": {"compute_hourly_cost": "Fictional quote"},
            },
            "result": _stored_result(),
        },
        "error": None,
    }


def _stored_result() -> dict[str, object]:
    annual = [
        {"year": year, "recurring_total": 100_000 * year, "transition": 0, "total": 100_000 * year}
        for year in range(1, 6)
    ]
    units = {
        "recurring_cost": 300_000,
        "cost_per_training_run": 1200,
        "cost_per_million_requests": 42,
        "cost_per_productive_accelerator_hour": 17,
    }
    return {
        "current": {
            "annual_costs": annual,
            "unit_economics_3_year": units,
            "unit_economics_5_year": units,
        },
        "proposed": {
            "annual_costs": annual,
            "unit_economics_3_year": units,
            "unit_economics_5_year": units,
        },
        "comparison": {
            "net_value_3_year": 45_000,
            "net_value_5_year": 90_000,
            "payback_months": 18.4,
        },
        "sensitivities": [{"dimension": "price", "case": "low", "net_value_5_year": 110_000}],
        "confidence": {
            "score": 64,
            "level": "Medium",
            "sourced_assumptions": 22,
            "material_assumptions": 34,
        },
        "lineage": [
            {
                "output_path": "proposed.tco_5_year",
                "formula": "sum annual total",
                "derived_value": 900_000,
            }
        ],
        "executive_summary": {
            "net_value_5_year": 90_000,
            "recommendation": "Validate with a controlled pilot.",
        },
    }


def test_workspace_exposes_primary_decision_landmarks() -> None:
    html = read(INDEX)

    assert 'aria-label="Scenario workspace"' in html
    assert 'aria-label="Decision analysis"' in html
    assert 'id="current-state"' in html
    assert 'id="proposed-state"' in html
    assert 'id="executive-summary"' in html
    assert 'id="calculation-lineage"' in html
    assert "3-year TCO" in html
    assert "5-year TCO" in html


def test_form_names_match_the_scenario_create_contract() -> None:
    html = read(INDEX)
    for field_name in REQUIRED_FORM_FIELDS:
        assert f'name="{field_name}"' in html, field_name


def test_client_uses_safe_rendering_and_expected_scenario_routes() -> None:
    script = read(SCRIPT)

    assert "/api/scenarios" in script
    assert "/exports/" in script
    assert 'current_infrastructure: infrastructure("current")' in script
    assert 'proposed_infrastructure: infrastructure("proposed")' in script
    assert 'method: "POST"' in script
    assert 'method: "PUT"' in script
    assert 'method: "DELETE"' in script
    assert "beforeunload" in script
    assert ".textContent" in script
    assert ".createElement(" in script
    assert "innerHTML" not in script
    assert "insertAdjacentHTML" not in script


def test_client_consumes_saved_analysis_envelope_and_engine_outputs(
    stored_analysis_response: dict[str, object],
) -> None:
    script = read(SCRIPT)
    data = stored_analysis_response["data"]

    assert isinstance(data, dict)
    assert data["input"]["name"] == "Fictional accelerator decision"
    assert "analysis.input" in script
    assert "scenario.input?.name" in script
    assert "scenario.result || null" in script
    assert "body?.error?.message" in script
    assert "assumptionSources(state.assumptions)" in script
    assert '$(`[name="${name}"]`, $("#scenario-form"))' in script
    assert "result.current.annual_costs" in script
    assert "result.comparison.net_value_5_year" in script
    assert "result.sensitivities" in script
    assert "result.lineage" in script
    assert "result.executive_summary" in script


def test_pure_browser_contract_handles_real_envelopes_and_finance(
    stored_analysis_response: dict[str, object],
) -> None:
    if not shutil.which("node"):
        pytest.skip("Node.js is required for the browser contract test")
    probe = """
const fs = require("node:fs");
const ui = require("./static/app.js");
const response = JSON.parse(fs.readFileSync(0, "utf8"));
const scenario = ui.normalizeScenario(response);
const infrastructure = {
  accelerator_count: 2, compute_hourly_cost: 10, operating_hours_year: 1000,
  storage_tb: 1, storage_per_tb_month: 100,
  network_egress_tb_month: 1, network_per_gb: 0.1,
  power_kw: 10, pue: 1.2, power_per_kwh: 0.2,
  staff_fte: 1, staff_annual_cost: 50000
};
const item = {
  assumption: "compute_hourly_cost", value: "€".repeat(80),
  source: "Invoice", confidence: "high"
};
const stored = ui.assumptionSources([item]).compute_hourly_cost;
const restored = ui.splitStoredSource(stored);
process.stdout.write(JSON.stringify({
  name: scenario.name, id: scenario.id, result: Boolean(scenario.result),
  annualCost: ui.annualCost(infrastructure), restored, storedLength: stored.length,
  exportPath: ui.exportPath("scenario/id", "pdf")
}));
"""
    completed = subprocess.run(
        ["node", "-e", probe],
        cwd=ROOT,
        input=json.dumps(stored_analysis_response),
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(completed.stdout)

    assert observed["name"] == "Fictional accelerator decision"
    assert observed["id"] == "245da36b-8a7d-43be-aa9e-f21433dcbc6e"
    assert observed["result"] is True
    assert observed["annualCost"] == 74_800
    assert observed["storedLength"] <= 500
    assert observed["restored"]["source"] == "Invoice"
    assert observed["restored"]["confidence"] == "high"
    assert 0 < len(observed["restored"]["value"]) < 80
    assert observed["exportPath"] == "/api/scenarios/scenario%2Fid/exports/pdf"


def test_layout_contract_covers_focus_reflow_and_overflow() -> None:
    styles = read(STYLES)

    assert "[hidden]" in styles
    assert "display: none !important" in styles
    assert ":focus-visible" in styles
    assert "overflow-x: auto" in styles
    assert "@media (max-width: 760px)" in styles
    assert "minmax(0, 1fr)" in styles
    assert "prefers-reduced-motion" in styles
    assert "width: 100vw" not in styles


def test_assets_remain_small_and_favicon_is_accessible_svg() -> None:
    for path in (INDEX, SCRIPT, STYLES):
        assert len(read(path).splitlines()) < 800, path.name

    favicon = read(FAVICON)
    assert favicon.startswith("<svg")
    assert 'viewBox="0 0 64 64"' in favicon
