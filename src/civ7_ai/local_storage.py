"""LocalStorage transport between the sandboxed Civ VII UI and the companion."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Event, Thread

from .bridge import BridgeController
from .domain import JsonValue
from .nvidia import NvidiaPlannerError

type JsonObject = dict[str, JsonValue]

OBSERVATION_KEY = "civ7-ai-bridge:observation"
DECISION_KEY = "civ7-ai-bridge:decision"


class LocalStorageBridge:
    """Poll Civ VII's local UI storage and return one validated decision per observation."""

    def __init__(
        self,
        controller: BridgeController,
        *,
        storage_path: Path,
        poll_interval_seconds: float = 0.25,
    ) -> None:
        self._controller = controller
        self._storage_path = storage_path
        self._poll_interval_seconds = poll_interval_seconds
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._last_observation: tuple[str, str] | None = None

    def start(self) -> None:
        """Start the background poller once while the HTTP health server remains foreground."""

        if self._thread is not None:
            raise RuntimeError("LocalStorage bridge is already running")
        self._thread = Thread(target=self._serve, name="civ7-ai-local-storage", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop polling and join the background worker before process shutdown."""

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def process_once(self) -> bool:
        """Process one unseen observation, returning whether a decision was written."""

        stored = self._read_observation()
        if stored is None or stored == self._last_observation:
            return False
        storage_id, raw_observation = stored
        try:
            observation = json.loads(raw_observation)
            if not isinstance(observation, dict):
                raise ValueError("LocalStorage observation must be an object")
            decision = self._controller.handle(observation)
        except (ValueError, json.JSONDecodeError, NvidiaPlannerError) as error:
            print(f"LocalStorage bridge ignored observation: {error}")
            self._last_observation = stored
            return False
        self._write_decision(storage_id, decision.to_json())
        self._last_observation = stored
        mode = "EXECUTE" if decision.execute else "DRY-RUN"
        print(f"{mode}: {decision.action_id} — {decision.reason}")
        return True

    def _serve(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.process_once()
            except sqlite3.Error as error:
                # Civ VII can briefly lock its storage while committing UI state; the next poll
                # safely retries rather than interrupting the active game session.
                print(f"LocalStorage bridge retrying after SQLite error: {error}")
            self._stop_event.wait(self._poll_interval_seconds)

    def _read_observation(self) -> tuple[str, str] | None:
        if not self._storage_path.is_file():
            return None
        with sqlite3.connect(self._storage_path, timeout=1) as connection:
            row = connection.execute(
                'SELECT id, value FROM "Values" WHERE key = ? ORDER BY id LIMIT 1',
                (OBSERVATION_KEY,),
            ).fetchone()
        if row is None:
            return None
        storage_id, value = row
        if not isinstance(storage_id, str) or not isinstance(value, str):
            raise ValueError("LocalStorage observation row has invalid types")
        return storage_id, value

    def _write_decision(self, storage_id: str, decision: JsonObject) -> None:
        encoded = json.dumps(decision, ensure_ascii=False, separators=(",", ":"))
        with sqlite3.connect(self._storage_path, timeout=1) as connection:
            connection.execute(
                """INSERT INTO "Values" (id, key, value) VALUES (?, ?, ?)
                ON CONFLICT(id, key) DO UPDATE SET value = excluded.value""",
                (storage_id, DECISION_KEY, encoded),
            )
