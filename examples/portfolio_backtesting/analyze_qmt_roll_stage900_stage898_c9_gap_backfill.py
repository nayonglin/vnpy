from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import math
import os
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
DATA_ROOT = PROJECT_DIR / "downloaded_futures"
RAW_ROOT = DATA_ROOT / "tqsdk_stage900_stage898_c9_gap_backfill"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage900"
MODEL_TAG = "stage900_stage898_c9_gap_backfill_v1"
OUTPUT_PREFIX = "qmt_roll_stage900_stage898_c9_gap_backfill"

STAGE898_PREFIX = "qmt_roll_stage898_c9_backtest_integrity_audit"
STAGE898_TAG = "stage898_c9_backtest_integrity_audit_v1"
STAGE898_COVERAGE_GAPS_PATH = OUTPUT_DIR / f"{STAGE898_PREFIX}_coverage_gaps_{STAGE898_TAG}.csv"

BATCH_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_batch_plan_{MODEL_TAG}.csv"
LOCAL_CACHE_SCAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_cache_scan_{MODEL_TAG}.csv"
EXTRACT_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tqsdk_extract_status_{MODEL_TAG}.csv"
MINUTE_BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_bars_{MODEL_TAG}.csv"
COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

MINUTE_BAR_MIN_COUNT = int(os.getenv("STAGE900_MINUTE_BAR_MIN_COUNT", "10"))
MAX_SECONDS_PER_BATCH = int(os.getenv("STAGE900_MAX_SECONDS_PER_BATCH", "90"))
ENABLE_TQSDK_BACKTEST = os.getenv("STAGE900_ENABLE_TQSDK_BACKTEST", "1").strip() != "0"
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


def _detect_datetime_column(columns: list[str]) -> str | None:
    for column in ["bar_datetime", "datetime", "time", "date", "trade_time"]:
        if column in columns:
            return column
    return None


