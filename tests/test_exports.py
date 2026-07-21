"""Portable export tests."""

import csv
import io
import json

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


def test_csv_export_flattens_fields_and_blocks_formula_injection(tmp_path, scenario_payload) -> None:
    scenario_payload["name"] = "=HYPERLINK(\"https://unsafe.example\")"
    analysis = stored_analysis(tmp_path, scenario_payload)

    rows = list(csv.reader(io.StringIO(export_csv(analysis))))
    values = dict(rows[1:])

    assert rows[0] == ["field", "value"]
    assert values["input.name"].startswith("'=HYPERLINK")
    assert values["result.net_savings"] == "42.0"


def test_pdf_export_produces_a_real_pdf(tmp_path, scenario_payload) -> None:
    analysis = stored_analysis(tmp_path, scenario_payload)

    document = export_pdf(analysis)

    assert document.startswith(b"%PDF-")
    assert len(document) > 1000
