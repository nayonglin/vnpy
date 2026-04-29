from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import (
    ACCOUNT_SIZE_CNY,
    HIGH_RETURN_TARGET,
    MAX_DRAWDOWN_LIMIT,
    summarize_daily_extra,
    to_float,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import HORIZON, NATIVE_RESULTS_DIR, add_path_columns, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_alt_strong_pullback_definitions_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_alt_strong_pullback_definitions_v1"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_alt_strong_pullback_30w_replay_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_alt_strong_pullback_30w_replay_v1"

CANDIDATE_DEFINITIONS: tuple[str, ...] = (
    "strong_industry_near_high_resid5",
    "industry252_resid10_pullback",
    "mom120_lowvol_ret10_pullback",
)
HORIZONS: tuple[int, ...] = (5, 10)
TOP_KS: tuple[int, ...] = (3, 5)
BASKET_GROSS_WEIGHTS: tuple[float, ...] = (0.70, 1.00)
MAX_PER_INDUSTRY_VALUES: tuple[int, ...] = (1, 2)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def read_selected() -> pl.DataFrame:
    return pl.read_csv(
        SOURCE_DIR / f"{SOURCE_PREFIX}_selected.csv",
        try_parse_dates=True,
        schema_overrides={"symbol": pl.Utf8},
    ).filter(pl.col("definition").is_in(CANDIDATE_DEFINITIONS))


def build_path_dates(stock_df: pl.DataFrame) -> pl.DataFrame:
    keep = ["datetime", "symbol", *[f"start_date_{day}" for day in range(1, HORIZON + 1)]]
    return add_path_columns(stock_df.select(["datetime", "symbol", "close"]).sort(["symbol", "datetime"])).select(keep)


def build_shaped_selected(
    selected: pl.DataFrame,
    definition: str,
    horizon: int,
    top_k: int,
    basket_gross_weight: float,
    max_per_industry: int,
) -> pl.DataFrame:
    scenario = f"{definition}_h{horizon}_top{top_k}_gross{int(basket_gross_weight * 100)}_ind{max_per_industry}"
    work = (
        selected.filter(pl.col("definition") == definition)
        .with_columns(
            pl.col("pullback_score").rank("ordinal", descending=True).over(["datetime", "industry"]).alias("_industry_rank")
        )
        .filter(pl.col("_industry_rank") <= max_per_industry)
        .with_columns(pl.col("pullback_score").rank("ordinal", descending=True).over("datetime").alias("_daily_shape_rank"))
        .filter(pl.col("_daily_shape_rank") <= top_k)
        .with_columns(
            pl.len().over("datetime").alias("candidate_count"),
            pl.col("industry").n_unique().over("datetime").alias("selected_industry_count"),
            pl.len().over(["datetime", "industry"]).alias("selected_industry_stock_count"),
        )
        .filter(pl.col("candidate_count") > 0)
        .with_columns((pl.lit(basket_gross_weight) / pl.col("candidate_count")).alias("basket_weight"))
        .with_columns(
            pl.lit(scenario).alias("scenario"),
            pl.lit(horizon).alias("shape_horizon"),
            pl.lit(top_k).alias("shape_top_k"),
            pl.lit(basket_gross_weight).alias("shape_basket_gross_weight"),
            pl.lit(max_per_industry).alias("shape_max_per_industry"),
            pl.col("basket_weight").sum().over("datetime").alias("basket_gross_weight"),
        )
        .drop(["_industry_rank", "_daily_shape_rank"])
    )
    return work


def build_target_weights(shaped: pl.DataFrame, horizon: int) -> pl.DataFrame:
    parts: list[pl.DataFrame] = []
    extra_cols = [
        col
        for col in [
            "definition",
            "definition_description",
            "industry",
            "market",
            "adv20_turnover",
            "turnover_rate_f",
            "circ_mv",
            "total_mv",
            "candidate_count",
            "selected_industry_count",
            "selected_industry_stock_count",
            "basket_gross_weight",
            "shape_horizon",
            "shape_top_k",
            "shape_basket_gross_weight",
            "shape_max_per_industry",
        ]
        if col in shaped.columns
    ]
    for day in range(1, horizon + 1):
        parts.append(
            shaped.select(
                "scenario",
                pl.col("datetime").alias("signal_date"),
                "symbol",
                "pullback_score",
                "basket_weight",
                *extra_cols,
                pl.col(f"start_date_{day}").alias("target_date"),
            )
            .with_columns(
                pl.lit(day).alias("holding_day"),
                (pl.col("basket_weight") / horizon).alias("lot_weight"),
            )
            .filter(pl.col("target_date").is_not_null())
        )
    lots = pl.concat(parts, how="vertical")
    return (
        lots.group_by(["scenario", "target_date", "symbol"])
        .agg(
            pl.col("lot_weight").sum().alias("target_weight"),
            pl.len().alias("active_lots"),
            pl.col("signal_date").n_unique().alias("source_signal_days"),
            pl.col("holding_day").min().alias("min_holding_day"),
            pl.col("holding_day").max().alias("max_holding_day"),
            *[pl.col(col).first().alias(col) for col in extra_cols],
        )
        .sort(["scenario", "target_date", "symbol"])
    )


def build_yearly(daily: pl.DataFrame) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()
    return (
        daily.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["scenario", "year"])
        .agg(
            ((1 + pl.col("strategy_daily_ret_min_fee")).product() - 1).alias("year_return_min_fee"),
            pl.col("drawdown_min_fee").min().alias("year_curve_drawdown_min_fee"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            (pl.col("zero_lot_target_count").sum() / pl.col("target_symbol_count").sum()).alias("zero_lot_target_ratio"),
        )
        .sort(["scenario", "year"])
    )


def build_quality(summary: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in summary.iter_rows(named=True):
        scenario = row["scenario"]
        total_return = to_float(row.get("total_return_min_fee"))
        max_dd = to_float(row.get("max_drawdown_min_fee"))
        latest_capture = to_float(row.get("latest_exposure_capture_ratio"))
        zero_ratio = to_float(row.get("zero_lot_target_ratio"))
        active_win = to_float(row.get("net_active_day_win_rate"))
        rows.extend(
            [
                {
                    "scenario": scenario,
                    "checkpoint": "max_drawdown_within_20pct",
                    "status": "pass" if max_dd >= MAX_DRAWDOWN_LIMIT else "fail",
                    "value": pct(max_dd),
                    "expected": ">=-20%",
                    "note": "用户给定的30万策略回撤边界。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "high_return_target",
                    "status": "pass" if total_return >= HIGH_RETURN_TARGET else "warn",
                    "value": pct(total_return),
                    "expected": ">=100%",
                    "note": "高收益目标，必须结合回撤看。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "latest_exposure_capture_ratio",
                    "status": "fail" if latest_capture < 0.50 else "warn" if latest_capture < 0.70 else "pass",
                    "value": pct(latest_capture),
                    "expected": ">=70% preferred, >=50% hard",
                    "note": "最新目标日整手后暴露捕获。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "zero_lot_target_ratio",
                    "status": "fail" if zero_ratio > 0.35 else "warn" if zero_ratio > 0.20 else "pass",
                    "value": pct(zero_ratio),
                    "expected": "<=20% preferred, <=35% hard",
                    "note": "30万账户整手颗粒度。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "active_day_win_rate",
                    "status": "warn" if active_win < 0.50 else "pass",
                    "value": pct(active_win),
                    "expected": ">=50%",
                    "note": "活跃日胜率太低说明收益可能来自少数跳变。",
                },
            ]
        )
    return pl.DataFrame(rows).sort(["scenario", "checkpoint"])


def replay_scenario(
    scenario: str,
    target_weights: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
) -> tuple[dict[str, Any], pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    scenario_targets = target_weights.filter(pl.col("scenario") == scenario).drop("scenario")
    target_maps = lot.build_target_maps(scenario_targets)
    dates = lot.build_tracking_dates(scenario_targets, benchmark_df)
    orders, daily, _curve = lot.replay_lot_account(target_maps, dates, exec_info)
    if not orders.is_empty():
        orders = orders.with_columns(pl.lit(scenario).alias("scenario"))
    if not daily.is_empty():
        daily = daily.with_columns(pl.lit(scenario).alias("scenario"))
    summary = lot.summarize_orders(orders, daily)
    summary = summarize_daily_extra(summary, daily)
    meta = scenario_targets.select(
        [
            "definition",
            "shape_horizon",
            "shape_top_k",
            "shape_basket_gross_weight",
            "shape_max_per_industry",
        ]
    ).row(0, named=True)
    summary.update(meta)
    summary["scenario"] = scenario
    return summary, orders, daily, build_yearly(daily)


def write_report(summary: pl.DataFrame, quality: pl.DataFrame, yearly: pl.DataFrame, paths: dict[str, Path]) -> Path:
    report_path = paths["report"]
    pass_dd = summary.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT).sort(
        ["total_return_min_fee", "sharpe_min_fee"], descending=[True, True]
    )
    high_return = summary.filter(pl.col("total_return_min_fee") >= HIGH_RETURN_TARGET).sort(
        ["max_drawdown_min_fee", "sharpe_min_fee"], descending=[True, True]
    )
    best = summary.row(0, named=True)
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    lines = [
        "# 股票震荡liquid_q3 替代强势回调定义30万复放 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：只对信号归因Top定义做30万整手复放，不修改paper入口。",
        f"- 候选定义：`{CANDIDATE_DEFINITIONS}`。",
        f"- 组合形状：持有期`{HORIZONS}`，top_k`{TOP_KS}`，gross`{BASKET_GROSS_WEIGHTS}`，单行业`{MAX_PER_INDUSTRY_VALUES}`。",
        "- A/B判断：30万候选复放，不接入第78，不触发A/B。",
        "",
        "## 核心摘要",
        "",
    ]
    if pass_dd.height:
        best_pass = pass_dd.row(0, named=True)
        lines.append(
            f"- 回撤20%以内最高收益候选：`{best_pass['scenario']}`，期末权益`{best_pass['final_equity_min_fee']:.4f}`，总收益`{pct(best_pass['total_return_min_fee'])}`，最大回撤`{pct(best_pass['max_drawdown_min_fee'])}`，Sharpe `{best_pass['sharpe_min_fee']:.3f}`。"
        )
    else:
        lines.append("- 回撤20%以内候选：无。")
    if high_return.height:
        best_high = high_return.row(0, named=True)
        lines.append(
            f"- 收益100%以上候选中回撤最小：`{best_high['scenario']}`，总收益`{pct(best_high['total_return_min_fee'])}`，最大回撤`{pct(best_high['max_drawdown_min_fee'])}`。"
        )
    else:
        lines.append("- 收益100%以上候选：无。")
    lines.append(
        f"- 全场收益最高：`{best['scenario']}`，期末权益`{best['final_equity_min_fee']:.4f}`，总收益`{pct(best['total_return_min_fee'])}`，最大回撤`{pct(best['max_drawdown_min_fee'])}`，Sharpe `{best['sharpe_min_fee']:.3f}`。"
    )
    lines.append(f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。")
    display_cols = [
        "scenario",
        "definition",
        "shape_horizon",
        "shape_top_k",
        "shape_basket_gross_weight",
        "shape_max_per_industry",
        "final_equity_min_fee",
        "total_return_min_fee",
        "max_drawdown_min_fee",
        "sharpe_min_fee",
        "return_over_max_dd",
        "zero_lot_target_ratio",
        "latest_exposure_capture_ratio",
        "avg_actual_gross_weight",
        "avg_actual_symbol_count",
        "net_active_day_win_rate",
        "min_fee_equity_gap",
    ]
    top_yearly_scenarios = summary.sort("total_return_min_fee", descending=True)["scenario"].head(5).to_list()
    lines.extend(
        [
            "",
            "## 场景汇总",
            "",
            markdown_table(summary.select([col for col in display_cols if col in summary.columns]), [col for col in display_cols if col in summary.columns], max_rows=80),
            "",
            "## 回撤20%以内候选",
            "",
            markdown_table(pass_dd.select([col for col in display_cols if col in pass_dd.columns]), [col for col in display_cols if col in pass_dd.columns], max_rows=80)
            if pass_dd.height
            else "无数据",
            "",
            "## 年度拆分Top候选",
            "",
            markdown_table(yearly.filter(pl.col("scenario").is_in(top_yearly_scenarios)).sort(["scenario", "year"]), yearly.columns, max_rows=120),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, quality.columns, max_rows=160),
            "",
            "## 结论",
            "",
            "- 本阶段用于判断强势回调新定义是否能通过30万真实整手约束。",
            "- 若信号归因好但复放后收益/回撤不达标，说明优势仍不足以覆盖账户颗粒度和持仓路径。",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "target_weights": OUTPUT_DIR / f"{PREFIX}_target_weights.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
    }
    stock_df, benchmark_df = load_panels()
    selected = read_selected().join(build_path_dates(stock_df), on=["datetime", "symbol"], how="left")
    exec_info = build_exec_info(stock_df)

    all_targets: list[pl.DataFrame] = []
    for definition in CANDIDATE_DEFINITIONS:
        for horizon in HORIZONS:
            for top_k in TOP_KS:
                for gross in BASKET_GROSS_WEIGHTS:
                    for max_per_industry in MAX_PER_INDUSTRY_VALUES:
                        shaped = build_shaped_selected(selected, definition, horizon, top_k, gross, max_per_industry)
                        if not shaped.is_empty():
                            all_targets.append(build_target_weights(shaped, horizon))
    target_weights = pl.concat(all_targets, how="diagonal_relaxed").sort(["scenario", "target_date", "symbol"])
    scenarios = target_weights["scenario"].unique().sort().to_list()

    summaries: list[dict[str, Any]] = []
    orders_list: list[pl.DataFrame] = []
    daily_list: list[pl.DataFrame] = []
    yearly_list: list[pl.DataFrame] = []
    for scenario in scenarios:
        summary, orders, daily, yearly = replay_scenario(scenario, target_weights, benchmark_df, exec_info)
        summaries.append(summary)
        if not orders.is_empty():
            orders_list.append(orders)
        if not daily.is_empty():
            daily_list.append(daily)
        if not yearly.is_empty():
            yearly_list.append(yearly)

    summary_df = pl.DataFrame(summaries).sort(
        ["total_return_min_fee", "max_drawdown_min_fee", "sharpe_min_fee"],
        descending=[True, True, True],
    )
    quality_df = build_quality(summary_df)
    orders_df = pl.concat(orders_list, how="diagonal_relaxed") if orders_list else pl.DataFrame()
    daily_df = pl.concat(daily_list, how="diagonal_relaxed") if daily_list else pl.DataFrame()
    yearly_df = pl.concat(yearly_list, how="diagonal_relaxed") if yearly_list else pl.DataFrame()

    summary_df.write_csv(paths["summary"])
    quality_df.write_csv(paths["quality"])
    yearly_df.write_csv(paths["yearly"])
    target_weights.write_csv(paths["target_weights"])
    orders_df.write_csv(paths["orders"])
    daily_df.write_csv(paths["daily"])
    report_path = write_report(summary_df, quality_df, yearly_df, paths)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "candidate_definitions": CANDIDATE_DEFINITIONS,
            "horizons": HORIZONS,
            "top_ks": TOP_KS,
            "basket_gross_weights": BASKET_GROSS_WEIGHTS,
            "max_per_industry_values": MAX_PER_INDUSTRY_VALUES,
            "outputs": {key: str(path) for key, path in paths.items()},
            "report": str(report_path),
        },
    )
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
