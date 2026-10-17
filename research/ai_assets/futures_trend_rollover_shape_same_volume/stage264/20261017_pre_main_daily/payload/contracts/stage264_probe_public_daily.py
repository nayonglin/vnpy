"""Small, credential-free public daily probes; preserve and quarantine raw data.

No dependencies are installed. No database is written. No continuous symbol is
requested. URLs and field order follow the official sources recorded below.
"""
from __future__ import annotations

import csv
import argparse
from datetime import datetime, date
import hashlib
import io
import json
import math
from pathlib import Path
import sqlite3
import time
from zoneinfo import ZoneInfo

import requests


LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
OUTPUT = LINE / "outputs/stage264_pre_main_daily/public_probe"
DATABASE = ROOT / ".vntrader/database.db"
SOURCES = {
    "sina_official_akshare_source": "https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/futures_zh_sina.py",
    "edb_official_documentation": "https://doc.shinnytech.com/edb/latest/md_server.html",
}
SINA = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_V21052021_4_12=/InnerFuturesNewService.getDailyKLine"
EDB = "https://edb.shinnytech.com/md/kline"
FIELDS = ("date", "open", "high", "low", "close", "volume", "hold", "settle")
SAMPLES = [
    ("RB1505", "rb1505.SHFE", "201505"),
    ("JM1505", "jm1505.DCE", "201505"),
    ("CF1505", "CF505.CZCE", "201505"),
    ("CF505", "CF505.CZCE", "201505"),
    ("RB1905", "rb1905.SHFE", "201905"),
]


def stamp() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalized_sina(text: str) -> list[dict]:
    payload = text.split("=(", 1)[1].rsplit(");", 1)[0]
    data = json.loads(payload)
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("unexpected_sina_payload_type")
    rows = []
    for raw in data:
        if isinstance(raw, dict):
            # Akshare's direct DataFrame column reassignment uses source order.
            values = list(raw.values())
        elif isinstance(raw, list):
            values = raw
        else:
            raise ValueError("unexpected_sina_row_type")
        if len(values) != len(FIELDS):
            raise ValueError(f"unexpected_sina_field_count:{len(values)}")
        item = dict(zip(FIELDS, values))
        date.fromisoformat(str(item["date"]))
        for field in FIELDS[1:]:
            item[field] = float(item[field])
        rows.append(item)
    return rows


