from __future__ import annotations

import json
import os
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl


BASE_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "native_results"))).expanduser().resolve()
DEFAULT_INPUT_CACHE_DIR: Path = BASE_DIR / "native_results" / "cache"

STOCK_PANEL_PATH: Path = Path(
    os.getenv("STOCK_PANEL_PATH", os.getenv("STOCK_RANGE_PANEL_PATH", str(DEFAULT_INPUT_CACHE_DIR / "stock_panel.parquet")))
)
BENCHMARK_PATH: Path = Path(
    os.getenv("BENCHMARK_PATH", os.getenv("STOCK_RANGE_BENCHMARK_PATH", str(DEFAULT_INPUT_CACHE_DIR / "benchmark.parquet")))
)

PREFIX: str = "stock_range_reversion_signal_attribution_v1"
HORIZONS: tuple[int, ...] = (1, 3, 5, 10)
N_GROUPS: int = 5
MIN_DAILY_WIDTH: int = 50

FEATURES: list[tuple[str, str]] = [
    ("score_oversold_ret_5", "过去5日跌幅越大，分数越高"),
    ("score_oversold_ret_10", "过去10日跌幅越大，分数越高"),
    ("score_oversold_ret_20", "过去20日跌幅越大，分数越高"),
    ("score_below_ma20", "越低于20日均线，分数越高"),
    ("score_down_volume_pressure", "放量下跌压力越大，分数越高"),
]


def pct(numerator: float, denominator: float) -> float:
    """Return a stable percentage ratio."""
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def to_float(value: Any) -> float:
    """Convert nullable scalar into float."""
    if value is None:
        return 0.0
    if hasattr(value, "item"):
        try:
            value = value.item()
        except ValueError:
            pass
    return float(value)


def load_inputs() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Load cached stock and benchmark panels."""
    if not STOCK_PANEL_PATH.exists():
        raise FileNotFoundError(f"Missing stock panel: {STOCK_PANEL_PATH}")
    if not BENCHMARK_PATH.exists():
        raise FileNotFoundError(f"Missing benchmark panel: {BENCHMARK_PATH}")

    stock_df = normalize_stock_panel(pl.read_parquet(STOCK_PANEL_PATH)).sort(["symbol", "datetime"])
    benchmark_df = pl.read_parquet(BENCHMARK_PATH).sort("datetime")
    return stock_df, benchmark_df


def normalize_stock_panel(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize legacy and enriched stock panels into one research schema."""
    if "raw_close" in df.columns and "qfq_close" in df.columns:
        eligible_expr = (
            pl.col("eligible_component_row")
            if "eligible_component_row" in df.columns
            else pl.col("eligible_research_row")
            if "eligible_research_row" in df.columns
            else pl.lit(True)
        )
        return df.with_columns(
            pl.col("qfq_open").alias("open"),
            pl.col("qfq_high").alias("high"),
            pl.col("qfq_low").alias("low"),
            pl.col("qfq_close").alias("close"),
            pl.col("qfq_preclose").alias("preclose"),
            pl.col("raw_open").alias("trade_open"),
            pl.col("raw_high").alias("trade_high"),
            pl.col("raw_low").alias("trade_low"),
            pl.col("raw_close").alias("trade_close"),
            pl.col("raw_up_limit").alias("trade_up_limit"),
            pl.col("raw_down_limit").alias("trade_down_limit"),
            pl.when(eligible_expr.is_null())
            .then(True)
            .otherwise(eligible_expr)
            .alias("eligible_research_row"),
        )

    return df.with_columns(
        pl.col("open").alias("trade_open"),
        pl.col("high").alias("trade_high"),
        pl.col("low").alias("trade_low"),
        pl.col("close").alias("trade_close"),
        pl.col("up_limit").alias("trade_up_limit"),
        pl.col("down_limit").alias("trade_down_limit"),
        pl.lit(True).alias("eligible_research_row"),
    )


