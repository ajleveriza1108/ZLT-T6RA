from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

UUID_RE = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
)

RECOVERY_COMMAND_TERMS = (
    "BOOT",
    "RECOV",
    "RESTORE",
    "BACKUP",
    "DUMP",
    "PART",
    "FLASH",
    "UPGRADE",
    "UPDATE",
    "FOTA",
    "FILE",
    "FS",
    "NV",
    "NVR",
    "DIAG",
    "LOAD",
    "DOWNLOAD",
    "SECURE",
    "VERIFY",
    "SIGN",
    "ROOT",
)

HIGH_RISK_COMMAND_TERMS = (
    "WRITE",
    "ERASE",
    "FLASH",
    "FORMAT",
    "RESET",
    "REBOOT",
    "UPGRADE",
    "DOWNLOAD",
    "LOAD",
    "SET",
)

def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default

def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")

def provenance(source: str, project: Path, backup: Path) -> str:
    s = source.replace("\\", "/").lower()
    p = str(project).replace("\\", "/").lower()
    b = str(backup).replace("\\", "/").lower()

    if s.startswith((b + "/03_webui_program").lower()):
        return "ORIGINAL_DEVICE_WEBUI_CAPTURE"

    if "/02_firmware/analysis_existing/" in s:
        return "PRIOR_DEVICE_ANALYSIS_CAPTURE"

    if "/08_authenticated_backup/" in s:
        return "AUTHENTICATED_DEVICE_CAPTURE"

    if s.startswith(p):
        if "/docs/" in s:
            return "PROJECT_DOCUMENTATION"
        if "/apps/network-lab/" in s:
            return "PROJECT_APPLICATION_CODE"
        return "PROJECT_SOURCE"

    return "OTHER"

def read_source_context(source: str, needle: str) -> dict[str, Any]:
    path = Path(source)

    if not path.exists() or not path.is_file():
        return {
            "available": False,
            "reason": "source file does not exist locally",
        }

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {
            "available": False,
            "reason": str(exc),
        }

    index = text.lower().find(needle.lower())

    if index < 0:
        return {
            "available": True,
            "found": False,
        }

    left = max(0, index - 5000)
    right = min(len(text), index + len(needle) + 5000)
    context = text[left:right]

    methods = sorted(set(
        m.group(1).upper()
        for m in re.finditer(
            r"""(?i)\b(?:method|type)\s*[:=]\s*["']?(GET|POST|PUT|DELETE|PATCH)["']?""",
            context,
        )
    ))

    nearby_routes = sorted(set(
        m.group(1)
        for m in re.finditer(
            r"""["'](/[A-Za-z0-9_./?=&%{}:-]{2,240})["']""",
            context,
        )
    ))

    nearby_words = sorted(set(
        word.lower()
        for word in (
            "recovery", "rollback", "restore", "fota", "firmware",
            "upgrade", "signature", "verify", "rootlogin",
            "download", "upload", "bootloader", "partition",
        )
        if word in context.lower()
    ))

    return {
        "available": True,
        "found": True,
        "offset": index,
        "methods_nearby": methods,
        "routes_nearby": nearby_routes[:100],
        "keywords_nearby": nearby_words,
        "context": re.sub(r"\s+", " ", context)[:12000],
    }

def extract_clac_commands(text: str) -> list[str]:
    commands = set()

    for line in text.splitlines():
        value = line.strip()

        if not value:
            continue

        for token in re.findall(r"AT[\^\+\%&$#A-Z0-9_=-]+", value.upper()):
            if token == "AT":
                continue
            commands.add(token)

    return sorted(commands)

def categorize_commands(commands: list[str]) -> list[dict[str, Any]]:
    rows = []

    for command in commands:
        upper = command.upper()
        matches = [
            term for term in RECOVERY_COMMAND_TERMS
            if term in upper
        ]

        if not matches:
            continue

        risk_terms = [
            term for term in HIGH_RISK_COMMAND_TERMS
            if term in upper
        ]

        rows.append({
            "command_name": command,
            "matched_terms": matches,
            "risk_terms": risk_terms,
            "action": "DO_NOT_EXECUTE_AUTOMATICALLY",
        })

    return rows

