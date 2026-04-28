from __future__ import annotations

import json
import os
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import (
    N_GROUPS,
    add_forward_returns,
    add_price_features,
    to_float,
)


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_residual_industry_signal_2018_2026"),
    )
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_residual_industry_signal_v1"

LOOKBACKS: tuple[int, ...] = tuple(int(item) for item in os.getenv("LOOKBACKS", "5,10,20").split(",") if item)
HORIZONS: tuple[int, ...] = tuple(int(item) for item in os.getenv("HORIZONS", "5,10").split(",") if item)
COST_BPS: tuple[float, ...] = tuple(float(item) for item in os.getenv("COST_BPS", "20,50").split(",") if item)
MIN_GLOBAL_DAILY_WIDTH: int = int(os.getenv("MIN_GLOBAL_DAILY_WIDTH", "50") or 50)
MIN_INDUSTRY_DAILY_WIDTH: int = int(os.getenv("MIN_INDUSTRY_DAILY_WIDTH", "20") or 20)
MIN_SUMMARY_DAYS: int = int(os.getenv("MIN_SUMMARY_DAYS", "60") or 60)


def pct(value: float) -> str:
    return f"{value:.2%}"


def t_stat_expr(mean_col: str, std_col: str, days_col: str) -> pl.Expr:
    return (
        pl.when((pl.col(std_col).is_not_null()) & (pl.col(std_col) > 0) & (pl.col(days_col) > 1))
        .then(pl.col(mean_col) / (pl.col(std_col) / pl.col(days_col).sqrt()))
        .otherwise(0.0)
    )


def build_benchmark_past_returns(benchmark_df: pl.DataFrame) -> pl.DataFrame:
    bm = benchmark_df.sort("datetime")
    exprs = [(pl.col("close") / pl.col("close").shift(lookback) - 1).alias(f"bm_ret_{lookback}") for lookback in LOOKBACKS]
    return bm.with_columns(exprs).select(["datetime", *[f"bm_ret_{lookback}" for lookback in LOOKBACKS]])


def add_peer_residual_features(df: pl.DataFrame) -> pl.DataFrame:
    work = df
    for lookback in LOOKBACKS:
        ret_col = f"ret_{lookback}"
        bm_col = f"bm_ret_{lookback}"
        peer_sum = f"_industry_sum_ret_{lookback}"
        peer_count = f"_industry_count_ret_{lookback}"
        peer_mean = f"industry_peer_ret_{lookback}"
        industry_relative = f"industry_relative_ret_{lookback}"
        market_relative = f"market_relative_ret_{lookback}"
        work = work.with_columns(
            (pl.col(ret_col) - pl.col(bm_col)).alias(market_relative),
            pl.col(ret_col).sum().over(["datetime", "industry"]).alias(peer_sum),
            pl.col(ret_col).count().over(["datetime", "industry"]).alias(peer_count),
        ).with_columns(
            pl.when(pl.col(peer_count) > 1)
            .then((pl.col(peer_sum) - pl.col(ret_col)) / (pl.col(peer_count) - 1))
            .otherwise(None)
            .alias(peer_mean)
        ).with_columns(
            (pl.col(ret_col) - pl.col(peer_mean)).alias(industry_relative),
            (-pl.col(ret_col)).alias(f"score_raw_ret_{lookback}"),
            (-pl.col(market_relative)).alias(f"score_market_resid_ret_{lookback}"),
        ).with_columns(
            (-pl.col(industry_relative)).alias(f"score_industry_resid_ret_{lookback}"),
        )
    return work.drop([col for col in work.columns if col.startswith("_industry_")])


def bucket_definitions() -> list[tuple[str, str, pl.Expr]]:
    return [
        ("all_component", "历史中证1000成分有效样本", pl.col("eligible_component_row").fill_null(False)),
        (
            "active_q4_q5",
            "自由换手和20日成交额都在前40%",
            (pl.col("turnover_rate_f_q") >= 4) & (pl.col("adv20_turnover_q") >= 4),
        ),
    ]


