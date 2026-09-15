from __future__ import annotations

import csv
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from .config_loader import repo_root
from .settings_store import get_settings

_LOCK = Lock()
_MEMORY: list[dict[str, Any]] = []


def _csv_path():
    root = repo_root() / "captures"
    root.mkdir(parents=True, exist_ok=True)
    return root / "telemetry.csv"


def make_sample(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operator": summary.get("operator", "Unknown"),
        "rat": summary.get("rat", "Unknown"),
        "csq": summary.get("csq"),
        "registered": bool(summary.get("registered")),
        "packet_attached": bool(summary.get("packet_attached")),
        "pdp_active": bool(summary.get("pdp_active")),
        "apn": summary.get("apn"),
    }


def append_sample(sample: dict[str, Any]) -> None:
    memory_limit = int(
        get_settings()
        .get("telemetry", {})
        .get("memory_limit", 1000)
    )

    with _LOCK:
        _MEMORY.append(sample)

        if memory_limit > 0:
            del _MEMORY[:-memory_limit]

        path = _csv_path()
        new_file = not path.exists()

        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(sample.keys()),
            )

            if new_file:
                writer.writeheader()

            writer.writerow(sample)


def read_samples(limit: int = 120) -> list[dict[str, Any]]:
    limit = max(1, limit)

    with _LOCK:
        if _MEMORY:
            return list(_MEMORY[-limit:])

        path = _csv_path()

        if not path.exists():
            return []

        try:
            with path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as handle:
                rows = list(csv.DictReader(handle))
        except Exception:
            return []

    cooked: list[dict[str, Any]] = []

    for row in rows[-limit:]:
        csq_text = row.get("csq", "")
        cooked.append(
            {
                "timestamp": row.get("timestamp", ""),
                "operator": row.get("operator", "Unknown"),
                "rat": row.get("rat", "Unknown"),
                "csq": (
                    int(csq_text)
                    if csq_text and csq_text.lstrip("-").isdigit()
                    else None
                ),
                "registered": row.get("registered") == "True",
                "packet_attached": row.get("packet_attached") == "True",
                "pdp_active": row.get("pdp_active") == "True",
                "apn": row.get("apn") or None,
            }
        )

    return cooked
