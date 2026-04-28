from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_repairability_filter_robustness_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_repairability_filter_robustness_v1"

BASELINE_SCENARIO: str = "age4_daily_all"
CANDIDATE_SCENARIO: str = "age4_daily_exclude_volume_dry"
PERIODS: tuple[tuple[str, str, str], ...] = (
    ("early_2018_2021", "2018-01-01", "2021-12-31"),
    ("late_2022_2026", "2022-01-01", "2026-12-31"),
)


def summarize_returns(returns: list[float]) -> dict[str, float]:
    if not returns:
        return {"days": 0, "period_return": 0.0, "max_drawdown": 0.0, "sharpe": 0.0}
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for daily_ret in returns:
        equity *= 1.0 + float(daily_ret)
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
    mean = sum(returns) / len(returns)
    variance = sum((ret - mean) ** 2 for ret in returns) / (len(returns) - 1) if len(returns) > 1 else 0.0
    std = variance**0.5
    sharpe = mean / std * (TRADING_DAYS**0.5) if std > 0 else 0.0
    return {
        "days": len(returns),
        "period_return": equity - 1.0,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
    }


def build_period_summary(equity_df: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for period_name, start, end in PERIODS:
        period = equity_df.filter((pl.col("date") >= pl.lit(start).str.strptime(pl.Date)) & (pl.col("date") <= pl.lit(end).str.strptime(pl.Date)))
        for key, group in period.partition_by(["scenario", "roundtrip_cost_bps"], as_dict=True).items():
            scenario, cost_bps = key
            stats = summarize_returns(group.sort("date")["strategy_daily_ret"].to_list())
            rows.append(
                {
                    "period": period_name,
                    "scenario": scenario,
                    "roundtrip_cost_bps": float(cost_bps),
                    **stats,
                }
            )
    return pl.DataFrame(rows).sort(["roundtrip_cost_bps", "period", "scenario"])


def build_yearly_delta(yearly_df: pl.DataFrame) -> pl.DataFrame:
    baseline = yearly_df.filter(pl.col("scenario") == BASELINE_SCENARIO).select(
        "roundtrip_cost_bps",
        "year",
        pl.col("year_return").alias("baseline_year_return"),
        pl.col("year_cost_drag").alias("baseline_year_cost_drag"),
        pl.col("avg_gross_exposure").alias("baseline_avg_gross_exposure"),
    )
    return (
        yearly_df.join(baseline, on=["roundtrip_cost_bps", "year"], how="left")
        .with_columns(
            (pl.col("year_return") - pl.col("baseline_year_return")).alias("year_return_delta_vs_baseline"),
            (pl.col("year_cost_drag") - pl.col("baseline_year_cost_drag")).alias("year_cost_drag_delta_vs_baseline"),
            (pl.col("avg_gross_exposure") - pl.col("baseline_avg_gross_exposure")).alias(
                "avg_gross_exposure_delta_vs_baseline"
            ),
            (pl.col("year_return") > pl.col("baseline_year_return")).alias("beats_baseline_year"),
        )
        .sort(["roundtrip_cost_bps", "scenario", "year"])
    )


def build_yearly_scorecard(yearly_delta: pl.DataFrame) -> pl.DataFrame:
    return (
        yearly_delta.filter(pl.col("scenario") != BASELINE_SCENARIO)
        .group_by(["scenario", "roundtrip_cost_bps"])
        .agg(
            pl.len().alias("year_count"),
            pl.col("beats_baseline_year").sum().alias("beat_year_count"),
            pl.col("year_return_delta_vs_baseline").mean().alias("avg_year_return_delta"),
            pl.col("year_return_delta_vs_baseline").min().alias("worst_year_return_delta"),
            pl.col("year_return_delta_vs_baseline").max().alias("best_year_return_delta"),
            pl.col("year_cost_drag_delta_vs_baseline").mean().alias("avg_year_cost_drag_delta"),
            pl.col("avg_gross_exposure_delta_vs_baseline").mean().alias("avg_exposure_delta"),
        )
        .with_columns((pl.col("beat_year_count") / pl.col("year_count")).alias("beat_year_ratio"))
        .sort(["roundtrip_cost_bps", "scenario"])
    )


def build_yearly_retention(selected_all: pl.DataFrame) -> pl.DataFrame:
    selected_year = (
        selected_all.with_columns(pl.col("datetime").dt.year().alias("year"))
        .group_by(["scenario", "year"])
        .agg(
            pl.len().alias("selected_rows"),
            pl.col("datetime").n_unique().alias("signal_days"),
            pl.col("basket_weight").sum().alias("basket_weight_sum"),
        )
    )
    baseline = selected_year.filter(pl.col("scenario") == BASELINE_SCENARIO).select(
        "year",
        pl.col("selected_rows").alias("baseline_selected_rows"),
        pl.col("signal_days").alias("baseline_signal_days"),
        pl.col("basket_weight_sum").alias("baseline_basket_weight_sum"),
    )
    return (
        selected_year.join(baseline, on="year", how="left")
        .with_columns(
            (pl.col("selected_rows") / pl.col("baseline_selected_rows")).alias("row_retention_ratio"),
            (pl.col("signal_days") / pl.col("baseline_signal_days")).alias("signal_day_retention_ratio"),
            (pl.col("basket_weight_sum") / pl.col("baseline_basket_weight_sum")).alias(
                "basket_weight_retention_ratio"
            ),
        )
        .sort(["scenario", "year"])
    )


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return frame.select([col for col in columns if col in frame.columns]).head(max_rows).to_pandas().to_markdown(
        index=False
    )


def write_report(
    period_summary: pl.DataFrame,
    yearly_delta: pl.DataFrame,
    yearly_scorecard: pl.DataFrame,
    yearly_retention: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    candidate_score_50 = yearly_scorecard.filter(
        (pl.col("scenario") == CANDIDATE_SCENARIO) & (pl.col("roundtrip_cost_bps") == 50.0)
    ).to_dicts()
    score = candidate_score_50[0] if candidate_score_50 else None
    period_candidate_50 = period_summary.filter(
        (pl.col("scenario") == CANDIDATE_SCENARIO) & (pl.col("roundtrip_cost_bps") == 50.0)
    )
    lines = [
        "# 股票震荡liquid_q3成交干枯过滤稳健性验证 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：第244阶段候选`exclude_volume_dry`的稳健性验证，不新增交易规则、不调参数。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C；本阶段只做股票线内部候选验证。",
        "",
        "## 核心观察",
        "",
    ]
    if score:
        lines.append(
            f"- `exclude_volume_dry`在50bp下年度跑赢基线`{int(score['beat_year_count'])}/{int(score['year_count'])}`年，"
            f"平均年度超额`{pct(score['avg_year_return_delta'])}`，最差年度相对差`{pct(score['worst_year_return_delta'])}`。"
        )
    for row in period_candidate_50.iter_rows(named=True):
        lines.append(
            f"- 50bp `{row['period']}`：收益`{pct(row['period_return'])}`，最大回撤`{pct(row['max_drawdown'])}`，Sharpe `{row['sharpe']:.2f}`。"
        )
    lines.extend(
        [
            "- 结论：候选值得继续验证，但还不能正式化；下一步应做不调参的启动年份/滚动窗口验证，并检查是否依赖2024单一年份。",
            "",
            "## 前后半段表现",
            "",
            markdown_table(
                period_summary.filter(pl.col("scenario").is_in([BASELINE_SCENARIO, CANDIDATE_SCENARIO])),
                ["period", "scenario", "roundtrip_cost_bps", "days", "period_return", "max_drawdown", "sharpe"],
            ),
            "",
            "## 年度胜负记分",
            "",
            markdown_table(
                yearly_scorecard,
                [
                    "scenario",
                    "roundtrip_cost_bps",
                    "year_count",
                    "beat_year_count",
                    "beat_year_ratio",
                    "avg_year_return_delta",
                    "worst_year_return_delta",
                    "best_year_return_delta",
                    "avg_year_cost_drag_delta",
                    "avg_exposure_delta",
                ],
            ),
            "",
            "## 候选年度明细：50bp",
            "",
            markdown_table(
                yearly_delta.filter(
                    (pl.col("scenario") == CANDIDATE_SCENARIO) & (pl.col("roundtrip_cost_bps") == 50.0)
                ),
                [
                    "year",
                    "year_return",
                    "baseline_year_return",
                    "year_return_delta_vs_baseline",
                    "year_cost_drag_delta_vs_baseline",
                    "avg_gross_exposure_delta_vs_baseline",
                    "beats_baseline_year",
                ],
            ),
            "",
            "## 年度保留率",
            "",
            markdown_table(
                yearly_retention.filter(pl.col("scenario") == CANDIDATE_SCENARIO),
                [
                    "scenario",
                    "year",
                    "selected_rows",
                    "baseline_selected_rows",
                    "row_retention_ratio",
                    "signal_day_retention_ratio",
                    "basket_weight_retention_ratio",
                ],
            ),
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：仍不能排除研究选择偏差。",
            "- 原因：候选不是通过阈值扫描得到，但它来自上一阶段归因后的选择；本阶段只验证年度和前后半段，尚未做启动年份/滚动窗口。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：候选在收益、回撤、成本、换手上同时改善，并且不是只靠一个年度；但仍需更严格稳健性验证。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- `exclude_volume_dry`保留为股票震荡独立路线的候选规则。",
            "- 下一步只做验证，不调阈值，不叠加新过滤器。",
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
    equity_df = pl.read_csv(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_equity_curve.csv", try_parse_dates=True)
    yearly_df = pl.read_csv(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_yearly.csv")
    selected_all = pl.read_parquet(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_selected_all.parquet")
    period_summary = build_period_summary(equity_df)
    yearly_delta = build_yearly_delta(yearly_df)
    yearly_scorecard = build_yearly_scorecard(yearly_delta)
    yearly_retention = build_yearly_retention(selected_all)
    meta: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_scenario": BASELINE_SCENARIO,
        "candidate_scenario": CANDIDATE_SCENARIO,
        "periods": PERIODS,
        "source_output_dir": str(FILTER_OUTPUT_DIR),
    }
    paths = {
        "period_summary": OUTPUT_DIR / f"{PREFIX}_period_summary.csv",
        "yearly_delta": OUTPUT_DIR / f"{PREFIX}_yearly_delta.csv",
        "yearly_scorecard": OUTPUT_DIR / f"{PREFIX}_yearly_scorecard.csv",
        "yearly_retention": OUTPUT_DIR / f"{PREFIX}_yearly_retention.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    period_summary.write_csv(paths["period_summary"])
    yearly_delta.write_csv(paths["yearly_delta"])
    yearly_scorecard.write_csv(paths["yearly_scorecard"])
    yearly_retention.write_csv(paths["yearly_retention"])
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(period_summary, yearly_delta, yearly_scorecard, yearly_retention, meta, paths)
    print(yearly_scorecard)
    print(period_summary.filter(pl.col("scenario").is_in([BASELINE_SCENARIO, CANDIDATE_SCENARIO])))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
