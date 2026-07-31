from pathlib import Path

from civ7_ai.addon_installation import install_addon, read_bridge_token


def test_installer_writes_mod_and_shared_secret(tmp_path: Path) -> None:
    installation = install_addon(local_app_data=tmp_path, port=43210)

    assert installation.mod_root == (
        tmp_path / "Firaxis Games" / "Sid Meier's Civilization VII" / "Mods" / "civ7-ai-bridge"
    )
    assert (installation.mod_root / "civ7-ai-bridge.modinfo").is_file()
    assert (installation.mod_root / "ui" / "civ7-ai-bridge.js").is_file()
    assert installation.token_path == tmp_path / "Civilization VII AI" / "bridge-token.txt"
    config = (installation.mod_root / "ui" / "civ7-ai-bridge-config.js").read_text(encoding="utf-8")
    assert "http://127.0.0.1:43210/v1/observations" in config
    assert "pollIntervalMs: 1000" in config
    assert installation.token in config
    assert read_bridge_token(local_app_data=tmp_path) == installation.token


def test_installer_preserves_token_across_updates(tmp_path: Path) -> None:
    first = install_addon(local_app_data=tmp_path)
    second = install_addon(local_app_data=tmp_path)

    assert second.token == first.token


def test_installer_uses_epic_user_data_root_when_game_created_it(tmp_path: Path) -> None:
    epic_root = tmp_path / "Firaxis Games" / "Sid Meier's Civilization VII (Epic)"
    epic_root.mkdir(parents=True)
    (epic_root / "Mods.sqlite").touch()

    installation = install_addon(local_app_data=tmp_path)

    assert installation.mod_root == epic_root / "Mods" / "civ7-ai-bridge"
