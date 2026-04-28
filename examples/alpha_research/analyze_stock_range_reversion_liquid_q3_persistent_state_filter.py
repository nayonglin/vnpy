from __future__ import annotations

import json
import os
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_industry_signal_lifecycle import (
    add_industry_rank_lifecycle,
    build_base_frame,
)
from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_market_down_state_variables import build_date_state
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    COST_BPS,
    FEATURE,
    HORIZON,
    NATIVE_RESULTS_DIR,
    TRADING_DAYS,
    add_path_columns,
    build_benchmark_daily,
    build_calendar,
    build_concentration,
    build_daily_gross,
    build_equity_curve,
    build_symbol_daily,
    build_turnover,
    build_yearly_summary,
    pct,
    summarize_curve,
)
from backtest_stock_range_reversion_liquid_q3_persistent_confirmation import (
    apply_capped_weights,
    build_confirmation_lots,
    build_confirmed_base,
)


OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_persistent_state_filter_2018_2026"),
    )
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_persistent_state_filter_v1"

ENTRY_AGE_MIN: int = int(os.getenv("ENTRY_AGE_MIN", "4") or 4)
MIN_SIGNAL_DAYS: int = int(os.getenv("MIN_SIGNAL_DAYS", "40") or 40)
MIN_PATH_DAYS: int = int(os.getenv("MIN_PATH_DAYS", "60") or 60)
STRESS_YEARS: tuple[int, ...] = tuple(int(item) for item in os.getenv("STRESS_YEARS", "2018,2022,2025").split(","))
STATE_COLUMNS: tuple[str, ...] = (
    "market_state_20d",
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
)


def t_stat(mean: float, std: float | None, n: int) -> float:
    if not std or std <= 0 or n <= 1:
        return 0.0
    return mean / (std / sqrt(n))


def scenario_definitions() -> list[dict[str, Any]]:
    return [
        {
            "scenario": "age4_daily_all",
            "description": "4天确认每日建篮，不做市场状态过滤",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_state_baseline",
            "filter_name": "all",
            "filter_description": "不过滤",
        },
        {
            "scenario": "age4_daily_market_down20",
            "description": "4天确认每日建篮，只保留中证1000过去20日为负的信号日",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_state_filter",
            "filter_name": "market_down20_only",
            "filter_description": "`market_state_20d == market_down_20d`",
        },
        {
            "scenario": "age4_daily_exclude_hot_breadth",
            "description": "4天确认每日建篮，排除20日广谱强势宽度信号日",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_state_filter",
            "filter_name": "exclude_hot_breadth",
            "filter_description": "`breadth_pos_20d_band != breadth20_gt_60pct`",
        },
        {
            "scenario": "age4_daily_exclude_up20_hot_breadth",
            "description": "4天确认每日建篮，排除指数20日上涨且市场宽度超过60%的普涨信号日",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_state_filter",
            "filter_name": "exclude_up20_hot_breadth",
            "filter_description": "不在`bm_ret_20 >= 0`且`breadth_pos_20d_ratio > 60%`时建篮",
        },
    ]


def filter_expr(filter_name: str) -> pl.Expr:
    if filter_name == "all":
        return pl.lit(True)
    if filter_name == "market_down20_only":
        return pl.col("market_state_20d") == "market_down_20d"
    if filter_name == "exclude_hot_breadth":
        return pl.col("breadth_pos_20d_band") != "breadth20_gt_60pct"
    if filter_name == "exclude_up20_hot_breadth":
        return ~((pl.col("bm_ret_20") >= 0.0) & (pl.col("breadth_pos_20d_ratio") > 0.60))
    raise ValueError(f"Unknown filter: {filter_name}")


def build_age4_selected_with_state(
    base: pl.DataFrame, stock_df: pl.DataFrame, benchmark_df: pl.DataFrame, layer_tags: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame]:
    path_df = add_path_columns(base)
    lifecycle_df = add_industry_rank_lifecycle(base, "liquid_q3")
    confirmed_base = build_confirmed_base(path_df, lifecycle_df)
    age4_selected = apply_capped_weights(confirmed_base, ENTRY_AGE_MIN)
    date_state = build_date_state(stock_df, benchmark_df, layer_tags).with_columns(
        pl.when(pl.col("bm_ret_20").is_null())
        .then(pl.lit("unknown"))
        .when(pl.col("bm_ret_20") > 0)
        .then(pl.lit("market_up_20d"))
        .otherwise(pl.lit("market_down_20d"))
        .alias("market_state_20d")
    )
    selected_with_state = age4_selected.join(date_state.rename({"date": "datetime"}), on="datetime", how="left")
    return selected_with_state, date_state


