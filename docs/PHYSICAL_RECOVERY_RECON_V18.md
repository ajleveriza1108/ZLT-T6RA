# Physical Recovery Recon v18

This stage starts only after software readback paths have been exhausted.

It remains non-destructive. It does not enter emergency mode or send any bootloader command.

The tool maps:

- the currently attached composite USB device;
- interface numbers and Windows services/drivers;
- installed INF metadata;
- historical USB product IDs for the same vendor from the local registry;
- relevant Windows SetupAPI enumeration history;
- evidence that a Download/Loader/Boot/Recovery interface may have appeared previously.

It generates a private report under:

`11_physical_recovery_recon/PHYSICAL_RECOVERY_RECON_REPORT.md`

If no proven recovery mode is found, the next required evidence is high-resolution PCB photography with the device powered off.

Do not short unidentified pads and do not upload chipset loaders until the exact recovery mechanism and chipset compatibility are established.
