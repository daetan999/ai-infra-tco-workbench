"""FastAPI boundary and workflow tests."""

from fastapi.testclient import TestClient

from app.main import create_app


def client_for(tmp_path, evaluator) -> TestClient:
    return TestClient(create_app(db_path=tmp_path / "analysis.db", evaluator=evaluator))


def test_health_and_docs_are_available(tmp_path, evaluator) -> None:
    with client_for(tmp_path, evaluator) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200


def test_crud_workflow_creates_immutable_versions(tmp_path, evaluator, scenario_payload) -> None:
    with client_for(tmp_path, evaluator) as client:
        created_response = client.post("/api/scenarios", json=scenario_payload)
        assert created_response.status_code == 201
        created = created_response.json()["data"]

        changed = {**scenario_payload, "name": "Modernization with revised demand"}
        updated_response = client.put(f"/api/scenarios/{created['scenario_id']}", json=changed)
        assert updated_response.status_code == 200
        updated = updated_response.json()["data"]

        assert updated["version"] == 2
        assert client.get(f"/api/scenarios/{created['scenario_id']}").json()["data"] == updated
        versions = client.get(f"/api/scenarios/{created['scenario_id']}/versions").json()["data"]
        assert [item["version"] for item in versions] == [2, 1]
        original = client.get(f"/api/scenarios/{created['scenario_id']}/versions/1")
        assert original.json()["data"]["input"]["name"] == "Inference modernization"
        assert len(client.get("/api/scenarios").json()["data"]) == 1

        deleted = client.delete(f"/api/scenarios/{created['scenario_id']}")
        assert deleted.status_code == 200
        assert client.get(f"/api/scenarios/{created['scenario_id']}").status_code == 404


def test_exports_have_safe_content_dispositions(tmp_path, evaluator, scenario_payload) -> None:
    with client_for(tmp_path, evaluator) as client:
        created = client.post("/api/scenarios", json=scenario_payload).json()["data"]
        base = f"/api/scenarios/{created['scenario_id']}/exports"

        json_response = client.get(f"{base}/json")
        csv_response = client.get(f"{base}/csv")
        pdf_response = client.get(f"{base}/pdf")

        assert json_response.headers["content-type"].startswith("application/json")
        assert csv_response.headers["content-type"].startswith("text/csv")
        assert pdf_response.headers["content-type"] == "application/pdf"
        assert "attachment;" in pdf_response.headers["content-disposition"]
        assert pdf_response.content.startswith(b"%PDF-")


def test_validation_and_missing_records_use_error_envelopes(
    tmp_path, evaluator, scenario_payload
) -> None:
    with client_for(tmp_path, evaluator) as client:
        scenario_payload["contract_years"] = 0
        validation = client.post("/api/scenarios", json=scenario_payload)
        missing = client.get("/api/scenarios/00000000-0000-0000-0000-000000000000")

        assert validation.status_code == 422
        assert validation.json()["success"] is False
        assert validation.json()["error"]["code"] == "validation_error"
        assert missing.status_code == 404
        assert missing.json() == {
            "success": False,
            "data": None,
            "error": {"code": "not_found", "message": "Scenario not found."},
        }


def test_unexpected_errors_are_redacted(tmp_path, scenario_payload) -> None:
    def failing_evaluator(_payload):
        raise RuntimeError("secret database password: hunter2")

    with client_for(tmp_path, failing_evaluator) as client:
        response = client.post("/api/scenarios", json=scenario_payload)

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "internal_error",
        "message": "An unexpected error occurred.",
    }
    assert "hunter2" not in response.text


def test_default_adapter_evaluates_with_the_real_financial_engine(
    tmp_path, scenario_payload
) -> None:
    with TestClient(create_app(db_path=tmp_path / "analysis.db")) as client:
        response = client.post("/api/scenarios", json=scenario_payload)

    assert response.status_code == 201
    result = response.json()["data"]["result"]
    assert result["executive_summary"]["scenario_name"] == "Inference modernization"
    assert result["comparison"]["disclaimer"]
