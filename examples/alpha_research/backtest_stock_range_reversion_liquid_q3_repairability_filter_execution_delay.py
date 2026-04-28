from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_repairability_filter_cost_capacity import (
    BASELINE_SCENARIO,
    CANDIDATE_SCENARIO,
    SCENARIOS,
    build_symbol_daily_from_selected,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from backtest_stock_range_reversion_liquid_q3_repairability_filter_execution_constraints import (
    build_desired_maps,
    build_exec_info,
    markdown_table,
    simulate_one,
    summarize_curve,
)


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_repairability_filter_execution_delay_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_repairability_filter_execution_delay_v1"

DELAY_DAYS: tuple[int, ...] = (0, 1, 2)
BASE_VARIANTS: tuple[dict[str, Any], ...] = (
    {
        "variant_key": "no_adv_cap",
        "description": "开盘成交，只限制停牌/一字板，不设ADV成交上限",
        "roundtrip_cost_bps": 50.0,
        "account_size_cny": 10_000_000.0,
        "max_participation_adv20": None,
    },
    {
        "variant_key": "cap5pct_adv_10m",
        "description": "开盘成交，1000万资金，单票单日成交额不超过5% ADV20",
        "roundtrip_cost_bps": 50.0,
        "account_size_cny": 10_000_000.0,
        "max_participation_adv20": 0.05,
    },
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Execution Timing Is Alpha",
        "https://www.quantifiedstrategies.com/?p=1189555",
    ),
    (
        "When Execution Delays Erode Short-Term Alpha",
        "https://concretumgroup.com/when-execution-delays-erode-short-term-alpha/",
    ),
    (
        "Intraday Patterns in the Cross-section of Stock Returns",
        "https://arxiv.org/abs/1005.3535",
    ),
    (
        "Short-term reversals and costs of immediacy",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
)


def execution_variants() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for delay_days in DELAY_DAYS:
        for base in BASE_VARIANTS:
            variants.append(
                {
                    "execution_variant": f"delay{delay_days}d_{base['variant_key']}_50bp",
                    "description": f"目标仓位延迟{delay_days}个交易日，{base['description']}",
                    "execution_delay_days": delay_days,
                    "roundtrip_cost_bps": base["roundtrip_cost_bps"],
                    "account_size_cny": base["account_size_cny"],
                    "max_participation_adv20": base["max_participation_adv20"],
                }
            )
    return variants


def build_delayed_desired(
    desired: dict[tuple[str, date], dict[str, float]], dates: list[date], delay_days: int
) -> dict[tuple[str, date], dict[str, float]]:
    delayed: dict[tuple[str, date], dict[str, float]] = {}
    for idx, source_date in enumerate(dates):
        target_idx = idx + delay_days
        if target_idx >= len(dates):
            continue
        execution_date = dates[target_idx]
        for scenario in SCENARIOS:
            target = desired.get((scenario, source_date), {})
            if target:
                delayed[(scenario, execution_date)] = dict(target)
    return delayed


def run_delay_backtest(
    desired: dict[tuple[str, date], dict[str, float]],
    dates: list[date],
    exec_info: dict[tuple[date, str], Any],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    diag_rows: list[dict[str, Any]] = []
    for variant in execution_variants():
        delayed_desired = build_delayed_desired(desired, dates, int(variant["execution_delay_days"]))
        for scenario in SCENARIOS:
            scenario_curve_rows, scenario_diag_rows = simulate_one(scenario, variant, dates, delayed_desired, exec_info)
            curve_rows.extend(scenario_curve_rows)
            diag_rows.extend(scenario_diag_rows)
            curve = pl.DataFrame(scenario_curve_rows)
            diagnostics = pl.DataFrame(scenario_diag_rows)
            summary = summarize_curve(curve, diagnostics, variant)
            summary["execution_delay_days"] = int(variant["execution_delay_days"])
            summary_rows.append(summary)
    return (
        pl.DataFrame(summary_rows).sort(["execution_variant", "scenario"]),
        pl.DataFrame(curve_rows).sort(["execution_variant", "scenario", "date"]),
        pl.DataFrame(diag_rows).sort(["execution_variant", "scenario", "date"]),
    )


def build_delay_delta(summary: pl.DataFrame) -> pl.DataFrame:
    baseline = summary.filter(pl.col("scenario") == BASELINE_SCENARIO).select(
        "execution_variant",
        pl.col("final_equity").alias("baseline_final_equity"),
        pl.col("total_return").alias("baseline_total_return"),
        pl.col("max_drawdown").alias("baseline_max_drawdown"),
        pl.col("sharpe").alias("baseline_sharpe"),
    )
    return (
        summary.join(baseline, on="execution_variant", how="left")
        .with_columns(
            (pl.col("final_equity") - pl.col("baseline_final_equity")).alias("final_equity_delta_vs_baseline"),
            (pl.col("total_return") - pl.col("baseline_total_return")).alias("total_return_delta_vs_baseline"),
            (pl.col("max_drawdown") - pl.col("baseline_max_drawdown")).alias("max_drawdown_delta_vs_baseline"),
            (pl.col("sharpe") - pl.col("baseline_sharpe")).alias("sharpe_delta_vs_baseline"),
        )
        .sort(["execution_variant", "scenario"])
    )


def write_report(summary: pl.DataFrame, delay_delta: pl.DataFrame, meta: dict[str, Any], paths: dict[str, Path]) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    candidate_cap = delay_delta.filter(
        (pl.col("scenario") == CANDIDATE_SCENARIO) & pl.col("execution_variant").str.contains("cap5pct_adv_10m")
    ).sort("execution_delay_days")
    candidate_no_cap = delay_delta.filter(
        (pl.col("scenario") == CANDIDATE_SCENARIO) & pl.col("execution_variant").str.contains("no_adv_cap")
    ).sort("execution_delay_days")
    delay0 = candidate_cap.filter(pl.col("execution_delay_days") == 0).to_dicts()[0]
    delay1 = candidate_cap.filter(pl.col("execution_delay_days") == 1).to_dicts()[0]
    delay2 = candidate_cap.filter(pl.col("execution_delay_days") == 2).to_dicts()[0]
    retention_1 = delay1["total_return"] / delay0["total_return"] if delay0["total_return"] else 0.0
    retention_2 = delay2["total_return"] / delay0["total_return"] if delay0["total_return"] else 0.0
    continue_judgment = "是" if delay1["final_equity"] > 1.0 and delay1["sharpe"] > 0 else "否"
    continue_reason = (
        "延迟1日后候选仍为正收益且Sharpe为正，说明信号不是完全依赖立刻成交。"
        if continue_judgment == "是"
        else "延迟1日后候选已经无法维持正收益或正Sharpe，说明信号对成交时点过于敏感。"
    )

    lines = [
        "# 股票震荡liquid_q3成交干枯过滤延迟成交压力 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：第248阶段真实成交约束后的延迟成交压力，不新增信号、不调`volume_ratio_20 <= 0.70`阈值。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 短周期均值回归的alpha半衰期通常很短，执行延迟会把策略从原始信息集推到另一个收益区间。",
        "- 因此延迟成交不是普通敏感性测试，而是可交易性的核心反证；若延迟后快速归零，就不能正式化。",
        "- 本阶段采用同一目标仓位整体延迟0/1/2个交易日的方式，不新增择时判断。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心观察",
            "",
            f"- 候选1000万、5% ADV上限：延迟0日总收益`{pct(delay0['total_return'])}`，Sharpe `{delay0['sharpe']:.2f}`；延迟1日总收益`{pct(delay1['total_return'])}`，Sharpe `{delay1['sharpe']:.2f}`；延迟2日总收益`{pct(delay2['total_return'])}`，Sharpe `{delay2['sharpe']:.2f}`。",
            f"- 延迟1日收益保留率约`{pct(retention_1)}`，延迟2日收益保留率约`{pct(retention_2)}`。",
            f"- 延迟1日相对同口径基线：期末权益差`{delay1['final_equity_delta_vs_baseline']:.4f}`，回撤差`{pct(delay1['max_drawdown_delta_vs_baseline'])}`，Sharpe差`{delay1['sharpe_delta_vs_baseline']:.2f}`。",
            "- 直觉判断：延迟后如果优势大幅衰减，说明它更像短半衰期流动性修复；这并不否定策略，但会限制执行方式。",
            "",
            "## 候选延迟明细：1000万/5% ADV",
            "",
            markdown_table(
                candidate_cap,
                [
                    "execution_delay_days",
                    "execution_variant",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "active_day_win_rate",
                    "avg_actual_gross_exposure",
                    "overall_fill_ratio",
                    "final_equity_delta_vs_baseline",
                    "total_return_delta_vs_baseline",
                    "max_drawdown_delta_vs_baseline",
                    "sharpe_delta_vs_baseline",
                ],
            ),
            "",
            "## 候选延迟明细：无ADV上限",
            "",
            markdown_table(
                candidate_no_cap,
                [
                    "execution_delay_days",
                    "execution_variant",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "active_day_win_rate",
                    "avg_actual_gross_exposure",
                    "overall_fill_ratio",
                    "final_equity_delta_vs_baseline",
                    "total_return_delta_vs_baseline",
                    "max_drawdown_delta_vs_baseline",
                    "sharpe_delta_vs_baseline",
                ],
            ),
            "",
            "## 全部汇总",
            "",
            markdown_table(
                summary,
                [
                    "execution_variant",
                    "scenario",
                    "execution_delay_days",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "cost_drag_sum",
                    "active_day_win_rate",
                    "avg_actual_gross_exposure",
                    "overall_fill_ratio",
                    "cap_limited_weight_sum",
                    "blocked_buy_weight_sum",
                    "blocked_sell_weight_sum",
                ],
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只延迟执行同一套目标仓位，不新增预测变量、不调信号阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否，但仍不是严格样本外。",
            "- 原因：延迟成交是反证测试；它不会通过新增自由度改善结果，只会暴露alpha半衰期风险。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第248阶段通过第一层真实成交约束后，必须确认信号是否过度依赖即时成交。",
            "",
            "## 运行后继续价值反思",
            "",
            f"- 判断：{continue_judgment}。",
            f"- 原因：{continue_reason}",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 延迟1日和2日仍保持正收益并优于基线，下一步做纸面跟踪框架和候选版本整理。",
            "- 同时保留执行提醒：收益随延迟递减，正式化前仍要考虑收盘前信号/收盘成交的可行性。",
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
    selected_all = pl.read_parquet(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_selected_all.parquet")
    stock_df, _benchmark_df = load_panels()
    symbol_daily = build_symbol_daily_from_selected(selected_all)
    desired, dates = build_desired_maps(symbol_daily)
    exec_info = build_exec_info(stock_df)
    summary, curves, diagnostics = run_delay_backtest(desired, dates, exec_info)
    delay_delta = build_delay_delta(summary)
    meta: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_scenario": BASELINE_SCENARIO,
        "candidate_scenario": CANDIDATE_SCENARIO,
        "delay_days": DELAY_DAYS,
        "base_variants": BASE_VARIANTS,
        "source_output_dir": str(FILTER_OUTPUT_DIR),
        "research_sources": RESEARCH_SOURCES,
        "delay_note": "Target weights are shifted by N trading days and replayed with the same open-to-next-open execution simulator.",
    }
    paths = {
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "delay_delta": OUTPUT_DIR / f"{PREFIX}_delay_delta.csv",
        "curves": OUTPUT_DIR / f"{PREFIX}_curves.csv",
        "diagnostics": OUTPUT_DIR / f"{PREFIX}_diagnostics.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary.write_csv(paths["summary"])
    delay_delta.write_csv(paths["delay_delta"])
    curves.write_csv(paths["curves"])
    diagnostics.write_csv(paths["diagnostics"])
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(summary, delay_delta, meta, paths)
    print(summary)
    print(delay_delta)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
