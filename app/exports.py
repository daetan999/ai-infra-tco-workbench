"""Safe, dependency-local exports for stored financial analyses."""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Mapping, Sequence
from html import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .schemas import StoredAnalysis

FORMULA_PREFIXES = ("=", "+", "-", "@")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
NAVY = colors.HexColor("#10202F")
INK = colors.HexColor("#233544")
SLATE = colors.HexColor("#5E7080")
MIST = colors.HexColor("#EAF0F3")
TEAL = colors.HexColor("#178C80")
AMBER = colors.HexColor("#B7791F")


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
    """Render an executive-ready financial report with auditable appendices."""
    stream = io.BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=LETTER,
        rightMargin=0.62 * inch,
        leftMargin=0.62 * inch,
        topMargin=0.72 * inch,
        bottomMargin=0.62 * inch,
        title=_safe_text(analysis.input.name),
        author="Dae Tan",
        subject="Illustrative AI infrastructure TCO and ROI analysis",
    )
    document.build(
        list(_pdf_story(analysis)),
        onFirstPage=_page_chrome,
        onLaterPages=_page_chrome,
    )
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


def _pdf_story(analysis: StoredAnalysis) -> tuple[Any, ...]:
    styles = _pdf_styles()
    return (
        *_cover_story(analysis, styles),
        PageBreak(),
        *_comparison_story(analysis, styles),
        PageBreak(),
        *_assumptions_story(analysis, styles),
        PageBreak(),
        *_sensitivity_story(analysis, styles),
        PageBreak(),
        *_lineage_story(analysis, styles),
    )


def _cover_story(analysis: StoredAnalysis, styles: Mapping[str, ParagraphStyle]) -> tuple[Any, ...]:
    result = analysis.result
    summary = _mapping_value(result, "executive_summary")
    comparison = _mapping_value(result, "comparison")
    confidence = _mapping_value(result, "confidence")
    notice = (
        "Fictional demonstration. Illustrative assumptions are not live vendor quotes, "
        "and modeled ROI is not a guarantee."
    )
    return (
        Paragraph("ENTERPRISE AI INFRASTRUCTURE", styles["eyebrow"]),
        Paragraph(escape(analysis.input.name), styles["title"]),
        Paragraph(escape(analysis.input.description), styles["lead"]),
        _notice(notice, styles),
        Spacer(1, 18),
        Paragraph("Executive summary", styles["h1"]),
        _metric_table(summary, comparison, confidence, styles),
        Spacer(1, 16),
        Paragraph("Decision interpretation", styles["h2"]),
        Paragraph(
            escape(str(summary.get("recommendation", "Review the modeled case."))), styles["body"]
        ),
        Spacer(1, 8),
        Paragraph(escape(str(summary.get("disclaimer", notice))), styles["small"]),
        Spacer(1, 18),
        _report_metadata(analysis, styles),
    )


def _metric_table(
    summary: Mapping[str, Any],
    comparison: Mapping[str, Any],
    confidence: Mapping[str, Any],
    styles: Mapping[str, ParagraphStyle],
) -> Table:
    rows = (
        ("Current 5-year TCO", _money(summary.get("current_tco_5_year"))),
        ("Proposed 5-year TCO", _money(summary.get("proposed_tco_5_year"))),
        ("Modeled 5-year savings", _money(summary.get("savings_5_year"))),
        ("Modeled productivity value", _money(summary.get("productivity_value_5_year"))),
        ("Modeled net value", _money(summary.get("net_value_5_year"))),
        ("Modeled ROI", _percent(summary.get("roi_5_year_pct"))),
        ("Simple payback", _months(summary.get("payback_months"))),
        ("Assumption confidence", str(confidence.get("level", "Unavailable"))),
    )
    cells = [
        [Paragraph(label, styles["metric_label"]), Paragraph(value, styles["metric_value"])]
        for label, value in rows
    ]
    return _styled_table(cells, (3.15 * inch, 3.15 * inch), header=False)