def add_price_features(stock_df: pl.DataFrame) -> pl.DataFrame:
    """Add fixed, non-optimized oversold features."""
    return (
        stock_df.with_columns(
            pl.col("close").shift(1).over("symbol").alias("close_lag_1"),
            pl.col("close").shift(5).over("symbol").alias("close_lag_5"),
            pl.col("close").shift(10).over("symbol").alias("close_lag_10"),
            pl.col("close").shift(20).over("symbol").alias("close_lag_20"),
            pl.col("close").rolling_mean(20).over("symbol").alias("close_ma20"),
            pl.col("volume").rolling_mean(20).over("symbol").alias("volume_ma20"),
        )
        .with_columns(
            (pl.col("close") / pl.col("close_lag_1") - 1).alias("ret_1"),
            (pl.col("close") / pl.col("close_lag_5") - 1).alias("ret_5"),
            (pl.col("close") / pl.col("close_lag_10") - 1).alias("ret_10"),
            (pl.col("close") / pl.col("close_lag_20") - 1).alias("ret_20"),
            (pl.col("close") / pl.col("close_ma20") - 1).alias("dist_ma20"),
            (pl.col("volume") / pl.col("volume_ma20")).alias("volume_ratio_20"),
        )
        .with_columns(
            (-pl.col("ret_5")).alias("score_oversold_ret_5"),
            (-pl.col("ret_10")).alias("score_oversold_ret_10"),
            (-pl.col("ret_20")).alias("score_oversold_ret_20"),
            (-pl.col("dist_ma20")).alias("score_below_ma20"),
            (pl.when(pl.col("ret_1") < 0).then(-pl.col("ret_1") * pl.col("volume_ratio_20")).otherwise(0.0))
            .alias("score_down_volume_pressure"),
        )
    )


