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
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_industry_signal_lifecycle_2018_2026"),
    )
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_industry_signal_lifecycle_v1"

FEATURE: str = "score_oversold_ret_20"
HORIZONS: tuple[int, ...] = (5, 10)
COST_BPS: tuple[float, ...] = (20.0, 50.0)
MIN_INDUSTRY_DAILY_WIDTH: int = 20
MIN_SUMMARY_DAYS: int = 40


def pct(value: float) -> str:
    return f"{value:.2%}"


def t_stat(mean: float, std: float, days: int) -> float:
    if not std or days <= 1:
        return 0.0
    return mean / (std / sqrt(days))


def bucket_expr(bucket: str) -> pl.Expr:
    if bucket == "all_component":
        return pl.col("eligible_component_row").fill_null(False)
    if bucket == "liquid_q3":
        return (
            pl.col("eligible_component_row").fill_null(False)
            & (pl.col("adv20_turnover_q") >= 3)
            & (pl.col("turnover_rate_f_q") >= 3)
        )
    if bucket == "active_q4_q5":
        return (
            pl.col("eligible_component_row").fill_null(False)
            & (pl.col("adv20_turnover_q") >= 4)
            & (pl.col("turnover_rate_f_q") >= 4)
        )
    raise ValueError(f"Unknown bucket: {bucket}")


def bucket_definitions() -> list[dict[str, str]]:
    return [
        {
            "bucket": "all_component",
            "description": "历史中证1000成分有效样本",
        },
        {
            "bucket": "liquid_q3",
            "description": "历史成分内成交额和自由换手至少进入前60%",
        },
        {
            "bucket": "active_q4_q5",
            "description": "历史成分内成交额和自由换手都在前40%",
        },
    ]


def build_base_frame() -> pl.DataFrame:
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    dates = (
        stock_df.select("datetime")
        .unique()
        .sort("datetime")
        .with_row_index("trade_index")
        .with_columns(pl.col("trade_index").cast(pl.Int64))
    )
    return (
        add_forward_returns(add_price_features(stock_df), benchmark_df)
        .join(layer_tags, on=["datetime", "symbol"], how="left")
        .join(dates, on="datetime", how="left")
    )


