from __future__ import annotations

from datetime import datetime
import json
import logging
import math
import os
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import ZoneInfo


logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("tqsdk").setLevel(logging.WARNING)

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

STAGE_NAME = os.getenv("STAGE459_STAGE_NAME", "Stage159")
MODEL_TAG = os.getenv("STAGE459_MODEL_TAG", "stage459_completed_preclose_full_bar_shard_v1")
OUTPUT_PREFIX = os.getenv("STAGE459_OUTPUT_PREFIX", "qmt_roll_stage459_completed_preclose_full_bar_shard")
LINE_ID = "futures_trend_drawdown30_preserve_return"
RAW_ROOT = PROJECT_DIR / "downloaded_futures" / os.getenv(
    "STAGE459_RAW_SUBDIR", "tqsdk_stage459_completed_preclose_full_bar_shard"
)

STAGE154_REQUIRED_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage454_preclose_signal_bar_data_readiness_required_keys_stage454_preclose_signal_bar_data_readiness_v1.csv"
)
STAGE154_DOWNLOAD_PLAN_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage454_preclose_signal_bar_data_readiness_download_plan_stage454_preclose_signal_bar_data_readiness_v1.csv"
)

TARGETS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_targets_{MODEL_TAG}.csv"
STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_extract_status_{MODEL_TAG}.csv"
BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_completed_minute_bars_{MODEL_TAG}.csv"
SYNTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_synthetic_preclose_bars_{MODEL_TAG}.csv"
SPAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_span_summary_{MODEL_TAG}.csv"
PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CHINA_TZ = ZoneInfo("Asia/Shanghai")
START_SPAN = int(os.getenv("STAGE459_START_SPAN", "1"))
MAX_SPANS = int(os.getenv("STAGE459_MAX_SPANS", "30"))
MAX_DATES_PER_SYMBOL = int(os.getenv("STAGE459_MAX_DATES_PER_SYMBOL", "5"))
MAX_SECONDS_PER_SYMBOL = int(os.getenv("STAGE459_MAX_SECONDS_PER_SYMBOL", "180"))
SESSION_LOOKBACK_CALENDAR_DAYS = int(os.getenv("STAGE459_SESSION_LOOKBACK_CALENDAR_DAYS", "3"))
FREEZE_TIME = os.getenv("STAGE459_FREEZE_TIME", "14:55")
FILL_END_TIME = os.getenv("STAGE459_FILL_END_TIME", "15:00")
FORCE_REFRESH = os.getenv("STAGE459_FORCE_REFRESH", "0").strip() == "1"
DISABLE_TQSDK_PRINT = os.getenv("STAGE459_DISABLE_TQSDK_PRINT", "1").strip() != "0"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(value_item) for value_item in value]
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
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _require_credentials() -> tuple[str, str]:
    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS.")
    return username, password


def _to_tqsdk_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def _exchange(vt_symbol: str) -> str:
    return str(vt_symbol).split(".", 1)[1]


def _raw_path_for(vt_symbol: str) -> Path:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return RAW_ROOT / exchange / f"{symbol}_completed_minute_backtest.csv"


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(CHINA_TZ).tz_localize(None)


def _time_on_date(date_value: Any, hhmm: str) -> pd.Timestamp:
    hour_text, minute_text = hhmm.split(":", 1)
    return pd.Timestamp(date_value).normalize() + pd.Timedelta(hours=int(hour_text), minutes=int(minute_text))


