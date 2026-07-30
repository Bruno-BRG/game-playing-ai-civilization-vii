<h1 align="center">Game AI — Civilization VII</h1>

<p align="center">
  A safe, observable Civilization VII game-playing agent for
  <a href="https://github.com/moeru-ai/airi">Project AIRI</a>.
</p>

This project combines YOLO26 computer vision, constrained planning, and guarded desktop input.
The first target is intentionally measurable: complete ten turns from a prepared single-player
save while recording every frame, detection, decision, and action.

> [!IMPORTANT]
> The project is for owned copies of the game and local single-player research. It does not read
> or modify process memory, expose hidden opponent state, or automate multiplayer. No game assets,
> screenshots, SDK files, models, or datasets are distributed in this repository.

## Current status

- [x] Windows window discovery and DXcam capture boundary
- [x] YOLO26 inference adapter
- [x] NMS-free YOLO26 ONNX export command
- [x] Stable observation and action contracts
- [x] Dry-run execution by default
- [x] Foreground-window guard before live mouse or keyboard input
- [x] Screenshot and JSONL trace artifacts
- [x] Conservative next-turn baseline planner
- [ ] Civilization VII dataset and trained weights
- [ ] OCR and strategic LLM planner
- [ ] Official SDK telemetry mod
- [ ] AIRI service integration

## Setup

Install [uv](https://docs.astral.sh/uv/) and sync the project:

```powershell
uv sync --extra vision --extra windows
```

Use Civilization VII in borderless-windowed mode. The default window-title fragment is
`Civilization VII`.

## Safe smoke test

Run against a local fixture without loading a model or injecting input:

```powershell
uv run airi-civ7 run --image C:\path\to\fixture.jpg --steps 1
```

Run live capture in dry-run mode with a trained model:

```powershell
uv run airi-civ7 run --model models\yolo26n-civilization-vii.pt --steps 10
```

Only add `--execute` after reviewing dry-run traces. Live execution refuses input whenever the
configured game title is not the foreground window:

```powershell
uv run airi-civ7 run --model models\yolo26n-civilization-vii.pt --steps 10 --execute
```

Artifacts are stored under `runs/<UTC timestamp>/` with captured frames and `trace.jsonl`.

## Train YOLO26n

Place an approved YOLO-format dataset under `datasets/civilization-vii` or update `data.yaml` to
an external dataset location:

```powershell
uv run airi-civ7 train `
  --data datasets\civilization-vii\data.yaml `
  --model yolo26n.pt `
  --epochs 100 `
  --image-size 960
```

Export the trained end-to-end model to ONNX:

```powershell
uv run airi-civ7 export `
  --model models\training\yolo26n-civilization-vii\weights\best.pt `
  --output models
```

YOLO26 uses an end-to-end one-to-one head by default, producing detections without a separate NMS
step. See the [official YOLO26 documentation](https://docs.ultralytics.com/models/yolo26/).

## Design documents

- [Architecture](docs/architecture.md)
- [Dataset contract](docs/dataset.md)
- [Roadmap](docs/roadmap.md)

## Related Project AIRI work

- [Game AI — Dome Keeper](https://github.com/proj-airi/game-playing-ai-dome-keeper)
- [Game AI — Balatro](https://github.com/proj-airi/game-playing-ai-balatro)
- [2D game-playing playground](https://github.com/proj-airi/game-playing-ai-playground-2d)

## License

Source code in this repository is available under the MIT License. Sid Meier's Civilization,
Civilization VII, Firaxis Games, 2K, and their respective marks and assets belong to their owners.
