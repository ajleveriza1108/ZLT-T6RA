from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

MAX_TEXT_BYTES = 16 * 1024 * 1024
CHUNK = 4 * 1024 * 1024

RECOVERY_TERMS = (
    "recovery",
    "rollback",
    "restore",
    "rescue",
    "bootloader",
    "fastboot",
    "adb",
    "download mode",
    "downloadmode",
    "usbloader",
    "loader",
    "emergency",
    "failsafe",
    "factory",
    "systemupgrade",
    "system upgrade",
    "local upgrade",
    "localupgrade",
    "fota",
    "upgrade",
    "swupdate",
    "signature",
    "verify",
    "secure boot",
    "secureboot",
    "rootfs",
    "squashfs",
    "ubi",
    "ubifs",
    "partition",
    "boot",
    "rootlogin",
    "diag",
    "balong",
)

ROUTE_RE = re.compile(
    r"""(?i)(?:["'])(/[A-Za-z0-9_./?=&%{}:-]{2,240})(?:["'])"""
)
UUID_RE = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
)
METHOD_RE = re.compile(
    r"""(?i)\b(?:method|type)\s*[:=]\s*["']?(GET|POST|PUT|DELETE|PATCH)["']?"""
)

SENSITIVE_RE = [
    (
        re.compile(
            r"(?i)\b(imei|imsi|iccid|serial(?:number)?|sn)\s*[:=]\s*([A-Za-z0-9_-]+)"
        ),
        r"\1=[REDACTED]",
    ),
    (re.compile(r"\b\d{14,20}\b"), "[REDACTED_LONG_ID]"),
]


def sanitize(text: str) -> str:
    value = text

    for pattern, replacement in SENSITIVE_RE:
        value = pattern.sub(replacement, value)

    return value


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def hash_file(path: Path) -> dict[str, str]:
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()

    with path.open("rb") as handle:
        while True:
            block = handle.read(CHUNK)

            if not block:
                break

            sha256.update(block)
            sha512.update(block)

    return {
        "sha256": sha256.hexdigest(),
        "sha512": sha512.hexdigest(),
    }


def run(command: list[str], timeout: int = 10) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )

        return {
            "returncode": completed.returncode,
            "stdout": sanitize(completed.stdout or ""),
            "stderr": sanitize(completed.stderr or ""),
        }

    except Exception as exc:
        return {
            "error": str(exc),
        }


def project_serial_settings(project: Path) -> dict[str, Any]:
    defaults = load_json(
        project / "apps" / "network-lab" / "config" / "defaults.json",
        {},
    )

    serial_cfg = (
        defaults.get("serial", {})
        if isinstance(defaults, dict)
        else {}
    )

    return {
        "baudrate": int(serial_cfg.get("baudrate", 115200)),
        "read_timeout_seconds": float(
            serial_cfg.get("read_timeout_seconds", 0.35)
        ),
        "write_timeout_seconds": float(
            serial_cfg.get("write_timeout_seconds", 2.0)
        ),
        "query_timeout_seconds": float(
            serial_cfg.get("query_timeout_seconds", 4.5)
        ),
    }


