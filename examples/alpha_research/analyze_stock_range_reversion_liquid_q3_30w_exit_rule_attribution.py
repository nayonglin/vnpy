from __future__ import annotations

import json
from dataclasses import dataclass
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
    build_concentrated_selected,
    read_source_candidates,
    summarize_daily_extra,
    to_float,
    write_json,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    FEATURE,
    HORIZON,
    NATIVE_RESULTS_DIR,
    TRADING_DAYS,
    pct,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_exit_rule_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_30w_exit_rule_attribution_v1"

SHAPES: tuple[tuple[int, float, int], ...] = (
    (5, 0.70, 2),
    (8, 0.70, 2),
    (5, 1.00, 1),
    (8, 1.00, 2),
)


@dataclass(frozen=True)
class ExitRule:
    name: str
    description: str
    max_holding_days: int
    tranche_denominator: int
    stop_loss: float | None = None
    take_profit: float | None = None


EXIT_RULES: tuple[ExitRule, ...] = (
    ExitRule("hold10_base", "原始10日持有，不加显式退出。", 10, 10),
    ExitRule("hold5_same_tranche", "只持有前5日，单笔切片仍按10日分摊，释放资金留现金。", 5, 10),
    ExitRule("hold5_renorm", "只持有前5日，单笔切片按5日重分配，保持更接近原篮子暴露。", 5, 5),
    ExitRule("stop3_hold10", "10日路径内累计亏损达到3%后次日退出。", 10, 10, stop_loss=-0.03),
    ExitRule("stop5_hold10", "10日路径内累计亏损达到5%后次日退出。", 10, 10, stop_loss=-0.05),
    ExitRule("take5_hold10", "10日路径内累计盈利达到5%后次日止盈。", 10, 10, take_profit=0.05),
    ExitRule("take8_hold10", "10日路径内累计盈利达到8%后次日止盈。", 10, 10, take_profit=0.08),
    ExitRule("stop3_take6_hold10", "10日路径内累计亏损3%止损，累计盈利6%止盈。", 10, 10, stop_loss=-0.03, take_profit=0.06),
    ExitRule("stop5_take5_hold10", "10日路径内累计亏损5%止损，累计盈利5%止盈。", 10, 10, stop_loss=-0.05, take_profit=0.05),
    ExitRule("stop5_take8_hold10", "10日路径内累计亏损5%止损，累计盈利8%止盈。", 10, 10, stop_loss=-0.05, take_profit=0.08),
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "When do stop-loss rules stop losses?",
        "https://www.sciencedirect.com/science/article/pii/S138641811300030X",
    ),
    (
        "A simple computational model for stop-loss and take-profit strategies",
        "https://www.sciencedirect.com/science/article/pii/S0305054804001194",
    ),
    (
        "Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit",
        "https://arxiv.org/abs/1411.5062",
    ),
    (
        "Backtesting.py order and stop-loss/take-profit references",
        "https://kernc.github.io/backtesting.py/",
    ),
)


def is_valid_number(value: Any) -> bool:
    parsed = to_float(value, default=float("nan"))
    return parsed == parsed


