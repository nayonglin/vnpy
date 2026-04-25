from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_ai_product_suitability_walkforward import product_from_contract


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "fu_satellite_tail_2026_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_tail_2026_attribution"

SATELLITE_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal"
BASE_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal"

TAIL_START: pd.Timestamp = pd.Timestamp("2026-01-01")
SATELLITE_PRODUCT: str = "fu.SHFE"

SATELLITE_DAILY_PATH: Path = OUTPUT_DIR / f"{SATELLITE_PREFIX}_daily.csv"
BASE_DAILY_PATH: Path = OUTPUT_DIR / f"{BASE_PREFIX}_daily.csv"
SATELLITE_POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{SATELLITE_PREFIX}_position_changes_2020_2026_04.csv"
BASE_POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{BASE_PREFIX}_position_changes_2020_2026_04.csv"
SATELLITE_ENTRY_SNAPSHOTS_PATH: Path = OUTPUT_DIR / f"{SATELLITE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
BASE_ENTRY_SNAPSHOTS_PATH: Path = OUTPUT_DIR / f"{BASE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
SATELLITE_TRADES_PATH: Path = OUTPUT_DIR / f"{SATELLITE_PREFIX}_trades_2020_2026_04.csv"

PRODUCT_ATTRIBUTION_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_attribution_{MODEL_TAG}.csv"
MONTHLY_ATTRIBUTION_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_attribution_{MODEL_TAG}.csv"
WORST_DAYS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_days_{MODEL_TAG}.csv"
ENTRY_BREAKDOWN_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_breakdown_{MODEL_TAG}.csv"
ENTRY_COMPARISON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_comparison_vs_ai_top8_{MODEL_TAG}.csv"
OPENED_ENTRIES_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_opened_entries_{MODEL_TAG}.csv"
OPENED_ENTRY_EVENT_COMPARISON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_opened_entry_event_comparison_vs_ai_top8_{MODEL_TAG}.csv"
TRADE_BREAKDOWN_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_breakdown_{MODEL_TAG}.csv"
DAILY_COMPARISON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_comparison_vs_ai_top8_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


POSITION_COLUMNS: tuple[str, ...] = (
    "date",
    "vt_symbol",
    "start_pos",
    "end_pos",
    "pos_change",
    "trade_count",
    "turnover",
    "commission",
    "slippage",
    "holding_pnl",
    "trading_pnl",
    "total_pnl",
    "net_pnl",
)

ENTRY_COLUMNS: tuple[str, ...] = (
    "date",
    "product_vt_symbol",
    "contract_vt_symbol",
    "entry_context",
    "direction",
    "signal",
    "candidate_status",
    "skip_reason",
    "estimated_equity",
    "risk_ratio",
    "risk_multiplier",
    "selected_volume",
    "selected_volume_ungated",
    "portfolio_drawdown_pct",
    "same_direction_correlation_active_count",
    "same_direction_correlation_max_corr",
    "selection_pairwise_score",
    "selection_pairwise_rank",
    "selection_pairwise_volume_tilt_applied",
    "selection_pairwise_volume_tilt_multiplier",
    "ai_product_pool_allowed",
    "ai_product_pool_signal_date",
    "ai_product_pool_score",
    "ai_product_pool_rank",
    "ai_product_pool_top_n",
    "active_positions_before",
    "remaining_position_slots",
    "bullish_alignment",
    "bearish_alignment",
    "breakout",
    "rsi_value",
    "is_opened",
    "loss_streak",
)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _safe_divide(numerator: float, denominator: float) -> float:
    if abs(denominator) <= 1e-12:
        return 0.0
    return float(numerator / denominator)


def _numeric_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default)


