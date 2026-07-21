"""Generate the committed fictional TCO business-case report."""

from pathlib import Path
from tempfile import TemporaryDirectory

from app.demo_data import demo_scenarios
from app.engine import evaluate_financial_scenario
from app.exports import export_pdf
from app.repository import AnalysisRepository

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "docs" / "examples" / "fictional-cpu-to-gpu-business-case.pdf"


def generate() -> Path:
    """Build the sample from the same deterministic engine and exporter as the app."""
    scenario = demo_scenarios()[0]
    payload = scenario.model_dump(mode="json")
    result = evaluate_financial_scenario(payload)
    with TemporaryDirectory(prefix="tco-report-") as directory:
        repository = AnalysisRepository(Path(directory) / "sample.db")
        analysis = repository.create(scenario, result)
        report = export_pdf(analysis)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(report)
    return OUTPUT


if __name__ == "__main__":
    print(generate().relative_to(ROOT))
