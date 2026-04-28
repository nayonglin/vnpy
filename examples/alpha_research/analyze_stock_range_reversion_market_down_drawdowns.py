from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import add_forward_returns, add_price_features
from backtest_stock_range_reversion_market_down_long_only import (
    COST_BPS,
    FEATURE,
    HORIZON,
    MARKET_STATE,
    PREFIX as BACKTEST_PREFIX,
    add_path_return_columns,
    build_selected_candidates,
    build_stock_long,
    to_float,
)


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
BACKTEST_DIR: Path = Path(
    os.getenv(
        "BACKTEST_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_long_only_2018_2026"),
    )
).expanduser().resolve()
OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_drawdown_attribution_2018_2026"),
    )
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_market_down_drawdown_attribution_v1"


@dataclass(frozen=True)
class DrawdownSegment:
    roundtrip_cost_bps: float
    peak_date: Any
    trough_date: Any
    recovery_date: Any | None
    peak_equity: float
    trough_equity: float
    max_drawdown: float
    trading_days_peak_to_trough: int


def require_path(path: Path) -> Path:
    """Return an existing path or raise a clear error."""
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def load_backtest_outputs() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Load the previous minimum path backtest outputs."""
    summary = pl.read_csv(require_path(BACKTEST_DIR / f"{BACKTEST_PREFIX}_summary.csv"))
    equity = pl.read_csv(require_path(BACKTEST_DIR / f"{BACKTEST_PREFIX}_equity_curve.csv"), try_parse_dates=True)
    basket_daily = pl.read_csv(require_path(BACKTEST_DIR / f"{BACKTEST_PREFIX}_basket_daily.csv"), try_parse_dates=True)
    basket_horizon = pl.read_csv(require_path(BACKTEST_DIR / f"{BACKTEST_PREFIX}_basket_horizon.csv"), try_parse_dates=True)
    return summary, equity, basket_daily, basket_horizon


def find_max_drawdown_segment(curve: pl.DataFrame, cost_bps: float) -> DrawdownSegment:
    """Find the max peak-to-trough drawdown segment for one cost curve."""
    work = curve.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("pnl_date")
    if work.is_empty():
        raise ValueError(f"No equity curve for cost {cost_bps}")

    peak_equity = -1.0
    peak_date = None
    peak_index = 0
    worst: dict[str, Any] = {
        "drawdown": 0.0,
        "peak_date": None,
        "trough_date": None,
        "peak_equity": 0.0,
        "trough_equity": 0.0,
        "peak_index": 0,
        "trough_index": 0,
    }
    rows = list(work.select(["pnl_date", "strategy_equity"]).iter_rows(named=True))
    for index, row in enumerate(rows):
        equity = float(row["strategy_equity"])
        if equity > peak_equity:
            peak_equity = equity
            peak_date = row["pnl_date"]
            peak_index = index
        drawdown = equity / peak_equity - 1 if peak_equity > 0 else 0.0
        if drawdown < worst["drawdown"]:
            worst = {
                "drawdown": drawdown,
                "peak_date": peak_date,
                "trough_date": row["pnl_date"],
                "peak_equity": peak_equity,
                "trough_equity": equity,
                "peak_index": peak_index,
                "trough_index": index,
            }

    recovery_date = None
    if worst["peak_date"] is not None:
        for row in rows[int(worst["trough_index"]) + 1 :]:
            if float(row["strategy_equity"]) >= float(worst["peak_equity"]):
                recovery_date = row["pnl_date"]
                break

    return DrawdownSegment(
        roundtrip_cost_bps=cost_bps,
        peak_date=worst["peak_date"],
        trough_date=worst["trough_date"],
        recovery_date=recovery_date,
        peak_equity=float(worst["peak_equity"]),
        trough_equity=float(worst["trough_equity"]),
        max_drawdown=float(worst["drawdown"]),
        trading_days_peak_to_trough=int(worst["trough_index"] - worst["peak_index"] + 1),
    )


def segment_curve(equity: pl.DataFrame, segment: DrawdownSegment) -> pl.DataFrame:
    """Return one cost curve restricted to a drawdown segment."""
    return equity.filter(
        (pl.col("roundtrip_cost_bps") == segment.roundtrip_cost_bps)
        & (pl.col("pnl_date") >= segment.peak_date)
        & (pl.col("pnl_date") <= segment.trough_date)
    ).sort("pnl_date")


def summarize_drawdown_segments(equity: pl.DataFrame) -> tuple[pl.DataFrame, list[DrawdownSegment]]:
    """Summarize max drawdown segments for all configured cost scenarios."""
    rows: list[dict[str, Any]] = []
    segments: list[DrawdownSegment] = []
    for cost_bps in COST_BPS:
        segment = find_max_drawdown_segment(equity, cost_bps)
        segments.append(segment)
        seg_curve = segment_curve(equity, segment)
        benchmark_peak = to_float(seg_curve["benchmark_equity"][0]) if seg_curve.height else 0.0
        benchmark_trough = to_float(seg_curve["benchmark_equity"][-1]) if seg_curve.height else 0.0
        rows.append(
            {
                "roundtrip_cost_bps": cost_bps,
                "peak_date": segment.peak_date,
                "trough_date": segment.trough_date,
                "recovery_date": segment.recovery_date,
                "peak_equity": segment.peak_equity,
                "trough_equity": segment.trough_equity,
                "max_drawdown": segment.max_drawdown,
                "trading_days_peak_to_trough": segment.trading_days_peak_to_trough,
                "strategy_return_peak_to_trough": segment.trough_equity / segment.peak_equity - 1,
                "active_benchmark_return_peak_to_trough": benchmark_trough / benchmark_peak - 1
                if benchmark_peak
                else 0.0,
                "avg_gross_exposure": to_float(seg_curve["gross_exposure"].mean()) if seg_curve.height else 0.0,
                "max_gross_exposure": to_float(seg_curve["gross_exposure"].max()) if seg_curve.height else 0.0,
                "avg_active_sleeves": to_float(seg_curve["active_sleeves"].mean()) if seg_curve.height else 0.0,
                "max_active_sleeves": int(seg_curve["active_sleeves"].max()) if seg_curve.height else 0,
                "avg_active_stock_positions": to_float(seg_curve["active_stock_positions"].mean())
                if seg_curve.height
                else 0.0,
                "negative_day_ratio": to_float((seg_curve["strategy_daily_ret"] < 0).mean()) if seg_curve.height else 0.0,
            }
        )
    return pl.DataFrame(rows), segments


def build_cohort_contribution(
    basket_daily: pl.DataFrame,
    basket_horizon: pl.DataFrame,
    segments: list[DrawdownSegment],
) -> pl.DataFrame:
    """Attribute drawdown-period path returns by signal-date cohort."""
    frames: list[pl.DataFrame] = []
    for segment in segments:
        daily_cost = (segment.roundtrip_cost_bps / 10000.0) / HORIZON
        work = basket_daily.filter(
            (pl.col("pnl_date") >= segment.peak_date) & (pl.col("pnl_date") <= segment.trough_date)
        ).with_columns(
            ((pl.col("basket_stock_daily_ret") - daily_cost) / HORIZON).alias("strategy_component_ret"),
            (pl.col("benchmark_daily_ret") / HORIZON).alias("benchmark_component_ret"),
        )
        cohort = (
            work.group_by("signal_date")
            .agg(
                pl.len().alias("active_holding_rows"),
                pl.col("pnl_date").min().alias("first_pnl_date"),
                pl.col("pnl_date").max().alias("last_pnl_date"),
                pl.col("stock_count").mean().alias("avg_stock_count"),
                pl.col("strategy_component_ret").sum().alias("strategy_component_ret_sum"),
                pl.col("benchmark_component_ret").sum().alias("benchmark_component_ret_sum"),
                pl.col("basket_stock_daily_ret").mean().alias("avg_basket_stock_daily_ret"),
            )
            .join(basket_horizon, on="signal_date", how="left")
            .with_columns(
                pl.lit(segment.roundtrip_cost_bps).alias("roundtrip_cost_bps"),
                pl.lit(segment.peak_date).alias("segment_peak_date"),
                pl.lit(segment.trough_date).alias("segment_trough_date"),
            )
            .sort("strategy_component_ret_sum")
        )
        frames.append(cohort)
    return pl.concat(frames, how="vertical") if frames else pl.DataFrame()


def build_selected_stock_long() -> pl.DataFrame:
    """Rebuild selected stock-level holding rows for industry and market contribution."""
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    df = add_forward_returns(add_price_features(stock_df), benchmark_df).join(
        layer_tags, on=["datetime", "symbol"], how="left"
    )
    df = add_path_return_columns(df)
    top_df = build_selected_candidates(df)
    stock_long = build_stock_long(top_df)
    count_df = (
        stock_long.group_by(["signal_date", "holding_day", "pnl_date"])
        .agg(pl.len().alias("basket_stock_count"))
    )
    return stock_long.join(count_df, on=["signal_date", "holding_day", "pnl_date"], how="left")


def build_group_contribution(
    stock_long: pl.DataFrame,
    segments: list[DrawdownSegment],
    group_col: str,
) -> pl.DataFrame:
    """Attribute drawdown-period stock-level path returns by one group column."""
    frames: list[pl.DataFrame] = []
    label_col = group_col if group_col in stock_long.columns else None
    for segment in segments:
        daily_cost = (segment.roundtrip_cost_bps / 10000.0) / HORIZON
        work = stock_long.filter(
            (pl.col("pnl_date") >= segment.peak_date) & (pl.col("pnl_date") <= segment.trough_date)
        )
        if label_col:
            work = work.with_columns(pl.col(label_col).fill_null("unknown").cast(pl.String).alias("group_value"))
        else:
            work = work.with_columns(pl.lit("unknown").alias("group_value"))
        work = work.with_columns(
            ((pl.col("stock_daily_ret") - daily_cost) / pl.col("basket_stock_count") / HORIZON).alias(
                "strategy_component_ret"
            )
        )
        group = (
            work.group_by("group_value")
            .agg(
                pl.len().alias("stock_holding_rows"),
                pl.col("signal_date").n_unique().alias("signal_days"),
                pl.col("symbol").n_unique().alias("symbol_count"),
                pl.col("stock_daily_ret").mean().alias("avg_stock_daily_ret"),
                pl.col("strategy_component_ret").sum().alias("strategy_component_ret_sum"),
            )
            .with_columns(
                (pl.col("stock_holding_rows") / pl.col("stock_holding_rows").sum()).alias("row_share"),
                pl.lit(segment.roundtrip_cost_bps).alias("roundtrip_cost_bps"),
                pl.lit(segment.peak_date).alias("segment_peak_date"),
                pl.lit(segment.trough_date).alias("segment_trough_date"),
                pl.lit(group_col).alias("group_col"),
            )
            .sort("strategy_component_ret_sum")
        )
        frames.append(group)
    return pl.concat(frames, how="vertical") if frames else pl.DataFrame()


def build_year_path_summary(equity: pl.DataFrame, basket_horizon: pl.DataFrame) -> pl.DataFrame:
    """Summarize year-level path returns and basket returns."""
    year_path = (
        equity.with_columns(pl.col("pnl_date").dt.year().alias("year"))
        .group_by(["roundtrip_cost_bps", "year"])
        .agg(
            (pl.col("strategy_equity").last() / pl.col("strategy_equity").first() - 1).alias(
                "simple_year_path_return"
            ),
            pl.col("strategy_drawdown").min().alias("min_drawdown_seen"),
            pl.col("gross_exposure").mean().alias("avg_exposure"),
            pl.col("active_sleeves").mean().alias("avg_active_sleeves"),
        )
    )
    basket_year = (
        basket_horizon.with_columns(pl.col("signal_date").dt.year().alias("year"))
        .group_by("year")
        .agg(
            pl.len().alias("basket_count"),
            pl.col("gross_basket_ret").mean().alias("gross_basket_ret_mean"),
            pl.col("gross_basket_excess_ret").mean().alias("gross_basket_excess_ret_mean"),
            pl.col("benchmark_horizon_ret").mean().alias("benchmark_horizon_ret_mean"),
        )
    )
    return year_path.join(basket_year, on="year", how="left").sort(["roundtrip_cost_bps", "year"])


def write_report(
    drawdown_df: pl.DataFrame,
    cohort_df: pl.DataFrame,
    industry_df: pl.DataFrame,
    market_df: pl.DataFrame,
    year_df: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    """Write a Chinese drawdown attribution report."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡 market_down 回撤归因 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是新策略回测，也没有新增交易过滤器；只拆解第214阶段固定路径的最大回撤来源。",
        f"- 回测口径沿用：`{MARKET_STATE}`、`{FEATURE}`、固定持有`{HORIZON}`日；成本情景为`{', '.join(str(x) for x in COST_BPS)}bp`。",
        "- 归因重点：最大回撤段、拖累最大的信号篮子、行业/市场板块贡献、年度路径。",
        "",
        "## 最大回撤段",
        "",
    ]

    for row in drawdown_df.sort("roundtrip_cost_bps").iter_rows(named=True):
        recovery = row["recovery_date"] if row["recovery_date"] is not None else "未恢复"
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp`：峰值`{row['peak_date']}`到谷底`{row['trough_date']}`，"
            f"回撤`{row['max_drawdown']:.2%}`，交易日`{row['trading_days_peak_to_trough']}`，恢复日`{recovery}`。"
        )
        lines.append(
            f"  段内同暴露基准`{row['active_benchmark_return_peak_to_trough']:.2%}`，"
            f"平均暴露`{row['avg_gross_exposure']:.2%}`，平均重叠篮子`{row['avg_active_sleeves']:.2f}`，"
            f"负收益日`{row['negative_day_ratio']:.2%}`。"
        )

    lines.extend(["", "## 拖累最大的信号篮子", ""])
    for cost_bps in sorted(cohort_df["roundtrip_cost_bps"].unique().to_list()):
        worst = cohort_df.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("strategy_component_ret_sum").head(6)
        lines.append(f"- 成本`{cost_bps:.0f}bp`最大回撤段：")
        for row in worst.iter_rows(named=True):
            lines.append(
                f"  - 信号日`{row['signal_date']}`：段内贡献`{row['strategy_component_ret_sum']:.4%}`，"
                f"10日篮子毛收益`{row['gross_basket_ret']:.4%}`，基准同期`{row['benchmark_horizon_ret']:.4%}`，"
                f"候选`{row['candidate_count']}`只。"
            )

    lines.extend(["", "## 行业拖累", ""])
    for cost_bps in sorted(industry_df["roundtrip_cost_bps"].unique().to_list()):
        worst = industry_df.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("strategy_component_ret_sum").head(8)
        lines.append(f"- 成本`{cost_bps:.0f}bp`最大回撤段：")
        for row in worst.iter_rows(named=True):
            lines.append(
                f"  - `{row['group_value']}`：贡献`{row['strategy_component_ret_sum']:.4%}`，"
                f"占持仓行`{row['row_share']:.2%}`，股票数`{row['symbol_count']}`。"
            )

    lines.extend(["", "## 市场板块拖累", ""])
    for cost_bps in sorted(market_df["roundtrip_cost_bps"].unique().to_list()):
        focus = market_df.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("strategy_component_ret_sum")
        lines.append(f"- 成本`{cost_bps:.0f}bp`最大回撤段：")
        for row in focus.iter_rows(named=True):
            lines.append(
                f"  - `{row['group_value']}`：贡献`{row['strategy_component_ret_sum']:.4%}`，"
                f"占持仓行`{row['row_share']:.2%}`，股票数`{row['symbol_count']}`。"
            )

    lines.extend(["", "## 年度路径观察", ""])
    focus_year = year_df.filter(pl.col("year").is_in([2018, 2022, 2024]))
    for row in focus_year.sort(["roundtrip_cost_bps", "year"]).iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['year']}`：路径收益`{row['simple_year_path_return']:.2%}`，"
            f"年内最低回撤`{row['min_drawdown_seen']:.2%}`，平均暴露`{row['avg_exposure']:.2%}`，"
            f"篮子数`{row['basket_count']}`，篮子毛收益`{row['gross_basket_ret_mean']:.4%}`。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果最大回撤段主要由连续市场下跌和满重叠篮子造成，下一步应研究外生风险预算和暂停新增篮子的规则，而不是调超跌阈值。",
            "- 如果拖累集中在少数行业，后续可以先做行业暴露上限归因；这仍是风控归因，不是收益优化。",
            "- 这一步不触发第78 A/B，也不接入正式策略。",
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
    """Run drawdown attribution for the fixed market-down path backtest."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, equity, basket_daily, basket_horizon = load_backtest_outputs()
    drawdown_df, segments = summarize_drawdown_segments(equity)
    cohort_df = build_cohort_contribution(basket_daily, basket_horizon, segments)
    stock_long = build_selected_stock_long()
    industry_df = build_group_contribution(stock_long, segments, "industry")
    market_df = build_group_contribution(stock_long, segments, "market")
    year_df = build_year_path_summary(equity, basket_horizon)

    meta: dict[str, Any] = {
        "source_backtest_dir": str(BACKTEST_DIR),
        "feature": FEATURE,
        "horizon": HORIZON,
        "market_state": MARKET_STATE,
        "cost_bps": COST_BPS,
        "summary_rows": summary.height,
        "equity_rows": equity.height,
        "basket_daily_rows": basket_daily.height,
        "basket_horizon_rows": basket_horizon.height,
    }

    drawdown_path = OUTPUT_DIR / f"{PREFIX}_drawdown_segments.csv"
    cohort_path = OUTPUT_DIR / f"{PREFIX}_cohort_contribution.csv"
    industry_path = OUTPUT_DIR / f"{PREFIX}_industry_contribution.csv"
    market_path = OUTPUT_DIR / f"{PREFIX}_market_contribution.csv"
    year_path = OUTPUT_DIR / f"{PREFIX}_year_path_summary.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    drawdown_df.write_csv(drawdown_path)
    cohort_df.write_csv(cohort_path)
    industry_df.write_csv(industry_path)
    market_df.write_csv(market_path)
    year_df.write_csv(year_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        drawdown_df,
        cohort_df,
        industry_df,
        market_df,
        year_df,
        meta,
        {
            "drawdown_segments": drawdown_path,
            "cohort_contribution": cohort_path,
            "industry_contribution": industry_path,
            "market_contribution": market_path,
            "year_path_summary": year_path,
            "meta": meta_path,
        },
    )
    print(drawdown_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
