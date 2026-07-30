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

- Define a JSON-schema planner protocol
- Connect an OpenAI-compatible multimodal or text model through AIRI
- Maintain campaign goals, turn summaries, and short-term memory
- Evaluate decisions against deterministic prepared saves

## M4 — Mod telemetry

- Build a read-only single-player telemetry mod with the official SDK
- Correlate stable game identifiers with visual UI targets
- Version and validate the telemetry envelope

## M5 — Project AIRI integration

- Expose the runner through an authenticated local service or MCP boundary
- Stream action traces and screenshots into AIRI
- Require explicit user approval before switching from dry-run to live input
