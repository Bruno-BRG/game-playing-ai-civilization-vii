# Dataset contract

## Baseline profile

- Civilization VII PC, borderless-windowed mode
- English UI for the first model
- One fixed resolution and UI scale per dataset revision
- Full game window captured without desktop background
- Session-level train/validation/test split

## Labels

The initial taxonomy focuses on interactive state rather than every map entity:

- `button.next_turn`: the actionable end-turn control, not disabled variants
- `button.choose_research`: prompt opening the technology choice
- `button.choose_civic`: prompt opening the civic choice
- `button.choose_production`: prompt opening a city production choice
- `button.continue`: confirmation or narrative continuation control
- `button.close`: dismissible modal close control
- `panel.notification`: notification requiring inspection
- `dialog.event`: narrative or choice modal
- `unit.selected`: selection marker for the current unit
- `unit.settler`: visible settler unit
- `unit.scout`: visible scout unit
- `city.own`: an owned settlement nameplate or city anchor
- `tile.valid_move`: a movement destination explicitly highlighted by the game

Boxes should cover the smallest consistently visible interactive region. Do not label text alone
when the clickable control has a stable icon or background. Disabled and ambiguous controls must
be negative examples until separate classes are introduced.

## Quality gate

Before input execution is enabled, the next-turn class needs a session-isolated validation set
with no false positives across menus, loading screens, Age transitions, and modal dialogs. Record
precision, recall, mAP50, and real game-loop false-positive counts for every released model.