def signal_variants(lookback: int) -> list[dict[str, Any]]:
    return [
        {
            "variant": "raw_global",
            "description": "全市场裸超跌排序",
            "score_col": f"score_raw_ret_{lookback}",
            "partition_cols": [],
            "min_width": MIN_GLOBAL_DAILY_WIDTH,
        },
        {
            "variant": "market_residual_global",
            "description": "全市场市场残差排序；同日减指数常数，理论上应与裸排序近似等价",
            "score_col": f"score_market_resid_ret_{lookback}",
            "partition_cols": [],
            "min_width": MIN_GLOBAL_DAILY_WIDTH,
        },
        {
            "variant": "industry_residual_global",
            "description": "全市场行业内残差超跌排序",
            "score_col": f"score_industry_resid_ret_{lookback}",
            "partition_cols": [],
            "min_width": MIN_GLOBAL_DAILY_WIDTH,
        },
        {
            "variant": "industry_neutral_raw",
            "description": "行业内裸超跌分位排序后合并",
            "score_col": f"score_raw_ret_{lookback}",
            "partition_cols": ["industry"],
            "min_width": MIN_INDUSTRY_DAILY_WIDTH,
        },
    ]


def valid_filter(score_col: str, horizon: int) -> pl.Expr:
    return (
        pl.col(f"final_keep_{horizon}")
        & pl.col("eligible_component_row").fill_null(False)
        & pl.col(score_col).is_not_null()
        & pl.col(score_col).is_finite()
        & pl.col(f"fwd_ret_{horizon}").is_not_null()
        & pl.col(f"fwd_ret_{horizon}").is_finite()
        & pl.col(f"fwd_excess_ret_{horizon}").is_not_null()
        & pl.col(f"fwd_excess_ret_{horizon}").is_finite()
    )


def add_rank_groups(work: pl.DataFrame, score_col: str, partition_cols: list[str], min_width: int) -> pl.DataFrame:
    over_cols = ["datetime", *partition_cols]
    return (
        work.with_columns(
            pl.col(score_col).rank("ordinal").over(over_cols).alias("_rank"),
            pl.len().over(over_cols).alias("_n"),
        )
        .filter(pl.col("_n") >= min_width)
        .with_columns(
            ((((pl.col("_rank") - 1) * N_GROUPS) / pl.col("_n")).floor().cast(pl.Int64) + 1)
            .clip(1, N_GROUPS)
            .alias("feature_group")
        )
    )