def add_forward_returns(stock_df: pl.DataFrame, benchmark_df: pl.DataFrame) -> pl.DataFrame:
    """Add next-close entry returns and tradability flags for each horizon."""
    df = stock_df.with_columns(
        pl.col("close").shift(-1).over("symbol").alias("entry_close"),
        pl.col("trade_open").shift(-1).over("symbol").alias("entry_trade_open"),
        pl.col("trade_high").shift(-1).over("symbol").alias("entry_trade_high"),
        pl.col("trade_low").shift(-1).over("symbol").alias("entry_trade_low"),
        pl.col("trade_close").shift(-1).over("symbol").alias("entry_trade_close"),
        pl.col("is_suspended").shift(-1).over("symbol").alias("entry_is_suspended"),
        pl.col("is_st").shift(-1).over("symbol").alias("entry_is_st"),
        pl.col("trade_up_limit").shift(-1).over("symbol").alias("entry_trade_up_limit"),
        pl.col("eligible_research_row").shift(-1).over("symbol").alias("entry_eligible_research_row"),
    )

    df = df.with_columns(
        (
            (
                (pl.col("entry_trade_open") == pl.col("entry_trade_high"))
                & (pl.col("entry_trade_high") == pl.col("entry_trade_low"))
                & (pl.col("entry_trade_low") == pl.col("entry_trade_close"))
                & (pl.col("entry_trade_close") >= pl.col("entry_trade_up_limit") - 0.005)
            )
            .fill_null(True)
        ).alias("entry_oneword_limit_up"),
    )

    bm = benchmark_df.sort("datetime").with_columns(
        pl.col("close").shift(20).alias("bm_close_lag_20"),
    ).with_columns(
        (pl.col("close") / pl.col("bm_close_lag_20") - 1).alias("bm_ret_20"),
    )

    select_cols = ["datetime", "bm_ret_20"]
    for horizon in HORIZONS:
        df = df.with_columns(
            pl.col("close").shift(-(horizon + 1)).over("symbol").alias(f"exit_close_{horizon}"),
            pl.col("trade_open").shift(-(horizon + 1)).over("symbol").alias(f"exit_trade_open_{horizon}"),
            pl.col("trade_high").shift(-(horizon + 1)).over("symbol").alias(f"exit_trade_high_{horizon}"),
            pl.col("trade_low").shift(-(horizon + 1)).over("symbol").alias(f"exit_trade_low_{horizon}"),
            pl.col("trade_close").shift(-(horizon + 1)).over("symbol").alias(f"exit_trade_close_{horizon}"),
            pl.col("is_suspended").shift(-(horizon + 1)).over("symbol").alias(f"exit_is_suspended_{horizon}"),
            pl.col("trade_down_limit").shift(-(horizon + 1)).over("symbol").alias(f"exit_trade_down_limit_{horizon}"),
            pl.col("eligible_research_row").shift(-(horizon + 1)).over("symbol").alias(f"exit_eligible_research_row_{horizon}"),
        ).with_columns(
            (
                (
                    (pl.col(f"exit_trade_open_{horizon}") == pl.col(f"exit_trade_high_{horizon}"))
                    & (pl.col(f"exit_trade_high_{horizon}") == pl.col(f"exit_trade_low_{horizon}"))
                    & (pl.col(f"exit_trade_low_{horizon}") == pl.col(f"exit_trade_close_{horizon}"))
                    & (pl.col(f"exit_trade_close_{horizon}") <= pl.col(f"exit_trade_down_limit_{horizon}") + 0.005)
                )
                .fill_null(True)
            ).alias(f"exit_oneword_limit_down_{horizon}"),
            (pl.col(f"exit_close_{horizon}") / pl.col("entry_close") - 1).alias(f"fwd_ret_{horizon}"),
        )

        bm = bm.with_columns(
            pl.col("close").shift(-1).alias("bm_entry_close"),
            pl.col("close").shift(-(horizon + 1)).alias(f"bm_exit_close_{horizon}"),
        ).with_columns(
            (pl.col(f"bm_exit_close_{horizon}") / pl.col("bm_entry_close") - 1).alias(f"bm_fwd_ret_{horizon}")
        )
        select_cols.append(f"bm_fwd_ret_{horizon}")

    df = df.join(bm.select(select_cols), on="datetime", how="left")

    for horizon in HORIZONS:
        df = df.with_columns(
            (pl.col(f"fwd_ret_{horizon}") - pl.col(f"bm_fwd_ret_{horizon}")).alias(f"fwd_excess_ret_{horizon}")
        )
        df = df.with_columns(
            (
                (~pl.col("entry_is_suspended").fill_null(True))
                & (~pl.col("is_st").fill_null(True))
                & (~pl.col("entry_is_st").fill_null(True))
                & (~pl.col("entry_oneword_limit_up").fill_null(True))
                & (~pl.col(f"exit_is_suspended_{horizon}").fill_null(True))
                & (~pl.col(f"exit_oneword_limit_down_{horizon}").fill_null(True))
                & pl.col("eligible_research_row").fill_null(False)
                & pl.col("entry_eligible_research_row").fill_null(False)
                & pl.col(f"exit_eligible_research_row_{horizon}").fill_null(False)
                & pl.col(f"fwd_ret_{horizon}").is_not_null()
                & pl.col(f"fwd_excess_ret_{horizon}").is_not_null()
                & (pl.col("volume") > 0)
                & (pl.col("turnover") > 0)
            ).alias(f"final_keep_{horizon}"),
        )

    return df.with_columns(
        pl.when(pl.col("bm_ret_20").is_null())
        .then(pl.lit("unknown"))
        .when(pl.col("bm_ret_20") >= 0)
        .then(pl.lit("market_up_20d"))
        .otherwise(pl.lit("market_down_20d"))
        .alias("market_state_20d")
    )


