# Architecture

The primary architecture uses Civilization VII's supported UI-script mod surface. The visual
runner remains a useful fallback and independent post-action observer.

```text
Civilization VII add-on (visible single-player state + legal action IDs)
  -> authenticated HTTP on 127.0.0.1
    -> companion validation + state deduplication
      -> NVIDIA Build fast or strategic Nemotron profile
        -> forced choose_action tool call
          -> companion legal-ID validation
            -> add-on correlation + game API revalidation
              -> PlayerOperations or native next-action event
```

The NVIDIA API key exists only in the local companion's `NVIDIA_API_KEY` environment variable.
The add-on holds a separate generated loopback token, never the provider credential. The companion
is dry-run unless `--execute` is present.

Routine actions use Nemotron 3 Nano Omni 30B-A3B with thinking disabled and a named tool choice.
This keeps the hosted request near one second while preserving constrained tool selection. The
same model's full reasoning mode is an explicit strategic profile for future long-horizon
decisions, not the per-action loop.

## Structured bridge boundaries

- **Add-on observation** includes the local player, yields, cities, units, research choices, and
  currently visible tiles near local entities. Fogged tiles and multiplayer/hotseat are excluded.
- **Legal action construction** happens inside the game. Each parameterized operation must pass
  Civilization VII's `canStart` check before it is offered.
- **Planning** can select only an exact action ID through a forced JSON-schema tool call.
- **Correlation** ties a decision to one observation. The add-on rejects stale decisions and the
  companion prevents an unchanged state from executing twice.
- **Execution** re-runs the native validity check immediately before `sendRequest`. The
  `next_action` path dispatches the same event as Civilization VII's own binding so required
  blockers remain authoritative.
- **Tracing** stores the full structured observation and decision as JSONL for audit and replay.

## Visual fallback

```text
Civilization VII window
  -> DXcam frame
    -> YOLO26 detections
      -> normalized observation
        -> conservative planner
          -> validated action
            -> dry-run or guarded Windows input
              -> frame + JSONL trace
```

Capture, perception, planning, execution, and run orchestration remain separate boundaries. One
action per observation prevents a long visual plan from continuing after the screen has changed.
Live desktop input checks that the exact captured Civilization VII window is still foreground.

## Add-on evolution

The bridge currently exposes state and the smallest useful action set: research selection plus the
native next-action resolver. New production, unit, city, and diplomacy operations should follow the
same offer-by-ID, `canStart`, correlate, and revalidate protocol. No operation may accept an
arbitrary API name or unvalidated model parameters.

Visual perception remains useful for UI grounding and for verifying that an intended structured
action actually changed the visible game.
