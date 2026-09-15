# Focused Recovery Mapper v17

This stage follows the v16 recovery/readback survey.

It focuses on the only two meaningful v16 leads:

1. recovery-related UUID candidates found in saved WebUI/analysis material;
2. the serial interface that actually responds to AT.

The mapper determines whether a UUID came from original device captures or from our own project/documentation. This prevents project-generated text from being mistaken for device evidence.

For the responsive serial interface it parses the already-captured `AT^CLAC` command list and identifies command names that look related to boot, recovery, backup, dump, partitions, firmware, filesystem, NV, diagnostics, or verification.

Important: matching command names are not executed automatically.

Output:

`10_focused_recovery_mapper/FOCUSED_RECOVERY_REPORT.md`

and

`10_focused_recovery_mapper/focused_recovery.json`

The modem remains unmodified.
