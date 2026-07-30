import pytest

from airi_civilization_vii.capture import CaptureRegion, require_window_foreground


def test_capture_region_requires_positive_area() -> None:
    with pytest.raises(ValueError, match="positive area"):
        CaptureRegion(left=100, top=100, right=100, bottom=200)


def test_foreground_guard_accepts_exact_window_handle() -> None:
    require_window_foreground(target_handle=42, foreground_handle=42, title="Civilization VII")


def test_foreground_guard_rejects_occluded_game_window() -> None:
    with pytest.raises(RuntimeError, match="not the foreground window"):
        require_window_foreground(
            target_handle=42,
            foreground_handle=99,
            title="Sid Meier's Civilization VII (DX12)",
        )
