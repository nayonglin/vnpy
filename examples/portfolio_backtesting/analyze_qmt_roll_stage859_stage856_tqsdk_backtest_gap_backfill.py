from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import math
import multiprocessing as mp
import os
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
DATA_ROOT = PROJECT_DIR / "downloaded_futures"
RAW_ROOT = DATA_ROOT / "tqsdk_stage859_stage856_remaining_gap_backfill"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage859"
MODEL_TAG = "stage859_stage856_tqsdk_backtest_gap_backfill_v1"
OUTPUT_PREFIX = "qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill"

STAGE856_PREFIX = "qmt_roll_stage856_stage855_remaining_gap_download"
STAGE856_TAG = "stage856_stage855_remaining_gap_download_v1"
REMAINING_GAP_REQUESTS_PATH = (
    OUTPUT_DIR / f"{STAGE856_PREFIX}_remaining_gap_requests_{STAGE856_TAG}.csv"
)

BATCH_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_batch_plan_{MODEL_TAG}.csv"
SOURCE_READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_readiness_{MODEL_TAG}.csv"
LOCAL_CACHE_SCAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_cache_scan_{MODEL_TAG}.csv"
AKSHARE_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_akshare_probe_{MODEL_TAG}.csv"
EXTRACT_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tqsdk_extract_status_{MODEL_TAG}.csv"
MINUTE_BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_bars_{MODEL_TAG}.csv"
REQUEST_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_coverage_after_stage859_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

MAX_BATCHES = int(os.getenv("STAGE859_MAX_BATCHES", "25"))
ENABLE_TQSDK_BACKTEST = os.getenv("STAGE859_ENABLE_TQSDK_BACKTEST", "1").strip() != "0"
MAX_SECONDS_PER_BATCH = int(os.getenv("STAGE859_MAX_SECONDS_PER_BATCH", "75"))
AKSHARE_MAX_SYMBOLS = int(os.getenv("STAGE859_AKSHARE_MAX_SYMBOLS", "8"))
AKSHARE_TIMEOUT_SECONDS = int(os.getenv("STAGE859_AKSHARE_TIMEOUT_SECONDS", "15"))
MINUTE_BAR_MIN_COUNT = int(os.getenv("STAGE859_MINUTE_BAR_MIN_COUNT", "10"))
START_TIME = "00:00:00"
END_PLUS_DAYS = 1


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _normal_date(value: Any) -> pd.Timestamp:
    return pd.Timestamp(pd.to_datetime(value, errors="coerce")).normalize()


