"""Fictional demo scenario tests."""

from app.demo_data import demo_scenarios, seed_demo_data
from app.repository import AnalysisRepository


def test_demo_catalog_contains_exactly_three_named_fictional_scenarios() -> None:
    demos = demo_scenarios()

    assert len(demos) == 3
    assert all(demo.fictional for demo in demos)
    assert [demo.name for demo in demos] == [
        "Fictional Northstar Private RAG TCO",
        "Cloud GPU vs owned infrastructure",
        "Shared serving utilization",
    ]
    assert len({demo.model_dump_json() for demo in demos}) == 3
    shared = demos[2]
    assert shared.current_infrastructure.productive_utilization_pct == 35.0
    assert shared.proposed_infrastructure.productive_utilization_pct == 72.0

    northstar = demos[0]
    assert northstar.workload.model_size_billion == 70.0
    assert northstar.workload.training_runs_per_month == 0
    assert northstar.workload.monthly_requests_million == 60.0
    assert northstar.workload.annual_growth_pct == 35.0
    assert northstar.current_infrastructure.storage_tb == 36.0
    assert northstar.proposed_infrastructure.storage_tb == 36.0
    assert northstar.assumption_sources[
        "workload.monthly_requests_million"
    ] == "Fictional Northstar peak-demand normalization"
    assert northstar.assumption_sources[
        "current_infrastructure.storage_tb"
    ] == "Northstar storage plan: 18 TB governed data plus working capacity"


def test_demo_seed_is_idempotent(tmp_path, evaluator) -> None:
    repository = AnalysisRepository(tmp_path / "analysis.db")

    assert seed_demo_data(repository, evaluator) == 3
    assert seed_demo_data(repository, evaluator) == 0
    assert len(repository.list_latest()) == 3
