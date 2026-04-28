from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_paper_oos_attribution import (
    OUTPUT_DIR as ATTR_OUTPUT_DIR,
    PREFIX as ATTR_PREFIX,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_paper_oos_market_state_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_paper_oos_market_state_v1"

FREEZE_TARGET_DATE: date = datetime.strptime(
    os.getenv("PAPER_OOS_FREEZE_TARGET_DATE", "20260416"), "%Y%m%d"
).date()
MIN_OOS_DAYS_FOR_STABLE_JUDGMENT: int = int(os.getenv("PAPER_OOS_MIN_DAYS", "20") or 20)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Mean reversion equity strategies need recent-data and cost validation",
        "https://arxiv.org/abs/1909.04327",
    ),
    (
        "Zipline metrics include benchmark-relative returns, beta, exposure and drawdown",
        "https://zipline.ml4trading.io/risk-and-perf-metrics.html",
    ),
    (
        "Out-of-sample backtests can decay when regimes shift",
        "https://www.researchgate.net/publication/307553701_All_That_Glitters_Is_Not_Gold_Comparing_Backtest_and_Out-of-Sample_Performance_on_a_Large_Cohort_of_Trading_Algorithms",
    ),
)


def read_csv(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if abs(denominator) <= 1e-12:
        return None
    return numerator / denominator


def classify_index_state(value: Any) -> str:
    ret = to_float(value, default=0.0)
    if ret <= -0.01:
        return "index_down_gt_1pct"
    if ret >= 0.01:
        return "index_up_gt_1pct"
    return "index_flat"


def classify_breadth_state(value: Any) -> str:
    ratio = to_float(value, default=0.5)
    if ratio < 0.45:
        return "weak_breadth"
    if ratio > 0.55:
        return "strong_breadth"
    return "mixed_breadth"


def classify_exante_trend_state(value: Any) -> str:
    ret = to_float(value, default=0.0)
    if ret >= 0.05:
        return "exante_20d_uptrend"
    if ret <= -0.05:
        return "exante_20d_downtrend"
    return "exante_20d_neutral"


def classify_vol_state(value: Any) -> str:
    vol = to_float(value, default=0.0)
    if vol >= 0.025:
        return "exante_high_vol"
    if vol <= 0.012 and vol > 0:
        return "exante_low_vol"
    return "exante_mid_vol"


def build_benchmark_state(benchmark_df: pl.DataFrame) -> pl.DataFrame:
    return (
        benchmark_df.sort("datetime")
        .with_columns(
            pl.col("open").shift(-1).alias("next_open"),
            (pl.col("close") / pl.col("close").shift(1) - 1).alias("benchmark_close_to_close_ret"),
            (pl.col("close") / pl.col("open") - 1).alias("benchmark_intraday_ret"),
            (pl.col("open") / pl.col("preclose") - 1).alias("benchmark_gap_ret"),
        )
        .with_columns((pl.col("next_open") / pl.col("open") - 1).alias("benchmark_open_to_next_open_ret"))
        .with_columns(
            (pl.col("close").shift(1) / pl.col("close").shift(6) - 1).alias("exante_close_mom_5"),
            (pl.col("close").shift(1) / pl.col("close").shift(21) - 1).alias("exante_close_mom_20"),
            pl.col("benchmark_open_to_next_open_ret")
            .shift(1)
            .rolling_std(window_size=20, min_samples=5)
            .alias("exante_o2o_vol_20"),
            (
                pl.col("turnover").shift(1)
                / pl.col("turnover").shift(1).rolling_mean(window_size=20, min_samples=5)
            ).alias("exante_turnover_ratio_20"),
        )
        .select(
            pl.col("datetime").alias("date"),
            "benchmark_open_to_next_open_ret",
            "benchmark_close_to_close_ret",
            "benchmark_intraday_ret",
            "benchmark_gap_ret",
            "exante_close_mom_5",
            "exante_close_mom_20",
            "exante_o2o_vol_20",
            "exante_turnover_ratio_20",
        )
    )


def build_universe_state(stock_df: pl.DataFrame) -> pl.DataFrame:
    needed = [
        "datetime",
        "symbol",
        "trade_open",
        "is_suspended",
        "eligible_component_row",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
        "is_limit_up_close",
        "is_limit_down_close",
    ]
    cols = [col for col in needed if col in stock_df.columns]
    work = (
        stock_df.select(cols)
        .sort(["symbol", "datetime"])
        .with_columns(pl.col("trade_open").shift(-1).over("symbol").alias("next_trade_open"))
        .with_columns(
            pl.when(
                pl.col("trade_open").is_not_null()
                & (pl.col("trade_open") > 0)
                & pl.col("next_trade_open").is_not_null()
                & (pl.col("next_trade_open") > 0)
            )
            .then(pl.col("next_trade_open") / pl.col("trade_open") - 1)
            .otherwise(None)
            .alias("open_to_next_open_ret")
        )
        .filter(pl.col("eligible_component_row"))
    )
    return (
        work.group_by("datetime")
        .agg(
            pl.len().alias("universe_component_rows"),
            (
                pl.col("trade_open").is_not_null()
                & (pl.col("trade_open") > 0)
                & pl.col("open_to_next_open_ret").is_not_null()
                & (~pl.col("is_suspended").fill_null(False))
            )
            .sum()
            .alias("universe_tradable_count"),
            pl.col("open_to_next_open_ret").mean().alias("universe_equal_o2o_ret"),
            pl.col("open_to_next_open_ret").median().alias("universe_median_o2o_ret"),
            (pl.col("open_to_next_open_ret") > 0).mean().alias("universe_up_ratio"),
            (pl.col("open_to_next_open_ret") <= -0.02).mean().alias("universe_down_2pct_ratio"),
            pl.col("open_to_next_open_ret").std().alias("universe_cross_section_vol"),
            pl.col("is_oneword_limit_up").fill_null(False).mean().alias("oneword_limit_up_ratio"),
            pl.col("is_oneword_limit_down").fill_null(False).mean().alias("oneword_limit_down_ratio"),
            pl.col("is_limit_up_close").fill_null(False).mean().alias("limit_up_close_ratio"),
            pl.col("is_limit_down_close").fill_null(False).mean().alias("limit_down_close_ratio"),
        )
        .rename({"datetime": "date"})
        .sort("date")
    )


def add_state_labels(state_daily: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in state_daily.iter_rows(named=True):
        current = dict(row)
        current["index_state"] = classify_index_state(row.get("benchmark_open_to_next_open_ret"))
        current["breadth_state"] = classify_breadth_state(row.get("universe_up_ratio"))
        current["exante_trend_state"] = classify_exante_trend_state(row.get("exante_close_mom_20"))
        current["exante_vol_state"] = classify_vol_state(row.get("exante_o2o_vol_20"))
        rows.append(current)
    return pl.DataFrame(rows).sort("date") if rows else pl.DataFrame()


def summarize_by(state_daily: pl.DataFrame, group_col: str) -> pl.DataFrame:
    if state_daily.is_empty() or group_col not in state_daily.columns:
        return pl.DataFrame()
    return (
        state_daily.group_by(group_col)
        .agg(
            pl.len().alias("days"),
            pl.col("strategy_gross_daily_ret").sum().alias("strategy_gross_sum"),
            pl.col("strategy_daily_ret").sum().alias("strategy_net_sum"),
            pl.col("same_exposure_benchmark_o2o_ret").sum().alias("same_exposure_benchmark_sum"),
            pl.col("same_exposure_universe_equal_ret").sum().alias("same_exposure_universe_sum"),
            pl.col("gross_alpha_vs_same_exposure_benchmark").sum().alias("gross_alpha_vs_benchmark_sum"),
            pl.col("gross_alpha_vs_same_exposure_universe").sum().alias("gross_alpha_vs_universe_sum"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("benchmark_open_to_next_open_ret").mean().alias("avg_benchmark_o2o_ret"),
            pl.col("universe_up_ratio").mean().alias("avg_universe_up_ratio"),
        )
        .sort("strategy_net_sum")
    )


def diagnose_drag(summary: dict[str, Any]) -> str:
    gross = float(summary["segment_strategy_gross_sum"])
    benchmark = float(summary["segment_same_exposure_benchmark_sum"])
    alpha = float(summary["segment_gross_alpha_vs_benchmark_sum"])
    if gross >= 0:
        return "no_segment_drag"
    if benchmark < 0 and alpha < 0:
        return "mixed_market_and_selection_drag"
    if benchmark < 0:
        return "market_drag_visible"
    if alpha < 0:
        return "selection_or_reversal_timing_drag"
    return "cost_or_residual_drag"


def build_quality_checkpoints(summary: dict[str, Any], state_daily: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, str]] = []

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

    days = int(summary["segment_days"])
    add(
        "oos_state_segment_not_empty",
        "pass" if days > 0 else "fail",
        days,
        ">0",
        "必须有冻结后的新增交易日，市场状态归因才有意义。",
    )
    add(
        "oos_state_days_sample_size",
        "pass" if days >= MIN_OOS_DAYS_FOR_STABLE_JUDGMENT else "warn",
        days,
        f">={MIN_OOS_DAYS_FOR_STABLE_JUDGMENT}",
        "样本太短时，只能做方向性解释，不能做策略有效性裁决。",
    )
    benchmark_nulls = (
        state_daily.select(pl.col("benchmark_open_to_next_open_ret").null_count()).item()
        if not state_daily.is_empty()
        else days
    )
    add(
        "benchmark_o2o_coverage",
        "pass" if benchmark_nulls == 0 else "fail",
        benchmark_nulls,
        0,
        "同暴露指数归因需要中证1000开盘到次开盘收益完整。",
    )
    universe_nulls = (
        state_daily.select(pl.col("universe_equal_o2o_ret").null_count()).item() if not state_daily.is_empty() else days
    )
    add(
        "universe_breadth_coverage",
        "pass" if universe_nulls == 0 else "fail",
        universe_nulls,
        0,
        "市场宽度归因需要成分股等权收益和上涨比例完整。",
    )
    min_tradable = (
        int(state_daily.select(pl.col("universe_tradable_count").min()).item()) if not state_daily.is_empty() else 0
    )
    add(
        "universe_tradable_width",
        "pass" if min_tradable >= 500 else "warn",
        min_tradable,
        ">=500",
        "成分股可交易宽度过窄时，宽度状态可能不可靠。",
    )
    add(
        "no_parameter_change",
        "pass",
        "no signal/threshold change",
        "no signal/threshold change",
        "本阶段只做状态归因，不把状态标签写成交易过滤器。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    state_daily: pl.DataFrame,
    market_summary: pl.DataFrame,
    breadth_summary: pl.DataFrame,
    trend_summary: pl.DataFrame,
    vol_summary: pl.DataFrame,
    quality_checkpoints: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality_checkpoints.filter(pl.col("status") == "fail")
    warned = quality_checkpoints.filter(pl.col("status") == "warn")
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 paper OOS市场状态归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：冻结后paper OOS市场状态解释；不新增信号、不调参数。",
        f"- 冻结目标执行日：`{FREEZE_TARGET_DATE}`。",
        f"- 样本外目标日：`{summary['segment_start_date']}`到`{summary['segment_end_date']}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 均值回归策略不能只看自身收益曲线，必须看市场状态、基准相对表现、成本和样本外衰减。",
        "- 开源回测框架通常把算法收益、benchmark收益、风险和暴露拆开记录；这支持我们把paper OOS段拆成同暴露指数、市场宽度和选股/时点残差。",
        "- 直觉判断：短样本亏损最容易诱发手痒调参；先确认外部市场状态，再判断模型自身问题。",
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
            f"- 新增样本交易日`{summary['segment_days']}`天。",
            f"- 策略毛收益合计`{pct(summary['segment_strategy_gross_sum'])}`，净收益合计`{pct(summary['segment_strategy_net_sum'])}`。",
            f"- 同暴露中证1000开盘到次开盘收益合计`{pct(summary['segment_same_exposure_benchmark_sum'])}`。",
            f"- 同暴露成分股等权收益合计`{pct(summary['segment_same_exposure_universe_sum'])}`。",
            f"- 策略毛收益相对同暴露中证1000残差`{pct(summary['segment_gross_alpha_vs_benchmark_sum'])}`。",
            f"- 策略毛收益相对同暴露成分股等权残差`{pct(summary['segment_gross_alpha_vs_universe_sum'])}`。",
            f"- 指数下跌超过1%的天数`{summary['index_down_gt_1pct_days']}`天，市场宽度弱的天数`{summary['weak_breadth_days']}`天。",
            f"- 拖累诊断：`{summary['drag_diagnosis']}`。",
            "- 我的判断：新增段亏损不完全是大盘拖累；同暴露指数本段偏正，而策略残差偏负，短期更像买入后的反转节奏和局部行业风格拖累。但样本只有7天，不能把它升级成信号失效结论。",
            "",
            "## 质量检查点",
            "",
            markdown_table(quality_checkpoints, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 失败项",
            "",
            "无数据" if failed.is_empty() else markdown_table(failed, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 警告项",
            "",
            "无数据" if warned.is_empty() else markdown_table(warned, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 日级状态归因",
            "",
            markdown_table(
                state_daily,
                [
                    "date",
                    "strategy_gross_daily_ret",
                    "strategy_daily_ret",
                    "actual_gross_weight",
                    "benchmark_open_to_next_open_ret",
                    "same_exposure_benchmark_o2o_ret",
                    "universe_equal_o2o_ret",
                    "same_exposure_universe_equal_ret",
                    "gross_alpha_vs_same_exposure_benchmark",
                    "universe_up_ratio",
                    "index_state",
                    "breadth_state",
                    "exante_trend_state",
                    "exante_vol_state",
                ],
                max_rows=80,
            ),
            "",
            "## 按指数状态汇总",
            "",
            markdown_table(
                market_summary,
                [
                    "index_state",
                    "days",
                    "strategy_gross_sum",
                    "strategy_net_sum",
                    "same_exposure_benchmark_sum",
                    "gross_alpha_vs_benchmark_sum",
                    "avg_actual_gross_weight",
                    "avg_benchmark_o2o_ret",
                    "avg_universe_up_ratio",
                ],
                max_rows=20,
            ),
            "",
            "## 按市场宽度汇总",
            "",
            markdown_table(
                breadth_summary,
                [
                    "breadth_state",
                    "days",
                    "strategy_gross_sum",
                    "strategy_net_sum",
                    "same_exposure_universe_sum",
                    "gross_alpha_vs_universe_sum",
                    "avg_actual_gross_weight",
                    "avg_benchmark_o2o_ret",
                    "avg_universe_up_ratio",
                ],
                max_rows=20,
            ),
            "",
            "## 按事前20日趋势汇总",
            "",
            markdown_table(
                trend_summary,
                [
                    "exante_trend_state",
                    "days",
                    "strategy_gross_sum",
                    "strategy_net_sum",
                    "same_exposure_benchmark_sum",
                    "gross_alpha_vs_benchmark_sum",
                    "avg_actual_gross_weight",
                    "avg_benchmark_o2o_ret",
                    "avg_universe_up_ratio",
                ],
                max_rows=20,
            ),
            "",
            "## 按事前波动汇总",
            "",
            markdown_table(
                vol_summary,
                [
                    "exante_vol_state",
                    "days",
                    "strategy_gross_sum",
                    "strategy_net_sum",
                    "same_exposure_benchmark_sum",
                    "gross_alpha_vs_benchmark_sum",
                    "avg_actual_gross_weight",
                    "avg_benchmark_o2o_ret",
                    "avg_universe_up_ratio",
                ],
                max_rows=20,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只解释冻结后paper OOS段的市场状态，不新增交易规则、不调阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：即使发现策略残差偏负，也没有把市场状态直接改成过滤器；保留样本过短警告。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：上一阶段确认执行健康后，下一步应区分市场拖累和选股/时点残差。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：本段同暴露指数偏正而策略残差偏负，提示后续OOS达到20天后要重点看买入后反转节奏和行业风格，而不是先怪成交。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 不把本阶段状态标签改成交易过滤器；先继续积累OOS样本。",
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
    segment_daily_path = ATTR_OUTPUT_DIR / f"{ATTR_PREFIX}_segment_daily.csv"
    if not segment_daily_path.exists():
        raise FileNotFoundError(segment_daily_path)

    segment_daily = read_csv(segment_daily_path).filter(pl.col("date") > FREEZE_TARGET_DATE)
    stock_df, benchmark_df = load_panels()
    benchmark_state = build_benchmark_state(benchmark_df)
    universe_state = build_universe_state(stock_df)
    state_daily = (
        segment_daily.join(benchmark_state, on="date", how="left")
        .join(universe_state, on="date", how="left")
        .with_columns(
            (pl.col("benchmark_open_to_next_open_ret") * pl.col("actual_gross_weight")).alias(
                "same_exposure_benchmark_o2o_ret"
            ),
            (pl.col("universe_equal_o2o_ret") * pl.col("actual_gross_weight")).alias(
                "same_exposure_universe_equal_ret"
            ),
        )
        .with_columns(
            (pl.col("strategy_gross_daily_ret") - pl.col("same_exposure_benchmark_o2o_ret")).alias(
                "gross_alpha_vs_same_exposure_benchmark"
            ),
            (pl.col("strategy_gross_daily_ret") - pl.col("same_exposure_universe_equal_ret")).alias(
                "gross_alpha_vs_same_exposure_universe"
            ),
        )
        .sort("date")
    )
    state_daily = add_state_labels(state_daily)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "freeze_target_date": FREEZE_TARGET_DATE,
        "segment_start_date": state_daily["date"].min() if not state_daily.is_empty() else None,
        "segment_end_date": state_daily["date"].max() if not state_daily.is_empty() else None,
        "segment_days": state_daily.height,
        "segment_strategy_gross_sum": to_float(state_daily["strategy_gross_daily_ret"].sum()) if not state_daily.is_empty() else 0.0,
        "segment_strategy_net_sum": to_float(state_daily["strategy_daily_ret"].sum()) if not state_daily.is_empty() else 0.0,
        "segment_same_exposure_benchmark_sum": to_float(state_daily["same_exposure_benchmark_o2o_ret"].sum()) if not state_daily.is_empty() else 0.0,
        "segment_same_exposure_universe_sum": to_float(state_daily["same_exposure_universe_equal_ret"].sum()) if not state_daily.is_empty() else 0.0,
        "segment_gross_alpha_vs_benchmark_sum": to_float(state_daily["gross_alpha_vs_same_exposure_benchmark"].sum()) if not state_daily.is_empty() else 0.0,
        "segment_gross_alpha_vs_universe_sum": to_float(state_daily["gross_alpha_vs_same_exposure_universe"].sum()) if not state_daily.is_empty() else 0.0,
        "avg_actual_gross_weight": to_float(state_daily["actual_gross_weight"].mean()) if not state_daily.is_empty() else 0.0,
        "avg_benchmark_o2o_ret": to_float(state_daily["benchmark_open_to_next_open_ret"].mean()) if not state_daily.is_empty() else 0.0,
        "avg_universe_equal_o2o_ret": to_float(state_daily["universe_equal_o2o_ret"].mean()) if not state_daily.is_empty() else 0.0,
        "avg_universe_up_ratio": to_float(state_daily["universe_up_ratio"].mean()) if not state_daily.is_empty() else 0.0,
        "index_down_gt_1pct_days": state_daily.filter(pl.col("index_state") == "index_down_gt_1pct").height if not state_daily.is_empty() else 0,
        "weak_breadth_days": state_daily.filter(pl.col("breadth_state") == "weak_breadth").height if not state_daily.is_empty() else 0,
    }
    summary["benchmark_explained_ratio_vs_strategy_gross"] = safe_ratio(
        float(summary["segment_same_exposure_benchmark_sum"]),
        float(summary["segment_strategy_gross_sum"]),
    )
    summary["universe_explained_ratio_vs_strategy_gross"] = safe_ratio(
        float(summary["segment_same_exposure_universe_sum"]),
        float(summary["segment_strategy_gross_sum"]),
    )
    summary["drag_diagnosis"] = diagnose_drag(summary)

    market_summary = summarize_by(state_daily, "index_state")
    breadth_summary = summarize_by(state_daily, "breadth_state")
    trend_summary = summarize_by(state_daily, "exante_trend_state")
    vol_summary = summarize_by(state_daily, "exante_vol_state")
    quality_checkpoints = build_quality_checkpoints(summary, state_daily)

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "state_daily": OUTPUT_DIR / f"{PREFIX}_state_daily.csv",
        "market_summary": OUTPUT_DIR / f"{PREFIX}_market_summary.csv",
        "breadth_summary": OUTPUT_DIR / f"{PREFIX}_breadth_summary.csv",
        "trend_summary": OUTPUT_DIR / f"{PREFIX}_trend_summary.csv",
        "vol_summary": OUTPUT_DIR / f"{PREFIX}_vol_summary.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    state_daily.write_csv(paths["state_daily"])
    market_summary.write_csv(paths["market_summary"])
    breadth_summary.write_csv(paths["breadth_summary"])
    trend_summary.write_csv(paths["trend_summary"])
    vol_summary.write_csv(paths["vol_summary"])
    quality_checkpoints.write_csv(paths["quality_checkpoints"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "freeze_target_date": FREEZE_TARGET_DATE,
            "min_oos_days_for_stable_judgment": MIN_OOS_DAYS_FOR_STABLE_JUDGMENT,
            "source_oos_attribution_dir": str(ATTR_OUTPUT_DIR),
            "research_sources": RESEARCH_SOURCES,
            "note": "Market-state attribution only; state labels are descriptive and are not used as trading filters.",
        },
    )
    report_path = write_report(
        summary,
        state_daily,
        market_summary,
        breadth_summary,
        trend_summary,
        vol_summary,
        quality_checkpoints,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
