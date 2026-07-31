"""Authenticated loopback bridge between the Civ VII add-on and NVIDIA Build."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Protocol

from .domain import JsonValue
from .nvidia import ModelDecision, NvidiaPlannerError

type JsonObject = dict[str, JsonValue]


class DecisionPlanner(Protocol):
    """Planning boundary used by the bridge controller."""

    def choose_action(self, observation: JsonObject) -> ModelDecision: ...


@dataclass(frozen=True, slots=True)
class BridgeDecision:
    """One correlated response returned to the in-game add-on."""

    observation_id: str
    action_id: str
    reason: str
    execute: bool
    duplicate: bool = False

    def to_json(self) -> JsonObject:
        """Return the versioned response envelope consumed by the add-on."""

        return {
            "protocol_version": 1,
            "observation_id": self.observation_id,
            "action_id": self.action_id,
            "reason": self.reason,
            "execute": self.execute,
            "duplicate": self.duplicate,
        }


class BridgeController:
    """Validate, deduplicate, plan, and trace add-on observations."""

    def __init__(self, planner: DecisionPlanner, *, execute: bool, trace_path: Path) -> None:
        self._planner = planner
        self._execute = execute
        self._trace_path = trace_path
        self._last_fingerprint: str | None = None
        self._last_decision: BridgeDecision | None = None

    def handle(self, observation: JsonObject) -> BridgeDecision:
        """Choose an action once per distinct state and always fail closed on multiplayer."""

        observation_id, legal_ids = _validate_observation(observation)
        game = observation["game"]
        if not isinstance(game, dict):
            raise ValueError("game must be an object")
        is_multiplayer = game.get("is_multiplayer")
        if is_multiplayer is not False:
            decision = BridgeDecision(
                observation_id=observation_id,
                action_id="wait",
                reason="Bridge execution is restricted to single-player games.",
                execute=False,
            )
            self._trace(observation, decision)
            return decision

        fingerprint = _state_fingerprint(observation)
        if fingerprint == self._last_fingerprint and self._last_decision is not None:
            decision = BridgeDecision(
                observation_id=observation_id,
                action_id=self._last_decision.action_id,
                reason="Unchanged state; previous decision will not be executed twice.",
                execute=False,
                duplicate=True,
            )
            self._trace(observation, decision)
            return decision

        model_decision = self._planner.choose_action(observation)
        if model_decision.action_id not in legal_ids:
            raise NvidiaPlannerError("Planner returned an action outside the validated legal set")
        decision = BridgeDecision(
            observation_id=observation_id,
            action_id=model_decision.action_id,
            reason=model_decision.reason,
            execute=self._execute and model_decision.action_id != "wait",
        )
        self._last_fingerprint = fingerprint
        self._last_decision = decision
        self._trace(observation, decision)
        return decision

    def _trace(self, observation: JsonObject, decision: BridgeDecision) -> None:
        self._trace_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"observation": observation, "decision": decision.to_json()}
        with self._trace_path.open("a", encoding="utf-8") as trace:
            trace.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _validate_observation(observation: JsonObject) -> tuple[str, set[str]]:
    if observation.get("protocol_version") != 1:
        raise ValueError("Unsupported protocol_version")
    observation_id = observation.get("observation_id")
    if not isinstance(observation_id, str) or not observation_id:
        raise ValueError("observation_id must be a non-empty string")
    if not isinstance(observation.get("game"), dict):
        raise ValueError("game must be an object")
    legal_actions = observation.get("legal_actions")
    if not isinstance(legal_actions, list) or not legal_actions:
        raise ValueError("legal_actions must be a non-empty array")
    legal_ids: set[str] = set()
    for action in legal_actions:
        if not isinstance(action, dict):
            raise ValueError("Every legal action must be an object")
        action_id = action.get("id")
        if not isinstance(action_id, str) or not action_id:
            raise ValueError("Every legal action must have a non-empty string id")
        if action_id in legal_ids:
            raise ValueError("legal action ids must be unique")
        legal_ids.add(action_id)
    if "wait" not in legal_ids:
        raise ValueError("legal_actions must include wait")
    return observation_id, legal_ids


def _state_fingerprint(observation: JsonObject) -> str:
    stable_observation = {
        key: value
        for key, value in observation.items()
        if key not in {"observation_id", "captured_at"}
    }
    canonical = json.dumps(stable_observation, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class BridgeServer(ThreadingHTTPServer):
    """Loopback-only HTTP server carrying the authenticated bridge protocol."""

    def __init__(
        self,
        address: tuple[str, int],
        controller: BridgeController,
        token: str,
    ) -> None:
        if address[0] not in {"127.0.0.1", "localhost"}:
            raise ValueError("Bridge server must bind to loopback")
        self.controller = controller
        self.token = token
        super().__init__(address, BridgeRequestHandler)


class BridgeRequestHandler(BaseHTTPRequestHandler):
    """HTTP adapter for health checks and observation requests."""

    server: BridgeServer

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path != "/health":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        self._send_json(HTTPStatus.OK, {"status": "ok", "protocol_version": 1})

    def do_POST(self) -> None:
        if self.path != "/v1/observations":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        token = self.headers.get("X-AIRI-Bridge-Token", "")
        if not hmac.compare_digest(token, self.server.token):
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_content_length"})
            return
        if length <= 0 or length > 2_000_000:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "invalid_body_size"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be an object")
            decision = self.server.controller.handle(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        except NvidiaPlannerError as error:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(error)})
            return
        mode = "EXECUTE" if decision.execute else "DRY-RUN"
        print(f"{mode}: {decision.action_id} — {decision.reason}")
        self._send_json(HTTPStatus.OK, decision.to_json())

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, status: HTTPStatus, payload: Mapping[str, JsonValue]) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-AIRI-Bridge-Token")
