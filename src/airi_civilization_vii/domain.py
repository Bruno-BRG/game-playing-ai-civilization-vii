"""Stable data contracts shared by capture, perception, planning, and execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """A pixel-space rectangle whose right and bottom edges are exclusive."""

    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(self) -> None:
        if self.left < 0 or self.top < 0:
            raise ValueError("Bounding boxes cannot start outside the image")
        if self.right <= self.left or self.bottom <= self.top:
            raise ValueError("Bounding boxes must have a positive area")

    @property
    def center(self) -> tuple[int, int]:
        """Return the integer pixel used for semantic click actions."""

        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)


@dataclass(frozen=True, slots=True)
class Detection:
    """One model detection with a run-local stable identifier."""

    id: str
    label: str
    confidence: float
    box: BoundingBox

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("Detection confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class Observation:
    """A persisted game frame and the semantic entities detected within it."""

    sequence: int
    captured_at: str
    width: int
    height: int
    image_path: Path
    detections: tuple[Detection, ...]

    def detection(self, detection_id: str) -> Detection | None:
        """Resolve an action target against this exact observation."""

        return next((item for item in self.detections if item.id == detection_id), None)

    def to_json(self) -> dict[str, JsonValue]:
        """Return a JSON-compatible snapshot for traces and model prompts."""

        return {
            "sequence": self.sequence,
            "captured_at": self.captured_at,
            "width": self.width,
            "height": self.height,
            "image_path": str(self.image_path),
            "detections": [
                {
                    "id": detection.id,
                    "label": detection.label,
                    "confidence": detection.confidence,
                    "box": {
                        "left": detection.box.left,
                        "top": detection.box.top,
                        "right": detection.box.right,
                        "bottom": detection.box.bottom,
                    },
                }
                for detection in self.detections
            ],
        }


class ActionKind(StrEnum):
    """The intentionally small set of side effects a planner may request."""

    CLICK_DETECTION = "click_detection"
    CLICK_POINT = "click_point"
    PRESS_KEYS = "press_keys"
    WAIT = "wait"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class Action:
    """A validated, auditable request produced by a planner.

    Coordinates are relative to the captured game region. Executors translate them
    to desktop coordinates only after verifying that Civilization VII is foreground.
    """

    kind: ActionKind
    target_id: str | None = None
    point: tuple[int, int] | None = None
    keys: tuple[str, ...] = ()
    duration_seconds: float = 0

    def __post_init__(self) -> None:
        if self.kind is ActionKind.CLICK_DETECTION and not self.target_id:
            raise ValueError("click_detection requires target_id")
        if self.kind is ActionKind.CLICK_POINT and self.point is None:
            raise ValueError("click_point requires point")
        if self.kind is ActionKind.PRESS_KEYS and not self.keys:
            raise ValueError("press_keys requires at least one key")
        if self.kind is ActionKind.WAIT and not 0 <= self.duration_seconds <= 10:
            raise ValueError("wait duration must be between 0 and 10 seconds")

    def to_json(self) -> dict[str, JsonValue]:
        """Return a JSON-compatible action for trace persistence."""

        return {
            "kind": self.kind,
            "target_id": self.target_id,
            "point": list(self.point) if self.point is not None else None,
            "keys": list(self.keys),
            "duration_seconds": self.duration_seconds,
        }
