from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_market_down_state_variables import build_benchmark_state
from analyze_stock_range_reversion_signal_attribution import add_forward_returns, add_price_features
from backtest_stock_range_reversion_market_down_long_only import (
    build_selected_candidates,
    get_bucket_definition,
)
from backtest_stock_range_reversion_market_down_merged_portfolio import (
    BUCKET,
    COST_BPS,
    FEATURE,
    HORIZON,
    MARKET_STATE,
    build_benchmark_daily,
    build_calendar,
    build_concentration,
    build_daily_gross,
    build_equity_curve,
    build_symbol_daily,
    build_symbol_exposure_summary,
    build_turnover,
    summarize_curve,
    to_float,
)


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_market_down_entry_timing_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_market_down_entry_timing_v1"
MAX_DELAY_DAYS: int = 3


@dataclass(frozen=True)
class EntryScenario:
    name: str
    description: str
    fixed_delay_days: int | None = None
    confirm_rule: str | None = None
    max_wait_days: int = 0


SCENARIOS: tuple[EntryScenario, ...] = (
    EntryScenario("baseline_next_close", "第218阶段baseline：信号后第1个交易日收盘入场", fixed_delay_days=0),
    EntryScenario("delay_1d", "固定延迟1个交易日入场", fixed_delay_days=1),
    EntryScenario("delay_2d", "固定延迟2个交易日入场", fixed_delay_days=2),
    EntryScenario("delay_3d", "固定延迟3个交易日入场", fixed_delay_days=3),
    EntryScenario(
        "wait_ret1_nonnegative_max3",
        "最多等3个交易日，直到中证1000单日收益转正；未确认则跳过",
        confirm_rule="bm_ret_1_nonnegative",
        max_wait_days=3,
    ),
    EntryScenario(
        "wait_down_streak_break_max3",
        "最多等3个交易日，直到中证1000连续下跌中断；未确认则跳过",
        confirm_rule="bm_down_streak_zero",
        max_wait_days=3,
    ),
    EntryScenario(
        "wait_ret5_decelerate_max3",
        "最多等3个交易日，直到中证10005日跌速放缓；未确认则跳过",
        confirm_rule="bm_ret_5_delta_nonnegative",
        max_wait_days=3,
    ),
)


def add_extended_path_columns(df: pl.DataFrame, max_delay_days: int) -> pl.DataFrame:
    """Add start and close-to-close return columns needed by delayed entries."""
    work = df.sort(["symbol", "datetime"])
    exprs: list[pl.Expr] = []
    for day in range(1, HORIZON + max_delay_days + 1):
        exprs.extend(
            [
                pl.col("datetime").shift(-day).over("symbol").alias(f"entry_timing_start_date_{day}"),
                pl.col("datetime").shift(-(day + 1)).over("symbol").alias(f"entry_timing_pnl_date_{day}"),
                (
                    pl.col("close").shift(-(day + 1)).over("symbol")
                    / pl.col("close").shift(-day).over("symbol")
                    - 1
                ).alias(f"entry_timing_stock_daily_ret_{day}"),
            ]
        )
    return work.with_columns(exprs)


def build_selected_frame_with_extended_paths() -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    """Load the fixed candidate frame after adding delayed paths on the full panel."""
    bucket_description, _bucket_expr = get_bucket_definition()
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    df = add_forward_returns(add_price_features(stock_df), benchmark_df).join(
        layer_tags, on=["datetime", "symbol"], how="left"
    )
    df = add_extended_path_columns(df, MAX_DELAY_DAYS)
    selected = build_selected_candidates(df)
    if selected.is_empty():
        raise RuntimeError("No selected candidates.")
    meta = {
        "date_min": str(selected["datetime"].min()),
        "date_max": str(selected["datetime"].max()),
        "symbol_count": selected["symbol"].n_unique(),
        "selected_roundtrips": selected.height,
        "signal_day_count": selected["datetime"].n_unique(),
        "bucket_description": bucket_description,
    }
    return selected, benchmark_df.sort("datetime"), meta


def build_trading_index(benchmark_df: pl.DataFrame) -> tuple[list[Any], dict[Any, int]]:
    """Return benchmark trading dates and date-to-index mapping."""
    dates = benchmark_df.sort("datetime")["datetime"].to_list()
    return dates, {date: index for index, date in enumerate(dates)}


