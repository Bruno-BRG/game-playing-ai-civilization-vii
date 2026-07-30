"""Civilization VII installation, save, and launcher discovery."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class InstallationSource(StrEnum):
    """The source that resolved a verified game installation."""

    EXPLICIT = "explicit"
    ENVIRONMENT = "environment"
    EPIC_MANIFEST = "epic_manifest"
    EPIC_DEFAULT = "epic_default"


class GameExecutable(StrEnum):
    """Supported official executables within a verified installation."""

    LAUNCHER = "launcher"
    DX12 = "dx12"
    VULKAN = "vulkan"


@dataclass(frozen=True, slots=True)
class GameInstallation:
    """Verified executable paths belonging to one Civilization VII installation."""

    root: Path
    source: InstallationSource
    launcher: Path
    dx12: Path
    vulkan: Path

    def executable(self, kind: GameExecutable) -> Path:
        """Resolve an executable selected by the public CLI."""

        return {
            GameExecutable.LAUNCHER: self.launcher,
            GameExecutable.DX12: self.dx12,
            GameExecutable.VULKAN: self.vulkan,
        }[kind]


def installation_from_root(root: Path, *, source: InstallationSource) -> GameInstallation:
    """Validate the known executable layout below a candidate game root."""

    resolved_root = root.expanduser().resolve()
    binary_directory = resolved_root / "Base" / "Binaries" / "Win64"
    installation = GameInstallation(
        root=resolved_root,
        source=source,
        launcher=binary_directory / "Civ7_Launcher.exe",
        dx12=binary_directory / "Civ7_Win64_DX12_FinalRelease.exe",
        vulkan=binary_directory / "Civ7_Win64_Vulkan_FinalRelease.exe",
    )
    missing = [
        executable
        for executable in (installation.launcher, installation.dx12, installation.vulkan)
        if not executable.is_file()
    ]
    if missing:
        missing_paths = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Civilization VII installation is incomplete: {missing_paths}")
    return installation


def discover_installation(
    explicit_root: Path | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> GameInstallation:
    """Discover Civilization VII using explicit, environment, and Epic metadata sources.

    Precedence is intentional: an explicit CLI path is authoritative, followed by
    `CIV7_GAME_ROOT`. Epic manifests are preferred over the conventional Epic path
    because manifests reflect custom library locations.
    """

    current_environment = os.environ if environment is None else environment
    if explicit_root is not None:
        return installation_from_root(explicit_root, source=InstallationSource.EXPLICIT)

    environment_root = current_environment.get("CIV7_GAME_ROOT")
    if environment_root:
        return installation_from_root(
            Path(environment_root),
            source=InstallationSource.ENVIRONMENT,
        )

    program_data = current_environment.get("PROGRAMDATA")
    if program_data:
        manifest_directory = (
            Path(program_data) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
        )
        for manifest_path in sorted(manifest_directory.glob("*.item")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            launch_executable = str(manifest.get("LaunchExecutable", "")).replace("\\", "/")
            if not launch_executable.casefold().endswith("/civ7_launcher.exe"):
                continue
            install_location = manifest.get("InstallLocation")
            if isinstance(install_location, str):
                return installation_from_root(
                    Path(install_location),
                    source=InstallationSource.EPIC_MANIFEST,
                )

    program_files = current_environment.get("ProgramFiles")
    if program_files:
        conventional_root = Path(program_files) / "Epic Games" / "CivilizationVII"
        if conventional_root.exists():
            return installation_from_root(
                conventional_root,
                source=InstallationSource.EPIC_DEFAULT,
            )

    raise FileNotFoundError(
        "Civilization VII was not found. Pass --game-root or set CIV7_GAME_ROOT."
    )


def documents_directory() -> Path:
    """Resolve the Windows Documents known folder, including OneDrive redirection."""

    if sys.platform != "win32":
        return Path.home() / "Documents"

    # CSIDL_PERSONAL asks Windows for the user-visible Documents folder instead of
    # assuming an English path or bypassing OneDrive known-folder redirection.
    buffer = ctypes.create_unicode_buffer(260)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer)
    if result != 0:
        raise RuntimeError(f"Windows could not resolve the Documents folder: HRESULT {result}")
    return Path(buffer.value)


def discover_saves_root(*, documents: Path | None = None) -> Path | None:
    """Return the existing single-player save root without reading or modifying saves."""

    resolved_documents = documents_directory() if documents is None else documents
    candidate = resolved_documents / "My Games" / "Sid Meier's Civilization VII" / "Saves"
    return candidate if candidate.is_dir() else None


def launch_game(
    installation: GameInstallation,
    *,
    executable: GameExecutable = GameExecutable.LAUNCHER,
) -> int:
    """Start an official game executable and return its initial process identifier.

    The launcher is the default because it preserves Epic entitlement and account
    initialization. Direct DX12 or Vulkan execution is available for local diagnosis.
    """

    executable_path = installation.executable(executable)
    process = subprocess.Popen(
        [str(executable_path)],
        cwd=executable_path.parent,
        shell=False,
    )
    return process.pid
