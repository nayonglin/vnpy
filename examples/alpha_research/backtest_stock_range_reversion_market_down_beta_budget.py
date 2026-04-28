from __future__ import annotations

import json
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_market_down_beta_residual import (
    build_equity_and_drawdown,
    max_drawdown_window,
    product_return,
    safe_mean,
    safe_std,
)
from backtest_stock_range_reversion_market_down_long_only import INITIAL_EQUITY, TRADING_DAYS, to_float
from backtest_stock_range_reversion_market_down_merged_portfolio import (
    BUCKET,
    FEATURE,
    HORIZON,
    MARKET_STATE,
    OUTPUT_DIR as MERGED_OUTPUT_DIR,
    PREFIX as MERGED_PREFIX,
)


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_beta_budget_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_market_down_beta_budget_v1"
INPUT_EQUITY_PATH: Path = MERGED_OUTPUT_DIR / f"{MERGED_PREFIX}_equity_curve.csv"


@dataclass(frozen=True)
class BetaBudgetScenario:
    name: str
    category: str
    description: str
    tradability: str
    fixed_cash_scale: float | None = None
    vol_target: float | None = None
    max_scale: float = 1.0
    hedge_ratio: float = 0.0


SCENARIOS: tuple[BetaBudgetScenario, ...] = (
    BetaBudgetScenario(
        name="baseline_long_only",
        category="baseline",
        description="第218阶段合并持仓long-only baseline",
        tradability="tradable_long_only",
        fixed_cash_scale=1.0,
    ),
    BetaBudgetScenario(
        name="cash_scale_75",
        category="cash_scaling",
        description="全路径股票仓位固定缩放到75%，其余现金",
        tradability="tradable_long_only",
        fixed_cash_scale=0.75,
    ),
    BetaBudgetScenario(
        name="cash_scale_50",
        category="cash_scaling",
        description="全路径股票仓位固定缩放到50%，其余现金",
        tradability="tradable_long_only",
        fixed_cash_scale=0.50,
    ),
    BetaBudgetScenario(
        name="vol_target_15_max1",
        category="vol_target_scaling",
        description="用前20日中证1000年化波动做15%目标波动缩放，最大1倍股票仓位",
        tradability="tradable_long_only",
        vol_target=0.15,
        max_scale=1.0,
    ),
    BetaBudgetScenario(
        name="vol_target_10_max1",
        category="vol_target_scaling",
        description="用前20日中证1000年化波动做10%目标波动缩放，最大1倍股票仓位",
        tradability="tradable_long_only",
        vol_target=0.10,
        max_scale=1.0,
    ),
    BetaBudgetScenario(
        name="hedge_same_exposure_50_no_cost",
        category="hedge_attribution",
        description="按同暴露中证1000收益做50%名义对冲，不计对冲成本，仅归因",
        tradability="attribution_not_directly_tradable",
        fixed_cash_scale=1.0,
        hedge_ratio=0.50,
    ),
    BetaBudgetScenario(
        name="hedge_same_exposure_100_no_cost",
        category="hedge_attribution",
        description="按同暴露中证1000收益做100%名义对冲，不计对冲成本，仅归因",
        tradability="attribution_not_directly_tradable",
        fixed_cash_scale=1.0,
        hedge_ratio=1.0,
    ),
)


def prior_rolling_vol20(values: list[float]) -> list[float | None]:
    """Build prior 20-day annualized volatility from benchmark returns."""
    vols: list[float | None] = []
    for index in range(len(values)):
        if index < 20:
            vols.append(None)
            continue
        window = values[index - 20 : index]
        std = safe_std(window)
        vols.append(std * sqrt(TRADING_DAYS))
    return vols


