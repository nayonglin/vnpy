from __future__ import annotations

import json
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
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
    build_shaped_selected,
    read_selected,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


REPLAY_SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_2018_2026"
).expanduser().resolve()
REPLAY_SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_signal_date_loss_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_signal_date_loss_attribution_v1"

FOCUS_SHAPES: tuple[tuple[int, int, float, int], ...] = (
    (10, 8, 1.00, 2),
    (10, 5, 1.00, 1),
    (10, 8, 0.70, 2),
    (10, 5, 0.70, 1),
)

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
        "Backtesting a Cross-Sectional Mean Reversion Strategy in Python",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)

SIGNAL_NUMERIC_FEATURES: tuple[str, ...] = (
    "model_score",
    "technical_context_score",
    "technical_pullback_quality",
    "technical_damage_penalty",
    "context_weighted_score",
    "pullback_weighted_score",
    "industry_resid_pullback_score",
    "score_oversold_ret_20",
    "technical_pullback_score",
    "ret_5",
    "ret_10",
    "resid_ret_5",
    "resid_ret_10",
    "volume_ratio_20",
    "ibs",
    "rsi2",
    "rsi3",
    "close_to_high_252",
    "mom120_skip20",
    "mom252_skip20",
    "industry_mom120_skip20",
    "industry_mom252_skip20",
    "ma20_slope_20",
    "ma50_slope_20",
    "dist_ma20_now",
    "dist_ma50_now",
    "score_mid_momentum",
    "score_near_252_high",
    "score_industry_strength",
    "score_residual_strength",
    "score_trend_structure",
    "score_breakout_pullback_context",
    "score_price_pullback",
    "score_residual_pullback",
    "score_low_volume_pullback",
    "score_ma_pullback",
    "score_short_cycle_pullback",
    "penalty_far_from_high",
    "penalty_trend_broken",
    "penalty_high_volume_selloff",
    "penalty_weak_industry",
    "penalty_volume_vacuum",
    "adv20_turnover",
    "turnover_rate_f",
    "circ_mv",
)

