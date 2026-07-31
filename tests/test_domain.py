from pathlib import Path

import pytest

from civ7_ai.domain import Action, ActionKind, BoundingBox, Detection, Observation


def test_bounding_box_center_uses_pixel_coordinates() -> None:
    box = BoundingBox(left=10, top=20, right=31, bottom=42)

    assert box.center == (20, 31)


def test_observation_resolves_only_its_detection_ids() -> None:
    detection = Detection(
        id="button.next_turn:0",
        label="button.next_turn",
        confidence=0.95,
        box=BoundingBox(left=10, top=20, right=30, bottom=40),
    )
    observation = Observation(
        sequence=0,
        captured_at="2026-07-30T00:00:00+00:00",
        width=100,
        height=100,
        image_path=Path("frame.jpg"),
        detections=(detection,),
    )

    assert observation.detection("button.next_turn:0") == detection
    assert observation.detection("button.next_turn:1") is None


def test_click_detection_requires_a_target() -> None:
    with pytest.raises(ValueError, match="requires target_id"):
        Action(kind=ActionKind.CLICK_DETECTION)
