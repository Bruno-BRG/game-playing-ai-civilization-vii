"""Dry-run and guarded Windows input executors."""

from __future__ import annotations

import ctypes
import sys
import time
from dataclasses import dataclass
from typing import Protocol

from .domain import Action, ActionKind, Observation


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """The resolved side effect recorded in the run trace."""

    executed: bool
    summary: str


class Executor(Protocol):
    """Resolve and optionally perform a validated action."""

    def execute(self, action: Action, observation: Observation) -> ExecutionResult: ...


def resolve_click_point(action: Action, observation: Observation) -> tuple[int, int]:
    """Resolve an action to capture-relative coordinates without performing input."""

    if action.kind is ActionKind.CLICK_POINT:
        if action.point is None:
            raise ValueError("click_point action has no point")
        x, y = action.point
    elif action.kind is ActionKind.CLICK_DETECTION:
        if action.target_id is None:
            raise ValueError("click_detection action has no target")
        detection = observation.detection(action.target_id)
        if detection is None:
            raise ValueError(f"Detection {action.target_id!r} does not belong to this observation")
        x, y = detection.box.center
    else:
        raise ValueError(f"Action {action.kind} does not resolve to a click")

    if not 0 <= x < observation.width or not 0 <= y < observation.height:
        raise ValueError("Click point is outside the captured game region")
    return (x, y)


class DryRunExecutor:
    """Resolve actions and describe them without injecting operating-system input."""

    def execute(self, action: Action, observation: Observation) -> ExecutionResult:
        if action.kind in {ActionKind.CLICK_DETECTION, ActionKind.CLICK_POINT}:
            point = resolve_click_point(action, observation)
            return ExecutionResult(False, f"would click capture-relative point {point}")
        if action.kind is ActionKind.PRESS_KEYS:
            return ExecutionResult(False, f"would press keys {action.keys}")
        if action.kind is ActionKind.WAIT:
            return ExecutionResult(False, f"would wait {action.duration_seconds:.2f}s")
        return ExecutionResult(False, "planner stopped the run")


class WindowsInputExecutor:
    """Inject input only while the expected game window is foreground.

    The foreground-title check is repeated immediately before every action. Losing
    focus therefore fails closed instead of sending a Civilization action to another
    application. Only a small key allowlist is accepted.
    """

    _ALLOWED_KEYS = frozenset(
        {
            "esc",
            "enter",
            "space",
            "tab",
            "shift",
            "ctrl",
            "alt",
            "left",
            "right",
            "up",
            "down",
        }
    )

    def __init__(self, *, window_title: str, capture_origin: tuple[int, int]) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Windows input execution is only available on Windows")
        try:
            import pydirectinput
        except ImportError as error:
            raise RuntimeError("Install Windows support with: uv sync --extra windows") from error

        self._input = pydirectinput
        self._window_title = window_title.casefold()
        self._capture_origin = capture_origin
        self._input.PAUSE = 0.05
        self._input.FAILSAFE = True

    def execute(self, action: Action, observation: Observation) -> ExecutionResult:
        if action.kind in {ActionKind.CLICK_DETECTION, ActionKind.CLICK_POINT}:
            self._require_game_foreground()
            relative_x, relative_y = resolve_click_point(action, observation)
            desktop_x = self._capture_origin[0] + relative_x
            desktop_y = self._capture_origin[1] + relative_y
            self._input.click(desktop_x, desktop_y)
            return ExecutionResult(True, f"clicked desktop point {(desktop_x, desktop_y)}")

        if action.kind is ActionKind.PRESS_KEYS:
            self._require_game_foreground()
            unsupported = set(action.keys) - self._ALLOWED_KEYS
            if unsupported:
                raise ValueError(f"Unsupported keys requested: {sorted(unsupported)}")
            if len(action.keys) == 1:
                self._input.press(action.keys[0])
            else:
                self._input.hotkey(*action.keys)
            return ExecutionResult(True, f"pressed keys {action.keys}")

        if action.kind is ActionKind.WAIT:
            time.sleep(action.duration_seconds)
            return ExecutionResult(True, f"waited {action.duration_seconds:.2f}s")
        return ExecutionResult(False, "planner stopped the run")

    def _require_game_foreground(self) -> None:
        user32 = ctypes.windll.user32
        handle = user32.GetForegroundWindow()
        title_length = user32.GetWindowTextLengthW(handle)
        buffer = ctypes.create_unicode_buffer(title_length + 1)
        user32.GetWindowTextW(handle, buffer, title_length + 1)
        if self._window_title not in buffer.value.casefold():
            raise RuntimeError(
                f"Refusing input because the foreground window is {buffer.value!r}, "
                f"not {self._window_title!r}"
            )
