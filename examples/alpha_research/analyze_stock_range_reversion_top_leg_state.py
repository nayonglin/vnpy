from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_active_bucket_stability import (
    active_bucket_definitions,
    add_groups,
    finite_signal_filter,
)
from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import add_forward_returns, add_price_features


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_top_leg_state_2018_2026"),
    )
).expanduser().resolve()

PREFIX: str = "stock_range_reversion_top_leg_state_v1"
FEATURES: tuple[str, ...] = tuple(
    item.strip()
    for item in os.getenv(
        "FEATURES",
        "score_oversold_ret_5,score_oversold_ret_10,score_oversold_ret_20",
    ).split(",")
    if item.strip()
)
HORIZONS: tuple[int, ...] = tuple(int(item) for item in os.getenv("HORIZONS", "5,10").split(",") if item.strip())
COST_BPS: tuple[float, ...] = tuple(float(item) for item in os.getenv("COST_BPS", "10,20,50,100").split(",") if item.strip())
MIN_STATE_DAYS: int = int(os.getenv("MIN_STATE_DAYS", "40") or 40)


def t_stat(mean: float, std: float | None, n: int) -> float:
    """Return a simple t-stat from a daily mean series."""
    if not std or std <= 0 or n <= 1:
        return 0.0
    return mean / (std / (n**0.5))


def with_market_bands(df: pl.DataFrame) -> pl.DataFrame:
    """Add fixed, ex-ante benchmark state bands and a hindsight diagnostic label."""
    return df.with_columns(
        pl.when(pl.col("bm_ret_20").is_null())
        .then(pl.lit("unknown"))
        .when(pl.col("bm_ret_20") <= -0.08)
        .then(pl.lit("sharp_down_le_-8pct"))
        .when(pl.col("bm_ret_20") <= -0.03)
        .then(pl.lit("down_-8pct_to_-3pct"))
        .when(pl.col("bm_ret_20") < 0.03)
        .then(pl.lit("flat_-3pct_to_3pct"))
        .when(pl.col("bm_ret_20") < 0.08)
        .then(pl.lit("up_3pct_to_8pct"))
        .otherwise(pl.lit("strong_up_ge_8pct"))
        .alias("bm_ret_20_band")
    )


