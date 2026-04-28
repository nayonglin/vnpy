from __future__ import annotations

import json
import os
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import add_forward_returns, add_price_features
from backtest_stock_range_reversion_market_down_long_only import (
    BUCKET,
    COST_BPS,
    FEATURE,
    HORIZON,
    INITIAL_EQUITY,
    MARKET_STATE,
    TRADING_DAYS,
    add_path_return_columns,
    build_selected_candidates,
    get_bucket_definition,
    to_float,
)


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_merged_portfolio_2018_2026"),
    )
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_market_down_merged_portfolio_v1"


def add_start_date_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Add close-to-close start dates for the fixed holding path."""
    work = df.sort(["symbol", "datetime"])
    return work.with_columns(
        [
            pl.col("datetime").shift(-day).over("symbol").alias(f"start_date_{day}")
            for day in range(1, HORIZON + 1)
        ]
    )


def build_selected_frame() -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    """Load the fixed market-down candidate frame."""
    bucket_description, _bucket_expr = get_bucket_definition()
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    df = add_forward_returns(add_price_features(stock_df), benchmark_df).join(
        layer_tags, on=["datetime", "symbol"], how="left"
    )
    df = add_start_date_columns(add_path_return_columns(df))
    selected = build_selected_candidates(df)
    if selected.is_empty():
        raise RuntimeError("No selected candidates.")
    meta = {
        "date_min": str(selected["datetime"].min()),
        "date_max": str(selected["datetime"].max()),
        "symbol_count": selected["symbol"].n_unique(),
        "selected_roundtrips": selected.height,
        "signal_day_count": selected["datetime"].n_unique(),
        "bucket_description": bucket_description,
    }
    return selected, benchmark_df.sort("datetime"), meta


def build_lots(selected: pl.DataFrame) -> pl.DataFrame:
    """Explode fixed baskets into daily target-weight lots."""
    selected = selected.with_columns(pl.len().over("datetime").alias("candidate_count"))
    parts: list[pl.DataFrame] = []
    extra_cols = [col for col in ["industry", "market", "adv20_turnover", "circ_mv"] if col in selected.columns]
    for day in range(1, HORIZON + 1):
        parts.append(
            selected.select(
                pl.col("datetime").alias("signal_date"),
                "symbol",
                "candidate_count",
                FEATURE,
                *extra_cols,
                pl.col(f"start_date_{day}").alias("target_date"),
                pl.col(f"pnl_date_{day}").alias("pnl_date"),
                pl.col(f"stock_daily_ret_{day}").alias("stock_daily_ret"),
            )
            .with_columns(
                pl.lit(day).alias("holding_day"),
                (1.0 / HORIZON / pl.col("candidate_count")).alias("lot_weight"),
            )
            .filter(
                pl.col("target_date").is_not_null()
                & pl.col("pnl_date").is_not_null()
                & pl.col("stock_daily_ret").is_not_null()
                & pl.col("stock_daily_ret").is_finite()
            )
        )
    return pl.concat(parts, how="vertical").sort(["target_date", "signal_date", "symbol"])


def build_symbol_daily(lots: pl.DataFrame) -> pl.DataFrame:
    """Merge same-symbol lots into one symbol-level daily holding row."""
    agg_exprs: list[pl.Expr] = [
        pl.col("lot_weight").sum().alias("target_weight"),
        pl.len().alias("active_lots"),
        pl.col("stock_daily_ret").first().alias("stock_daily_ret"),
        pl.col("signal_date").n_unique().alias("source_signal_days"),
        pl.col("holding_day").min().alias("min_holding_day"),
        pl.col("holding_day").max().alias("max_holding_day"),
    ]
    for col in ["industry", "market", "adv20_turnover", "circ_mv"]:
        if col in lots.columns:
            agg_exprs.append(pl.col(col).first().alias(col))
    return (
        lots.group_by(["target_date", "pnl_date", "symbol"])
        .agg(agg_exprs)
        .with_columns((pl.col("target_weight") * pl.col("stock_daily_ret")).alias("weighted_stock_ret"))
        .sort(["target_date", "symbol"])
    )


def build_calendar(benchmark_df: pl.DataFrame, min_date: Any, max_date: Any) -> pl.DataFrame:
    """Build the trading-day calendar used by target weights and equity."""
    return (
        benchmark_df.select(pl.col("datetime").alias("date"))
        .filter((pl.col("date") >= min_date) & (pl.col("date") <= max_date))
        .sort("date")
    )


def build_turnover(symbol_daily: pl.DataFrame, calendar: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Build net target-weight changes after merging duplicate same-symbol lots."""
    target_weights = symbol_daily.select("target_date", "symbol", "target_weight").unique(
        subset=["target_date", "symbol"]
    )
    symbols = target_weights.select("symbol").unique().sort("symbol")
    grid = calendar.rename({"date": "target_date"}).join(symbols, how="cross")
    full_targets = (
        grid.join(target_weights, on=["target_date", "symbol"], how="left")
        .with_columns(pl.col("target_weight").fill_null(0.0))
        .sort(["symbol", "target_date"])
        .with_columns(
            pl.col("target_weight").shift(1).over("symbol").fill_null(0.0).alias("prev_target_weight")
        )
        .with_columns(
            (pl.col("target_weight") - pl.col("prev_target_weight")).alias("target_weight_delta"),
            (pl.col("target_weight") - pl.col("prev_target_weight")).abs().alias("abs_target_weight_delta"),
        )
    )
    turnover = (
        full_targets.group_by("target_date")
        .agg(
            pl.col("abs_target_weight_delta").sum().alias("gross_abs_weight_change"),
            pl.col("target_weight_delta").clip(0).sum().alias("buy_weight"),
            (-pl.col("target_weight_delta").clip(None, 0)).sum().alias("sell_weight"),
            (pl.col("abs_target_weight_delta") / 2).sum().alias("one_way_turnover"),
            (pl.col("target_weight") > 0).sum().alias("target_active_symbols"),
            pl.col("target_weight").sum().alias("target_gross_exposure"),
        )
        .sort("target_date")
    )
    nonzero_targets = full_targets.filter(pl.col("target_weight") > 0).select(
        "target_date", "symbol", "target_weight", "target_weight_delta", "abs_target_weight_delta"
    )
    return turnover, nonzero_targets


