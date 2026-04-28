from __future__ import annotations

import json
import os
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import add_price_features
from backtest_stock_range_reversion_market_down_merged_portfolio import (
    BUCKET,
    COST_BPS,
    FEATURE,
    HORIZON,
    MARKET_STATE,
    OUTPUT_DIR as MERGED_OUTPUT_DIR,
    PREFIX as MERGED_PREFIX,
    build_selected_frame,
    to_float,
)


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_state_variables_2018_2026"),
    )
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_market_down_state_variables_v1"
MIN_SIGNAL_DAYS: int = int(os.getenv("MIN_SIGNAL_DAYS", "40") or 40)
MIN_PATH_DAYS: int = int(os.getenv("MIN_PATH_DAYS", "60") or 60)
STRESS_YEARS: tuple[int, ...] = tuple(int(item) for item in os.getenv("STRESS_YEARS", "2018,2022").split(","))


def t_stat(mean: float, std: float | None, n: int) -> float:
    """Return a simple t-stat for a mean series."""
    if not std or std <= 0 or n <= 1:
        return 0.0
    return mean / (std / (n**0.5))


def band_bm_ret_5() -> pl.Expr:
    """Return fixed benchmark 5-day return bands known on the signal date."""
    return (
        pl.when(pl.col("bm_ret_5").is_null())
        .then(pl.lit("unknown"))
        .when(pl.col("bm_ret_5") <= -0.05)
        .then(pl.lit("ret5_le_-5pct"))
        .when(pl.col("bm_ret_5") <= -0.02)
        .then(pl.lit("ret5_-5_to_-2pct"))
        .when(pl.col("bm_ret_5") < 0.0)
        .then(pl.lit("ret5_-2_to_0pct"))
        .otherwise(pl.lit("ret5_ge_0pct"))
    )


def band_bm_ret_20() -> pl.Expr:
    """Return fixed benchmark 20-day return bands known on the signal date."""
    return (
        pl.when(pl.col("bm_ret_20").is_null())
        .then(pl.lit("unknown"))
        .when(pl.col("bm_ret_20") <= -0.08)
        .then(pl.lit("ret20_le_-8pct"))
        .when(pl.col("bm_ret_20") <= -0.03)
        .then(pl.lit("ret20_-8_to_-3pct"))
        .when(pl.col("bm_ret_20") < 0.0)
        .then(pl.lit("ret20_-3_to_0pct"))
        .otherwise(pl.lit("ret20_ge_0pct"))
    )


def band_drawdown60() -> pl.Expr:
    """Return fixed benchmark drawdown-from-60-day-high bands."""
    return (
        pl.when(pl.col("bm_drawdown_60").is_null())
        .then(pl.lit("unknown"))
        .when(pl.col("bm_drawdown_60") <= -0.20)
        .then(pl.lit("dd60_le_-20pct"))
        .when(pl.col("bm_drawdown_60") <= -0.10)
        .then(pl.lit("dd60_-20_to_-10pct"))
        .when(pl.col("bm_drawdown_60") <= -0.05)
        .then(pl.lit("dd60_-10_to_-5pct"))
        .otherwise(pl.lit("dd60_gt_-5pct"))
    )


def band_down_streak() -> pl.Expr:
    """Return benchmark consecutive down-day bands."""
    return (
        pl.when(pl.col("bm_down_streak") <= 0)
        .then(pl.lit("streak_0"))
        .when(pl.col("bm_down_streak") <= 2)
        .then(pl.lit("streak_1_2"))
        .when(pl.col("bm_down_streak") <= 4)
        .then(pl.lit("streak_3_4"))
        .otherwise(pl.lit("streak_ge_5"))
    )


def band_breadth20() -> pl.Expr:
    """Return fixed 20-day breadth bands."""
    return (
        pl.when(pl.col("breadth_pos_20d_ratio").is_null())
        .then(pl.lit("unknown"))
        .when(pl.col("breadth_pos_20d_ratio") <= 0.20)
        .then(pl.lit("breadth20_le_20pct"))
        .when(pl.col("breadth_pos_20d_ratio") <= 0.40)
        .then(pl.lit("breadth20_20_to_40pct"))
        .when(pl.col("breadth_pos_20d_ratio") <= 0.60)
        .then(pl.lit("breadth20_40_to_60pct"))
        .otherwise(pl.lit("breadth20_gt_60pct"))
    )