def build_benchmark_confirmation_state(benchmark_df: pl.DataFrame) -> dict[Any, dict[str, Any]]:
    """Build benchmark state available at each candidate entry close."""
    state = build_benchmark_state(benchmark_df).sort("date").with_columns(
        (pl.col("bm_ret_5") - pl.col("bm_ret_5").shift(1)).alias("bm_ret_5_delta")
    )
    return {
        row["date"]: row
        for row in state.select(["date", "bm_ret_1", "bm_ret_5", "bm_ret_5_delta", "bm_down_streak"]).iter_rows(
            named=True
        )
    }


def check_confirm_rule(rule: str, state_row: dict[str, Any] | None) -> bool:
    """Evaluate one entry confirmation rule on a candidate entry date."""
    if state_row is None:
        return False
    if rule == "bm_ret_1_nonnegative":
        value = state_row.get("bm_ret_1")
        return value is not None and value >= 0
    if rule == "bm_down_streak_zero":
        value = state_row.get("bm_down_streak")
        return value is not None and value == 0
    if rule == "bm_ret_5_delta_nonnegative":
        value = state_row.get("bm_ret_5_delta")
        return value is not None and value >= 0
    raise ValueError(f"Unknown confirm rule: {rule}")


def decide_entry_dates(
    signal_dates: list[Any],
    benchmark_df: pl.DataFrame,
    scenario: EntryScenario,
    scenario_order: int,
) -> pl.DataFrame:
    """Build per-signal entry decisions for one scenario."""
    trading_dates, trading_index = build_trading_index(benchmark_df)
    confirmation_state = build_benchmark_confirmation_state(benchmark_df)
    rows: list[dict[str, Any]] = []
    for signal_date in signal_dates:
        signal_index = trading_index[signal_date]
        accepted = False
        entry_delay_days: int | None = None
        entry_date = None
        trigger_reason = ""

        if scenario.fixed_delay_days is not None:
            entry_delay_days = scenario.fixed_delay_days
            entry_index = signal_index + 1 + entry_delay_days
            accepted = entry_index < len(trading_dates)
            entry_date = trading_dates[entry_index] if accepted else None
            trigger_reason = "fixed_delay" if accepted else "missing_entry_date"
        else:
            for delay in range(0, scenario.max_wait_days + 1):
                entry_index = signal_index + 1 + delay
                if entry_index >= len(trading_dates):
                    continue
                candidate_date = trading_dates[entry_index]
                if scenario.confirm_rule and check_confirm_rule(scenario.confirm_rule, confirmation_state.get(candidate_date)):
                    accepted = True
                    entry_delay_days = delay
                    entry_date = candidate_date
                    trigger_reason = scenario.confirm_rule
                    break
            if not accepted:
                trigger_reason = f"no_confirm_within_{scenario.max_wait_days}d"

        rows.append(
            {
                "scenario_order": scenario_order,
                "scenario": scenario.name,
                "scenario_description": scenario.description,
                "signal_date": signal_date,
                "accepted": accepted,
                "entry_delay_days": entry_delay_days,
                "entry_date": entry_date,
                "trigger_reason": trigger_reason,
            }
        )
    return pl.DataFrame(rows)


