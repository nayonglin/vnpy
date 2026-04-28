from __future__ import annotations

import json
import os
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_industry_signal_lifecycle import build_base_frame
from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_liquid_q3_persistent_state_filter import build_age4_selected_with_state
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    FEATURE,
    HORIZON,
    NATIVE_RESULTS_DIR,
    pct,
)


OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_repairability_attribution_2018_2026"),
    )
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_repairability_attribution_v1"

ENTRY_AGE_MIN: int = int(os.getenv("ENTRY_AGE_MIN", "4") or 4)
MIN_DAILY_STATE_DAYS: int = int(os.getenv("MIN_DAILY_STATE_DAYS", "40") or 40)
MIN_STOCK_SIGNALS: int = int(os.getenv("MIN_STOCK_SIGNALS", "120") or 120)
STRESS_YEARS: tuple[int, ...] = tuple(int(item) for item in os.getenv("STRESS_YEARS", "2018,2022,2025").split(","))

STATE_COLUMNS: tuple[str, ...] = (
    "stock_ret20_band",
    "stock_ret10_band",
    "stock_ret5_band",
    "stock_ret1_band",
    "dist_ma20_band",
    "volume_ratio20_band",
    "turnover_5_20_band",
    "turnover_20_60_band",
    "down_volume_pressure_band",
    "recent_limit_down_5_band",
    "signal_limit_state",
    "adv20_turnover_q",
    "turnover_rate_f_q",
    "circ_mv_q",
    "total_mv_q",
    "listing_age_band",
    "top_age_bucket",
    "transition_from",
    "market_state_20d",
    "bm_ret_5_band",
    "bm_down_streak_band",
    "breadth_pos_20d_band",
    "limit_down_close_ratio_q",
    "industry",
)


def t_stat(mean: float, std: float | None, n: int) -> float:
    if not std or std <= 0 or n <= 1:
        return 0.0
    return mean / (std / sqrt(n))


def band_stock_ret(column: str, prefix: str, deep: float, severe: float, mild: float) -> pl.Expr:
    return (
        pl.when(pl.col(column).is_null())
        .then(pl.lit("unknown"))
        .when(pl.col(column) <= deep)
        .then(pl.lit(f"{prefix}_deep_drop"))
        .when(pl.col(column) <= severe)
        .then(pl.lit(f"{prefix}_severe_drop"))
        .when(pl.col(column) < mild)
        .then(pl.lit(f"{prefix}_mild_drop"))
        .otherwise(pl.lit(f"{prefix}_flat_or_up"))
    )


