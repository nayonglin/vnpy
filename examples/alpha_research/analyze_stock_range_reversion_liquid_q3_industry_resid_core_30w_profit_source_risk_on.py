from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from math import ceil, sqrt
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
    read_csv_with_symbol,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_regime_attribution import (
    REGIME_COLUMNS,
    build_interaction_summary,
    build_market_state,
    build_strategy_state,
    enrich_daily,
    regime_summary,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_v1"

MAX_CASH_GROSS_WEIGHT: float = 1.0
CANDIDATE_BASE_SCENARIO: str = "industry_resid_core_h10_top5_gross70_ind1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Volatility Managed Portfolios",
        "https://www.stern.nyu.edu/sites/default/files/assets/documents/Volatility%20Managed%20Portfolios.pdf",
    ),
    (
        "Smoothing volatility targeting",
        "https://arxiv.org/abs/2212.07288",
    ),
    (
        "QuantPedia Cross-Sectional Equity Mean Reversion",
        "https://quantpedia.com/quantopian-quantpedia-trading-strategy-series-cross-sectional-equity-mean-rever/",
    ),
    (
        "Backtesting a Cross-Sectional Mean Reversion Strategy in Python",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "GitHub risk-parity topic",
        "https://github.com/topics/risk-parity",
    ),
)


@dataclass(frozen=True)
class RiskOnRule:
    name: str
    description: str
    max_scale: float
    condition: str
    uses_base_strategy_state: bool = False


