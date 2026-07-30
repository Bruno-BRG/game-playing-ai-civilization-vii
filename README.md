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
- [x] Epic manifest, renderer, redirected saves, and runtime doctor
- [x] YOLO26 inference adapter
- [x] NMS-free YOLO26 ONNX export command
- [x] Stable observation and action contracts
- [x] Dry-run execution by default
- [x] Foreground-window guard before live mouse or keyboard input
- [x] Exact-window foreground guard before desktop pixel capture
- [x] Explicit in-game F8 handoff before observation or input
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

Verify an Epic or custom installation, redirected save folder, and running window:

```powershell
uv run airi-civ7 doctor
```

The doctor checks `--game-root`, `CIV7_GAME_ROOT`, Epic manifests, and finally the conventional
Epic installation path. It detects OneDrive Documents redirection through the Windows known-folder
API. Launch through the entitlement-aware game launcher with:

```powershell
uv run airi-civ7 launch
```

## Safe smoke test

Run against a local fixture without loading a model or injecting input:

```powershell
uv run airi-civ7 run --image C:\path\to\fixture.jpg --steps 1
```

Run live capture in dry-run mode with a trained model:

```powershell
uv run airi-civ7 run --model models\yolo26n-civilization-vii.pt --steps 10
```

To configure or load the match yourself and activate the agent only after reaching the first turn,
add `--wait-for-gameplay`. The runner stays in `PREPARING`, becomes `ARMED` when the exact game
window owns foreground focus, and enters `ACTIVE` only after you press F8:

```powershell
uv run airi-civ7 run `
  --model models\yolo26n-civilization-vii.pt `
  --wait-for-gameplay `
  --steps 10
```

No game pixels are captured and no input is injected before that handoff. The default timeout is
15 minutes and can be changed with `--handoff-timeout`. Every accepted handoff is written to
`handoff.json` in the run directory.

The generic COCO weights do not recognize Civilization VII controls. Use the observation policy to
collect all configured frames without input while building the game-specific dataset:

```powershell
uv run airi-civ7 run `
  --model models\yolo26n.pt `
  --planner observe `
  --wait-for-gameplay `
  --steps 10 `
  --runs-root live-runs
```

For a supervised input-path check, the `next-action` baseline uses Civilization VII's official
Enter binding. Enter advances to the next required action and may end the turn when no actions
remain, so begin with exactly one step:

```powershell
uv run airi-civ7 run `
  --model models\yolo26n.pt `
  --planner next-action `
  --wait-for-gameplay `
  --steps 1 `
  --execute `
  --runs-root live-runs
```

Only add `--execute` after reviewing dry-run traces. Live execution refuses input whenever the
configured game title is not the foreground window:

```powershell
uv run airi-civ7 run `
  --model models\yolo26n-civilization-vii.pt `
  --wait-for-gameplay `
  --steps 10 `
  --execute
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