def _date_text(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return str(pd.Timestamp(ts).date())


def _split_vt(vt_symbol: str) -> tuple[str, str]:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return symbol, exchange


def _to_tq_symbol(vt_symbol: str) -> str:
    symbol, exchange = _split_vt(vt_symbol)
    return f"{exchange}.{symbol}"


def _raw_path_for(vt_symbol: str, required_date: str) -> Path:
    symbol, exchange = _split_vt(vt_symbol)
    return RAW_ROOT / exchange / f"{symbol}_{required_date.replace('-', '')}_minute_backtest.csv"


def _load_gaps() -> pd.DataFrame:
    gaps = _load_csv(REMAINING_GAP_REQUESTS_PATH).copy()
    gaps = _numeric(
        gaps,
        [
            "priority_abs_pnl",
            "realized_pnl",
            "big_winner",
            "entry_year",
            "after_stage856_exact_date_bars",
            "covered_after_stage856",
        ],
    )
    gaps["required_date_text"] = gaps["required_date"].map(_date_text)
    gaps["vt_symbol"] = gaps["vt_symbol"].astype(str)
    gaps["product"] = gaps["product"].astype(str)
    gaps["direction"] = gaps["direction"].astype(str)
    return gaps


def _build_batch_plan(gaps: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (vt_symbol, required_date), group in gaps.groupby(["vt_symbol", "required_date_text"], sort=False):
        rows.append(
            {
                "vt_symbol": vt_symbol,
                "tq_symbol": _to_tq_symbol(vt_symbol),
                "required_date": required_date,
                "product": ",".join(sorted(set(group["product"].astype(str)))),
                "directions": ",".join(sorted(set(group["direction"].astype(str)))),
                "request_count": int(len(group)),
                "entry_day_requests": int(group["request_type"].astype(str).eq("stage825_entry_day").sum()),
                "pressure_key_date_requests": int(
                    group["request_type"].astype(str).eq("stage849_pressure_key_date").sum()
                ),
                "priority_abs_pnl_sum": float(group["priority_abs_pnl"].sum()),
                "priority_abs_pnl_max": float(group["priority_abs_pnl"].max()),
                "realized_pnl_sum": float(group["realized_pnl"].sum()),
                "big_winner_requests": int(group["big_winner"].fillna(0).astype(float).gt(0).sum()),
                "raw_path": str(_raw_path_for(vt_symbol, required_date)),
            }
        )
    plan = pd.DataFrame(rows).sort_values(
        ["priority_abs_pnl_sum", "priority_abs_pnl_max", "request_count", "vt_symbol", "required_date"],
        ascending=[False, False, False, True, True],
    )
    plan["batch_rank"] = np.arange(1, len(plan) + 1)
    return plan.reset_index(drop=True)


def _detect_datetime_column(columns: list[str]) -> str | None:
    for column in ["bar_datetime", "datetime", "time", "date", "trade_time"]:
        if column in columns:
            return column
    return None


def _candidate_cache_files(plan: pd.DataFrame) -> list[tuple[str, Path]]:
    needed = set(plan["vt_symbol"].astype(str))
    results: list[tuple[str, Path]] = []
    for path in DATA_ROOT.rglob("*.csv"):
        lower_path = str(path).lower()
        if "daily" in lower_path:
            continue
        stem = path.stem.replace("_minute_backtest", "")
        exchange = path.parent.name.upper()
        for vt_symbol in needed:
            symbol, vt_exchange = _split_vt(vt_symbol)
            if stem.lower() == symbol.lower() and exchange == vt_exchange.upper():
                results.append((vt_symbol, path))
                break
    return results


def _local_cache_scan(gaps: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    candidates = _candidate_cache_files(plan)
    gap_lookup = {
        (str(row.vt_symbol), str(row.required_date_text)): []
        for row in gaps.itertuples(index=False)
    }
    for row in gaps.itertuples(index=False):
        gap_lookup[(str(row.vt_symbol), str(row.required_date_text))].append(row)

    for vt_symbol, path in candidates:
        try:
            head = pd.read_csv(path, encoding="utf-8-sig", nrows=5)
            dt_col = _detect_datetime_column(list(head.columns))
            if dt_col is None:
                rows.append(
                    {
                        "vt_symbol": vt_symbol,
                        "file": str(path),
                        "status": "missing_datetime_column",
                        "target_date": "",
                        "target_date_bars": 0,
                        "minute_like": 0,
                        "covered_requests": 0,
                    }
                )
                continue
            dates = pd.to_datetime(
                pd.read_csv(path, encoding="utf-8-sig", usecols=[dt_col])[dt_col],
                errors="coerce",
            ).dt.strftime("%Y-%m-%d")
            counts = dates.value_counts().to_dict()
        except Exception as exc:
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "file": str(path),
                    "status": "read_failed",
                    "message": repr(exc)[:300],
                    "target_date": "",
                    "target_date_bars": 0,
                    "minute_like": 0,
                    "covered_requests": 0,
                }
            )
            continue
        for (lookup_symbol, target_date), gap_rows in gap_lookup.items():
            if lookup_symbol != vt_symbol:
                continue
            bars = int(counts.get(target_date, 0))
            if bars <= 0:
                continue
            minute_like = int(bars >= MINUTE_BAR_MIN_COUNT)
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "file": str(path),
                    "status": "date_seen",
                    "target_date": target_date,
                    "target_date_bars": bars,
                    "minute_like": minute_like,
                    "covered_requests": int(len(gap_rows)) if minute_like else 0,
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "vt_symbol",
                "file",
                "status",
                "target_date",
                "target_date_bars",
                "minute_like",
                "covered_requests",
            ]
        )
    return pd.DataFrame(rows).sort_values(["minute_like", "target_date_bars"], ascending=[False, False])