def scenario_scale_values(cost_df: pl.DataFrame, scenario: BetaBudgetScenario) -> list[float]:
    """Return ex-ante stock exposure scale for each day."""
    if scenario.vol_target is None:
        return [scenario.fixed_cash_scale if scenario.fixed_cash_scale is not None else 1.0] * cost_df.height

    benchmark_rets = [to_float(value) for value in cost_df["benchmark_daily_ret"].to_list()]
    vol20_values = prior_rolling_vol20(benchmark_rets)
    scale_values: list[float] = []
    for vol in vol20_values:
        if vol is None or vol <= 0:
            scale_values.append(scenario.max_scale)
        else:
            scale_values.append(max(0.0, min(scenario.max_scale, scenario.vol_target / vol)))
    return scale_values


def add_budget_path(cost_df: pl.DataFrame, scenario: BetaBudgetScenario, scenario_order: int) -> pl.DataFrame:
    """Apply one beta-budget scenario to one cost curve."""
    scale_values = scenario_scale_values(cost_df, scenario)
    work = cost_df.sort("date").with_columns(pl.Series("stock_scale", scale_values))
    work = work.with_columns(
        (pl.col("strategy_gross_daily_ret") * pl.col("stock_scale")).alias("scaled_strategy_gross_daily_ret"),
        (pl.col("turnover_cost_ret") * pl.col("stock_scale")).alias("scaled_stock_cost_ret"),
        (pl.col("strategy_daily_ret") * pl.col("stock_scale")).alias("scaled_strategy_net_daily_ret"),
        (pl.col("benchmark_active_daily_ret") * pl.col("stock_scale")).alias(
            "scaled_same_exposure_benchmark_daily_ret"
        ),
        (pl.col("return_gross_exposure") * pl.col("stock_scale")).alias("scaled_long_gross_exposure"),
        (pl.col("one_way_turnover") * pl.col("stock_scale")).alias("scaled_one_way_turnover"),
    ).with_columns(
        (-scenario.hedge_ratio * pl.col("scaled_same_exposure_benchmark_daily_ret")).alias("hedge_daily_ret"),
        (scenario.hedge_ratio * pl.col("scaled_long_gross_exposure")).alias("hedge_notional"),
    ).with_columns(
        (pl.col("scaled_strategy_net_daily_ret") + pl.col("hedge_daily_ret")).alias("scenario_daily_ret"),
        (
            pl.col("scaled_long_gross_exposure") - scenario.hedge_ratio * pl.col("scaled_long_gross_exposure")
        ).alias("net_beta_exposure_proxy"),
    )

    returns = [to_float(value) for value in work["scenario_daily_ret"].to_list()]
    equity_values, drawdown_values = build_equity_and_drawdown(returns)
    return work.with_columns(
        pl.Series("scenario_equity", equity_values),
        pl.Series("scenario_drawdown", drawdown_values),
        pl.lit(scenario_order).alias("scenario_order"),
        pl.lit(scenario.name).alias("scenario"),
        pl.lit(scenario.category).alias("category"),
        pl.lit(scenario.description).alias("scenario_description"),
        pl.lit(scenario.tradability).alias("tradability"),
        pl.lit(scenario.hedge_ratio).alias("hedge_ratio"),
        pl.lit(scenario.vol_target, dtype=pl.Float64).alias("vol_target"),
        pl.lit(scenario.max_scale).alias("max_scale"),
        pl.lit(scenario.fixed_cash_scale, dtype=pl.Float64).alias("fixed_cash_scale"),
    )


