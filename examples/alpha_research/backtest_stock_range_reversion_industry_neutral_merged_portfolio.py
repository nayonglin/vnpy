from __future__ import annotations

import json
import os
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import add_forward_returns, add_price_features
from backtest_stock_range_reversion_market_down_long_only import to_float


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_industry_neutral_merged_portfolio_2018_2026"),
    )
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_industry_neutral_merged_portfolio_v1"

FEATURE: str = "score_oversold_ret_20"
HORIZON: int = 10
COST_BPS: tuple[float, ...] = tuple(float(item) for item in os.getenv("COST_BPS", "20,50").split(",") if item)
INITIAL_EQUITY: float = 1.0
TRADING_DAYS: int = 252
N_GROUPS: int = 5
MIN_INDUSTRY_DAILY_WIDTH: int = 20
MAX_INDUSTRY_WEIGHT_PER_BASKET: float = 0.20
MAX_STOCK_WEIGHT_PER_BASKET: float = 0.05


def pct(value: float) -> str:
    return f"{value:.2%}"


def scenario_definitions() -> list[dict[str, Any]]:
    return [
        {
            "scenario": "all_component_equal_stock",
            "description": "全成分行业内排序，top组按股票等权，不加行业上限",
            "bucket": "all_component",
            "weight_mode": "equal_stock",
        },
        {
            "scenario": "all_component_capped",
            "description": "全成分行业内排序，单行业/单票上限，未用完资金留现金",
            "bucket": "all_component",
            "weight_mode": "capped",
        },
        {
            "scenario": "liquid_q3_capped",
            "description": "成交额和自由换手至少进入前60%，行业内排序后加行业/单票上限",
            "bucket": "liquid_q3",
            "weight_mode": "capped",
        },
        {
            "scenario": "active_q4_q5_capped",
            "description": "成交额和自由换手都在前40%，行业内排序后加行业/单票上限",
            "bucket": "active_q4_q5",
            "weight_mode": "capped",
        },
    ]


def bucket_expr(bucket: str) -> pl.Expr:
    if bucket == "all_component":
        return pl.col("eligible_component_row").fill_null(False)
    if bucket == "liquid_q3":
        return (
            pl.col("eligible_component_row").fill_null(False)
            & (pl.col("adv20_turnover_q") >= 3)
            & (pl.col("turnover_rate_f_q") >= 3)
        )
    if bucket == "active_q4_q5":
        return (
            pl.col("eligible_component_row").fill_null(False)
            & (pl.col("adv20_turnover_q") >= 4)
            & (pl.col("turnover_rate_f_q") >= 4)
        )
    raise ValueError(f"Unknown bucket: {bucket}")


def add_path_columns(df: pl.DataFrame) -> pl.DataFrame:
    work = df.sort(["symbol", "datetime"])
    exprs: list[pl.Expr] = []
    for day in range(1, HORIZON + 1):
        exprs.extend(
            [
                pl.col("datetime").shift(-day).over("symbol").alias(f"start_date_{day}"),
                pl.col("datetime").shift(-(day + 1)).over("symbol").alias(f"pnl_date_{day}"),
                (
                    pl.col("close").shift(-(day + 1)).over("symbol")
                    / pl.col("close").shift(-day).over("symbol")
                    - 1
                ).alias(f"stock_daily_ret_{day}"),
            ]
        )
    return work.with_columns(exprs)


def valid_signal_filter() -> pl.Expr:
    return (
        pl.col(f"final_keep_{HORIZON}")
        & pl.col("industry").is_not_null()
        & pl.col(FEATURE).is_not_null()
        & pl.col(FEATURE).is_finite()
        & pl.col(f"fwd_ret_{HORIZON}").is_not_null()
        & pl.col(f"fwd_ret_{HORIZON}").is_finite()
        & pl.col(f"fwd_excess_ret_{HORIZON}").is_not_null()
        & pl.col(f"fwd_excess_ret_{HORIZON}").is_finite()
    )