def _czce_full_year_symbol(symbol: str, required_date: str) -> str | None:
    letters = "".join(ch for ch in symbol if ch.isalpha()).upper()
    digits = "".join(ch for ch in symbol if ch.isdigit())
    if len(digits) != 3:
        return None
    year_digit = int(digits[0])
    month = int(digits[1:])
    req_year = pd.Timestamp(required_date).year
    candidates: list[int] = []
    for year in range(req_year - 2, req_year + 4):
        if year % 10 == year_digit:
            candidates.append(year)
    if not candidates:
        return None
    # Futures expiry should usually be near or after the required date; choose the closest plausible contract year.
    req_month = pd.Timestamp(required_date).month
    req_serial = req_year * 12 + req_month
    best_year = min(candidates, key=lambda year: abs((year * 12 + month) - req_serial))
    return f"{letters}{best_year % 100:02d}{month:02d}"


def _akshare_symbol_candidates(vt_symbol: str, required_date: str) -> list[str]:
    symbol, exchange = _split_vt(vt_symbol)
    upper = symbol.upper()
    candidates = [upper]
    if exchange.upper() == "CZCE":
        full = _czce_full_year_symbol(symbol, required_date)
        if full and full not in candidates:
            candidates.insert(0, full)
    return candidates


def _akshare_worker(symbol: str, queue: mp.Queue) -> None:
    try:
        import akshare as ak

        data = ak.futures_zh_minute_sina(symbol=symbol, period="1")
        if not isinstance(data, pd.DataFrame) or data.empty:
            queue.put({"status": "empty", "symbol": symbol, "rows": 0, "columns": []})
            return
        dt_col = _detect_datetime_column(list(data.columns))
        if dt_col is None:
            queue.put({"status": "missing_datetime", "symbol": symbol, "rows": int(len(data)), "columns": list(data.columns)})
            return
        dates = pd.to_datetime(data[dt_col], errors="coerce")
        queue.put(
            {
                "status": "ok",
                "symbol": symbol,
                "rows": int(len(data)),
                "columns": list(data.columns),
                "min_datetime": str(dates.min()) if dates.notna().any() else "",
                "max_datetime": str(dates.max()) if dates.notna().any() else "",
                "date_counts": dates.dt.strftime("%Y-%m-%d").value_counts().head(2000).to_dict(),
            }
        )
    except Exception as exc:
        queue.put(
            {
                "status": "error",
                "symbol": symbol,
                "rows": 0,
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:500],
            }
        )