def add_quantile_groups(df: pl.DataFrame, feature: str) -> pl.DataFrame:
    """Assign same-day cross-sectional quintile groups; group 5 has highest score."""
    return (
        df.with_columns(
            pl.col(feature).rank("ordinal").over("datetime").alias("_rank"),
            pl.len().over("datetime").alias("_n"),
        )
        .with_columns(
            ((((pl.col("_rank") - 1) * N_GROUPS) / pl.col("_n")).floor().cast(pl.Int64) + 1)
            .clip(1, N_GROUPS)
            .alias("group")
        )
        .drop(["_rank", "_n"])
    )


def evaluate_feature(df: pl.DataFrame, feature: str, horizon: int) -> tuple[dict[str, Any], pl.DataFrame, pl.DataFrame]:
    """Evaluate one feature and one forward horizon."""
    label_col = f"fwd_excess_ret_{horizon}"
    work = df.filter(
        pl.col(f"final_keep_{horizon}")
        & pl.col(feature).is_not_null()
        & pl.col(feature).is_finite()
        & pl.col(label_col).is_not_null()
        & pl.col(label_col).is_finite()
    )

    ic_df = (
        work.with_columns(
            pl.col(feature).rank("average").over("datetime").alias("feature_rank"),
            pl.col(label_col).rank("average").over("datetime").alias("label_rank"),
        )
        .group_by("datetime")
        .agg(
            pl.len().alias("n"),
            pl.corr("feature_rank", "label_rank").alias("rank_ic"),
        )
        .filter((pl.col("n") >= MIN_DAILY_WIDTH) & pl.col("rank_ic").is_not_null() & pl.col("rank_ic").is_finite())
        .sort("datetime")
    )

    grouped = (
        add_quantile_groups(work, feature)
        .group_by(["datetime", "group"])
        .agg(
            pl.col(label_col).mean().alias("group_excess_ret"),
            pl.len().alias("stock_count"),
        )
        .with_columns(
            pl.lit(feature).alias("feature"),
            pl.lit(horizon).alias("horizon"),
        )
        .sort(["feature", "horizon", "datetime", "group"])
    )

    top_df = grouped.filter(pl.col("group") == N_GROUPS).select(
        ["datetime", pl.col("group_excess_ret").alias("top_ret"), pl.col("stock_count").alias("top_count")]
    )
    bottom_df = grouped.filter(pl.col("group") == 1).select(
        ["datetime", pl.col("group_excess_ret").alias("bottom_ret"), pl.col("stock_count").alias("bottom_count")]
    )
    date_state = work.group_by("datetime").agg(pl.first("market_state_20d").alias("market_state_20d"))
    ls_df = (
        top_df.join(bottom_df, on="datetime", how="inner")
        .join(date_state, on="datetime", how="left")
        .with_columns((pl.col("top_ret") - pl.col("bottom_ret")).alias("top_minus_bottom"))
        .sort("datetime")
    )

    ls_mean = to_float(ls_df["top_minus_bottom"].mean()) if ls_df.height else 0.0
    ls_std = to_float(ls_df["top_minus_bottom"].std()) if ls_df.height else 0.0
    ic_mean = to_float(ic_df["rank_ic"].mean()) if ic_df.height else 0.0
    ic_std = to_float(ic_df["rank_ic"].std()) if ic_df.height else 0.0

    summary = {
        "feature": feature,
        "horizon": horizon,
        "sample_rows": work.height,
        "sample_days": ic_df.height,
        "avg_daily_width": to_float(ic_df["n"].mean()) if ic_df.height else 0.0,
        "rank_ic_mean": ic_mean,
        "rank_ic_std": ic_std,
        "rank_ic_ir": ic_mean / ic_std if ic_std else 0.0,
        "rank_ic_positive_ratio": to_float((ic_df["rank_ic"] > 0).mean()) if ic_df.height else 0.0,
        "top_mean": to_float(ls_df["top_ret"].mean()) if ls_df.height else 0.0,
        "bottom_mean": to_float(ls_df["bottom_ret"].mean()) if ls_df.height else 0.0,
        "top_minus_bottom_mean": ls_mean,
        "top_minus_bottom_std": ls_std,
        "top_minus_bottom_t": ls_mean / (ls_std / sqrt(ls_df.height)) if ls_std and ls_df.height else 0.0,
        "top_minus_bottom_positive_ratio": to_float((ls_df["top_minus_bottom"] > 0).mean()) if ls_df.height else 0.0,
    }

    state_summary = (
        ls_df.group_by("market_state_20d")
        .agg(
            pl.len().alias("days"),
            pl.col("top_ret").mean().alias("top_mean"),
            pl.col("bottom_ret").mean().alias("bottom_mean"),
            pl.col("top_minus_bottom").mean().alias("top_minus_bottom_mean"),
            (pl.col("top_minus_bottom") > 0).mean().alias("positive_ratio"),
        )
        .with_columns(
            pl.lit(feature).alias("feature"),
            pl.lit(horizon).alias("horizon"),
        )
        .sort(["feature", "horizon", "market_state_20d"])
    )

    return summary, grouped, state_summary


