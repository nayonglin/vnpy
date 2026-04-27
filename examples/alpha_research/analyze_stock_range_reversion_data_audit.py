from __future__ import annotations

import json
import os
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

PREFIX: str = "stock_range_reversion_data_audit_v1"
HOLDING_DAYS: int = 5


def pct(numerator: float, denominator: float) -> float:
    """Return a stable percentage ratio."""
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def scalar(value: Any) -> Any:
    """Convert Polars/numpy scalar-like values into JSON-friendly values."""
    if hasattr(value, "item"):
        try:
            return value.item()
        except ValueError:
            pass
    return value


def load_inputs() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Load cached stock panel and benchmark data."""
    if not STOCK_PANEL_PATH.exists():
        raise FileNotFoundError(f"Missing stock panel: {STOCK_PANEL_PATH}")
    if not BENCHMARK_PATH.exists():
        raise FileNotFoundError(f"Missing benchmark panel: {BENCHMARK_PATH}")

    stock_df = normalize_stock_panel(pl.read_parquet(STOCK_PANEL_PATH)).sort(["symbol", "datetime"])
    benchmark_df = pl.read_parquet(BENCHMARK_PATH).sort("datetime")
    return stock_df, benchmark_df


def normalize_stock_panel(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize legacy and enriched panels into the audit schema."""
    if "raw_close" in df.columns:
        eligible_expr = (
            pl.col("eligible_component_row")
            if "eligible_component_row" in df.columns
            else pl.col("eligible_research_row")
            if "eligible_research_row" in df.columns
            else pl.lit(True)
        )
        return df.with_columns(
            pl.col("raw_open").alias("open"),
            pl.col("raw_high").alias("high"),
            pl.col("raw_low").alias("low"),
            pl.col("raw_close").alias("close"),
            pl.col("raw_preclose").alias("preclose"),
            pl.col("raw_up_limit").alias("up_limit"),
            pl.col("raw_down_limit").alias("down_limit"),
            pl.col("turnover_rate").alias("turn"),
            pl.col("pct_chg").alias("pctChg"),
            eligible_expr.alias("eligible_research_row"),
        )
    return df


