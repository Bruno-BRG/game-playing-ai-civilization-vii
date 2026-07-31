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
    installed_script = (installation.mod_root / "ui" / "civ7-ai-bridge.js").read_text(
        encoding="utf-8"
    )
    assert "http://127.0.0.1:43210/v1/observations" in installed_script
    assert 'observationStorageKey: "civ7-ai-bridge:observation"' in installed_script
    assert 'decisionStorageKey: "civ7-ai-bridge:decision"' in installed_script
    assert "pollIntervalMs: 1000" in installed_script
    assert installation.token in installed_script
    assert installed_script.index("globalThis.Civ7AiBridgeConfig") < installed_script.index(
        "(() => {"
    )
    assert not (installation.mod_root / "ui" / "civ7-ai-bridge-config.js").exists()
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


def test_addon_uses_civ_local_storage_transport() -> None:
    addon_script = (
        Path(__file__).parents[1] / "src" / "civ7_ai" / "addon" / "ui" / "civ7-ai-bridge.js"
    ).read_text(encoding="utf-8")

    # ROOT CAUSE:
    #
    # Civilization VII's Cohtml runtime refuses HTTP URLs, including loopback URLs. Its UI
    # LocalStorage database is the supported local exchange that survives that sandbox.
    assert "localStorage.setItem(observationStorageKey" in addon_script
    assert "localStorage.getItem(decisionStorageKey" in addon_script
    assert "PlayerOperationTypes.SET_TECH_TREE_TARGET_NODE" in addon_script
    assert "session_id: sessionId" in addon_script
    assert "new XMLHttpRequest()" not in addon_script
    assert "fetch(config.endpoint" not in addon_script


def test_manifest_loads_the_combined_bridge_script_once() -> None:
    manifest = (
        Path(__file__).parents[1] / "src" / "civ7_ai" / "addon" / "civ7-ai-bridge.modinfo"
    ).read_text(encoding="utf-8")

    # ROOT CAUSE:
    #
    # Civilization VII isolates globals between separate UIScript items. Loading configuration
    # and bridge code as different items made the bridge see an empty configuration.
    assert manifest.count("<Item>ui/civ7-ai-bridge.js</Item>") == 1
    assert "civ7-ai-bridge-config.js" not in manifest