def build_daily_series(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    daily_frames: list[pl.DataFrame] = []
    industry_frames: list[pl.DataFrame] = []

    for bucket, bucket_description, bucket_expr in bucket_definitions():
        for lookback in LOOKBACKS:
            for horizon in HORIZONS:
                abs_col = f"fwd_ret_{horizon}"
                excess_col = f"fwd_excess_ret_{horizon}"
                bm_fwd_col = f"bm_fwd_ret_{horizon}"
                for variant in signal_variants(lookback):
                    score_col = variant["score_col"]
                    partition_cols = variant["partition_cols"]
                    work = df.filter(bucket_expr & valid_filter(score_col, horizon))
                    if "industry" in partition_cols:
                        work = work.filter(pl.col("industry").is_not_null())
                    if work.is_empty():
                        continue

                    ranked = add_rank_groups(work, score_col, partition_cols, variant["min_width"])
                    grouped = (
                        ranked.group_by(["datetime", "feature_group"])
                        .agg(
                            pl.col(abs_col).mean().alias("group_abs_ret"),
                            pl.col(excess_col).mean().alias("group_excess_ret"),
                            pl.len().alias("stock_count"),
                            pl.col("industry").n_unique().alias("industry_count"),
                            pl.col("_n").mean().alias("avg_partition_width"),
                            pl.first(bm_fwd_col).alias("benchmark_forward_ret"),
                            pl.first("market_state_20d").alias("market_state_20d"),
                            pl.first(f"bm_ret_{lookback}").alias("benchmark_past_ret"),
                        )
                    )
                    top = grouped.filter(pl.col("feature_group") == N_GROUPS).select(
                        [
                            "datetime",
                            pl.col("group_abs_ret").alias("top_abs_ret"),
                            pl.col("group_excess_ret").alias("top_excess_ret"),
                            pl.col("stock_count").alias("top_stock_count"),
                            pl.col("industry_count").alias("top_industry_count"),
                            pl.col("avg_partition_width").alias("top_avg_partition_width"),
                            "benchmark_forward_ret",
                            "market_state_20d",
                            "benchmark_past_ret",
                        ]
                    )
                    bottom = grouped.filter(pl.col("feature_group") == 1).select(
                        [
                            "datetime",
                            pl.col("group_abs_ret").alias("bottom_abs_ret"),
                            pl.col("group_excess_ret").alias("bottom_excess_ret"),
                            pl.col("stock_count").alias("bottom_stock_count"),
                            pl.col("industry_count").alias("bottom_industry_count"),
                        ]
                    )
                    daily = (
                        top.join(bottom, on="datetime", how="inner")
                        .with_columns(
                            (pl.col("top_abs_ret") - pl.col("bottom_abs_ret")).alias("top_minus_bottom_abs"),
                            (pl.col("top_excess_ret") - pl.col("bottom_excess_ret")).alias(
                                "top_minus_bottom_excess"
                            ),
                            pl.lit(bucket).alias("bucket"),
                            pl.lit(bucket_description).alias("bucket_description"),
                            pl.lit(lookback).alias("lookback"),
                            pl.lit(horizon).alias("horizon"),
                            pl.lit(variant["variant"]).alias("signal_variant"),
                            pl.lit(variant["description"]).alias("signal_description"),
                            pl.lit("industry" if partition_cols else "global").alias("ranking_scope"),
                        )
                    )
                    daily_frames.append(daily)

                    top_industry = (
                        ranked.filter(pl.col("feature_group") == N_GROUPS)
                        .group_by("industry")
                        .agg(
                            pl.col("datetime").n_unique().alias("active_days"),
                            pl.len().alias("top_stock_rows"),
                            pl.col(abs_col).mean().alias("top_abs_ret_mean"),
                            pl.col(excess_col).mean().alias("top_excess_ret_mean"),
                        )
                        .with_columns(
                            pl.lit(bucket).alias("bucket"),
                            pl.lit(lookback).alias("lookback"),
                            pl.lit(horizon).alias("horizon"),
                            pl.lit(variant["variant"]).alias("signal_variant"),
                        )
                    )
                    industry_frames.append(top_industry)

    daily_df = pl.concat(daily_frames, how="vertical") if daily_frames else pl.DataFrame()
    industry_df = pl.concat(industry_frames, how="vertical") if industry_frames else pl.DataFrame()
    return daily_df, industry_df


def summarize_daily(daily_df: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    if daily_df.is_empty():
        return pl.DataFrame()
    summary = (
        daily_df.with_columns(pl.col("datetime").dt.year().alias("year"))
        .group_by(keys)
        .agg(
            pl.len().alias("days"),
            pl.col("top_stock_count").mean().alias("avg_top_stock_count"),
            pl.col("top_industry_count").mean().alias("avg_top_industry_count"),
            pl.col("top_abs_ret").mean().alias("top_abs_ret_mean"),
            pl.col("top_abs_ret").std().alias("top_abs_ret_std"),
            (pl.col("top_abs_ret") > 0).mean().alias("top_abs_ret_positive_ratio"),
            pl.col("top_excess_ret").mean().alias("top_excess_ret_mean"),
            pl.col("top_excess_ret").std().alias("top_excess_ret_std"),
            (pl.col("top_excess_ret") > 0).mean().alias("top_excess_ret_positive_ratio"),
            pl.col("top_minus_bottom_excess").mean().alias("top_minus_bottom_excess_mean"),
            pl.col("top_minus_bottom_excess").std().alias("top_minus_bottom_excess_std"),
            (pl.col("top_minus_bottom_excess") > 0).mean().alias("top_minus_bottom_excess_positive_ratio"),
            pl.col("benchmark_forward_ret").mean().alias("benchmark_forward_ret_mean"),
            pl.col("benchmark_past_ret").mean().alias("benchmark_past_ret_mean"),
        )
        .filter(pl.col("days") >= MIN_SUMMARY_DAYS)
        .with_columns(
            t_stat_expr("top_abs_ret_mean", "top_abs_ret_std", "days").alias("top_abs_ret_t"),
            t_stat_expr("top_excess_ret_mean", "top_excess_ret_std", "days").alias("top_excess_ret_t"),
            t_stat_expr(
                "top_minus_bottom_excess_mean", "top_minus_bottom_excess_std", "days"
            ).alias("top_minus_bottom_excess_t"),
        )
        .drop(["top_abs_ret_std", "top_excess_ret_std", "top_minus_bottom_excess_std"])
    )
    for cost_bps in COST_BPS:
        cost_return = cost_bps / 10000.0
        summary = summary.with_columns((pl.col("top_abs_ret_mean") - cost_return).alias(f"net_top_abs_ret_{int(cost_bps)}bps"))
    return summary


def build_stability(year_df: pl.DataFrame) -> pl.DataFrame:
    if year_df.is_empty():
        return pl.DataFrame()
    return (
        year_df.group_by(["bucket", "lookback", "horizon", "signal_variant"])
        .agg(
            pl.len().alias("year_count"),
            (pl.col("top_abs_ret_mean") > 0).sum().alias("positive_abs_year_count"),
            (pl.col("top_excess_ret_mean") > 0).sum().alias("positive_excess_year_count"),
            (pl.col("top_minus_bottom_excess_mean") > 0).sum().alias("positive_spread_year_count"),
            pl.col("top_abs_ret_mean").min().alias("min_year_top_abs_ret"),
            pl.col("top_abs_ret_mean").median().alias("median_year_top_abs_ret"),
            pl.col("top_excess_ret_mean").median().alias("median_year_top_excess_ret"),
            pl.col("top_minus_bottom_excess_mean").median().alias("median_year_spread"),
        )
        .with_columns(
            (pl.col("positive_abs_year_count") / pl.col("year_count")).alias("positive_abs_year_ratio"),
            (pl.col("positive_excess_year_count") / pl.col("year_count")).alias("positive_excess_year_ratio"),
            (pl.col("positive_spread_year_count") / pl.col("year_count")).alias("positive_spread_year_ratio"),
        )
        .sort(["bucket", "lookback", "horizon", "signal_variant"])
    )


def build_variant_delta(summary_df: pl.DataFrame) -> pl.DataFrame:
    if summary_df.is_empty():
        return pl.DataFrame()
    keys = ["bucket", "lookback", "horizon"]
    base = (
        summary_df.filter(pl.col("signal_variant") == "raw_global")
        .select(
            [
                *keys,
                pl.col("top_abs_ret_mean").alias("base_top_abs_ret_mean"),
                pl.col("top_excess_ret_mean").alias("base_top_excess_ret_mean"),
                pl.col("top_minus_bottom_excess_mean").alias("base_spread_mean"),
            ]
        )
    )
    return (
        summary_df.join(base, on=keys, how="left")
        .with_columns(
            (pl.col("top_abs_ret_mean") - pl.col("base_top_abs_ret_mean")).alias("delta_top_abs_vs_raw"),
            (pl.col("top_excess_ret_mean") - pl.col("base_top_excess_ret_mean")).alias(
                "delta_top_excess_vs_raw"
            ),
            (pl.col("top_minus_bottom_excess_mean") - pl.col("base_spread_mean")).alias("delta_spread_vs_raw"),
        )
        .drop(["base_top_abs_ret_mean", "base_top_excess_ret_mean", "base_spread_mean"])
        .sort(keys + ["signal_variant"])
    )


def top_focus_rows(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty():
        return frame
    return frame.filter((pl.col("bucket") == "active_q4_q5") & (pl.col("lookback") == 20) & (pl.col("horizon") == 10))


def write_report(
    summary_df: pl.DataFrame,
    year_df: pl.DataFrame,
    state_df: pl.DataFrame,
    stability_df: pl.DataFrame,
    delta_df: pl.DataFrame,
    industry_df: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    focus = top_focus_rows(delta_df).sort("signal_variant")
    all_focus = (
        delta_df.filter((pl.col("bucket") == "all_component") & (pl.col("lookback") == 20) & (pl.col("horizon") == 10))
        .sort("signal_variant")
        if not delta_df.is_empty()
        else pl.DataFrame()
    )
    focus_year = top_focus_rows(year_df).sort(["signal_variant", "year"])
    focus_stability = top_focus_rows(stability_df).sort("signal_variant")
    all_stability = (
        stability_df.filter((pl.col("bucket") == "all_component") & (pl.col("lookback") == 20) & (pl.col("horizon") == 10))
        .sort("signal_variant")
        if not stability_df.is_empty()
        else pl.DataFrame()
    )
    focus_industry = (
        industry_df.filter((pl.col("bucket") == "active_q4_q5") & (pl.col("lookback") == 20) & (pl.col("horizon") == 10))
        .sort("top_stock_rows", descending=True)
        .head(12)
        if not industry_df.is_empty()
        else pl.DataFrame()
    )

    lines = [
        "# 股票震荡残差/行业内信号归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：信号层归因，不是组合回测，不是正式交易版本。",
        "",
        "## 已记录的策略思路",
        "",
        "- 参考业界短期反转、残差统计套利、行业内反转和流动性冲击修复思想。",
        "- A股第一版不做多空对称，也不做配对交易，优先做long-only横截面超跌修复。",
        "- 核心问题从“谁跌得最多”推进到“谁相对行业/同类资产跌过头”。",
        "- 状态过滤必须是反证式、少参数、外生变量；不能为了躲开2022而写年份适配器。",
        "",
        "## 方法",
        "",
        f"- 样本：`{meta['date_min']}`到`{meta['date_max']}`，`{meta['symbol_count']}`只股票，`{meta['row_count']:,}`行。",
        "- 观察层：`all_component`和`active_q4_q5`。",
        "- 比较四类信号：`raw_global`、`market_residual_global`、`industry_residual_global`、`industry_neutral_raw`。",
        "- 重点观察：`active_q4_q5 + 20日回看 + 10日前瞻`。",
        "- 成本压力只做`20bp/50bp`静态扣减，不作为优化参数。",
        "",
        "## 重点结果：active_q4_q5 / lookback20 / horizon10",
        "",
    ]

    for row in focus.iter_rows(named=True):
        lines.append(
            f"- `{row['signal_variant']}`：days `{row['days']}`，top绝对 `{pct(row['top_abs_ret_mean'])}`，"
            f"top超额 `{pct(row['top_excess_ret_mean'])}`，top-bottom超额 `{pct(row['top_minus_bottom_excess_mean'])}`，"
            f"t `{row['top_minus_bottom_excess_t']:.2f}`，20bp后top绝对 `{pct(row['net_top_abs_ret_20bps'])}`，"
            f"50bp后top绝对 `{pct(row['net_top_abs_ret_50bps'])}`，平均top股票 `{row['avg_top_stock_count']:.1f}`，"
            f"平均top行业 `{row['avg_top_industry_count']:.1f}`，相对raw top绝对变化 `{pct(row['delta_top_abs_vs_raw'])}`。"
        )

    lines.extend(["", "## 对照结果：all_component / lookback20 / horizon10", ""])
    for row in all_focus.iter_rows(named=True):
        lines.append(
            f"- `{row['signal_variant']}`：days `{row['days']}`，top绝对 `{pct(row['top_abs_ret_mean'])}`，"
            f"top超额 `{pct(row['top_excess_ret_mean'])}`，top-bottom超额 `{pct(row['top_minus_bottom_excess_mean'])}`，"
            f"t `{row['top_minus_bottom_excess_t']:.2f}`，20bp后top绝对 `{pct(row['net_top_abs_ret_20bps'])}`，"
            f"50bp后top绝对 `{pct(row['net_top_abs_ret_50bps'])}`，平均top股票 `{row['avg_top_stock_count']:.1f}`，"
            f"平均top行业 `{row['avg_top_industry_count']:.1f}`。"
        )

    lines.extend(["", "## 年度稳定性", ""])
    for row in focus_stability.iter_rows(named=True):
        lines.append(
            f"- `{row['signal_variant']}`：top绝对正收益年份 `{row['positive_abs_year_count']}/{row['year_count']}`，"
            f"top超额正年份 `{row['positive_excess_year_count']}/{row['year_count']}`，"
            f"年度top绝对中位 `{pct(row['median_year_top_abs_ret'])}`，最差年份 `{pct(row['min_year_top_abs_ret'])}`。"
        )
    lines.extend(["", "## all_component年度稳定性对照", ""])
    for row in all_stability.iter_rows(named=True):
        lines.append(
            f"- `{row['signal_variant']}`：top绝对正收益年份 `{row['positive_abs_year_count']}/{row['year_count']}`，"
            f"top超额正年份 `{row['positive_excess_year_count']}/{row['year_count']}`，"
            f"年度top绝对中位 `{pct(row['median_year_top_abs_ret'])}`，最差年份 `{pct(row['min_year_top_abs_ret'])}`。"
        )

    lines.extend(["", "## 年度明细", ""])
    for row in focus_year.iter_rows(named=True):
        lines.append(
            f"- `{int(row['year'])}` `{row['signal_variant']}`：top绝对 `{pct(row['top_abs_ret_mean'])}`，"
            f"top超额 `{pct(row['top_excess_ret_mean'])}`，spread `{pct(row['top_minus_bottom_excess_mean'])}`。"
        )

    lines.extend(["", "## top组行业分布提示", ""])
    for row in focus_industry.iter_rows(named=True):
        industry = row["industry"] if row["industry"] is not None else "unknown"
        lines.append(
            f"- `{row['signal_variant']}` `{industry}`：top行数 `{row['top_stock_rows']}`，"
            f"top绝对 `{pct(row['top_abs_ret_mean'])}`，top超额 `{pct(row['top_excess_ret_mean'])}`。"
        )

    lines.extend(
        [
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只把既有裸超跌拆成市场残差、行业残差和行业内排序；不新增交易规则，不扫阈值，不选择正式参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：保留全部四类信号和年度明细；如果行业残差不优于raw，也直接记录反证，不把结果包装成新策略。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：独立股市震荡策略的第一性原理不是裸抄底，而是识别同类资产里的流动性错杀；残差/行业内归因是进入组合回测前的必要门槛。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是，但下一步必须先做分散度/行业上限约束，再做组合路径。",
            "- 原因：`industry_neutral_raw`在全成分口径更分散且收益高于raw；在`active_q4_q5`口径更厚，但平均top行业只有约2个，行业集中度过高。真正可穿越周期的方向不是直接追active高收益，而是把行业内排序与流动性下限、行业上限和容量约束结合。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
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
    bm_past = build_benchmark_past_returns(benchmark_df)
    df = (
        add_forward_returns(add_price_features(stock_df), benchmark_df)
        .join(bm_past.select(["datetime", "bm_ret_5", "bm_ret_10"]), on="datetime", how="left")
        .join(layer_tags, on=["datetime", "symbol"], how="left")
    )
    df = add_peer_residual_features(df)
    daily_df, industry_df = build_daily_series(df)
    summary_df = summarize_daily(daily_df, ["bucket", "lookback", "horizon", "signal_variant", "ranking_scope"])
    year_df = summarize_daily(
        daily_df.with_columns(pl.col("datetime").dt.year().alias("year")),
        ["year", "bucket", "lookback", "horizon", "signal_variant", "ranking_scope"],
    )
    state_df = summarize_daily(
        daily_df, ["market_state_20d", "bucket", "lookback", "horizon", "signal_variant", "ranking_scope"]
    )
    stability_df = build_stability(year_df)
    delta_df = build_variant_delta(summary_df)

    if not industry_df.is_empty():
        industry_df = industry_df.sort(["bucket", "lookback", "horizon", "signal_variant", "top_stock_rows"], descending=[False, False, False, False, True])

    meta: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "row_count": df.height,
        "symbol_count": df["symbol"].n_unique(),
        "date_min": str(df["datetime"].min()),
        "date_max": str(df["datetime"].max()),
        "lookbacks": LOOKBACKS,
        "horizons": HORIZONS,
        "cost_bps": COST_BPS,
        "min_global_daily_width": MIN_GLOBAL_DAILY_WIDTH,
        "min_industry_daily_width": MIN_INDUSTRY_DAILY_WIDTH,
        "min_summary_days": MIN_SUMMARY_DAYS,
        "method": "raw_vs_market_residual_vs_industry_residual_signal_attribution",
    }

    daily_path = OUTPUT_DIR / f"{PREFIX}_daily_series.csv"
    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    delta_path = OUTPUT_DIR / f"{PREFIX}_delta_vs_raw.csv"
    year_path = OUTPUT_DIR / f"{PREFIX}_year_summary.csv"
    state_path = OUTPUT_DIR / f"{PREFIX}_state_summary.csv"
    stability_path = OUTPUT_DIR / f"{PREFIX}_stability.csv"
    industry_path = OUTPUT_DIR / f"{PREFIX}_top_industry.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    daily_df.write_csv(daily_path)
    summary_df.write_csv(summary_path)
    delta_df.write_csv(delta_path)
    year_df.write_csv(year_path)
    state_df.write_csv(state_path)
    stability_df.write_csv(stability_path)
    industry_df.write_csv(industry_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        year_df,
        state_df,
        stability_df,
        delta_df,
        industry_df,
        meta,
        {
            "daily_series": daily_path,
            "summary": summary_path,
            "delta_vs_raw": delta_path,
            "year_summary": year_path,
            "state_summary": state_path,
            "stability": stability_path,
            "top_industry": industry_path,
            "meta": meta_path,
        },
    )
    print(f"output_dir={OUTPUT_DIR}")
    print(f"report={report_path}")
    print(top_focus_rows(delta_df).sort("signal_variant"))


if __name__ == "__main__":
    main()
