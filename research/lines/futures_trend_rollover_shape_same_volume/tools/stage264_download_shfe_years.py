"""官方索引限定的SHFE年度原包下载；默认只列计划，--verify-only全程离线。

--download --years 2015 为首包；其他年份须已存在独立首包gate及其原包SHA。
完成文件核SHA/CRC后跳过；残留.part不覆盖，不自动重试或自动续传。
本工具在2026-10-17原始内联下载完成后落盘，不冒认历史下载入口。
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import zipfile
from zoneinfo import ZoneInfo

LINE_ROOT = Path(__file__).resolve().parents[1]
ROOT = LINE_ROOT / "outputs/stage264_pre_main_daily"
INDEX_URL = "https://www.shfe.com.cn/reports/tradedata/datadownload/download.json"
MAX_BYTES = 32 * 1024 * 1024
ALLOWED_YEARS = set(range(2014, 2020))
OLE_SIGNATURE = bytes.fromhex("d0cf11e0a1b11ae1")


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_routes(index_path, selection_path):
    index_path = Path(index_path)
    selection = json.loads(Path(selection_path).read_text())
    if selection["index_url"] != INDEX_URL or sha256(index_path) != selection["index_sha256"]:
        raise ValueError("index_identity_mismatch")
    original = json.loads(index_path.read_text())["data"]["historicalData"]
    valid = {(int(v["year"]), v["url"]) for v in original if str(v["type"]) == "1"}
    routes = {}
    for entry in selection["selection"]:
        year = int(entry["year"])
        raw = entry["url"]
        if str(entry["type"]) != "1" or year not in ALLOWED_YEARS or year in routes:
            raise ValueError("selection_year_or_type_invalid")
        if (year, raw) not in valid:
            raise ValueError("selection_not_in_official_index")
        url = urljoin("https://www.shfe.com.cn", raw)
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc != "www.shfe.com.cn" or parts.query or parts.fragment:
            raise ValueError("non_official_download_url")
        if not parts.path.startswith("/reports/tradedata/datadownload/") or not parts.path.endswith(".zip"):
            raise ValueError("non_archive_download_url")
        routes[year] = url
    return routes


def verify_archive(path, expected_sha=None, expected_bytes=None):
    path = Path(path)
    digest = sha256(path)
    if expected_sha is not None and digest != expected_sha:
        raise ValueError("archive_sha256_mismatch")
    size = path.stat().st_size
    if size > MAX_BYTES or (expected_bytes is not None and size != expected_bytes):
        raise ValueError("archive_size_mismatch")
    members = []
    with zipfile.ZipFile(path) as archive:
        # Inspect sizes before decompression; actual six archives are <40MiB each unpacked.
        if sum(v.file_size for v in archive.infolist()) > 256 * 1024 * 1024:
            raise ValueError("expanded_size_limit")
        if archive.testzip() is not None:
            raise ValueError("archive_crc_mismatch")
        for info in archive.infolist():
            if info.is_dir():
                continue
            with archive.open(info) as stream:
                if stream.read(8) != OLE_SIGNATURE:
                    raise ValueError("member_not_ole_xls")
            try:
                display = info.filename if info.flag_bits & 0x800 else info.filename.encode("cp437").decode("gbk")
            except (UnicodeEncodeError, UnicodeDecodeError):
                display = info.filename
            members.append({"name": info.filename, "display_name": display,
                            "uncompressed_bytes": info.file_size, "compressed_bytes": info.compress_size,
                            "is_dir": False})
    if not members:
        raise ValueError("archive_has_no_xls_members")
    return {"bytes": size, "sha256": digest, "zip_valid": True, "crc_valid": True,
            "all_members_ole_xls": True, "members": members}


def require_first_sample_gate(state):
    gate = state.get("first_sample_gate", {})
    first = next((v for v in state["years"] if v["year"] == 2015), None)
    if gate.get("gate") != "pass" or not gate.get("archive_sha256") or first is None:
        raise ValueError("independent_first_sample_gate_missing")
    if first.get("status") != "downloaded":
        raise ValueError("first_sample_not_downloaded")
    verify_archive(first["path"], expected_sha=gate["archive_sha256"])


def write_response(response, path, max_bytes=MAX_BYTES):
    path = Path(path)
    partial = path.with_suffix(".part")
    if path.exists() or partial.exists():
        raise ValueError("existing_file_do_not_overwrite")
    if response.status_code != 200:
        raise ValueError("http_status_rejected")
    declared = response.headers.get("Content-Length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise ValueError("declared_size_limit")
    received = 0
    with partial.open("xb") as stream:
        for block in response.iter_content(chunk_size=65536):
            received += len(block)
            if received > max_bytes:
                raise ValueError("stream_size_limit")
            stream.write(block)
    result = verify_archive(partial)
    os.replace(partial, path)
    return result


def download_one(record, session):
    path = Path(record["path"])
    if record.get("status") == "downloaded":
        return {"action": "verified_existing", **verify_archive(
            path, expected_sha=record["sha256"], expected_bytes=record["bytes"])}
    if path.exists() or path.with_suffix(".part").exists():
        raise ValueError("unregistered_or_partial_file_stop")
    with session.get(record["url"], headers={"User-Agent": "research-readonly-archive-download/1.0",
                     "Accept": "application/zip,*/*"}, stream=True, timeout=(8, 30),
                     allow_redirects=False) as response:
        result = write_response(response, path)
        return {"action": "downloaded", "http_status": response.status_code,
                "content_type": response.headers.get("Content-Type"), **result}


def save_state(path, state):
    state["updated_at"] = now()
    temp = path.with_suffix(".tmp.json")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    os.replace(temp, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=ROOT / "shfe_archive_index.json")
    parser.add_argument("--selection", type=Path, default=ROOT / "shfe_archive_index_selection.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "shfe_official")
    parser.add_argument("--years", type=int, nargs="+", default=[2015])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--download", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    try:
        routes = load_routes(args.index, args.selection)
        years = list(dict.fromkeys(args.years))
        if not set(years) <= set(routes):
            raise ValueError("requested_year_not_in_selection")
        out = args.output_dir.resolve()
        out.relative_to(ROOT.resolve())
        status_path = out / "year_download_status.json"
        if not args.download and not args.verify_only:
            print(json.dumps({"status": "plan_only", "years": years,
                              "urls": [routes[v] for v in years]}, ensure_ascii=False))
            return 0
        if status_path.exists():
            state = json.loads(status_path.read_text())
            if state["index_sha256"] != sha256(args.index):
                raise ValueError("status_index_identity_mismatch")
            for rec in state["years"]:
                expected = out / "raw_years" / f"shfe_futures_{rec['year']}.zip"
                if rec["url"] != routes[rec["year"]] or Path(rec["path"]).resolve() != expected:
                    raise ValueError("status_route_or_path_mismatch")
        elif args.verify_only:
            raise ValueError("status_missing")
        else:
            state = {"index_url": INDEX_URL, "index_sha256": sha256(args.index),
                     "max_bytes_per_archive": MAX_BYTES, "authenticated_requests": 0,
                     "download_method": "reusable_entrypoint", "years": [
                         {"year": year, "url": url, "status": "pending",
                          "path": str(out / "raw_years" / f"shfe_futures_{year}.zip")}
                         for year, url in sorted(routes.items())]}
        selected = [next(v for v in state["years"] if v["year"] == y) for y in years]
        if args.verify_only:
            result = [dict(year=r["year"], **verify_archive(r["path"], r["sha256"], r["bytes"]))
                      for r in selected if r.get("status") == "downloaded"]
            if len(result) != len(selected):
                raise ValueError("requested_archive_not_complete")
            print(json.dumps({"status": "verified_offline", "archives": result}, ensure_ascii=False))
            return 0
        import requests
        (out / "raw_years").mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.trust_env = False  # No environment proxy or .netrc automatic credentials.
            session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
            for rec in selected:
                if rec.get("status") != "downloaded" and rec["year"] != 2015:
                    require_first_sample_gate(state)
                rec["attempt_started_at"] = now()
                try:
                    result = download_one(rec, session)
                    rec.update(result, status="downloaded", last_verified_at=now())
                    if result["action"] == "downloaded":
                        rec.update(completed_at=now(), download_entrypoint_sha256=sha256(__file__))
                except Exception as error:
                    rec.update(status="failed", error_type=type(error).__name__, failed_at=now())
                    save_state(status_path, state)
                    raise
                save_state(status_path, state)
                print(json.dumps({"year": rec["year"], "action": result["action"],
                                  "sha256": rec["sha256"]}, ensure_ascii=False), flush=True)
        return 0
    except Exception as error:
        # Never print SDK/request exception bodies, headers or traceback.
        print(json.dumps({"status": "stopped", "error_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