RISK_ON_RULES: tuple[RiskOnRule, ...] = (
    RiskOnRule(
        name="breadth_ret20_healthy_plus25_cap100",
        description="前一日20日上涨家数占比处于健康桶时，目标权重乘1.25，但组合目标毛仓不超过100%。",
        max_scale=1.25,
        condition="breadth_ret20_healthy",
    ),
    RiskOnRule(
        name="breadth_ret20_healthy_cash_to_full",
        description="前一日20日上涨家数占比处于健康桶时，尽量把现金仓位补到100%目标毛仓。",
        max_scale=10.0,
        condition="breadth_ret20_healthy",
    ),
    RiskOnRule(
        name="strategy_not_hot_plus25_cap100",
        description="基准路径前一日策略60日收益不处于ret60_up时，目标权重乘1.25，但组合目标毛仓不超过100%。",
        max_scale=1.25,
        condition="strategy_not_hot",
        uses_base_strategy_state=True,
    ),
    RiskOnRule(
        name="strategy_not_hot_cash_to_full",
        description="基准路径前一日策略60日收益不处于ret60_up时，尽量把现金仓位补到100%目标毛仓。",
        max_scale=10.0,
        condition="strategy_not_hot",
        uses_base_strategy_state=True,
    ),
    RiskOnRule(
        name="breadth_healthy_strategy_not_hot_cash_to_full",
        description="前一日20日上涨家数健康且基准路径策略60日收益不热时，尽量把现金仓位补到100%目标毛仓。",
        max_scale=10.0,
        condition="breadth_healthy_and_strategy_not_hot",
        uses_base_strategy_state=True,
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def normalize_summary_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (date, datetime)):
            normalized[key] = value.isoformat()
        else:
            normalized[key] = value
    return normalized


def annualized_sharpe(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    if variance <= 0:
        return 0.0
    return mean / sqrt(variance) * sqrt(TRADING_DAYS)


def build_regime_feature_summary(enriched: pl.DataFrame) -> pl.DataFrame:
    parts: list[pl.DataFrame] = []
    for col in REGIME_COLUMNS:
        scenario_part = regime_summary(enriched, ["scenario", col])
        if not scenario_part.is_empty():
            parts.append(
                scenario_part.rename({col: "bucket"}).with_columns(pl.lit(col).alias("regime_feature"))
            )
        all_part = regime_summary(enriched, [col])
        if not all_part.is_empty():
            parts.append(
                all_part.rename({col: "bucket"}).with_columns(
                    pl.lit("ALL").alias("scenario"),
                    pl.lit(col).alias("regime_feature"),
                )
            )
    if not parts:
        return pl.DataFrame()
    return (
        pl.concat(parts, how="diagonal_relaxed")
        .select(
            [
                "scenario",
                "regime_feature",
                "bucket",
                "days",
                "compound_return",
                "simple_return_sum",
                "avg_daily_ret",
                "loss_day_ratio",
                "avg_actual_gross_weight",
                "avg_actual_symbol_count",
                "zero_lot_target_ratio",
            ]
        )
        .sort(["scenario", "compound_return"], descending=[False, True])
    )


def build_cross_good_regimes(feature_summary: pl.DataFrame) -> pl.DataFrame:
    scenario_rows = feature_summary.filter(pl.col("scenario") != "ALL")
    if scenario_rows.is_empty():
        return pl.DataFrame()
    return (
        scenario_rows.group_by(["regime_feature", "bucket"])
        .agg(
            pl.col("scenario").n_unique().alias("scenario_count"),
            (pl.col("compound_return") > 0).sum().alias("positive_scenario_count"),
            pl.col("days").sum().alias("days"),
            pl.col("compound_return").sum().alias("compound_return_sum"),
            pl.col("simple_return_sum").sum().alias("simple_return_sum"),
            pl.col("avg_daily_ret").mean().alias("avg_daily_ret"),
            pl.col("loss_day_ratio").mean().alias("avg_loss_day_ratio"),
            pl.col("avg_actual_gross_weight").mean().alias("avg_actual_gross_weight"),
        )
        .filter((pl.col("scenario_count") >= 3) & (pl.col("positive_scenario_count") >= 3))
        .sort(["positive_scenario_count", "simple_return_sum"], descending=[True, True])
    )


def build_cross_good_interactions(interaction_summary: pl.DataFrame) -> pl.DataFrame:
    if interaction_summary.is_empty():
        return pl.DataFrame()
    return (
        interaction_summary.group_by(["interaction_feature", "bucket"])
        .agg(
            pl.col("scenario").n_unique().alias("scenario_count"),
            (pl.col("compound_return") > 0).sum().alias("positive_scenario_count"),
            pl.col("days").sum().alias("days"),
            pl.col("compound_return").sum().alias("compound_return_sum"),
            pl.col("simple_return_sum").sum().alias("simple_return_sum"),
            pl.col("avg_daily_ret").mean().alias("avg_daily_ret"),
            pl.col("loss_day_ratio").mean().alias("avg_loss_day_ratio"),
            pl.col("avg_actual_gross_weight").mean().alias("avg_actual_gross_weight"),
        )
        .filter((pl.col("scenario_count") >= 3) & (pl.col("positive_scenario_count") >= 3))
        .sort(["positive_scenario_count", "simple_return_sum"], descending=[True, True])
    )


def build_return_tail_summary(enriched: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for frame in enriched.partition_by("scenario"):
        scenario = frame["scenario"][0]
        returns = [float(value) for value in frame["strategy_daily_ret_min_fee"].to_list()]
        if not returns:
            continue
        total = sum(returns)
        sorted_returns = sorted(returns)
        n_tail = max(1, ceil(len(returns) * 0.10))
        top_sum = sum(sorted_returns[-n_tail:])
        bottom_sum = sum(sorted_returns[:n_tail])
        positive_sum = sum(value for value in returns if value > 0)
        negative_sum = sum(value for value in returns if value < 0)
        rows.append(
            {
                "scenario": scenario,
                "days": len(returns),
                "simple_return_sum": total,
                "positive_day_count": sum(1 for value in returns if value > 0),
                "negative_day_count": sum(1 for value in returns if value < 0),
                "positive_return_sum": positive_sum,
                "negative_return_sum": negative_sum,
                "top10pct_day_return_sum": top_sum,
                "bottom10pct_day_return_sum": bottom_sum,
                "top10pct_share_of_positive_sum": top_sum / positive_sum if positive_sum else 0.0,
                "bottom10pct_share_of_negative_sum": bottom_sum / negative_sum if negative_sum else 0.0,
                "avg_daily_ret": total / len(returns),
                "sharpe_min_fee": annualized_sharpe(returns),
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None).sort("simple_return_sum", descending=True)


def build_target_source_summary(target_weights: pl.DataFrame, stock_df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    stock_ret = (
        stock_df.select(["datetime", "symbol", "trade_open"])
        .sort(["symbol", "datetime"])
        .with_columns(pl.col("trade_open").shift(-1).over("symbol").alias("next_trade_open"))
        .with_columns(
            pl.when(
                pl.col("trade_open").is_not_null()
                & (pl.col("trade_open") > 0)
                & pl.col("next_trade_open").is_not_null()
                & (pl.col("next_trade_open") > 0)
            )
            .then(pl.col("next_trade_open") / pl.col("trade_open") - 1.0)
            .otherwise(None)
            .alias("open_to_next_open_ret")
        )
        .select(["datetime", "symbol", "open_to_next_open_ret"])
    )
    joined = (
        target_weights.filter(pl.col("scenario").is_in(FOCUS_SCENARIOS))
        .join(stock_ret, left_on=["target_date", "symbol"], right_on=["datetime", "symbol"], how="left")
        .with_columns(
            (pl.col("target_weight") * pl.col("open_to_next_open_ret").fill_null(0.0)).alias("raw_target_contribution"),
            (
                pl.col("model_score").rank("average").over(["scenario", "target_date"])
                / pl.len().over(["scenario", "target_date"])
            ).alias("selected_score_rank_pct"),
        )
        .with_columns(
            pl.when(pl.col("selected_score_rank_pct") >= 0.80)
            .then(pl.lit("selected_score_top20"))
            .when(pl.col("selected_score_rank_pct") >= 0.50)
            .then(pl.lit("selected_score_mid"))
            .otherwise(pl.lit("selected_score_low"))
            .alias("selected_score_bucket")
        )
    )
    industry = (
        joined.group_by(["scenario", "industry"])
        .agg(
            pl.len().alias("target_rows"),
            pl.col("target_date").n_unique().alias("target_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("raw_target_contribution").sum().alias("raw_contribution_sum"),
            pl.col("open_to_next_open_ret").mean().alias("avg_open_to_next_open_ret"),
            (pl.col("open_to_next_open_ret") > 0).mean().alias("positive_row_ratio"),
            pl.col("model_score").mean().alias("avg_model_score"),
        )
        .sort(["scenario", "raw_contribution_sum"], descending=[False, True])
    )
    score_bucket = (
        joined.group_by(["scenario", "selected_score_bucket"])
        .agg(
            pl.len().alias("target_rows"),
            pl.col("target_date").n_unique().alias("target_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("raw_target_contribution").sum().alias("raw_contribution_sum"),
            pl.col("open_to_next_open_ret").mean().alias("avg_open_to_next_open_ret"),
            (pl.col("open_to_next_open_ret") > 0).mean().alias("positive_row_ratio"),
            pl.col("model_score").mean().alias("avg_model_score"),
        )
        .sort(["scenario", "raw_contribution_sum"], descending=[False, True])
    )
    return industry, score_bucket


def condition_is_on(rule: RiskOnRule, state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    breadth_healthy = state.get("prev_breadth_ret20_state") == "ret20_healthy"
    strategy_not_hot = state.get("prev_strategy_ret60_state") in {"ret60_flat", "ret60_down"}
    if rule.condition == "breadth_ret20_healthy":
        return breadth_healthy
    if rule.condition == "strategy_not_hot":
        return strategy_not_hot
    if rule.condition == "breadth_healthy_and_strategy_not_hot":
        return breadth_healthy and strategy_not_hot
    raise ValueError(f"Unknown risk-on condition: {rule.condition}")


def build_state_map(enriched: pl.DataFrame) -> dict[tuple[str, date], dict[str, Any]]:
    cols = [
        "scenario",
        "date",
        "prev_breadth_ret20_state",
        "prev_breadth_ma60_state",
        "prev_index_trend_120_state",
        "prev_index_drawdown_120_state",
        "prev_index_vol60_state",
        "prev_strategy_ret60_state",
        "prev_strategy_dd120_state",
        "prev_strategy_vol60_state",
    ]
    return {
        (str(row["scenario"]), row["date"]): row
        for row in enriched.select([col for col in cols if col in enriched.columns]).iter_rows(named=True)
    }


def scale_targets_for_rule(
    scenario_targets: pl.DataFrame,
    base_scenario: str,
    rule: RiskOnRule,
    state_map: dict[tuple[str, date], dict[str, Any]],
) -> tuple[pl.DataFrame, pl.DataFrame]:
    scaled_frames: list[pl.DataFrame] = []
    scale_rows: list[dict[str, Any]] = []
    for frame in scenario_targets.partition_by("target_date"):
        target_date = frame["target_date"][0]
        base_gross = float(frame["target_weight"].sum() or 0.0)
        state = state_map.get((base_scenario, target_date))
        on = condition_is_on(rule, state)
        desired_scale = rule.max_scale if on else 1.0
        cap_scale = MAX_CASH_GROSS_WEIGHT / base_gross if base_gross > 0 else 1.0
        effective_scale = min(desired_scale, cap_scale)
        scaled_frames.append(
            frame.with_columns(
                pl.col("target_weight").alias("base_target_weight"),
                (pl.col("target_weight") * effective_scale).alias("target_weight"),
                pl.lit(rule.name).alias("risk_on_rule_name"),
                pl.lit(rule.description).alias("risk_on_rule_description"),
                pl.lit(on).alias("risk_on_condition_on"),
                pl.lit(desired_scale).alias("risk_on_desired_scale"),
                pl.lit(effective_scale).alias("risk_on_effective_scale"),
                pl.lit(base_gross).alias("base_target_gross_weight"),
                pl.lit(base_gross * effective_scale).alias("scaled_target_gross_weight"),
            )
        )
        scale_rows.append(
            {
                "base_scenario": base_scenario,
                "risk_on_rule_name": rule.name,
                "target_date": target_date,
                "risk_on_condition_on": on,
                "risk_on_desired_scale": desired_scale,
                "risk_on_effective_scale": effective_scale,
                "base_target_gross_weight": base_gross,
                "scaled_target_gross_weight": base_gross * effective_scale,
                "prev_breadth_ret20_state": state.get("prev_breadth_ret20_state") if state else "missing",
                "prev_strategy_ret60_state": state.get("prev_strategy_ret60_state") if state else "missing",
            }
        )
    scaled = pl.concat(scaled_frames, how="diagonal_relaxed") if scaled_frames else pl.DataFrame()
    scale_daily = pl.DataFrame(scale_rows, infer_schema_length=None)
    return scaled, scale_daily


def add_base_deltas(summary: pl.DataFrame) -> pl.DataFrame:
    base = (
        summary.filter(pl.col("risk_on_rule_name") == "base_rerun")
        .select(
            "base_scenario",
            pl.col("final_equity_min_fee").alias("base_final_equity_min_fee"),
            pl.col("total_return_min_fee").alias("base_total_return_min_fee"),
            pl.col("max_drawdown_min_fee").alias("base_max_drawdown_min_fee"),
            pl.col("sharpe_min_fee").alias("base_sharpe_min_fee"),
            pl.col("avg_actual_gross_weight").alias("base_avg_actual_gross_weight"),
        )
    )
    return (
        summary.join(base, on="base_scenario", how="left")
        .with_columns(
            (pl.col("final_equity_min_fee") - pl.col("base_final_equity_min_fee")).alias("delta_final_equity_min_fee"),
            (pl.col("total_return_min_fee") - pl.col("base_total_return_min_fee")).alias("delta_total_return_min_fee"),
            (pl.col("max_drawdown_min_fee") - pl.col("base_max_drawdown_min_fee")).alias("delta_max_drawdown_min_fee"),
            (pl.col("sharpe_min_fee") - pl.col("base_sharpe_min_fee")).alias("delta_sharpe_min_fee"),
            (pl.col("avg_actual_gross_weight") - pl.col("base_avg_actual_gross_weight")).alias(
                "delta_avg_actual_gross_weight"
            ),
        )
        .drop(
            [
                "base_final_equity_min_fee",
                "base_total_return_min_fee",
                "base_max_drawdown_min_fee",
                "base_sharpe_min_fee",
                "base_avg_actual_gross_weight",
            ]
        )
    )


def build_quality(summary: pl.DataFrame, cross_good: pl.DataFrame, scale_daily: pl.DataFrame) -> pl.DataFrame:
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

    stress = summary.filter(pl.col("risk_on_rule_name") != "base_rerun")
    candidate = stress.filter(pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO)
    improve_return = stress.filter(pl.col("delta_total_return_min_fee") > 0)
    improve_both = stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") >= 0)
    )
    candidate_high_dd_ok = candidate.filter(
        (pl.col("total_return_min_fee") >= HIGH_RETURN_TARGET) & (pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT)
    )
    max_scaled_gross = to_float(scale_daily["scaled_target_gross_weight"].max()) if not scale_daily.is_empty() else None
    add(
        "focus_scenario_count",
        "pass" if summary["base_scenario"].n_unique() == len(FOCUS_SCENARIOS) else "fail",
        summary["base_scenario"].n_unique(),
        len(FOCUS_SCENARIOS),
        "固定四个代表形状。",
    )
    add(
        "risk_on_rule_count",
        "pass" if stress["risk_on_rule_name"].n_unique() == len(RISK_ON_RULES) else "fail",
        stress["risk_on_rule_name"].n_unique(),
        len(RISK_ON_RULES),
        "只运行预注册risk-on探针。",
    )
    add(
        "cross_good_regimes_available",
        "pass" if not cross_good.is_empty() else "warn",
        cross_good.height,
        ">0",
        "收益来源需要能找到跨场景一致正贡献状态。",
    )
    add(
        "cash_account_no_leverage",
        "pass" if max_scaled_gross is not None and max_scaled_gross <= MAX_CASH_GROSS_WEIGHT + 1e-9 else "fail",
        max_scaled_gross,
        f"<={MAX_CASH_GROSS_WEIGHT}",
        "30万现金账户探针不允许目标毛仓超过100%。",
    )
    add(
        "any_risk_on_improves_return",
        "pass" if not improve_return.is_empty() else "warn",
        f"{improve_return.height}/{stress.height}",
        ">0",
        "加仓探针至少需要提高收益才值得继续。",
    )
    add(
        "any_risk_on_improves_return_without_worse_dd",
        "pass" if not improve_both.is_empty() else "warn",
        f"{improve_both.height}/{stress.height}",
        ">0",
        "若加仓只提高收益但显著扩大回撤，不能作为风控友好版本。",
    )
    add(
        "candidate_high_return_and_within_20pct",
        "pass" if not candidate_high_dd_ok.is_empty() else "warn",
        f"{candidate_high_dd_ok.height}/{candidate.height}",
        ">0",
        "用户目标是30万高收益且回撤20%以内；若无，不能升级候选。",
    )
    add(
        "base_strategy_state_rules_are_exploratory",
        "warn" if any(rule.uses_base_strategy_state for rule in RISK_ON_RULES) else "pass",
        "base path state used",
        "path-dependent replay needed before candidate",
        "含策略自身状态的risk-on规则使用基准路径状态，只能作为收益来源探针。",
    )
    add(
        "no_alpha_change",
        "pass",
        "target exposure scaling only",
        "target exposure scaling only",
        "本阶段不改变选股信号和排序。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: pl.DataFrame,
    feature_summary: pl.DataFrame,
    cross_good: pl.DataFrame,
    interaction_good: pl.DataFrame,
    tail_summary: pl.DataFrame,
    industry_source: pl.DataFrame,
    score_source: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    stress = summary.filter(pl.col("risk_on_rule_name") != "base_rerun")
    best_return = stress.sort(["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True]).row(
        0, named=True
    )
    best_dd_ok = stress.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT).sort(
        ["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True]
    )
    best_dd_ok_line = (
        "- 回撤20%以内risk-on变体：无。"
        if best_dd_ok.is_empty()
        else (
            f"- 回撤20%以内risk-on收益最高：`{best_dd_ok['scenario'][0]}`，总收益"
            f"`{pct(best_dd_ok['total_return_min_fee'][0])}`，最大回撤"
            f"`{pct(best_dd_ok['max_drawdown_min_fee'][0])}`。"
        )
    )
    lines = [
        "# 股票震荡industry_resid_core 30万收益来源/risk-on探针 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡30万industry_resid_core独立研究线，不接入第78。",
        "- 本阶段性质：先归因收益来源，再测试现金账户不加杠杆的risk-on仓位探针。",
        f"- 账户规模：`{lot.ACCOUNT_SIZE_CNY:,.0f}`元；目标毛仓上限：`{MAX_CASH_GROSS_WEIGHT:.0%}`。",
        "- A/B判断：独立股票研究线收益来源归因，不触发第78 A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 公开波动管理/风险预算资料支持按可观测状态调整暴露，但收益 timing 比风险 timing 更容易过拟合。",
        "- 横截面均值回归的收益常集中在少数反弹日和市场宽度恢复环境；因此必须区分“收益来源归因”和“可交易加仓规则”。",
        "- 本阶段只做现金账户探针：gross70可以在好状态补仓，gross100不允许超过满仓。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
        f"- risk-on收益最高：`{best_return['scenario']}`，总收益`{pct(best_return['total_return_min_fee'])}`，最大回撤`{pct(best_return['max_drawdown_min_fee'])}`，Sharpe `{best_return['sharpe_min_fee']:.3f}`。",
        best_dd_ok_line,
        "- 重要提醒：含策略自身状态的risk-on规则使用基准路径状态，是收益来源探针，不是可直接上线的路径依赖版本。",
        "",
        "## 跨场景正收益来源",
        "",
        markdown_table(
            cross_good,
            [
                "regime_feature",
                "bucket",
                "scenario_count",
                "positive_scenario_count",
                "days",
                "compound_return_sum",
                "simple_return_sum",
                "avg_daily_ret",
                "avg_loss_day_ratio",
                "avg_actual_gross_weight",
            ],
            max_rows=80,
        ),
        "",
        "## 交互正收益来源",
        "",
        markdown_table(
            interaction_good,
            [
                "interaction_feature",
                "bucket",
                "scenario_count",
                "positive_scenario_count",
                "days",
                "compound_return_sum",
                "simple_return_sum",
                "avg_daily_ret",
                "avg_loss_day_ratio",
                "avg_actual_gross_weight",
            ],
            max_rows=80,
        ),
        "",
        "## 收益日集中度",
        "",
        markdown_table(
            tail_summary,
            [
                "scenario",
                "days",
                "simple_return_sum",
                "positive_return_sum",
                "negative_return_sum",
                "top10pct_day_return_sum",
                "bottom10pct_day_return_sum",
                "top10pct_share_of_positive_sum",
                "bottom10pct_share_of_negative_sum",
                "sharpe_min_fee",
            ],
            max_rows=40,
        ),
        "",
        "## 行业目标贡献近似",
        "",
        markdown_table(
            industry_source.sort(["scenario", "raw_contribution_sum"], descending=[False, True]),
            [
                "scenario",
                "industry",
                "target_rows",
                "target_days",
                "symbols",
                "raw_contribution_sum",
                "avg_open_to_next_open_ret",
                "positive_row_ratio",
                "avg_model_score",
            ],
            max_rows=80,
        ),
        "",
        "## 选中股票分数桶贡献近似",
        "",
        markdown_table(
            score_source,
            [
                "scenario",
                "selected_score_bucket",
                "target_rows",
                "target_days",
                "symbols",
                "raw_contribution_sum",
                "avg_open_to_next_open_ret",
                "positive_row_ratio",
                "avg_model_score",
            ],
            max_rows=80,
        ),
        "",
        "## risk-on探针汇总",
        "",
        markdown_table(
            summary,
            [
                "base_scenario",
                "risk_on_rule_name",
                "final_equity_min_fee",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "avg_actual_gross_weight",
                "avg_effective_scale",
                "risk_on_day_ratio",
                "latest_actual_gross_weight",
                "return_over_max_dd",
            ],
            max_rows=140,
        ),
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
        "",
        "## 结论",
        "",
        "- 收益来源可以研究，但risk-on比risk-off更容易过拟合；本阶段结果只决定是否值得写路径依赖版本。",
        "- 若risk-on不能同时满足高收益和20%以内回撤，则不应为了收益放大继续扫状态。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：风险较高。",
        "- 原因：研究收益来源后再加仓，天然接近收益 timing，需要限制规则数量和现金账户约束。",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：依据质量检查，不把探针直接升级。",
        "- 原因：含策略状态的规则使用基准路径状态，需要路径依赖重放才能作为候选。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：Stage322说明降风险不足以达成目标，必须知道收益到底从哪里来。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：若risk-on只提高收益同时扩大回撤，则转向信号层；若能改善收益回撤，再做路径依赖重放。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths["report"]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "feature_summary": OUTPUT_DIR / f"{PREFIX}_feature_summary.csv",
        "cross_good": OUTPUT_DIR / f"{PREFIX}_cross_good_regimes.csv",
        "interaction_good": OUTPUT_DIR / f"{PREFIX}_interaction_good_regimes.csv",
        "tail_summary": OUTPUT_DIR / f"{PREFIX}_tail_summary.csv",
        "industry_source": OUTPUT_DIR / f"{PREFIX}_industry_source.csv",
        "score_source": OUTPUT_DIR / f"{PREFIX}_score_source.csv",
        "scale_daily": OUTPUT_DIR / f"{PREFIX}_scale_daily.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }

    target_weights = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_target_weights.csv").filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    base_daily = pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_daily.csv", try_parse_dates=True).filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    base_summary = pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_summary.csv", try_parse_dates=True).filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    market_state = build_market_state(stock_df, benchmark_df)
    strategy_state = build_strategy_state(base_daily)
    enriched = enrich_daily(base_daily, market_state, strategy_state)
    state_map = build_state_map(enriched)
    feature_summary = build_regime_feature_summary(enriched)
    cross_good = build_cross_good_regimes(feature_summary)
    interaction_summary = build_interaction_summary(enriched)
    interaction_good = build_cross_good_interactions(interaction_summary)
    tail_summary = build_return_tail_summary(enriched)
    industry_source, score_source = build_target_source_summary(target_weights, stock_df)

    summary_rows: list[dict[str, Any]] = []
    orders_frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    scale_frames: list[pl.DataFrame] = []

    for row in base_summary.iter_rows(named=True):
        base_scenario = str(row["scenario"])
        base_row = dict(row)
        base_row["base_scenario"] = base_scenario
        base_row["risk_on_rule_name"] = "base_rerun"
        base_row["risk_on_rule_description"] = "不加仓基准。"
        base_row["avg_effective_scale"] = 1.0
        base_row["risk_on_day_ratio"] = 0.0
        base_row["uses_base_strategy_state"] = False
        summary_rows.append(normalize_summary_row(base_row))

    for base_scenario in FOCUS_SCENARIOS:
        scenario_targets = target_weights.filter(pl.col("scenario") == base_scenario).drop("scenario")
        dates = lot.build_tracking_dates(scenario_targets, benchmark_df)
        for rule in RISK_ON_RULES:
            scaled_targets, scale_daily = scale_targets_for_rule(scenario_targets, base_scenario, rule, state_map)
            target_maps = lot.build_target_maps(scaled_targets)
            orders, daily, _curves = lot.replay_lot_account(target_maps, dates, exec_info)
            scenario_name = f"{base_scenario}_{rule.name}"
            orders = orders.with_columns(
                pl.lit(scenario_name).alias("scenario"),
                pl.lit(base_scenario).alias("base_scenario"),
                pl.lit(rule.name).alias("risk_on_rule_name"),
            )
            daily = daily.with_columns(
                pl.lit(scenario_name).alias("scenario"),
                pl.lit(base_scenario).alias("base_scenario"),
                pl.lit(rule.name).alias("risk_on_rule_name"),
            ).join(
                scale_daily.select(
                    [
                        pl.col("target_date").alias("date"),
                        "risk_on_condition_on",
                        "risk_on_desired_scale",
                        "risk_on_effective_scale",
                        "base_target_gross_weight",
                        "scaled_target_gross_weight",
                        "prev_breadth_ret20_state",
                        "prev_strategy_ret60_state",
                    ]
                ),
                on="date",
                how="left",
            )
            summary = lot.summarize_orders(orders, daily)
            summary = summarize_daily_extra(summary, daily)
            summary.update(
                {
                    "scenario": scenario_name,
                    "base_scenario": base_scenario,
                    "risk_on_rule_name": rule.name,
                    "risk_on_rule_description": rule.description,
                    "uses_base_strategy_state": rule.uses_base_strategy_state,
                    "avg_effective_scale": to_float(scale_daily["risk_on_effective_scale"].mean()),
                    "max_effective_scale": to_float(scale_daily["risk_on_effective_scale"].max()),
                    "risk_on_days": scale_daily.filter(pl.col("risk_on_condition_on")).height,
                    "risk_on_day_ratio": scale_daily.filter(pl.col("risk_on_condition_on")).height / scale_daily.height,
                    "avg_scaled_target_gross_weight": to_float(scale_daily["scaled_target_gross_weight"].mean()),
                    "max_scaled_target_gross_weight": to_float(scale_daily["scaled_target_gross_weight"].max()),
                }
            )
            summary_rows.append(normalize_summary_row(summary))
            orders_frames.append(orders)
            daily_frames.append(daily)
            scale_frames.append(scale_daily)

    summary = add_base_deltas(pl.DataFrame(summary_rows, infer_schema_length=None)).sort(
        ["base_scenario", "risk_on_rule_name"]
    )
    orders_all = pl.concat(orders_frames, how="diagonal_relaxed") if orders_frames else pl.DataFrame()
    daily_all = pl.concat(daily_frames, how="diagonal_relaxed") if daily_frames else pl.DataFrame()
    scale_all = pl.concat(scale_frames, how="diagonal_relaxed") if scale_frames else pl.DataFrame()
    quality = build_quality(summary, cross_good, scale_all)
    report_path = write_report(
        summary,
        feature_summary,
        cross_good,
        interaction_good,
        tail_summary,
        industry_source,
        score_source,
        quality,
        paths,
    )

    summary.write_csv(paths["summary"])
    feature_summary.write_csv(paths["feature_summary"])
    cross_good.write_csv(paths["cross_good"])
    interaction_good.write_csv(paths["interaction_good"])
    tail_summary.write_csv(paths["tail_summary"])
    industry_source.write_csv(paths["industry_source"])
    score_source.write_csv(paths["score_source"])
    scale_all.write_csv(paths["scale_daily"])
    daily_all.write_csv(paths["daily"])
    orders_all.write_csv(paths["orders"])
    quality.write_csv(paths["quality"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "focus_scenarios": FOCUS_SCENARIOS,
            "max_cash_gross_weight": MAX_CASH_GROSS_WEIGHT,
            "candidate_base_scenario": CANDIDATE_BASE_SCENARIO,
            "risk_on_rules": [
                {
                    "name": item.name,
                    "description": item.description,
                    "max_scale": item.max_scale,
                    "condition": item.condition,
                    "uses_base_strategy_state": item.uses_base_strategy_state,
                }
                for item in RISK_ON_RULES
            ],
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
        },
    )
    print(f"report={report_path}")
    print(quality)
    print(
        summary.select(
            [
                "base_scenario",
                "risk_on_rule_name",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "avg_effective_scale",
                "risk_on_day_ratio",
            ]
        )
    )


if __name__ == "__main__":
    main()
