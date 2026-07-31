import pytest

import civ7_ai.cli as cli
from civ7_ai.cli import main
from civ7_ai.domain import JsonValue
from civ7_ai.nvidia import ModelDecision, NvidiaConfig


def test_live_next_action_requires_explicit_gameplay_handoff() -> None:
    with pytest.raises(ValueError, match="requires --wait-for-gameplay"):
        main(["run", "--planner", "next-action", "--steps", "1", "--execute"])


def test_live_next_action_is_limited_to_one_supervised_step() -> None:
    with pytest.raises(ValueError, match="requires --steps 1"):
        main(
            [
                "run",
                "--planner",
                "next-action",
                "--wait-for-gameplay",
                "--steps",
                "2",
                "--execute",
            ]
        )


def test_bridge_requires_nvidia_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    with pytest.raises(ValueError, match="NVIDIA_API_KEY"):
        main(["bridge"])


def test_nvidia_test_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    with pytest.raises(ValueError, match="NVIDIA_API_KEY"):
        main(["nvidia-test"])


def test_strategic_profile_selects_thinking_enabled_omni(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received_configs: list[NvidiaConfig] = []

    class StubNvidiaPlanner:
        def __init__(self, config: NvidiaConfig) -> None:
            received_configs.append(config)

        def choose_action(self, _observation: dict[str, JsonValue]) -> ModelDecision:
            return ModelDecision(action_id="wait", reason="Profile verified.")

    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setattr(cli, "NvidiaPlanner", StubNvidiaPlanner)

    assert main(["nvidia-test", "--profile", "strategic"]) == 0
    assert len(received_configs) == 1
    assert received_configs[0].model == "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    assert received_configs[0].max_tokens == 65_536
    assert received_configs[0].enable_thinking is True
    assert received_configs[0].reasoning_budget == 16_384
