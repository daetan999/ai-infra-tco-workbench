"""FastAPI application factory for the local-only TCO workbench."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .demo_data import seed_demo_data
from .repository import AnalysisRepository
from .routes import ApiError, create_router

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).parents[1]


def _default_evaluator(payload: dict[str, Any]) -> Mapping[str, Any]:
    from .engine import evaluate_financial_scenario

    return evaluate_financial_scenario(payload)


def _enabled(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def create_app(
    db_path: str | Path | None = None,
    evaluator: Callable[[dict[str, Any]], Mapping[str, Any]] | None = None,
) -> FastAPI:
    """Create an app with injectable local persistence and deterministic evaluation."""
    database_path = Path(db_path or os.getenv("TCO_WORKBENCH_DB", "data/tco-workbench.db"))
    repository = AnalysisRepository(database_path)
    active_evaluator = evaluator or _default_evaluator

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if _enabled(os.getenv("SEED_DEMO_DATA")):
            seed_demo_data(repository, active_evaluator)
        yield

    application = FastAPI(
        title="AI Infrastructure TCO Workbench",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.repository = repository

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(create_router(repository, active_evaluator))
    _install_error_handlers(application)
    _install_frontend(application)
    return application


def _install_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApiError)
    async def api_error_handler(_request: Request, error: ApiError) -> JSONResponse:
        return _error_response(error.status_code, error.code, error.message)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        del error
        return _error_response(422, "validation_error", "The request payload is invalid.")

    @application.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, error: Exception) -> JSONResponse:
        LOGGER.exception("Unhandled workbench error", exc_info=error)
        return _error_response(500, "internal_error", "An unexpected error occurred.")


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    content = {
        "success": False,
        "data": None,
        "error": {"code": code, "message": message},
    }
    return JSONResponse(status_code=status_code, content=content)


def _install_frontend(application: FastAPI) -> None:
    static_path = ROOT / "static"
    template_path = ROOT / "templates"
    if static_path.is_dir():
        application.mount("/static", StaticFiles(directory=static_path), name="static")
    if not template_path.is_dir():
        return
    templates = Jinja2Templates(directory=template_path)

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def workspace(request: Request):
        return templates.TemplateResponse(request=request, name="index.html")


app = create_app()
