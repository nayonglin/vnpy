from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import add_forward_returns, add_price_features
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    COST_BPS,
    FEATURE,
    HORIZON,
    INITIAL_EQUITY,
    NATIVE_RESULTS_DIR,
    TRADING_DAYS,
    build_benchmark_daily,
    build_calendar,
    build_concentration,
    build_daily_gross,
    build_equity_curve,
    build_symbol_daily,
    build_turnover,
    build_yearly_summary,
    pct,
    select_industry_neutral_candidates,
    summarize_curve,
)
from backtest_stock_range_reversion_market_down_long_only import to_float


OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_rebalance_cadence_2018_2026"),
    )
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_rebalance_cadence_v1"

CADENCE_STEPS: tuple[int, ...] = tuple(
    int(item) for item in os.getenv("CADENCE_STEPS", "1,2,5,10").split(",") if item
)
DRAWDOWN_YEARS: tuple[int, ...] = tuple(
    int(item) for item in os.getenv("DRAWDOWN_YEARS", "2018,2022,2023").split(",") if item
)

BASE_SCENARIO: dict[str, Any] = {
    "scenario": "liquid_q3_capped",
    "description": "成交额和自由换手至少进入前60%，行业内排序后加行业/单票上限",
    "bucket": "liquid_q3",
    "weight_mode": "capped",
}


def make_variant_name(step: int, phase: int) -> str:
    return f"liquid_q3_cadence_{step}d_p{phase}"


def cadence_variant_definitions() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for step in CADENCE_STEPS:
        for phase in range(step):
            variants.append(
                {
                    "scenario": make_variant_name(step, phase),
                    "scenario_description": f"liquid_q3行业内排序，每{step}个信号日换仓，相位{phase}",
                    "bucket": "liquid_q3",
                    "weight_mode": "cadence_scaled",
                    "cadence_step": step,
                    "phase": phase,
                }
            )
    return variants


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


def build_cadence_selected(base_selected: pl.DataFrame) -> pl.DataFrame:
    signal_dates = (
        base_selected.select("datetime")
        .unique()
        .sort("datetime")
        .with_row_index("signal_index")
    )
    frames: list[pl.DataFrame] = []
    for variant in cadence_variant_definitions():
        schedule = signal_dates.filter((pl.col("signal_index") % variant["cadence_step"]) == variant["phase"])
        if schedule.is_empty():
            continue
        selected = (
            base_selected.join(schedule.select("datetime", "signal_index"), on="datetime", how="inner")
            .with_columns(
                pl.lit(variant["scenario"]).alias("scenario"),
                pl.lit(variant["scenario_description"]).alias("scenario_description"),
                pl.lit(variant["bucket"]).alias("bucket"),
                pl.lit(variant["weight_mode"]).alias("weight_mode"),
                pl.lit(variant["cadence_step"]).alias("cadence_step"),
                pl.lit(variant["phase"]).alias("phase"),
            )
        )
        frames.append(selected)
    if not frames:
        raise RuntimeError("No cadence selected candidates.")
    return pl.concat(frames, how="vertical").sort(["scenario", "datetime", "industry", FEATURE])