def _run_akshare_probe(gaps: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
    if AKSHARE_MAX_SYMBOLS <= 0:
        return pd.DataFrame()
    selected = plan.head(AKSHARE_MAX_SYMBOLS).copy()
    rows: list[dict[str, Any]] = []
    ctx = mp.get_context("fork")
    for row in selected.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        target_date = str(row.required_date)
        candidates = _akshare_symbol_candidates(vt_symbol, target_date)
        best: dict[str, Any] | None = None
        for candidate in candidates:
            queue: mp.Queue = ctx.Queue()
            process = ctx.Process(target=_akshare_worker, args=(candidate, queue))
            process.start()
            process.join(AKSHARE_TIMEOUT_SECONDS)
            if process.is_alive():
                process.terminate()
                process.join(2)
                probe = {"status": "timeout", "symbol": candidate, "rows": 0}
            elif queue.empty():
                probe = {"status": "empty_message", "symbol": candidate, "rows": 0}
            else:
                probe = queue.get()
            date_counts = probe.get("date_counts", {}) if isinstance(probe.get("date_counts"), dict) else {}
            target_bars = int(date_counts.get(target_date, 0))
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "required_date": target_date,
                    "akshare_symbol": candidate,
                    "status": probe.get("status"),
                    "rows": int(probe.get("rows", 0) or 0),
                    "target_date_bars": target_bars,
                    "covers_target_date": int(target_bars >= MINUTE_BAR_MIN_COUNT),
                    "min_datetime": probe.get("min_datetime", ""),
                    "max_datetime": probe.get("max_datetime", ""),
                    "error_type": probe.get("error_type", ""),
                    "error_message": probe.get("error_message", ""),
                }
            )
            if target_bars >= MINUTE_BAR_MIN_COUNT:
                best = probe
                break
            if probe.get("status") == "ok" and best is None:
                best = probe
        _ = best
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _source_readiness() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for module in ["akshare", "tqsdk", "rqdatac", "vnpy_rqdata", "tushare"]:
        try:
            imported = __import__(module)
            version = getattr(imported, "__version__", "")
            status = "installed"
        except Exception as exc:
            version = ""
            status = f"import_failed:{type(exc).__name__}"
        rows.append({"source": module, "status": status, "version": version})
    try:
        from vnpy.trader.setting import SETTINGS

        username = str(SETTINGS.get("datafeed.username", ""))
        password = str(SETTINGS.get("datafeed.password", ""))
        rows.append(
            {
                "source": "tqsdk_vnpy_settings_credentials",
                "status": "available" if username and password else "missing",
                "version": f"user_len={len(username)},password_len={len(password)}",
            }
        )
    except Exception as exc:
        rows.append(
            {
                "source": "tqsdk_vnpy_settings_credentials",
                "status": f"read_failed:{type(exc).__name__}",
                "version": "",
            }
        )
    rows.append(
        {
            "source": "rqdatac_credentials_env",
            "status": "available"
            if os.getenv("RQDATAC2_CONF") or (os.getenv("RQDATA_USERNAME") and os.getenv("RQDATA_PASSWORD"))
            else "missing",
            "version": "",
        }
    )
    rows.append(
        {
            "source": "tushare_token_env",
            "status": "available" if os.getenv("TUSHARE_TOKEN") else "missing",
            "version": "",
        }
    )
    return pd.DataFrame(rows)


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    from vnpy.trader.utility import ZoneInfo

    ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(ZoneInfo("Asia/Shanghai")).tz_localize(None)


