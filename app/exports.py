"""Safe, dependency-local exports for stored financial analyses."""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from .schemas import StoredAnalysis

FORMULA_PREFIXES = ("=", "+", "-", "@")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def export_json(analysis: StoredAnalysis) -> str:
    """Serialize a complete analysis as deterministic, valid JSON."""
    return json.dumps(analysis.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)


def export_csv(analysis: StoredAnalysis) -> str:
    """Flatten a complete analysis into a formula-injection-safe CSV."""
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("field", "value"))
    for path, value in _flatten(analysis.model_dump(mode="json")):
        writer.writerow((_csv_cell(path), _csv_cell(_display(value))))
    return stream.getvalue()


def export_pdf(analysis: StoredAnalysis) -> bytes:
    """Render a compact, actual PDF containing inputs and results."""
    stream = io.BytesIO()
    document = canvas.Canvas(stream, pagesize=LETTER, pageCompression=1)
    document.setTitle(_safe_text(analysis.input.name))
    y = _pdf_heading(document, analysis)
    for path, value in _flatten(analysis.model_dump(mode="json")):
        y = _pdf_row(document, f"{path}: {_display(value)}", y)
    document.save()
    return stream.getvalue()


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, Mapping):
        rows: list[tuple[str, Any]] = []
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten(value[key], path))
        return rows
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        rows = []
        for index, item in enumerate(value):
            rows.extend(_flatten(item, f"{prefix}.{index}"))
        return rows
    return [(prefix, value)]


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _csv_cell(value: str) -> str:
    cleaned = _safe_text(value)
    return f"'{cleaned}" if cleaned.startswith(FORMULA_PREFIXES) else cleaned


def _safe_text(value: str) -> str:
    return CONTROL_CHARACTERS.sub("", value)


def _pdf_heading(document: canvas.Canvas, analysis: StoredAnalysis) -> float:
    document.setFont("Helvetica-Bold", 16)
    document.drawString(54, 750, "AI Infrastructure TCO Analysis")
    document.setFont("Helvetica", 10)
    document.drawString(54, 732, _safe_text(analysis.input.name)[:90])
    document.drawString(54, 716, f"Version {analysis.version} · {analysis.created_at.isoformat()}")
    return 692


def _pdf_row(document: canvas.Canvas, text: str, y: float) -> float:
    safe = _safe_text(text)
    for chunk in (safe[index : index + 92] for index in range(0, len(safe), 92)):
        if y < 54:
            document.showPage()
            document.setFont("Helvetica", 8)
            y = 750
        document.setFont("Helvetica", 8)
        document.drawString(54, y, chunk)
        y -= 11
    return y

