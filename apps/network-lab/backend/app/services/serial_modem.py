from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Dict, Iterable

import serial
from serial.tools import list_ports


SAFE_QUERY_COMMANDS: dict[str, str] = {
    "cfun": "AT+CFUN?",
    "cpin": "AT+CPIN?",
    "operator": "AT+COPS?",
    "creg": "AT+CREG?",
    "cgreg": "AT+CGREG?",
    "cereg": "AT+CEREG?",
    "attach": "AT+CGATT?",
    "contexts": "AT+CGDCONT?",
    "active_contexts": "AT+CGACT?",
    "addresses": "AT+CGPADDR",
    "signal": "AT+CSQ",
    "hcsq": "AT^HCSQ?",
    "sysinfoex": "AT^SYSINFOEX?",
}

_PORT_LOCK = threading.Lock()


@dataclass(slots=True)
class SerialConfig:
    port: str = "COM12"
    baudrate: int = 115200
    read_timeout: float = 0.35
    write_timeout: float = 2.0


def detect_t6ra_port() -> str | None:
    preferred = os.getenv("T6RA_PORT")
    if preferred:
        return preferred

    candidates: list[str] = []
    for p in list_ports.comports():
        hwid = (p.hwid or "").upper()
        desc = (p.description or "").upper()

        if "VID:PID=12D1:1506" in hwid or "VID_12D1&PID_1506" in hwid:
            if "MI_02" in hwid:
                return p.device
            candidates.append(p.device)

        if "PCUI" in desc or "USB SERIAL" in desc:
            candidates.append(p.device)

    if os.name == "nt":
        return candidates[0] if candidates else "COM12"

    return candidates[0] if candidates else None