def serial_probe(project: Path) -> dict[str, Any]:
    settings = project_serial_settings(project)

    result: dict[str, Any] = {
        "settings_source": "apps/network-lab/config/defaults.json",
        "settings": settings,
        "ports": [],
    }

    try:
        import serial
        from serial.tools import list_ports
    except Exception as exc:
        result["error"] = f"pyserial unavailable: {exc}"
        return result

    def query(port: str, command: str, timeout: float) -> str:
        with serial.Serial(
            port=port,
            baudrate=settings["baudrate"],
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=settings["read_timeout_seconds"],
            write_timeout=settings["write_timeout_seconds"],
            rtscts=False,
            dsrdtr=False,
        ) as handle:
            handle.dtr = True
            handle.rts = False
            handle.reset_input_buffer()
            handle.reset_output_buffer()
            handle.write((command + "\r").encode("ascii"))

            deadline = time.monotonic() + timeout
            chunks: list[str] = []
            last_rx = time.monotonic()

            while time.monotonic() < deadline:
                data = handle.read(4096)

                if data:
                    chunks.append(
                        data.decode("ascii", errors="replace")
                    )
                    last_rx = time.monotonic()

                joined = "".join(chunks)

                terminal = (
                    "\r\nOK\r\n" in joined
                    or "\r\nERROR\r\n" in joined
                    or "+CME ERROR:" in joined
                    or "COMMAND NOT SUPPORT" in joined
                )

                if terminal and time.monotonic() - last_rx > 0.15:
                    break

            return sanitize("".join(chunks).strip())

    commands = (
        "AT",
        "ATI",
        "AT+CGMI",
        "AT+CGMM",
        "AT+CGMR",
        "AT+CFUN?",
        "AT^CLAC",
    )

    for info in list_ports.comports():
        row: dict[str, Any] = {
            "port": info.device,
            "description": info.description,
            "manufacturer": info.manufacturer,
            "product": info.product,
            "interface": info.interface,
            "hwid": info.hwid,
            "responsive": False,
            "queries": {},
        }

        try:
            attention = query(
                info.device,
                "AT",
                min(2.0, settings["query_timeout_seconds"]),
            )
            row["queries"]["AT"] = attention

            if "OK" not in attention.upper():
                result["ports"].append(row)
                continue

            row["responsive"] = True

            for command in commands[1:]:
                try:
                    row["queries"][command] = query(
                        info.device,
                        command,
                        settings["query_timeout_seconds"],
                    )
                except Exception as exc:
                    row["queries"][command] = (
                        f"HOST_ERROR: {exc}"
                    )

        except Exception as exc:
            row["error"] = str(exc)

        result["ports"].append(row)

    return result


def adb_survey() -> dict[str, Any]:
    adb = shutil.which("adb")

    result: dict[str, Any] = {
        "available": bool(adb),
        "state": None,
        "devices": None,
        "read_only_shell": {},
    }

    if not adb:
        return result

    devices = run([adb, "devices", "-l"])
    result["devices"] = devices

    state = run([adb, "get-state"])
    result["state"] = (state.get("stdout") or "").strip()

    if result["state"] != "device":
        return result

    safe_shell = {
        "id": "id",
        "proc_partitions": "cat /proc/partitions",
        "proc_mtd": "cat /proc/mtd",
        "mounts": "cat /proc/mounts",
        "block_by_name": (
            "ls -la /dev/block/by-name 2>/dev/null; "
            "ls -la /dev/block/platform/*/by-name 2>/dev/null"
        ),
        "mtd_nodes": "ls -la /dev/mtd* 2>/dev/null",
    }

    for key, shell_command in safe_shell.items():
        result["read_only_shell"][key] = run(
            [adb, "shell", shell_command]
        )

    return result


def fastboot_survey() -> dict[str, Any]:
    fastboot = shutil.which("fastboot")

    result: dict[str, Any] = {
        "available": bool(fastboot),
        "devices": None,
        "getvar_all": None,
    }

    if not fastboot:
        return result

    devices = run([fastboot, "devices"])
    result["devices"] = devices

    if (devices.get("stdout") or "").strip():
        result["getvar_all"] = run(
            [fastboot, "getvar", "all"],
            timeout=8,
        )

    return result


def iter_text_files(roots: list[Path]):
    seen: set[Path] = set()

    for root in roots:
        if not root.exists():
            continue

        if root.is_file():
            candidates = [root]
        else:
            candidates = root.rglob("*")

        for path in candidates:
            if not path.is_file():
                continue

            try:
                resolved = path.resolve()
            except Exception:
                continue

            if resolved in seen:
                continue

            seen.add(resolved)

            try:
                size = path.stat().st_size
            except Exception:
                continue

            if size <= 0 or size > MAX_TEXT_BYTES:
                continue

            suffix = path.suffix.lower()

            if suffix not in {
                ".js", ".mjs", ".html", ".htm", ".css",
                ".json", ".txt", ".map", ".md", ".py",
            }:
                continue

            yield path


