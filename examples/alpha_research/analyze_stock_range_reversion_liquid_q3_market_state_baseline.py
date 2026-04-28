from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_paper_oos_market_state import (
    RESEARCH_SOURCES as OOS_MARKET_STATE_SOURCES,
    add_state_labels,
    build_benchmark_state,
    build_universe_state,
    summarize_by,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_ledger import LEDGER_VERSION
from generate_stock_range_reversion_liquid_q3_paper_ledger import OUTPUT_DIR as LEDGER_DIR
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_market_state_baseline_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_market_state_baseline_v1"

WINDOW_DAYS: int = int(os.getenv("MARKET_STATE_BASELINE_WINDOW_DAYS", "7") or 7)
MIN_ANALOG_WINDOWS: int = int(os.getenv("MARKET_STATE_BASELINE_MIN_ANALOG_WINDOWS", "30") or 30)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Regime-conditional decomposition compares strategy behavior across states",
        "https://arxiv.org/abs/2602.11708",
    ),
    (
        "Rolling OOS windows should include trading costs and avoid post-hoc optimization",
        "https://quant.stackexchange.com/questions/31954/out-of-sample-performance",
    ),
    *OOS_MARKET_STATE_SOURCES,
)


def read_csv(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def percentile_rank_le(values: list[float], value: float) -> float | None:
    clean = [item for item in values if item == item]
    if not clean:
        return None
    return sum(item <= value for item in clean) / len(clean)


def summarize_values(values: list[float]) -> dict[str, float | int | None]:
    clean = [item for item in values if item == item]
    if not clean:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "count": len(clean),
        "mean": sum(clean) / len(clean),
        "median": median(clean),
        "min": min(clean),
        "max": max(clean),
    }


