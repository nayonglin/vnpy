"""Build a read-only research manifest; never download, trade, train or replay.

The scoped epoch universe comes from actual nonempty 2015--2019 main mappings.
Full-mapping first/last main dates remain distinct from scoped first/last dates.
CZCE date anchors follow Stage196's nearest unexpired delivery-month rule, with
an explicit three-year plausibility guard and no silent decade fallback.
"""
from __future__ import annotations

import calendar
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
from zoneinfo import ZoneInfo


LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
MAPPING = ROOT / "examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
DATABASE = ROOT / ".vntrader/database.db"
OUTPUT = LINE / "outputs/stage264_pre_main_daily"
START, END, SOURCE_PRELOAD, AM = "2015-01-01", "2019-12-31", "2015-01-01", 120
PRODUCTS = set("AP.CZCE CF.CZCE FG.CZCE MA.CZCE OI.CZCE SA.CZCE SH.CZCE SM.CZCE au.SHFE cu.SHFE hc.SHFE jm.DCE lc.GFEX lh.DCE rb.SHFE ru.SHFE si.GFEX sp.SHFE".split())
SUFFIXES = {"CZCE": "ZCE", "SHFE": "SHF", "DCE": "DCE", "CFFEX": "CFX", "INE": "INE", "GFEX": "GFE"}
DOCUMENTATION = {
    "rqdata": "https://www.ricequant.com/doc/rqdata/python/generic-api",
    "rqdata_historical_product_codes": "https://www.ricequant.com/doc/rqdata/python/futures-mod#郑商所相关数据约定",
    "tushare_contract_codes": "https://tushare.pro/document/2?doc_id=134",
    "tushare_contract_metadata": "https://tushare.pro/document/2?doc_id=135",
    "tq_contract_codes": "https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html",
    "tq_downloader_source": "https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/tools/downloader.py",
}


def contract_identity(vt_symbol: str, anchor_date: str) -> dict:
    """Resolve a real contract near its observed date, never a continuous code."""
    match = re.fullmatch(r"([A-Za-z]+)([0-9]{3,4})\.([A-Z]+)", vt_symbol)
    if not match:
        raise ValueError(f"not_a_real_contract:{vt_symbol}")
    product, digits, exchange = match.groups()
    anchor = date.fromisoformat(anchor_date)
    month = int(digits[-2:])
    if not 1 <= month <= 12 or exchange not in SUFFIXES:
        raise ValueError(f"invalid_contract:{vt_symbol}")
    if len(digits) == 3 and exchange != "CZCE":
        raise ValueError(f"three_digits_outside_czce:{vt_symbol}")
    modulus = 10 if len(digits) == 3 else 100
    residue = int(digits[:-2])
    candidates = []
    for year in range(anchor.year - 1, anchor.year + 4):
        if year % modulus != residue:
            continue
        delivery_end = date(year, month, calendar.monthrange(year, month)[1])
        distance = (delivery_end - anchor).days
        if -20 <= distance <= 3 * 366:
            candidates.append((distance < 0, abs(distance), year))
    if not candidates:
        raise ValueError(f"unresolvable_contract_epoch:{vt_symbol}:{anchor_date}")
    year = min(candidates)[2]
    yymm, yyyymm = f"{year % 100:02d}{month:02d}", f"{year:04d}{month:02d}"
    legacy_methanol = exchange == "CZCE" and product == "MA" and yyyymm <= "201505"
    return {
        "contract_epoch_id": f"{vt_symbol}@{yyyymm}", "product": f"{product}.{exchange}",
        "vt_symbol": vt_symbol, "exchange": exchange, "contract_yyyymm": yyyymm,
        "tq_yymm_alias_candidate": f"{exchange}.{product}{yymm}",
        "tq_yymm_alias_status": "unverified_alias_not_officially_documented" if len(digits) == 3 else "same_as_mapping_symbol",
        "rqdata_order_book_id": "unknown" if legacy_methanol else f"{product.upper()}{yymm}",
        "rqdata_normalized_format_candidate": f"{product.upper()}{yymm}",
        "rqdata_historical_alias_candidate": f"ME{yymm}" if legacy_methanol else "none_documented",
        "rqdata_code_status": "legacy_methanol_metadata_and_multiplier_review_required_no_auto_merge" if legacy_methanol else "official_documentation_format_only_catalog_not_queried",
        "tushare_ts_code": f"{product.upper()}{yymm}.{SUFFIXES[exchange]}",
        "tushare_code_status": "official_documentation_format_only_catalog_not_queried",
    }