def _normalize_bar_frame(frame: pd.DataFrame, vt_symbol: str, required_date: str, source: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    data = frame.copy()
    dt_col = _detect_datetime_column(list(data.columns))
    if dt_col is None:
        return pd.DataFrame()
    data["bar_datetime"] = pd.to_datetime(data[dt_col], errors="coerce")
    data = data.dropna(subset=["bar_datetime"])
    data["bar_date"] = data["bar_datetime"].dt.strftime("%Y-%m-%d")
    data = data[data["bar_date"].eq(required_date)].copy()
    if len(data) < MINUTE_BAR_MIN_COUNT:
        return pd.DataFrame()
    data["vt_symbol"] = vt_symbol
    data["tq_symbol"] = _to_tq_symbol(vt_symbol)
    data["required_date"] = required_date
    data["minute_source"] = source
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi", "bar_id"]:
        if column not in data.columns:
            data[column] = np.nan
        data[column] = pd.to_numeric(data[column], errors="coerce")
    columns = [
        "vt_symbol",
        "tq_symbol",
        "bar_datetime",
        "bar_id",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_oi",
        "close_oi",
        "required_date",
        "minute_source",
        "bar_date",
    ]
    return data[columns].drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values("bar_datetime")


def _load_gaps() -> pd.DataFrame:
    gaps = _load_csv(STAGE898_COVERAGE_GAPS_PATH).copy()
    gaps["entry_date_text"] = gaps["entry_date"].map(_date_text)
    gaps["vt_symbol"] = gaps["vt_symbol"].astype(str)
    gaps["profile"] = gaps["profile"].astype(str)
    return gaps


def _build_batch_plan(gaps: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (vt_symbol, required_date), group in gaps.groupby(["vt_symbol", "entry_date_text"], sort=False):
        rows.append(
            {
                "vt_symbol": vt_symbol,
                "tq_symbol": _to_tq_symbol(vt_symbol),
                "required_date": required_date,
                "profile_count": int(group["profile"].nunique()),
                "gap_rows": int(len(group)),
                "directions": ",".join(sorted(set(group["direction"].astype(str)))),
                "open_volume_sum": float(pd.to_numeric(group["volume"], errors="coerce").fillna(0).sum()),
                "profiles": ",".join(sorted(set(group["profile"].astype(str)))),
                "raw_path": str(_raw_path_for(vt_symbol, required_date)),
            }
        )
    plan = pd.DataFrame(rows).sort_values(["required_date", "vt_symbol"]).reset_index(drop=True)
    plan["batch_rank"] = np.arange(1, len(plan) + 1)
    return plan


def _candidate_cache_files(vt_symbol: str) -> list[Path]:
    symbol, exchange = _split_vt(vt_symbol)
    results: list[Path] = []
    for path in DATA_ROOT.rglob("*.csv"):
        lower_path = str(path).lower()
        if "daily" in lower_path:
            continue
        if symbol.lower() not in path.name.lower():
            continue
        try:
            head = pd.read_csv(path, encoding="utf-8-sig", nrows=5)
        except Exception:
            continue
        if "vt_symbol" in head.columns:
            symbols = set(head["vt_symbol"].dropna().astype(str).head(20))
            if symbols and vt_symbol not in symbols:
                continue
        elif path.parent.name.upper() != exchange.upper():
            continue
        results.append(path)
    return results


def _local_cache_scan_and_bars(plan: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    bar_frames: list[pd.DataFrame] = []
    covered_keys: set[tuple[str, str]] = set()
    for row in plan.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        required_date = str(row.required_date)
        best_bars = pd.DataFrame()
        best_file = ""
        for path in _candidate_cache_files(vt_symbol):
            try:
                raw = pd.read_csv(path, encoding="utf-8-sig")
            except Exception as exc:
                rows.append(
                    {
                        "vt_symbol": vt_symbol,
                        "required_date": required_date,
                        "file": str(path),
                        "status": "read_failed",
                        "target_date_bars": 0,
                        "message": repr(exc)[:300],
                    }
                )
                continue
            bars = _normalize_bar_frame(raw, vt_symbol, required_date, "stage900_existing_local_minute_cache")
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "required_date": required_date,
                    "file": str(path),
                    "status": "date_seen" if not bars.empty else "target_not_covered",
                    "target_date_bars": int(len(bars)),
                    "message": "",
                }
            )
            if len(bars) > len(best_bars):
                best_bars = bars
                best_file = str(path)
        if not best_bars.empty:
            best_bars["local_source_file"] = best_file
            bar_frames.append(best_bars)
            covered_keys.add((vt_symbol, required_date))
    local_scan = pd.DataFrame(rows)
    bars_frame = pd.concat(bar_frames, ignore_index=True, sort=False) if bar_frames else pd.DataFrame()
    if not bars_frame.empty:
        bars_frame = bars_frame.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(
            ["vt_symbol", "bar_datetime"]
        )
    if not local_scan.empty:
        local_scan["local_cache_selected"] = [
            int((str(row.vt_symbol), str(row.required_date)) in covered_keys)
            for row in local_scan.itertuples(index=False)
        ]
    return local_scan, bars_frame


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
    return _normalize_bar_frame(data, vt_symbol, required_date, "stage900_tqsdk_backtest")


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
        "raw_path": str(raw_path),
        "status": "unknown",
        "rows": 0,
        "target_date_rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }
    cached = _load_raw_if_covered(raw_path, vt_symbol, required_date)
    if not cached.empty:
        status["status"] = "cached_stage900_raw"
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
                    "minute_source": "stage900_tqsdk_backtest",
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
        bars["bar_date"] = bars["bar_datetime"].dt.strftime("%Y-%m-%d")
        bars = bars.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
        bars.to_csv(raw_path, index=False, encoding="utf-8-sig")
    if status["status"] == "unknown":
        status["status"] = "extracted" if not bars.empty else "empty"
    status["rows"] = int(len(bars))
    status["target_date_rows"] = int(bars["bar_date"].eq(required_date).sum()) if "bar_date" in bars else 0
    status["elapsed_seconds"] = round(time.time() - started, 2)
    return status, bars


def _run_tqsdk_extract(plan: pd.DataFrame, local_bars: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    local_keys = set()
    if not local_bars.empty:
        local_keys = set(zip(local_bars["vt_symbol"].astype(str), local_bars["required_date"].astype(str)))
    remaining = [
        row
        for row in plan.itertuples(index=False)
        if (str(row.vt_symbol), str(row.required_date)) not in local_keys
    ]
    try:
        from vnpy.trader.setting import SETTINGS

        username = str(SETTINGS.get("datafeed.username", ""))
        password = str(SETTINGS.get("datafeed.password", ""))
    except Exception:
        username = ""
        password = ""
    status_rows: list[dict[str, Any]] = []
    bar_frames: list[pd.DataFrame] = []
    for row in remaining:
        if not username or not password:
            status_rows.append(
                {
                    "batch_rank": int(row.batch_rank),
                    "vt_symbol": str(row.vt_symbol),
                    "tq_symbol": str(row.tq_symbol),
                    "required_date": str(row.required_date),
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
        bars = _normalize_bar_frame(bars, str(row.vt_symbol), str(row.required_date), "stage900_tqsdk_backtest")
        if not bars.empty:
            bar_frames.append(bars)
    status_frame = pd.DataFrame(status_rows)
    bars_frame = pd.concat(bar_frames, ignore_index=True, sort=False) if bar_frames else pd.DataFrame()
    if not bars_frame.empty:
        bars_frame = bars_frame.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(
            ["vt_symbol", "bar_datetime"]
        )
    return status_frame, bars_frame


def _coverage(plan: pd.DataFrame, local_bars: pd.DataFrame, tqsdk_bars: pd.DataFrame) -> pd.DataFrame:
    frames = []
    if not local_bars.empty:
        frames.append(local_bars.assign(cover_source="existing_local_minute_cache"))
    if not tqsdk_bars.empty:
        frames.append(tqsdk_bars.assign(cover_source="stage900_tqsdk_backtest"))
    merged = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for row in plan.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        required_date = str(row.required_date)
        if merged.empty:
            subset = pd.DataFrame()
        else:
            subset = merged[
                merged["vt_symbol"].astype(str).eq(vt_symbol)
                & merged["required_date"].astype(str).eq(required_date)
            ]
        rows.append(
            {
                **row._asdict(),
                "covered": int(len(subset) >= MINUTE_BAR_MIN_COUNT),
                "target_date_rows": int(len(subset)),
                "cover_source": ",".join(sorted(set(subset["cover_source"].astype(str)))) if not subset.empty else "",
            }
        )
    return pd.DataFrame(rows)


def _summary(gaps: pd.DataFrame, plan: pd.DataFrame, local_bars: pd.DataFrame, tqsdk_bars: pd.DataFrame, coverage: pd.DataFrame) -> dict[str, Any]:
    covered = coverage[coverage["covered"].astype(int).eq(1)] if not coverage.empty else pd.DataFrame()
    decision = "stage900_c9_gap_backfill_complete_no_rule" if len(covered) == len(plan) and len(plan) else "stage900_c9_gap_backfill_incomplete_no_rule"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "gap_rows_input": int(len(gaps)),
        "unique_symbol_dates": int(len(plan)),
        "covered_symbol_dates": int(len(covered)),
        "remaining_symbol_dates": int(len(plan) - len(covered)),
        "local_cache_symbol_dates": int(coverage["cover_source"].astype(str).str.contains("existing_local").sum()) if not coverage.empty else 0,
        "tqsdk_symbol_dates": int(coverage["cover_source"].astype(str).str.contains("stage900_tqsdk").sum()) if not coverage.empty else 0,
        "minute_bars": int(len(local_bars) + len(tqsdk_bars)),
        "unique_symbols": int(pd.concat([local_bars, tqsdk_bars], ignore_index=True, sort=False)["vt_symbol"].nunique())
        if len(local_bars) + len(tqsdk_bars)
        else 0,
        "decision": decision,
    }


def _write_report(summary: dict[str, Any], plan: pd.DataFrame, coverage: pd.DataFrame, tqsdk_status: pd.DataFrame) -> None:
    lines = [
        f"# {STAGE} Stage898 C9缺口分钟K补齐",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk 官方文档显示 `DataDownloader` 属于专业版历史下载工具；本仓库此前 Stage859 已验证可用的替代路径是 `TqBacktest + get_kline_serial(60)`。",
        "- 本阶段只补 Stage898 指出的 C9 entry-day 缺口，不改交易规则、不调参数、不触发A/B。",
        "",
        "## 结果摘要",
        "",
        _md_table(pd.DataFrame([summary])),
        "",
        "## 覆盖明细",
        "",
        _md_table(coverage, max_rows=20),
        "",
        "## TqBacktest状态",
        "",
        _md_table(tqsdk_status, max_rows=20),
        "",
        "## 输出文件",
        "",
        f"- minute_bars：`{MINUTE_BARS_PATH.name}`",
        f"- coverage：`{COVERAGE_PATH.name}`",
        f"- decision：`{DECISION_PATH.name}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gaps = _load_gaps()
    plan = _build_batch_plan(gaps)
    local_scan, local_bars = _local_cache_scan_and_bars(plan)
    tqsdk_status, tqsdk_bars = _run_tqsdk_extract(plan, local_bars)
    minute_bars = pd.concat([local_bars, tqsdk_bars], ignore_index=True, sort=False) if len(local_bars) + len(tqsdk_bars) else pd.DataFrame()
    if not minute_bars.empty:
        minute_bars = minute_bars.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
    coverage = _coverage(plan, local_bars, tqsdk_bars)
    summary = _summary(gaps, plan, local_bars, tqsdk_bars, coverage)

    plan.to_csv(BATCH_PLAN_PATH, index=False, encoding="utf-8-sig")
    local_scan.to_csv(LOCAL_CACHE_SCAN_PATH, index=False, encoding="utf-8-sig")
    tqsdk_status.to_csv(EXTRACT_STATUS_PATH, index=False, encoding="utf-8-sig")
    minute_bars.to_csv(MINUTE_BARS_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": summary["decision"],
        "metrics": summary,
        "strategy_changed": False,
        "allow_new_rule": False,
        "allow_engine_ab": False,
        "outputs": {
            "batch_plan": str(BATCH_PLAN_PATH),
            "local_cache_scan": str(LOCAL_CACHE_SCAN_PATH),
            "tqsdk_extract_status": str(EXTRACT_STATUS_PATH),
            "minute_bars": str(MINUTE_BARS_PATH),
            "coverage": str(COVERAGE_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, plan, coverage, tqsdk_status)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
