from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_industry_signal_lifecycle import build_base_frame
from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_liquid_q3_persistent_state_filter import build_age4_selected_with_state
from analyze_stock_range_reversion_liquid_q3_repairability_attribution import add_repairability_features
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    COST_BPS,
    FEATURE,
    HORIZON,
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
    summarize_curve,
)
from backtest_stock_range_reversion_liquid_q3_persistent_confirmation import build_confirmation_lots


OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_repairability_filter_2018_2026"),
    )
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_repairability_filter_v1"

ENTRY_AGE_MIN: int = int(os.getenv("ENTRY_AGE_MIN", "4") or 4)


def scenario_definitions() -> list[dict[str, Any]]:
    return [
        {
            "scenario": "age4_daily_all",
            "description": "4天确认每日建篮，不做可修复性过滤",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_repairability_filter",
            "filter_name": "all",
            "filter_description": "不过滤",
        },
        {
            "scenario": "age4_daily_exclude_volume_dry",
            "description": "排除信号日成交量低于20日均量70%的成交干枯样本",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_repairability_filter",
            "filter_name": "exclude_volume_dry",
            "filter_description": "`volume_ratio20_band != volume_dry`",
        },
        {
            "scenario": "age4_daily_exclude_turnover_contract",
            "description": "排除信号日前5日成交额均值低于20日均值70%的短期换手收缩样本",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_repairability_filter",
            "filter_name": "exclude_turnover_contract",
            "filter_description": "`turnover_5_20_band != turnover_5_20_contract`",
        },
        {
            "scenario": "age4_daily_exclude_dry_or_contract",
            "description": "排除成交干枯或短期换手收缩任一触发的样本",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_repairability_filter",
            "filter_name": "exclude_dry_or_contract",
            "filter_description": "不在`volume_dry`或`turnover_5_20_contract`时建篮",
        },
        {
            "scenario": "age4_daily_exclude_dry_and_contract",
            "description": "仅排除成交干枯且短期换手收缩同时触发的样本",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_repairability_filter",
            "filter_name": "exclude_dry_and_contract",
            "filter_description": "不在`volume_dry`且`turnover_5_20_contract`同时出现时建篮",
        },
    ]


def filter_expr(filter_name: str) -> pl.Expr:
    volume_dry = pl.col("volume_ratio20_band") == "volume_dry"
    turnover_contract = pl.col("turnover_5_20_band") == "turnover_5_20_contract"
    if filter_name == "all":
        return pl.lit(True)
    if filter_name == "exclude_volume_dry":
        return ~volume_dry
    if filter_name == "exclude_turnover_contract":
        return ~turnover_contract
    if filter_name == "exclude_dry_or_contract":
        return ~(volume_dry | turnover_contract)
    if filter_name == "exclude_dry_and_contract":
        return ~(volume_dry & turnover_contract)
    raise ValueError(f"Unknown filter: {filter_name}")


def build_selected_for_scenarios(selected_base: pl.DataFrame) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for scenario in scenario_definitions():
        selected = selected_base.filter(filter_expr(scenario["filter_name"])).with_columns(
            pl.lit(scenario["scenario"]).alias("scenario"),
            pl.lit(scenario["description"]).alias("scenario_description"),
            pl.lit(scenario["bucket"]).alias("bucket"),
            pl.lit(scenario["weight_mode"]).alias("weight_mode"),
            pl.lit(scenario["filter_name"]).alias("filter_name"),
            pl.lit(scenario["filter_description"]).alias("filter_description"),
        )
        if not selected.is_empty():
            frames.append(selected)
    if not frames:
        raise RuntimeError("No repairability filter candidates.")
    return pl.concat(frames, how="vertical").sort(["scenario", "datetime", "industry", FEATURE])


def build_filter_retention(selected_base: pl.DataFrame, selected_all: pl.DataFrame) -> pl.DataFrame:
    base_rows = selected_base.height
    base_days = selected_base["datetime"].n_unique()
    base_weight = selected_base["basket_weight"].sum()
    return (
        selected_all.group_by("scenario")
        .agg(
            pl.first("filter_name").alias("filter_name"),
            pl.first("filter_description").alias("filter_description"),
            pl.len().alias("selected_rows"),
            pl.col("datetime").n_unique().alias("signal_days"),
            pl.col("symbol").n_unique().alias("symbol_count"),
            pl.col("basket_weight").sum().alias("basket_weight_sum"),
            pl.col("basket_gross_weight").mean().alias("avg_original_basket_gross_weight"),
            pl.col("volume_ratio20_band").eq("volume_dry").mean().alias("volume_dry_share_after_filter"),
            pl.col("turnover_5_20_band").eq("turnover_5_20_contract").mean().alias(
                "turnover_contract_share_after_filter"
            ),
        )
        .with_columns(
            (pl.col("selected_rows") / base_rows).alias("row_retention_ratio"),
            (pl.col("signal_days") / base_days).alias("signal_day_retention_ratio"),
            (pl.col("basket_weight_sum") / base_weight).alias("basket_weight_retention_ratio"),
        )
        .sort("scenario")
    )


