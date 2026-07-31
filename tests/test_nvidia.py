from collections.abc import Mapping

import pytest

from airi_civilization_vii.domain import JsonValue
from airi_civilization_vii.nvidia import NvidiaConfig, NvidiaPlanner, NvidiaPlannerError


def observation() -> dict[str, JsonValue]:
    return {
        "protocol_version": 1,
        "observation_id": "25:1",
        "game": {"is_multiplayer": False},
        "legal_actions": [
            {"id": "wait", "kind": "wait"},
            {"id": "next_action", "kind": "next_action"},
        ],
    }


def test_planner_forces_a_schema_constrained_tool_call() -> None:
    captured_body: dict[str, JsonValue] = {}

    def transport(
        url: str,
        headers: Mapping[str, str],
        body: dict[str, JsonValue],
        timeout_seconds: float,
    ) -> dict[str, JsonValue]:
        assert url == "https://integrate.api.nvidia.com/v1/chat/completions"
        assert headers["Authorization"] == "Bearer secret"
        assert timeout_seconds == 60
        captured_body.update(body)
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "choose_action",
                                    "arguments": (
                                        '{"action_id":"next_action","reason":"Turn is ready."}'
                                    ),
                                }
                            }
                        ]
                    }
                }
            ]
        }

    decision = NvidiaPlanner(NvidiaConfig(api_key="secret"), transport=transport).choose_action(
        observation()
    )

    assert decision.action_id == "next_action"
    assert decision.reason == "Turn is ready."
    tools = captured_body["tools"]
    assert isinstance(tools, list)
    tool = tools[0]
    assert isinstance(tool, dict)
    function = tool["function"]
    assert isinstance(function, dict)
    parameters = function["parameters"]
    assert isinstance(parameters, dict)
    properties = parameters["properties"]
    assert isinstance(properties, dict)
    action_id = properties["action_id"]
    assert isinstance(action_id, dict)
    assert action_id["enum"] == ["wait", "next_action"]


def test_planner_rejects_an_invented_action() -> None:
    def transport(
        _url: str,
        _headers: Mapping[str, str],
        _body: dict[str, JsonValue],
        _timeout_seconds: float,
    ) -> dict[str, JsonValue]:
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "choose_action",
                                    "arguments": '{"action_id":"reveal_map","reason":"Cheat."}',
                                }
                            }
                        ]
                    }
                }
            ]
        }

    with pytest.raises(NvidiaPlannerError, match="invented action"):
        NvidiaPlanner(NvidiaConfig(api_key="secret"), transport=transport).choose_action(
            observation()
        )
