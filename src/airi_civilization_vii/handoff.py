"""Explicit operator-to-agent gameplay handoff."""

from __future__ import annotations

import ctypes
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from .capture import WindowTarget, require_window_foreground

F8_VIRTUAL_KEY = 0x77


class HandoffState(StrEnum):
    """Operator-visible lifecycle before autonomous observation begins."""

    PREPARING = "preparing"
    ARMED = "armed"
    ACTIVE = "active"


@dataclass(frozen=True, slots=True)
class HandoffResult:
    """Audit record proving how and where the operator activated a run."""

    activated_at: str
    key: str
    window_handle: int
    window_title: str

    def to_json(self) -> dict[str, object]:
        """Return a JSON-compatible handoff record."""

        return {
            "state": HandoffState.ACTIVE.value,
            "activated_at": self.activated_at,
            "method": "global-hotkey",
            "key": self.key,
            "window_handle": self.window_handle,
            "window_title": self.window_title,
        }


def wait_for_handoff(
    target: WindowTarget,
    *,
    timeout_seconds: float = 900,
    stable_seconds: float = 0.75,
    poll_interval_seconds: float = 0.05,
    on_state_change: Callable[[HandoffState], None] | None = None,
    get_foreground_handle: Callable[[], int] | None = None,
    is_key_down: Callable[[int], bool] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> HandoffResult:
    """Wait for a fresh F8 press while the exact game window owns foreground focus.

    A key held before the wait starts, or pressed while another window is focused, is
    consumed and must be released before it can activate the run. After the valid edge,
    the game must retain foreground focus for ``stable_seconds``. No pixels are captured
    and no input is injected by this boundary.
    """

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if stable_seconds < 0:
        raise ValueError("stable_seconds cannot be negative")
    if not 0 < poll_interval_seconds <= 1:
        raise ValueError("poll_interval_seconds must be between 0 and 1")

    foreground_handle = get_foreground_handle or _get_foreground_handle
    key_down = is_key_down or _is_key_down
    started_at = monotonic()
    key_was_released = False
    current_state: HandoffState | None = None

    def publish(state: HandoffState) -> None:
        nonlocal current_state
        if state is current_state:
            return
        current_state = state
        if on_state_change is not None:
            on_state_change(state)

    while True:
        now = monotonic()
        _raise_if_timed_out(started_at, now, timeout_seconds)
        game_is_foreground = foreground_handle() == target.handle
        f8_is_down = key_down(F8_VIRTUAL_KEY)

        if not f8_is_down:
            key_was_released = True
            publish(HandoffState.ARMED if game_is_foreground else HandoffState.PREPARING)
            sleep(poll_interval_seconds)
            continue

        if not key_was_released or not game_is_foreground:
            # A press from another window never becomes valid merely by Alt-Tabbing.
            key_was_released = False
            publish(HandoffState.PREPARING)
            sleep(poll_interval_seconds)
            continue

        stable_until = now + stable_seconds
        while monotonic() < stable_until:
            current_time = monotonic()
            _raise_if_timed_out(started_at, current_time, timeout_seconds)
            try:
                require_window_foreground(
                    target_handle=target.handle,
                    foreground_handle=foreground_handle(),
                    title=target.title,
                )
            except RuntimeError:
                # Consume this F8 edge; the operator must release and deliberately retry.
                key_was_released = False
                publish(HandoffState.PREPARING)
                break
            sleep(min(poll_interval_seconds, stable_until - current_time))
        else:
            publish(HandoffState.ACTIVE)
            return HandoffResult(
                activated_at=datetime.now(UTC).isoformat(),
                key="F8",
                window_handle=target.handle,
                window_title=target.title,
            )


def _raise_if_timed_out(started_at: float, now: float, timeout_seconds: float) -> None:
    if now - started_at >= timeout_seconds:
        raise TimeoutError("Timed out waiting for an F8 handoff from Civilization VII")


def _get_foreground_handle() -> int:
    if sys.platform != "win32":
        raise RuntimeError("Global gameplay handoff is only available on Windows")
    return int(ctypes.windll.user32.GetForegroundWindow())


def _is_key_down(virtual_key: int) -> bool:
    if sys.platform != "win32":
        raise RuntimeError("Global gameplay handoff is only available on Windows")
    # GetAsyncKeyState's high bit represents the physical state at polling time.
    return bool(ctypes.windll.user32.GetAsyncKeyState(virtual_key) & 0x8000)
