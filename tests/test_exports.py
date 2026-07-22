"""Portable export tests."""

import csv
import io
import json
from urllib.parse import quote

from pypdf import PdfReader

from app.engine import evaluate_financial_scenario
from app.exports import export_csv, export_json, export_pdf
from app.repository import AnalysisRepository
from app.schemas import ScenarioInput


def stored_analysis(tmp_path, scenario_payload):
    repository = AnalysisRepository(tmp_path / "analysis.db")
    return repository.create(ScenarioInput.model_validate(scenario_payload), {"net_savings": 42.0})


def test_json_export_is_machine_readable(tmp_path, scenario_payload) -> None:
    analysis = stored_analysis(tmp_path, scenario_payload)

    payload = json.loads(export_json(analysis))

    assert payload["scenario_id"] == analysis.scenario_id
    assert payload["input"]["name"] == "Inference modernization"
    assert payload["result"]["net_savings"] == 42.0


def test_csv_export_flattens_fields_and_blocks_formula_injection(
    tmp_path, scenario_payload
) -> None:
    scenario_payload["name"] = '=HYPERLINK("https://unsafe.example")'
    analysis = stored_analysis(tmp_path, scenario_payload)

    rows = list(csv.reader(io.StringIO(export_csv(analysis))))
    values = dict(rows[1:])

    assert rows[0] == ["field", "value"]
    assert values["input.name"].startswith("'=HYPERLINK")
    assert values["result.net_savings"] == "42.0"


def test_pdf_export_produces_a_real_pdf(tmp_path, scenario_payload) -> None:
    metadata = quote(json.dumps({"value": "$2.50", "confidence": "high"}))
    scenario_payload["assumption_sources"] = {
        "current_infrastructure.compute_hourly_cost": (
            f"Fictional invoice | workbench-meta:{metadata}"
        ),
        "proposed_infrastructure.compute_hourly_cost": (
            f"Fictional invoice | workbench-meta:{metadata}"
        ),
    }
    repository = AnalysisRepository(tmp_path / "analysis.db")
    scenario = ScenarioInput.model_validate(scenario_payload)
    result = evaluate_financial_scenario(scenario.model_dump(mode="json"))
    analysis = repository.create(scenario, result)

    document = export_pdf(analysis)
    reader = PdfReader(io.BytesIO(document))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    normalized_text = " ".join(text.split())

    assert document.startswith(b"%PDF-")
    assert len(document) > 5000
    assert len(reader.pages) >= 3
    assert "Executive summary" in text
    assert "Five-year comparison" in text
    assert "Sensitivity analysis" in text
    assert "Calculation lineage" in text
    assert "Fictional demonstration" in text
    assert "not a guarantee" in text
    assert "Page 1" in text
    assert "Fictional invoice (high confidence)" in normalized_text
    assert normalized_text.count("Fictional invoice (high confidence)") == 1
    assert "Training Runs Per Month" not in normalized_text
    assert "workbench-meta" not in text
