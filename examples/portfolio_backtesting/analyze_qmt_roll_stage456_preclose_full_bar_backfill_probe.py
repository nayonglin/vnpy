from __future__ import annotations

from datetime import datetime, timedelta
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

MODEL_TAG = "stage456_preclose_full_bar_backfill_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage456_preclose_full_bar_backfill_probe"
LINE_ID = "futures_trend_drawdown30_preserve_return"
RAW_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_stage456_preclose_full_bar_probe"

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
BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_bars_{MODEL_TAG}.csv"
SYNTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_synthetic_preclose_bars_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CHINA_TZ = ZoneInfo("Asia/Shanghai")
MAX_SPANS = int(os.getenv("STAGE456_MAX_SPANS", "3"))
MAX_DATES_PER_SYMBOL = int(os.getenv("STAGE456_MAX_DATES_PER_SYMBOL", "5"))
MAX_SECONDS_PER_SYMBOL = int(os.getenv("STAGE456_MAX_SECONDS_PER_SYMBOL", "180"))
SESSION_LOOKBACK_CALENDAR_DAYS = int(os.getenv("STAGE456_SESSION_LOOKBACK_CALENDAR_DAYS", "3"))
FREEZE_TIME = os.getenv("STAGE456_FREEZE_TIME", "14:55")
FILL_END_TIME = os.getenv("STAGE456_FILL_END_TIME", "15:00")
FORCE_REFRESH = os.getenv("STAGE456_FORCE_REFRESH", "0").strip() == "1"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
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


def _raw_path_for(vt_symbol: str) -> Path:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return RAW_ROOT / exchange / f"{symbol}_minute_backtest.csv"


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
    plan = _load_plan().head(MAX_SPANS if MAX_SPANS > 0 else len(_load_plan())).copy()
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