def band_liquidity_ratio() -> pl.Expr:
    """Return component turnover contraction bands."""
    return (
        pl.when(pl.col("component_turnover_20_60_ratio").is_null())
        .then(pl.lit("unknown"))
        .when(pl.col("component_turnover_20_60_ratio") <= 0.70)
        .then(pl.lit("liq20_60_le_0.70"))
        .when(pl.col("component_turnover_20_60_ratio") <= 0.90)
        .then(pl.lit("liq20_60_0.70_to_0.90"))
        .when(pl.col("component_turnover_20_60_ratio") <= 1.10)
        .then(pl.lit("liq20_60_0.90_to_1.10"))
        .otherwise(pl.lit("liq20_60_gt_1.10"))
    )


def add_down_streak(benchmark_df: pl.DataFrame) -> pl.DataFrame:
    """Add consecutive benchmark down-day counts."""
    streaks: list[int] = []
    streak = 0
    for ret in benchmark_df.sort("datetime")["pct_chg"].to_list():
        if ret is not None and ret < 0:
            streak += 1
        else:
            streak = 0
        streaks.append(streak)
    return benchmark_df.sort("datetime").with_columns(pl.Series("bm_down_streak", streaks))


def add_quantile_band(df: pl.DataFrame, column: str, output: str, *, low_label: str, high_label: str) -> pl.DataFrame:
    """Add descriptive quintile bands for a daily state variable."""
    series = df[column].drop_nulls()
    if series.is_empty():
        return df.with_columns(pl.lit("unknown").alias(output))
    q20 = to_float(series.quantile(0.2))
    q40 = to_float(series.quantile(0.4))
    q60 = to_float(series.quantile(0.6))
    q80 = to_float(series.quantile(0.8))
    return df.with_columns(
        pl.when(pl.col(column).is_null())
        .then(pl.lit("unknown"))
        .when(pl.col(column) <= q20)
        .then(pl.lit(f"q1_{low_label}"))
        .when(pl.col(column) <= q40)
        .then(pl.lit("q2"))
        .when(pl.col(column) <= q60)
        .then(pl.lit("q3"))
        .when(pl.col(column) <= q80)
        .then(pl.lit("q4"))
        .otherwise(pl.lit(f"q5_{high_label}"))
        .alias(output)
    )


def build_benchmark_state(benchmark_df: pl.DataFrame) -> pl.DataFrame:
    """Build benchmark-only ex-ante state variables."""
    bm = add_down_streak(benchmark_df).sort("datetime")
    bm = bm.with_columns(
        (pl.col("close") / pl.col("close").shift(1) - 1).alias("bm_ret_1"),
        (pl.col("close") / pl.col("close").shift(5) - 1).alias("bm_ret_5"),
        (pl.col("close") / pl.col("close").shift(10) - 1).alias("bm_ret_10"),
        (pl.col("close") / pl.col("close").shift(20) - 1).alias("bm_ret_20"),
        (pl.col("close") / pl.col("close").shift(60) - 1).alias("bm_ret_60"),
        pl.col("close").rolling_max(60).alias("bm_close_high_60"),
        pl.col("turnover").rolling_mean(20).alias("bm_turnover_ma20"),
        pl.col("turnover").rolling_mean(60).alias("bm_turnover_ma60"),
    ).with_columns(
        (pl.col("close") / pl.col("bm_close_high_60") - 1).alias("bm_drawdown_60"),
        (pl.col("turnover") / pl.col("bm_turnover_ma20")).alias("bm_turnover_ratio_20"),
        (pl.col("bm_turnover_ma20") / pl.col("bm_turnover_ma60")).alias("bm_turnover_20_60_ratio"),
        (pl.col("bm_ret_1").rolling_std(20) * sqrt(252)).alias("bm_vol20_annualized"),
    )
    return bm.select(
        pl.col("datetime").alias("date"),
        "bm_ret_1",
        "bm_ret_5",
        "bm_ret_10",
        "bm_ret_20",
        "bm_ret_60",
        "bm_drawdown_60",
        "bm_down_streak",
        "bm_turnover_ratio_20",
        "bm_turnover_20_60_ratio",
        "bm_vol20_annualized",
    )