def normalized_edb(text: str) -> list[dict]:
    rows = []
    for raw in csv.DictReader(io.StringIO(text)):
        if "datetime_nano" not in raw:
            raise ValueError("unexpected_edb_schema")
        nano = int(raw["datetime_nano"])
        item = {"date": datetime.fromtimestamp(nano / 1e9, ZoneInfo("Asia/Shanghai")).date().isoformat()}
        item.update({field: float(raw[field]) for field in ("open", "high", "low", "close", "volume")})
        item["hold"] = float(raw["close_oi"])
        item["settle"] = ""
        item["datetime_nano"] = nano
        rows.append(item)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def inspect_rows(rows: list[dict], vt: str, delivery: str, manifest: dict, connection, known_trade_dates: set[str]) -> dict:
    dates = [row["date"] for row in rows]
    duplicate_days = len(dates) - len(set(dates))
    def valid_price(row: dict, suffix: str = "") -> bool:
        op, hi, lo, cl = (row[f"{key}{suffix}"] for key in ("open", "high", "low", "close"))
        return all(math.isfinite(value) for value in (op, hi, lo, cl)) and 0 < lo <= min(op, cl) <= max(op, cl) <= hi
    bad = [row for row in rows if not valid_price(row)]
    year, month = int(delivery[:4]), int(delivery[4:])
    # A broad plausibility window is not proof of listing/full-lifetime coverage.
    eligible = [row for row in rows if year - 2 <= int(row["date"][:4]) <= year
                and (int(row["date"][:4]), int(row["date"][5:7])) <= (year, month)]
    valid_dates = {row["date"] for row in eligible if valid_price(row) and dates.count(row["date"]) == 1}
    wrong_epoch = len(eligible) != len(rows)
    symbol, exchange = vt.rsplit(".", 1)
    db_rows = {row["datetime"][:10]: dict(row) for row in connection.execute(
        "SELECT datetime,open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata "
        "WHERE symbol=? AND exchange=? AND interval='d' AND datetime>=? AND datetime<? ORDER BY datetime",
        (symbol, exchange, f"{year-2}-01-01", f"{year+1}-01-01"))}
    mismatch, overlap, maxima, units = [], 0, {key: 0.0 for key in ("open", "high", "low", "close")}, []
    for row in eligible:
        old = db_rows.get(row["date"])
        if old is None:
            continue
        overlap += 1
        differences = {key: abs(row[key] - old[f"{key}_price"]) for key in maxima}
        for key, value in differences.items():
            maxima[key] = max(maxima[key], value)
        if any(value > 1e-8 for value in differences.values()):
            mismatch.append({"date": row["date"], "abs_price_differences": differences,
                             "public_ohlc": {key: row[key] for key in maxima},
                             "database_ohlc": {key: old[f"{key}_price"] for key in maxima}})
        if len(units) < 3:
            units.append({"date": row["date"], "public_volume": row["volume"], "database_volume": old["volume"],
                          "public_hold": row["hold"], "database_open_interest": old["open_interest"]})
    first_main = manifest["first_main_date"]
    before_dates = sorted(day for day in valid_dates if day < first_main)
    new_dates = sorted(day for day in valid_dates if day not in db_rows)
    valid_db_dates = {day for day, row in db_rows.items() if valid_price(row, "_price")}
    through = sum(day <= first_main for day in valid_dates | valid_db_dates)
    expected_in_returned_span = {day for day in known_trade_dates if dates and min(dates) <= day <= max(dates)}
    missing_dates = sorted(expected_in_returned_span - set(dates))
    extra_dates = sorted(set(dates) - known_trade_dates)
    return {
        "returned_rows": len(rows), "real_first_date": min(dates) if dates else None,
        "real_last_date": max(dates) if dates else None, "duplicate_dates": duplicate_days,
        "invalid_ohlc_rows": len(bad), "invalid_ohlc_examples": bad[:10],
        "valid_unique_price_days_in_expected_epoch": len(valid_dates), "expected_delivery_yyyymm": delivery,
        "expected_epoch_rows": len(eligible), "wrong_epoch_or_outside_plausibility_rows": len(rows)-len(eligible),
        "date_epoch_pass": bool(rows) and not wrong_epoch, "listing_date": "unknown",
        "full_lifetime_coverage_claim": False, "first_main_date": first_main,
        "public_before_first_main_days": len(before_dates), "new_before_first_main_days": sum(day not in db_rows for day in before_dates),
        "new_days_vs_existing_database": len(new_dates), "union_days_through_first_main": through,
        "AM120_ready_at_first_main_close_after_union": through >= 120,
        "overlap_days": overlap, "ohlc_mismatch_days": len(mismatch), "max_abs_ohlc_difference": maxima,
        "ohlc_mismatch_examples": mismatch[:10], "volume_oi_examples_separate_units_audit": units,
        "known_product_trading_dates_in_returned_span": len(expected_in_returned_span),
        "missing_known_trade_dates_in_returned_span": missing_dates,
        "returned_dates_absent_from_scoped_product_calendar": extra_dates,
        "calendar_limit": "manifest main-mapping product dates cover 2015-2019; dates outside this scope remain calendar-unverified",
        "acceptance": "empty" if not rows else "quarantined_wrong_epoch" if wrong_epoch else
            "quarantined_quality_or_price_mismatch" if bad or duplicate_days or mismatch or missing_dates else
            "candidate_requires_independent_review" if overlap else "unverified_no_same_epoch_overlap",
        "volume_oi_unit_policy": "retain_source_units_no_pre2020_conversion_or_silent_replacement",
    }


