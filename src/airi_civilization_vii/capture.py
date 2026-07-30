"""Game-frame capture backends."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image


@dataclass(frozen=True, slots=True)
class CaptureRegion:
    """A desktop-space region in left, top, right, bottom order."""

    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(self) -> None:
        if self.right <= self.left or self.bottom <= self.top:
            raise ValueError("Capture regions must have a positive area")

    @property
    def dxcam_region(self) -> tuple[int, int, int, int]:
        """Return the tuple shape expected by DXcam."""

        return (self.left, self.top, self.right, self.bottom)


@dataclass(frozen=True, slots=True)
class WindowTarget:
    """The exact top-level window whose pixels and input belong to one game run."""

    handle: int
    title: str
    region: CaptureRegion


class CaptureSource(Protocol):
    """Produces one RGB image without deciding where it will be persisted."""

    @property
    def origin(self) -> tuple[int, int]: ...

    def capture(self) -> Image.Image: ...


class ImageCapture:
    """Repeat a fixture image for dataset review and cross-platform smoke tests."""

    def __init__(self, image_path: Path) -> None:
        self._image_path = image_path

    @property
    def origin(self) -> tuple[int, int]:
        return (0, 0)

    def capture(self) -> Image.Image:
        with Image.open(self._image_path) as image:
            return image.convert("RGB")


def require_window_foreground(*, target_handle: int, foreground_handle: int, title: str) -> None:
    """Fail closed when desktop pixels no longer represent the target game window."""

    if foreground_handle != target_handle:
        raise RuntimeError(
            f"Refusing capture or input because {title!r} is not the foreground window"
        )


def find_window(title_fragment: str) -> WindowTarget:
    """Find one visible top-level Windows window using a title fragment.

    The returned coordinates include the window chrome. Running Civilization VII in
    borderless-windowed mode keeps the capture stable and avoids exclusive-fullscreen
    capture limitations.
    """

    if sys.platform != "win32":
        raise RuntimeError("Window discovery is only available on Windows")

    user32 = ctypes.windll.user32
    matches: list[WindowTarget] = []
    fragment = title_fragment.casefold()
    enum_callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    class Rect(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    @enum_callback_type  # type: ignore[untyped-decorator]
    def inspect_window(handle: int, _context: int) -> bool:
        if not user32.IsWindowVisible(handle):
            return True

        title_length = user32.GetWindowTextLengthW(handle)
        if title_length == 0:
            return True

        buffer = ctypes.create_unicode_buffer(title_length + 1)
        user32.GetWindowTextW(handle, buffer, title_length + 1)
        if fragment not in buffer.value.casefold():
            return True

        rect = Rect()
        if user32.GetWindowRect(handle, ctypes.byref(rect)):
            matches.append(
                WindowTarget(
                    handle=int(handle),
                    title=buffer.value,
                    region=CaptureRegion(rect.left, rect.top, rect.right, rect.bottom),
                )
            )
        return True

    user32.EnumWindows(inspect_window, 0)
    if not matches:
        raise RuntimeError(f"No visible window title contains {title_fragment!r}")
    if len(matches) > 1:
        raise RuntimeError(f"More than one visible window title contains {title_fragment!r}")
    return matches[0]


class DxcamCapture:
    """Capture the Civilization VII window through the Desktop Duplication API."""

    def __init__(self, target: WindowTarget) -> None:
        if sys.platform != "win32":
            raise RuntimeError("DXcam capture is only available on Windows")

        try:
            import dxcam
        except ImportError as error:
            raise RuntimeError(
                "Install the Windows dependencies with: uv sync --extra windows"
            ) from error

        self._target = target
        self._camera = dxcam.create(output_color="RGB")

    @property
    def origin(self) -> tuple[int, int]:
        return (self._target.region.left, self._target.region.top)

    def capture(self) -> Image.Image:
        foreground_handle = int(ctypes.windll.user32.GetForegroundWindow())
        require_window_foreground(
            target_handle=self._target.handle,
            foreground_handle=foreground_handle,
            title=self._target.title,
        )
        frame = self._camera.grab(region=self._target.region.dxcam_region)
        if frame is None:
            raise RuntimeError("DXcam did not return a frame; keep the game visible and try again")
        return Image.fromarray(frame)