def summarize_daily(daily: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Summarize top-leg daily absolute and excess return series."""
    if daily.is_empty():
        return pl.DataFrame()

    summary = (
        daily.group_by(keys)
        .agg(
            pl.len().alias("days"),
            pl.col("candidate_count").mean().alias("avg_candidate_count"),
            pl.col("candidate_count").median().alias("median_candidate_count"),
            pl.col("gross_top_abs_ret_mean").mean().alias("gross_top_abs_ret_mean"),
            pl.col("gross_top_abs_ret_mean").std().alias("gross_top_abs_ret_std"),
            (pl.col("gross_top_abs_ret_mean") > 0).mean().alias("gross_top_abs_ret_positive_ratio"),
            pl.col("gross_top_excess_mean").mean().alias("gross_top_excess_mean"),
            pl.col("gross_top_excess_mean").std().alias("gross_top_excess_std"),
            (pl.col("gross_top_excess_mean") > 0).mean().alias("gross_top_excess_positive_ratio"),
            pl.col("bm_fwd_ret").mean().alias("benchmark_forward_ret_mean"),
            pl.col("bm_ret_20").mean().alias("benchmark_past_20d_ret_mean"),
        )
        .filter(pl.col("days") >= MIN_STATE_DAYS)
        .with_columns(
            pl.when((pl.col("gross_top_abs_ret_std").is_not_null()) & (pl.col("gross_top_abs_ret_std") > 0))
            .then(pl.col("gross_top_abs_ret_mean") / (pl.col("gross_top_abs_ret_std") / pl.col("days").sqrt()))
            .otherwise(0.0)
            .alias("gross_top_abs_ret_t"),
            pl.when((pl.col("gross_top_excess_std").is_not_null()) & (pl.col("gross_top_excess_std") > 0))
            .then(pl.col("gross_top_excess_mean") / (pl.col("gross_top_excess_std") / pl.col("days").sqrt()))
            .otherwise(0.0)
            .alias("gross_top_excess_t"),
        )
        .drop(["gross_top_abs_ret_std", "gross_top_excess_std"])
    )
    return summary


def summarize_cost(daily: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Summarize top-leg net returns under fixed roundtrip cost scenarios."""
    frames: list[pl.DataFrame] = []
    for cost_bps in COST_BPS:
        cost_return = cost_bps / 10000.0
        net = daily.with_columns(
            (pl.col("gross_top_abs_ret_mean") - cost_return).alias("net_top_abs_ret_mean"),
            (pl.col("gross_top_excess_mean") - cost_return).alias("net_top_excess_mean"),
        )
        summary = (
            net.group_by(keys)
            .agg(
                pl.len().alias("days"),
                pl.col("net_top_abs_ret_mean").mean().alias("net_top_abs_ret_mean"),
                pl.col("net_top_abs_ret_mean").std().alias("net_top_abs_ret_std"),
                (pl.col("net_top_abs_ret_mean") > 0).mean().alias("net_top_abs_ret_positive_ratio"),
                pl.col("net_top_excess_mean").mean().alias("net_top_excess_mean"),
                pl.col("net_top_excess_mean").std().alias("net_top_excess_std"),
                (pl.col("net_top_excess_mean") > 0).mean().alias("net_top_excess_positive_ratio"),
            )
            .filter(pl.col("days") >= MIN_STATE_DAYS)
            .with_columns(
                pl.when((pl.col("net_top_abs_ret_std").is_not_null()) & (pl.col("net_top_abs_ret_std") > 0))
                .then(pl.col("net_top_abs_ret_mean") / (pl.col("net_top_abs_ret_std") / pl.col("days").sqrt()))
                .otherwise(0.0)
                .alias("net_top_abs_ret_t"),
                pl.when((pl.col("net_top_excess_std").is_not_null()) & (pl.col("net_top_excess_std") > 0))
                .then(pl.col("net_top_excess_mean") / (pl.col("net_top_excess_std") / pl.col("days").sqrt()))
                .otherwise(0.0)
                .alias("net_top_excess_t"),
                pl.lit(cost_bps).alias("roundtrip_cost_bps"),
            )
            .drop(["net_top_abs_ret_std", "net_top_excess_std"])
        )
        frames.append(summary)
    return pl.concat(frames, how="vertical") if frames else pl.DataFrame()


def build_daily_top_series(df: pl.DataFrame) -> pl.DataFrame:
    """Build daily top-quintile return series for each active bucket and signal."""
    frames: list[pl.DataFrame] = []
    for bucket, description, expr in active_bucket_definitions():
        for feature in FEATURES:
            for horizon in HORIZONS:
                label_col = f"fwd_excess_ret_{horizon}"
                abs_col = f"fwd_ret_{horizon}"
                bm_col = f"bm_fwd_ret_{horizon}"
                work = df.filter(expr & finite_signal_filter(feature, horizon))
                if work.is_empty():
                    continue

                top = add_groups(work, feature, []).filter(pl.col("feature_group") == 5)
                if top.is_empty():
                    continue

                daily = (
                    top.group_by("datetime")
                    .agg(
                        pl.len().alias("candidate_count"),
                        pl.col(abs_col).mean().alias("gross_top_abs_ret_mean"),
                        pl.col(label_col).mean().alias("gross_top_excess_mean"),
                        pl.first(bm_col).alias("bm_fwd_ret"),
                        pl.first("bm_ret_20").alias("bm_ret_20"),
                        pl.first("market_state_20d").alias("market_state_20d"),
                        pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
                    )
                    .with_columns(
                        pl.when(pl.col("bm_fwd_ret").is_null())
                        .then(pl.lit("unknown"))
                        .when(pl.col("bm_fwd_ret") >= 0)
                        .then(pl.lit("future_bm_up"))
                        .otherwise(pl.lit("future_bm_down"))
                        .alias("future_bm_state_hindsight"),
                        pl.lit(bucket).alias("bucket"),
                        pl.lit(description).alias("bucket_description"),
                        pl.lit(feature).alias("feature"),
                        pl.lit(horizon).alias("horizon"),
                    )
                )
                frames.append(with_market_bands(daily))

    return pl.concat(frames, how="vertical") if frames else pl.DataFrame()


def build_state_summary(daily_top_df: pl.DataFrame) -> pl.DataFrame:
    """Build ex-ante and diagnostic state summaries."""
    frames: list[pl.DataFrame] = []
    base_keys = ["bucket", "bucket_description", "feature", "horizon"]
    for state_col, state_kind in [
        ("market_state_20d", "ex_ante"),
        ("bm_ret_20_band", "ex_ante"),
        ("future_bm_state_hindsight", "hindsight_diagnostic"),
    ]:
        summary = summarize_daily(daily_top_df, [*base_keys, state_col])
        if summary.is_empty():
            continue
        frames.append(
            summary.with_columns(
                pl.lit(state_kind).alias("state_kind"),
                pl.lit(state_col).alias("state_layer"),
                pl.col(state_col).cast(pl.String).alias("state_value"),
            ).drop(state_col)
        )
    return pl.concat(frames, how="vertical") if frames else pl.DataFrame()


def build_state_cost(daily_top_df: pl.DataFrame) -> pl.DataFrame:
    """Build state-level cost sensitivity grid."""
    frames: list[pl.DataFrame] = []
    base_keys = ["bucket", "bucket_description", "feature", "horizon"]
    for state_col, state_kind in [
        ("market_state_20d", "ex_ante"),
        ("bm_ret_20_band", "ex_ante"),
        ("future_bm_state_hindsight", "hindsight_diagnostic"),
    ]:
        summary = summarize_cost(daily_top_df, [*base_keys, state_col])
        if summary.is_empty():
            continue
        frames.append(
            summary.with_columns(
                pl.lit(state_kind).alias("state_kind"),
                pl.lit(state_col).alias("state_layer"),
                pl.col(state_col).cast(pl.String).alias("state_value"),
            ).drop(state_col)
        )
    return pl.concat(frames, how="vertical") if frames else pl.DataFrame()


def build_year_state_summary(daily_top_df: pl.DataFrame) -> pl.DataFrame:
    """Summarize market-state top-leg performance by calendar year."""
    work = daily_top_df.with_columns(pl.col("datetime").dt.year().alias("year"))
    summary = summarize_daily(
        work,
        ["year", "bucket", "bucket_description", "feature", "horizon", "market_state_20d"],
    )
    if summary.is_empty():
        return summary
    return summary.with_columns(
        pl.lit("ex_ante").alias("state_kind"),
        pl.lit("market_state_20d").alias("state_layer"),
        pl.col("market_state_20d").cast(pl.String).alias("state_value"),
    ).drop("market_state_20d")


def write_report(
    daily_top_df: pl.DataFrame,
    state_summary_df: pl.DataFrame,
    state_cost_df: pl.DataFrame,
    year_state_df: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    """Write a Chinese report for top-leg state attribution."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡 top-leg 市场状态归因 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是股票组合回测，不新增交易规则，也不调参数；只检查固定高活跃桶 top 20% 候选的长侧绝对收益和超额收益在不同市场状态下是否有厚度。",
        f"- 样本：`{meta['date_min']}`到`{meta['date_max']}`，`{meta['symbol_count']}`只股票，`{meta['row_count']:,}`行；top-leg日序列`{daily_top_df.height:,}`行。",
        "- `market_state_20d`和`bm_ret_20_band`是信号日前可知的中证1000过去20日状态；`future_bm_state_hindsight`只是事后诊断，不能当交易过滤器。",
        "",
        "## 可提前识别状态：10日长侧",
        "",
    ]

    focus = state_summary_df.filter(
        (pl.col("state_layer") == "market_state_20d")
        & (pl.col("horizon") == 10)
        & pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"])
    ).sort(["feature", "bucket", "state_value"])
    for row in focus.iter_rows(named=True):
        lines.append(
            f"- `{row['feature']}` `{row['bucket']}` `{row['state_value']}`：days `{row['days']}`，"
            f"毛绝对`{row['gross_top_abs_ret_mean']:.4%}`，毛超额`{row['gross_top_excess_mean']:.4%}`，"
            f"超额t `{row['gross_top_excess_t']:.2f}`，超额正向日`{row['gross_top_excess_positive_ratio']:.2%}`。"
        )

    lines.extend(["", "## 成本后状态压力", ""])
    focus_cost = state_cost_df.filter(
        (pl.col("state_layer") == "market_state_20d")
        & (pl.col("horizon") == 10)
        & pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"])
        & pl.col("bucket").is_in(["active_q4_q5", "adv20_turnover_q5"])
        & pl.col("roundtrip_cost_bps").is_in([20.0, 50.0])
    ).sort(["feature", "bucket", "state_value", "roundtrip_cost_bps"])
    for row in focus_cost.iter_rows(named=True):
        lines.append(
            f"- `{row['feature']}` `{row['bucket']}` `{row['state_value']}` 成本`{row['roundtrip_cost_bps']:.0f}bp`："
            f"净绝对`{row['net_top_abs_ret_mean']:.4%}`，净超额`{row['net_top_excess_mean']:.4%}`，"
            f"净超额t `{row['net_top_excess_t']:.2f}`。"
        )

    lines.extend(["", "## 过去20日基准幅度分层", ""])
    band_focus = state_summary_df.filter(
        (pl.col("state_layer") == "bm_ret_20_band")
        & (pl.col("horizon") == 10)
        & pl.col("feature").is_in(["score_oversold_ret_20"])
        & pl.col("bucket").is_in(["active_q4_q5", "adv20_turnover_q5"])
    ).sort(["bucket", "state_value"])
    for row in band_focus.iter_rows(named=True):
        lines.append(
            f"- `{row['bucket']}` `{row['state_value']}`：days `{row['days']}`，"
            f"毛绝对`{row['gross_top_abs_ret_mean']:.4%}`，毛超额`{row['gross_top_excess_mean']:.4%}`。"
        )

    lines.extend(["", "## 未来基准方向诊断", ""])
    future_focus = state_summary_df.filter(
        (pl.col("state_layer") == "future_bm_state_hindsight")
        & (pl.col("horizon") == 10)
        & pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"])
        & (pl.col("bucket") == "active_q4_q5")
    ).sort(["feature", "state_value"])
    for row in future_focus.iter_rows(named=True):
        lines.append(
            f"- `{row['feature']}` `{row['state_value']}`：days `{row['days']}`，"
            f"毛绝对`{row['gross_top_abs_ret_mean']:.4%}`，毛超额`{row['gross_top_excess_mean']:.4%}`，"
            f"同期基准`{row['benchmark_forward_ret_mean']:.4%}`。"
        )

    lines.extend(["", "## 近端年份", ""])
    year_focus = year_state_df.filter(
        (pl.col("year") >= 2024)
        & (pl.col("horizon") == 10)
        & pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"])
        & (pl.col("bucket") == "active_q4_q5")
    ).sort(["feature", "year", "state_value"])
    for row in year_focus.iter_rows(named=True):
        lines.append(
            f"- `{row['year']}` `{row['feature']}` `{row['state_value']}`：days `{row['days']}`，"
            f"毛绝对`{row['gross_top_abs_ret_mean']:.4%}`，毛超额`{row['gross_top_excess_mean']:.4%}`。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果长侧只在未来基准上涨时赚钱，而在可提前识别的过去状态下没有稳定净超额，就说明它更像反弹 beta 暴露，不该直接组合化。",
            "- 如果可提前识别的下跌/震荡状态在20bp后仍有净绝对收益和净超额，才值得继续做更严格的入场拥挤、调仓冲突和组合路径回测。",
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
    """Run top-leg market-state attribution for stock range reversion."""
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
        "cost_bps": COST_BPS,
        "min_state_days": MIN_STATE_DAYS,
    }

    daily_top_df = build_daily_top_series(df).sort(["feature", "horizon", "bucket", "datetime"])
    state_summary_df = build_state_summary(daily_top_df).sort(
        ["state_kind", "state_layer", "feature", "horizon", "bucket", "state_value"]
    )
    state_cost_df = build_state_cost(daily_top_df).sort(
        ["state_kind", "state_layer", "feature", "horizon", "bucket", "state_value", "roundtrip_cost_bps"]
    )
    year_state_df = build_year_state_summary(daily_top_df).sort(
        ["year", "feature", "horizon", "bucket", "state_value"]
    )

    daily_path = OUTPUT_DIR / f"{PREFIX}_daily_top_series.csv"
    state_summary_path = OUTPUT_DIR / f"{PREFIX}_state_summary.csv"
    state_cost_path = OUTPUT_DIR / f"{PREFIX}_state_cost_grid.csv"
    year_state_path = OUTPUT_DIR / f"{PREFIX}_year_state_summary.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    daily_top_df.write_csv(daily_path)
    state_summary_df.write_csv(state_summary_path)
    state_cost_df.write_csv(state_cost_path)
    year_state_df.write_csv(year_state_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        daily_top_df,
        state_summary_df,
        state_cost_df,
        year_state_df,
        meta,
        {
            "daily_top_series": daily_path,
            "state_summary": state_summary_path,
            "state_cost_grid": state_cost_path,
            "year_state_summary": year_state_path,
            "meta": meta_path,
        },
    )
    print(state_summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