def serial_focus(recovery_access: dict[str, Any]) -> dict[str, Any]:
    serial = recovery_access.get("serial", {})
    ports = serial.get("ports", []) if isinstance(serial, dict) else []
    responsive = [
        row for row in ports
        if isinstance(row, dict) and row.get("responsive")
    ]

    result = {
        "responsive_count": len(responsive),
        "ports": [],
    }

    for row in responsive:
        queries = row.get("queries", {}) if isinstance(row.get("queries"), dict) else {}
        clac = str(queries.get("AT^CLAC", ""))
        commands = extract_clac_commands(clac)

        result["ports"].append({
            "port": row.get("port"),
            "description": row.get("description"),
            "manufacturer": row.get("manufacturer"),
            "product": row.get("product"),
            "interface": row.get("interface"),
            "hwid": row.get("hwid"),
            "identity": {
                "ATI": queries.get("ATI"),
                "AT+CGMI": queries.get("AT+CGMI"),
                "AT+CGMM": queries.get("AT+CGMM"),
                "AT+CGMR": queries.get("AT+CGMR"),
                "AT+CFUN?": queries.get("AT+CFUN?"),
            },
            "clac_command_count": len(commands),
            "recovery_related_command_names": categorize_commands(commands),
        })

    return result

def classify_uuid_candidate(candidate: dict[str, Any], project: Path, backup: Path) -> dict[str, Any]:
    uuid = str(candidate.get("uuid", ""))
    source = str(candidate.get("source", ""))
    prov = provenance(source, project, backup)
    context = read_source_context(source, uuid)

    original_weight = {
        "ORIGINAL_DEVICE_WEBUI_CAPTURE": 100,
        "AUTHENTICATED_DEVICE_CAPTURE": 100,
        "PRIOR_DEVICE_ANALYSIS_CAPTURE": 80,
        "PROJECT_APPLICATION_CODE": 20,
        "PROJECT_DOCUMENTATION": 0,
        "PROJECT_SOURCE": 10,
        "OTHER": 5,
    }.get(prov, 0)

    methods = set(candidate.get("methods_nearby") or [])
    methods.update(context.get("methods_nearby") or [])

    keywords = set(context.get("keywords_nearby") or [])
    candidate_context = str(candidate.get("context", "")).lower()

    for word in (
        "recovery", "rollback", "restore", "fota", "firmware",
        "upgrade", "signature", "verify", "rootlogin",
        "download", "upload", "bootloader", "partition",
    ):
        if word in candidate_context:
            keywords.add(word)

    dangerous = bool(
        {"upload"} & keywords
        or any(method in {"PUT", "DELETE", "PATCH"} for method in methods)
    )

    confidence = "LOW"
    if original_weight >= 80 and keywords:
        confidence = "HIGH"
    elif original_weight >= 20 and keywords:
        confidence = "MEDIUM"

    return {
        "uuid": uuid,
        "source": source,
        "provenance": prov,
        "confidence": confidence,
        "methods_nearby": sorted(methods),
        "keywords_nearby": sorted(keywords),
        "dangerous_write_context": dangerous,
        "source_context": context,
    }

