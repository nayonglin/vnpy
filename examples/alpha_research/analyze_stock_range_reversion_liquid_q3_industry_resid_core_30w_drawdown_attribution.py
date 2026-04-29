from __future__ import annotations

import json
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution import (
    add_buckets,
    build_drawdown_episodes,
    build_full_position_daily,
    build_worst_day_industry,
    build_worst_day_symbol,
    build_worst_days,
    downside_vol,
)
from analyze_stock_range_reversion_liquid_q3_market_state_baseline import add_market_state
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_drawdown_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_drawdown_attribution_v1"

FOCUS_SCENARIOS: tuple[str, ...] = (
    "industry_resid_core_h10_top8_gross100_ind2",
    "industry_resid_core_h10_top5_gross100_ind1",
    "industry_resid_core_h10_top8_gross70_ind2",
    "industry_resid_core_h10_top5_gross70_ind1",
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Empirical investigation of state-of-the-art mean reversion strategies for equity markets",
        "https://arxiv.org/abs/1909.04327",
    ),
    (
        "Profitability of contrarian strategies in the Chinese stock market",
        "https://arxiv.org/abs/1505.00328",
    ),
    (
        "Quant strategy excess drawdown analysis: style switching and liquidity shocks",
        "https://stock.finance.sina.com.cn/stock/go.php/vReport_Show/kind/11/rptid/763659338573/index.phtml",
    ),
    (
        "Downside Risk Reduction Using Regime-Switching Signals",
        "https://arxiv.org/abs/2402.05272",
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def read_csv_with_symbol(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def annualized_vol(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    return sqrt(max(variance, 0.0)) * sqrt(TRADING_DAYS)


def summarize_state_by(state_daily: pl.DataFrame, group_col: str) -> pl.DataFrame:
    if state_daily.is_empty() or group_col not in state_daily.columns:
        return pl.DataFrame()
    return (
        state_daily.group_by(["scenario", group_col])
        .agg(
            pl.len().alias("days"),
            pl.col("strategy_daily_ret_min_fee").sum().alias("net_return_sum"),
            ((pl.col("strategy_daily_ret_min_fee") + 1).product() - 1).alias("compounded_return"),
            pl.col("strategy_daily_ret_min_fee").mean().alias("avg_daily_ret"),
            pl.col("strategy_daily_ret_min_fee").min().alias("worst_daily_ret"),
            (pl.col("strategy_daily_ret_min_fee") > 0).mean().alias("daily_win_rate"),
            pl.col("strategy_gross_daily_ret").sum().alias("gross_return_sum"),
            pl.col("turnover_cost_ret_min_fee").sum().alias("cost_drag_sum"),
            pl.col("same_exposure_benchmark_o2o_ret").sum().alias("same_exposure_benchmark_sum"),
            pl.col("gross_alpha_vs_same_exposure_benchmark").sum().alias("alpha_vs_benchmark_sum"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            pl.col("zero_lot_target_count").mean().alias("avg_zero_lot_target_count"),
        )
        .sort(["scenario", "net_return_sum"])
    )


def summarize_scenario(daily: pl.DataFrame, drawdowns: pl.DataFrame) -> dict[str, Any]:
    returns = [float(value) for value in daily["strategy_daily_ret_min_fee"].to_list()]
    worst_episode = drawdowns.row(0, named=True) if not drawdowns.is_empty() else {}
    scenario = str(daily["scenario"][0])
    return {
        "scenario": scenario,
        "date_start": daily["date"].min(),
        "date_end": daily["date"].max(),
        "trading_days": daily.height,
        "final_equity_min_fee": to_float(daily["equity_min_fee"][-1]),
        "total_return_min_fee": to_float(daily["equity_min_fee"][-1]) - 1.0,
        "max_drawdown_min_fee": to_float(daily["drawdown_min_fee"].min()),
        "annualized_vol_min_fee": annualized_vol(returns),
        "downside_vol_min_fee": downside_vol(returns),
        "worst_daily_ret_min_fee": min(returns) if returns else 0.0,
        "active_day_win_rate": sum(1 for value in returns if value > 0) / len(returns) if returns else 0.0,
        "avg_actual_gross_weight": to_float(daily["actual_gross_weight"].mean()),
        "max_actual_gross_weight": to_float(daily["actual_gross_weight"].max()),
        "avg_actual_symbol_count": to_float(daily["actual_symbol_count"].mean()),
        "avg_zero_lot_target_count": to_float(daily["zero_lot_target_count"].mean()),
        "drawdown_episode_count": drawdowns.height,
        "worst_drawdown_peak_date": worst_episode.get("peak_date"),
        "worst_drawdown_trough_date": worst_episode.get("trough_date"),
        "worst_drawdown_recovery_date": worst_episode.get("recovery_date"),
        "worst_drawdown_recovered": worst_episode.get("recovered"),
        "worst_drawdown_depth": worst_episode.get("max_drawdown"),
        "worst_drawdown_days_to_trough": worst_episode.get("trading_days_to_trough"),
        "worst_drawdown_days_to_recovery_or_end": worst_episode.get("trading_days_to_recovery_or_end"),
        "worst_drawdown_avg_gross_weight": worst_episode.get("avg_actual_gross_weight"),
        "worst_drawdown_avg_zero_lot_target_count": worst_episode.get("avg_zero_lot_target_count"),
    }


def build_drawdown_period_position_summary(position_daily: pl.DataFrame, drawdowns: pl.DataFrame) -> pl.DataFrame:
    if position_daily.is_empty() or drawdowns.is_empty():
        return pl.DataFrame()
    episode_rows: list[dict[str, Any]] = []
    top_episodes = drawdowns.group_by("scenario").head(3)
    for episode in top_episodes.iter_rows(named=True):
        scenario = str(episode["scenario"])
        start_date = episode["start_date"]
        trough_date = episode["trough_date"]
        positions = position_daily.filter(
            (pl.col("scenario") == scenario) & (pl.col("date") >= start_date) & (pl.col("date") <= trough_date)
        )
        if positions.is_empty():
            continue
        industry = (
            positions.group_by("industry")
            .agg(
                pl.len().alias("position_days"),
                pl.col("symbol").n_unique().alias("symbols"),
                pl.col("actual_weight").mean().alias("avg_weight"),
                pl.col("actual_weight").max().alias("max_weight"),
                pl.col("gross_contribution").sum().alias("gross_contribution_sum"),
            )
            .sort("gross_contribution_sum")
            .head(8)
        )
        for row in industry.iter_rows(named=True):
            episode_rows.append(
                {
                    "scenario": scenario,
                    "peak_date": episode["peak_date"],
                    "start_date": start_date,
                    "trough_date": trough_date,
                    "max_drawdown": episode["max_drawdown"],
                    **row,
                }
            )
    return pl.DataFrame(episode_rows) if episode_rows else pl.DataFrame()


def build_quality(
    scenario_summary: pl.DataFrame,
    state_daily: pl.DataFrame,
    position_daily: pl.DataFrame,
    focus_scenarios: tuple[str, ...],
) -> pl.DataFrame:
    rows: list[dict[str, str]] = []

    def add(checkpoint: str, status: str, value: Any, expected: Any, note: str) -> None:
        rows.append(
            {
                "checkpoint": checkpoint,
                "status": status,
                "value": "" if value is None else str(value),
                "expected": "" if expected is None else str(expected),
                "note": note,
            }
        )

    found = set(scenario_summary["scenario"].to_list()) if not scenario_summary.is_empty() else set()
    missing = [item for item in focus_scenarios if item not in found]
    add(
        "focus_scenarios_available",
        "pass" if not missing else "fail",
        ",".join(missing) if missing else "all found",
        "all focus scenarios found",
        "必须能找到第308阶段代表形状。",
    )
    add(
        "drawdown_episodes_found",
        "pass" if scenario_summary.select(pl.col("drawdown_episode_count").min()).item() > 0 else "fail",
        scenario_summary.select(pl.col("drawdown_episode_count").min()).item() if not scenario_summary.is_empty() else 0,
        ">0 for every scenario",
        "必须识别回撤段才有归因意义。",
    )
    benchmark_nulls = state_daily.select(pl.col("benchmark_open_to_next_open_ret").null_count()).item()
    add(
        "benchmark_state_coverage",
        "pass" if benchmark_nulls == 0 else "fail",
        benchmark_nulls,
        0,
        "市场状态归因需要完整基准收益。",
    )
    missing_position_returns = (
        position_daily.filter(pl.col("missing_return")).height if not position_daily.is_empty() else 0
    )
    add(
        "position_return_coverage",
        "pass" if missing_position_returns == 0 else "fail",
        missing_position_returns,
        0,
        "实际持仓贡献应能取到收益。",
    )
    if not position_daily.is_empty():
        attribution = (
            position_daily.group_by(["scenario", "date"])
            .agg(pl.col("gross_contribution").sum().alias("recomputed_gross_ret"))
            .join(state_daily.select(["scenario", "date", "strategy_gross_daily_ret"]), on=["scenario", "date"], how="left")
            .with_columns((pl.col("recomputed_gross_ret") - pl.col("strategy_gross_daily_ret")).abs().alias("diff"))
        )
        max_diff = to_float(attribution["diff"].max())
    else:
        max_diff = None
    add(
        "position_contribution_matches_daily_gross",
        "pass" if max_diff is not None and max_diff <= 1e-10 else "fail",
        max_diff,
        "<=1e-10",
        "持仓贡献求和应复原日级毛收益。",
    )
    best_dd = scenario_summary.select(pl.col("max_drawdown_min_fee").min()).item() if not scenario_summary.is_empty() else None
    add(
        "drawdown_not_within_user_limit",
        "pass" if best_dd is not None and best_dd < -0.20 else "warn",
        pct(best_dd) if best_dd is not None else "NA",
        "<-20%",
        "本阶段应解释失败，而不是包装成可交易。",
    )
    add(
        "no_strategy_parameter_change",
        "pass",
        "no signal/threshold change",
        "no signal/threshold change",
        "本阶段只做归因，不改变交易规则。",
    )
    return pl.DataFrame(rows)


def write_report(
    scenario_summary: pl.DataFrame,
    drawdowns: pl.DataFrame,
    worst_days: pl.DataFrame,
    state_summaries: dict[str, pl.DataFrame],
    worst_industry: pl.DataFrame,
    worst_symbol: pl.DataFrame,
    drawdown_period_industry: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    lines = [
        "# 股票震荡industry_resid_core 30万回撤簇归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：第308阶段30万整手复放回撤簇归因；不新增交易规则、不调参数。",
        "- 聚焦形状：最高收益、次高收益、两个70% gross低回撤候选。",
        "",
        "## 外部调研判断",
        "",
        "- 均值回归策略的主要失效点通常不是单笔信号完全无效，而是市场状态切换、流动性冲击、风格拥挤和成本拖累导致的路径亏损。",
        "- A股反转文献支持反转效应存在，但短期反转在不同牛熊/风格状态下稳定性会变化。",
        "- 因此本阶段只做回撤归因，不把任何状态过滤或止损规则直接升级为交易规则。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 场景摘要",
            "",
            markdown_table(
                scenario_summary,
                [
                    "scenario",
                    "date_start",
                    "date_end",
                    "final_equity_min_fee",
                    "total_return_min_fee",
                    "max_drawdown_min_fee",
                    "annualized_vol_min_fee",
                    "downside_vol_min_fee",
                    "active_day_win_rate",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "avg_zero_lot_target_count",
                    "worst_drawdown_peak_date",
                    "worst_drawdown_trough_date",
                    "worst_drawdown_depth",
                    "worst_drawdown_days_to_trough",
                ],
                max_rows=20,
            ),
            "",
            "## 最大回撤段",
            "",
            markdown_table(
                drawdowns.group_by("scenario").head(8),
                [
                    "scenario",
                    "peak_date",
                    "start_date",
                    "trough_date",
                    "recovery_date",
                    "recovered",
                    "max_drawdown",
                    "trading_days_to_trough",
                    "trading_days_to_recovery_or_end",
                    "net_return_to_trough",
                    "gross_return_sum_to_trough",
                    "cost_drag_sum_to_trough",
                    "avg_actual_gross_weight",
                    "avg_zero_lot_target_count",
                    "worst_daily_return",
                ],
                max_rows=40,
            ),
            "",
            "## 回撤段行业贡献",
            "",
            markdown_table(
                drawdown_period_industry,
                [
                    "scenario",
                    "peak_date",
                    "trough_date",
                    "max_drawdown",
                    "industry",
                    "position_days",
                    "symbols",
                    "avg_weight",
                    "max_weight",
                    "gross_contribution_sum",
                ],
                max_rows=80,
            ),
            "",
            "## 最差单日",
            "",
            markdown_table(
                worst_days,
                [
                    "scenario",
                    "date",
                    "strategy_daily_ret_min_fee",
                    "strategy_gross_daily_ret",
                    "turnover_cost_ret_min_fee",
                    "actual_gross_weight",
                    "actual_symbol_count",
                    "zero_lot_target_count",
                    "index_state",
                    "breadth_state",
                    "exante_trend_state",
                    "exante_vol_state",
                ],
                max_rows=60,
            ),
            "",
            "## 状态归因",
            "",
            "### 指数状态",
            "",
            markdown_table(state_summaries["index_state"], state_summaries["index_state"].columns, max_rows=80),
            "",
            "### 市场宽度",
            "",
            markdown_table(state_summaries["breadth_state"], state_summaries["breadth_state"].columns, max_rows=80),
            "",
            "### 20日趋势状态",
            "",
            markdown_table(state_summaries["exante_trend_state"], state_summaries["exante_trend_state"].columns, max_rows=80),
            "",
            "### 20日波动状态",
            "",
            markdown_table(state_summaries["exante_vol_state"], state_summaries["exante_vol_state"].columns, max_rows=80),
            "",
            "## 30万账户结构归因",
            "",
            "### 实际暴露分组",
            "",
            markdown_table(state_summaries["gross_exposure_bucket"], state_summaries["gross_exposure_bucket"].columns, max_rows=80),
            "",
            "### 买不到一手目标数量分组",
            "",
            markdown_table(state_summaries["zero_lot_bucket"], state_summaries["zero_lot_bucket"].columns, max_rows=80),
            "",
            "### 实际持仓数量分组",
            "",
            markdown_table(state_summaries["actual_names_bucket"], state_summaries["actual_names_bucket"].columns, max_rows=80),
            "",
            "### 暴露跳变分组",
            "",
            markdown_table(state_summaries["exposure_change_bucket"], state_summaries["exposure_change_bucket"].columns, max_rows=80),
            "",
            "## 最差10%单日行业贡献",
            "",
            markdown_table(
                worst_industry,
                [
                    "scenario",
                    "industry",
                    "position_days",
                    "symbols",
                    "avg_weight",
                    "max_weight",
                    "gross_contribution_sum",
                    "avg_position_contribution",
                ],
                max_rows=120,
            ),
            "",
            "## 最差10%单日个股贡献",
            "",
            markdown_table(
                worst_symbol,
                [
                    "scenario",
                    "symbol",
                    "code_name",
                    "industry",
                    "held_bad_days",
                    "avg_weight",
                    "max_weight",
                    "gross_contribution_sum",
                    "avg_daily_ret",
                ],
                max_rows=120,
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
            "- 原因：本阶段只做第308阶段失败路径归因，不测试新过滤器或止损参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：报告没有选择更优参数，只暴露回撤来源；下一步若测试风控必须限于少数第一性原理假设。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第308阶段信号层有效但复放回撤过深，需要知道回撤来自哪里。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是，但继续价值在风险层归因后的少量反证测试。",
            "- 原因：如果回撤主要来自特定市场状态或暴露形态，可以测试外生降权；如果来自广泛行业/个股扩散，就应暂停交易化。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不修改`industry_resid_core`信号。",
            "- 下一步只考虑市场状态降权、实际暴露上限、行业实际暴露约束三类少量反证；不扫top_k/gross/持有期。",
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
    daily_path = SOURCE_DIR / f"{SOURCE_PREFIX}_daily.csv"
    orders_path = SOURCE_DIR / f"{SOURCE_PREFIX}_orders.csv"
    daily_all = pl.read_csv(daily_path, try_parse_dates=True).sort(["scenario", "date"])
    orders_all = read_csv_with_symbol(orders_path).sort(["scenario", "date", "symbol", "side"])
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    state_daily_parts: list[pl.DataFrame] = []
    position_parts: list[pl.DataFrame] = []
    drawdown_parts: list[pl.DataFrame] = []
    worst_day_parts: list[pl.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    worst_industry_parts: list[pl.DataFrame] = []
    worst_symbol_parts: list[pl.DataFrame] = []

    for scenario in FOCUS_SCENARIOS:
        daily = daily_all.filter(pl.col("scenario") == scenario).sort("date")
        orders = orders_all.filter(pl.col("scenario") == scenario).sort(["date", "symbol", "side"])
        if daily.is_empty():
            continue
        position_daily = build_full_position_daily(daily, orders, exec_info).with_columns(pl.lit(scenario).alias("scenario"))
        state_daily = (
            add_market_state(
                daily.with_columns(pl.col("strategy_daily_ret_min_fee").alias("strategy_daily_ret")),
                benchmark_df,
                stock_df,
            )
            .with_columns(pl.lit(scenario).alias("scenario"))
            .with_columns(pl.col("actual_gross_weight").diff().abs().fill_null(0.0).alias("actual_gross_weight_abs_change"))
            .sort("date")
        )
        state_daily = add_buckets(state_daily)
        drawdowns = build_drawdown_episodes(daily).with_columns(pl.lit(scenario).alias("scenario"))
        worst_days = build_worst_days(state_daily).with_columns(pl.lit(scenario).alias("scenario"))
        worst_industry = build_worst_day_industry(position_daily, state_daily).with_columns(pl.lit(scenario).alias("scenario"))
        worst_symbol = build_worst_day_symbol(position_daily, state_daily).with_columns(pl.lit(scenario).alias("scenario"))
        summary_rows.append(summarize_scenario(daily, drawdowns))
        state_daily_parts.append(state_daily)
        position_parts.append(position_daily)
        drawdown_parts.append(drawdowns)
        worst_day_parts.append(worst_days)
        worst_industry_parts.append(worst_industry)
        worst_symbol_parts.append(worst_symbol)

    state_daily_all = pl.concat(state_daily_parts, how="vertical") if state_daily_parts else pl.DataFrame()
    position_daily_all = pl.concat(position_parts, how="vertical") if position_parts else pl.DataFrame()
    drawdowns_all = pl.concat(drawdown_parts, how="vertical") if drawdown_parts else pl.DataFrame()
    worst_days_all = pl.concat(worst_day_parts, how="vertical") if worst_day_parts else pl.DataFrame()
    scenario_summary = pl.DataFrame(summary_rows).sort("max_drawdown_min_fee") if summary_rows else pl.DataFrame()
    worst_industry_all = pl.concat(worst_industry_parts, how="vertical") if worst_industry_parts else pl.DataFrame()
    worst_symbol_all = pl.concat(worst_symbol_parts, how="vertical") if worst_symbol_parts else pl.DataFrame()
    drawdown_period_industry = build_drawdown_period_position_summary(position_daily_all, drawdowns_all)

    state_summaries = {
        name: summarize_state_by(state_daily_all, name)
        for name in [
            "index_state",
            "breadth_state",
            "exante_trend_state",
            "exante_vol_state",
            "gross_exposure_bucket",
            "zero_lot_bucket",
            "actual_names_bucket",
            "exposure_change_bucket",
        ]
    }
    quality = build_quality(scenario_summary, state_daily_all, position_daily_all, FOCUS_SCENARIOS)

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "scenario_summary": OUTPUT_DIR / f"{PREFIX}_scenario_summary.csv",
        "state_daily": OUTPUT_DIR / f"{PREFIX}_state_daily.csv",
        "position_daily": OUTPUT_DIR / f"{PREFIX}_position_daily.csv",
        "drawdown_episodes": OUTPUT_DIR / f"{PREFIX}_drawdown_episodes.csv",
        "drawdown_period_industry": OUTPUT_DIR / f"{PREFIX}_drawdown_period_industry.csv",
        "worst_days": OUTPUT_DIR / f"{PREFIX}_worst_days.csv",
        "worst_day_industry": OUTPUT_DIR / f"{PREFIX}_worst_day_industry.csv",
        "worst_day_symbol": OUTPUT_DIR / f"{PREFIX}_worst_day_symbol.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    for name, frame in state_summaries.items():
        path = OUTPUT_DIR / f"{PREFIX}_{name}_summary.csv"
        paths[f"{name}_summary"] = path
        frame.write_csv(path)
    scenario_summary.write_csv(paths["scenario_summary"])
    state_daily_all.write_csv(paths["state_daily"])
    position_daily_all.write_csv(paths["position_daily"])
    drawdowns_all.write_csv(paths["drawdown_episodes"])
    drawdown_period_industry.write_csv(paths["drawdown_period_industry"])
    worst_days_all.write_csv(paths["worst_days"])
    worst_industry_all.write_csv(paths["worst_day_industry"])
    worst_symbol_all.write_csv(paths["worst_day_symbol"])
    quality.write_csv(paths["quality_checkpoints"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_daily": str(daily_path),
            "source_orders": str(orders_path),
            "focus_scenarios": FOCUS_SCENARIOS,
            "research_sources": RESEARCH_SOURCES,
            "note": "Drawdown attribution only; no strategy parameter changes.",
        },
    )
    report_path = write_report(
        scenario_summary,
        drawdowns_all,
        worst_days_all,
        state_summaries,
        worst_industry_all,
        worst_symbol_all,
        drawdown_period_industry,
        quality,
        paths,
    )
    print(json.dumps(scenario_summary.to_dicts(), ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
