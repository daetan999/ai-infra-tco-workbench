"""Local SQLite persistence for immutable financial analysis runs."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .schemas import ScenarioInput, StoredAnalysis

SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    archived_at TEXT
);
CREATE TABLE IF NOT EXISTS analysis_runs (
    run_id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(scenario_id),
    version INTEGER NOT NULL CHECK(version > 0),
    payload_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(scenario_id, version)
);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_scenario_version
ON analysis_runs(scenario_id, version DESC);
"""


class AnalysisRepository:
    """Persist local scenarios while never updating an analysis run."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create tables and indexes for a new local database."""
        with self._connection() as connection:
            connection.executescript(SCHEMA)

    def create(self, scenario: ScenarioInput, result: dict[str, Any]) -> StoredAnalysis:
        """Create a scenario and its immutable first analysis run."""
        scenario_id = str(uuid4())
        created_at = datetime.now(UTC)
        run = self._new_run(scenario_id, 1, created_at, scenario, result)
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO scenarios(scenario_id, created_at) VALUES (?, ?)",
                (scenario_id, created_at.isoformat()),
            )
            self._insert_run(connection, run)
        return run

    def create_version(
        self,
        scenario_id: str,
        scenario: ScenarioInput,
        result: dict[str, Any],
    ) -> StoredAnalysis | None:
        """Append an evaluated version, returning None for missing scenarios."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            version = self._next_version(connection, scenario_id)
            if version is None:
                return None
            run = self._new_run(scenario_id, version, datetime.now(UTC), scenario, result)
            self._insert_run(connection, run)
        return run

    def get_latest(self, scenario_id: str) -> StoredAnalysis | None:
        """Return the latest active version of one scenario."""
        query = """
            SELECT r.* FROM analysis_runs r
            JOIN scenarios s ON s.scenario_id = r.scenario_id
            WHERE r.scenario_id = ? AND s.archived_at IS NULL
            ORDER BY r.version DESC LIMIT 1
        """
        return self._fetch_one(query, (scenario_id,))

    def get_version(self, scenario_id: str, version: int) -> StoredAnalysis | None:
        """Return one active historical version."""
        query = """
            SELECT r.* FROM analysis_runs r
            JOIN scenarios s ON s.scenario_id = r.scenario_id
            WHERE r.scenario_id = ? AND r.version = ? AND s.archived_at IS NULL
        """
        return self._fetch_one(query, (scenario_id, version))

    def list_versions(self, scenario_id: str) -> list[StoredAnalysis]:
        """Return all active versions, newest first."""
        query = """
            SELECT r.* FROM analysis_runs r
            JOIN scenarios s ON s.scenario_id = r.scenario_id
            WHERE r.scenario_id = ? AND s.archived_at IS NULL
            ORDER BY r.version DESC
        """
        return self._fetch_all(query, (scenario_id,))

    def list_latest(self) -> list[StoredAnalysis]:
        """Return the newest version of every active scenario."""
        query = """
            SELECT r.* FROM analysis_runs r
            JOIN scenarios s ON s.scenario_id = r.scenario_id
            WHERE s.archived_at IS NULL AND r.version = (
                SELECT MAX(latest.version) FROM analysis_runs latest
                WHERE latest.scenario_id = r.scenario_id
            )
            ORDER BY r.created_at DESC, r.scenario_id ASC
        """
        return self._fetch_all(query, ())

    def delete(self, scenario_id: str) -> bool:
        """Archive a scenario without deleting or altering any analysis run."""
        query = "UPDATE scenarios SET archived_at = ? WHERE scenario_id = ? AND archived_at IS NULL"
        with self._connection() as connection:
            cursor = connection.execute(query, (datetime.now(UTC).isoformat(), scenario_id))
        return cursor.rowcount == 1

    def _next_version(self, connection: sqlite3.Connection, scenario_id: str) -> int | None:
        row = connection.execute(
            "SELECT archived_at FROM scenarios WHERE scenario_id = ?", (scenario_id,)
        ).fetchone()
        if row is None or row["archived_at"] is not None:
            return None
        latest = connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM analysis_runs WHERE scenario_id = ?",
            (scenario_id,),
        ).fetchone()
        return int(latest["version"]) + 1

    def _insert_run(self, connection: sqlite3.Connection, run: StoredAnalysis) -> None:
        query = """
            INSERT INTO analysis_runs
                (run_id, scenario_id, version, payload_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        connection.execute(query, self._run_values(run))

    def _run_values(self, run: StoredAnalysis) -> tuple[str, str, int, str, str, str]:
        payload = run.input.model_dump(mode="json")
        return (
            run.run_id,
            run.scenario_id,
            run.version,
            json.dumps(payload, allow_nan=False, separators=(",", ":")),
            json.dumps(run.result, allow_nan=False, separators=(",", ":")),
            run.created_at.isoformat(),
        )

    def _new_run(
        self,
        scenario_id: str,
        version: int,
        created_at: datetime,
        scenario: ScenarioInput,
        result: dict[str, Any],
    ) -> StoredAnalysis:
        return StoredAnalysis(
            scenario_id=scenario_id,
            run_id=str(uuid4()),
            version=version,
            created_at=created_at,
            input=scenario,
            result=result,
        )

    def _fetch_one(self, query: str, parameters: tuple[Any, ...]) -> StoredAnalysis | None:
        with self._connection() as connection:
            row = connection.execute(query, parameters).fetchone()
        return self._decode(row) if row is not None else None

    def _fetch_all(self, query: str, parameters: tuple[Any, ...]) -> list[StoredAnalysis]:
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row) -> StoredAnalysis:
        return StoredAnalysis(
            scenario_id=row["scenario_id"],
            run_id=row["run_id"],
            version=row["version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            input=ScenarioInput.model_validate_json(row["payload_json"]),
            result=json.loads(row["result_json"]),
        )