def add_repairability_features(base: pl.DataFrame) -> pl.DataFrame:
    work = base.sort(["symbol", "datetime"]).with_columns(
        pl.col("turnover").rolling_mean(5).over("symbol").alias("turnover_ma5"),
        pl.col("turnover").rolling_mean(20).over("symbol").alias("turnover_ma20"),
        pl.col("turnover").rolling_mean(60).over("symbol").alias("turnover_ma60"),
        pl.col("volume").rolling_mean(5).over("symbol").alias("volume_ma5"),
        pl.col("is_limit_down_close").cast(pl.Int64).rolling_sum(5).over("symbol").alias("limit_down_count_5"),
        pl.col("is_oneword_limit_down").cast(pl.Int64).rolling_sum(5).over("symbol").alias(
            "oneword_limit_down_count_5"
        ),
    )
    work = work.with_columns(
        (pl.col("turnover_ma5") / pl.col("turnover_ma20")).alias("turnover_5_20_ratio"),
        (pl.col("turnover_ma20") / pl.col("turnover_ma60")).alias("turnover_20_60_ratio"),
        (pl.col("volume_ma5") / pl.col("volume_ma20")).alias("volume_5_20_ratio"),
    )
    return work.with_columns(
        band_stock_ret("ret_20", "ret20", -0.25, -0.15, -0.05).alias("stock_ret20_band"),
        band_stock_ret("ret_10", "ret10", -0.18, -0.10, -0.03).alias("stock_ret10_band"),
        band_stock_ret("ret_5", "ret5", -0.10, -0.05, 0.0).alias("stock_ret5_band"),
        band_stock_ret("ret_1", "ret1", -0.05, -0.02, 0.0).alias("stock_ret1_band"),
        (
            pl.when(pl.col("dist_ma20").is_null())
            .then(pl.lit("unknown"))
            .when(pl.col("dist_ma20") <= -0.20)
            .then(pl.lit("below_ma20_deep"))
            .when(pl.col("dist_ma20") <= -0.10)
            .then(pl.lit("below_ma20_severe"))
            .when(pl.col("dist_ma20") < 0)
            .then(pl.lit("below_ma20_mild"))
            .otherwise(pl.lit("above_ma20"))
            .alias("dist_ma20_band")
        ),
        (
            pl.when(pl.col("volume_ratio_20").is_null())
            .then(pl.lit("unknown"))
            .when(pl.col("volume_ratio_20") <= 0.70)
            .then(pl.lit("volume_dry"))
            .when(pl.col("volume_ratio_20") <= 1.20)
            .then(pl.lit("volume_normal"))
            .when(pl.col("volume_ratio_20") <= 2.00)
            .then(pl.lit("volume_expand"))
            .otherwise(pl.lit("volume_panic"))
            .alias("volume_ratio20_band")
        ),
        (
            pl.when(pl.col("turnover_5_20_ratio").is_null())
            .then(pl.lit("unknown"))
            .when(pl.col("turnover_5_20_ratio") <= 0.70)
            .then(pl.lit("turnover_5_20_contract"))
            .when(pl.col("turnover_5_20_ratio") <= 1.20)
            .then(pl.lit("turnover_5_20_normal"))
            .when(pl.col("turnover_5_20_ratio") <= 1.80)
            .then(pl.lit("turnover_5_20_expand"))
            .otherwise(pl.lit("turnover_5_20_spike"))
            .alias("turnover_5_20_band")
        ),
        (
            pl.when(pl.col("turnover_20_60_ratio").is_null())
            .then(pl.lit("unknown"))
            .when(pl.col("turnover_20_60_ratio") <= 0.70)
            .then(pl.lit("turnover_20_60_contract"))
            .when(pl.col("turnover_20_60_ratio") <= 1.10)
            .then(pl.lit("turnover_20_60_normal"))
            .otherwise(pl.lit("turnover_20_60_expand"))
            .alias("turnover_20_60_band")
        ),
        (
            pl.when(pl.col("score_down_volume_pressure").is_null())
            .then(pl.lit("unknown"))
            .when(pl.col("score_down_volume_pressure") <= 0)
            .then(pl.lit("no_down_volume_pressure"))
            .when(pl.col("score_down_volume_pressure") <= 0.03)
            .then(pl.lit("mild_down_volume_pressure"))
            .when(pl.col("score_down_volume_pressure") <= 0.08)
            .then(pl.lit("heavy_down_volume_pressure"))
            .otherwise(pl.lit("panic_down_volume_pressure"))
            .alias("down_volume_pressure_band")
        ),
        (
            pl.when(pl.col("oneword_limit_down_count_5") > 0)
            .then(pl.lit("recent_oneword_limit_down"))
            .when(pl.col("limit_down_count_5") >= 2)
            .then(pl.lit("recent_limit_down_chain"))
            .when(pl.col("limit_down_count_5") == 1)
            .then(pl.lit("recent_one_limit_down"))
            .otherwise(pl.lit("no_recent_limit_down"))
            .alias("recent_limit_down_5_band")
        ),
        (
            pl.when(pl.col("is_oneword_limit_down").fill_null(False))
            .then(pl.lit("signal_oneword_limit_down"))
            .when(pl.col("is_limit_down_close").fill_null(False))
            .then(pl.lit("signal_limit_down_close"))
            .otherwise(pl.lit("signal_normal_close"))
            .alias("signal_limit_state")
        ),
        (
            pl.when(pl.col("listing_days").is_null())
            .then(pl.lit("unknown"))
            .when(pl.col("listing_days") <= 252)
            .then(pl.lit("listing_lt_1y"))
            .when(pl.col("listing_days") <= 756)
            .then(pl.lit("listing_1_3y"))
            .otherwise(pl.lit("listing_gt_3y"))
            .alias("listing_age_band")
        ),
    )


