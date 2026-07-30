from pathlib import Path

from airi_civilization_vii.domain import ActionKind, BoundingBox, Detection, Observation
from airi_civilization_vii.planning import NextTurnBaselinePlanner


def observation_with(*detections: Detection) -> Observation:
    return Observation(
        sequence=0,
        captured_at="2026-07-30T00:00:00+00:00",
        width=1920,
        height=1080,
        image_path=Path("frame.jpg"),
        detections=detections,
    )


def next_turn_detection(identifier: str) -> Detection:
    return Detection(
        id=identifier,
        label="button.next_turn",
        confidence=0.9,
        box=BoundingBox(left=1700, top=900, right=1800, bottom=1000),
    )


def test_baseline_clicks_one_unambiguous_next_turn_button() -> None:
    action = NextTurnBaselinePlanner().plan(observation_with(next_turn_detection("next:0")))

    assert action.kind is ActionKind.CLICK_DETECTION
    assert action.target_id == "next:0"


def test_baseline_stops_when_next_turn_is_missing() -> None:
    action = NextTurnBaselinePlanner().plan(observation_with())

    assert action.kind is ActionKind.STOP


def test_baseline_stops_when_next_turn_is_ambiguous() -> None:
    action = NextTurnBaselinePlanner().plan(
        observation_with(next_turn_detection("next:0"), next_turn_detection("next:1"))
    )

    assert action.kind is ActionKind.STOP
