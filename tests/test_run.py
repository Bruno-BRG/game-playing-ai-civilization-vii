import json
from pathlib import Path

import pytest
from PIL import Image

from civ7_ai.capture import ImageCapture
from civ7_ai.domain import Action, BoundingBox, Detection, Observation
from civ7_ai.execution import DryRunExecutor, ExecutionResult
from civ7_ai.planning import NextTurnBaselinePlanner
from civ7_ai.run import GameRun


class FixedDetector:
    def detect(self, image: Image.Image) -> tuple[Detection, ...]:
        assert image.size == (320, 180)
        return (
            Detection(
                id="button.next_turn:0",
                label="button.next_turn",
                confidence=0.99,
                box=BoundingBox(left=250, top=120, right=310, bottom=170),
            ),
        )


class RejectingExecutor:
    def execute(self, action: Action, observation: Observation) -> ExecutionResult:
        del action, observation
        raise RuntimeError("game lost foreground focus")


def test_game_run_persists_correlated_frames_and_trace(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixture.jpg"
    Image.new("RGB", (320, 180), color=(24, 32, 40)).save(fixture_path)
    run_directory = tmp_path / "run"

    observed_steps = GameRun(
        capture=ImageCapture(fixture_path),
        detector=FixedDetector(),
        planner=NextTurnBaselinePlanner(),
        executor=DryRunExecutor(),
        run_directory=run_directory,
    ).execute(max_steps=2)

    assert observed_steps == 2
    assert (run_directory / "frames/frame-0000.jpg").exists()
    assert (run_directory / "frames/frame-0001.jpg").exists()

    trace_lines = (run_directory / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(trace_lines) == 2
    first_record = json.loads(trace_lines[0])
    assert first_record["observation"]["sequence"] == 0
    assert first_record["action"]["target_id"] == "button.next_turn:0"
    assert first_record["execution"]["executed"] is False


def test_game_run_traces_executor_rejection_before_raising(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixture.jpg"
    Image.new("RGB", (320, 180), color=(24, 32, 40)).save(fixture_path)
    run_directory = tmp_path / "rejected-run"

    game_run = GameRun(
        capture=ImageCapture(fixture_path),
        detector=FixedDetector(),
        planner=NextTurnBaselinePlanner(),
        executor=RejectingExecutor(),
        run_directory=run_directory,
    )

    with pytest.raises(RuntimeError, match="lost foreground"):
        game_run.execute(max_steps=1)

    trace_record = json.loads((run_directory / "trace.jsonl").read_text(encoding="utf-8").strip())
    assert trace_record["execution"]["executed"] is False
    assert trace_record["execution"]["summary"] == "rejected: game lost foreground focus"