def build_exit_lots(selected: pl.DataFrame, rule: ExitRule) -> tuple[pl.DataFrame, pl.DataFrame]:
    lot_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    meta_cols = [
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
            "shape_top_k",
            "shape_basket_gross_weight",
            "shape_max_per_industry",
        ]
        if col in selected.columns
    ]

    for row in selected.iter_rows(named=True):
        shape_scenario = str(row["scenario"])
        scenario = f"{shape_scenario}_{rule.name}"
        cumulative = 0.0
        exit_day: int | None = None
        exit_reason = ""
        valid_path_days = 0
        common = {col: row.get(col) for col in meta_cols}
        for day in range(1, min(rule.max_holding_days, HORIZON) + 1):
            start_date = row.get(f"start_date_{day}")
            pnl_date = row.get(f"pnl_date_{day}")
            daily_ret = row.get(f"stock_daily_ret_{day}")
            if start_date is None or pnl_date is None or not is_valid_number(daily_ret):
                continue

            daily_ret_float = to_float(daily_ret)
            cumulative = (1.0 + cumulative) * (1.0 + daily_ret_float) - 1.0
            valid_path_days += 1
            triggered = False
            trigger_reason = ""
            if rule.stop_loss is not None and cumulative <= rule.stop_loss:
                triggered = True
                trigger_reason = "stop_loss"
            elif rule.take_profit is not None and cumulative >= rule.take_profit:
                triggered = True
                trigger_reason = "take_profit"

            lot_rows.append(
                {
                    "scenario": scenario,
                    "shape_scenario": shape_scenario,
                    "exit_rule": rule.name,
                    "exit_rule_description": rule.description,
                    "max_holding_days": rule.max_holding_days,
                    "tranche_denominator": rule.tranche_denominator,
                    "stop_loss": rule.stop_loss,
                    "take_profit": rule.take_profit,
                    "signal_date": row["datetime"],
                    "symbol": row["symbol"],
                    FEATURE: row[FEATURE],
                    "basket_weight": row["basket_weight"],
                    **common,
                    "target_date": start_date,
                    "pnl_date": pnl_date,
                    "stock_daily_ret": daily_ret_float,
                    "holding_day": day,
                    "lot_weight": to_float(row["basket_weight"]) / float(rule.tranche_denominator),
                    "path_cum_ret_after_day": cumulative,
                    "exit_triggered_after_day": triggered,
                    "exit_reason_after_day": trigger_reason,
                }
            )

            if triggered:
                exit_day = day
                exit_reason = trigger_reason
                break

        event_rows.append(
            {
                "scenario": scenario,
                "shape_scenario": shape_scenario,
                "exit_rule": rule.name,
                "signal_date": row["datetime"],
                "symbol": row["symbol"],
                "industry": row.get("industry", ""),
                FEATURE: row[FEATURE],
                "valid_path_days": valid_path_days,
                "exit_day": exit_day,
                "exit_reason": exit_reason or ("time_exit" if rule.max_holding_days < HORIZON else "horizon_exit"),
                "path_cum_ret_at_exit_or_horizon": cumulative,
                "stopped_or_took_profit": exit_day is not None,
            }
        )

    lots = pl.DataFrame(lot_rows).sort(["scenario", "target_date", "signal_date", "symbol"]) if lot_rows else pl.DataFrame()
    events = pl.DataFrame(event_rows).sort(["scenario", "signal_date", "symbol"]) if event_rows else pl.DataFrame()
    return lots, events


