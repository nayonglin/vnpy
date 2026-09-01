from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import json
import logging
import math
from pathlib import Path
import sys
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
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

import analyze_qmt_roll_stage451_true_path_1455_vwap_replay as s451  # noqa: E402
import analyze_qmt_roll_stage452_iterative_1455_proxy_backfill as s452  # noqa: E402
import analyze_qmt_roll_stage501_asymmetric_entry_exit_execution as s501  # noqa: E402
import analyze_qmt_roll_stage503_next_real_open_risk_frontier as s503  # noqa: E402


MODEL_TAG = "stage504_next_real_open_fallback_backfill_v1"
OUTPUT_PREFIX = "qmt_roll_stage504_next_real_open_fallback_backfill"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
RISK_MULTIPLIERS = (0.7, 0.6)
RAW_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_stage504_next_real_open_fallback_backfill"
CHINA_TZ = ZoneInfo("Asia/Shanghai")
MAX_ITERATIONS = 3
MAX_SECONDS_PER_SYMBOL = 240
WINDOW_PADDING_MINUTES = 10

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
BACKFILL_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_backfill_status_{MODEL_TAG}.csv"
FALLBACK_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fallback_audit_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
FRONTIER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _patch_raw_roots() -> None:
    roots = [RAW_ROOT]
    for root in s452.RAW_ROOTS:
        path = Path(root)
        if path not in roots:
            roots.append(path)
    s452.RAW_ROOTS = roots


def _to_tqsdk_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def _raw_path(vt_symbol: str) -> Path:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return RAW_ROOT / exchange / f"{symbol}_minute_backtest.csv"


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(CHINA_TZ).tz_localize(None)


def _load_existing_raw(vt_symbol: str) -> pd.DataFrame:
    path = _raw_path(vt_symbol)
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty:
        return frame
    frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce").dt.tz_localize(None)
    frame["vt_symbol"] = vt_symbol
    return frame.dropna(subset=["bar_datetime"]).copy()


def _require_credentials() -> tuple[str, str]:
    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS.")
    return username, password


def _candidate_windows(row: Any) -> list[dict[str, Any]]:
    vt_symbol = str(row.vt_symbol)
    signal_date = pd.Timestamp(row.signal_date).normalize()
    fill_date = pd.Timestamp(row.fill_date).normalize()
    windows: list[dict[str, Any]] = []
    if s501._has_night_session(vt_symbol):
        windows.append(
            {
                "vt_symbol": vt_symbol,
                "signal_date": signal_date,
                "fill_date": fill_date,
                "window_type": "night_2100_2105_first_open",
                "target_start": signal_date + pd.Timedelta(hours=21),
                "target_end": signal_date + pd.Timedelta(hours=21, minutes=5),
            }
        )
    windows.append(
        {
            "vt_symbol": vt_symbol,
            "signal_date": signal_date,
            "fill_date": fill_date,
            "window_type": "day_0900_0905_first_open",
            "target_start": fill_date + pd.Timedelta(hours=9),
            "target_end": fill_date + pd.Timedelta(hours=9, minutes=5),
        }
    )
    return windows


def _windows_for_fallbacks(usage: pd.DataFrame) -> pd.DataFrame:
    if usage.empty:
        return pd.DataFrame()
    fallback = usage[usage["price_source"].astype(str).str.startswith("fallback")].copy()
    rows: list[dict[str, Any]] = []
    for row in fallback.itertuples(index=False):
        for window in _candidate_windows(row):
            window["variant"] = str(row.variant)
            window["offset"] = str(row.offset)
            window["direction"] = str(row.direction)
            rows.append(window)
    if not rows:
        return pd.DataFrame()
    windows = pd.DataFrame(rows).drop_duplicates(
        ["vt_symbol", "signal_date", "fill_date", "window_type", "target_start", "target_end"]
    )
    return windows.sort_values(["vt_symbol", "target_start", "window_type"]).reset_index(drop=True)


def _windows_covered(vt_symbol: str, windows: pd.DataFrame) -> bool:
    bars = s452._load_raw_bars(vt_symbol)
    if bars.empty:
        return False
    bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce").dt.tz_localize(None)
    for row in windows.itertuples(index=False):
        start = pd.Timestamp(row.target_start)
        end = pd.Timestamp(row.target_end)
        if bars[(bars["bar_datetime"] >= start) & (bars["bar_datetime"] < end)].empty:
            return False
    return True