def _load_raw_if_covered(path: Path, vt_symbol: str, required_date: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        data = pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()
    if data.empty or "bar_datetime" not in data.columns:
        return pd.DataFrame()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data = data.dropna(subset=["bar_datetime"])
    data["bar_date"] = data["bar_datetime"].dt.strftime("%Y-%m-%d")
    target = data[data["bar_date"].eq(required_date)].copy()
    if len(target) < MINUTE_BAR_MIN_COUNT:
        return pd.DataFrame()
    target["vt_symbol"] = vt_symbol
    return target


def _extract_tqsdk_batch(row: Any, username: str, password: str) -> tuple[dict[str, Any], pd.DataFrame]:
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("tqsdk").setLevel(logging.WARNING)

    vt_symbol = str(row.vt_symbol)
    tq_symbol = str(row.tq_symbol)
    required_date = str(row.required_date)
    raw_path = Path(str(row.raw_path))
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    status = {
        "batch_rank": int(row.batch_rank),
        "vt_symbol": vt_symbol,
        "tq_symbol": tq_symbol,
        "required_date": required_date,
        "request_count": int(row.request_count),
        "entry_day_requests": int(row.entry_day_requests),
        "pressure_key_date_requests": int(row.pressure_key_date_requests),
        "priority_abs_pnl_sum": float(row.priority_abs_pnl_sum),
        "raw_path": str(raw_path),
        "status": "unknown",
        "rows": 0,
        "target_date_rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }
    cached = _load_raw_if_covered(raw_path, vt_symbol, required_date)
    if not cached.empty:
        status["status"] = "cached_stage859_raw"
        status["rows"] = int(len(cached))
        status["target_date_rows"] = int(len(cached))
        return status, cached

    if not ENABLE_TQSDK_BACKTEST:
        status["status"] = "skipped_disabled"
        return status, pd.DataFrame()

    try:
        from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
    except Exception as exc:
        status["status"] = "import_failed"
        status["message"] = repr(exc)[:500]
        return status, pd.DataFrame()

    start_dt = pd.Timestamp(f"{required_date} {START_TIME}")
    end_dt = start_dt + timedelta(days=END_PLUS_DAYS)
    started = time.time()
    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    api = None
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=start_dt.to_pydatetime(), end_dt=end_dt.to_pydatetime()),
            auth=TqAuth(username, password),
            disable_print=True,
        )
        klines = api.get_kline_serial(tq_symbol, duration_seconds=60, data_length=500)
        while True:
            if time.time() - started > MAX_SECONDS_PER_BATCH:
                status["status"] = "timeout"
                status["message"] = f"timeout_after_{MAX_SECONDS_PER_BATCH}s"
                break
            api.wait_update()
            if not api.is_changing(klines.iloc[-1], "datetime"):
                continue
            bar = klines.iloc[-1].to_dict()
            bar_id = int(bar.get("id", -1))
            if bar_id in seen_ids:
                continue
            seen_ids.add(bar_id)
            bar_dt = _normalize_tqsdk_datetime(bar.get("datetime"))
            if pd.isna(bar_dt):
                continue
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "tq_symbol": tq_symbol,
                    "bar_datetime": bar_dt,
                    "bar_id": bar_id,
                    "open": float(bar.get("open", np.nan)),
                    "high": float(bar.get("high", np.nan)),
                    "low": float(bar.get("low", np.nan)),
                    "close": float(bar.get("close", np.nan)),
                    "volume": float(bar.get("volume", np.nan)),
                    "open_oi": float(bar.get("open_oi", np.nan)),
                    "close_oi": float(bar.get("close_oi", np.nan)),
                    "required_date": required_date,
                    "minute_source": "tqsdk_stage859_backtest",
                }
            )
    except BacktestFinished:
        status["status"] = "extracted"
    except Exception as exc:
        status["status"] = "failed"
        status["message"] = repr(exc)[:500]
    finally:
        if api is not None:
            api.close()

    bars = pd.DataFrame(rows)
    if not bars.empty:
        bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce")
        bars = bars.dropna(subset=["bar_datetime"])
        bars = bars.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
        bars["bar_date"] = bars["bar_datetime"].dt.strftime("%Y-%m-%d")
        bars.to_csv(raw_path, index=False, encoding="utf-8-sig")
    if status["status"] == "unknown":
        status["status"] = "extracted" if not bars.empty else "empty"
    status["rows"] = int(len(bars))
    status["target_date_rows"] = int(bars["bar_date"].eq(required_date).sum()) if "bar_date" in bars else 0
    status["elapsed_seconds"] = round(time.time() - started, 2)
    return status, bars


