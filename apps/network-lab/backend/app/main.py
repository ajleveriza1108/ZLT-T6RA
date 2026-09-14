from __future__ import annotations

import threading

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .services.mock_modem import mock_summary
from .services.serial_modem import SerialModem, detect_t6ra_port, parse_summary

app = FastAPI(
    title="T6R-A Network Lab API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "version": "0.2.0",
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


@app.get("/api/device/raw")
def device_raw() -> dict:
    summary = device_summary()
    return {
        "mode": summary["mode"],
        "port": summary["port"],
        "raw": summary["raw"],
    }