def build_concentration(symbol_daily: pl.DataFrame, calendar: pl.DataFrame) -> pl.DataFrame:
    """Summarize daily merged holding concentration."""
    concentration = (
        symbol_daily.group_by("target_date")
        .agg(
            pl.len().alias("active_symbols"),
            pl.col("target_weight").sum().alias("gross_exposure"),
            pl.col("target_weight").max().alias("max_symbol_weight"),
            pl.col("target_weight").sort(descending=True).head(5).sum().alias("top5_weight"),
            pl.col("target_weight").sort(descending=True).head(10).sum().alias("top10_weight"),
            (pl.col("target_weight") ** 2).sum().alias("herfindahl"),
            (pl.col("active_lots") > 1).sum().alias("duplicated_symbols"),
            pl.col("active_lots").max().alias("max_symbol_lots"),
        )
        .with_columns(
            (pl.col("gross_exposure") ** 2 / pl.col("herfindahl")).alias("effective_names"),
            (pl.col("duplicated_symbols") / pl.col("active_symbols")).alias("duplicated_symbol_ratio"),
        )
    )
    return (
        calendar.rename({"date": "target_date"})
        .join(concentration, on="target_date", how="left")
        .with_columns(
            pl.col("active_symbols").fill_null(0),
            pl.col("gross_exposure").fill_null(0.0),
            pl.col("max_symbol_weight").fill_null(0.0),
            pl.col("top5_weight").fill_null(0.0),
            pl.col("top10_weight").fill_null(0.0),
            pl.col("herfindahl").fill_null(0.0),
            pl.col("duplicated_symbols").fill_null(0),
            pl.col("max_symbol_lots").fill_null(0),
            pl.col("effective_names").fill_null(0.0),
            pl.col("duplicated_symbol_ratio").fill_null(0.0),
        )
        .sort("target_date")
    )


