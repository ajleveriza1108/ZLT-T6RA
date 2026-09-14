# Network Lab v0.2

## What changed

The browser can now switch between:

- `Mock` — simulated modem data for UI development.
- `Real COM12` — safe query-only reads from the physical Balong PCUI interface.

The backend deliberately rejects commands not listed in `SAFE_QUERY_COMMANDS`.

## Real mode command set

```text
AT+CFUN?
AT+CPIN?
AT+COPS?
AT+CREG?
AT+CGREG?
AT+CEREG?
AT+CGATT?
AT+CGDCONT?
AT+CGACT?
AT+CGPADDR
AT+CSQ
AT^HCSQ?
AT^SYSINFOEX?
```

No write commands are exposed.

## v50 coexistence

The existing CFUN watchdog may briefly occupy COM12.

The Network Lab retries serial-port opening instead of treating the first sharing violation as a modem failure.

Real-mode automatic refresh is intentionally 15 seconds rather than aggressive polling.

## Signal values

CSQ is displayed directly.

`AT^HCSQ?` vendor values are exposed raw until exact Balong 5612 conversion semantics are verified. Do not present guessed conversions as authoritative dBm/dB values.

## Next

After real mode is verified:

1. persistent telemetry logger;
2. cell/signal history;
3. network scan page;
4. Internet diagnostics;
5. offline firmware acquisition/recovery tooling.
