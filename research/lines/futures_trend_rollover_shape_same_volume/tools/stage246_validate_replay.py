"""Stage246 全周期回放结果只读验收；输出缺口清单，不调用交易或回测引擎。

依据：Stage901->847 的结果字段、Stage861 分钟缓存、
qmt_roll_ai_selection_pairwise_runtime.build_runtime_feature_row 和
build_qmt_roll_ai_position_training_samples.load_contract_bars 的实际读取合同。
夜盘规则调用同目录 stage246_validate_minute_sessions，日历尾端
2026-10-15 的上期所行情证据：
https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from stage246_download_entry_minutes import read_coverage
from stage246_validate_minute_sessions import audit_key, trading_dates


LINE = "futures_trend_rollover_shape_same_volume"
CACHE_NAME = "qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv"
CACHE_COLUMNS = ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi", "bar_date"]
VALUES = ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]
EXTRA_DATE = date(2026, 10, 15)
EXTRA_SOURCE = "https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def minute_download_audit(result: Path, root: Path) -> tuple[set[tuple[str, str]], list[dict[str, Any]], list[dict[str, str]], list[str]]:
    coverage_path = result / "opening_minute_coverage.csv"
    keys = read_coverage([coverage_path])
    dates = [date.fromisoformat(day) for _, day in keys]
    calendar = trading_dates(root / ".vntrader/database.db", min(dates), max(dates))
    # 诊断截至10月14日，日线库当天收盘后才更新；10月15日已由交易所行情页证实交易。
    if max(dates) >= date(2026, 10, 14):
        calendar.add(EXTRA_DATE)
    folder = root / f"research/lines/{LINE}/outputs/stage246_2020_20261014/entry_minute_download"
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    errors: list[str] = []
    for symbol, day in sorted(keys):
        try:
            row = audit_key(symbol, day, calendar, folder)
            rows.append(row)
            if row["status"] != "complete":
                reason = f"session_{row['status']}:{row['source_status']}"
                missing.append({"vt_symbol": symbol, "entry_date": day, "reason": reason,
                                "night_missing": str(row["early_missing"] + row["evening_missing"]),
                                "day_missing": str(row["day_missing"]), "cache_status": "not_checked"})
        except Exception as exc:
            errors.append(f"session_audit_exception:{symbol}:{day}:{type(exc).__name__}")
            missing.append({"vt_symbol": symbol, "entry_date": day,
                            "reason": f"session_audit_exception:{type(exc).__name__}",
                            "night_missing": "", "day_missing": "", "cache_status": "not_checked"})
    return keys, rows, missing, errors


def cache_by_required_key(cache: Path, keys: set[tuple[str, str]]) -> dict[tuple[str, str], Any]:
    import pandas as pd

    by_symbol: dict[str, set[str]] = defaultdict(set)
    for symbol, day in keys:
        by_symbol[symbol].add(day)
    frames: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for chunk in pd.read_csv(cache, usecols=CACHE_COLUMNS, chunksize=100_000, encoding="utf-8-sig"):
        relevant = chunk.loc[chunk["vt_symbol"].astype(str).isin(by_symbol)]
        if relevant.empty:
            continue
        relevant = relevant.loc[
            [str(day) in by_symbol.get(str(symbol), set())
             for symbol, day in zip(relevant["vt_symbol"], relevant["bar_date"])]
        ]
        for key, group in relevant.groupby(["vt_symbol", "bar_date"], sort=False):
            frames[(str(key[0]), str(key[1]))].append(group)
    return {key: pd.concat(parts, ignore_index=True) for key, parts in frames.items()}


def same_bars(downloaded: Any, consumed: Any) -> tuple[bool, str]:
    import numpy as np
    import pandas as pd

    if consumed is None or consumed.empty:
        return False, "cache_key_missing"
    original = downloaded[["bar_datetime", *VALUES]].copy()
    current = consumed[["bar_datetime", *VALUES]].copy()
    for frame in (original, current):
        frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce")
        frame.sort_values("bar_datetime", inplace=True)
        frame.reset_index(drop=True, inplace=True)
    if original["bar_datetime"].isna().any() or current["bar_datetime"].isna().any():
        return False, "datetime_invalid"
    if original["bar_datetime"].duplicated().any() or current["bar_datetime"].duplicated().any():
        return False, "duplicate_datetime"
    if len(original) != len(current) or not original["bar_datetime"].equals(current["bar_datetime"]):
        return False, "datetime_grid_mismatch"
    for column in VALUES:
        left = pd.to_numeric(original[column], errors="coerce").to_numpy(dtype=float)
        right = pd.to_numeric(current[column], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(left).all() or not np.isfinite(right).all():
            return False, f"nonfinite_{column}"
        if not np.array_equal(left, right):
            return False, f"value_mismatch_{column}"
    return True, "identical"


def consumed_minute_audit(root: Path, result: Path, keys: set[tuple[str, str]]) -> tuple[list[dict[str, str]], dict[str, Any], list[str]]:
    import pandas as pd

    cache = root / "examples/portfolio_backtesting/backtest_outputs" / CACHE_NAME
    errors: list[str] = []
    rows: list[dict[str, str]] = []
    digest = sha256(cache) if cache.is_file() else ""
    try:
        provenance = json.loads((result / "run_provenance.json").read_text(encoding="utf-8"))
        replay_digest = str(provenance["minute_input_sha256"])
    except (OSError, ValueError, KeyError):
        replay_digest = ""
        errors.append("run_provenance_missing_or_invalid")
    if not digest:
        errors.append("stage861_cache_missing")
    if digest != replay_digest:
        errors.append("stage861_cache_sha256_differs_from_replay")
    consumed = cache_by_required_key(cache, keys) if cache.is_file() else {}
    folder = root / f"research/lines/{LINE}/outputs/stage246_2020_20261014/entry_minute_download"
    by_day: dict[str, list[str]] = defaultdict(list)
    for symbol, day in keys:
        by_day[day].append(symbol)
    downloads: dict[tuple[str, str], Any] = {}
    for day in sorted(by_day):
        path = folder / f"{day.replace('-', '')}.parquet"
        if not path.is_file():
            continue
        try:
            frame = pd.read_parquet(path)
            for symbol, group in frame.groupby("vt_symbol", sort=False):
                key = str(symbol), day
                if key in keys:
                    downloads[key] = group
        except Exception as exc:
            errors.append(f"download_parquet_unreadable:{day}:{type(exc).__name__}")
    for symbol, day in sorted(keys):
        key = symbol, day
        if key not in downloads:
            status, reason = "missing", "download_key_missing"
        else:
            same, reason = same_bars(downloads[key], consumed.get(key))
            status = "identical" if same else "mismatch"
        rows.append({"vt_symbol": symbol, "entry_date": day, "status": status,
                     "reason": reason, "download_rows": str(len(downloads[key])) if key in downloads else "0",
                     "cache_rows": str(len(consumed.get(key, [])))})
    if cache.is_file() and sha256(cache) != digest:
        errors.append("stage861_cache_changed_during_audit")
    return rows, {"cache_path": str(cache), "cache_sha256": digest,
                  "replay_minute_input_sha256": replay_digest,
                  "cache_matches_replay": bool(digest and digest == replay_digest)}, errors


def positions_daily_audit(root: Path, result: Path) -> tuple[list[dict[str, str]], int]:
    import pandas as pd

    active: set[tuple[str, str]] = set()
    for chunk in pd.read_csv(result / "positions.csv", usecols=["date", "vt_symbol", "start_pos", "end_pos", "trade_count"], chunksize=100_000):
        numeric = chunk[["start_pos", "end_pos", "trade_count"]].apply(pd.to_numeric, errors="coerce").fillna(0)
        selected = chunk.loc[numeric.ne(0).any(axis=1), ["vt_symbol", "date"]]
        active.update((str(symbol), str(day)[:10]) for symbol, day in selected.itertuples(index=False, name=None))
    db = root / ".vntrader/database.db"
    missing: list[dict[str, str]] = []
    grouped: dict[str, set[str]] = defaultdict(set)
    for symbol, day in active:
        grouped[symbol].add(day)
    with sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True) as connection:
        for vt_symbol, days in sorted(grouped.items()):
            symbol, exchange = vt_symbol.rsplit(".", 1)
            available = {row[0] for row in connection.execute(
                "SELECT DISTINCT substr(datetime,1,10) FROM dbbardata "
                "WHERE symbol=? AND exchange=? AND interval='d' AND datetime>=? AND datetime<?",
                (symbol, exchange, min(days),
                 (date.fromisoformat(max(days)) + timedelta(days=1)).isoformat()),
            )}
            for day in sorted(days - available):
                missing.append({"vt_symbol": vt_symbol, "date": day, "reason": "active_position_daily_bar_missing"})
    return missing, len(active)


def pairwise_raw_daily_audit(root: Path, result: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    import pandas as pd

    candidates = pd.read_csv(result / "entry_candidates.csv", usecols=["date", "contract_vt_symbol", "selection_pairwise_enabled"])
    selected = candidates.loc[pd.to_numeric(candidates["selection_pairwise_enabled"], errors="coerce").eq(1)]
    pairs = sorted({(str(row.contract_vt_symbol), str(row.date)[:10]) for row in selected.itertuples(index=False)
                    if str(row.contract_vt_symbol).count(".") == 1})
    root_daily = root / "examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04"
    bars_cache: dict[str, set[str] | None] = {}
    rows: list[dict[str, str]] = []
    for symbol, day in pairs:
        if symbol not in bars_cache:
            contract, exchange = symbol.rsplit(".", 1)
            path = root_daily / exchange / f"{contract}.csv"
            if not path.is_file():
                bars_cache[symbol] = None
            else:
                raw = pd.read_csv(path, usecols=["trade_date"], dtype=str, encoding="utf-8-sig")
                bars_cache[symbol] = set(pd.to_datetime(raw["trade_date"], errors="coerce").dropna().dt.strftime("%Y-%m-%d"))
        dates = bars_cache[symbol]
        if dates is None or not dates:
            status, latest = "history_fallback", ""
        else:
            usable = [value for value in dates if value <= day]
            if not usable:
                status, latest = "history_fallback", ""
            else:
                latest = max(usable)
                status = "current" if latest == day else "stale"
        rows.append({"vt_symbol": symbol, "candidate_date": day, "raw_latest_usable_trade_date": latest,
                     "status": status, "raw_path": str(root_daily / symbol.rsplit(".", 1)[1] / f"{symbol.rsplit('.', 1)[0]}.csv")})
    return rows, dict(Counter(row["status"] for row in rows))


def execution_proxy_audit(result: Path) -> tuple[list[dict[str, str]], dict[str, Any], list[str]]:
    import pandas as pd

    usage = pd.read_csv(result / "execution_proxy_usage.csv", dtype=str).fillna("")
    trades = pd.read_csv(result / "trades.csv", usecols=["trade_id"], dtype=str).fillna("")
    usage_ids = Counter(usage["trade_id"].astype(str))
    trade_ids = Counter(trades["trade_id"].astype(str))
    errors = [] if usage_ids == trade_ids and all(count == 1 for count in usage_ids.values()) else ["execution_proxy_trade_ids_not_1_to_1"]
    required: list[dict[str, str]] = []
    for row in usage.itertuples(index=False):
        source = str(row.price_source)
        first = str(row.proxy_first_time)
        reason = target = required_time = ""
        if str(row.vt_symbol).startswith("SH") and str(row.vt_symbol).endswith(".CZCE") and source == "fallback_daily_next_open":
            reason, target, required_time = "SH_fallback_daily_next_open", str(row.fill_date), "09:00"
        elif source == "raw_day_0900_0905_first_open" and not first.endswith("09:00:00"):
            reason, target, required_time = "raw_day_first_not_0900", str(row.fill_date), "09:00"
        elif source == "raw_night_2100_2105_first_open" and not first.endswith("21:00:00"):
            reason, target, required_time = "raw_night_first_not_2100", str(row.signal_date), "21:00"
        if reason:
            required.append({"trade_id": str(row.trade_id), "vt_symbol": str(row.vt_symbol),
                             "entry_date": target, "reason": reason, "required_time": required_time,
                             "price_source": source, "proxy_first_time": first,
                             "signal_date": str(row.signal_date), "fill_date": str(row.fill_date)})
    return required, {"usage_rows": len(usage), "trade_rows": len(trades),
                      "unique_usage_trade_ids": len(usage_ids), "ids_1_to_1": not errors,
                      "price_source_counts": dict(Counter(usage["price_source"]))}, errors


def execution_patched_price_audit(root: Path, result: Path) -> tuple[list[dict[str, str]], dict[str, Any], list[str]]:
    """仅核对本次补丁日期实际使用 raw 日/夜代理的成交价；unused 不阻断。"""
    import pandas as pd

    output_root = root / f"research/lines/{LINE}/outputs/stage246_2020_20261014"
    minute_dir = output_root / "entry_minute_download"
    raw_root = root / "examples/portfolio_backtesting/downloaded_futures/tqsdk_stage506_next_real_forward_risk_signal_frontier"
    proofs = sorted(output_root.glob("execution_minute_patch_*.json"), key=lambda path: (path.stat().st_mtime_ns, path.name))
    files: dict[Path, dict[str, Any]] = {}
    errors: list[str] = []
    for proof_path in proofs:
        try:
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            if proof.get("status") != "completed" or not isinstance(proof.get("files"), list):
                raise ValueError("patch_proof_not_completed")
            for item in proof["files"]:
                path = Path(str(item["path"])).resolve()
                if not path.is_relative_to(raw_root.resolve()):
                    raise ValueError("patch_raw_path_outside_stage506")
                symbol = str(item["vt_symbol"])
                dates = {date.fromisoformat(str(value)).isoformat() for value in item["dates"]}
                if not dates or not str(item.get("after_sha256", "")):
                    raise ValueError("patch_dates_or_sha_missing")
                record = files.setdefault(path, {"vt_symbol": symbol, "dates": set(), "sha256": "", "proof": ""})
                if record["vt_symbol"] != symbol:
                    raise ValueError("patch_symbol_conflict")
                record["dates"].update(dates)
                # 已按 mtime 排序；同一路径最后一次出现就是现存文件应匹配的 SHA。
                record["sha256"] = str(item["after_sha256"])
                record["proof"] = str(proof_path)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"execution_patch_proof_invalid:{proof_path.name}:{type(exc).__name__}")

    usage = pd.read_csv(result / "execution_proxy_usage.csv", dtype=str).fillna("")
    rows: list[dict[str, str]] = []
    raw_cache: dict[Path, Any] = {}
    download_cache: dict[str, Any] = {}
    proof_cache: dict[str, bool] = {}
    matched_trade_rows = 0

    def open_at(frame: Any, symbol: str, moment: str) -> tuple[float | None, str]:
        if frame is None or frame.empty:
            return None, "rows_missing"
        selected = frame.loc[frame["vt_symbol"].astype(str).eq(symbol) &
                             pd.to_datetime(frame["bar_datetime"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S").eq(moment)]
        if len(selected) != 1:
            return None, "minute_missing_or_duplicate"
        price = pd.to_numeric(selected["open"], errors="coerce").iloc[0]
        if pd.isna(price):
            return None, "open_invalid"
        return float(price), "ok"

    for path, record in sorted(files.items()):
        symbol = record["vt_symbol"]
        path_status = "ok" if path.is_file() and sha256(path) == record["sha256"] else "raw_file_sha_mismatch"
        if path_status != "ok":
            errors.append(f"execution_patch_current_sha_mismatch:{symbol}:{path.name}")
        try:
            raw_cache[path] = pd.read_csv(path, usecols=["vt_symbol", "bar_datetime", "open"], encoding="utf-8-sig") if path.is_file() else None
        except (OSError, ValueError):
            raw_cache[path] = None
            errors.append(f"execution_patch_raw_unreadable:{symbol}:{path.name}")
        if path.is_file() and sha256(path) != record["sha256"]:
            path_status = "raw_file_sha_mismatch"
            errors.append(f"execution_patch_raw_changed_during_audit:{symbol}:{path.name}")
        for day in sorted(record["dates"]):
            relevant: list[Any] = []
            for trade in usage.itertuples(index=False):
                if str(trade.vt_symbol) != symbol:
                    continue
                source = str(trade.price_source)
                if source.startswith("raw_day_") and str(trade.fill_date) == day:
                    relevant.append(trade)
                elif source.startswith("raw_night_") and str(trade.signal_date) == day:
                    relevant.append(trade)
            if not relevant:
                rows.append({"vt_symbol": symbol, "date": day, "status": "unused", "reason": "patched_date_not_used_by_raw_proxy",
                             "trade_id": "", "price_source": "", "proxy_first_time": "", "trade_price": "",
                             "raw_open": "", "download_open": "", "raw_path": str(path), "patch_proof": record["proof"]})
                continue
            for trade in relevant:
                matched_trade_rows += 1
                moment_ts = pd.to_datetime(str(trade.proxy_first_time), errors="coerce")
                moment = moment_ts.strftime("%Y-%m-%d %H:%M:%S") if not pd.isna(moment_ts) else ""
                if day not in download_cache:
                    parquet = minute_dir / f"{day.replace('-', '')}.parquet"
                    proof_path = minute_dir / f"{day.replace('-', '')}_proof.json"
                    try:
                        download_cache[day] = pd.read_parquet(parquet, columns=["vt_symbol", "bar_datetime", "open"])
                        proof_data = json.loads(proof_path.read_text(encoding="utf-8"))
                        proof_cache[day] = sha256(parquet) == str(proof_data.get("sha256", ""))
                    except (OSError, ValueError, KeyError, TypeError):
                        download_cache[day] = None
                        proof_cache[day] = False
                raw_open, raw_state = open_at(raw_cache[path], symbol, moment)
                download_open, download_state = open_at(download_cache[day], symbol, moment)
                try:
                    trade_price = float(trade.trade_price)
                except (TypeError, ValueError):
                    trade_price = None
                if path_status != "ok":
                    status, reason = "failed", path_status
                elif not proof_cache[day]:
                    status, reason = "failed", "download_proof_sha_mismatch_or_missing"
                elif raw_state != "ok":
                    status, reason = "failed", f"raw_{raw_state}"
                elif download_state != "ok":
                    status, reason = "failed", f"download_{download_state}"
                elif trade_price is None or trade_price != raw_open or raw_open != download_open:
                    status, reason = "failed", "trade_raw_download_open_not_identical"
                else:
                    status, reason = "passed", "identical"
                rows.append({"vt_symbol": symbol, "date": day, "status": status, "reason": reason,
                             "trade_id": str(trade.trade_id), "price_source": str(trade.price_source),
                             "proxy_first_time": moment, "trade_price": "" if trade_price is None else str(trade_price),
                             "raw_open": "" if raw_open is None else str(raw_open),
                             "download_open": "" if download_open is None else str(download_open),
                             "raw_path": str(path), "patch_proof": record["proof"]})
    failed = [row for row in rows if row["status"] == "failed"]
    if failed:
        errors.append("execution_patched_price_not_identical")
    return rows, {"patch_proofs": len(proofs), "patched_raw_files": len(files),
                  "patched_symbol_dates": sum(len(record["dates"]) for record in files.values()),
                  "raw_proxy_trade_rows": matched_trade_rows,
                  "price_passed": sum(row["status"] == "passed" for row in rows),
                  "price_failed": len(failed), "unused": sum(row["status"] == "unused" for row in rows)}, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root, result = args.repo_root.resolve(), args.result.resolve()
    out = args.out.resolve() if args.out else result
    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    keys, session_rows, missing, findings = minute_download_audit(result, root)
    errors.extend(findings)
    cache_rows, cache_info, findings = consumed_minute_audit(root, result, keys)
    errors.extend(findings)
    cache_status = {(row["vt_symbol"], row["entry_date"]): row for row in cache_rows}
    existing_missing = {(row["vt_symbol"], row["entry_date"]) for row in missing}
    for key in sorted(keys):
        row = cache_status[key]
        if row["status"] != "identical":
            if key in existing_missing:
                next(item for item in missing if (item["vt_symbol"], item["entry_date"]) == key)["cache_status"] = row["reason"]
            else:
                missing.append({"vt_symbol": key[0], "entry_date": key[1], "reason": row["reason"],
                                "night_missing": "0", "day_missing": "0", "cache_status": row["status"]})
    positions_missing, positions_active = positions_daily_audit(root, result)
    pairwise_rows, pairwise_counts = pairwise_raw_daily_audit(root, result)
    proxy_required, proxy_info, findings = execution_proxy_audit(result)
    errors.extend(findings)
    patched_price_rows, patched_price_info, findings = execution_patched_price_audit(root, result)
    errors.extend(findings)

    write_csv(out / "minute_session_audit.csv", session_rows, list(session_rows[0]) if session_rows else ["vt_symbol", "entry_date", "status"])
    write_csv(out / "minute_cache_audit.csv", cache_rows,
              ["vt_symbol", "entry_date", "status", "reason", "download_rows", "cache_rows"])
    write_csv(out / "missing_required_entry_days.csv", missing,
              ["vt_symbol", "entry_date", "reason", "night_missing", "day_missing", "cache_status"])
    write_csv(out / "positions_missing_daily.csv", positions_missing, ["vt_symbol", "date", "reason"])
    write_csv(out / "pairwise_raw_daily_audit.csv", pairwise_rows,
              ["vt_symbol", "candidate_date", "raw_latest_usable_trade_date", "status", "raw_path"])
    write_csv(out / "execution_proxy_required_days.csv", proxy_required,
              ["trade_id", "vt_symbol", "entry_date", "reason", "required_time", "price_source",
               "proxy_first_time", "signal_date", "fill_date"])
    write_csv(out / "execution_patched_price_audit.csv", patched_price_rows,
              ["vt_symbol", "date", "status", "reason", "trade_id", "price_source", "proxy_first_time",
               "trade_price", "raw_open", "download_open", "raw_path", "patch_proof"])
    stale = [row for row in pairwise_rows if row["status"] == "stale"]
    if missing:
        errors.append("required_entry_minute_days_incomplete_or_not_consumed")
    if positions_missing:
        errors.append("active_position_sqlite_daily_missing")
    if stale:
        errors.append("selection_pairwise_raw_daily_stale")
    if proxy_required:
        errors.append("execution_proxy_raw_days_required")
    report = {
        "status": "passed" if not errors else "failed", "repo_root": str(root), "result": str(result),
        "out": str(out), "errors": sorted(set(errors)), "counts": {
            "unique_open_keys": len(keys), "minute_session_complete": sum(row["status"] == "complete" for row in session_rows),
            "minute_cache_identical": sum(row["status"] == "identical" for row in cache_rows),
            "missing_required_entry_days": len(missing), "active_position_keys": positions_active,
            "positions_missing_daily": len(positions_missing), "pairwise_candidate_contract_days": len(pairwise_rows),
            "pairwise_stale": len(stale), "pairwise_history_fallback": pairwise_counts.get("history_fallback", 0),
            "execution_proxy_required_days": len(proxy_required),
            "execution_patched_price_passed": patched_price_info["price_passed"],
            "execution_patched_price_failed": patched_price_info["price_failed"],
            "execution_patched_unused_dates": patched_price_info["unused"],
        }, "cache": cache_info, "execution_proxy": proxy_info,
        "execution_patched_price": patched_price_info,
        "error_details": {
            "missing_entry_reasons": dict(Counter(row["reason"] for row in missing)),
            "missing_entry_samples": missing[:20],
            "positions_missing_samples": positions_missing[:20],
            "pairwise_stale_samples": stale[:20],
            "execution_proxy_reasons": dict(Counter(row["reason"] for row in proxy_required)),
            "execution_proxy_required_samples": proxy_required[:20],
            "execution_patched_price_failure_samples": [row for row in patched_price_rows if row["status"] == "failed"][:20],
        },
        "calendar_extra_date": EXTRA_DATE.isoformat(), "calendar_extra_source": EXTRA_SOURCE,
        "limitation": "Only actual opening natural-day minute keys and exported execution-proxy rows are checked; no engine rerun.",
    }
    (out / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "counts": report["counts"], "errors": report["errors"]}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