def write_report(
    summary_df: pl.DataFrame,
    state_df: pl.DataFrame,
    output_paths: dict[str, Path],
    sample_meta: dict[str, Any],
) -> Path:
    """Write Chinese signal attribution report."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"

    h5 = summary_df.filter(pl.col("horizon") == 5).sort("top_minus_bottom_mean", descending=True)
    best_h5 = h5.row(0, named=True) if h5.height else None
    all_sorted = summary_df.sort("top_minus_bottom_mean", descending=True)
    best_all = all_sorted.row(0, named=True) if all_sorted.height else None

    lines = [
        "# 股票横截面超跌反弹信号层归因 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是股票策略回测，也没有资金曲线；只检验固定、朴素的横截面超跌分数是否对应未来超额收益。",
        "- 评价口径：信号日收盘后，按次日收盘入场，持有1/3/5/10个交易日，收益扣除中证1000基准同期收益。",
        "- 分组口径：每日横截面五组，group 5为分数最高的一组，也就是更超跌/更低于均线/更强放量下跌压力。",
    ]

    if best_h5:
        lines.extend(
            [
                f"- 5日口径最强的朴素分数是`{best_h5['feature']}`，top-bottom平均超额收益`{best_h5['top_minus_bottom_mean']:.4%}`，Rank IC均值`{best_h5['rank_ic_mean']:.4f}`。",
            ]
        )
    if best_all:
        lines.append(
            f"- 全部 horizon 中 top-bottom 平均最高的是`{best_all['feature']}`/`{best_all['horizon']}日`，均值`{best_all['top_minus_bottom_mean']:.4%}`，t值`{best_all['top_minus_bottom_t']:.2f}`。"
        )

    if sample_meta["has_historical_components"]:
        sample_line = (
            f"- 样本范围为`{sample_meta['date_min']}`到`{sample_meta['date_max']}`，"
            f"`{sample_meta['symbol_count']}`只历史出现过的成分股；本次已使用 Tushare 历史成分过滤，"
            "幸存者偏差较静态当前成分口径明显降低，但历史长度仍只有一年多。"
        )
        judgment_line = (
            "- 如果top-bottom均值和Rank IC同向为正，说明股票横截面超跌反弹有初步方向；"
            "但因为历史短，仍不能进入正式策略设计。"
        )
        next_step_line = "- 下一步不应直接调阈值，而应把同一套固定口径扩展到更长历史，并做行业、市值、流动性分层。"
    else:
        sample_line = (
            f"- 样本范围为`{sample_meta['date_min']}`到`{sample_meta['date_max']}`，"
            f"`{sample_meta['symbol_count']}`只股票；若未使用历史成分字段，结论只能作为 smoke test，不能当作正式策略证据。"
        )
        judgment_line = (
            "- 如果top-bottom均值和Rank IC同向为正，说明股票横截面超跌反弹有初步方向；"
            "但因为历史短、当前成分样本和历史成分缺口，不能进入正式策略设计。"
        )
        next_step_line = "- 下一步不应直接调阈值，而应补历史成分，或把同一套固定口径跑到更长、更干净的数据上。"

    lines.extend(
        [
            sample_line,
            "",
            "## 5日持有摘要",
            "",
            "| feature | Rank IC | Top-Bottom均值 | T值 | 正向日占比 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )

    for row in h5.iter_rows(named=True):
        lines.append(
            f"| `{row['feature']}` | {row['rank_ic_mean']:.4f} | {row['top_minus_bottom_mean']:.4%} | {row['top_minus_bottom_t']:.2f} | {row['top_minus_bottom_positive_ratio']:.2%} |"
        )

    lines.extend(
        [
            "",
            "## 市场状态观察",
            "",
            "- `market_up_20d`/`market_down_20d`只按中证1000过去20日涨跌粗分；这是归因分层，不是交易过滤器。",
        ]
    )

    state_h5 = state_df.filter(pl.col("horizon") == 5).sort(["feature", "market_state_20d"])
    for row in state_h5.iter_rows(named=True):
        lines.append(
            f"- `{row['feature']}` `{row['market_state_20d']}`：days `{row['days']}`，top-bottom均值 `{row['top_minus_bottom_mean']:.4%}`，正向日占比 `{row['positive_ratio']:.2%}`。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            judgment_line,
            "- 如果输入为双口径研究面板，信号和收益使用前复权价，停牌、涨跌停和成交约束使用原始价。",
            next_step_line,
            "- Polanyi式手感：这一步看的是“水温”，不是下水游泳；如果水温都不对，就别急着设计泳姿。",
            "",
            "## 输出文件",
            "",
        ]
    )

    for name, path in output_paths.items():
        lines.append(f"- {name}: `{path}`")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    """Run stock range-reversion signal attribution."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stock_df, benchmark_df = load_inputs()
    df = add_price_features(stock_df)
    df = add_forward_returns(df, benchmark_df)
    sample_meta = {
        "symbol_count": df["symbol"].n_unique(),
        "date_min": str(df["datetime"].min()),
        "date_max": str(df["datetime"].max()),
        "has_historical_components": (
            bool(df.select(pl.col("is_index_component").fill_null(False).any()).item())
            if "is_index_component" in df.columns
            else False
        ),
    }

    summaries: list[dict[str, Any]] = []
    group_frames: list[pl.DataFrame] = []
    state_frames: list[pl.DataFrame] = []

    for feature, _description in FEATURES:
        for horizon in HORIZONS:
            summary, grouped, state_summary = evaluate_feature(df, feature, horizon)
            summaries.append(summary)
            group_frames.append(grouped)
            state_frames.append(state_summary)

    summary_df = pl.DataFrame(summaries).sort(["horizon", "top_minus_bottom_mean"], descending=[False, True])
    group_df = pl.concat(group_frames, how="vertical") if group_frames else pl.DataFrame()
    state_df = pl.concat(state_frames, how="vertical") if state_frames else pl.DataFrame()

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    group_path = OUTPUT_DIR / f"{PREFIX}_group_returns.csv"
    state_path = OUTPUT_DIR / f"{PREFIX}_market_state_summary.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    summary_df.write_csv(summary_path)
    group_df.write_csv(group_path)
    state_df.write_csv(state_path)
    meta_path.write_text(
        json.dumps(
            {
                "features": [{"name": name, "description": description} for name, description in FEATURES],
                "horizons": HORIZONS,
                "n_groups": N_GROUPS,
                "min_daily_width": MIN_DAILY_WIDTH,
                "entry": "next close",
                "return": "stock forward return minus benchmark forward return",
                "sample": sample_meta,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    output_paths = {
        "summary": summary_path,
        "group_returns": group_path,
        "market_state_summary": state_path,
        "meta": meta_path,
    }
    report_path = write_report(summary_df, state_df, output_paths, sample_meta)

    print(summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
