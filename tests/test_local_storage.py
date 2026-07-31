import json
import sqlite3
from pathlib import Path

from civ7_ai.bridge import BridgeController
from civ7_ai.domain import JsonValue
from civ7_ai.local_storage import DECISION_KEY, OBSERVATION_KEY, LocalStorageBridge
from civ7_ai.nvidia import ModelDecision


class StubPlanner:
    def choose_action(self, observation: dict[str, JsonValue]) -> ModelDecision:
        assert observation["observation_id"] == "25:1"
        return ModelDecision("next_action", "Selected by test planner.")


def test_local_storage_bridge_writes_correlated_decision(tmp_path: Path) -> None:
    storage_path = tmp_path / "LocalStorage.sqlite"
    with sqlite3.connect(storage_path) as connection:
        connection.execute(
            """CREATE TABLE "Values" (
                id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (id, key)
            ) WITHOUT ROWID"""
        )
        connection.execute(
            'INSERT INTO "Values" (id, key, value) VALUES (?, ?, ?)',
            (
                "file://gameui",
                OBSERVATION_KEY,
                json.dumps(
                    {
                        "protocol_version": 1,
                        "observation_id": "25:1",
                        "captured_at": "2026-07-31T03:00:00Z",
                        "game": {"turn": 25, "is_multiplayer": False},
                        "legal_actions": [
                            {"id": "wait", "kind": "wait"},
                            {"id": "next_action", "kind": "next_action"},
                        ],
                    }
                ),
            ),
        )

    controller = BridgeController(StubPlanner(), execute=True, trace_path=tmp_path / "trace.jsonl")
    bridge = LocalStorageBridge(controller, storage_path=storage_path)

    assert bridge.process_once() is True
    assert bridge.process_once() is False
    with sqlite3.connect(storage_path) as connection:
        row = connection.execute(
            'SELECT value FROM "Values" WHERE id = ? AND key = ?',
            ("file://gameui", DECISION_KEY),
        ).fetchone()
    assert row is not None
    decision = json.loads(row[0])
    assert decision["observation_id"] == "25:1"
    assert decision["action_id"] == "next_action"
    assert decision["execute"] is True
