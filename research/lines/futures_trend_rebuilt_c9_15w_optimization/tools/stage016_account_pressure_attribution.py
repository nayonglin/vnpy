from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage016"
MODEL_TAG = "stage016_account_pressure_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage016_account_pressure_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage016_account_pressure_attribution"
STAGE013_OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
STAGE015_OUTPUT_DIR = LINE_DIR / "outputs" / "stage015_pilot_confirmation_jd_feasibility"

CURVES_PATH = (
    STAGE013_OUTPUT_DIR
    / "rebuilt_c9_stage013_account_state_pilot_gate_engine_curves_stage013_account_state_pilot_gate_engine_v1.csv"
)
FIXED_WINDOWS_PATH = (
    STAGE013_OUTPUT_DIR
    / "rebuilt_c9_stage013_account_state_pilot_gate_engine_goal_fixed_horizon_windows_stage013_account_state_pilot_gate_engine_v1.csv"
)
WORST_WINDOWS_PATH = (
    STAGE013_OUTPUT_DIR
    / "rebuilt_c9_stage013_account_state_pilot_gate_engine_goal_worst_windows_stage013_account_state_pilot_gate_engine_v1.csv"
)
STAGE015_CLOSED_LOTS_PATH = (
    STAGE015_OUTPUT_DIR
    / "rebuilt_c9_stage015_pilot_confirmation_jd_feasibility_closed_lots_stage015_pilot_confirmation_jd_feasibility_v1.csv"
)

FIXED_START_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fixed_window_start_state_summary_{MODEL_TAG}.csv"
DAILY_FORWARD_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_forward_pressure_summary_{MODEL_TAG}.csv"
WORST_PATH_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_window_pressure_path_detail_{MODEL_TAG}.csv"
WORST_PATH_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_window_pressure_path_summary_{MODEL_TAG}.csv"
ENTRY_PRESSURE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_pressure_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

FOCUS_START = pd.Timestamp("2022-01-01")
FOCUS_END = pd.Timestamp("2023-12-31")
FORWARD_HORIZONS = (63, 126, 252, 366)
WORST_PATH_WINDOWS = (21, 63, 126, 252)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if not isinstance(value, (str, bytes)) and pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_空_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _read_curves() -> pd.DataFrame:
    usecols = [
        "requested_start_month",
        "date",
        "account_equity",
        "broker10_margin_to_equity_pct",
        "drawdown_pct",
        "c3_active_products",
        "c3_active_contracts",
        "net_pnl",
        "holding_pnl",
        "trading_pnl",
        "trade_count",
    ]
    data = pd.read_csv(CURVES_PATH, encoding="utf-8-sig", usecols=usecols, parse_dates=["date"])
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    numeric_cols = [column for column in usecols if column not in {"requested_start_month", "date"}]
    for column in numeric_cols:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
    data = data.sort_values(["requested_start_month", "date"]).reset_index(drop=True)
    frames: list[pd.DataFrame] = []
    for _, group in data.groupby("requested_start_month", sort=True):
        g = group.copy().sort_values("date")
        for window in (5, 21, 63):
            g[f"net_pnl_sum_{window}d"] = g["net_pnl"].rolling(window, min_periods=1).sum()
            g[f"holding_pnl_sum_{window}d"] = g["holding_pnl"].rolling(window, min_periods=1).sum()
            g[f"broker_max_{window}d"] = g["broker10_margin_to_equity_pct"].rolling(window, min_periods=1).max()
            g[f"dd_min_{window}d"] = g["drawdown_pct"].rolling(window, min_periods=1).min()
        frames.append(g)
    return pd.concat(frames, ignore_index=True, sort=False)


def _broker_bucket(value: Any) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "missing"
    number = float(number)
    if number >= 80:
        return "broker_ge80"
    if number >= 70:
        return "broker_70_80"
    if number >= 60:
        return "broker_60_70"
    if number >= 40:
        return "broker_40_60"
    if number > 0:
        return "broker_0_40"
    return "broker_0"


def _drawdown_bucket(value: Any) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "missing"
    number = float(number)
    if number <= -40:
        return "dd_le_-40"
    if number <= -30:
        return "dd_-30_-40"
    if number <= -20:
        return "dd_-20_-30"
    if number <= -10:
        return "dd_-10_-20"
    return "dd_gt_-10"