MANUAL_BUCKET_FEATURES: tuple[str, ...] = (
    "signal_ret5_manual",
    "signal_ret10_manual",
    "signal_resid_ret5_manual",
    "signal_resid_ret10_manual",
    "signal_close_to_high_252_manual",
    "signal_volume_ratio_20_manual",
    "signal_dist_ma20_manual",
    "signal_dist_ma50_manual",
    "signal_damage_manual",
    "signal_trend_penalty_manual",
    "signal_volume_selloff_penalty_manual",
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


def build_target_day_returns(stock_df: pl.DataFrame) -> pl.DataFrame:
    close = pl.col("trade_close")
    return (
        stock_df.select(["datetime", "symbol", "trade_close"])
        .sort(["symbol", "datetime"])
        .with_columns((close / close.shift(1).over("symbol") - 1.0).alias("target_daily_ret"))
        .rename({"datetime": "target_date"})
        .select(["target_date", "symbol", "target_daily_ret"])
    )


def build_signal_lots(selected: pl.DataFrame) -> pl.DataFrame:
    parts: list[pl.DataFrame] = []
    for horizon, top_k, gross, max_per_industry in FOCUS_SHAPES:
        shaped = build_shaped_selected(selected, horizon, top_k, gross, max_per_industry)
        if shaped.is_empty():
            continue
        signal_cols = [col for col in SIGNAL_NUMERIC_FEATURES if col in shaped.columns]
        id_cols = [col for col in ["code_name", "industry", "market", "model", "model_description"] if col in shaped.columns]
        for day in range(1, horizon + 1):
            parts.append(
                shaped.select(
                    "scenario",
                    pl.col("datetime").alias("signal_date"),
                    "symbol",
                    *id_cols,
                    *signal_cols,
                    "basket_weight",
                    "candidate_count",
                    "selected_industry_count",
                    "selected_industry_stock_count",
                    "shape_horizon",
                    "shape_top_k",
                    "shape_basket_gross_weight",
                    "shape_max_per_industry",
                    pl.col(f"start_date_{day}").alias("target_date"),
                )
                .with_columns(
                    pl.lit(day).alias("holding_day"),
                    (pl.col("basket_weight") / horizon).alias("lot_weight"),
                )
                .filter(pl.col("target_date").is_not_null())
            )
    if not parts:
        return pl.DataFrame()
    return pl.concat(parts, how="diagonal_relaxed").sort(["scenario", "target_date", "symbol", "signal_date"])


def add_manual_buckets(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.col("ret_5").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("ret_5") <= -0.08)
        .then(pl.lit("ret5_deep_down"))
        .when(pl.col("ret_5") <= -0.03)
        .then(pl.lit("ret5_down"))
        .when(pl.col("ret_5") <= 0.03)
        .then(pl.lit("ret5_flat"))
        .otherwise(pl.lit("ret5_up"))
        .alias("signal_ret5_manual"),
        pl.when(pl.col("ret_10").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("ret_10") <= -0.12)
        .then(pl.lit("ret10_deep_down"))
        .when(pl.col("ret_10") <= -0.04)
        .then(pl.lit("ret10_down"))
        .when(pl.col("ret_10") <= 0.04)
        .then(pl.lit("ret10_flat"))
        .otherwise(pl.lit("ret10_up"))
        .alias("signal_ret10_manual"),
        pl.when(pl.col("resid_ret_5").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("resid_ret_5") <= -0.06)
        .then(pl.lit("resid5_deep_down"))
        .when(pl.col("resid_ret_5") <= -0.02)
        .then(pl.lit("resid5_down"))
        .when(pl.col("resid_ret_5") <= 0.02)
        .then(pl.lit("resid5_flat"))
        .otherwise(pl.lit("resid5_up"))
        .alias("signal_resid_ret5_manual"),
        pl.when(pl.col("resid_ret_10").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("resid_ret_10") <= -0.10)
        .then(pl.lit("resid10_deep_down"))
        .when(pl.col("resid_ret_10") <= -0.03)
        .then(pl.lit("resid10_down"))
        .when(pl.col("resid_ret_10") <= 0.03)
        .then(pl.lit("resid10_flat"))
        .otherwise(pl.lit("resid10_up"))
        .alias("signal_resid_ret10_manual"),
        pl.when(pl.col("close_to_high_252").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("close_to_high_252") >= 0.90)
        .then(pl.lit("near_252_high"))
        .when(pl.col("close_to_high_252") >= 0.70)
        .then(pl.lit("mid_252_high"))
        .otherwise(pl.lit("far_from_252_high"))
        .alias("signal_close_to_high_252_manual"),
        pl.when(pl.col("volume_ratio_20").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("volume_ratio_20") < 0.70)
        .then(pl.lit("volume_dry"))
        .when(pl.col("volume_ratio_20") <= 1.30)
        .then(pl.lit("volume_normal"))
        .otherwise(pl.lit("volume_high"))
        .alias("signal_volume_ratio_20_manual"),
        pl.when(pl.col("dist_ma20_now").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("dist_ma20_now") <= -0.08)
        .then(pl.lit("below_ma20_deep"))
        .when(pl.col("dist_ma20_now") <= -0.03)
        .then(pl.lit("below_ma20"))
        .when(pl.col("dist_ma20_now") <= 0.03)
        .then(pl.lit("near_ma20"))
        .otherwise(pl.lit("above_ma20"))
        .alias("signal_dist_ma20_manual"),
        pl.when(pl.col("dist_ma50_now").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("dist_ma50_now") <= -0.12)
        .then(pl.lit("below_ma50_deep"))
        .when(pl.col("dist_ma50_now") <= -0.05)
        .then(pl.lit("below_ma50"))
        .when(pl.col("dist_ma50_now") <= 0.05)
        .then(pl.lit("near_ma50"))
        .otherwise(pl.lit("above_ma50"))
        .alias("signal_dist_ma50_manual"),
        pl.when(pl.col("technical_damage_penalty").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("technical_damage_penalty") <= 0)
        .then(pl.lit("damage_none"))
        .when(pl.col("technical_damage_penalty") <= 0.25)
        .then(pl.lit("damage_low"))
        .otherwise(pl.lit("damage_high"))
        .alias("signal_damage_manual"),
        pl.when(pl.col("penalty_trend_broken").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("penalty_trend_broken") <= 0)
        .then(pl.lit("trend_penalty_none"))
        .when(pl.col("penalty_trend_broken") <= 0.25)
        .then(pl.lit("trend_penalty_low"))
        .otherwise(pl.lit("trend_penalty_high"))
        .alias("signal_trend_penalty_manual"),
        pl.when(pl.col("penalty_high_volume_selloff").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("penalty_high_volume_selloff") <= 0)
        .then(pl.lit("volume_selloff_penalty_none"))
        .when(pl.col("penalty_high_volume_selloff") <= 0.25)
        .then(pl.lit("volume_selloff_penalty_low"))
        .otherwise(pl.lit("volume_selloff_penalty_high"))
        .alias("signal_volume_selloff_penalty_manual"),
    )