def summarize_scenario(curve: pl.DataFrame) -> dict[str, Any]:
    """Summarize one scenario and cost path."""
    days = curve.height
    cost_bps = to_float(curve["roundtrip_cost_bps"][0]) if days else 0.0
    returns = [to_float(value) for value in curve["scenario_daily_ret"].to_list()]
    daily_mean = safe_mean(returns)
    daily_std = safe_std(returns)
    active_curve = curve.filter((pl.col("scaled_long_gross_exposure") > 0) | (pl.col("hedge_notional") > 0))
    active_returns = [to_float(value) for value in active_curve["scenario_daily_ret"].to_list()]
    total_return = to_float(curve["scenario_equity"][-1]) / INITIAL_EQUITY - 1 if days else 0.0
    return {
        "roundtrip_cost_bps": cost_bps,
        "scenario_order": int(curve["scenario_order"][0]) if days else -1,
        "scenario": curve["scenario"][0] if days else "",
        "category": curve["category"][0] if days else "",
        "tradability": curve["tradability"][0] if days else "",
        "scenario_description": curve["scenario_description"][0] if days else "",
        "days": days,
        "final_equity": to_float(curve["scenario_equity"][-1]) if days else INITIAL_EQUITY,
        "total_return": total_return,
        "annualized_return": (1 + total_return) ** (TRADING_DAYS / days) - 1
        if days and total_return > -1
        else 0.0,
        "max_drawdown": to_float(curve["scenario_drawdown"].min()) if days else 0.0,
        "sharpe": daily_mean / daily_std * sqrt(TRADING_DAYS) if daily_std else 0.0,
        "active_day_win_rate": safe_mean([1.0 if value > 0 else 0.0 for value in active_returns])
        if active_returns
        else 0.0,
        "avg_stock_scale": to_float(curve["stock_scale"].mean()) if days else 0.0,
        "median_stock_scale": to_float(curve["stock_scale"].median()) if days else 0.0,
        "min_stock_scale": to_float(curve["stock_scale"].min()) if days else 0.0,
        "avg_long_gross_exposure": to_float(curve["scaled_long_gross_exposure"].mean()) if days else 0.0,
        "max_long_gross_exposure": to_float(curve["scaled_long_gross_exposure"].max()) if days else 0.0,
        "avg_hedge_notional": to_float(curve["hedge_notional"].mean()) if days else 0.0,
        "max_hedge_notional": to_float(curve["hedge_notional"].max()) if days else 0.0,
        "avg_net_beta_exposure_proxy": to_float(curve["net_beta_exposure_proxy"].mean()) if days else 0.0,
        "annualized_one_way_turnover": to_float(curve["scaled_one_way_turnover"].mean()) * TRADING_DAYS
        if days
        else 0.0,
        "total_stock_cost_ret": to_float(curve["scaled_stock_cost_ret"].sum()) if days else 0.0,
    }


def build_summary(curves: pl.DataFrame) -> pl.DataFrame:
    """Build scenario summary rows."""
    rows: list[dict[str, Any]] = []
    for cost_bps in sorted(curves["roundtrip_cost_bps"].unique().to_list()):
        cost_df = curves.filter(pl.col("roundtrip_cost_bps") == cost_bps)
        for scenario_order in sorted(cost_df["scenario_order"].unique().to_list()):
            rows.append(summarize_scenario(cost_df.filter(pl.col("scenario_order") == scenario_order).sort("date")))
    return pl.DataFrame(rows).sort(["roundtrip_cost_bps", "scenario_order"])


def build_baseline_delta(summary_df: pl.DataFrame) -> pl.DataFrame:
    """Compare every scenario with long-only baseline at the same cost."""
    baseline = summary_df.filter(pl.col("scenario") == "baseline_long_only").select(
        "roundtrip_cost_bps",
        pl.col("final_equity").alias("baseline_final_equity"),
        pl.col("total_return").alias("baseline_total_return"),
        pl.col("max_drawdown").alias("baseline_max_drawdown"),
        pl.col("sharpe").alias("baseline_sharpe"),
        pl.col("avg_long_gross_exposure").alias("baseline_avg_long_gross_exposure"),
    )
    return (
        summary_df.join(baseline, on="roundtrip_cost_bps", how="left")
        .with_columns(
            (pl.col("total_return") - pl.col("baseline_total_return")).alias("total_return_delta"),
            (pl.col("max_drawdown") - pl.col("baseline_max_drawdown")).alias("max_drawdown_delta"),
            (pl.col("sharpe") - pl.col("baseline_sharpe")).alias("sharpe_delta"),
            (pl.col("avg_long_gross_exposure") - pl.col("baseline_avg_long_gross_exposure")).alias(
                "avg_long_exposure_delta"
            ),
            (pl.col("final_equity") / pl.col("baseline_final_equity") - 1).alias("final_equity_ratio_delta"),
        )
        .sort(["roundtrip_cost_bps", "scenario_order"])
    )