def text_recovery_map(
    project: Path,
    backup: Path,
) -> dict[str, Any]:
    roots = [
        backup / "03_webui_program",
        backup / "02_firmware" / "analysis_existing",
        backup / "08_authenticated_backup",
        project / "apps" / "network-lab",
        project / "docs",
    ]

    hits: list[dict[str, Any]] = []
    uuids: dict[str, dict[str, Any]] = {}
    routes: dict[str, dict[str, Any]] = {}
    scanned = 0

    for path in iter_text_files(roots):
        scanned += 1

        try:
            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            continue

        low = text.lower()

        if not any(term in low for term in RECOVERY_TERMS):
            continue

        source = str(path)

        for term in RECOVERY_TERMS:
            start = 0
            term_low = term.lower()

            while len(hits) < 2000:
                index = low.find(term_low, start)

                if index < 0:
                    break

                left = max(0, index - 220)
                right = min(
                    len(text),
                    index + len(term) + 380,
                )

                context = sanitize(
                    re.sub(
                        r"\s+",
                        " ",
                        text[left:right],
                    ).strip()
                )

                hits.append({
                    "term": term,
                    "source": source,
                    "offset": index,
                    "context": context[:700],
                })

                start = index + len(term)

        for match in UUID_RE.finditer(text):
            left = max(0, match.start() - 700)
            right = min(len(text), match.end() + 700)
            context = text[left:right]
            context_low = context.lower()

            if not any(
                term in context_low
                for term in RECOVERY_TERMS
            ):
                continue

            methods = sorted(
                set(METHOD_RE.findall(context))
            )

            uuid = match.group(0).lower()
            row = {
                "uuid": uuid,
                "source": source,
                "methods_nearby": methods,
                "context": sanitize(
                    re.sub(r"\s+", " ", context)
                )[:1200],
            }

            old = uuids.get(uuid)

            if (
                old is None
                or len(row["methods_nearby"])
                > len(old["methods_nearby"])
            ):
                uuids[uuid] = row

        for match in ROUTE_RE.finditer(text):
            route = match.group(1)

            if not any(
                term.replace(" ", "") in route.lower().replace(" ", "")
                for term in RECOVERY_TERMS
                if len(term) >= 4
            ):
                continue

            routes[route] = {
                "route": route,
                "source": source,
            }

    return {
        "files_scanned": scanned,
        "keyword_hits": hits,
        "uuid_candidates": sorted(
            uuids.values(),
            key=lambda row: row["uuid"],
        ),
        "routes": sorted(
            routes.values(),
            key=lambda row: row["route"],
        ),
    }


def parse_pnp(path: Path) -> dict[str, Any]:
    rows = load_json(path, [])

    if isinstance(rows, dict):
        rows = [rows]

    interfaces = []

    if not isinstance(rows, list):
        return {
            "count": 0,
            "interfaces": [],
        }

    for row in rows:
        if not isinstance(row, dict):
            continue

        interfaces.append({
            "status": row.get("Status"),
            "class": row.get("Class"),
            "friendly_name": row.get("FriendlyName"),
            "instance_id": row.get("InstanceId"),
            "properties": row.get("Properties", {}),
        })

    return {
        "count": len(interfaces),
        "interfaces": interfaces,
    }


def candidate_paths(
    adb: dict[str, Any],
    fastboot: dict[str, Any],
    serial: dict[str, Any],
    static_map: dict[str, Any],
    pnp: dict[str, Any],
) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []

    adb_state = adb.get("state")

    if adb_state == "device":
        paths.append({
            "path": "authorized_adb_readback",
            "priority": 1,
            "status": "available",
            "reason": (
                "ADB reports device. Read-only shell partition mapping is available."
            ),
        })
    elif adb_state:
        paths.append({
            "path": "adb_authorization_or_transport",
            "priority": 2,
            "status": "blocked",
            "reason": f"ADB current state is {adb_state!r}.",
        })

    fastboot_text = ""
    if isinstance(fastboot.get("devices"), dict):
        fastboot_text = (
            fastboot["devices"].get("stdout") or ""
        ).strip()

    if fastboot_text:
        paths.append({
            "path": "fastboot_readback_recovery",
            "priority": 1,
            "status": "available",
            "reason": "A Fastboot device is currently visible.",
        })
    elif fastboot.get("available"):
        paths.append({
            "path": "fastboot_mode_discovery",
            "priority": 3,
            "status": "not_currently_exposed",
            "reason": (
                "Fastboot tooling exists but no Fastboot device is currently visible."
            ),
        })

    responsive = [
        row for row in serial.get("ports", [])
        if row.get("responsive")
    ]

    if responsive:
        paths.append({
            "path": "serial_query_channel",
            "priority": 2,
            "status": "available",
            "reason": (
                f"{len(responsive)} serial interface(s) responded to query-only AT."
            ),
        })

    recovery_uuid_count = len(
        static_map.get("uuid_candidates", [])
    )
    recovery_route_count = len(
        static_map.get("routes", [])
    )

    if recovery_uuid_count or recovery_route_count:
        paths.append({
            "path": "host_webui_recovery_logic",
            "priority": 2,
            "status": "evidence_found",
            "reason": (
                f"Saved firmware/WebUI assets contain "
                f"{recovery_uuid_count} recovery-related UUID candidate(s) "
                f"and {recovery_route_count} route candidate(s)."
            ),
        })

    if pnp.get("count", 0):
        paths.append({
            "path": "usb_interface_reclassification",
            "priority": 4,
            "status": "inventory_available",
            "reason": (
                f"{pnp['count']} relevant Windows PnP interface(s) were inventoried "
                "for driver/service/interface mapping."
            ),
        })

    return sorted(
        paths,
        key=lambda row: (
            int(row.get("priority", 99)),
            row.get("path", ""),
        ),
    )