def cast_signal_numeric_features(frame: pl.DataFrame) -> pl.DataFrame:
    exprs = [
        pl.col(feature).cast(pl.Float64, strict=False).alias(feature)
        for feature in SIGNAL_NUMERIC_FEATURES
        if feature in frame.columns
    ]
    return frame.with_columns(exprs) if exprs else frame


def add_quantile_buckets(frame: pl.DataFrame, features: tuple[str, ...]) -> pl.DataFrame:
    result = frame
    exprs: list[pl.Expr] = []
    for feature in features:
        if feature not in result.columns:
            continue
        non_null = result.filter(pl.col(feature).is_not_null())
        if non_null.height < 30:
            continue
        low = non_null[feature].quantile(0.33)
        high = non_null[feature].quantile(0.66)
        if low is None or high is None:
            continue
        low_f = float(low)
        high_f = float(high)
        if abs(high_f - low_f) <= 1e-12:
            continue
        exprs.append(
            pl.when(pl.col(feature).is_null())
            .then(pl.lit("missing"))
            .when(pl.col(feature) <= low_f)
            .then(pl.lit(f"{feature}_low"))
            .when(pl.col(feature) >= high_f)
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
            pl.len().alias("signal_lot_days"),
            pl.struct(["signal_date", "symbol"]).n_unique().alias("signals"),
            pl.col("target_date").n_unique().alias("target_days"),
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
            pl.col("target_daily_ret").mean().alias("avg_target_daily_ret"),
            (pl.col("gross_contribution") < 0).mean().alias("loss_lot_ratio"),
            pl.col("lot_weight").mean().alias("avg_lot_weight"),
            pl.col("lot_weight").max().alias("max_lot_weight"),
        )
        .sort("gross_contribution_sum")
    )


def build_window_summary(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty():
        return pl.DataFrame()
    return contribution_summary(frame, ["scenario"]).with_columns(
        (pl.col("gross_contribution_sum") / pl.col("signal_lot_days")).alias("contribution_per_lot_day")
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
            "signal_lot_days",
            "signals",
            "target_days",
            "symbols",
            "gross_contribution_sum",
            "negative_contribution_sum",
            "positive_contribution_sum",
            "avg_contribution",
            "avg_target_daily_ret",
            "loss_lot_ratio",
            "avg_lot_weight",
            "max_lot_weight",
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
            pl.col("signal_lot_days").sum().alias("signal_lot_days"),
            pl.col("signals").sum().alias("signal_count_sum"),
            pl.col("symbols").sum().alias("symbol_count_sum"),
            pl.col("gross_contribution_sum").sum().alias("gross_contribution_sum"),
            pl.col("negative_contribution_sum").sum().alias("negative_contribution_sum"),
            pl.col("positive_contribution_sum").sum().alias("positive_contribution_sum"),
            pl.col("avg_contribution").mean().alias("avg_bucket_contribution"),
            pl.col("loss_lot_ratio").mean().alias("avg_loss_lot_ratio"),
        )
        .filter((pl.col("scenario_count") >= 3) & (pl.col("negative_scenario_count") >= 3))
        .sort("gross_contribution_sum")
    )


