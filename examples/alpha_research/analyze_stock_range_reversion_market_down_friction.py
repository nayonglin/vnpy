from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_active_bucket_stability import add_groups
from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import add_forward_returns, add_price_features
from backtest_stock_range_reversion_market_down_long_only import (
    FEATURE,
    HORIZON,
    MARKET_STATE,
    add_path_return_columns,
    build_selected_candidates,
    build_stock_long,
    get_bucket_definition,
    to_float,
)


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_trade_friction_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_market_down_trade_friction_v1"
PARTICIPATION_RATES: tuple[float, ...] = (0.01, 0.02, 0.05, 0.10)
LIMIT_EPS: float = 0.005


def pct(numerator: float, denominator: float) -> float:
    """Return a stable ratio."""
    return float(numerator) / float(denominator) if denominator else 0.0


def load_research_frame() -> pl.DataFrame:
    """Load local stock data and add fixed signal, return, and layer fields."""
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    df = add_forward_returns(add_price_features(stock_df), benchmark_df).join(
        layer_tags, on=["datetime", "symbol"], how="left"
    )
    df = df.sort(["symbol", "datetime"]).with_columns(
        pl.col("trade_down_limit").shift(-1).over("symbol").alias("entry_trade_down_limit"),
        pl.col("is_limit_up_close").shift(-1).over("symbol").alias("entry_is_limit_up_close"),
        pl.col("is_limit_down_close").shift(-1).over("symbol").alias("entry_is_limit_down_close"),
        pl.col("is_oneword_limit_down").shift(-1).over("symbol").alias("entry_oneword_limit_down"),
        pl.col("is_limit_up_close").shift(-(HORIZON + 1)).over("symbol").alias(f"exit_is_limit_up_close_{HORIZON}"),
        pl.col("is_limit_down_close")
        .shift(-(HORIZON + 1))
        .over("symbol")
        .alias(f"exit_is_limit_down_close_{HORIZON}"),
    )
    return add_path_return_columns(df)


def base_signal_filter() -> pl.Expr:
    """Return signal-date-only filter before forward tradability constraints."""
    _description, bucket_expr = get_bucket_definition()
    return (
        bucket_expr
        & (pl.col("market_state_20d") == MARKET_STATE)
        & pl.col("eligible_research_row").fill_null(False)
        & pl.col(FEATURE).is_not_null()
        & pl.col(FEATURE).is_finite()
    )


def build_raw_top_candidates(df: pl.DataFrame) -> pl.DataFrame:
    """Build top-quintile candidates before applying final forward tradability."""
    work = df.filter(base_signal_filter())
    return add_groups(work, FEATURE, []).filter(pl.col("feature_group") == 5)


def build_raw_candidate_friction(raw_top: pl.DataFrame) -> pl.DataFrame:
    """Summarize why raw top candidates do or do not pass final tradability."""
    reason_exprs = {
        "pass_final_keep": pl.col(f"final_keep_{HORIZON}").fill_null(False),
        "entry_suspended": pl.col("entry_is_suspended").fill_null(True),
        "current_st": pl.col("is_st").fill_null(True),
        "entry_st": pl.col("entry_is_st").fill_null(True),
        "entry_oneword_limit_up": pl.col("entry_oneword_limit_up").fill_null(True),
        "exit_suspended": pl.col(f"exit_is_suspended_{HORIZON}").fill_null(True),
        "exit_oneword_limit_down": pl.col(f"exit_oneword_limit_down_{HORIZON}").fill_null(True),
        "entry_not_eligible": ~pl.col("entry_eligible_research_row").fill_null(False),
        "exit_not_eligible": ~pl.col(f"exit_eligible_research_row_{HORIZON}").fill_null(False),
        "missing_fwd_ret": pl.col(f"fwd_ret_{HORIZON}").is_null()
        | pl.col(f"fwd_excess_ret_{HORIZON}").is_null(),
    }
    total = raw_top.height
    rows: list[dict[str, Any]] = []
    for reason, expr in reason_exprs.items():
        count = int(raw_top.select(expr.sum()).item()) if total else 0
        rows.append({"reason": reason, "count": count, "ratio": pct(count, total)})

    by_year = raw_top.with_columns(pl.col("datetime").dt.year().alias("year")).group_by("year").agg(
        pl.len().alias("raw_top_count"),
        pl.col(f"final_keep_{HORIZON}").fill_null(False).sum().alias("pass_final_keep_count"),
        pl.col("entry_oneword_limit_up").fill_null(True).sum().alias("entry_oneword_limit_up_count"),
        pl.col(f"exit_oneword_limit_down_{HORIZON}").fill_null(True).sum().alias("exit_oneword_limit_down_count"),
        pl.col("entry_is_suspended").fill_null(True).sum().alias("entry_suspended_count"),
        pl.col(f"exit_is_suspended_{HORIZON}").fill_null(True).sum().alias("exit_suspended_count"),
    ).with_columns(
        (pl.col("pass_final_keep_count") / pl.col("raw_top_count")).alias("pass_final_keep_ratio"),
        pl.lit("year_summary").alias("reason"),
    )
    reason_df = pl.DataFrame(rows).with_columns(pl.lit(None, dtype=pl.Int64).alias("year"))
    return pl.concat(
        [
            reason_df.select(["year", "reason", "count", "ratio"]),
            by_year.select(
                [
                    pl.col("year").cast(pl.Int64),
                    "reason",
                    pl.col("raw_top_count").cast(pl.Int64).alias("count"),
                    pl.col("pass_final_keep_ratio").alias("ratio"),
                ]
            ),
        ],
        how="vertical",
    )


