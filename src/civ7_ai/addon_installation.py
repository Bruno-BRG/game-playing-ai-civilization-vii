"""Install the packaged Civ VII AI bridge into the game's user mod folder."""

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


def _discover_user_data_root(local_app_data: Path) -> Path:
    """Prefer an active Epic data root and otherwise use the standard PC directory."""

    firaxis_root = local_app_data / "Firaxis Games"
    candidates = (
        firaxis_root / "Sid Meier's Civilization VII (Epic)",
        firaxis_root / "Sid Meier's Civilization VII",
    )
    for candidate in candidates:
        # The Epic build adds a platform suffix. Runtime-owned files distinguish its real
        # user-data root from an empty generic directory left by an older installer.
        if (candidate / "Mods.sqlite").is_file() or (candidate / "AppOptions.txt").is_file():
            return candidate
    return candidates[-1]


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

    user_data_root = _discover_user_data_root(local_app_data)
    mod_root = user_data_root / "Mods" / "civ7-ai-bridge"
    token_path = local_app_data / "Civilization VII AI" / "bridge-token.txt"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token = token_path.read_text(encoding="utf-8").strip() if token_path.exists() else ""
    if not token:
        token = secrets.token_urlsafe(32)
        token_path.write_text(token + "\n", encoding="utf-8")

    addon_assets = files("civ7_ai").joinpath("addon")
    mod_root.mkdir(parents=True, exist_ok=True)
    (mod_root / "ui").mkdir(parents=True, exist_ok=True)
    manifest_source = addon_assets.joinpath("civ7-ai-bridge.modinfo")
    with (
        manifest_source.open("rb") as source_file,
        (mod_root / "civ7-ai-bridge.modinfo").open("wb") as target_file,
    ):
        shutil.copyfileobj(source_file, target_file)

    config = (
        "globalThis.Civ7AiBridgeConfig = Object.freeze({\n"
        f"  endpoint: {json.dumps(f'http://127.0.0.1:{port}/v1/observations')},\n"
        f"  token: {json.dumps(token)},\n"
        "  pollIntervalMs: 1000,\n"
        "});\n"
    )
    addon_script = addon_assets.joinpath("ui", "civ7-ai-bridge.js").read_text(encoding="utf-8")
    (mod_root / "ui" / "civ7-ai-bridge.js").write_text(
        config + "\n" + addon_script,
        encoding="utf-8",
    )
    separate_config_path = mod_root / "ui" / "civ7-ai-bridge-config.js"
    if separate_config_path.exists():
        # Each Civ VII UIScript receives an isolated global context. The generated config must
        # live in the same script as its consumer, so remove the obsolete split installation.
        separate_config_path.unlink()
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
    token_path = local_app_data / "Civilization VII AI" / "bridge-token.txt"
    if not token_path.is_file():
        raise FileNotFoundError("Bridge token not found; run 'civ7-ai install-addon' first")
    token = token_path.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("Bridge token file is empty; reinstall the add-on")
    return token
