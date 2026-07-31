from collections.abc import Mapping

import pytest

from civ7_ai.domain import JsonValue
from civ7_ai.nvidia import NvidiaConfig, NvidiaPlanner, NvidiaPlannerError


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
        assert timeout_seconds == 30
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
    assert captured_body["model"] == "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    assert captured_body["temperature"] == 0.2
    assert captured_body["top_p"] == 0.95
    assert captured_body["max_tokens"] == 1024
    assert "reasoning_budget" not in captured_body
    assert captured_body["tool_choice"] == {
        "type": "function",
        "function": {"name": "choose_action"},
    }
    chat_template_kwargs = captured_body["chat_template_kwargs"]
    assert isinstance(chat_template_kwargs, dict)
    assert chat_template_kwargs == {"enable_thinking": False}
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


def test_reasoning_budget_cannot_exceed_generation_budget() -> None:
    with pytest.raises(ValueError, match="reasoning_budget"):
        NvidiaConfig(
            api_key="secret",
            max_tokens=100,
            enable_thinking=True,
            reasoning_budget=101,
        )


def test_reasoning_budget_requires_thinking() -> None:
    with pytest.raises(ValueError, match="requires enable_thinking"):
        NvidiaConfig(api_key="secret", reasoning_budget=100)


def test_strategic_config_enables_omni_reasoning_fields() -> None:
    captured_body: dict[str, JsonValue] = {}

    def transport(
        _url: str,
        _headers: Mapping[str, str],
        body: dict[str, JsonValue],
        _timeout_seconds: float,
    ) -> dict[str, JsonValue]:
        captured_body.update(body)
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "choose_action",
                                    "arguments": '{"action_id":"wait","reason":"Hold."}',
                                }
                            }
                        ]
                    }
                }
            ]
        }

    planner = NvidiaPlanner(
        NvidiaConfig(
            api_key="secret",
            model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
            max_tokens=65_536,
            enable_thinking=True,
            reasoning_budget=16_384,
        ),
        transport=transport,
    )

    decision = planner.choose_action(
        {
            "protocol_version": 1,
            "observation_id": "strategic-test",
            "game": {"is_multiplayer": False},
            "legal_actions": [{"id": "wait", "kind": "wait"}],
        }
    )

    assert decision.action_id == "wait"
    assert captured_body["reasoning_budget"] == 16_384
    assert captured_body["chat_template_kwargs"] == {
        "enable_thinking": True,
        "force_nonempty_content": True,
    }
