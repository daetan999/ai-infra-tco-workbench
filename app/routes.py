"""HTTP routes for local scenario CRUD, version history, and exports."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import Response

from .exports import export_csv, export_json, export_pdf
from .repository import AnalysisRepository
from .schemas import ScenarioInput, StoredAnalysis

Evaluator = Callable[[dict[str, Any]], Mapping[str, Any]]
LOGGER = logging.getLogger(__name__)


class ApiError(Exception):
    """Expected API failure rendered by the application error handler."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def success(data: Any) -> dict[str, Any]:
    """Create the workbench success envelope."""
    return {"success": True, "data": data, "error": None}


def serialize(analysis: StoredAnalysis) -> dict[str, Any]:
    """Convert a stored run into a JSON-compatible object."""
    return analysis.model_dump(mode="json")


def create_router(repository: AnalysisRepository, evaluator: Evaluator) -> APIRouter:
    """Build a router with explicit local dependencies."""
    router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])
    @router.get("")
    def list_scenarios() -> dict[str, Any]:
        return success([serialize(item) for item in repository.list_latest()])

    @router.post("", status_code=201)
    def create_scenario(scenario: ScenarioInput) -> dict[str, Any]:
        result = _evaluate(evaluator, scenario)
        return success(serialize(repository.create(scenario, result)))

    @router.get("/{scenario_id}")
    def get_scenario(scenario_id: UUID) -> dict[str, Any]:
        return success(serialize(_require(repository.get_latest(str(scenario_id)))))

    @router.put("/{scenario_id}")
    def update_scenario(scenario_id: UUID, scenario: ScenarioInput) -> dict[str, Any]:
        result = _evaluate(evaluator, scenario)
        analysis = repository.create_version(str(scenario_id), scenario, result)
        return success(serialize(_require(analysis)))

    @router.delete("/{scenario_id}")
    def delete_scenario(scenario_id: UUID) -> dict[str, Any]:
        if not repository.delete(str(scenario_id)):
            raise _not_found()
        return success({"scenario_id": str(scenario_id), "deleted": True})

    @router.get("/{scenario_id}/versions")
    def list_versions(scenario_id: UUID) -> dict[str, Any]:
        versions = repository.list_versions(str(scenario_id))
        if not versions:
            raise _not_found()
        return success([serialize(item) for item in versions])

    @router.get("/{scenario_id}/versions/{version}")
    def get_version(scenario_id: UUID, version: int) -> dict[str, Any]:
        analysis = repository.get_version(str(scenario_id), version)
        return success(serialize(_require(analysis)))

    @router.get("/{scenario_id}/exports/{export_format}")
    def download_export(
        scenario_id: UUID,
        export_format: Literal["json", "csv", "pdf"],
    ) -> Response:
        analysis = _require(repository.get_latest(str(scenario_id)))
        return _export_response(analysis, export_format)

    return router


def _evaluate(evaluator: Evaluator, scenario: ScenarioInput) -> dict[str, Any]:
    try:
        result = evaluator(scenario.model_dump(mode="json"))
        if not isinstance(result, Mapping):
            raise TypeError("The financial engine must return a mapping.")
        return dict(result)
    except Exception as error:
        LOGGER.exception("Financial scenario evaluation failed", exc_info=error)
        raise ApiError(500, "internal_error", "An unexpected error occurred.") from error


def _require(analysis: StoredAnalysis | None) -> StoredAnalysis:
    if analysis is None:
        raise _not_found()
    return analysis


def _not_found() -> ApiError:
    return ApiError(404, "not_found", "Scenario not found.")


def _export_response(
    analysis: StoredAnalysis,
    export_format: Literal["json", "csv", "pdf"],
) -> Response:
    content, media_type = _export_content(analysis, export_format)
    filename = f"tco-analysis-{analysis.scenario_id}-v{analysis.version}.{export_format}"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }
    return Response(content=content, media_type=media_type, headers=headers)


def _export_content(
    analysis: StoredAnalysis, export_format: Literal["json", "csv", "pdf"]
) -> tuple[str | bytes, str]:
    if export_format == "json":
        return export_json(analysis), "application/json"
    if export_format == "csv":
        return export_csv(analysis), "text/csv"
    return export_pdf(analysis), "application/pdf"
