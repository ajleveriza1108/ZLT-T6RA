from __future__ import annotations

import threading

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .services.mock_modem import mock_networks, mock_summary
from .services.network_tools import run_internet_test
from .services.serial_modem import (
    SAFE_QUERY_COMMANDS,
    SerialModem,
    detect_t6ra_port,
    parse_network_scan,
    parse_summary,
)
from .services.telemetry import append_sample, make_sample, read_samples

app = FastAPI(
    title="T6R-A Network Lab API",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_runtime_lock = threading.Lock()
_runtime_mode = "mock"


def get_mode() -> str:
    with _runtime_lock:
        return _runtime_mode


def set_mode(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"mock", "real"}:
        raise HTTPException(status_code=400, detail="mode must be mock or real")

    global _runtime_mode
    with _runtime_lock:
        _runtime_mode = normalized
    return normalized


def current_summary() -> dict:
    if get_mode() == "mock":
        return mock_summary()

    port = detect_t6ra_port()
    if not port:
        raise HTTPException(status_code=503, detail="T6R-A PCUI port not found")

    modem = SerialModem()
    try:
        return parse_summary(modem.snapshot(), port)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "version": "0.4.0",
        "mode": get_mode(),
        "detected_port": detect_t6ra_port(),
        "write_commands_enabled": False,
        "firmware_writes_enabled": False,
    }


@app.get("/api/mode")
def read_mode() -> dict:
    return {"mode": get_mode()}


@app.post("/api/mode")
def change_mode(mode: str = Query(..., pattern="^(mock|real)$")) -> dict:
    return {"mode": set_mode(mode)}


@app.get("/api/device/summary")
def device_summary() -> dict:
    return current_summary()


@app.get("/api/sim")
def sim_info() -> dict:
    s = current_summary()
    return {
        "sim_status": s["sim_status"],
        "cfun": s["cfun"],
        "operator": s["operator"],
        "rat": s["rat"],
        "registered": s["registered"],
        "packet_attached": s["packet_attached"],
    }


@app.get("/api/signal")
def signal_info() -> dict:
    s = current_summary()
    return {
        "csq": s["csq"],
        "hcsq": s["hcsq"],
        "sysinfoex": s["sysinfoex"],
    }


@app.get("/api/pdp")
def pdp_info() -> dict:
    s = current_summary()
    return {
        "contexts": s["contexts"],
        "packet_attached": s["packet_attached"],
        "pdp_active": s["pdp_active"],
        "apn": s["apn"],
        "ipv4": s["ipv4"],
    }


@app.post("/api/network/scan")
def network_scan(confirm: bool = False) -> dict:
    if get_mode() == "mock":
        return {
            "results": mock_networks(),
            "note": "Mock scan dataset.",
        }

    if not confirm:
        raise HTTPException(
            status_code=409,
            detail=(
                "Real AT+COPS=? scan is intentionally manual. "
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
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/internet/test")
def internet_test() -> dict:
    if get_mode() == "mock":
        return {
            "dns_ok": True,
            "dns_answer": "93.184.216.34",
            "ping_target": "1.1.1.1",
            "ping_ok": True,
            "ping_ms": 28.0,
            "packet_loss_pct": 0.0,
            "download_mbps": 48.6,
            "upload_mbps": 12.4,
            "note": "Mock Internet test dataset.",
        }

    return run_internet_test()


@app.get("/api/telemetry")
def telemetry(limit: int = Query(120, ge=1, le=1000)) -> dict:
    return {"samples": read_samples(limit)}


@app.post("/api/telemetry/capture")
def capture_telemetry() -> dict:
    sample = make_sample(current_summary())
    append_sample(sample)
    return sample


@app.get("/api/at/commands")
def at_commands() -> dict:
    return {"commands": SAFE_QUERY_COMMANDS}


@app.post("/api/at/query")
def at_query(key: str) -> dict:
    if key not in SAFE_QUERY_COMMANDS:
        raise HTTPException(status_code=400, detail="Unknown or blocked AT query key")

    command = SAFE_QUERY_COMMANDS[key]

    if get_mode() == "mock":
        response = mock_summary()["raw"].get(key, f"{command}\r\n\r\nOK")
        return {"command": command, "response": response}

    modem = SerialModem()
    try:
        return {"command": command, "response": modem.query(command)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/firmware/status")
def firmware_status() -> dict:
    return {
        "flashing_enabled": False,
        "current_track": "Offline acquisition / recovery preparation",
        "gates": [
            {
                "id": "baseline",
                "title": "Known-good baseline",
                "status": "pass",
                "detail": "Baseband and host behavior have been mapped sufficiently to proceed to firmware preservation.",
            },
            {
                "id": "image",
                "title": "Exact PH0222 image or verified dump",
                "status": "pending",
                "detail": "Preserve an exact factory image/dump and record hashes before any modification.",
            },
            {
                "id": "verify",
                "title": "Package/signature verification",
                "status": "pending",
                "detail": "Understand updater and boot verification requirements offline.",
            },
            {
                "id": "recovery",
                "title": "Proven recovery path",
                "status": "pending",
                "detail": "No experimental firmware is flashed until recovery is proven.",
            },
            {
                "id": "patch",
                "title": "Minimal T6RA-LAB 0.1 patch",
                "status": "blocked",
                "detail": "Build only after image, verification and recovery gates are complete.",
            },
        ],
    }