def build_lots_for_decisions(selected: pl.DataFrame, decisions: pl.DataFrame) -> pl.DataFrame:
    """Build delayed-entry lots from selected candidates and signal-level decisions."""
    work = (
        selected.join(
            decisions.select(["signal_date", "accepted", "entry_delay_days", "entry_date"]),
            left_on="datetime",
            right_on="signal_date",
            how="inner",
        )
        .filter(pl.col("accepted") & pl.col("entry_delay_days").is_not_null())
        .with_columns(pl.len().over("datetime").alias("candidate_count"))
    )
    if work.is_empty():
        return pl.DataFrame()

    parts: list[pl.DataFrame] = []
    extra_cols = [col for col in ["industry", "market", "adv20_turnover", "circ_mv"] if col in work.columns]
    for delay in range(0, MAX_DELAY_DAYS + 1):
        delay_df = work.filter(pl.col("entry_delay_days") == delay)
        if delay_df.is_empty():
            continue
        for holding_day in range(1, HORIZON + 1):
            source_day = delay + holding_day
            parts.append(
                delay_df.select(
                    pl.col("datetime").alias("signal_date"),
                    "symbol",
                    "candidate_count",
                    FEATURE,
                    *extra_cols,
                    "entry_delay_days",
                    "entry_date",
                    pl.col(f"entry_timing_start_date_{source_day}").alias("target_date"),
                    pl.col(f"entry_timing_pnl_date_{source_day}").alias("pnl_date"),
                    pl.col(f"entry_timing_stock_daily_ret_{source_day}").alias("stock_daily_ret"),
                )
                .with_columns(
                    pl.lit(holding_day).alias("holding_day"),
                    (1.0 / HORIZON / pl.col("candidate_count")).alias("lot_weight"),
                )
                .filter(
                    pl.col("target_date").is_not_null()
                    & pl.col("pnl_date").is_not_null()
                    & pl.col("stock_daily_ret").is_not_null()
                    & pl.col("stock_daily_ret").is_finite()
                )
            )
    return pl.concat(parts, how="vertical").sort(["target_date", "signal_date", "symbol"]) if parts else pl.DataFrame()


def add_scenario_columns(df: pl.DataFrame, scenario: EntryScenario, scenario_order: int) -> pl.DataFrame:
    """Attach scenario metadata to an output frame."""
    return df.with_columns(
        pl.lit(scenario_order).alias("scenario_order"),
        pl.lit(scenario.name).alias("scenario"),
        pl.lit(scenario.description).alias("scenario_description"),
    )


