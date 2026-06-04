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

MODEL_TAG = "stage564_stage526_cost_elasticity_execution_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage564_stage526_cost_elasticity_execution_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
STAGE537_TAG = "stage537_stage526_segment_lifecycle_audit_v1"
STAGE537_PREFIX = "qmt_roll_stage537_stage526_segment_lifecycle_audit"
CANDIDATE = "r080_pc25_maxpos4"

DAILY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"
POSITIONS_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_positions_{STAGE526_TAG}.csv"
SUMMARY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_summary_{STAGE526_TAG}.csv"
SEGMENTS_IN = OUTPUT_DIR / f"{STAGE537_PREFIX}_segments_{STAGE537_TAG}.csv"

COST_ELASTICITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_elasticity_{MODEL_TAG}.csv"
SEGMENT_COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_segment_cost_by_duration_{MODEL_TAG}.csv"
EVENT_ROW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_event_rows_{MODEL_TAG}.csv"
EVENT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_event_summary_{MODEL_TAG}.csv"
PRODUCT_DAY_EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_day_events_{MODEL_TAG}.csv"
PRODUCT_DAY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_day_event_summary_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_window_monthly_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

BAD_START = pd.Timestamp("2022-03-09")
BAD_END = pd.Timestamp("2022-12-07")
DD40 = -40.0


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"[A-Za-z]+", symbol)
    product = match.group(0) if match else symbol
    return f"{product}.{exchange}"


def _drawdown(equity: pd.Series) -> pd.Series:
    equity = equity.astype(float)
    return (equity / equity.cummax() - 1.0) * 100.0


