from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import (
    MIN_LAYER_DAILY_WIDTH,
    MIN_LAYER_DAYS,
    load_layer_tags,
    load_panels,
)
from analyze_stock_range_reversion_signal_attribution import (
    N_GROUPS,
    add_forward_returns,
    add_price_features,
)


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_active_bucket_stability_2018_2026"),
    )
).expanduser().resolve()

FEATURES: tuple[str, ...] = tuple(
    item.strip()
    for item in os.getenv(
        "FEATURES",
        "score_oversold_ret_5,score_oversold_ret_10,score_oversold_ret_20",
    ).split(",")
    if item.strip()
)
HORIZONS: tuple[int, ...] = tuple(int(item) for item in os.getenv("HORIZONS", "5,10").split(",") if item.strip())
PREFIX: str = "stock_range_reversion_active_bucket_stability_v1"


def finite_signal_filter(feature: str, horizon: int) -> pl.Expr:
    """Return base valid-row filter for one feature/horizon."""
    label_col = f"fwd_excess_ret_{horizon}"
    return (
        pl.col(f"final_keep_{horizon}")
        & pl.col(feature).is_not_null()
        & pl.col(feature).is_finite()
        & pl.col(label_col).is_not_null()
        & pl.col(label_col).is_finite()
    )


def add_groups(work: pl.DataFrame, feature: str, partition_cols: list[str]) -> pl.DataFrame:
    """Assign feature quintile groups inside date plus optional layer partitions."""
    over_cols = ["datetime", *partition_cols]
    return (
        work.with_columns(
            pl.col(feature).rank("ordinal").over(over_cols).alias("_rank"),
            pl.len().over(over_cols).alias("_n"),
        )
        .filter(pl.col("_n") >= MIN_LAYER_DAILY_WIDTH)
        .with_columns(
            ((((pl.col("_rank") - 1) * N_GROUPS) / pl.col("_n")).floor().cast(pl.Int64) + 1)
            .clip(1, N_GROUPS)
            .alias("feature_group")
        )
        .drop("_rank")
    )


def long_short_series(
    work: pl.DataFrame,
    feature: str,
    horizon: int,
    partition_cols: list[str] | None = None,
) -> pl.DataFrame:
    """Return top-minus-bottom daily series for one feature/horizon and optional partitions."""
    partition_cols = partition_cols or []
    label_col = f"fwd_excess_ret_{horizon}"
    grouped = (
        add_groups(work, feature, partition_cols)
        .group_by(["datetime", *partition_cols, "feature_group"])
        .agg(
            pl.col(label_col).mean().alias("group_excess_ret"),
            pl.len().alias("stock_count"),
            pl.first("_n").alias("_n"),
        )
    )
    key_cols = ["datetime", *partition_cols]
    top_df = grouped.filter(pl.col("feature_group") == N_GROUPS).select(
        [*key_cols, pl.col("group_excess_ret").alias("top_ret"), pl.col("stock_count").alias("top_count"), "_n"]
    )
    bottom_df = grouped.filter(pl.col("feature_group") == 1).select(
        [*key_cols, pl.col("group_excess_ret").alias("bottom_ret"), pl.col("stock_count").alias("bottom_count")]
    )
    return (
        top_df.join(bottom_df, on=key_cols, how="inner")
        .with_columns((pl.col("top_ret") - pl.col("bottom_ret")).alias("top_minus_bottom"))
        .sort(key_cols)
    )


def add_t_stat(df: pl.DataFrame) -> pl.DataFrame:
    """Add t-stat from mean/std/days columns."""
    return df.with_columns(
        pl.when((pl.col("top_minus_bottom_std").is_not_null()) & (pl.col("top_minus_bottom_std") > 0))
        .then(pl.col("top_minus_bottom_mean") / (pl.col("top_minus_bottom_std") / pl.col("days").sqrt()))
        .otherwise(0.0)
        .alias("top_minus_bottom_t")
    )


