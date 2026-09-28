from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/stage013b_cffex_root_source_http"
_parent = None


def parent():
    global _parent
    if _parent is None:
        path = ROOT / "tools/stage013_cffex_root_source.py"
        if hashlib.sha256(path.read_bytes()).hexdigest() != "667935a6f5f7bbe9a6414972cbe2184455dcd06175b06b1498d3f9952e5b8143":
            raise RuntimeError("scientific_parent_changed")
        spec = importlib.util.spec_from_file_location("cffex_source_scientific_parent", path)
        _parent = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_parent)
    return _parent


def download(month, destination):
    base = parent()
    if month not in ("202606", "202607", "202608"):
        raise RuntimeError("download_month_outside_contract")
    path, receipt = destination / f"{month}.response", destination / f"{month}.request.json"
    if path.exists() or receipt.exists():
        raise RuntimeError("download_attempt_already_exists")
    url = base.helper().CFFEX_ARCHIVE_URL.format(month=month)
    if url != f"http://www.cffex.com.cn/sj/historysj/{month}/zip/{month}.zip":
        raise RuntimeError("official_http_source_url_changed")
    record = {"month": month, "url": url, "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "http_status": None, "attempts": 1, "retries": 0, "transport_authenticated_by_tls": False}
    try:
        response = requests.get(url, headers={"User-Agent": "vnpy-research-source-audit/1.0",
                               "Accept": "application/zip,application/octet-stream", "Referer": "https://www.cffex.com.cn/lssjxz/"},
                                timeout=(5, 20), allow_redirects=False)
        path.write_bytes(response.content)
        record.update(http_status=response.status_code, response=base.identity(path))
        if response.status_code != 200:
            raise RuntimeError(f"source_http_failure:{month}:{response.status_code}")
        return response.content
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}:{exc}"
        raise
    finally:
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        base.save(receipt, record)


def configured():
    base = parent()
    if not hasattr(base, "original_source_identities"):
        base.original_source_identities = base.source_identities

    def extended_identities():
        files, months = base.original_source_identities()
        old_urls = base.OLD_DATA / "source_archives.csv"
        expected = json.loads((base.OLD_DATA / "artifact_manifest.json").read_text())["files"]["source_archives.csv"]
        if base.identity(old_urls)["sha256"] != expected["sha256"]:
            raise RuntimeError("old_successful_source_urls_changed")
        failure = ROOT / "artifacts/stage013_cffex_root_source/summary.json"
        if base.identity(failure)["sha256"] != "517865975d3c1814f27bb08551d862c2291ac67d25ce5be41ae954b4f90c234b":
            raise RuntimeError("previous_transport_failure_changed")
        added = [Path(__file__), ROOT / "tests/test_stage013b_cffex_http_transport.py",
                 ROOT / "stages/20260906_0325_stage013b_transport_amendment.md", old_urls, failure,
                 ROOT.parents[2] / ".py311/lib/python3.11/site-packages/akshare/futures/futures_daily_bar.py"]
        files.update({str(path): base.identity(path) for path in added})
        return files, months

    base.source_identities = extended_identities
    base.download = download
    base.OUTPUT = OUTPUT
    return base


def run():
    if OUTPUT.exists():
        raise RuntimeError("cffex_http_output_already_exists")
    return configured().run()


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, allow_nan=False))