def build_selected_entry_exit_friction(selected: pl.DataFrame) -> pl.DataFrame:
    """Summarize edge tradability risks for selected candidates."""
    selected = selected.with_columns(
        (pl.col("entry_trade_close") >= pl.col("entry_trade_up_limit") - LIMIT_EPS)
        .fill_null(False)
        .alias("entry_close_at_up_limit"),
        (pl.col("entry_trade_close") <= pl.col("entry_trade_down_limit") + LIMIT_EPS)
        .fill_null(False)
        .alias("entry_close_at_down_limit"),
        (pl.col(f"exit_trade_close_{HORIZON}") <= pl.col(f"exit_trade_down_limit_{HORIZON}") + LIMIT_EPS)
        .fill_null(False)
        .alias("exit_close_at_down_limit"),
        pl.col(f"exit_is_limit_up_close_{HORIZON}").fill_null(False).alias("exit_close_at_up_limit"),
    )
    total = selected.height
    fields = [
        "entry_oneword_limit_up",
        "entry_oneword_limit_down",
        "entry_close_at_up_limit",
        "entry_close_at_down_limit",
        f"exit_oneword_limit_down_{HORIZON}",
        "exit_close_at_down_limit",
        "exit_close_at_up_limit",
        "entry_is_suspended",
        f"exit_is_suspended_{HORIZON}",
    ]
    rows: list[dict[str, Any]] = []
    for field in fields:
        count = int(selected.select(pl.col(field).fill_null(False).sum()).item()) if total else 0
        rows.append({"field": field, "count": count, "ratio": pct(count, total)})
    return pl.DataFrame(rows)


def build_holding_friction(selected: pl.DataFrame, df: pl.DataFrame) -> pl.DataFrame:
    """Summarize limit and suspension states during holding days."""
    stock_long = build_stock_long(selected)
    status_cols = [
        "datetime",
        "symbol",
        "is_suspended",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
        "is_limit_up_close",
        "is_limit_down_close",
        "turnover",
        "adv20_turnover",
    ]
    status = df.select([col for col in status_cols if col in df.columns]).rename({"datetime": "pnl_date"})
    holding = stock_long.join(status, on=["pnl_date", "symbol"], how="left")
    total = holding.height
    rows: list[dict[str, Any]] = []
    for field in [
        "is_suspended",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
        "is_limit_up_close",
        "is_limit_down_close",
    ]:
        count = int(holding.select(pl.col(field).fill_null(False).sum()).item()) if total else 0
        rows.append({"field": field, "count": count, "ratio": pct(count, total)})
    zero_turnover = int(holding.select((pl.col("turnover").fill_null(0) <= 0).sum()).item()) if total else 0
    rows.append({"field": "zero_or_missing_turnover", "count": zero_turnover, "ratio": pct(zero_turnover, total)})
    return pl.DataFrame(rows)