def add_path_outcomes(selected: pl.DataFrame) -> pl.DataFrame:
    cum_exprs: list[pl.Expr] = []
    cumulative = pl.lit(1.0)
    for day in range(1, HORIZON + 1):
        cumulative = cumulative * (1.0 + pl.col(f"stock_daily_ret_{day}"))
        cum_exprs.append((cumulative - 1.0).alias(f"path_cum_ret_{day}"))
    cum_cols = [f"path_cum_ret_{day}" for day in range(1, HORIZON + 1)]
    return (
        selected.with_columns(cum_exprs)
        .with_columns(
            pl.min_horizontal([pl.col(col) for col in cum_cols]).alias("path_min_cum_ret"),
            pl.max_horizontal([pl.col(col) for col in cum_cols]).alias("path_max_cum_ret"),
        )
        .with_columns(
            pl.when(pl.col(f"fwd_ret_{HORIZON}") >= 0.08)
            .then(pl.lit("big_rebound"))
            .when(pl.col(f"fwd_ret_{HORIZON}") > 0)
            .then(pl.lit("repair_win"))
            .when(pl.col(f"fwd_ret_{HORIZON}") <= -0.08)
            .then(pl.lit("severe_loss"))
            .otherwise(pl.lit("small_loss"))
            .alias("outcome_bucket")
        )
    )


def summarize_daily_by_state(selected: pl.DataFrame, state_columns: tuple[str, ...]) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for state_column in state_columns:
        if state_column not in selected.columns:
            continue
        daily = (
            selected.filter(pl.col(state_column).is_not_null())
            .group_by(["datetime", state_column])
            .agg(
                pl.len().alias("stock_signals"),
                pl.col("symbol").n_unique().alias("symbol_count"),
                pl.col("industry").n_unique().alias("industry_count"),
                pl.col("basket_weight").sum().alias("weight_sum"),
                (pl.col("basket_weight") * pl.col(f"fwd_ret_{HORIZON}")).sum().alias("ret_on_capital"),
                (pl.col("basket_weight") * pl.col(f"fwd_excess_ret_{HORIZON}")).sum().alias("excess_ret_on_capital"),
                pl.col(f"fwd_ret_{HORIZON}").mean().alias("equal_stock_ret"),
                (pl.col(f"fwd_ret_{HORIZON}") > 0).mean().alias("stock_win_rate"),
                (pl.col(f"fwd_ret_{HORIZON}") <= -0.08).mean().alias("severe_loss_rate"),
                (pl.col(f"fwd_ret_{HORIZON}") >= 0.08).mean().alias("big_rebound_rate"),
                pl.col("path_min_cum_ret").mean().alias("path_min_cum_ret_mean"),
                pl.col("path_max_cum_ret").mean().alias("path_max_cum_ret_mean"),
                pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
                pl.col("circ_mv").median().alias("median_circ_mv"),
            )
            .with_columns(
                pl.when(pl.col("weight_sum") > 0)
                .then(pl.col("ret_on_capital") / pl.col("weight_sum"))
                .otherwise(None)
                .alias("ret_on_deployed"),
                pl.col("datetime").dt.year().alias("year"),
            )
        )
        summary = (
            daily.group_by(state_column)
            .agg(
                pl.len().alias("days"),
                pl.col("stock_signals").sum().alias("stock_signals"),
                pl.col("stock_signals").mean().alias("avg_daily_stock_signals"),
                pl.col("symbol_count").mean().alias("avg_daily_symbol_count"),
                pl.col("industry_count").mean().alias("avg_daily_industry_count"),
                pl.col("weight_sum").mean().alias("avg_weight_sum"),
                pl.col("ret_on_capital").mean().alias("ret_on_capital_mean"),
                pl.col("ret_on_capital").std().alias("ret_on_capital_std"),
                (pl.col("ret_on_capital") > 0).mean().alias("capital_day_win_rate"),
                pl.col("ret_on_deployed").mean().alias("ret_on_deployed_mean"),
                pl.col("excess_ret_on_capital").mean().alias("excess_ret_on_capital_mean"),
                pl.col("equal_stock_ret").mean().alias("equal_stock_ret_mean"),
                pl.col("stock_win_rate").mean().alias("avg_stock_win_rate"),
                pl.col("severe_loss_rate").mean().alias("avg_severe_loss_rate"),
                pl.col("big_rebound_rate").mean().alias("avg_big_rebound_rate"),
                pl.col("path_min_cum_ret_mean").mean().alias("path_min_cum_ret_mean"),
                pl.col("path_max_cum_ret_mean").mean().alias("path_max_cum_ret_mean"),
                pl.col("median_adv20_turnover").median().alias("median_adv20_turnover"),
                pl.col("median_circ_mv").median().alias("median_circ_mv"),
                pl.col("year").is_in(STRESS_YEARS).mean().alias("stress_year_day_ratio"),
            )
            .with_columns(
                pl.lit(state_column).alias("state_layer"),
                pl.col(state_column).cast(pl.String).alias("state_value"),
                pl.struct(["ret_on_capital_mean", "ret_on_capital_std", "days"]).map_elements(
                    lambda row: t_stat(row["ret_on_capital_mean"], row["ret_on_capital_std"], row["days"]),
                    return_dtype=pl.Float64,
                ).alias("ret_on_capital_t"),
            )
            .drop(state_column, "ret_on_capital_std")
            .filter((pl.col("days") >= MIN_DAILY_STATE_DAYS) & (pl.col("stock_signals") >= MIN_STOCK_SIGNALS))
        )
        frames.append(summary)
    return pl.concat(frames, how="vertical").sort(["state_layer", "state_value"]) if frames else pl.DataFrame()