def build_daily_gross(symbol_daily: pl.DataFrame) -> pl.DataFrame:
    """Build merged portfolio gross daily stock returns."""
    return (
        symbol_daily.group_by("pnl_date")
        .agg(
            pl.col("weighted_stock_ret").sum().alias("strategy_gross_daily_ret"),
            pl.col("target_weight").sum().alias("return_gross_exposure"),
            pl.len().alias("return_active_symbols"),
            pl.col("active_lots").sum().alias("return_active_lots"),
        )
        .sort("pnl_date")
    )


def build_benchmark_daily(benchmark_df: pl.DataFrame) -> pl.DataFrame:
    """Build benchmark close-to-close returns."""
    return (
        benchmark_df.select("datetime", "close")
        .sort("datetime")
        .with_columns((pl.col("close") / pl.col("close").shift(1) - 1).alias("benchmark_daily_ret"))
        .select(pl.col("datetime").alias("date"), "benchmark_daily_ret")
    )


def build_equity_curve(
    daily_gross: pl.DataFrame,
    turnover: pl.DataFrame,
    benchmark_daily: pl.DataFrame,
    calendar: pl.DataFrame,
    cost_bps: float,
) -> pl.DataFrame:
    """Build equity curve using merged holdings and net turnover cost."""
    one_way_cost = cost_bps / 2 / 10000.0
    daily = (
        calendar.join(daily_gross.rename({"pnl_date": "date"}), on="date", how="left")
        .join(turnover.rename({"target_date": "date"}), on="date", how="left")
        .join(benchmark_daily, on="date", how="left")
        .with_columns(
            pl.col("strategy_gross_daily_ret").fill_null(0.0),
            pl.col("return_gross_exposure").fill_null(0.0),
            pl.col("return_active_symbols").fill_null(0),
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
    cost_bps: float,
) -> dict[str, Any]:
    """Summarize merged portfolio path, turnover, and concentration."""
    days = curve.height
    total_return = to_float(curve["strategy_equity"][-1]) / INITIAL_EQUITY - 1 if days else 0.0
    gross_total_return = to_float(curve["strategy_gross_equity"][-1]) / INITIAL_EQUITY - 1 if days else 0.0
    benchmark_total_return = to_float(curve["benchmark_equity"][-1]) / INITIAL_EQUITY - 1 if days else 0.0
    daily_mean = to_float(curve["strategy_daily_ret"].mean()) if days else 0.0
    daily_std = to_float(curve["strategy_daily_ret"].std()) if days else 0.0
    active_curve = curve.filter((pl.col("return_gross_exposure") > 0) | (pl.col("gross_abs_weight_change") > 0))
    active_concentration = concentration.filter(pl.col("gross_exposure") > 0)
    gross_abs_change_sum = to_float(turnover["gross_abs_weight_change"].sum()) if turnover.height else 0.0
    independent_abs_change_sum = selected["datetime"].n_unique() * (2.0 / HORIZON)
    one_way_cost = cost_bps / 2 / 10000.0
    net_cost_notional = gross_abs_change_sum * one_way_cost
    independent_cost_notional = independent_abs_change_sum * one_way_cost
    return {
        "roundtrip_cost_bps": cost_bps,
        "feature": FEATURE,
        "horizon": HORIZON,
        "bucket": BUCKET,
        "market_state": MARKET_STATE,
        "days": days,
        "signal_basket_count": selected["datetime"].n_unique(),
        "stock_roundtrips": selected.height,
        "final_equity": to_float(curve["strategy_equity"][-1]) if days else INITIAL_EQUITY,
        "total_return": total_return,
        "annualized_return": (1 + total_return) ** (TRADING_DAYS / days) - 1
        if days and total_return > -1
        else 0.0,
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
        "avg_gross_exposure": to_float(curve["return_gross_exposure"].mean()) if days else 0.0,
        "max_gross_exposure": to_float(curve["return_gross_exposure"].max()) if days else 0.0,
        "avg_active_symbols": to_float(concentration["active_symbols"].mean()) if concentration.height else 0.0,
        "median_active_symbols": to_float(concentration["active_symbols"].median()) if concentration.height else 0.0,
        "avg_active_symbols_when_active": to_float(active_concentration["active_symbols"].mean())
        if active_concentration.height
        else 0.0,
        "median_active_symbols_when_active": to_float(active_concentration["active_symbols"].median())
        if active_concentration.height
        else 0.0,
        "avg_max_symbol_weight": to_float(concentration["max_symbol_weight"].mean()) if concentration.height else 0.0,
        "max_symbol_weight": to_float(concentration["max_symbol_weight"].max()) if concentration.height else 0.0,
        "avg_top5_weight": to_float(concentration["top5_weight"].mean()) if concentration.height else 0.0,
        "avg_top10_weight": to_float(concentration["top10_weight"].mean()) if concentration.height else 0.0,
        "avg_effective_names": to_float(concentration["effective_names"].mean()) if concentration.height else 0.0,
        "max_symbol_lots": int(concentration["max_symbol_lots"].max()) if concentration.height else 0,
        "avg_daily_gross_abs_weight_change": to_float(turnover["gross_abs_weight_change"].mean())
        if turnover.height
        else 0.0,
        "median_daily_gross_abs_weight_change": to_float(turnover["gross_abs_weight_change"].median())
        if turnover.height
        else 0.0,
        "annualized_one_way_turnover": to_float(turnover["one_way_turnover"].mean()) * TRADING_DAYS
        if turnover.height
        else 0.0,
        "net_turnover_abs_change_sum": gross_abs_change_sum,
        "independent_abs_change_sum": independent_abs_change_sum,
        "net_cost_notional": net_cost_notional,
        "independent_cost_notional": independent_cost_notional,
        "net_cost_vs_independent_ratio": net_cost_notional / independent_cost_notional
        if independent_cost_notional
        else 0.0,
    }


def build_yearly_summary(curves: pl.DataFrame) -> pl.DataFrame:
    """Summarize annual path returns for each cost scenario."""
    return (
        curves.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["roundtrip_cost_bps", "year"])
        .agg(
            ((1 + pl.col("strategy_daily_ret")).product() - 1).alias("year_return"),
            ((1 + pl.col("strategy_gross_daily_ret")).product() - 1).alias("year_gross_return"),
            ((1 + pl.col("benchmark_active_daily_ret")).product() - 1).alias("year_benchmark_return"),
            pl.col("turnover_cost_ret").sum().alias("year_cost_drag"),
            pl.col("gross_abs_weight_change").sum().alias("year_gross_abs_weight_change"),
            pl.col("return_gross_exposure").mean().alias("avg_gross_exposure"),
        )
        .sort(["roundtrip_cost_bps", "year"])
    )