def select_industry_neutral_candidates(df: pl.DataFrame, scenario: dict[str, Any]) -> pl.DataFrame:
    work = df.filter(bucket_expr(scenario["bucket"]) & valid_signal_filter())
    if work.is_empty():
        return pl.DataFrame()
    ranked = (
        work.with_columns(
            pl.col(FEATURE).rank("ordinal").over(["datetime", "industry"]).alias("_rank"),
            pl.len().over(["datetime", "industry"]).alias("_industry_width"),
        )
        .filter(pl.col("_industry_width") >= MIN_INDUSTRY_DAILY_WIDTH)
        .with_columns(
            ((((pl.col("_rank") - 1) * N_GROUPS) / pl.col("_industry_width")).floor().cast(pl.Int64) + 1)
            .clip(1, N_GROUPS)
            .alias("feature_group")
        )
        .filter(pl.col("feature_group") == N_GROUPS)
        .with_columns(
            pl.len().over("datetime").alias("candidate_count"),
            pl.col("industry").n_unique().over("datetime").alias("selected_industry_count"),
            pl.len().over(["datetime", "industry"]).alias("selected_industry_stock_count"),
        )
    )

    if scenario["weight_mode"] == "equal_stock":
        weighted = ranked.with_columns((1.0 / pl.col("candidate_count")).alias("basket_weight"))
    else:
        weighted = (
            ranked.with_columns(
                pl.min_horizontal(
                    1.0 / pl.col("selected_industry_count"),
                    pl.lit(MAX_INDUSTRY_WEIGHT_PER_BASKET),
                ).alias("_industry_budget")
            )
            .with_columns(
                pl.min_horizontal(
                    pl.col("_industry_budget") / pl.col("selected_industry_stock_count"),
                    pl.lit(MAX_STOCK_WEIGHT_PER_BASKET),
                ).alias("basket_weight")
            )
            .drop("_industry_budget")
        )

    extra_cols = [
        col
        for col in [
            "industry",
            "market",
            "adv20_turnover",
            "turnover_rate_f",
            "adv20_turnover_q",
            "turnover_rate_f_q",
            "circ_mv",
            "total_mv",
        ]
        if col in weighted.columns
    ]
    return (
        weighted.with_columns(
            pl.col("basket_weight").sum().over("datetime").alias("basket_gross_weight"),
            pl.lit(scenario["scenario"]).alias("scenario"),
            pl.lit(scenario["description"]).alias("scenario_description"),
            pl.lit(scenario["bucket"]).alias("bucket"),
            pl.lit(scenario["weight_mode"]).alias("weight_mode"),
        )
        .select(
            [
                "scenario",
                "scenario_description",
                "bucket",
                "weight_mode",
                "datetime",
                "symbol",
                FEATURE,
                "feature_group",
                "candidate_count",
                "selected_industry_count",
                "selected_industry_stock_count",
                "basket_weight",
                "basket_gross_weight",
                *extra_cols,
                *[f"start_date_{day}" for day in range(1, HORIZON + 1)],
                *[f"pnl_date_{day}" for day in range(1, HORIZON + 1)],
                *[f"stock_daily_ret_{day}" for day in range(1, HORIZON + 1)],
            ]
        )
        .sort(["datetime", "industry", FEATURE])
    )


def build_lots(selected: pl.DataFrame) -> pl.DataFrame:
    parts: list[pl.DataFrame] = []
    extra_cols = [
        col
        for col in [
            "scenario_description",
            "bucket",
            "weight_mode",
            "industry",
            "market",
            "adv20_turnover",
            "turnover_rate_f",
            "adv20_turnover_q",
            "turnover_rate_f_q",
            "circ_mv",
            "total_mv",
            "candidate_count",
            "selected_industry_count",
            "selected_industry_stock_count",
            "basket_gross_weight",
        ]
        if col in selected.columns
    ]
    for day in range(1, HORIZON + 1):
        parts.append(
            selected.select(
                "scenario",
                pl.col("datetime").alias("signal_date"),
                "symbol",
                FEATURE,
                "basket_weight",
                *extra_cols,
                pl.col(f"start_date_{day}").alias("target_date"),
                pl.col(f"pnl_date_{day}").alias("pnl_date"),
                pl.col(f"stock_daily_ret_{day}").alias("stock_daily_ret"),
            )
            .with_columns(
                pl.lit(day).alias("holding_day"),
                (pl.col("basket_weight") / HORIZON).alias("lot_weight"),
            )
            .filter(
                pl.col("target_date").is_not_null()
                & pl.col("pnl_date").is_not_null()
                & pl.col("stock_daily_ret").is_not_null()
                & pl.col("stock_daily_ret").is_finite()
            )
        )
    return pl.concat(parts, how="vertical").sort(["scenario", "target_date", "signal_date", "symbol"])


def build_symbol_daily(lots: pl.DataFrame) -> pl.DataFrame:
    agg_exprs: list[pl.Expr] = [
        pl.col("lot_weight").sum().alias("target_weight"),
        pl.len().alias("active_lots"),
        pl.col("stock_daily_ret").first().alias("stock_daily_ret"),
        pl.col("signal_date").n_unique().alias("source_signal_days"),
        pl.col("holding_day").min().alias("min_holding_day"),
        pl.col("holding_day").max().alias("max_holding_day"),
    ]
    for col in ["industry", "market", "adv20_turnover", "turnover_rate_f", "circ_mv", "total_mv"]:
        if col in lots.columns:
            agg_exprs.append(pl.col(col).first().alias(col))
    return (
        lots.group_by(["scenario", "target_date", "pnl_date", "symbol"])
        .agg(agg_exprs)
        .with_columns((pl.col("target_weight") * pl.col("stock_daily_ret")).alias("weighted_stock_ret"))
        .sort(["scenario", "target_date", "symbol"])
    )


