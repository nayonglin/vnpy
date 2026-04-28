from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from backtest_stock_range_reversion_market_down_merged_portfolio import (
    BUCKET,
    COST_BPS,
    FEATURE,
    HORIZON,
    MARKET_STATE,
    OUTPUT_DIR as MERGED_OUTPUT_DIR,
    PREFIX as MERGED_PREFIX,
    TRADING_DAYS,
    build_benchmark_daily,
    build_calendar,
    build_concentration,
    build_daily_gross,
    build_equity_curve,
    build_lots,
    build_selected_frame,
    build_symbol_daily,
    build_symbol_exposure_summary,
    build_turnover,
    summarize_curve,
    to_float,
)
from backtest_stock_range_reversion_market_down_risk_budget import (
    SCENARIOS,
    RiskScenario,
    build_trading_index,
    select_signal_dates,
)


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_merged_risk_budget_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_market_down_merged_risk_budget_v1"


def filter_selected_by_dates(selected: pl.DataFrame, accepted_dates: list[Any]) -> pl.DataFrame:
    """Keep only rows whose signal date is accepted by the risk scenario."""
    accepted_series = pl.Series("datetime", accepted_dates).implode()
    return selected.filter(pl.col("datetime").is_in(accepted_series))


def add_scenario_columns(df: pl.DataFrame, scenario: RiskScenario, scenario_order: int) -> pl.DataFrame:
    """Attach scenario metadata to an output frame."""
    return df.with_columns(
        pl.lit(scenario.name).alias("scenario"),
        pl.lit(scenario.description).alias("scenario_description"),
        pl.lit(scenario_order).alias("scenario_order"),
    )


