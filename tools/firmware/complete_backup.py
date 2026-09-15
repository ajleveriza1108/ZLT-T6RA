from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import ssl
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CHUNK = 4 * 1024 * 1024
MAX_RESPONSE = 16 * 1024 * 1024
MAX_DOWNLOAD = 4 * 1024 * 1024 * 1024

UUID_RE = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
)
URL_RE = re.compile(r"""(?i)\bhttps?://[^\s"'<>\\]+""")

PACKAGE_EXTS = {
    ".pac", ".bin", ".img", ".swu", ".tar", ".zip", ".rom", ".dump",
    ".ubi", ".ubifs", ".squashfs", ".gz", ".xz", ".bz2",
}
EXPORT_EXTS = {
    ".cfg", ".conf", ".config", ".xml", ".json", ".txt", ".dat",
    ".backup", ".bak", ".tar", ".zip", ".gz",
}

SAFE_TERMS = (
    "get", "read", "query", "export", "backup", "download", "status",
    "info", "firmware", "fota", "upgrade", "version", "package",
)

DANGEROUS_TERMS = (
    "upload", "apply", "install", "flash", "write", "erase", "delete",
    "reset", "reboot", "restart", "set", "save", "commit", "upgrade_start",
)

def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default

def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")

def sanitize(text: str) -> str:
    text = re.sub(
        r"(?i)\b(imei|imsi|iccid|serial(?:number)?|sn)\s*[:=]\s*([A-Za-z0-9_-]+)",
        r"\1=[REDACTED]",
        text,
    )
    text = re.sub(r"\b\d{14,20}\b", "[REDACTED_LONG_ID]", text)
    return text

def hash_file(path: Path) -> dict[str, str]:
    h256 = hashlib.sha256()
    h512 = hashlib.sha512()

    with path.open("rb") as handle:
        while True:
            block = handle.read(CHUNK)
            if not block:
                break
            h256.update(block)
            h512.update(block)

    return {"sha256": h256.hexdigest(), "sha512": h512.hexdigest()}

def http():
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context),
        urllib.request.HTTPRedirectHandler(),
    )

HTTP = http()

def safe_filename(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return value[:180] or "artifact.bin"

def find_base_url(backup: Path) -> str:
    for path in (
        backup / "03_webui_program" / "webui_summary.json",
        backup / "02_firmware" / "analysis_existing" / "acquisition" / "acquisition_report.json",
    ):
        data = load_json(path, {})
        if isinstance(data, dict):
            value = data.get("base_url")
            if not value and isinstance(data.get("survey"), dict):
                value = data["survey"].get("base_url")
            if value:
                return str(value).rstrip("/")
    return ""

def discover_candidates(backup: Path) -> list[dict[str, Any]]:
    possible = [
        backup / "03_webui_program" / "analysis.json",
        backup / "02_firmware" / "analysis_existing" / "acquisition" / "query_candidates.json",
    ]

    candidates = []

    for path in possible:
        data = load_json(path, [])
        if isinstance(data, dict):
            data = data.get("uuid_candidates", [])
        if isinstance(data, list):
            candidates.extend(row for row in data if isinstance(row, dict))

    approved = {}
    for row in candidates:
        uuid = str(row.get("uuid", "")).lower()
        context = str(row.get("context", ""))
        low = context.lower()

        if not UUID_RE.fullmatch(uuid):
            continue
        if not row.get("get_semantics"):
            continue
        if any(term in low for term in DANGEROUS_TERMS):
            continue
        if not any(term in low for term in SAFE_TERMS):
            continue

        approved[uuid] = row

    return list(approved.values())

def query_candidate(
    base_url: str,
    row: dict[str, Any],
    session_id: str,
    token: str,
) -> bytes:
    wrapper = urllib.parse.urljoin(
        base_url.rstrip("/") + "/",
        "cgi-bin/http.cgi",
    )

    form = {
        "cmd": row["uuid"],
        "method": "GET",
        "sessionId": session_id,
    }

    if token:
        form["token"] = token

    request = urllib.request.Request(
        wrapper,
        data=urllib.parse.urlencode(form).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "T6RA-Backup-Completion/1.1",
        },
        method="POST",
    )

    with HTTP.open(request, timeout=10) as response:
        body = response.read(MAX_RESPONSE + 1)

        if len(body) > MAX_RESPONSE:
            raise RuntimeError("response exceeded backup cap")

        return body

