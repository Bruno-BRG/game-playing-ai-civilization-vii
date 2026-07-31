"""Install the packaged AIRI bridge add-on into Civilization VII's user mod folder."""

from __future__ import annotations

import json
import os
import secrets
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AddonInstallation:
    """Installed add-on paths and the shared companion authentication token."""

    mod_root: Path
    token_path: Path
    token: str


def install_addon(
    *,
    port: int = 43127,
    environment: Mapping[str, str] | None = None,
    local_app_data: Path | None = None,
) -> AddonInstallation:
    """Install or update the add-on while preserving an existing local bridge token."""

    if not 1 <= port <= 65535:
        raise ValueError("Bridge port must be between 1 and 65535")
    environment = os.environ if environment is None else environment
    if local_app_data is None:
        local_app_data_value = environment.get("LOCALAPPDATA")
        if not local_app_data_value:
            raise FileNotFoundError("LOCALAPPDATA is not available")
        local_app_data = Path(local_app_data_value)

    mod_root = (
        local_app_data
        / "Firaxis Games"
        / "Sid Meier's Civilization VII"
        / "Mods"
        / "airi-civ7-bridge"
    )
    token_path = local_app_data / "AIRI" / "Civilization VII" / "bridge-token.txt"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token = token_path.read_text(encoding="utf-8").strip() if token_path.exists() else ""
    if not token:
        token = secrets.token_urlsafe(32)
        token_path.write_text(token + "\n", encoding="utf-8")

    addon_assets = files("airi_civilization_vii").joinpath("addon")
    mod_root.mkdir(parents=True, exist_ok=True)
    (mod_root / "ui").mkdir(parents=True, exist_ok=True)
    for relative_path in ("airi-civ7-bridge.modinfo", "ui/airi-bridge.js"):
        source = addon_assets.joinpath(*relative_path.split("/"))
        with (
            source.open("rb") as source_file,
            (mod_root / Path(relative_path)).open("wb") as target_file,
        ):
            shutil.copyfileobj(source_file, target_file)

    config = (
        "globalThis.AiriCiv7BridgeConfig = Object.freeze({\n"
        f"  endpoint: {json.dumps(f'http://127.0.0.1:{port}/v1/observations')},\n"
        f"  token: {json.dumps(token)},\n"
        "  pollIntervalMs: 5000,\n"
        "});\n"
    )
    (mod_root / "ui" / "airi-bridge-config.js").write_text(config, encoding="utf-8")
    return AddonInstallation(mod_root=mod_root, token_path=token_path, token=token)


def read_bridge_token(
    *,
    environment: Mapping[str, str] | None = None,
    local_app_data: Path | None = None,
) -> str:
    """Read the token created by install_addon without exposing it through CLI arguments."""

    environment = os.environ if environment is None else environment
    if local_app_data is None:
        local_app_data_value = environment.get("LOCALAPPDATA")
        if not local_app_data_value:
            raise FileNotFoundError("LOCALAPPDATA is not available")
        local_app_data = Path(local_app_data_value)
    token_path = local_app_data / "AIRI" / "Civilization VII" / "bridge-token.txt"
    if not token_path.is_file():
        raise FileNotFoundError("Bridge token not found; run 'airi-civ7 install-addon' first")
    token = token_path.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("Bridge token file is empty; reinstall the add-on")
    return token