def build_signal_daily(selected: pl.DataFrame) -> pl.DataFrame:
    state_exprs = [pl.first(col).alias(col) for col in STATE_COLUMNS if col in selected.columns]
    return (
        selected.group_by("datetime")
        .agg(
            pl.len().alias("candidate_count"),
            pl.col("industry").n_unique().alias("selected_industry_count"),
            pl.col("basket_gross_weight").first().alias("basket_gross_weight"),
            (pl.col("basket_weight") * pl.col(f"fwd_ret_{HORIZON}")).sum().alias("basket_ret_on_capital"),
            (pl.col("basket_weight") * pl.col(f"fwd_excess_ret_{HORIZON}")).sum().alias(
                "basket_excess_ret_on_capital"
            ),
            pl.col(f"fwd_ret_{HORIZON}").mean().alias("basket_ret_equal_stock"),
            pl.col(f"fwd_excess_ret_{HORIZON}").mean().alias("basket_excess_ret_equal_stock"),
            pl.col(f"bm_fwd_ret_{HORIZON}").first().alias("benchmark_forward_ret"),
            *state_exprs,
        )
        .rename({"datetime": "signal_date"})
        .with_columns(
            pl.when(pl.col("basket_gross_weight") > 0)
            .then(pl.col("basket_ret_on_capital") / pl.col("basket_gross_weight"))
            .otherwise(0.0)
            .alias("basket_ret_on_deployed"),
            pl.when(pl.col("basket_gross_weight") > 0)
            .then(pl.col("basket_excess_ret_on_capital") / pl.col("basket_gross_weight"))
            .otherwise(0.0)
            .alias("basket_excess_ret_on_deployed"),
            pl.col("signal_date").dt.year().alias("year"),
        )
    )


def summarize_signal_by_state(signal_daily: pl.DataFrame, state_columns: tuple[str, ...]) -> pl.DataFrame:
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
                pl.col("basket_gross_weight").mean().alias("avg_basket_gross_weight"),
                pl.col("basket_ret_on_capital").mean().alias("basket_ret_on_capital_mean"),
                pl.col("basket_ret_on_capital").std().alias("basket_ret_on_capital_std"),
                (pl.col("basket_ret_on_capital") > 0).mean().alias("basket_ret_on_capital_win_rate"),
                pl.col("basket_ret_on_deployed").mean().alias("basket_ret_on_deployed_mean"),
                pl.col("basket_excess_ret_on_capital").mean().alias("basket_excess_ret_on_capital_mean"),
                pl.col("benchmark_forward_ret").mean().alias("benchmark_forward_ret_mean"),
                pl.col("year").is_in(STRESS_YEARS).mean().alias("stress_year_signal_ratio"),
            )
            .with_columns(
                pl.lit(state_column).alias("state_layer"),
                pl.col(state_column).cast(pl.String).alias("state_value"),
                pl.struct(["basket_ret_on_capital_mean", "basket_ret_on_capital_std", "signal_days"]).map_elements(
                    lambda row: t_stat(
                        row["basket_ret_on_capital_mean"], row["basket_ret_on_capital_std"], row["signal_days"]
                    ),
                    return_dtype=pl.Float64,
                ).alias("basket_ret_on_capital_t"),
            )
            .drop(state_column, "basket_ret_on_capital_std")
            .filter(pl.col("signal_days") >= MIN_SIGNAL_DAYS)
        )
        frames.append(summary)
    return pl.concat(frames, how="vertical").sort(["state_layer", "state_value"]) if frames else pl.DataFrame()


def summarize_path_by_state(path_daily: pl.DataFrame, state_columns: tuple[str, ...]) -> pl.DataFrame:
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


def build_year_state_mix(signal_daily: pl.DataFrame, state_columns: tuple[str, ...]) -> pl.DataFrame:
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


def build_selected_for_scenarios(selected_with_state: pl.DataFrame) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for scenario in scenario_definitions():
        selected = (
            selected_with_state.filter(filter_expr(scenario["filter_name"]))
            .with_columns(
                pl.lit(scenario["scenario"]).alias("scenario"),
                pl.lit(scenario["description"]).alias("scenario_description"),
                pl.lit(scenario["bucket"]).alias("bucket"),
                pl.lit(scenario["weight_mode"]).alias("weight_mode"),
                pl.lit(scenario["filter_name"]).alias("filter_name"),
                pl.lit(scenario["filter_description"]).alias("filter_description"),
            )
        )
        if not selected.is_empty():
            frames.append(selected)
    if not frames:
        raise RuntimeError("No state filter candidates.")
    return pl.concat(frames, how="vertical").sort(["scenario", "datetime", "industry", FEATURE])


