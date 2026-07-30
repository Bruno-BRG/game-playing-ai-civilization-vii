import json
from pathlib import Path

import pytest

from airi_civilization_vii.installation import (
    InstallationSource,
    discover_installation,
    discover_saves_root,
)


def create_installation(root: Path) -> None:
    binary_directory = root / "Base" / "Binaries" / "Win64"
    binary_directory.mkdir(parents=True)
    for filename in (
        "Civ7_Launcher.exe",
        "Civ7_Win64_DX12_FinalRelease.exe",
        "Civ7_Win64_Vulkan_FinalRelease.exe",
    ):
        (binary_directory / filename).touch()


def test_explicit_root_is_authoritative(tmp_path: Path) -> None:
    game_root = tmp_path / "CivilizationVII"
    create_installation(game_root)

    installation = discover_installation(game_root, environment={})

    assert installation.root == game_root.resolve()
    assert installation.source is InstallationSource.EXPLICIT


def test_epic_manifest_supports_custom_library_location(tmp_path: Path) -> None:
    game_root = tmp_path / "Custom Epic Library" / "CivilizationVII"
    create_installation(game_root)
    manifest_directory = tmp_path / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    manifest_directory.mkdir(parents=True)
    (manifest_directory / "civ7.item").write_text(
        json.dumps(
            {
                "InstallLocation": str(game_root),
                "LaunchExecutable": "Base/Binaries/Win64/Civ7_Launcher.exe",
            }
        ),
        encoding="utf-8",
    )

    installation = discover_installation(environment={"PROGRAMDATA": str(tmp_path)})

    assert installation.root == game_root.resolve()
    assert installation.source is InstallationSource.EPIC_MANIFEST


def test_invalid_explicit_root_does_not_silently_fall_back(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="incomplete"):
        discover_installation(tmp_path / "missing", environment={})


def test_save_discovery_respects_redirected_documents_folder(tmp_path: Path) -> None:
    saves_root = tmp_path / "My Games" / "Sid Meier's Civilization VII" / "Saves"
    saves_root.mkdir(parents=True)

    assert discover_saves_root(documents=tmp_path) == saves_root
