from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable

import serial
from serial.tools import list_ports

from .config_loader import query_commands
from .settings_store import get_settings

_PORT_LOCK = threading.Lock()


def safe_query_commands() -> dict[str, str]:
    return query_commands()


@dataclass(slots=True)
class SerialConfig:
    port: str
    baudrate: int
    read_timeout: float
    write_timeout: float
    query_timeout: float
    open_retries: int
    scan_timeout: float

    @classmethod
    def from_settings(cls, port: str) -> "SerialConfig":
        serial_settings = get_settings()["serial"]

        return cls(
            port=port,
            baudrate=int(serial_settings["baudrate"]),
            read_timeout=float(serial_settings["read_timeout_seconds"]),
            write_timeout=float(serial_settings["write_timeout_seconds"]),
            query_timeout=float(serial_settings["query_timeout_seconds"]),
            open_retries=int(serial_settings["open_retries"]),
            scan_timeout=float(serial_settings["scan_timeout_seconds"]),
        )


def _metadata_score(port: Any) -> int:
    text = " ".join(
        str(value or "")
        for value in (
            getattr(port, "description", None),
            getattr(port, "manufacturer", None),
            getattr(port, "product", None),
            getattr(port, "interface", None),
            getattr(port, "hwid", None),
        )
    ).upper()

    tokens = {
        "PCUI": 100,
        "MODEM": 80,
        "MOBILE": 65,
        "USB SERIAL": 55,
        "SERIAL CDC": 55,
        "CDC": 30,
    }

    return max((score for token, score in tokens.items() if token in text), default=0)


def list_serial_ports() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for port in list_ports.comports():
        rows.append(
            {
                "device": port.device,
                "description": port.description,
                "manufacturer": port.manufacturer,
                "product": port.product,
                "interface": port.interface,
                "hwid": port.hwid,
                "score": _metadata_score(port),
            }
        )

    rows.sort(key=lambda row: (-int(row["score"]), str(row["device"])))
    return rows


def configured_serial_port() -> str | None:
    port = get_settings().get("serial", {}).get("port")
    return str(port) if port else None


def resolve_serial_port() -> str | None:
    ports = list_serial_ports()
    available = {str(row["device"]) for row in ports}

    configured = configured_serial_port()

    if configured and configured in available:
        return configured

    ranked = [row for row in ports if int(row["score"]) > 0]

    if ranked:
        return str(ranked[0]["device"])

    return None


