"""有界只读输入盘点；不计算 EMA、不签日线资格、不启动 native。"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from datetime import datetime

ROOT = Path(__file__).resolve().parents[5]
LINE = ROOT / "research/lines/futures_trend_triple_screen"
OUT = Path(__file__).resolve().parent
DB = ROOT / ".vntrader/database.db"
P = LINE / "outputs/stage099_pairwise_off_account"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def stat(path):
    p = Path(path)
    if not p.exists():
        return {"exists": False, "bytes": 0}
    s = p.stat()
    return {"exists": True, "bytes": s.st_size, "mtime_ns": s.st_mtime_ns}


def main():
    result_path = OUT / "inventory.json"
    if result_path.exists():
        raise FileExistsError("one_finite_inventory_already_exists")
    pre_path = P / "preflight/A_OFF.json"
    pre = json.loads(pre_path.read_text())
    param_path = P / "A_OFF/effective_parameters.json"
    params = json.loads(param_path.read_text())
    old_param_path = LINE / "outputs/stage001_first_screen/A0_attempt2/effective_parameters.json"
    old = json.loads(old_param_path.read_text())
    metadata = sorted(params["contract_sizes"])
    before = {"db": stat(DB), "wal": stat(str(DB) + "-wal"), "shm": stat(str(DB) + "-shm")}
    if before["wal"]["bytes"]:
        raise ValueError("nonempty_wal_no_inventory")
    found = digest(DB)
    expected = pre["data_bindings"][str(DB)]["sha256"]
    if found != expected:
        raise ValueError("frozen_database_changed")
    daily013 = LINE / "outputs/stage013_missing_daily_recovery/network_attempt1/qualified_daily.csv"
    review013 = LINE / "outputs/stage013_independent_review/review_receipt.json"
    original = ROOT / "examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04/SHFE/fu2101.csv"
    header013, r013 = rows(daily013)
    original_header, original_rows = rows(original)
    samples = [r013[0], r013[len(r013) // 2], r013[-1]]
    samples_original = sorted(original_rows, key=lambda r: r["trade_date"])
    samples_original = [samples_original[len(samples_original) // 2]]
    fields = ("open", "high", "low", "close", "volume")
    query_params = ["2019-06-01 00:00:00", "2026-10-14 00:00:00", *metadata]
    scope = ("WITH s AS (SELECT *,symbol||'.'||exchange AS vt FROM dbbardata "
             "WHERE interval='d' AND datetime>=? AND datetime<=? AND "
             "symbol||'.'||exchange IN (" + ",".join("?" for _ in metadata) + ")) ")
    with sqlite3.connect(DB.as_uri() + "?mode=ro&immutable=1", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        db.row_factory = sqlite3.Row
        aggregate = dict(db.execute(scope + "SELECT count(*) AS rows,count(DISTINCT vt) AS contracts,"
            "count(DISTINCT substr(datetime,1,10)) AS dates,min(datetime) AS first,max(datetime) AS last,"
            "sum(open_price IS NULL OR high_price IS NULL OR low_price IS NULL OR close_price IS NULL OR volume IS NULL) AS null_ohlcv,"
            "sum(open_price<=0 OR low_price<=0 OR high_price<=0 OR close_price<=0 OR low_price>min(open_price,close_price) OR high_price<max(open_price,close_price)) AS invalid_ohlc,"
            "sum(volume<0) AS negative_volume,sum(volume=0) AS zero_volume,"
            "sum(substr(datetime,12,8)<>'00:00:00') AS non_midnight FROM s", query_params).fetchone())
        duplicate_keys = db.execute(scope + "SELECT count(*) FROM (SELECT vt,substr(datetime,1,10) FROM s GROUP BY vt,substr(datetime,1,10) HAVING count(*)>1)", query_params).fetchone()[0]
        calendar = [r[0] for r in db.execute(scope + "SELECT DISTINCT substr(datetime,1,10) FROM s ORDER BY 1", query_params)]
        zero_samples = [dict(r) for r in db.execute(scope + "SELECT vt,datetime,open_price,high_price,low_price,close_price,volume FROM s WHERE volume=0 ORDER BY vt,datetime LIMIT 3", query_params)]
        checks = []
        for source, selected in [(str(daily013), samples), (str(original), samples_original)]:
            for r in selected:
                vt = r.get("vt_symbol", "fu2101.SHFE")
                code, exchange = vt.rsplit(".", 1)
                day = r["trade_date"][:10]
                got = db.execute("SELECT datetime,open_price AS open,high_price AS high,low_price AS low,close_price AS close,volume FROM dbbardata WHERE interval='d' AND symbol=? AND exchange=? AND substr(datetime,1,10)=?", (code, exchange, day)).fetchall()
                diffs = {k: abs(float(r[k]) - float(got[0][k])) for k in fields} if len(got) == 1 else None
                checks.append(dict(source=source, vt_symbol=vt, date=day, db_rows=len(got), absolute_differences=diffs,
                                   provider_datetime=r.get("datetime"), db_datetime=got[0]["datetime"] if len(got) == 1 else None))
        excluded_path = LINE / "outputs/stage013_missing_daily_recovery/excluded_constraints.csv"
        _, excluded = rows(excluded_path)
        absent = []
        for r in excluded:
            code, exchange = r["vt_symbol"].rsplit(".", 1)
            count = db.execute("SELECT count(*) FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' AND substr(datetime,1,10)=?", (code, exchange, r["execution_trade_date"])).fetchone()[0]
            absent.append(dict(r, exact_db_rows=count))
    calendar_path = LINE / "outputs/stage005_potential_signal_demand/global_engine_calendar.csv"
    _, accepted_calendar = rows(calendar_path)
    files = [pre_path, P / "A_OFF/run_context.json", param_path, old_param_path, daily013, review013,
             original, excluded_path, calendar_path, LINE / "outputs/stage027_independent_review/review_receipt.json",
             LINE / "outputs/stage027_ordered_features/input_manifest.json",
             LINE / "outputs/stage022_qualified_wait/data_stack_manifest.json",
             LINE / "tools/stage027_build_ordered_features.py", LINE / "tools/stage127_ema_limit_model.py",
             LINE / "tools/stage127_ema_limit_strategy.py", LINE / "tools/stage127_ema_limit_engine.py",
             ROOT / "examples/portfolio_backtesting/qmt_roll_intraday_execution.py",
             ROOT / "examples/portfolio_backtesting/import_tqsdk_all_futures_daily_to_db.py",
             ROOT / "examples/portfolio_backtesting/download_tqsdk_all_futures_daily_csv.py",
             ROOT / "examples/portfolio_backtesting/run_qmt_roll_backtest.py",
             Path("/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor/vnpy_portfoliostrategy/backtesting.py")]
    bound = {}
    for p in files:
        h = digest(p)
        expected_binding = pre.get("data_bindings", {}).get(str(p), pre.get("source_bindings", {}).get(str(p)))
        bound[str(p)] = dict(sha256=h, bytes=p.stat().st_size,
                            A_OFF_preflight_sha_match=(h == expected_binding["sha256"]) if expected_binding else None)
    after = {"db": stat(DB), "wal": stat(str(DB) + "-wal"), "shm": stat(str(DB) + "-shm")}
    if before != after:
        raise ValueError("database_or_sidecar_stat_changed")
    explicit = [(p, b) for p, b in pre["data_bindings"].items() if p.endswith("qualified_daily.csv")]
    result = dict(schema="stage138_readonly_input_inventory_v1", recorded_at=datetime.now().astimezone().isoformat(),
        status="finite_inventory_complete_no_new_qualification", database=dict(path=str(DB), sha256=found,
        expected_sha256=expected, before=before, after=after, query_only=True, immutable=True, aggregate=aggregate,
        duplicate_contract_date_keys=duplicate_keys, zero_volume_samples=zero_samples),
        metadata=dict(contracts=len(metadata), no_alias_continuous=all(re.fullmatch(r"[A-Za-z]+\d{3,4}\.[A-Z]+", v) and not re.search(r"(?:888|889|999|8888|8899|9999|0000)\.", v) for v in metadata),
        priceticks_equal_A0=params["priceticks"] == old["priceticks"], contract_sizes_equal_A0=params["contract_sizes"] == old["contract_sizes"],
        lc_configured_tick_values=sorted({v for k, v in params["priceticks"].items() if k.startswith("lc")})),
        calendar=dict(path=str(calendar_path), rows=len(calendar), equals_existing_global_calendar=calendar == [r["date"] for r in accepted_calendar]),
        sampled_price_checks=checks, stage013_excluded_exact_DB_checks=absent,
        stage013=dict(path=str(daily013), schema=header013, exact_unique_keys=len({(r["vt_symbol"], r["trade_date"]) for r in r013}),
            contracts=len({r["vt_symbol"] for r in r013}), zero_volume_rows=sum(float(r["volume"]) == 0 for r in r013), full_history_qualified=False),
        original_sample=dict(path=str(original), schema=original_header, rows=len(original_rows)),
        A_OFF_bound_daily_inventory=dict(original_daily_csv_paths=sum("/downloaded_futures/tqsdk_daily_" in p and p.endswith(".csv") for p in pre["data_bindings"]),
            explicit_qualified_daily_paths=len(explicit), explicit_paths_declared_only=[dict(path=p, **b) for p, b in explicit], all_declared_sources_rehashed=False),
        source_bindings=bound, feature_builds=0, native_runs=0, tests_run=0, financial_replays=0, model_calls=0, provider_calls=0,
        qualification_granted=False, financial_ready=False, production_qualified=False)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(status=result["status"], database_sha256=found, aggregate=aggregate,
        duplicate_keys=duplicate_keys, metadata_contracts=len(metadata), exact_stage013_keys=result["stage013"]["exact_unique_keys"],
        calendar_matches=result["calendar"]["equals_existing_global_calendar"], samples_equal=all(c["absolute_differences"] is not None and not any(c["absolute_differences"].values()) for c in checks),
        carry_exclusions_absent=all(r["exact_db_rows"] == 0 for r in absent), inventory_sha256=digest(result_path)), ensure_ascii=False))


if __name__ == "__main__":
    main()
