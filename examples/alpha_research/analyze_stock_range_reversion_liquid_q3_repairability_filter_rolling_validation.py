from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_repairability_filter_rolling_validation_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_repairability_filter_rolling_validation_v1"

BASELINE_SCENARIO: str = "age4_daily_all"
CANDIDATE_SCENARIO: str = "age4_daily_exclude_volume_dry"
START_YEARS: tuple[int, ...] = tuple(range(2018, 2027))
ROLLING_WINDOWS: tuple[int, ...] = (126, 252, 504)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "ScienceDirect 2022 JBF short-term reversals",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "Quantpedia short-term reversal summary",
        "https://quantpedia.com/strategies/short-term-reversal-in-stocks/",
    ),
    (
        "Teddy Koker cross-sectional mean reversion example",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "GitHub walk-forward validation topic/examples",
        "https://github.com/topics/walk-forward-validation",
    ),
)


def summarize_curve_frame(frame: pl.DataFrame) -> dict[str, float | int | str]:
    ordered = frame.sort("date")
    returns = [float(value) for value in ordered["strategy_daily_ret"].to_list()]
    if not returns:
        return {
            "days": 0,
            "start_date": "",
            "end_date": "",
            "final_equity": 1.0,
            "period_return": 0.0,
            "annualized_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "cost_drag_sum": 0.0,
            "one_way_turnover_sum": 0.0,
            "annualized_one_way_turnover": 0.0,
            "avg_gross_exposure": 0.0,
            "active_day_ratio": 0.0,
        }

    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for daily_ret in returns:
        equity *= 1.0 + daily_ret
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)

    mean = sum(returns) / len(returns)
    variance = sum((ret - mean) ** 2 for ret in returns) / (len(returns) - 1) if len(returns) > 1 else 0.0
    std = variance**0.5
    sharpe = mean / std * (TRADING_DAYS**0.5) if std > 0 else 0.0
    annualized_return = equity ** (TRADING_DAYS / len(returns)) - 1.0 if equity > 0 else -1.0
    one_way_turnover_sum = float(ordered["one_way_turnover"].sum())

    return {
        "days": len(returns),
        "start_date": str(ordered["date"].min()),
        "end_date": str(ordered["date"].max()),
        "final_equity": equity,
        "period_return": equity - 1.0,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "cost_drag_sum": -float(ordered["turnover_cost_ret"].sum()),
        "one_way_turnover_sum": one_way_turnover_sum,
        "annualized_one_way_turnover": one_way_turnover_sum / len(returns) * TRADING_DAYS,
        "avg_gross_exposure": float(ordered["target_gross_exposure"].mean() or 0.0),
        "active_day_ratio": float((ordered["target_gross_exposure"] > 0).mean() or 0.0),
    }