def _fixed_window_start_state_summary(curves: pd.DataFrame) -> pd.DataFrame:
    fixed = pd.read_csv(FIXED_WINDOWS_PATH, encoding="utf-8-sig", parse_dates=["start_date", "end_date"])
    fixed["source_start_month"] = fixed["source_start_month"].astype(str)
    start = curves.rename(columns={"requested_start_month": "source_start_month", "date": "start_date"})
    merged = fixed.merge(
        start[
            [
                "source_start_month",
                "start_date",
                "broker10_margin_to_equity_pct",
                "drawdown_pct",
                "c3_active_products",
                "c3_active_contracts",
                "net_pnl_sum_21d",
                "net_pnl_sum_63d",
            ]
        ],
        on=["source_start_month", "start_date"],
        how="left",
    )
    merged["start_broker_bucket"] = merged["broker10_margin_to_equity_pct"].map(_broker_bucket)
    merged["start_drawdown_bucket"] = merged["drawdown_pct"].map(_drawdown_bucket)
    merged["active_products_bucket"] = merged["c3_active_products"].map(lambda value: f"active_products_{int(value)}")
    merged["active4_near_peak"] = merged["c3_active_products"].ge(4) & merged["drawdown_pct"].ge(-5)
    merged["active3plus_near_peak_broker20_60"] = (
        merged["c3_active_products"].ge(3)
        & merged["drawdown_pct"].ge(-5)
        & merged["broker10_margin_to_equity_pct"].between(20, 60, inclusive="both")
    )
    rows: list[dict[str, Any]] = []
    for feature in (
        "start_broker_bucket",
        "start_drawdown_bucket",
        "active_products_bucket",
        "active4_near_peak",
        "active3plus_near_peak_broker20_60",
    ):
        for keys, group in merged.groupby(["horizon_days", feature], dropna=False):
            horizon, value = keys
            positive = pd.to_numeric(group["positive_return"], errors="coerce").fillna(0).astype(int)
            returns = pd.to_numeric(group["return_pct"], errors="coerce")
            rows.append(
                {
                    "feature": feature,
                    "feature_value": str(value),
                    "horizon_days": int(horizon),
                    "count": int(len(group)),
                    "negative_count": int(positive.eq(0).sum()),
                    "negative_rate_pct": float(positive.eq(0).mean() * 100.0),
                    "min_return_pct": float(returns.min()),
                    "p10_return_pct": float(returns.quantile(0.10)),
                    "median_return_pct": float(returns.median()),
                    "mean_return_pct": float(returns.mean()),
                    "p90_return_pct": float(returns.quantile(0.90)),
                }
            )
    return pd.DataFrame(rows).sort_values(["feature", "horizon_days", "negative_rate_pct"], ascending=[True, True, False])


