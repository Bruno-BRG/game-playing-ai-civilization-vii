from pathlib import Path

import pytest

from airi_civilization_vii.domain import Action, ActionKind, BoundingBox, Detection, Observation
from airi_civilization_vii.execution import DryRunExecutor, resolve_click_point


def make_observation() -> Observation:
    return Observation(
        sequence=4,
        captured_at="2026-07-30T00:00:00+00:00",
        width=200,
        height=100,
        image_path=Path("frame.jpg"),
        detections=(
            Detection(
                id="button.next_turn:0",
                label="button.next_turn",
                confidence=0.97,
                box=BoundingBox(left=150, top=60, right=190, bottom=90),
            ),
        ),
    )


def test_resolve_click_uses_detection_from_same_observation() -> None:
    point = resolve_click_point(
        Action(kind=ActionKind.CLICK_DETECTION, target_id="button.next_turn:0"),
        make_observation(),
    )

    assert point == (170, 75)


def test_resolve_click_rejects_stale_detection_id() -> None:
    with pytest.raises(ValueError, match="does not belong"):
        resolve_click_point(
            Action(kind=ActionKind.CLICK_DETECTION, target_id="button.next_turn:7"),
            make_observation(),
        )


def test_dry_run_never_reports_input_as_executed() -> None:
    result = DryRunExecutor().execute(
        Action(kind=ActionKind.CLICK_DETECTION, target_id="button.next_turn:0"),
        make_observation(),
    )

    assert result.executed is False
    assert result.summary == "would click capture-relative point (170, 75)"