def _comparison_story(
    analysis: StoredAnalysis, styles: Mapping[str, ParagraphStyle]
) -> tuple[Any, ...]:
    result = analysis.result
    current = _mapping_value(result, "current")
    proposed = _mapping_value(result, "proposed")
    comparison = _mapping_value(result, "comparison")
    rows = [["Year", "Current", "Proposed", "Delta"]]
    current_years = current.get("annual_costs", [])
    proposed_years = proposed.get("annual_costs", [])
    paired_years = zip(current_years, proposed_years, strict=True)
    for index, (current_year, proposed_year) in enumerate(paired_years, 1):
        current_total = _number_value(current_year, "total")
        proposed_total = _number_value(proposed_year, "total")
        rows.append(
            [
                f"Year {index}",
                _money(current_total),
                _money(proposed_total),
                _money(current_total - proposed_total),
            ]
        )
    return (
        Paragraph("Five-year comparison", styles["h1"]),
        Paragraph(
            "Annual costs include visible recurring components and one-time transition costs.",
            styles["body"],
        ),
        Spacer(1, 12),
        _styled_table(rows, (1.05 * inch, 1.75 * inch, 1.75 * inch, 1.75 * inch)),
        Spacer(1, 18),
        Paragraph("Business-case measures", styles["h2"]),
        _key_value_table(
            (
                ("Three-year TCO savings", _money(comparison.get("savings_3_year"))),
                ("Five-year TCO savings", _money(comparison.get("savings_5_year"))),
                ("Five-year modeled net value", _money(comparison.get("net_value_5_year"))),
                ("Five-year modeled ROI", _percent(comparison.get("roi_5_year_pct"))),
                (
                    "Break-even within five years",
                    _yes_no(comparison.get("break_even_within_5_years")),
                ),
            ),
            styles,
        ),
    )


def _assumptions_story(
    analysis: StoredAnalysis, styles: Mapping[str, ParagraphStyle]
) -> tuple[Any, ...]:
    payload = analysis.input.model_dump(mode="json")
    workload = _mapping_value(payload, "workload")
    current = _mapping_value(payload, "current_infrastructure")
    proposed = _mapping_value(payload, "proposed_infrastructure")
    sources = payload.get("assumption_sources", {})
    return (
        Paragraph("Scenario assumptions", styles["h1"]),
        Paragraph(
            "All assumptions remain visible and should be replaced with approved evidence "
            "before a decision.",
            styles["body"],
        ),
        Spacer(1, 10),
        Paragraph("Workload envelope", styles["h2"]),
        _mapping_table(
            workload,
            styles,
            (
                "workload_type",
                "model_size_billion",
                "training_runs_per_month",
                "monthly_requests_million",
                "average_demand_units",
                "peak_demand_units",
                "annual_growth_pct",
            ),
        ),
        Spacer(1, 16),
        Paragraph("Current and proposed states", styles["h2"]),
        _infrastructure_table(current, proposed),
        Spacer(1, 16),
        Paragraph("Transition and provenance", styles["h2"]),
        _key_value_table(
            (
                ("Migration cost", _money(payload.get("migration_cost"))),
                ("Implementation cost", _money(payload.get("implementation_cost"))),
                ("Contract duration", f"{payload.get('contract_years')} year(s)"),
                ("Sources", _sources_text(sources)),
            ),
            styles,
        ),
    )


def _sensitivity_story(
    analysis: StoredAnalysis, styles: Mapping[str, ParagraphStyle]
) -> tuple[Any, ...]:
    rows = [["Dimension", "Case", "Assumption", "Proposed TCO", "Net value", "ROI"]]
    for case in analysis.result.get("sensitivities", []):
        rows.append(
            [
                _title(case.get("dimension")),
                _title(case.get("case")),
                _display(case.get("assumption_value")),
                _money(case.get("proposed_tco_5_year")),
                _money(case.get("net_value_5_year")),
                _percent(case.get("roi_5_year_pct")),
            ]
        )
    return (
        Paragraph("Sensitivity analysis", styles["h1"]),
        Paragraph(
            "One-factor deterministic ranges challenge utilization, price, growth, and energy "
            "assumptions. They are scenarios, not forecasts or probability distributions.",
            styles["body"],
        ),
        Spacer(1, 12),
        _styled_table(
            rows, (1.0 * inch, 0.7 * inch, 0.9 * inch, 1.35 * inch, 1.35 * inch, 0.8 * inch)
        ),
        Spacer(1, 18),
        _notice(
            "Interpret sensitivity as decision risk. A favorable base case with a fragile "
            "downside still requires validation.",
            styles,
        ),
    )


