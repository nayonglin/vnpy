from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
OUTPUT = ROOT / "artifacts/stage012_alternative_spot_source"
TARGETS = {"RB": "\u87ba\u7eb9\u94a2", "AP": "\u82f9\u679c"}
PAGE = "https://www.99qh.com/data/spotTrend"
BOOTSTRAP = "https://centerapi.fx168api.com/app/common/v.js"
TREND = "https://centerapi.fx168api.com/app/qh/api/spot/trend"


def identity(path):
    return {"path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def source_identities():
    previous = ROOT / "artifacts/stage011_basis_source_audit"
    summary_path = previous / "summary.json"
    if identity(summary_path)["sha256"] != "66ecfd90e71419a1a5533eaa2f0669406ba9f5b330b4de13ae204f298661adef":
        raise RuntimeError("previous_source_audit_changed")
    summary = json.loads(summary_path.read_text())
    manifest_path = previous / "input_manifest.json"
    if identity(manifest_path) != summary["input_manifest"]:
        raise RuntimeError("previous_source_manifest_changed")
    files = json.loads(manifest_path.read_text())
    if any(identity(Path(path)) != expected for path, expected in files.items()):
        raise RuntimeError("previous_source_inputs_changed")
    added = [Path(__file__), ROOT / "tests/test_stage012_alternative_spot_source.py",
             ROOT / "stages/20260906_0257_stage012_alternative_spot_source_contract.md",
             REPO / ".py311/lib/python3.11/site-packages/akshare/spot/spot_price_qh.py",
             summary_path, manifest_path]
    files.update({str(path): identity(path) for path in added})
    return files


def catalog(html):
    page = BeautifulSoup(html, "html.parser")
    scripts = page.find_all("script", id="__NEXT_DATA__")
    if len(scripts) != 1:
        raise RuntimeError("public_catalog_missing_or_access_check")
    try:
        payload = json.loads(scripts[0].string or scripts[0].get_text())
        groups = payload["props"]["pageProps"]["data"]["varietyListData"]
        rows = [{key: item[key] for key in ("qhExchangeName", "name", "productId")}
                for group in groups for item in group["productList"]]
    except (ValueError, TypeError, KeyError) as exc:
        raise RuntimeError("public_catalog_schema_invalid") from exc
    ids, names = set(), set()
    for row in rows:
        if (not isinstance(row["name"], str) or not row["name"] or not row["qhExchangeName"]
                or isinstance(row["productId"], bool) or not str(row["productId"]).isdigit()):
            raise RuntimeError("public_catalog_identity_invalid")
        if str(row["productId"]) in ids or row["name"] in names:
            raise RuntimeError("public_catalog_duplicate")
        ids.add(str(row["productId"]))
        names.add(row["name"])
    if not rows:
        raise RuntimeError("public_catalog_empty")
    return rows


def history(payload):
    if not isinstance(payload, dict) or payload.get("code", 200) not in (0, 200):
        raise RuntimeError("history_business_rejected")
    if payload.get("success", True) is not True:
        raise RuntimeError("history_business_rejected")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("list"), list) or not data["list"]:
        raise RuntimeError("history_list_missing_or_empty")
    if len(data["list"]) >= 50000 or any(int(data[key]) != len(data["list"]) for key in ("total", "totalCount") if key in data):
        raise RuntimeError("history_pagination_incomplete")
    frame = pd.DataFrame(data["list"])
    if not set(("date", "fp", "sp")).issubset(frame.columns):
        raise RuntimeError("history_columns_invalid")
    rows = frame[["date", "fp", "sp"]].copy()
    if not rows.date.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise RuntimeError("history_date_format_invalid")
    try:
        pd.to_datetime(rows.date, format="%Y-%m-%d", errors="raise")
    except ValueError as exc:
        raise RuntimeError("history_date_invalid") from exc
    if rows.date.duplicated().any():
        raise RuntimeError("history_duplicate_date")
    if rows.date.lt("2020-01-01").any() or rows.date.gt("2026-08-28").any():
        raise RuntimeError("history_outside_requested_window")
    numbers = rows[["fp", "sp"]].apply(pd.to_numeric, errors="coerce")
    rows["quality_ok"] = np.isfinite(numbers).all(axis=1) & numbers.gt(0).all(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        rows["futures_over_spot_minus_one"] = (numbers.fp / numbers.sp - 1).where(rows.quality_ok)
    rows = rows.sort_values("date").reset_index(drop=True)
    return rows, {"rows": len(rows), "quality_ok_rows": int(rows.quality_ok.sum()),
                  "first_date": rows.date.min(), "last_date": rows.date.max(),
                  "raw_fields": sorted(frame.columns.tolist()), "data_metadata_fields": sorted(data),
                  "futures_price_type": "vendor_close_not_settlement", "historical_publication_verified": False,
                  "historical_revisions_verified": False, "safe_to_splice_into_100ppi": False}


def run():
    if OUTPUT.exists():
        raise RuntimeError("alternative_spot_output_already_exists")
    files = source_identities()
    OUTPUT.mkdir(parents=True)
    save(OUTPUT / "input_manifest.json", files)
    records, samples, unavailable = [], {}, []

    def get(name, url, *, params=None, header=None, persist_body=True):
        if len(records) >= 4:
            raise RuntimeError("request_budget_exceeded")
        record = {"name": name, "url": url, "params": params, "attempts": 1,
                  "started_at_utc": datetime.now(timezone.utc).isoformat(), "http_status": None}
        records.append(record)
        headers = {"User-Agent": "vnpy-research-source-audit/1.0"}
        if header is not None:
            headers.update({"_pcc": header, "Origin": "https://www.99qh.com", "Referer": "https://www.99qh.com"})
        try:
            response = requests.get(url, params=params, headers=headers, timeout=(5, 10), allow_redirects=False)
            record.update(http_status=response.status_code, bytes=len(response.content),
                          body_sha256=hashlib.sha256(response.content).hexdigest())
            if persist_body:
                body_path = OUTPUT / f"{name}.raw"
                body_path.write_bytes(response.content)
                record["raw_response"] = identity(body_path)
            if response.status_code != 200:
                raise RuntimeError(f"http_rejected:{response.status_code}")
            return response
        finally:
            record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
            save(OUTPUT / f"{name}.request.json", record)

    try:
        entries = catalog(get("catalog", PAGE).content)
        save(OUTPUT / "catalog.json", entries)
        selected = {key: next((entry for entry in entries if entry["name"] == name), None)
                    for key, name in TARGETS.items()}
        unavailable = [key for key, entry in selected.items() if entry is None]
        if not any(selected.values()):
            raise RuntimeError("target_products_not_in_catalog")
        # This is the public SDK's anonymous response header, never a user credential.
        header = get("public_bootstrap", BOOTSTRAP, persist_body=False).headers.get("_pcc")
        if not isinstance(header, str) or not header.strip():
            raise RuntimeError("public_header_unavailable_stop_no_bypass")
        for key, entry in selected.items():
            if entry is None:
                continue
            params = {"productId": entry["productId"], "pageNo": "1", "pageSize": "50000",
                      "startDate": "2020-01-01", "endDate": "2026-08-28", "appCategory": "web"}
            response = get(f"history_{key}", TREND, params=params, header=header)
            rows, meta = history(json.loads(response.content))
            output = OUTPUT / f"history_{key}.csv"
            rows.to_csv(output, index=False)
            samples[key] = {**meta, "product": entry, "output": identity(output)}
        header = None
        status, error = "samples_observed_not_full_source_qualification", None
    except Exception as exc:
        status, error = "source_not_qualified", f"{type(exc).__name__}:{exc}"
    if any(identity(Path(path)) != expected for path, expected in files.items()):
        raise RuntimeError("source_inputs_changed_during_probe")
    result = {"status": status, "error": error, "history": samples, "products_absent_from_catalog": unavailable,
              "requests": records, "request_count": len(records), "retry_count": 0,
              "old_basis_cache_modified": False, "full_data_extension_performed": False,
              "new_historical_models": 0, "new_labels": 0, "new_backtests": 0, "reviewers": 0,
              "input_manifest": identity(OUTPUT / "input_manifest.json")}
    save(OUTPUT / "summary.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, allow_nan=False))