def extract_urls(text: str, base_url: str) -> set[str]:
    urls: set[str] = set()

    for match in URL_RE.finditer(text):
        urls.add(html.unescape(match.group(0).rstrip(");,]")))

    for match in re.finditer(
        r"""(?i)["']([^"']+\.(?:pac|bin|img|swu|tar|zip|rom|dump|ubi|ubifs|squashfs|gz|xz|bz2|cfg|conf|config|xml|json|dat|backup|bak)(?:\?[^"']*)?)["']""",
        text,
    ):
        urls.add(
            urllib.parse.urljoin(
                base_url.rstrip("/") + "/",
                html.unescape(match.group(1)),
            )
        )

    return urls

def download(url: str, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    parsed = urllib.parse.urlparse(url)
    filename = Path(parsed.path).name

    if not filename:
        filename = f"download_{hashlib.sha256(url.encode()).hexdigest()[:12]}.bin"

    destination = out_dir / safe_filename(filename)
    temporary = destination.with_suffix(destination.suffix + ".part")

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "T6RA-Backup-Completion/1.1"},
        method="GET",
    )

    total = 0

    with HTTP.open(request, timeout=20) as response, temporary.open("wb") as handle:
        while True:
            block = response.read(CHUNK)
            if not block:
                break

            total += len(block)
            if total > MAX_DOWNLOAD:
                raise RuntimeError("download exceeded configured backup cap")

            handle.write(block)

    if total == 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("empty download")

    temporary.replace(destination)

    return {
        "url": url,
        "path": str(destination),
        "bytes": total,
        "hashes": hash_file(destination),
    }

def classify(path: Path) -> str:
    ext = path.suffix.lower()

    if ext in PACKAGE_EXTS:
        return "firmware_package"

    if ext in EXPORT_EXTS:
        return "configuration_export"

    return "other"

def update_status(
    backup: Path,
    approved_count: int,
    successful_queries: int,
    acquired: list[dict[str, Any]],
) -> dict[str, Any]:
    path = backup / "BACKUP_STATUS.json"
    status = load_json(path, {})

    firmware_count = sum(
        1 for row in acquired
        if row.get("classification") == "firmware_package"
    )
    config_count = sum(
        1 for row in acquired
        if row.get("classification") == "configuration_export"
    )

    old_stock = int(status.get("stock_package_count", 0) or 0)
    total_stock = old_stock + firmware_count

    raw_candidates = int(status.get("raw_partition_candidates", 0) or 0)
    raw_dumped = int(status.get("raw_partitions_dumped", 0) or 0)
    full_raw = raw_candidates > 0 and raw_dumped == raw_candidates

    if full_raw and total_stock > 0:
        backup_class = "FULL_RAW_PLUS_STOCK_PACKAGE"
    elif full_raw:
        backup_class = "FULL_RAW_FLASH_BACKUP"
    elif total_stock > 0:
        backup_class = "STOCK_PACKAGE_PLUS_BASELINE"
    elif raw_dumped > 0:
        backup_class = "PARTIAL_RAW_PLUS_BASELINE"
    else:
        backup_class = "BASELINE_PROGRAM_CONFIG_ONLY"

    status["backup_class"] = backup_class
    status["stock_package_count"] = total_stock
    status["authenticated_get_candidates"] = approved_count
    status["authenticated_get_success"] = successful_queries
    status["authenticated_config_export_count"] = config_count
    status["authenticated_artifact_count"] = len(acquired)
    status["full_device_restore_ready"] = False
    status["restore_procedure_proven"] = False

    dump_json(path, status)
    return status

