from __future__ import annotations

import json
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution import (
    build_drawdown_episodes,
    build_full_position_daily,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution_v1"

FOCUS_SCENARIOS: tuple[str, ...] = (
    "industry_resid_core_h10_top8_gross100_ind2",
    "industry_resid_core_h10_top5_gross100_ind1",
    "industry_resid_core_h10_top8_gross70_ind2",
    "industry_resid_core_h10_top5_gross70_ind1",
)
PRIMARY_SCENARIO: str = "industry_resid_core_h10_top8_gross70_ind2"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term residual reversal",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
    (
        "Short-term reversals, returns to liquidity provision and the costs of immediacy",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "Understanding momentum and reversal",
        "https://www.sciencedirect.com/science/article/pii/S0304405X21000878",
    ),
    (
        "Teddy Koker cross-sectional mean reversion backtest",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)

NUMERIC_FEATURES: tuple[str, ...] = (
    "actual_weight",
    "target_model_score",
    "target_technical_context_score",
    "target_technical_pullback_quality",
    "target_technical_damage_penalty",
    "target_adv20_turnover",
    "target_turnover_rate_f",
    "target_circ_mv",
    "target_candidate_count",
    "target_selected_industry_count",
    "stock_ret_5",
    "stock_ret_10",
    "stock_ret_20",
    "stock_ret_60",
    "stock_dist_ma20",
    "stock_dist_ma60",
    "stock_dist_ma120",
    "stock_close_to_high_252",
    "stock_volume_ratio_20",
    "stock_ibs",
    "stock_open_gap",
    "stock_intraday_ret",
    "stock_listing_days",
)

MANUAL_BUCKET_FEATURES: tuple[str, ...] = (
    "target_technical_damage_penalty_manual",
    "stock_ret_20_manual",
    "stock_close_to_high_252_manual",
    "stock_volume_ratio_20_manual",
    "stock_dist_ma60_manual",
    "target_adv20_turnover_manual",
    "actual_weight_manual",
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def read_csv_with_symbol(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def annualized_vol(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    return sqrt(max(variance, 0.0)) * sqrt(TRADING_DAYS)


def build_stock_features(stock_df: pl.DataFrame) -> pl.DataFrame:
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
                "code_name",
                "is_st",
                "listing_days",
                "trade_open",
                "trade_high",
                "trade_low",
                "trade_close",
                "preclose",
                "volume",
                "turnover",
                "adv20_turnover",
                "turnover_rate",
                "is_suspended",
                "is_oneword_limit_up",
                "is_oneword_limit_down",
                "is_limit_up_close",
                "is_limit_down_close",
            ]
        )
        .sort(["symbol", "datetime"])
        .with_columns(
            (close / close.shift(1).over("symbol") - 1.0).alias("stock_ret_1"),
            (close / close.shift(5).over("symbol") - 1.0).alias("stock_ret_5"),
            (close / close.shift(10).over("symbol") - 1.0).alias("stock_ret_10"),
            (close / close.shift(20).over("symbol") - 1.0).alias("stock_ret_20"),
            (close / close.shift(60).over("symbol") - 1.0).alias("stock_ret_60"),
            (close / close.shift(120).over("symbol") - 1.0).alias("stock_ret_120"),
            (close / close.rolling_mean(20).over("symbol") - 1.0).alias("stock_dist_ma20"),
            (close / close.rolling_mean(60).over("symbol") - 1.0).alias("stock_dist_ma60"),
            (close / close.rolling_mean(120).over("symbol") - 1.0).alias("stock_dist_ma120"),
            (close / close.rolling_max(252).over("symbol")).alias("stock_close_to_high_252"),
            (volume / volume.rolling_mean(20).over("symbol")).alias("stock_volume_ratio_20"),
            pl.when((high - low).abs() > 1e-12)
            .then((close - low) / (high - low))
            .otherwise(None)
            .alias("stock_ibs"),
            pl.when((pl.col("preclose") > 0) & open_.is_not_null())
            .then(open_ / pl.col("preclose") - 1.0)
            .otherwise(None)
            .alias("stock_open_gap"),
            pl.when((open_ > 0) & close.is_not_null())
            .then(close / open_ - 1.0)
            .otherwise(None)
            .alias("stock_intraday_ret"),
        )
        .rename(
            {
                "datetime": "date",
                "code_name": "stock_code_name",
                "adv20_turnover": "stock_adv20_turnover",
                "turnover_rate": "stock_turnover_rate",
            }
        )
    )


def build_target_features(target_weights: pl.DataFrame) -> pl.DataFrame:
    keep = [
        "scenario",
        "target_date",
        "symbol",
        "active_lots",
        "source_signal_days",
        "min_holding_day",
        "max_holding_day",
        "model_score",
        "technical_context_score",
        "technical_pullback_quality",
        "technical_damage_penalty",
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
    existing = [col for col in keep if col in target_weights.columns]
    renamed: list[pl.Expr] = []
    for col in existing:
        if col in {"scenario", "target_date", "symbol"}:
            renamed.append(pl.col(col))
        else:
            renamed.append(pl.col(col).alias(f"target_{col}"))
    return target_weights.select(renamed).rename({"target_date": "date"})


def build_drawdown_windows(daily_all: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for scenario in FOCUS_SCENARIOS:
        daily = daily_all.filter(pl.col("scenario") == scenario).sort("date")
        if daily.is_empty():
            continue
        drawdown = build_drawdown_episodes(daily)
        if drawdown.is_empty():
            continue
        worst = drawdown.row(0, named=True)
        rows.append(
            {
                "scenario": scenario,
                "peak_date": worst["peak_date"],
                "start_date": worst["start_date"],
                "trough_date": worst["trough_date"],
                "recovery_date": worst["recovery_date"],
                "max_drawdown": worst["max_drawdown"],
                "trading_days_to_trough": worst["trading_days_to_trough"],
                "trading_days_to_recovery_or_end": worst["trading_days_to_recovery_or_end"],
            }
        )
    return pl.DataFrame(rows).sort("scenario") if rows else pl.DataFrame()


def build_position_panel(
    daily_all: pl.DataFrame,
    orders_all: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for scenario in FOCUS_SCENARIOS:
        daily = daily_all.filter(pl.col("scenario") == scenario).sort("date")
        orders = orders_all.filter(pl.col("scenario") == scenario).sort(["date", "symbol", "side"])
        if daily.is_empty():
            continue
        positions = build_full_position_daily(daily, orders, exec_info)
        if positions.is_empty():
            continue
        frames.append(positions.with_columns(pl.lit(scenario).alias("scenario")))
    return pl.concat(frames, how="vertical") if frames else pl.DataFrame()


def add_manual_buckets(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.col("target_technical_damage_penalty").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("target_technical_damage_penalty") <= 0)
        .then(pl.lit("damage_none"))
        .when(pl.col("target_technical_damage_penalty") <= 0.25)
        .then(pl.lit("damage_low"))
        .otherwise(pl.lit("damage_high"))
        .alias("target_technical_damage_penalty_manual"),
        pl.when(pl.col("stock_ret_20").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("stock_ret_20") <= -0.20)
        .then(pl.lit("ret20_crash_le_-20pct"))
        .when(pl.col("stock_ret_20") <= -0.10)
        .then(pl.lit("ret20_deep_down"))
        .when(pl.col("stock_ret_20") <= 0)
        .then(pl.lit("ret20_mild_down"))
        .otherwise(pl.lit("ret20_up"))
        .alias("stock_ret_20_manual"),
        pl.when(pl.col("stock_close_to_high_252").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("stock_close_to_high_252") >= 0.90)
        .then(pl.lit("near_252_high"))
        .when(pl.col("stock_close_to_high_252") >= 0.70)
        .then(pl.lit("mid_252_high"))
        .otherwise(pl.lit("far_from_252_high"))
        .alias("stock_close_to_high_252_manual"),
        pl.when(pl.col("stock_volume_ratio_20").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("stock_volume_ratio_20") < 0.70)
        .then(pl.lit("volume_dry"))
        .when(pl.col("stock_volume_ratio_20") <= 1.30)
        .then(pl.lit("volume_normal"))
        .otherwise(pl.lit("volume_high"))
        .alias("stock_volume_ratio_20_manual"),
        pl.when(pl.col("stock_dist_ma60").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("stock_dist_ma60") >= 0.05)
        .then(pl.lit("above_ma60"))
        .when(pl.col("stock_dist_ma60") >= -0.05)
        .then(pl.lit("near_ma60"))
        .otherwise(pl.lit("below_ma60"))
        .alias("stock_dist_ma60_manual"),
        pl.when(pl.col("target_adv20_turnover").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("target_adv20_turnover") < 100_000_000)
        .then(pl.lit("adv_lt_100m"))
        .when(pl.col("target_adv20_turnover") < 300_000_000)
        .then(pl.lit("adv_100m_300m"))
        .otherwise(pl.lit("adv_ge_300m"))
        .alias("target_adv20_turnover_manual"),
        pl.when(pl.col("actual_weight") < 0.01)
        .then(pl.lit("weight_lt_1pct"))
        .when(pl.col("actual_weight") < 0.02)
        .then(pl.lit("weight_1_2pct"))
        .otherwise(pl.lit("weight_ge_2pct"))
        .alias("actual_weight_manual"),
    )


def add_quantile_buckets(frame: pl.DataFrame, features: tuple[str, ...]) -> pl.DataFrame:
    result = frame
    exprs: list[pl.Expr] = []
    for feature in features:
        if feature not in result.columns:
            continue
        non_null = result.filter(pl.col(feature).is_not_null())
        if non_null.height < 30:
            continue
        low = to_float(non_null[feature].quantile(0.33))
        high = to_float(non_null[feature].quantile(0.66))
        if abs(high - low) <= 1e-12:
            continue
        exprs.append(
            pl.when(pl.col(feature).is_null())
            .then(pl.lit("missing"))
            .when(pl.col(feature) <= low)
            .then(pl.lit(f"{feature}_low"))
            .when(pl.col(feature) >= high)
            .then(pl.lit(f"{feature}_high"))
            .otherwise(pl.lit(f"{feature}_mid"))
            .alias(f"{feature}_qbucket")
        )
    return result.with_columns(exprs) if exprs else result


def contribution_summary(frame: pl.DataFrame, group_cols: list[str]) -> pl.DataFrame:
    if frame.is_empty():
        return pl.DataFrame()
    return (
        frame.group_by(group_cols)
        .agg(
            pl.len().alias("position_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("gross_contribution").sum().alias("gross_contribution_sum"),
            pl.when(pl.col("gross_contribution") < 0)
            .then(pl.col("gross_contribution"))
            .otherwise(0.0)
            .sum()
            .alias("negative_contribution_sum"),
            pl.when(pl.col("gross_contribution") > 0)
            .then(pl.col("gross_contribution"))
            .otherwise(0.0)
            .sum()
            .alias("positive_contribution_sum"),
            pl.col("gross_contribution").mean().alias("avg_contribution"),
            pl.col("daily_ret").mean().alias("avg_daily_ret"),
            (pl.col("gross_contribution") < 0).mean().alias("loss_day_ratio"),
            pl.col("actual_weight").mean().alias("avg_actual_weight"),
            pl.col("actual_weight").max().alias("max_actual_weight"),
        )
        .sort("gross_contribution_sum")
    )


def build_feature_bucket_summary(frame: pl.DataFrame) -> pl.DataFrame:
    bucket_cols = [col for col in frame.columns if col.endswith("_qbucket")] + [
        col for col in MANUAL_BUCKET_FEATURES if col in frame.columns
    ]
    parts: list[pl.DataFrame] = []
    for bucket_col in bucket_cols:
        scenario_summary = contribution_summary(frame, ["scenario", bucket_col])
        if not scenario_summary.is_empty():
            parts.append(
                scenario_summary.rename({bucket_col: "bucket"}).with_columns(pl.lit(bucket_col).alias("feature"))
            )
        all_summary = contribution_summary(frame, [bucket_col])
        if not all_summary.is_empty():
            parts.append(
                all_summary.rename({bucket_col: "bucket"}).with_columns(
                    pl.lit("ALL").alias("scenario"),
                    pl.lit(bucket_col).alias("feature"),
                )
            )
    if not parts:
        return pl.DataFrame()
    return pl.concat(parts, how="diagonal_relaxed").select(
        [
            "scenario",
            "feature",
            "bucket",
            "position_days",
            "symbols",
            "gross_contribution_sum",
            "negative_contribution_sum",
            "positive_contribution_sum",
            "avg_contribution",
            "avg_daily_ret",
            "loss_day_ratio",
            "avg_actual_weight",
            "max_actual_weight",
        ]
    ).sort(["scenario", "gross_contribution_sum"])


def build_consistent_bad_buckets(feature_summary: pl.DataFrame) -> pl.DataFrame:
    if feature_summary.is_empty():
        return pl.DataFrame()
    scenario_rows = feature_summary.filter(pl.col("scenario") != "ALL")
    if scenario_rows.is_empty():
        return pl.DataFrame()
    return (
        scenario_rows.group_by(["feature", "bucket"])
        .agg(
            pl.col("scenario").n_unique().alias("scenario_count"),
            (pl.col("gross_contribution_sum") < 0).sum().alias("negative_scenario_count"),
            pl.col("position_days").sum().alias("position_days"),
            pl.col("symbols").sum().alias("symbol_count_sum"),
            pl.col("gross_contribution_sum").sum().alias("gross_contribution_sum"),
            pl.col("negative_contribution_sum").sum().alias("negative_contribution_sum"),
            pl.col("positive_contribution_sum").sum().alias("positive_contribution_sum"),
            pl.col("avg_contribution").mean().alias("avg_bucket_contribution"),
            pl.col("loss_day_ratio").mean().alias("avg_loss_day_ratio"),
        )
        .filter((pl.col("scenario_count") >= 3) & (pl.col("negative_scenario_count") >= 3))
        .sort("gross_contribution_sum")
    )


def build_missing_summary(frame: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for col in NUMERIC_FEATURES:
        if col not in frame.columns:
            continue
        rows.append(
            {
                "feature": col,
                "rows": frame.height,
                "missing": frame.select(pl.col(col).null_count()).item(),
                "missing_ratio": frame.select(pl.col(col).null_count()).item() / frame.height if frame.height else 0.0,
            }
        )
    return pl.DataFrame(rows).sort("missing_ratio", descending=True) if rows else pl.DataFrame()


def build_quality(
    drawdown_windows: pl.DataFrame,
    drawdown_positions: pl.DataFrame,
    enriched_positions: pl.DataFrame,
    feature_summary: pl.DataFrame,
) -> pl.DataFrame:
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
        "drawdown_window_count",
        "pass" if drawdown_windows.height == len(FOCUS_SCENARIOS) else "fail",
        drawdown_windows.height,
        len(FOCUS_SCENARIOS),
        "必须识别四个代表场景的最大回撤窗口。",
    )
    add(
        "drawdown_position_days_available",
        "pass" if drawdown_positions.height > 0 else "fail",
        drawdown_positions.height,
        ">0",
        "亏损样本归因必须有真实持仓日。",
    )
    target_missing = (
        enriched_positions.filter(pl.col("target_model_score").is_null()).height if "target_model_score" in enriched_positions.columns else enriched_positions.height
    )
    add(
        "target_feature_join_coverage",
        "pass" if enriched_positions.height and target_missing / enriched_positions.height <= 0.05 else "warn",
        f"{target_missing / enriched_positions.height:.2%}" if enriched_positions.height else "NA",
        "<=5% missing",
        "目标权重中的信号特征应覆盖大部分真实持仓日。",
    )
    add(
        "feature_bucket_summary_available",
        "pass" if feature_summary.height > 0 else "fail",
        feature_summary.height,
        ">0",
        "必须生成特征分桶归因。",
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
    drawdown_windows: pl.DataFrame,
    window_summary: pl.DataFrame,
    industry_summary: pl.DataFrame,
    symbol_summary: pl.DataFrame,
    feature_summary: pl.DataFrame,
    consistent_bad_buckets: pl.DataFrame,
    missing_summary: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    primary_feature = feature_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO).head(40)
    lines = [
        "# 股票震荡industry_resid_core 30万长回撤亏损样本归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：第308阶段代表场景最大回撤窗口内的真实持仓日亏损样本归因；不新增交易规则、不调参数。",
        f"- 主观察场景：`{PRIMARY_SCENARIO}`。",
        "- A/B判断：纯归因，不接入第78，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 残差短期反转有文献支持，但收益会受到动态风险暴露、流动性成本和趋势延续环境影响。",
        "- 公开均值回归示例可参考研究流程，但不足以解释本仓库30万整手账户里的长回撤。",
        "- 因此本阶段先找亏损样本的稳定指纹，再决定是否值得进入信号层剔除测试。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心摘要",
            "",
            "- 本阶段不是新策略回测；所有数值都是最大回撤窗口内真实持仓日的毛贡献归因。",
            "- 重点看两个问题：坏贡献是否集中在少数行业/个股；坏贡献是否对应稳定的技术/流动性特征。",
            f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
            "",
            "## 最大回撤窗口",
            "",
            markdown_table(
                drawdown_windows,
                [
                    "scenario",
                    "peak_date",
                    "start_date",
                    "trough_date",
                    "recovery_date",
                    "max_drawdown",
                    "trading_days_to_trough",
                    "trading_days_to_recovery_or_end",
                ],
                max_rows=20,
            ),
            "",
            "## 回撤窗口持仓贡献摘要",
            "",
            markdown_table(
                window_summary,
                [
                    "scenario",
                    "position_days",
                    "symbols",
                    "gross_contribution_sum",
                    "negative_contribution_sum",
                    "positive_contribution_sum",
                    "avg_contribution",
                    "avg_daily_ret",
                    "loss_day_ratio",
                    "avg_actual_weight",
                    "max_actual_weight",
                ],
                max_rows=20,
            ),
            "",
            "## 行业亏损贡献Top",
            "",
            markdown_table(
                industry_summary,
                [
                    "scenario",
                    "industry",
                    "position_days",
                    "symbols",
                    "gross_contribution_sum",
                    "negative_contribution_sum",
                    "positive_contribution_sum",
                    "avg_contribution",
                    "loss_day_ratio",
                    "avg_actual_weight",
                    "max_actual_weight",
                ],
                max_rows=80,
            ),
            "",
            "## 个股亏损贡献Top",
            "",
            markdown_table(
                symbol_summary,
                [
                    "scenario",
                    "symbol",
                    "code_name",
                    "industry",
                    "position_days",
                    "gross_contribution_sum",
                    "negative_contribution_sum",
                    "positive_contribution_sum",
                    "avg_contribution",
                    "loss_day_ratio",
                    "avg_actual_weight",
                    "max_actual_weight",
                ],
                max_rows=100,
            ),
            "",
            "## 主观察场景特征分桶",
            "",
            markdown_table(
                primary_feature,
                [
                    "feature",
                    "bucket",
                    "position_days",
                    "symbols",
                    "gross_contribution_sum",
                    "negative_contribution_sum",
                    "positive_contribution_sum",
                    "avg_contribution",
                    "avg_daily_ret",
                    "loss_day_ratio",
                    "avg_actual_weight",
                ],
                max_rows=80,
            ),
            "",
            "## 跨场景稳定坏桶",
            "",
            markdown_table(
                consistent_bad_buckets,
                [
                    "feature",
                    "bucket",
                    "scenario_count",
                    "negative_scenario_count",
                    "position_days",
                    "gross_contribution_sum",
                    "negative_contribution_sum",
                    "positive_contribution_sum",
                    "avg_bucket_contribution",
                    "avg_loss_day_ratio",
                ],
                max_rows=80,
            ),
            "",
            "## 特征缺失率",
            "",
            markdown_table(missing_summary, ["feature", "rows", "missing", "missing_ratio"], max_rows=80),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只分析已经发生的最大回撤窗口，不测试任何剔除阈值或交易规则。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：后续若直接按本报告最差桶写规则，会有过拟合风险。",
            "- 原因：亏损指纹只能提出假设，下一步必须用极少数第一性原理规则做反证，不能按桶逐个修曲线。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：弱广度和行业上限两个风险层都不足以修复，需要回到亏损样本本身找稳定坏形态。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：取决于坏桶是否跨场景稳定。",
            "- 原因：只有跨场景、可解释、事前可识别的坏特征，才值得进入下一阶段剔除测试。",
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
    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "drawdown_windows": OUTPUT_DIR / f"{PREFIX}_drawdown_windows.csv",
        "window_positions": OUTPUT_DIR / f"{PREFIX}_window_positions.csv",
        "window_summary": OUTPUT_DIR / f"{PREFIX}_window_summary.csv",
        "industry_summary": OUTPUT_DIR / f"{PREFIX}_industry_summary.csv",
        "symbol_summary": OUTPUT_DIR / f"{PREFIX}_symbol_summary.csv",
        "feature_bucket_summary": OUTPUT_DIR / f"{PREFIX}_feature_bucket_summary.csv",
        "consistent_bad_buckets": OUTPUT_DIR / f"{PREFIX}_consistent_bad_buckets.csv",
        "missing_summary": OUTPUT_DIR / f"{PREFIX}_missing_summary.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    daily_all = pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_daily.csv", try_parse_dates=True).sort(["scenario", "date"])
    orders_all = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_orders.csv").sort(["scenario", "date", "symbol"])
    target_weights = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_target_weights.csv").filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    stock_df, _benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    position_panel = build_position_panel(daily_all, orders_all, exec_info)
    drawdown_windows = build_drawdown_windows(daily_all)
    window_parts: list[pl.DataFrame] = []
    for row in drawdown_windows.iter_rows(named=True):
        scenario = str(row["scenario"])
        peak_date = row["peak_date"]
        trough_date = row["trough_date"]
        window_parts.append(
            position_panel.filter(
                (pl.col("scenario") == scenario) & (pl.col("date") >= peak_date) & (pl.col("date") <= trough_date)
            )
        )
    window_positions = pl.concat(window_parts, how="vertical") if window_parts else pl.DataFrame()

    target_features = build_target_features(target_weights)
    stock_features = build_stock_features(stock_df)
    enriched = (
        window_positions.join(target_features, on=["scenario", "date", "symbol"], how="left")
        .join(stock_features, on=["date", "symbol"], how="left")
        .with_columns(
            pl.when(pl.col("gross_contribution") < 0)
            .then(pl.lit("loss"))
            .when(pl.col("gross_contribution") > 0)
            .then(pl.lit("gain"))
            .otherwise(pl.lit("flat"))
            .alias("contribution_direction")
        )
    )
    enriched = add_quantile_buckets(add_manual_buckets(enriched), NUMERIC_FEATURES)

    window_summary = contribution_summary(enriched, ["scenario"])
    industry_summary = contribution_summary(enriched, ["scenario", "industry"]).group_by("scenario").head(20)
    symbol_summary = contribution_summary(enriched, ["scenario", "symbol", "code_name", "industry"]).group_by(
        "scenario"
    ).head(30)
    feature_summary = build_feature_bucket_summary(enriched)
    consistent_bad_buckets = build_consistent_bad_buckets(feature_summary)
    missing_summary = build_missing_summary(enriched)
    quality = build_quality(drawdown_windows, window_positions, enriched, feature_summary)

    drawdown_windows.write_csv(paths["drawdown_windows"])
    enriched.write_csv(paths["window_positions"])
    window_summary.write_csv(paths["window_summary"])
    industry_summary.write_csv(paths["industry_summary"])
    symbol_summary.write_csv(paths["symbol_summary"])
    feature_summary.write_csv(paths["feature_bucket_summary"])
    consistent_bad_buckets.write_csv(paths["consistent_bad_buckets"])
    missing_summary.write_csv(paths["missing_summary"])
    quality.write_csv(paths["quality"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "focus_scenarios": FOCUS_SCENARIOS,
            "primary_scenario": PRIMARY_SCENARIO,
            "research_sources": RESEARCH_SOURCES,
            "note": "Loss sample attribution only; no trading rule changes.",
        },
    )
    report_path = write_report(
        drawdown_windows,
        window_summary,
        industry_summary,
        symbol_summary,
        feature_summary,
        consistent_bad_buckets,
        missing_summary,
        quality,
        paths,
    )
    print(f"report={report_path}")
    print(window_summary)
    print(consistent_bad_buckets.head(30))
    print(quality)


if __name__ == "__main__":
    main()
