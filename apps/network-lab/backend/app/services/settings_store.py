from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any

from .config_loader import defaults

_LOCK = RLock()


def _settings_dir() -> Path:
    base = os.getenv("LOCALAPPDATA")

    if base:
        root = Path(base)
    else:
        root = Path.home() / ".config"

    return root / "T6RA-NetworkLab"


def _settings_path() -> Path:
    return _settings_dir() / "settings.json"


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)

    for key, value in overlay.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)

    return merged


def _load_persisted() -> dict[str, Any]:
    path = _settings_path()

    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def get_settings() -> dict[str, Any]:
    with _LOCK:
        settings = _deep_merge(defaults(), _load_persisted())

        env_port = os.getenv("T6RA_PORT")
        env_mode = os.getenv("T6RA_MODE")
        env_baud = os.getenv("T6RA_BAUD")

        if env_port:
            settings.setdefault("serial", {})["port"] = env_port

        if env_mode:
            settings.setdefault("runtime", {})["mode"] = env_mode.lower()

        if env_baud:
            try:
                settings.setdefault("serial", {})["baudrate"] = int(env_baud)
            except ValueError:
                pass

        return settings


def save_settings(settings: dict[str, Any]) -> None:
    with _LOCK:
        directory = _settings_dir()
        directory.mkdir(parents=True, exist_ok=True)

        path = _settings_path()
        temporary = path.with_suffix(".tmp")

        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2, sort_keys=True)

        temporary.replace(path)


def set_setting(section: str, key: str, value: Any) -> dict[str, Any]:
    with _LOCK:
        current = _load_persisted()
        target = current.setdefault(section, {})
        target[key] = value
        save_settings(current)
        return get_settings()
