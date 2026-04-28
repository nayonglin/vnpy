from __future__ import annotations

import json
import os
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_signal_attribution import (
    FEATURES,
    N_GROUPS,
    add_forward_returns,
    add_price_features,
    normalize_stock_panel,
    to_float,
)


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
DEFAULT_PANEL_DIRS: list[Path] = [
    NATIVE_RESULTS_DIR / "stock_range_reversion_cache_tushare_daily_2018_2020",
    NATIVE_RESULTS_DIR / "stock_range_reversion_cache_tushare_daily_2021",
    NATIVE_RESULTS_DIR / "stock_range_reversion_cache_tushare_daily_2022",
    NATIVE_RESULTS_DIR / "stock_range_reversion_cache_tushare_daily_2023",
    NATIVE_RESULTS_DIR / "stock_range_reversion_cache_tushare_daily_2024",
    NATIVE_RESULTS_DIR / "stock_range_reversion_cache_tushare_daily_2025_2026",
]

OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_layer_attribution_2018_2026"),
    )
).expanduser().resolve()
LAYER_TAG_PATH: Path = Path(
    os.getenv(
        "LAYER_TAG_PATH",
        str(
            NATIVE_RESULTS_DIR
            / "stock_range_reversion_layer_tags_tushare_2018_2026"
            / "stock_range_reversion_layer_tags.parquet"
        ),
    )
).expanduser()

PANEL_DIRS_ENV: str = os.getenv("PANEL_DIRS", "").strip()
PANEL_DIRS: list[Path] = (
    [Path(item).expanduser().resolve() for item in PANEL_DIRS_ENV.split(",") if item.strip()]
    if PANEL_DIRS_ENV
    else DEFAULT_PANEL_DIRS
)

PREFIX: str = "stock_range_reversion_layer_attribution_v1"
HORIZONS: tuple[int, ...] = tuple(int(item) for item in os.getenv("HORIZONS", "5,10").split(",") if item.strip())
FEATURE_NAMES: tuple[str, ...] = tuple(
    item.strip()
    for item in os.getenv(
        "FEATURES",
        "score_oversold_ret_5,score_oversold_ret_10,score_oversold_ret_20,score_below_ma20",
    ).split(",")
    if item.strip()
)
LAYER_COLUMNS: tuple[str, ...] = tuple(
    item.strip()
    for item in os.getenv(
        "LAYER_COLUMNS",
        "circ_mv_q,total_mv_q,turnover_rate_f_q,adv20_turnover_q,market,industry",
    ).split(",")
    if item.strip()
)
MIN_LAYER_DAILY_WIDTH: int = int(os.getenv("MIN_LAYER_DAILY_WIDTH", "20") or 20)
MIN_LAYER_DAYS: int = int(os.getenv("MIN_LAYER_DAYS", "60") or 60)