def _extract_symbol_windows(vt_symbol: str, windows: pd.DataFrame, username: str, password: str) -> dict[str, Any]:
    if _windows_covered(vt_symbol, windows):
        return {
            "vt_symbol": vt_symbol,
            "status": "cached_raw",
            "target_windows": int(len(windows)),
            "rows": int(len(_load_existing_raw(vt_symbol))),
            "elapsed_seconds": 0.0,
            "message": "",
        }

    tq_symbol = _to_tqsdk_symbol(vt_symbol)
    start_dt = pd.Timestamp(windows["target_start"].min()) - timedelta(minutes=WINDOW_PADDING_MINUTES)
    end_dt = pd.Timestamp(windows["target_end"].max()) + timedelta(minutes=WINDOW_PADDING_MINUTES)
    status = {
        "vt_symbol": vt_symbol,
        "tq_symbol": tq_symbol,
        "extract_start": start_dt,
        "extract_end": end_dt,
        "target_windows": int(len(windows)),
        "status": "unknown",
        "rows": 0,
        "elapsed_seconds": 0.0,
        "message": "",
    }
    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    started = time.time()
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

    new_bars = pd.DataFrame(rows)
    old_bars = _load_existing_raw(vt_symbol)
    frames = [frame for frame in [old_bars, new_bars] if not frame.empty]
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not merged.empty:
        merged["bar_datetime"] = pd.to_datetime(merged["bar_datetime"], errors="coerce").dt.tz_localize(None)
        merged = merged.dropna(subset=["bar_datetime"]).drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")
        merged = merged.sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)
        path = _raw_path(vt_symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(path, index=False, encoding="utf-8-sig")
    if status["status"] == "unknown":
        status["status"] = "extracted" if len(new_bars) else "empty"
    status["rows"] = int(len(merged))
    status["new_rows"] = int(len(new_bars))
    status["elapsed_seconds"] = round(time.time() - started, 2)
    status["covered_after_extract"] = bool(_windows_covered(vt_symbol, windows))
    return status


def _backfill(usage: pd.DataFrame, iteration: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    windows = _windows_for_fallbacks(usage)
    if windows.empty:
        return pd.DataFrame(), pd.DataFrame()
    username, password = _require_credentials()
    status_rows: list[dict[str, Any]] = []
    for vt_symbol, group in windows.groupby("vt_symbol", sort=True):
        status = _extract_symbol_windows(str(vt_symbol), group.copy(), username, password)
        status["iteration"] = int(iteration)
        status_rows.append(status)
    return pd.DataFrame(status_rows), windows


def _run_all_variants() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    baseline = s503._load_stage079_baseline()
    daily_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    source_frames: list[pd.DataFrame] = []
    for multiplier in RISK_MULTIPLIERS:
        daily, usage, source_counts = s503._run_variant(multiplier)
        daily_frames.append(daily)
        usage_frames.append(usage)
        source_frames.append(source_counts)
    long_daily = s503._build_long_daily(baseline, daily_frames)
    usage_all = pd.concat(usage_frames, ignore_index=True) if usage_frames else pd.DataFrame()
    source_all = pd.concat(source_frames, ignore_index=True) if source_frames else pd.DataFrame()
    return long_daily, usage_all, source_all


def _source_counts(usage: pd.DataFrame) -> pd.DataFrame:
    if usage.empty:
        return pd.DataFrame(columns=["variant", "price_source", "trade_count"])
    rows = []
    for (variant, source), value in usage.groupby(["variant", "price_source"]).size().items():
        rows.append({"variant": variant, "price_source": source, "trade_count": int(value)})
    return pd.DataFrame(rows)


def _frontier(summary: pd.DataFrame, usage: pd.DataFrame) -> pd.DataFrame:
    stage079_return = _safe_float(summary[summary["variant"].eq(BASELINE_VARIANT)]["total_return_pct"].iloc[0])
    risk_map = {
        f"stage079_next_real_risk{int(round(multiplier * 100)):03d}": float(multiplier)
        for multiplier in RISK_MULTIPLIERS
    }
    fallback_by_variant = (
        usage.assign(is_fallback=usage["price_source"].astype(str).str.startswith("fallback"))
        .groupby("variant")["is_fallback"]
        .sum()
        .astype(int)
        .to_dict()
        if not usage.empty
        else {}
    )
    frame = summary[summary["variant"].isin(risk_map)].copy()
    frame["risk_multiplier"] = frame["variant"].map(risk_map)
    frame["return_retention_vs_stage079_pct"] = frame["total_return_pct"].astype(float) / stage079_return * 100.0
    frame["dd40_pass"] = frame["max_dd_pct"].astype(float).ge(-40.0).astype(int)
    frame["fallback_trade_count"] = frame["variant"].map(fallback_by_variant).fillna(0).astype(int)
    return frame[
        [
            "variant",
            "risk_multiplier",
            "end_equity",
            "total_return_pct",
            "return_retention_vs_stage079_pct",
            "max_dd_pct",
            "sharpe",
            "ulcer_pct",
            "dd40_pass",
            "fallback_trade_count",
        ]
    ].sort_values(["dd40_pass", "total_return_pct"], ascending=[False, False])


def _plot(long_daily: pd.DataFrame) -> None:
    keep = [BASELINE_VARIANT, "stage079_next_real_risk070", "stage079_next_real_risk060"]
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for variant, frame in long_daily[long_daily["variant"].isin(keep)].groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        x = pd.to_datetime(frame["date"])
        nav = frame["account_equity"].astype(float) / ACCOUNT_CAPITAL
        axes[0].plot(x, nav, label=label, linewidth=1.1)
        axes[1].plot(x, (nav / nav.cummax() - 1.0) * 100.0, label=label, linewidth=1.0)
    axes[0].set_title("Stage504 next-real-open fallback backfill")
    axes[0].set_ylabel("NAV")
    axes[0].legend(fontsize=8)
    axes[1].set_title("Underwater drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-40.0, color="#222222", linestyle="--", linewidth=1.0)
    axes[1].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    frontier: pd.DataFrame,
    source_counts: pd.DataFrame,
    backfill_status: pd.DataFrame,
    fallback_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_cols = [
        "variant",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "rolling252_dd30_breach_rate",
        "rolling504_dd30_breach_rate",
        "annual_cold_start_dd30_pass_rate",
        "quarter_cold_start_dd30_pass_rate",
    ]
    horizon_cols = [
        "variant",
        "horizon_days",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "max_dd_worst_pct",
        "dd30_breach_rate",
        "ulcer_p95_pct",
    ]
    report = [
        "# Stage204 下一真实窗口 fallback 补齐复核",
        "",
        f"- 生成时间：{decision['generated_at']}",
        "- 阶段性质：真实可成交证据清理；不新增策略、不修改 Stage079/C3 信号。",
        "- 口径：只针对 Stage203 `risk060/risk070` fallback 真实成交键补抽 21:00/09:00 分钟窗口，然后重跑同一风险倍率。",
        "",
        "## 外部调研判断",
        "",
        "- 事件驱动回测必须先清理成交时点证据，不能让 daily next open fallback 混入最终候选。",
        "- 风险预算方向有研究依据，但本阶段只清理数据证据，不调风险倍率。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最佳DD40版本：`{decision['best_dd40_variant']}`。",
        f"- 最佳DD40收益保留：`{decision['best_dd40_return_retention_vs_stage079_pct']:.4f}%`。",
        f"- 最佳DD40最大回撤：`{decision['best_dd40_max_dd_pct']:.4f}%`。",
        f"- 最佳DD40 fallback：`{decision['best_dd40_fallback_trade_count']}`。",
        "",
        "## 前沿汇总",
        "",
        _md_table(frontier),
        "",
        "## 全周期指标",
        "",
        _md_table(summary[summary_cols]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[horizon_cols].sort_values(["variant", "horizon_days"])),
        "",
        "## 成交价格来源",
        "",
        _md_table(source_counts.sort_values(["variant", "trade_count"], ascending=[True, False])),
        "",
        "## fallback 补数状态",
        "",
        _md_table(backfill_status.sort_values(["iteration", "vt_symbol"]), max_rows=80),
        "",
        "## 剩余 fallback 审计",
        "",
        _md_table(fallback_audit.sort_values(["variant", "signal_date", "vt_symbol"]), max_rows=80),
        "",
        "## 图表视觉复盘",
        "",
        "- 需要结合生成图判断：若 `risk060` 仍只是贴着 `-40%` 线，不能因为表格过线就晋级。",
        "- 若补齐后 `risk070` 仍穿 `-40%`，说明收益保留和回撤目标之间的冲突是真实暴露结构问题，不是 fallback 偏差。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。本阶段只补成交数据，不调参数、不筛日期、不筛品种。",
        "- 运行后过拟合反思：若 fallback 清理改变结果，也只能按固定 `0.7/0.6` 档判断，不能继续调相邻小数。",
        "- 运行前继续价值反思：是。Stage203 的边界是否可信取决于 fallback 能否清理。",
        "- 运行后继续价值反思：以决策标签为准；若仍无候选，下一步转向低自由度状态风险预算。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    _patch_raw_roots()
    all_status: list[pd.DataFrame] = []
    all_windows: list[pd.DataFrame] = []
    final_daily = pd.DataFrame()
    final_usage = pd.DataFrame()
    final_sources = pd.DataFrame()
    for iteration in range(1, MAX_ITERATIONS + 1):
        final_daily, final_usage, final_sources = _run_all_variants()
        fallback = final_usage[final_usage["price_source"].astype(str).str.startswith("fallback")].copy()
        if fallback.empty:
            break
        if iteration == MAX_ITERATIONS:
            break
        status, windows = _backfill(fallback, iteration)
        if not status.empty:
            all_status.append(status)
        if not windows.empty:
            windows = windows.copy()
            windows["iteration"] = int(iteration)
            all_windows.append(windows)
        if not status.empty and not status["covered_after_extract"].fillna(False).any():
            break

    summary, horizon, score, cost, gate = s451._evaluate(final_daily)
    source_counts = _source_counts(final_usage)
    frontier = _frontier(summary, final_usage)
    fallback_audit = final_usage[final_usage["price_source"].astype(str).str.startswith("fallback")].copy()
    backfill_status = pd.concat(all_status, ignore_index=True) if all_status else pd.DataFrame()
    fallback_windows = pd.concat(all_windows, ignore_index=True) if all_windows else pd.DataFrame()

    passed = frontier[frontier["dd40_pass"].eq(1)].copy()
    clean_passed = passed[passed["fallback_trade_count"].eq(0)].copy()
    if not clean_passed.empty:
        best = clean_passed.sort_values("total_return_pct", ascending=False).iloc[0]
    elif not passed.empty:
        best = passed.sort_values("total_return_pct", ascending=False).iloc[0]
    else:
        best = frontier.sort_values("total_return_pct", ascending=False).iloc[0]

    if clean_passed.empty:
        decision_label = "next_real_fallback_backfill_no_clean_dd40_candidate"
    elif _safe_float(best["return_retention_vs_stage079_pct"]) >= 65.0:
        decision_label = "next_real_fallback_clean_dd40_return65_candidate_needs_final_audit"
    else:
        decision_label = "next_real_fallback_clean_dd40_but_return_retention_short"

    decision = {
        "stage": "Stage204",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "iterations": int(iteration),
        "backfill_symbol_count": int(backfill_status["vt_symbol"].nunique()) if not backfill_status.empty else 0,
        "fallback_windows_requested": int(len(fallback_windows)),
        "fallback_remaining_count": int(len(fallback_audit)),
        "best_dd40_variant": str(best["variant"]) if not passed.empty else "",
        "best_dd40_risk_multiplier": _safe_float(best["risk_multiplier"]),
        "best_dd40_end_equity": _safe_float(best["end_equity"]),
        "best_dd40_total_return_pct": _safe_float(best["total_return_pct"]),
        "best_dd40_return_retention_vs_stage079_pct": _safe_float(best["return_retention_vs_stage079_pct"]),
        "best_dd40_max_dd_pct": _safe_float(best["max_dd_pct"]),
        "best_dd40_fallback_trade_count": int(best["fallback_trade_count"]) if not passed.empty else 0,
        "outputs": {
            "daily": str(DAILY_PATH),
            "trade_usage": str(TRADE_USAGE_PATH),
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "score": str(SCORE_PATH),
            "cost": str(COST_PATH),
            "gate": str(GATE_PATH),
            "frontier": str(FRONTIER_PATH),
            "backfill_status": str(BACKFILL_STATUS_PATH),
            "fallback_audit": str(FALLBACK_AUDIT_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若仍无 clean DD40+收益保留候选，停止调固定风险倍率，转向上一日可见状态驱动的低自由度风险预算。",
    }

    _plot(final_daily)
    final_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    final_usage.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    backfill_status.to_csv(BACKFILL_STATUS_PATH, index=False, encoding="utf-8-sig")
    fallback_audit.to_csv(FALLBACK_AUDIT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    frontier.to_csv(FRONTIER_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, frontier, source_counts, backfill_status, fallback_audit, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