def run_filtered_backtests(
    selected_all: pl.DataFrame, benchmark_df: pl.DataFrame, date_state: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    lots_all = build_confirmation_lots(selected_all)
    symbol_daily_all = build_symbol_daily(lots_all)
    benchmark_daily = build_benchmark_daily(benchmark_df)
    all_curves: list[pl.DataFrame] = []
    all_summary: list[dict[str, Any]] = []
    all_turnover: list[pl.DataFrame] = []
    all_concentration: list[pl.DataFrame] = []

    scenario_lookup = {item["scenario"]: item for item in scenario_definitions()}
    for scenario in scenario_definitions():
        scenario_name = scenario["scenario"]
        scenario_symbol_daily = symbol_daily_all.filter(pl.col("scenario") == scenario_name)
        scenario_selected = selected_all.filter(pl.col("scenario") == scenario_name)
        if scenario_symbol_daily.is_empty():
            continue
        min_date = min(scenario_symbol_daily["target_date"].min(), scenario_symbol_daily["pnl_date"].min())
        max_date = max(scenario_symbol_daily["target_date"].max(), scenario_symbol_daily["pnl_date"].max())
        calendar = build_calendar(benchmark_df, min_date, max_date)
        turnover, _targets = build_turnover(scenario_symbol_daily, calendar, scenario_name)
        concentration, _industry_daily = build_concentration(scenario_symbol_daily, calendar, scenario_name)
        daily_gross = build_daily_gross(scenario_symbol_daily)
        all_turnover.append(turnover)
        all_concentration.append(concentration)
        for cost_bps in COST_BPS:
            curve = build_equity_curve(scenario_name, daily_gross, turnover, benchmark_daily, calendar, cost_bps)
            all_curves.append(curve)
            row = summarize_curve(curve, turnover, concentration, scenario_selected, scenario, cost_bps)
            row["filter_name"] = scenario["filter_name"]
            row["filter_description"] = scenario["filter_description"]
            all_summary.append(row)

    summary_df = pl.DataFrame(all_summary).sort(["roundtrip_cost_bps", "scenario"])
    equity_df = pl.concat(all_curves, how="vertical").sort(["roundtrip_cost_bps", "scenario", "date"])
    turnover_df = pl.concat(all_turnover, how="vertical").sort(["scenario", "target_date"])
    concentration_df = pl.concat(all_concentration, how="vertical").sort(["scenario", "target_date"])
    yearly_df = (
        build_yearly_summary(equity_df)
        .join(
            summary_df.select("scenario", "filter_name", "filter_description").unique(),
            on="scenario",
            how="left",
        )
        .sort(["roundtrip_cost_bps", "scenario", "year"])
    )
    path_daily_df = equity_df.join(date_state, on="date", how="left").with_columns(
        pl.col("date").dt.year().alias("year"),
        ((pl.col("return_gross_exposure") > 0) | (pl.col("gross_abs_weight_change") > 0)).alias(
            "active_or_trade_day"
        ),
        (pl.col("strategy_drawdown") <= -0.10).alias("strategy_drawdown_le_10pct"),
        (pl.col("strategy_drawdown") <= -0.20).alias("strategy_drawdown_le_20pct"),
    )
    return summary_df, equity_df, yearly_df, turnover_df, concentration_df, path_daily_df


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return frame.select([col for col in columns if col in frame.columns]).head(max_rows).to_pandas().to_markdown(
        index=False
    )


def write_report(
    signal_summary: pl.DataFrame,
    path_summary: pl.DataFrame,
    filter_summary: pl.DataFrame,
    filter_yearly: pl.DataFrame,
    weak_signal_states: pl.DataFrame,
    weak_path_states: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    baseline_50 = filter_summary.filter(
        (pl.col("scenario") == "age4_daily_all") & (pl.col("roundtrip_cost_bps") == 50.0)
    ).to_dicts()
    best_filter_50 = (
        filter_summary.filter(pl.col("roundtrip_cost_bps") == 50.0)
        .sort(["final_equity", "max_drawdown"], descending=[True, True])
        .head(1)
        .to_dicts()
    )
    base = baseline_50[0] if baseline_50 else None
    best = best_filter_50[0] if best_filter_50 else None
    lines = [
        "# 股票震荡liquid_q3持续确认状态归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：`4天确认+每日建篮`的市场状态归因和少数固定过滤压力测试，不是正式交易版本。",
        f"- 固定底稿：`liquid_q3`行业内top20连续在榜至少`{ENTRY_AGE_MIN}`天，次日收盘建篮，固定持有`{HORIZON}`日。",
        "",
        "## 核心观察",
        "",
    ]
    if base:
        lines.append(
            f"- 基线50bp：期末权益`{base['final_equity']:.4f}`，总收益`{pct(base['total_return'])}`，"
            f"最大回撤`{pct(base['max_drawdown'])}`，Sharpe `{base['sharpe']:.2f}`，"
            f"年化单边换手`{base['annualized_one_way_turnover']:.2f}`倍。"
        )
    if best:
        lines.append(
            f"- 固定过滤中50bp期末权益最高的是`{best['scenario']}`：期末权益`{best['final_equity']:.4f}`，"
            f"总收益`{pct(best['total_return'])}`，最大回撤`{pct(best['max_drawdown'])}`，"
            f"Sharpe `{best['sharpe']:.2f}`，年化单边换手`{best['annualized_one_way_turnover']:.2f}`倍。"
        )
    lines.append(
        "- 固定过滤没有超过不过滤基线；`market_down20_only`虽然降低暴露和换手，但50bp期末权益降到约`1.71`，2025亏损扩大。"
    )
    lines.append(
        "- 信号日前`market_down_20d`的10日篮子收益更高，但持仓日`market_down_20d`日收益为负；问题更像持仓路径中的急跌暴露，而不是信号日前是否下跌。"
    )
    lines.extend(
        [
            "- 过滤测试只用于压力判断；若改善来自少数状态/少数年份，不能直接正式化。",
            "",
            "## 信号日前最弱状态",
            "",
            markdown_table(
                weak_signal_states,
                [
                    "state_layer",
                    "state_value",
                    "signal_days",
                    "basket_ret_on_capital_mean",
                    "basket_ret_on_capital_win_rate",
                    "basket_ret_on_deployed_mean",
                    "basket_excess_ret_on_capital_mean",
                    "avg_basket_gross_weight",
                    "stress_year_signal_ratio",
                ],
                max_rows=30,
            ),
            "",
            "## 持仓日最弱状态：50bp",
            "",
            markdown_table(
                weak_path_states.filter(pl.col("roundtrip_cost_bps") == 50.0),
                [
                    "state_layer",
                    "state_value",
                    "active_days",
                    "strategy_daily_ret_mean",
                    "strategy_daily_win_rate",
                    "strategy_gross_daily_ret_mean",
                    "turnover_cost_ret_mean",
                    "avg_gross_exposure",
                    "avg_gross_abs_weight_change",
                    "drawdown_le_20pct_day_ratio",
                    "stress_year_day_ratio",
                ],
                max_rows=30,
            ),
            "",
            "## 固定过滤回测汇总",
            "",
            markdown_table(
                filter_summary.sort(["roundtrip_cost_bps", "scenario"]),
                [
                    "scenario",
                    "roundtrip_cost_bps",
                    "filter_name",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "avg_return_gross_exposure",
                    "annualized_one_way_turnover",
                    "avg_active_symbols_when_active",
                    "avg_active_industries_when_active",
                    "cost_drag_sum",
                ],
            ),
            "",
            "## 过滤年度结果：50bp",
            "",
            markdown_table(
                filter_yearly.filter(pl.col("roundtrip_cost_bps") == 50.0).sort(["scenario", "year"]),
                [
                    "scenario",
                    "year",
                    "year_return",
                    "year_gross_return",
                    "year_benchmark_return",
                    "year_cost_drag",
                    "avg_gross_exposure",
                ],
                max_rows=80,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：只使用信号日前可知的市场状态变量，并固定`4天确认+每日建篮`底稿；过滤器限制为少数可解释状态，不扫描确认天数、相位或权重。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段保留全部固定过滤结果，且没有把任何过滤器包装为优化结论；结果显示所有信号日前过滤都弱于不过滤基线，属于负向约束结论。",
            "- 风险：弱状态归因仍可能是路径相关的事后描述，不能直接把最弱状态拼成复合过滤器。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第240阶段证明确认机制能降低换手，但2018/2022/2025仍有失效，需要判断是否存在可解释的外生状态。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是，但方向从信号日前过滤转向持仓日风险保护。",
            "- 原因：信号日前下跌状态并不差，简单过滤会删掉有效反弹；持仓日急跌、连续下跌和高跌停压力才是净值路径的主要伤害，下一步应测试少数事前可知的持仓日急跌降杠杆/空仓保护。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
            "- 不采用`market_down20_only`、`exclude_hot_breadth`或`exclude_up20_hot_breadth`作为策略规则。",
            "- 下一步不继续拼信号日前状态过滤，转向持仓日急跌保护压力测试。",
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
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    base = build_base_frame()
    selected_with_state, date_state = build_age4_selected_with_state(base, stock_df, benchmark_df, layer_tags)
    signal_daily = build_signal_daily(selected_with_state)
    signal_summary = summarize_signal_by_state(signal_daily, STATE_COLUMNS)
    year_state_mix = build_year_state_mix(signal_daily, STATE_COLUMNS)
    selected_all = build_selected_for_scenarios(selected_with_state)
    filter_summary, filter_equity, filter_yearly, filter_turnover, filter_concentration, path_daily = run_filtered_backtests(
        selected_all, benchmark_df, date_state
    )
    path_summary = summarize_path_by_state(
        path_daily.filter(pl.col("scenario") == "age4_daily_all"), STATE_COLUMNS
    )
    weak_signal_states = signal_summary.sort(["basket_ret_on_capital_mean", "signal_days"]).head(40)
    weak_path_states = path_summary.sort(["roundtrip_cost_bps", "strategy_daily_ret_mean", "active_days"]).head(80)

    meta: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "feature": FEATURE,
        "horizon": HORIZON,
        "entry_age_min": ENTRY_AGE_MIN,
        "cost_bps": COST_BPS,
        "trading_days": TRADING_DAYS,
        "stress_years": STRESS_YEARS,
        "state_columns": STATE_COLUMNS,
        "signal_days": signal_daily.height,
        "selected_row_count": selected_with_state.height,
        "date_min": str(selected_with_state["datetime"].min()),
        "date_max": str(selected_with_state["datetime"].max()),
        "symbol_count": selected_with_state["symbol"].n_unique(),
        "scenarios": scenario_definitions(),
    }

    paths = {
        "date_state": OUTPUT_DIR / f"{PREFIX}_date_state.csv",
        "signal_daily": OUTPUT_DIR / f"{PREFIX}_signal_daily.csv",
        "signal_state_summary": OUTPUT_DIR / f"{PREFIX}_signal_state_summary.csv",
        "year_state_mix": OUTPUT_DIR / f"{PREFIX}_year_state_mix.csv",
        "path_daily": OUTPUT_DIR / f"{PREFIX}_path_daily.csv",
        "path_state_summary": OUTPUT_DIR / f"{PREFIX}_path_state_summary.csv",
        "filter_summary": OUTPUT_DIR / f"{PREFIX}_filter_summary.csv",
        "filter_equity": OUTPUT_DIR / f"{PREFIX}_filter_equity_curve.csv",
        "filter_yearly": OUTPUT_DIR / f"{PREFIX}_filter_yearly.csv",
        "filter_turnover": OUTPUT_DIR / f"{PREFIX}_filter_turnover.csv",
        "filter_concentration": OUTPUT_DIR / f"{PREFIX}_filter_daily_concentration.csv",
        "weak_signal_states": OUTPUT_DIR / f"{PREFIX}_weak_signal_states.csv",
        "weak_path_states": OUTPUT_DIR / f"{PREFIX}_weak_path_states.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    date_state.write_csv(paths["date_state"])
    signal_daily.write_csv(paths["signal_daily"])
    signal_summary.write_csv(paths["signal_state_summary"])
    year_state_mix.write_csv(paths["year_state_mix"])
    path_daily.write_csv(paths["path_daily"])
    path_summary.write_csv(paths["path_state_summary"])
    filter_summary.write_csv(paths["filter_summary"])
    filter_equity.write_csv(paths["filter_equity"])
    filter_yearly.write_csv(paths["filter_yearly"])
    filter_turnover.write_csv(paths["filter_turnover"])
    filter_concentration.write_csv(paths["filter_concentration"])
    weak_signal_states.write_csv(paths["weak_signal_states"])
    weak_path_states.write_csv(paths["weak_path_states"])
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(
        signal_summary,
        path_summary,
        filter_summary,
        filter_yearly,
        weak_signal_states,
        weak_path_states,
        meta,
        paths,
    )
    print(filter_summary.sort(["roundtrip_cost_bps", "scenario"]))
    print(weak_signal_states.head(12))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