def valid_ohlc(row: dict) -> bool:
    values = [row[field] for field in ("open_price", "high_price", "low_price", "close_price")]
    if not all(value is not None and math.isfinite(value) and value > 0 for value in values):
        return False
    op, hi, lo, cl = values
    return lo <= min(op, cl) <= max(op, cl) <= hi


def summarize_bars(rows: list[dict], vt_symbol: str, yyyymm: str, first_main: str, scope_first: str) -> dict:
    """Count unique valid same-delivery days, with strict before/through clocks."""
    by_day = defaultdict(list)
    unresolved = 0
    for row in rows:
        day = row["datetime"][:10]
        try:
            identity = contract_identity(vt_symbol, day)
        except ValueError:
            unresolved += 1
            continue
        if identity["contract_yyyymm"] == yyyymm:
            by_day[day].append(row)
    valid_dates, invalid_rows, duplicate_days = [], 0, 0
    for day, actual in sorted(by_day.items()):
        duplicate_days += len(actual) > 1
        bad = sum(not valid_ohlc(row) for row in actual)
        invalid_rows += bad
        if len(actual) == 1 and not bad:
            valid_dates.append(day)
    before = sum(day < first_main for day in valid_dates)
    through = sum(day <= first_main for day in valid_dates)
    scope_through = sum(SOURCE_PRELOAD <= day <= scope_first for day in valid_dates)
    return {
        "history_count_before_first_main": before,
        "history_count_through_first_main": through,
        "needed_bars_lower_bound": max(0, AM - through),
        "AM120_ready_at_first_main_close": through >= AM,
        "history_count_before_first_main_in_scope": sum(day < scope_first for day in valid_dates),
        "history_count_through_first_main_in_scope": sum(day <= scope_first for day in valid_dates),
        "source_scope_history_count_through_first_main_in_scope": scope_through,
        "source_scope_needed_bars_lower_bound": max(0, AM - scope_through),
        "source_scope_AM120_ready": scope_through >= AM,
        "same_epoch_existing_first_date": min(by_day) if by_day else "unknown",
        "same_epoch_existing_last_date": max(by_day) if by_day else "unknown",
        "same_epoch_valid_first_date": valid_dates[0] if valid_dates else "unknown",
        "same_epoch_valid_last_date": valid_dates[-1] if valid_dates else "unknown",
        "same_epoch_raw_daily_rows": sum(map(len, by_day.values())),
        "same_epoch_valid_daily_count": len(valid_dates),
        "same_epoch_duplicate_days": duplicate_days,
        "same_epoch_invalid_ohlc_rows": invalid_rows,
        "same_symbol_all_epochs_raw_daily_rows": len(rows),
        "same_symbol_unresolved_epoch_rows": unresolved,
        "same_symbol_all_epochs_first_date": rows[0]["datetime"][:10] if rows else "unknown",
        "same_symbol_all_epochs_last_date": rows[-1]["datetime"][:10] if rows else "unknown",
    }