class SerialModem:
    def __init__(self, config: SerialConfig | None = None) -> None:
        port = detect_t6ra_port()
        self.config = config or SerialConfig(port=port or "COM12")

    @staticmethod
    def allowed_commands() -> Iterable[str]:
        return SAFE_QUERY_COMMANDS.values()

    def query(self, command: str, timeout_seconds: float = 4.5, open_retries: int = 8) -> str:
        if command not in SAFE_QUERY_COMMANDS.values():
            raise ValueError("Command blocked: Network Lab is query-only.")

        with _PORT_LOCK:
            last_error: Exception | None = None
            for attempt in range(open_retries):
                try:
                    return self._query_once(command, timeout_seconds)
                except (serial.SerialException, PermissionError, OSError) as exc:
                    last_error = exc
                    time.sleep(0.35 + (attempt * 0.15))

            raise RuntimeError(
                f"Could not open {self.config.port} after {open_retries} retries: {last_error}"
            )

    def _query_once(self, command: str, timeout_seconds: float) -> str:
        with serial.Serial(
            port=self.config.port,
            baudrate=self.config.baudrate,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=self.config.read_timeout,
            write_timeout=self.config.write_timeout,
            rtscts=False,
            dsrdtr=False,
        ) as ser:
            ser.dtr = True
            ser.rts = False
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write((command + "\r").encode("ascii"))

            deadline = time.monotonic() + timeout_seconds
            chunks: list[str] = []
            last_rx = time.monotonic()

            while time.monotonic() < deadline:
                data = ser.read(4096)
                if data:
                    chunks.append(data.decode("ascii", errors="replace"))
                    last_rx = time.monotonic()

                joined = "".join(chunks)
                terminal = (
                    "\r\nOK\r\n" in joined
                    or "\r\nERROR\r\n" in joined
                    or "+CME ERROR:" in joined
                    or "COMMAND NOT SUPPORT" in joined
                )

                if terminal and (time.monotonic() - last_rx) > 0.15:
                    break

            return "".join(chunks).strip()

    def scan_networks(self, timeout_seconds: float = 160.0) -> str:
        # Query operation, but intentionally separate because AT+COPS=? is slow
        # and may occupy the radio for an extended period.
        with _PORT_LOCK:
            return self._query_once("AT+COPS=?", timeout_seconds)

    def snapshot(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for name, cmd in SAFE_QUERY_COMMANDS.items():
            try:
                result[name] = self.query(cmd)
            except Exception as exc:
                result[name] = f"HOST_ERROR: {exc}"
        return result


def parse_network_scan(text: str) -> list[dict]:
    # +COPS: (2,"Globe Telecom-PH","Globe","51502",7),(...)
    results: list[dict] = []
    status_map = {0: "Unknown", 1: "Available", 2: "Current", 3: "Forbidden"}
    rat_map = {0: "GSM", 2: "UTRAN", 7: "LTE", 9: "NR", 11: "NR"}

    pattern = re.compile(
        r'\((\d+),"([^"]*)","([^"]*)","([^"]+)",(\d+)\)'
    )
    for m in pattern.finditer(text):
        stat = int(m.group(1))
        results.append(
            {
                "operator": m.group(2) or m.group(3) or m.group(4),
                "numeric": m.group(4),
                "rat": rat_map.get(int(m.group(5)), f"AcT {m.group(5)}"),
                "status": status_map.get(stat, str(stat)),
            }
        )
    return results


def _first_int(pattern: str, text: str) -> int | None:
    m = re.search(pattern, text, flags=re.I)
    return int(m.group(1)) if m else None


def _registered(text: str, prefix: str) -> bool:
    return bool(re.search(rf"\+{re.escape(prefix)}:\s*(?:\d+,)?[15]\b", text, flags=re.I))


def _operator(text: str) -> str:
    m = re.search(r'\+COPS:\s*\d+,\d+,"([^"]+)"', text, flags=re.I)
    if m:
        return m.group(1)

    m = re.search(r"\+COPS:\s*\d+,\d+,([0-9]+)", text, flags=re.I)
    return m.group(1) if m else "Unknown"


def _rat_from_cops(text: str) -> str:
    m = re.search(r'\+COPS:\s*\d+,\d+,"?[^",]+"?,(\d+)', text, flags=re.I)
    if not m:
        return "Unknown"

    act = int(m.group(1))
    return {0: "GSM", 2: "UTRAN", 7: "LTE", 9: "NR", 11: "NR"}.get(act, f"AcT {act}")


def _parse_contexts(text: str, active_text: str, address_text: str) -> list[dict]:
    active: dict[int, bool] = {}
    for m in re.finditer(r"\+CGACT:\s*(\d+),(\d+)", active_text, flags=re.I):
        active[int(m.group(1))] = m.group(2) == "1"

    addresses: dict[int, list[str]] = {}
    for line in address_text.splitlines():
        m = re.search(r"\+CGPADDR:\s*(\d+),(.+)", line, flags=re.I)
        if not m:
            continue

        cid = int(m.group(1))
        values = [
            item.strip().strip('"')
            for item in m.group(2).split(",")
            if item.strip().strip('"') not in {"", "0.0.0.0", "::"}
        ]
        addresses[cid] = values

    rows: list[dict] = []
    for line in text.splitlines():
        m = re.search(
            r'\+CGDCONT:\s*(\d+),"([^"]*)","([^"]*)","([^"]*)"',
            line,
            flags=re.I,
        )
        if not m:
            continue

        cid = int(m.group(1))
        rows.append(
            {
                "cid": cid,
                "pdp_type": m.group(2),
                "apn": m.group(3),
                "pdp_address": m.group(4),
                "active": active.get(cid, False),
                "addresses": addresses.get(cid, []),
            }
        )
    return rows


def _parse_hcsq(text: str) -> dict:
    m = re.search(r'\^HCSQ:\s*"([^"]+)"\s*,\s*(.+)', text, flags=re.I)
    if not m:
        return {"rat": None, "raw_values": [], "raw": text}

    values: list[int | str] = []
    for token in m.group(2).split(","):
        token = token.strip()
        try:
            values.append(int(token))
        except ValueError:
            values.append(token)

    return {"rat": m.group(1), "raw_values": values, "raw": text}


def parse_summary(raw: Dict[str, str], port: str) -> dict:
    cfun = _first_int(r"\+CFUN:\s*(\d+)", raw.get("cfun", ""))
    csq = _first_int(r"\+CSQ:\s*(\d+)", raw.get("signal", ""))
    attach = _first_int(r"\+CGATT:\s*(\d+)", raw.get("attach", ""))

    cpin_match = re.search(
        r"\+CPIN:\s*([A-Z0-9 _-]+)",
        raw.get("cpin", ""),
        flags=re.I,
    )

    registered = (
        _registered(raw.get("cereg", ""), "CEREG")
        or _registered(raw.get("cgreg", ""), "CGREG")
        or _registered(raw.get("creg", ""), "CREG")
    )

    contexts = _parse_contexts(
        raw.get("contexts", ""),
        raw.get("active_contexts", ""),
        raw.get("addresses", ""),
    )

    active_contexts = [row for row in contexts if row["active"]]
    internet_candidates = [
        row for row in active_contexts
        if row["apn"].lower() not in {"ims", ""}
    ]
    primary = (
        internet_candidates[0]
        if internet_candidates
        else (active_contexts[0] if active_contexts else None)
    )

    return {
        "device": "ZLT T6R-A",
        "connected": True,
        "mode": "real",
        "port": port,
        "operator": _operator(raw.get("operator", "")),
        "rat": _rat_from_cops(raw.get("operator", "")),
        "cfun": cfun,
        "sim_status": cpin_match.group(1).strip() if cpin_match else "Unknown",
        "registered": registered,
        "packet_attached": attach == 1,
        "csq": csq,
        "hcsq": _parse_hcsq(raw.get("hcsq", "")),
        "sysinfoex": raw.get("sysinfoex", ""),
        "contexts": contexts,
        "apn": primary["apn"] if primary else None,
        "ipv4": primary["addresses"][0] if primary and primary["addresses"] else None,
        "pdp_active": bool(active_contexts),
        "raw": raw,
    }
