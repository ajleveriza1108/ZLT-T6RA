from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .services.mock_modem import mock_summary
from .services.serial_modem import SerialModem, parse_summary

app = FastAPI(
    title="T6R-A Network Lab API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "mode": os.getenv("T6RA_MODE", "mock").lower(),
    }


@app.get("/api/device/summary")
def device_summary() -> dict:
    mode = os.getenv("T6RA_MODE", "mock").lower()

    if mode != "real":
        return mock_summary()

    modem = SerialModem()
    parsed = parse_summary(modem.snapshot())

    return {
        "device": "ZLT T6R-A",
        "connected": True,
        "operator": parsed["operator"],
        "rat": "Cellular",
        "band": None,
        "pci": None,
        "cfun": parsed["cfun"],
        "sim_status": parsed["sim_status"],
        "registered": parsed["registered"],
        "packet_attached": parsed["packet_attached"],
        "apn": None,
        "wan": "Unknown",
        "ipv4": None,
        "signal": {
            "rsrp": None,
            "rsrq": None,
            "sinr": None,
            "rssi": None,
            "csq": parsed["csq"],
        },
        "internet": None,
        "raw": parsed["raw"],
    }