def write_gap_report(
    backup: Path,
    status: dict[str, Any],
    approved: int,
    successful: int,
    acquired: int,
) -> None:
    missing = []

    if int(status.get("stock_package_count", 0) or 0) == 0:
        missing.append("No exact stock firmware package captured.")

    if int(status.get("raw_partition_candidates", 0) or 0) == 0:
        missing.append("No readable raw partition map through the currently exposed software interfaces.")

    if not bool(status.get("restore_procedure_proven", False)):
        missing.append("Recovery/restore procedure is not proven.")

    lines = [
        "# T6R-A Backup Gap Report",
        "",
        f"Backup class: **{status.get('backup_class')}**",
        f"Safe authenticated GET candidates: **{approved}**",
        f"Successful authenticated GET responses: **{successful}**",
        f"New acquired artifacts: **{acquired}**",
        "",
        "## Remaining gaps",
        "",
    ]

    for item in missing:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "No modem write operation was performed by this stage.",
        "",
    ])

    (backup / "BACKUP_GAP_REPORT.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", required=True)
    args = parser.parse_args()

    backup = Path(args.backup).resolve()
    base_url = find_base_url(backup)
    approved = discover_candidates(backup)

    session_id = os.environ.get("T6RA_BACKUP_SESSION_ID", "")
    token = os.environ.get("T6RA_BACKUP_TOKEN", "")

    output = backup / "08_authenticated_backup"
    responses = output / "responses"
    artifacts = output / "artifacts"

    responses.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)

    results = []
    urls: set[str] = set()

    if base_url and session_id:
        for row in approved:
            try:
                body = query_candidate(
                    base_url,
                    row,
                    session_id,
                    token,
                )

                text = body.decode("utf-8", errors="replace")
                safe_text = sanitize(text)

                response_file = responses / f"{row['uuid']}.txt"
                response_file.write_text(safe_text, encoding="utf-8")

                urls.update(extract_urls(text, base_url))

                results.append({
                    "uuid": row["uuid"],
                    "success": True,
                    "bytes": len(body),
                    "response_file": str(response_file),
                })

            except Exception as exc:
                results.append({
                    "uuid": row["uuid"],
                    "success": False,
                    "error": str(exc),
                })

    downloads = []

    for url in sorted(urls):
        ext = Path(urllib.parse.urlparse(url).path).suffix.lower()

        if ext not in PACKAGE_EXTS and ext not in EXPORT_EXTS:
            continue

        try:
            row = download(url, artifacts)
            row["classification"] = classify(Path(row["path"]))
            downloads.append(row)
        except Exception as exc:
            downloads.append({
                "url": url,
                "classification": "failed",
                "error": str(exc),
            })

    successful_downloads = [
        row for row in downloads if row.get("path")
    ]

    dump_json(output / "authenticated_query_results.json", results)
    dump_json(output / "discovered_download_urls.json", sorted(urls))
    dump_json(output / "acquired_artifacts.json", downloads)

    successful_queries = sum(
        1 for row in results if row.get("success")
    )

    status = update_status(
        backup,
        len(approved),
        successful_queries,
        successful_downloads,
    )

    write_gap_report(
        backup,
        status,
        len(approved),
        successful_queries,
        len(successful_downloads),
    )

    print(json.dumps({
        "base_url_found": bool(base_url),
        "session_supplied": bool(session_id),
        "approved_get_candidates": len(approved),
        "successful_get_queries": successful_queries,
        "discovered_download_urls": len(urls),
        "acquired_artifacts": len(successful_downloads),
        "backup_class": status.get("backup_class"),
        "stock_package_count": status.get("stock_package_count"),
        "raw_partition_candidates": status.get("raw_partition_candidates"),
        "raw_partitions_dumped": status.get("raw_partitions_dumped"),
        "restore_ready": status.get("full_device_restore_ready"),
    }, indent=2))

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
