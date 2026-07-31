import json
import urllib.error
import urllib.request
from pathlib import Path
from threading import Thread

import pytest

from airi_civilization_vii.bridge import BridgeController, BridgeServer
from airi_civilization_vii.domain import JsonValue
from airi_civilization_vii.nvidia import ModelDecision


class StubPlanner:
    def __init__(self, action_id: str = "next_action") -> None:
        self.action_id = action_id
        self.calls = 0

    def choose_action(self, observation: dict[str, JsonValue]) -> ModelDecision:
        self.calls += 1
        assert observation["protocol_version"] == 1
        return ModelDecision(self.action_id, "Selected by test planner.")


def observation(observation_id: str = "25:1", *, multiplayer: bool = False) -> dict[str, JsonValue]:
    return {
        "protocol_version": 1,
        "observation_id": observation_id,
        "captured_at": "2026-07-30T23:00:00Z",
        "game": {"turn": 25, "is_multiplayer": multiplayer},
        "legal_actions": [
            {"id": "wait", "kind": "wait"},
            {"id": "next_action", "kind": "next_action"},
        ],
    }


def test_execute_mode_returns_one_correlated_action(tmp_path: Path) -> None:
    planner = StubPlanner()
    trace_path = tmp_path / "trace.jsonl"
    controller = BridgeController(planner, execute=True, trace_path=trace_path)

    decision = controller.handle(observation())

    assert decision.observation_id == "25:1"
    assert decision.action_id == "next_action"
    assert decision.execute is True
    assert planner.calls == 1
    record = json.loads(trace_path.read_text(encoding="utf-8"))
    assert record["decision"]["action_id"] == "next_action"


def test_unchanged_state_is_not_executed_twice(tmp_path: Path) -> None:
    planner = StubPlanner()
    controller = BridgeController(planner, execute=True, trace_path=tmp_path / "trace.jsonl")

    first = controller.handle(observation("25:1"))
    duplicate = controller.handle(observation("25:2"))

    assert first.execute is True
    assert duplicate.action_id == "next_action"
    assert duplicate.execute is False
    assert duplicate.duplicate is True
    assert planner.calls == 1


def test_multiplayer_fails_closed_without_calling_model(tmp_path: Path) -> None:
    planner = StubPlanner()
    controller = BridgeController(planner, execute=True, trace_path=tmp_path / "trace.jsonl")

    decision = controller.handle(observation(multiplayer=True))

    assert decision.action_id == "wait"
    assert decision.execute is False
    assert planner.calls == 0


def test_loopback_server_authenticates_observations(tmp_path: Path) -> None:
    controller = BridgeController(
        StubPlanner(), execute=False, trace_path=tmp_path / "trace.jsonl"
    )
    server = BridgeServer(("127.0.0.1", 0), controller, "bridge-secret")
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(f"{base_url}/health") as response:
            assert json.loads(response.read())["status"] == "ok"

        encoded_observation = json.dumps(observation()).encode("utf-8")
        unauthorized_request = urllib.request.Request(
            f"{base_url}/v1/observations",
            data=encoded_observation,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as unauthorized:
            urllib.request.urlopen(unauthorized_request)
        assert unauthorized.value.code == 401

        authorized_request = urllib.request.Request(
            f"{base_url}/v1/observations",
            data=encoded_observation,
            headers={
                "Content-Type": "application/json",
                "X-AIRI-Bridge-Token": "bridge-secret",
            },
            method="POST",
        )
        with urllib.request.urlopen(authorized_request) as response:
            decision = json.loads(response.read())
        assert decision["action_id"] == "next_action"
        assert decision["execute"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