def _max_dd_window(equity: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    dd = _drawdown(equity)
    trough = pd.Timestamp(dd.idxmin())
    peak = pd.Timestamp(equity.loc[:trough].idxmax())
    return peak, trough, float(dd.loc[trough])


def load_daily() -> pd.DataFrame:
    daily = _read_csv(DAILY_IN)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    daily = daily[daily["variant"].eq(CANDIDATE)].dropna(subset=["date"]).sort_values("date").copy()
    for column in [
        "account_equity",
        "total_net_pnl",
        "total_slippage",
        "trade_count",
        "broker10_margin_to_equity_pct",
        "net_pnl",
        "xsmom_true_daily_pnl",
    ]:
        daily[column] = _num(daily, column)
    daily["cum_slippage"] = daily["total_slippage"].cumsum()
    daily["month"] = daily["date"].dt.to_period("M").astype(str)
    return daily.reset_index(drop=True)


def load_summary_metrics() -> dict[str, float]:
    summary = _read_csv(SUMMARY_IN)
    row = summary[summary["variant"].eq(CANDIDATE)]
    if row.empty:
        return {}
    record = row.iloc[0]
    return {
        "end_equity": float(record.get("end_equity", 0.0)),
        "total_return_pct": float(record.get("total_return_pct", 0.0)),
        "max_dd_pct": float(record.get("max_dd_pct", 0.0)),
        "sharpe": float(record.get("sharpe", 0.0)),
        "ulcer_pct": float(record.get("ulcer_pct", 0.0)),
        "total_slippage": float(record.get("total_slippage", 0.0)),
        "total_trade_count": float(record.get("total_trade_count", 0.0)),
        "nonzero_daily_win_rate_pct": float(record.get("nonzero_daily_win_rate_pct", 0.0)),
    }


def equity_for_cost(daily: pd.DataFrame, cost_multiplier: float) -> pd.Series:
    equity = daily["account_equity"] - (cost_multiplier - 1.0) * daily["cum_slippage"]
    return pd.Series(equity.to_numpy(dtype=float), index=daily["date"])


def build_cost_elasticity(daily: pd.DataFrame) -> tuple[pd.DataFrame, float, float]:
    rows: list[dict[str, Any]] = []
    for cost_multiplier in np.round(np.arange(1.0, 5.0001, 0.25), 2):
        equity = equity_for_cost(daily, float(cost_multiplier))
        peak, trough, max_dd = _max_dd_window(equity)
        rows.append(
            {
                "cost_multiplier": float(cost_multiplier),
                "end_equity": float(equity.iloc[-1]),
                "max_dd_pct": max_dd,
                "peak_date": peak.date().isoformat(),
                "trough_date": trough.date().isoformat(),
                "dd40_pass": int(max_dd >= DD40),
            }
        )
    table = pd.DataFrame(rows)

    lo, hi = 1.0, 5.0
    if _max_dd_window(equity_for_cost(daily, hi))[2] >= DD40:
        critical = hi
    else:
        for _ in range(60):
            mid = (lo + hi) / 2.0
            max_dd = _max_dd_window(equity_for_cost(daily, mid))[2]
            if max_dd >= DD40:
                lo = mid
            else:
                hi = mid
        critical = lo
    reduction_needed_at_3x = max(0.0, (3.0 - critical) / 2.0)
    return table, float(critical), float(reduction_needed_at_3x)


def load_segments() -> pd.DataFrame:
    segments = _read_csv(SEGMENTS_IN)
    for column in ["segment_days", "net_pnl", "holding_pnl", "trading_pnl", "slippage", "trade_count", "trade_days", "overlap_bad_window"]:
        segments[column] = _num(segments, column)
    segments["gross_pnl_before_slippage"] = segments["net_pnl"] + segments["slippage"]
    segments["net_pnl_2x_cost"] = segments["net_pnl"] - segments["slippage"]
    segments["net_pnl_3x_cost"] = segments["net_pnl"] - 2.0 * segments["slippage"]
    segments["cost_turned_negative_1x"] = (segments["gross_pnl_before_slippage"].gt(0) & segments["net_pnl"].lt(0)).astype(int)
    segments["cost_turned_negative_3x"] = (segments["gross_pnl_before_slippage"].gt(0) & segments["net_pnl_3x_cost"].lt(0)).astype(int)
    segments["gross_negative"] = segments["gross_pnl_before_slippage"].lt(0).astype(int)
    return segments


def build_segment_cost(segments: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for scope, frame in [
        ("all", segments),
        ("bad_window_overlap", segments[segments["overlap_bad_window"].eq(1)]),
    ]:
        grouped = (
            frame.groupby("duration_bucket", as_index=False)
            .agg(
                segment_count=("vt_symbol", "count"),
                net_pnl=("net_pnl", "sum"),
                gross_pnl_before_slippage=("gross_pnl_before_slippage", "sum"),
                slippage=("slippage", "sum"),
                extra_cost_3x_vs_1x=("slippage", lambda s: float(s.sum() * 2.0)),
                net_pnl_3x_cost=("net_pnl_3x_cost", "sum"),
                gross_negative_count=("gross_negative", "sum"),
                cost_turned_negative_1x_count=("cost_turned_negative_1x", "sum"),
                cost_turned_negative_3x_count=("cost_turned_negative_3x", "sum"),
                trade_count=("trade_count", "sum"),
                median_net_pnl=("net_pnl", "median"),
            )
            .sort_values("duration_bucket")
        )
        grouped.insert(0, "scope", scope)
        grouped["slippage_to_abs_net_pct"] = grouped["slippage"] / grouped["net_pnl"].abs().replace(0.0, np.nan) * 100.0
        grouped["slippage_to_abs_net_pct"] = grouped["slippage_to_abs_net_pct"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True, sort=False)


def _event_type(start_pos: float, end_pos: float, pos_change: float) -> str:
    if start_pos == 0.0 and end_pos != 0.0:
        return "open"
    if start_pos != 0.0 and end_pos == 0.0:
        return "close"
    if start_pos != 0.0 and end_pos != 0.0 and np.sign(start_pos) != np.sign(end_pos):
        return "reverse"
    if start_pos != 0.0 and end_pos != 0.0 and np.sign(start_pos) == np.sign(end_pos):
        if abs(end_pos) > abs(start_pos):
            return "add"
        if abs(end_pos) < abs(start_pos):
            return "reduce"
        if pos_change != 0.0:
            return "same_size_adjust"
    if start_pos == 0.0 and end_pos == 0.0 and pos_change != 0.0:
        return "intraday_flat"
    return "other_trade"


def load_trade_events() -> pd.DataFrame:
    usecols = [
        "date",
        "vt_symbol",
        "start_pos",
        "end_pos",
        "pos_change",
        "trade_count",
        "turnover",
        "slippage",
        "holding_pnl",
        "trading_pnl",
        "net_pnl",
        "variant",
    ]
    frames: list[pd.DataFrame] = []
    for chunk in pd.read_csv(POSITIONS_IN, usecols=usecols, chunksize=500_000, encoding="utf-8-sig"):
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce").dt.normalize()
        chunk = chunk[chunk["variant"].eq(CANDIDATE)].copy()
        if chunk.empty:
            continue
        for column in ["start_pos", "end_pos", "pos_change", "trade_count", "turnover", "slippage", "holding_pnl", "trading_pnl", "net_pnl"]:
            chunk[column] = _num(chunk, column)
        chunk = chunk[chunk["trade_count"].gt(0.0) | chunk["pos_change"].ne(0.0)].copy()
        if chunk.empty:
            continue
        chunk["product_vt_symbol"] = chunk["vt_symbol"].map(_product_from_contract)
        chunk["event_type"] = [
            _event_type(start, end, change)
            for start, end, change in zip(chunk["start_pos"], chunk["end_pos"], chunk["pos_change"], strict=False)
        ]
        chunk["bad_window"] = chunk["date"].between(BAD_START, BAD_END).astype(int)
        frames.append(chunk)
    if not frames:
        raise RuntimeError("no trade events")
    events = pd.concat(frames, ignore_index=True, sort=False)

    product_day_keys = ["date", "product_vt_symbol"]
    product_day = (
        events.groupby(product_day_keys)
        .agg(
            traded_contracts=("vt_symbol", "nunique"),
            has_open=("event_type", lambda s: int(s.isin(["open", "reverse"]).any())),
            has_close=("event_type", lambda s: int(s.isin(["close", "reverse"]).any())),
            has_add=("event_type", lambda s: int(s.eq("add").any())),
            has_reduce=("event_type", lambda s: int(s.eq("reduce").any())),
        )
        .reset_index()
    )
    product_day["roll_like_product_day"] = (
        product_day["traded_contracts"].gt(1) & product_day["has_open"].eq(1) & product_day["has_close"].eq(1)
    ).astype(int)
    events = events.merge(product_day[product_day_keys + ["traded_contracts", "roll_like_product_day"]], on=product_day_keys, how="left")
    events["event_family"] = np.where(events["roll_like_product_day"].eq(1), "roll_or_contract_switch", events["event_type"])
    return events


def build_event_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for scope, frame in [("all", events), ("bad_window", events[events["bad_window"].eq(1)])]:
        grouped = frame.groupby("event_family", as_index=False).agg(row_count=("vt_symbol", "count"))
        pair_counts = frame.drop_duplicates(["event_family", "date", "product_vt_symbol"]).groupby("event_family").size().rename("product_day_count")
        grouped = grouped.merge(pair_counts.reset_index(), on="event_family", how="left")
        numeric = (
            frame.groupby("event_family", as_index=False)
            .agg(
                trade_count=("trade_count", "sum"),
                slippage=("slippage", "sum"),
                turnover=("turnover", "sum"),
                net_pnl=("net_pnl", "sum"),
                trading_pnl=("trading_pnl", "sum"),
                holding_pnl=("holding_pnl", "sum"),
                avg_abs_pos_change=("pos_change", lambda s: float(s.abs().mean())),
            )
        )
        grouped = grouped.merge(numeric, on="event_family", how="left")
        grouped.insert(0, "scope", scope)
        grouped["slippage_per_trade"] = grouped["slippage"] / grouped["trade_count"].replace(0.0, np.nan)
        grouped["slippage_per_trade"] = grouped["slippage_per_trade"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        rows.append(grouped.sort_values("slippage", ascending=False))
    return pd.concat(rows, ignore_index=True, sort=False)


def classify_product_day(row: pd.Series) -> str:
    if row["roll_like_product_day"]:
        return "roll_or_contract_switch"
    if row["has_open"] and row["has_close"]:
        return "same_product_reverse_or_flip"
    if row["has_open"]:
        return "new_open_day"
    if row["has_close"]:
        return "close_day"
    if row["has_add"] and row["has_reduce"]:
        return "rebalance_day"
    if row["has_add"]:
        return "add_day"
    if row["has_reduce"]:
        return "reduce_day"
    return "other_trade_day"


def build_product_day_events(events: pd.DataFrame) -> pd.DataFrame:
    frame = (
        events.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            traded_contracts=("vt_symbol", "nunique"),
            row_count=("vt_symbol", "count"),
            trade_count=("trade_count", "sum"),
            slippage=("slippage", "sum"),
            turnover=("turnover", "sum"),
            net_pnl=("net_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            has_open=("event_type", lambda s: int(s.isin(["open", "reverse"]).any())),
            has_close=("event_type", lambda s: int(s.isin(["close", "reverse"]).any())),
            has_add=("event_type", lambda s: int(s.eq("add").any())),
            has_reduce=("event_type", lambda s: int(s.eq("reduce").any())),
            bad_window=("bad_window", "max"),
        )
    )
    frame["roll_like_product_day"] = (
        frame["traded_contracts"].gt(1) & frame["has_open"].eq(1) & frame["has_close"].eq(1)
    ).astype(int)
    frame["product_day_type"] = frame.apply(classify_product_day, axis=1)
    return frame


def build_product_day_summary(product_day: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for scope, frame in [("all", product_day), ("bad_window", product_day[product_day["bad_window"].eq(1)])]:
        grouped = (
            frame.groupby("product_day_type", as_index=False)
            .agg(
                product_day_count=("date", "count"),
                trade_count=("trade_count", "sum"),
                slippage=("slippage", "sum"),
                net_pnl=("net_pnl", "sum"),
                trading_pnl=("trading_pnl", "sum"),
                holding_pnl=("holding_pnl", "sum"),
                turnover=("turnover", "sum"),
                avg_traded_contracts=("traded_contracts", "mean"),
            )
            .sort_values("slippage", ascending=False)
        )
        grouped.insert(0, "scope", scope)
        grouped["slippage_per_trade"] = grouped["slippage"] / grouped["trade_count"].replace(0.0, np.nan)
        grouped["slippage_per_trade"] = grouped["slippage_per_trade"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True, sort=False)


def build_bad_window_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    frame = daily[daily["date"].between(BAD_START, BAD_END)].copy()
    frame["is_trade_day"] = frame["trade_count"].gt(0).astype(int)
    frame["negative_day"] = frame["total_net_pnl"].lt(0).astype(int)
    return (
        frame.groupby("month", as_index=False)
        .agg(
            days=("date", "count"),
            total_net_pnl=("total_net_pnl", "sum"),
            c3_net_pnl=("net_pnl", "sum"),
            xsmom_pnl=("xsmom_true_daily_pnl", "sum"),
            total_slippage=("total_slippage", "sum"),
            extra_3x_cost_vs_1x=("total_slippage", lambda s: float(s.sum() * 2.0)),
            trade_count=("trade_count", "sum"),
            trade_days=("is_trade_day", "sum"),
            negative_days=("negative_day", "sum"),
            max_broker10=("broker10_margin_to_equity_pct", "max"),
        )
        .sort_values("month")
    )


def build_gates(
    critical_multiplier: float,
    reduction_needed: float,
    daily: pd.DataFrame,
    segment_cost: pd.DataFrame,
    product_day_summary: pd.DataFrame,
) -> pd.DataFrame:
    bw = daily[daily["date"].between(BAD_START, BAD_END)].copy()
    bw_net = float(bw["total_net_pnl"].sum())
    bw_slip = float(bw["total_slippage"].sum())
    extra_cost_3x = bw_slip * 2.0
    cost_share_of_window_loss = extra_cost_3x / abs(bw_net) * 100.0 if bw_net < 0 else 0.0

    all_duration = segment_cost[segment_cost["scope"].eq("all")]
    short = all_duration[all_duration["duration_bucket"].eq("1-3")]
    mid = all_duration[all_duration["duration_bucket"].isin(["6-10", "11-20", "21-60"])]
    short_gross = float(short["gross_pnl_before_slippage"].sum()) if not short.empty else 0.0
    mid_net = float(mid["net_pnl"].sum()) if not mid.empty else 0.0
    cost_turned_3x = int(all_duration["cost_turned_negative_3x_count"].sum())

    all_pd = product_day_summary[product_day_summary["scope"].eq("all")]
    total_slip = float(all_pd["slippage"].sum())
    roll_slip = float(all_pd.loc[all_pd["product_day_type"].eq("roll_or_contract_switch"), "slippage"].sum())
    roll_slip_share = roll_slip / total_slip * 100.0 if total_slip else 0.0

    rows = [
        {
            "gate": "3x_cost_dd40_not_passed",
            "description": "3x成本是否仍然穿DD40",
            "actual": f"critical_multiplier={critical_multiplier:.4f}, 3x reduction needed={reduction_needed * 100:.2f}%",
            "threshold": "critical multiplier >= 3.0",
            "passed": int(critical_multiplier >= 3.0),
        },
        {
            "gate": "cost_is_not_primary_loss_driver",
            "description": "坏窗口额外成本占窗口亏损是否只是次要项",
            "actual": f"extra_cost_3x={extra_cost_3x:.0f}, window_net={bw_net:.0f}, share={cost_share_of_window_loss:.2f}%",
            "threshold": "extra 3x cost share < 20%",
            "passed": int(cost_share_of_window_loss < 20.0),
        },
        {
            "gate": "short_duration_loss_not_cost_only",
            "description": "1-3天段亏损是否在加回滑点后仍明显为负",
            "actual": f"1-3d gross pnl before slippage={short_gross:.0f}",
            "threshold": "1-3d gross pnl < 0",
            "passed": int(short_gross < 0.0),
        },
        {
            "gate": "right_tail_at_risk_from_broad_trade_buffer",
            "description": "6天以后持仓是否贡献主要右尾，宽泛buffer可能误伤",
            "actual": f"6-60d net pnl={mid_net:.0f}",
            "threshold": "6-60d net pnl > 0",
            "passed": int(mid_net > 0.0),
        },
        {
            "gate": "roll_cost_not_dominant",
            "description": "换月/合约切换成本是否不是总成本主因",
            "actual": f"roll/switch slippage share={roll_slip_share:.2f}%",
            "threshold": "roll/switch slippage share < 50%",
            "passed": int(roll_slip_share < 50.0),
        },
        {
            "gate": "cost_turns_few_gross_winners_negative",
            "description": "成本是否只把少量gross赢家变成亏损",
            "actual": f"3x cost-turned-negative segments={cost_turned_3x}",
            "threshold": "<= 20 segments",
            "passed": int(cost_turned_3x <= 20),
        },
    ]
    return pd.DataFrame(rows)


def write_chart(
    cost_elasticity: pd.DataFrame,
    critical_multiplier: float,
    segment_cost: pd.DataFrame,
    product_day_summary: pd.DataFrame,
    monthly: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    ax = axes[0, 0]
    ax.plot(cost_elasticity["cost_multiplier"], cost_elasticity["max_dd_pct"], marker="o", color="#2563eb")
    ax.axhline(DD40, color="#dc2626", linestyle="--", linewidth=1)
    ax.axvline(critical_multiplier, color="#f97316", linestyle="--", linewidth=1)
    ax.set_title("Cost multiplier elasticity")
    ax.set_xlabel("cost multiplier")
    ax.set_ylabel("max drawdown %")
    ax.grid(alpha=0.2)

    ax = axes[0, 1]
    duration = segment_cost[segment_cost["scope"].eq("all")].copy()
    order = ["1-3", "4-5", "6-10", "11-20", "21-60", "60+"]
    duration["duration_bucket"] = pd.Categorical(duration["duration_bucket"], categories=order, ordered=True)
    duration = duration.sort_values("duration_bucket")
    x = np.arange(len(duration))
    width = 0.26
    ax.bar(x - width, duration["gross_pnl_before_slippage"], width=width, label="gross before slippage", color="#94a3b8")
    ax.bar(x, duration["net_pnl"], width=width, label="1x net", color="#16a34a")
    ax.bar(x + width, duration["net_pnl_3x_cost"], width=width, label="3x net", color="#dc2626")
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(duration["duration_bucket"].astype(str))
    ax.set_title("Duration buckets: cost does not explain the left tail")
    ax.set_ylabel("PnL")
    ax.legend(fontsize=8)

    ax = axes[1, 0]
    events = product_day_summary[product_day_summary["scope"].eq("all")].sort_values("slippage", ascending=True)
    colors = np.where(events["net_pnl"] >= 0, "#16a34a", "#dc2626")
    ax.barh(events["product_day_type"], events["slippage"], color="#2563eb", alpha=0.75, label="slippage")
    ax2 = ax.twiny()
    ax2.scatter(events["net_pnl"], events["product_day_type"], color=colors, label="net pnl", zorder=3)
    ax.set_title("Execution events: cost concentration by product-day")
    ax.set_xlabel("slippage")
    ax2.set_xlabel("net pnl")

    ax = axes[1, 1]
    x = np.arange(len(monthly))
    ax.bar(x, monthly["total_net_pnl"], color=np.where(monthly["total_net_pnl"] >= 0, "#16a34a", "#dc2626"), label="net pnl")
    ax.bar(x, -monthly["extra_3x_cost_vs_1x"], color="#f97316", alpha=0.65, label="extra 3x cost vs 1x")
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(monthly["month"], rotation=30)
    ax.set_title("Bad window bridge: path loss dominates extra cost")
    ax.set_ylabel("PnL / extra cost")
    ax.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def write_report(summary: pd.DataFrame, gates: pd.DataFrame, cost_elasticity: pd.DataFrame, segment_cost: pd.DataFrame, product_day_summary: pd.DataFrame) -> None:
    text = f"""# Stage564 Stage526 Cost Elasticity / Execution Audit

生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Decision

`execution_cost_monitor_needed_no_trade_buffer_not_promoted`

## Key Summary

{summary.to_markdown(index=False)}

## Gates

{gates.to_markdown(index=False)}

## Cost Elasticity

{cost_elasticity.head(12).to_markdown(index=False)}

## Segment Cost By Duration

{segment_cost[segment_cost['scope'].eq('all')].to_markdown(index=False)}

## Product-Day Event Summary

{product_day_summary[product_day_summary['scope'].eq('all')].to_markdown(index=False)}

## Outputs

- chart: `{CHART_PATH}`
- decision: `{DECISION_PATH}`
- cost elasticity: `{COST_ELASTICITY_PATH}`
- segment cost: `{SEGMENT_COST_PATH}`
- product-day event summary: `{PRODUCT_DAY_SUMMARY_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    daily = load_daily()
    metrics = load_summary_metrics()
    cost_elasticity, critical_multiplier, reduction_needed = build_cost_elasticity(daily)
    segments = load_segments()
    segment_cost = build_segment_cost(segments)
    events = load_trade_events()
    event_summary = build_event_summary(events)
    product_day = build_product_day_events(events)
    product_day_summary = build_product_day_summary(product_day)
    monthly = build_bad_window_monthly(daily)
    gates = build_gates(critical_multiplier, reduction_needed, daily, segment_cost, product_day_summary)

    bw = daily[daily["date"].between(BAD_START, BAD_END)].copy()
    bw_net = float(bw["total_net_pnl"].sum())
    bw_slip = float(bw["total_slippage"].sum())
    all_duration = segment_cost[segment_cost["scope"].eq("all")]
    short = all_duration[all_duration["duration_bucket"].eq("1-3")]
    mid = all_duration[all_duration["duration_bucket"].isin(["6-10", "11-20", "21-60"])]
    total_product_day_slip = float(product_day_summary[product_day_summary["scope"].eq("all")]["slippage"].sum())
    roll_slip = float(product_day_summary[
        product_day_summary["scope"].eq("all") & product_day_summary["product_day_type"].eq("roll_or_contract_switch")
    ]["slippage"].sum())
    summary = pd.DataFrame(
        [
            {"metric": "stage526_end_equity", "value": metrics.get("end_equity", np.nan), "note": "Stage526 normal-cost candidate"},
            {"metric": "stage526_total_return_pct", "value": metrics.get("total_return_pct", np.nan), "note": "normal-cost total return"},
            {"metric": "stage526_max_dd_pct", "value": metrics.get("max_dd_pct", np.nan), "note": "normal-cost max drawdown"},
            {"metric": "stage526_sharpe", "value": metrics.get("sharpe", np.nan), "note": "normal-cost Sharpe"},
            {"metric": "stage526_total_slippage", "value": metrics.get("total_slippage", np.nan), "note": "normal-cost total slippage"},
            {"metric": "stage526_total_trade_count", "value": metrics.get("total_trade_count", np.nan), "note": "normal-cost total trades"},
            {"metric": "critical_cost_multiplier_for_dd40", "value": critical_multiplier, "note": "highest multiplier before max DD breaches 40"},
            {"metric": "slippage_reduction_needed_at_3x_pct", "value": reduction_needed * 100.0, "note": "3x cost must be reduced to effective critical multiplier"},
            {"metric": "bad_window_total_net_pnl", "value": bw_net, "note": "2022-03-09 to 2022-12-07"},
            {"metric": "bad_window_extra_3x_cost_vs_1x", "value": bw_slip * 2.0, "note": "extra cost under 3x vs 1x in bad window"},
            {"metric": "short_1_3d_gross_pnl_before_slippage", "value": float(short["gross_pnl_before_slippage"].sum()) if not short.empty else 0.0, "note": "cost addback test"},
            {"metric": "duration_6_60d_net_pnl", "value": float(mid["net_pnl"].sum()) if not mid.empty else 0.0, "note": "right-tail at risk"},
            {"metric": "roll_switch_slippage_share_pct", "value": roll_slip / total_product_day_slip * 100.0 if total_product_day_slip else 0.0, "note": "roll/switch slippage share"},
            {"metric": "passed_gate_count", "value": int(gates["passed"].sum()), "note": "diagnostic gates passed"},
            {"metric": "failed_gate_count", "value": int(len(gates) - gates["passed"].sum()), "note": "diagnostic gates failed"},
        ]
    )

    cost_elasticity.to_csv(COST_ELASTICITY_PATH, index=False, encoding="utf-8-sig")
    segment_cost.to_csv(SEGMENT_COST_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_ROW_PATH, index=False, encoding="utf-8-sig")
    event_summary.to_csv(EVENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_day.to_csv(PRODUCT_DAY_EVENT_PATH, index=False, encoding="utf-8-sig")
    product_day_summary.to_csv(PRODUCT_DAY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    write_chart(cost_elasticity, critical_multiplier, segment_cost, product_day_summary, monthly)
    write_report(summary, gates, cost_elasticity, segment_cost, product_day_summary)

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "execution_cost_monitor_needed_no_trade_buffer_not_promoted",
        "critical_cost_multiplier_for_dd40": critical_multiplier,
        "slippage_reduction_needed_at_3x_pct": reduction_needed * 100.0,
        "bad_window_total_net_pnl": bw_net,
        "bad_window_extra_3x_cost_vs_1x": bw_slip * 2.0,
        "passed_gate_count": int(gates["passed"].sum()),
        "failed_gate_count": int(len(gates) - gates["passed"].sum()),
        "gates": gates.to_dict(orient="records"),
        "outputs": {
            "cost_elasticity": str(COST_ELASTICITY_PATH),
            "segment_cost": str(SEGMENT_COST_PATH),
            "event_rows": str(EVENT_ROW_PATH),
            "event_summary": str(EVENT_SUMMARY_PATH),
            "product_day_events": str(PRODUCT_DAY_EVENT_PATH),
            "product_day_summary": str(PRODUCT_DAY_SUMMARY_PATH),
            "monthly": str(MONTHLY_PATH),
            "gates": str(GATE_PATH),
            "summary": str(SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