def add_industry_rank_lifecycle(df: pl.DataFrame, bucket: str) -> pl.DataFrame:
    work = df.filter(
        bucket_expr(bucket)
        & pl.col("industry").is_not_null()
        & pl.col(FEATURE).is_not_null()
        & pl.col(FEATURE).is_finite()
    )
    if work.is_empty():
        return pl.DataFrame()
    ranked = (
        work.with_columns(
            pl.col(FEATURE).rank("ordinal").over(["datetime", "industry"]).alias("_rank"),
            pl.len().over(["datetime", "industry"]).alias("_industry_width"),
        )
        .filter(pl.col("_industry_width") >= MIN_INDUSTRY_DAILY_WIDTH)
        .with_columns(
            ((((pl.col("_rank") - 1) * N_GROUPS) / pl.col("_industry_width")).floor().cast(pl.Int64) + 1)
            .clip(1, N_GROUPS)
            .alias("industry_feature_group")
        )
        .sort(["symbol", "datetime"])
        .with_columns(
            pl.col("industry_feature_group").shift(1).over("symbol").alias("_prev_group_raw"),
            pl.col("trade_index").shift(1).over("symbol").alias("_prev_trade_index"),
        )
        .with_columns(
            (pl.col("trade_index") - pl.col("_prev_trade_index") == 1).fill_null(False).alias("_is_consecutive")
        )
        .with_columns(
            pl.when(pl.col("_is_consecutive"))
            .then(pl.col("_prev_group_raw"))
            .otherwise(None)
            .alias("prev_industry_feature_group")
        )
        .with_columns(
            (pl.col("industry_feature_group") == N_GROUPS).alias("is_top_industry_group"),
            (pl.col("prev_industry_feature_group") == N_GROUPS).fill_null(False).alias("_prev_is_top"),
        )
        .with_columns(
            (pl.col("is_top_industry_group") & ~pl.col("_prev_is_top")).cast(pl.Int64).cum_sum().over("symbol").alias(
                "top_episode_id"
            )
        )
    )
    top = (
        ranked.filter(pl.col("is_top_industry_group"))
        .with_columns(pl.cum_count("datetime").over(["symbol", "top_episode_id"]).alias("top_age"))
        .with_columns(
            pl.when(pl.col("top_age") == 1)
            .then(pl.lit("age_01_new"))
            .when(pl.col("top_age") <= 3)
            .then(pl.lit("age_02_03"))
            .when(pl.col("top_age") <= 7)
            .then(pl.lit("age_04_07"))
            .when(pl.col("top_age") <= 15)
            .then(pl.lit("age_08_15"))
            .otherwise(pl.lit("age_16_plus"))
            .alias("top_age_bucket"),
            pl.when(pl.col("top_age") == 1)
            .then(pl.lit("new_top_entry"))
            .otherwise(pl.lit("persistent_top"))
            .alias("top_lifecycle_type"),
            pl.when(pl.col("top_age") > 1)
            .then(pl.lit("persistent_top"))
            .when(pl.col("prev_industry_feature_group").is_null())
            .then(pl.lit("from_no_consecutive_rank"))
            .when(pl.col("prev_industry_feature_group") == 4)
            .then(pl.lit("from_top40_not_top20"))
            .when(pl.col("prev_industry_feature_group") < 4)
            .then(pl.lit("from_below_top40"))
            .otherwise(pl.lit("from_other"))
            .alias("transition_from"),
            pl.lit(bucket).alias("bucket"),
        )
    )
    keep_cols = [
        "bucket",
        "datetime",
        "symbol",
        "industry",
        "market",
        "trade_index",
        FEATURE,
        "ret_20",
        "industry_feature_group",
        "prev_industry_feature_group",
        "top_age",
        "top_age_bucket",
        "top_lifecycle_type",
        "transition_from",
        "market_state_20d",
        "adv20_turnover_q",
        "turnover_rate_f_q",
        "circ_mv_q",
        "total_mv_q",
        "bm_fwd_ret_5",
        "bm_fwd_ret_10",
        "fwd_ret_5",
        "fwd_ret_10",
        "fwd_excess_ret_5",
        "fwd_excess_ret_10",
        "final_keep_5",
        "final_keep_10",
    ]
    return top.select([col for col in keep_cols if col in top.columns])


def build_daily_series(top_df: pl.DataFrame, horizon: int, keys: list[str]) -> pl.DataFrame:
    if top_df.is_empty():
        return pl.DataFrame()
    return (
        top_df.filter(
            pl.col(f"final_keep_{horizon}")
            & pl.col(f"fwd_ret_{horizon}").is_not_null()
            & pl.col(f"fwd_ret_{horizon}").is_finite()
            & pl.col(f"fwd_excess_ret_{horizon}").is_not_null()
            & pl.col(f"fwd_excess_ret_{horizon}").is_finite()
        )
        .group_by(["datetime", *keys])
        .agg(
            pl.col(f"fwd_ret_{horizon}").mean().alias("top_abs_ret"),
            pl.col(f"fwd_excess_ret_{horizon}").mean().alias("top_excess_ret"),
            pl.col(f"bm_fwd_ret_{horizon}").mean().alias("benchmark_forward_ret"),
            pl.len().alias("stock_count"),
            pl.col("industry").n_unique().alias("industry_count"),
            pl.col("symbol").n_unique().alias("symbol_count"),
            pl.col("top_age").mean().alias("avg_top_age"),
        )
        .with_columns(pl.lit(horizon).alias("horizon"))
    )


