# Roadmap

## Phase 0 — Baseline

- preserve current findings;
- record stock behavior;
- keep reference modem usable.

## Phase 1 — Development environment

- repository structure;
- mock modem backend;
- Network Lab dashboard;
- query-only real modem adapter.

## Phase 2 — Firmware acquisition

- obtain exact PH0222 / 1.1.30 image or device dump;
- record SHA-256 hashes;
- inventory partitions and filesystem formats.

## Phase 3 — Recovery and verification

- understand upgrade package format;
- determine checksum/signature enforcement;
- establish a recovery method before any firmware write.

## Phase 4 — Offline reverse engineering

- unpack root filesystem;
- map startup sequence;
- identify host network manager;
- identify PLMN/operator-policy service;
- locate CFUN policy;
- map WAN/APN lifecycle.

## Phase 5 — T6RA-LAB 0.1

Minimal patch only.

No bootloader changes.
No baseband firmware changes.

## Phase 6 — Regression validation

Validate Wi-Fi, LAN, USB, SIM, APN, DHCP, DNS, NAT, firewall, LEDs, buttons, reboot, reset, update and recovery.

## Phase 7 — Standalone validation

Cold boot without a PC:

```text
SIM -> CFUN=1 -> register -> APN -> PDP -> WAN -> NAT -> Wi-Fi Internet
```

## Phase 8 — Network Lab expansion

- signal trends;
- serving-cell history;
- carrier comparison;
- network scans;
- latency/jitter/loss;
- throughput;
- CSV exports;
- firmware diagnostics.

## Optional Phase 9 — Custom host services

Only if the vendor network manager remains a blocker after minimal patching.
