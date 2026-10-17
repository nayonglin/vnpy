"""Read-only, date-qualified audit of mapped main-contract daily bars.

This audits data availability only. It never imports an execution engine, trains a
model, repairs data, or connects to a trading/data gateway.
"""
from __future__ import annotations

import ast
import argparse
import csv
import hashlib
import json
import math
import platform
import re
import sqlite3
import subprocess
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


LINE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = LINE_DIR.parents[2]
MAPPING_PATH = REPO_DIR / "examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
DATABASE_PATH = REPO_DIR / ".vntrader/database.db"
OUTPUT_PATH = LINE_DIR / "outputs/stage262_ai_sample_contract/early_daily_coverage.json"
START, END = "2015-01-01", "2019-12-31"
PRODUCTS = tuple("AP.CZCE CF.CZCE FG.CZCE MA.CZCE OI.CZCE SA.CZCE SH.CZCE SM.CZCE au.SHFE cu.SHFE hc.SHFE jm.DCE lc.GFEX lh.DCE rb.SHFE ru.SHFE si.GFEX sp.SHFE".split())
REAL_CONTRACT = re.compile(r"([A-Za-z]+)([0-9]{3,4})\.([A-Z]+)")


def identity(path: Path) -> dict:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"Input changed while hashing: {path}")
    return {"path": str(path.relative_to(REPO_DIR)), "size_bytes": after.st_size,
            "mtime_ns": after.st_mtime_ns, "sha256": digest.hexdigest()}


def ohlc_errors(row: sqlite3.Row) -> list[str]:
    prices = [row[key] for key in ("open_price", "high_price", "low_price", "close_price")]
    if any(value is None or not math.isfinite(value) for value in prices):
        return ["nonfinite_or_null"]
    errors = []
    if any(value <= 0 for value in prices):
        errors.append("nonpositive")
    op, hi, lo, cl = prices
    if not lo <= min(op, cl) <= max(op, cl) <= hi:
        errors.append("inconsistent_extrema")
    return errors


def source_boundary(requested_start: str) -> dict:
    """Inspect configuration without importing or executing source modules."""
    base = REPO_DIR / "examples/portfolio_backtesting"
    universe_text = (base / "qmt_universe.py").read_text()
    assignments = {}
    for node in ast.parse(universe_text).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in {"PRELOAD_START_DT", "START_DT"}:
                value = node.value
                if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                        and value.func.id == "datetime"):
                    raise ValueError("Unexpected date configuration; manual review required")
                assignments[node.target.id] = datetime(*[ast.literal_eval(arg) for arg in value.args])
    run_text = (base / "run_qmt_roll_backtest.py").read_text()
    run_fn = next(node for node in ast.parse(run_text).body
                  if isinstance(node, ast.FunctionDef) and node.name == "run_backtest")
    preload_node = next(node for node in run_fn.body if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "preload_start" for t in node.targets))
    preload_expression = ast.get_source_segment(run_text, preload_node.value)
    expected_expression = "preload_start or max(PRELOAD_START_DT, analysis_start - timedelta(days=365))"
    if preload_expression != expected_expression:
        raise ValueError("Preload behavior changed; manual review required")
    refresh_text = (base / "build_qmt_roll_stage183_ai_product_pool_source_refresh.py").read_text()
    call = next(node for node in ast.walk(ast.parse(refresh_text))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "run_backtest")
    kwargs = {keyword.arg for keyword in call.keywords}
    requested = datetime.fromisoformat(requested_start)
    effective = max(assignments["PRELOAD_START_DT"], requested - timedelta(days=365))
    return {
        "inspection_only_engine_executed": False,
        "source_entry": "examples/portfolio_backtesting/build_qmt_roll_stage183_ai_product_pool_source_refresh.py",
        "stage183_passes_analysis_start": "analysis_start" in kwargs,
        "stage183_passes_preload_start": "preload_start" in kwargs,
        "run_backtest_preload_expression": preload_expression,
        "preload_expression_line": preload_node.lineno,
        "configured_preload_start": assignments["PRELOAD_START_DT"].date().isoformat(),
        "requested_analysis_start": requested_start,
        "effective_preload_with_unchanged_stage183": effective.date().isoformat(),
        "current_entry_proves_2015_replay": False,
        "judgment": "2015主力日线是必要数据基础；现有Stage183入口未传preload_start，默认下限2019-06-01，直接改analysis-start不能产生2015起点的统一源回放证据。",
    }