def build_symbol_exposure_summary(symbol_daily: pl.DataFrame) -> pl.DataFrame:
    """Find names with the highest repeated merged exposure."""
    return (
        symbol_daily.group_by("symbol")
        .agg(
            pl.len().alias("holding_days"),
            pl.col("target_weight").mean().alias("avg_target_weight"),
            pl.col("target_weight").max().alias("max_target_weight"),
            (pl.col("active_lots") > 1).mean().alias("duplicate_day_ratio"),
            pl.col("active_lots").max().alias("max_active_lots"),
            pl.col("industry").first().alias("industry") if "industry" in symbol_daily.columns else pl.lit(None).alias("industry"),
        )
        .sort(["max_target_weight", "holding_days"], descending=[True, True])
    )


def write_report(
    summary_df: pl.DataFrame,
    yearly: pl.DataFrame,
    concentration: pl.DataFrame,
    turnover: pl.DataFrame,
    symbol_exposure: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    """Write a Chinese report for merged-portfolio accounting."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡 market_down 合并持仓组合记账 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是新策略，也不调信号阈值；只把第214阶段的重叠篮子合并成真实日度目标持仓，并按净买卖计算成本。",
        f"- 固定口径：`{MARKET_STATE}`、`{BUCKET}`、`{FEATURE}` top quintile，次日收盘入场，固定持有`{HORIZON}`日。",
        f"- 样本：信号日`{meta['signal_day_count']}`个，股票回合`{meta['selected_roundtrips']:,}`个，涉及股票`{meta['symbol_count']}`只。",
        "",
        "## 合并持仓路径结果",
        "",
    ]
    for row in summary_df.sort("roundtrip_cost_bps").iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp`：期末权益`{row['final_equity']:.4f}`，"
            f"总收益`{row['total_return']:.2%}`，年化`{row['annualized_return']:.2%}`，"
            f"最大回撤`{row['max_drawdown']:.2%}`，Sharpe `{row['sharpe']:.2f}`，"
            f"活跃/交易日净胜率`{row['net_active_day_win_rate']:.2%}`。"
        )
        lines.append(
            f"  毛收益口径：期末权益`{row['gross_final_equity']:.4f}`，总收益`{row['gross_total_return']:.2%}`，"
            f"最大回撤`{row['gross_max_drawdown']:.2%}`；同暴露基准总收益`{row['benchmark_total_return']:.2%}`。"
        )
        lines.append(
            f"  净换手成本名义占独立篮子成本约`{row['net_cost_vs_independent_ratio']:.2%}`，"
            f"年化单边换手`{row['annualized_one_way_turnover']:.2f}`倍。"
        )

    first = summary_df.sort("roundtrip_cost_bps").row(0, named=True) if summary_df.height else None
    if first:
        lines.extend(
            [
                "",
                "## 持仓与集中度",
                "",
                f"- 活跃或交易日占比`{first['active_or_trade_day_ratio']:.2%}`。",
                f"- 平均总暴露`{first['avg_gross_exposure']:.2%}`，最大总暴露`{first['max_gross_exposure']:.2%}`。",
                f"- 全样本平均活跃股票`{first['avg_active_symbols']:.1f}`只，中位`{first['median_active_symbols']:.1f}`只；"
                f"有持仓日平均活跃股票`{first['avg_active_symbols_when_active']:.1f}`只，中位`{first['median_active_symbols_when_active']:.1f}`只。",
                f"- 平均单票最大权重`{first['avg_max_symbol_weight']:.2%}`，历史单票最大权重`{first['max_symbol_weight']:.2%}`。",
                f"- 平均Top5权重`{first['avg_top5_weight']:.2%}`，平均Top10权重`{first['avg_top10_weight']:.2%}`，平均有效持仓数`{first['avg_effective_names']:.1f}`。",
                f"- 单票最大重叠腿数`{first['max_symbol_lots']}`。",
                f"- 日均净权重变动`{first['avg_daily_gross_abs_weight_change']:.2%}`，中位净权重变动`{first['median_daily_gross_abs_weight_change']:.2%}`。",
            ]
        )

    lines.extend(["", "## 年度结果", ""])
    for row in yearly.sort(["roundtrip_cost_bps", "year"]).iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['year']}`：净收益`{row['year_return']:.2%}`，"
            f"毛收益`{row['year_gross_return']:.2%}`，同暴露基准`{row['year_benchmark_return']:.2%}`，"
            f"成本拖累`{row['year_cost_drag']:.2%}`。"
        )

    lines.extend(["", "## 权重最高股票", ""])
    for row in symbol_exposure.head(10).iter_rows(named=True):
        industry = row.get("industry") or "unknown"
        lines.append(
            f"- `{row['symbol']}` `{industry}`：持有日`{row['holding_days']}`，最大权重`{row['max_target_weight']:.2%}`，"
            f"平均权重`{row['avg_target_weight']:.2%}`，最大重叠腿`{row['max_active_lots']}`。"
        )

    worst_turnover = turnover.sort("gross_abs_weight_change", descending=True).head(5)
    lines.extend(["", "## 换手压力最高交易日", ""])
    for row in worst_turnover.iter_rows(named=True):
        lines.append(
            f"- `{row['target_date']}`：净权重变动`{row['gross_abs_weight_change']:.2%}`，"
            f"买入`{row['buy_weight']:.2%}`，卖出`{row['sell_weight']:.2%}`，目标股票`{row['target_active_symbols']}`只。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果合并持仓后的收益接近或好于独立袖珍篮子，说明同股重叠主要降低真实成本，而不是制造虚假收益。",
            "- 如果集中度没有明显失控，后续才值得讨论简单风险预算；否则应先处理单票权重和净换手上限。",
            "- 这一步仍不触发第78 A/B，也不接入正式股票策略。",
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
    """Run merged-holding accounting for the fixed market-down path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    selected, benchmark_df, meta = build_selected_frame()
    lots = build_lots(selected)
    symbol_daily = build_symbol_daily(lots)
    min_date = min(lots["target_date"].min(), lots["pnl_date"].min())
    max_date = max(lots["target_date"].max(), lots["pnl_date"].max())
    calendar = build_calendar(benchmark_df, min_date, max_date)
    turnover, target_weights = build_turnover(symbol_daily, calendar)
    concentration = build_concentration(symbol_daily, calendar)
    daily_gross = build_daily_gross(symbol_daily)
    benchmark_daily = build_benchmark_daily(benchmark_df)

    curves: list[pl.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for cost_bps in COST_BPS:
        curve = build_equity_curve(daily_gross, turnover, benchmark_daily, calendar, cost_bps)
        curves.append(curve)
        summary_rows.append(summarize_curve(curve, turnover, concentration, selected, cost_bps))

    summary_df = pl.DataFrame(summary_rows).sort("roundtrip_cost_bps")
    equity_df = pl.concat(curves, how="vertical").sort(["roundtrip_cost_bps", "date"])
    yearly = build_yearly_summary(equity_df)
    symbol_exposure = build_symbol_exposure_summary(symbol_daily)
    meta.update(
        {
            "feature": FEATURE,
            "horizon": HORIZON,
            "bucket": BUCKET,
            "market_state": MARKET_STATE,
            "cost_bps": COST_BPS,
            "initial_equity": INITIAL_EQUITY,
            "path_model": "merged daily target holdings with net-turnover costs",
            "lot_count": lots.height,
            "merged_symbol_daily_rows": symbol_daily.height,
        }
    )

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    equity_path = OUTPUT_DIR / f"{PREFIX}_equity_curve.csv"
    yearly_path = OUTPUT_DIR / f"{PREFIX}_yearly.csv"
    concentration_path = OUTPUT_DIR / f"{PREFIX}_daily_concentration.csv"
    turnover_path = OUTPUT_DIR / f"{PREFIX}_turnover.csv"
    target_weights_path = OUTPUT_DIR / f"{PREFIX}_target_weights.csv"
    symbol_exposure_path = OUTPUT_DIR / f"{PREFIX}_symbol_exposure.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    summary_df.write_csv(summary_path)
    equity_df.write_csv(equity_path)
    yearly.write_csv(yearly_path)
    concentration.write_csv(concentration_path)
    turnover.write_csv(turnover_path)
    target_weights.write_csv(target_weights_path)
    symbol_exposure.write_csv(symbol_exposure_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        yearly,
        concentration,
        turnover,
        symbol_exposure,
        meta,
        {
            "summary": summary_path,
            "equity_curve": equity_path,
            "yearly": yearly_path,
            "daily_concentration": concentration_path,
            "turnover": turnover_path,
            "target_weights": target_weights_path,
            "symbol_exposure": symbol_exposure_path,
            "meta": meta_path,
        },
    )
    print(summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