def summarize_ls(ls_df: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Summarize a long-short series by keys."""
    if ls_df.is_empty():
        return pl.DataFrame()
    return add_t_stat(
        ls_df.group_by(keys)
        .agg(
            pl.len().alias("days"),
            pl.col("_n").mean().alias("avg_daily_width"),
            pl.col("top_ret").mean().alias("top_mean"),
            pl.col("bottom_ret").mean().alias("bottom_mean"),
            pl.col("top_minus_bottom").mean().alias("top_minus_bottom_mean"),
            pl.col("top_minus_bottom").std().alias("top_minus_bottom_std"),
            (pl.col("top_minus_bottom") > 0).mean().alias("top_minus_bottom_positive_ratio"),
        )
        .filter(pl.col("days") >= MIN_LAYER_DAYS)
    ).drop("top_minus_bottom_std")


def summarize_year_ls(ls_df: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Summarize a long-short series by year and keys."""
    if ls_df.is_empty():
        return pl.DataFrame()
    return add_t_stat(
        ls_df.with_columns(pl.col("datetime").dt.year().alias("year"))
        .group_by(["year", *keys])
        .agg(
            pl.len().alias("days"),
            pl.col("_n").mean().alias("avg_daily_width"),
            pl.col("top_minus_bottom").mean().alias("top_minus_bottom_mean"),
            pl.col("top_minus_bottom").std().alias("top_minus_bottom_std"),
            (pl.col("top_minus_bottom") > 0).mean().alias("top_minus_bottom_positive_ratio"),
        )
        .filter(pl.col("days") >= 20)
    ).drop("top_minus_bottom_std")


def active_bucket_definitions() -> list[tuple[str, str, pl.Expr]]:
    """Return active bucket definitions used for stability checks."""
    return [
        ("turnover_f_q5", "自由换手最高20%", pl.col("turnover_rate_f_q") == 5),
        ("adv20_turnover_q5", "20日成交额最高20%", pl.col("adv20_turnover_q") == 5),
        (
            "dual_turnover_q5",
            "自由换手和20日成交额同时最高20%",
            (pl.col("turnover_rate_f_q") == 5) & (pl.col("adv20_turnover_q") == 5),
        ),
        (
            "active_q4_q5",
            "自由换手和20日成交额都在前40%",
            (pl.col("turnover_rate_f_q") >= 4) & (pl.col("adv20_turnover_q") >= 4),
        ),
    ]


def evaluate_active_buckets(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Evaluate high-activity buckets across years."""
    summary_frames: list[pl.DataFrame] = []
    year_frames: list[pl.DataFrame] = []

    for bucket, description, expr in active_bucket_definitions():
        for feature in FEATURES:
            for horizon in HORIZONS:
                work = df.filter(expr & finite_signal_filter(feature, horizon))
                if work.is_empty():
                    continue
                ls_df = long_short_series(work, feature, horizon)
                summary = summarize_ls(ls_df, [])
                if not summary.is_empty():
                    summary_frames.append(
                        summary.with_columns(
                            pl.lit(bucket).alias("bucket"),
                            pl.lit(description).alias("bucket_description"),
                            pl.lit(feature).alias("feature"),
                            pl.lit(horizon).alias("horizon"),
                        )
                    )
                year_summary = summarize_year_ls(ls_df, [])
                if not year_summary.is_empty():
                    year_frames.append(
                        year_summary.with_columns(
                            pl.lit(bucket).alias("bucket"),
                            pl.lit(description).alias("bucket_description"),
                            pl.lit(feature).alias("feature"),
                            pl.lit(horizon).alias("horizon"),
                        )
                    )

    return (
        pl.concat(summary_frames, how="vertical") if summary_frames else pl.DataFrame(),
        pl.concat(year_frames, how="vertical") if year_frames else pl.DataFrame(),
    )


def evaluate_cross_layers(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Evaluate market x size cross layers and active-bucket industry layers."""
    df = df.with_columns(
        pl.when(pl.col("market").is_not_null() & pl.col("circ_mv_q").is_not_null())
        .then(pl.concat_str([pl.col("market"), pl.lit("_circ_mv_q"), pl.col("circ_mv_q").cast(pl.String)]))
        .otherwise(None)
        .alias("market_circ_mv_q")
    )

    cross_frames: list[pl.DataFrame] = []
    industry_frames: list[pl.DataFrame] = []
    industry_expr = pl.col("turnover_rate_f_q") == 5

    for feature in FEATURES:
        for horizon in HORIZONS:
            cross_work = df.filter(pl.col("market_circ_mv_q").is_not_null() & finite_signal_filter(feature, horizon))
            if not cross_work.is_empty():
                ls_df = long_short_series(cross_work, feature, horizon, ["market_circ_mv_q"])
                summary = summarize_ls(ls_df, ["market_circ_mv_q"])
                if not summary.is_empty():
                    cross_frames.append(
                        summary.with_columns(
                            pl.lit(feature).alias("feature"),
                            pl.lit(horizon).alias("horizon"),
                            pl.col("market_circ_mv_q").alias("layer_value"),
                            pl.lit("market_circ_mv_q").alias("layer"),
                        ).drop("market_circ_mv_q")
                    )

            industry_work = df.filter(
                industry_expr & pl.col("industry").is_not_null() & finite_signal_filter(feature, horizon)
            )
            if not industry_work.is_empty():
                ls_df = long_short_series(industry_work, feature, horizon, ["industry"])
                summary = summarize_ls(ls_df, ["industry"])
                if not summary.is_empty():
                    industry_frames.append(
                        summary.with_columns(
                            pl.lit("turnover_f_q5").alias("bucket"),
                            pl.lit(feature).alias("feature"),
                            pl.lit(horizon).alias("horizon"),
                            pl.col("industry").alias("industry"),
                        )
                    )

    return (
        pl.concat(cross_frames, how="vertical") if cross_frames else pl.DataFrame(),
        pl.concat(industry_frames, how="vertical") if industry_frames else pl.DataFrame(),
    )


def build_stability_table(year_df: pl.DataFrame) -> pl.DataFrame:
    """Condense yearly results into stability metrics."""
    if year_df.is_empty():
        return pl.DataFrame()
    return (
        year_df.group_by(["bucket", "bucket_description", "feature", "horizon"])
        .agg(
            pl.len().alias("year_count"),
            (pl.col("top_minus_bottom_mean") > 0).sum().alias("positive_year_count"),
            pl.col("top_minus_bottom_mean").min().alias("min_year_top_minus_bottom"),
            pl.col("top_minus_bottom_mean").median().alias("median_year_top_minus_bottom"),
            pl.col("top_minus_bottom_mean").mean().alias("mean_year_top_minus_bottom"),
            pl.col("top_minus_bottom_positive_ratio").mean().alias("mean_positive_day_ratio"),
        )
        .with_columns((pl.col("positive_year_count") / pl.col("year_count")).alias("positive_year_ratio"))
        .sort(["feature", "horizon", "bucket"])
    )


def write_report(
    summary_df: pl.DataFrame,
    year_df: pl.DataFrame,
    stability_df: pl.DataFrame,
    cross_df: pl.DataFrame,
    industry_df: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    """Write a Chinese active-bucket stability report."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡高活跃桶稳定性归因 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是股票组合回测，也没有新增交易规则；只检验高换手/高成交活跃分层里的固定超跌信号是否逐年稳定。",
        f"- 样本：`{meta['date_min']}`到`{meta['date_max']}`，`{meta['symbol_count']}`只股票，`{meta['row_count']:,}`行。",
        "",
        "## 高活跃桶年度稳定性",
        "",
    ]

    focus = stability_df.filter(
        pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"]) & (pl.col("horizon") == 10)
    ).sort(["feature", "bucket"])
    for row in focus.iter_rows(named=True):
        lines.append(
            f"- `{row['feature']}`/`10日` `{row['bucket']}`：正收益年份 `{row['positive_year_count']}/{row['year_count']}`，"
            f"年度中位 top-bottom `{row['median_year_top_minus_bottom']:.4%}`，最差年份 `{row['min_year_top_minus_bottom']:.4%}`。"
        )

    latest = year_df.filter(
        (pl.col("year") >= 2024)
        & pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"])
        & (pl.col("horizon") == 10)
    ).sort(["feature", "bucket", "year"])
    lines.extend(["", "## 近端年份", ""])
    for row in latest.iter_rows(named=True):
        lines.append(
            f"- `{row['year']}` `{row['feature']}` `{row['bucket']}`：top-bottom `{row['top_minus_bottom_mean']:.4%}`，"
            f"t `{row['top_minus_bottom_t']:.2f}`，days `{row['days']}`。"
        )

    cross_focus = cross_df.filter(
        pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"]) & (pl.col("horizon") == 10)
    ).sort("top_minus_bottom_mean", descending=True).head(15)
    lines.extend(["", "## 市场板块 x 流通市值", ""])
    for row in cross_focus.iter_rows(named=True):
        lines.append(
            f"- `{row['feature']}` `{row['layer_value']}`：top-bottom `{row['top_minus_bottom_mean']:.4%}`，"
            f"t `{row['top_minus_bottom_t']:.2f}`，days `{row['days']}`。"
        )

    industry_focus = industry_df.filter(
        pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"]) & (pl.col("horizon") == 10)
    ).sort("top_minus_bottom_mean", descending=True).head(15)
    lines.extend(["", "## 高自由换手桶行业集中度", ""])
    for row in industry_focus.iter_rows(named=True):
        lines.append(
            f"- `{row['feature']}` `{row['industry']}`：top-bottom `{row['top_minus_bottom_mean']:.4%}`，"
            f"t `{row['top_minus_bottom_t']:.2f}`，days `{row['days']}`。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果高活跃桶在多数年份为正，说明它不是单一年份噪音；如果近端年份也为正，才有资格进入成本/容量约束分析。",
            "- 如果强结果集中在高自由换手桶，后续组合化必须把冲击成本、滑点和成交容量放在前面。",
            "- 这一步仍不触发第78 A/B，也不进入正式股票组合回测。",
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
    """Run active-bucket stability attribution."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    df = add_forward_returns(add_price_features(stock_df), benchmark_df).join(
        layer_tags, on=["datetime", "symbol"], how="left"
    )
    meta: dict[str, Any] = {
        "row_count": df.height,
        "symbol_count": df["symbol"].n_unique(),
        "date_min": str(df["datetime"].min()),
        "date_max": str(df["datetime"].max()),
        "features": FEATURES,
        "horizons": HORIZONS,
        "n_groups": N_GROUPS,
        "min_layer_daily_width": MIN_LAYER_DAILY_WIDTH,
        "min_layer_days": MIN_LAYER_DAYS,
    }

    summary_df, year_df = evaluate_active_buckets(df)
    stability_df = build_stability_table(year_df)
    cross_df, industry_df = evaluate_cross_layers(df)

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    year_path = OUTPUT_DIR / f"{PREFIX}_year_summary.csv"
    stability_path = OUTPUT_DIR / f"{PREFIX}_stability.csv"
    cross_path = OUTPUT_DIR / f"{PREFIX}_market_size_cross.csv"
    industry_path = OUTPUT_DIR / f"{PREFIX}_active_industry.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    summary_df.write_csv(summary_path)
    year_df.write_csv(year_path)
    stability_df.write_csv(stability_path)
    cross_df.write_csv(cross_path)
    industry_df.write_csv(industry_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        year_df,
        stability_df,
        cross_df,
        industry_df,
        meta,
        {
            "summary": summary_path,
            "year_summary": year_path,
            "stability": stability_path,
            "market_size_cross": cross_path,
            "active_industry": industry_path,
            "meta": meta_path,
        },
    )
    print(stability_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