def build_capacity_summary(selected: pl.DataFrame) -> pl.DataFrame:
    """Estimate equal-weight sleeve capacity from ADV participation rates."""
    daily = selected.group_by("datetime").agg(
        pl.len().alias("candidate_count"),
        pl.col("adv20_turnover").sum().alias("sum_adv20_turnover"),
        pl.col("adv20_turnover").quantile(0.1).alias("p10_adv20_turnover"),
        pl.col("adv20_turnover").quantile(0.2).alias("p20_adv20_turnover"),
        pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
    )
    rows: list[dict[str, Any]] = []
    for participation in PARTICIPATION_RATES:
        cap = daily.with_columns(
            (pl.col("sum_adv20_turnover") * participation).alias("one_sleeve_sum_capacity_yuan"),
            (pl.col("candidate_count") * pl.col("p10_adv20_turnover") * participation).alias(
                "one_sleeve_equal_weight_capacity_p10_yuan"
            ),
            (pl.col("candidate_count") * pl.col("p20_adv20_turnover") * participation).alias(
                "one_sleeve_equal_weight_capacity_p20_yuan"
            ),
            (pl.col("candidate_count") * pl.col("median_adv20_turnover") * participation).alias(
                "one_sleeve_equal_weight_capacity_median_yuan"
            ),
        ).with_columns(
            (pl.col("one_sleeve_sum_capacity_yuan") * HORIZON).alias("strategy_sum_capacity_yuan"),
            (pl.col("one_sleeve_equal_weight_capacity_p10_yuan") * HORIZON).alias(
                "strategy_equal_weight_capacity_p10_yuan"
            ),
            (pl.col("one_sleeve_equal_weight_capacity_p20_yuan") * HORIZON).alias(
                "strategy_equal_weight_capacity_p20_yuan"
            ),
            (pl.col("one_sleeve_equal_weight_capacity_median_yuan") * HORIZON).alias(
                "strategy_equal_weight_capacity_median_yuan"
            ),
        )
        rows.append(
            {
                "participation_rate": participation,
                "days": cap.height,
                "median_candidate_count": to_float(cap["candidate_count"].median()),
                "median_strategy_sum_capacity_yuan": to_float(cap["strategy_sum_capacity_yuan"].median()),
                "p25_strategy_sum_capacity_yuan": to_float(cap["strategy_sum_capacity_yuan"].quantile(0.25)),
                "median_strategy_equal_weight_capacity_p10_yuan": to_float(
                    cap["strategy_equal_weight_capacity_p10_yuan"].median()
                ),
                "median_strategy_equal_weight_capacity_p20_yuan": to_float(
                    cap["strategy_equal_weight_capacity_p20_yuan"].median()
                ),
                "median_strategy_equal_weight_capacity_median_yuan": to_float(
                    cap["strategy_equal_weight_capacity_median_yuan"].median()
                ),
            }
        )
    return pl.DataFrame(rows)