def build_breadth_state(stock_df: pl.DataFrame, layer_tags: pl.DataFrame) -> pl.DataFrame:
    """Build daily cross-sectional breadth and liquidity states from local stock data."""
    stock_features = add_price_features(stock_df).join(layer_tags, on=["datetime", "symbol"], how="left")
    eligible = stock_features.filter(pl.col("eligible_component_row").fill_null(False))
    daily = (
        eligible.group_by("datetime")
        .agg(
            pl.len().alias("eligible_component_count"),
            (pl.col("ret_1") > 0).mean().alias("breadth_pos_1d_ratio"),
            (pl.col("ret_5") > 0).mean().alias("breadth_pos_5d_ratio"),
            (pl.col("ret_20") > 0).mean().alias("breadth_pos_20d_ratio"),
            pl.col("ret_20").median().alias("median_component_ret_20"),
            pl.col("ret_20").quantile(0.2).alias("p20_component_ret_20"),
            pl.col("turnover").sum().alias("component_turnover_sum"),
            pl.col("adv20_turnover").sum().alias("component_adv20_turnover_sum"),
            pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
            pl.col("turnover_rate_f").median().alias("median_turnover_rate_f"),
            pl.col("is_limit_down_close").fill_null(False).mean().alias("limit_down_close_ratio"),
            pl.col("is_limit_up_close").fill_null(False).mean().alias("limit_up_close_ratio"),
            (
                (pl.col("turnover_rate_f_q") >= 4)
                & (pl.col("adv20_turnover_q") >= 4)
                & pl.col("turnover_rate_f_q").is_not_null()
                & pl.col("adv20_turnover_q").is_not_null()
            )
            .mean()
            .alias("active_q4_q5_share"),
        )
        .sort("datetime")
        .with_columns(
            pl.col("component_turnover_sum").rolling_mean(20).alias("component_turnover_ma20"),
            pl.col("component_turnover_sum").rolling_mean(60).alias("component_turnover_ma60"),
        )
        .with_columns(
            (pl.col("component_turnover_ma20") / pl.col("component_turnover_ma60")).alias(
                "component_turnover_20_60_ratio"
            )
        )
    )
    return daily.rename({"datetime": "date"})


def build_date_state(stock_df: pl.DataFrame, benchmark_df: pl.DataFrame, layer_tags: pl.DataFrame) -> pl.DataFrame:
    """Build all ex-ante market state variables and descriptive bands."""
    date_state = build_benchmark_state(benchmark_df).join(
        build_breadth_state(stock_df, layer_tags), on="date", how="left"
    )
    date_state = date_state.with_columns(
        band_bm_ret_5().alias("bm_ret_5_band"),
        band_bm_ret_20().alias("bm_ret_20_band"),
        band_drawdown60().alias("bm_drawdown_60_band"),
        band_down_streak().alias("bm_down_streak_band"),
        band_breadth20().alias("breadth_pos_20d_band"),
        band_liquidity_ratio().alias("component_turnover_20_60_band"),
    )
    for column, output, low_label, high_label in [
        ("bm_vol20_annualized", "bm_vol20_q", "low_vol", "high_vol"),
        ("breadth_pos_20d_ratio", "breadth_pos_20d_q", "weak_breadth", "strong_breadth"),
        ("component_turnover_20_60_ratio", "component_turnover_20_60_q", "liquidity_contract", "liquidity_expand"),
        ("active_q4_q5_share", "active_q4_q5_share_q", "low_active_share", "high_active_share"),
        ("limit_down_close_ratio", "limit_down_close_ratio_q", "low_limit_down", "high_limit_down"),
    ]:
        date_state = add_quantile_band(date_state, column, output, low_label=low_label, high_label=high_label)
    return date_state.sort("date")


def build_signal_daily(selected: pl.DataFrame, date_state: pl.DataFrame) -> pl.DataFrame:
    """Build signal-date basket outcomes joined with ex-ante state."""
    signal_daily = (
        selected.group_by("datetime")
        .agg(
            pl.len().alias("candidate_count"),
            pl.col(f"fwd_ret_{HORIZON}").mean().alias("gross_basket_ret"),
            pl.col(f"fwd_excess_ret_{HORIZON}").mean().alias("gross_basket_excess_ret"),
            pl.first(f"bm_fwd_ret_{HORIZON}").alias("benchmark_forward_ret"),
            pl.col("adv20_turnover").median().alias("median_candidate_adv20_turnover")
            if "adv20_turnover" in selected.columns
            else pl.lit(None).alias("median_candidate_adv20_turnover"),
        )
        .rename({"datetime": "signal_date"})
        .with_columns(pl.col("signal_date").dt.year().alias("year"))
    )
    return signal_daily.join(date_state.rename({"date": "signal_date"}), on="signal_date", how="left")


