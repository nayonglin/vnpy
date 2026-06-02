from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage516_margin_aware_sizing_frontier as s516  # noqa: E402


MODEL_TAG = "stage529_stage526_candidate_drilldown_v1"
OUTPUT_PREFIX = "qmt_roll_stage529_stage526_candidate_drilldown"

STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
STAGE520_TAG = "stage520_product_cap_usage_gate_frontier_v1"
STAGE520_PREFIX = "qmt_roll_stage520_product_cap_usage_gate_frontier"

CANDIDATE = "r080_pc25_maxpos4"
REFERENCE = "r080_pc25_u75"

DAILY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"
POSITIONS_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_positions_{STAGE526_TAG}.csv"
STAGE520_DAILY_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_margin_daily_{STAGE520_TAG}.csv"

PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
BAD_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_windows_{MODEL_TAG}.csv"
WINDOW_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_product_attribution_{MODEL_TAG}.csv"
MARGIN_PEAK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_peak_products_{MODEL_TAG}.csv"
COST_FAILURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_failure_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

ACCOUNT_CAPITAL = 615_000.0
HOLDING_HORIZONS = (21, 63, 126, 252, 504)


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
        "xsmom_true_margin",
        "c3_margin_exact",
        "account_equity",
        "broker10_total_margin_exact",
        "broker10_margin_to_equity_pct",
        "c3_active_products",
    ]
    for column in numeric_cols:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["equity_1x"] = daily["account_equity"].astype(float)
    cumulative_slippage = daily["total_slippage"].astype(float).cumsum()
    daily["equity_2x"] = daily["equity_1x"] - cumulative_slippage
    daily["equity_3x"] = daily["equity_1x"] - 2.0 * cumulative_slippage
    for column in ["equity_1x", "equity_2x", "equity_3x"]:
        daily[f"dd_{column}"] = _drawdown_pct(pd.Series(daily[column].to_numpy(dtype=float), index=daily["date"])).to_numpy()
    return daily


def _load_reference_daily() -> pd.DataFrame:
    ref = pd.read_csv(STAGE520_DAILY_IN, encoding="utf-8-sig")
    ref["date"] = pd.to_datetime(ref["date"], errors="coerce").dt.normalize()
    ref = ref[ref["variant"].eq(REFERENCE)].dropna(subset=["date"]).sort_values("date").copy()
    for column in ["total_net_pnl", "account_equity", "broker10_margin_to_equity_pct"]:
        ref[column] = pd.to_numeric(ref.get(column, 0.0), errors="coerce").fillna(0.0)
    return ref[["date", "total_net_pnl", "account_equity", "broker10_margin_to_equity_pct"]].copy()


def _load_candidate_positions(metadata: dict[str, Any]) -> pd.DataFrame:
    usecols = [
        "date",
        "vt_symbol",
        "start_pos",
        "end_pos",
        "pos_change",
        "close_price",
        "trade_count",
        "slippage",
        "holding_pnl",
        "trading_pnl",
        "net_pnl",
        "variant",
    ]
    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(POSITIONS_IN, usecols=usecols, chunksize=450_000, encoding="utf-8-sig"):
        chunk = chunk[chunk["variant"].eq(CANDIDATE)].copy()
        if chunk.empty:
            continue
        chunks.append(chunk)
    if not chunks:
        raise RuntimeError(f"no candidate positions found in {POSITIONS_IN}")
    positions = pd.concat(chunks, ignore_index=True, sort=False)
    positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.normalize()
    for column in ["start_pos", "end_pos", "pos_change", "close_price", "trade_count", "slippage", "holding_pnl", "trading_pnl", "net_pnl"]:
        positions[column] = pd.to_numeric(positions.get(column, 0.0), errors="coerce").fillna(0.0)
    positions["product_vt_symbol"] = positions["vt_symbol"].map(_product_from_contract)
    positions["size"] = positions["vt_symbol"].map(metadata["sizes"]).fillna(1.0).astype(float)
    positions["margin_ratio"] = positions["vt_symbol"].map(metadata["margin_ratios"]).fillna(0.15).astype(float)
    positions["abs_end_pos"] = positions["end_pos"].abs()
    positions["c3_margin_exact"] = (
        positions["abs_end_pos"] * positions["close_price"].clip(lower=0.0) * positions["size"] * positions["margin_ratio"]
    )
    positions["active_contract"] = (positions["abs_end_pos"] > 0.0).astype(int)
    return positions.dropna(subset=["date"]).copy()


