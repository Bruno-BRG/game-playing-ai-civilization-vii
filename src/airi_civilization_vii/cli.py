"""Command-line entrypoint for capture, training, export, and guarded game runs."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .capture import CaptureSource, DxcamCapture, ImageCapture, WindowTarget, find_window
from .execution import DryRunExecutor, Executor, WindowsInputExecutor
from .installation import (
    GameExecutable,
    discover_installation,
    discover_saves_root,
    launch_game,
)
from .perception import NullDetector, YoloDetector
from .planning import NextTurnBaselinePlanner
from .run import GameRun, timestamped_run_directory
from .training import export_onnx, train_yolo26


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI while keeping imports safe on non-Windows hosts."""

    parser = argparse.ArgumentParser(prog="airi-civ7")
    subcommands = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subcommands.add_parser("doctor", help="diagnose the local game environment")
    doctor_parser.add_argument("--game-root", type=Path)
    doctor_parser.add_argument("--json", action="store_true", dest="as_json")

    launch_parser = subcommands.add_parser("launch", help="launch Civilization VII")
    launch_parser.add_argument("--game-root", type=Path)
    launch_parser.add_argument(
        "--executable",
        choices=[item.value for item in GameExecutable],
        default=GameExecutable.LAUNCHER.value,
    )

    run_parser = subcommands.add_parser("run", help="run the observable capture-plan-act loop")
    run_parser.add_argument("--model", type=Path, help="trained YOLO26 .pt or .onnx model")
    run_parser.add_argument(
        "--image", type=Path, help="repeat a fixture instead of capturing the game"
    )
    run_parser.add_argument("--window-title", default="Civilization VII")
    run_parser.add_argument("--steps", type=int, default=10)
    run_parser.add_argument("--step-delay", type=float, default=1.0)
    run_parser.add_argument("--runs-root", type=Path, default=Path("runs"))
    run_parser.add_argument(
        "--execute",
        action="store_true",
        help="inject input; omitted by default so the runner is always dry-run first",
    )

    train_parser = subcommands.add_parser("train", help="fine-tune YOLO26")
    train_parser.add_argument(
        "--data",
        type=Path,
        default=Path("datasets/civilization-vii/data.yaml"),
    )
    train_parser.add_argument("--model", default="yolo26n.pt")
    train_parser.add_argument("--epochs", type=int, default=100)
    train_parser.add_argument("--image-size", type=int, default=960)
    train_parser.add_argument("--output", type=Path, default=Path("models/training"))

    export_parser = subcommands.add_parser("export", help="export a trained model to ONNX")
    export_parser.add_argument("--model", type=Path, required=True)
    export_parser.add_argument("--image-size", type=int, default=960)
    export_parser.add_argument("--output", type=Path, default=Path("models"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected command and return a process-compatible status code.

    Call stack:

    main
      -> GameRun.execute
        -> CaptureSource.capture
        -> Detector.detect
        -> Planner.plan
        -> Executor.execute
    """

    arguments = build_parser().parse_args(argv)
    if arguments.command == "doctor":
        installation = discover_installation(arguments.game_root)
        saves_root = discover_saves_root()
        try:
            target = find_window("Civilization VII")
        except RuntimeError:
            target = None
        saves_count = len(list(saves_root.rglob("*.Civ7Save"))) if saves_root else 0
        saves_root_text = str(saves_root) if saves_root is not None else None
        report = {
            "installation": {
                "source": installation.source,
                "root": str(installation.root),
                "launcher": str(installation.launcher),
                "dx12": str(installation.dx12),
                "vulkan": str(installation.vulkan),
            },
            "saves": {
                "root": saves_root_text,
                "count": saves_count,
            },
            "window": (
                {
                    "handle": target.handle,
                    "title": target.title,
                    "region": list(target.region.dxcam_region),
                }
                if target is not None
                else None
            ),
        }
        if arguments.as_json:
            print(json.dumps(report, indent=2))
        else:
            print(f"Installation: {installation.root} ({installation.source})")
            print(f"Saves: {saves_root_text} ({saves_count} files)")
            print(f"Window: {target.title if target is not None else 'not running'}")
        return 0
    if arguments.command == "launch":
        installation = discover_installation(arguments.game_root)
        process_id = launch_game(
            installation,
            executable=GameExecutable(arguments.executable),
        )
        print(f"Started {arguments.executable} process {process_id}")
        return 0
    if arguments.command == "train":
        train_yolo26(
            data=arguments.data,
            model=arguments.model,
            epochs=arguments.epochs,
            image_size=arguments.image_size,
            output_directory=arguments.output,
        )
        return 0
    if arguments.command == "export":
        exported_path = export_onnx(
            model_path=arguments.model,
            image_size=arguments.image_size,
            output_directory=arguments.output,
        )
        print(exported_path)
        return 0

    capture: CaptureSource
    window_target: WindowTarget | None = None
    if arguments.image is not None:
        if arguments.execute:
            raise ValueError("--execute cannot be combined with a repeated fixture image")
        capture = ImageCapture(arguments.image)
    else:
        window_target = find_window(arguments.window_title)
        capture = DxcamCapture(window_target)

    detector = YoloDetector(arguments.model) if arguments.model else NullDetector()
    executor: Executor
    if arguments.execute:
        if window_target is None:
            raise ValueError("Live execution requires a discovered game window")
        executor = WindowsInputExecutor(
            window_handle=window_target.handle,
            window_title=window_target.title,
            capture_origin=capture.origin,
        )
    else:
        executor = DryRunExecutor()
    run_directory = timestamped_run_directory(arguments.runs_root)
    observed_steps = GameRun(
        capture=capture,
        detector=detector,
        planner=NextTurnBaselinePlanner(),
        executor=executor,
        run_directory=run_directory,
        step_delay_seconds=arguments.step_delay,
    ).execute(max_steps=arguments.steps)
    print(f"Observed {observed_steps} step(s). Trace: {run_directory / 'trace.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
