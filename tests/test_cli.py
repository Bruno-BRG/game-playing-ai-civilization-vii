import pytest

from airi_civilization_vii.cli import main


def test_live_next_action_requires_explicit_gameplay_handoff() -> None:
    with pytest.raises(ValueError, match="requires --wait-for-gameplay"):
        main(["run", "--planner", "next-action", "--steps", "1", "--execute"])


def test_live_next_action_is_limited_to_one_supervised_step() -> None:
    with pytest.raises(ValueError, match="requires --steps 1"):
        main(
            [
                "run",
                "--planner",
                "next-action",
                "--wait-for-gameplay",
                "--steps",
                "2",
                "--execute",
            ]
        )