def build_start_year_summary(equity_df: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in equity_df.partition_by(["scenario", "roundtrip_cost_bps"], as_dict=True).items():
        scenario, cost_bps = key
        for start_year in START_YEARS:
            start_date = date(start_year, 1, 1)
            frame = group.filter(pl.col("date") >= start_date)
            if frame.is_empty():
                continue
            rows.append(
                {
                    "scenario": scenario,
                    "roundtrip_cost_bps": float(cost_bps),
                    "start_year": start_year,
                    "period": f"since_{start_year}",
                    **summarize_curve_frame(frame),
                }
            )
    return pl.DataFrame(rows).sort(["roundtrip_cost_bps", "start_year", "scenario"])


def build_start_year_delta(start_year_summary: pl.DataFrame) -> pl.DataFrame:
    baseline = start_year_summary.filter(pl.col("scenario") == BASELINE_SCENARIO).select(
        "roundtrip_cost_bps",
        "start_year",
        pl.col("period_return").alias("baseline_period_return"),
        pl.col("annualized_return").alias("baseline_annualized_return"),
        pl.col("max_drawdown").alias("baseline_max_drawdown"),
        pl.col("sharpe").alias("baseline_sharpe"),
        pl.col("cost_drag_sum").alias("baseline_cost_drag_sum"),
        pl.col("annualized_one_way_turnover").alias("baseline_annualized_one_way_turnover"),
    )
    return (
        start_year_summary.join(baseline, on=["roundtrip_cost_bps", "start_year"], how="left")
        .with_columns(
            (pl.col("period_return") - pl.col("baseline_period_return")).alias("period_return_delta_vs_baseline"),
            (pl.col("annualized_return") - pl.col("baseline_annualized_return")).alias(
                "annualized_return_delta_vs_baseline"
            ),
            (pl.col("max_drawdown") - pl.col("baseline_max_drawdown")).alias("max_drawdown_improvement_vs_baseline"),
            (pl.col("sharpe") - pl.col("baseline_sharpe")).alias("sharpe_delta_vs_baseline"),
            (pl.col("cost_drag_sum") - pl.col("baseline_cost_drag_sum")).alias("cost_drag_delta_vs_baseline"),
            (pl.col("annualized_one_way_turnover") - pl.col("baseline_annualized_one_way_turnover")).alias(
                "annualized_turnover_delta_vs_baseline"
            ),
            (pl.col("period_return") > pl.col("baseline_period_return")).alias("beats_baseline_return"),
            (pl.col("max_drawdown") > pl.col("baseline_max_drawdown")).alias("beats_baseline_drawdown"),
            (pl.col("sharpe") > pl.col("baseline_sharpe")).alias("beats_baseline_sharpe"),
            ((pl.col("period_return") > pl.col("baseline_period_return")) & (pl.col("max_drawdown") > pl.col("baseline_max_drawdown"))).alias(
                "beats_baseline_return_and_drawdown"
            ),
        )
        .sort(["roundtrip_cost_bps", "start_year", "scenario"])
    )


def build_start_year_scorecard(start_year_delta: pl.DataFrame) -> pl.DataFrame:
    return (
        start_year_delta.filter(pl.col("scenario") != BASELINE_SCENARIO)
        .group_by(["scenario", "roundtrip_cost_bps"])
        .agg(
            pl.len().alias("start_count"),
            pl.col("beats_baseline_return").sum().alias("return_beat_count"),
            pl.col("beats_baseline_drawdown").sum().alias("drawdown_beat_count"),
            pl.col("beats_baseline_sharpe").sum().alias("sharpe_beat_count"),
            pl.col("beats_baseline_return_and_drawdown").sum().alias("return_and_drawdown_beat_count"),
            pl.col("period_return_delta_vs_baseline").mean().alias("avg_period_return_delta"),
            pl.col("period_return_delta_vs_baseline").min().alias("worst_period_return_delta"),
            pl.col("period_return_delta_vs_baseline").max().alias("best_period_return_delta"),
            pl.col("max_drawdown_improvement_vs_baseline").mean().alias("avg_max_drawdown_improvement"),
            pl.col("max_drawdown_improvement_vs_baseline").min().alias("worst_max_drawdown_improvement"),
            pl.col("sharpe_delta_vs_baseline").mean().alias("avg_sharpe_delta"),
            pl.col("sharpe_delta_vs_baseline").min().alias("worst_sharpe_delta"),
            pl.col("annualized_turnover_delta_vs_baseline").mean().alias("avg_annualized_turnover_delta"),
        )
        .with_columns(
            (pl.col("return_beat_count") / pl.col("start_count")).alias("return_beat_ratio"),
            (pl.col("drawdown_beat_count") / pl.col("start_count")).alias("drawdown_beat_ratio"),
            (pl.col("sharpe_beat_count") / pl.col("start_count")).alias("sharpe_beat_ratio"),
            (pl.col("return_and_drawdown_beat_count") / pl.col("start_count")).alias(
                "return_and_drawdown_beat_ratio"
            ),
        )
        .sort(["roundtrip_cost_bps", "scenario"])
    )


def build_rolling_summary(equity_df: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in equity_df.partition_by(["scenario", "roundtrip_cost_bps"], as_dict=True).items():
        scenario, cost_bps = key
        ordered = group.sort("date")
        for window in ROLLING_WINDOWS:
            if ordered.height < window:
                continue
            for end_idx in range(window - 1, ordered.height):
                frame = ordered.slice(end_idx - window + 1, window)
                stats = summarize_curve_frame(frame)
                rows.append(
                    {
                        "scenario": scenario,
                        "roundtrip_cost_bps": float(cost_bps),
                        "window_days": window,
                        "window_start": stats["start_date"],
                        "window_end": stats["end_date"],
                        **stats,
                    }
                )
    return pl.DataFrame(rows).sort(["roundtrip_cost_bps", "window_days", "window_end", "scenario"])


def build_rolling_delta(rolling_summary: pl.DataFrame) -> pl.DataFrame:
    baseline = rolling_summary.filter(pl.col("scenario") == BASELINE_SCENARIO).select(
        "roundtrip_cost_bps",
        "window_days",
        "window_start",
        "window_end",
        pl.col("period_return").alias("baseline_period_return"),
        pl.col("annualized_return").alias("baseline_annualized_return"),
        pl.col("max_drawdown").alias("baseline_max_drawdown"),
        pl.col("sharpe").alias("baseline_sharpe"),
        pl.col("cost_drag_sum").alias("baseline_cost_drag_sum"),
        pl.col("annualized_one_way_turnover").alias("baseline_annualized_one_way_turnover"),
    )
    return (
        rolling_summary.join(
            baseline,
            on=["roundtrip_cost_bps", "window_days", "window_start", "window_end"],
            how="left",
        )
        .with_columns(
            (pl.col("period_return") - pl.col("baseline_period_return")).alias("period_return_delta_vs_baseline"),
            (pl.col("annualized_return") - pl.col("baseline_annualized_return")).alias(
                "annualized_return_delta_vs_baseline"
            ),
            (pl.col("max_drawdown") - pl.col("baseline_max_drawdown")).alias("max_drawdown_improvement_vs_baseline"),
            (pl.col("sharpe") - pl.col("baseline_sharpe")).alias("sharpe_delta_vs_baseline"),
            (pl.col("cost_drag_sum") - pl.col("baseline_cost_drag_sum")).alias("cost_drag_delta_vs_baseline"),
            (pl.col("annualized_one_way_turnover") - pl.col("baseline_annualized_one_way_turnover")).alias(
                "annualized_turnover_delta_vs_baseline"
            ),
            (pl.col("period_return") > pl.col("baseline_period_return")).alias("beats_baseline_return"),
            (pl.col("max_drawdown") > pl.col("baseline_max_drawdown")).alias("beats_baseline_drawdown"),
            (pl.col("sharpe") > pl.col("baseline_sharpe")).alias("beats_baseline_sharpe"),
            ((pl.col("period_return") > pl.col("baseline_period_return")) & (pl.col("max_drawdown") > pl.col("baseline_max_drawdown"))).alias(
                "beats_baseline_return_and_drawdown"
            ),
        )
        .sort(["roundtrip_cost_bps", "window_days", "window_end", "scenario"])
    )


def build_rolling_scorecard(rolling_delta: pl.DataFrame) -> pl.DataFrame:
    return (
        rolling_delta.filter(pl.col("scenario") != BASELINE_SCENARIO)
        .group_by(["scenario", "roundtrip_cost_bps", "window_days"])
        .agg(
            pl.len().alias("window_count"),
            pl.col("beats_baseline_return").sum().alias("return_beat_count"),
            pl.col("beats_baseline_drawdown").sum().alias("drawdown_beat_count"),
            pl.col("beats_baseline_sharpe").sum().alias("sharpe_beat_count"),
            pl.col("beats_baseline_return_and_drawdown").sum().alias("return_and_drawdown_beat_count"),
            pl.col("period_return_delta_vs_baseline").mean().alias("avg_period_return_delta"),
            pl.col("period_return_delta_vs_baseline").median().alias("median_period_return_delta"),
            pl.col("period_return_delta_vs_baseline").min().alias("worst_period_return_delta"),
            pl.col("period_return_delta_vs_baseline").max().alias("best_period_return_delta"),
            pl.col("max_drawdown_improvement_vs_baseline").mean().alias("avg_max_drawdown_improvement"),
            pl.col("max_drawdown_improvement_vs_baseline").median().alias("median_max_drawdown_improvement"),
            pl.col("max_drawdown_improvement_vs_baseline").min().alias("worst_max_drawdown_improvement"),
            pl.col("sharpe_delta_vs_baseline").mean().alias("avg_sharpe_delta"),
            pl.col("sharpe_delta_vs_baseline").median().alias("median_sharpe_delta"),
            pl.col("sharpe_delta_vs_baseline").min().alias("worst_sharpe_delta"),
            pl.col("annualized_turnover_delta_vs_baseline").mean().alias("avg_annualized_turnover_delta"),
        )
        .with_columns(
            (pl.col("return_beat_count") / pl.col("window_count")).alias("return_beat_ratio"),
            (pl.col("drawdown_beat_count") / pl.col("window_count")).alias("drawdown_beat_ratio"),
            (pl.col("sharpe_beat_count") / pl.col("window_count")).alias("sharpe_beat_ratio"),
            (pl.col("return_and_drawdown_beat_count") / pl.col("window_count")).alias(
                "return_and_drawdown_beat_ratio"
            ),
        )
        .sort(["roundtrip_cost_bps", "window_days", "scenario"])
    )


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 120) -> str:
    if frame.is_empty():
        return "无数据"
    return frame.select([col for col in columns if col in frame.columns]).head(max_rows).to_pandas().to_markdown(
        index=False
    )


def format_score_row(row: dict[str, Any], label: str) -> str:
    return (
        f"- {label}：样本`{int(row['window_count'])}`个，收益跑赢率`{pct(row['return_beat_ratio'])}`，"
        f"回撤改善率`{pct(row['drawdown_beat_ratio'])}`，Sharpe跑赢率`{pct(row['sharpe_beat_ratio'])}`，"
        f"平均收益差`{pct(row['avg_period_return_delta'])}`，最差收益差`{pct(row['worst_period_return_delta'])}`。"
    )


def write_report(
    start_year_delta: pl.DataFrame,
    start_year_scorecard: pl.DataFrame,
    rolling_scorecard: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    candidate_start_50 = start_year_scorecard.filter(
        (pl.col("scenario") == CANDIDATE_SCENARIO) & (pl.col("roundtrip_cost_bps") == 50.0)
    ).to_dicts()
    start_score = candidate_start_50[0] if candidate_start_50 else None
    candidate_rolling_50 = rolling_scorecard.filter(
        (pl.col("scenario") == CANDIDATE_SCENARIO) & (pl.col("roundtrip_cost_bps") == 50.0)
    ).sort("window_days")
    rolling_rows = candidate_rolling_50.to_dicts()

    lines = [
        "# 股票震荡liquid_q3成交干枯过滤启动年份/滚动窗口验证 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：第244阶段候选`exclude_volume_dry`的启动年份与滚动窗口验证，不新增交易规则、不调参数。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C；本阶段只做股票线内部验证。",
        "",
        "## 外部调研判断",
        "",
        "- 短周期股票反转更像流动性供给/即时性成本补偿，而不是固定形态指标本身的魔法。",
        "- 成交成本、股票池流动性和滚动窗口稳定性是业界资料反复强调的风险点；GitHub上可直接参考的多数是教学型或参数优化框架，不能直接复制成A股实盘系统。",
        "- 因此本阶段采用固定候选规则的启动年份/滚动窗口验证，而不是继续加指标。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")

    lines.extend(["", "## 核心观察", ""])
    if start_score:
        lines.append(
            f"- 50bp启动年份验证：`exclude_volume_dry`收益跑赢基线`{int(start_score['return_beat_count'])}/{int(start_score['start_count'])}`，"
            f"回撤改善`{int(start_score['drawdown_beat_count'])}/{int(start_score['start_count'])}`，"
            f"Sharpe跑赢`{int(start_score['sharpe_beat_count'])}/{int(start_score['start_count'])}`；"
            f"平均收益差`{pct(start_score['avg_period_return_delta'])}`，最差收益差`{pct(start_score['worst_period_return_delta'])}`。"
        )
    for row in rolling_rows:
        lines.append(format_score_row(row, f"50bp滚动{int(row['window_days'])}日"))
    lines.extend(
        [
            "- 注意：回撤改善有一部分来自过滤后暴露和换手下降，不能单独当作胜利；更关键的是252/504日窗口里收益、Sharpe和回撤方向同时改善。",
            "- 直觉判断：这条过滤不像单一年份偶然修饰，它更像是在把“无承接的继续下跌”从超跌篮子里剥离；但它仍然是归因后选择出来的候选，不能把验证胜率误读成完全样本外。",
            "",
            "## 启动年份记分",
            "",
            markdown_table(
                start_year_scorecard,
                [
                    "scenario",
                    "roundtrip_cost_bps",
                    "start_count",
                    "return_beat_count",
                    "drawdown_beat_count",
                    "sharpe_beat_count",
                    "return_and_drawdown_beat_count",
                    "return_beat_ratio",
                    "drawdown_beat_ratio",
                    "sharpe_beat_ratio",
                    "avg_period_return_delta",
                    "worst_period_return_delta",
                    "avg_max_drawdown_improvement",
                    "worst_max_drawdown_improvement",
                    "avg_sharpe_delta",
                    "worst_sharpe_delta",
                    "avg_annualized_turnover_delta",
                ],
            ),
            "",
            "## 候选启动年份明细：50bp",
            "",
            markdown_table(
                start_year_delta.filter(
                    (pl.col("scenario") == CANDIDATE_SCENARIO) & (pl.col("roundtrip_cost_bps") == 50.0)
                ),
                [
                    "period",
                    "days",
                    "period_return",
                    "baseline_period_return",
                    "period_return_delta_vs_baseline",
                    "max_drawdown",
                    "baseline_max_drawdown",
                    "max_drawdown_improvement_vs_baseline",
                    "sharpe",
                    "baseline_sharpe",
                    "sharpe_delta_vs_baseline",
                    "annualized_turnover_delta_vs_baseline",
                ],
            ),
            "",
            "## 滚动窗口记分",
            "",
            markdown_table(
                rolling_scorecard,
                [
                    "scenario",
                    "roundtrip_cost_bps",
                    "window_days",
                    "window_count",
                    "return_beat_count",
                    "drawdown_beat_count",
                    "sharpe_beat_count",
                    "return_and_drawdown_beat_count",
                    "return_beat_ratio",
                    "drawdown_beat_ratio",
                    "sharpe_beat_ratio",
                    "avg_period_return_delta",
                    "median_period_return_delta",
                    "worst_period_return_delta",
                    "avg_max_drawdown_improvement",
                    "median_max_drawdown_improvement",
                    "worst_max_drawdown_improvement",
                    "avg_sharpe_delta",
                    "median_sharpe_delta",
                    "worst_sharpe_delta",
                    "avg_annualized_turnover_delta",
                ],
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只复核第244阶段已经固定的`exclude_volume_dry`候选，不新增阈值、不换股票池、不挑行业、不改变成本口径。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：仍不能完全排除。",
            "- 原因：启动年份和滚动窗口胜率可以降低“只靠一个年份”的嫌疑，但候选来自第243阶段归因后的研究选择，还不是严格预注册样本外。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第245阶段已经说明年度/前后半段有改善，下一步关键不是调参，而是看不同启动点和滚动窗口下是否稳定。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：候选在启动年份、长滚动窗口和换手成本上继续显示稳定优势，值得进入更贴近实盘的压力测试；但还不到正式化。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- `exclude_volume_dry`保留为股票震荡独立路线的主候选过滤。",
            "- 下一步应做成本压力和容量/成交额约束复核，重点看50bp以上、成交额分层、单日换手尖峰，而不是叠加更多信号。",
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
    start_year_summary = build_start_year_summary(equity_df)
    start_year_delta = build_start_year_delta(start_year_summary)
    start_year_scorecard = build_start_year_scorecard(start_year_delta)
    rolling_summary = build_rolling_summary(equity_df)
    rolling_delta = build_rolling_delta(rolling_summary)
    rolling_scorecard = build_rolling_scorecard(rolling_delta)

    meta: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_scenario": BASELINE_SCENARIO,
        "candidate_scenario": CANDIDATE_SCENARIO,
        "start_years": START_YEARS,
        "rolling_windows": ROLLING_WINDOWS,
        "source_output_dir": str(FILTER_OUTPUT_DIR),
        "research_sources": RESEARCH_SOURCES,
    }
    paths = {
        "start_year_summary": OUTPUT_DIR / f"{PREFIX}_start_year_summary.csv",
        "start_year_delta": OUTPUT_DIR / f"{PREFIX}_start_year_delta.csv",
        "start_year_scorecard": OUTPUT_DIR / f"{PREFIX}_start_year_scorecard.csv",
        "rolling_summary": OUTPUT_DIR / f"{PREFIX}_rolling_summary.csv",
        "rolling_delta": OUTPUT_DIR / f"{PREFIX}_rolling_delta.csv",
        "rolling_scorecard": OUTPUT_DIR / f"{PREFIX}_rolling_scorecard.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    start_year_summary.write_csv(paths["start_year_summary"])
    start_year_delta.write_csv(paths["start_year_delta"])
    start_year_scorecard.write_csv(paths["start_year_scorecard"])
    rolling_summary.write_csv(paths["rolling_summary"])
    rolling_delta.write_csv(paths["rolling_delta"])
    rolling_scorecard.write_csv(paths["rolling_scorecard"])
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(start_year_delta, start_year_scorecard, rolling_scorecard, meta, paths)
    print(start_year_scorecard)
    print(rolling_scorecard)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