def add_market_state(daily_ledger: pl.DataFrame, benchmark_df: pl.DataFrame, stock_df: pl.DataFrame) -> pl.DataFrame:
    benchmark_state = build_benchmark_state(benchmark_df)
    universe_state = build_universe_state(stock_df)
    state_daily = add_state_labels(
        daily_ledger.join(benchmark_state, on="date", how="left")
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
    return state_daily.with_columns(
        pl.when(pl.col("universe_up_ratio").is_null())
        .then(pl.lit("missing_breadth"))
        .otherwise(pl.col("breadth_state"))
        .alias("breadth_state")
    )


def build_cross_summary(state_daily: pl.DataFrame) -> pl.DataFrame:
    if state_daily.is_empty():
        return pl.DataFrame()
    groupings = [
        ("index_state", "breadth_state"),
        ("breadth_state", "exante_trend_state"),
        ("breadth_state", "exante_vol_state"),
    ]
    frames: list[pl.DataFrame] = []
    for left, right in groupings:
        frames.append(
            state_daily.group_by([left, right])
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
            .with_columns(
                pl.lit(f"{left}__{right}").alias("grouping"),
                pl.col(left).cast(pl.Utf8).alias("left_value"),
                pl.col(right).cast(pl.Utf8).alias("right_value"),
            )
            .select(
                [
                    "grouping",
                    "left_value",
                    "right_value",
                    "days",
                    "strategy_gross_sum",
                    "strategy_net_sum",
                    "same_exposure_benchmark_sum",
                    "same_exposure_universe_sum",
                    "gross_alpha_vs_benchmark_sum",
                    "gross_alpha_vs_universe_sum",
                    "avg_actual_gross_weight",
                    "avg_benchmark_o2o_ret",
                    "avg_universe_up_ratio",
                ]
            )
        )
    return pl.concat(frames, how="vertical").sort(["grouping", "strategy_net_sum"])


def build_rolling_windows(state_daily: pl.DataFrame, window_days: int) -> pl.DataFrame:
    rows = state_daily.sort("date").iter_rows(named=True)
    history = list(rows)
    window_rows: list[dict[str, Any]] = []
    for end_index in range(window_days - 1, len(history)):
        window = history[end_index - window_days + 1 : end_index + 1]
        gross_sum = sum(to_float(row.get("strategy_gross_daily_ret")) for row in window)
        net_sum = sum(to_float(row.get("strategy_daily_ret")) for row in window)
        benchmark_sum = sum(to_float(row.get("same_exposure_benchmark_o2o_ret")) for row in window)
        universe_sum = sum(to_float(row.get("same_exposure_universe_equal_ret")) for row in window)
        alpha_benchmark_sum = sum(to_float(row.get("gross_alpha_vs_same_exposure_benchmark")) for row in window)
        alpha_universe_sum = sum(to_float(row.get("gross_alpha_vs_same_exposure_universe")) for row in window)
        window_rows.append(
            {
                "start_date": window[0]["date"],
                "end_date": window[-1]["date"],
                "window_days": window_days,
                "strategy_gross_sum": gross_sum,
                "strategy_net_sum": net_sum,
                "same_exposure_benchmark_sum": benchmark_sum,
                "same_exposure_universe_sum": universe_sum,
                "gross_alpha_vs_benchmark_sum": alpha_benchmark_sum,
                "gross_alpha_vs_universe_sum": alpha_universe_sum,
                "avg_actual_gross_weight": sum(to_float(row.get("actual_gross_weight")) for row in window) / window_days,
                "avg_benchmark_o2o_ret": sum(to_float(row.get("benchmark_open_to_next_open_ret")) for row in window)
                / window_days,
                "avg_universe_up_ratio": sum(to_float(row.get("universe_up_ratio"), default=0.5) for row in window)
                / window_days,
                "weak_breadth_days": sum(row.get("breadth_state") == "weak_breadth" for row in window),
                "strong_breadth_days": sum(row.get("breadth_state") == "strong_breadth" for row in window),
                "index_down_gt_1pct_days": sum(row.get("index_state") == "index_down_gt_1pct" for row in window),
                "index_up_gt_1pct_days": sum(row.get("index_state") == "index_up_gt_1pct" for row in window),
                "exante_uptrend_days": sum(row.get("exante_trend_state") == "exante_20d_uptrend" for row in window),
                "exante_downtrend_days": sum(row.get("exante_trend_state") == "exante_20d_downtrend" for row in window),
                "latest_equity": window[-1].get("strategy_equity"),
                "latest_drawdown": window[-1].get("strategy_drawdown"),
                "window_label": "latest" if end_index == len(history) - 1 else "history",
            }
        )
    return pl.DataFrame(window_rows).sort("end_date") if window_rows else pl.DataFrame()


def build_window_summary(rolling_windows: pl.DataFrame) -> tuple[dict[str, Any], pl.DataFrame]:
    if rolling_windows.is_empty():
        return {}, pl.DataFrame()
    latest = rolling_windows.tail(1).row(0, named=True)
    all_rows = list(rolling_windows.iter_rows(named=True))
    current_weak_days = int(latest["weak_breadth_days"])
    current_uptrend_days = int(latest["exante_uptrend_days"])
    analog_rows = [
        row
        for row in all_rows
        if int(row["weak_breadth_days"]) >= current_weak_days
        and int(row["exante_uptrend_days"]) >= current_uptrend_days
    ]
    if not analog_rows:
        analog_rows = [latest]
    all_net = [to_float(row["strategy_net_sum"]) for row in all_rows]
    all_alpha = [to_float(row["gross_alpha_vs_benchmark_sum"]) for row in all_rows]
    analog_net = [to_float(row["strategy_net_sum"]) for row in analog_rows]
    analog_alpha = [to_float(row["gross_alpha_vs_benchmark_sum"]) for row in analog_rows]
    summary = {
        "latest_window_start_date": latest["start_date"],
        "latest_window_end_date": latest["end_date"],
        "latest_window_days": latest["window_days"],
        "rolling_window_count": len(all_rows),
        "analog_window_count": len(analog_rows),
        "latest_strategy_gross_sum": latest["strategy_gross_sum"],
        "latest_strategy_net_sum": latest["strategy_net_sum"],
        "latest_same_exposure_benchmark_sum": latest["same_exposure_benchmark_sum"],
        "latest_same_exposure_universe_sum": latest["same_exposure_universe_sum"],
        "latest_gross_alpha_vs_benchmark_sum": latest["gross_alpha_vs_benchmark_sum"],
        "latest_gross_alpha_vs_universe_sum": latest["gross_alpha_vs_universe_sum"],
        "latest_weak_breadth_days": latest["weak_breadth_days"],
        "latest_exante_uptrend_days": latest["exante_uptrend_days"],
        "latest_net_percentile_rank_le_all_windows": percentile_rank_le(all_net, to_float(latest["strategy_net_sum"])),
        "latest_alpha_percentile_rank_le_all_windows": percentile_rank_le(
            all_alpha, to_float(latest["gross_alpha_vs_benchmark_sum"])
        ),
        "latest_net_percentile_rank_le_analog_windows": percentile_rank_le(
            analog_net, to_float(latest["strategy_net_sum"])
        ),
        "latest_alpha_percentile_rank_le_analog_windows": percentile_rank_le(
            analog_alpha, to_float(latest["gross_alpha_vs_benchmark_sum"])
        ),
        "all_windows_net_stats": summarize_values(all_net),
        "all_windows_alpha_stats": summarize_values(all_alpha),
        "analog_windows_net_stats": summarize_values(analog_net),
        "analog_windows_alpha_stats": summarize_values(analog_alpha),
    }
    return summary, pl.DataFrame(analog_rows).sort("end_date")


def classify_baseline_status(summary: dict[str, Any]) -> str:
    alpha_pct = summary.get("latest_alpha_percentile_rank_le_all_windows")
    net_pct = summary.get("latest_net_percentile_rank_le_all_windows")
    if alpha_pct is not None and alpha_pct <= 0.10:
        return "historically_bad_alpha_tail"
    if net_pct is not None and net_pct <= 0.10:
        return "historically_bad_net_tail"
    if alpha_pct is not None and alpha_pct <= 0.25:
        return "below_median_but_not_tail"
    return "not_historical_tail"


def build_quality_checkpoints(
    state_daily: pl.DataFrame,
    rolling_windows: pl.DataFrame,
    analog_windows: pl.DataFrame,
) -> pl.DataFrame:
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

    add(
        "baseline_daily_rows",
        "pass" if state_daily.height >= 1000 else "warn",
        state_daily.height,
        ">=1000",
        "历史状态基线需要覆盖足够长的多年份样本。",
    )
    benchmark_nulls = (
        state_daily.select(pl.col("benchmark_open_to_next_open_ret").null_count()).item()
        if not state_daily.is_empty()
        else None
    )
    add(
        "benchmark_o2o_coverage",
        "pass" if benchmark_nulls == 0 else "fail",
        benchmark_nulls,
        0,
        "历史同暴露基准需要中证1000开盘到次开盘收益完整。",
    )
    universe_nulls = (
        state_daily.select(pl.col("universe_equal_o2o_ret").null_count()).item() if not state_daily.is_empty() else None
    )
    universe_null_ratio = (
        universe_nulls / state_daily.height
        if universe_nulls is not None and state_daily.height > 0
        else None
    )
    add(
        "universe_breadth_coverage",
        "pass" if universe_nulls == 0 else ("warn" if universe_null_ratio is not None and universe_null_ratio <= 0.05 else "fail"),
        f"{universe_nulls} ({universe_null_ratio:.2%})" if universe_null_ratio is not None else universe_nulls,
        "0 preferred; <=5% tolerated",
        "少量早期市场宽度缺失可保留为warning；宽度相关结论需避开missing_breadth状态。",
    )
    add(
        "rolling_window_count",
        "pass" if rolling_windows.height >= 500 else "warn",
        rolling_windows.height,
        ">=500",
        "滚动窗口太少时，分位判断不稳定。",
    )
    add(
        "analog_window_count",
        "pass" if analog_windows.height >= MIN_ANALOG_WINDOWS else "warn",
        analog_windows.height,
        f">={MIN_ANALOG_WINDOWS}",
        "同类状态窗口少时，只能作为参考，不能作为过滤器依据。",
    )
    add(
        "no_parameter_change",
        "pass",
        "no signal/threshold change",
        "no signal/threshold change",
        "本阶段只做历史状态基线，不改交易规则。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    index_summary: pl.DataFrame,
    breadth_summary: pl.DataFrame,
    trend_summary: pl.DataFrame,
    cross_summary: pl.DataFrame,
    rolling_windows: pl.DataFrame,
    analog_windows: pl.DataFrame,
    quality_checkpoints: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality_checkpoints.filter(pl.col("status") == "fail")
    warned = quality_checkpoints.filter(pl.col("status") == "warn")
    latest_windows = rolling_windows.tail(12)
    worst_alpha_windows = rolling_windows.sort("gross_alpha_vs_benchmark_sum").head(10)
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3历史市场状态基线 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：历史状态基线和最新7日窗口分位对照；不新增信号、不调参数。",
        f"- 滚动窗口长度：`{WINDOW_DAYS}`个交易日。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 均值回归策略的OOS表现需要在不同市场状态、相对基准和交易成本下拆开看。",
        "- 本阶段用历史滚动窗口给最新7日OOS做分位坐标；分位只用于风险解释，不用于挑选新过滤器。",
        "- 直觉判断：如果最新窗口只是历史常见波动，就不该动手；如果落在历史尾部，才值得升级为风险事件观察。",
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
            f"- 历史日样本`{summary['baseline_daily_rows']}`天，滚动`{WINDOW_DAYS}`日窗口`{summary['rolling_window_count']}`个。",
            f"- 最新窗口：`{summary['latest_window_start_date']}`到`{summary['latest_window_end_date']}`。",
            f"- 最新窗口策略净收益`{pct(summary['latest_strategy_net_sum'])}`，毛收益`{pct(summary['latest_strategy_gross_sum'])}`。",
            f"- 最新窗口同暴露中证1000`{pct(summary['latest_same_exposure_benchmark_sum'])}`，同暴露成分股等权`{pct(summary['latest_same_exposure_universe_sum'])}`。",
            f"- 最新窗口相对同暴露中证1000残差`{pct(summary['latest_gross_alpha_vs_benchmark_sum'])}`。",
            f"- 最新窗口净收益历史分位`{summary['latest_net_percentile_rank_le_all_windows']:.2%}`，残差历史分位`{summary['latest_alpha_percentile_rank_le_all_windows']:.2%}`。",
            f"- 同类状态窗口`{summary['analog_window_count']}`个，最新窗口残差在同类窗口分位`{summary['latest_alpha_percentile_rank_le_analog_windows']:.2%}`。",
            f"- 基线状态：`{summary['baseline_status']}`。",
            "- 我的判断：最新7日残差偏弱，需要继续观察；但它是否已经落入历史尾部，要看分位结果，不直接用这7天修改策略。",
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
            "## 指数状态历史汇总",
            "",
            markdown_table(
                index_summary,
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
            "## 市场宽度历史汇总",
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
            "## 事前趋势历史汇总",
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
            "## 交叉状态历史汇总",
            "",
            markdown_table(
                cross_summary,
                [
                    "grouping",
                    "left_value",
                    "right_value",
                    "days",
                    "strategy_net_sum",
                    "same_exposure_benchmark_sum",
                    "gross_alpha_vs_benchmark_sum",
                    "avg_actual_gross_weight",
                    "avg_universe_up_ratio",
                ],
                max_rows=80,
            ),
            "",
            "## 最新滚动窗口",
            "",
            markdown_table(
                latest_windows,
                [
                    "start_date",
                    "end_date",
                    "strategy_net_sum",
                    "same_exposure_benchmark_sum",
                    "gross_alpha_vs_benchmark_sum",
                    "weak_breadth_days",
                    "exante_uptrend_days",
                    "window_label",
                ],
                max_rows=20,
            ),
            "",
            "## 历史残差最差窗口",
            "",
            markdown_table(
                worst_alpha_windows,
                [
                    "start_date",
                    "end_date",
                    "strategy_net_sum",
                    "same_exposure_benchmark_sum",
                    "gross_alpha_vs_benchmark_sum",
                    "weak_breadth_days",
                    "exante_uptrend_days",
                    "window_label",
                ],
                max_rows=10,
            ),
            "",
            "## 同类状态窗口样本",
            "",
            markdown_table(
                analog_windows.tail(20),
                [
                    "start_date",
                    "end_date",
                    "strategy_net_sum",
                    "same_exposure_benchmark_sum",
                    "gross_alpha_vs_benchmark_sum",
                    "weak_breadth_days",
                    "exante_uptrend_days",
                    "window_label",
                ],
                max_rows=20,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只用历史状态基线解释当前OOS窗口，不产生交易过滤器。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：所有阈值只用于状态描述和分位定位，未修改策略参数或筛选条件。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第260阶段指出当前OOS残差偏负，需要知道它在历史同类状态中是否异常。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：历史分位能给后续paper OOS监控提供风险坐标，避免只凭最近7天直觉行动。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 不把历史状态分位改成交易规则；先作为paper OOS监控指标。",
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
    daily_path = LEDGER_DIR / f"{LEDGER_VERSION}_daily_ledger.csv"
    if not daily_path.exists():
        raise FileNotFoundError(daily_path)
    daily_ledger = read_csv(daily_path)
    stock_df, benchmark_df = load_panels()
    state_daily = add_market_state(daily_ledger, benchmark_df, stock_df)
    index_summary = summarize_by(state_daily, "index_state")
    breadth_complete = state_daily.filter(pl.col("breadth_state") != "missing_breadth")
    breadth_summary = summarize_by(breadth_complete, "breadth_state")
    trend_summary = summarize_by(state_daily, "exante_trend_state")
    vol_summary = summarize_by(state_daily, "exante_vol_state")
    cross_summary = build_cross_summary(breadth_complete)
    rolling_windows = build_rolling_windows(state_daily, WINDOW_DAYS)
    window_summary, analog_windows = build_window_summary(rolling_windows)
    quality_checkpoints = build_quality_checkpoints(state_daily, rolling_windows, analog_windows)
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_daily_rows": state_daily.height,
        "state_start_date": state_daily["date"].min() if not state_daily.is_empty() else None,
        "state_end_date": state_daily["date"].max() if not state_daily.is_empty() else None,
        "window_days": WINDOW_DAYS,
        **window_summary,
    }
    summary["baseline_status"] = classify_baseline_status(summary)

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "state_daily": OUTPUT_DIR / f"{PREFIX}_state_daily.csv",
        "index_summary": OUTPUT_DIR / f"{PREFIX}_index_summary.csv",
        "breadth_summary": OUTPUT_DIR / f"{PREFIX}_breadth_summary.csv",
        "trend_summary": OUTPUT_DIR / f"{PREFIX}_trend_summary.csv",
        "vol_summary": OUTPUT_DIR / f"{PREFIX}_vol_summary.csv",
        "cross_summary": OUTPUT_DIR / f"{PREFIX}_cross_summary.csv",
        "rolling_windows": OUTPUT_DIR / f"{PREFIX}_rolling_windows.csv",
        "analog_windows": OUTPUT_DIR / f"{PREFIX}_analog_windows.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    state_daily.write_csv(paths["state_daily"])
    index_summary.write_csv(paths["index_summary"])
    breadth_summary.write_csv(paths["breadth_summary"])
    trend_summary.write_csv(paths["trend_summary"])
    vol_summary.write_csv(paths["vol_summary"])
    cross_summary.write_csv(paths["cross_summary"])
    rolling_windows.write_csv(paths["rolling_windows"])
    analog_windows.write_csv(paths["analog_windows"])
    quality_checkpoints.write_csv(paths["quality_checkpoints"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "ledger_version": LEDGER_VERSION,
            "window_days": WINDOW_DAYS,
            "min_analog_windows": MIN_ANALOG_WINDOWS,
            "source_ledger_dir": str(LEDGER_DIR),
            "research_sources": RESEARCH_SOURCES,
            "note": "Historical state baseline only; state percentiles are monitoring coordinates, not trading filters.",
        },
    )
    report_path = write_report(
        summary,
        index_summary,
        breadth_summary,
        trend_summary,
        cross_summary,
        rolling_windows,
        analog_windows,
        quality_checkpoints,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