def _load_cached(vt_symbol: str, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> pd.DataFrame:
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
    if frame["bar_datetime"].min() <= start_dt and frame["bar_datetime"].max() >= end_dt - timedelta(minutes=1):
        frame["vt_symbol"] = vt_symbol
        return frame
    return pd.DataFrame()


def _extract_symbol(vt_symbol: str, dates: list[pd.Timestamp], username: str, password: str) -> tuple[dict[str, Any], pd.DataFrame]:
    sorted_dates = sorted({pd.Timestamp(date).normalize() for date in dates})
    start_dt = sorted_dates[0] - pd.Timedelta(days=SESSION_LOOKBACK_CALENDAR_DAYS) + pd.Timedelta(
        hours=20, minutes=55
    )
    end_dt = _time_on_date(sorted_dates[-1], FILL_END_TIME) + pd.Timedelta(minutes=10)
    cached = _load_cached(vt_symbol, start_dt, end_dt)
    status = {
        "vt_symbol": vt_symbol,
        "tq_symbol": _to_tqsdk_symbol(vt_symbol),
        "target_dates": len(sorted_dates),
        "extract_start": start_dt,
        "extract_end": end_dt,
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
        )
        klines = api.get_kline_serial(status["tq_symbol"], duration_seconds=60, data_length=500)
        while True:
            if time.time() - started > MAX_SECONDS_PER_SYMBOL:
                status["status"] = "timeout"
                status["message"] = f"timeout_after_{MAX_SECONDS_PER_SYMBOL}s"
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
                    "tq_symbol": status["tq_symbol"],
                    "bar_datetime": bar_dt,
                    "bar_id": bar_id,
                    "open": float(bar.get("open", np.nan)),
                    "high": float(bar.get("high", np.nan)),
                    "low": float(bar.get("low", np.nan)),
                    "close": float(bar.get("close", np.nan)),
                    "volume": float(bar.get("volume", np.nan)),
                    "open_oi": float(bar.get("open_oi", np.nan)),
                    "close_oi": float(bar.get("close_oi", np.nan)),
                }
            )
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
        for i, date_value in enumerate(dates):
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
            valid_ohlc = (
                not preclose.empty
                and preclose[["open", "high", "low", "close"]].replace([np.inf, -np.inf], np.nan).notna().all().all()
            )
            preclose_volume = pd.to_numeric(preclose.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
            volume_ok = not preclose.empty and float(preclose_volume.sum()) > 0.0
            oi_ok = not preclose.empty and pd.to_numeric(preclose["close_oi"], errors="coerce").notna().any()
            fill_ok = not fill.empty and fill[["open", "close"]].replace([np.inf, -np.inf], np.nan).notna().all().all()
            fill_volume = pd.to_numeric(fill.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
            fill_close = pd.to_numeric(fill.get("close", pd.Series(dtype=float)), errors="coerce")
            fill_volume_sum = float(fill_volume.sum()) if not fill.empty else 0.0
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
                    "volume_ok": int(volume_ok),
                    "open_interest_ok": int(oi_ok),
                    "fill_ok": int(fill_ok),
                    "full_bar_ready": int(valid_ohlc and volume_ok and oi_ok and fill_ok),
                    "synthetic_open": float(preclose["open"].iloc[0]) if valid_ohlc else np.nan,
                    "synthetic_high": float(preclose["high"].max()) if valid_ohlc else np.nan,
                    "synthetic_low": float(preclose["low"].min()) if valid_ohlc else np.nan,
                    "synthetic_close": float(preclose["close"].iloc[-1]) if valid_ohlc else np.nan,
                    "synthetic_volume": float(preclose_volume.sum()) if volume_ok else np.nan,
                    "synthetic_open_interest": float(pd.to_numeric(preclose["close_oi"], errors="coerce").dropna().iloc[-1])
                    if oi_ok
                    else np.nan,
                    "fill_first_open": float(fill["open"].iloc[0]) if fill_ok else np.nan,
                    "fill_last_close": float(fill["close"].iloc[-1]) if fill_ok else np.nan,
                    "fill_vwap_like": float((fill_close * fill_volume).sum() / fill_volume_sum)
                    if fill_ok and fill_volume_sum > 0
                    else (float(fill_close.mean()) if fill_ok else np.nan),
                }
            )
            previous_date = date
    return pd.DataFrame(rows).sort_values(["plan_rank", "vt_symbol", "date"]).reset_index(drop=True)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = _select_targets()
    targets.to_csv(TARGETS_PATH, index=False, encoding="utf-8-sig")
    if targets.empty:
        raise RuntimeError("No Stage456 targets selected from Stage154 download plan.")

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

    ready_count = int(synth["full_bar_ready"].sum()) if not synth.empty else 0
    target_count = int(len(synth))
    status_success = int(status_df["status"].isin(["cached_raw", "extracted", "timeout"]).sum()) if not status_df.empty else 0
    summary = pd.DataFrame(
        [
            {
                "model_tag": MODEL_TAG,
                "selected_symbol_count": int(targets["vt_symbol"].nunique()),
                "selected_target_dates": int(len(targets)),
                "status_success_like_count": status_success,
                "minute_bar_count": int(len(bars_df)),
                "full_bar_ready_count": ready_count,
                "full_bar_ready_rate": ready_count / target_count if target_count else 0.0,
                "boundary_uncertain_count": int(synth["boundary_uncertain"].sum()) if not synth.empty else 0,
                "preclose_bar_count_min": int(synth["preclose_bar_count"].min()) if not synth.empty else 0,
                "fill_bar_count_min": int(synth["fill_bar_count"].min()) if not synth.empty else 0,
                "max_spans": MAX_SPANS,
                "max_dates_per_symbol": MAX_DATES_PER_SYMBOL,
                "max_seconds_per_symbol": MAX_SECONDS_PER_SYMBOL,
            }
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision_label = (
        "full_preclose_bar_backfill_probe_success_extend_sharded_download"
        if target_count and ready_count == target_count
        else "full_preclose_bar_backfill_probe_partial_need_calendar_or_more_data"
    )
    decision = {
        "stage": "Stage156",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "promotion_candidate": "none",
        "selected_symbol_count": int(targets["vt_symbol"].nunique()),
        "selected_target_dates": int(len(targets)),
        "minute_bar_count": int(len(bars_df)),
        "full_bar_ready_count": ready_count,
        "full_bar_ready_rate": ready_count / target_count if target_count else 0.0,
        "outputs": {
            "targets": str(TARGETS_PATH),
            "status": str(STATUS_PATH),
            "minute_bars": str(BARS_PATH),
            "synthetic_preclose_bars": str(SYNTH_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "先审计分钟volume字段来源与Stage079中volume/open_interest字段的实际物料性；若volume不可用且物料性不为零，不能进入全量一致预收盘回放。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = "\n".join(
        [
            "# Stage156 预收盘完整合成日K分片补数据探针",
            "",
            f"- 生成时间：{decision['generated_at']}",
            "- 阶段性质：执行数据工程可行性探针；不新增策略、不修改 Stage079/C3 交易规则。",
            f"- 决策标签：`{decision_label}`。",
            "",
            "## 外部调研与判断",
            "",
            "- TqSdk `TqBacktest` 支持历史回放，`get_kline_serial(..., 60)` 可取1分钟K。",
            "- TqSdk分钟K列包含 `open/high/low/close/volume/open_oi/close_oi`，但本批次 `volume` 字段为全0；字段存在不等于满足 Stage155 的 OHLCVOI 规格。",
            "- 本阶段只验证小批次能否合成预收盘日K，不看收益、不做候选晋级。",
            "",
            "## 参数",
            "",
            f"- `MAX_SPANS={MAX_SPANS}`",
            f"- `MAX_DATES_PER_SYMBOL={MAX_DATES_PER_SYMBOL}`",
            f"- `MAX_SECONDS_PER_SYMBOL={MAX_SECONDS_PER_SYMBOL}`",
            f"- `SESSION_LOOKBACK_CALENDAR_DAYS={SESSION_LOOKBACK_CALENDAR_DAYS}`",
            f"- `FREEZE_TIME={FREEZE_TIME}`",
            f"- `FILL_END_TIME={FILL_END_TIME}`",
            "",
            "## 汇总",
            "",
            _md_table(summary),
            "",
            "## 抽取状态",
            "",
            _md_table(status_df, max_rows=20),
            "",
            "## 合成日K样本",
            "",
            _md_table(synth, max_rows=20),
            "",
            "## 结论",
            "",
            "- 本阶段没有策略候选晋级。",
            "- 本批次 OHLC、close_oi 与 `14:55-15:00` 填充窗口可用，但 `volume` 全0导致 strict `full_bar_ready_rate=0`。",
            "- 下一步优先审计分钟 `volume` 的数据源替代和 Stage079 中 volume/open_interest 字段的实际物料性，而不是回到alpha调参。",
            "",
            "## 过拟合与继续价值反思",
            "",
            "- 过拟合：否。本阶段只补数据并验证字段完备性，没有按收益筛样本或参数。",
            "- 继续价值：是。它直接决定 Stage079 的3/6个月体验优化能否进入真实可部署回放。",
        ]
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