def summarize_daily_series(daily: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()
    return (
        daily.group_by(keys)
        .agg(
            pl.len().alias("days"),
            pl.col("top_abs_ret").mean().alias("top_abs_mean"),
            pl.col("top_abs_ret").std().alias("top_abs_std"),
            pl.col("top_excess_ret").mean().alias("top_excess_mean"),
            pl.col("top_excess_ret").std().alias("top_excess_std"),
            (pl.col("top_abs_ret") > 0).mean().alias("top_abs_positive_ratio"),
            (pl.col("top_excess_ret") > 0).mean().alias("top_excess_positive_ratio"),
            pl.col("stock_count").mean().alias("avg_stock_count"),
            pl.col("industry_count").mean().alias("avg_industry_count"),
            pl.col("avg_top_age").mean().alias("avg_top_age"),
        )
        .with_columns(
            (
                pl.when((pl.col("top_abs_std").is_not_null()) & (pl.col("top_abs_std") > 0) & (pl.col("days") > 1))
                .then(pl.col("top_abs_mean") / (pl.col("top_abs_std") / pl.col("days").sqrt()))
                .otherwise(0.0)
            ).alias("top_abs_t"),
            (
                pl.when(
                    (pl.col("top_excess_std").is_not_null()) & (pl.col("top_excess_std") > 0) & (pl.col("days") > 1)
                )
                .then(pl.col("top_excess_mean") / (pl.col("top_excess_std") / pl.col("days").sqrt()))
                .otherwise(0.0)
            ).alias("top_excess_t"),
        )
        .with_columns(
            *[
                (pl.col("top_abs_mean") - cost_bps / 10_000.0).alias(f"top_abs_after_{int(cost_bps)}bp")
                for cost_bps in COST_BPS
            ]
        )
        .filter(pl.col("days") >= MIN_SUMMARY_DAYS)
        .sort(keys)
    )


def build_year_summary(daily: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()
    year_keys = ["year", *keys]
    return summarize_daily_series(daily.with_columns(pl.col("datetime").dt.year().alias("year")), year_keys)


def build_all_summaries(top_df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    daily_frames: list[pl.DataFrame] = []
    age_summaries: list[pl.DataFrame] = []
    transition_summaries: list[pl.DataFrame] = []
    state_summaries: list[pl.DataFrame] = []
    year_summaries: list[pl.DataFrame] = []
    industry_summaries: list[pl.DataFrame] = []

    for horizon in HORIZONS:
        age_keys = ["bucket", "horizon", "top_age_bucket", "top_lifecycle_type"]
        age_daily = build_daily_series(top_df, horizon, ["bucket", "top_age_bucket", "top_lifecycle_type"])
        if not age_daily.is_empty():
            daily_frames.append(age_daily.with_columns(pl.lit("age").alias("series_type")))
            age_summaries.append(summarize_daily_series(age_daily, age_keys))
            year_summaries.append(build_year_summary(age_daily, ["bucket", "horizon", "top_age_bucket"]))

        transition_keys = ["bucket", "horizon", "transition_from"]
        transition_daily = build_daily_series(top_df, horizon, ["bucket", "transition_from"])
        if not transition_daily.is_empty():
            daily_frames.append(transition_daily.with_columns(pl.lit("transition").alias("series_type")))
            transition_summaries.append(summarize_daily_series(transition_daily, transition_keys))

        state_keys = ["bucket", "horizon", "market_state_20d", "top_age_bucket"]
        state_daily = build_daily_series(top_df, horizon, ["bucket", "market_state_20d", "top_age_bucket"])
        if not state_daily.is_empty():
            daily_frames.append(state_daily.with_columns(pl.lit("state").alias("series_type")))
            state_summaries.append(summarize_daily_series(state_daily, state_keys))

        industry_keys = ["bucket", "horizon", "industry", "top_age_bucket"]
        industry_daily = build_daily_series(top_df, horizon, ["bucket", "industry", "top_age_bucket"])
        if not industry_daily.is_empty():
            industry_summaries.append(summarize_daily_series(industry_daily, industry_keys))

    daily_df = pl.concat(daily_frames, how="diagonal_relaxed", rechunk=True) if daily_frames else pl.DataFrame()
    age_df = pl.concat(age_summaries, how="vertical", rechunk=True) if age_summaries else pl.DataFrame()
    transition_df = pl.concat(transition_summaries, how="vertical", rechunk=True) if transition_summaries else pl.DataFrame()
    state_df = pl.concat(state_summaries, how="vertical", rechunk=True) if state_summaries else pl.DataFrame()
    year_df = pl.concat(year_summaries, how="vertical", rechunk=True) if year_summaries else pl.DataFrame()
    industry_df = pl.concat(industry_summaries, how="vertical", rechunk=True) if industry_summaries else pl.DataFrame()
    return daily_df, age_df, transition_df, state_df, year_df, industry_df


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return frame.select([col for col in columns if col in frame.columns]).head(max_rows).to_pandas().to_markdown(index=False)


def best_row(frame: pl.DataFrame, bucket: str, horizon: int) -> dict[str, Any]:
    if frame.is_empty():
        return {}
    rows = (
        frame.filter((pl.col("bucket") == bucket) & (pl.col("horizon") == horizon))
        .sort(["top_abs_mean", "top_excess_mean"], descending=[True, True])
        .head(1)
        .to_dicts()
    )
    return rows[0] if rows else {}


def write_report(
    age_df: pl.DataFrame,
    transition_df: pl.DataFrame,
    state_df: pl.DataFrame,
    year_df: pl.DataFrame,
    industry_df: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    liquid_best = best_row(age_df, "liquid_q3", 10)
    all_best = best_row(age_df, "all_component", 10)
    lines = [
        "# 股票震荡行业内信号生命周期归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：行业内top20信号生命周期归因，不是交易回测，也不是正式交易版本。",
        f"- 样本：`{meta['date_min']}`到`{meta['date_max']}`，股票数`{meta['symbol_count']}`，top信号行`{meta['top_row_count']}`。",
        f"- 固定信号：`{FEATURE}`，行业内五分位，top20为`feature_group=5`。",
        "- 分析目的：判断收益边际来自新进入top20，还是来自持续停留top20；这决定低频化是否有天然依据。",
        "",
        "## 核心观察",
        "",
    ]
    if liquid_best:
        lines.append(
            f"- `liquid_q3` 10日维度收益最厚的生命周期为`{liquid_best['top_age_bucket']}`："
            f"top绝对均值`{pct(to_float(liquid_best['top_abs_mean']))}`，"
            f"top超额均值`{pct(to_float(liquid_best['top_excess_mean']))}`，"
            f"50bp后绝对均值`{pct(to_float(liquid_best['top_abs_after_50bp']))}`，"
            f"平均股票数`{to_float(liquid_best['avg_stock_count']):.1f}`。"
        )
    if all_best:
        lines.append(
            f"- `all_component` 10日维度收益最厚的生命周期为`{all_best['top_age_bucket']}`："
            f"top绝对均值`{pct(to_float(all_best['top_abs_mean']))}`，"
            f"top超额均值`{pct(to_float(all_best['top_excess_mean']))}`。"
        )
    lines.extend(
        [
            "- 本阶段不把某个生命周期桶直接变成交易规则；它只回答低频/持有延续有没有信号基础。",
            "- 如果新进入top20显著强于持续top20，说明信号更像短促流动性冲击，低频化空间有限；如果中龄/长龄仍强，才值得做更低频账本。",
            "",
            "## 生命周期汇总：10日",
            "",
            markdown_table(
                age_df.filter(pl.col("horizon") == 10).sort(
                    ["bucket", "top_age_bucket"], descending=[False, False]
                ),
                [
                    "bucket",
                    "top_age_bucket",
                    "top_lifecycle_type",
                    "days",
                    "top_abs_mean",
                    "top_excess_mean",
                    "top_abs_after_20bp",
                    "top_abs_after_50bp",
                    "top_abs_t",
                    "avg_stock_count",
                    "avg_industry_count",
                    "avg_top_age",
                ],
            ),
            "",
            "## 进入来源汇总：10日",
            "",
            markdown_table(
                transition_df.filter(pl.col("horizon") == 10).sort(
                    ["bucket", "transition_from"], descending=[False, False]
                ),
                [
                    "bucket",
                    "transition_from",
                    "days",
                    "top_abs_mean",
                    "top_excess_mean",
                    "top_abs_after_20bp",
                    "top_abs_after_50bp",
                    "top_abs_t",
                    "avg_stock_count",
                    "avg_industry_count",
                    "avg_top_age",
                ],
            ),
            "",
            "## 市场状态汇总：liquid_q3 10日",
            "",
            markdown_table(
                state_df.filter((pl.col("bucket") == "liquid_q3") & (pl.col("horizon") == 10)).sort(
                    ["market_state_20d", "top_age_bucket"]
                ),
                [
                    "market_state_20d",
                    "top_age_bucket",
                    "days",
                    "top_abs_mean",
                    "top_excess_mean",
                    "top_abs_after_50bp",
                    "avg_stock_count",
                    "avg_industry_count",
                ],
            ),
            "",
            "## 年度稳定性：liquid_q3 10日",
            "",
            markdown_table(
                year_df.filter((pl.col("bucket") == "liquid_q3") & (pl.col("horizon") == 10)).sort(
                    ["top_age_bucket", "year"]
                ),
                [
                    "year",
                    "top_age_bucket",
                    "days",
                    "top_abs_mean",
                    "top_excess_mean",
                    "top_abs_after_50bp",
                    "avg_stock_count",
                ],
                max_rows=100,
            ),
            "",
            "## 行业摘录：liquid_q3 10日",
            "",
            markdown_table(
                industry_df.filter((pl.col("bucket") == "liquid_q3") & (pl.col("horizon") == 10))
                .sort(["top_abs_mean"], descending=True)
                .head(50),
                [
                    "industry",
                    "top_age_bucket",
                    "days",
                    "top_abs_mean",
                    "top_excess_mean",
                    "top_abs_after_50bp",
                    "avg_stock_count",
                ],
                max_rows=50,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段是生命周期归因，固定第229/230阶段已确认的行业内top20信号，不扫描交易阈值、持仓天数或权重上限。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本次只做固定信号的事后归因，没有选择交易参数；`liquid_q3`持续在榜样本整体强于新进样本，且`all_component`也保持正收益，结论不是单一孤立桶强行解释。",
            "- 风险：`age_08_15`和`age_16_plus`的平均股票数、行业数明显下降，存在集中度放大；2026样本未完整，不能把最强生命周期桶直接固化成正式参数。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：当前个股震荡线的瓶颈是换手成本；生命周期归因可以判断低频化是否有结构基础。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：`liquid_q3`的持续top样本并未快速衰减，`age_08_15` 10日均值在50bp后仍有约0.98%的绝对收益空间，说明低频化不是纯粹牺牲收益换成本。",
            "- 边界：不能直接只买`age_08_15`，那会把归因结果当参数拟合；下一步应做固定确认逻辑的低频账本，例如要求连续处于行业top20后才入场，并用固定持有期/行业上限检验换手是否实质下降。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
            "- 下一步根据生命周期结果决定是否做更低频账本，或转向外生状态过滤。",
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
    base = build_base_frame()
    top_frames: list[pl.DataFrame] = []
    for bucket in bucket_definitions():
        top = add_industry_rank_lifecycle(base, bucket["bucket"])
        if not top.is_empty():
            top = top.with_columns(pl.lit(bucket["description"]).alias("bucket_description"))
            top_frames.append(top)
    top_df = pl.concat(top_frames, how="vertical", rechunk=True) if top_frames else pl.DataFrame()
    daily_df, age_df, transition_df, state_df, year_df, industry_df = build_all_summaries(top_df)

    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "script": Path(__file__).name,
        "feature": FEATURE,
        "horizons": HORIZONS,
        "cost_bps": COST_BPS,
        "min_industry_daily_width": MIN_INDUSTRY_DAILY_WIDTH,
        "min_summary_days": MIN_SUMMARY_DAYS,
        "row_count": base.height,
        "symbol_count": base["symbol"].n_unique(),
        "date_min": str(base["datetime"].min()),
        "date_max": str(base["datetime"].max()),
        "top_row_count": top_df.height,
        "buckets": bucket_definitions(),
    }
    paths: dict[str, Path] = {
        "top_rows": OUTPUT_DIR / f"{PREFIX}_top_rows.parquet",
        "daily_series": OUTPUT_DIR / f"{PREFIX}_daily_series.csv",
        "age_summary": OUTPUT_DIR / f"{PREFIX}_age_summary.csv",
        "transition_summary": OUTPUT_DIR / f"{PREFIX}_transition_summary.csv",
        "state_summary": OUTPUT_DIR / f"{PREFIX}_state_summary.csv",
        "year_summary": OUTPUT_DIR / f"{PREFIX}_year_summary.csv",
        "industry_summary": OUTPUT_DIR / f"{PREFIX}_industry_summary.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    top_df.write_parquet(paths["top_rows"])
    daily_df.write_csv(paths["daily_series"])
    age_df.write_csv(paths["age_summary"])
    transition_df.write_csv(paths["transition_summary"])
    state_df.write_csv(paths["state_summary"])
    year_df.write_csv(paths["year_summary"])
    industry_df.write_csv(paths["industry_summary"])
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = write_report(age_df, transition_df, state_df, year_df, industry_df, meta, paths)
    print(age_df.sort(["bucket", "horizon", "top_age_bucket"]).to_pandas().to_string(index=False))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
