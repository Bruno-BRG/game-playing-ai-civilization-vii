"""Constrained NVIDIA Build planning for structured Civilization VII observations."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .domain import JsonValue

type JsonObject = dict[str, JsonValue]
type JsonTransport = Callable[[str, Mapping[str, str], JsonObject, float], JsonObject]


class NvidiaPlannerError(RuntimeError):
    """Raised when NVIDIA Build does not return one valid constrained action."""


@dataclass(frozen=True, slots=True)
class NvidiaConfig:
    """Connection and reasoning settings for the NVIDIA Build Nemotron model."""

    api_key: str
    model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    base_url: str = "https://integrate.api.nvidia.com/v1"
    timeout_seconds: float = 30
    temperature: float = 0.2
    top_p: float = 0.95
    max_tokens: int = 1024
    enable_thinking: bool = False
    reasoning_budget: int = 0

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("NVIDIA_API_KEY is required")
        if not self.model.strip():
            raise ValueError("NVIDIA model cannot be empty")
        if not self.base_url.startswith("https://"):
            raise ValueError("NVIDIA base URL must use HTTPS")
        if self.timeout_seconds <= 0:
            raise ValueError("NVIDIA request timeout must be positive")
        if not 0 <= self.temperature <= 1:
            raise ValueError("NVIDIA temperature must be between 0 and 1")
        if not 0 < self.top_p <= 1:
            raise ValueError("NVIDIA top_p must be greater than 0 and at most 1")
        if self.max_tokens <= 0:
            raise ValueError("NVIDIA max_tokens must be positive")
        if not 0 <= self.reasoning_budget <= self.max_tokens:
            raise ValueError("NVIDIA reasoning_budget must be between 0 and max_tokens")
        if self.reasoning_budget and not self.enable_thinking:
            raise ValueError("NVIDIA reasoning_budget requires enable_thinking")


@dataclass(frozen=True, slots=True)
class ModelDecision:
    """A model choice already resolved against the offered legal action identifiers."""

    action_id: str
    reason: str


def post_json(
    url: str,
    headers: Mapping[str, str],
    body: JsonObject,
    timeout_seconds: float,
) -> JsonObject:
    """POST JSON through the standard library so the companion has no HTTP SDK dependency."""

    request = urllib.request.Request(
        url,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers=dict(headers),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")[:1000]
        raise NvidiaPlannerError(f"NVIDIA Build returned HTTP {error.code}: {details}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise NvidiaPlannerError(f"NVIDIA Build request failed: {error}") from error
    if not isinstance(payload, dict):
        raise NvidiaPlannerError("NVIDIA Build returned a non-object response")
    return payload


class NvidiaPlanner:
    """Ask NVIDIA Build to select exactly one action from the add-on's legal action set."""

    def __init__(self, config: NvidiaConfig, *, transport: JsonTransport = post_json) -> None:
        self._config = config
        self._transport = transport

    def choose_action(self, observation: JsonObject) -> ModelDecision:
        """Return a forced tool call and reject invented or malformed action identifiers."""

        legal_actions_value = observation.get("legal_actions")
        if not isinstance(legal_actions_value, list):
            raise NvidiaPlannerError("Observation does not contain legal_actions")

        legal_ids: list[str] = []
        for action in legal_actions_value:
            if not isinstance(action, dict):
                raise NvidiaPlannerError("Every legal action must be an object")
            action_id = action.get("id")
            if not isinstance(action_id, str) or not action_id:
                raise NvidiaPlannerError("Every legal action must have a non-empty string id")
            legal_ids.append(action_id)
        if not legal_ids:
            raise NvidiaPlannerError("Observation offered no legal actions")
        if len(set(legal_ids)) != len(legal_ids):
            raise NvidiaPlannerError("Observation contains duplicate legal action ids")
        legal_id_values: list[JsonValue] = []
        legal_id_values.extend(legal_ids)

        chat_template_kwargs: JsonObject = {
            "enable_thinking": self._config.enable_thinking,
        }
        if self._config.enable_thinking:
            # Reasoning-enabled Nemotron models need a final content segment so the hosted
            # parser preserves a tool call emitted after the thinking trace.
            chat_template_kwargs["force_nonempty_content"] = True

        request_body: JsonObject = {
            "model": self._config.model,
            "temperature": self._config.temperature,
            "top_p": self._config.top_p,
            "max_tokens": self._config.max_tokens,
            "chat_template_kwargs": chat_template_kwargs,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a Civilization VII strategy controller in a local single-player "
                        "match. Choose exactly one offered legal action. Prefer resolving required "
                        "choices before ending a turn. Never claim access to hidden state."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(observation, ensure_ascii=False, separators=(",", ":")),
                },
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "choose_action",
                        "description": "Choose one action id from the current legal action list.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "action_id": {"type": "string", "enum": legal_id_values},
                                "reason": {"type": "string"},
                            },
                            "required": ["action_id", "reason"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "choose_action"}},
        }
        if self._config.reasoning_budget:
            request_body["reasoning_budget"] = self._config.reasoning_budget
        response = self._transport(
            f"{self._config.base_url.rstrip('/')}/chat/completions",
            {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            request_body,
            self._config.timeout_seconds,
        )
        decision = self._parse_response(response)
        if decision.action_id not in legal_ids:
            raise NvidiaPlannerError(
                f"NVIDIA Build invented action id {decision.action_id!r}; refusing it"
            )
        return decision

    @staticmethod
    def _parse_response(response: JsonObject) -> ModelDecision:
        try:
            choices = response["choices"]
            if not isinstance(choices, list) or not choices:
                raise TypeError
            choice = choices[0]
            if not isinstance(choice, dict):
                raise TypeError
            message = choice["message"]
            if not isinstance(message, dict):
                raise TypeError
            tool_calls = message["tool_calls"]
            if not isinstance(tool_calls, list) or len(tool_calls) != 1:
                raise TypeError
            tool_call = tool_calls[0]
            if not isinstance(tool_call, dict):
                raise TypeError
            function = tool_call["function"]
            if not isinstance(function, dict) or function.get("name") != "choose_action":
                raise TypeError
            arguments_value = function["arguments"]
            if isinstance(arguments_value, str):
                arguments = json.loads(arguments_value)
            else:
                arguments = arguments_value
            if not isinstance(arguments, dict):
                raise TypeError
            action_id = arguments["action_id"]
            reason = arguments["reason"]
            if not isinstance(action_id, str) or not isinstance(reason, str):
                raise TypeError
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise NvidiaPlannerError(
                "NVIDIA Build did not return one valid choose_action tool call"
            ) from error
        return ModelDecision(action_id=action_id, reason=reason)