def _forward_returns(curves: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, group in curves.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").reset_index(drop=True).copy()
        equity = g["account_equity"].to_numpy(dtype=float)
        for horizon in FORWARD_HORIZONS:
            future = np.full(len(g), np.nan)
            if len(g) > horizon:
                future[:-horizon] = (equity[horizon:] / equity[:-horizon] - 1.0) * 100.0
            g[f"fwd_{horizon}d_return_pct"] = future
        frames.append(g)
    return pd.concat(frames, ignore_index=True, sort=False)


def _daily_forward_summary(curves: pd.DataFrame) -> pd.DataFrame:
    data = _forward_returns(curves)
    conditions = {
        "all_days": lambda df: pd.Series(True, index=df.index),
        "broker_ge80": lambda df: df["broker10_margin_to_equity_pct"].ge(80),
        "broker_ge70": lambda df: df["broker10_margin_to_equity_pct"].ge(70),
        "broker_ge60": lambda df: df["broker10_margin_to_equity_pct"].ge(60),
        "broker_ge60_dd_le_-20": lambda df: df["broker10_margin_to_equity_pct"].ge(60) & df["drawdown_pct"].le(-20),
        "active4_near_peak": lambda df: df["c3_active_products"].ge(4) & df["drawdown_pct"].ge(-5),
        "active3plus_near_peak_broker20_60": lambda df: (
            df["c3_active_products"].ge(3)
            & df["drawdown_pct"].ge(-5)
            & df["broker10_margin_to_equity_pct"].between(20, 60, inclusive="both")
        ),
        "active3plus_21d_loss": lambda df: df["c3_active_products"].ge(3) & df["net_pnl_sum_21d"].lt(0),
        "active3plus_63d_loss": lambda df: df["c3_active_products"].ge(3) & df["net_pnl_sum_63d"].lt(0),
        "broker50_dd10_active3plus": lambda df: (
            df["broker10_margin_to_equity_pct"].ge(50) & df["drawdown_pct"].le(-10) & df["c3_active_products"].ge(3)
        ),
        "stage013_pilot_condition": lambda df: df["drawdown_pct"].le(-30) & df["c3_active_products"].le(1),
    }
    rows: list[dict[str, Any]] = []
    for horizon in FORWARD_HORIZONS:
        ret_col = f"fwd_{horizon}d_return_pct"
        scoped = data.dropna(subset=[ret_col]).copy()
        for name, maker in conditions.items():
            mask = maker(scoped).fillna(False).astype(bool)
            group = scoped[mask]
            if group.empty:
                continue
            ret = pd.to_numeric(group[ret_col], errors="coerce")
            rows.append(
                {
                    "condition": name,
                    "horizon_trading_days": horizon,
                    "count": int(len(group)),
                    "negative_rate_pct": float(ret.lt(0).mean() * 100.0),
                    "min_return_pct": float(ret.min()),
                    "p10_return_pct": float(ret.quantile(0.10)),
                    "median_return_pct": float(ret.median()),
                    "mean_return_pct": float(ret.mean()),
                    "p90_return_pct": float(ret.quantile(0.90)),
                    "median_broker10_pct": float(group["broker10_margin_to_equity_pct"].median()),
                    "median_drawdown_pct": float(group["drawdown_pct"].median()),
                    "median_active_products": float(group["c3_active_products"].median()),
                }
            )
    return pd.DataFrame(rows).sort_values(["horizon_trading_days", "negative_rate_pct"], ascending=[True, False])


def _worst_window_pressure_path(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    worst = pd.read_csv(WORST_WINDOWS_PATH, encoding="utf-8-sig", parse_dates=["start_date", "end_date"]).head(100)
    worst["source_start_month"] = worst["source_start_month"].astype(str)
    rows: list[dict[str, Any]] = []
    for window_id, item in enumerate(worst.itertuples(index=False), start=1):
        group = curves[
            (curves["requested_start_month"].eq(item.source_start_month))
            & (curves["date"].ge(item.start_date))
            & (curves["date"].le(item.end_date))
        ].sort_values("date")
        for first_n in WORST_PATH_WINDOWS:
            segment = group.head(first_n)
            if segment.empty:
                continue
            rows.append(
                {
                    "window_id": window_id,
                    "source_start_month": item.source_start_month,
                    "window_start_date": item.start_date,
                    "window_end_date": item.end_date,
                    "return_pct": float(item.return_pct),
                    "first_trading_days": first_n,
                    "start_broker10_pct": float(segment.iloc[0]["broker10_margin_to_equity_pct"]),
                    "start_drawdown_pct": float(segment.iloc[0]["drawdown_pct"]),
                    "start_active_products": float(segment.iloc[0]["c3_active_products"]),
                    "max_broker10_pct": float(segment["broker10_margin_to_equity_pct"].max()),
                    "min_drawdown_pct": float(segment["drawdown_pct"].min()),
                    "max_active_products": float(segment["c3_active_products"].max()),
                    "sum_net_pnl": float(segment["net_pnl"].sum()),
                    "sum_holding_pnl": float(segment["holding_pnl"].sum()),
                    "last_broker10_pct": float(segment.iloc[-1]["broker10_margin_to_equity_pct"]),
                    "last_drawdown_pct": float(segment.iloc[-1]["drawdown_pct"]),
                }
            )
    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby("first_trading_days", dropna=False)
        .agg(
            window_count=("window_id", "count"),
            median_start_broker10_pct=("start_broker10_pct", "median"),
            median_start_drawdown_pct=("start_drawdown_pct", "median"),
            median_start_active_products=("start_active_products", "median"),
            median_max_broker10_pct=("max_broker10_pct", "median"),
            max_max_broker10_pct=("max_broker10_pct", "max"),
            median_min_drawdown_pct=("min_drawdown_pct", "median"),
            min_min_drawdown_pct=("min_drawdown_pct", "min"),
            median_max_active_products=("max_active_products", "median"),
            median_sum_net_pnl=("sum_net_pnl", "median"),
            median_sum_holding_pnl=("sum_holding_pnl", "median"),
        )
        .reset_index()
    )
    return detail, summary


def _entry_pressure_summary() -> pd.DataFrame:
    data = pd.read_csv(STAGE015_CLOSED_LOTS_PATH, encoding="utf-8-sig", parse_dates=["entry_date", "exit_date"])
    numeric_cols = [
        "portfolio_drawdown_pct",
        "active_positions_before",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_active_count",
        "realized_pnl",
        "r_multiple",
        "selected_volume",
    ]
    for column in numeric_cols:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    data["focus_2022_2023"] = data["entry_date"].between(FOCUS_START, FOCUS_END, inclusive="both")
    conditions = {
        "all_closed_lots": lambda df: pd.Series(True, index=df.index),
        "stage013_pilot_condition": lambda df: df["portfolio_drawdown_pct"].ge(0.30) & df["active_positions_before"].le(1),
        "active3plus_dd_le5pct": lambda df: df["active_positions_before"].ge(3) & df["portfolio_drawdown_pct"].le(0.05),
        "active3plus_dd_le10pct": lambda df: df["active_positions_before"].ge(3) & df["portfolio_drawdown_pct"].le(0.10),
        "active3plus_dd_le5_corr_ge0.3": lambda df: (
            df["active_positions_before"].ge(3)
            & df["portfolio_drawdown_pct"].le(0.05)
            & df["same_direction_correlation_max_corr"].ge(0.3)
        ),
        "active3plus_dd_le5_corr_ge0.6": lambda df: (
            df["active_positions_before"].ge(3)
            & df["portfolio_drawdown_pct"].le(0.05)
            & df["same_direction_correlation_max_corr"].ge(0.6)
        ),
        "active3plus_any_dd_corr_ge0.6": lambda df: (
            df["active_positions_before"].ge(3) & df["same_direction_correlation_max_corr"].ge(0.6)
        ),
    }
    rows: list[dict[str, Any]] = []
    for scope_name, scope_mask in {
        "all_entries": pd.Series(True, index=data.index),
        "focus_2022_2023": data["focus_2022_2023"].fillna(False).astype(bool),
    }.items():
        scoped = data[scope_mask].copy()
        for name, maker in conditions.items():
            group = scoped[maker(scoped).fillna(False).astype(bool)]
            if group.empty:
                continue
            r = pd.to_numeric(group["r_multiple"], errors="coerce")
            rows.append(
                {
                    "scope": scope_name,
                    "condition": name,
                    "count": int(len(group)),
                    "product_count": int(group["product"].nunique()),
                    "entry_year_count": int(group["entry_date"].dt.year.nunique()),
                    "win_rate_pct": float(group["realized_pnl"].gt(0).mean() * 100.0),
                    "total_pnl": float(group["realized_pnl"].sum()),
                    "avg_r": float(r.mean()),
                    "median_r": float(r.median()),
                    "p10_r": float(r.quantile(0.10)),
                    "p90_r": float(r.quantile(0.90)),
                    "selected_volume_sum": float(group["selected_volume"].sum()),
                }
            )
    return pd.DataFrame(rows).sort_values(["scope", "total_pnl"], ascending=[True, True])


def _plot(
    fixed_summary: pd.DataFrame,
    daily_summary: pd.DataFrame,
    worst_summary: pd.DataFrame,
    entry_summary: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), dpi=160)
    ax_active, ax_daily, ax_worst, ax_entry = axes.flatten()

    active = fixed_summary[
        fixed_summary["feature"].eq("active_products_bucket") & fixed_summary["horizon_days"].isin([366, 540])
    ].copy()
    if not active.empty:
        labels = active["horizon_days"].astype(str) + "d " + active["feature_value"].astype(str)
        ax_active.barh(labels.iloc[::-1], active["negative_rate_pct"].iloc[::-1], color="#2563eb", alpha=0.8)
        ax_active.set_title("Fixed windows: negative rate by active product count")
        ax_active.set_xlabel("negative rate %")
        ax_active.grid(axis="x", alpha=0.25)

    daily = daily_summary[daily_summary["horizon_trading_days"].eq(252)].copy()
    keep = [
        "all_days",
        "broker_ge80",
        "broker_ge60",
        "active4_near_peak",
        "active3plus_near_peak_broker20_60",
        "broker50_dd10_active3plus",
        "stage013_pilot_condition",
    ]
    daily = daily[daily["condition"].isin(keep)].copy()
    if not daily.empty:
        ax_daily.barh(daily["condition"].iloc[::-1], daily["negative_rate_pct"].iloc[::-1], color="#f97316", alpha=0.85)
        ax_daily.set_title("Daily state: next 252 trading-day negative rate")
        ax_daily.set_xlabel("negative rate %")
        ax_daily.grid(axis="x", alpha=0.25)

    if not worst_summary.empty:
        ax_worst.plot(
            worst_summary["first_trading_days"],
            worst_summary["median_max_broker10_pct"],
            marker="o",
            color="#7c3aed",
            label="median max broker10",
        )
        ax_worst.plot(
            worst_summary["first_trading_days"],
            -worst_summary["median_min_drawdown_pct"],
            marker="o",
            color="#dc2626",
            label="median abs min drawdown",
        )
        ax_worst.set_title("Top100 worst windows: pressure develops after start")
        ax_worst.set_xlabel("first N trading days")
        ax_worst.legend()
        ax_worst.grid(alpha=0.25)

    entry = entry_summary[entry_summary["scope"].eq("focus_2022_2023")].copy()
    if not entry.empty:
        entry = entry.sort_values("total_pnl").head(8)
        ax_entry.barh(entry["condition"].iloc[::-1], entry["total_pnl"].iloc[::-1], color="#059669", alpha=0.85)
        ax_entry.axvline(0.0, color="#111827", linewidth=0.8)
        ax_entry.set_title("Focus 2022-2023: entry pressure buckets PnL")
        ax_entry.grid(axis="x", alpha=0.25)

    fig.suptitle("Stage016 Account Pressure Attribution", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    plt.close(fig)


def _decision(
    daily_summary: pd.DataFrame,
    worst_summary: pd.DataFrame,
    entry_summary: pd.DataFrame,
) -> dict[str, Any]:
    def row(condition: str, horizon: int) -> dict[str, Any]:
        match = daily_summary[
            daily_summary["condition"].eq(condition) & daily_summary["horizon_trading_days"].eq(horizon)
        ]
        return match.to_dict("records")[0] if not match.empty else {}

    broker80_252 = row("broker_ge80", 252)
    active4_252 = row("active4_near_peak", 252)
    pilot_366 = row("stage013_pilot_condition", 366)
    worst_63 = (
        worst_summary[worst_summary["first_trading_days"].eq(63)].to_dict("records")[0]
        if not worst_summary.empty and worst_summary["first_trading_days"].eq(63).any()
        else {}
    )
    focus_active3_dd10 = entry_summary[
        entry_summary["scope"].eq("focus_2022_2023") & entry_summary["condition"].eq("active3plus_dd_le10pct")
    ]
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage_nature": "readonly_account_pressure_attribution_no_strategy_change",
        "decision": "stage016_pressure_attribution_no_engine_yet",
        "strategy_changed": False,
        "official_live_strategy_changed": False,
        "high_broker80_next252": broker80_252,
        "active4_near_peak_next252": active4_252,
        "stage013_pilot_condition_next366": pilot_366,
        "worst_top100_first63_summary": worst_63,
        "focus_active3_dd_le10_entry_summary": (
            focus_active3_dd10.to_dict("records")[0] if not focus_active3_dd10.empty else {}
        ),
        "judgment": (
            "High broker10 heat is not a clean precursor in Stage013; the remaining worst windows begin near equity highs "
            "with 3-4 active products and only moderate broker10, then pressure develops. Active4-near-peak is a real "
            "risk label but still has large right-tail cost, so it is not yet a trade rule."
        ),
        "next_step": (
            "Do not write a broker80/90 forced deleverage engine. If continuing, test low-degree external regime/volatility "
            "signals or a non-trading survival sleeve; jd.DCE remains small-budget non-overlap only."
        ),
        "output_files": {
            "fixed_start_summary": str(FIXED_START_SUMMARY_PATH),
            "daily_forward_summary": str(DAILY_FORWARD_SUMMARY_PATH),
            "worst_path_detail": str(WORST_PATH_DETAIL_PATH),
            "worst_path_summary": str(WORST_PATH_SUMMARY_PATH),
            "entry_pressure_summary": str(ENTRY_PRESSURE_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    fixed_summary: pd.DataFrame,
    daily_summary: pd.DataFrame,
    worst_summary: pd.DataFrame,
    entry_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    fixed_focus = fixed_summary[
        fixed_summary["feature"].isin(["active_products_bucket", "start_broker_bucket", "start_drawdown_bucket"])
        & fixed_summary["horizon_days"].isin([366, 540])
    ].copy()
    daily_focus = daily_summary[daily_summary["horizon_trading_days"].isin([252, 366])].copy()
    entry_focus = entry_summary[entry_summary["scope"].eq("focus_2022_2023")].copy()
    lines = [
        "# Stage016 Account Pressure Attribution",
        "",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：只读账户压力归因；不改策略、不连接 CTP、不调用下单 API。",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 核心判断",
        "",
        "- `broker10>=80%` 不是 Stage013 剩余左尾的干净前置风险信号；它在样本中极少，且后续 252/366 交易日均未出现负收益。",
        "- 最差窗口的起点通常不是高 broker10，而是权益高位、回撤接近 0、活跃品种 3-4 个、broker10 中等；压力是在窗口开始后 63-126 个交易日内发展出来的。",
        "- `active4_near_peak` 是更像前置的风险标签，但它仍有很强右尾，不能直接写成减仓/禁开规则。",
        "- Stage013 的深回撤低活跃 pilot condition 在 366 日 forward 上反而全为正，说明它更像恢复期保护，而不是剩余左尾的起点。",
        "",
        "## 固定窗口起点状态",
        "",
        _md_table(fixed_focus.head(30)),
        "",
        "## 每日状态 forward return",
        "",
        _md_table(daily_focus.head(30)),
        "",
        "## Top100 最差窗口前段压力路径",
        "",
        _md_table(worst_summary),
        "",
        "## 逐笔 entry 压力桶",
        "",
        _md_table(entry_focus),
        "",
        "## 输出",
        "",
    ]
    for key, path in decision["output_files"].items():
        lines.append(f"- `{key}`：`{path}`")
    lines.extend(
        [
            "",
            "## 反思",
            "",
            "- 过拟合反思：否。本阶段只验证预声明的账户压力形状，并主动保留反证：高 broker10 和 active4 不能直接交易化。",
            "- 继续价值反思：是，但账户压力方向不能再走 broker80/90 强制减仓。下一步更适合引入低自由度外生 regime/volatility 信息，或做非交易层生存线。"
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curves = _read_curves()
    fixed_summary = _fixed_window_start_state_summary(curves)
    daily_summary = _daily_forward_summary(curves)
    worst_detail, worst_summary = _worst_window_pressure_path(curves)
    entry_summary = _entry_pressure_summary()
    decision = _decision(daily_summary, worst_summary, entry_summary)

    fixed_summary.to_csv(FIXED_START_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    daily_summary.to_csv(DAILY_FORWARD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    worst_detail.to_csv(WORST_PATH_DETAIL_PATH, index=False, encoding="utf-8-sig")
    worst_summary.to_csv(WORST_PATH_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    entry_summary.to_csv(ENTRY_PRESSURE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _plot(fixed_summary, daily_summary, worst_summary, entry_summary)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(fixed_summary, daily_summary, worst_summary, entry_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
