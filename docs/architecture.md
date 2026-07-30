# Architecture

The first milestone is deliberately narrower than “play any Civilization VII campaign.” It
must complete ten turns from a prepared single-player save while producing enough artifacts
to explain every action.

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

## Boundaries

- **Capture** knows how to acquire pixels but has no gameplay policy.
- **Perception** converts pixels into stable labels and bounding boxes.
- **Planning** sees only normalized observations and returns one constrained action.
- **Execution** resolves the action against the same observation and owns side effects.
- **Run orchestration** correlates screenshots, observations, actions, and results.

One action per observation prevents a long plan from continuing after the screen has changed.
Input is disabled by default. When explicitly enabled, the executor checks that the configured
Civilization VII window is foreground immediately before every side effect.

## Planned telemetry mod

The official Modding SDK can eventually expose single-player state that is hard to infer from
pixels, such as current turn, yields, selected research, city queues, and unit identifiers. The
mod must write or serve read-only, versioned snapshots. It must not inspect process memory,
automate multiplayer, or make hidden opponent information available to the planner.

Visual perception remains necessary for UI grounding and for verifying that an intended action
actually changed the screen.