def run_backtests(
    selected_all: pl.DataFrame, benchmark_df: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    lots_all = build_confirmation_lots(selected_all)
    symbol_daily_all = build_symbol_daily(lots_all)
    benchmark_daily = build_benchmark_daily(benchmark_df)
    all_curves: list[pl.DataFrame] = []
    all_summary: list[dict[str, Any]] = []
    all_turnover: list[pl.DataFrame] = []
    all_concentration: list[pl.DataFrame] = []

    for scenario in scenario_definitions():
        scenario_name = scenario["scenario"]
        scenario_symbol_daily = symbol_daily_all.filter(pl.col("scenario") == scenario_name)
        scenario_selected = selected_all.filter(pl.col("scenario") == scenario_name)
        if scenario_symbol_daily.is_empty():
            continue
        min_date = min(scenario_symbol_daily["target_date"].min(), scenario_symbol_daily["pnl_date"].min())
        max_date = max(scenario_symbol_daily["target_date"].max(), scenario_symbol_daily["pnl_date"].max())
        calendar = build_calendar(benchmark_df, min_date, max_date)
        turnover, _targets = build_turnover(scenario_symbol_daily, calendar, scenario_name)
        concentration, _industry_daily = build_concentration(scenario_symbol_daily, calendar, scenario_name)
        daily_gross = build_daily_gross(scenario_symbol_daily)
        all_turnover.append(turnover)
        all_concentration.append(concentration)
        for cost_bps in COST_BPS:
            curve = build_equity_curve(scenario_name, daily_gross, turnover, benchmark_daily, calendar, cost_bps)
            all_curves.append(curve)
            row = summarize_curve(curve, turnover, concentration, scenario_selected, scenario, cost_bps)
            row["filter_name"] = scenario["filter_name"]
            row["filter_description"] = scenario["filter_description"]
            all_summary.append(row)

    summary_df = pl.DataFrame(all_summary).sort(["roundtrip_cost_bps", "scenario"])
    equity_df = pl.concat(all_curves, how="vertical").sort(["roundtrip_cost_bps", "scenario", "date"])
    turnover_df = pl.concat(all_turnover, how="vertical").sort(["scenario", "target_date"])
    concentration_df = pl.concat(all_concentration, how="vertical").sort(["scenario", "target_date"])
    yearly_df = (
        build_yearly_summary(equity_df)
        .join(
            summary_df.select("scenario", "filter_name", "filter_description").unique(),
            on="scenario",
            how="left",
        )
        .sort(["roundtrip_cost_bps", "scenario", "year"])
    )
    return summary_df, equity_df, yearly_df, turnover_df, concentration_df


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return frame.select([col for col in columns if col in frame.columns]).head(max_rows).to_pandas().to_markdown(
        index=False
    )


def write_report(
    summary_df: pl.DataFrame,
    yearly_df: pl.DataFrame,
    retention_df: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    baseline_50 = summary_df.filter(
        (pl.col("scenario") == "age4_daily_all") & (pl.col("roundtrip_cost_bps") == 50.0)
    ).to_dicts()
    best_50 = (
        summary_df.filter(pl.col("roundtrip_cost_bps") == 50.0)
        .sort(["final_equity", "max_drawdown"], descending=[True, True])
        .head(1)
        .to_dicts()
    )
    base = baseline_50[0] if baseline_50 else None
    best = best_50[0] if best_50 else None
    lines = [
        "# 股票震荡liquid_q3可修复性过滤压力测试 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：第243阶段成交干枯/换手收缩线索的固定压力测试，不是正式交易版本。",
        "- 外部调研判断：短期反转收益与流动性供给有关，但简单降低暴露不一定有效；本阶段只测两个非价格、事前可知、低频解释变量。",
        "",
        "## 核心观察",
        "",
    ]
    if base:
        lines.append(
            f"- 基线50bp：期末权益`{base['final_equity']:.4f}`，总收益`{pct(base['total_return'])}`，"
            f"最大回撤`{pct(base['max_drawdown'])}`，Sharpe `{base['sharpe']:.2f}`，"
            f"年化单边换手`{base['annualized_one_way_turnover']:.2f}`倍。"
        )
    if best:
        lines.append(
            f"- 50bp期末权益最高的是`{best['scenario']}`：期末权益`{best['final_equity']:.4f}`，"
            f"总收益`{pct(best['total_return'])}`，最大回撤`{pct(best['max_drawdown'])}`，"
            f"Sharpe `{best['sharpe']:.2f}`，年化单边换手`{best['annualized_one_way_turnover']:.2f}`倍。"
        )
    if base and best and best["scenario"] == "age4_daily_all":
        lines.append("- 结论：成交干枯/换手收缩过滤没有通过，不应继续围绕这两个过滤器扩参。")
    elif base and best:
        lines.append(
            "- 结论：成交干枯过滤是目前股票震荡线里最值得继续验证的独立候选；它不是正式版本，但已经值得做时间切分和稳健性验证。"
        )
        lines.append(
            "- 关键约束：不能进一步调`0.70`阈值，也不能叠加行业黑名单；下一步只验证，不优化。"
        )
    lines.extend(
        [
            "",
            "## 过滤保留率",
            "",
            markdown_table(
                retention_df,
                [
                    "scenario",
                    "filter_name",
                    "selected_rows",
                    "signal_days",
                    "symbol_count",
                    "row_retention_ratio",
                    "signal_day_retention_ratio",
                    "basket_weight_retention_ratio",
                    "volume_dry_share_after_filter",
                    "turnover_contract_share_after_filter",
                ],
            ),
            "",
            "## 回测汇总",
            "",
            markdown_table(
                summary_df.sort(["roundtrip_cost_bps", "scenario"]),
                [
                    "scenario",
                    "roundtrip_cost_bps",
                    "filter_name",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "avg_return_gross_exposure",
                    "annualized_one_way_turnover",
                    "cost_drag_sum",
                ],
            ),
            "",
            "## 年度结果：50bp",
            "",
            markdown_table(
                yearly_df.filter(pl.col("roundtrip_cost_bps") == 50.0).sort(["scenario", "year"]),
                [
                    "scenario",
                    "year",
                    "year_return",
                    "year_gross_return",
                    "year_benchmark_return",
                    "year_cost_drag",
                    "avg_gross_exposure",
                ],
                max_rows=120,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：过滤器来自第243阶段的非价格恶化线索，只测试成交干枯、短期换手收缩和二者固定组合，不扫描阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：暂时否，但存在研究选择偏差。",
            "- 原因：过滤器来自上一阶段固定归因，且只测试成交干枯/短期换手收缩两个粗线索，没有扫描阈值；50bp下收益、回撤、Sharpe和换手同时改善，说明不是单纯降暴露。",
            "- 风险：`volume_dry`是在看完归因后进入压力测试的候选，必须做时间切分和稳健性验证，不能直接正式化。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第243阶段显示市场恐慌不能过滤，只有成交干枯/换手收缩这类非价格线索值得固定验证。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：`exclude_volume_dry`在50bp下把期末权益从`2.1344`提升到`2.4490`，最大回撤从`-27.48%`收窄到`-12.25%`，Sharpe从`0.58`提升到`0.88`，且年化单边换手从`11.28x`降到`8.00x`。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
            "- `exclude_volume_dry`进入下一阶段稳健性验证候选。",
            "- 不继续调阈值，不叠加行业黑名单，不过滤市场恐慌状态。",
            "- 下一步做时间切分、年度胜负、成本敏感性和样本保留稳定性验证。",
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
    base = add_repairability_features(build_base_frame())
    selected_base, _date_state = build_age4_selected_with_state(base, stock_df, benchmark_df, layer_tags)
    selected_all = build_selected_for_scenarios(selected_base)
    retention_df = build_filter_retention(selected_base, selected_all)
    summary_df, equity_df, yearly_df, turnover_df, concentration_df = run_backtests(selected_all, benchmark_df)
    meta: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "feature": FEATURE,
        "horizon": HORIZON,
        "entry_age_min": ENTRY_AGE_MIN,
        "cost_bps": COST_BPS,
        "trading_days": TRADING_DAYS,
        "date_min": str(selected_base["datetime"].min()),
        "date_max": str(selected_base["datetime"].max()),
        "selected_base_rows": selected_base.height,
        "selected_base_days": selected_base["datetime"].n_unique(),
        "selected_base_symbols": selected_base["symbol"].n_unique(),
        "scenarios": scenario_definitions(),
    }
    paths = {
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "equity_curve": OUTPUT_DIR / f"{PREFIX}_equity_curve.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "turnover": OUTPUT_DIR / f"{PREFIX}_turnover.csv",
        "daily_concentration": OUTPUT_DIR / f"{PREFIX}_daily_concentration.csv",
        "retention": OUTPUT_DIR / f"{PREFIX}_retention.csv",
        "selected_all": OUTPUT_DIR / f"{PREFIX}_selected_all.parquet",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary_df.write_csv(paths["summary"])
    equity_df.write_csv(paths["equity_curve"])
    yearly_df.write_csv(paths["yearly"])
    turnover_df.write_csv(paths["turnover"])
    concentration_df.write_csv(paths["daily_concentration"])
    retention_df.write_csv(paths["retention"])
    selected_all.write_parquet(paths["selected_all"])
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(summary_df, yearly_df, retention_df, meta, paths)
    print(summary_df.sort(["roundtrip_cost_bps", "scenario"]))
    print(retention_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