def _product_daily(positions: pd.DataFrame) -> pd.DataFrame:
    daily = (
        positions.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            c3_margin_exact=("c3_margin_exact", "sum"),
            active_contracts=("active_contract", "sum"),
        )
        .sort_values(["date", "product_vt_symbol"])
    )
    daily["active_product"] = (daily["c3_margin_exact"] > 0.0).astype(int)
    return daily


def _product_summary(product_daily: pd.DataFrame) -> pd.DataFrame:
    summary = (
        product_daily.groupby("product_vt_symbol", as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            active_days=("active_product", "sum"),
            positive_pnl_days=("net_pnl", lambda x: int((x > 0.0).sum())),
            negative_pnl_days=("net_pnl", lambda x: int((x < 0.0).sum())),
            max_c3_margin=("c3_margin_exact", "max"),
            p95_c3_margin=("c3_margin_exact", lambda x: float(np.quantile(x, 0.95))),
            margin_day_sum=("c3_margin_exact", "sum"),
        )
        .sort_values("net_pnl", ascending=False)
    )
    summary["pnl_per_1m_margin_day"] = summary["net_pnl"] / (summary["margin_day_sum"].replace(0.0, np.nan) / 1_000_000.0)
    summary["pnl_per_1m_margin_day"] = summary["pnl_per_1m_margin_day"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    summary["slippage_to_abs_pnl_pct"] = summary["slippage"] / summary["net_pnl"].abs().replace(0.0, np.nan) * 100.0
    summary["slippage_to_abs_pnl_pct"] = summary["slippage_to_abs_pnl_pct"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return summary


def _rolling_bad_windows(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    ordered = daily.sort_values("date").reset_index(drop=True)
    for horizon in HOLDING_HORIZONS:
        if len(ordered) <= horizon:
            continue
        equity = ordered["equity_1x"].astype(float)
        returns = equity.shift(-horizon) / equity - 1.0
        valid = returns.iloc[:-horizon].copy()
        if valid.empty:
            continue
        start_idx = int(valid.idxmin())
        end_idx = start_idx + horizon
        window = ordered.iloc[start_idx : end_idx + 1].copy()
        eq = pd.Series(window["equity_1x"].to_numpy(dtype=float), index=window["date"])
        rows.append(
            {
                "window_type": f"worst_return_{horizon}d",
                "holding_days": horizon,
                "start": window["date"].iloc[0],
                "end": window["date"].iloc[-1],
                "return_pct": float(valid.loc[start_idx] * 100.0),
                "window_max_dd_pct": float(_drawdown_pct(eq).min()),
                "broker10_max_pct": float(window["broker10_margin_to_equity_pct"].max()),
                "total_net_pnl": float(window["total_net_pnl"].sum()),
                "c3_net_pnl": float(window["net_pnl"].sum()),
                "xsmom_net_pnl": float(window["xsmom_true_daily_pnl"].sum()),
                "total_slippage": float(window["total_slippage"].sum()),
                "trade_count": float(window["trade_count"].sum()),
            }
        )
    peak, trough, max_dd = _max_dd_window(pd.Series(daily["equity_1x"].to_numpy(dtype=float), index=daily["date"]))
    window = daily[(daily["date"] >= peak) & (daily["date"] <= trough)].copy()
    rows.append(
        {
            "window_type": "full_max_drawdown_1x",
            "holding_days": int(len(window)),
            "start": peak,
            "end": trough,
            "return_pct": float((window["equity_1x"].iloc[-1] / window["equity_1x"].iloc[0] - 1.0) * 100.0) if len(window) else 0.0,
            "window_max_dd_pct": max_dd,
            "broker10_max_pct": float(window["broker10_margin_to_equity_pct"].max()) if len(window) else 0.0,
            "total_net_pnl": float(window["total_net_pnl"].sum()) if len(window) else 0.0,
            "c3_net_pnl": float(window["net_pnl"].sum()) if len(window) else 0.0,
            "xsmom_net_pnl": float(window["xsmom_true_daily_pnl"].sum()) if len(window) else 0.0,
            "total_slippage": float(window["total_slippage"].sum()) if len(window) else 0.0,
            "trade_count": float(window["trade_count"].sum()) if len(window) else 0.0,
        }
    )
    return pd.DataFrame(rows).sort_values(["window_type"]).reset_index(drop=True)


def _window_product_attribution(product_daily: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for row in windows.itertuples(index=False):
        start = pd.Timestamp(row.start)
        end = pd.Timestamp(row.end)
        frame = product_daily[(product_daily["date"] >= start) & (product_daily["date"] <= end)].copy()
        if frame.empty:
            continue
        grouped = (
            frame.groupby("product_vt_symbol", as_index=False)
            .agg(
                net_pnl=("net_pnl", "sum"),
                holding_pnl=("holding_pnl", "sum"),
                trading_pnl=("trading_pnl", "sum"),
                slippage=("slippage", "sum"),
                trade_count=("trade_count", "sum"),
                active_days=("active_product", "sum"),
                max_c3_margin=("c3_margin_exact", "max"),
            )
            .sort_values("net_pnl", ascending=True)
        )
        grouped["window_type"] = row.window_type
        grouped["start"] = start
        grouped["end"] = end
        rows.append(grouped)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True, sort=False)


def _cost_failure(daily: pd.DataFrame, product_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    product_rows: list[pd.DataFrame] = []
    for cost_label, equity_col in [("1x", "equity_1x"), ("2x", "equity_2x"), ("3x", "equity_3x")]:
        equity = pd.Series(daily[equity_col].to_numpy(dtype=float), index=daily["date"])
        peak, trough, max_dd = _max_dd_window(equity)
        window = daily[(daily["date"] >= peak) & (daily["date"] <= trough)].copy()
        rows.append(
            {
                "cost_label": cost_label,
                "peak_date": peak,
                "trough_date": trough,
                "max_dd_pct": max_dd,
                "window_days": int(len(window)),
                "window_total_net_pnl": float(window["total_net_pnl"].sum()) if len(window) else 0.0,
                "window_c3_net_pnl": float(window["net_pnl"].sum()) if len(window) else 0.0,
                "window_xsmom_net_pnl": float(window["xsmom_true_daily_pnl"].sum()) if len(window) else 0.0,
                "window_total_slippage": float(window["total_slippage"].sum()) if len(window) else 0.0,
                "cum_total_slippage_at_trough": float(window["total_slippage"].cumsum().iloc[-1]) if len(window) else 0.0,
                "extra_cost_vs_1x_at_trough": float(
                    (daily.loc[daily["date"].le(trough), "total_slippage"].sum()) * {"1x": 0.0, "2x": 1.0, "3x": 2.0}[cost_label]
                ),
                "broker10_max_pct": float(window["broker10_margin_to_equity_pct"].max()) if len(window) else 0.0,
            }
        )
        frame = product_daily[(product_daily["date"] >= peak) & (product_daily["date"] <= trough)].copy()
        if not frame.empty:
            grouped = (
                frame.groupby("product_vt_symbol", as_index=False)
                .agg(
                    net_pnl=("net_pnl", "sum"),
                    slippage=("slippage", "sum"),
                    trade_count=("trade_count", "sum"),
                    max_c3_margin=("c3_margin_exact", "max"),
                )
                .sort_values("net_pnl", ascending=True)
            )
            grouped["cost_label"] = cost_label
            grouped["peak_date"] = peak
            grouped["trough_date"] = trough
            product_rows.append(grouped)
    return pd.DataFrame(rows), pd.concat(product_rows, ignore_index=True, sort=False) if product_rows else pd.DataFrame()


def _margin_peak_products(daily: pd.DataFrame, product_daily: pd.DataFrame) -> pd.DataFrame:
    peak_days = daily.sort_values("broker10_margin_to_equity_pct", ascending=False).head(12)[
        [
            "date",
            "account_equity",
            "broker10_margin_to_equity_pct",
            "c3_margin_exact",
            "xsmom_true_margin",
            "c3_active_products",
            "total_net_pnl",
        ]
    ].copy()
    rows: list[pd.DataFrame] = []
    for day in peak_days.itertuples(index=False):
        frame = product_daily[product_daily["date"].eq(pd.Timestamp(day.date))].copy()
        frame = frame[frame["c3_margin_exact"].gt(0.0)].sort_values("c3_margin_exact", ascending=False).head(6)
        if frame.empty:
            continue
        frame["event_date"] = pd.Timestamp(day.date)
        frame["event_broker10_margin_pct"] = float(day.broker10_margin_to_equity_pct)
        frame["event_account_equity"] = float(day.account_equity)
        frame["event_xsmom_margin"] = float(day.xsmom_true_margin)
        rows.append(frame)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _reference_edge_context(daily: pd.DataFrame, ref: pd.DataFrame) -> dict[str, Any]:
    merged = daily[["date", "total_net_pnl", "account_equity", "broker10_margin_to_equity_pct"]].merge(
        ref, on="date", how="inner", suffixes=("_candidate", "_reference")
    )
    merged["edge_pnl"] = merged["total_net_pnl_candidate"] - merged["total_net_pnl_reference"]
    worst_edge = merged.sort_values("edge_pnl").head(10)
    best_edge = merged.sort_values("edge_pnl", ascending=False).head(10)
    return {
        "total_edge_pnl": float(merged["edge_pnl"].sum()),
        "edge_positive_days_pct": float((merged["edge_pnl"] > 0.0).mean() * 100.0),
        "worst_10_edge_pnl_sum": float(worst_edge["edge_pnl"].sum()),
        "best_10_edge_pnl_sum": float(best_edge["edge_pnl"].sum()),
        "worst_edge_days": worst_edge[["date", "edge_pnl", "total_net_pnl_candidate", "total_net_pnl_reference"]].to_dict(orient="records"),
        "best_edge_days": best_edge[["date", "edge_pnl", "total_net_pnl_candidate", "total_net_pnl_reference"]].to_dict(orient="records"),
    }


def _decision(
    daily: pd.DataFrame,
    product_summary: pd.DataFrame,
    windows: pd.DataFrame,
    cost_failure: pd.DataFrame,
    ref_context: dict[str, Any],
) -> dict[str, Any]:
    negative = product_summary[product_summary["net_pnl"].lt(0.0)].sort_values("net_pnl")
    positive = product_summary[product_summary["net_pnl"].gt(0.0)].sort_values("net_pnl", ascending=False)
    total_negative = float(negative["net_pnl"].sum())
    top3_loss_share = float(negative.head(3)["net_pnl"].sum() / total_negative * 100.0) if abs(total_negative) > 1e-9 else 0.0
    worst_63 = windows[windows["window_type"].eq("worst_return_63d")]
    worst_126 = windows[windows["window_type"].eq("worst_return_126d")]
    cf3 = cost_failure[cost_failure["cost_label"].eq("3x")]
    label = "candidate_drilldown_survives_no_blacklist"
    if not cf3.empty and float(cf3["max_dd_pct"].iloc[0]) < -40.0:
        label = "candidate_drilldown_3x_cost_is_main_unfinished_risk"
    return {
        "decision": label,
        "candidate": CANDIDATE,
        "top_profit_products": positive.head(8).to_dict(orient="records"),
        "top_loss_products": negative.head(8).to_dict(orient="records"),
        "top3_loss_share_of_total_negative_pct": top3_loss_share,
        "worst_63d": worst_63.to_dict(orient="records"),
        "worst_126d": worst_126.to_dict(orient="records"),
        "cost_3x_failure": cf3.to_dict(orient="records"),
        "reference_edge_context": ref_context,
        "interpretation": "固定候选深复盘，不调参；若继续优化，应先处理3x成本/2021-2022坏窗口，而不是产品黑名单或小数阈值。",
    }


def _plot(
    daily: pd.DataFrame,
    product_summary: pd.DataFrame,
    windows: pd.DataFrame,
    window_products: pd.DataFrame,
    cost_failure: pd.DataFrame,
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    ax_equity, ax_product, ax_window, ax_cost = axes.flatten()

    ax_equity.plot(daily["date"], daily["equity_1x"], label="1x cost", linewidth=1.0, color="#0f766e")
    ax_equity.plot(daily["date"], daily["equity_2x"], label="2x cost", linewidth=0.9, color="#2563eb")
    ax_equity.plot(daily["date"], daily["equity_3x"], label="3x cost", linewidth=0.9, color="#dc2626")
    ax_equity.set_title("候选权益：成本压力")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=8)

    top = product_summary.head(7)
    bottom = product_summary.tail(7)
    bar = pd.concat([bottom, top], ignore_index=True).drop_duplicates("product_vt_symbol")
    colors = ["#dc2626" if value < 0 else "#0f766e" for value in bar["net_pnl"]]
    ax_product.barh(bar["product_vt_symbol"], bar["net_pnl"], color=colors, alpha=0.85)
    ax_product.axvline(0, color="#111827", linewidth=1)
    ax_product.set_title("产品PnL贡献：头尾")
    ax_product.grid(axis="x", alpha=0.25)

    focus = window_products[window_products["window_type"].isin(["worst_return_63d", "worst_return_126d"])].copy()
    focus = focus.sort_values(["window_type", "net_pnl"]).groupby("window_type").head(8)
    if not focus.empty:
        labels = focus["window_type"] + " | " + focus["product_vt_symbol"]
        ax_window.barh(labels, focus["net_pnl"], color=["#dc2626" if v < 0 else "#0f766e" for v in focus["net_pnl"]], alpha=0.85)
        ax_window.axvline(0, color="#111827", linewidth=1)
    ax_window.set_title("最差3/6个月窗口：产品亏损")
    ax_window.grid(axis="x", alpha=0.25)

    dd_frame = daily[["date", "dd_equity_1x", "dd_equity_2x", "dd_equity_3x", "broker10_margin_to_equity_pct"]].copy()
    ax_cost.plot(dd_frame["date"], dd_frame["dd_equity_1x"], label="DD 1x", linewidth=0.9, color="#0f766e")
    ax_cost.plot(dd_frame["date"], dd_frame["dd_equity_2x"], label="DD 2x", linewidth=0.9, color="#2563eb")
    ax_cost.plot(dd_frame["date"], dd_frame["dd_equity_3x"], label="DD 3x", linewidth=0.9, color="#dc2626")
    ax_cost.axhline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_cost.set_title("成本压力回撤")
    ax_cost.grid(alpha=0.25)
    ax_cost.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    product_summary: pd.DataFrame,
    windows: pd.DataFrame,
    window_products: pd.DataFrame,
    margin_peaks: pd.DataFrame,
    cost_failure: pd.DataFrame,
    cost_failure_products: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    top_profit = product_summary.sort_values("net_pnl", ascending=False).head(12)
    top_loss = product_summary.sort_values("net_pnl", ascending=True).head(12)
    worst_products = window_products[window_products["window_type"].isin(["worst_return_63d", "worst_return_126d"])].sort_values(
        ["window_type", "net_pnl"], ascending=[True, True]
    )
    cost3_products = cost_failure_products[cost_failure_products["cost_label"].eq("3x")].sort_values("net_pnl").head(12)
    lines = [
        "# Stage529 Stage526候选深复盘",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 性质：固定候选只读复盘；不改策略、不重跑参数、不使用未来信息。",
        f"- 候选：`{CANDIDATE}`。",
        f"- 决策：`{decision.get('decision', '')}`。",
        "",
        "## 产品贡献 Top/Bottom",
        "",
        "### Top profit",
        "",
        _md_table(top_profit[["product_vt_symbol", "net_pnl", "slippage", "trade_count", "active_days", "max_c3_margin", "pnl_per_1m_margin_day"]]),
        "",
        "### Top loss",
        "",
        _md_table(top_loss[["product_vt_symbol", "net_pnl", "slippage", "trade_count", "active_days", "max_c3_margin", "pnl_per_1m_margin_day"]]),
        "",
        "## 最差窗口",
        "",
        _md_table(windows),
        "",
        "## 最差3/6个月产品归因",
        "",
        _md_table(worst_products[["window_type", "product_vt_symbol", "net_pnl", "slippage", "trade_count", "active_days", "max_c3_margin"]], max_rows=24),
        "",
        "## 3x成本失败窗口",
        "",
        _md_table(cost_failure),
        "",
        "### 3x失败窗口产品归因",
        "",
        _md_table(cost3_products[["product_vt_symbol", "net_pnl", "slippage", "trade_count", "max_c3_margin"]]),
        "",
        "## 保证金峰值产品",
        "",
        _md_table(
            margin_peaks[
                [
                    "event_date",
                    "product_vt_symbol",
                    "c3_margin_exact",
                    "active_contracts",
                    "net_pnl",
                    "event_broker10_margin_pct",
                    "event_xsmom_margin",
                ]
            ],
            max_rows=36,
        ),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    daily = _load_candidate_daily()
    ref = _load_reference_daily()
    positions = _load_candidate_positions(metadata)
    positions = positions[positions["date"].isin(set(daily["date"]))].copy()
    product_daily = _product_daily(positions)
    product_summary = _product_summary(product_daily)
    windows = _rolling_bad_windows(daily)
    window_products = _window_product_attribution(product_daily, windows)
    margin_peaks = _margin_peak_products(daily, product_daily)
    cost_failure, cost_failure_products = _cost_failure(daily, product_daily)
    ref_context = _reference_edge_context(daily, ref)
    decision = _decision(daily, product_summary, windows, cost_failure, ref_context)

    _plot(daily, product_summary, windows, window_products, cost_failure)
    _write_report(product_summary, windows, window_products, margin_peaks, cost_failure, cost_failure_products, decision)

    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(BAD_WINDOW_PATH, index=False, encoding="utf-8-sig")
    window_products.to_csv(WINDOW_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    margin_peaks.to_csv(MARGIN_PEAK_PATH, index=False, encoding="utf-8-sig")
    cost_failure.to_csv(COST_FAILURE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
