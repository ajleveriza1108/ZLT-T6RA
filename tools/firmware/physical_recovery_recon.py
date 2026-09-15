from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

USB_HWID_RE = re.compile(
    r"(?i)USB\\VID_([0-9A-F]{4})&PID_([0-9A-F]{4})(?:&MI_([0-9A-F]{2}))?"
)

RECOVERY_WORDS = (
    "download",
    "loader",
    "boot",
    "fastboot",
    "adb",
    "diag",
    "diagnostic",
    "recovery",
    "emergency",
    "factory",
    "flash",
)

def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default

def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")

def normalize_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    return []

def extract_hwid_candidates(row: dict[str, Any]) -> list[str]:
    values = []
    instance = str(row.get("InstanceId", ""))
    if instance:
        values.append(instance)

    props = row.get("Properties", {})
    if isinstance(props, dict):
        for key in (
            "DEVPKEY_Device_HardwareIds",
            "DEVPKEY_Device_CompatibleIds",
        ):
            value = props.get(key)
            if isinstance(value, list):
                values.extend(str(x) for x in value)
            elif value:
                values.append(str(value))

    return values

def device_usb_identity(row: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    seen = set()

    for value in extract_hwid_candidates(row):
        for m in USB_HWID_RE.finditer(value):
            key = (m.group(1).upper(), m.group(2).upper(), (m.group(3) or "").upper())
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "vid": key[0],
                "pid": key[1],
                "mi": key[2] or None,
            })

    return found

def present_interface_map(rows: list[dict[str, Any]]) -> dict[str, Any]:
    interfaces = []
    parent_pairs: dict[tuple[str,str], list[dict[str,Any]]] = {}

    for row in rows:
        identities = device_usb_identity(row)
        if not identities:
            continue

        props = row.get("Properties", {})
        if not isinstance(props, dict):
            props = {}

        for ident in identities:
            item = {
                "vid": ident["vid"],
                "pid": ident["pid"],
                "mi": ident["mi"],
                "friendly_name": row.get("FriendlyName"),
                "class": row.get("Class"),
                "status": row.get("Status"),
                "service": props.get("DEVPKEY_Device_Service"),
                "driver_inf": props.get("DEVPKEY_Device_DriverInfPath"),
                "driver_provider": props.get("DEVPKEY_Device_DriverProvider"),
                "driver_version": props.get("DEVPKEY_Device_DriverVersion"),
                "bus_description": props.get("DEVPKEY_Device_BusReportedDeviceDesc"),
                "location_paths": props.get("DEVPKEY_Device_LocationPaths"),
            }
            interfaces.append(item)
            parent_pairs.setdefault((ident["vid"], ident["pid"]), []).append(item)

    scored = []
    for pair, members in parent_pairs.items():
        score = len({m.get("mi") for m in members if m.get("mi")})
        labels = " ".join(
            str(m.get("friendly_name") or "") + " " +
            str(m.get("bus_description") or "") + " " +
            str(m.get("service") or "")
            for m in members
        ).lower()
        if "modem" in labels or "diag" in labels or "rndis" in labels or "adb" in labels:
            score += 10

        scored.append({
            "vid": pair[0],
            "pid": pair[1],
            "score": score,
            "interfaces": members,
        })

    scored.sort(key=lambda x: (-x["score"], x["vid"], x["pid"]))

    return {
        "all_interfaces": interfaces,
        "candidate_composite_devices": scored,
        "primary_candidate": scored[0] if scored else None,
    }

def historical_registry_modes(
    registry_text: str,
    primary: dict[str, Any] | None,
) -> dict[str, Any]:
    if not primary:
        return {"matching_vendor_modes": [], "recovery_word_hits": []}

    vid = primary["vid"].upper()
    pattern = re.compile(
        rf"(?i)VID_{re.escape(vid)}&PID_([0-9A-F]{{4}})"
    )

    pids = sorted(set(m.group(1).upper() for m in pattern.finditer(registry_text)))

    lines = registry_text.splitlines()
    word_hits = []

    for index, line in enumerate(lines):
        low = line.lower()
        if any(word in low for word in RECOVERY_WORDS):
            left = max(0, index - 2)
            right = min(len(lines), index + 3)
            context = "\n".join(lines[left:right])
            if f"VID_{vid}" in context.upper():
                word_hits.append(context)

    return {
        "vendor_id": vid,
        "matching_vendor_modes": pids,
        "recovery_word_hits": word_hits[:100],
    }

def setupapi_relevant(
    setup_text: str,
    primary: dict[str, Any] | None,
) -> list[str]:
    if not primary:
        return []

    vid = primary["vid"].upper()
    lines = setup_text.splitlines()
    hits = []

    for i, line in enumerate(lines):
        if f"VID_{vid}" not in line.upper():
            continue
        left = max(0, i - 8)
        right = min(len(lines), i + 18)
        block = "\n".join(lines[left:right])
        hits.append(block)

    # Unique by content.
    seen = set()
    unique = []
    for block in hits:
        if block in seen:
            continue
        seen.add(block)
        unique.append(block)

    return unique[-100:]

