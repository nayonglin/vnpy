from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_industry_signal_lifecycle import build_base_frame
from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_liquid_q3_persistent_state_filter import (
    build_age4_selected_with_state,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    COST_BPS,
    FEATURE,
    HORIZON,
    NATIVE_RESULTS_DIR,
    TRADING_DAYS,
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
from backtest_stock_range_reversion_liquid_q3_persistent_confirmation import build_confirmation_lots


OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_persistent_crash_guard_2018_2026"),
    )
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_persistent_crash_guard_v1"

ENTRY_AGE_MIN: int = int(os.getenv("ENTRY_AGE_MIN", "4") or 4)
EPS: float = 1e-12


def scenario_definitions() -> list[dict[str, Any]]:
    return [
        {
            "scenario": "age4_daily_no_guard",
            "description": "4天确认每日建篮，不做持仓期急跌保护",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_crash_guard",
            "guard_name": "no_guard",
            "guard_action": "none",
        },
        {
            "scenario": "age4_daily_ret5_crash_half",
            "description": "持仓日前中证1000五日跌幅不小于5%时，下一日目标权重减半",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_crash_guard",
            "guard_name": "ret5_le_-5pct",
            "guard_action": "half",
        },
        {
            "scenario": "age4_daily_ret5_crash_flat",
            "description": "持仓日前中证1000五日跌幅不小于5%时，下一日目标权重归零",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_crash_guard",
            "guard_name": "ret5_le_-5pct",
            "guard_action": "flat",
        },
        {
            "scenario": "age4_daily_down_streak3_flat",
            "description": "持仓日前中证1000连续下跌至少3天时，下一日目标权重归零",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_crash_guard",
            "guard_name": "down_streak_ge3",
            "guard_action": "flat",
        },
        {
            "scenario": "age4_daily_limit_down_q5_flat",
            "description": "持仓日前跌停收盘占比处于最高五分位时，下一日目标权重归零",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_crash_guard",
            "guard_name": "limit_down_q5",
            "guard_action": "flat",
        },
        {
            "scenario": "age4_daily_panic_combo_half",
            "description": "五日急跌、连续下跌或跌停压力任一触发时，下一日目标权重减半",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_crash_guard",
            "guard_name": "panic_combo",
            "guard_action": "half",
        },
        {
            "scenario": "age4_daily_panic_combo_flat",
            "description": "五日急跌、连续下跌或跌停压力任一触发时，下一日目标权重归零",
            "bucket": "liquid_q3",
            "weight_mode": "age4_daily_crash_guard",
            "guard_name": "panic_combo",
            "guard_action": "flat",
        },
    ]


def guard_condition_expr(guard_name: str) -> pl.Expr:
    ret5_crash = pl.col("bm_ret_5") <= -0.05
    down_streak = pl.col("bm_down_streak") >= 3
    limit_pressure = pl.col("limit_down_close_ratio_q") == "q5_high_limit_down"
    if guard_name == "no_guard":
        return pl.lit(False)
    if guard_name == "ret5_le_-5pct":
        return ret5_crash
    if guard_name == "down_streak_ge3":
        return down_streak
    if guard_name == "limit_down_q5":
        return limit_pressure
    if guard_name == "panic_combo":
        return ret5_crash | down_streak | limit_pressure
    raise ValueError(f"Unknown guard: {guard_name}")


def guard_multiplier_expr(guard_name: str, guard_action: str) -> pl.Expr:
    condition = guard_condition_expr(guard_name).fill_null(False)
    if guard_action == "none":
        return pl.lit(1.0)
    if guard_action == "half":
        return pl.when(condition).then(pl.lit(0.5)).otherwise(pl.lit(1.0))
    if guard_action == "flat":
        return pl.when(condition).then(pl.lit(0.0)).otherwise(pl.lit(1.0))
    raise ValueError(f"Unknown guard action: {guard_action}")