def build_calendar(benchmark_df: pl.DataFrame, min_date: Any, max_date: Any) -> pl.DataFrame:
    return (
        benchmark_df.select(pl.col("datetime").alias("date"))
        .filter((pl.col("date") >= min_date) & (pl.col("date") <= max_date))
        .sort("date")
    )


def build_turnover(symbol_daily: pl.DataFrame, calendar: pl.DataFrame, scenario: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    target_weights = symbol_daily.select("target_date", "symbol", "target_weight").unique(
        subset=["target_date", "symbol"]
    )
    if target_weights.is_empty():
        return pl.DataFrame(), pl.DataFrame()
    symbols = target_weights.select("symbol").unique().sort("symbol")
    grid = calendar.rename({"date": "target_date"}).join(symbols, how="cross")
    full_targets = (
        grid.join(target_weights, on=["target_date", "symbol"], how="left")
        .with_columns(pl.col("target_weight").fill_null(0.0))
        .sort(["symbol", "target_date"])
        .with_columns(pl.col("target_weight").shift(1).over("symbol").fill_null(0.0).alias("prev_target_weight"))
        .with_columns(
            (pl.col("target_weight") - pl.col("prev_target_weight")).alias("target_weight_delta"),
            (pl.col("target_weight") - pl.col("prev_target_weight")).abs().alias("abs_target_weight_delta"),
            pl.lit(scenario).alias("scenario"),
        )
    )
    turnover = (
        full_targets.group_by(["scenario", "target_date"])
        .agg(
            pl.col("abs_target_weight_delta").sum().alias("gross_abs_weight_change"),
            pl.col("target_weight_delta").clip(0).sum().alias("buy_weight"),
            (-pl.col("target_weight_delta").clip(None, 0)).sum().alias("sell_weight"),
            (pl.col("abs_target_weight_delta") / 2).sum().alias("one_way_turnover"),
            (pl.col("target_weight") > 0).sum().alias("target_active_symbols"),
            pl.col("target_weight").sum().alias("target_gross_exposure"),
        )
        .sort(["scenario", "target_date"])
    )
    nonzero_targets = full_targets.filter(pl.col("target_weight") > 0).select(
        "scenario",
        "target_date",
        "symbol",
        "target_weight",
        "target_weight_delta",
        "abs_target_weight_delta",
    )
    return turnover, nonzero_targets


def build_concentration(symbol_daily: pl.DataFrame, calendar: pl.DataFrame, scenario: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    concentration = (
        symbol_daily.group_by("target_date")
        .agg(
            pl.len().alias("active_symbols"),
            pl.col("industry").n_unique().alias("active_industries"),
            pl.col("target_weight").sum().alias("gross_exposure"),
            pl.col("target_weight").max().alias("max_symbol_weight"),
            pl.col("target_weight").sort(descending=True).head(5).sum().alias("top5_symbol_weight"),
            pl.col("target_weight").sort(descending=True).head(10).sum().alias("top10_symbol_weight"),
            (pl.col("target_weight") ** 2).sum().alias("herfindahl"),
            (pl.col("active_lots") > 1).sum().alias("duplicated_symbols"),
            pl.col("active_lots").max().alias("max_symbol_lots"),
        )
        .with_columns(
            (pl.col("gross_exposure") ** 2 / pl.col("herfindahl")).alias("effective_names"),
            (pl.col("duplicated_symbols") / pl.col("active_symbols")).alias("duplicated_symbol_ratio"),
        )
    )
    industry_daily = (
        symbol_daily.group_by(["target_date", "industry"])
        .agg(pl.col("target_weight").sum().alias("industry_weight"))
        .sort(["target_date", "industry_weight"], descending=[False, True])
    )
    industry_concentration = (
        industry_daily.group_by("target_date")
        .agg(
            pl.len().alias("industry_count"),
            pl.col("industry_weight").max().alias("max_industry_weight"),
            pl.col("industry_weight").sort(descending=True).head(3).sum().alias("top3_industry_weight"),
            pl.col("industry_weight").sort(descending=True).head(5).sum().alias("top5_industry_weight"),
        )
        .with_columns(pl.lit(scenario).alias("scenario"))
    )
    filled = (
        calendar.rename({"date": "target_date"})
        .join(concentration, on="target_date", how="left")
        .join(industry_concentration.drop("scenario"), on="target_date", how="left")
        .with_columns(
            pl.col("active_symbols").fill_null(0),
            pl.col("active_industries").fill_null(0),
            pl.col("gross_exposure").fill_null(0.0),
            pl.col("max_symbol_weight").fill_null(0.0),
            pl.col("top5_symbol_weight").fill_null(0.0),
            pl.col("top10_symbol_weight").fill_null(0.0),
            pl.col("herfindahl").fill_null(0.0),
            pl.col("duplicated_symbols").fill_null(0),
            pl.col("max_symbol_lots").fill_null(0),
            pl.col("effective_names").fill_null(0.0),
            pl.col("duplicated_symbol_ratio").fill_null(0.0),
            pl.col("industry_count").fill_null(0),
            pl.col("max_industry_weight").fill_null(0.0),
            pl.col("top3_industry_weight").fill_null(0.0),
            pl.col("top5_industry_weight").fill_null(0.0),
            pl.lit(scenario).alias("scenario"),
        )
        .sort(["scenario", "target_date"])
    )
    return filled, industry_daily.with_columns(pl.lit(scenario).alias("scenario"))


def build_daily_gross(symbol_daily: pl.DataFrame) -> pl.DataFrame:
    return (
        symbol_daily.group_by(["scenario", "pnl_date"])
        .agg(
            pl.col("weighted_stock_ret").sum().alias("strategy_gross_daily_ret"),
            pl.col("target_weight").sum().alias("return_gross_exposure"),
            pl.len().alias("return_active_symbols"),
            pl.col("industry").n_unique().alias("return_active_industries"),
            pl.col("active_lots").sum().alias("return_active_lots"),
        )
        .sort(["scenario", "pnl_date"])
    )


def build_benchmark_daily(benchmark_df: pl.DataFrame) -> pl.DataFrame:
    return (
        benchmark_df.select("datetime", "close")
        .sort("datetime")
        .with_columns((pl.col("close") / pl.col("close").shift(1) - 1).alias("benchmark_daily_ret"))
        .select(pl.col("datetime").alias("date"), "benchmark_daily_ret")
    )


def build_equity_curve(
    scenario: str,
    daily_gross: pl.DataFrame,
    turnover: pl.DataFrame,
    benchmark_daily: pl.DataFrame,
    calendar: pl.DataFrame,
    cost_bps: float,
) -> pl.DataFrame:
    one_way_cost = cost_bps / 2 / 10000.0
    daily = (
        calendar.join(
            daily_gross.filter(pl.col("scenario") == scenario).drop("scenario").rename({"pnl_date": "date"}),
            on="date",
            how="left",
        )
        .join(
            turnover.filter(pl.col("scenario") == scenario).drop("scenario").rename({"target_date": "date"}),
            on="date",
            how="left",
        )
        .join(benchmark_daily, on="date", how="left")
        .with_columns(
            pl.col("strategy_gross_daily_ret").fill_null(0.0),
            pl.col("return_gross_exposure").fill_null(0.0),
            pl.col("return_active_symbols").fill_null(0),
            pl.col("return_active_industries").fill_null(0),
            pl.col("return_active_lots").fill_null(0),
            pl.col("gross_abs_weight_change").fill_null(0.0),
            pl.col("buy_weight").fill_null(0.0),
            pl.col("sell_weight").fill_null(0.0),
            pl.col("one_way_turnover").fill_null(0.0),
            pl.col("target_active_symbols").fill_null(0),
            pl.col("target_gross_exposure").fill_null(0.0),
            pl.col("benchmark_daily_ret").fill_null(0.0),
        )
        .with_columns(
            (pl.col("gross_abs_weight_change") * one_way_cost).alias("turnover_cost_ret"),
            (pl.col("benchmark_daily_ret") * pl.col("return_gross_exposure")).alias("benchmark_active_daily_ret"),
        )
        .with_columns(
            (pl.col("strategy_gross_daily_ret") - pl.col("turnover_cost_ret")).alias("strategy_daily_ret"),
            pl.lit(cost_bps).alias("roundtrip_cost_bps"),
            pl.lit(scenario).alias("scenario"),
        )
        .with_columns(
            (INITIAL_EQUITY * (1 + pl.col("strategy_daily_ret")).cum_prod()).alias("strategy_equity"),
            (INITIAL_EQUITY * (1 + pl.col("strategy_gross_daily_ret")).cum_prod()).alias("strategy_gross_equity"),
            (INITIAL_EQUITY * (1 + pl.col("benchmark_active_daily_ret")).cum_prod()).alias("benchmark_equity"),
        )
        .with_columns(
            (pl.col("strategy_equity") / pl.col("strategy_equity").cum_max() - 1).alias("strategy_drawdown"),
            (pl.col("strategy_gross_equity") / pl.col("strategy_gross_equity").cum_max() - 1).alias(
                "strategy_gross_drawdown"
            ),
            (pl.col("benchmark_equity") / pl.col("benchmark_equity").cum_max() - 1).alias("benchmark_drawdown"),
        )
    )
    return daily


def summarize_curve(
    curve: pl.DataFrame,
    turnover: pl.DataFrame,
    concentration: pl.DataFrame,
    selected: pl.DataFrame,
    scenario: dict[str, Any],
    cost_bps: float,
) -> dict[str, Any]:
    days = curve.height
    active_curve = curve.filter((pl.col("return_gross_exposure") > 0) | (pl.col("gross_abs_weight_change") > 0))
    active_concentration = concentration.filter(pl.col("gross_exposure") > 0)
    selected_daily = selected.group_by("datetime").agg(
        pl.len().alias("candidate_count"),
        pl.col("industry").n_unique().alias("selected_industry_count"),
        pl.col("basket_gross_weight").first().alias("basket_gross_weight"),
    )
    daily_mean = to_float(curve["strategy_daily_ret"].mean()) if days else 0.0
    daily_std = to_float(curve["strategy_daily_ret"].std()) if days else 0.0
    total_return = to_float(curve["strategy_equity"][-1]) - 1 if days else 0.0
    gross_total_return = to_float(curve["strategy_gross_equity"][-1]) - 1 if days else 0.0
    benchmark_total_return = to_float(curve["benchmark_equity"][-1]) - 1 if days else 0.0
    scenario_turnover = turnover.filter(pl.col("scenario") == scenario["scenario"])
    return {
        "scenario": scenario["scenario"],
        "scenario_description": scenario["description"],
        "bucket": scenario["bucket"],
        "weight_mode": scenario["weight_mode"],
        "roundtrip_cost_bps": cost_bps,
        "days": days,
        "signal_day_count": selected["datetime"].n_unique(),
        "stock_roundtrips": selected.height,
        "avg_candidate_count": to_float(selected_daily["candidate_count"].mean()) if selected_daily.height else 0.0,
        "avg_signal_industry_count": to_float(selected_daily["selected_industry_count"].mean())
        if selected_daily.height
        else 0.0,
        "avg_basket_gross_weight": to_float(selected_daily["basket_gross_weight"].mean())
        if selected_daily.height
        else 0.0,
        "min_basket_gross_weight": to_float(selected_daily["basket_gross_weight"].min()) if selected_daily.height else 0.0,
        "final_equity": to_float(curve["strategy_equity"][-1]) if days else INITIAL_EQUITY,
        "total_return": total_return,
        "annualized_return": (1 + total_return) ** (TRADING_DAYS / days) - 1 if days and total_return > -1 else 0.0,
        "max_drawdown": to_float(curve["strategy_drawdown"].min()) if days else 0.0,
        "sharpe": daily_mean / daily_std * sqrt(TRADING_DAYS) if daily_std else 0.0,
        "gross_final_equity": to_float(curve["strategy_gross_equity"][-1]) if days else INITIAL_EQUITY,
        "gross_total_return": gross_total_return,
        "gross_max_drawdown": to_float(curve["strategy_gross_drawdown"].min()) if days else 0.0,
        "benchmark_final_equity": to_float(curve["benchmark_equity"][-1]) if days else INITIAL_EQUITY,
        "benchmark_total_return": benchmark_total_return,
        "benchmark_max_drawdown": to_float(curve["benchmark_drawdown"].min()) if days else 0.0,
        "active_or_trade_day_ratio": active_curve.height / days if days else 0.0,
        "net_active_day_win_rate": to_float((active_curve["strategy_daily_ret"] > 0).mean())
        if active_curve.height
        else 0.0,
        "avg_return_gross_exposure": to_float(curve["return_gross_exposure"].mean()) if days else 0.0,
        "max_return_gross_exposure": to_float(curve["return_gross_exposure"].max()) if days else 0.0,
        "avg_active_symbols_when_active": to_float(active_concentration["active_symbols"].mean())
        if active_concentration.height
        else 0.0,
        "avg_active_industries_when_active": to_float(active_concentration["active_industries"].mean())
        if active_concentration.height
        else 0.0,
        "avg_effective_names_when_active": to_float(active_concentration["effective_names"].mean())
        if active_concentration.height
        else 0.0,
        "avg_max_symbol_weight_when_active": to_float(active_concentration["max_symbol_weight"].mean())
        if active_concentration.height
        else 0.0,
        "max_symbol_weight": to_float(concentration["max_symbol_weight"].max()) if concentration.height else 0.0,
        "avg_max_industry_weight_when_active": to_float(active_concentration["max_industry_weight"].mean())
        if active_concentration.height
        else 0.0,
        "max_industry_weight": to_float(concentration["max_industry_weight"].max()) if concentration.height else 0.0,
        "avg_top5_industry_weight_when_active": to_float(active_concentration["top5_industry_weight"].mean())
        if active_concentration.height
        else 0.0,
        "annualized_one_way_turnover": to_float(scenario_turnover["one_way_turnover"].mean()) * TRADING_DAYS
        if scenario_turnover.height
        else 0.0,
        "net_turnover_abs_change_sum": to_float(scenario_turnover["gross_abs_weight_change"].sum())
        if scenario_turnover.height
        else 0.0,
        "cost_drag_sum": to_float(curve["turnover_cost_ret"].sum()) if days else 0.0,
    }


def build_yearly_summary(curves: pl.DataFrame) -> pl.DataFrame:
    return (
        curves.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["scenario", "roundtrip_cost_bps", "year"])
        .agg(
            ((1 + pl.col("strategy_daily_ret")).product() - 1).alias("year_return"),
            ((1 + pl.col("strategy_gross_daily_ret")).product() - 1).alias("year_gross_return"),
            ((1 + pl.col("benchmark_active_daily_ret")).product() - 1).alias("year_benchmark_return"),
            pl.col("turnover_cost_ret").sum().alias("year_cost_drag"),
            pl.col("return_gross_exposure").mean().alias("avg_gross_exposure"),
        )
        .sort(["scenario", "roundtrip_cost_bps", "year"])
    )


def build_symbol_exposure_summary(symbol_daily: pl.DataFrame) -> pl.DataFrame:
    return (
        symbol_daily.group_by(["scenario", "symbol"])
        .agg(
            pl.len().alias("holding_days"),
            pl.col("target_weight").mean().alias("avg_target_weight"),
            pl.col("target_weight").max().alias("max_target_weight"),
            pl.col("active_lots").max().alias("max_active_lots"),
            pl.col("industry").first().alias("industry") if "industry" in symbol_daily.columns else pl.lit(None).alias("industry"),
        )
        .sort(["scenario", "max_target_weight", "holding_days"], descending=[False, True, True])
    )


def build_selected_daily_summary(selected: pl.DataFrame) -> pl.DataFrame:
    return (
        selected.group_by(["scenario", "datetime"])
        .agg(
            pl.len().alias("candidate_count"),
            pl.col("industry").n_unique().alias("selected_industry_count"),
            pl.col("basket_weight").sum().alias("basket_gross_weight"),
            pl.col("basket_weight").max().alias("max_basket_stock_weight"),
        )
        .sort(["scenario", "datetime"])
    )


def write_report(
    summary_df: pl.DataFrame,
    yearly: pl.DataFrame,
    symbol_exposure: pl.DataFrame,
    selected_daily: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡行业内排序合并持仓路径 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：最小组合路径压力测试，不是正式交易版本。",
        "",
        "## 方法",
        "",
        f"- 固定信号：`{FEATURE}`，行业内分位排序，top quintile，次日收盘入场，固定持有`{HORIZON}`日。",
        f"- 行业内最小宽度：`{MIN_INDUSTRY_DAILY_WIDTH}`。",
        f"- 约束场景：全成分等权、全成分行业上限、流动性q3+行业上限、active q4/q5行业上限。",
        f"- capped场景单篮子行业上限`{MAX_INDUSTRY_WEIGHT_PER_BASKET:.0%}`，单票上限`{MAX_STOCK_WEIGHT_PER_BASKET:.0%}`，未用完资金留现金。",
        f"- 样本：`{meta['date_min']}`到`{meta['date_max']}`，股票数`{meta['symbol_count']}`。",
        "",
        "## 路径结果",
        "",
    ]
    for row in summary_df.sort(["roundtrip_cost_bps", "scenario"]).iter_rows(named=True):
        lines.append(
            f"- `{row['scenario']}` 成本`{row['roundtrip_cost_bps']:.0f}bp`：期末权益`{row['final_equity']:.4f}`，"
            f"总收益`{pct(row['total_return'])}`，最大回撤`{pct(row['max_drawdown'])}`，Sharpe `{row['sharpe']:.2f}`，"
            f"同暴露基准收益`{pct(row['benchmark_total_return'])}`。"
        )
        lines.append(
            f"  暴露/分散：平均暴露`{pct(row['avg_return_gross_exposure'])}`，最大暴露`{pct(row['max_return_gross_exposure'])}`，"
            f"有持仓日股票`{row['avg_active_symbols_when_active']:.1f}`只、行业`{row['avg_active_industries_when_active']:.1f}`个，"
            f"平均有效持仓`{row['avg_effective_names_when_active']:.1f}`，平均最大行业权重`{pct(row['avg_max_industry_weight_when_active'])}`。"
        )
        lines.append(
            f"  信号宽度：信号日`{row['signal_day_count']}`，股票回合`{row['stock_roundtrips']}`，"
            f"平均候选`{row['avg_candidate_count']:.1f}`，平均信号行业`{row['avg_signal_industry_count']:.1f}`，"
            f"平均篮子使用率`{pct(row['avg_basket_gross_weight'])}`，年化单边换手`{row['annualized_one_way_turnover']:.2f}`倍。"
        )

    lines.extend(["", "## 年度结果", ""])
    for row in yearly.sort(["roundtrip_cost_bps", "scenario", "year"]).iter_rows(named=True):
        lines.append(
            f"- `{row['scenario']}` 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['year']}`："
            f"净收益`{pct(row['year_return'])}`，毛收益`{pct(row['year_gross_return'])}`，"
            f"同暴露基准`{pct(row['year_benchmark_return'])}`，平均暴露`{pct(row['avg_gross_exposure'])}`。"
        )

    lines.extend(["", "## 权重最高股票", ""])
    for row in symbol_exposure.head(20).iter_rows(named=True):
        lines.append(
            f"- `{row['scenario']}` `{row['symbol']}` `{row['industry']}`：持有日`{row['holding_days']}`，"
            f"最大权重`{pct(row['max_target_weight'])}`，平均权重`{pct(row['avg_target_weight'])}`，最大重叠腿`{row['max_active_lots']}`。"
        )

    selected_summary = (
        selected_daily.group_by("scenario")
        .agg(
            pl.col("candidate_count").mean().alias("avg_candidate_count"),
            pl.col("selected_industry_count").mean().alias("avg_industry_count"),
            pl.col("basket_gross_weight").mean().alias("avg_basket_gross_weight"),
            pl.col("basket_gross_weight").min().alias("min_basket_gross_weight"),
            pl.col("max_basket_stock_weight").mean().alias("avg_max_basket_stock_weight"),
        )
        .sort("scenario")
    )
    lines.extend(["", "## 信号日篮子使用率", ""])
    for row in selected_summary.iter_rows(named=True):
        lines.append(
            f"- `{row['scenario']}`：平均候选`{row['avg_candidate_count']:.1f}`，平均行业`{row['avg_industry_count']:.1f}`，"
            f"平均篮子使用率`{pct(row['avg_basket_gross_weight'])}`，最低使用率`{pct(row['min_basket_gross_weight'])}`，"
            f"平均单票篮子最大权重`{pct(row['avg_max_basket_stock_weight'])}`。"
        )

    lines.extend(
        [
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：只把第229阶段固定的行业内排序放入合并持仓账本，约束为事前固定分散/容量边界，不扫信号阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段保留四个事前设定场景与20bp/50bp成本压力，没有按结果反向调阈值；`liquid_q3_capped`只作为下一步归因候选，不作为正式策略参数。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第229阶段确认行业内排序信号有边际，但信号边际必须经受合并持仓、净换手、行业上限和成本压力。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是，但还不能正式化。",
            "- 原因：`liquid_q3_capped`在收益、回撤、流动性和分散度之间最均衡，但15倍左右年化单边换手和成本拖累仍是硬瓶颈；下一步应研究换仓频率、状态贡献和回撤来源，而不是接入实盘。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
            "- 下一步聚焦`liquid_q3_capped`的换手/换仓频率压力测试，以及2018、2022、2023回撤归因。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    df = add_path_columns(
        add_forward_returns(add_price_features(stock_df), benchmark_df).join(
            layer_tags, on=["datetime", "symbol"], how="left"
        )
    )

    selected_frames: list[pl.DataFrame] = []
    for scenario in scenario_definitions():
        selected = select_industry_neutral_candidates(df, scenario)
        if selected.is_empty():
            continue
        selected_frames.append(selected)
    if not selected_frames:
        raise RuntimeError("No selected candidates.")

    selected_all = pl.concat(selected_frames, how="vertical")
    lots_all = build_lots(selected_all)
    symbol_daily_all = build_symbol_daily(lots_all)
    benchmark_daily = build_benchmark_daily(benchmark_df)

    all_curves: list[pl.DataFrame] = []
    all_summary: list[dict[str, Any]] = []
    all_turnover: list[pl.DataFrame] = []
    all_targets: list[pl.DataFrame] = []
    all_concentration: list[pl.DataFrame] = []
    all_industry_daily: list[pl.DataFrame] = []

    for scenario in scenario_definitions():
        scenario_name = scenario["scenario"]
        scenario_symbol_daily = symbol_daily_all.filter(pl.col("scenario") == scenario_name)
        scenario_selected = selected_all.filter(pl.col("scenario") == scenario_name)
        if scenario_symbol_daily.is_empty():
            continue
        min_date = min(scenario_symbol_daily["target_date"].min(), scenario_symbol_daily["pnl_date"].min())
        max_date = max(scenario_symbol_daily["target_date"].max(), scenario_symbol_daily["pnl_date"].max())
        calendar = build_calendar(benchmark_df, min_date, max_date)
        turnover, targets = build_turnover(scenario_symbol_daily, calendar, scenario_name)
        concentration, industry_daily = build_concentration(scenario_symbol_daily, calendar, scenario_name)
        daily_gross = build_daily_gross(scenario_symbol_daily)
        all_turnover.append(turnover)
        all_targets.append(targets)
        all_concentration.append(concentration)
        all_industry_daily.append(industry_daily)
        for cost_bps in COST_BPS:
            curve = build_equity_curve(scenario_name, daily_gross, turnover, benchmark_daily, calendar, cost_bps)
            all_curves.append(curve)
            all_summary.append(summarize_curve(curve, turnover, concentration, scenario_selected, scenario, cost_bps))

    summary_df = pl.DataFrame(all_summary).sort(["roundtrip_cost_bps", "scenario"])
    equity_df = pl.concat(all_curves, how="vertical").sort(["roundtrip_cost_bps", "scenario", "date"])
    turnover_df = pl.concat(all_turnover, how="vertical").sort(["scenario", "target_date"])
    target_weights_df = pl.concat(all_targets, how="vertical").sort(["scenario", "target_date", "symbol"])
    concentration_df = pl.concat(all_concentration, how="vertical").sort(["scenario", "target_date"])
    industry_daily_df = pl.concat(all_industry_daily, how="vertical").sort(["scenario", "target_date", "industry"])
    yearly_df = build_yearly_summary(equity_df)
    symbol_exposure_df = build_symbol_exposure_summary(symbol_daily_all)
    selected_daily_df = build_selected_daily_summary(selected_all)

    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date_min": str(selected_all["datetime"].min()),
        "date_max": str(selected_all["datetime"].max()),
        "symbol_count": selected_all["symbol"].n_unique(),
        "feature": FEATURE,
        "horizon": HORIZON,
        "cost_bps": COST_BPS,
        "min_industry_daily_width": MIN_INDUSTRY_DAILY_WIDTH,
        "max_industry_weight_per_basket": MAX_INDUSTRY_WEIGHT_PER_BASKET,
        "max_stock_weight_per_basket": MAX_STOCK_WEIGHT_PER_BASKET,
        "scenarios": scenario_definitions(),
    }

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    equity_path = OUTPUT_DIR / f"{PREFIX}_equity_curve.csv"
    yearly_path = OUTPUT_DIR / f"{PREFIX}_yearly.csv"
    concentration_path = OUTPUT_DIR / f"{PREFIX}_daily_concentration.csv"
    industry_daily_path = OUTPUT_DIR / f"{PREFIX}_industry_daily.csv"
    turnover_path = OUTPUT_DIR / f"{PREFIX}_turnover.csv"
    target_weights_path = OUTPUT_DIR / f"{PREFIX}_target_weights.csv"
    symbol_exposure_path = OUTPUT_DIR / f"{PREFIX}_symbol_exposure.csv"
    selected_daily_path = OUTPUT_DIR / f"{PREFIX}_selected_daily.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    summary_df.write_csv(summary_path)
    equity_df.write_csv(equity_path)
    yearly_df.write_csv(yearly_path)
    concentration_df.write_csv(concentration_path)
    industry_daily_df.write_csv(industry_daily_path)
    turnover_df.write_csv(turnover_path)
    target_weights_df.write_csv(target_weights_path)
    symbol_exposure_df.write_csv(symbol_exposure_path)
    selected_daily_df.write_csv(selected_daily_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        yearly_df,
        symbol_exposure_df,
        selected_daily_df,
        meta,
        {
            "summary": summary_path,
            "equity_curve": equity_path,
            "yearly": yearly_path,
            "daily_concentration": concentration_path,
            "industry_daily": industry_daily_path,
            "turnover": turnover_path,
            "target_weights": target_weights_path,
            "symbol_exposure": symbol_exposure_path,
            "selected_daily": selected_daily_path,
            "meta": meta_path,
        },
    )
    print(summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