def verify_old_manifest(backup: Path) -> dict[str, Any]:
    manifest = load_json(
        backup / "MANIFEST.json",
        [],
    )

    if not isinstance(manifest, list):
        return {
            "present": False,
            "checked": 0,
            "matched": 0,
            "changed": [],
            "missing": [],
        }

    checked = 0
    matched = 0
    changed = []
    missing = []

    for row in manifest:
        if not isinstance(row, dict):
            continue

        rel = row.get("path")
        expected = row.get("sha256")

        if not rel or not expected:
            continue

        path = backup / str(rel)

        if not path.exists():
            missing.append(str(rel))
            continue

        checked += 1
        actual = hash_file(path)["sha256"]

        if actual.lower() == str(expected).lower():
            matched += 1
        else:
            changed.append({
                "path": str(rel),
                "old_sha256": expected,
                "current_sha256": actual,
            })

    return {
        "present": True,
        "checked": checked,
        "matched": matched,
        "changed": changed,
        "missing": missing,
        "note": (
            "Changes after v13 can be expected because v15 updated backup status "
            "and added authenticated-backup outputs."
        ),
    }


def current_manifest(
    backup: Path,
) -> list[dict[str, Any]]:
    excluded_names = {
        "MANIFEST_CURRENT.json",
        "MANIFEST_SHA256_CURRENT.txt",
        "MANIFEST_SHA512_CURRENT.txt",
    }

    rows = []

    for path in sorted(backup.rglob("*")):
        if not path.is_file():
            continue

        if path.name in excluded_names:
            continue

        relative = str(path.relative_to(backup))
        digests = hash_file(path)

        rows.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": digests["sha256"],
            "sha512": digests["sha512"],
        })

    return rows


def write_current_manifest(
    backup: Path,
) -> int:
    rows = current_manifest(backup)

    dump_json(
        backup / "MANIFEST_CURRENT.json",
        rows,
    )

    (backup / "MANIFEST_SHA256_CURRENT.txt").write_text(
        "\n".join(
            f"{row['sha256']}  {row['path']}"
            for row in rows
        ) + "\n",
        encoding="ascii",
    )

    (backup / "MANIFEST_SHA512_CURRENT.txt").write_text(
        "\n".join(
            f"{row['sha512']}  {row['path']}"
            for row in rows
        ) + "\n",
        encoding="ascii",
    )

    return len(rows)


