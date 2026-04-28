from __future__ import annotations

import json
import os
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_active_bucket_stability import (
    active_bucket_definitions,
    add_groups,
    finite_signal_filter,
)
from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import add_forward_returns, add_price_features


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_long_only_2018_2026"),
    )
).expanduser().resolve()

PREFIX: str = "stock_range_reversion_market_down_long_only_v1"
FEATURE: str = os.getenv("FEATURE", "score_oversold_ret_20")
HORIZON: int = int(os.getenv("HORIZON", "10") or 10)
BUCKET: str = os.getenv("BUCKET", "active_q4_q5")
MARKET_STATE: str = os.getenv("MARKET_STATE", "market_down_20d")
COST_BPS: tuple[float, ...] = tuple(float(item) for item in os.getenv("COST_BPS", "20,50").split(",") if item.strip())
INITIAL_EQUITY: float = float(os.getenv("INITIAL_EQUITY", "1.0") or 1.0)
TRADING_DAYS: int = int(os.getenv("TRADING_DAYS", "252") or 252)


def to_float(value: Any) -> float:
    """Convert nullable scalar to float."""
    if value is None:
        return 0.0
    if hasattr(value, "item"):
        try:
            value = value.item()
        except ValueError:
            pass
    return float(value)


def get_bucket_definition() -> tuple[str, pl.Expr]:
    """Return the configured active bucket description and expression."""
    for bucket, description, expr in active_bucket_definitions():
        if bucket == BUCKET:
            return description, expr
    raise ValueError(f"Unknown bucket: {BUCKET}")


