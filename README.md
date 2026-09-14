# ZLT T6R-A Network Lab

Research and development workspace for the **ZLT T6R-A / PH0222 / 1.1.30** modem-router.

This project has two parallel tracks:

1. **T6R-A Network Lab** — a local management and diagnostics application for SIM, operator, RF, cell, APN/PDP, WAN, latency, DNS, throughput, logging, and AT-command research.
2. **T6RA-LAB Firmware** — a conservative host-firmware customization track that preserves the working Balong 5612 baseband, Wi-Fi/router stack, hardware support, and recovery path while removing carrier-specific host policy only after recovery and image-verification gates pass.

## Current architecture

```text
T6R-A
├─ Host/router firmware
│  ├─ WebUI
│  ├─ PLMN/operator policy
│  ├─ APN/WAN manager
│  ├─ Wi-Fi/LAN
│  ├─ DHCP/DNS/NAT/firewall
│  └─ upgrade/recovery services
└─ Balong 5612 baseband
   ├─ SIM
   ├─ LTE/RedCap radio
   ├─ network registration
   ├─ packet attachment
   ├─ PDP contexts
   └─ AT interface
```

The baseband has already demonstrated that it can read and register a non-DITO SIM. The remaining restriction is being enforced by the router host layer.

## Development rule

**Do not flash experimental firmware during normal development.**

The physical modem remains the reference unit. Firmware work is performed on offline copies until recovery and image-verification gates pass.

## Repository layout

```text
apps/
  network-lab/
    backend/       Python/FastAPI modem bridge and diagnostics API
    frontend/      React/TypeScript Network Lab UI
firmware/
  original/        local-only factory image/dumps; never commit
  analysis/        offline firmware/rootfs analysis
  patches/         patch descriptions and source-controlled diffs
  recovery/        recovery documentation/procedures
  build/           local build output; never commit
docs/
captures/          local modem captures/logs; never commit
tools/
  windows/
  linux/
```

## Quick start — UI in mock mode

Backend:

```powershell
cd "D:\Windows Projects\ZLT-T6RA\apps\network-lab\backend"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:T6RA_MODE="mock"
uvicorn app.main:app --reload --port 8765
```

Frontend, in another terminal:

```powershell
cd "D:\Windows Projects\ZLT-T6RA\apps\network-lab\frontend"
npm install
npm run dev
```

Open the Vite URL shown in the terminal.

## Real modem mode

Keep the initial application **read-only**.

```powershell
$env:T6RA_MODE="real"
$env:T6RA_PORT="COM12"
uvicorn app.main:app --reload --port 8765
```

The first real-mode endpoints use query-only AT commands.

## Firmware safety gates

No modified firmware is flashed until:

- exact PH0222 firmware or a verified dump is preserved;
- SHA-256 hashes are recorded;
- partition/rootfs layout is understood;
- updater/package verification is understood;
- a recovery path is proven;
- the first patch is minimal and reproducible;
- bootloader and Balong/baseband firmware remain untouched in the first releases.