def main(analyze_saved: bool = False) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest_rows = json.loads((OUTPUT.parent / "manifest_contracts.json").read_text())
    manifests = {row["contract_epoch_id"]: row for row in manifest_rows}
    known_trade_dates = {}
    with (OUTPUT.parent / "manifest_main_dates.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            known_trade_dates.setdefault(row["product"], set()).add(row["date"])
    connection = sqlite3.connect(DATABASE.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    probes = []
    previous = json.loads((OUTPUT / "public_provider_probe.json").read_text()) if analyze_saved else None
    specs = [("sina", alias, vt, delivery, SINA, {"symbol": alias, "type": "2021_04_12"})
             for alias, vt, delivery in SAMPLES]
    specs.append(("edb", "SHFE.rb1505", "rb1505.SHFE", "201505", EDB,
                  {"period": 86400, "symbol": "SHFE.rb1505", "start_time": "2014-01-01 00:00:00", "end_time": "2015-05-31 23:59:59"}))
    try:
        for index, (vendor, alias, vt, delivery, url, params) in enumerate(specs):
            if index and not analyze_saved:
                time.sleep(1)
            probe = {"vendor": vendor, "requested_symbol": alias, "contract_epoch_id": f"{vt}@{delivery}",
                     "requested_at": stamp(), "method": "GET", "base_url": url, "query": params,
                     "authentication": "none", "automatic_retries": 0}
            key = f"{vendor}_{alias.replace('.', '_')}_{delivery}"
            try:
                raw_path = OUTPUT / f"{key}.raw.txt"
                if analyze_saved:
                    probe = dict(previous["probes"][index])
                    raw = raw_path.read_bytes()
                    if sha(raw) != probe["raw_sha256"]:
                        raise ValueError("saved_raw_sha_mismatch")
                    # Akshare/Sina payloads have ASCII JSON; EDB is UTF-8 CSV.
                    body = raw.decode("gbk" if vendor == "sina" else "utf-8-sig")
                    probe["reanalyzed_from_saved_raw_at"] = stamp()
                else:
                    response = requests.get(url, params=params, timeout=(10, 30))
                    raw = response.content
                    body = response.text
                    raw_path.write_bytes(raw)
                    probe.update({"completed_at": stamp(), "request_url": response.url, "http_status": response.status_code,
                                  "content_type": response.headers.get("content-type", ""), "raw_bytes": len(raw),
                                  "raw_path": str(raw_path.relative_to(LINE)), "raw_sha256": sha(raw)})
                if probe["http_status"] != 200:
                    probe.update({"status": "http_failure_no_retry", "response_excerpt": body[:250]})
                else:
                    try:
                        rows = normalized_sina(body) if vendor == "sina" else normalized_edb(body)
                        write_csv(OUTPUT / f"{key}.normalized.csv", rows)
                        subset = [row for row in rows if "2014-01-01" <= row["date"] <= "2015-12-31"]
                        write_csv(OUTPUT / f"{key}.2014_2015.csv", subset)
                        manifest = manifests[f"{vt}@{delivery}"]
                        probe.update(inspect_rows(rows, vt, delivery, manifest, connection, known_trade_dates[manifest["product"]]))
                        probe["status"] = "parsed" if rows else "empty_no_retry"
                    except (ValueError, IndexError, KeyError, TypeError) as error:
                        probe.update({"status": "parse_failed_no_retry", "parse_error_type": type(error).__name__,
                                      "parse_error": str(error)[:200], "response_excerpt": body[:250]})
            except requests.RequestException as error:
                probe.update({"completed_at": stamp(), "status": "transport_failure_no_retry",
                              "error_type": type(error).__name__, "error": str(error)[:300]})
            probes.append(probe)
            print(json.dumps({key: probe.get(key) for key in ("vendor", "requested_symbol", "status", "http_status", "returned_rows", "real_first_date", "real_last_date", "acceptance", "new_before_first_main_days")}, ensure_ascii=False), flush=True)
            report = {"generated_at": stamp(), "line_id": "futures_trend_rollover_shape_same_volume", "stage": "Stage264",
                      "completed": len(probes) == len(specs), "public_http_requests": len(probes),
                      "last_analysis_mode": "saved_raw_no_network" if analyze_saved else "public_get",
                      "official_sources_checked": SOURCES, "source_contract": {
                          "sina_parameters": "futures_zh_daily_sina official Akshare source: symbol and type=2021_04_12; unmodified ordinary GET",
                          "edb_scope": "official doc: daily without token; anticipated history begins 2021-01-01, not proof of 2015 availability"},
                      "safety": {"private_credentials_read": False, "database_writes": False, "official_source_changes": False,
                                 "training_runs": 0, "backtest_runs": 0, "continuous_symbols_requested": False,
                                 "dependencies_installed": False}, "probes": probes}
            (OUTPUT / "public_provider_probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analyze-saved", action="store_true", help="Revalidate preserved responses with zero network requests")
    main(parser.parse_args().analyze_saved)
