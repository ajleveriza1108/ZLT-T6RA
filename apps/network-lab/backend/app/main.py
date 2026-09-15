from __future__ import annotations

import os

import threading
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .services.config_loader import app_metadata
from .services.firmware_state import firmware_status as read_firmware_status
from .services.mock_modem import mock_networks, mock_summary
from .services.network_tools import run_internet_test
from .services.serial_modem import (
    SerialModem,
    discover_modem_ports,
    list_serial_ports,
    resolve_serial_port,
    safe_query_commands,
    parse_network_scan,
    parse_summary,
)
from .services.settings_store import get_settings, set_setting
from .services.telemetry import append_sample, make_sample, read_samples

_META = app_metadata()

app = FastAPI(
    title=str(_META["name"]),
    version=str(_META["version"]),
)


_allowed_origin = os.getenv("T6RA_ALLOWED_ORIGIN")

if _allowed_origin:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_allowed_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
_runtime_lock = threading.Lock()
_runtime_mode = str(
    get_settings()
    .get("runtime", {})
    .get("mode", "mock")
).lower()


class SerialSelection(BaseModel):
    port: str | None = None


def get_mode() -> str:
    with _runtime_lock:
        return _runtime_mode


def set_mode(value: str) -> str:
    normalized = value.strip().lower()

    if normalized not in {"mock", "real"}:
        raise HTTPException(
            status_code=400,
            detail="mode must be mock or real",
        )

    global _runtime_mode

    with _runtime_lock:
        _runtime_mode = normalized

    set_setting("runtime", "mode", normalized)

    return normalized


def current_summary() -> dict[str, Any]:
    if get_mode() == "mock":
        return mock_summary()

    port = resolve_serial_port()

    if not port:
        raise HTTPException(
            status_code=503,
            detail=(
                "No modem-like serial interface is selected or detected. "
                "Open Settings and run device discovery."
            ),
        )

    modem = SerialModem(port=port)

    try:
        return parse_summary(modem.snapshot(), port)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "name": _META["name"],
        "version": _META["version"],
        "mode": get_mode(),
        "detected_port": resolve_serial_port(),
        "write_commands_enabled": False,
        "firmware_writes_enabled": read_firmware_status()["flashing_enabled"],
    }


@app.get("/api/config")
def runtime_config() -> dict[str, Any]:
    settings = get_settings()

    return {
        "settings": settings,
        "resolved_port": resolve_serial_port(),
        "ports": list_serial_ports(),
    }


@app.post("/api/config/serial")
def configure_serial(selection: SerialSelection) -> dict[str, Any]:
    chosen = selection.port

    if chosen is not None:
        available = {
            row["device"]
            for row in list_serial_ports()
        }

        if chosen not in available:
            raise HTTPException(
                status_code=400,
                detail=f"Serial port is not currently available: {chosen}",
            )

    set_setting("serial", "port", chosen)

    return runtime_config()


@app.post("/api/device/discover")
def device_discovery() -> dict[str, Any]:
    return {
        "candidates": discover_modem_ports(),
        "resolved_port": resolve_serial_port(),
    }


@app.get("/api/mode")
def read_mode() -> dict[str, str]:
    return {"mode": get_mode()}


@app.post("/api/mode")
def change_mode(
    mode: str = Query(..., pattern="^(mock|real)$"),
) -> dict[str, str]:
    return {"mode": set_mode(mode)}


@app.get("/api/device/summary")
def device_summary() -> dict[str, Any]:
    return current_summary()


@app.get("/api/sim")
def sim_info() -> dict[str, Any]:
    summary = current_summary()

    return {
        "sim_status": summary["sim_status"],
        "cfun": summary["cfun"],
        "operator": summary["operator"],
        "rat": summary["rat"],
        "registered": summary["registered"],
        "packet_attached": summary["packet_attached"],
    }


@app.get("/api/signal")
def signal_info() -> dict[str, Any]:
    summary = current_summary()

    return {
        "csq": summary["csq"],
        "hcsq": summary["hcsq"],
        "sysinfoex": summary["sysinfoex"],
    }


@app.get("/api/pdp")
def pdp_info() -> dict[str, Any]:
    summary = current_summary()

    return {
        "contexts": summary["contexts"],
        "packet_attached": summary["packet_attached"],
        "pdp_active": summary["pdp_active"],
        "apn": summary["apn"],
        "ipv4": summary["ipv4"],
    }


@app.post("/api/network/scan")
def network_scan(confirm: bool = False) -> dict[str, Any]:
    if get_mode() == "mock":
        return {
            "results": mock_networks(),
            "note": "Mock scan dataset loaded from configuration.",
        }

    if not confirm:
        raise HTTPException(
            status_code=409,
            detail=(
                "Real network scan is intentionally manual. "
                "Retry with confirm=true."
            ),
        )

    modem = SerialModem()

    try:
        raw = modem.scan_networks()

        return {
            "results": parse_network_scan(raw),
            "note": "Real operator scan completed.",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@app.post("/api/internet/test")
def internet_test() -> dict[str, Any]:
    if get_mode() == "mock":
        return {
            "dns_ok": True,
            "dns_answer": "192.0.2.10",
            "ping_target": "192.0.2.1",
            "ping_ok": True,
            "ping_ms": 20.0,
            "packet_loss_pct": 0.0,
            "download_mbps": None,
            "upload_mbps": None,
            "note": "Mock Internet test.",
        }

    return run_internet_test()


@app.get("/api/telemetry")
def telemetry(
    limit: int = Query(120, ge=1, le=10000),
) -> dict[str, Any]:
    return {"samples": read_samples(limit)}


@app.post("/api/telemetry/capture")
def capture_telemetry() -> dict[str, Any]:
    sample = make_sample(current_summary())
    append_sample(sample)
    return sample


@app.get("/api/at/commands")
def at_commands() -> dict[str, Any]:
    return {"commands": safe_query_commands()}


@app.post("/api/at/query")
def at_query(key: str) -> dict[str, Any]:
    commands = safe_query_commands()

    if key not in commands:
        raise HTTPException(
            status_code=400,
            detail="Unknown or blocked AT query key",
        )

    command = commands[key]

    if get_mode() == "mock":
        response = mock_summary()["raw"].get(
            key,
            f"{command}\r\n\r\nOK",
        )

        return {
            "command": command,
            "response": response,
        }

    modem = SerialModem()

    try:
        return {
            "command": command,
            "response": modem.query(command),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@app.get("/api/firmware/status")
def firmware_status() -> dict[str, Any]:
    return read_firmware_status()