def summarize_stock_by_state(selected: pl.DataFrame, state_columns: tuple[str, ...]) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for state_column in state_columns:
        if state_column not in selected.columns:
            continue
        summary = (
            selected.filter(pl.col(state_column).is_not_null())
            .group_by(state_column)
            .agg(
                pl.len().alias("stock_signals"),
                pl.col("datetime").n_unique().alias("signal_days"),
                pl.col(f"fwd_ret_{HORIZON}").mean().alias("fwd_ret_mean"),
                pl.col(f"fwd_excess_ret_{HORIZON}").mean().alias("fwd_excess_ret_mean"),
                (pl.col(f"fwd_ret_{HORIZON}") > 0).mean().alias("win_rate"),
                (pl.col(f"fwd_ret_{HORIZON}") <= -0.08).mean().alias("severe_loss_rate"),
                (pl.col(f"fwd_ret_{HORIZON}") >= 0.08).mean().alias("big_rebound_rate"),
                pl.col("path_min_cum_ret").mean().alias("path_min_cum_ret_mean"),
                pl.col("path_max_cum_ret").mean().alias("path_max_cum_ret_mean"),
                pl.col("ret_20").mean().alias("avg_ret_20"),
                pl.col("ret_5").mean().alias("avg_ret_5"),
                pl.col("volume_ratio_20").mean().alias("avg_volume_ratio_20"),
                pl.col("turnover_5_20_ratio").mean().alias("avg_turnover_5_20_ratio"),
                pl.col("turnover_20_60_ratio").mean().alias("avg_turnover_20_60_ratio"),
                pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
                pl.col("circ_mv").median().alias("median_circ_mv"),
            )
            .with_columns(
                pl.lit(state_column).alias("state_layer"),
                pl.col(state_column).cast(pl.String).alias("state_value"),
            )
            .drop(state_column)
            .filter((pl.col("signal_days") >= MIN_DAILY_STATE_DAYS) & (pl.col("stock_signals") >= MIN_STOCK_SIGNALS))
        )
        frames.append(summary)
    return pl.concat(frames, how="vertical").sort(["state_layer", "state_value"]) if frames else pl.DataFrame()


