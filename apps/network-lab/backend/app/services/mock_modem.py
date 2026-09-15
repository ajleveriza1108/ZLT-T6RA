from __future__ import annotations

from copy import deepcopy
from typing import Any

from .config_loader import mock_device


def mock_summary() -> dict[str, Any]:
    value = mock_device()
    value.pop("networks", None)
    return value


def mock_networks() -> list[dict[str, Any]]:
    value = mock_device()
    networks = value.get("networks", [])
    return deepcopy(networks) if isinstance(networks, list) else []
