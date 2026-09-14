from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

_LOCK = Lock()
_MEMORY: list[dict[str, Any]] = []
_MAX_MEMORY = 1000


def _repo_root() -> Path:
    # app/services/telemetry.py -> backend -> network-lab -> apps -> repo
    return Path(__file__).resolve().parents[5]


def _csv_path() -> Path:
    root = _repo_root() / "captures"
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
    with _LOCK:
        _MEMORY.append(sample)
        del _MEMORY[:-_MAX_MEMORY]

        path = _csv_path()
        new_file = not path.exists()

        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(sample.keys()))
            if new_file:
                writer.writeheader()
            writer.writerow(sample)


def read_samples(limit: int = 120) -> list[dict[str, Any]]:
    limit = max(1, min(1000, limit))

    with _LOCK:
        if _MEMORY:
            return list(_MEMORY[-limit:])

        path = _csv_path()
        if not path.exists():
            return []

        try:
            with path.open("r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except Exception:
            return []

    # restore simple types for the frontend
    cooked: list[dict[str, Any]] = []
    for row in rows[-limit:]:
        cooked.append(
            {
                "timestamp": row.get("timestamp", ""),
                "operator": row.get("operator", "Unknown"),
                "rat": row.get("rat", "Unknown"),
                "csq": int(row["csq"]) if row.get("csq", "").isdigit() else None,
                "registered": row.get("registered") == "True",
                "packet_attached": row.get("packet_attached") == "True",
                "pdp_active": row.get("pdp_active") == "True",
                "apn": row.get("apn") or None,
            }
        )
    return cooked