def load_merged_equity() -> pl.DataFrame:
    """Load the baseline merged-holding path from stage 218."""
    path = MERGED_OUTPUT_DIR / f"{MERGED_PREFIX}_equity_curve.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    return pl.read_csv(path, try_parse_dates=True)


def build_path_daily(date_state: pl.DataFrame) -> pl.DataFrame:
    """Join merged-holding path returns with ex-ante daily market state."""
    return load_merged_equity().join(date_state, on="date", how="left").with_columns(
        pl.col("date").dt.year().alias("year"),
        ((pl.col("return_gross_exposure") > 0) | (pl.col("gross_abs_weight_change") > 0)).alias(
            "active_or_trade_day"
        ),
        (pl.col("strategy_drawdown") <= -0.10).alias("strategy_drawdown_le_10pct"),
        (pl.col("strategy_drawdown") <= -0.20).alias("strategy_drawdown_le_20pct"),
    )


def summarize_signal_by_state(signal_daily: pl.DataFrame, state_columns: list[str]) -> pl.DataFrame:
    """Summarize 10-day basket outcomes by ex-ante state."""
    frames: list[pl.DataFrame] = []
    for state_column in state_columns:
        if state_column not in signal_daily.columns:
            continue
        summary = (
            signal_daily.group_by(state_column)
            .agg(
                pl.len().alias("signal_days"),
                pl.col("candidate_count").sum().alias("stock_roundtrips"),
                pl.col("candidate_count").mean().alias("avg_candidate_count"),
                pl.col("gross_basket_ret").mean().alias("gross_basket_ret_mean"),
                pl.col("gross_basket_ret").std().alias("gross_basket_ret_std"),
                (pl.col("gross_basket_ret") > 0).mean().alias("gross_basket_ret_win_rate"),
                pl.col("gross_basket_excess_ret").mean().alias("gross_basket_excess_ret_mean"),
                pl.col("gross_basket_excess_ret").std().alias("gross_basket_excess_ret_std"),
                (pl.col("gross_basket_excess_ret") > 0).mean().alias("gross_basket_excess_ret_win_rate"),
                pl.col("benchmark_forward_ret").mean().alias("benchmark_forward_ret_mean"),
                pl.col("median_candidate_adv20_turnover").median().alias("median_candidate_adv20_turnover"),
                pl.col("year").is_in(STRESS_YEARS).mean().alias("stress_year_signal_ratio"),
            )
            .with_columns(
                pl.lit(state_column).alias("state_layer"),
                pl.col(state_column).cast(pl.String).alias("state_value"),
                (pl.col("gross_basket_ret_mean") - 0.002).alias("net20_basket_ret_mean"),
                (pl.col("gross_basket_ret_mean") - 0.005).alias("net50_basket_ret_mean"),
                pl.struct(["gross_basket_ret_mean", "gross_basket_ret_std", "signal_days"]).map_elements(
                    lambda row: t_stat(row["gross_basket_ret_mean"], row["gross_basket_ret_std"], row["signal_days"]),
                    return_dtype=pl.Float64,
                ).alias("gross_basket_ret_t"),
            )
            .drop(state_column, "gross_basket_ret_std", "gross_basket_excess_ret_std")
            .filter(pl.col("signal_days") >= MIN_SIGNAL_DAYS)
        )
        frames.append(summary)
    return pl.concat(frames, how="vertical").sort(["state_layer", "state_value"]) if frames else pl.DataFrame()


