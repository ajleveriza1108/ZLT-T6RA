from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def network_lab_root() -> Path:
    return Path(__file__).resolve().parents[3]


def config_dir() -> Path:
    return network_lab_root() / "config"


def load_json_config(filename: str) -> dict[str, Any]:
    path = config_dir() / filename

    if not path.exists():
        raise FileNotFoundError(f"Required configuration file is missing: {path}")

    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)

    if not isinstance(value, dict):
        raise ValueError(f"Configuration must be a JSON object: {path}")

    return value


def app_metadata() -> dict[str, Any]:
    return load_json_config("app.json")


def defaults() -> dict[str, Any]:
    return load_json_config("defaults.json")


def query_commands() -> dict[str, str]:
    value = load_json_config("query_commands.json")
    return {str(k): str(v) for k, v in value.items()}


def mock_device() -> dict[str, Any]:
    return deepcopy(load_json_config("mock_device.json"))
