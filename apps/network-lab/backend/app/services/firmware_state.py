from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config_loader import repo_root


def _real_files(path: Path) -> list[Path]:
    if not path.exists():
        return []

    return [
        item
        for item in path.rglob("*")
        if item.is_file()
        and item.name != ".gitkeep"
    ]


def _json_flag(path: Path, key: str) -> bool:
    if not path.exists():
        return False

    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return bool(value.get(key))
    except Exception:
        return False


def firmware_status() -> dict[str, Any]:
    root = repo_root() / "firmware"

    original_files = _real_files(root / "original")
    image_present = bool(original_files)

    verification_manifest = root / "analysis" / "verification.json"
    verification_pass = _json_flag(
        verification_manifest,
        "verified",
    )

    recovery_manifest = root / "recovery" / "recovery_verified.json"
    recovery_pass = _json_flag(
        recovery_manifest,
        "verified",
    )

    patch_files = _real_files(root / "patches")
    prerequisites_pass = (
        image_present
        and verification_pass
        and recovery_pass
    )

    return {
        "flashing_enabled": prerequisites_pass and bool(patch_files),
        "current_track": (
            "Patch validation"
            if prerequisites_pass
            else "Offline acquisition / recovery preparation"
        ),
        "gates": [
            {
                "id": "baseline",
                "title": "Known-good baseline",
                "status": "pass",
                "detail": "Project baseline is established.",
            },
            {
                "id": "image",
                "title": "Factory image / verified dump",
                "status": "pass" if image_present else "pending",
                "detail": (
                    f"{len(original_files)} preserved file(s) detected."
                    if image_present
                    else "No preserved firmware/dump file detected yet."
                ),
            },
            {
                "id": "verify",
                "title": "Package / signature verification",
                "status": "pass" if verification_pass else "pending",
                "detail": (
                    str(verification_manifest)
                    if verification_pass
                    else "Create firmware/analysis/verification.json with verified=true after validation."
                ),
            },
            {
                "id": "recovery",
                "title": "Proven recovery path",
                "status": "pass" if recovery_pass else "pending",
                "detail": (
                    str(recovery_manifest)
                    if recovery_pass
                    else "Create firmware/recovery/recovery_verified.json with verified=true only after recovery is proven."
                ),
            },
            {
                "id": "patch",
                "title": "Candidate patch",
                "status": (
                    "pass"
                    if prerequisites_pass and patch_files
                    else ("pending" if prerequisites_pass else "blocked")
                ),
                "detail": (
                    f"{len(patch_files)} patch artifact(s) detected."
                    if patch_files
                    else "No candidate patch artifact detected."
                ),
            },
        ],
    }
