from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import (
    HIGH_RETURN_TARGET,
    MAX_DRAWDOWN_LIMIT,
    summarize_daily_extra,
    to_float,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution import (
    FOCUS_SCENARIOS,
    PRIMARY_SCENARIO,
    build_drawdown_windows,
    read_csv_with_symbol,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_replay import (
    SOURCE_DIR as SELECTED_SOURCE_DIR,
    SOURCE_PREFIX as SELECTED_SOURCE_PREFIX,
    build_path_dates,
    read_selected,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_signal_date_loss_attribution import (
    FOCUS_SHAPES,
    REPLAY_SOURCE_DIR,
    REPLAY_SOURCE_PREFIX,
    build_signal_lots,
    cast_signal_numeric_features,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_exit_deterioration_replay_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_exit_deterioration_replay_v1"

WATCH_DAYS: int = 3
ACCOUNT_SIZE_CNY: float = 300_000.0

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit",
        "https://arxiv.org/abs/1411.5062",
    ),
    (
        "Mean Reversion Trading with Sequential Deadlines and Transaction Costs",
        "https://arxiv.org/abs/1707.03498",
    ),
    (
        "Short-term reversals, returns to liquidity provision and the costs of immediacy",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "Connors Research: Does Mean Reversion Still Work?",
        "https://connorsresearch.com/connors-research-traders-journal-volume-1-does-mean-reversion-still-work/",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)

SIGNAL_KEY: tuple[str, ...] = ("source_scenario", "signal_date", "symbol")


@dataclass(frozen=True)
class ExitRule:
    name: str
    description: str


EXIT_RULES: tuple[ExitRule, ...] = (
    ExitRule(
        "base_no_exit",
        "不做持仓期恶化退出，复现第308阶段代表场景。",
    ),
    ExitRule(
        "exit_watch3_no_bounce",
        "入场后前3天观察；若第2或第3天累计收益仍小于等于-3%，次日退出剩余lot。",
    ),
    ExitRule(
        "exit_watch3_ma20_shortweak",
        "入场后前3天观察；若收盘低于MA20超过3%且5日收益小于等于-5%，次日退出剩余lot。",
    ),
    ExitRule(
        "exit_watch3_volume_selloff",
        "入场后前3天观察；若当日收盘相对开盘跌超2%、IBS低于0.25且量比高于1.3，次日退出剩余lot。",
    ),
    ExitRule(
        "exit_watch3_composite_2of3",
        "入场后前3天观察；若无反弹、MA20短弱、放量低IBS下杀三类恶化中至少两类同时出现，次日退出剩余lot。",
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def annualized_sharpe(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    if variance <= 0:
        return 0.0
    return mean / sqrt(variance) * sqrt(TRADING_DAYS)


def build_stock_path_features(stock_df: pl.DataFrame) -> pl.DataFrame:
    close = pl.col("trade_close")
    open_ = pl.col("trade_open")
    high = pl.col("trade_high")
    low = pl.col("trade_low")
    volume = pl.col("volume")
    return (
        stock_df.select(
            [
                "datetime",
                "symbol",
                "trade_open",
                "trade_high",
                "trade_low",
                "trade_close",
                "preclose",
                "volume",
            ]
        )
        .sort(["symbol", "datetime"])
        .with_columns(
            (close / close.shift(1).over("symbol") - 1.0).alias("target_daily_ret"),
            (close / close.shift(5).over("symbol") - 1.0).alias("path_ret_5"),
            (close / close.shift(10).over("symbol") - 1.0).alias("path_ret_10"),
            (close / close.rolling_mean(20).over("symbol") - 1.0).alias("path_dist_ma20"),
            (close / close.rolling_mean(60).over("symbol") - 1.0).alias("path_dist_ma60"),
            (close / close.rolling_max(252).over("symbol")).alias("path_close_to_high_252"),
            (volume / volume.rolling_mean(20).over("symbol")).alias("path_volume_ratio_20"),
            pl.when((high - low).abs() > 1e-12)
            .then((close - low) / (high - low))
            .otherwise(None)
            .alias("path_ibs"),
            pl.when((open_ > 0) & close.is_not_null())
            .then(close / open_ - 1.0)
            .otherwise(None)
            .alias("path_intraday_ret"),
        )
        .rename({"datetime": "target_date"})
        .select(
            [
                "target_date",
                "symbol",
                "target_daily_ret",
                "path_ret_5",
                "path_ret_10",
                "path_dist_ma20",
                "path_dist_ma60",
                "path_close_to_high_252",
                "path_volume_ratio_20",
                "path_ibs",
                "path_intraday_ret",
            ]
        )
    )


def build_enriched_lots(stock_df: pl.DataFrame) -> pl.DataFrame:
    selected = read_selected().join(build_path_dates(stock_df), on=["datetime", "symbol"], how="left")
    lots = (
        build_signal_lots(selected)
        .rename({"scenario": "source_scenario"})
        .filter(pl.col("source_scenario").is_in(FOCUS_SCENARIOS))
    )
    path_features = build_stock_path_features(stock_df)
    enriched = (
        lots.join(path_features, on=["target_date", "symbol"], how="left")
        .with_columns(
            pl.col("target_daily_ret").fill_null(0.0).alias("target_daily_ret"),
            (1.0 + pl.col("target_daily_ret").fill_null(0.0))
            .cum_prod()
            .over(list(SIGNAL_KEY))
            .sub(1.0)
            .alias("cum_ret_to_day"),
        )
        .with_columns(
            (
                (pl.col("holding_day") <= WATCH_DAYS)
                & (pl.col("holding_day") >= 2)
                & (pl.col("cum_ret_to_day") <= -0.03)
            ).alias("trigger_no_bounce"),
            (
                (pl.col("holding_day") <= WATCH_DAYS)
                & (pl.col("path_dist_ma20") <= -0.03)
                & (pl.col("path_ret_5") <= -0.05)
            ).alias("trigger_ma20_shortweak"),
            (
                (pl.col("holding_day") <= WATCH_DAYS)
                & (pl.col("path_intraday_ret") <= -0.02)
                & (pl.col("path_ibs") <= 0.25)
                & (pl.col("path_volume_ratio_20") >= 1.30)
            ).alias("trigger_volume_selloff"),
        )
        .with_columns(
            (
                pl.col("trigger_no_bounce").cast(pl.Int8)
                + pl.col("trigger_ma20_shortweak").cast(pl.Int8)
                + pl.col("trigger_volume_selloff").cast(pl.Int8)
            ).alias("trigger_component_count")
        )
        .with_columns(
            ((pl.col("holding_day") <= WATCH_DAYS) & (pl.col("trigger_component_count") >= 2)).alias(
                "trigger_composite_2of3"
            ),
            (pl.col("lot_weight") * pl.col("target_daily_ret")).alias("lot_contribution"),
        )
    )
    return cast_signal_numeric_features(enriched).sort([*SIGNAL_KEY, "holding_day"])


def trigger_column(rule_name: str) -> str | None:
    mapping = {
        "exit_watch3_no_bounce": "trigger_no_bounce",
        "exit_watch3_ma20_shortweak": "trigger_ma20_shortweak",
        "exit_watch3_volume_selloff": "trigger_volume_selloff",
        "exit_watch3_composite_2of3": "trigger_composite_2of3",
    }
    return mapping.get(rule_name)


def build_first_triggers(lots: pl.DataFrame, rule_name: str) -> pl.DataFrame:
    col = trigger_column(rule_name)
    if col is None:
        return pl.DataFrame()
    return (
        lots.filter(pl.col(col))
        .sort([*SIGNAL_KEY, "holding_day"])
        .group_by(list(SIGNAL_KEY), maintain_order=True)
        .agg(
            pl.col("holding_day").first().alias("exit_after_holding_day"),
            pl.col("target_date").first().alias("trigger_date"),
            pl.col("cum_ret_to_day").first().alias("trigger_cum_ret_to_day"),
            pl.col("path_ret_5").first().alias("trigger_path_ret_5"),
            pl.col("path_dist_ma20").first().alias("trigger_path_dist_ma20"),
            pl.col("path_volume_ratio_20").first().alias("trigger_path_volume_ratio_20"),
            pl.col("path_ibs").first().alias("trigger_path_ibs"),
            pl.col("path_intraday_ret").first().alias("trigger_path_intraday_ret"),
            pl.col("trigger_component_count").first().alias("trigger_component_count"),
        )
    )


def build_rule_lots(lots: pl.DataFrame, rule: ExitRule) -> tuple[pl.DataFrame, pl.DataFrame]:
    if rule.name == "base_no_exit":
        return (
            lots.with_columns(
                pl.lit(rule.name).alias("exit_rule"),
                pl.lit(None, dtype=pl.Int64).alias("exit_after_holding_day"),
                pl.lit(None, dtype=pl.Date).alias("trigger_date"),
                pl.lit(False).alias("removed_by_exit"),
            ),
            pl.DataFrame(),
        )
    triggers = build_first_triggers(lots, rule.name)
    with_triggers = lots.join(triggers, on=list(SIGNAL_KEY), how="left").with_columns(
        pl.lit(rule.name).alias("exit_rule"),
        (pl.col("exit_after_holding_day").is_not_null() & (pl.col("holding_day") > pl.col("exit_after_holding_day"))).alias(
            "removed_by_exit"
        ),
    )
    events = build_trigger_events(with_triggers, rule.name)
    return with_triggers, events


def build_trigger_events(rule_lots: pl.DataFrame, rule_name: str) -> pl.DataFrame:
    triggered = rule_lots.filter(pl.col("exit_after_holding_day").is_not_null())
    if triggered.is_empty():
        return pl.DataFrame()
    return (
        triggered.group_by([*SIGNAL_KEY, "exit_rule"])
        .agg(
            pl.col("trigger_date").first(),
            pl.col("exit_after_holding_day").first(),
            pl.col("trigger_cum_ret_to_day").first(),
            pl.col("trigger_path_ret_5").first(),
            pl.col("trigger_path_dist_ma20").first(),
            pl.col("trigger_path_volume_ratio_20").first(),
            pl.col("trigger_path_ibs").first(),
            pl.col("trigger_path_intraday_ret").first(),
            pl.col("trigger_component_count").first(),
            pl.col("lot_contribution").sum().alias("original_signal_contribution"),
            pl.when(pl.col("holding_day") <= pl.col("exit_after_holding_day"))
            .then(pl.col("lot_contribution"))
            .otherwise(0.0)
            .sum()
            .alias("kept_contribution"),
            pl.when(pl.col("holding_day") > pl.col("exit_after_holding_day"))
            .then(pl.col("lot_contribution"))
            .otherwise(0.0)
            .sum()
            .alias("removed_future_contribution"),
            pl.len().alias("lot_days"),
        )
        .with_columns(
            (-pl.col("removed_future_contribution")).alias("exit_delta"),
            (pl.col("removed_future_contribution") < 0).alias("exit_helped"),
            pl.lit(rule_name).alias("exit_rule"),
        )
    )


def build_target_weights(rule_lots: pl.DataFrame) -> pl.DataFrame:
    kept = rule_lots.filter(~pl.col("removed_by_exit"))
    extra_cols = [
        col
        for col in [
            "exit_rule",
            "source_scenario",
            "code_name",
            "industry",
            "market",
            "model",
            "model_description",
            "shape_horizon",
            "shape_top_k",
            "shape_basket_gross_weight",
            "shape_max_per_industry",
        ]
        if col in kept.columns
    ]
    grouped = (
        kept.group_by(["exit_rule", "source_scenario", "target_date", "symbol"])
        .agg(
            pl.col("lot_weight").sum().alias("target_weight"),
            pl.len().alias("active_lots"),
            pl.col("signal_date").n_unique().alias("source_signal_days"),
            pl.col("holding_day").min().alias("min_holding_day"),
            pl.col("holding_day").max().alias("max_holding_day"),
            *[pl.col(col).first().alias(col) for col in extra_cols if col not in {"exit_rule", "source_scenario"}],
        )
        .filter(pl.col("target_weight") > 1e-12)
        .with_columns(
            (pl.col("source_scenario") + pl.lit("__") + pl.col("exit_rule")).alias("scenario"),
        )
        .sort(["scenario", "target_date", "symbol"])
    )
    return grouped


def build_yearly(daily: pl.DataFrame) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()
    return (
        daily.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["scenario", "source_scenario", "exit_rule", "year"])
        .agg(
            ((1 + pl.col("strategy_daily_ret_min_fee")).product() - 1).alias("year_return_min_fee"),
            pl.col("drawdown_min_fee").min().alias("year_curve_drawdown_min_fee"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            (pl.col("zero_lot_target_count").sum() / pl.col("target_symbol_count").sum()).alias("zero_lot_target_ratio"),
        )
        .sort(["scenario", "year"])
    )


def replay_variant_targets(
    target_weights: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    summaries: list[dict[str, Any]] = []
    orders_list: list[pl.DataFrame] = []
    daily_list: list[pl.DataFrame] = []
    for scenario in target_weights["scenario"].unique().sort().to_list():
        scenario_targets = target_weights.filter(pl.col("scenario") == scenario).drop("scenario")
        source_scenario = scenario_targets["source_scenario"][0]
        exit_rule = scenario_targets["exit_rule"][0]
        target_maps = lot.build_target_maps(scenario_targets)
        dates = lot.build_tracking_dates(scenario_targets, benchmark_df)
        orders, daily, _curve = lot.replay_lot_account(target_maps, dates, exec_info)
        if not orders.is_empty():
            orders = orders.with_columns(
                pl.lit(scenario).alias("scenario"),
                pl.lit(source_scenario).alias("source_scenario"),
                pl.lit(exit_rule).alias("exit_rule"),
            )
            orders_list.append(orders)
        if not daily.is_empty():
            daily = daily.with_columns(
                pl.lit(scenario).alias("scenario"),
                pl.lit(source_scenario).alias("source_scenario"),
                pl.lit(exit_rule).alias("exit_rule"),
            )
            daily_list.append(daily)
        summary = lot.summarize_orders(orders, daily)
        summary = summarize_daily_extra(summary, daily)
        summary.update(
            {
                "scenario": scenario,
                "source_scenario": source_scenario,
                "exit_rule": exit_rule,
            }
        )
        summaries.append(summary)
    summary_df = pl.DataFrame(summaries).sort(
        ["source_scenario", "exit_rule", "total_return_min_fee"],
        descending=[False, False, True],
    )
    daily_df = pl.concat(daily_list, how="diagonal_relaxed") if daily_list else pl.DataFrame()
    orders_df = pl.concat(orders_list, how="diagonal_relaxed") if orders_list else pl.DataFrame()
    return summary_df, orders_df, daily_df


def build_event_summary(events: pl.DataFrame, opportunities: pl.DataFrame, drawdown_windows: pl.DataFrame) -> pl.DataFrame:
    if events.is_empty():
        return pl.DataFrame()
    events_with_window = events.join(drawdown_windows.select(["scenario", "start_date", "trough_date"]).rename({"scenario": "source_scenario"}), on="source_scenario", how="left")
    samples = [
        ("full_history", events_with_window, opportunities),
        (
            "drawdown_window",
            events_with_window.filter((pl.col("trigger_date") >= pl.col("start_date")) & (pl.col("trigger_date") <= pl.col("trough_date"))),
            opportunities.filter((pl.col("target_date") >= pl.col("start_date")) & (pl.col("target_date") <= pl.col("trough_date"))),
        ),
        (
            "outside_drawdown",
            events_with_window.filter((pl.col("trigger_date") < pl.col("start_date")) | (pl.col("trigger_date") > pl.col("trough_date"))),
            opportunities.filter((pl.col("target_date") < pl.col("start_date")) | (pl.col("target_date") > pl.col("trough_date"))),
        ),
    ]
    parts: list[pl.DataFrame] = []
    for sample_name, sample_events, sample_opps in samples:
        if sample_events.is_empty():
            continue
        denom = (
            sample_opps.group_by("source_scenario")
            .agg(pl.struct(["signal_date", "symbol"]).n_unique().alias("opportunity_signals"))
            .with_columns(pl.lit(sample_name).alias("sample"))
        )
        summary = (
            sample_events.group_by(["source_scenario", "exit_rule"])
            .agg(
                pl.struct(["signal_date", "symbol"]).n_unique().alias("triggered_signals"),
                pl.col("exit_delta").sum().alias("exit_delta_sum"),
                pl.col("removed_future_contribution").sum().alias("removed_future_contribution_sum"),
                pl.col("exit_delta").mean().alias("avg_exit_delta"),
                pl.col("exit_helped").mean().alias("exit_help_ratio"),
                pl.col("exit_after_holding_day").mean().alias("avg_exit_after_holding_day"),
                pl.col("trigger_cum_ret_to_day").mean().alias("avg_trigger_cum_ret_to_day"),
            )
            .with_columns(pl.lit(sample_name).alias("sample"))
            .join(denom, on=["source_scenario", "sample"], how="left")
            .with_columns((pl.col("triggered_signals") / pl.col("opportunity_signals")).alias("trigger_ratio"))
        )
        parts.append(summary)
    return pl.concat(parts, how="diagonal_relaxed").sort(["sample", "source_scenario", "exit_delta_sum"])


def build_opportunities(lots: pl.DataFrame, drawdown_windows: pl.DataFrame) -> pl.DataFrame:
    return (
        lots.filter(pl.col("holding_day") <= WATCH_DAYS)
        .join(drawdown_windows.select(["scenario", "start_date", "trough_date"]).rename({"scenario": "source_scenario"}), on="source_scenario", how="left")
    )


def build_impact_summary(summary: pl.DataFrame, events_summary: pl.DataFrame) -> pl.DataFrame:
    base = (
        summary.filter(pl.col("exit_rule") == "base_no_exit")
        .select(
            [
                "source_scenario",
                pl.col("total_return_min_fee").alias("base_total_return_min_fee"),
                pl.col("max_drawdown_min_fee").alias("base_max_drawdown_min_fee"),
                pl.col("sharpe_min_fee").alias("base_sharpe_min_fee"),
                pl.col("order_rows").alias("base_order_rows"),
            ]
        )
    )
    impact = (
        summary.join(base, on="source_scenario", how="left")
        .with_columns(
            (pl.col("total_return_min_fee") - pl.col("base_total_return_min_fee")).alias("total_return_delta"),
            (pl.col("max_drawdown_min_fee") - pl.col("base_max_drawdown_min_fee")).alias("max_drawdown_delta"),
            (pl.col("sharpe_min_fee") - pl.col("base_sharpe_min_fee")).alias("sharpe_delta"),
            (pl.col("order_rows") - pl.col("base_order_rows")).alias("order_rows_delta"),
        )
    )
    full_events = events_summary.filter(pl.col("sample") == "full_history").select(
        [
            "source_scenario",
            "exit_rule",
            "triggered_signals",
            "trigger_ratio",
            "exit_delta_sum",
            "exit_help_ratio",
        ]
    )
    return impact.join(full_events, on=["source_scenario", "exit_rule"], how="left").sort(
        ["source_scenario", "max_drawdown_delta", "total_return_delta"],
        descending=[False, True, True],
    )


def build_quality(summary: pl.DataFrame, source_summary: pl.DataFrame, impact: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(checkpoint: str, status: str, value: Any, expected: Any, note: str) -> None:
        rows.append(
            {
                "checkpoint": checkpoint,
                "status": status,
                "value": "" if value is None else str(value),
                "expected": "" if expected is None else str(expected),
                "note": note,
            }
        )

    base = summary.filter(pl.col("exit_rule") == "base_no_exit")
    source_focus = source_summary.filter(pl.col("scenario").is_in(FOCUS_SCENARIOS))
    compare = base.join(
        source_focus.select(
            [
                pl.col("scenario").alias("source_scenario"),
                pl.col("total_return_min_fee").alias("source_total_return_min_fee"),
                pl.col("max_drawdown_min_fee").alias("source_max_drawdown_min_fee"),
                pl.col("sharpe_min_fee").alias("source_sharpe_min_fee"),
            ]
        ),
        on="source_scenario",
        how="left",
    ).with_columns(
        (pl.col("total_return_min_fee") - pl.col("source_total_return_min_fee")).abs().alias("return_abs_error"),
        (pl.col("max_drawdown_min_fee") - pl.col("source_max_drawdown_min_fee")).abs().alias("dd_abs_error"),
    )
    max_error = max(float(compare["return_abs_error"].max() or 0.0), float(compare["dd_abs_error"].max() or 0.0))
    add(
        "base_rerun_matches_stage308",
        "pass" if max_error <= 1e-10 else "fail",
        max_error,
        "<=1e-10",
        "退出规则回放的base必须精确复现第308阶段代表场景。",
    )
    add(
        "focus_scenario_count",
        "pass" if base.height == len(FOCUS_SCENARIOS) else "fail",
        base.height,
        len(FOCUS_SCENARIOS),
        "必须覆盖四个代表场景。",
    )
    add(
        "exit_rule_count",
        "pass" if summary["exit_rule"].n_unique() == len(EXIT_RULES) else "fail",
        summary["exit_rule"].n_unique(),
        len(EXIT_RULES),
        "只测试预注册的少量退出规则。",
    )
    best = impact.filter(pl.col("exit_rule") != "base_no_exit").sort(
        ["max_drawdown_delta", "total_return_delta"], descending=[True, True]
    )
    best_row = best.row(0, named=True) if not best.is_empty() else {}
    add(
        "any_exit_improves_drawdown_and_return",
        "pass"
        if best_row
        and to_float(best_row.get("max_drawdown_delta")) > 0
        and to_float(best_row.get("total_return_delta")) > 0
        else "warn",
        f"best_dd_delta={pct(to_float(best_row.get('max_drawdown_delta')))}, return_delta={pct(to_float(best_row.get('total_return_delta')))}"
        if best_row
        else "NA",
        "drawdown_delta>0 and return_delta>0",
        "退出规则若只能降收益或只改善很小，不应接入候选。",
    )
    pass_dd = summary.filter((pl.col("exit_rule") != "base_no_exit") & (pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT))
    add(
        "any_exit_within_20pct_drawdown",
        "pass" if not pass_dd.is_empty() else "warn",
        pass_dd.height,
        ">0",
        "用户给定的30万策略回撤边界。",
    )
    high_return = summary.filter((pl.col("exit_rule") != "base_no_exit") & (pl.col("total_return_min_fee") >= HIGH_RETURN_TARGET))
    add(
        "any_exit_high_return_target",
        "pass" if not high_return.is_empty() else "warn",
        high_return.height,
        ">0",
        "高收益目标，必须结合回撤看。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: pl.DataFrame,
    impact: pl.DataFrame,
    event_summary: pl.DataFrame,
    yearly: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    display_cols = [
        "source_scenario",
        "exit_rule",
        "final_equity_min_fee",
        "total_return_min_fee",
        "max_drawdown_min_fee",
        "sharpe_min_fee",
        "total_return_delta",
        "max_drawdown_delta",
        "sharpe_delta",
        "order_rows",
        "order_rows_delta",
        "zero_lot_target_ratio",
        "avg_actual_gross_weight",
        "triggered_signals",
        "trigger_ratio",
        "exit_delta_sum",
        "exit_help_ratio",
    ]
    primary = impact.filter(pl.col("source_scenario") == PRIMARY_SCENARIO)
    best_exit = impact.filter(pl.col("exit_rule") != "base_no_exit").sort(
        ["max_drawdown_delta", "total_return_delta"], descending=[True, True]
    )
    best_row = best_exit.row(0, named=True) if not best_exit.is_empty() else None
    primary_yearly = yearly.filter(pl.col("source_scenario") == PRIMARY_SCENARIO)

    def impact_row(source_scenario: str, exit_rule: str) -> dict[str, Any] | None:
        row = impact.filter((pl.col("source_scenario") == source_scenario) & (pl.col("exit_rule") == exit_rule))
        return row.row(0, named=True) if not row.is_empty() else None

    primary_volume = impact_row(PRIMARY_SCENARIO, "exit_watch3_volume_selloff")
    primary_ma20 = impact_row(PRIMARY_SCENARIO, "exit_watch3_ma20_shortweak")
    lines = [
        "# 股票震荡industry_resid_core 30万持仓期恶化退出回放 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：第317阶段后的持仓期恶化确认；少量预注册退出规则，真实30万整手回放。",
        f"- 观察窗口：入场后前`{WATCH_DAYS}`个持仓目标日，信号在收盘后确认，次日移除剩余lot。",
        "- A/B判断：股票震荡独立研究，不接入第78；若无稳定候选，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 均值回归不是无条件死扛，有限持有期和交易成本下，退出时机本身是策略设计的一部分。",
        "- 但短反策略常被普通止损破坏，因为深跌反而可能是修复来源；因此本阶段不测试固定百分比止损，只测试“入场后未修复且状态恶化”的退出。",
        "- 规则数量保持很少，且先验来自第316/317阶段，不继续扫描阈值。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
    ]
    if best_row:
        lines.append(
            f"- 全场最大回撤改善最高：`{best_row['source_scenario']}` / `{best_row['exit_rule']}`，总收益`{pct(best_row['total_return_min_fee'])}`，最大回撤`{pct(best_row['max_drawdown_min_fee'])}`，收益变化`{pct(best_row['total_return_delta'])}`，回撤变化`{pct(best_row['max_drawdown_delta'])}`。"
        )
    lines.extend(
        [
            "",
            "## 本次关键发现",
            "",
            "- `base_no_exit`精确复现第308阶段，说明本阶段退出回放口径可信。",
        ]
    )
    if primary_volume:
        lines.append(
            f"- 主观察场景中最温和的`exit_watch3_volume_selloff`：总收益从`{pct(primary_volume['base_total_return_min_fee'])}`降到`{pct(primary_volume['total_return_min_fee'])}`，最大回撤从`{pct(primary_volume['base_max_drawdown_min_fee'])}`改善到`{pct(primary_volume['max_drawdown_min_fee'])}`，收益损失`{pct(primary_volume['total_return_delta'])}`，回撤改善仅`{pct(primary_volume['max_drawdown_delta'])}`。"
        )
    if primary_ma20:
        lines.append(
            f"- 主观察场景中`exit_watch3_ma20_shortweak`触发率`{primary_ma20['trigger_ratio']:.2%}`，总收益损失`{pct(primary_ma20['total_return_delta'])}`，回撤还恶化`{pct(primary_ma20['max_drawdown_delta'])}`，说明高频退出会砍掉修复收益。"
        )
    lines.extend(
        [
            "- 事件归因也支持这个判断：除回撤窗口里的少量`volume_selloff`外，多数退出事件在全历史中移除的是正未来贡献。",
            "- 因此本阶段不产生候选策略；不应继续围绕前3天退出阈值做细扫。",
        ]
    )
    lines.extend(
        [
            "",
            "## 主观察场景结果",
            "",
            markdown_table(primary.select([col for col in display_cols if col in primary.columns]), [col for col in display_cols if col in primary.columns], max_rows=80)
            if not primary.is_empty()
            else "无数据",
            "",
            "## 全场影响汇总",
            "",
            markdown_table(impact.select([col for col in display_cols if col in impact.columns]), [col for col in display_cols if col in impact.columns], max_rows=160),
            "",
            "## 触发事件归因",
            "",
            markdown_table(event_summary, event_summary.columns, max_rows=160) if not event_summary.is_empty() else "无数据",
            "",
            "## 主观察场景年度拆分",
            "",
            markdown_table(primary_yearly, primary_yearly.columns, max_rows=160) if not primary_yearly.is_empty() else "无数据",
            "",
            "## 质量检查",
            "",
            markdown_table(quality, quality.columns, max_rows=80),
            "",
            "## 结论",
            "",
            "- 本阶段否决普通持仓期恶化退出：没有任何规则同时改善收益和回撤，也没有任何规则把回撤压到20%以内。",
            "- `volume_selloff`可作为风险观察标签保留，但不是交易规则候选；它的回撤改善太小且全历史收益受损。",
            "- 下一步不应继续扫退出阈值，应转向组合层结构：降低长回撤期暴露的方式必须来自更慢、更稳的风险预算或策略组合，而不是单票短期退出。",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "impact": OUTPUT_DIR / f"{PREFIX}_impact_summary.csv",
        "event_summary": OUTPUT_DIR / f"{PREFIX}_event_summary.csv",
        "events": OUTPUT_DIR / f"{PREFIX}_events.csv",
        "target_weights": OUTPUT_DIR / f"{PREFIX}_target_weights.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
    }

    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)
    source_daily = read_csv_with_symbol(REPLAY_SOURCE_DIR / f"{REPLAY_SOURCE_PREFIX}_daily.csv")
    source_summary = read_csv_with_symbol(REPLAY_SOURCE_DIR / f"{REPLAY_SOURCE_PREFIX}_summary.csv")
    drawdown_windows = build_drawdown_windows(source_daily)

    base_lots = build_enriched_lots(stock_df)
    rule_lot_frames: list[pl.DataFrame] = []
    event_frames: list[pl.DataFrame] = []
    for rule in EXIT_RULES:
        rule_lots, events = build_rule_lots(base_lots, rule)
        rule_lot_frames.append(rule_lots)
        if not events.is_empty():
            event_frames.append(events)
    all_rule_lots = pl.concat(rule_lot_frames, how="diagonal_relaxed")
    all_events = pl.concat(event_frames, how="diagonal_relaxed") if event_frames else pl.DataFrame()
    opportunities = build_opportunities(base_lots, drawdown_windows)
    event_summary = build_event_summary(all_events, opportunities, drawdown_windows)
    target_weights = build_target_weights(all_rule_lots)

    summary, orders, daily = replay_variant_targets(target_weights, benchmark_df, exec_info)
    yearly = build_yearly(daily)
    impact = build_impact_summary(summary, event_summary)
    quality = build_quality(summary, source_summary, impact)
    report_path = write_report(summary, impact, event_summary, yearly, quality, paths)

    summary.write_csv(paths["summary"])
    impact.write_csv(paths["impact"])
    event_summary.write_csv(paths["event_summary"])
    all_events.write_csv(paths["events"])
    target_weights.write_csv(paths["target_weights"])
    orders.write_csv(paths["orders"])
    daily.write_csv(paths["daily"])
    yearly.write_csv(paths["yearly"])
    quality.write_csv(paths["quality"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "watch_days": WATCH_DAYS,
            "focus_shapes": FOCUS_SHAPES,
            "focus_scenarios": FOCUS_SCENARIOS,
            "exit_rules": [rule.__dict__ for rule in EXIT_RULES],
            "selected_source_dir": str(SELECTED_SOURCE_DIR),
            "selected_source_prefix": SELECTED_SOURCE_PREFIX,
            "replay_source_dir": str(REPLAY_SOURCE_DIR),
            "replay_source_prefix": REPLAY_SOURCE_PREFIX,
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
            "report": str(report_path),
        },
    )
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
