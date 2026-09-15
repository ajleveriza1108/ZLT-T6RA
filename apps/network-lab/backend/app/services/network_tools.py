from __future__ import annotations

import re
import socket
import subprocess
from typing import Any

from .settings_store import get_settings


def parse_windows_ping(output: str) -> tuple[bool, float | None, float | None]:
    ok = "TTL=" in output.upper()

    average_match = re.search(
        r"Average\s*=\s*(\d+)ms",
        output,
        flags=re.I,
    )
    average = (
        float(average_match.group(1))
        if average_match
        else None
    )

    loss_match = re.search(
        r"\((\d+)%\s*loss\)",
        output,
        flags=re.I,
    )
    loss = float(loss_match.group(1)) if loss_match else None

    return ok, average, loss


def run_internet_test() -> dict[str, Any]:
    network = get_settings()["network"]

    dns_host = str(network["dns_test_host"])
    ping_target = str(network["ping_target"])
    ping_count = int(network["ping_count"])
    ping_timeout_ms = int(network["ping_timeout_ms"])

    dns_ok = False
    dns_answer: str | None = None

    try:
        dns_answer = socket.gethostbyname(dns_host)
        dns_ok = bool(dns_answer)
    except OSError:
        pass

    ping_ok = False
    ping_ms: float | None = None
    packet_loss: float | None = None

    try:
        completed = subprocess.run(
            [
                "ping",
                "-n",
                str(ping_count),
                "-w",
                str(ping_timeout_ms),
                ping_target,
            ],
            capture_output=True,
            text=True,
            timeout=max(10, (ping_count * ping_timeout_ms // 1000) + 5),
            creationflags=0x08000000,
        )

        ping_ok, ping_ms, packet_loss = parse_windows_ping(
            (completed.stdout or "")
            + "\n"
            + (completed.stderr or "")
        )
    except Exception:
        pass

    return {
        "dns_ok": dns_ok,
        "dns_answer": dns_answer,
        "ping_target": ping_target,
        "ping_ok": ping_ok,
        "ping_ms": ping_ms,
        "packet_loss_pct": packet_loss,
        "download_mbps": None,
        "upload_mbps": None,
        "note": (
            "DNS and ICMP are measured from the Windows host. "
            "Targets are configured in config/defaults.json."
        ),
    }