def write_report(output: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Focused Recovery Mapper",
        "",
        "## WebUI recovery UUID",
        "",
    ]

    uuid_rows = result["uuid_candidates"]

    if not uuid_rows:
        lines.append("No recovery UUID candidates survived focused analysis.")
    else:
        for row in uuid_rows:
            lines.extend([
                f"- UUID: `{row['uuid']}`",
                f"- Provenance: **{row['provenance']}**",
                f"- Confidence: **{row['confidence']}**",
                f"- Nearby methods: `{', '.join(row['methods_nearby']) or 'none proven'}`",
                f"- Nearby keywords: `{', '.join(row['keywords_nearby']) or 'none'}`",
                f"- Write-context warning: **{row['dangerous_write_context']}**",
                "",
            ])

    lines.extend([
        "## Responsive serial interface",
        "",
        f"Responsive interfaces: **{result['serial']['responsive_count']}**",
        "",
    ])

    for port in result["serial"]["ports"]:
        lines.extend([
            f"### `{port.get('port')}`",
            "",
            f"- Description: `{port.get('description')}`",
            f"- Interface: `{port.get('interface')}`",
            f"- CLAC command count: **{port.get('clac_command_count')}**",
            f"- Recovery/readback-looking command names: **{len(port.get('recovery_related_command_names', []))}**",
            "",
        ])

        for command in port.get("recovery_related_command_names", []):
            lines.append(
                f"- `{command['command_name']}` — terms: "
                f"{', '.join(command['matched_terms'])}; "
                f"automatic execution: **disabled**"
            )

    lines.extend([
        "",
        "## Decision",
        "",
        result["decision"],
        "",
        "No unknown recovery-looking AT command was executed. "
        "No WebUI recovery UUID was invoked by this mapper.",
        "",
    ])

    (output / "FOCUSED_RECOVERY_REPORT.md").write_text(
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
    output = backup / "10_focused_recovery_mapper"
    output.mkdir(parents=True, exist_ok=True)

    v16 = load_json(
        backup / "09_recovery_readback_mapper" / "recovery_access.json",
        {},
    )

    static_map = (
        v16.get("static_recovery_map", {})
        if isinstance(v16, dict)
        else {}
    )

    candidates = (
        static_map.get("uuid_candidates", [])
        if isinstance(static_map, dict)
        else []
    )

    focused_uuids = [
        classify_uuid_candidate(row, project, backup)
        for row in candidates
        if isinstance(row, dict) and UUID_RE.fullmatch(str(row.get("uuid", "")))
    ]

    serial = serial_focus(v16)

    genuine_device_uuids = [
        row for row in focused_uuids
        if row["provenance"] in {
            "ORIGINAL_DEVICE_WEBUI_CAPTURE",
            "AUTHENTICATED_DEVICE_CAPTURE",
            "PRIOR_DEVICE_ANALYSIS_CAPTURE",
        }
        and row["confidence"] in {"HIGH", "MEDIUM"}
    ]

    serial_candidates = sum(
        len(port.get("recovery_related_command_names", []))
        for port in serial.get("ports", [])
    )

    if genuine_device_uuids:
        decision = (
            "Primary next lead: inspect the original-device WebUI recovery UUID "
            "context and reconstruct its exact read/status semantics. Do not invoke "
            "write/upgrade/recovery actions until the method and parameters are proven."
        )
    elif serial_candidates:
        decision = (
            "The WebUI UUID lead appears weak or project-derived. Primary next lead: "
            "classify the recovery/readback-looking AT command names from AT^CLAC "
            "using documentation/static evidence before executing any of them."
        )
    else:
        decision = (
            "Neither focused software lead currently exposes a proven readback path. "
            "Do not flash. The next stage is physical recovery/interface research."
        )

    result = {
        "uuid_candidates": focused_uuids,
        "serial": serial,
        "genuine_device_uuid_count": len(genuine_device_uuids),
        "serial_recovery_name_count": serial_candidates,
        "decision": decision,
        "safety": {
            "webui_uuid_invoked": False,
            "unknown_at_command_executed": False,
            "reboot_performed": False,
            "firmware_written": False,
            "partition_written": False,
        },
    }

    dump_json(output / "focused_recovery.json", result)
    write_report(output, result)

    print(json.dumps({
        "uuid_candidates_total": len(focused_uuids),
        "genuine_device_uuid_count": len(genuine_device_uuids),
        "serial_responsive_ports": serial.get("responsive_count", 0),
        "serial_recovery_name_count": serial_candidates,
        "decision": decision,
        "report": str(output / "FOCUSED_RECOVERY_REPORT.md"),
    }, indent=2))

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
