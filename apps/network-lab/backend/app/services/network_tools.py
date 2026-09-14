from __future__ import annotations

import re
import socket
import subprocess
from typing import Any


def parse_windows_ping(output: str) -> tuple[bool, float | None, float | None]:
    ok = "TTL=" in output.upper()

    avg_match = re.search(
        r"Average\s*=\s*(\d+)ms",
        output,
        flags=re.I,
    )
    average = float(avg_match.group(1)) if avg_match else None

    loss_match = re.search(
        r"\((\d+)%\s*loss\)",
        output,
        flags=re.I,
    )
    loss = float(loss_match.group(1)) if loss_match else None

    return ok, average, loss


def run_internet_test() -> dict[str, Any]:
    dns_ok = False
    dns_answer: str | None = None

    try:
        dns_answer = socket.gethostbyname("example.com")
        dns_ok = bool(dns_answer)
    except OSError:
        pass

    ping_target = "1.1.1.1"
    ping_ok = False
    ping_ms: float | None = None
    packet_loss: float | None = None

    try:
        cp = subprocess.run(
            ["ping", "-n", "4", "-w", "1200", ping_target],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=0x08000000,
        )
        ping_ok, ping_ms, packet_loss = parse_windows_ping(
            (cp.stdout or "") + "\n" + (cp.stderr or "")
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
            "Dedicated bound-interface throughput testing is not enabled yet."
        ),
    }
