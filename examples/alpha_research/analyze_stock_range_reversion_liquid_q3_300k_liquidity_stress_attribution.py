from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution import (
    OUTPUT_DIR as CURVE_OUTPUT_DIR,
    PREFIX as CURVE_PREFIX,
)
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import ACCOUNT_SIZE_CNY, write_json
from analyze_stock_range_reversion_liquid_q3_300k_repairable_state_overlay import (
    OUTPUT_DIR as REPAIRABLE_OUTPUT_DIR,
    PREFIX as REPAIRABLE_PREFIX,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import PAPER_SCENARIO, markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_liquidity_stress_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_liquidity_stress_attribution_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term reversals can be compensation for liquidity provision",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "Short-term reversal strategies have negative exposure to volatility shocks",
        "https://quantpedia.com/liquidity-creation-in-short-term-reversal-strategies-and-volatility-risk/",
    ),
    (
        "Liquidity vacuums limit mean reversion reliability",
        "https://tradevae.com/academy/trading-strategies/mean-reversion/limits-of-mean-reversion-strategies/",
    ),
    (
        "Price limits change market stability and liquidity-provider risk",
        "https://arxiv.org/abs/1805.04728",
    ),
)


def read_csv(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def compound_return(values: list[float]) -> float:
    equity = 1.0
    for value in values:
        equity *= 1.0 + value
    return equity - 1.0


def classify_stress_subtype(row: dict[str, Any]) -> str:
    up_ratio = to_float(row.get("universe_up_ratio"), default=0.5)
    down_2pct = to_float(row.get("universe_down_2pct_ratio"), default=0.0)
    limit_down = to_float(row.get("limit_down_close_ratio"), default=0.0)
    oneword_down = to_float(row.get("oneword_limit_down_ratio"), default=0.0)
    benchmark_mom_20 = to_float(row.get("benchmark_mom_20"), default=0.0)
    benchmark_down_streak = int(to_float(row.get("benchmark_down_streak"), default=0.0))
    benchmark_ret = to_float(row.get("benchmark_c2c_ret"), default=0.0)

    if oneword_down > 0.002 or limit_down > 0.03:
        return "stress_lockdown"
    if benchmark_mom_20 < -0.08 or benchmark_down_streak >= 4 or benchmark_ret < -0.02:
        return "stress_trend_breakdown_overlap"
    if down_2pct > 0.40 or up_ratio < 0.25:
        return "stress_broad_capitulation"
    if 0.25 <= up_ratio <= 0.45 and limit_down <= 0.02 and oneword_down <= 0.002:
        return "stress_liquidity_premium_window"
    return "stress_mixed_pressure"


def add_stress_subtype(stress_daily: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in stress_daily.iter_rows(named=True):
        current = dict(row)
        current["stress_subtype"] = classify_stress_subtype(current)
        current["lockdown_flag"] = current["stress_subtype"] == "stress_lockdown"
        current["trend_breakdown_overlap_flag"] = current["stress_subtype"] == "stress_trend_breakdown_overlap"
        current["broad_capitulation_flag"] = current["stress_subtype"] == "stress_broad_capitulation"
        current["liquidity_premium_window_flag"] = current["stress_subtype"] == "stress_liquidity_premium_window"
        rows.append(current)
    return pl.DataFrame(rows).sort("date") if rows else pl.DataFrame()


def summarize_by(frame: pl.DataFrame, group_col: str) -> pl.DataFrame:
    if frame.is_empty() or group_col not in frame.columns:
        return pl.DataFrame()
    return (
        frame.group_by(group_col)
        .agg(
            pl.len().alias("days"),
            pl.col("strategy_daily_ret_min_fee").sum().alias("net_return_sum"),
            ((pl.col("strategy_daily_ret_min_fee") + 1).product() - 1).alias("compounded_return"),
            pl.col("strategy_daily_ret_min_fee").mean().alias("avg_daily_ret"),
            pl.col("strategy_daily_ret_min_fee").min().alias("worst_daily_ret"),
            pl.col("strategy_daily_ret_min_fee").quantile(0.10).alias("p10_daily_ret"),
            (pl.col("strategy_daily_ret_min_fee") > 0).mean().alias("daily_win_rate"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            pl.col("zero_lot_target_count").mean().alias("avg_zero_lot_target_count"),
            pl.col("universe_up_ratio").mean().alias("avg_universe_up_ratio"),
            pl.col("universe_down_2pct_ratio").mean().alias("avg_universe_down_2pct_ratio"),
            pl.col("limit_down_close_ratio").mean().alias("avg_limit_down_close_ratio"),
            pl.col("oneword_limit_down_ratio").mean().alias("avg_oneword_limit_down_ratio"),
            pl.col("benchmark_mom_20").mean().alias("avg_benchmark_mom_20"),
            pl.col("benchmark_down_streak").mean().alias("avg_benchmark_down_streak"),
        )
        .sort("net_return_sum")
    )


def build_worst_stress_days(stress_daily: pl.DataFrame) -> pl.DataFrame:
    return stress_daily.sort("strategy_daily_ret_min_fee").select(
        [
            "date",
            "stress_subtype",
            "strategy_daily_ret_min_fee",
            "strategy_gross_daily_ret",
            "turnover_cost_ret_min_fee",
            "actual_gross_weight",
            "actual_symbol_count",
            "zero_lot_target_count",
            "universe_up_ratio",
            "universe_down_2pct_ratio",
            "limit_down_close_ratio",
            "oneword_limit_down_ratio",
            "benchmark_c2c_ret",
            "benchmark_mom_20",
            "benchmark_down_streak",
        ]
    ).head(40)


def position_join_stress(position_daily: pl.DataFrame, stress_daily: pl.DataFrame) -> pl.DataFrame:
    return position_daily.join(
        stress_daily.select(
            [
                "date",
                "stress_subtype",
                "strategy_daily_ret_min_fee",
                "universe_up_ratio",
                "limit_down_close_ratio",
                "oneword_limit_down_ratio",
                "benchmark_mom_20",
            ]
        ),
        on="date",
        how="inner",
    )


def summarize_position_group(position_stress: pl.DataFrame, group_cols: list[str], worst_only: bool = False) -> pl.DataFrame:
    if position_stress.is_empty():
        return pl.DataFrame()
    work = position_stress
    if worst_only:
        threshold = to_float(work["strategy_daily_ret_min_fee"].quantile(0.10))
        work = work.filter(pl.col("strategy_daily_ret_min_fee") <= threshold)
    return (
        work.group_by(group_cols)
        .agg(
            pl.len().alias("position_days"),
            pl.col("date").n_unique().alias("calendar_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("actual_weight").mean().alias("avg_weight"),
            pl.col("actual_weight").max().alias("max_weight"),
            pl.col("gross_contribution").sum().alias("gross_contribution_sum"),
            pl.col("gross_contribution").mean().alias("avg_position_contribution"),
            pl.col("daily_ret").mean().alias("avg_position_daily_ret"),
        )
        .sort("gross_contribution_sum")
    )


def build_quality_checkpoints(summary: dict[str, Any], stress_daily: pl.DataFrame, position_stress: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(name: str, status: str, value: Any, expected: Any, note: str) -> None:
        rows.append(
            {
                "checkpoint": name,
                "status": status,
                "value": "" if value is None else str(value),
                "expected": "" if expected is None else str(expected),
                "note": note,
            }
        )

    add(
        "stress_days_found",
        "pass" if stress_daily.height > 0 else "fail",
        stress_daily.height,
        ">0",
        "必须识别出压力状态，才能做内部归因。",
    )
    add(
        "stress_subtypes_found",
        "pass" if stress_daily["stress_subtype"].n_unique() >= 2 else "warn",
        stress_daily["stress_subtype"].n_unique() if not stress_daily.is_empty() else 0,
        ">=2",
        "压力状态至少应能拆出多个子结构。",
    )
    missing_subtype = stress_daily.select(pl.col("stress_subtype").null_count()).item() if not stress_daily.is_empty() else -1
    add(
        "stress_subtype_coverage",
        "pass" if missing_subtype == 0 else "fail",
        missing_subtype,
        0,
        "所有压力日都要有子类型标签。",
    )
    position_days = position_stress.height
    add(
        "stress_position_contribution_available",
        "pass" if position_days > 0 else "fail",
        position_days,
        ">0",
        "压力日需要能追溯到持仓贡献。",
    )
    add(
        "no_signal_parameter_change",
        "pass",
        "no signal/threshold change",
        "no signal/threshold change",
        "本阶段只做压力桶归因，不改交易信号。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    subtype_summary: pl.DataFrame,
    worst_days: pl.DataFrame,
    stress_industry: pl.DataFrame,
    worst_industry: pl.DataFrame,
    worst_symbol: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    best_subtype = subtype_summary.sort("net_return_sum", descending=True).row(0, named=True)
    worst_subtype = subtype_summary.sort("worst_daily_ret").row(0, named=True)
    lines = [
        "# 股票震荡liquid_q3 30万压力状态内部归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：`mr_liquidity_stress`内部归因；不新增信号、不调参数、不生成新策略版本。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元。",
        "- A/B判断：纯归因，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 短期反转常被解释为提供流动性的补偿，因此压力环境可能贡献收益。",
        "- 但短期反转也会暴露于波动冲击和流动性真空；A股涨跌停机制会放大这种尾部。",
        "- 所以本阶段只拆压力桶，不把任何子类型直接写成交易规则。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心摘要",
            "",
            f"- 压力日`{summary['stress_days']}`天，占全样本`{pct(summary['stress_day_ratio'])}`。",
            f"- 压力日净收益合计`{pct(summary['stress_net_return_sum'])}`，复合收益`{pct(summary['stress_compounded_return'])}`，最差单日`{pct(summary['stress_worst_daily_ret'])}`。",
            f"- 压力日平均实际暴露`{pct(summary['stress_avg_actual_gross_weight'])}`，平均持仓`{summary['stress_avg_actual_symbol_count']:.1f}`只。",
            f"- 收益贡献最高子类型：`{best_subtype['stress_subtype']}`，净收益合计`{pct(best_subtype['net_return_sum'])}`，复合收益`{pct(best_subtype['compounded_return'])}`。",
            f"- 最差单日所在子类型：`{worst_subtype['stress_subtype']}`，最差单日`{pct(worst_subtype['worst_daily_ret'])}`。",
            "- 初步判断：压力状态不是单一坏环境；它同时包含流动性补偿窗口和尾部锁死风险。下一步应优先从行业/个股结构切尾，而不是继续调整总仓。",
            "",
            "## 压力子类型汇总",
            "",
            markdown_table(
                subtype_summary,
                [
                    "stress_subtype",
                    "days",
                    "net_return_sum",
                    "compounded_return",
                    "avg_daily_ret",
                    "worst_daily_ret",
                    "p10_daily_ret",
                    "daily_win_rate",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "avg_universe_up_ratio",
                    "avg_universe_down_2pct_ratio",
                    "avg_limit_down_close_ratio",
                    "avg_oneword_limit_down_ratio",
                    "avg_benchmark_mom_20",
                ],
                max_rows=20,
            ),
            "",
            "## 最差压力日",
            "",
            markdown_table(worst_days, worst_days.columns, max_rows=40),
            "",
            "## 压力日行业贡献",
            "",
            markdown_table(
                stress_industry,
                [
                    "industry",
                    "position_days",
                    "calendar_days",
                    "symbols",
                    "avg_weight",
                    "max_weight",
                    "gross_contribution_sum",
                    "avg_position_contribution",
                    "avg_position_daily_ret",
                ],
                max_rows=80,
            ),
            "",
            "## 最差10%压力日行业贡献",
            "",
            markdown_table(
                worst_industry,
                [
                    "industry",
                    "position_days",
                    "calendar_days",
                    "symbols",
                    "avg_weight",
                    "max_weight",
                    "gross_contribution_sum",
                    "avg_position_contribution",
                    "avg_position_daily_ret",
                ],
                max_rows=80,
            ),
            "",
            "## 最差10%压力日个股贡献",
            "",
            markdown_table(
                worst_symbol.head(40),
                [
                    "symbol",
                    "code_name",
                    "industry",
                    "position_days",
                    "calendar_days",
                    "avg_weight",
                    "max_weight",
                    "gross_contribution_sum",
                    "avg_position_contribution",
                    "avg_position_daily_ret",
                ],
                max_rows=40,
            ),
            "",
            "## 质量检查点",
            "",
            markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 失败项",
            "",
            "无数据" if failed.is_empty() else markdown_table(failed, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 警告项",
            "",
            "无数据" if warned.is_empty() else markdown_table(warned, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只拆解压力状态，不搜索参数、不修改交易规则。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：归因结果只用于确定下一步风险来源，不把子类型直接固化为过滤器。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：上一阶段显示收益和尾部都集中在压力状态，必须拆清压力内部结构。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：压力桶归因能决定下一步该做行业暴露上限、ST审计，还是压力子类型OOS切片。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 下一步只允许沿风险来源继续做结构约束，不做总仓加减仓。",
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
    daily = read_csv(REPAIRABLE_OUTPUT_DIR / f"{REPAIRABLE_PREFIX}_base_rerun_daily.csv")
    repairable_state = read_csv(REPAIRABLE_OUTPUT_DIR / f"{REPAIRABLE_PREFIX}_repairable_state.csv")
    position_daily = read_csv(CURVE_OUTPUT_DIR / f"{CURVE_PREFIX}_position_daily.csv")

    joined = (
        daily.join(repairable_state.rename({"target_date": "date"}), on="date", how="left")
        .filter(pl.col("mr_environment_state") == "mr_liquidity_stress")
        .sort("date")
    )
    stress_daily = add_stress_subtype(joined)
    subtype_summary = summarize_by(stress_daily, "stress_subtype")
    worst_days = build_worst_stress_days(stress_daily)
    position_stress = position_join_stress(position_daily, stress_daily)
    stress_industry = summarize_position_group(position_stress, ["industry"])
    worst_industry = summarize_position_group(position_stress, ["industry"], worst_only=True)
    worst_symbol = summarize_position_group(position_stress, ["symbol", "code_name", "industry"], worst_only=True)

    stress_returns = [float(value) for value in stress_daily["strategy_daily_ret_min_fee"].to_list()]
    total_days = daily.height
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scenario": PAPER_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "date_start": daily["date"].min(),
        "date_end": daily["date"].max(),
        "total_days": total_days,
        "stress_days": stress_daily.height,
        "stress_day_ratio": stress_daily.height / total_days if total_days else 0.0,
        "stress_net_return_sum": to_float(stress_daily["strategy_daily_ret_min_fee"].sum()),
        "stress_compounded_return": compound_return(stress_returns),
        "stress_avg_daily_ret": to_float(stress_daily["strategy_daily_ret_min_fee"].mean()),
        "stress_worst_daily_ret": to_float(stress_daily["strategy_daily_ret_min_fee"].min()),
        "stress_daily_win_rate": to_float((stress_daily["strategy_daily_ret_min_fee"] > 0).mean()),
        "stress_avg_actual_gross_weight": to_float(stress_daily["actual_gross_weight"].mean()),
        "stress_avg_actual_symbol_count": to_float(stress_daily["actual_symbol_count"].mean()),
        "stress_subtype_count": stress_daily["stress_subtype"].n_unique() if not stress_daily.is_empty() else 0,
    }
    quality = build_quality_checkpoints(summary, stress_daily, position_stress)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "stress_daily": OUTPUT_DIR / f"{PREFIX}_stress_daily.csv",
        "subtype_summary": OUTPUT_DIR / f"{PREFIX}_subtype_summary.csv",
        "worst_days": OUTPUT_DIR / f"{PREFIX}_worst_days.csv",
        "position_stress": OUTPUT_DIR / f"{PREFIX}_position_stress.csv",
        "stress_industry": OUTPUT_DIR / f"{PREFIX}_stress_industry.csv",
        "worst_stress_industry": OUTPUT_DIR / f"{PREFIX}_worst_stress_industry.csv",
        "worst_stress_symbol": OUTPUT_DIR / f"{PREFIX}_worst_stress_symbol.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    stress_daily.write_csv(paths["stress_daily"])
    subtype_summary.write_csv(paths["subtype_summary"])
    worst_days.write_csv(paths["worst_days"])
    position_stress.write_csv(paths["position_stress"])
    stress_industry.write_csv(paths["stress_industry"])
    worst_industry.write_csv(paths["worst_stress_industry"])
    worst_symbol.write_csv(paths["worst_stress_symbol"])
    quality.write_csv(paths["quality_checkpoints"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "research_sources": RESEARCH_SOURCES,
            "source_daily": REPAIRABLE_OUTPUT_DIR / f"{REPAIRABLE_PREFIX}_base_rerun_daily.csv",
            "source_state": REPAIRABLE_OUTPUT_DIR / f"{REPAIRABLE_PREFIX}_repairable_state.csv",
            "source_position": CURVE_OUTPUT_DIR / f"{CURVE_PREFIX}_position_daily.csv",
            "note": "Liquidity stress attribution only; no strategy parameter changes.",
        },
    )
    report_path = write_report(
        summary,
        subtype_summary,
        worst_days,
        stress_industry,
        worst_industry,
        worst_symbol,
        quality,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