def summarize_path_by_state(path_daily: pl.DataFrame, state_columns: list[str]) -> pl.DataFrame:
    """Summarize merged path daily returns by ex-ante state."""
    frames: list[pl.DataFrame] = []
    for state_column in state_columns:
        if state_column not in path_daily.columns:
            continue
        summary = (
            path_daily.filter(pl.col("active_or_trade_day"))
            .group_by(["roundtrip_cost_bps", state_column])
            .agg(
                pl.len().alias("active_days"),
                pl.col("strategy_daily_ret").mean().alias("strategy_daily_ret_mean"),
                pl.col("strategy_daily_ret").std().alias("strategy_daily_ret_std"),
                (pl.col("strategy_daily_ret") > 0).mean().alias("strategy_daily_win_rate"),
                pl.col("strategy_gross_daily_ret").mean().alias("strategy_gross_daily_ret_mean"),
                pl.col("turnover_cost_ret").mean().alias("turnover_cost_ret_mean"),
                pl.col("return_gross_exposure").mean().alias("avg_gross_exposure"),
                pl.col("gross_abs_weight_change").mean().alias("avg_gross_abs_weight_change"),
                pl.col("strategy_drawdown_le_10pct").mean().alias("drawdown_le_10pct_day_ratio"),
                pl.col("strategy_drawdown_le_20pct").mean().alias("drawdown_le_20pct_day_ratio"),
                pl.col("year").is_in(STRESS_YEARS).mean().alias("stress_year_day_ratio"),
            )
            .with_columns(
                pl.lit(state_column).alias("state_layer"),
                pl.col(state_column).cast(pl.String).alias("state_value"),
                pl.struct(["strategy_daily_ret_mean", "strategy_daily_ret_std", "active_days"]).map_elements(
                    lambda row: t_stat(row["strategy_daily_ret_mean"], row["strategy_daily_ret_std"], row["active_days"]),
                    return_dtype=pl.Float64,
                ).alias("strategy_daily_ret_t"),
            )
            .drop(state_column, "strategy_daily_ret_std")
            .filter(pl.col("active_days") >= MIN_PATH_DAYS)
        )
        frames.append(summary)
    return pl.concat(frames, how="vertical").sort(["roundtrip_cost_bps", "state_layer", "state_value"]) if frames else pl.DataFrame()


def build_year_state_mix(signal_daily: pl.DataFrame, state_columns: list[str]) -> pl.DataFrame:
    """Build year-level state distribution on signal dates."""
    frames: list[pl.DataFrame] = []
    for state_column in state_columns:
        if state_column not in signal_daily.columns:
            continue
        frames.append(
            signal_daily.group_by(["year", state_column])
            .agg(pl.len().alias("signal_days"))
            .with_columns(
                pl.lit(state_column).alias("state_layer"),
                pl.col(state_column).cast(pl.String).alias("state_value"),
                (pl.col("signal_days") / pl.col("signal_days").sum().over("year")).alias("year_signal_share"),
            )
            .drop(state_column)
        )
    return pl.concat(frames, how="vertical").sort(["state_layer", "year", "state_value"]) if frames else pl.DataFrame()