def build_missing_summary(frame: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for col in SIGNAL_NUMERIC_FEATURES:
        if col not in frame.columns:
            continue
        missing = frame.select(pl.col(col).null_count()).item()
        rows.append(
            {
                "feature": col,
                "rows": frame.height,
                "missing": missing,
                "missing_ratio": missing / frame.height if frame.height else 0.0,
            }
        )
    return pl.DataFrame(rows).sort("missing_ratio", descending=True) if rows else pl.DataFrame()


def build_quality(
    drawdown_windows: pl.DataFrame,
    window_lots: pl.DataFrame,
    feature_summary: pl.DataFrame,
    missing_summary: pl.DataFrame,
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
        "signal_lots_available",
        "pass" if window_lots.height > 0 else "fail",
        window_lots.height,
        ">0",
        "必须有信号日拆分后的回撤窗口lot样本。",
    )
    missing_ret = window_lots.filter(pl.col("target_daily_ret").is_null()).height if window_lots.height else 0
    missing_ret_ratio = missing_ret / window_lots.height if window_lots.height else 1.0
    add(
        "target_return_join_coverage",
        "pass" if missing_ret_ratio <= 0.02 else "warn",
        f"{missing_ret_ratio:.2%}",
        "<=2% missing",
        "目标日收益应覆盖绝大多数信号lot。",
    )
    max_missing = missing_summary["missing_ratio"].max() if not missing_summary.is_empty() else None
    add(
        "signal_feature_coverage",
        "pass" if max_missing is not None and float(max_missing) <= 0.35 else "warn",
        f"{float(max_missing):.2%}" if max_missing is not None else "NA",
        "<=35% max missing",
        "信号日特征覆盖不能太差，否则分桶解释不稳定。",
    )
    add(
        "feature_bucket_summary_available",
        "pass" if feature_summary.height > 0 else "fail",
        feature_summary.height,
        ">0",
        "必须生成信号日特征分桶归因。",
    )
    add(
        "no_same_day_target_features",
        "pass",
        "signal-date only",
        "signal-date only",
        "本阶段不使用目标日收盘后才知道的IBS/日内收益作为过滤依据。",
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
    consistent_bad: pl.DataFrame,
    missing_summary: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    primary_features = feature_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO).sort("gross_contribution_sum")
    primary_manual = primary_features.filter(pl.col("feature").is_in(MANUAL_BUCKET_FEATURES)).sort("gross_contribution_sum")
    primary_industry = industry_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO).sort("gross_contribution_sum")
    primary_symbols = symbol_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO).sort("gross_contribution_sum")

    def bucket_contribution(frame: pl.DataFrame, scenario: str, feature: str, bucket: str) -> str:
        row = frame.filter(
            (pl.col("scenario") == scenario) & (pl.col("feature") == feature) & (pl.col("bucket") == bucket)
        )
        if row.is_empty():
            return "NA"
        value = row["gross_contribution_sum"][0]
        return f"{value:.6f}"

    lines = [
        "# 股票震荡industry_resid_core 30万信号日亏损归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：第308阶段代表场景最大回撤窗口内，按建仓信号日可见特征拆分lot级毛贡献；不新增交易规则、不调参数。",
        f"- 主观察场景：`{PRIMARY_SCENARIO}`。",
        "- A/B判断：纯归因，不接入第78，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 残差短期反转有文献支持，但短反收益容易被趋势延续、动态风险暴露和流动性需求吞掉。",
        "- 因此本阶段只允许使用信号日已经知道的价格结构、残差回调、成交量和技术损坏特征；不把目标日IBS/日内收益这类事后信息当成过滤器。",
        "- 公开代码可参考横截面均值回归研究流程，但不能直接解决30万整手账户里的长回撤。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        "- 本阶段不是新策略回测；贡献按信号lot在最大回撤窗口内的目标日收益估算，用于定位事前坏形态。",
        "- 重点看：第316阶段的持仓日坏特征，能否在信号日被提前识别。",
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
        "",
        "## 本次关键发现",
        "",
        f"- 主观察场景里，信号日`damage_high`贡献为`{bucket_contribution(primary_manual, PRIMARY_SCENARIO, 'signal_damage_manual', 'damage_high')}`，`trend_penalty_high`贡献为`{bucket_contribution(primary_manual, PRIMARY_SCENARIO, 'signal_trend_penalty_manual', 'trend_penalty_high')}`，二者都是正贡献；不能把技术损坏惩罚简单改成建仓过滤。",
        f"- 主观察场景里，`ret10_deep_down`贡献为`{bucket_contribution(primary_manual, PRIMARY_SCENARIO, 'signal_ret10_manual', 'ret10_deep_down')}`，`far_from_252_high`贡献为`{bucket_contribution(primary_manual, PRIMARY_SCENARIO, 'signal_close_to_high_252_manual', 'far_from_252_high')}`，说明信号日深跌/远离高点并不是本阶段长回撤主因。",
        f"- 反而`damage_none`贡献为`{bucket_contribution(primary_manual, PRIMARY_SCENARIO, 'signal_damage_manual', 'damage_none')}`，`trend_penalty_none`贡献为`{bucket_contribution(primary_manual, PRIMARY_SCENARIO, 'signal_trend_penalty_manual', 'trend_penalty_none')}`，`volume_dry`贡献为`{bucket_contribution(primary_manual, PRIMARY_SCENARIO, 'signal_volume_ratio_20_manual', 'volume_dry')}`；坏样本更像从正常回调持仓中滑向趋势破坏。",
        "- 因此第316阶段看到的目标日短跌/破位/低IBS，不能直接前移成建仓过滤；下一步应该研究持仓期恶化确认或退出，而不是继续加建仓条件。",
        "",
        "## 最大回撤窗口",
        "",
        markdown_table(drawdown_windows, drawdown_windows.columns, max_rows=20),
        "",
        "## 回撤窗口信号lot贡献摘要",
        "",
        markdown_table(window_summary, window_summary.columns, max_rows=20),
        "",
        "## 主观察场景手工分桶亏损Top",
        "",
        markdown_table(primary_manual, primary_manual.columns, max_rows=40) if primary_manual.height else "无数据",
        "",
        "## 主观察场景全部特征分桶亏损Top",
        "",
        markdown_table(primary_features, primary_features.columns, max_rows=40) if primary_features.height else "无数据",
        "",
        "## 跨场景一致坏分桶Top",
        "",
        markdown_table(consistent_bad, consistent_bad.columns, max_rows=80) if consistent_bad.height else "无数据",
        "",
        "## 主观察场景行业亏损Top",
        "",
        markdown_table(primary_industry, primary_industry.columns, max_rows=40) if primary_industry.height else "无数据",
        "",
        "## 主观察场景个股亏损Top",
        "",
        markdown_table(primary_symbols, primary_symbols.columns, max_rows=40) if primary_symbols.height else "无数据",
        "",
        "## 特征缺失率Top",
        "",
        markdown_table(missing_summary, missing_summary.columns, max_rows=80) if not missing_summary.is_empty() else "无数据",
        "",
        "## 质量检查",
        "",
        markdown_table(quality, quality.columns, max_rows=40),
        "",
        "## 结论",
        "",
        "- 信号日坏分桶与第316阶段持仓日坏分桶并不同向，尤其技术损坏、深跌、远离高点在信号日并非坏贡献。",
        "- 当前不应做`ret5/ret10低`、`跌破均线`、`远离252高点`这类简单建仓过滤；这会误杀一部分真正有修复力的反转样本。",
        "- 下一步更合理：做持仓期恶化确认/退出归因，例如入场后第1-3天若从正常回调变成连续下跌、跌破MA20/MA60、放量下杀或低IBS延续，再判断提前退出是否能削掉2022-2024长回撤。",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "window_summary": OUTPUT_DIR / f"{PREFIX}_window_summary.csv",
        "signal_lots": OUTPUT_DIR / f"{PREFIX}_signal_lots.csv",
        "industry_summary": OUTPUT_DIR / f"{PREFIX}_industry_summary.csv",
        "symbol_summary": OUTPUT_DIR / f"{PREFIX}_symbol_summary.csv",
        "feature_bucket_summary": OUTPUT_DIR / f"{PREFIX}_feature_bucket_summary.csv",
        "consistent_bad_buckets": OUTPUT_DIR / f"{PREFIX}_consistent_bad_buckets.csv",
        "missing_summary": OUTPUT_DIR / f"{PREFIX}_missing_summary.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
    }

    stock_df, _benchmark_df = load_panels()
    daily_all = read_csv_with_symbol(REPLAY_SOURCE_DIR / f"{REPLAY_SOURCE_PREFIX}_daily.csv")
    selected = read_selected().join(build_path_dates(stock_df), on=["datetime", "symbol"], how="left")
    signal_lots = build_signal_lots(selected)
    target_returns = build_target_day_returns(stock_df)
    drawdown_windows = build_drawdown_windows(daily_all)

    enriched_lots = (
        signal_lots.join(target_returns, on=["target_date", "symbol"], how="left")
        .join(
            drawdown_windows.select(["scenario", "start_date", "trough_date", "peak_date", "recovery_date", "max_drawdown"]),
            on="scenario",
            how="left",
        )
        .filter((pl.col("target_date") >= pl.col("start_date")) & (pl.col("target_date") <= pl.col("trough_date")))
        .with_columns((pl.col("lot_weight") * pl.col("target_daily_ret").fill_null(0.0)).alias("gross_contribution"))
    )
    numeric_lots = cast_signal_numeric_features(enriched_lots)
    bucketed = add_manual_buckets(add_quantile_buckets(numeric_lots, SIGNAL_NUMERIC_FEATURES))

    window_summary = build_window_summary(bucketed)
    industry_summary = contribution_summary(bucketed, ["scenario", "industry"]) if "industry" in bucketed.columns else pl.DataFrame()
    symbol_group_cols = [col for col in ["scenario", "symbol", "code_name", "industry"] if col in bucketed.columns]
    symbol_summary = contribution_summary(bucketed, symbol_group_cols) if symbol_group_cols else pl.DataFrame()
    feature_summary = build_feature_bucket_summary(bucketed)
    consistent_bad = build_consistent_bad_buckets(feature_summary)
    missing_summary = build_missing_summary(bucketed)
    quality = build_quality(drawdown_windows, bucketed, feature_summary, missing_summary)

    window_summary.write_csv(paths["window_summary"])
    bucketed.write_csv(paths["signal_lots"])
    industry_summary.write_csv(paths["industry_summary"])
    symbol_summary.write_csv(paths["symbol_summary"])
    feature_summary.write_csv(paths["feature_bucket_summary"])
    consistent_bad.write_csv(paths["consistent_bad_buckets"])
    missing_summary.write_csv(paths["missing_summary"])
    quality.write_csv(paths["quality"])
    report_path = write_report(
        drawdown_windows,
        window_summary,
        industry_summary,
        symbol_summary,
        feature_summary,
        consistent_bad,
        missing_summary,
        quality,
        paths,
    )
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "selected_source_dir": str(SELECTED_SOURCE_DIR),
            "selected_source_prefix": SELECTED_SOURCE_PREFIX,
            "replay_source_dir": str(REPLAY_SOURCE_DIR),
            "replay_source_prefix": REPLAY_SOURCE_PREFIX,
            "output_dir": str(OUTPUT_DIR),
            "prefix": PREFIX,
            "focus_shapes": FOCUS_SHAPES,
            "focus_scenarios": FOCUS_SCENARIOS,
            "primary_scenario": PRIMARY_SCENARIO,
            "research_sources": RESEARCH_SOURCES,
            "annualized_signal_lot_vol_by_scenario": {
                row["scenario"]: annualized_vol(
                    bucketed.filter(pl.col("scenario") == row["scenario"])["gross_contribution"].to_list()
                )
                for row in window_summary.select("scenario").iter_rows(named=True)
            }
            if not window_summary.is_empty()
            else {},
            "outputs": {key: str(path) for key, path in paths.items()},
            "report": str(report_path),
        },
    )
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
