"""按正式回放的实际开仓合约和上海自然日补分钟源。

只读覆盖清单，按自然日并发注册该日合约的 60 秒序列；不调用交易 API，
不修改 Stage861。每个日期的 parquet、校验证据和全局进度均可断点续跑。
来源：同目录 stage246_download_minutes.py；coverage 来自 Stage246 历史回放。
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
import fcntl
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any


LINE = "futures_trend_rollover_shape_same_volume"
COLUMNS = [
    "vt_symbol", "bar_datetime", "bar_date", "open", "high", "low", "close",
    "volume", "open_oi", "close_oi", "minute_source",
]
SOURCE = "stage246_tqsdk_entry_date_snapshot"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_coverage(paths: list[Path]) -> set[tuple[str, str]]:
    """并集去重；即使原 coverage 有分钟，也重新核验该开仓 key。"""
    keys: set[tuple[str, str]] = set()
    for path in paths:
        with path.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            if not {"vt_symbol", "entry_date"}.issubset(reader.fieldnames or []):
                raise ValueError("coverage_columns_missing")
            for row in reader:
                symbol = str(row["vt_symbol"] or "").strip()
                if not symbol or symbol.count(".") != 1:
                    raise ValueError("coverage_symbol_invalid")
                entry_date = date.fromisoformat(str(row["entry_date"]).strip()).isoformat()
                keys.add((symbol, entry_date))
    if not keys:
        raise ValueError("coverage_has_no_entry_keys")
    return keys


def expected_day_grid(day: str) -> set[datetime]:
    target = date.fromisoformat(day)
    windows = [(9, 0, 10, 14), (10, 30, 11, 29), (13, 30, 14, 59)]
    result: set[datetime] = set()
    for start_hour, start_minute, end_hour, end_minute in windows:
        first = datetime(target.year, target.month, target.day, start_hour, start_minute)
        last = datetime(target.year, target.month, target.day, end_hour, end_minute)
        cursor = first
        while cursor <= last:
            result.add(cursor)
            cursor += timedelta(minutes=1)
    return result


def validate_raw_serial_bounds(day: str, earliest: str, latest: str) -> dict[str, str]:
    """证明1000根未在目标日零点截断，也未越过次日08:00快照。"""
    target = date.fromisoformat(day)
    first = datetime.fromisoformat(str(earliest))
    last = datetime.fromisoformat(str(latest))
    midnight = datetime(target.year, target.month, target.day)
    last_daytime = midnight.replace(hour=14, minute=59)
    snapshot = midnight + timedelta(days=1, hours=8)
    if first.tzinfo is not None or last.tzinfo is not None or not first < midnight:
        raise ValueError("raw_serial_truncated_before_target")
    if last < last_daytime or last > snapshot or first > last:
        raise ValueError("raw_serial_snapshot_bounds_invalid")
    return {"earliest": first.isoformat(sep=" "), "latest": last.isoformat(sep=" "), "status": "bounded"}


def validate_natural_day(frame: Any, symbol: str, day: str) -> dict[str, Any]:
    """精确核验日盘225根；夜盘仅按原上海自然日保留。"""
    import numpy as np
    import pandas as pd

    expected = expected_day_grid(day)
    if frame.empty or not set(COLUMNS[:-1]).issubset(frame.columns):
        raise ValueError("minute_columns_or_rows_missing")
    if set(frame["vt_symbol"].astype(str)) != {symbol}:
        raise ValueError("minute_symbol_mismatch")
    moments = pd.to_datetime(frame["bar_datetime"], errors="coerce")
    if moments.isna().any() or moments.dt.tz is not None:
        raise ValueError("minute_datetime_invalid")
    if moments.duplicated().any() or not moments.is_monotonic_increasing:
        raise ValueError("minute_duplicate_or_unsorted")
    natural_dates = moments.dt.strftime("%Y-%m-%d")
    if not natural_dates.eq(day).all() or not frame["bar_date"].astype(str).eq(day).all():
        raise ValueError("minute_natural_date_mismatch")
    if not moments.dt.second.eq(0).all() or not moments.dt.microsecond.eq(0).all():
        raise ValueError("minute_grid_alignment_invalid")
    numeric = frame[["open", "high", "low", "close", "volume", "open_oi", "close_oi"]].apply(
        pd.to_numeric, errors="coerce"
    )
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("minute_nonfinite")
    if (numeric[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("minute_nonpositive_price")
    if (numeric[["volume", "open_oi", "close_oi"]] < 0).any().any():
        raise ValueError("minute_negative_volume_or_oi")
    if not numeric["high"].ge(numeric[["open", "close", "low"]].max(axis=1)).all():
        raise ValueError("minute_high_invalid")
    if not numeric["low"].le(numeric[["open", "close", "high"]].min(axis=1)).all():
        raise ValueError("minute_low_invalid")
    observed = {moment.to_pydatetime() for moment in moments}
    missing = expected - observed
    if missing:
        raise ValueError(f"daytime_grid_missing:{len(missing)}")
    return {
        "vt_symbol": symbol,
        "bar_date": day,
        "rows": int(len(frame)),
        "daytime_rows": len(expected),
        "night_or_other_rows": int(len(frame) - len(expected)),
        "first": str(moments.min()),
        "last": str(moments.max()),
        "status": "complete_daytime_night_unverified",
    }


def checkpoint_paths(out: Path, day: str) -> tuple[Path, Path, Path]:
    stem = day.replace("-", "")
    return out / f"{stem}.parquet", out / f"{stem}_proof.json", out / f"{stem}_coverage.csv"


def cached_groups(out: Path, day: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """只接受 SHA 匹配且逐合约重验通过的既有缓存。"""
    import pandas as pd

    parquet, proof_path, _ = checkpoint_paths(out, day)
    if not (parquet.is_file() and proof_path.is_file()):
        return {}, {}
    try:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        if proof.get("sha256") != sha256(parquet):
            return {}, {}
        frame = pd.read_parquet(parquet)
        groups: dict[str, Any] = {}
        validations: dict[str, dict[str, Any]] = {}
        for symbol, group in frame.groupby("vt_symbol", sort=False):
            symbol = str(symbol)
            ordered = group.sort_values("bar_datetime").reset_index(drop=True)
            try:
                raw = proof.get("raw_serial_ranges", {}).get(symbol, {})
                validate_raw_serial_bounds(day, raw["earliest"], raw["latest"])
                validations[symbol] = validate_natural_day(ordered, symbol, day)
                groups[symbol] = ordered
            except (ValueError, KeyError, TypeError):
                continue
        return groups, validations
    except (OSError, ValueError, KeyError, TypeError):
        return {}, {}


def global_progress(out: Path, all_keys: set[tuple[str, str]], selected_days: set[str], partial_scope: bool, *, deep_check: bool) -> dict[str, Any]:
    """从日期证据重算全部输入 key，任何未完成都会在进度中显式列出。"""
    completed: set[tuple[str, str]] = set()
    by_day: dict[str, set[str]] = {}
    for symbol, day in all_keys:
        by_day.setdefault(day, set()).add(symbol)
    for day, symbols in by_day.items():
        if deep_check:
            groups, _ = cached_groups(out, day)
            ready = set(groups)
        else:
            parquet, proof_path, _ = checkpoint_paths(out, day)
            ready = set()
            if parquet.is_file() and proof_path.is_file():
                try:
                    proof = json.loads(proof_path.read_text(encoding="utf-8"))
                    if proof.get("sha256") == sha256(parquet):
                        ready = set(proof.get("completed_symbols", []))
                except (OSError, ValueError, TypeError):
                    pass
        completed.update((symbol, day) for symbol in symbols & ready)
    missing = all_keys - completed
    return {
        "status": "partial" if partial_scope or missing else "full",
        "all_input_keys": [list(key) for key in sorted(all_keys)],
        "completed_keys": [list(key) for key in sorted(completed)],
        "missing_keys": [list(key) for key in sorted(missing)],
        "total_input_keys": len(all_keys),
        "completed_count": len(completed),
        "missing_count": len(missing),
        "selected_days": sorted(selected_days),
        "partial_scope": partial_scope,
    }


def save_progress(out: Path, all_keys: set[tuple[str, str]], selected_days: set[str], partial_scope: bool, *, deep_check: bool = False) -> dict[str, Any]:
    lock_path = out / "progress.lock"
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        progress = global_progress(out, all_keys, selected_days, partial_scope, deep_check=deep_check)
        temporary = out / f"progress.{os.getpid()}.tmp"
        temporary.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, out / "progress.json")
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return progress


def download_day(day: str, symbols: list[str], cfg: dict[str, str], timeout: float) -> tuple[dict[str, Any], dict[str, str], dict[str, dict[str, str]]]:
    """同一天的全部缺失合约共用一个只读 TqBacktest。"""
    import pandas as pd
    from tqsdk import TqApi, TqAuth, TqBacktest, TqSim

    snapshot = datetime.fromisoformat(day) + timedelta(days=1, hours=8)
    api = None
    serials: dict[str, Any] = {}
    failures: dict[str, str] = {}
    frames: dict[str, Any] = {}
    raw_serial_ranges: dict[str, dict[str, str]] = {}
    was_gc_enabled = gc.isenabled()
    started = time.monotonic()
    try:
        gc.disable()
        api = TqApi(
            TqSim(),
            # The SDK needs a later trading session even when the snapshot is
            # just before a long exchange holiday. The snapshot bound below
            # still rejects every row later than next-day 08:00.
            backtest=TqBacktest(start_dt=snapshot, end_dt=snapshot + timedelta(days=21)),
            auth=TqAuth(cfg["datafeed.username"], cfg["datafeed.password"]),
            disable_print=True,
        )
        gc.disable()

        async def subscribe_all() -> None:
            for vt_symbol in symbols:
                contract, exchange = vt_symbol.split(".")
                serials[vt_symbol] = api.get_kline_serial(f"{exchange}.{contract}", 60, data_length=1000)

        api.create_task(subscribe_all())
        while time.monotonic() - started < timeout:
            if len(serials) == len(symbols) and all(api.is_serial_ready(item) for item in serials.values()):
                break
            api.wait_update(deadline=time.time() + 5)
        for vt_symbol in symbols:
            serial = serials.get(vt_symbol)
            if serial is None or not api.is_serial_ready(serial):
                failures[vt_symbol] = "serial_not_ready"
                continue
            frame = serial.copy()
            frame = frame[(frame["id"] >= 0) & (frame["datetime"] > 0)].copy()
            frame["bar_datetime"] = pd.to_datetime(frame["datetime"], unit="ns", utc=True).dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
            if frame.empty:
                failures[vt_symbol] = "raw_serial_empty"
                continue
            try:
                raw_serial_ranges[vt_symbol] = validate_raw_serial_bounds(
                    day, str(frame["bar_datetime"].min()), str(frame["bar_datetime"].max())
                )
            except ValueError as exc:
                failures[vt_symbol] = type(exc).__name__
                continue
            frame = frame[frame["bar_datetime"].dt.strftime("%Y-%m-%d").eq(day)].copy()
            frame["bar_date"] = day
            frame["vt_symbol"] = vt_symbol
            frame["minute_source"] = SOURCE
            frame = frame[COLUMNS].sort_values("bar_datetime").reset_index(drop=True)
            try:
                validate_natural_day(frame, vt_symbol, day)
            except (ValueError, KeyError, TypeError) as exc:
                failures[vt_symbol] = type(exc).__name__
                continue
            frames[vt_symbol] = frame
    finally:
        if api is not None:
            api.close()
        serials.clear()
        api = None
        gc.collect()
        if was_gc_enabled:
            gc.enable()
    return frames, failures, raw_serial_ranges


def save_day(out: Path, day: str, groups: dict[str, Any], required_symbols: set[str], failures: dict[str, str], raw_serial_ranges: dict[str, dict[str, str]]) -> dict[str, Any]:
    import pandas as pd

    parquet, proof_path, coverage_path = checkpoint_paths(out, day)
    joined = pd.concat([groups[symbol] for symbol in sorted(groups)], ignore_index=True)
    joined = joined.sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)
    validations = [validate_natural_day(groups[symbol], symbol, day) for symbol in sorted(groups)]
    temp_parquet = out / f"{day.replace('-', '')}.{os.getpid()}.tmp.parquet"
    joined.to_parquet(temp_parquet, index=False)
    os.replace(temp_parquet, parquet)
    proof = {
        "day": day,
        "snapshot_at": (datetime.fromisoformat(day) + timedelta(days=1, hours=8)).isoformat(),
        "required_symbols": sorted(required_symbols),
        "completed_symbols": sorted(required_symbols & set(groups)),
        "missing_symbols": sorted(required_symbols - set(groups)),
        "all_cached_symbols": sorted(groups),
        "raw_serial_ranges": {symbol: raw_serial_ranges[symbol] for symbol in sorted(groups)},
        "rows": int(len(joined)),
        "sha256": sha256(parquet),
        "status": "complete" if required_symbols.issubset(groups) else "incomplete",
        "error_types": failures,
        "send_order_api_calls": 0,
        "minute_source": SOURCE,
    }
    temporary = out / f"{day.replace('-', '')}.{os.getpid()}.tmp.json"
    temporary.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, proof_path)
    pd.DataFrame(validations).to_csv(coverage_path, index=False, encoding="utf-8-sig")
    return proof


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--credential-settings", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--dates", action="append", help="逗号分隔自然日；可重复指定")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--limit", type=int, default=0, help="最多处理的自然日数；始终标记 partial")
    parser.add_argument("--timeout", type=float, default=150.0)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    out = (args.output_dir or root / f"research/lines/{LINE}/outputs/stage246_2020_20261014/entry_minute_download").resolve()
    os.umask(0o077)
    out.mkdir(parents=True, exist_ok=True)
    if hasattr(time, "tzset"):
        os.environ["TZ"] = "Asia/Shanghai"
        time.tzset()
    os.chdir(root)
    sys.path[:0] = [str(root), str(args.bundle_root.resolve() / "vendor"), str(root / "examples/portfolio_backtesting")]
    all_keys = read_coverage(args.coverage)
    all_days = sorted({day for _, day in all_keys})
    selected = set(all_days)
    if args.dates:
        wanted = {date.fromisoformat(item.strip()).isoformat() for value in args.dates for item in value.split(",") if item.strip()}
        selected &= wanted
    if args.start_date:
        selected = {day for day in selected if day >= date.fromisoformat(args.start_date).isoformat()}
    if args.end_date:
        selected = {day for day in selected if day <= date.fromisoformat(args.end_date).isoformat()}
    selected_days = sorted(selected)
    if args.limit < 0 or args.timeout <= 0:
        raise SystemExit("invalid limit or timeout")
    if args.limit:
        selected_days = selected_days[:args.limit]
    partial_scope = bool(args.limit or args.dates or args.start_date or args.end_date)
    save_progress(out, all_keys, set(selected_days), partial_scope, deep_check=True)
    if not selected_days:
        raise SystemExit("no selected dates")
    cfg = json.loads(args.credential_settings.read_text(encoding="utf-8"))
    if not cfg.get("datafeed.username") or not cfg.get("datafeed.password"):
        raise SystemExit("credential fields unavailable")
    for index, day in enumerate(selected_days, 1):
        required_symbols = {symbol for symbol, key_day in all_keys if key_day == day}
        lock_path = out / f"{day.replace('-', '')}.lock"
        with lock_path.open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            groups, _ = cached_groups(out, day)
            missing_symbols = sorted(required_symbols - set(groups))
            failures: dict[str, str] = {}
            proof_path = checkpoint_paths(out, day)[1]
            raw_serial_ranges = {}
            if groups and proof_path.is_file():
                raw_serial_ranges = json.loads(proof_path.read_text(encoding="utf-8")).get("raw_serial_ranges", {})
            if missing_symbols:
                started = time.monotonic()
                try:
                    fetched, failures, fetched_ranges = download_day(day, missing_symbols, cfg, args.timeout)
                    groups.update(fetched)
                    raw_serial_ranges.update(fetched_ranges)
                except Exception as exc:
                    failures.update({symbol: type(exc).__name__ for symbol in missing_symbols})
                elapsed = round(time.monotonic() - started, 3)
            else:
                elapsed = 0.0
            if groups:
                proof = save_day(out, day, groups, required_symbols, failures, raw_serial_ranges)
            else:
                proof = {"day": day, "status": "incomplete", "missing_symbols": sorted(required_symbols), "error_types": failures, "send_order_api_calls": 0}
                checkpoint_paths(out, day)[1].write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        progress = save_progress(out, all_keys, set(selected_days), partial_scope)
        print(f"{index}/{len(selected_days)} {day} {proof['status']} cached={len(groups)} missing={len(proof['missing_symbols'])} seconds={elapsed}", flush=True)
    progress = save_progress(out, all_keys, set(selected_days), partial_scope, deep_check=True)
    print(json.dumps({key: progress[key] for key in ("status", "total_input_keys", "completed_count", "missing_count", "partial_scope")}, ensure_ascii=False))
    if progress["missing_count"] or partial_scope:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