def _load_required_csv(path: Path, *, usecols: tuple[str, ...] | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    if usecols is None:
        return pd.read_csv(path)
    return pd.read_csv(path, usecols=lambda column: column in set(usecols))


def _format_money(value: float) -> str:
    return f"{value:,.0f}"


def _format_pct(value: float) -> str:
    return f"{value:.2%}"


def _format_product_losses(group: pd.DataFrame, limit: int = 3) -> str:
    losses = group[group["net_pnl"] < 0.0].sort_values("net_pnl").head(limit)
    return "; ".join(f"{row.product_vt_symbol}:{row.net_pnl:,.0f}" for row in losses.itertuples(index=False))


def load_strategy_daily(path: Path) -> pd.DataFrame:
    df = _load_required_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in ("trade_count", "turnover", "commission", "slippage", "trading_pnl", "holding_pnl", "total_pnl", "net_pnl", "balance", "drawdown", "ddpercent"):
        df[column] = _numeric_series(df, column)
    return df.sort_values("date").reset_index(drop=True)


def summarize_strategy_period(daily: pd.DataFrame, start: pd.Timestamp) -> dict[str, Any]:
    daily = daily.sort_values("date").reset_index(drop=True)
    period = daily[daily["date"] >= start].copy()
    if period.empty:
        return {}

    previous = daily[daily["date"] < start].tail(1)
    start_balance = float(previous["balance"].iloc[0]) if not previous.empty else float(period["balance"].iloc[0] - period["net_pnl"].iloc[0])
    balances = pd.concat([pd.Series([start_balance]), period["balance"].reset_index(drop=True)], ignore_index=True)
    highlevel = balances.cummax()
    drawdown = balances - highlevel
    ddpercent = drawdown / highlevel.replace(0.0, np.nan)

    return {
        "start_date": str(period["date"].min().date()),
        "end_date": str(period["date"].max().date()),
        "start_balance": start_balance,
        "end_balance": float(period["balance"].iloc[-1]),
        "net_pnl": float(period["net_pnl"].sum()),
        "return_pct": _safe_divide(float(period["balance"].iloc[-1]) - start_balance, start_balance),
        "max_drawdown": float(drawdown.min()),
        "max_ddpercent": float(ddpercent.min()) if ddpercent.notna().any() else 0.0,
        "trade_count": int(round(float(period["trade_count"].sum()))),
        "slippage": float(period["slippage"].sum()),
        "worst_day": str(period.loc[period["net_pnl"].idxmin(), "date"].date()),
        "worst_day_net_pnl": float(period["net_pnl"].min()),
        "best_day": str(period.loc[period["net_pnl"].idxmax(), "date"].date()),
        "best_day_net_pnl": float(period["net_pnl"].max()),
    }


def load_product_daily(path: Path) -> pd.DataFrame:
    df = _load_required_csv(path, usecols=POSITION_COLUMNS)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["product_vt_symbol"] = df["vt_symbol"].map(product_from_contract)
    for column in POSITION_COLUMNS:
        if column not in {"date", "vt_symbol"}:
            df[column] = _numeric_series(df, column)
    df["abs_end_pos"] = df["end_pos"].abs()
    df["abs_pos_change"] = df["pos_change"].abs()
    df["active_flag"] = ((df["abs_end_pos"] > 0.0) | (df["trade_count"] > 0.0) | (df["net_pnl"] != 0.0)).astype("float64")
    grouped = (
        df.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            total_pnl=("total_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            commission=("commission", "sum"),
            turnover=("turnover", "sum"),
            trade_count=("trade_count", "sum"),
            abs_end_pos=("abs_end_pos", "sum"),
            abs_pos_change=("abs_pos_change", "sum"),
            active_contract_count=("active_flag", "sum"),
        )
        .sort_values(["product_vt_symbol", "date"])
        .reset_index(drop=True)
    )
    return grouped


def _product_drawdown(values: pd.Series) -> float:
    equity = values.cumsum()
    highlevel = pd.concat([pd.Series([0.0]), equity.reset_index(drop=True)], ignore_index=True).cummax()
    drawdown = pd.concat([pd.Series([0.0]), equity.reset_index(drop=True)], ignore_index=True) - highlevel
    return float(drawdown.min())


def summarize_product_attribution(product_daily: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    tail = product_daily[product_daily["date"] >= start].copy()
    if tail.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    total_loss = min(float(tail["net_pnl"].sum()), 0.0)
    for product, group in tail.groupby("product_vt_symbol", sort=False):
        group = group.sort_values("date")
        net_pnl = float(group["net_pnl"].sum())
        trade_count = float(group["trade_count"].sum())
        active_mask = (group["active_contract_count"] > 0.0) | (group["net_pnl"] != 0.0)
        rows.append(
            {
                "product_vt_symbol": product,
                "net_pnl_2026": net_pnl,
                "total_pnl_2026": float(group["total_pnl"].sum()),
                "holding_pnl_2026": float(group["holding_pnl"].sum()),
                "trading_pnl_2026": float(group["trading_pnl"].sum()),
                "slippage_2026": float(group["slippage"].sum()),
                "commission_2026": float(group["commission"].sum()),
                "turnover_2026": float(group["turnover"].sum()),
                "trade_count_2026": int(round(trade_count)),
                "pnl_per_trade_2026": _safe_divide(net_pnl, trade_count),
                "active_days_2026": int(active_mask.sum()),
                "win_days_2026": int((group["net_pnl"] > 0.0).sum()),
                "loss_days_2026": int((group["net_pnl"] < 0.0).sum()),
                "worst_day": str(group.loc[group["net_pnl"].idxmin(), "date"].date()),
                "worst_day_net_pnl": float(group["net_pnl"].min()),
                "best_day": str(group.loc[group["net_pnl"].idxmax(), "date"].date()),
                "best_day_net_pnl": float(group["net_pnl"].max()),
                "product_max_drawdown_2026": _product_drawdown(group["net_pnl"]),
                "loss_share_if_total_loss": _safe_divide(net_pnl, total_loss) if total_loss < 0.0 and net_pnl < 0.0 else 0.0,
            }
        )

    return pd.DataFrame(rows).sort_values(["net_pnl_2026", "product_vt_symbol"]).reset_index(drop=True)


def build_product_comparison(satellite_product_daily: pd.DataFrame, base_product_daily: pd.DataFrame) -> pd.DataFrame:
    satellite = summarize_product_attribution(satellite_product_daily, TAIL_START)
    base = summarize_product_attribution(base_product_daily, TAIL_START)

    satellite = satellite.add_prefix("satellite_").rename(columns={"satellite_product_vt_symbol": "product_vt_symbol"})
    base = base.add_prefix("base_").rename(columns={"base_product_vt_symbol": "product_vt_symbol"})
    comparison = satellite.merge(base, on="product_vt_symbol", how="outer").fillna(0.0)
    for column in ("net_pnl_2026", "trade_count_2026", "slippage_2026", "active_days_2026"):
        comparison[f"delta_{column}"] = comparison[f"satellite_{column}"] - comparison[f"base_{column}"]
    return comparison.sort_values(["delta_net_pnl_2026", "satellite_net_pnl_2026", "product_vt_symbol"]).reset_index(drop=True)


def build_monthly_attribution(product_daily: pd.DataFrame) -> pd.DataFrame:
    tail = product_daily[product_daily["date"] >= TAIL_START].copy()
    tail["month"] = tail["date"].dt.strftime("%Y-%m")
    monthly = (
        tail.groupby(["month", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            active_days=("active_contract_count", lambda values: int((pd.to_numeric(values, errors="coerce") > 0.0).sum())),
            worst_day_net_pnl=("net_pnl", "min"),
            best_day_net_pnl=("net_pnl", "max"),
        )
        .sort_values(["month", "net_pnl", "product_vt_symbol"])
        .reset_index(drop=True)
    )
    monthly["trade_count"] = monthly["trade_count"].round().astype(int)
    return monthly


def build_daily_comparison(satellite_daily: pd.DataFrame, base_daily: pd.DataFrame, satellite_product_daily: pd.DataFrame) -> pd.DataFrame:
    satellite_tail = satellite_daily[satellite_daily["date"] >= TAIL_START].copy()
    base_tail = base_daily[base_daily["date"] >= TAIL_START].copy()
    keep = ["date", "net_pnl", "balance", "drawdown", "ddpercent", "trade_count", "slippage"]
    comparison = satellite_tail[keep].rename(
        columns={column: f"satellite_{column}" for column in keep if column != "date"}
    ).merge(
        base_tail[keep].rename(columns={column: f"base_{column}" for column in keep if column != "date"}),
        on="date",
        how="outer",
    )
    comparison = comparison.sort_values("date").reset_index(drop=True).fillna(0.0)
    comparison["delta_net_pnl"] = comparison["satellite_net_pnl"] - comparison["base_net_pnl"]
    comparison["delta_trade_count"] = comparison["satellite_trade_count"] - comparison["base_trade_count"]
    comparison["delta_slippage"] = comparison["satellite_slippage"] - comparison["base_slippage"]

    product_losses = (
        satellite_product_daily[satellite_product_daily["date"] >= TAIL_START]
        .groupby("date")
        .apply(_format_product_losses, include_groups=False)
        .reset_index(name="top_satellite_product_losses")
    )
    return comparison.merge(product_losses, on="date", how="left")


def build_worst_days(daily_comparison: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    return (
        daily_comparison.sort_values(["satellite_net_pnl", "date"])
        .head(limit)
        .assign(date=lambda df: df["date"].dt.strftime("%Y-%m-%d"))
        .reset_index(drop=True)
    )


def build_entry_breakdown() -> tuple[pd.DataFrame, pd.DataFrame]:
    snapshots = _load_entry_snapshots(SATELLITE_ENTRY_SNAPSHOTS_PATH)
    if snapshots.empty:
        return pd.DataFrame(), pd.DataFrame()

    breakdown = (
        snapshots.groupby("product_vt_symbol", as_index=False)
        .agg(
            candidate_rows=("product_vt_symbol", "size"),
            opened_entries=("opened_flag", "sum"),
            skipped_rows=("skipped_flag", "sum"),
            ai_allowed_rate=("ai_product_pool_allowed", "mean"),
            avg_ai_rank=("ai_product_pool_rank", "mean"),
            avg_ai_score=("ai_product_pool_score", "mean"),
            avg_pairwise_rank=("selection_pairwise_rank", "mean"),
            avg_pairwise_score=("selection_pairwise_score", "mean"),
            avg_risk_multiplier=("risk_multiplier", "mean"),
            avg_loss_streak=("loss_streak", "mean"),
            avg_selected_volume=("selected_volume", "mean"),
            avg_active_positions_before=("active_positions_before", "mean"),
            avg_remaining_position_slots=("remaining_position_slots", "mean"),
            avg_portfolio_drawdown_pct=("portfolio_drawdown_pct", "mean"),
            avg_same_direction_max_corr=("same_direction_correlation_max_corr", "mean"),
            satellite_flag=("satellite_flag", "max"),
        )
        .sort_values(["opened_entries", "candidate_rows", "product_vt_symbol"], ascending=[False, False, True])
        .reset_index(drop=True)
    )

    opened_columns = [
        "date",
        "product_vt_symbol",
        "contract_vt_symbol",
        "direction",
        "signal",
        "entry_context",
        "estimated_equity",
        "risk_ratio",
        "risk_multiplier",
        "selected_volume",
        "portfolio_drawdown_pct",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
        "selection_pairwise_score",
        "selection_pairwise_rank",
        "ai_product_pool_allowed",
        "ai_product_pool_signal_date",
        "ai_product_pool_score",
        "ai_product_pool_rank",
        "active_positions_before",
        "remaining_position_slots",
        "rsi_value",
        "loss_streak",
    ]
    opened = snapshots[snapshots["opened_flag"] > 0].copy()
    opened = opened[opened_columns].sort_values(["date", "product_vt_symbol"]).reset_index(drop=True)
    opened["date"] = opened["date"].dt.strftime("%Y-%m-%d")
    return breakdown, opened


def _load_entry_snapshots(path: Path, *, variant: str | None = None) -> pd.DataFrame:
    snapshots = _load_required_csv(path, usecols=ENTRY_COLUMNS)
    snapshots["date"] = pd.to_datetime(snapshots["date"]).dt.normalize()
    snapshots = snapshots[snapshots["date"] >= TAIL_START].copy()
    if snapshots.empty:
        return snapshots

    for column in (
        "estimated_equity",
        "risk_ratio",
        "risk_multiplier",
        "selected_volume",
        "selected_volume_ungated",
        "portfolio_drawdown_pct",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
        "selection_pairwise_score",
        "selection_pairwise_rank",
        "selection_pairwise_volume_tilt_applied",
        "selection_pairwise_volume_tilt_multiplier",
        "ai_product_pool_allowed",
        "ai_product_pool_score",
        "ai_product_pool_rank",
        "active_positions_before",
        "remaining_position_slots",
        "rsi_value",
        "is_opened",
        "loss_streak",
    ):
        snapshots[column] = _numeric_series(snapshots, column)
    snapshots["opened_flag"] = ((snapshots["candidate_status"].astype(str) == "opened") | (snapshots["is_opened"] > 0.0)).astype(int)
    snapshots["skipped_flag"] = (snapshots["candidate_status"].astype(str) != "opened").astype(int)
    snapshots["satellite_flag"] = (snapshots["product_vt_symbol"].astype(str) == SATELLITE_PRODUCT).astype(int)
    if variant is not None:
        snapshots["variant"] = variant
    return snapshots


def build_entry_comparison(product_comparison: pd.DataFrame) -> pd.DataFrame:
    satellite = _load_entry_snapshots(SATELLITE_ENTRY_SNAPSHOTS_PATH, variant="satellite")
    base = _load_entry_snapshots(BASE_ENTRY_SNAPSHOTS_PATH, variant="base")
    combined = pd.concat([satellite, base], ignore_index=True)
    opened = combined[combined["opened_flag"] > 0].copy()
    if opened.empty:
        return pd.DataFrame()

    grouped = (
        opened.groupby(["variant", "product_vt_symbol"], as_index=False)
        .agg(
            opened_entries=("opened_flag", "sum"),
            selected_volume_sum=("selected_volume", "sum"),
            selected_volume_avg=("selected_volume", "mean"),
            selected_volume_max=("selected_volume", "max"),
            estimated_equity_avg=("estimated_equity", "mean"),
            risk_multiplier_avg=("risk_multiplier", "mean"),
            loss_streak_avg=("loss_streak", "mean"),
            avg_ai_rank=("ai_product_pool_rank", "mean"),
            avg_pairwise_rank=("selection_pairwise_rank", "mean"),
            avg_active_positions_before=("active_positions_before", "mean"),
            avg_remaining_position_slots=("remaining_position_slots", "mean"),
            long_entries=("direction", lambda values: int((values.astype(str) == "long").sum())),
            short_entries=("direction", lambda values: int((values.astype(str) == "short").sum())),
            first_entry_date=("date", "min"),
            last_entry_date=("date", "max"),
        )
    )
    grouped["first_entry_date"] = grouped["first_entry_date"].dt.strftime("%Y-%m-%d")
    grouped["last_entry_date"] = grouped["last_entry_date"].dt.strftime("%Y-%m-%d")

    satellite_group = grouped[grouped["variant"] == "satellite"].drop(columns=["variant"]).add_prefix("satellite_")
    satellite_group = satellite_group.rename(columns={"satellite_product_vt_symbol": "product_vt_symbol"})
    base_group = grouped[grouped["variant"] == "base"].drop(columns=["variant"]).add_prefix("base_")
    base_group = base_group.rename(columns={"base_product_vt_symbol": "product_vt_symbol"})
    comparison = satellite_group.merge(base_group, on="product_vt_symbol", how="outer")

    pnl_columns = [
        "product_vt_symbol",
        "satellite_net_pnl_2026",
        "base_net_pnl_2026",
        "delta_net_pnl_2026",
        "satellite_trade_count_2026",
        "base_trade_count_2026",
        "delta_trade_count_2026",
    ]
    comparison = comparison.merge(product_comparison[pnl_columns], on="product_vt_symbol", how="left")
    comparison = comparison.fillna(0.0)
    for column in (
        "opened_entries",
        "selected_volume_sum",
        "selected_volume_avg",
        "estimated_equity_avg",
        "risk_multiplier_avg",
        "loss_streak_avg",
        "long_entries",
        "short_entries",
    ):
        comparison[f"delta_{column}"] = comparison[f"satellite_{column}"] - comparison[f"base_{column}"]

    return comparison.sort_values(["delta_net_pnl_2026", "product_vt_symbol"]).reset_index(drop=True)


def build_opened_entry_event_comparison() -> pd.DataFrame:
    satellite = _load_entry_snapshots(SATELLITE_ENTRY_SNAPSHOTS_PATH, variant="satellite")
    base = _load_entry_snapshots(BASE_ENTRY_SNAPSHOTS_PATH, variant="base")
    key_columns = ["date", "product_vt_symbol", "contract_vt_symbol", "direction", "signal"]
    metric_columns = [
        "estimated_equity",
        "risk_ratio",
        "risk_multiplier",
        "loss_streak",
        "selected_volume",
        "selected_volume_ungated",
        "portfolio_drawdown_pct",
        "active_positions_before",
        "remaining_position_slots",
        "ai_product_pool_rank",
        "selection_pairwise_rank",
        "same_direction_correlation_max_corr",
    ]

    def opened_frame(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
        opened = df[df["opened_flag"] > 0].copy()
        if opened.empty:
            return pd.DataFrame(columns=key_columns)
        keep = key_columns + metric_columns
        result = opened[keep].copy()
        result = result.rename(columns={column: f"{prefix}_{column}" for column in metric_columns})
        return result

    satellite_opened = opened_frame(satellite, "satellite")
    base_opened = opened_frame(base, "base")
    comparison = satellite_opened.merge(base_opened, on=key_columns, how="outer").sort_values(key_columns).reset_index(drop=True)
    comparison = comparison.fillna(0.0)
    for column in metric_columns:
        comparison[f"delta_{column}"] = comparison[f"satellite_{column}"] - comparison[f"base_{column}"]
    comparison["date"] = comparison["date"].dt.strftime("%Y-%m-%d")
    return comparison


def build_trade_breakdown() -> pd.DataFrame:
    trades = _load_required_csv(SATELLITE_TRADES_PATH)
    trades["date"] = pd.to_datetime(trades["date"]).dt.normalize()
    trades = trades[trades["date"] >= TAIL_START].copy()
    if trades.empty:
        return pd.DataFrame()
    trades["product_vt_symbol"] = trades["vt_symbol"].map(product_from_contract)
    for column in ("volume", "price", "signed_volume"):
        trades[column] = _numeric_series(trades, column)

    return (
        trades.groupby(["product_vt_symbol", "direction", "offset", "exit_reason"], dropna=False, as_index=False)
        .agg(
            trade_rows=("trade_id", "count"),
            volume=("volume", "sum"),
            signed_volume=("signed_volume", "sum"),
            avg_price=("price", "mean"),
            first_trade_date=("date", "min"),
            last_trade_date=("date", "max"),
        )
        .assign(
            first_trade_date=lambda df: df["first_trade_date"].dt.strftime("%Y-%m-%d"),
            last_trade_date=lambda df: df["last_trade_date"].dt.strftime("%Y-%m-%d"),
        )
        .sort_values(["product_vt_symbol", "direction", "offset", "exit_reason"], na_position="last")
        .reset_index(drop=True)
    )


def _top_records(df: pd.DataFrame, value_column: str, count: int = 5, ascending: bool = True) -> list[dict[str, Any]]:
    if df.empty:
        return []
    columns: list[str] = []
    for column in ("product_vt_symbol", value_column, "satellite_net_pnl_2026", "base_net_pnl_2026", "delta_net_pnl_2026"):
        if column in df.columns and column not in columns:
            columns.append(column)
    return df.sort_values(value_column, ascending=ascending).head(count)[columns].to_dict(orient="records")


def build_summary(
    satellite_daily: pd.DataFrame,
    base_daily: pd.DataFrame,
    product_comparison: pd.DataFrame,
    monthly_attribution: pd.DataFrame,
    daily_comparison: pd.DataFrame,
    entry_breakdown: pd.DataFrame,
    entry_comparison: pd.DataFrame,
) -> dict[str, Any]:
    satellite_period = summarize_strategy_period(satellite_daily, TAIL_START)
    base_period = summarize_strategy_period(base_daily, TAIL_START)
    daily_delta_net_pnl = float(daily_comparison["delta_net_pnl"].sum())

    satellite_products = product_comparison.copy()
    fu_row = satellite_products[satellite_products["product_vt_symbol"] == SATELLITE_PRODUCT]
    fu_summary: dict[str, Any] = {}
    if not fu_row.empty:
        row = fu_row.iloc[0]
        fu_summary = {
            "net_pnl_2026": float(row["satellite_net_pnl_2026"]),
            "base_net_pnl_2026": float(row["base_net_pnl_2026"]),
            "delta_net_pnl_2026": float(row["delta_net_pnl_2026"]),
            "trade_count_2026": int(round(float(row["satellite_trade_count_2026"]))),
            "slippage_2026": float(row["satellite_slippage_2026"]),
            "active_days_2026": int(round(float(row["satellite_active_days_2026"]))),
            "worst_day": str(row["satellite_worst_day"]),
            "worst_day_net_pnl": float(row["satellite_worst_day_net_pnl"]),
            "product_max_drawdown_2026": float(row["satellite_product_max_drawdown_2026"]),
        }

    monthly_fu = monthly_attribution[monthly_attribution["product_vt_symbol"] == SATELLITE_PRODUCT].copy()
    if not monthly_fu.empty:
        fu_summary["worst_month"] = str(monthly_fu.sort_values("net_pnl").iloc[0]["month"])
        fu_summary["worst_month_net_pnl"] = float(monthly_fu["net_pnl"].min())
        fu_summary["best_month"] = str(monthly_fu.sort_values("net_pnl", ascending=False).iloc[0]["month"])
        fu_summary["best_month_net_pnl"] = float(monthly_fu["net_pnl"].max())

    total_loss = abs(min(float(satellite_period.get("net_pnl", 0.0)), 0.0))
    fu_loss_share = _safe_divide(abs(min(float(fu_summary.get("net_pnl_2026", 0.0)), 0.0)), total_loss)
    delta_loss = abs(min(daily_delta_net_pnl, 0.0))
    fu_delta_loss_share = _safe_divide(abs(min(float(fu_summary.get("delta_net_pnl_2026", 0.0)), 0.0)), delta_loss)

    return {
        "model_tag": MODEL_TAG,
        "tail_start": str(TAIL_START.date()),
        "satellite_product": SATELLITE_PRODUCT,
        "satellite_period": satellite_period,
        "base_period": base_period,
        "daily_delta_net_pnl_vs_base": daily_delta_net_pnl,
        "daily_delta_trade_count_vs_base": float(daily_comparison["delta_trade_count"].sum()),
        "daily_delta_slippage_vs_base": float(daily_comparison["delta_slippage"].sum()),
        "fu_summary": fu_summary,
        "fu_loss_share_of_satellite_2026_loss": fu_loss_share,
        "fu_delta_loss_share_of_vs_base_2026_loss": fu_delta_loss_share,
        "worst_satellite_products": _top_records(product_comparison, "satellite_net_pnl_2026", count=8, ascending=True),
        "worst_delta_products_vs_base": _top_records(product_comparison, "delta_net_pnl_2026", count=8, ascending=True),
        "best_delta_products_vs_base": _top_records(product_comparison, "delta_net_pnl_2026", count=8, ascending=False),
        "opened_entries_by_product": entry_breakdown[["product_vt_symbol", "opened_entries", "candidate_rows"]].head(12).to_dict(orient="records") if not entry_breakdown.empty else [],
        "opened_entry_delta_by_product": entry_comparison[
            [
                "product_vt_symbol",
                "satellite_opened_entries",
                "base_opened_entries",
                "delta_opened_entries",
                "satellite_selected_volume_sum",
                "base_selected_volume_sum",
                "delta_selected_volume_sum",
                "delta_net_pnl_2026",
            ]
        ]
        .sort_values(["delta_net_pnl_2026", "product_vt_symbol"])
        .head(12)
        .to_dict(orient="records")
        if not entry_comparison.empty
        else [],
    }


def build_report(
    summary: dict[str, Any],
    product_comparison: pd.DataFrame,
    entry_comparison: pd.DataFrame,
    entry_event_comparison: pd.DataFrame,
    worst_days: pd.DataFrame,
) -> str:
    satellite = summary["satellite_period"]
    base = summary["base_period"]
    fu = summary.get("fu_summary", {})

    lines: list[str] = [
        f"# {MODEL_TAG}",
        "",
        "## 结论",
    ]
    delta = _safe_float(summary.get("daily_delta_net_pnl_vs_base"))
    fu_net = _safe_float(fu.get("net_pnl_2026"))
    fu_delta = _safe_float(fu.get("delta_net_pnl_2026"))

    if fu_net >= 0.0:
        lines.append(
            f"- `2026`尾部弱化不是由`{SATELLITE_PRODUCT}`直接亏损导致：该品种自身净贡献为`{_format_money(fu_net)}`。"
        )
    else:
        lines.append(
            f"- `2026`尾部弱化中`{SATELLITE_PRODUCT}`自身亏损为`{_format_money(fu_net)}`，占卫星版本同期亏损约`{_format_pct(_safe_float(summary.get('fu_loss_share_of_satellite_2026_loss')))}`。"
        )
    lines.append(
        f"- 相比原18品种AI Top8，卫星版本`2026`逐日净损益差额为`{_format_money(delta)}`，其中`{SATELLITE_PRODUCT}`差额为`{_format_money(fu_delta)}`。"
    )
    sh_row = product_comparison[product_comparison["product_vt_symbol"] == "SH.CZCE"]
    if not sh_row.empty:
        row = sh_row.iloc[0]
        lines.append(
            f"- 最大负差额来自`SH.CZCE`：卫星版比原AI Top8少`{_format_money(abs(float(row['delta_net_pnl_2026'])))}`，这是继续拆解的主线。"
        )
    lines.append(
        "- 我的判断：如果差额主要来自原池品种被挤出或仓位路径改变，就不能简单给`fu`加硬过滤；应优先约束组合拥挤和插槽占用。"
    )
    lines.extend(
        [
            "",
            "## 2026分段表现",
            "",
            "| 版本 | 起始权益 | 期末权益 | 净损益 | 区间收益 | 最大回撤 | 总滑点 | 总交易次数 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            f"| 卫星版本 | `{_format_money(_safe_float(satellite.get('start_balance')))}` | `{_format_money(_safe_float(satellite.get('end_balance')))}` | `{_format_money(_safe_float(satellite.get('net_pnl')))}` | `{_format_pct(_safe_float(satellite.get('return_pct')))}` | `{_format_pct(_safe_float(satellite.get('max_ddpercent')))}` | `{_format_money(_safe_float(satellite.get('slippage')))}` | `{int(_safe_float(satellite.get('trade_count'))):,}` |",
            f"| 原AI Top8 | `{_format_money(_safe_float(base.get('start_balance')))}` | `{_format_money(_safe_float(base.get('end_balance')))}` | `{_format_money(_safe_float(base.get('net_pnl')))}` | `{_format_pct(_safe_float(base.get('return_pct')))}` | `{_format_pct(_safe_float(base.get('max_ddpercent')))}` | `{_format_money(_safe_float(base.get('slippage')))}` | `{int(_safe_float(base.get('trade_count'))):,}` |",
            "",
            "## `fu.SHFE`卫星",
            "",
            f"- 净损益：`{_format_money(fu_net)}`",
            f"- 相比原AI Top8差额：`{_format_money(fu_delta)}`",
            f"- 交易次数：`{int(_safe_float(fu.get('trade_count_2026'))):,}`",
            f"- 总滑点：`{_format_money(_safe_float(fu.get('slippage_2026')))}`",
            f"- 活跃天数：`{int(_safe_float(fu.get('active_days_2026'))):,}`",
            f"- 最差日：`{fu.get('worst_day', '')}`，净损益`{_format_money(_safe_float(fu.get('worst_day_net_pnl')))}`",
            f"- 最差月：`{fu.get('worst_month', '')}`，净损益`{_format_money(_safe_float(fu.get('worst_month_net_pnl')))}`",
            "",
            "## 2026最差产品差额",
            "",
            "| 品种 | 卫星净损益 | 原AI Top8净损益 | 差额 | 卫星交易次数 | 原交易次数 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for row in product_comparison.sort_values("delta_net_pnl_2026").head(10).itertuples(index=False):
        lines.append(
            f"| `{row.product_vt_symbol}` | `{_format_money(float(row.satellite_net_pnl_2026))}` | `{_format_money(float(row.base_net_pnl_2026))}` | `{_format_money(float(row.delta_net_pnl_2026))}` | `{int(round(float(row.satellite_trade_count_2026))):,}` | `{int(round(float(row.base_trade_count_2026))):,}` |"
        )

    lines.extend(
        [
            "",
            "## 入场差异",
            "",
            "| 品种 | 卫星入场 | 原AI Top8入场 | 入场差 | 卫星手数和 | 原手数和 | 手数差 | PnL差额 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in entry_comparison.sort_values("delta_net_pnl_2026").head(10).itertuples(index=False):
        lines.append(
            f"| `{row.product_vt_symbol}` | `{int(round(float(row.satellite_opened_entries))):,}` | `{int(round(float(row.base_opened_entries))):,}` | `{int(round(float(row.delta_opened_entries))):,}` | `{_format_money(float(row.satellite_selected_volume_sum))}` | `{_format_money(float(row.base_selected_volume_sum))}` | `{_format_money(float(row.delta_selected_volume_sum))}` | `{_format_money(float(row.delta_net_pnl_2026))}` |"
        )

    sh_events = entry_event_comparison[entry_event_comparison["product_vt_symbol"] == "SH.CZCE"].copy()
    if not sh_events.empty:
        lines.extend(
            [
                "",
                "## `SH.CZCE`事件级诊断",
                "",
                "| 日期 | 方向 | 信号 | 卫星手数 | 原手数 | 卫星风险乘数 | 原风险乘数 | 卫星连续亏损 | 原连续亏损 |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in sh_events.itertuples(index=False):
            lines.append(
                f"| `{row.date}` | `{row.direction}` | `{row.signal}` | `{_format_money(float(row.satellite_selected_volume))}` | `{_format_money(float(row.base_selected_volume))}` | `{float(row.satellite_risk_multiplier):.2f}` | `{float(row.base_risk_multiplier):.2f}` | `{int(round(float(row.satellite_loss_streak)))}` | `{int(round(float(row.base_loss_streak)))}` |"
            )

    lines.extend(
        [
            "",
            "## 最差交易日",
            "",
            "| 日期 | 卫星净损益 | 原AI Top8净损益 | 差额 | 卫星回撤 | 主要亏损品种 |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in worst_days.head(10).itertuples(index=False):
        lines.append(
            f"| `{row.date}` | `{_format_money(float(row.satellite_net_pnl))}` | `{_format_money(float(row.base_net_pnl))}` | `{_format_money(float(row.delta_net_pnl))}` | `{float(row.satellite_ddpercent):.2f}%` | `{row.top_satellite_product_losses}` |"
        )

    lines.extend(
        [
            "",
            "## 后续判断",
            "",
            "- 这一轮只做归因，不新增回测结果，也不新增策略过滤参数。",
            "- 若要继续优化，应优先验证“卫星品种占用插槽时是否挤出更优原池品种”，而不是按2026单段亏损直接拟合禁用规则。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    satellite_daily = load_strategy_daily(SATELLITE_DAILY_PATH)
    base_daily = load_strategy_daily(BASE_DAILY_PATH)
    satellite_product_daily = load_product_daily(SATELLITE_POSITION_CHANGES_PATH)
    base_product_daily = load_product_daily(BASE_POSITION_CHANGES_PATH)

    product_comparison = build_product_comparison(satellite_product_daily, base_product_daily)
    monthly_attribution = build_monthly_attribution(satellite_product_daily)
    daily_comparison = build_daily_comparison(satellite_daily, base_daily, satellite_product_daily)
    worst_days = build_worst_days(daily_comparison)
    entry_breakdown, opened_entries = build_entry_breakdown()
    entry_comparison = build_entry_comparison(product_comparison)
    entry_event_comparison = build_opened_entry_event_comparison()
    trade_breakdown = build_trade_breakdown()

    summary = build_summary(
        satellite_daily=satellite_daily,
        base_daily=base_daily,
        product_comparison=product_comparison,
        monthly_attribution=monthly_attribution,
        daily_comparison=daily_comparison,
        entry_breakdown=entry_breakdown,
        entry_comparison=entry_comparison,
    )
    report = build_report(summary, product_comparison, entry_comparison, entry_event_comparison, worst_days)

    product_comparison.to_csv(PRODUCT_ATTRIBUTION_OUTPUT_PATH, index=False)
    monthly_attribution.to_csv(MONTHLY_ATTRIBUTION_OUTPUT_PATH, index=False)
    daily_comparison.assign(date=lambda df: df["date"].dt.strftime("%Y-%m-%d")).to_csv(DAILY_COMPARISON_OUTPUT_PATH, index=False)
    worst_days.to_csv(WORST_DAYS_OUTPUT_PATH, index=False)
    entry_breakdown.to_csv(ENTRY_BREAKDOWN_OUTPUT_PATH, index=False)
    entry_comparison.to_csv(ENTRY_COMPARISON_OUTPUT_PATH, index=False)
    entry_event_comparison.to_csv(OPENED_ENTRY_EVENT_COMPARISON_OUTPUT_PATH, index=False)
    opened_entries.to_csv(OPENED_ENTRIES_OUTPUT_PATH, index=False)
    trade_breakdown.to_csv(TRADE_BREAKDOWN_OUTPUT_PATH, index=False)
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(report, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
