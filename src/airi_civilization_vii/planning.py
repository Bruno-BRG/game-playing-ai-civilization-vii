"""Planner boundary and a conservative baseline policy."""

from __future__ import annotations

from typing import Protocol

from .domain import Action, ActionKind, Observation


class Planner(Protocol):
    """Choose at most one auditable action from the latest observation."""

    def plan(self, observation: Observation) -> Action: ...


class NextTurnBaselinePlanner:
    """Click an unambiguous next-turn button and otherwise leave the game untouched.

    This policy validates the entire capture-to-action loop before an LLM planner is
    connected. Ambiguous duplicate detections fail closed instead of guessing.
    """

    def plan(self, observation: Observation) -> Action:
        candidates = [
            detection
            for detection in observation.detections
            if detection.label == "button.next_turn"
        ]
        if len(candidates) != 1:
            return Action(kind=ActionKind.STOP)
        return Action(kind=ActionKind.CLICK_DETECTION, target_id=candidates[0].id)