def _lineage_story(
    analysis: StoredAnalysis, styles: Mapping[str, ParagraphStyle]
) -> tuple[Any, ...]:
    lineage = analysis.result.get("lineage", [])
    selected = [item for item in lineage if _include_lineage(str(item.get("output_path", "")))][:36]
    rows = [["Output", "Formula", "Derived value"]]
    rows.extend(_lineage_row(item, styles) for item in selected)
    return (
        Paragraph("Calculation lineage", styles["h1"]),
        Paragraph(
            "Selected material outputs are shown below. JSON and CSV exports retain the "
            "complete analysis snapshot and lineage collection.",
            styles["body"],
        ),
        Spacer(1, 12),
        _styled_table(rows, (2.2 * inch, 3.25 * inch, 0.85 * inch)),
    )


def _pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        **_pdf_text_styles(base),
        **_pdf_body_styles(base),
        **_pdf_metric_styles(base),
    }


def _pdf_text_styles(base: Mapping[str, ParagraphStyle]) -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=29,
            textColor=NAVY,
            spaceAfter=10,
            alignment=0,
        ),
        "lead": ParagraphStyle(
            "Lead", parent=base["BodyText"], fontSize=11, leading=16, textColor=INK
        ),
        "eyebrow": ParagraphStyle(
            "Eyebrow",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=TEAL,
            tracking=1.2,
            spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            textColor=NAVY,
            spaceAfter=8,
        ),
    }


def _pdf_body_styles(base: Mapping[str, ParagraphStyle]) -> dict[str, ParagraphStyle]:
    return {
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=INK,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontSize=9, leading=13, textColor=INK
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontSize=7.5, leading=11, textColor=SLATE
        ),
    }


def _pdf_metric_styles(base: Mapping[str, ParagraphStyle]) -> dict[str, ParagraphStyle]:
    return {
        "metric_label": ParagraphStyle(
            "Metric label", parent=base["BodyText"], fontSize=8, leading=10, textColor=SLATE
        ),
        "metric_value": ParagraphStyle(
            "Metric value",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=NAVY,
            alignment=2,
        ),
    }


def _styled_table(
    rows: Sequence[Sequence[Any]], widths: Sequence[float], header: bool = True
) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands: list[tuple[Any, ...]] = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D5DB")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), (colors.white, colors.HexColor("#F6F9FA"))),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        commands.extend(
            (
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            )
        )
    table.setStyle(TableStyle(commands))
    return table


def _key_value_table(
    pairs: Sequence[tuple[str, str]], styles: Mapping[str, ParagraphStyle]
) -> Table:
    cells = [
        [Paragraph(escape(label), styles["metric_label"]), Paragraph(escape(value), styles["body"])]
        for label, value in pairs
    ]
    return _styled_table(cells, (2.15 * inch, 4.15 * inch), header=False)


def _mapping_table(
    values: Mapping[str, Any],
    styles: Mapping[str, ParagraphStyle],
    fields: Sequence[str],
) -> Table:
    return _key_value_table(
        tuple((_title(field), _display(values.get(field))) for field in fields), styles
    )