def build_drawdown_windows(curves: pl.DataFrame) -> pl.DataFrame:
    """Build max drawdown windows for every scenario."""
    rows: list[dict[str, Any]] = []
    for cost_bps in sorted(curves["roundtrip_cost_bps"].unique().to_list()):
        cost_df = curves.filter(pl.col("roundtrip_cost_bps") == cost_bps)
        for scenario_order in sorted(cost_df["scenario_order"].unique().to_list()):
            scenario_df = cost_df.filter(pl.col("scenario_order") == scenario_order).sort("date")
            dates = scenario_df["date"].to_list()
            equity_values = [to_float(value) for value in scenario_df["scenario_equity"].to_list()]
            window = max_drawdown_window(dates, equity_values)
            segment = scenario_df.filter(
                (pl.col("date") > window["peak_date"]) & (pl.col("date") <= window["trough_date"])
            )
            rows.append(
                {
                    "roundtrip_cost_bps": cost_bps,
                    "scenario_order": scenario_order,
                    "scenario": scenario_df["scenario"][0],
                    "category": scenario_df["category"][0],
                    "tradability": scenario_df["tradability"][0],
                    **window,
                    "window_scenario_return": product_return(
                        [to_float(value) for value in segment["scenario_daily_ret"].to_list()]
                    ),
                    "window_scaled_strategy_net_return": product_return(
                        [to_float(value) for value in segment["scaled_strategy_net_daily_ret"].to_list()]
                    ),
                    "window_hedge_return": product_return(
                        [to_float(value) for value in segment["hedge_daily_ret"].to_list()]
                    ),
                    "window_same_exposure_benchmark_return": product_return(
                        [to_float(value) for value in segment["scaled_same_exposure_benchmark_daily_ret"].to_list()]
                    ),
                    "window_raw_benchmark_return": product_return(
                        [to_float(value) for value in segment["benchmark_daily_ret"].to_list()]
                    ),
                    "window_avg_stock_scale": to_float(segment["stock_scale"].mean()) if segment.height else 0.0,
                    "window_avg_long_gross_exposure": to_float(segment["scaled_long_gross_exposure"].mean())
                    if segment.height
                    else 0.0,
                    "window_avg_hedge_notional": to_float(segment["hedge_notional"].mean()) if segment.height else 0.0,
                }
            )
    return pl.DataFrame(rows).sort(["roundtrip_cost_bps", "scenario_order"])


def build_year_summary(curves: pl.DataFrame) -> pl.DataFrame:
    """Build annual scenario returns and average risk budget."""
    return (
        curves.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["roundtrip_cost_bps", "scenario_order", "scenario", "category", "tradability", "year"])
        .agg(
            ((1 + pl.col("scenario_daily_ret")).product() - 1).alias("year_return"),
            ((1 + pl.col("scaled_strategy_net_daily_ret")).product() - 1).alias("year_scaled_stock_return"),
            ((1 + pl.col("hedge_daily_ret")).product() - 1).alias("year_hedge_return"),
            pl.col("scaled_stock_cost_ret").sum().alias("year_stock_cost_ret"),
            pl.col("stock_scale").mean().alias("avg_stock_scale"),
            pl.col("scaled_long_gross_exposure").mean().alias("avg_long_gross_exposure"),
            pl.col("hedge_notional").mean().alias("avg_hedge_notional"),
        )
        .sort(["roundtrip_cost_bps", "scenario_order", "year"])
    )