def run_scenario(
    selected: pl.DataFrame,
    benchmark_daily: pl.DataFrame,
    calendar: pl.DataFrame,
    accepted_dates: list[Any],
    scenario: RiskScenario,
    scenario_order: int,
) -> tuple[list[dict[str, Any]], list[pl.DataFrame], pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Run one merged-holding risk scenario for all cost assumptions."""
    accepted_selected = filter_selected_by_dates(selected, accepted_dates)
    lots = build_lots(accepted_selected)
    symbol_daily = build_symbol_daily(lots)
    turnover, target_weights = build_turnover(symbol_daily, calendar)
    concentration = build_concentration(symbol_daily, calendar)
    daily_gross = build_daily_gross(symbol_daily)
    symbol_exposure = build_symbol_exposure_summary(symbol_daily)

    summary_rows: list[dict[str, Any]] = []
    curves: list[pl.DataFrame] = []
    for cost_bps in COST_BPS:
        curve = build_equity_curve(daily_gross, turnover, benchmark_daily, calendar, cost_bps)
        curve = add_scenario_columns(curve, scenario, scenario_order)
        curves.append(curve)
        row = summarize_curve(curve, turnover, concentration, accepted_selected, cost_bps)
        row.update(
            {
                "scenario": scenario.name,
                "scenario_description": scenario.description,
                "scenario_order": scenario_order,
                "accepted_signal_baskets": len(accepted_dates),
                "acceptance_ratio": len(accepted_dates) / selected["datetime"].n_unique(),
                "accepted_stock_roundtrips": accepted_selected.height,
            }
        )
        summary_rows.append(row)

    return (
        summary_rows,
        curves,
        add_scenario_columns(turnover, scenario, scenario_order),
        add_scenario_columns(concentration, scenario, scenario_order),
        add_scenario_columns(target_weights, scenario, scenario_order),
        add_scenario_columns(symbol_exposure, scenario, scenario_order),
    )


def build_year_summary(equity_df: pl.DataFrame, decisions_df: pl.DataFrame) -> pl.DataFrame:
    """Summarize annual path and signal acceptance by scenario."""
    year_path = (
        equity_df.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["scenario_order", "scenario", "roundtrip_cost_bps", "year"])
        .agg(
            ((1 + pl.col("strategy_daily_ret")).product() - 1).alias("year_return"),
            ((1 + pl.col("strategy_gross_daily_ret")).product() - 1).alias("year_gross_return"),
            ((1 + pl.col("benchmark_active_daily_ret")).product() - 1).alias("year_benchmark_return"),
            pl.col("turnover_cost_ret").sum().alias("year_cost_drag"),
            pl.col("gross_abs_weight_change").sum().alias("year_gross_abs_weight_change"),
            pl.col("return_gross_exposure").mean().alias("avg_gross_exposure"),
            pl.col("strategy_drawdown").min().alias("min_drawdown_seen"),
        )
    )
    year_decisions = (
        decisions_df.with_columns(pl.col("signal_date").dt.year().alias("year"))
        .group_by(["scenario_order", "scenario", "year"])
        .agg(
            pl.len().alias("signal_baskets"),
            pl.col("accepted").sum().alias("accepted_signal_baskets"),
            (pl.col("accepted").sum() / pl.len()).alias("acceptance_ratio"),
        )
    )
    return (
        year_path.join(year_decisions, on=["scenario_order", "scenario", "year"], how="left")
        .sort(["roundtrip_cost_bps", "scenario_order", "year"])
    )


def summarize_baseline_delta(summary_df: pl.DataFrame) -> pl.DataFrame:
    """Compare each scenario with the merged-holding baseline at the same cost."""
    baseline = summary_df.filter(pl.col("scenario") == "baseline").select(
        "roundtrip_cost_bps",
        pl.col("total_return").alias("baseline_total_return"),
        pl.col("max_drawdown").alias("baseline_max_drawdown"),
        pl.col("avg_gross_exposure").alias("baseline_avg_gross_exposure"),
        pl.col("final_equity").alias("baseline_final_equity"),
    )
    return (
        summary_df.join(baseline, on="roundtrip_cost_bps", how="left")
        .with_columns(
            (pl.col("total_return") - pl.col("baseline_total_return")).alias("total_return_delta"),
            (pl.col("max_drawdown") - pl.col("baseline_max_drawdown")).alias("max_drawdown_delta"),
            (pl.col("avg_gross_exposure") - pl.col("baseline_avg_gross_exposure")).alias("avg_exposure_delta"),
            (pl.col("final_equity") / pl.col("baseline_final_equity") - 1).alias("final_equity_ratio_delta"),
        )
        .sort(["roundtrip_cost_bps", "scenario_order"])
    )


def write_report(
    summary_df: pl.DataFrame,
    delta_df: pl.DataFrame,
    year_df: pl.DataFrame,
    decisions_df: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    """Write a Chinese report for merged-holding risk-budget pressure tests."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡 market_down 合并持仓风险预算压力测试 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是新策略版本，也不是参数优化；只把第216阶段机械风控迁移到第218阶段真实合并持仓账本。",
        f"- 固定口径：`{MARKET_STATE}`、`{BUCKET}`、`{FEATURE}`、固定持有`{HORIZON}`日；成本情景：`{', '.join(str(x) for x in COST_BPS)}bp`。",
        "- 风控约束只看重叠篮子上限和信号间隔，不使用行业收益、未来收益或回撤段信息生成规则。",
        "",
        "## 总体结果",
        "",
    ]

    for cost_bps in sorted(summary_df["roundtrip_cost_bps"].unique().to_list()):
        lines.append(f"### 成本`{cost_bps:.0f}bp`")
        focus = summary_df.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("scenario_order")
        for row in focus.iter_rows(named=True):
            lines.append(
                f"- `{row['scenario']}`：接受篮子`{row['accepted_signal_baskets']}`个，"
                f"接受率`{row['acceptance_ratio']:.2%}`，期末权益`{row['final_equity']:.4f}`，"
                f"总收益`{row['total_return']:.2%}`，最大回撤`{row['max_drawdown']:.2%}`，"
                f"Sharpe `{row['sharpe']:.2f}`，平均暴露`{row['avg_gross_exposure']:.2%}`，"
                f"年化单边换手`{row['annualized_one_way_turnover']:.2f}`倍。"
            )

    lines.extend(["", "## 相对baseline变化", ""])
    for row in delta_df.filter(pl.col("scenario") != "baseline").iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['scenario']}`："
            f"总收益变化`{row['total_return_delta']:.2%}`，最大回撤变化`{row['max_drawdown_delta']:.2%}`，"
            f"平均暴露变化`{row['avg_exposure_delta']:.2%}`，期末权益相对变化`{row['final_equity_ratio_delta']:.2%}`。"
        )

    lines.extend(["", "## 2018/2022压力年份", ""])
    stress_years = year_df.filter(pl.col("year").is_in([2018, 2022])).sort(
        ["roundtrip_cost_bps", "scenario_order", "year"]
    )
    for row in stress_years.iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['scenario']}` `{row['year']}`："
            f"净收益`{row['year_return']:.2%}`，年内最低回撤`{row['min_drawdown_seen']:.2%}`，"
            f"平均暴露`{row['avg_gross_exposure']:.2%}`，接受篮子`{row['accepted_signal_baskets']}`。"
        )

    lines.extend(["", "## 信号拒绝原因", ""])
    rejection = (
        decisions_df.filter(~pl.col("accepted"))
        .group_by(["scenario_order", "scenario", "reject_reason"])
        .agg(pl.len().alias("rejected_count"))
        .sort(["scenario_order", "reject_reason"])
    )
    for row in rejection.iter_rows(named=True):
        lines.append(
            f"- `{row['scenario']}` `{row['reject_reason']}`：拒绝`{row['rejected_count']}`个信号篮子。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果回撤下降主要伴随收益和暴露同比例下降，说明简单风控只是削弱仓位，不是提高信号质量。",
            "- 如果合并持仓后的风控仍不能显著改善Sharpe，下一步应回到市场状态变量识别，而不是继续找更细的重叠阈值。",
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
    """Run merged-holding mechanical risk-budget pressure tests."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    selected, benchmark_df, selected_meta = build_selected_frame()
    baseline_lots = build_lots(selected)
    full_start = min(baseline_lots["target_date"].min(), baseline_lots["pnl_date"].min())
    full_end = max(baseline_lots["target_date"].max(), baseline_lots["pnl_date"].max())
    calendar = build_calendar(benchmark_df, full_start, full_end)
    benchmark_daily = build_benchmark_daily(benchmark_df)
    trading_index = build_trading_index(benchmark_df)
    signal_dates = selected.select("datetime").unique().sort("datetime")["datetime"].to_list()

    summary_rows: list[dict[str, Any]] = []
    equity_frames: list[pl.DataFrame] = []
    decision_frames: list[pl.DataFrame] = []
    turnover_frames: list[pl.DataFrame] = []
    concentration_frames: list[pl.DataFrame] = []
    target_weight_frames: list[pl.DataFrame] = []
    symbol_exposure_frames: list[pl.DataFrame] = []

    for scenario_order, scenario in enumerate(SCENARIOS):
        accepted_dates, decisions = select_signal_dates(signal_dates, trading_index, scenario)
        decisions = add_scenario_columns(decisions, scenario, scenario_order)
        decision_frames.append(decisions)
        (
            scenario_rows,
            scenario_curves,
            scenario_turnover,
            scenario_concentration,
            scenario_target_weights,
            scenario_symbol_exposure,
        ) = run_scenario(selected, benchmark_daily, calendar, accepted_dates, scenario, scenario_order)
        summary_rows.extend(scenario_rows)
        equity_frames.extend(scenario_curves)
        turnover_frames.append(scenario_turnover)
        concentration_frames.append(scenario_concentration)
        target_weight_frames.append(scenario_target_weights)
        symbol_exposure_frames.append(scenario_symbol_exposure)

    summary_df = pl.DataFrame(summary_rows).sort(["roundtrip_cost_bps", "scenario_order"])
    equity_df = pl.concat(equity_frames, how="vertical").sort(["roundtrip_cost_bps", "scenario_order", "date"])
    decisions_df = pl.concat(decision_frames, how="vertical").sort(["scenario_order", "signal_date"])
    turnover_df = pl.concat(turnover_frames, how="vertical").sort(["scenario_order", "target_date"])
    concentration_df = pl.concat(concentration_frames, how="vertical").sort(["scenario_order", "target_date"])
    target_weights_df = pl.concat(target_weight_frames, how="vertical").sort(["scenario_order", "target_date", "symbol"])
    symbol_exposure_df = pl.concat(symbol_exposure_frames, how="vertical").sort(
        ["scenario_order", "max_target_weight"], descending=[False, True]
    )
    year_df = build_year_summary(equity_df, decisions_df)
    delta_df = summarize_baseline_delta(summary_df)
    meta: dict[str, Any] = {
        **selected_meta,
        "source_merged_dir": str(MERGED_OUTPUT_DIR),
        "source_merged_prefix": MERGED_PREFIX,
        "feature": FEATURE,
        "horizon": HORIZON,
        "market_state": MARKET_STATE,
        "cost_bps": COST_BPS,
        "scenario_count": len(SCENARIOS),
        "scenarios": [scenario.__dict__ for scenario in SCENARIOS],
        "full_start": str(full_start),
        "full_end": str(full_end),
        "trading_days": TRADING_DAYS,
    }

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    delta_path = OUTPUT_DIR / f"{PREFIX}_baseline_delta.csv"
    equity_path = OUTPUT_DIR / f"{PREFIX}_equity_curve.csv"
    year_path = OUTPUT_DIR / f"{PREFIX}_year_summary.csv"
    decisions_path = OUTPUT_DIR / f"{PREFIX}_signal_decisions.csv"
    turnover_path = OUTPUT_DIR / f"{PREFIX}_turnover.csv"
    concentration_path = OUTPUT_DIR / f"{PREFIX}_daily_concentration.csv"
    target_weights_path = OUTPUT_DIR / f"{PREFIX}_target_weights.csv"
    symbol_exposure_path = OUTPUT_DIR / f"{PREFIX}_symbol_exposure.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    summary_df.write_csv(summary_path)
    delta_df.write_csv(delta_path)
    equity_df.write_csv(equity_path)
    year_df.write_csv(year_path)
    decisions_df.write_csv(decisions_path)
    turnover_df.write_csv(turnover_path)
    concentration_df.write_csv(concentration_path)
    target_weights_df.write_csv(target_weights_path)
    symbol_exposure_df.write_csv(symbol_exposure_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        delta_df,
        year_df,
        decisions_df,
        meta,
        {
            "summary": summary_path,
            "baseline_delta": delta_path,
            "equity_curve": equity_path,
            "year_summary": year_path,
            "signal_decisions": decisions_path,
            "turnover": turnover_path,
            "daily_concentration": concentration_path,
            "target_weights": target_weights_path,
            "symbol_exposure": symbol_exposure_path,
            "meta": meta_path,
        },
    )
    print(summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