def build_manifest(mapping_path: Path, database_path: Path, products=PRODUCTS) -> tuple[list[dict], list[dict]]:
    groups, scoped = defaultdict(list), set()
    seen = set()
    with mapping_path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            product = f'{row["product"]}.{row["exchange"]}'
            vt = row["main_contract_vt"].strip()
            if product not in products or not vt:
                continue
            day = row["date"]
            identity = contract_identity(vt, day)
            if identity["product"] != product:
                raise ValueError(f"mapping_product_mismatch:{day}:{vt}:{product}")
            mapping_key = (day, product)
            if mapping_key in seen:
                raise ValueError(f"duplicate_main_mapping:{mapping_key}")
            seen.add(mapping_key)
            raw_tq = row["main_contract_tq"].strip()
            if raw_tq != f'{row["exchange"]}.{vt.rsplit(".", 1)[0]}':
                raise ValueError(f"mapping_tq_vt_mismatch:{day}:{vt}:{raw_tq}")
            item = {"date": day, **identity, "tq_symbol_raw_mapping": raw_tq}
            groups[identity["contract_epoch_id"]].append(item)
            if START <= day <= END:
                scoped.add(identity["contract_epoch_id"])
    connection = sqlite3.connect(database_path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    contracts, days = [], []
    try:
        for epoch in sorted(scoped):
            group = sorted(groups[epoch], key=lambda row: row["date"])
            selected = [row for row in group if START <= row["date"] <= END]
            first, last = group[0]["date"], group[-1]["date"]
            scope_first, scope_last = selected[0]["date"], selected[-1]["date"]
            item = {key: value for key, value in group[0].items() if key != "date"}
            symbol, exchange = item["vt_symbol"].rsplit(".", 1)
            rows = [dict(row) for row in connection.execute(
                "SELECT datetime,open_price,high_price,low_price,close_price FROM dbbardata "
                "WHERE symbol=? AND exchange=? AND interval='d' ORDER BY datetime", (symbol, exchange))]
            item.update({"first_main_date": first, "last_main_date": last,
                         "first_main_date_in_scope": scope_first, "last_main_date_in_scope": scope_last,
                         "main_mapping_days_in_scope": len(selected), "main_mapping_days_all_dates": len(group)})
            item.update(summarize_bars(rows, item["vt_symbol"], item["contract_yyyymm"], first, scope_first))
            delivery_year, delivery_month = int(item["contract_yyyymm"][:4]), int(item["contract_yyyymm"][4:])
            item.update({
                "list_date": "unknown", "delist_date": "unknown", "lifetime_metadata_source": "not_queried",
                "full_lifetime_download_start": "unknown", "full_lifetime_download_end": "unknown",
                "full_lifetime_boundary_rule": "verified_vendor_list_date_through_delist_date_inclusive",
                "probe_or_download_start": (date.fromisoformat(first) - timedelta(days=730)).isoformat(),
                "probe_or_download_end": date(delivery_year, delivery_month, calendar.monthrange(delivery_year, delivery_month)[1]).isoformat(),
                "probe_window_status": "heuristic_wide_probe_only_not_listing_or_lifetime_boundary",
                "download_status": "pending_metadata_and_vendor_probe", "resume_key": epoch,
                "raw_output_relative_path": f'raw/{{vendor}}/{exchange}/{symbol}_{item["contract_yyyymm"]}_1d.csv',
                "target_interval": "1d", "bar_date_semantics": "exchange_trading_date",
                "volume_open_interest_regime": "retain_raw_vendor_units_audit_pre2020_double_sided_separately",
            })
            contracts.append(item)
            actual_by_day = defaultdict(list)
            for actual in rows:
                actual_by_day[actual["datetime"][:10]].append(actual)
            for selected_day in selected:
                actual = actual_by_day[selected_day["date"]]
                valid_count = sum(valid_ohlc(row) for row in actual)
                days.append({"date": selected_day["date"], "contract_epoch_id": epoch,
                             "product": item["product"], "vt_symbol": item["vt_symbol"],
                             "contract_yyyymm": item["contract_yyyymm"],
                             "tq_symbol_raw_mapping": selected_day["tq_symbol_raw_mapping"],
                             "actual_daily_bar_rows": len(actual), "valid_ohlc_rows": valid_count,
                             "coverage_ok": len(actual) == 1 and valid_count == 1})
    finally:
        connection.close()
    contracts.sort(key=lambda row: (row["first_main_date_in_scope"], row["product"], row["contract_yyyymm"]))
    days.sort(key=lambda row: (row["date"], row["product"]))
    return contracts, days


def file_identity(path: Path) -> dict:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"input_changed_while_hashing:{path}")
    return {"path": str(path), "bytes": after.st_size, "mtime_ns": after.st_mtime_ns, "sha256": digest.hexdigest()}


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    paths = [MAPPING, DATABASE, Path(__file__).resolve(),
             LINE / "outputs/stage263_ai_data_expansion/source_summary.json",
             ROOT / "examples/portfolio_backtesting/repair_qmt_roll_stage196_stage78_2015_tushare_data.py"]
    paths.extend(path for suffix in ("-wal", "-shm") if (path := Path(str(DATABASE) + suffix)).exists())
    before = {str(path): file_identity(path) for path in paths}
    contracts, days = build_manifest(MAPPING, DATABASE)
    for path in paths:
        if file_identity(path) != before[str(path)]:
            raise RuntimeError(f"input_changed_during_manifest_build:{path}")
    if len(contracts) != 231 or len({row["product"] for row in contracts}) != 14 or len(days) != 14187:
        raise RuntimeError("scope_changed_review_required")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "manifest_contracts.csv", contracts)
    write_csv(OUTPUT / "manifest_main_dates.csv", days)
    (OUTPUT / "manifest_contracts.json").write_text(json.dumps(contracts, ensure_ascii=False, indent=2) + "\n")
    state = [{"resume_key": row["resume_key"], "contract_epoch_id": row["contract_epoch_id"],
              "vendor": "unselected", "status": "pending_metadata_and_vendor_probe", "attempt_count": 0,
              "verified_start": "unknown", "verified_end": "unknown", "raw_path": "", "raw_sha256": "",
              "returned_rows": 0, "last_successful_segment_end": "unknown", "error": ""} for row in contracts]
    write_csv(OUTPUT / "download_state_template.csv", state)
    summary = {
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "line_id": "futures_trend_rollover_shape_same_volume", "stage": "Stage264",
        "git_branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "status": "research_manifest_only_no_download_or_replay", "scope_start": START, "scope_end": END,
        "contract_epochs": len(contracts), "products": len({row["product"] for row in contracts}),
        "main_mapping_days_in_scope": len(days), "effective_source_AM_size": AM,
        "missing_or_invalid_main_mapping_days_in_scope": sum(not row["coverage_ok"] for row in days),
        "ready_at_global_first_main_close": sum(row["AM120_ready_at_first_main_close"] for row in contracts),
        "needed_bars_lower_bound_at_global_first_main_close": sum(row["needed_bars_lower_bound"] for row in contracts),
        "source_scope_preload_start": SOURCE_PRELOAD,
        "stage263_comparable_ready_at_first_in_scope_main_close": sum(row["source_scope_AM120_ready"] for row in contracts),
        "stage263_comparable_needed_bars_lower_bound": sum(row["source_scope_needed_bars_lower_bound"] for row in contracts),
        "global_first_main_precedes_scope_start_epochs": sum(row["first_main_date"] < START for row in contracts),
        "unknown_listing_date_epochs": sum(row["list_date"] == "unknown" for row in contracts),
        "duplicate_same_epoch_days": sum(row["same_epoch_duplicate_days"] for row in contracts),
        "invalid_same_epoch_ohlc_rows": sum(row["same_epoch_invalid_ohlc_rows"] for row in contracts),
        "product_epoch_counts": dict(sorted(Counter(row["product"] for row in contracts).items())),
        "source_identities": before, "official_documentation": DOCUMENTATION,
        "definitions": {
            "contract_epoch_id": "vt_symbol@YYYYMM; mapping and every bar are independently date-qualified",
            "history_count_before_first_main": "unique valid same-delivery daily bars strictly before global first mapped main date",
            "needed_bars_lower_bound": "max(0,120-history_count_through_first_main); includes actual first-main-day bar only if present",
            "stage263_comparable": "counts same-epoch valid bars >=2015-01-01 through first main date inside 2015--2019 scope",
            "probe_window": "first global main date minus730 calendar days through delivery month end; a heuristic exploratory query, never listing/expiry evidence or guaranteed full lifetime",
            "full_lifetime_download": "must first obtain and validate metadata list_date/delist_date and delivery month; currently unknown for all epochs",
            "vendor_codes": "official format normalization only; individual historical catalog existence/entitlement not verified; TQ YYMM aliases remain explicitly unverified",
            "resume": "copy download_state_template.csv to a separate mutable state file; key by resume_key, write raw/hash/status atomically; generator does not read or overwrite downloader checkpoints",
            "lower_bound_limit": "minimum missing count at the first-main clock; not a trading-calendar gap count or proof all120 bars existed before listing",
        },
        "data_download_calls": 0, "training_calls": 0, "backtest_calls": 0, "database_write_calls": 0,
    }
    summary["output_identities"] = {path.name: file_identity(path) for path in OUTPUT.iterdir()
                                      if path.name in {"manifest_contracts.csv", "manifest_main_dates.csv", "manifest_contracts.json", "download_state_template.csv"}}
    (OUTPUT / "summary_daily_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: summary[key] for key in ("status", "contract_epochs", "products", "main_mapping_days_in_scope", "ready_at_global_first_main_close", "needed_bars_lower_bound_at_global_first_main_close", "stage263_comparable_ready_at_first_in_scope_main_close", "stage263_comparable_needed_bars_lower_bound", "global_first_main_precedes_scope_start_epochs")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