def classify_current_interfaces(primary: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not primary:
        return []

    rows = []

    for item in primary["interfaces"]:
        text = " ".join(
            str(item.get(k) or "")
            for k in (
                "friendly_name", "class", "service",
                "driver_inf", "bus_description",
            )
        ).lower()

        role = "unknown"

        if "rndis" in text or "remote ndis" in text:
            role = "network_rndis"
        elif "adb" in text or "winusb" in text:
            role = "adb_or_winusb"
        elif "diag" in text:
            role = "diagnostic"
        elif "gps" in text or "nmea" in text:
            role = "gps_nmea"
        elif "modem" in text:
            role = "modem_or_at"
        elif item.get("class") == "Ports":
            role = "serial_port"

        rows.append({
            **item,
            "inferred_role": role,
        })

    return rows

def write_report(output: Path, result: dict[str, Any]) -> None:
    primary = result.get("primary_candidate")
    current = result.get("current_interfaces", [])
    historical = result.get("historical", {})

    lines = [
        "# T6R-A Physical Recovery Recon",
        "",
        "## Current composite USB device",
        "",
    ]

    if primary:
        lines.extend([
            f"- Vendor ID: `{primary['vid']}`",
            f"- Product ID: `{primary['pid']}`",
            f"- Composite interfaces found: **{len(primary['interfaces'])}**",
            "",
        ])

        for row in current:
            lines.append(
                f"- MI `{row.get('mi') or 'n/a'}` — "
                f"{row.get('inferred_role')} — "
                f"{row.get('friendly_name') or 'unnamed'} — "
                f"service `{row.get('service') or 'unknown'}`"
            )
    else:
        lines.append("No modem-like composite USB device could be ranked automatically.")

    lines.extend([
        "",
        "## Historical USB modes for the same vendor",
        "",
    ])

    modes = historical.get("matching_vendor_modes", [])
    if modes:
        for pid in modes:
            lines.append(f"- PID `{pid}`")
    else:
        lines.append("- No alternate product IDs were found in the captured Windows registry history.")

    lines.extend([
        "",
        "## Recovery-mode evidence",
        "",
        f"- Registry recovery-word blocks: **{len(historical.get('recovery_word_hits', []))}**",
        f"- SetupAPI blocks for the modem vendor: **{len(result.get('setupapi_blocks', []))}**",
        "",
        "## Decision",
        "",
        result["decision"],
        "",
        "## Required physical evidence before any test-point action",
        "",
        "1. Power the modem off and disconnect external power/USB.",
        "2. Open the enclosure only if you are comfortable doing so without damaging antenna/coax connectors.",
        "3. Photograph the complete PCB front and back at high resolution.",
        "4. Take close-ups of the SoC/CPU, flash/eMMC/NAND, USB connector area, unpopulated headers, and labeled test pads.",
        "5. Keep pad labels readable; include one photo showing board orientation.",
        "6. Do **not** short, bridge, ground, solder, or power any unidentified test point yet.",
        "7. Do **not** use a legacy Balong loader unless chipset compatibility is independently proven.",
        "",
        "The next stage should identify UART/USB-boot/test pads from actual PCB evidence before any electrical action.",
        "",
    ])

    (output / "PHYSICAL_RECOVERY_RECON_REPORT.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", required=True)
    args = parser.parse_args()

    backup = Path(args.backup).resolve()
    output = backup / "11_physical_recovery_recon"

    present = normalize_rows(load_json(output / "present_pnp.json", []))
    registry_text = ""
    setup_text = ""

    reg_path = output / "usb_registry_summary.txt"
    if reg_path.exists():
        registry_text = reg_path.read_text(encoding="utf-8", errors="replace")

    setup_path = output / "setupapi.dev.log"
    if setup_path.exists():
        setup_text = setup_path.read_text(encoding="utf-8", errors="replace")

    interface_map = present_interface_map(present)
    primary = interface_map.get("primary_candidate")
    current = classify_current_interfaces(primary)
    historical = historical_registry_modes(registry_text, primary)
    setup_blocks = setupapi_relevant(setup_text, primary)

    alternate_modes = [
        pid for pid in historical.get("matching_vendor_modes", [])
        if primary and pid != primary["pid"]
    ]

    recovery_registry = historical.get("recovery_word_hits", [])

    if alternate_modes and recovery_registry:
        decision = (
            "Windows history contains alternate USB product IDs for the same vendor "
            "and recovery-related registry text. Preserve this evidence and inspect the "
            "PCB before attempting any mode transition."
        )
    elif alternate_modes:
        decision = (
            "Windows history contains alternate USB product IDs for the same vendor, "
            "but their purpose is not proven. PCB inspection is now the decisive step."
        )
    else:
        decision = (
            "No proven alternate recovery USB mode is visible in Windows history. "
            "Proceed to powered-off PCB photography/test-point identification only; "
            "do not short pads yet."
        )

    result = {
        "primary_candidate": primary,
        "current_interfaces": current,
        "historical": historical,
        "setupapi_blocks": setup_blocks,
        "decision": decision,
        "safety": {
            "mode_switch_attempted": False,
            "testpoint_action_attempted": False,
            "loader_uploaded": False,
            "firmware_written": False,
            "registry_written": False,
        },
    }

    dump_json(output / "physical_recovery_recon.json", result)

    (output / "setupapi_relevant.txt").write_text(
        "\n\n====================\n\n".join(setup_blocks),
        encoding="utf-8",
    )

    write_report(output, result)

    print(json.dumps({
        "primary_vid": primary.get("vid") if primary else None,
        "primary_pid": primary.get("pid") if primary else None,
        "current_interface_count": len(current),
        "historical_vendor_pids": historical.get("matching_vendor_modes", []),
        "alternate_pid_count": len(alternate_modes),
        "recovery_registry_hits": len(recovery_registry),
        "decision": decision,
        "report": str(output / "PHYSICAL_RECOVERY_RECON_REPORT.md"),
    }, indent=2))

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