def write_report(
    signal_summary: pl.DataFrame,
    path_summary: pl.DataFrame,
    weak_signal_states: pl.DataFrame,
    weak_path_states: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    """Write a Chinese state-variable attribution report."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡 market_down 状态变量归因 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是新策略版本，也不生成交易开关；只检查第218阶段合并持仓baseline的亏损是否能被信号日前可知的市场状态解释。",
        f"- 固定口径：`{MARKET_STATE}`、`{BUCKET}`、`{FEATURE}`、持有`{HORIZON}`日；成本情景：`{', '.join(str(x) for x in COST_BPS)}bp`。",
        "- 状态变量包括指数跌速、60日回撤、20日波动、下跌连续性、市场宽度、涨跌停压力、成交活跃收缩。",
        f"- 样本：信号日`{meta['signal_days']}`个，路径活跃/交易日历日`{meta['active_or_trade_calendar_days']}`个。",
        "",
        "## 信号日前状态最弱组",
        "",
    ]
    for row in weak_signal_states.head(12).iter_rows(named=True):
        lines.append(
            f"- `{row['state_layer']}`=`{row['state_value']}`：信号日`{row['signal_days']}`，"
            f"10日毛收益`{row['gross_basket_ret_mean']:.4%}`，20bp后`{row['net20_basket_ret_mean']:.4%}`，"
            f"毛胜率`{row['gross_basket_ret_win_rate']:.2%}`，压力年份占比`{row['stress_year_signal_ratio']:.2%}`。"
        )

    lines.extend(["", "## 持仓日状态最弱组", ""])
    for row in weak_path_states.head(12).iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['state_layer']}`=`{row['state_value']}`："
            f"活跃日`{row['active_days']}`，日净收益`{row['strategy_daily_ret_mean']:.4%}`，"
            f"胜率`{row['strategy_daily_win_rate']:.2%}`，平均暴露`{row['avg_gross_exposure']:.2%}`，"
            f"回撤<-20%日占比`{row['drawdown_le_20pct_day_ratio']:.2%}`。"
        )

    lines.extend(["", "## 重点状态观察", ""])
    for layer in [
        "bm_ret_5_band",
        "bm_drawdown_60_band",
        "breadth_pos_20d_band",
        "component_turnover_20_60_band",
    ]:
        layer_rows = signal_summary.filter(pl.col("state_layer") == layer).sort("gross_basket_ret_mean")
        if layer_rows.is_empty():
            continue
        worst = layer_rows.row(0, named=True)
        best = layer_rows.row(-1, named=True)
        lines.append(
            f"- `{layer}`：最弱`{worst['state_value']}` 10日毛收益`{worst['gross_basket_ret_mean']:.4%}`；"
            f"最强`{best['state_value']}` 10日毛收益`{best['gross_basket_ret_mean']:.4%}`。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果弱状态同时集中在低宽度、急跌、高波动、流动性收缩，并且样本足够，后续可以研究少参数市场状态开关。",
            "- 如果弱状态只是事后回撤段重合、信号日前收益差异不稳定，则不应继续组合化。",
            "- 这一步仍不触发第78 A/B，也不接入正式股票策略。",
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
    """Run ex-ante state-variable attribution for the merged market-down path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    selected, _benchmark_again, selected_meta = build_selected_frame()
    date_state = build_date_state(stock_df, benchmark_df, layer_tags)
    signal_daily = build_signal_daily(selected, date_state)
    path_daily = build_path_daily(date_state)
    state_columns = [
        "bm_ret_5_band",
        "bm_ret_20_band",
        "bm_drawdown_60_band",
        "bm_down_streak_band",
        "bm_vol20_q",
        "breadth_pos_20d_band",
        "breadth_pos_20d_q",
        "component_turnover_20_60_band",
        "component_turnover_20_60_q",
        "active_q4_q5_share_q",
        "limit_down_close_ratio_q",
    ]
    signal_summary = summarize_signal_by_state(signal_daily, state_columns)
    path_summary = summarize_path_by_state(path_daily, state_columns)
    year_state_mix = build_year_state_mix(signal_daily, state_columns)
    weak_signal_states = signal_summary.sort(["gross_basket_ret_mean", "signal_days"]).head(30)
    weak_path_states = path_summary.filter(pl.col("roundtrip_cost_bps") == 20).sort(
        ["strategy_daily_ret_mean", "active_days"]
    ).head(30)

    meta: dict[str, Any] = {
        **selected_meta,
        "feature": FEATURE,
        "bucket": BUCKET,
        "horizon": HORIZON,
        "market_state": MARKET_STATE,
        "cost_bps": COST_BPS,
        "signal_days": signal_daily.height,
        "active_or_trade_calendar_days": int(path_daily.filter(pl.col("active_or_trade_day")).select("date").n_unique()),
        "active_or_trade_cost_rows": int(path_daily.filter(pl.col("active_or_trade_day")).height),
        "state_columns": state_columns,
        "stress_years": STRESS_YEARS,
        "min_signal_days": MIN_SIGNAL_DAYS,
        "min_path_days": MIN_PATH_DAYS,
    }

    date_state_path = OUTPUT_DIR / f"{PREFIX}_date_state.csv"
    signal_daily_path = OUTPUT_DIR / f"{PREFIX}_signal_daily.csv"
    path_daily_path = OUTPUT_DIR / f"{PREFIX}_path_daily.csv"
    signal_summary_path = OUTPUT_DIR / f"{PREFIX}_signal_state_summary.csv"
    path_summary_path = OUTPUT_DIR / f"{PREFIX}_path_state_summary.csv"
    year_state_mix_path = OUTPUT_DIR / f"{PREFIX}_year_state_mix.csv"
    weak_signal_path = OUTPUT_DIR / f"{PREFIX}_weak_signal_states.csv"
    weak_path_path = OUTPUT_DIR / f"{PREFIX}_weak_path_states.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    date_state.write_csv(date_state_path)
    signal_daily.write_csv(signal_daily_path)
    path_daily.write_csv(path_daily_path)
    signal_summary.write_csv(signal_summary_path)
    path_summary.write_csv(path_summary_path)
    year_state_mix.write_csv(year_state_mix_path)
    weak_signal_states.write_csv(weak_signal_path)
    weak_path_states.write_csv(weak_path_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        signal_summary,
        path_summary,
        weak_signal_states,
        weak_path_states,
        meta,
        {
            "date_state": date_state_path,
            "signal_daily": signal_daily_path,
            "path_daily": path_daily_path,
            "signal_state_summary": signal_summary_path,
            "path_state_summary": path_summary_path,
            "year_state_mix": year_state_mix_path,
            "weak_signal_states": weak_signal_path,
            "weak_path_states": weak_path_path,
            "meta": meta_path,
        },
    )
    print(weak_signal_states.head(12))
    print(weak_path_states.head(12))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
