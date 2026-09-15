# Recovery / Readback Mapper

This tool is the next gate after a backup result with no stock firmware package and no raw partition access.

It is intentionally non-destructive.

It maps:

- current Windows USB/PnP interfaces and driver binding;
- ADB state;
- Fastboot visibility;
- serial interfaces using query-only AT commands;
- saved WebUI/firmware-analysis assets for recovery, rollback, bootloader, upgrade, root-login, partition, and signature clues;
- integrity drift between the historical v13 backup manifest and the current backup;
- ranked recovery/readback paths based on actual evidence.

It does not:

- reboot or reset the modem;
- request a boot-mode transition;
- upload or flash firmware;
- write a partition;
- write NVRAM;
- change IMEI;
- change APN, PLMN, radio, or router settings.

The report is stored in the private modem backup folder:

`09_recovery_readback_mapper/RECOVERY_ACCESS_REPORT.md`

The tool also generates `MANIFEST_CURRENT.json`,
`MANIFEST_SHA256_CURRENT.txt`, and `MANIFEST_SHA512_CURRENT.txt`
without replacing the historical v13 manifest.

A recovery path is not considered proven merely because an interface exists.
Experimental flashing remains blocked until recovery/readback can be demonstrated repeatably.
