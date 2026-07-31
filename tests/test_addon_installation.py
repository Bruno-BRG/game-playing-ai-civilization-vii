from pathlib import Path

from airi_civilization_vii.addon_installation import install_addon, read_bridge_token


def test_installer_writes_mod_and_shared_secret(tmp_path: Path) -> None:
    installation = install_addon(local_app_data=tmp_path, port=43210)

    assert installation.mod_root == (
        tmp_path / "Firaxis Games" / "Sid Meier's Civilization VII" / "Mods" / "airi-civ7-bridge"
    )
    assert (installation.mod_root / "airi-civ7-bridge.modinfo").is_file()
    assert (installation.mod_root / "ui" / "airi-bridge.js").is_file()
    config = (installation.mod_root / "ui" / "airi-bridge-config.js").read_text(encoding="utf-8")
    assert "http://127.0.0.1:43210/v1/observations" in config
    assert installation.token in config
    assert read_bridge_token(local_app_data=tmp_path) == installation.token


def test_installer_preserves_token_across_updates(tmp_path: Path) -> None:
    first = install_addon(local_app_data=tmp_path)
    second = install_addon(local_app_data=tmp_path)

    assert second.token == first.token