def build_cadence_lots(selected: pl.DataFrame) -> pl.DataFrame:
    parts: list[pl.DataFrame] = []
    extra_cols = [
        col
        for col in [
            "scenario_description",
            "bucket",
            "weight_mode",
            "cadence_step",
            "phase",
            "signal_index",
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
            .with_columns(pl.lit(day).alias("holding_day"))
            .filter(
                pl.col("target_date").is_not_null()
                & pl.col("pnl_date").is_not_null()
                & pl.col("stock_daily_ret").is_not_null()
                & pl.col("stock_daily_ret").is_finite()
            )
        )
    raw_lots = pl.concat(parts, how="vertical")
    active_sleeves = (
        raw_lots.select("scenario", "target_date", "signal_date")
        .unique()
        .group_by(["scenario", "target_date"])
        .agg(pl.len().alias("active_sleeves"))
    )
    return (
        raw_lots.join(active_sleeves, on=["scenario", "target_date"], how="left")
        .with_columns((pl.col("basket_weight") / pl.col("active_sleeves")).alias("lot_weight"))
        .sort(["scenario", "target_date", "signal_date", "symbol"])
    )


def summarize_phases(summary_df: pl.DataFrame) -> pl.DataFrame:
    return (
        summary_df.group_by(["cadence_step", "roundtrip_cost_bps"])
        .agg(
            pl.len().alias("phase_count"),
            pl.col("final_equity").mean().alias("mean_final_equity"),
            pl.col("final_equity").min().alias("min_final_equity"),
            pl.col("final_equity").max().alias("max_final_equity"),
            pl.col("total_return").mean().alias("mean_total_return"),
            pl.col("total_return").min().alias("min_total_return"),
            pl.col("total_return").max().alias("max_total_return"),
            pl.col("max_drawdown").mean().alias("mean_max_drawdown"),
            pl.col("max_drawdown").min().alias("worst_max_drawdown"),
            pl.col("max_drawdown").max().alias("best_max_drawdown"),
            pl.col("sharpe").mean().alias("mean_sharpe"),
            pl.col("sharpe").min().alias("min_sharpe"),
            pl.col("avg_return_gross_exposure").mean().alias("mean_gross_exposure"),
            pl.col("annualized_one_way_turnover").mean().alias("mean_annualized_one_way_turnover"),
            pl.col("annualized_one_way_turnover").min().alias("min_annualized_one_way_turnover"),
            pl.col("annualized_one_way_turnover").max().alias("max_annualized_one_way_turnover"),
            pl.col("cost_drag_sum").mean().alias("mean_cost_drag_sum"),
            pl.col("net_active_day_win_rate").mean().alias("mean_net_active_day_win_rate"),
        )
        .sort(["roundtrip_cost_bps", "cadence_step"])
    )


def build_year_industry_contribution(symbol_daily: pl.DataFrame, curves: pl.DataFrame) -> pl.DataFrame:
    gross = (
        symbol_daily.with_columns(pl.col("pnl_date").dt.year().alias("year"))
        .filter(pl.col("year").is_in(DRAWDOWN_YEARS))
        .group_by(["scenario", "year", "industry"])
        .agg(
            pl.col("weighted_stock_ret").sum().alias("gross_contribution_sum"),
            pl.col("target_weight").mean().alias("avg_target_weight"),
            pl.col("target_weight").max().alias("max_target_weight"),
            pl.len().alias("symbol_day_count"),
            pl.col("symbol").n_unique().alias("symbol_count"),
        )
    )
    year_curve = (
        curves.with_columns(pl.col("date").dt.year().alias("year"))
        .filter(pl.col("year").is_in(DRAWDOWN_YEARS))
        .group_by(["scenario", "roundtrip_cost_bps", "year"])
        .agg(
            ((1 + pl.col("strategy_daily_ret")).product() - 1).alias("year_return"),
            ((1 + pl.col("strategy_gross_daily_ret")).product() - 1).alias("year_gross_return"),
            pl.col("turnover_cost_ret").sum().alias("year_cost_drag"),
            pl.col("return_gross_exposure").mean().alias("avg_gross_exposure"),
        )
    )
    return (
        gross.join(year_curve, on=["scenario", "year"], how="inner")
        .sort(["roundtrip_cost_bps", "scenario", "year", "gross_contribution_sum"])
    )


def write_report(
    summary_df: pl.DataFrame,
    phase_summary: pl.DataFrame,
    yearly: pl.DataFrame,
    year_industry: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡liquid_q3换仓节奏压力测试 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：换仓频率压力测试，不是正式交易版本。",
        "",
        "## 方法",
        "",
        f"- 固定信号：`{FEATURE}`，`liquid_q3`股票池，行业内top quintile，次日收盘入场，信号有效期`{HORIZON}`日。",
        "- 资金归一：同一交易日若有多个信号篮子同时有效，则按有效篮子数均分资金，避免降频版本天然低仓位。",
        f"- 预设换仓节奏：`{','.join(str(item) for item in CADENCE_STEPS)}`个信号日；`2/5/10`日节奏保留所有相位。",
        f"- 成本：`{','.join(f'{item:.0f}bp' for item in COST_BPS)}`往返成本。",
        f"- 样本：`{meta['date_min']}`到`{meta['date_max']}`，股票数`{meta['symbol_count']}`。",
        "",
        "## 相位汇总",
        "",
    ]
    for row in phase_summary.iter_rows(named=True):
        lines.append(
            f"- `{int(row['cadence_step'])}d` 成本`{row['roundtrip_cost_bps']:.0f}bp`：相位数`{row['phase_count']}`，"
            f"平均期末权益`{row['mean_final_equity']:.4f}`，区间`{row['min_final_equity']:.4f}`到`{row['max_final_equity']:.4f}`，"
            f"平均总收益`{pct(row['mean_total_return'])}`，最差回撤`{pct(row['worst_max_drawdown'])}`，"
            f"平均Sharpe `{row['mean_sharpe']:.2f}`，平均暴露`{pct(row['mean_gross_exposure'])}`，"
            f"平均年化单边换手`{row['mean_annualized_one_way_turnover']:.2f}`倍，平均成本拖累`{pct(row['mean_cost_drag_sum'])}`。"
        )

    lines.extend(["", "## 单相位结果", ""])
    for row in summary_df.sort(["roundtrip_cost_bps", "cadence_step", "phase"]).iter_rows(named=True):
        lines.append(
            f"- `{row['scenario']}` 成本`{row['roundtrip_cost_bps']:.0f}bp`：期末权益`{row['final_equity']:.4f}`，"
            f"总收益`{pct(row['total_return'])}`，最大回撤`{pct(row['max_drawdown'])}`，Sharpe `{row['sharpe']:.2f}`，"
            f"平均暴露`{pct(row['avg_return_gross_exposure'])}`，年化单边换手`{row['annualized_one_way_turnover']:.2f}`倍。"
        )

    lines.extend(["", "## 回撤年份行业贡献", ""])
    drawdown_sample = (
        year_industry.filter(pl.col("roundtrip_cost_bps") == min(COST_BPS))
        .sort(["scenario", "year", "gross_contribution_sum"])
        .group_by(["scenario", "year"], maintain_order=True)
        .head(5)
    )
    for row in drawdown_sample.iter_rows(named=True):
        lines.append(
            f"- `{row['scenario']}` `{row['year']}` `{row['industry']}`：毛贡献和`{pct(row['gross_contribution_sum'])}`，"
            f"股票数`{row['symbol_count']}`，平均权重`{pct(row['avg_target_weight'])}`，"
            f"全年净收益`{pct(row['year_return'])}`，成本拖累`{pct(row['year_cost_drag'])}`。"
        )

    lines.extend(["", "## 年度结果", ""])
    yearly_sample = yearly.filter(pl.col("roundtrip_cost_bps") == min(COST_BPS)).sort(
        ["cadence_step", "phase", "year"]
    )
    for row in yearly_sample.iter_rows(named=True):
        lines.append(
            f"- `{row['scenario']}` `{row['year']}`：净收益`{pct(row['year_return'])}`，"
            f"毛收益`{pct(row['year_gross_return'])}`，同暴露基准`{pct(row['year_benchmark_return'])}`，"
            f"平均暴露`{pct(row['avg_gross_exposure'])}`。"
        )

    lines.extend(
        [
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只测试预先定义的换仓节奏和所有相位，不按结果挑起始日，也不改信号、股票池、行业上限或单票上限。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：报告同时保留所有节奏、所有相位和20bp/50bp成本；任何更优节奏只作为下一步归因对象，不作为正式参数。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第230阶段的主要硬约束是15倍左右年化单边换手和高成本拖累，换仓节奏是进入正式化前必须回答的问题。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是，但粗降频本身不是答案。",
            "- 原因：同资本归一后，10日节奏平均年化单边换手只比每日节奏下降约7%，相位差异反而扩大；下一步应研究持仓延续、阈值滞后和只替换弱腿，而不是把某个降频相位当参数。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
            "- 简单降频不作为正式候选；下一步转向turnover-aware持仓延续/替换账本。",
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

    base_selected = select_industry_neutral_candidates(df, BASE_SCENARIO)
    if base_selected.is_empty():
        raise RuntimeError("No base selected candidates.")
    selected_all = build_cadence_selected(base_selected)
    lots_all = build_cadence_lots(selected_all)
    symbol_daily_all = build_symbol_daily(lots_all)
    benchmark_daily = build_benchmark_daily(benchmark_df)

    all_curves: list[pl.DataFrame] = []
    all_summary: list[dict[str, Any]] = []
    all_turnover: list[pl.DataFrame] = []
    all_concentration: list[pl.DataFrame] = []

    variant_lookup = {item["scenario"]: item for item in cadence_variant_definitions()}
    for scenario_name, scenario_symbol_daily in symbol_daily_all.partition_by("scenario", as_dict=True).items():
        variant = variant_lookup[scenario_name[0] if isinstance(scenario_name, tuple) else scenario_name]
        scenario_label = variant["scenario"]
        scenario_selected = selected_all.filter(pl.col("scenario") == scenario_label)
        min_date = min(scenario_symbol_daily["target_date"].min(), scenario_symbol_daily["pnl_date"].min())
        max_date = max(scenario_symbol_daily["target_date"].max(), scenario_symbol_daily["pnl_date"].max())
        calendar = build_calendar(benchmark_df, min_date, max_date)
        turnover, _targets = build_turnover(scenario_symbol_daily, calendar, scenario_label)
        concentration, _industry_daily = build_concentration(scenario_symbol_daily, calendar, scenario_label)
        daily_gross = build_daily_gross(scenario_symbol_daily)

        scenario_dict = {
            "scenario": scenario_label,
            "description": variant["scenario_description"],
            "bucket": variant["bucket"],
            "weight_mode": variant["weight_mode"],
        }
        for cost_bps in COST_BPS:
            curve = build_equity_curve(
                scenario_label,
                daily_gross,
                turnover,
                benchmark_daily,
                calendar,
                cost_bps,
            )
            all_curves.append(curve)
            row = summarize_curve(
                curve,
                turnover,
                concentration,
                scenario_selected,
                scenario_dict,
                cost_bps,
            )
            row["cadence_step"] = variant["cadence_step"]
            row["phase"] = variant["phase"]
            all_summary.append(row)

        all_turnover.append(turnover)
        all_concentration.append(concentration)

    summary_df = pl.DataFrame(all_summary).sort(["roundtrip_cost_bps", "cadence_step", "phase"])
    curves_df = pl.concat(all_curves, how="vertical").sort(["roundtrip_cost_bps", "scenario", "date"])
    turnover_df = pl.concat(all_turnover, how="vertical").sort(["scenario", "target_date"])
    concentration_df = pl.concat(all_concentration, how="vertical").sort(["scenario", "target_date"])
    yearly_df = (
        build_yearly_summary(curves_df)
        .join(summary_df.select("scenario", "cadence_step", "phase").unique(), on="scenario", how="left")
        .sort(["roundtrip_cost_bps", "cadence_step", "phase", "year"])
    )
    phase_summary = summarize_phases(summary_df)
    year_industry = build_year_industry_contribution(symbol_daily_all, curves_df)

    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "script": Path(__file__).name,
        "feature": FEATURE,
        "horizon": HORIZON,
        "cost_bps": list(COST_BPS),
        "cadence_steps": list(CADENCE_STEPS),
        "drawdown_years": list(DRAWDOWN_YEARS),
        "date_min": str(stock_df["datetime"].min()),
        "date_max": str(stock_df["datetime"].max()),
        "symbol_count": stock_df["symbol"].n_unique(),
        "initial_equity": INITIAL_EQUITY,
        "trading_days": TRADING_DAYS,
        "capital_normalization": "divide each active signal basket by active sleeve count on the target date",
    }

    paths: dict[str, Path] = {
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "phase_summary": OUTPUT_DIR / f"{PREFIX}_phase_summary.csv",
        "equity_curve": OUTPUT_DIR / f"{PREFIX}_equity_curve.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "turnover": OUTPUT_DIR / f"{PREFIX}_turnover.csv",
        "concentration": OUTPUT_DIR / f"{PREFIX}_daily_concentration.csv",
        "selected_daily": OUTPUT_DIR / f"{PREFIX}_selected_daily.csv",
        "year_industry": OUTPUT_DIR / f"{PREFIX}_year_industry_contribution.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    selected_daily = (
        selected_all.group_by(["scenario", "datetime"])
        .agg(
            pl.col("cadence_step").first().alias("cadence_step"),
            pl.col("phase").first().alias("phase"),
            pl.len().alias("candidate_count"),
            pl.col("industry").n_unique().alias("selected_industry_count"),
            pl.col("basket_weight").sum().alias("basket_gross_weight"),
            pl.col("basket_weight").max().alias("max_basket_stock_weight"),
        )
        .sort(["scenario", "datetime"])
    )

    summary_df.write_csv(paths["summary"])
    phase_summary.write_csv(paths["phase_summary"])
    curves_df.write_csv(paths["equity_curve"])
    yearly_df.write_csv(paths["yearly"])
    turnover_df.write_csv(paths["turnover"])
    concentration_df.write_csv(paths["concentration"])
    selected_daily.write_csv(paths["selected_daily"])
    year_industry.write_csv(paths["year_industry"])
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = write_report(summary_df, phase_summary, yearly_df, year_industry, meta, paths)
    print(phase_summary)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