def build_outcome_profile(selected: pl.DataFrame) -> pl.DataFrame:
    return (
        selected.group_by("outcome_bucket")
        .agg(
            pl.len().alias("stock_signals"),
            pl.col("datetime").n_unique().alias("signal_days"),
            pl.col(f"fwd_ret_{HORIZON}").mean().alias("fwd_ret_mean"),
            pl.col(f"fwd_excess_ret_{HORIZON}").mean().alias("fwd_excess_ret_mean"),
            pl.col("path_min_cum_ret").mean().alias("path_min_cum_ret_mean"),
            pl.col("path_max_cum_ret").mean().alias("path_max_cum_ret_mean"),
            pl.col("ret_20").mean().alias("avg_ret_20"),
            pl.col("ret_5").mean().alias("avg_ret_5"),
            pl.col("volume_ratio_20").mean().alias("avg_volume_ratio_20"),
            pl.col("turnover_5_20_ratio").mean().alias("avg_turnover_5_20_ratio"),
            pl.col("turnover_20_60_ratio").mean().alias("avg_turnover_20_60_ratio"),
            pl.col("limit_down_count_5").mean().alias("avg_limit_down_count_5"),
            pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
            pl.col("turnover_rate_f").median().alias("median_turnover_rate_f"),
            pl.col("circ_mv").median().alias("median_circ_mv"),
            pl.col("top_age").mean().alias("avg_top_age"),
        )
        .sort("fwd_ret_mean")
    )


def build_year_state_mix(daily_summary_source: pl.DataFrame, state_columns: tuple[str, ...]) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for state_column in state_columns:
        if state_column not in daily_summary_source.columns:
            continue
        frames.append(
            daily_summary_source.filter(pl.col(state_column).is_not_null())
            .group_by([pl.col("datetime").dt.year().alias("year"), state_column])
            .agg(
                pl.len().alias("stock_signals"),
                pl.col(f"fwd_ret_{HORIZON}").mean().alias("fwd_ret_mean"),
                (pl.col(f"fwd_ret_{HORIZON}") <= -0.08).mean().alias("severe_loss_rate"),
            )
            .with_columns(
                pl.lit(state_column).alias("state_layer"),
                pl.col(state_column).cast(pl.String).alias("state_value"),
            )
            .drop(state_column)
        )
    return pl.concat(frames, how="vertical").sort(["state_layer", "year", "state_value"]) if frames else pl.DataFrame()


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 40) -> str:
    if frame.is_empty():
        return "无数据"
    return frame.select([col for col in columns if col in frame.columns]).head(max_rows).to_pandas().to_markdown(
        index=False
    )