def _load_required_missing() -> pd.DataFrame:
    required = pd.read_csv(STAGE154_REQUIRED_PATH, encoding="utf-8-sig")
    required["date"] = pd.to_datetime(required["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    required["has_preclose_1455_1500"] = pd.to_numeric(
        required["has_preclose_1455_1500"], errors="coerce"
    ).fillna(0).astype(int)
    return required[required["has_preclose_1455_1500"].eq(0)].dropna(subset=["date", "vt_symbol"]).copy()


def _load_plan() -> pd.DataFrame:
    plan = pd.read_csv(STAGE154_DOWNLOAD_PLAN_PATH, encoding="utf-8-sig")
    plan["span_start"] = pd.to_datetime(plan["span_start"], errors="coerce").dt.tz_localize(None).dt.normalize()
    plan["span_end"] = pd.to_datetime(plan["span_end"], errors="coerce").dt.tz_localize(None).dt.normalize()
    plan["plan_rank"] = np.arange(1, len(plan) + 1)
    return plan.dropna(subset=["vt_symbol", "span_start", "span_end"]).copy()


def _select_targets() -> pd.DataFrame:
    missing = _load_required_missing()
    plan_all = _load_plan()
    if START_SPAN < 1:
        raise ValueError("STAGE459_START_SPAN must be >= 1.")
    plan = plan_all[plan_all["plan_rank"].ge(START_SPAN)].copy()
    if MAX_SPANS > 0:
        plan = plan.head(MAX_SPANS)
    rows: list[dict[str, Any]] = []
    for plan_row in plan.itertuples(index=False):
        vt_symbol = str(plan_row.vt_symbol)
        dates = missing[
            missing["vt_symbol"].astype(str).eq(vt_symbol)
            & (missing["date"] >= pd.Timestamp(plan_row.span_start))
            & (missing["date"] <= pd.Timestamp(plan_row.span_end))
        ].sort_values("date")
        if MAX_DATES_PER_SYMBOL > 0:
            dates = dates.head(MAX_DATES_PER_SYMBOL)
        for date_row in dates.itertuples(index=False):
            rows.append(
                {
                    "plan_rank": int(plan_row.plan_rank),
                    "vt_symbol": vt_symbol,
                    "exchange": _exchange(vt_symbol),
                    "product_vt_symbol": str(plan_row.product_vt_symbol),
                    "date": pd.Timestamp(date_row.date).normalize(),
                    "span_start": pd.Timestamp(plan_row.span_start).normalize(),
                    "span_end": pd.Timestamp(plan_row.span_end).normalize(),
                    "missing_dates_in_span": int(plan_row.missing_dates),
                    "span_calendar_days": int(plan_row.span_calendar_days),
                }
            )
    targets = pd.DataFrame(rows)
    if targets.empty:
        return targets
    return targets.sort_values(["plan_rank", "vt_symbol", "date"]).reset_index(drop=True)


def _bar_record(vt_symbol: str, tq_symbol: str, row: pd.Series) -> dict[str, Any] | None:
    bar = row.to_dict()
    bar_dt = _normalize_tqsdk_datetime(bar.get("datetime"))
    if pd.isna(bar_dt):
        return None
    return {
        "vt_symbol": vt_symbol,
        "tq_symbol": tq_symbol,
        "bar_datetime": bar_dt,
        "bar_id": int(bar.get("id", -1)),
        "open": float(bar.get("open", np.nan)),
        "high": float(bar.get("high", np.nan)),
        "low": float(bar.get("low", np.nan)),
        "close": float(bar.get("close", np.nan)),
        "volume": float(bar.get("volume", np.nan)),
        "open_oi": float(bar.get("open_oi", np.nan)),
        "close_oi": float(bar.get("close_oi", np.nan)),
    }


def _load_cached(vt_symbol: str, start_dt: pd.Timestamp, required_end_dt: pd.Timestamp) -> pd.DataFrame:
    path = _raw_path_for(vt_symbol)
    if FORCE_REFRESH or not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty:
        return frame
    frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce").dt.tz_localize(None)
    frame = frame.dropna(subset=["bar_datetime"]).copy()
    if frame.empty:
        return frame
    if frame["bar_datetime"].min() <= start_dt and frame["bar_datetime"].max() >= required_end_dt:
        frame["vt_symbol"] = vt_symbol
        return frame
    return pd.DataFrame()


def _extract_symbol(vt_symbol: str, dates: list[pd.Timestamp], username: str, password: str) -> tuple[dict[str, Any], pd.DataFrame]:
    sorted_dates = sorted({pd.Timestamp(date).normalize() for date in dates})
    start_dt = sorted_dates[0] - pd.Timedelta(days=SESSION_LOOKBACK_CALENDAR_DAYS) + pd.Timedelta(
        hours=20, minutes=55
    )
    required_end_dt = _time_on_date(sorted_dates[-1], FILL_END_TIME) - pd.Timedelta(minutes=2)
    end_dt = _time_on_date(sorted_dates[-1], FILL_END_TIME) + pd.Timedelta(minutes=10)
    cached = _load_cached(vt_symbol, start_dt, required_end_dt)
    tq_symbol = _to_tqsdk_symbol(vt_symbol)
    status = {
        "vt_symbol": vt_symbol,
        "tq_symbol": tq_symbol,
        "target_dates": len(sorted_dates),
        "extract_start": start_dt,
        "extract_end": end_dt,
        "cache_required_end": required_end_dt,
        "status": "unknown",
        "rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
        "raw_path": str(_raw_path_for(vt_symbol)),
    }
    if not cached.empty:
        status["status"] = "cached_raw"
        status["rows"] = int(len(cached))
        return status, cached

    started = time.time()
    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    api: TqApi | None = None
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=start_dt.to_pydatetime(), end_dt=end_dt.to_pydatetime()),
            auth=TqAuth(username, password),
            disable_print=DISABLE_TQSDK_PRINT,
        )
        klines = api.get_kline_serial(tq_symbol, duration_seconds=60, data_length=500)
        while True:
            if time.time() - started > MAX_SECONDS_PER_SYMBOL:
                status["status"] = "timeout"
                status["message"] = f"timeout_after_{MAX_SECONDS_PER_SYMBOL}s"
                break
            api.wait_update()
            if not api.is_changing(klines.iloc[-1], "datetime"):
                continue
            if len(klines) < 2:
                continue
            record = _bar_record(vt_symbol, tq_symbol, klines.iloc[-2])
            if record is None:
                continue
            bar_id = int(record["bar_id"])
            if bar_id in seen_ids:
                continue
            seen_ids.add(bar_id)
            rows.append(record)
    except BacktestFinished:
        status["status"] = "extracted"
    except Exception as exc:
        status["status"] = "failed"
        status["message"] = repr(exc)
    finally:
        if api is not None:
            api.close()

    bars = pd.DataFrame(rows)
    if not bars.empty:
        bars = bars.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
        path = _raw_path_for(vt_symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        bars.to_csv(path, index=False, encoding="utf-8-sig")
    if status["status"] == "unknown":
        status["status"] = "extracted" if len(bars) else "empty"
    status["rows"] = int(len(bars))
    status["elapsed_seconds"] = round(time.time() - started, 2)
    return status, bars


def _synthesize_for_targets(targets: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame()
    bars = bars.copy()
    bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce").dt.tz_localize(None)
    bars = bars.dropna(subset=["bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
    grouped = {symbol: frame.copy() for symbol, frame in bars.groupby("vt_symbol", sort=False)}
    rows: list[dict[str, Any]] = []
    for vt_symbol, target_frame in targets.groupby("vt_symbol", sort=False):
        frame = grouped.get(str(vt_symbol), pd.DataFrame())
        dates = sorted(pd.to_datetime(target_frame["date"]).dt.normalize().unique())
        previous_date: pd.Timestamp | None = None
        for date_value in dates:
            date = pd.Timestamp(date_value).normalize()
            target = target_frame[target_frame["date"].eq(date)].iloc[0].to_dict()
            if previous_date is None:
                session_start = date - pd.Timedelta(days=SESSION_LOOKBACK_CALENDAR_DAYS) + pd.Timedelta(
                    hours=20, minutes=55
                )
                boundary_uncertain = 1
            else:
                session_start = previous_date + pd.Timedelta(hours=15)
                boundary_uncertain = 0
            freeze_dt = _time_on_date(date, FREEZE_TIME)
            fill_end_dt = _time_on_date(date, FILL_END_TIME)
            preclose = frame[(frame["bar_datetime"] >= session_start) & (frame["bar_datetime"] < freeze_dt)]
            fill = frame[(frame["bar_datetime"] >= freeze_dt) & (frame["bar_datetime"] < fill_end_dt)]

            numeric_ohlc = preclose[["open", "high", "low", "close"]].replace([np.inf, -np.inf], np.nan)
            valid_ohlc = not preclose.empty and numeric_ohlc.notna().all().all()
            preclose_volume = pd.to_numeric(preclose.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
            fill_volume = pd.to_numeric(fill.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
            preclose_close_oi = pd.to_numeric(preclose.get("close_oi", pd.Series(dtype=float)), errors="coerce")
            fill_ohlc_ok = not fill.empty and fill[["open", "close"]].replace([np.inf, -np.inf], np.nan).notna().all().all()
            volume_sum = float(preclose_volume.sum()) if not preclose.empty else 0.0
            fill_volume_sum = float(fill_volume.sum()) if not fill.empty else 0.0
            oi_ok = not preclose.empty and preclose_close_oi.notna().any()
            ready = bool(valid_ohlc and volume_sum > 0.0 and oi_ok and fill_ohlc_ok)
            rows.append(
                {
                    **target,
                    "session_start": session_start,
                    "freeze_dt": freeze_dt,
                    "fill_end_dt": fill_end_dt,
                    "boundary_uncertain": boundary_uncertain,
                    "preclose_bar_count": int(len(preclose)),
                    "fill_bar_count": int(len(fill)),
                    "valid_ohlc": int(valid_ohlc),
                    "volume_ok": int(not preclose.empty and volume_sum > 0.0),
                    "open_interest_ok": int(oi_ok),
                    "fill_ok": int(fill_ohlc_ok),
                    "full_bar_ready": int(ready),
                    "synthetic_open": float(preclose["open"].iloc[0]) if valid_ohlc else np.nan,
                    "synthetic_high": float(preclose["high"].max()) if valid_ohlc else np.nan,
                    "synthetic_low": float(preclose["low"].min()) if valid_ohlc else np.nan,
                    "synthetic_close": float(preclose["close"].iloc[-1]) if valid_ohlc else np.nan,
                    "synthetic_volume": volume_sum if volume_sum > 0.0 else np.nan,
                    "synthetic_open_interest": float(preclose_close_oi.dropna().iloc[-1]) if oi_ok else np.nan,
                    "fill_first_open": float(fill["open"].iloc[0]) if fill_ohlc_ok else np.nan,
                    "fill_last_close": float(fill["close"].iloc[-1]) if fill_ohlc_ok else np.nan,
                    "fill_volume": fill_volume_sum if fill_volume_sum > 0.0 else np.nan,
                }
            )
            previous_date = date
    return pd.DataFrame(rows).sort_values(["plan_rank", "vt_symbol", "date"]).reset_index(drop=True)


def _summarize_group(frame: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    grouped = frame.groupby(by, dropna=False)
    rows: list[dict[str, Any]] = []
    for key, group in grouped:
        key_tuple = key if isinstance(key, tuple) else (key,)
        row = {column: value for column, value in zip(by, key_tuple)}
        row.update(
            {
                "target_dates": int(len(group)),
                "ready_count": int(group["full_bar_ready"].sum()),
                "ready_rate": float(group["full_bar_ready"].mean()),
                "valid_ohlc_rate": float(group["valid_ohlc"].mean()),
                "volume_ok_rate": float(group["volume_ok"].mean()),
                "open_interest_ok_rate": float(group["open_interest_ok"].mean()),
                "fill_ok_rate": float(group["fill_ok"].mean()),
                "preclose_bar_count_min": int(group["preclose_bar_count"].min()),
                "fill_bar_count_min": int(group["fill_bar_count"].min()),
                "synthetic_volume_sum": float(pd.to_numeric(group["synthetic_volume"], errors="coerce").fillna(0).sum()),
                "fill_volume_sum": float(pd.to_numeric(group["fill_volume"], errors="coerce").fillna(0).sum()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(by).reset_index(drop=True)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = _select_targets()
    targets.to_csv(TARGETS_PATH, index=False, encoding="utf-8-sig")
    if targets.empty:
        raise RuntimeError("No Stage459 targets selected from Stage154 download plan.")

    username, password = _require_credentials()
    status_rows: list[dict[str, Any]] = []
    bar_frames: list[pd.DataFrame] = []
    for vt_symbol, frame in targets.groupby("vt_symbol", sort=False):
        status, bars = _extract_symbol(str(vt_symbol), list(pd.to_datetime(frame["date"])), username, password)
        status_rows.append(status)
        if not bars.empty:
            bar_frames.append(bars)

    status_df = pd.DataFrame(status_rows)
    status_df.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    bars_df = pd.concat(bar_frames, ignore_index=True) if bar_frames else pd.DataFrame()
    if not bars_df.empty:
        bars_df = bars_df.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
    bars_df.to_csv(BARS_PATH, index=False, encoding="utf-8-sig")

    synth = _synthesize_for_targets(targets, bars_df)
    synth.to_csv(SYNTH_PATH, index=False, encoding="utf-8-sig")
    span_summary = _summarize_group(synth, ["plan_rank", "vt_symbol", "product_vt_symbol", "exchange"])
    product_summary = _summarize_group(synth, ["product_vt_symbol", "exchange"])
    span_summary.to_csv(SPAN_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_PATH, index=False, encoding="utf-8-sig")

    target_count = int(len(synth))
    ready_count = int(synth["full_bar_ready"].sum()) if target_count else 0
    full_ready_rate = ready_count / target_count if target_count else 0.0
    status_success_like = (
        int(status_df["status"].isin(["cached_raw", "extracted", "timeout"]).sum()) if not status_df.empty else 0
    )
    failed_symbols = int(status_df["status"].eq("failed").sum()) if not status_df.empty else 0
    volume_positive_bar_count = (
        int((pd.to_numeric(bars_df["volume"], errors="coerce") > 0).sum()) if not bars_df.empty else 0
    )
    summary = pd.DataFrame(
        [
            {
                "model_tag": MODEL_TAG,
                "start_span": START_SPAN,
                "max_spans": MAX_SPANS,
                "max_dates_per_symbol": MAX_DATES_PER_SYMBOL,
                "selected_span_count": int(targets["plan_rank"].nunique()),
                "selected_symbol_count": int(targets["vt_symbol"].nunique()),
                "selected_target_dates": int(len(targets)),
                "status_success_like_count": status_success_like,
                "failed_symbol_count": failed_symbols,
                "minute_bar_count": int(len(bars_df)),
                "volume_positive_bar_count": volume_positive_bar_count,
                "full_bar_ready_count": ready_count,
                "full_bar_ready_rate": full_ready_rate,
                "boundary_uncertain_count": int(synth["boundary_uncertain"].sum()) if not synth.empty else 0,
                "preclose_bar_count_min": int(synth["preclose_bar_count"].min()) if not synth.empty else 0,
                "fill_bar_count_min": int(synth["fill_bar_count"].min()) if not synth.empty else 0,
                "synthetic_volume_sum": float(pd.to_numeric(synth["synthetic_volume"], errors="coerce").fillna(0).sum())
                if not synth.empty
                else 0.0,
                "fill_volume_sum": float(pd.to_numeric(synth["fill_volume"], errors="coerce").fillna(0).sum())
                if not synth.empty
                else 0.0,
            }
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    if target_count and ready_count == target_count and failed_symbols == 0:
        decision_label = "completed_preclose_full_bar_shard_ready_extend_next_shard"
    elif ready_count > 0:
        decision_label = "completed_preclose_full_bar_shard_partial_need_gap_attribution"
    else:
        decision_label = "completed_preclose_full_bar_shard_failed_stop_replay"
    decision = {
        "stage": STAGE_NAME,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "promotion_candidate": "none",
        "start_span": START_SPAN,
        "max_spans": MAX_SPANS,
        "selected_span_count": int(targets["plan_rank"].nunique()),
        "selected_symbol_count": int(targets["vt_symbol"].nunique()),
        "selected_target_dates": int(len(targets)),
        "minute_bar_count": int(len(bars_df)),
        "volume_positive_bar_count": volume_positive_bar_count,
        "full_bar_ready_count": ready_count,
        "full_bar_ready_rate": full_ready_rate,
        "outputs": {
            "targets": str(TARGETS_PATH),
            "status": str(STATUS_PATH),
            "completed_minute_bars": str(BARS_PATH),
            "synthetic_preclose_bars": str(SYNTH_PATH),
            "span_summary": str(SPAN_PATH),
            "product_summary": str(PRODUCT_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若本分片strict ready为100%，继续后续分片；若全量稳定，再接入一致预收盘真实回放与3/6个月体验优化。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = "\n".join(
        [
            f"# {STAGE_NAME} completed-row预收盘完整bar分片回补",
            "",
            f"- 生成时间：{decision['generated_at']}",
            "- 阶段性质：执行数据工程分片验证；不新增策略、不修改 Stage079/C3 交易规则。",
            f"- 决策标签：`{decision_label}`。",
            "",
            "## 外部调研与判断",
            "",
            "- TqSdk官方文档说明 `TqBacktest` 会推进K线与Tick；回测模式下K线在创建和结束时分别更新一次。",
            "- Stage158 已验证滚动最后一根K线成交量为0，而上一根已完成K线可恢复 `volume/open_oi/close_oi`。",
            "- xtquant/QMT 仍可作为备份分钟源，但当前首选路径是先修正 TqBacktest completed-row 语义。",
            "",
            "## 参数",
            "",
            f"- `START_SPAN={START_SPAN}`",
            f"- `MAX_SPANS={MAX_SPANS}`",
            f"- `MAX_DATES_PER_SYMBOL={MAX_DATES_PER_SYMBOL}`",
            f"- `MAX_SECONDS_PER_SYMBOL={MAX_SECONDS_PER_SYMBOL}`",
            f"- `SESSION_LOOKBACK_CALENDAR_DAYS={SESSION_LOOKBACK_CALENDAR_DAYS}`",
            f"- `FREEZE_TIME={FREEZE_TIME}`",
            f"- `FILL_END_TIME={FILL_END_TIME}`",
            f"- `FORCE_REFRESH={int(FORCE_REFRESH)}`",
            f"- `DISABLE_TQSDK_PRINT={int(DISABLE_TQSDK_PRINT)}`",
            "",
            "## 总览",
            "",
            _md_table(summary),
            "",
            "## 抽取状态",
            "",
            _md_table(status_df, max_rows=30),
            "",
            "## Span覆盖摘要",
            "",
            _md_table(span_summary, max_rows=30),
            "",
            "## 产品覆盖摘要",
            "",
            _md_table(product_summary, max_rows=30),
            "",
            "## 合成日K样本",
            "",
            _md_table(synth, max_rows=20),
            "",
            "## 结论",
            "",
            "- 本阶段没有策略候选晋级。",
            "- 本阶段只判断 completed-row OHLCVOI 分片是否足够稳定，作为后续一致预收盘真实回放的数据前置。",
            "- 若后续分片继续保持 strict ready，才恢复 Stage079/Stage103 的3个月/6个月体验优化；否则先做缺口归因。",
            "",
            "## 过拟合与继续价值反思",
            "",
            "- 过拟合：否。本阶段只修正数据抽取语义并扩大分片，不看收益、不调参数。",
            "- 继续价值：是。它直接决定短持有体验优化是否有真实部署含义。",
        ]
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
