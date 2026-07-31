from collections.abc import Callable

import pytest

from civ7_ai.capture import CaptureRegion, WindowTarget
from civ7_ai.handoff import F8_VIRTUAL_KEY, HandoffState, wait_for_handoff


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _target() -> WindowTarget:
    return WindowTarget(
        handle=42,
        title="Sid Meier's Civilization VII (DX12)",
        region=CaptureRegion(0, 0, 1920, 1080),
    )


def _sequence_reader(values: list[int | bool]) -> Callable[..., int | bool]:
    remaining = iter(values)
    last = values[-1]

    def read(*_arguments: object) -> int | bool:
        nonlocal last
        last = next(remaining, last)
        return last

    return read


def test_handoff_requires_release_then_f8_on_exact_foreground_window() -> None:
    clock = FakeClock()
    states: list[HandoffState] = []
    foreground = _sequence_reader([42, 42])
    keys = _sequence_reader([False, True])

    result = wait_for_handoff(
        _target(),
        stable_seconds=0,
        poll_interval_seconds=0.05,
        on_state_change=states.append,
        get_foreground_handle=lambda: int(foreground()),
        is_key_down=lambda key: bool(keys(key)),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    assert result.key == "F8"
    assert result.window_handle == 42
    assert states == [HandoffState.ARMED, HandoffState.ACTIVE]


def test_handoff_consumes_f8_pressed_in_another_window() -> None:
    clock = FakeClock()
    foreground = _sequence_reader([99, 42, 42, 42])
    keys = _sequence_reader([True, True, False, True])

    result = wait_for_handoff(
        _target(),
        stable_seconds=0,
        poll_interval_seconds=0.05,
        get_foreground_handle=lambda: int(foreground()),
        is_key_down=lambda key: bool(keys(key)),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    assert result.window_handle == 42
    assert clock.now == pytest.approx(0.15)


def test_handoff_requires_stable_foreground_after_f8() -> None:
    clock = FakeClock()
    foreground = _sequence_reader([42, 42, 99, 42, 42, 42, 42])
    keys = _sequence_reader([False, True, True, False, True])

    result = wait_for_handoff(
        _target(),
        stable_seconds=0.1,
        poll_interval_seconds=0.05,
        get_foreground_handle=lambda: int(foreground()),
        is_key_down=lambda key: bool(keys(key)),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    assert result.window_handle == 42
    assert clock.now >= 0.25


def test_handoff_times_out_without_a_valid_press() -> None:
    clock = FakeClock()

    with pytest.raises(TimeoutError, match="F8 handoff"):
        wait_for_handoff(
            _target(),
            timeout_seconds=0.1,
            stable_seconds=0,
            poll_interval_seconds=0.05,
            get_foreground_handle=lambda: 42,
            is_key_down=lambda key: key != F8_VIRTUAL_KEY,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