def audit_calendar(stock_df: pl.DataFrame, benchmark_df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    """Audit symbol/date coverage against the benchmark trading calendar."""
    symbol_count = stock_df["symbol"].n_unique()
    benchmark_dates = benchmark_df.select("datetime").unique().sort("datetime")
    benchmark_date_count = benchmark_dates.height
    expected_rows = symbol_count * benchmark_date_count

    by_symbol = (
        stock_df.group_by("symbol")
        .agg(
            pl.len().alias("row_count"),
            pl.col("datetime").min().alias("first_date"),
            pl.col("datetime").max().alias("last_date"),
            pl.col("datetime").n_unique().alias("trade_days"),
        )
        .with_columns(
            (pl.lit(benchmark_date_count) - pl.col("trade_days")).alias("missing_days"),
            (pl.col("trade_days") / pl.lit(benchmark_date_count)).alias("coverage_ratio"),
        )
        .sort(["coverage_ratio", "symbol"])
    )

    by_date = (
        stock_df.group_by("datetime")
        .agg(pl.col("symbol").n_unique().alias("symbol_count"))
        .join(benchmark_dates, on="datetime", how="right")
        .with_columns(pl.col("symbol_count").fill_null(0))
        .with_columns(
            (pl.lit(symbol_count) - pl.col("symbol_count")).alias("missing_symbols"),
            (pl.col("symbol_count") / pl.lit(symbol_count)).alias("coverage_ratio"),
        )
        .sort("datetime")
    )

    summary = {
        "raw_rows": stock_df.height,
        "symbol_count": symbol_count,
        "benchmark_date_count": benchmark_date_count,
        "date_min": str(stock_df["datetime"].min()),
        "date_max": str(stock_df["datetime"].max()),
        "expected_symbol_date_rows": expected_rows,
        "missing_symbol_date_rows": expected_rows - stock_df.height,
        "calendar_coverage_ratio": pct(stock_df.height, expected_rows),
        "symbols_with_missing_days": int((by_symbol["missing_days"] > 0).sum()),
        "dates_with_missing_symbols": int((by_date["missing_symbols"] > 0).sum()),
        "min_symbols_per_day": scalar(by_date["symbol_count"].min()),
        "median_symbols_per_day": scalar(by_date["symbol_count"].median()),
        "max_symbols_per_day": scalar(by_date["symbol_count"].max()),
        "min_days_per_symbol": scalar(by_symbol["trade_days"].min()),
        "median_days_per_symbol": scalar(by_symbol["trade_days"].median()),
        "max_days_per_symbol": scalar(by_symbol["trade_days"].max()),
    }

    return by_symbol, by_date, summary


def audit_quality(stock_df: pl.DataFrame) -> pl.DataFrame:
    """Audit raw OHLCV and status field quality."""
    duplicate_rows = (
        stock_df.group_by(["datetime", "symbol"])
        .agg(pl.len().alias("row_count"))
        .filter(pl.col("row_count") > 1)
        .select((pl.col("row_count") - 1).sum().alias("duplicate_extra_rows"))
        .item()
    )

    checks: list[dict[str, Any]] = [
        {"check": "duplicate_extra_rows", "count": int(duplicate_rows), "ratio": pct(duplicate_rows, stock_df.height)},
    ]

    for col in ["open", "high", "low", "close", "preclose", "volume", "turnover", "turn", "pctChg"]:
        count = int(stock_df.select(pl.col(col).is_null().sum()).item())
        checks.append({"check": f"null_{col}", "count": count, "ratio": pct(count, stock_df.height)})

    invalid_ohlc = stock_df.filter(
        (pl.col("high") < pl.max_horizontal("open", "close", "low"))
        | (pl.col("low") > pl.min_horizontal("open", "close", "high"))
    ).height
    non_positive_price = stock_df.filter(
        (pl.col("open") <= 0)
        | (pl.col("high") <= 0)
        | (pl.col("low") <= 0)
        | (pl.col("close") <= 0)
        | (pl.col("preclose") <= 0)
    ).height
    zero_volume = stock_df.filter(pl.col("volume").fill_null(0) <= 0).height
    zero_turnover = stock_df.filter(pl.col("turnover").fill_null(0) <= 0).height
    suspended = stock_df.filter(pl.col("is_suspended")).height
    st_rows = stock_df.filter(pl.col("is_st")).height
    eligible_rows = int(stock_df["eligible_research_row"].sum()) if "eligible_research_row" in stock_df.columns else stock_df.height

    event_checks = [
        ("invalid_ohlc", invalid_ohlc),
        ("non_positive_price", non_positive_price),
        ("zero_or_null_volume", zero_volume),
        ("zero_or_null_turnover", zero_turnover),
        ("suspended_rows", suspended),
        ("st_rows", st_rows),
        ("eligible_research_rows", eligible_rows),
    ]
    for name, count in event_checks:
        checks.append({"check": name, "count": int(count), "ratio": pct(count, stock_df.height)})

    return pl.DataFrame(checks)


def build_filter_frame(stock_df: pl.DataFrame, benchmark_df: pl.DataFrame) -> pl.DataFrame:
    """Rebuild the existing 5-day tradability and label filters for audit."""
    eligible_expr = pl.col("eligible_research_row") if "eligible_research_row" in stock_df.columns else pl.lit(True)
    df = stock_df.with_columns(
        pl.col("close").shift(-1).over("symbol").alias("entry_close"),
        pl.col("open").shift(-1).over("symbol").alias("entry_open"),
        pl.col("high").shift(-1).over("symbol").alias("entry_high"),
        pl.col("low").shift(-1).over("symbol").alias("entry_low"),
        pl.col("is_suspended").shift(-1).over("symbol").alias("entry_is_suspended"),
        pl.col("is_st").shift(-1).over("symbol").alias("entry_is_st"),
        pl.col("up_limit").shift(-1).over("symbol").alias("entry_up_limit"),
        pl.col("close").shift(-HOLDING_DAYS).over("symbol").alias("exit_close"),
        pl.col("open").shift(-HOLDING_DAYS).over("symbol").alias("exit_open"),
        pl.col("high").shift(-HOLDING_DAYS).over("symbol").alias("exit_high"),
        pl.col("low").shift(-HOLDING_DAYS).over("symbol").alias("exit_low"),
        pl.col("is_suspended").shift(-HOLDING_DAYS).over("symbol").alias("exit_is_suspended"),
        pl.col("down_limit").shift(-HOLDING_DAYS).over("symbol").alias("exit_down_limit"),
    )

    df = df.with_columns(
        (~pl.col("entry_is_suspended").fill_null(True)).alias("pass_suspend_entry"),
        (~pl.col("exit_is_suspended").fill_null(True)).alias("pass_suspend_exit"),
        ((~pl.col("is_st").fill_null(True)) & (~pl.col("entry_is_st").fill_null(True))).alias("pass_st"),
        (
            (
                (pl.col("entry_open") == pl.col("entry_high"))
                & (pl.col("entry_high") == pl.col("entry_low"))
                & (pl.col("entry_low") == pl.col("entry_close"))
                & (pl.col("entry_close") >= pl.col("entry_up_limit") - 0.005)
            )
            .fill_null(True)
        ).alias("entry_oneword_limit_up"),
        (
            (
                (pl.col("exit_open") == pl.col("exit_high"))
                & (pl.col("exit_high") == pl.col("exit_low"))
                & (pl.col("exit_low") == pl.col("exit_close"))
                & (pl.col("exit_close") <= pl.col("exit_down_limit") + 0.005)
            )
            .fill_null(True)
        ).alias("exit_oneword_limit_down"),
    ).with_columns(
        (~pl.col("entry_oneword_limit_up")).alias("pass_limit_entry"),
        (~pl.col("exit_oneword_limit_down")).alias("pass_limit_exit"),
        (pl.col("exit_close") / pl.col("entry_close") - 1).alias("ret_5"),
    )

    bm = (
        benchmark_df.sort("datetime")
        .with_columns(
            pl.col("close").shift(-1).alias("bm_entry_close"),
            pl.col("close").shift(-HOLDING_DAYS).alias("bm_exit_close"),
        )
        .with_columns((pl.col("bm_exit_close") / pl.col("bm_entry_close") - 1).alias("bm_ret_5"))
        .select(["datetime", "bm_ret_5"])
    )

    df = df.join(bm, on="datetime", how="left").with_columns(
        (pl.col("ret_5") - pl.col("bm_ret_5")).alias("excess_ret_5"),
    )

    return df.with_columns(
        (
            pl.col("pass_suspend_entry")
            & pl.col("pass_suspend_exit")
            & pl.col("pass_st")
            & pl.col("pass_limit_entry")
            & pl.col("pass_limit_exit")
            & pl.col("ret_5").is_not_null()
            & pl.col("excess_ret_5").is_not_null()
            & (pl.col("volume") > 0)
            & (pl.col("turnover") > 0)
            & eligible_expr.fill_null(False)
        ).alias("final_keep")
    )


def audit_filters(filter_df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    """Summarize tradability filter losses and daily cross-section width."""
    raw_rows = filter_df.height
    filter_checks = [
        ("drop_missing_entry_bar", pl.col("entry_close").is_null()),
        ("drop_missing_exit_or_benchmark", pl.col("ret_5").is_null() | pl.col("excess_ret_5").is_null()),
        ("drop_entry_suspended_actual", pl.col("entry_is_suspended").fill_null(False)),
        ("drop_exit_suspended_actual", pl.col("exit_is_suspended").fill_null(False)),
        (
            "drop_st_or_entry_st_actual",
            pl.col("is_st").fill_null(False) | pl.col("entry_is_st").fill_null(False),
        ),
        ("drop_entry_oneword_limit_up_actual", pl.col("entry_oneword_limit_up").fill_null(False)),
        ("drop_exit_oneword_limit_down_actual", pl.col("exit_oneword_limit_down").fill_null(False)),
        ("drop_zero_or_null_volume", pl.col("volume").fill_null(0) <= 0),
        ("drop_zero_or_null_turnover", pl.col("turnover").fill_null(0) <= 0),
        ("final_keep", pl.col("final_keep")),
    ]

    rows: list[dict[str, Any]] = []
    for name, expr in filter_checks:
        count = int(filter_df.select(expr.sum()).item())
        rows.append({"item": name, "count": count, "ratio": pct(count, raw_rows)})

    daily_width = (
        filter_df.group_by("datetime")
        .agg(
            pl.len().alias("raw_symbol_count"),
            pl.col("final_keep").sum().alias("tradable_symbol_count"),
            pl.col("ret_5").is_not_null().sum().alias("valid_label_count"),
        )
        .with_columns(
            (pl.col("tradable_symbol_count") / pl.col("raw_symbol_count")).alias("tradable_ratio")
        )
        .sort("datetime")
    )

    effective_daily_width = daily_width.filter(pl.col("valid_label_count") > 0)
    summary = {
        "final_keep_rows": int(filter_df["final_keep"].sum()),
        "final_keep_ratio": pct(int(filter_df["final_keep"].sum()), raw_rows),
        "tradable_dates": daily_width.filter(pl.col("tradable_symbol_count") > 0).height,
        "min_tradable_symbols_per_day": scalar(daily_width["tradable_symbol_count"].min()),
        "median_tradable_symbols_per_day": scalar(daily_width["tradable_symbol_count"].median()),
        "max_tradable_symbols_per_day": scalar(daily_width["tradable_symbol_count"].max()),
        "effective_label_dates": effective_daily_width.height,
        "min_effective_tradable_symbols_per_day": scalar(effective_daily_width["tradable_symbol_count"].min()),
        "median_effective_tradable_symbols_per_day": scalar(effective_daily_width["tradable_symbol_count"].median()),
        "max_effective_tradable_symbols_per_day": scalar(effective_daily_width["tradable_symbol_count"].max()),
    }

    return pl.DataFrame(rows), daily_width, summary


def write_report(
    calendar_summary: dict[str, Any],
    quality_df: pl.DataFrame,
    filter_summary_df: pl.DataFrame,
    filter_summary: dict[str, Any],
    output_paths: dict[str, Path],
) -> Path:
    """Write a human-readable Chinese audit report."""
    quality_items = {row["check"]: row for row in quality_df.iter_rows(named=True)}
    filter_items = {row["item"]: row for row in filter_summary_df.iter_rows(named=True)}

    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡研究数据可用性审计 v1",
        "",
        "## 核心结论",
        "",
        "- 当前仓库没有发现已经落地的“股票震荡/股票均值回归”研究历史；已有的是股票 alpha 示例、成交量因子研究和 CSI1000 数据准备脚手架。",
        "- 现有股票缓存可以支撑股票震荡方向的第一轮信号层研究，但还不能支撑严肃正式回测。",
        f"- 数据覆盖：`{calendar_summary['symbol_count']}`只股票，`{calendar_summary['benchmark_date_count']}`个交易日，范围`{calendar_summary['date_min']}`到`{calendar_summary['date_max']}`。",
        f"- 样本完整度：预期 symbol-date 行`{calendar_summary['expected_symbol_date_rows']}`，实际`{calendar_summary['raw_rows']}`，缺口`{calendar_summary['missing_symbol_date_rows']}`，覆盖率`{calendar_summary['calendar_coverage_ratio']:.2%}`。",
        f"- 5日标签/交易过滤后保留`{filter_summary['final_keep_rows']}`行，占原始行`{filter_summary['final_keep_ratio']:.2%}`；有效标签日期中位每日可交易横截面宽度`{filter_summary['median_effective_tradable_symbols_per_day']}`。",
        "",
        "## 主要风险",
        "",
        "- 幸存者偏差风险高：现有 `public_zz1000_volume_research.py` 使用最新中证1000成分，且 `MAX_SYMBOLS` 默认只取300只；不是历史成分全量面板。",
        "- 复权风险高：现有 baostock 下载脚本使用 `adjustflag=\"3\"`，从生成逻辑看是不复权口径；没有复权因子列，股票震荡信号会被除权除息跳变污染。",
        "- 历史长度短：缓存只有2025-01-02到2026-04-17，只有约一年多数据，无法证明跨牛熊、跨风格有效。",
        "- 股票交易约束已有初步处理：停牌、ST、入场一字涨停、退出一字跌停和成交额/成交量过滤已经能重建，但还缺退市、上市天数、历史成分和复权确认。",
        "",
        "## 数据质量观察",
        "",
        f"- 重复 symbol-date 行：`{quality_items['duplicate_extra_rows']['count']}`。",
        f"- OHLC不一致行：`{quality_items['invalid_ohlc']['count']}`。",
        f"- 非正价格行：`{quality_items['non_positive_price']['count']}`。",
        f"- 零或空成交量行：`{quality_items['zero_or_null_volume']['count']}`。",
        f"- 零或空成交额行：`{quality_items['zero_or_null_turnover']['count']}`。",
        f"- 停牌行：`{quality_items['suspended_rows']['count']}`。",
        f"- ST行：`{quality_items['st_rows']['count']}`。",
        "",
        "## 交易过滤损耗",
        "",
        f"- 入场数据缺失：`{filter_items['drop_missing_entry_bar']['count']}`行。",
        f"- 出场或基准标签缺失：`{filter_items['drop_missing_exit_or_benchmark']['count']}`行，主要来自样本最后`{HOLDING_DAYS}`个交易日缺未来收益。",
        f"- 真实入场停牌：`{filter_items['drop_entry_suspended_actual']['count']}`行。",
        f"- 真实出场停牌：`{filter_items['drop_exit_suspended_actual']['count']}`行。",
        f"- 真实ST/次日ST：`{filter_items['drop_st_or_entry_st_actual']['count']}`行。",
        f"- 真实入场一字涨停：`{filter_items['drop_entry_oneword_limit_up_actual']['count']}`行。",
        f"- 真实出场一字跌停：`{filter_items['drop_exit_oneword_limit_down_actual']['count']}`行。",
        f"- 有效标签日期：`{filter_summary['effective_label_dates']}`个；有效日期每日可交易横截面最小/中位/最大为`{filter_summary['min_effective_tradable_symbols_per_day']}`/`{filter_summary['median_effective_tradable_symbols_per_day']}`/`{filter_summary['max_effective_tradable_symbols_per_day']}`。",
        "",
        "## 对股票震荡路线的判断",
        "",
        "- 可以继续，但下一步应是“信号层归因”，不是马上写组合回测或优化参数。",
        "- 第一性原理上，股票震荡的优势来自横截面宽度和仓位粒度；当前缓存的300只股票已经足够做 smoke test，但不足以证明可穿越周期。",
        "- Polanyi式手感：这份数据像一张能闻到市场气味的试纸，但还不是能上战场的地图；它适合验证超跌反弹有没有基本方向，不适合宣称策略可用。",
        "",
        "## 建议下一步",
        "",
        "1. 先做股票长侧超跌反弹的信号层归因：只看横截面排名后的未来1/3/5/10日收益分布，不做资金曲线。",
        "2. 信号必须用横截面 rank，而不是固定 RSI 阈值；先看分组单调性、Rank IC、市场状态分层。",
        "3. 同步补数据问题：确认复权口径，尽量扩展历史成分和更长年份；在这之前不做正式策略接入。",
        "",
        "## 输出文件",
        "",
    ]

    for name, path in output_paths.items():
        lines.append(f"- {name}: `{path}`")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    """Run stock range-reversion data audit."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stock_df, benchmark_df = load_inputs()
    by_symbol, by_date, calendar_summary = audit_calendar(stock_df, benchmark_df)
    quality_df = audit_quality(stock_df)
    filter_df = build_filter_frame(stock_df, benchmark_df)
    filter_summary_df, daily_width_df, filter_summary = audit_filters(filter_df)

    symbol_path = OUTPUT_DIR / f"{PREFIX}_symbol_coverage.csv"
    date_path = OUTPUT_DIR / f"{PREFIX}_date_coverage.csv"
    quality_path = OUTPUT_DIR / f"{PREFIX}_quality_summary.csv"
    filter_path = OUTPUT_DIR / f"{PREFIX}_filter_summary.csv"
    daily_width_path = OUTPUT_DIR / f"{PREFIX}_daily_tradable_width.csv"
    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.json"

    by_symbol.write_csv(symbol_path)
    by_date.write_csv(date_path)
    quality_df.write_csv(quality_path)
    filter_summary_df.write_csv(filter_path)
    daily_width_df.write_csv(daily_width_path)

    summary = {
        "calendar": calendar_summary,
        "filters": filter_summary,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    output_paths = {
        "symbol_coverage": symbol_path,
        "date_coverage": date_path,
        "quality_summary": quality_path,
        "filter_summary": filter_path,
        "daily_tradable_width": daily_width_path,
        "summary_json": summary_path,
    }
    report_path = write_report(calendar_summary, quality_df, filter_summary_df, filter_summary, output_paths)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