def build_target_weights_from_lots(lots: pl.DataFrame) -> pl.DataFrame:
    if lots.is_empty():
        return pl.DataFrame()
    agg_exprs: list[pl.Expr] = [
        pl.col("lot_weight").sum().alias("target_weight"),
        pl.len().alias("active_lots"),
        pl.col("stock_daily_ret").first().alias("stock_daily_ret"),
        pl.col("signal_date").n_unique().alias("source_signal_days"),
        pl.col("holding_day").min().alias("min_holding_day"),
        pl.col("holding_day").max().alias("max_holding_day"),
    ]
    for col in [
        "shape_scenario",
        "exit_rule",
        "exit_rule_description",
        "industry",
        "market",
        "adv20_turnover",
        "turnover_rate_f",
        "circ_mv",
        "total_mv",
        "shape_top_k",
        "shape_basket_gross_weight",
        "shape_max_per_industry",
        "max_holding_days",
        "tranche_denominator",
        "stop_loss",
        "take_profit",
    ]:
        if col in lots.columns:
            agg_exprs.append(pl.col(col).first().alias(col))
    return (
        lots.group_by(["scenario", "target_date", "pnl_date", "symbol"])
        .agg(agg_exprs)
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


def summarize_exit_events(events: pl.DataFrame) -> pl.DataFrame:
    if events.is_empty():
        return pl.DataFrame()
    return (
        events.group_by(["scenario", "shape_scenario", "exit_rule", "exit_reason"])
        .agg(
            pl.len().alias("signals"),
            pl.col("stopped_or_took_profit").mean().alias("trigger_ratio"),
            pl.col("exit_day").mean().alias("avg_exit_day"),
            pl.col("path_cum_ret_at_exit_or_horizon").mean().alias("avg_path_cum_ret_at_exit_or_horizon"),
            pl.col("path_cum_ret_at_exit_or_horizon").median().alias("median_path_cum_ret_at_exit_or_horizon"),
        )
        .sort(["scenario", "signals"], descending=[False, True])
    )


def build_quality(summary: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in summary.iter_rows(named=True):
        scenario = row["scenario"]
        total_return = to_float(row.get("total_return_min_fee"))
        max_dd = to_float(row.get("max_drawdown_min_fee"))
        zero_ratio = to_float(row.get("zero_lot_target_ratio"))
        latest_capture = to_float(row.get("latest_exposure_capture_ratio"))
        active_win = to_float(row.get("net_active_day_win_rate"))
        rows.extend(
            [
                {
                    "scenario": scenario,
                    "checkpoint": "max_drawdown_within_20pct",
                    "status": "pass" if max_dd >= MAX_DRAWDOWN_LIMIT else "fail",
                    "value": pct(max_dd),
                    "expected": ">=-20%",
                    "note": "用户明确可接受的最大回撤边界。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "high_return_target",
                    "status": "pass" if total_return >= HIGH_RETURN_TARGET else "warn",
                    "value": pct(total_return),
                    "expected": ">=100%",
                    "note": "高收益目标，必须和回撤一起看。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "zero_lot_target_ratio",
                    "status": "fail" if zero_ratio > 0.35 else "warn" if zero_ratio > 0.20 else "pass",
                    "value": pct(zero_ratio),
                    "expected": "<=20% preferred, <=35% hard",
                    "note": "30万账户整手取整仍可能严重扭曲组合。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "latest_exposure_capture_ratio",
                    "status": "fail" if latest_capture < 0.50 else "warn" if latest_capture < 0.70 else "pass",
                    "value": pct(latest_capture),
                    "expected": ">=70% preferred, >=50% hard",
                    "note": "最新目标日取整后目标市值捕获率。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "active_day_win_rate",
                    "status": "warn" if active_win < 0.50 else "pass",
                    "value": pct(active_win),
                    "expected": ">=50%",
                    "note": "退出规则若只降收益不改善胜率，需要谨慎。",
                },
            ]
        )
    return pl.DataFrame(rows).sort(["scenario", "checkpoint"])


def replay_variant(
    selected: pl.DataFrame,
    rule: ExitRule,
    benchmark_df: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
) -> tuple[dict[str, Any], pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    lots, events = build_exit_lots(selected, rule)
    target_weights = build_target_weights_from_lots(lots)
    if target_weights.is_empty():
        return {}, pl.DataFrame(), pl.DataFrame(), pl.DataFrame(), pl.DataFrame(), events
    scenario = target_weights["scenario"][0]
    scenario_targets = target_weights.drop("scenario")
    target_maps = lot.build_target_maps(scenario_targets)
    dates = lot.build_tracking_dates(scenario_targets, benchmark_df)
    orders, daily, _curve = lot.replay_lot_account(target_maps, dates, exec_info)
    if not orders.is_empty():
        orders = orders.with_columns(pl.lit(scenario).alias("scenario"))
    if not daily.is_empty():
        daily = daily.with_columns(pl.lit(scenario).alias("scenario"))
    summary = lot.summarize_orders(orders, daily)
    summary = summarize_daily_extra(summary, daily)
    meta = target_weights.select(
        [
            "shape_scenario",
            "exit_rule",
            "exit_rule_description",
            "shape_top_k",
            "shape_basket_gross_weight",
            "shape_max_per_industry",
            "max_holding_days",
            "tranche_denominator",
            "stop_loss",
            "take_profit",
        ]
    ).row(0, named=True)
    summary.update(meta)
    summary["scenario"] = scenario
    if not events.is_empty():
        scenario_events = events.filter(pl.col("scenario") == scenario)
        triggered = scenario_events.filter(pl.col("stopped_or_took_profit"))
        summary["exit_trigger_ratio"] = triggered.height / scenario_events.height if scenario_events.height else 0.0
        summary["avg_signal_path_ret_at_exit_or_horizon"] = to_float(
            scenario_events["path_cum_ret_at_exit_or_horizon"].mean()
        )
        summary["median_signal_path_ret_at_exit_or_horizon"] = to_float(
            scenario_events["path_cum_ret_at_exit_or_horizon"].median()
        )
    yearly = build_yearly(daily)
    return summary, orders, daily, yearly, target_weights, events


def write_report(
    summary: pl.DataFrame,
    quality: pl.DataFrame,
    yearly: pl.DataFrame,
    exit_summary: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    pass_dd = summary.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT).sort(
        ["total_return_min_fee", "sharpe_min_fee"], descending=[True, True]
    )
    high_return = summary.filter(pl.col("total_return_min_fee") >= HIGH_RETURN_TARGET).sort(
        ["max_drawdown_min_fee", "sharpe_min_fee"], descending=[True, True]
    )
    best = summary.sort(
        ["total_return_min_fee", "max_drawdown_min_fee", "sharpe_min_fee"],
        descending=[True, True, True],
    ).row(0, named=True)
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    lines = [
        "# 股票震荡liquid_q3 30万显式退出归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：固定弱势修复入场，只测试朴素止损、止盈和持有期退出对尾部风险的影响。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；最大回撤目标：`20%`以内；高收益目标：`100%+`。",
        f"- 形状：`{SHAPES}`；退出规则数量：`{len(EXIT_RULES)}`。",
        "- A/B判断：退出归因研究，不接入第78，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 止损和止盈是风险分布改造工具，不是天然收益增强工具；如果价格更接近随机游走或强均值回归，机械止损可能降低期望。",
        "- 只有当亏损路径存在趋势延续、尾部聚集或交易制度约束时，退出规则才可能改善回撤。",
        "- 因此本阶段不做大规模阈值搜索，只测试少数朴素退出规则，看是否存在结构性尾部改善。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")

    lines.extend(["", "## 核心摘要", ""])
    if pass_dd.height:
        best_pass = pass_dd.row(0, named=True)
        lines.append(
            f"- 回撤20%以内最高收益候选：`{best_pass['scenario']}`，期末权益`{best_pass['final_equity_min_fee']:.4f}`，总收益`{pct(best_pass['total_return_min_fee'])}`，最大回撤`{pct(best_pass['max_drawdown_min_fee'])}`，Sharpe `{best_pass['sharpe_min_fee']:.3f}`。"
        )
    else:
        lines.append("- 回撤20%以内候选：本轮无。")
    if high_return.height:
        best_high = high_return.row(0, named=True)
        lines.append(
            f"- 收益100%以上候选中回撤最小：`{best_high['scenario']}`，总收益`{pct(best_high['total_return_min_fee'])}`，最大回撤`{pct(best_high['max_drawdown_min_fee'])}`。"
        )
    else:
        lines.append("- 收益100%以上候选：本轮无。")
    lines.append(
        f"- 全场收益最高：`{best['scenario']}`，期末权益`{best['final_equity_min_fee']:.4f}`，总收益`{pct(best['total_return_min_fee'])}`，最大回撤`{pct(best['max_drawdown_min_fee'])}`，Sharpe `{best['sharpe_min_fee']:.3f}`。"
    )
    lines.append(f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。")
    lines.append("- 判断：若朴素退出不能把高收益组合压到20%回撤内，下一步不应继续扫止损止盈阈值。")

    display_cols = [
        "scenario",
        "shape_scenario",
        "exit_rule",
        "final_equity_min_fee",
        "total_return_min_fee",
        "max_drawdown_min_fee",
        "sharpe_min_fee",
        "return_over_max_dd",
        "exit_trigger_ratio",
        "zero_lot_target_ratio",
        "latest_exposure_capture_ratio",
        "avg_actual_gross_weight",
        "avg_actual_symbol_count",
        "net_active_day_win_rate",
        "min_fee_equity_gap",
    ]
    lines.extend(
        [
            "",
            "## 场景汇总Top80",
            "",
            markdown_table(
                summary.sort(
                    ["total_return_min_fee", "max_drawdown_min_fee", "sharpe_min_fee"],
                    descending=[True, True, True],
                )
                .select([col for col in display_cols if col in summary.columns])
                .head(80)
            ),
            "",
            "## 回撤20%以内候选",
            "",
            markdown_table(pass_dd.select([col for col in display_cols if col in pass_dd.columns]).head(40))
            if pass_dd.height
            else "无数据",
            "",
            "## 退出事件摘要Top80",
            "",
            markdown_table(exit_summary.head(80)) if not exit_summary.is_empty() else "无数据",
            "",
            "## 年度拆分Top候选",
            "",
            markdown_table(
                yearly.filter(pl.col("scenario").is_in(summary.sort("total_return_min_fee", descending=True)["scenario"].head(5)))
                .sort(["scenario", "year"])
                .head(80)
            )
            if not yearly.is_empty()
            else "无数据",
            "",
            "## 质量检查",
            "",
            markdown_table(quality.head(120)) if not quality.is_empty() else "无数据",
            "",
            "## 结论",
            "",
            "- 本阶段只回答退出规则是否能结构性改善尾部，不把最优阈值当成策略结论。",
            "- 如果回撤改善主要来自降低暴露且收益同步坍缩，它不是有效突破。",
            "- 若存在回撤下降且收益保留的候选，下一步必须做walk-forward和启动年份验证。",
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
        "exit_summary": OUTPUT_DIR / f"{PREFIX}_exit_summary.csv",
        "target_weights": OUTPUT_DIR / f"{PREFIX}_target_weights.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
    }

    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)
    base = read_source_candidates()
    summaries: list[dict[str, Any]] = []
    all_orders: list[pl.DataFrame] = []
    all_daily: list[pl.DataFrame] = []
    all_yearly: list[pl.DataFrame] = []
    all_targets: list[pl.DataFrame] = []
    all_events: list[pl.DataFrame] = []

    for top_k, basket_gross, max_per_industry in SHAPES:
        selected = build_concentrated_selected(base, top_k, basket_gross, max_per_industry)
        for rule in EXIT_RULES:
            summary, orders, daily, yearly, target_weights, events = replay_variant(
                selected,
                rule,
                benchmark_df,
                exec_info,
            )
            if summary:
                summaries.append(summary)
            if not orders.is_empty():
                all_orders.append(orders)
            if not daily.is_empty():
                all_daily.append(daily)
            if not yearly.is_empty():
                all_yearly.append(yearly)
            if not target_weights.is_empty():
                all_targets.append(target_weights)
            if not events.is_empty():
                all_events.append(events)

    summary_df = pl.DataFrame(summaries).sort(
        ["total_return_min_fee", "max_drawdown_min_fee", "sharpe_min_fee"],
        descending=[True, True, True],
    )
    orders_df = pl.concat(all_orders, how="vertical") if all_orders else pl.DataFrame()
    daily_df = pl.concat(all_daily, how="vertical") if all_daily else pl.DataFrame()
    yearly_df = pl.concat(all_yearly, how="vertical") if all_yearly else pl.DataFrame()
    target_df = pl.concat(all_targets, how="vertical") if all_targets else pl.DataFrame()
    events_df = pl.concat(all_events, how="vertical") if all_events else pl.DataFrame()
    exit_summary_df = summarize_exit_events(events_df)
    quality_df = build_quality(summary_df)

    summary_df.write_csv(paths["summary"])
    quality_df.write_csv(paths["quality"])
    yearly_df.write_csv(paths["yearly"])
    exit_summary_df.write_csv(paths["exit_summary"])
    target_df.write_csv(paths["target_weights"])
    orders_df.write_csv(paths["orders"])
    daily_df.write_csv(paths["daily"])
    report_path = write_report(summary_df, quality_df, yearly_df, exit_summary_df, paths)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "source": "weak_market60_q1q2_reallocated",
            "shapes": SHAPES,
            "exit_rules": [rule.__dict__ for rule in EXIT_RULES],
            "outputs": {key: str(value) for key, value in paths.items()},
            "report": str(report_path),
        },
    )
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