def add_path_return_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Add mark-to-market return columns for the fixed holding path."""
    work = df.sort(["symbol", "datetime"])
    exprs: list[pl.Expr] = []
    for day in range(1, HORIZON + 1):
        exprs.extend(
            [
                pl.col("datetime").shift(-(day + 1)).over("symbol").alias(f"pnl_date_{day}"),
                (
                    pl.col("close").shift(-(day + 1)).over("symbol")
                    / pl.col("close").shift(-day).over("symbol")
                    - 1
                ).alias(f"stock_daily_ret_{day}"),
            ]
        )
    return work.with_columns(exprs)


def build_benchmark_long(benchmark_df: pl.DataFrame) -> pl.DataFrame:
    """Build benchmark daily returns aligned to each signal date and holding day."""
    bm = benchmark_df.sort("datetime")
    parts: list[pl.DataFrame] = []
    for day in range(1, HORIZON + 1):
        parts.append(
            bm.select(
                pl.col("datetime").alias("signal_date"),
                pl.col("datetime").shift(-(day + 1)).alias("pnl_date"),
                (pl.col("close").shift(-(day + 1)) / pl.col("close").shift(-day) - 1).alias(
                    "benchmark_daily_ret"
                ),
            )
            .with_columns(pl.lit(day).alias("holding_day"))
            .filter(pl.col("pnl_date").is_not_null() & pl.col("benchmark_daily_ret").is_not_null())
        )
    return pl.concat(parts, how="vertical")


def build_stock_long(top_df: pl.DataFrame) -> pl.DataFrame:
    """Explode selected stocks into daily holding returns."""
    parts: list[pl.DataFrame] = []
    select_extra = [col for col in ["adv20_turnover", "turnover_rate_f", "circ_mv", "market", "industry"] if col in top_df.columns]
    for day in range(1, HORIZON + 1):
        parts.append(
            top_df.select(
                pl.col("datetime").alias("signal_date"),
                "symbol",
                FEATURE,
                *select_extra,
                pl.col(f"pnl_date_{day}").alias("pnl_date"),
                pl.col(f"stock_daily_ret_{day}").alias("stock_daily_ret"),
            )
            .with_columns(pl.lit(day).alias("holding_day"))
            .filter(
                pl.col("pnl_date").is_not_null()
                & pl.col("stock_daily_ret").is_not_null()
                & pl.col("stock_daily_ret").is_finite()
            )
        )
    return pl.concat(parts, how="vertical")


def build_selected_candidates(df: pl.DataFrame) -> pl.DataFrame:
    """Select the fixed top-quintile candidates for the market-down window."""
    _description, bucket_expr = get_bucket_definition()
    work = df.filter(
        bucket_expr
        & (pl.col("market_state_20d") == MARKET_STATE)
        & finite_signal_filter(FEATURE, HORIZON)
    )
    if work.is_empty():
        return pl.DataFrame()
    return add_groups(work, FEATURE, []).filter(pl.col("feature_group") == 5)


def build_basket_daily(top_df: pl.DataFrame, benchmark_df: pl.DataFrame) -> pl.DataFrame:
    """Build one equal-weight basket return per signal date and holding day."""
    stock_long = build_stock_long(top_df)
    benchmark_long = build_benchmark_long(benchmark_df)
    basket_daily = (
        stock_long.group_by(["signal_date", "holding_day", "pnl_date"])
        .agg(
            pl.len().alias("stock_count"),
            pl.col("stock_daily_ret").mean().alias("basket_stock_daily_ret"),
            pl.col("stock_daily_ret").std().alias("basket_stock_daily_ret_std"),
            pl.col("adv20_turnover").median().alias("median_adv20_turnover")
            if "adv20_turnover" in stock_long.columns
            else pl.lit(None).alias("median_adv20_turnover"),
        )
        .join(benchmark_long, on=["signal_date", "holding_day", "pnl_date"], how="left")
        .filter(pl.col("benchmark_daily_ret").is_not_null())
        .sort(["pnl_date", "signal_date", "holding_day"])
    )
    return basket_daily


def build_basket_horizon(top_df: pl.DataFrame) -> pl.DataFrame:
    """Build horizon-level basket outcomes by signal date."""
    return (
        top_df.group_by("datetime")
        .agg(
            pl.len().alias("candidate_count"),
            pl.col(f"fwd_ret_{HORIZON}").mean().alias("gross_basket_ret"),
            pl.col(f"fwd_excess_ret_{HORIZON}").mean().alias("gross_basket_excess_ret"),
            pl.first(f"bm_fwd_ret_{HORIZON}").alias("benchmark_horizon_ret"),
            pl.col("adv20_turnover").median().alias("median_adv20_turnover")
            if "adv20_turnover" in top_df.columns
            else pl.lit(None).alias("median_adv20_turnover"),
        )
        .rename({"datetime": "signal_date"})
        .sort("signal_date")
    )


def build_equity_curve(
    basket_daily: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    cost_bps: float,
) -> pl.DataFrame:
    """Build an overlapping-sleeve equity curve under one cost scenario."""
    sleeve_weight = 1.0 / HORIZON
    daily_cost = (cost_bps / 10000.0) / HORIZON
    components = basket_daily.with_columns(
        ((pl.col("basket_stock_daily_ret") - daily_cost) * sleeve_weight).alias("strategy_component_ret"),
        (pl.col("benchmark_daily_ret") * sleeve_weight).alias("benchmark_component_ret"),
        pl.lit(sleeve_weight).alias("exposure_component"),
    )
    daily = (
        components.group_by("pnl_date")
        .agg(
            pl.col("strategy_component_ret").sum().alias("strategy_daily_ret"),
            pl.col("benchmark_component_ret").sum().alias("benchmark_daily_ret_active"),
            pl.col("exposure_component").sum().alias("gross_exposure"),
            pl.col("signal_date").n_unique().alias("active_sleeves"),
            pl.col("stock_count").sum().alias("active_stock_positions"),
        )
        .sort("pnl_date")
    )
    min_date = daily["pnl_date"].min()
    max_date = daily["pnl_date"].max()
    all_dates = benchmark_df.select(pl.col("datetime").alias("pnl_date")).filter(
        (pl.col("pnl_date") >= min_date) & (pl.col("pnl_date") <= max_date)
    )
    curve = (
        all_dates.join(daily, on="pnl_date", how="left")
        .with_columns(
            pl.col("strategy_daily_ret").fill_null(0.0),
            pl.col("benchmark_daily_ret_active").fill_null(0.0),
            pl.col("gross_exposure").fill_null(0.0),
            pl.col("active_sleeves").fill_null(0),
            pl.col("active_stock_positions").fill_null(0),
        )
        .with_columns(
            (INITIAL_EQUITY * (1 + pl.col("strategy_daily_ret")).cum_prod()).alias("strategy_equity"),
            (INITIAL_EQUITY * (1 + pl.col("benchmark_daily_ret_active")).cum_prod()).alias("benchmark_equity"),
        )
        .with_columns(
            (pl.col("strategy_equity") / pl.col("strategy_equity").cum_max() - 1).alias("strategy_drawdown"),
            (pl.col("benchmark_equity") / pl.col("benchmark_equity").cum_max() - 1).alias("benchmark_drawdown"),
            pl.lit(cost_bps).alias("roundtrip_cost_bps"),
        )
    )
    return curve


def summarize_curve(curve: pl.DataFrame, basket_horizon: pl.DataFrame, cost_bps: float, top_df: pl.DataFrame) -> dict[str, Any]:
    """Summarize the path and horizon basket outcomes."""
    cost_return = cost_bps / 10000.0
    basket_net = basket_horizon.with_columns(
        (pl.col("gross_basket_ret") - cost_return).alias("net_basket_ret"),
        (pl.col("gross_basket_excess_ret") - cost_return).alias("net_basket_excess_ret"),
    )
    days = curve.height
    total_return = to_float(curve["strategy_equity"][-1]) / INITIAL_EQUITY - 1 if days else 0.0
    benchmark_total_return = to_float(curve["benchmark_equity"][-1]) / INITIAL_EQUITY - 1 if days else 0.0
    daily_mean = to_float(curve["strategy_daily_ret"].mean()) if days else 0.0
    daily_std = to_float(curve["strategy_daily_ret"].std()) if days else 0.0
    annualized_return = (1 + total_return) ** (TRADING_DAYS / days) - 1 if days and total_return > -1 else 0.0
    benchmark_annualized_return = (
        (1 + benchmark_total_return) ** (TRADING_DAYS / days) - 1
        if days and benchmark_total_return > -1
        else 0.0
    )
    return {
        "roundtrip_cost_bps": cost_bps,
        "feature": FEATURE,
        "horizon": HORIZON,
        "bucket": BUCKET,
        "market_state": MARKET_STATE,
        "days": days,
        "signal_basket_count": basket_horizon.height,
        "stock_roundtrips": top_df.height,
        "avg_candidate_count": to_float(basket_horizon["candidate_count"].mean()) if basket_horizon.height else 0.0,
        "median_candidate_count": to_float(basket_horizon["candidate_count"].median()) if basket_horizon.height else 0.0,
        "final_equity": to_float(curve["strategy_equity"][-1]) if days else INITIAL_EQUITY,
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": to_float(curve["strategy_drawdown"].min()) if days else 0.0,
        "sharpe": daily_mean / daily_std * sqrt(TRADING_DAYS) if daily_std else 0.0,
        "benchmark_final_equity": to_float(curve["benchmark_equity"][-1]) if days else INITIAL_EQUITY,
        "benchmark_total_return": benchmark_total_return,
        "benchmark_annualized_return": benchmark_annualized_return,
        "benchmark_max_drawdown": to_float(curve["benchmark_drawdown"].min()) if days else 0.0,
        "active_day_ratio": to_float((curve["gross_exposure"] > 0).mean()) if days else 0.0,
        "avg_gross_exposure": to_float(curve["gross_exposure"].mean()) if days else 0.0,
        "max_gross_exposure": to_float(curve["gross_exposure"].max()) if days else 0.0,
        "max_active_sleeves": int(curve["active_sleeves"].max()) if days else 0,
        "avg_active_stock_positions": to_float(curve["active_stock_positions"].mean()) if days else 0.0,
        "gross_basket_ret_mean": to_float(basket_horizon["gross_basket_ret"].mean()) if basket_horizon.height else 0.0,
        "gross_basket_excess_ret_mean": to_float(basket_horizon["gross_basket_excess_ret"].mean()) if basket_horizon.height else 0.0,
        "net_basket_ret_mean": to_float(basket_net["net_basket_ret"].mean()) if basket_net.height else 0.0,
        "net_basket_excess_ret_mean": to_float(basket_net["net_basket_excess_ret"].mean()) if basket_net.height else 0.0,
        "net_basket_win_rate": to_float((basket_net["net_basket_ret"] > 0).mean()) if basket_net.height else 0.0,
        "net_basket_excess_win_rate": to_float((basket_net["net_basket_excess_ret"] > 0).mean()) if basket_net.height else 0.0,
    }


def write_report(
    summary_df: pl.DataFrame,
    basket_horizon: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    """Write a Chinese report for the minimum path backtest."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡 market_down 最小路径回测 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段是研究用最小路径回测，不是正式股票策略；只验证第213阶段唯一明确窗口，不扫信号、不扫阈值、不扫持仓数。",
        f"- 口径：`{MARKET_STATE}`、`{BUCKET}`、`{FEATURE}` top quintile，信号日收盘后，次日收盘入场，固定持有`{HORIZON}`个交易日。",
        f"- 组合方式：每个信号日形成一个等权篮子，每个篮子使用`1/{HORIZON}`资金，最多约1倍总暴露；无信号时资金留现金。",
        f"- 样本：`{meta['date_min']}`到`{meta['date_max']}`，`{meta['symbol_count']}`只股票，候选股票回合`{meta['stock_roundtrips']:,}`个。",
        "",
        "## 路径结果",
        "",
    ]

    for row in summary_df.sort("roundtrip_cost_bps").iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp`：期末权益`{row['final_equity']:.4f}`，"
            f"总收益`{row['total_return']:.2%}`，年化`{row['annualized_return']:.2%}`，"
            f"最大回撤`{row['max_drawdown']:.2%}`，Sharpe `{row['sharpe']:.2f}`，"
            f"篮子胜率`{row['net_basket_win_rate']:.2%}`。"
        )
        lines.append(
            f"  同暴露基准：期末权益`{row['benchmark_final_equity']:.4f}`，"
            f"总收益`{row['benchmark_total_return']:.2%}`，最大回撤`{row['benchmark_max_drawdown']:.2%}`。"
        )

    first = summary_df.sort("roundtrip_cost_bps").row(0, named=True) if summary_df.height else None
    if first:
        lines.extend(
            [
                "",
                "## 交易结构",
                "",
                f"- 信号篮子数：`{first['signal_basket_count']}`；股票往返回合：`{first['stock_roundtrips']}`。",
                f"- 平均候选数：`{first['avg_candidate_count']:.1f}`；候选数中位：`{first['median_candidate_count']:.1f}`。",
                f"- 活跃交易日占比：`{first['active_day_ratio']:.2%}`；平均总暴露：`{first['avg_gross_exposure']:.2%}`；最大总暴露：`{first['max_gross_exposure']:.2%}`。",
                f"- 最大重叠篮子数：`{first['max_active_sleeves']}`；平均活跃股票腿数量：`{first['avg_active_stock_positions']:.1f}`。",
            ]
        )

    recent = basket_horizon.with_columns(pl.col("signal_date").dt.year().alias("year")).group_by("year").agg(
        pl.len().alias("basket_count"),
        pl.col("gross_basket_ret").mean().alias("gross_basket_ret_mean"),
        pl.col("gross_basket_excess_ret").mean().alias("gross_basket_excess_ret_mean"),
    ).sort("year")
    lines.extend(["", "## 年度篮子毛收益", ""])
    for row in recent.iter_rows(named=True):
        lines.append(
            f"- `{row['year']}`：篮子`{row['basket_count']}`个，毛绝对`{row['gross_basket_ret_mean']:.4%}`，毛超额`{row['gross_basket_excess_ret_mean']:.4%}`。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果路径收益主要来自少数深跌年份，后续不能靠提高频率或收窄阈值去追收益，应回到状态识别和风险预算。",
            "- 如果50bp后仍能维持正收益但回撤过深，下一步应先研究仓位节奏和市场风险开关，而不是扩大股票池或提高集中度。",
            "- 这一步仍不触发第78 A/B，也不接入正式策略。",
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
    """Run the fixed market-down long-only path backtest."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bucket_description, _bucket_expr = get_bucket_definition()
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    df = add_forward_returns(add_price_features(stock_df), benchmark_df).join(
        layer_tags, on=["datetime", "symbol"], how="left"
    )
    df = add_path_return_columns(df)
    top_df = build_selected_candidates(df)
    if top_df.is_empty():
        raise RuntimeError("No selected candidates.")

    basket_daily = build_basket_daily(top_df, benchmark_df)
    basket_horizon = build_basket_horizon(top_df)

    summary_rows: list[dict[str, Any]] = []
    equity_paths: list[pl.DataFrame] = []
    for cost_bps in COST_BPS:
        curve = build_equity_curve(basket_daily, benchmark_df, cost_bps)
        equity_paths.append(curve)
        summary_rows.append(summarize_curve(curve, basket_horizon, cost_bps, top_df))

    summary_df = pl.DataFrame(summary_rows).sort("roundtrip_cost_bps")
    equity_df = pl.concat(equity_paths, how="vertical").sort(["roundtrip_cost_bps", "pnl_date"])
    meta: dict[str, Any] = {
        "date_min": str(df["datetime"].min()),
        "date_max": str(df["datetime"].max()),
        "symbol_count": df["symbol"].n_unique(),
        "row_count": df.height,
        "feature": FEATURE,
        "horizon": HORIZON,
        "bucket": BUCKET,
        "bucket_description": bucket_description,
        "market_state": MARKET_STATE,
        "cost_bps": COST_BPS,
        "initial_equity": INITIAL_EQUITY,
        "stock_roundtrips": top_df.height,
        "signal_basket_count": basket_horizon.height,
        "path_model": "overlapping equal-weight daily sleeves, one sleeve uses 1/horizon capital",
    }

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    equity_path = OUTPUT_DIR / f"{PREFIX}_equity_curve.csv"
    basket_daily_path = OUTPUT_DIR / f"{PREFIX}_basket_daily.csv"
    basket_horizon_path = OUTPUT_DIR / f"{PREFIX}_basket_horizon.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    summary_df.write_csv(summary_path)
    equity_df.write_csv(equity_path)
    basket_daily.write_csv(basket_daily_path)
    basket_horizon.write_csv(basket_horizon_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        basket_horizon,
        meta,
        {
            "summary": summary_path,
            "equity_curve": equity_path,
            "basket_daily": basket_daily_path,
            "basket_horizon": basket_horizon_path,
            "meta": meta_path,
        },
    )
    print(summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