def run_entry_scenario(
    selected: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    benchmark_daily: pl.DataFrame,
    global_calendar: pl.DataFrame,
    signal_dates: list[Any],
    scenario: EntryScenario,
    scenario_order: int,
) -> tuple[list[dict[str, Any]], list[pl.DataFrame], pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Run one entry-timing scenario across all cost assumptions."""
    decisions = decide_entry_dates(signal_dates, benchmark_df, scenario, scenario_order)
    lots = build_lots_for_decisions(selected, decisions)
    if lots.is_empty():
        raise RuntimeError(f"No lots for scenario {scenario.name}")
    symbol_daily = build_symbol_daily(lots)
    turnover, target_weights = build_turnover(symbol_daily, global_calendar)
    concentration = build_concentration(symbol_daily, global_calendar)
    daily_gross = build_daily_gross(symbol_daily)
    symbol_exposure = build_symbol_exposure_summary(symbol_daily)
    accepted_selected = selected.join(
        decisions.filter(pl.col("accepted")).select("signal_date"),
        left_on="datetime",
        right_on="signal_date",
        how="inner",
    )

    curves: list[pl.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for cost_bps in COST_BPS:
        curve = build_equity_curve(daily_gross, turnover, benchmark_daily, global_calendar, cost_bps)
        curve = add_scenario_columns(curve, scenario, scenario_order)
        curves.append(curve)
        row = summarize_curve(curve, turnover, concentration, accepted_selected, cost_bps)
        row.update(
            {
                "scenario_order": scenario_order,
                "scenario": scenario.name,
                "scenario_description": scenario.description,
                "accepted_signal_baskets": int(decisions["accepted"].sum()),
                "acceptance_ratio": to_float(decisions["accepted"].mean()),
                "avg_entry_delay_days": to_float(decisions.filter(pl.col("accepted"))["entry_delay_days"].mean()),
                "median_entry_delay_days": to_float(decisions.filter(pl.col("accepted"))["entry_delay_days"].median()),
                "skipped_signal_baskets": int((~decisions["accepted"]).sum()),
                "accepted_stock_roundtrips": accepted_selected.height,
            }
        )
        summary_rows.append(row)

    return (
        summary_rows,
        curves,
        add_scenario_columns(decisions, scenario, scenario_order),
        add_scenario_columns(turnover, scenario, scenario_order),
        add_scenario_columns(concentration, scenario, scenario_order),
        add_scenario_columns(target_weights, scenario, scenario_order),
        add_scenario_columns(symbol_exposure, scenario, scenario_order),
    )


def build_global_calendar(selected: pl.DataFrame, benchmark_df: pl.DataFrame) -> pl.DataFrame:
    """Build a shared calendar covering baseline and max delayed exits."""
    trading_dates, trading_index = build_trading_index(benchmark_df)
    signal_dates = selected.select("datetime").unique().sort("datetime")["datetime"].to_list()
    min_index = trading_index[min(signal_dates)] + 1
    max_index = trading_index[max(signal_dates)] + HORIZON + MAX_DELAY_DAYS + 1
    max_index = min(max_index, len(trading_dates) - 1)
    return build_calendar(benchmark_df, trading_dates[min_index], trading_dates[max_index])


def build_year_summary(equity_df: pl.DataFrame, decisions_df: pl.DataFrame) -> pl.DataFrame:
    """Summarize annual path returns and accepted signal counts."""
    year_path = (
        equity_df.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["scenario_order", "scenario", "roundtrip_cost_bps", "year"])
        .agg(
            ((1 + pl.col("strategy_daily_ret")).product() - 1).alias("year_return"),
            ((1 + pl.col("strategy_gross_daily_ret")).product() - 1).alias("year_gross_return"),
            pl.col("turnover_cost_ret").sum().alias("year_cost_drag"),
            pl.col("return_gross_exposure").mean().alias("avg_gross_exposure"),
            pl.col("strategy_drawdown").min().alias("min_drawdown_seen"),
        )
    )
    year_decisions = (
        decisions_df.with_columns(pl.col("signal_date").dt.year().alias("year"))
        .group_by(["scenario_order", "scenario", "year"])
        .agg(
            pl.len().alias("signal_baskets"),
            pl.col("accepted").sum().alias("accepted_signal_baskets"),
            (pl.col("accepted").sum() / pl.len()).alias("acceptance_ratio"),
            pl.col("entry_delay_days").drop_nulls().mean().alias("avg_entry_delay_days"),
        )
    )
    return (
        year_path.join(year_decisions, on=["scenario_order", "scenario", "year"], how="left")
        .sort(["roundtrip_cost_bps", "scenario_order", "year"])
    )


def summarize_baseline_delta(summary_df: pl.DataFrame) -> pl.DataFrame:
    """Compare each entry scenario with next-close baseline at the same cost."""
    baseline = summary_df.filter(pl.col("scenario") == "baseline_next_close").select(
        "roundtrip_cost_bps",
        pl.col("final_equity").alias("baseline_final_equity"),
        pl.col("total_return").alias("baseline_total_return"),
        pl.col("max_drawdown").alias("baseline_max_drawdown"),
        pl.col("sharpe").alias("baseline_sharpe"),
        pl.col("avg_gross_exposure").alias("baseline_avg_gross_exposure"),
    )
    return (
        summary_df.join(baseline, on="roundtrip_cost_bps", how="left")
        .with_columns(
            (pl.col("total_return") - pl.col("baseline_total_return")).alias("total_return_delta"),
            (pl.col("max_drawdown") - pl.col("baseline_max_drawdown")).alias("max_drawdown_delta"),
            (pl.col("sharpe") - pl.col("baseline_sharpe")).alias("sharpe_delta"),
            (pl.col("avg_gross_exposure") - pl.col("baseline_avg_gross_exposure")).alias("avg_exposure_delta"),
            (pl.col("final_equity") / pl.col("baseline_final_equity") - 1).alias("final_equity_ratio_delta"),
        )
        .sort(["roundtrip_cost_bps", "scenario_order"])
    )


def build_decision_summary(decisions_df: pl.DataFrame) -> pl.DataFrame:
    """Summarize accepted/skipped decisions and delay distribution."""
    return (
        decisions_df.group_by(["scenario_order", "scenario", "trigger_reason", "entry_delay_days"])
        .agg(
            pl.len().alias("signal_baskets"),
            pl.col("accepted").sum().alias("accepted_signal_baskets"),
        )
        .sort(["scenario_order", "trigger_reason", "entry_delay_days"])
    )


def write_report(
    summary_df: pl.DataFrame,
    delta_df: pl.DataFrame,
    year_df: pl.DataFrame,
    decision_summary: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    """Write a Chinese report for entry-timing attribution."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡 market_down 入场节奏归因 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是新策略版本，也不是参数优化；只比较固定入场节奏和少数事前确认条件对第218阶段合并持仓账本的影响。",
        f"- 固定信号：`{MARKET_STATE}`、`{BUCKET}`、`{FEATURE}`，固定持有`{HORIZON}`日；成本情景：`{', '.join(str(x) for x in COST_BPS)}bp`。",
        "- 确认条件只使用入场候选日收盘可知的中证1000状态；未确认的信号直接跳过。",
        f"- 样本：原始信号日`{meta['signal_day_count']}`个，最大等待`{MAX_DELAY_DAYS}`个交易日。",
        "",
        "## 总体结果",
        "",
    ]
    for cost_bps in sorted(summary_df["roundtrip_cost_bps"].unique().to_list()):
        lines.append(f"### 成本`{cost_bps:.0f}bp`")
        for row in summary_df.filter(pl.col("roundtrip_cost_bps") == cost_bps).sort("scenario_order").iter_rows(named=True):
            lines.append(
                f"- `{row['scenario']}`：接受`{row['accepted_signal_baskets']}`个，"
                f"接受率`{row['acceptance_ratio']:.2%}`，平均延迟`{row['avg_entry_delay_days']:.2f}`日，"
                f"期末权益`{row['final_equity']:.4f}`，总收益`{row['total_return']:.2%}`，"
                f"最大回撤`{row['max_drawdown']:.2%}`，Sharpe `{row['sharpe']:.2f}`，"
                f"平均暴露`{row['avg_gross_exposure']:.2%}`。"
            )

    lines.extend(["", "## 相对次日入场变化", ""])
    for row in delta_df.filter(pl.col("scenario") != "baseline_next_close").iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['scenario']}`："
            f"总收益变化`{row['total_return_delta']:.2%}`，最大回撤变化`{row['max_drawdown_delta']:.2%}`，"
            f"Sharpe变化`{row['sharpe_delta']:.2f}`，平均暴露变化`{row['avg_exposure_delta']:.2%}`。"
        )

    lines.extend(["", "## 2018/2022压力年份", ""])
    for row in year_df.filter(pl.col("year").is_in([2018, 2022])).sort(
        ["roundtrip_cost_bps", "scenario_order", "year"]
    ).iter_rows(named=True):
        lines.append(
            f"- 成本`{row['roundtrip_cost_bps']:.0f}bp` `{row['scenario']}` `{row['year']}`："
            f"净收益`{row['year_return']:.2%}`，年内最低回撤`{row['min_drawdown_seen']:.2%}`，"
            f"平均暴露`{row['avg_gross_exposure']:.2%}`，接受`{row['accepted_signal_baskets']}`个。"
        )

    lines.extend(["", "## 决策分布", ""])
    for row in decision_summary.iter_rows(named=True):
        delay = "NA" if row["entry_delay_days"] is None else f"{int(row['entry_delay_days'])}d"
        lines.append(
            f"- `{row['scenario']}` `{row['trigger_reason']}` `{delay}`：信号`{row['signal_baskets']}`，接受`{row['accepted_signal_baskets']}`。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果延迟入场改善回撤但同步明显牺牲收益，说明它只是少持有几天风险，不是更聪明的确认。",
            "- 如果确认条件能改善回撤且保留深跌反弹收益，后续才值得压缩成少参数节奏规则。",
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
    """Run entry-timing attribution on the fixed market-down signal."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    selected, benchmark_df, selected_meta = build_selected_frame_with_extended_paths()
    signal_dates = selected.select("datetime").unique().sort("datetime")["datetime"].to_list()
    global_calendar = build_global_calendar(selected, benchmark_df)
    benchmark_daily = build_benchmark_daily(benchmark_df)

    summary_rows: list[dict[str, Any]] = []
    equity_frames: list[pl.DataFrame] = []
    decision_frames: list[pl.DataFrame] = []
    turnover_frames: list[pl.DataFrame] = []
    concentration_frames: list[pl.DataFrame] = []
    target_weight_frames: list[pl.DataFrame] = []
    symbol_exposure_frames: list[pl.DataFrame] = []

    for scenario_order, scenario in enumerate(SCENARIOS):
        (
            scenario_rows,
            scenario_curves,
            scenario_decisions,
            scenario_turnover,
            scenario_concentration,
            scenario_target_weights,
            scenario_symbol_exposure,
        ) = run_entry_scenario(
            selected,
            benchmark_df,
            benchmark_daily,
            global_calendar,
            signal_dates,
            scenario,
            scenario_order,
        )
        summary_rows.extend(scenario_rows)
        equity_frames.extend(scenario_curves)
        decision_frames.append(scenario_decisions)
        turnover_frames.append(scenario_turnover)
        concentration_frames.append(scenario_concentration)
        target_weight_frames.append(scenario_target_weights)
        symbol_exposure_frames.append(scenario_symbol_exposure)

    summary_df = pl.DataFrame(summary_rows).sort(["roundtrip_cost_bps", "scenario_order"])
    equity_df = pl.concat(equity_frames, how="vertical").sort(["roundtrip_cost_bps", "scenario_order", "date"])
    decisions_df = pl.concat(decision_frames, how="vertical").sort(["scenario_order", "signal_date"])
    turnover_df = pl.concat(turnover_frames, how="vertical").sort(["scenario_order", "target_date"])
    concentration_df = pl.concat(concentration_frames, how="vertical").sort(["scenario_order", "target_date"])
    target_weights_df = pl.concat(target_weight_frames, how="vertical").sort(["scenario_order", "target_date", "symbol"])
    symbol_exposure_df = pl.concat(symbol_exposure_frames, how="vertical").sort(
        ["scenario_order", "max_target_weight"], descending=[False, True]
    )
    year_df = build_year_summary(equity_df, decisions_df)
    delta_df = summarize_baseline_delta(summary_df)
    decision_summary = build_decision_summary(decisions_df)
    meta: dict[str, Any] = {
        **selected_meta,
        "feature": FEATURE,
        "bucket": BUCKET,
        "horizon": HORIZON,
        "market_state": MARKET_STATE,
        "cost_bps": COST_BPS,
        "max_delay_days": MAX_DELAY_DAYS,
        "scenario_count": len(SCENARIOS),
        "scenarios": [scenario.__dict__ for scenario in SCENARIOS],
        "global_start": str(global_calendar["date"].min()),
        "global_end": str(global_calendar["date"].max()),
    }

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    delta_path = OUTPUT_DIR / f"{PREFIX}_baseline_delta.csv"
    equity_path = OUTPUT_DIR / f"{PREFIX}_equity_curve.csv"
    year_path = OUTPUT_DIR / f"{PREFIX}_year_summary.csv"
    decisions_path = OUTPUT_DIR / f"{PREFIX}_entry_decisions.csv"
    decision_summary_path = OUTPUT_DIR / f"{PREFIX}_decision_summary.csv"
    turnover_path = OUTPUT_DIR / f"{PREFIX}_turnover.csv"
    concentration_path = OUTPUT_DIR / f"{PREFIX}_daily_concentration.csv"
    target_weights_path = OUTPUT_DIR / f"{PREFIX}_target_weights.csv"
    symbol_exposure_path = OUTPUT_DIR / f"{PREFIX}_symbol_exposure.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    summary_df.write_csv(summary_path)
    delta_df.write_csv(delta_path)
    equity_df.write_csv(equity_path)
    year_df.write_csv(year_path)
    decisions_df.write_csv(decisions_path)
    decision_summary.write_csv(decision_summary_path)
    turnover_df.write_csv(turnover_path)
    concentration_df.write_csv(concentration_path)
    target_weights_df.write_csv(target_weights_path)
    symbol_exposure_df.write_csv(symbol_exposure_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        delta_df,
        year_df,
        decision_summary,
        meta,
        {
            "summary": summary_path,
            "baseline_delta": delta_path,
            "equity_curve": equity_path,
            "year_summary": year_path,
            "entry_decisions": decisions_path,
            "decision_summary": decision_summary_path,
            "turnover": turnover_path,
            "daily_concentration": concentration_path,
            "target_weights": target_weights_path,
            "symbol_exposure": symbol_exposure_path,
            "meta": meta_path,
        },
    )
    print(summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