class SerialModem:
    def __init__(
        self,
        port: str | None = None,
        config: SerialConfig | None = None,
    ) -> None:
        resolved = port or resolve_serial_port()

        if not resolved:
            raise RuntimeError(
                "No modem-like serial interface was detected. "
                "Open Settings and select a serial port."
            )

        self.config = config or SerialConfig.from_settings(resolved)

    @staticmethod
    def allowed_commands() -> Iterable[str]:
        return safe_query_commands().values()

    def query(
        self,
        command: str,
        timeout_seconds: float | None = None,
    ) -> str:
        allowed = set(safe_query_commands().values())

        if command not in allowed:
            raise ValueError("Command blocked: it is not in the query whitelist.")

        timeout = (
            self.config.query_timeout
            if timeout_seconds is None
            else float(timeout_seconds)
        )

        with _PORT_LOCK:
            last_error: Exception | None = None

            for attempt in range(self.config.open_retries):
                try:
                    return self._query_once(command, timeout)
                except (serial.SerialException, PermissionError, OSError) as exc:
                    last_error = exc
                    time.sleep(0.30 + (attempt * 0.15))

            raise RuntimeError(
                f"Could not open {self.config.port}: {last_error}"
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

    def scan_networks(self) -> str:
        commands = safe_query_commands()

        with _PORT_LOCK:
            return self._query_once(
                "AT+COPS=?",
                self.config.scan_timeout,
            )

    def snapshot(self) -> Dict[str, str]:
        result: Dict[str, str] = {}

        for name, command in safe_query_commands().items():
            try:
                result[name] = self.query(command)
            except Exception as exc:
                result[name] = f"HOST_ERROR: {exc}"

        return result


def _response_has_ok(text: str) -> bool:
    return bool(re.search(r"(^|\r?\n)OK(\r?\n|$)", text, flags=re.I))


def _clean_identity(text: str, command: str) -> str | None:
    lines = []

    for raw_line in text.replace("\r", "\n").split("\n"):
        line = raw_line.strip()

        if not line:
            continue

        if line.upper() in {"OK", "ERROR"}:
            continue

        if line.upper() == command.upper():
            continue

        if line.startswith("+CGMM:"):
            line = line.split(":", 1)[1].strip()

        if line.startswith("+CGMI:"):
            line = line.split(":", 1)[1].strip()

        if line:
            lines.append(line)

    return " | ".join(lines) if lines else None


def probe_serial_port(port: str) -> dict[str, Any]:
    commands = safe_query_commands()
    modem = SerialModem(port=port)

    result: dict[str, Any] = {
        "device": port,
        "responsive": False,
        "identity": None,
        "model": None,
        "manufacturer": None,
        "error": None,
    }

    try:
        attention = modem.query(commands["attention"])
        result["responsive"] = _response_has_ok(attention)

        if not result["responsive"]:
            return result

        if "identity" in commands:
            text = modem.query(commands["identity"])
            result["identity"] = _clean_identity(text, commands["identity"])

        if "model" in commands:
            text = modem.query(commands["model"])
            result["model"] = _clean_identity(text, commands["model"])

        if "manufacturer" in commands:
            text = modem.query(commands["manufacturer"])
            result["manufacturer"] = _clean_identity(
                text,
                commands["manufacturer"],
            )

    except Exception as exc:
        result["error"] = str(exc)

    return result


def discover_modem_ports() -> list[dict[str, Any]]:
    rows = list_serial_ports()
    results: list[dict[str, Any]] = []

    for row in rows:
        probe = probe_serial_port(str(row["device"]))
        results.append({**row, **probe})

    results.sort(
        key=lambda row: (
            not bool(row.get("responsive")),
            -int(row.get("score", 0)),
            str(row.get("device", "")),
        )
    )

    return results


def parse_network_scan(text: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    status_map = {0: "Unknown", 1: "Available", 2: "Current", 3: "Forbidden"}
    rat_map = {0: "GSM", 2: "UTRAN", 7: "LTE", 9: "NR", 11: "NR"}

    pattern = re.compile(
        r'\((\d+),"([^"]*)","([^"]*)","([^"]+)",(\d+)\)'
    )

    for match in pattern.finditer(text):
        status = int(match.group(1))
        act = int(match.group(5))

        results.append(
            {
                "operator": match.group(2) or match.group(3) or match.group(4),
                "numeric": match.group(4),
                "rat": rat_map.get(act, f"AcT {act}"),
                "status": status_map.get(status, str(status)),
            }
        )

    return results


def _first_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.I)
    return int(match.group(1)) if match else None


def _registered(text: str, prefix: str) -> bool:
    return bool(
        re.search(
            rf"\+{re.escape(prefix)}:\s*(?:\d+,)?[15]\b",
            text,
            flags=re.I,
        )
    )


def _operator(text: str) -> str:
    match = re.search(
        r'\+COPS:\s*\d+,\d+,"([^"]+)"',
        text,
        flags=re.I,
    )

    if match:
        return match.group(1)

    match = re.search(
        r"\+COPS:\s*\d+,\d+,([0-9]+)",
        text,
        flags=re.I,
    )

    return match.group(1) if match else "Unknown"


def _rat_from_cops(text: str) -> str:
    match = re.search(
        r'\+COPS:\s*\d+,\d+,"?[^",]+"?,(\d+)',
        text,
        flags=re.I,
    )

    if not match:
        return "Unknown"

    act = int(match.group(1))

    return {
        0: "GSM",
        2: "UTRAN",
        7: "LTE",
        9: "NR",
        11: "NR",
    }.get(act, f"AcT {act}")


def _parse_contexts(
    text: str,
    active_text: str,
    address_text: str,
) -> list[dict[str, Any]]:
    active: dict[int, bool] = {}

    for match in re.finditer(
        r"\+CGACT:\s*(\d+),(\d+)",
        active_text,
        flags=re.I,
    ):
        active[int(match.group(1))] = match.group(2) == "1"

    addresses: dict[int, list[str]] = {}

    for line in address_text.splitlines():
        match = re.search(
            r"\+CGPADDR:\s*(\d+),(.+)",
            line,
            flags=re.I,
        )

        if not match:
            continue

        cid = int(match.group(1))
        values = [
            item.strip().strip('"')
            for item in match.group(2).split(",")
            if item.strip().strip('"') not in {"", "0.0.0.0", "::"}
        ]
        addresses[cid] = values

    rows: list[dict[str, Any]] = []

    for line in text.splitlines():
        match = re.search(
            r'\+CGDCONT:\s*(\d+),"([^"]*)","([^"]*)","([^"]*)"',
            line,
            flags=re.I,
        )

        if not match:
            continue

        cid = int(match.group(1))

        rows.append(
            {
                "cid": cid,
                "pdp_type": match.group(2),
                "apn": match.group(3),
                "pdp_address": match.group(4),
                "active": active.get(cid, False),
                "addresses": addresses.get(cid, []),
            }
        )

    return rows


def _parse_hcsq(text: str) -> dict[str, Any]:
    match = re.search(
        r'\^HCSQ:\s*"([^"]+)"\s*,\s*(.+)',
        text,
        flags=re.I,
    )

    if not match:
        return {"rat": None, "raw_values": [], "raw": text}

    values: list[int | str] = []

    for token in match.group(2).split(","):
        token = token.strip()

        try:
            values.append(int(token))
        except ValueError:
            values.append(token)

    return {
        "rat": match.group(1),
        "raw_values": values,
        "raw": text,
    }


def _identity_from_raw(raw: Dict[str, str]) -> str:
    commands = safe_query_commands()

    model_command = commands.get("model")
    identity_command = commands.get("identity")

    if model_command:
        model = _clean_identity(raw.get("model", ""), model_command)
        if model:
            return model

    if identity_command:
        identity = _clean_identity(
            raw.get("identity", ""),
            identity_command,
        )
        if identity:
            return identity

    return "Cellular Modem"


def parse_summary(raw: Dict[str, str], port: str) -> dict[str, Any]:
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
    primary = active_contexts[0] if active_contexts else None

    return {
        "device": _identity_from_raw(raw),
        "connected": True,
        "mode": "real",
        "port": port,
        "operator": _operator(raw.get("operator", "")),
        "rat": _rat_from_cops(raw.get("operator", "")),
        "cfun": cfun,
        "sim_status": (
            cpin_match.group(1).strip()
            if cpin_match
            else "Unknown"
        ),
        "registered": registered,
        "packet_attached": attach == 1,
        "csq": csq,
        "hcsq": _parse_hcsq(raw.get("hcsq", "")),
        "sysinfoex": raw.get("sysinfoex", ""),
        "contexts": contexts,
        "apn": primary["apn"] if primary else None,
        "ipv4": (
            primary["addresses"][0]
            if primary and primary["addresses"]
            else None
        ),
        "pdp_active": bool(active_contexts),
        "raw": raw,
    }
