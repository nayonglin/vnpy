from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage536_stage526_cost_churn_fragility_v1"
OUTPUT_PREFIX = "qmt_roll_stage536_stage526_cost_churn_fragility"

STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
CANDIDATE = "r080_pc25_maxpos4"

DAILY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"
POSITIONS_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_positions_{STAGE526_TAG}.csv"
SUMMARY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_summary_{STAGE526_TAG}.csv"

DAILY_DIAGNOSTIC_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_diagnostic_{MODEL_TAG}.csv"
MONTHLY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_summary_{MODEL_TAG}.csv"
PRODUCT_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_window_{MODEL_TAG}.csv"
SEGMENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_segments_{MODEL_TAG}.csv"
RULE_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rule_probe_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

BAD_START = pd.Timestamp("2022-03-09")
BAD_END = pd.Timestamp("2022-12-07")


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


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"[A-Za-z]+", symbol)
    product = match.group(0) if match else symbol
    return f"{product}.{exchange}"


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = equity.astype(float)
    return (values / values.cummax() - 1.0) * 100.0


def _max_dd_window(equity: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    dd = _drawdown_pct(equity)
    trough = pd.Timestamp(dd.idxmin())
    peak = pd.Timestamp(equity.loc[:trough].idxmax())
    return peak, trough, float(dd.loc[trough])


def _load_candidate_daily() -> pd.DataFrame:
    if not DAILY_IN.exists():
        raise FileNotFoundError(DAILY_IN)
    daily = pd.read_csv(DAILY_IN, encoding="utf-8-sig")
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    daily = daily[daily["variant"].eq(CANDIDATE)].dropna(subset=["date"]).sort_values("date").copy()
    numeric_cols = [
        "net_pnl",
        "xsmom_true_daily_pnl",
        "total_net_pnl",
        "slippage",
        "xsmom_true_slippage_cost",
        "total_slippage",
        "trade_count",
        "c3_active_products",
        "account_equity",
        "broker10_margin_to_equity_pct",
    ]
    for column in numeric_cols:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["cum_slippage"] = daily["total_slippage"].cumsum()
    daily["equity_1x"] = daily["account_equity"].astype(float)
    daily["equity_2x"] = daily["equity_1x"] - daily["cum_slippage"]
    daily["equity_3x"] = daily["equity_1x"] - 2.0 * daily["cum_slippage"]
    for column in ["equity_1x", "equity_2x", "equity_3x"]:
        daily[f"dd_{column}"] = _drawdown_pct(pd.Series(daily[column].to_numpy(dtype=float), index=daily["date"])).to_numpy()
    daily["extra_cost_3x_vs_1x_today"] = 2.0 * daily["total_slippage"]
    daily["month"] = daily["date"].dt.to_period("M").astype(str)
    return daily.reset_index(drop=True)


def _load_candidate_positions() -> pd.DataFrame:
    if not POSITIONS_IN.exists():
        raise FileNotFoundError(POSITIONS_IN)
    usecols = [
        "date",
        "vt_symbol",
        "start_pos",
        "end_pos",
        "pos_change",
        "trade_count",
        "slippage",
        "holding_pnl",
        "trading_pnl",
        "net_pnl",
        "variant",
    ]
    frames: list[pd.DataFrame] = []
    window_start = BAD_START - pd.Timedelta(days=45)
    window_end = BAD_END + pd.Timedelta(days=15)
    for chunk in pd.read_csv(POSITIONS_IN, usecols=usecols, chunksize=500_000, encoding="utf-8-sig"):
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce").dt.normalize()
        mask = chunk["variant"].eq(CANDIDATE) & chunk["date"].between(window_start, window_end)
        if not mask.any():
            continue
        frame = chunk.loc[mask].copy()
        for column in ["start_pos", "end_pos", "pos_change", "trade_count", "slippage", "holding_pnl", "trading_pnl", "net_pnl"]:
            frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
        frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_contract)
        frames.append(frame)
    if not frames:
        raise RuntimeError(f"no candidate positions found in {POSITIONS_IN}")
    positions = pd.concat(frames, ignore_index=True, sort=False)
    return positions.dropna(subset=["date"]).sort_values(["vt_symbol", "date"]).reset_index(drop=True)


