from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Dict

import serial


QUERY_COMMANDS = {
    "cfun": "AT+CFUN?",
    "cpin": "AT+CPIN?",
    "operator": "AT+COPS?",
    "cereg": "AT+CEREG?",
    "cgreg": "AT+CGREG?",
    "attach": "AT+CGATT?",
    "contexts": "AT+CGDCONT?",
    "active_contexts": "AT+CGACT?",
    "signal": "AT+CSQ",
    "hcsq": "AT^HCSQ?",
}


@dataclass
class SerialConfig:
    port: str = "COM12"
    baudrate: int = 115200
    timeout: float = 0.8


class SerialModem:
    """Small query-only Balong PCUI adapter for the first Network Lab MVP."""

    def __init__(self, config: SerialConfig | None = None) -> None:
        self.config = config or SerialConfig(
            port=os.getenv("T6RA_PORT", "COM12")
        )

    def query(self, command: str, timeout_seconds: float = 4.0) -> str:
        if command not in QUERY_COMMANDS.values():
            raise ValueError("Only approved query commands are enabled in MVP mode.")

        with serial.Serial(
            port=self.config.port,
            baudrate=self.config.baudrate,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=self.config.timeout,
            write_timeout=2,
            rtscts=False,
            dsrdtr=False,
        ) as ser:
            ser.dtr = True
            ser.rts = False
            ser.reset_input_buffer()
            ser.write((command + "\r").encode("ascii"))

            deadline = time.time() + timeout_seconds
            chunks: list[str] = []

            while time.time() < deadline:
                data = ser.read(4096)
                if data:
                    chunks.append(data.decode("ascii", errors="replace"))
                    joined = "".join(chunks)
                    if (
                        "\r\nOK\r\n" in joined
                        or "\r\nERROR\r\n" in joined
                        or "+CME ERROR:" in joined
                    ):
                        break

            return "".join(chunks).strip()

    def snapshot(self) -> Dict[str, str]:
        return {name: self.query(cmd) for name, cmd in QUERY_COMMANDS.items()}


def parse_summary(raw: Dict[str, str]) -> dict:
    text = "\n".join(raw.values())

    operator_match = re.search(r'\+COPS:\s*\d+,\d+,"([^"]+)"', raw.get("operator", ""))
    cfun_match = re.search(r"\+CFUN:\s*(\d+)", raw.get("cfun", ""))
    cpin_match = re.search(r"\+CPIN:\s*([A-Z ]+)", raw.get("cpin", ""))
    csq_match = re.search(r"\+CSQ:\s*(\d+),", raw.get("signal", ""))
    attach_match = re.search(r"\+CGATT:\s*(\d+)", raw.get("attach", ""))

    registered = bool(
        re.search(r"\+CEREG:\s*(?:\d+,)?[15]\b", raw.get("cereg", ""))
        or re.search(r"\+CGREG:\s*(?:\d+,)?[15]\b", raw.get("cgreg", ""))
    )

    return {
        "operator": operator_match.group(1) if operator_match else "Unknown",
        "cfun": int(cfun_match.group(1)) if cfun_match else None,
        "sim_status": cpin_match.group(1).strip() if cpin_match else "Unknown",
        "csq": int(csq_match.group(1)) if csq_match else None,
        "packet_attached": attach_match.group(1) == "1" if attach_match else False,
        "registered": registered,
        "raw": raw,
    }
