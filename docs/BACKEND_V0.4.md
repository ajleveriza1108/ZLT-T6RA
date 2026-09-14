# Network Lab v0.4 — Backend API

Implemented endpoints:

```text
GET  /api/health
GET  /api/mode
POST /api/mode
GET  /api/device/summary
GET  /api/sim
GET  /api/signal
GET  /api/pdp
POST /api/network/scan
POST /api/internet/test
GET  /api/telemetry
POST /api/telemetry/capture
GET  /api/at/commands
POST /api/at/query
GET  /api/firmware/status
```

## Safety

Real AT console accepts only whitelisted query commands.

Real operator scanning is manual and uses `AT+COPS=?`; it is not run by background polling.

Firmware flashing remains disabled until the image, verification and recovery gates pass.

Telemetry CSV is written under `captures/`, which is gitignored.
