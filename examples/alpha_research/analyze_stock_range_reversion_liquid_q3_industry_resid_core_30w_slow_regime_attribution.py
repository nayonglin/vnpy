from __future__ import annotations

import json
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution import build_drawdown_episodes
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution import (
    FOCUS_SCENARIOS,
    PRIMARY_SCENARIO,
    read_csv_with_symbol,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_regime_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_regime_attribution_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Volatility Managed Portfolios",
        "https://conference.nber.org/confer/2016/LTAMs16/Moreira_Muir.pdf",
    ),
    (
        "Smoothing volatility targeting",
        "https://arxiv.org/abs/2212.07288",
    ),
    (
        "Statistical Proxy based Mean-Reverting Portfolios with Sparsity and Volatility Constraints",
        "https://arxiv.org/abs/2305.00203",
    ),
    (
        "Backtesting a Cross-Sectional Mean Reversion Strategy in Python",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)

REGIME_COLUMNS: tuple[str, ...] = (
    "prev_index_trend_120_state",
    "prev_index_ret60_state",
    "prev_index_drawdown_120_state",
    "prev_index_vol60_state",
    "prev_breadth_ma60_state",
    "prev_breadth_ma120_state",
    "prev_breadth_ret20_state",
    "prev_strategy_dd120_state",
    "prev_strategy_ret60_state",
    "prev_strategy_vol60_state",
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def annualized_vol(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    return sqrt(max(variance, 0.0)) * sqrt(TRADING_DAYS)


def annualized_sharpe(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    if variance <= 0:
        return 0.0
    return mean / sqrt(variance) * sqrt(TRADING_DAYS)


def max_drawdown_from_returns(values: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in values:
        equity *= 1.0 + value
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)
    return worst


def bucket_index_trend(value: float | None) -> str:
    if value is None or value != value:
        return "missing"
    if value >= 0.03:
        return "above_ma120_plus3"
    if value >= -0.03:
        return "near_ma120"
    return "below_ma120_minus3"


def bucket_ret60(value: float | None) -> str:
    if value is None or value != value:
        return "missing"
    if value >= 0.05:
        return "ret60_up"
    if value >= -0.05:
        return "ret60_flat"
    return "ret60_down"


def bucket_drawdown_120(value: float | None) -> str:
    if value is None or value != value:
        return "missing"
    if value <= -0.20:
        return "dd120_deep"
    if value <= -0.10:
        return "dd120_mid"
    return "dd120_shallow"


def bucket_vol60(value: float | None) -> str:
    if value is None or value != value:
        return "missing"
    if value >= 0.35:
        return "vol60_high"
    if value >= 0.25:
        return "vol60_mid"
    return "vol60_low"


def bucket_breadth(value: float | None, prefix: str) -> str:
    if value is None or value != value:
        return "missing"
    if value >= 0.55:
        return f"{prefix}_healthy"
    if value >= 0.35:
        return f"{prefix}_mixed"
    return f"{prefix}_weak"


def bucket_strategy_dd(value: float | None) -> str:
    if value is None or value != value:
        return "missing"
    if value <= -0.20:
        return "strategy_dd120_deep"
    if value <= -0.10:
        return "strategy_dd120_mid"
    return "strategy_dd120_shallow"


def build_market_state(stock_df: pl.DataFrame, benchmark_df: pl.DataFrame) -> pl.DataFrame:
    close = pl.col("close")
    index_state = (
        benchmark_df.select(["datetime", "close"])
        .sort("datetime")
        .with_columns(
            (close / close.shift(1) - 1.0).alias("index_ret_1"),
            (close / close.shift(20) - 1.0).alias("index_ret_20"),
            (close / close.shift(60) - 1.0).alias("index_ret_60"),
            (close / close.shift(120) - 1.0).alias("index_ret_120"),
            (close / close.rolling_mean(120) - 1.0).alias("index_dist_ma120"),
            (close / close.rolling_max(120) - 1.0).alias("index_drawdown_120"),
        )
        .with_columns((pl.col("index_ret_1").rolling_std(60) * sqrt(TRADING_DAYS)).alias("index_vol_60"))
    )
    stock_close = pl.col("trade_close")
    stock_state = (
        stock_df.select(["datetime", "symbol", "trade_close"])
        .sort(["symbol", "datetime"])
        .with_columns(
            (stock_close / stock_close.rolling_mean(60).over("symbol") - 1.0).alias("stock_dist_ma60"),
            (stock_close / stock_close.rolling_mean(120).over("symbol") - 1.0).alias("stock_dist_ma120"),
            (stock_close / stock_close.shift(20).over("symbol") - 1.0).alias("stock_ret_20"),
        )
        .group_by("datetime")
        .agg(
            (pl.col("stock_dist_ma60") > 0).mean().alias("breadth_above_ma60_ratio"),
            (pl.col("stock_dist_ma120") > 0).mean().alias("breadth_above_ma120_ratio"),
            (pl.col("stock_ret_20") > 0).mean().alias("breadth_ret20_positive_ratio"),
            pl.col("symbol").n_unique().alias("breadth_symbol_count"),
        )
        .sort("datetime")
    )
    state = (
        index_state.join(stock_state, on="datetime", how="left")
        .with_columns(
            pl.col("index_dist_ma120").map_elements(bucket_index_trend, return_dtype=pl.Utf8).alias(
                "index_trend_120_state"
            ),
            pl.col("index_ret_60").map_elements(bucket_ret60, return_dtype=pl.Utf8).alias("index_ret60_state"),
            pl.col("index_drawdown_120").map_elements(bucket_drawdown_120, return_dtype=pl.Utf8).alias(
                "index_drawdown_120_state"
            ),
            pl.col("index_vol_60").map_elements(bucket_vol60, return_dtype=pl.Utf8).alias("index_vol60_state"),
            pl.col("breadth_above_ma60_ratio")
            .map_elements(lambda value: bucket_breadth(value, "ma60"), return_dtype=pl.Utf8)
            .alias("breadth_ma60_state"),
            pl.col("breadth_above_ma120_ratio")
            .map_elements(lambda value: bucket_breadth(value, "ma120"), return_dtype=pl.Utf8)
            .alias("breadth_ma120_state"),
            pl.col("breadth_ret20_positive_ratio")
            .map_elements(lambda value: bucket_breadth(value, "ret20"), return_dtype=pl.Utf8)
            .alias("breadth_ret20_state"),
        )
        .with_columns(
            pl.col("datetime").shift(-1).alias("target_date"),
            pl.col("datetime").alias("state_date"),
        )
        .filter(pl.col("target_date").is_not_null())
    )
    rename_map = {
        col: f"prev_{col}"
        for col in state.columns
        if col not in {"target_date", "state_date"}
    }
    return state.rename(rename_map)


def build_strategy_state(daily: pl.DataFrame) -> pl.DataFrame:
    return (
        daily.sort(["scenario", "date"])
        .with_columns(
            (pl.col("equity_min_fee") / pl.col("equity_min_fee").shift(60).over("scenario") - 1.0).alias(
                "strategy_ret_60"
            ),
            (pl.col("equity_min_fee") / pl.col("equity_min_fee").shift(120).over("scenario") - 1.0).alias(
                "strategy_ret_120"
            ),
            (pl.col("equity_min_fee") / pl.col("equity_min_fee").rolling_max(120).over("scenario") - 1.0).alias(
                "strategy_drawdown_120"
            ),
            (pl.col("strategy_daily_ret_min_fee").rolling_std(60).over("scenario") * sqrt(TRADING_DAYS)).alias(
                "strategy_vol_60"
            ),
        )
        .with_columns(
            pl.col("strategy_drawdown_120")
            .map_elements(bucket_strategy_dd, return_dtype=pl.Utf8)
            .alias("strategy_dd120_state"),
            pl.col("strategy_ret_60").map_elements(bucket_ret60, return_dtype=pl.Utf8).alias("strategy_ret60_state"),
            pl.col("strategy_vol_60").map_elements(bucket_vol60, return_dtype=pl.Utf8).alias("strategy_vol60_state"),
            pl.col("date").shift(-1).over("scenario").alias("target_date"),
            pl.col("date").alias("strategy_state_date"),
        )
        .filter(pl.col("target_date").is_not_null())
        .select(
            [
                "scenario",
                "target_date",
                "strategy_state_date",
                pl.col("strategy_ret_60").alias("prev_strategy_ret_60"),
                pl.col("strategy_ret_120").alias("prev_strategy_ret_120"),
                pl.col("strategy_drawdown_120").alias("prev_strategy_drawdown_120"),
                pl.col("strategy_vol_60").alias("prev_strategy_vol_60"),
                pl.col("strategy_dd120_state").alias("prev_strategy_dd120_state"),
                pl.col("strategy_ret60_state").alias("prev_strategy_ret60_state"),
                pl.col("strategy_vol60_state").alias("prev_strategy_vol60_state"),
            ]
        )
    )


def enrich_daily(daily: pl.DataFrame, market_state: pl.DataFrame, strategy_state: pl.DataFrame) -> pl.DataFrame:
    return (
        daily.filter(pl.col("scenario").is_in(FOCUS_SCENARIOS))
        .join(market_state, left_on="date", right_on="target_date", how="left")
        .join(strategy_state, left_on=["scenario", "date"], right_on=["scenario", "target_date"], how="left")
        .with_columns(
            pl.col("prev_index_trend_120_state").fill_null("missing"),
            pl.col("prev_index_ret60_state").fill_null("missing"),
            pl.col("prev_index_drawdown_120_state").fill_null("missing"),
            pl.col("prev_index_vol60_state").fill_null("missing"),
            pl.col("prev_breadth_ma60_state").fill_null("missing"),
            pl.col("prev_breadth_ma120_state").fill_null("missing"),
            pl.col("prev_breadth_ret20_state").fill_null("missing"),
            pl.col("prev_strategy_dd120_state").fill_null("missing"),
            pl.col("prev_strategy_ret60_state").fill_null("missing"),
            pl.col("prev_strategy_vol60_state").fill_null("missing"),
        )
    )


def regime_summary(frame: pl.DataFrame, group_cols: list[str]) -> pl.DataFrame:
    if frame.is_empty():
        return pl.DataFrame()
    return (
        frame.group_by(group_cols)
        .agg(
            pl.len().alias("days"),
            ((1.0 + pl.col("strategy_daily_ret_min_fee")).product() - 1.0).alias("compound_return"),
            pl.col("strategy_daily_ret_min_fee").sum().alias("simple_return_sum"),
            pl.col("strategy_daily_ret_min_fee").mean().alias("avg_daily_ret"),
            (pl.col("strategy_daily_ret_min_fee") < 0).mean().alias("loss_day_ratio"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            pl.col("zero_lot_target_count").sum().alias("zero_lot_target_count_sum"),
            pl.col("target_symbol_count").sum().alias("target_symbol_count_sum"),
        )
        .with_columns(
            (pl.col("zero_lot_target_count_sum") / pl.col("target_symbol_count_sum")).alias("zero_lot_target_ratio")
        )
        .sort(group_cols)
    )


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
        .sort(["scenario", "compound_return"])
    )


def build_cross_bad_regimes(feature_summary: pl.DataFrame) -> pl.DataFrame:
    scenario_rows = feature_summary.filter(pl.col("scenario") != "ALL")
    if scenario_rows.is_empty():
        return pl.DataFrame()
    return (
        scenario_rows.group_by(["regime_feature", "bucket"])
        .agg(
            pl.col("scenario").n_unique().alias("scenario_count"),
            (pl.col("compound_return") < 0).sum().alias("negative_scenario_count"),
            pl.col("days").sum().alias("days"),
            pl.col("compound_return").sum().alias("compound_return_sum"),
            pl.col("simple_return_sum").sum().alias("simple_return_sum"),
            pl.col("avg_daily_ret").mean().alias("avg_daily_ret"),
            pl.col("loss_day_ratio").mean().alias("avg_loss_day_ratio"),
            pl.col("avg_actual_gross_weight").mean().alias("avg_actual_gross_weight"),
        )
        .filter((pl.col("scenario_count") >= 3) & (pl.col("negative_scenario_count") >= 3))
        .sort("compound_return_sum")
    )


def build_interaction_summary(enriched: pl.DataFrame) -> pl.DataFrame:
    pairs = [
        ("prev_index_drawdown_120_state", "prev_breadth_ma60_state"),
        ("prev_index_trend_120_state", "prev_breadth_ma60_state"),
        ("prev_index_vol60_state", "prev_breadth_ma60_state"),
        ("prev_strategy_dd120_state", "prev_breadth_ma60_state"),
        ("prev_strategy_dd120_state", "prev_index_drawdown_120_state"),
    ]
    parts: list[pl.DataFrame] = []
    for left, right in pairs:
        part = regime_summary(enriched, ["scenario", left, right])
        if part.is_empty():
            continue
        parts.append(
            part.with_columns(
                pl.lit(f"{left}__{right}").alias("interaction_feature"),
                (pl.col(left) + pl.lit("__") + pl.col(right)).alias("bucket"),
            ).select(
                [
                    "scenario",
                    "interaction_feature",
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
        )
    return pl.concat(parts, how="diagonal_relaxed").sort(["scenario", "compound_return"]) if parts else pl.DataFrame()


def build_scenario_summary(daily: pl.DataFrame) -> pl.DataFrame:
    return (
        daily.group_by("scenario")
        .agg(
            pl.len().alias("days"),
            ((1.0 + pl.col("strategy_daily_ret_min_fee")).product() - 1.0).alias("total_return"),
            pl.col("drawdown_min_fee").min().alias("max_drawdown"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
        )
        .with_columns(
            pl.col("scenario")
            .map_elements(
                lambda scenario: annualized_sharpe(
                    daily.filter(pl.col("scenario") == scenario)["strategy_daily_ret_min_fee"].to_list()
                ),
                return_dtype=pl.Float64,
            )
            .alias("sharpe")
        )
        .sort("total_return", descending=True)
    )


def build_quality(enriched: pl.DataFrame, feature_summary: pl.DataFrame, cross_bad: pl.DataFrame) -> pl.DataFrame:
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

    add(
        "focus_scenario_count",
        "pass" if enriched["scenario"].n_unique() == len(FOCUS_SCENARIOS) else "fail",
        enriched["scenario"].n_unique(),
        len(FOCUS_SCENARIOS),
        "必须覆盖四个代表场景。",
    )
    missing_market = enriched.filter(pl.col("prev_index_trend_120_state") == "missing").height / enriched.height
    add(
        "market_state_missing_ratio",
        "pass" if missing_market <= 0.20 else "warn",
        f"{missing_market:.2%}",
        "<=20%",
        "慢变量前置需要历史窗口，早期少量缺失可接受。",
    )
    missing_strategy = enriched.filter(pl.col("prev_strategy_dd120_state") == "missing").height / enriched.height
    add(
        "strategy_state_missing_ratio",
        "pass" if missing_strategy <= 0.20 else "warn",
        f"{missing_strategy:.2%}",
        "<=20%",
        "策略自身120日慢状态早期缺失可接受。",
    )
    add(
        "feature_summary_available",
        "pass" if not feature_summary.is_empty() else "fail",
        feature_summary.height,
        ">0",
        "必须生成慢变量分桶归因。",
    )
    add(
        "cross_bad_regimes_available",
        "pass" if not cross_bad.is_empty() else "warn",
        cross_bad.height,
        ">0",
        "若无跨场景一致坏状态，慢变量风控继续价值较低。",
    )
    add(
        "no_strategy_parameter_change",
        "pass",
        "attribution only",
        "attribution only",
        "本阶段不改变交易规则。",
    )
    return pl.DataFrame(rows)


def write_report(
    scenario_summary: pl.DataFrame,
    feature_summary: pl.DataFrame,
    cross_bad: pl.DataFrame,
    interaction_summary: pl.DataFrame,
    drawdowns: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    primary_features = feature_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO).sort("compound_return")
    primary_interactions = interaction_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO).sort("compound_return")
    display_cols = [
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
    interaction_cols = [
        "scenario",
        "interaction_feature",
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
    lines = [
        "# 股票震荡industry_resid_core 30万组合层慢变量归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：组合层慢变量归因；不新增交易规则、不调参数。",
        "- A/B判断：纯归因，不接入第78，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 波动目标和风险预算常用于让组合风险跨状态更稳定，但它不是免费午餐；估计滞后和交易成本会侵蚀收益。",
        "- 均值回归策略尤其不能用过快的止损/过滤，因为短期痛苦经常也是未来修复来源。",
        "- 因此本阶段只看前一日可见的慢变量是否解释亏损，再决定是否值得做暴露节奏回放。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
        "- 本阶段不是新策略回测；收益/回撤沿用第308阶段代表场景，只做状态归因。",
        "",
        "## 代表场景总览",
        "",
        markdown_table(scenario_summary, scenario_summary.columns, max_rows=40),
        "",
        "## 最大回撤窗口",
        "",
        markdown_table(drawdowns, drawdowns.columns, max_rows=20),
        "",
        "## 主观察场景慢变量亏损Top",
        "",
        markdown_table(primary_features.select([col for col in display_cols if col in primary_features.columns]), [col for col in display_cols if col in primary_features.columns], max_rows=80)
        if not primary_features.is_empty()
        else "无数据",
        "",
        "## 跨场景一致坏慢变量Top",
        "",
        markdown_table(cross_bad, cross_bad.columns, max_rows=100) if not cross_bad.is_empty() else "无数据",
        "",
        "## 主观察场景慢变量交互Top",
        "",
        markdown_table(primary_interactions.select([col for col in interaction_cols if col in primary_interactions.columns]), [col for col in interaction_cols if col in primary_interactions.columns], max_rows=80)
        if not primary_interactions.is_empty()
        else "无数据",
        "",
        "## 质量检查",
        "",
        markdown_table(quality, quality.columns, max_rows=40),
        "",
        "## 结论",
        "",
        "- 若坏状态集中在少数慢变量组合，下一步才允许做低频暴露节奏回放。",
        "- 若坏状态分散或只来自策略自身回撤状态，则不应做市场状态降权，避免把收益弹性砍掉。",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "scenario_summary": OUTPUT_DIR / f"{PREFIX}_scenario_summary.csv",
        "feature_summary": OUTPUT_DIR / f"{PREFIX}_feature_summary.csv",
        "cross_bad": OUTPUT_DIR / f"{PREFIX}_cross_bad_regimes.csv",
        "interaction_summary": OUTPUT_DIR / f"{PREFIX}_interaction_summary.csv",
        "enriched_daily": OUTPUT_DIR / f"{PREFIX}_enriched_daily.csv",
        "drawdowns": OUTPUT_DIR / f"{PREFIX}_drawdowns.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
    }
    stock_df, benchmark_df = load_panels()
    source_daily = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_daily.csv")
    market_state = build_market_state(stock_df, benchmark_df)
    strategy_state = build_strategy_state(source_daily)
    enriched = enrich_daily(source_daily, market_state, strategy_state)
    scenario_summary = build_scenario_summary(enriched)
    feature_summary = build_regime_feature_summary(enriched)
    cross_bad = build_cross_bad_regimes(feature_summary)
    interaction_summary = build_interaction_summary(enriched)
    drawdown_parts: list[pl.DataFrame] = []
    for scenario in FOCUS_SCENARIOS:
        part = build_drawdown_episodes(enriched.filter(pl.col("scenario") == scenario).sort("date")).with_columns(
            pl.lit(scenario).alias("scenario")
        )
        if not part.is_empty():
            drawdown_parts.append(part.head(1))
    drawdowns = pl.concat(drawdown_parts, how="diagonal_relaxed").sort("scenario") if drawdown_parts else pl.DataFrame()
    quality = build_quality(enriched, feature_summary, cross_bad)
    report_path = write_report(
        scenario_summary,
        feature_summary,
        cross_bad,
        interaction_summary,
        drawdowns,
        quality,
        paths,
    )
    scenario_summary.write_csv(paths["scenario_summary"])
    feature_summary.write_csv(paths["feature_summary"])
    cross_bad.write_csv(paths["cross_bad"])
    interaction_summary.write_csv(paths["interaction_summary"])
    enriched.write_csv(paths["enriched_daily"])
    drawdowns.write_csv(paths["drawdowns"])
    quality.write_csv(paths["quality"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "focus_scenarios": FOCUS_SCENARIOS,
            "primary_scenario": PRIMARY_SCENARIO,
            "regime_columns": REGIME_COLUMNS,
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
            "report": str(report_path),
        },
    )
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
