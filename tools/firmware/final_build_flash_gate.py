from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

FIRMWARE_EXTS = {
    ".pac", ".bin", ".img", ".swu", ".tar", ".zip", ".rom", ".dump",
    ".ubi", ".ubifs", ".squashfs", ".gz", ".xz", ".bz2"
}

ROOTFS_HINTS = (
    "rootfs", "system", "squashfs", "ubifs", "ubi", "filesystem"
)

POLICY_TERMS = (
    "lock_plmn_flag",
    "lock_plmn_switch",
    "lockPlmn",
    "plmnLock",
    "LIMITED_ACCESS",
    "CFUN=0",
    "network_status",
    "network_operator",
    "networkState",
)

def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default

def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")

def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(4 * 1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def collect_firmware_candidates(project: Path, backup: Path) -> list[dict[str, Any]]:
    roots = [
        project / "firmware" / "original",
        backup / "02_firmware",
        backup / "06_raw_flash" / "partitions",
        backup / "08_authenticated_backup" / "artifacts",
    ]

    rows = []
    seen = set()

    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in FIRMWARE_EXTS and "partition" not in path.name.lower():
                continue
            try:
                resolved = path.resolve()
            except Exception:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            rows.append({
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": hash_file(path),
            })

    return rows

def collect_extracted_candidates(project: Path, backup: Path) -> list[dict[str, Any]]:
    roots = [
        project / "firmware" / "analysis" / "extracted",
        backup / "02_firmware" / "analysis_existing" / "extracted",
    ]
    rows = []

    for root in roots:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            low = path.name.lower()
            if any(hint in low for hint in ROOTFS_HINTS):
                rows.append({
                    "path": str(path),
                    "reason": "name_hint",
                })

    return rows

def search_policy_terms(project: Path, backup: Path) -> list[dict[str, Any]]:
    roots = [
        project / "firmware" / "analysis" / "extracted",
        backup / "02_firmware" / "analysis_existing" / "extracted",
    ]
    hits = []
    max_file = 32 * 1024 * 1024

    for root in roots:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            try:
                size = path.stat().st_size
            except Exception:
                continue

            if size <= 0 or size > max_file:
                continue

            try:
                data = path.read_bytes()
            except Exception:
                continue

            for term in POLICY_TERMS:
                needle = term.encode("utf-8", errors="ignore")
                index = data.find(needle)
                if index < 0:
                    continue

                left = max(0, index - 128)
                right = min(len(data), index + len(needle) + 256)
                context = data[left:right].decode("utf-8", errors="replace")

                hits.append({
                    "term": term,
                    "path": str(path),
                    "offset": index,
                    "context": re.sub(r"\s+", " ", context)[:500],
                })

    return hits

def build_gates(backup_status: dict[str, Any], firmware_candidates: list[dict[str, Any]], rootfs_candidates: list[dict[str, Any]], policy_hits: list[dict[str, Any]], backup: Path) -> dict[str, Any]:
    full_raw = bool(backup_status.get("full_raw_dump_complete", False))
    stock_count = int(backup_status.get("stock_package_count", 0) or 0)
    restore_proven = bool(backup_status.get("restore_procedure_proven", False))

    physical_report = backup / "11_physical_recovery_recon" / "PHYSICAL_RECOVERY_RECON_REPORT.md"
    physical_done = physical_report.exists()

    gates = {
        "baseline_backup_present": True,
        "physical_recovery_recon_completed": physical_done,
        "stock_package_or_full_raw_backup": bool(stock_count > 0 or full_raw or firmware_candidates),
        "rootfs_or_host_filesystem_identified": bool(rootfs_candidates),
        "operator_policy_location_identified": bool(policy_hits),
        "package_boot_verification_understood": False,
        "recovery_restore_proven": restore_proven,
        "candidate_patch_built": False,
        "offline_rebuild_verified": False,
        "flash_ready": False,
    }

    gates["flash_ready"] = all([
        gates["stock_package_or_full_raw_backup"],
        gates["rootfs_or_host_filesystem_identified"],
        gates["operator_policy_location_identified"],
        gates["package_boot_verification_understood"],
        gates["recovery_restore_proven"],
        gates["candidate_patch_built"],
        gates["offline_rebuild_verified"],
    ])

    return gates

def write_plan(out: Path, gates: dict[str, Any]) -> None:
    lines = [
        "# Final T6R-A Firmware Build / Flash Plan",
        "",
        "## Current gate state",
        "",
    ]

    for name, value in gates.items():
        lines.append(f"- `{name}`: **{value}**")

    lines.extend([
        "",
        "## Final sequence",
        "",
        "1. Obtain either the exact stock firmware package or a verified full raw flash backup.",
        "2. Prove a repeatable recovery/restore path before experimental flashing.",
        "3. Identify the actual host Linux root filesystem/partition.",
        "4. Locate the operator-policy logic that forces non-DITO rejection/CFUN0/WAN suppression.",
        "5. Build the smallest host-only patch; do not modify bootloader, Balong baseband, calibration, IMEI, or partition table.",
        "6. Repack/rebuild offline and verify hashes/package structure/signature behavior.",
        "7. Perform one controlled flash only after recovery is proven.",
        "8. Cold-boot test with the PC disconnected.",
        "9. Acceptance: SIM detection -> CFUN1 -> registration -> APN -> PDP/WAN -> DNS/NAT -> Wi-Fi/LAN Internet.",
        "",
        "## Current decision",
        "",
    ])

    if gates["flash_ready"]:
        lines.append("All gates are satisfied. Controlled flash can proceed.")
    elif not gates["stock_package_or_full_raw_backup"]:
        lines.append(
            "**BLOCKED:** no stock package or full raw flash backup exists yet. "
            "The next action is physical recovery/readback identification from PCB evidence."
        )
    elif not gates["recovery_restore_proven"]:
        lines.append(
            "**BLOCKED:** backup material exists but recovery/restore is not yet proven."
        )
    else:
        lines.append(
            "**BLOCKED:** additional build/verification gates remain."
        )

    (out / "FINAL_BUILD_FLASH_PLAN.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--backup", required=True)
    args = parser.parse_args()

    project = Path(args.project).resolve()
    backup = Path(args.backup).resolve()
    out = backup / "12_final_build_flash_gate"
    out.mkdir(parents=True, exist_ok=True)

    backup_status = load_json(backup / "BACKUP_STATUS.json", {})
    firmware_candidates = collect_firmware_candidates(project, backup)
    rootfs_candidates = collect_extracted_candidates(project, backup)
    policy_hits = search_policy_terms(project, backup)

    gates = build_gates(
        backup_status,
        firmware_candidates,
        rootfs_candidates,
        policy_hits,
        backup,
    )

    result = {
        "backup_status": backup_status,
        "firmware_candidates": firmware_candidates,
        "rootfs_candidates": rootfs_candidates,
        "operator_policy_hits": policy_hits,
        "gates": gates,
        "next_required_action": (
            "PCB_PHOTOS_AND_PHYSICAL_RECOVERY_IDENTIFICATION"
            if not gates["stock_package_or_full_raw_backup"]
            else "RECOVERY_PROOF_AND_OFFLINE_BUILD"
        ),
        "safety": {
            "flash_executed": False,
            "partition_written": False,
            "bootloader_written": False,
            "baseband_written": False,
            "nvram_written": False,
        },
    }

    dump_json(out / "FLASH_READINESS.json", result)
    write_plan(out, gates)

    print(json.dumps({
        "flash_ready": gates["flash_ready"],
        "stock_package_or_full_raw_backup": gates["stock_package_or_full_raw_backup"],
        "rootfs_identified": gates["rootfs_or_host_filesystem_identified"],
        "operator_policy_identified": gates["operator_policy_location_identified"],
        "recovery_restore_proven": gates["recovery_restore_proven"],
        "next_required_action": result["next_required_action"],
        "report": str(out / "FINAL_BUILD_FLASH_PLAN.md"),
    }, indent=2))

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