def build_scale_summary(curves: pl.DataFrame) -> pl.DataFrame:
    """Summarize scale distributions."""
    return (
        curves.group_by(["roundtrip_cost_bps", "scenario_order", "scenario", "category", "tradability"])
        .agg(
            pl.col("stock_scale").mean().alias("avg_stock_scale"),
            pl.col("stock_scale").min().alias("min_stock_scale"),
            pl.col("stock_scale").quantile(0.10).alias("p10_stock_scale"),
            pl.col("stock_scale").median().alias("median_stock_scale"),
            pl.col("stock_scale").quantile(0.90).alias("p90_stock_scale"),
            pl.col("stock_scale").max().alias("max_stock_scale"),
            pl.col("scaled_long_gross_exposure").mean().alias("avg_long_gross_exposure"),
            pl.col("hedge_notional").mean().alias("avg_hedge_notional"),
        )
        .sort(["roundtrip_cost_bps", "scenario_order"])
    )


def write_report(
    summary_df: pl.DataFrame,
    delta_df: pl.DataFrame,
    drawdown_df: pl.DataFrame,
    year_df: pl.DataFrame,
    scale_df: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    """Write a Chinese report for beta budget pressure testing."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡 market_down beta预算压力测试 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是新正式策略，也不是参数寻优；只用固定粗场景测试第222阶段指出的市场beta承载问题。",
        f"- 固定股票信号：`{MARKET_STATE}`、`{BUCKET}`、`{FEATURE}`，持有`{HORIZON}`日，沿用第218阶段合并持仓净换手曲线。",
        "- `cash_scaling`和`vol_target_scaling`是long-only可交易降速口径；`hedge_attribution`只是同暴露指数对冲归因，不计对冲成本，不作为实盘结果。",
        f"- 输入曲线：`{INPUT_EQUITY_PATH}`。",
        "",
        "## 总体结果",
        "",
    ]
    for cost_bps in sorted(summary_df["roundtrip_cost_bps"].unique().to_list()):
        lines.append(f"### 成本`{cost_bps:.0f}bp`")
        for row in summary_df.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("scenario_order").iter_rows(
            named=True
        ):
            lines.append(
                f"- `{row['scenario']}` `{row['tradability']}`：期末权益`{row['final_equity']:.4f}`，"
                f"总收益`{row['total_return']:.2%}`，最大回撤`{row['max_drawdown']:.2%}`，"
                f"Sharpe `{row['sharpe']:.2f}`，平均股票缩放`{row['avg_stock_scale']:.2%}`，"
                f"平均股票暴露`{row['avg_long_gross_exposure']:.2%}`，平均对冲名义`{row['avg_hedge_notional']:.2%}`。"
            )

    lines.extend(["", "## 相对long-only baseline", ""])
    for row in delta_df.filter(pl.col("scenario") != "baseline_long_only").iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['scenario']}`："
            f"总收益变化`{row['total_return_delta']:.2%}`，最大回撤变化`{row['max_drawdown_delta']:.2%}`，"
            f"Sharpe变化`{row['sharpe_delta']:.2f}`，平均股票暴露变化`{row['avg_long_exposure_delta']:.2%}`。"
        )

    lines.extend(["", "## 最大回撤窗口", ""])
    for row in drawdown_df.sort(["roundtrip_cost_bps", "scenario_order"]).iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['scenario']}`："
            f"peak=`{row['peak_date']}`，trough=`{row['trough_date']}`，"
            f"maxDD=`{row['max_drawdown']:.2%}`，窗口收益`{row['window_scenario_return']:.2%}`，"
            f"窗口平均股票缩放`{row['window_avg_stock_scale']:.2%}`，窗口平均股票暴露`{row['window_avg_long_gross_exposure']:.2%}`。"
        )

    lines.extend(["", "## 压力年份", ""])
    for row in year_df.filter(pl.col("year").is_in([2018, 2022, 2024])).sort(
        ["roundtrip_cost_bps", "scenario_order", "year"]
    ).iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['scenario']}` `{row['year']}`："
            f"收益`{row['year_return']:.2%}`，平均股票缩放`{row['avg_stock_scale']:.2%}`，"
            f"平均股票暴露`{row['avg_long_gross_exposure']:.2%}`。"
        )

    lines.extend(["", "## 缩放分布", ""])
    for row in scale_df.sort(["roundtrip_cost_bps", "scenario_order"]).iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['scenario']}`："
            f"均值`{row['avg_stock_scale']:.2%}`，p10`{row['p10_stock_scale']:.2%}`，"
            f"中位`{row['median_stock_scale']:.2%}`，p90`{row['p90_stock_scale']:.2%}`。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果long-only缩放只能靠大幅降低暴露来换回撤，说明当前股票震荡不能直接正式化，只能作为小仓位卫星或继续研究。",
            "- 如果对冲归因显著改善而现金缩放不够，则后续必须先解决可交易对冲工具和成本，不能把归因曲线当实盘。",
            "- 本阶段不触发第78 A/B，也不接入正式股票策略。",
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
    """Run fixed beta budget pressure tests on the merged market-down baseline."""
    if not INPUT_EQUITY_PATH.exists():
        raise FileNotFoundError(f"Missing merged equity curve: {INPUT_EQUITY_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = pl.read_csv(INPUT_EQUITY_PATH, try_parse_dates=True).sort(["roundtrip_cost_bps", "date"])

    curve_frames: list[pl.DataFrame] = []
    for cost_bps in sorted(source["roundtrip_cost_bps"].unique().to_list()):
        cost_df = source.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("date")
        for scenario_order, scenario in enumerate(SCENARIOS):
            curve_frames.append(add_budget_path(cost_df, scenario, scenario_order))
    curves = pl.concat(curve_frames, how="vertical").sort(["roundtrip_cost_bps", "scenario_order", "date"])
    summary_df = build_summary(curves)
    delta_df = build_baseline_delta(summary_df)
    drawdown_df = build_drawdown_windows(curves)
    year_df = build_year_summary(curves)
    scale_df = build_scale_summary(curves)

    meta: dict[str, Any] = {
        "feature": FEATURE,
        "bucket": BUCKET,
        "horizon": HORIZON,
        "market_state": MARKET_STATE,
        "input_equity_path": str(INPUT_EQUITY_PATH),
        "date_min": str(curves["date"].min()),
        "date_max": str(curves["date"].max()),
        "cost_bps": sorted(curves["roundtrip_cost_bps"].unique().to_list()),
        "scenarios": [scenario.__dict__ for scenario in SCENARIOS],
        "note": "hedge_attribution scenarios do not include index hedge costs or real shorting constraints.",
    }

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    delta_path = OUTPUT_DIR / f"{PREFIX}_baseline_delta.csv"
    curves_path = OUTPUT_DIR / f"{PREFIX}_equity_curve.csv"
    drawdown_path = OUTPUT_DIR / f"{PREFIX}_drawdown_windows.csv"
    year_path = OUTPUT_DIR / f"{PREFIX}_year_summary.csv"
    scale_path = OUTPUT_DIR / f"{PREFIX}_scale_summary.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    summary_df.write_csv(summary_path)
    delta_df.write_csv(delta_path)
    curves.write_csv(curves_path)
    drawdown_df.write_csv(drawdown_path)
    year_df.write_csv(year_path)
    scale_df.write_csv(scale_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        delta_df,
        drawdown_df,
        year_df,
        scale_df,
        {
            "summary": summary_path,
            "baseline_delta": delta_path,
            "equity_curve": curves_path,
            "drawdown_windows": drawdown_path,
            "year_summary": year_path,
            "scale_summary": scale_path,
            "meta": meta_path,
        },
    )
    print(summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
