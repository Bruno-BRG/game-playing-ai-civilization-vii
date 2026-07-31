# Roadmap

## M0 — Observable runner

- Capture the Civilization VII window on Windows
- Run a custom YOLO26 model
- Persist frames, detections, actions, and execution results
- Default to dry-run and fail closed on ambiguity

## M1 — Ten-turn baseline

- Collect and label the first fixed-profile dataset
- Train `yolo26n-civilization-vii`
- Detect the next-turn button without false positives
- Click ten consecutive turns from a prepared save

## M2 — Required choices

- Add research, civic, production, event, and notification states
- Add OCR for names, costs, yields, and choice descriptions
- Add post-action visual verification and bounded recovery

## M3 — Strategic planner

- [x] Define a JSON-schema planner protocol
- [x] Connect NVIDIA Build through its OpenAI-compatible endpoint
- [x] Force decisions through exact legal action IDs
- Maintain campaign goals, turn summaries, and short-term memory
- Evaluate decisions against deterministic prepared saves

## M4 — Mod telemetry

- [x] Build a versioned single-player structured-state add-on
- [x] Export local yields, cities, units, research, and revealed nearby tiles
- [x] Add game-validated research and native next-action commands
- Add production, settlement, tactical movement, and diplomacy commands
- Correlate stable game identifiers with visual UI targets
- [x] Version and validate the telemetry envelope

## M5 — Project AIRI integration

- Expose the runner through an authenticated local service or MCP boundary
- Stream action traces and screenshots into AIRI
- Require explicit user approval before switching from dry-run to live input
