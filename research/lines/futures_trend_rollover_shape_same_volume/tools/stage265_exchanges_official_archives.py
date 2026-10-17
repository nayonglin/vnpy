"""Stage265 official public daily archives, isolated research output only.

Download only routes published in retained SHFE/INE official indexes. Complete
archives are verified and reused; .part files may resume through normal Range
requests. No credentials, cookies, environment proxies, or automatic retries.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import urljoin, urlsplit
import zipfile
from zoneinfo import ZoneInfo

LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "outputs/stage265_deep_daily/other_exchanges"
OLD = LINE / "outputs/stage264_pre_main_daily"
MAX_BYTES = 96 * 1024 * 1024


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.replace(temp, path)


def archive_info(path):
    p = Path(path)
    members = []
    with zipfile.ZipFile(p) as z:
        if sum(i.file_size for i in z.infolist()) > 1024 * 1024 * 1024:
            raise ValueError("expanded_size_limit")
        bad = z.testzip()
        if bad:
            raise ValueError("zip_crc_failed")
        for i in z.infolist():
            if i.is_dir():
                continue
            try:
                name = i.filename if i.flag_bits & 0x800 else i.filename.encode("cp437").decode("gbk")
            except (UnicodeError, ValueError):
                name = i.filename
            members.append({"name": i.filename, "display_name": name,
                            "bytes": i.file_size, "crc32": f"{i.CRC:08x}"})
    if not members:
        raise ValueError("empty_archive")
    return {"bytes": p.stat().st_size, "sha256": digest(p),
            "zip_valid": True, "crc_valid": True, "members": members}


def plan(earliest):
    old_state = json.loads((OLD / "shfe_official/year_download_status.json").read_text())
    old_records = {int(v["year"]): v for v in old_state["years"] if v.get("status") == "downloaded"}
    sources = []
    for exchange, domain, index in [
        ("SHFE", "www.shfe.com.cn", OLD / "shfe_archive_index.json"),
        ("INE", "www.ine.cn", OUT / "ine_index.txt"),
    ]:
        raw = json.loads(index.read_text())
        for group in ("historicalData", "latestData"):
            for entry in raw["data"][group]:
                year = int(entry["year"])
                if str(entry["type"]) != "1" or year < earliest:
                    continue
                url = urljoin(f"https://{domain}", entry["url"])
                parts = urlsplit(url)
                if parts.scheme != "https" or parts.netloc != domain or not parts.path.endswith(".zip"):
                    raise ValueError("non_official_archive_route")
                path = OUT / exchange.lower() / "raw_years" / f"{exchange.lower()}_futures_{year}.zip"
                rec = {"source_id": f"{exchange}_futures_{year}", "exchange": exchange,
                       "year": year, "url": url, "path": str(path), "status": "pending",
                       "index_path": str(index), "index_sha256": digest(index),
                       "index_url": f"https://{domain}/reports/tradedata/datadownload/download.json",
                       "archive_kind": "year_to_date" if group == "latestData" else "historical_year",
                       "timestamp_semantics": "exchange_trade_date_not_intraday_timestamp",
                       "oi_semantics": "official_end_of_day_position_not_TQ_open_oi",
                       "volume_oi_side": "preserve_original_archive_notes_no_automatic_halving"}
                if exchange == "SHFE" and year in old_records:
                    old = old_records[year]
                    if old["url"] != url:
                        raise ValueError("existing_archive_route_changed")
                    rec.update(path=old["path"], status="reused_stage264", bytes=old["bytes"],
                               sha256=old["sha256"], original_download_at=old.get("completed_at"))
                sources.append(rec)
    return sorted(sources, key=lambda r: (r["exchange"], r["year"]))


def fetch(rec, session):
    path = Path(rec["path"])
    if path.exists():
        info = archive_info(path)
        if rec.get("sha256") and rec["sha256"] != info["sha256"]:
            raise ValueError("completed_archive_sha_mismatch")
        return {**info, "status": rec["status"] if rec["status"] == "reused_stage264" else "downloaded",
                "action": "verified_existing", "last_verified_at": now()}
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": "Stage265-public-daily-research/1.0", "Accept": "application/zip,*/*"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
        if rec.get("etag"):
            headers["If-Range"] = rec["etag"]
    rec.setdefault("attempts", []).append({"started_at": now(), "resume_offset": offset})
    with session.get(rec["url"], headers=headers, stream=True, timeout=(12, 45), allow_redirects=False) as response:
        rec["attempts"][-1]["http_status"] = response.status_code
        if response.status_code not in (200, 206):
            raise ValueError(f"http_status_{response.status_code}")
        if response.status_code == 206:
            if not offset or not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                raise ValueError("range_response_mismatch")
            mode = "ab"
        else:
            mode, offset = "wb", 0
        length = response.headers.get("Content-Length", "")
        if length.isdigit() and offset + int(length) > MAX_BYTES:
            raise ValueError("declared_size_limit")
        rec.update(etag=response.headers.get("ETag"), last_modified=response.headers.get("Last-Modified"),
                   content_type=response.headers.get("Content-Type"))
        received = offset
        with partial.open(mode) as f:
            for block in response.iter_content(65536):
                received += len(block)
                if received > MAX_BYTES:
                    raise ValueError("stream_size_limit")
                f.write(block)
    info = archive_info(partial)
    os.replace(partial, path)
    return {**info, "status": "downloaded", "action": "downloaded",
            "completed_at": now(), "last_verified_at": now()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--earliest-year", type=int, default=2010)
    p.add_argument("--download", action="store_true")
    p.add_argument("--exchange", nargs="+", choices=["SHFE", "INE"], default=["SHFE", "INE"])
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "official_archive_sources_manifest.json"
    previous = json.loads(manifest.read_text()) if manifest.exists() else {}
    prior = {r["source_id"]: r for r in previous.get("sources", [])}
    sources = plan(a.earliest_year)
    for r in sources:
        old = prior.get(r["source_id"])
        if old and old["url"] == r["url"] and old["path"] == r["path"]:
            r.update(old)
    state = {"created_at": previous.get("created_at", now()), "updated_at": now(),
             "purpose": "isolated_all_contract_daily_official_reference_archives",
             "target_complete_trade_date": "2026-10-16", "earliest_requested_year": a.earliest_year,
             "credentials_used": False, "main_database_written": False,
             "script_sha256": digest(__file__), "sources": sources}
    save(manifest, state)
    if not a.download:
        print(json.dumps({"status": "planned", "archive_count": len(sources),
                          "reuse_count": sum(r["status"] == "reused_stage264" for r in sources)}))
        return
    import requests
    with requests.Session() as session:
        session.trust_env = False
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
        for rec in sources:
            if rec["exchange"] not in a.exchange:
                continue
            try:
                result = fetch(rec, session)
                rec.update(result)
            except Exception as error:
                rec.update(status="failed", error_type=type(error).__name__, error=str(error), failed_at=now())
            state["updated_at"] = now()
            save(manifest, state)
            print(json.dumps({k: rec.get(k) for k in ("source_id", "status", "action", "bytes", "error_type")}), flush=True)
            time.sleep(.35)


if __name__ == "__main__":
    main()