def write_report(
    output: Path,
    result: dict[str, Any],
) -> None:
    static_map = result["static_recovery_map"]
    serial = result["serial"]
    adb = result["adb"]
    fastboot = result["fastboot"]
    candidates = result["candidate_paths"]
    manifest_check = result["old_manifest_check"]

    responsive = [
        row for row in serial.get("ports", [])
        if row.get("responsive")
    ]

    lines = [
        "# T6R-A Recovery / Readback Access Report",
        "",
        "## Current backup gate",
        "",
        f"- Backup class: **{result['backup_status'].get('backup_class')}**",
        f"- Stock packages: **{result['backup_status'].get('stock_package_count', 0)}**",
        f"- Raw partition candidates: **{result['backup_status'].get('raw_partition_candidates', 0)}**",
        f"- Restore ready: **{result['backup_status'].get('full_device_restore_ready', False)}**",
        "",
        "## Current access",
        "",
        f"- ADB available: **{adb.get('available')}**",
        f"- ADB state: **{adb.get('state')}**",
        f"- Fastboot available: **{fastboot.get('available')}**",
        f"- Responsive query-only serial interfaces: **{len(responsive)}**",
        f"- Recovery-related UUID candidates in saved code: **{len(static_map.get('uuid_candidates', []))}**",
        f"- Recovery-related route candidates in saved code: **{len(static_map.get('routes', []))}**",
        "",
        "## Ranked next recovery/readback paths",
        "",
    ]

    if candidates:
        for item in candidates:
            lines.append(
                f"- **P{item['priority']} — {item['path']}**: "
                f"{item['status']} — {item['reason']}"
            )
    else:
        lines.append(
            "- No software recovery/readback path is currently exposed. "
            "Do not flash; physical recovery research is required first."
        )

    lines.extend([
        "",
        "## Backup-integrity note",
        "",
        f"- Original manifest entries checked: **{manifest_check.get('checked', 0)}**",
        f"- Still matching original v13 hashes: **{manifest_check.get('matched', 0)}**",
        f"- Changed since v13: **{len(manifest_check.get('changed', []))}**",
        f"- Missing since v13: **{len(manifest_check.get('missing', []))}**",
        "",
        "A new CURRENT manifest was generated after this mapper run. "
        "The original v13 manifest is preserved as historical evidence.",
        "",
        "## Flash decision",
        "",
        "**BLOCKED.** No experimental firmware should be flashed until a "
        "repeatable recovery/readback path is demonstrated and package/boot "
        "verification is understood.",
        "",
    ])

    (output / "RECOVERY_ACCESS_REPORT.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--backup", required=True)
    parser.add_argument("--pnp-json", required=True)
    args = parser.parse_args()

    project = Path(args.project).resolve()
    backup = Path(args.backup).resolve()
    pnp_json = Path(args.pnp_json).resolve()

    output = backup / "09_recovery_readback_mapper"
    output.mkdir(parents=True, exist_ok=True)

    backup_status = load_json(
        backup / "BACKUP_STATUS.json",
        {},
    )

    old_manifest_check = verify_old_manifest(backup)

    adb = adb_survey()
    fastboot = fastboot_survey()
    serial = serial_probe(project)
    static_map = text_recovery_map(project, backup)
    pnp = parse_pnp(pnp_json)

    paths = candidate_paths(
        adb,
        fastboot,
        serial,
        static_map,
        pnp,
    )

    result = {
        "schema": 1,
        "created_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        ),
        "backup_status": backup_status,
        "adb": adb,
        "fastboot": fastboot,
        "serial": serial,
        "pnp": pnp,
        "static_recovery_map": static_map,
        "candidate_paths": paths,
        "old_manifest_check": old_manifest_check,
        "safety": {
            "reboot_performed": False,
            "boot_mode_changed": False,
            "firmware_written": False,
            "partition_written": False,
            "nvram_written": False,
            "modem_settings_changed": False,
        },
    }

    dump_json(
        output / "recovery_access.json",
        result,
    )

    dump_json(
        output / "recovery_code_map.json",
        static_map,
    )

    write_report(
        output,
        result,
    )

    manifest_count = write_current_manifest(backup)

    summary = {
        "adb_state": adb.get("state"),
        "fastboot_device_visible": bool(
            isinstance(fastboot.get("devices"), dict)
            and (fastboot["devices"].get("stdout") or "").strip()
        ),
        "responsive_serial_ports": sum(
            1
            for row in serial.get("ports", [])
            if row.get("responsive")
        ),
        "recovery_uuid_candidates": len(
            static_map.get("uuid_candidates", [])
        ),
        "recovery_route_candidates": len(
            static_map.get("routes", [])
        ),
        "ranked_paths": paths,
        "current_manifest_entries": manifest_count,
        "flash_gate": "BLOCKED",
        "report": str(
            output / "RECOVERY_ACCESS_REPORT.md"
        ),
    }

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