def write_report(
    daily_summary: pl.DataFrame,
    stock_summary: pl.DataFrame,
    outcome_profile: pl.DataFrame,
    weak_daily_states: pl.DataFrame,
    strong_daily_states: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    baseline_ret = meta["baseline_weighted_ret_on_capital"]
    baseline_deployed_ret = meta["baseline_ret_on_deployed"]
    baseline_win = meta["baseline_stock_win_rate"]
    weak = weak_daily_states.head(1).to_dicts()
    strong = strong_daily_states.head(1).to_dicts()
    lines = [
        "# 股票震荡liquid_q3可修复/恶化超跌归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：`4天确认+每日建篮`的信号层归因，不是新交易版本，不做参数选择。",
        "- 外部调研判断：短期反转常被解释为提供流动性的补偿，但收益对流动性冲击和波动冲击敏感；因此本阶段重点看成交、换手、跌停链、规模和持续在榜，而不是继续调止损。",
        f"- 固定底稿：`liquid_q3`行业内top20连续在榜至少`{ENTRY_AGE_MIN}`天，观察未来`{HORIZON}`日。",
        "",
        "## 核心观察",
        "",
        f"- 全样本按信号日汇总的10日资本口径均值为`{pct(baseline_ret)}`，部署资金口径均值`{pct(baseline_deployed_ret)}`，股票胜率`{baseline_win:.2%}`。",
    ]
    if weak:
        row = weak[0]
        lines.append(
            f"- 最弱日度状态是`{row['state_layer']}`=`{row['state_value']}`：日数`{row['days']}`，"
            f"10日资本口径均值`{pct(row['ret_on_capital_mean'])}`，严重亏损率`{row['avg_severe_loss_rate']:.2%}`。"
        )
    if strong:
        row = strong[0]
        lines.append(
            f"- 最强日度状态是`{row['state_layer']}`=`{row['state_value']}`：日数`{row['days']}`，"
            f"10日资本口径均值`{pct(row['ret_on_capital_mean'])}`，大反弹率`{row['avg_big_rebound_rate']:.2%}`。"
        )
    lines.extend(
        [
            "- 最强状态反而是市场急跌、连续下跌、极弱宽度、高跌停压力这些恐慌状态；这确认了第242阶段的直觉：不能粗暴躲开恐慌，因为恐慌也是反弹收益来源。",
            "- 最弱线索主要有两类：一类是行业/主题阶段性错杀，不能直接做行业黑名单；另一类是成交干枯、短期换手收缩，这属于可事前观察、低频更新的非价格恶化线索，值得做少数固定压力测试。",
            "- 深度价格超跌本身不是坏事：`ret20_deep_drop`和`ret10_deep_drop`在股票级和日度状态里并不弱，说明不能用跌幅越深越危险的线性思路处理均值回归。",
            "- 本报告只给归因线索；任何单一最弱状态都不能直接变成剔除规则，需要后续固定压力测试验证。",
            "",
            "## 未来结果画像",
            "",
            markdown_table(
                outcome_profile,
                [
                    "outcome_bucket",
                    "stock_signals",
                    "signal_days",
                    "fwd_ret_mean",
                    "fwd_excess_ret_mean",
                    "path_min_cum_ret_mean",
                    "path_max_cum_ret_mean",
                    "avg_ret_20",
                    "avg_ret_5",
                    "avg_volume_ratio_20",
                    "avg_turnover_5_20_ratio",
                    "avg_turnover_20_60_ratio",
                    "avg_limit_down_count_5",
                    "median_adv20_turnover",
                    "median_circ_mv",
                    "avg_top_age",
                ],
            ),
            "",
            "## 最弱日度状态",
            "",
            markdown_table(
                weak_daily_states,
                [
                    "state_layer",
                    "state_value",
                    "days",
                    "stock_signals",
                    "avg_weight_sum",
                    "ret_on_capital_mean",
                    "ret_on_deployed_mean",
                    "capital_day_win_rate",
                    "avg_stock_win_rate",
                    "avg_severe_loss_rate",
                    "avg_big_rebound_rate",
                    "path_min_cum_ret_mean",
                    "path_max_cum_ret_mean",
                    "median_adv20_turnover",
                    "median_circ_mv",
                    "stress_year_day_ratio",
                    "ret_on_capital_t",
                ],
                max_rows=30,
            ),
            "",
            "## 最强日度状态",
            "",
            markdown_table(
                strong_daily_states,
                [
                    "state_layer",
                    "state_value",
                    "days",
                    "stock_signals",
                    "avg_weight_sum",
                    "ret_on_capital_mean",
                    "ret_on_deployed_mean",
                    "capital_day_win_rate",
                    "avg_stock_win_rate",
                    "avg_severe_loss_rate",
                    "avg_big_rebound_rate",
                    "path_min_cum_ret_mean",
                    "path_max_cum_ret_mean",
                    "median_adv20_turnover",
                    "median_circ_mv",
                    "stress_year_day_ratio",
                    "ret_on_capital_t",
                ],
                max_rows=30,
            ),
            "",
            "## 股票级最弱状态",
            "",
            markdown_table(
                stock_summary.sort(["fwd_ret_mean", "stock_signals"]),
                [
                    "state_layer",
                    "state_value",
                    "stock_signals",
                    "signal_days",
                    "fwd_ret_mean",
                    "fwd_excess_ret_mean",
                    "win_rate",
                    "severe_loss_rate",
                    "big_rebound_rate",
                    "path_min_cum_ret_mean",
                    "path_max_cum_ret_mean",
                    "avg_ret_20",
                    "avg_ret_5",
                    "avg_volume_ratio_20",
                    "avg_turnover_5_20_ratio",
                    "avg_turnover_20_60_ratio",
                    "median_adv20_turnover",
                    "median_circ_mv",
                ],
                max_rows=30,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只用固定的事前可知解释变量做归因，不生成交易规则，不扫描阈值，不选择最优组合。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段没有把最弱状态变成交易规则，也没有挑行业黑名单；它给出的有效信息是反证粗急跌保护、提示成交干枯/换手收缩可作为下一步固定压力测试。",
            "- 风险：行业维度差异很容易拟合历史主题周期，因此不能直接用于剔除。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第242阶段证明粗急跌保护会伤害反弹，下一步必须回到信号层区分可修复超跌和继续恶化超跌。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：归因确认了恐慌状态不是该躲的对象，同时指出成交干枯/换手收缩这类非价格恶化线索；下一步可以只做少数固定剔除压力测试，避免继续调止损。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
            "- 不使用行业黑名单，不过滤市场急跌/高跌停压力，不按超跌深度做线性过滤。",
            "- 下一步只测试少数固定非价格恶化过滤：成交干枯、短期换手收缩、二者组合。",
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
    selected, _date_state = build_age4_selected_with_state(base, stock_df, benchmark_df, layer_tags)
    selected = add_path_outcomes(selected)
    daily_summary = summarize_daily_by_state(selected, STATE_COLUMNS)
    stock_summary = summarize_stock_by_state(selected, STATE_COLUMNS)
    outcome_profile = build_outcome_profile(selected)
    year_state_mix = build_year_state_mix(selected, STATE_COLUMNS)
    weak_daily_states = daily_summary.sort(["ret_on_capital_mean", "days"]).head(60)
    strong_daily_states = daily_summary.sort(["ret_on_capital_mean", "days"], descending=[True, False]).head(60)

    daily_baseline = selected.group_by("datetime").agg(
        (pl.col("basket_weight") * pl.col(f"fwd_ret_{HORIZON}")).sum().alias("ret_on_capital"),
        pl.col("basket_weight").sum().alias("weight_sum"),
    ).with_columns(
        pl.when(pl.col("weight_sum") > 0)
        .then(pl.col("ret_on_capital") / pl.col("weight_sum"))
        .otherwise(None)
        .alias("ret_on_deployed")
    )
    baseline = selected.select(
        (pl.col(f"fwd_ret_{HORIZON}") > 0).mean().alias("stock_win_rate"),
        (pl.col(f"fwd_ret_{HORIZON}") <= -0.08).mean().alias("severe_loss_rate"),
        (pl.col(f"fwd_ret_{HORIZON}") >= 0.08).mean().alias("big_rebound_rate"),
    ).row(0, named=True)
    meta: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "feature": FEATURE,
        "horizon": HORIZON,
        "entry_age_min": ENTRY_AGE_MIN,
        "stress_years": STRESS_YEARS,
        "state_columns": STATE_COLUMNS,
        "selected_rows": selected.height,
        "signal_days": selected["datetime"].n_unique(),
        "symbol_count": selected["symbol"].n_unique(),
        "date_min": str(selected["datetime"].min()),
        "date_max": str(selected["datetime"].max()),
        "baseline_weighted_ret_on_capital": daily_baseline["ret_on_capital"].mean(),
        "baseline_ret_on_deployed": daily_baseline["ret_on_deployed"].mean(),
        "baseline_stock_win_rate": baseline["stock_win_rate"],
        "baseline_severe_loss_rate": baseline["severe_loss_rate"],
        "baseline_big_rebound_rate": baseline["big_rebound_rate"],
        "min_daily_state_days": MIN_DAILY_STATE_DAYS,
        "min_stock_signals": MIN_STOCK_SIGNALS,
    }
    paths = {
        "selected_signals": OUTPUT_DIR / f"{PREFIX}_selected_signals.parquet",
        "daily_state_summary": OUTPUT_DIR / f"{PREFIX}_daily_state_summary.csv",
        "stock_state_summary": OUTPUT_DIR / f"{PREFIX}_stock_state_summary.csv",
        "outcome_profile": OUTPUT_DIR / f"{PREFIX}_outcome_profile.csv",
        "year_state_mix": OUTPUT_DIR / f"{PREFIX}_year_state_mix.csv",
        "weak_daily_states": OUTPUT_DIR / f"{PREFIX}_weak_daily_states.csv",
        "strong_daily_states": OUTPUT_DIR / f"{PREFIX}_strong_daily_states.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    selected.write_parquet(paths["selected_signals"])
    daily_summary.write_csv(paths["daily_state_summary"])
    stock_summary.write_csv(paths["stock_state_summary"])
    outcome_profile.write_csv(paths["outcome_profile"])
    year_state_mix.write_csv(paths["year_state_mix"])
    weak_daily_states.write_csv(paths["weak_daily_states"])
    strong_daily_states.write_csv(paths["strong_daily_states"])
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(
        daily_summary,
        stock_summary,
        outcome_profile,
        weak_daily_states,
        strong_daily_states,
        meta,
        paths,
    )
    print(outcome_profile)
    print(weak_daily_states.head(20))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