def _infrastructure_table(current: Mapping[str, Any], proposed: Mapping[str, Any]) -> Table:
    fields = (
        "label",
        "infrastructure_type",
        "accelerator_count",
        "compute_hourly_cost",
        "productive_utilization_pct",
        "storage_tb",
        "network_egress_tb_month",
        "power_kw",
        "pue",
        "staff_fte",
        "operating_hours_year",
    )
    rows = [["Assumption", "Current", "Proposed"]]
    rows.extend(
        [_title(field), _display(current.get(field)), _display(proposed.get(field))]
        for field in fields
    )
    return _styled_table(rows, (2.2 * inch, 2.05 * inch, 2.05 * inch))


def _report_metadata(analysis: StoredAnalysis, styles: Mapping[str, ParagraphStyle]) -> Table:
    return _key_value_table(
        (
            ("Scenario version", str(analysis.version)),
            ("Analysis run", analysis.run_id),
            ("Generated", analysis.created_at.isoformat()),
            (
                "Calculation posture",
                "Deterministic Decimal engine; no model performs financial calculations",
            ),
        ),
        styles,
    )


def _notice(copy: str, styles: Mapping[str, ParagraphStyle]) -> Table:
    table = Table([[Paragraph(escape(copy), styles["small"])]], colWidths=(6.3 * inch,))
    table.setStyle(
        TableStyle(
            (
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7E7")),
                ("BOX", (0, 0), (-1, -1), 0.7, AMBER),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            )
        )
    )
    return table


def _page_chrome(document: canvas.Canvas, _doc: SimpleDocTemplate) -> None:
    document.saveState()
    document.setStrokeColor(MIST)
    document.line(45, LETTER[1] - 38, LETTER[0] - 45, LETTER[1] - 38)
    document.setFillColor(SLATE)
    document.setFont("Helvetica", 7.5)
    document.drawString(45, LETTER[1] - 30, "ENTERPRISE AI INFRASTRUCTURE TCO & ROI WORKBENCH")
    document.drawString(
        45, 25, "Illustrative decision support - validate assumptions before commitment"
    )
    document.drawRightString(LETTER[0] - 45, 25, f"Page {document.getPageNumber()}")
    document.restoreState()


def _include_lineage(path: str) -> bool:
    executive_fields = (
        "executive_summary.net_value_5_year",
        "executive_summary.roi_5_year_pct",
        "executive_summary.payback_months",
        "executive_summary.recommendation",
    )
    confidence_fields = (
        "confidence.score",
        "confidence.source_coverage_pct",
        "confidence.contract_coverage_pct",
        "confidence.level",
    )
    return (
        ".tco_" in path
        or path.startswith("comparison.")
        or path
        in (
            *executive_fields,
            *confidence_fields,
        )
    )


def _lineage_row(item: Mapping[str, Any], styles: Mapping[str, ParagraphStyle]) -> list[Paragraph]:
    return [
        Paragraph(escape(_safe_text(str(item.get("output_path", "")))), styles["small"]),
        Paragraph(escape(_safe_text(str(item.get("formula", "")))), styles["small"]),
        Paragraph(escape(_display(item.get("derived_value"))), styles["small"]),
    ]


def _mapping_value(values: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = values.get(key, {})
    return value if isinstance(value, Mapping) else {}


def _number_value(values: Any, key: str) -> float:
    return float(values.get(key, 0)) if isinstance(values, Mapping) else 0.0


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "Unavailable"


def _percent(value: Any) -> str:
    try:
        return f"{float(value):,.1f}%"
    except (TypeError, ValueError):
        return "Unavailable"


def _months(value: Any) -> str:
    try:
        return f"{float(value):,.1f} months"
    except (TypeError, ValueError):
        return "No modeled payback"


def _title(value: Any) -> str:
    return str(value or "Unavailable").replace("_", " ").strip().title()


def _yes_no(value: Any) -> str:
    return "Yes" if value is True else "No" if value is False else "Unavailable"


def _sources_text(sources: Any) -> str:
    if isinstance(sources, Mapping):
        return "; ".join(f"{key}: {value}" for key, value in sources.items())
    if isinstance(sources, Sequence) and not isinstance(sources, (str, bytes)):
        return "; ".join(str(item) for item in sources)
    return "No sources recorded"