def _run_tqsdk_extract(plan: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if plan.empty:
        return pd.DataFrame(), pd.DataFrame()
    selected = plan.copy()
    if MAX_BATCHES > 0:
        selected = selected.head(MAX_BATCHES).copy()
    try:
        from vnpy.trader.setting import SETTINGS

        username = str(SETTINGS.get("datafeed.username", ""))
        password = str(SETTINGS.get("datafeed.password", ""))
    except Exception:
        username = ""
        password = ""
    status_rows: list[dict[str, Any]] = []
    bar_frames: list[pd.DataFrame] = []
    for row in selected.itertuples(index=False):
        if not username or not password:
            status_rows.append(
                {
                    "batch_rank": int(row.batch_rank),
                    "vt_symbol": str(row.vt_symbol),
                    "tq_symbol": str(row.tq_symbol),
                    "required_date": str(row.required_date),
                    "request_count": int(row.request_count),
                    "priority_abs_pnl_sum": float(row.priority_abs_pnl_sum),
                    "raw_path": str(row.raw_path),
                    "status": "missing_credentials",
                    "rows": 0,
                    "target_date_rows": 0,
                    "elapsed_seconds": 0.0,
                    "message": "vnpy SETTINGS datafeed credentials missing",
                }
            )
            continue
        status, bars = _extract_tqsdk_batch(row, username, password)
        status_rows.append(status)
        if not bars.empty:
            bar_frames.append(bars)
    status_frame = pd.DataFrame(status_rows)
    bars_frame = pd.concat(bar_frames, ignore_index=True, sort=False) if bar_frames else pd.DataFrame()
    if not bars_frame.empty:
        bars_frame["bar_datetime"] = pd.to_datetime(bars_frame["bar_datetime"], errors="coerce")
        bars_frame = bars_frame.dropna(subset=["bar_datetime"])
        bars_frame = bars_frame.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(
            ["vt_symbol", "bar_datetime"]
        )
    return status_frame, bars_frame


def _coverage_after_stage859(
    gaps: pd.DataFrame,
    local_scan: pd.DataFrame,
    akshare_probe: pd.DataFrame,
    tqsdk_status: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    local_keys: set[tuple[str, str]] = set()
    if not local_scan.empty:
        local_good = local_scan[local_scan["minute_like"].fillna(0).astype(int).eq(1)]
        local_keys = set(zip(local_good["vt_symbol"].astype(str), local_good["target_date"].astype(str)))
    akshare_keys: set[tuple[str, str]] = set()
    if not akshare_probe.empty:
        ak_good = akshare_probe[akshare_probe["covers_target_date"].fillna(0).astype(int).eq(1)]
        akshare_keys = set(zip(ak_good["vt_symbol"].astype(str), ak_good["required_date"].astype(str)))
    tqsdk_keys: set[tuple[str, str]] = set()
    if not tqsdk_status.empty:
        tq_good = tqsdk_status[tqsdk_status["target_date_rows"].fillna(0).astype(float).ge(MINUTE_BAR_MIN_COUNT)]
        tqsdk_keys = set(zip(tq_good["vt_symbol"].astype(str), tq_good["required_date"].astype(str)))
    for row in gaps.itertuples(index=False):
        key = (str(row.vt_symbol), str(row.required_date_text))
        source = ""
        covered = 0
        if key in tqsdk_keys:
            source = "tqsdk_stage859_backtest"
            covered = 1
        elif key in local_keys:
            source = "existing_local_minute_cache"
            covered = 1
        elif key in akshare_keys:
            source = "akshare_sina_probe"
            covered = 1
        rows.append(
            {
                **row._asdict(),
                "stage859_covered": covered,
                "stage859_cover_source": source,
            }
        )
    return pd.DataFrame(rows)


def _summary(
    gaps: pd.DataFrame,
    plan: pd.DataFrame,
    local_scan: pd.DataFrame,
    akshare_probe: pd.DataFrame,
    tqsdk_status: pd.DataFrame,
    coverage: pd.DataFrame,
    minute_bars: pd.DataFrame,
) -> dict[str, Any]:
    covered = coverage[coverage["stage859_covered"].fillna(0).astype(int).eq(1)]
    tqsdk_ok = (
        tqsdk_status[tqsdk_status["target_date_rows"].fillna(0).astype(float).ge(MINUTE_BAR_MIN_COUNT)]
        if not tqsdk_status.empty
        else pd.DataFrame()
    )
    local_ok = (
        local_scan[local_scan["minute_like"].fillna(0).astype(int).eq(1)]
        if not local_scan.empty
        else pd.DataFrame()
    )
    ak_ok = (
        akshare_probe[akshare_probe["covers_target_date"].fillna(0).astype(int).eq(1)]
        if not akshare_probe.empty
        else pd.DataFrame()
    )
    entry_covered = covered[covered["request_type"].astype(str).eq("stage825_entry_day")]
    pressure_covered = covered[covered["request_type"].astype(str).eq("stage849_pressure_key_date")]
    selected_batches = len(plan) if MAX_BATCHES <= 0 else min(MAX_BATCHES, len(plan))
    if len(covered) == len(gaps) and len(gaps) > 0:
        decision = "stage859_tqsdk_backtest_gap_backfill_full_success_no_rule"
    elif len(covered):
        decision = "stage859_tqsdk_backtest_gap_backfill_partial_success_no_rule"
    else:
        decision = "stage859_alt_source_probe_no_new_coverage_no_rule"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "remaining_gap_requests_input": int(len(gaps)),
        "remaining_gap_batches_input": int(len(plan)),
        "selected_tqsdk_batches": int(selected_batches if ENABLE_TQSDK_BACKTEST else 0),
        "tqsdk_success_batches": int(len(tqsdk_ok)),
        "tqsdk_failed_batches": int(
            len(tqsdk_status)
            - int(tqsdk_status["target_date_rows"].fillna(0).astype(float).ge(MINUTE_BAR_MIN_COUNT).sum())
        )
        if not tqsdk_status.empty
        else 0,
        "existing_local_cache_coverable_requests": int(local_ok["covered_requests"].sum())
        if not local_ok.empty and "covered_requests" in local_ok
        else 0,
        "akshare_probe_coverable_symbols": int(len(ak_ok)),
        "stage859_covered_requests": int(len(covered)),
        "stage859_covered_entry_day_requests": int(len(entry_covered)),
        "stage859_covered_pressure_key_date_requests": int(len(pressure_covered)),
        "stage859_covered_priority_abs_pnl": float(pd.to_numeric(covered["priority_abs_pnl"], errors="coerce").sum())
        if not covered.empty
        else 0.0,
        "stage859_covered_big_winner_requests": int(
            pd.to_numeric(covered["big_winner"], errors="coerce").fillna(0).astype(float).gt(0).sum()
        )
        if not covered.empty
        else 0,
        "stage859_minute_bars": int(len(minute_bars)),
        "stage859_unique_symbols": int(minute_bars["vt_symbol"].astype(str).nunique()) if not minute_bars.empty else 0,
        "remaining_uncovered_requests_after_stage859": int(len(gaps) - len(covered)),
        "decision": decision,
    }


def _write_report(
    summary: dict[str, Any],
    source_readiness: pd.DataFrame,
    plan: pd.DataFrame,
    local_scan: pd.DataFrame,
    akshare_probe: pd.DataFrame,
    tqsdk_status: pd.DataFrame,
    coverage: pd.DataFrame,
) -> None:
    covered = coverage[coverage["stage859_covered"].fillna(0).astype(int).eq(1)].copy()
    covered_view = covered[
        [
            "request_type",
            "source_id",
            "vt_symbol",
            "required_date_text",
            "stage859_cover_source",
            "priority_abs_pnl",
            "realized_pnl",
            "big_winner",
        ]
    ].sort_values("priority_abs_pnl", ascending=False)
    lines = [
        f"# {STAGE} Stage856剩余缺口替代源与TqBacktest补抽",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk 官方文档显示 `get_kline_serial(..., duration_seconds=60)` 可取 1 分钟K，`TqBacktest` 可在历史回放中推进 K 线；这与前面 `DataDownloader` 专业版下载权限阻断是两条不同路径。",
        "- AKShare `futures_zh_minute_sina(symbol, period='1')` 可取新浪期货分钟线，但实测多为合约后段约 1023 根，对 Stage856 的早期入场日缺口覆盖有限。",
        "- RQData/rqdatac 已安装但本机未发现环境变量凭证；Tushare token 存在，但当前优先级低于已验证可用的 TqBacktest 价格路径。",
        "",
        "## 结果摘要",
        "",
        _md_table(pd.DataFrame([summary])),
        "",
        "## 数据源可用性",
        "",
        _md_table(source_readiness, max_rows=20),
        "",
        "## TqBacktest抽取状态",
        "",
        _md_table(tqsdk_status, max_rows=40),
        "",
        "## 已覆盖请求",
        "",
        _md_table(covered_view, max_rows=40),
        "",
        "## 本地缓存扫描",
        "",
        _md_table(local_scan, max_rows=30),
        "",
        "## AKShare/Sina探测",
        "",
        _md_table(akshare_probe, max_rows=30),
        "",
        "## 后续判断",
        "",
        "- 本阶段只补数据证据，不写交易规则、不接真实引擎、不触发A/B。",
        "- TqBacktest 已完成 Stage856 全部剩余 batches 的补抽；下一阶段应把 Stage859 raw 统一导入成 Stage860 覆盖重算与视觉图谱。",
        "- 在 Stage860 真正重算覆盖前，不得把本阶段的补抽结果直接用于规则结论。",
        "",
        "## 输出文件",
        "",
        f"- batch_plan：`{BATCH_PLAN_PATH.name}`",
        f"- source_readiness：`{SOURCE_READINESS_PATH.name}`",
        f"- local_cache_scan：`{LOCAL_CACHE_SCAN_PATH.name}`",
        f"- akshare_probe：`{AKSHARE_PROBE_PATH.name}`",
        f"- tqsdk_extract_status：`{EXTRACT_STATUS_PATH.name}`",
        f"- minute_bars：`{MINUTE_BARS_PATH.name}`",
        f"- request_coverage：`{REQUEST_COVERAGE_PATH.name}`",
        f"- decision：`{DECISION_PATH.name}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    gaps = _load_gaps()
    plan = _build_batch_plan(gaps)
    source_readiness = _source_readiness()
    local_scan = _local_cache_scan(gaps, plan)
    akshare_probe = _run_akshare_probe(gaps, plan)
    tqsdk_status, minute_bars = _run_tqsdk_extract(plan)
    coverage = _coverage_after_stage859(gaps, local_scan, akshare_probe, tqsdk_status)
    summary = _summary(gaps, plan, local_scan, akshare_probe, tqsdk_status, coverage, minute_bars)

    plan.to_csv(BATCH_PLAN_PATH, index=False, encoding="utf-8-sig")
    source_readiness.to_csv(SOURCE_READINESS_PATH, index=False, encoding="utf-8-sig")
    local_scan.to_csv(LOCAL_CACHE_SCAN_PATH, index=False, encoding="utf-8-sig")
    akshare_probe.to_csv(AKSHARE_PROBE_PATH, index=False, encoding="utf-8-sig")
    tqsdk_status.to_csv(EXTRACT_STATUS_PATH, index=False, encoding="utf-8-sig")
    minute_bars.to_csv(MINUTE_BARS_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(REQUEST_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": summary["decision"],
        "metrics": summary,
        "outputs": {
            "batch_plan": str(BATCH_PLAN_PATH),
            "source_readiness": str(SOURCE_READINESS_PATH),
            "local_cache_scan": str(LOCAL_CACHE_SCAN_PATH),
            "akshare_probe": str(AKSHARE_PROBE_PATH),
            "tqsdk_extract_status": str(EXTRACT_STATUS_PATH),
            "minute_bars": str(MINUTE_BARS_PATH),
            "request_coverage": str(REQUEST_COVERAGE_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "raw_root": str(RAW_ROOT),
        },
        "allow_new_rule": False,
        "allow_engine": False,
        "allow_ab": False,
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, source_readiness, plan, local_scan, akshare_probe, tqsdk_status, coverage)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
