"""SQLite repository integration tests."""

from app.repository import AnalysisRepository
from app.schemas import ScenarioInput


def test_repository_appends_versions_without_mutating_prior_runs(tmp_path, scenario_payload) -> None:
    repository = AnalysisRepository(tmp_path / "analysis.db")
    initial = ScenarioInput.model_validate(scenario_payload)
    created = repository.create(initial, {"total": 100.0})

    changed_payload = {**scenario_payload, "name": "Inference modernization v2"}
    updated = repository.create_version(
        created.scenario_id,
        ScenarioInput.model_validate(changed_payload),
        {"total": 80.0},
    )

    assert created.version == 1
    assert updated.version == 2
    assert repository.get_version(created.scenario_id, 1) == created
    assert repository.get_latest(created.scenario_id) == updated
    assert [run.version for run in repository.list_versions(created.scenario_id)] == [2, 1]


def test_repository_lists_latest_runs_and_soft_deletes_scenarios(tmp_path, scenario_payload) -> None:
    repository = AnalysisRepository(tmp_path / "nested" / "analysis.db")
    scenario = ScenarioInput.model_validate(scenario_payload)
    first = repository.create(scenario, {"total": 100.0})
    second = repository.create(scenario, {"total": 90.0})

    assert {item.scenario_id for item in repository.list_latest()} == {
        first.scenario_id,
        second.scenario_id,
    }
    assert repository.delete(first.scenario_id) is True
    assert repository.delete(first.scenario_id) is False
    assert repository.get_latest(first.scenario_id) is None
    assert repository.get_version(first.scenario_id, 1) is None
    assert [item.scenario_id for item in repository.list_latest()] == [second.scenario_id]


def test_repository_uses_stable_unique_identifiers(tmp_path, scenario_payload) -> None:
    repository = AnalysisRepository(tmp_path / "analysis.db")
    scenario = ScenarioInput.model_validate(scenario_payload)

    first = repository.create(scenario, {})
    second = repository.create(scenario, {})

    assert first.scenario_id != second.scenario_id
    assert first.run_id != second.run_id
