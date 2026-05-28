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

MODEL_TAG = "stage458_completed_kline_volume_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage458_completed_kline_volume_probe"
LINE_ID = "futures_trend_drawdown30_preserve_return"

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
BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_bars_{MODEL_TAG}.csv"
SYNTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_synthetic_compare_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CHINA_TZ = ZoneInfo("Asia/Shanghai")
MAX_SPANS = int(os.getenv("STAGE458_MAX_SPANS", "2"))
MAX_DATES_PER_SYMBOL = int(os.getenv("STAGE458_MAX_DATES_PER_SYMBOL", "3"))
MAX_SECONDS_PER_SYMBOL = int(os.getenv("STAGE458_MAX_SECONDS_PER_SYMBOL", "120"))
SESSION_LOOKBACK_CALENDAR_DAYS = int(os.getenv("STAGE458_SESSION_LOOKBACK_CALENDAR_DAYS", "3"))
FREEZE_TIME = os.getenv("STAGE458_FREEZE_TIME", "14:55")
FILL_END_TIME = os.getenv("STAGE458_FILL_END_TIME", "15:00")


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
    plan = plan_all.head(MAX_SPANS if MAX_SPANS > 0 else len(plan_all)).copy()
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


def _bar_record(vt_symbol: str, tq_symbol: str, row: pd.Series, capture_mode: str) -> dict[str, Any] | None:
    bar = row.to_dict()
    bar_dt = _normalize_tqsdk_datetime(bar.get("datetime"))
    if pd.isna(bar_dt):
        return None
    return {
        "vt_symbol": vt_symbol,
        "tq_symbol": tq_symbol,
        "capture_mode": capture_mode,
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


def _extract_symbol(vt_symbol: str, dates: list[pd.Timestamp], username: str, password: str) -> tuple[dict[str, Any], pd.DataFrame]:
    sorted_dates = sorted({pd.Timestamp(date).normalize() for date in dates})
    start_dt = sorted_dates[0] - pd.Timedelta(days=SESSION_LOOKBACK_CALENDAR_DAYS) + pd.Timedelta(
        hours=20, minutes=55
    )
    end_dt = _time_on_date(sorted_dates[-1], FILL_END_TIME) + pd.Timedelta(minutes=10)
    tq_symbol = _to_tqsdk_symbol(vt_symbol)
    status = {
        "vt_symbol": vt_symbol,
        "tq_symbol": tq_symbol,
        "target_dates": len(sorted_dates),
        "extract_start": start_dt,
        "extract_end": end_dt,
        "status": "unknown",
        "rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }
    started = time.time()
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    api: TqApi | None = None
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=start_dt.to_pydatetime(), end_dt=end_dt.to_pydatetime()),
            auth=TqAuth(username, password),
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

            captures = [("rolling_last_row", klines.iloc[-1])]
            if len(klines) >= 2:
                captures.append(("completed_previous_row", klines.iloc[-2]))
            for capture_mode, row in captures:
                record = _bar_record(vt_symbol, tq_symbol, row, capture_mode)
                if record is None:
                    continue
                key = (capture_mode, int(record["bar_id"]))
                if key in seen:
                    continue
                seen.add(key)
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
        bars = bars.drop_duplicates(["vt_symbol", "capture_mode", "bar_datetime"]).sort_values(
            ["vt_symbol", "capture_mode", "bar_datetime"]
        )
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
    bars = bars.dropna(subset=["bar_datetime"]).sort_values(["vt_symbol", "capture_mode", "bar_datetime"])

    rows: list[dict[str, Any]] = []
    for (vt_symbol, capture_mode), frame in bars.groupby(["vt_symbol", "capture_mode"], sort=False):
        target_frame = targets[targets["vt_symbol"].astype(str).eq(str(vt_symbol))].copy()
        if target_frame.empty:
            continue
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
            oi_ok = not preclose.empty and pd.to_numeric(preclose["close_oi"], errors="coerce").notna().any()
            fill_ok = not fill.empty and fill[["open", "close"]].replace([np.inf, -np.inf], np.nan).notna().all().all()
            volume_sum = float(preclose_volume.sum()) if not preclose.empty else 0.0
            fill_volume_sum = float(fill_volume.sum()) if not fill.empty else 0.0
            rows.append(
                {
                    **target,
                    "capture_mode": capture_mode,
                    "session_start": session_start,
                    "freeze_dt": freeze_dt,
                    "fill_end_dt": fill_end_dt,
                    "boundary_uncertain": boundary_uncertain,
                    "preclose_bar_count": int(len(preclose)),
                    "fill_bar_count": int(len(fill)),
                    "valid_ohlc": int(valid_ohlc),
                    "volume_ok": int(not preclose.empty and volume_sum > 0.0),
                    "open_interest_ok": int(oi_ok),
                    "fill_ok": int(fill_ok),
                    "full_bar_ready": int(valid_ohlc and volume_sum > 0.0 and oi_ok and fill_ok),
                    "synthetic_volume": volume_sum if volume_sum > 0.0 else np.nan,
                    "fill_volume": fill_volume_sum if fill_volume_sum > 0.0 else np.nan,
                    "synthetic_open_interest": float(pd.to_numeric(preclose["close_oi"], errors="coerce").dropna().iloc[-1])
                    if oi_ok
                    else np.nan,
                    "synthetic_open": float(preclose["open"].iloc[0]) if valid_ohlc else np.nan,
                    "synthetic_high": float(preclose["high"].max()) if valid_ohlc else np.nan,
                    "synthetic_low": float(preclose["low"].min()) if valid_ohlc else np.nan,
                    "synthetic_close": float(preclose["close"].iloc[-1]) if valid_ohlc else np.nan,
                }
            )
            previous_date = date
    return pd.DataFrame(rows).sort_values(["plan_rank", "vt_symbol", "capture_mode", "date"]).reset_index(drop=True)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = _select_targets()
    targets.to_csv(TARGETS_PATH, index=False, encoding="utf-8-sig")
    if targets.empty:
        raise RuntimeError("No Stage458 targets selected from Stage154 download plan.")

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
        bars_df = bars_df.drop_duplicates(["vt_symbol", "capture_mode", "bar_datetime"]).sort_values(
            ["vt_symbol", "capture_mode", "bar_datetime"]
        )
    bars_df.to_csv(BARS_PATH, index=False, encoding="utf-8-sig")

    synth = _synthesize_for_targets(targets, bars_df)
    synth.to_csv(SYNTH_PATH, index=False, encoding="utf-8-sig")

    summary_rows: list[dict[str, Any]] = []
    for capture_mode, frame in synth.groupby("capture_mode", sort=True):
        target_count = int(len(frame))
        ready_count = int(frame["full_bar_ready"].sum()) if target_count else 0
        summary_rows.append(
            {
                "capture_mode": capture_mode,
                "selected_symbol_count": int(frame["vt_symbol"].nunique()),
                "selected_target_dates": target_count,
                "minute_bar_count": int(len(bars_df[bars_df["capture_mode"].eq(capture_mode)])),
                "volume_positive_bar_count": int(
                    (pd.to_numeric(bars_df[bars_df["capture_mode"].eq(capture_mode)]["volume"], errors="coerce") > 0).sum()
                ),
                "full_bar_ready_count": ready_count,
                "full_bar_ready_rate": ready_count / target_count if target_count else 0.0,
                "synthetic_volume_sum": float(pd.to_numeric(frame["synthetic_volume"], errors="coerce").fillna(0).sum()),
                "fill_volume_sum": float(pd.to_numeric(frame["fill_volume"], errors="coerce").fillna(0).sum()),
                "preclose_bar_count_min": int(frame["preclose_bar_count"].min()) if target_count else 0,
                "fill_bar_count_min": int(frame["fill_bar_count"].min()) if target_count else 0,
            }
        )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    completed = summary[summary["capture_mode"].eq("completed_previous_row")]
    rolling = summary[summary["capture_mode"].eq("rolling_last_row")]
    completed_ready = int(completed["full_bar_ready_count"].iloc[0]) if not completed.empty else 0
    completed_targets = int(completed["selected_target_dates"].iloc[0]) if not completed.empty else 0
    rolling_ready = int(rolling["full_bar_ready_count"].iloc[0]) if not rolling.empty else 0
    completed_positive_bars = int(completed["volume_positive_bar_count"].iloc[0]) if not completed.empty else 0

    if completed_targets and completed_ready == completed_targets and completed_positive_bars > 0:
        decision_label = "completed_kline_volume_unblocks_strict_ohlcvoi_probe_extend_stage156_fix"
    elif completed_positive_bars > 0:
        decision_label = "completed_kline_volume_partially_unblocks_need_boundary_fix"
    else:
        decision_label = "completed_kline_volume_still_missing_seek_external_source"

    decision = {
        "stage": "Stage158",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "promotion_candidate": "none",
        "selected_symbol_count": int(targets["vt_symbol"].nunique()),
        "selected_target_dates": int(len(targets)),
        "rolling_last_ready_count": rolling_ready,
        "completed_previous_ready_count": completed_ready,
        "completed_previous_positive_bar_count": completed_positive_bars,
        "outputs": {
            "targets": str(TARGETS_PATH),
            "status": str(STATUS_PATH),
            "probe_bars": str(BARS_PATH),
            "synthetic_compare": str(SYNTH_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若completed_previous_row完全通过，修正Stage156抽取语义并做更大分片；若仍不通过，转向专业版时间段接口、tick序列或QMT/第三方分钟源。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = "\n".join(
        [
            "# Stage158 已完成分钟K volume语义探针",
            "",
            f"- 生成时间：{decision['generated_at']}",
            "- 阶段性质：数据抽取语义校验；不新增策略、不修改 Stage079/C3 交易规则。",
            f"- 决策标签：`{decision_label}`。",
            "",
            "## 外部调研与判断",
            "",
            "- TqSdk文档定义 `get_kline_serial` 分钟K包含 `volume/open_oi/close_oi`。",
            "- TqSdk文档也定义 tick 序列包含当日累计 `volume/open_interest`；专业版时间段接口可直接取历史K线/tick序列。",
            "- 因此 Stage156 的 `volume=0` 需要先区分是数据源缺失，还是抽取了未完成的滚动K线。",
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
            "## 合成对比样本",
            "",
            _md_table(synth, max_rows=20),
            "",
            "## 结论",
            "",
            "- 本阶段没有策略候选晋级。",
            "- 如果 `completed_previous_row` 通过，说明 Stage156 的数据阻断主要来自滚动K线抽取语义，而不是 TqBacktest 完全缺失分钟成交量。",
            "- 下一步必须先把一致预收盘OHLCVOI数据链路修正并扩大分片，再恢复 Stage079 3/6个月体验优化。",
            "",
            "## 过拟合与继续价值反思",
            "",
            "- 过拟合：否。本阶段只验证同一数据源的K线完成语义，不按收益筛选。",
            "- 继续价值：是。若该探针通过，原先暂停的严格预收盘回放路线可以恢复；若失败，则继续寻找外部分钟量源。",
        ]
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
