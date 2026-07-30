"""Observable game-loop orchestration."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .capture import CaptureSource
from .domain import ActionKind, Observation
from .execution import ExecutionResult, Executor
from .perception import Detector
from .planning import Planner


class GameRun:
    """Own one capture-plan-act trace and all screenshot artifacts.

    Each action is correlated to the exact observation sequence that produced it.
    The loop stops when the planner cannot make an unambiguous decision, an executor
    rejects input, or the configured step limit is reached.
    """

    def __init__(
        self,
        *,
        capture: CaptureSource,
        detector: Detector,
        planner: Planner,
        executor: Executor,
        run_directory: Path,
        step_delay_seconds: float = 0,
    ) -> None:
        if not 0 <= step_delay_seconds <= 10:
            raise ValueError("step_delay_seconds must be between 0 and 10")
        self._capture = capture
        self._detector = detector
        self._planner = planner
        self._executor = executor
        self._run_directory = run_directory
        self._frames_directory = run_directory / "frames"
        self._trace_path = run_directory / "trace.jsonl"
        self._step_delay_seconds = step_delay_seconds

    def execute(self, *, max_steps: int) -> int:
        """Execute up to ``max_steps`` and return the number of observed frames."""

        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        self._frames_directory.mkdir(parents=True, exist_ok=True)

        observed_steps = 0
        for sequence in range(max_steps):
            captured_at = datetime.now(UTC).isoformat()
            image = self._capture.capture()
            image_path = self._frames_directory / f"frame-{sequence:04d}.jpg"
            image.save(image_path, quality=92)
            observation = Observation(
                sequence=sequence,
                captured_at=captured_at,
                width=image.width,
                height=image.height,
                image_path=image_path,
                detections=self._detector.detect(image),
            )
            action = self._planner.plan(observation)
            try:
                result = self._executor.execute(action, observation)
            except (RuntimeError, ValueError) as error:
                # Rejections must remain auditable even though the CLI exits non-zero.
                result = ExecutionResult(False, f"rejected: {error}")
                self._append_trace(observation, action.to_json(), asdict(result))
                raise
            self._append_trace(observation, action.to_json(), asdict(result))
            observed_steps += 1
            if action.kind is ActionKind.STOP:
                break
            if self._step_delay_seconds:
                # Give animations and turn processing time to settle before observing again.
                time.sleep(self._step_delay_seconds)
        return observed_steps

    def _append_trace(
        self,
        observation: Observation,
        action: Mapping[str, object],
        execution: Mapping[str, object],
    ) -> None:
        # JSONL keeps completed steps readable even if the process is interrupted mid-run.
        record = {
            "observation": observation.to_json(),
            "action": action,
            "execution": execution,
        }
        with self._trace_path.open("a", encoding="utf-8") as trace_file:
            trace_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def timestamped_run_directory(root: Path) -> Path:
    """Create a sortable, collision-resistant directory name for a new run."""

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return root / timestamp
