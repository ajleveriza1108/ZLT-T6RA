# Firmware Safety Gates

The project must pass these gates in order.

## Gate A — Preserve original

- verified firmware/dump exists;
- hashes recorded;
- multiple backup copies.

## Gate B — Understand image

- package header identified;
- partitions identified;
- compression/filesystem understood;
- repack is reproducible offline.

## Gate C — Understand verification

- updater validation documented;
- checksum/signature behavior understood;
- modified package is not flashed merely to discover whether it boots.

## Gate D — Recovery

At least one recovery path is proven before the first experimental flash.

## Gate E — Minimal patch

First firmware experiment modifies the smallest possible set of host files.

Do not modify:

- bootloader;
- partition table;
- Balong/baseband firmware;
- calibration/NVRAM;
- IMEI;
- RF calibration.

## Gate F — Regression test

The release must preserve all known-good router functions before it becomes the new working build.

## Versioning

Keep three categories:

```text
FACTORY     untouched reference
WORKING     last known-good lab build
EXPERIMENT  next candidate
```

Every binary image receives a SHA-256 hash.