def build_overlap_summary(selected: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Build holding-day same-symbol overlap and adjacent basket overlap summaries."""
    stock_long = build_stock_long(selected)
    lots = stock_long.group_by(["pnl_date", "symbol"]).agg(pl.len().alias("active_lots"))
    daily = lots.group_by("pnl_date").agg(
        pl.len().alias("active_symbols"),
        pl.col("active_lots").sum().alias("active_lot_rows"),
        (pl.col("active_lots") > 1).sum().alias("duplicated_symbols"),
        (pl.col("active_lots") - 1).clip(0).sum().alias("extra_duplicate_lots"),
        pl.col("active_lots").max().alias("max_symbol_lots"),
    ).with_columns(
        (pl.col("duplicated_symbols") / pl.col("active_symbols")).alias("duplicated_symbol_ratio"),
        (pl.col("extra_duplicate_lots") / pl.col("active_lot_rows")).alias("extra_duplicate_lot_share"),
    )
    daily_summary = daily.select(
        pl.len().alias("days"),
        pl.col("active_symbols").mean().alias("avg_active_symbols"),
        pl.col("active_lot_rows").mean().alias("avg_active_lot_rows"),
        pl.col("duplicated_symbols").mean().alias("avg_duplicated_symbols"),
        pl.col("duplicated_symbol_ratio").mean().alias("avg_duplicated_symbol_ratio"),
        pl.col("extra_duplicate_lot_share").mean().alias("avg_extra_duplicate_lot_share"),
        pl.col("max_symbol_lots").max().alias("max_symbol_lots"),
    )

    symbol_summary = lots.group_by("symbol").agg(
        pl.len().alias("holding_days"),
        pl.col("active_lots").max().alias("max_active_lots"),
        (pl.col("active_lots") > 1).mean().alias("duplicate_day_ratio"),
    ).sort(["max_active_lots", "duplicate_day_ratio"], descending=[True, True])

    by_date = {
        date: set(symbols)
        for date, symbols in selected.group_by("datetime").agg(pl.col("symbol")).iter_rows()
    }
    dates = sorted(by_date)
    overlap_rows: list[dict[str, Any]] = []
    for prev_date, next_date in zip(dates, dates[1:]):
        prev_symbols = by_date[prev_date]
        next_symbols = by_date[next_date]
        overlap_count = len(prev_symbols & next_symbols)
        overlap_rows.append(
            {
                "prev_signal_date": prev_date,
                "next_signal_date": next_date,
                "prev_count": len(prev_symbols),
                "next_count": len(next_symbols),
                "overlap_count": overlap_count,
                "overlap_to_prev": pct(overlap_count, len(prev_symbols)),
                "overlap_to_next": pct(overlap_count, len(next_symbols)),
                "turnover_to_next": 1 - pct(overlap_count, len(next_symbols)),
            }
        )
    adjacent_overlap = pl.DataFrame(overlap_rows)
    return daily_summary, symbol_summary, adjacent_overlap


def write_report(
    raw_friction: pl.DataFrame,
    entry_exit: pl.DataFrame,
    holding: pl.DataFrame,
    capacity: pl.DataFrame,
    overlap_daily: pl.DataFrame,
    overlap_symbols: pl.DataFrame,
    adjacent_overlap: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    """Write a Chinese report for trade-friction attribution."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡 market_down 交易摩擦归因 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是新策略回测，也不新增交易规则；只审计第214/216阶段固定路径是否低估交易摩擦。",
        f"- 固定口径：`{MARKET_STATE}`、`{FEATURE}`、固定持有`{HORIZON}`日。",
        f"- 样本：原始top候选`{meta['raw_top_count']:,}`个，最终回测候选`{meta['selected_count']:,}`个，信号日`{meta['signal_day_count']}`个。",
        "",
        "## 原始top候选过滤",
        "",
    ]
    for row in raw_friction.filter(pl.col("year").is_null()).iter_rows(named=True):
        lines.append(f"- `{row['reason']}`：`{row['count']}`，占比`{row['ratio']:.2%}`。")

    lines.extend(["", "## 已入选候选的入场/退出边缘风险", ""])
    for row in entry_exit.iter_rows(named=True):
        if row["count"]:
            lines.append(f"- `{row['field']}`：`{row['count']}`，占比`{row['ratio']:.2%}`。")
    if not entry_exit.filter(pl.col("count") > 0).height:
        lines.append("- 硬性入场/退出异常计数为0；这符合前序`final_keep`过滤预期。")

    lines.extend(["", "## 持有期状态", ""])
    for row in holding.iter_rows(named=True):
        lines.append(f"- `{row['field']}`：`{row['count']}`，占比`{row['ratio']:.4%}`。")

    lines.extend(["", "## 容量估算", ""])
    for row in capacity.iter_rows(named=True):
        lines.append(
            f"- ADV参与率`{row['participation_rate']:.0%}`：策略合计容量中位约`{row['median_strategy_sum_capacity_yuan'] / 1e8:.2f}`亿元，"
            f"等权p20容量中位约`{row['median_strategy_equal_weight_capacity_p20_yuan'] / 1e8:.2f}`亿元，"
            f"等权p10容量中位约`{row['median_strategy_equal_weight_capacity_p10_yuan'] / 1e8:.2f}`亿元。"
        )

    overlap_row = overlap_daily.row(0, named=True) if overlap_daily.height else {}
    lines.extend(["", "## 重叠与调仓冲突", ""])
    if overlap_row:
        lines.append(
            f"- 平均活跃股票数`{overlap_row['avg_active_symbols']:.1f}`，平均持仓腿数`{overlap_row['avg_active_lot_rows']:.1f}`，"
            f"平均重复股票数`{overlap_row['avg_duplicated_symbols']:.1f}`，重复腿占比`{overlap_row['avg_extra_duplicate_lot_share']:.2%}`，"
            f"单只股票最大重叠腿数`{int(overlap_row['max_symbol_lots'])}`。"
        )
    adj = adjacent_overlap.select(
        pl.col("overlap_to_next").median().alias("median_overlap_to_next"),
        pl.col("turnover_to_next").median().alias("median_turnover_to_next"),
        pl.col("overlap_to_next").quantile(0.9).alias("p90_overlap_to_next"),
    ).row(0, named=True)
    lines.append(
        f"- 相邻信号篮子对下一篮子的重合率中位`{adj['median_overlap_to_next']:.2%}`，"
        f"换手率中位`{adj['median_turnover_to_next']:.2%}`，重合率90分位`{adj['p90_overlap_to_next']:.2%}`。"
    )

    lines.extend(["", "## 重叠最严重股票", ""])
    for row in overlap_symbols.head(10).iter_rows(named=True):
        lines.append(
            f"- `{row['symbol']}`：持有日`{row['holding_days']}`，最大重叠腿`{row['max_active_lots']}`，"
            f"重复持有日占比`{row['duplicate_day_ratio']:.2%}`。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果硬性涨跌停/停牌摩擦很低，说明前序`final_keep`过滤没有明显漏掉一层硬约束。",
            "- 如果相邻篮子换手很高、同股重叠明显，真实组合需要更精细的持仓合并和调仓成本模型；第214阶段路径仍偏研究上限。",
            "- 这一步不触发第78 A/B，也不接入正式股票策略。",
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
    """Run trade-friction attribution for the fixed market-down path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_research_frame()
    raw_top = build_raw_top_candidates(df)
    selected = build_selected_candidates(df)

    raw_friction = build_raw_candidate_friction(raw_top)
    entry_exit = build_selected_entry_exit_friction(selected)
    holding = build_holding_friction(selected, df)
    capacity = build_capacity_summary(selected)
    overlap_daily, overlap_symbols, adjacent_overlap = build_overlap_summary(selected)

    meta: dict[str, Any] = {
        "feature": FEATURE,
        "horizon": HORIZON,
        "market_state": MARKET_STATE,
        "raw_top_count": raw_top.height,
        "selected_count": selected.height,
        "signal_day_count": selected["datetime"].n_unique(),
        "date_min": str(selected["datetime"].min()),
        "date_max": str(selected["datetime"].max()),
    }

    raw_path = OUTPUT_DIR / f"{PREFIX}_raw_candidate_friction.csv"
    entry_exit_path = OUTPUT_DIR / f"{PREFIX}_entry_exit_friction.csv"
    holding_path = OUTPUT_DIR / f"{PREFIX}_holding_friction.csv"
    capacity_path = OUTPUT_DIR / f"{PREFIX}_capacity.csv"
    overlap_daily_path = OUTPUT_DIR / f"{PREFIX}_overlap_daily_summary.csv"
    overlap_symbols_path = OUTPUT_DIR / f"{PREFIX}_overlap_symbols.csv"
    adjacent_path = OUTPUT_DIR / f"{PREFIX}_adjacent_signal_overlap.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    raw_friction.write_csv(raw_path)
    entry_exit.write_csv(entry_exit_path)
    holding.write_csv(holding_path)
    capacity.write_csv(capacity_path)
    overlap_daily.write_csv(overlap_daily_path)
    overlap_symbols.write_csv(overlap_symbols_path)
    adjacent_overlap.write_csv(adjacent_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        raw_friction,
        entry_exit,
        holding,
        capacity,
        overlap_daily,
        overlap_symbols,
        adjacent_overlap,
        meta,
        {
            "raw_candidate_friction": raw_path,
            "entry_exit_friction": entry_exit_path,
            "holding_friction": holding_path,
            "capacity": capacity_path,
            "overlap_daily_summary": overlap_daily_path,
            "overlap_symbols": overlap_symbols_path,
            "adjacent_signal_overlap": adjacent_path,
            "meta": meta_path,
        },
    )
    print(raw_friction)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
