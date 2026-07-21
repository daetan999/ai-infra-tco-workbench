"""Fictional demo scenario tests."""

from app.demo_data import demo_scenarios, seed_demo_data
from app.repository import AnalysisRepository


def test_demo_catalog_contains_exactly_three_named_fictional_scenarios() -> None:
    demos = demo_scenarios()

    assert len(demos) == 3
    assert all(demo.fictional for demo in demos)
    assert [demo.name for demo in demos] == [
        "CPU-to-GPU inference modernization",
        "Cloud GPU vs owned infrastructure",
        "Shared serving utilization",
    ]


def test_demo_seed_is_idempotent(tmp_path, evaluator) -> None:
    repository = AnalysisRepository(tmp_path / "analysis.db")

    assert seed_demo_data(repository, evaluator) == 3
    assert seed_demo_data(repository, evaluator) == 0
    assert len(repository.list_latest()) == 3