def audit(start: str = START, end: str = END) -> tuple[dict, list[dict]]:
    started = time.perf_counter()
    if date.fromisoformat(start) > date.fromisoformat(end):
        raise ValueError("Start must not be later than end")
    paths = [Path(__file__).resolve(), MAPPING_PATH, DATABASE_PATH,
             REPO_DIR / ".py311/lib/python3.11/site-packages/vnpy_sqlite/sqlite_database.py",
             REPO_DIR / "vnpy/trader/object.py"]
    paths.extend(REPO_DIR / "examples/portfolio_backtesting" / name for name in (
        "qmt_universe.py", "main_contract_mapping.py", "run_qmt_roll_backtest.py",
        "build_qmt_roll_stage183_ai_product_pool_source_refresh.py"))
    paths.extend(sidecar for suffix in ("-wal", "-shm")
                 if (sidecar := Path(str(DATABASE_PATH) + suffix)).exists())
    before = {str(path): identity(path) for path in paths}
    counters = {product: Counter() for product in PRODUCTS}
    expected = {product: defaultdict(list) for product in PRODUCTS}
    bad_mappings = {product: [] for product in PRODUCTS}
    observed_rows = {product: Counter() for product in PRODUCTS}
    raw_contracts = {product: defaultdict(list) for product in PRODUCTS}
    mapping_dates = set()
    with MAPPING_PATH.open(encoding="utf-8-sig", newline="") as stream:
        for line_no, row in enumerate(csv.DictReader(stream), 2):
            product = row["product"] + "." + row["exchange"]
            if product not in counters or not start <= row["date"] <= end:
                continue
            date.fromisoformat(row["date"])
            mapping_dates.add(row["date"])
            counters[product]["all_mapping_rows"] += 1
            observed_rows[product][row["date"]] += 1
            contract = row["main_contract_vt"].strip()
            raw_contracts[product][row["date"]].append(contract)
            if not contract:
                counters[product]["empty_main_contract_rows"] += 1
                continue
            match = REAL_CONTRACT.fullmatch(contract)
            if not match or (match.group(1) + "." + match.group(3)) != product:
                bad_mappings[product].append({"line": line_no, "date": row["date"], "contract": contract})
                continue
            expected[product][row["date"]].append(contract)

    connection = sqlite3.connect(DATABASE_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    contracts = sorted({vt for days in expected.values() for values in days.values() for vt in values})
    bars = defaultdict(list)
    selected_digest = hashlib.sha256()
    aliases = []
    for contract in contracts:
        symbol, exchange = contract.rsplit(".", 1)
        rows = connection.execute(
            "SELECT symbol,exchange,datetime,interval,open_price,high_price,low_price,close_price,volume,turnover,open_interest "
            "FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' AND datetime>=? AND datetime<? ORDER BY datetime",
            (symbol, exchange, start, (date.fromisoformat(end) + timedelta(days=1)).isoformat()),
        ).fetchall()
        for row in rows:
            # Keep the actual date in the key: CZCE three-digit contract codes repeat after ten years.
            bars[(row["datetime"][:10], contract)].append(row)
            selected_digest.update((json.dumps(dict(row), sort_keys=True, allow_nan=False) + "\n").encode())
        if exchange == "CZCE":
            span = connection.execute(
                "SELECT MIN(datetime),MAX(datetime),COUNT(*) FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d'",
                (symbol, exchange),
            ).fetchone()
            if span[0] and int(span[1][:4]) - int(span[0][:4]) >= 9:
                aliases.append({"contract": contract, "first_database_datetime": span[0],
                                "last_database_datetime": span[1], "all_dates_rows": span[2]})
    daily_schema = [dict(row) for row in connection.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE tbl_name='dbbardata' ORDER BY type,name")]
    results = []
    coverage_rows = []
    for product in PRODUCTS:
        dates = sorted(expected[product])
        gaps, duplicates, invalid, conflicting_map = [], [], [], []
        matched_dates, valid_dates = [], []
        flat_price_rows = zero_volume_rows = nonmidnight_rows = 0
        for day in dates:
            mapped_contracts = expected[product][day]
            if len(set(mapped_contracts)) > 1:
                conflicting_map.append({"date": day, "contracts": sorted(set(mapped_contracts))})
                continue
            contract = mapped_contracts[0]
            rows = bars[(day, contract)]
            if not rows:
                gaps.append({"date": day, "contract": contract})
                continue
            matched_dates.append(day)
            if len(rows) > 1:
                duplicates.append({"date": day, "contract": contract,
                                   "datetimes": [row["datetime"] for row in rows]})
            row_errors = []
            for row in rows:
                errors = ohlc_errors(row)
                if errors:
                    row_errors.append(errors)
                    invalid.append({"date": day, "contract": contract, "datetime": row["datetime"],
                                    "errors": errors, "ohlc": [row[key] for key in (
                                        "open_price", "high_price", "low_price", "close_price")]})
                flat_price_rows += row["open_price"] == row["high_price"] == row["low_price"] == row["close_price"]
                zero_volume_rows += row["volume"] == 0
                nonmidnight_rows += row["datetime"][10:] not in (" 00:00:00", "T00:00:00")
            if len(rows) == 1 and not row_errors:
                valid_dates.append(day)
        for day in sorted(mapping_dates):
            mappings = raw_contracts[product][day]
            real_contracts = expected[product][day]
            unique_contracts = sorted(set(real_contracts))
            contract = unique_contracts[0] if len(unique_contracts) == 1 else ""
            rows = bars[(day, contract)] if contract else []
            error_count = sum(bool(ohlc_errors(row)) for row in rows)
            valid = (observed_rows[product][day] == 1 and len(real_contracts) == 1
                     and len(rows) == 1 and not error_count)
            coverage_rows.append({
                "date": day, "product": product,
                "main_contract_vt": contract or "|".join(sorted(set(mappings))),
                "coverage_ok": bool(valid),
                "mapping_rows": observed_rows[product][day],
                "real_mapping_rows": len(real_contracts),
                "mapping_conflict": len(unique_contracts) > 1,
                "matched_daily_rows": len(rows),
                "missing_daily": bool(contract) and not rows,
                "duplicate_daily": len(rows) > 1,
                "invalid_ohlc_rows": error_count,
            })
        duplicate_mapping_rows = sum(len(values) - len(set(values)) for values in expected[product].values())
        complete = bool(dates) and not any((gaps, duplicates, invalid, conflicting_map,
                                          duplicate_mapping_rows, bad_mappings[product]))
        results.append({
            "product": product, **counters[product],
            "invalid_mapping_count": len(bad_mappings[product]), "invalid_mappings": bad_mappings[product],
            "duplicate_mapping_rows": duplicate_mapping_rows,
            "conflicting_mapping_dates": conflicting_map,
            "expected_mapping_days": len(dates), "matched_daily_days": len(matched_dates),
            "valid_unique_ohlc_days": len(valid_dates), "missing_daily_days": len(gaps),
            "duplicate_daily_dates": len(duplicates), "invalid_ohlc_rows": len(invalid),
            "first_expected_date": dates[0] if dates else None,
            "last_expected_date": dates[-1] if dates else None,
            "first_matched_date": matched_dates[0] if matched_dates else None,
            "last_matched_date": matched_dates[-1] if matched_dates else None,
            "coverage_ratio": len(matched_dates) / len(dates) if dates else None,
            "coverage_status": "no_valid_mapping" if not dates else (
                "complete_for_mapped_dates" if complete else "incomplete_or_invalid"),
            "flat_ohlc_rows_diagnostic_only": flat_price_rows,
            "zero_volume_rows_diagnostic_only": zero_volume_rows,
            "nonmidnight_matched_rows": nonmidnight_rows,
            "missing_by_year": dict(sorted(Counter(gap["date"][:4] for gap in gaps).items())),
            "missing_by_contract": dict(sorted(Counter(gap["contract"] for gap in gaps).items())),
            "missing": gaps, "duplicates": duplicates, "invalid_ohlc": invalid,
        })
    for result in results:
        if result["missing"]:
            product, exchange = result["product"].split(".")
            same_product = defaultdict(list)
            for row in connection.execute(
                "SELECT substr(datetime,1,10) AS day,symbol,volume FROM dbbardata WHERE exchange=? "
                "AND symbol GLOB ? AND interval='d' AND datetime>=? AND datetime<? ORDER BY datetime,symbol",
                (exchange, product + "[0-9]*", start, (date.fromisoformat(end) + timedelta(days=1)).isoformat()),
            ):
                same_product[row["day"]].append({"contract": row["symbol"] + "." + exchange,
                                                 "volume": row["volume"]})
            result["missing_dates_with_other_contract_bars"] = [
                {**gap, "other_contract_bars": same_product[gap["date"]]}
                for gap in result["missing"] if same_product[gap["date"]]]
            result["missing_dates_without_any_product_bar"] = sum(
                not same_product[gap["date"]] for gap in result["missing"])
    connection.close()
    after = {str(path): identity(path) for path in paths}
    if before != after:
        raise RuntimeError("An audited input changed during the audit; discard the snapshot")
    totals = {field: sum(result[field] for result in results) for field in (
        "expected_mapping_days", "matched_daily_days", "valid_unique_ohlc_days", "missing_daily_days",
        "duplicate_daily_dates", "invalid_ohlc_rows", "duplicate_mapping_rows", "invalid_mapping_count")}
    return {
        "audit_id": "stage262_daily_coverage_v2",
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "research_line": LINE_DIR.name,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_DIR, text=True).strip(),
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO_DIR, text=True).strip(),
        "runtime": {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version},
        "period": {"start": start, "end": end, "reference_mapping_calendar_days": len(mapping_dates)},
        "method": {
            "expected": "Nonempty real main_contract_vt, matching product/exchange, one product-date expectation.",
            "bar_match_key": ["mapping.date == substr(dbbardata.datetime,1,10)", "contract.symbol", "exchange", "interval=d"],
            "ohlc_valid": "finite and positive; low <= min(open,close) <= max(open,close) <= high",
            "flat_and_zero_volume": "diagnostics only; not automatically invalid or absent",
            "database_mode": "mode=ro + PRAGMA query_only=ON + read transaction; input hashes stable before/after",
            "calendar_limit": "Mapping dates are the expected calendar; no independent exchange holiday/listing certification.",
        },
        "input_identities": list(before.values()),
        "selected_contract_bars_sha256": selected_digest.hexdigest(),
        "daily_table_schema": daily_schema,
        "totals": totals,
        "products_with_full_period_mapping": [r["product"] for r in results
            if r["expected_mapping_days"] == len(mapping_dates)],
        "products_complete_for_mapped_dates": [r["product"] for r in results
            if r["coverage_status"] == "complete_for_mapped_dates"],
        "products_without_mapping": [r["product"] for r in results if not r["expected_mapping_days"]],
        "cross_decade_contract_aliases": aliases,
        "source_engine_boundary": source_boundary(start),
        "training_labels_generated": False, "backtests_run": 0, "models_trained": 0,
        "judgment": "Coverage is evaluated per product/date/real contract. Missing mapped-day bars remain ineligible; empty pre-coverage mappings remain ineligible. Bar availability does not establish source-engine labels or 120-day feature/60-day target maturity.",
        "daily_coverage_rows": len(coverage_rows),
        "daily_coverage_valid_rows": sum(row["coverage_ok"] for row in coverage_rows),
        "products": results,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
    }, coverage_rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=START)
    parser.add_argument("--end", default=END)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()
    report, coverage_rows = audit(args.start, args.end)
    if args.output_csv:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.output_csv.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(coverage_rows[0]))
            writer.writeheader()
            writer.writerows(sorted(coverage_rows, key=lambda row: (row["date"], row["product"])))
        report["daily_coverage_table"] = identity(args.output_csv.resolve())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output_json), "totals": report["totals"],
                      "elapsed_seconds": report["elapsed_seconds"]}, ensure_ascii=False))