def load_panels() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Load and concatenate stock and benchmark panels from all yearly ranges."""
    stock_frames: list[pl.DataFrame] = []
    benchmark_frames: list[pl.DataFrame] = []
    for panel_dir in PANEL_DIRS:
        stock_path = panel_dir / "stock_range_reversion_research_panel.parquet"
        benchmark_path = panel_dir / "stock_range_reversion_benchmark.parquet"
        if not stock_path.exists():
            raise FileNotFoundError(stock_path)
        if not benchmark_path.exists():
            raise FileNotFoundError(benchmark_path)
        stock_frames.append(normalize_stock_panel(pl.read_parquet(stock_path)))
        benchmark_frames.append(pl.read_parquet(benchmark_path))

    stock_df = pl.concat(stock_frames, how="vertical").unique(["datetime", "symbol"]).sort(["symbol", "datetime"])
    benchmark_df = pl.concat(benchmark_frames, how="vertical").unique("datetime").sort("datetime")
    return stock_df, benchmark_df


def load_layer_tags() -> pl.DataFrame:
    """Load layer tags needed for attribution."""
    if not LAYER_TAG_PATH.exists():
        raise FileNotFoundError(LAYER_TAG_PATH)
    needed = [
        "datetime",
        "symbol",
        "has_daily_basic",
        "industry",
        "market",
        "circ_mv_q",
        "total_mv_q",
        "free_share_q",
        "turnover_rate_q",
        "turnover_rate_f_q",
        "pb_q",
        "pe_ttm_q",
        "adv20_turnover_q",
        "circ_mv",
        "total_mv",
        "turnover_rate_f",
        "pb",
        "pe_ttm",
    ]
    schema = pl.scan_parquet(LAYER_TAG_PATH).collect_schema()
    cols = [col for col in needed if col in schema.names()]
    return pl.read_parquet(LAYER_TAG_PATH, columns=cols).unique(["datetime", "symbol"])


def add_layer_group(work: pl.DataFrame, feature: str, layer_col: str) -> pl.DataFrame:
    """Add feature quintile groups inside each date/layer cross-section."""
    return (
        work.with_columns(
            pl.col(feature).rank("ordinal").over(["datetime", layer_col]).alias("_rank"),
            pl.len().over(["datetime", layer_col]).alias("_n"),
        )
        .filter(pl.col("_n") >= MIN_LAYER_DAILY_WIDTH)
        .with_columns(
            ((((pl.col("_rank") - 1) * N_GROUPS) / pl.col("_n")).floor().cast(pl.Int64) + 1)
            .clip(1, N_GROUPS)
            .alias("feature_group")
        )
        .drop("_rank")
    )


def summarize_ls(ls_df: pl.DataFrame, layer_col: str, feature: str, horizon: int) -> pl.DataFrame:
    """Summarize long-short series by layer value."""
    if ls_df.is_empty():
        return pl.DataFrame()
    return (
        ls_df.group_by(layer_col)
        .agg(
            pl.len().alias("days"),
            pl.col("_n").mean().alias("avg_daily_width"),
            pl.col("top_ret").mean().alias("top_mean"),
            pl.col("bottom_ret").mean().alias("bottom_mean"),
            pl.col("top_minus_bottom").mean().alias("top_minus_bottom_mean"),
            pl.col("top_minus_bottom").std().alias("top_minus_bottom_std"),
            (pl.col("top_minus_bottom") > 0).mean().alias("top_minus_bottom_positive_ratio"),
        )
        .with_columns(
            pl.when((pl.col("top_minus_bottom_std").is_not_null()) & (pl.col("top_minus_bottom_std") > 0))
            .then(pl.col("top_minus_bottom_mean") / (pl.col("top_minus_bottom_std") / pl.col("days").sqrt()))
            .otherwise(0.0)
            .alias("top_minus_bottom_t"),
            pl.lit(layer_col).alias("layer"),
            pl.col(layer_col).cast(pl.String).alias("layer_value"),
            pl.lit(feature).alias("feature"),
            pl.lit(horizon).alias("horizon"),
        )
        .filter(pl.col("days") >= MIN_LAYER_DAYS)
        .select(
            [
                "layer",
                "layer_value",
                "feature",
                "horizon",
                "days",
                "avg_daily_width",
                "top_mean",
                "bottom_mean",
                "top_minus_bottom_mean",
                "top_minus_bottom_t",
                "top_minus_bottom_positive_ratio",
            ]
        )
    )


def summarize_year_ls(ls_df: pl.DataFrame, layer_col: str, feature: str, horizon: int) -> pl.DataFrame:
    """Summarize long-short series by layer value and calendar year."""
    if ls_df.is_empty():
        return pl.DataFrame()
    return (
        ls_df.with_columns(pl.col("datetime").dt.year().alias("year"))
        .group_by(["year", layer_col])
        .agg(
            pl.len().alias("days"),
            pl.col("_n").mean().alias("avg_daily_width"),
            pl.col("top_minus_bottom").mean().alias("top_minus_bottom_mean"),
            pl.col("top_minus_bottom").std().alias("top_minus_bottom_std"),
            (pl.col("top_minus_bottom") > 0).mean().alias("top_minus_bottom_positive_ratio"),
        )
        .with_columns(
            pl.when((pl.col("top_minus_bottom_std").is_not_null()) & (pl.col("top_minus_bottom_std") > 0))
            .then(pl.col("top_minus_bottom_mean") / (pl.col("top_minus_bottom_std") / pl.col("days").sqrt()))
            .otherwise(0.0)
            .alias("top_minus_bottom_t"),
            pl.lit(layer_col).alias("layer"),
            pl.col(layer_col).cast(pl.String).alias("layer_value"),
            pl.lit(feature).alias("feature"),
            pl.lit(horizon).alias("horizon"),
        )
        .filter(pl.col("days") >= 20)
        .select(
            [
                "year",
                "layer",
                "layer_value",
                "feature",
                "horizon",
                "days",
                "avg_daily_width",
                "top_minus_bottom_mean",
                "top_minus_bottom_t",
                "top_minus_bottom_positive_ratio",
            ]
        )
    )


def evaluate_layer(df: pl.DataFrame, feature: str, horizon: int, layer_col: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Evaluate one feature/horizon inside one layer column."""
    label_col = f"fwd_excess_ret_{horizon}"
    if layer_col not in df.columns:
        return pl.DataFrame(), pl.DataFrame()

    work = df.filter(
        pl.col(f"final_keep_{horizon}")
        & pl.col(layer_col).is_not_null()
        & pl.col(feature).is_not_null()
        & pl.col(feature).is_finite()
        & pl.col(label_col).is_not_null()
        & pl.col(label_col).is_finite()
    )
    if work.is_empty():
        return pl.DataFrame(), pl.DataFrame()

    grouped = (
        add_layer_group(work, feature, layer_col)
        .group_by(["datetime", layer_col, "feature_group"])
        .agg(
            pl.col(label_col).mean().alias("group_excess_ret"),
            pl.len().alias("stock_count"),
            pl.first("_n").alias("_n"),
        )
    )
    top_df = grouped.filter(pl.col("feature_group") == N_GROUPS).select(
        ["datetime", layer_col, pl.col("group_excess_ret").alias("top_ret"), pl.col("stock_count").alias("top_count"), "_n"]
    )
    bottom_df = grouped.filter(pl.col("feature_group") == 1).select(
        ["datetime", layer_col, pl.col("group_excess_ret").alias("bottom_ret"), pl.col("stock_count").alias("bottom_count")]
    )
    ls_df = (
        top_df.join(bottom_df, on=["datetime", layer_col], how="inner")
        .with_columns((pl.col("top_ret") - pl.col("bottom_ret")).alias("top_minus_bottom"))
        .sort(["datetime", layer_col])
    )
    return summarize_ls(ls_df, layer_col, feature, horizon), summarize_year_ls(ls_df, layer_col, feature, horizon)