def _load_summary_metrics() -> dict[str, float]:
    if not SUMMARY_IN.exists():
        return {}
    summary = pd.read_csv(SUMMARY_IN, encoding="utf-8-sig")
    row = summary[summary["variant"].eq(CANDIDATE)]
    if row.empty:
        return {}
    record = row.iloc[0]
    return {
        "ending_equity": float(record.get("end_equity", 0.0)),
        "total_return_pct": float(record.get("total_return_pct", 0.0)),
        "max_dd_pct": float(record.get("max_dd_pct", 0.0)),
        "sharpe": float(record.get("sharpe", 0.0)),
        "ulcer_pct": float(record.get("ulcer_pct", 0.0)),
        "total_slippage": float(record.get("total_slippage", 0.0)),
        "total_trade_count": float(record.get("total_trade_count", 0.0)),
        "nonzero_daily_win_rate_pct": float(record.get("nonzero_daily_win_rate_pct", 0.0)),
    }


def _window_summary(daily: pd.DataFrame) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for label, column in [("1x", "equity_1x"), ("2x", "equity_2x"), ("3x", "equity_3x")]:
        equity = pd.Series(daily[column].to_numpy(dtype=float), index=daily["date"])
        peak, trough, max_dd = _max_dd_window(equity)
        window = daily[daily["date"].between(peak, trough)].copy()
        peak_row = daily[daily["date"].eq(peak)].iloc[0]
        trough_row = daily[daily["date"].eq(trough)].iloc[0]
        in_window_cost = float((trough_row["cum_slippage"] - peak_row["cum_slippage"]) * {"1x": 0.0, "2x": 1.0, "3x": 2.0}[label])
        summaries[label] = {
            "peak_date": peak,
            "trough_date": trough,
            "max_dd_pct": max_dd,
            "peak_equity": float(peak_row[column]),
            "trough_equity": float(trough_row[column]),
            "window_days": int(len(window)),
            "window_total_net_pnl": float(window["total_net_pnl"].sum()),
            "window_total_slippage": float(window["total_slippage"].sum()),
            "window_trade_count": float(window["trade_count"].sum()),
            "window_extra_cost_vs_1x": in_window_cost,
            "broker10_max_pct": float(window["broker10_margin_to_equity_pct"].max()) if len(window) else 0.0,
        }
    one = summaries["1x"]
    three = summaries["3x"]
    summaries["comparison"] = {
        "same_peak_trough": bool(pd.Timestamp(one["peak_date"]) == pd.Timestamp(three["peak_date"]) and pd.Timestamp(one["trough_date"]) == pd.Timestamp(three["trough_date"])),
        "dd_gap_3x_minus_1x_pp": float(three["max_dd_pct"] - one["max_dd_pct"]),
        "same_window_extra_cost_3x": float(three["window_extra_cost_vs_1x"]),
        "same_window_slippage": float(three["window_total_slippage"]),
        "same_window_trade_count": float(three["window_trade_count"]),
    }
    return summaries


