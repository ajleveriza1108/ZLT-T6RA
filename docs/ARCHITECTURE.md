# Architecture

## Design principle

Preserve working hardware support. Replace only the layer proven to be responsible for unwanted policy.

## Components

### 1. Physical reference modem

The production/reference T6R-A should remain unmodified during software development.

Known interfaces include:

- host WebUI at `192.168.8.1`;
- Balong PCUI serial interface;
- RNDIS/USB networking;
- diagnostic USB functions.

### 2. Network Lab backend

Python/FastAPI service that abstracts the modem.

Backends:

- `mock`: deterministic simulated modem for UI development;
- `real`: query-only serial adapter for the physical modem.

Future adapters can include:

- host WebUI/API reader;
- firmware/rootfs analysis service;
- CSV/event logger.

### 3. Network Lab frontend

React/TypeScript UI.

Initial pages:

- Dashboard
- SIM Info
- Signal Monitor
- Network Scan
- APN / PDP
- Internet Diagnostics
- Cell Logger
- AT Console
- Firmware / Recovery

### 4. Firmware track

The initial firmware track does not replace the baseband.

Target:

```text
stock PH0222 host firmware
        +
minimal host-policy patch
        +
generic WAN/APN behavior
        +
Network Lab services later
```

## First firmware release target

`T6RA-LAB 0.1`

Scope:

- do not force radio-off behavior for non-DITO operators;
- remove host-side PLMN/operator rejection;
- allow real operator/signal state to reach the host;
- allow the stock WAN/APN manager to use a valid subscriber APN;
- preserve all unrelated services and hardware support.

## Separation of concerns

Network Lab application and T6RA-LAB firmware are separate deliverables.

The UI can evolve rapidly without reflashing firmware.