def write_report(summary_df: pl.DataFrame, year_df: pl.DataFrame, meta: dict[str, Any], paths: dict[str, Path]) -> Path:
    """Write Chinese report for the layer attribution."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡分层归因 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是股票组合回测，只是在同一套固定超跌信号下，检查收益是否集中在市值、换手、市场板块或行业分层。",
        f"- 样本：`{meta['date_min']}`到`{meta['date_max']}`，`{meta['symbol_count']}`只股票，`{meta['row_count']:,}`行。",
        f"- 分层最小日内宽度：`{MIN_LAYER_DAILY_WIDTH}`，最小有效日期：`{MIN_LAYER_DAYS}`。",
        "",
        "## 关键分层摘要",
        "",
    ]

    focus = summary_df.filter(
        pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"])
        & (pl.col("horizon") == 10)
        & pl.col("layer").is_in(["circ_mv_q", "turnover_rate_f_q", "adv20_turnover_q", "market"])
    ).sort(["feature", "layer", "layer_value"])

    for row in focus.iter_rows(named=True):
        lines.append(
            f"- `{row['feature']}`/`{row['horizon']}日` `{row['layer']}={row['layer_value']}`：days `{row['days']}`，"
            f"top-bottom `{row['top_minus_bottom_mean']:.4%}`，t `{row['top_minus_bottom_t']:.2f}`，"
            f"正向日 `{row['top_minus_bottom_positive_ratio']:.2%}`。"
        )

    industry_top = (
        summary_df.filter((pl.col("layer") == "industry") & (pl.col("horizon") == 10))
        .sort("top_minus_bottom_mean", descending=True)
        .head(10)
    )
    lines.extend(["", "## 行业观察", ""])
    for row in industry_top.iter_rows(named=True):
        lines.append(
            f"- `{row['feature']}` `{row['layer_value']}`：days `{row['days']}`，top-bottom `{row['top_minus_bottom_mean']:.4%}`，t `{row['top_minus_bottom_t']:.2f}`。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果某个信号只在单一市值桶或少数行业成立，后续应把它当作结构性偏差，而不是普适震荡 alpha。",
            "- 这一步仍不触发第78 A/B，也不触发正式股票组合回测。",
            "- Polanyi式手感：现在是在判断收益是不是只有局部在发力；如果多个维度都站得住，才值得研究组合化。",
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
    """Run stock range-reversion layer attribution."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    df = add_forward_returns(add_price_features(stock_df), benchmark_df).join(
        layer_tags, on=["datetime", "symbol"], how="left"
    )
    meta = {
        "row_count": df.height,
        "symbol_count": df["symbol"].n_unique(),
        "date_min": str(df["datetime"].min()),
        "date_max": str(df["datetime"].max()),
        "features": FEATURE_NAMES,
        "horizons": HORIZONS,
        "layers": LAYER_COLUMNS,
        "min_layer_daily_width": MIN_LAYER_DAILY_WIDTH,
        "min_layer_days": MIN_LAYER_DAYS,
    }

    summaries: list[pl.DataFrame] = []
    year_summaries: list[pl.DataFrame] = []
    for layer_col in LAYER_COLUMNS:
        for feature in FEATURE_NAMES:
            for horizon in HORIZONS:
                summary, year_summary = evaluate_layer(df, feature, horizon, layer_col)
                if not summary.is_empty():
                    summaries.append(summary)
                if not year_summary.is_empty():
                    year_summaries.append(year_summary)

    summary_df = (
        pl.concat(summaries, how="vertical")
        if summaries
        else pl.DataFrame(
            schema={
                "layer": pl.String,
                "layer_value": pl.String,
                "feature": pl.String,
                "horizon": pl.Int64,
            }
        )
    )
    year_df = pl.concat(year_summaries, how="vertical") if year_summaries else pl.DataFrame()
    summary_df = summary_df.sort(["layer", "feature", "horizon", "layer_value"])
    if not year_df.is_empty():
        year_df = year_df.sort(["year", "layer", "feature", "horizon", "layer_value"])

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    year_path = OUTPUT_DIR / f"{PREFIX}_year_summary.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"
    summary_df.write_csv(summary_path)
    year_df.write_csv(year_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        year_df,
        meta,
        {
            "summary": summary_path,
            "year_summary": year_path,
            "meta": meta_path,
        },
    )
    print(summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