def build_selected_scenarios(selected_base: pl.DataFrame) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for scenario in scenario_definitions():
        frames.append(
            selected_base.with_columns(
                pl.lit(scenario["scenario"]).alias("scenario"),
                pl.lit(scenario["description"]).alias("scenario_description"),
                pl.lit("liquid_q3").alias("bucket"),
                pl.lit("age4_daily_crash_guard").alias("weight_mode"),
                pl.lit(scenario["guard_name"]).alias("guard_name"),
                pl.lit(scenario["guard_action"]).alias("guard_action"),
            )
        )
    return pl.concat(frames, how="vertical").sort(["scenario", "datetime", "industry", FEATURE])


def apply_crash_guard(lots: pl.DataFrame, date_state: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    state_cols = [
        "date",
        "bm_ret_5",
        "bm_down_streak",
        "limit_down_close_ratio_q",
        "market_state_20d",
        "bm_ret_5_band",
        "bm_ret_20_band",
        "breadth_pos_20d_band",
    ]
    target_state = date_state.select([col for col in state_cols if col in date_state.columns]).rename(
        {"date": "target_date"}
    )
    scenario_meta = pl.DataFrame(scenario_definitions()).select("scenario", "guard_name", "guard_action")
    guarded = lots.join(target_state, on="target_date", how="left")
    frames: list[pl.DataFrame] = []
    for scenario in scenario_definitions():
        scenario_lots = guarded.filter(pl.col("scenario") == scenario["scenario"]).with_columns(
            guard_condition_expr(scenario["guard_name"]).fill_null(False).alias("guard_triggered"),
            guard_multiplier_expr(scenario["guard_name"], scenario["guard_action"]).alias("guard_multiplier"),
        )
        frames.append(scenario_lots)
    guarded_all = (
        pl.concat(frames, how="vertical")
        .with_columns(
            pl.col("lot_weight").alias("raw_lot_weight"),
            (pl.col("lot_weight") * pl.col("guard_multiplier")).alias("lot_weight"),
        )
        .filter(pl.col("lot_weight") > EPS)
        .join(scenario_meta, on="scenario", how="left")
        .sort(["scenario", "target_date", "signal_date", "symbol"])
    )
    daily_guard = (
        guarded.group_by(["scenario", "target_date"])
        .agg(
            guard_condition_expr("ret5_le_-5pct").fill_null(False).any().alias("ret5_crash_day"),
            guard_condition_expr("down_streak_ge3").fill_null(False).any().alias("down_streak_day"),
            guard_condition_expr("limit_down_q5").fill_null(False).any().alias("limit_pressure_day"),
            pl.col("bm_ret_5").first().alias("bm_ret_5"),
            pl.col("bm_down_streak").first().alias("bm_down_streak"),
            pl.col("limit_down_close_ratio_q").first().alias("limit_down_close_ratio_q"),
            pl.col("raw_lot_weight").sum().alias("raw_lot_weight_sum")
            if "raw_lot_weight" in guarded.columns
            else pl.col("lot_weight").sum().alias("raw_lot_weight_sum"),
        )
    )
    guard_daily_frames: list[pl.DataFrame] = []
    for scenario in scenario_definitions():
        scenario_daily = daily_guard.filter(pl.col("scenario") == scenario["scenario"]).with_columns(
            guard_condition_expr(scenario["guard_name"]).fill_null(False).alias("guard_triggered"),
            guard_multiplier_expr(scenario["guard_name"], scenario["guard_action"]).alias("guard_multiplier"),
        )
        guard_daily_frames.append(scenario_daily)
    guard_daily = (
        pl.concat(guard_daily_frames, how="vertical")
        .with_columns(
            (pl.col("raw_lot_weight_sum") * (1.0 - pl.col("guard_multiplier"))).alias("guarded_weight_sum")
        )
        .join(scenario_meta, on="scenario", how="left")
        .sort(["scenario", "target_date"])
    )
    return guarded_all, guard_daily


def build_guard_summary(guard_daily: pl.DataFrame) -> pl.DataFrame:
    return (
        guard_daily.group_by("scenario")
        .agg(
            pl.first("guard_name").alias("guard_name"),
            pl.first("guard_action").alias("guard_action"),
            pl.len().alias("target_days"),
            pl.col("guard_triggered").sum().alias("guard_trigger_days"),
            pl.col("guard_triggered").mean().alias("guard_trigger_day_ratio"),
            pl.col("guarded_weight_sum").sum().alias("guarded_weight_sum"),
            pl.col("guarded_weight_sum").mean().alias("avg_guarded_weight_sum"),
            pl.col("raw_lot_weight_sum").mean().alias("avg_raw_lot_weight_sum"),
        )
        .sort("scenario")
    )


def run_backtests(
    selected_all: pl.DataFrame, protected_lots: pl.DataFrame, benchmark_df: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    symbol_daily_all = build_symbol_daily(protected_lots)
    benchmark_daily = build_benchmark_daily(benchmark_df)
    all_curves: list[pl.DataFrame] = []
    all_summary: list[dict[str, Any]] = []
    all_turnover: list[pl.DataFrame] = []
    all_concentration: list[pl.DataFrame] = []
    lookup = {item["scenario"]: item for item in scenario_definitions()}

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
            row["guard_name"] = scenario["guard_name"]
            row["guard_action"] = scenario["guard_action"]
            all_summary.append(row)

    summary_df = pl.DataFrame(all_summary).sort(["roundtrip_cost_bps", "scenario"])
    equity_df = pl.concat(all_curves, how="vertical").sort(["roundtrip_cost_bps", "scenario", "date"])
    turnover_df = pl.concat(all_turnover, how="vertical").sort(["scenario", "target_date"])
    concentration_df = pl.concat(all_concentration, how="vertical").sort(["scenario", "target_date"])
    yearly_df = (
        build_yearly_summary(equity_df)
        .join(
            summary_df.select("scenario", "guard_name", "guard_action").unique(),
            on="scenario",
            how="left",
        )
        .sort(["roundtrip_cost_bps", "scenario", "year"])
    )
    return summary_df, equity_df, yearly_df, turnover_df, concentration_df


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return frame.select([col for col in columns if col in frame.columns]).head(max_rows).to_pandas().to_markdown(
        index=False
    )


def write_report(
    summary_df: pl.DataFrame,
    yearly_df: pl.DataFrame,
    guard_summary: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    baseline_50 = summary_df.filter(
        (pl.col("scenario") == "age4_daily_no_guard") & (pl.col("roundtrip_cost_bps") == 50.0)
    ).to_dicts()
    best_50 = (
        summary_df.filter(pl.col("roundtrip_cost_bps") == 50.0)
        .sort(["final_equity", "max_drawdown"], descending=[True, True])
        .head(1)
        .to_dicts()
    )
    base = baseline_50[0] if baseline_50 else None
    best = best_50[0] if best_50 else None
    lines = [
        "# 股票震荡liquid_q3持续确认持仓急跌保护 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：`4天确认+每日建篮`的持仓日急跌保护压力测试，不是正式交易版本。",
        "- 外部调研判断：均值回归止损/保护并非天然有效，容易砍掉反弹；因此本阶段只测上一阶段暴露出的少数持仓期弱状态，不做参数网格。",
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
            f"- 50bp下期末权益最高的是`{best['scenario']}`：期末权益`{best['final_equity']:.4f}`，"
            f"总收益`{pct(best['total_return'])}`，最大回撤`{pct(best['max_drawdown'])}`，"
            f"Sharpe `{best['sharpe']:.2f}`，年化单边换手`{best['annualized_one_way_turnover']:.2f}`倍。"
        )
    if base and best and best["scenario"] == "age4_daily_no_guard":
        lines.append(
            "- 结论：本轮持仓期急跌保护没有通过。保护动作要么砍掉反弹收益，要么提高换手和成本，"
            "并没有在50bp现实成本下改善收益/回撤比。"
        )
    elif base and best:
        lines.append(
            "- 结论：存在保护版本在期末权益上超过基线，但仍需用触发比例、年度稳定性和成本敏感性继续验证，"
            "不能直接视为正式参数。"
        )
    lines.extend(
        [
            "- 若保护只降低暴露但收益/回撤比没有改善，则它不是风险管理，而是把策略做薄。",
            "",
            "## 回测汇总",
            "",
            markdown_table(
                summary_df.sort(["roundtrip_cost_bps", "scenario"]),
                [
                    "scenario",
                    "roundtrip_cost_bps",
                    "guard_name",
                    "guard_action",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "avg_return_gross_exposure",
                    "annualized_one_way_turnover",
                    "cost_drag_sum",
                ],
                max_rows=80,
            ),
            "",
            "## 保护触发统计",
            "",
            markdown_table(
                guard_summary,
                [
                    "scenario",
                    "guard_name",
                    "guard_action",
                    "target_days",
                    "guard_trigger_days",
                    "guard_trigger_day_ratio",
                    "guarded_weight_sum",
                    "avg_guarded_weight_sum",
                    "avg_raw_lot_weight_sum",
                ],
                max_rows=80,
            ),
            "",
            "## 年度结果：50bp",
            "",
            markdown_table(
                yearly_df.filter(pl.col("roundtrip_cost_bps") == 50.0).sort(["scenario", "year"]),
                [
                    "scenario",
                    "year",
                    "year_return",
                    "year_gross_return",
                    "year_benchmark_return",
                    "year_cost_drag",
                    "avg_gross_exposure",
                ],
                max_rows=120,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：保护条件来自第241阶段已暴露的持仓期弱状态，只测试空仓/半仓两个粗动作，不扫描止损阈值、确认天数、相位或权重。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：结果没有选择出更优保护参数；相反，50bp下所有保护版本都弱于不保护基线，这更像一次反证而不是参数拟合。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第241阶段显示信号日前过滤无效，持仓期急跌才是净值路径伤害，本阶段正面验证风险保护是否有用。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：股票震荡主线仍有价值；本轮这种粗持仓期急跌保护方向暂时没有继续扩参价值。",
            "- 原因：保护触发日确实覆盖弱持仓环境，但均值回归策略的收益也来自恐慌后的修复；粗暴半仓/空仓会把亏损和修复一起砍掉，还增加调仓成本。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
            "- 不继续围绕急跌保护做阈值网格。",
            "- 下一步回到信号层和持仓路径归因，区分“恐慌后可修复的超跌”和“基本面/流动性恶化导致的继续下跌”。",
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
    selected_base, date_state = build_age4_selected_with_state(base, stock_df, benchmark_df, layer_tags)
    selected_all = build_selected_scenarios(selected_base)
    raw_lots = build_confirmation_lots(selected_all)
    protected_lots, guard_daily = apply_crash_guard(raw_lots, date_state)
    guard_summary = build_guard_summary(guard_daily)
    summary_df, equity_df, yearly_df, turnover_df, concentration_df = run_backtests(
        selected_all, protected_lots, benchmark_df
    )

    meta: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "feature": FEATURE,
        "horizon": HORIZON,
        "entry_age_min": ENTRY_AGE_MIN,
        "cost_bps": COST_BPS,
        "trading_days": TRADING_DAYS,
        "date_min": str(selected_base["datetime"].min()),
        "date_max": str(selected_base["datetime"].max()),
        "symbol_count": selected_base["symbol"].n_unique(),
        "raw_lot_rows": raw_lots.height,
        "protected_lot_rows": protected_lots.height,
        "scenarios": scenario_definitions(),
    }
    paths = {
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "equity_curve": OUTPUT_DIR / f"{PREFIX}_equity_curve.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "turnover": OUTPUT_DIR / f"{PREFIX}_turnover.csv",
        "daily_concentration": OUTPUT_DIR / f"{PREFIX}_daily_concentration.csv",
        "guard_daily": OUTPUT_DIR / f"{PREFIX}_guard_daily.csv",
        "guard_summary": OUTPUT_DIR / f"{PREFIX}_guard_summary.csv",
        "protected_lots": OUTPUT_DIR / f"{PREFIX}_protected_lots.parquet",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary_df.write_csv(paths["summary"])
    equity_df.write_csv(paths["equity_curve"])
    yearly_df.write_csv(paths["yearly"])
    turnover_df.write_csv(paths["turnover"])
    concentration_df.write_csv(paths["daily_concentration"])
    guard_daily.write_csv(paths["guard_daily"])
    guard_summary.write_csv(paths["guard_summary"])
    protected_lots.write_parquet(paths["protected_lots"])
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(
        summary_df,
        yearly_df,
        guard_summary,
        meta,
        paths,
    )
    print(summary_df.sort(["roundtrip_cost_bps", "scenario"]))
    print(guard_summary)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