def _daily_diagnostic(daily: pd.DataFrame, window_summary: dict[str, Any]) -> pd.DataFrame:
    peak = pd.Timestamp(window_summary["3x"]["peak_date"])
    trough = pd.Timestamp(window_summary["3x"]["trough_date"])
    frame = daily[daily["date"].between(peak, trough)].copy()
    frame["is_trade_day"] = frame["trade_count"].gt(0).astype(int)
    frame["negative_pnl_day"] = frame["total_net_pnl"].lt(0).astype(int)
    frame["cost_to_abs_pnl_pct"] = frame["total_slippage"] / frame["total_net_pnl"].abs().replace(0.0, np.nan) * 100.0
    frame["cost_to_abs_pnl_pct"] = frame["cost_to_abs_pnl_pct"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    frame["churn_loss_day"] = (frame["is_trade_day"].eq(1) & frame["negative_pnl_day"].eq(1)).astype(int)
    return frame


def _monthly_summary(daily_window: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        daily_window.groupby("month", as_index=False)
        .agg(
            days=("date", "count"),
            total_net_pnl=("total_net_pnl", "sum"),
            c3_net_pnl=("net_pnl", "sum"),
            xsmom_net_pnl=("xsmom_true_daily_pnl", "sum"),
            total_slippage=("total_slippage", "sum"),
            extra_cost_3x_vs_1x=("extra_cost_3x_vs_1x_today", "sum"),
            trade_count=("trade_count", "sum"),
            trade_days=("is_trade_day", "sum"),
            churn_loss_days=("churn_loss_day", "sum"),
            min_dd_3x=("dd_equity_3x", "min"),
            max_broker10=("broker10_margin_to_equity_pct", "max"),
        )
        .sort_values("month")
    )
    grouped["slippage_per_trade"] = grouped["total_slippage"] / grouped["trade_count"].replace(0.0, np.nan)
    grouped["slippage_per_trade"] = grouped["slippage_per_trade"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return grouped


def _product_window(positions: pd.DataFrame, daily_window: pd.DataFrame) -> pd.DataFrame:
    start = daily_window["date"].min()
    end = daily_window["date"].max()
    window = positions[positions["date"].between(start, end)].copy()
    grouped = (
        window.groupby("product_vt_symbol", as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            active_days=("end_pos", lambda item: int((item.abs() > 0).sum())),
            trade_days=("trade_count", lambda item: int((item > 0).sum())),
        )
        .sort_values("net_pnl")
    )
    grouped["slippage_per_trade"] = grouped["slippage"] / grouped["trade_count"].replace(0.0, np.nan)
    grouped["slippage_per_trade"] = grouped["slippage_per_trade"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    grouped["cost_to_abs_pnl_pct"] = grouped["slippage"] / grouped["net_pnl"].abs().replace(0.0, np.nan) * 100.0
    grouped["cost_to_abs_pnl_pct"] = grouped["cost_to_abs_pnl_pct"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return grouped


def _position_segments(positions: pd.DataFrame, daily_window: pd.DataFrame) -> pd.DataFrame:
    start = daily_window["date"].min()
    end = daily_window["date"].max()
    frame = positions[positions["date"].between(start, end)].copy()
    rows: list[dict[str, Any]] = []
    for vt_symbol, group in frame.groupby("vt_symbol"):
        group = group.sort_values("date").reset_index(drop=True)
        active = group["start_pos"].ne(0.0) | group["end_pos"].ne(0.0) | group["trade_count"].gt(0.0)
        segment_start = active & ~active.shift(fill_value=False)
        segment_id = segment_start.cumsum()
        active_group = group[active].copy()
        if active_group.empty:
            continue
        active_group["segment_id"] = segment_id[active].to_numpy()
        for seg_id, segment in active_group.groupby("segment_id"):
            direction = float(segment["end_pos"].replace(0.0, np.nan).dropna().median()) if segment["end_pos"].ne(0.0).any() else 0.0
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "product_vt_symbol": segment["product_vt_symbol"].iloc[0],
                    "segment_id": int(seg_id),
                    "start": segment["date"].iloc[0],
                    "end": segment["date"].iloc[-1],
                    "segment_days": int(len(segment)),
                    "direction": "long" if direction > 0 else ("short" if direction < 0 else "flat"),
                    "max_abs_pos": float(segment[["start_pos", "end_pos"]].abs().max().max()),
                    "net_pnl": float(segment["net_pnl"].sum()),
                    "holding_pnl": float(segment["holding_pnl"].sum()),
                    "trading_pnl": float(segment["trading_pnl"].sum()),
                    "slippage": float(segment["slippage"].sum()),
                    "trade_count": float(segment["trade_count"].sum()),
                    "trade_days": int(segment["trade_count"].gt(0.0).sum()),
                }
            )
    segments = pd.DataFrame(rows)
    if segments.empty:
        return segments
    segments["cost_to_abs_pnl_pct"] = segments["slippage"] / segments["net_pnl"].abs().replace(0.0, np.nan) * 100.0
    segments["cost_to_abs_pnl_pct"] = segments["cost_to_abs_pnl_pct"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    segments["short_loss"] = (segments["net_pnl"].lt(0.0) & segments["segment_days"].le(10)).astype(int)
    segments["trade_dense_loss"] = (segments["net_pnl"].lt(0.0) & segments["trade_count"].ge(4)).astype(int)
    return segments.sort_values("net_pnl")


def _rule_probes(daily_window: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    probes: list[dict[str, Any]] = []
    day_masks = [
        ("daily_trade_loss_days", daily_window["churn_loss_day"].eq(1)),
        ("daily_top25_slippage_days", daily_window["total_slippage"].ge(daily_window["total_slippage"].quantile(0.75))),
        (
            "daily_trade_loss_top25_slippage",
            daily_window["churn_loss_day"].eq(1) & daily_window["total_slippage"].ge(daily_window["total_slippage"].quantile(0.75)),
        ),
        ("daily_trade_count_ge2_loss", daily_window["negative_pnl_day"].eq(1) & daily_window["trade_count"].ge(2)),
    ]
    for name, mask in day_masks:
        subset = daily_window[mask].copy()
        probes.append(
            {
                "probe": name,
                "unit": "day",
                "count": int(len(subset)),
                "net_pnl": float(subset["total_net_pnl"].sum()) if len(subset) else 0.0,
                "slippage": float(subset["total_slippage"].sum()) if len(subset) else 0.0,
                "trade_count": float(subset["trade_count"].sum()) if len(subset) else 0.0,
                "extra_cost_3x_vs_1x": float(subset["extra_cost_3x_vs_1x_today"].sum()) if len(subset) else 0.0,
            }
        )

    if not segments.empty:
        segment_masks = [
            ("segment_short_loss_le10d", segments["short_loss"].eq(1)),
            ("segment_trade_dense_loss", segments["trade_dense_loss"].eq(1)),
            (
                "segment_short_loss_top25_slippage",
                segments["short_loss"].eq(1) & segments["slippage"].ge(segments["slippage"].quantile(0.75)),
            ),
            ("segment_loss_trade_count_ge4", segments["net_pnl"].lt(0.0) & segments["trade_count"].ge(4)),
        ]
        for name, mask in segment_masks:
            subset = segments[mask].copy()
            probes.append(
                {
                    "probe": name,
                    "unit": "segment",
                    "count": int(len(subset)),
                    "net_pnl": float(subset["net_pnl"].sum()) if len(subset) else 0.0,
                    "slippage": float(subset["slippage"].sum()) if len(subset) else 0.0,
                    "trade_count": float(subset["trade_count"].sum()) if len(subset) else 0.0,
                    "extra_cost_3x_vs_1x": float(2.0 * subset["slippage"].sum()) if len(subset) else 0.0,
                }
            )
    return pd.DataFrame(probes).sort_values(["unit", "net_pnl"])


def _decision(
    daily: pd.DataFrame,
    daily_window: pd.DataFrame,
    monthly: pd.DataFrame,
    product_window: pd.DataFrame,
    segments: pd.DataFrame,
    probes: pd.DataFrame,
    window_summary: dict[str, Any],
    summary_metrics: dict[str, float],
) -> dict[str, Any]:
    comparison = window_summary["comparison"]
    top_loss_segments = segments.sort_values("net_pnl").head(10).to_dict(orient="records") if not segments.empty else []
    top_loss_products = product_window.sort_values("net_pnl").head(8).to_dict(orient="records")
    top_cost_month = monthly.sort_values("total_slippage", ascending=False).head(3).to_dict(orient="records")
    short_loss = probes[probes["probe"].eq("segment_short_loss_le10d")]
    label = "cost_churn_fragility_explained_no_rule_ready"
    if not short_loss.empty and float(short_loss.iloc[0]["net_pnl"]) < 0:
        label = "short_loss_segments_are_cost_fragility_focus"
    return {
        "stage": "Stage236",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "candidate": CANDIDATE,
        "full_period": {
            "ending_equity": float(summary_metrics.get("ending_equity", daily["equity_1x"].iloc[-1])),
            "total_return_pct": float(summary_metrics.get("total_return_pct", (daily["equity_1x"].iloc[-1] / 615_000.0 - 1.0) * 100.0)),
            "max_dd_1x_pct": float(daily["dd_equity_1x"].min()),
            "max_dd_3x_pct": float(daily["dd_equity_3x"].min()),
            "total_slippage": float(summary_metrics.get("total_slippage", daily["total_slippage"].sum())),
            "total_trade_count": float(summary_metrics.get("total_trade_count", daily["trade_count"].sum())),
            "c3_daily_trade_count_column_sum": float(daily["trade_count"].sum()),
            "sharpe": float(summary_metrics.get("sharpe", 0.0)),
            "ulcer_pct": float(summary_metrics.get("ulcer_pct", 0.0)),
            "nonzero_daily_win_rate_pct": float(summary_metrics.get("nonzero_daily_win_rate_pct", 0.0)),
        },
        "window_summary": _json_safe(window_summary),
        "comparison": _json_safe(comparison),
        "bad_window": {
            "start": str(daily_window["date"].min().date()),
            "end": str(daily_window["date"].max().date()),
            "days": int(len(daily_window)),
            "net_pnl": float(daily_window["total_net_pnl"].sum()),
            "slippage": float(daily_window["total_slippage"].sum()),
            "trade_count": float(daily_window["trade_count"].sum()),
            "churn_loss_days": int(daily_window["churn_loss_day"].sum()),
        },
        "top_cost_months": _json_safe(top_cost_month),
        "top_loss_products": _json_safe(top_loss_products),
        "top_loss_segments": _json_safe(top_loss_segments),
        "probe_summary": _json_safe(probes.to_dict(orient="records")),
        "interpretation": "只读成本/换手脆弱性诊断，不新增交易规则。若继续，应先验证候选规则不会错过长趋势段。",
    }


def _plot(
    daily: pd.DataFrame,
    daily_window: pd.DataFrame,
    monthly: pd.DataFrame,
    product_window: pd.DataFrame,
    segments: pd.DataFrame,
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(17, 11))
    ax_equity, ax_month, ax_product, ax_segment = axes.flatten()

    ax_equity.plot(daily["date"], daily["dd_equity_1x"], label="DD 1x", color="#0f766e", linewidth=1.0)
    ax_equity.plot(daily["date"], daily["dd_equity_3x"], label="DD 3x", color="#dc2626", linewidth=1.0)
    ax_equity.axhline(-40.0, color="#111827", linestyle="--", linewidth=1)
    ax_equity.axvspan(daily_window["date"].min(), daily_window["date"].max(), color="#f59e0b", alpha=0.16)
    ax_equity.set_title("Stage526 drawdown under 1x/3x cost")
    ax_equity.set_ylabel("drawdown pct")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=8)

    month_view = monthly.copy()
    ax_month.bar(month_view["month"], month_view["total_net_pnl"], color=np.where(month_view["total_net_pnl"].ge(0), "#16a34a", "#dc2626"), alpha=0.82)
    ax_month_twin = ax_month.twinx()
    ax_month_twin.plot(month_view["month"], month_view["total_slippage"], color="#2563eb", marker="o", linewidth=1.2, label="slippage")
    ax_month.set_title("Bad-window monthly PnL and slippage")
    ax_month.tick_params(axis="x", labelrotation=45)
    ax_month.grid(axis="y", alpha=0.25)

    product = product_window.sort_values("net_pnl").head(10).copy()
    ax_product.barh(product["product_vt_symbol"], product["net_pnl"], color=np.where(product["net_pnl"].ge(0), "#16a34a", "#dc2626"))
    ax_product.axvline(0, color="#111827", linewidth=1)
    ax_product.set_title("Worst products in 3x DD window")
    ax_product.grid(axis="x", alpha=0.25)

    if not segments.empty:
        seg = segments.copy()
        colors = np.where(seg["net_pnl"].lt(0), "#dc2626", "#2563eb")
        sizes = np.clip(seg["trade_count"] * 12 + 20, 24, 280)
        ax_segment.scatter(seg["segment_days"], seg["net_pnl"], c=colors, s=sizes, alpha=0.72, edgecolors="#111827", linewidths=0.35)
        ax_segment.axhline(0, color="#111827", linewidth=1)
        ax_segment.axvline(10, color="#6b7280", linestyle="--", linewidth=1)
    ax_segment.set_title("Position segment days vs PnL")
    ax_segment.set_xlabel("segment days")
    ax_segment.set_ylabel("segment net pnl")
    ax_segment.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    daily_window: pd.DataFrame,
    monthly: pd.DataFrame,
    product_window: pd.DataFrame,
    segments: pd.DataFrame,
    probes: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    top_days = daily_window.sort_values("total_slippage", ascending=False).head(20)
    worst_segments = segments.sort_values("net_pnl").head(24) if not segments.empty else pd.DataFrame()
    lines = [
        "# Stage236 Stage526成本/换手脆弱性诊断",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：Stage235 后续只读诊断；聚焦 Stage526 的 3x成本失败与长回撤路径。",
        "- 运行前过拟合判断：否。读取固定 Stage526 输出，解释成本和换手分布，不新增策略、不扫参数。",
        "- 运行前继续价值判断：是。Stage526 未关账的主风险就是 3x成本 DD 超过 40%，必须先定位成本脆弱性。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随的交易成本风险通常来自震荡期反复止损/再入场，而不是单次滑点；公开资料和 GitHub 回测示例常把手续费、滑点、换手作为鲁棒性压力项。",
        "- 但本账户约束还有保证金和复利路径，不能直接复制外部 turnover filter；本阶段只做成本脆弱性归因。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 月度归因",
        "",
        _md_table(monthly),
        "",
        "## 规则/现象探针",
        "",
        _md_table(probes),
        "",
        "## 坏窗口产品归因",
        "",
        _md_table(product_window, max_rows=30),
        "",
        "## 高滑点交易日",
        "",
        _md_table(
            top_days[
                [
                    "date",
                    "total_net_pnl",
                    "total_slippage",
                    "trade_count",
                    "extra_cost_3x_vs_1x_today",
                    "dd_equity_3x",
                    "broker10_margin_to_equity_pct",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 最差持仓段",
        "",
        _md_table(
            worst_segments[
                [
                    "product_vt_symbol",
                    "vt_symbol",
                    "direction",
                    "start",
                    "end",
                    "segment_days",
                    "net_pnl",
                    "slippage",
                    "trade_count",
                    "cost_to_abs_pnl_pct",
                    "short_loss",
                    "trade_dense_loss",
                ]
            ]
            if not worst_segments.empty
            else worst_segments,
            max_rows=24,
        ),
        "",
        "## 图表视觉复盘",
        "",
        f"- 图表：`{CHART_PATH}`",
        "- 左上：确认 3x 成本曲线是在同一长回撤窗口中跌穿 40%，不是新的保证金峰值窗口。",
        "- 右上：月度柱线用于看亏损月份是否同时伴随高滑点/高换手。",
        "- 左下：产品贡献用于防止错误地把成本问题简化为产品黑名单。",
        "- 右下：如果短命亏损段是核心，红点应集中在 10日以内；若红点横跨长持有段，则不能用简单冷却或短段过滤。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    daily = _load_candidate_daily()
    positions = _load_candidate_positions()
    summary_metrics = _load_summary_metrics()
    window_summary = _window_summary(daily)
    daily_window = _daily_diagnostic(daily, window_summary)
    monthly = _monthly_summary(daily_window)
    product_window = _product_window(positions, daily_window)
    segments = _position_segments(positions, daily_window)
    probes = _rule_probes(daily_window, segments)
    decision = _decision(daily, daily_window, monthly, product_window, segments, probes, window_summary, summary_metrics)
    _plot(daily, daily_window, monthly, product_window, segments)
    _write_report(daily_window, monthly, product_window, segments, probes, decision)

    daily_window.to_csv(DAILY_DIAGNOSTIC_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_window.to_csv(PRODUCT_WINDOW_PATH, index=False, encoding="utf-8-sig")
    segments.to_csv(SEGMENT_PATH, index=False, encoding="utf-8-sig")
    probes.to_csv(RULE_PROBE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
