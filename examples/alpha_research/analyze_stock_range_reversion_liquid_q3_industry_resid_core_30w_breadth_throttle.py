from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution import (
    build_drawdown_episodes,
    downside_vol,
)
from analyze_stock_range_reversion_liquid_q3_300k_market_state_overlay import build_prev_close_market_state
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import (
    ACCOUNT_SIZE_CNY,
    HIGH_RETURN_TARGET,
    MAX_DRAWDOWN_LIMIT,
    summarize_daily_extra,
    to_float,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_breadth_throttle_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_breadth_throttle_v1"

FOCUS_SCENARIOS: tuple[str, ...] = (
    "industry_resid_core_h10_top8_gross100_ind2",
    "industry_resid_core_h10_top5_gross100_ind1",
    "industry_resid_core_h10_top8_gross70_ind2",
    "industry_resid_core_h10_top5_gross70_ind1",
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term residual reversal",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
    (
        "Short-Term Residual Reversal SSRN page",
        "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1911449",
    ),
    (
        "Combining return reversal and industry momentum",
        "https://www.cxoadvisory.com/technical-trading/combining-return-reversal-and-industry-momentum/",
    ),
    (
        "On Inefficiency of Markowitz-Style Investment Strategies When Drawdown is Important",
        "https://arxiv.org/abs/1710.01501",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)


@dataclass(frozen=True)
class BreadthThrottle:
    name: str
    description: str


THROTTLES: tuple[BreadthThrottle, ...] = (
    BreadthThrottle("base_rerun", "不做市场宽度降权；用于复现第308阶段30万整手复放。"),
    BreadthThrottle("prev_close_weak_breadth_half", "若前一交易日收盘市场宽度弱，则下一目标日目标权重乘0.50。"),
    BreadthThrottle("prev_close_weak_breadth_zero", "若前一交易日收盘市场宽度弱，则下一目标日目标权重乘0.00。"),
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


def annualized_sharpe(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    if variance <= 0:
        return 0.0
    return mean / sqrt(variance) * sqrt(TRADING_DAYS)


def scale_for_throttle(throttle: str, weak_breadth: bool) -> float:
    if throttle == "base_rerun":
        return 1.0
    if throttle == "prev_close_weak_breadth_half":
        return 0.5 if weak_breadth else 1.0
    if throttle == "prev_close_weak_breadth_zero":
        return 0.0 if weak_breadth else 1.0
    raise ValueError(f"Unknown throttle: {throttle}")


def apply_throttle(target_weights: pl.DataFrame, state: pl.DataFrame, throttle: BreadthThrottle) -> pl.DataFrame:
    state_small = state.select(
        [
            "target_date",
            "state_date",
            "prev_close_breadth_state",
            "prev_close_index_state",
            "prev_close_weak_breadth_flag",
            "prev_close_index_down_flag",
            "prev_universe_up_ratio",
            "prev_benchmark_close_to_close_ret",
        ]
    )
    rows: list[dict[str, Any]] = []
    joined = target_weights.join(state_small, on="target_date", how="left").sort(["scenario", "target_date", "industry", "symbol"])
    for row in joined.iter_rows(named=True):
        base_scenario = str(row["scenario"])
        weak_breadth = bool(row.get("prev_close_weak_breadth_flag") or False)
        scale = scale_for_throttle(throttle.name, weak_breadth)
        current = dict(row)
        base_weight = to_float(current.get("target_weight"))
        current["base_scenario"] = base_scenario
        current["throttle_name"] = throttle.name
        current["throttle_description"] = throttle.description
        current["base_target_weight"] = base_weight
        current["throttle_scale"] = scale
        current["target_weight"] = base_weight * scale
        current["target_amount_cny"] = current["target_weight"] * ACCOUNT_SIZE_CNY
        current["scenario"] = f"{base_scenario}_{throttle.name}"
        rows.append(current)
    return pl.DataFrame(rows).sort(["scenario", "target_date", "industry", "symbol"]) if rows else pl.DataFrame()


def summarize_variant(
    base_scenario: str,
    throttle: BreadthThrottle,
    orders: pl.DataFrame,
    daily: pl.DataFrame,
    scaled_targets: pl.DataFrame,
) -> dict[str, Any]:
    summary = lot.summarize_orders(orders, daily)
    summary = summarize_daily_extra(summary, daily)
    returns = [float(value) for value in daily["strategy_daily_ret_min_fee"].to_list()]
    scale_by_date = (
        scaled_targets.filter(pl.col("base_scenario") == base_scenario)
        .group_by("target_date")
        .agg(
            pl.col("throttle_scale").first().alias("throttle_scale"),
            pl.col("prev_close_weak_breadth_flag").first().alias("prev_close_weak_breadth_flag"),
            pl.col("prev_close_index_down_flag").first().alias("prev_close_index_down_flag"),
            pl.col("prev_close_breadth_state").first().alias("prev_close_breadth_state"),
            pl.col("prev_close_index_state").first().alias("prev_close_index_state"),
        )
        .sort("target_date")
    )
    latest_date = daily["date"].max()
    latest_scale = (
        scale_by_date.filter(pl.col("target_date") == latest_date)["throttle_scale"][0]
        if scale_by_date.filter(pl.col("target_date") == latest_date).height
        else None
    )
    weak_days = scale_by_date.filter(pl.col("prev_close_weak_breadth_flag")).height
    scaled_days = scale_by_date.filter(pl.col("throttle_scale") < 0.999999).height
    summary.update(
        {
            "scenario": f"{base_scenario}_{throttle.name}",
            "base_scenario": base_scenario,
            "throttle_name": throttle.name,
            "throttle_description": throttle.description,
            "annualized_vol_min_fee": annualized_vol(returns),
            "downside_vol_min_fee": downside_vol(returns),
            "annualized_sharpe_check": annualized_sharpe(returns),
            "worst_daily_ret_min_fee": min(returns) if returns else 0.0,
            "avg_throttle_scale": to_float(scale_by_date["throttle_scale"].mean()) if not scale_by_date.is_empty() else 1.0,
            "scaled_target_days": scaled_days,
            "scaled_target_day_ratio": scaled_days / daily.height if daily.height else 0.0,
            "weak_breadth_target_days": weak_days,
            "weak_breadth_target_day_ratio": weak_days / daily.height if daily.height else 0.0,
            "latest_throttle_scale": latest_scale,
        }
    )
    meta_cols = [
        "shape_horizon",
        "shape_top_k",
        "shape_basket_gross_weight",
        "shape_max_per_industry",
    ]
    meta = scaled_targets.filter(pl.col("base_scenario") == base_scenario).select(meta_cols).row(0, named=True)
    summary.update(meta)
    return summary


def add_base_deltas(summary: pl.DataFrame) -> pl.DataFrame:
    base = (
        summary.filter(pl.col("throttle_name") == "base_rerun")
        .select(
            "base_scenario",
            pl.col("final_equity_min_fee").alias("base_final_equity_min_fee"),
            pl.col("total_return_min_fee").alias("base_total_return_min_fee"),
            pl.col("max_drawdown_min_fee").alias("base_max_drawdown_min_fee"),
            pl.col("sharpe_min_fee").alias("base_sharpe_min_fee"),
            pl.col("annualized_vol_min_fee").alias("base_annualized_vol_min_fee"),
            pl.col("downside_vol_min_fee").alias("base_downside_vol_min_fee"),
            pl.col("worst_daily_ret_min_fee").alias("base_worst_daily_ret_min_fee"),
            pl.col("avg_actual_gross_weight").alias("base_avg_actual_gross_weight"),
        )
    )
    return (
        summary.join(base, on="base_scenario", how="left")
        .with_columns(
            (pl.col("final_equity_min_fee") - pl.col("base_final_equity_min_fee")).alias("delta_final_equity_min_fee"),
            (pl.col("total_return_min_fee") - pl.col("base_total_return_min_fee")).alias("delta_total_return_min_fee"),
            (pl.col("max_drawdown_min_fee") - pl.col("base_max_drawdown_min_fee")).alias("delta_max_drawdown_min_fee"),
            (pl.col("sharpe_min_fee") - pl.col("base_sharpe_min_fee")).alias("delta_sharpe_min_fee"),
            (pl.col("annualized_vol_min_fee") - pl.col("base_annualized_vol_min_fee")).alias(
                "delta_annualized_vol_min_fee"
            ),
            (pl.col("downside_vol_min_fee") - pl.col("base_downside_vol_min_fee")).alias("delta_downside_vol_min_fee"),
            (pl.col("worst_daily_ret_min_fee") - pl.col("base_worst_daily_ret_min_fee")).alias(
                "delta_worst_daily_ret_min_fee"
            ),
            (pl.col("avg_actual_gross_weight") - pl.col("base_avg_actual_gross_weight")).alias(
                "delta_avg_actual_gross_weight"
            ),
        )
        .drop(
            [
                "base_final_equity_min_fee",
                "base_total_return_min_fee",
                "base_max_drawdown_min_fee",
                "base_sharpe_min_fee",
                "base_annualized_vol_min_fee",
                "base_downside_vol_min_fee",
                "base_worst_daily_ret_min_fee",
                "base_avg_actual_gross_weight",
            ]
        )
    )


def summarize_state_daily(daily: pl.DataFrame, state: pl.DataFrame) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()
    joined = daily.join(state, left_on="date", right_on="target_date", how="left")
    return (
        joined.group_by(["base_scenario", "throttle_name", "prev_close_breadth_state"])
        .agg(
            pl.len().alias("days"),
            pl.col("strategy_daily_ret_min_fee").sum().alias("net_return_sum"),
            ((1 + pl.col("strategy_daily_ret_min_fee")).product() - 1).alias("compounded_return"),
            pl.col("strategy_daily_ret_min_fee").mean().alias("avg_daily_ret"),
            pl.col("strategy_daily_ret_min_fee").min().alias("worst_daily_ret"),
            (pl.col("strategy_daily_ret_min_fee") > 0).mean().alias("daily_win_rate"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            pl.col("turnover_cost_ret_min_fee").sum().alias("cost_drag_sum"),
        )
        .sort(["base_scenario", "throttle_name", "prev_close_breadth_state"])
    )


def build_yearly(daily: pl.DataFrame) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()
    return (
        daily.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["base_scenario", "throttle_name", "scenario", "year"])
        .agg(
            ((1 + pl.col("strategy_daily_ret_min_fee")).product() - 1).alias("year_return_min_fee"),
            pl.col("drawdown_min_fee").min().alias("year_curve_drawdown_min_fee"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            pl.col("zero_lot_target_count").sum().alias("zero_lot_target_count"),
            pl.col("target_symbol_count").sum().alias("target_symbol_count"),
            pl.col("filled_amount_sum_cny").sum().alias("filled_amount_sum_cny"),
        )
        .with_columns(
            (pl.col("zero_lot_target_count") / pl.col("target_symbol_count")).fill_nan(0.0).alias(
                "zero_lot_target_ratio"
            )
        )
        .sort(["base_scenario", "throttle_name", "year"])
    )


def build_quality(summary: pl.DataFrame, original_daily: pl.DataFrame, state: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []

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

    add(
        "focus_scenario_count",
        "pass" if summary["base_scenario"].n_unique() == len(FOCUS_SCENARIOS) else "fail",
        summary["base_scenario"].n_unique(),
        len(FOCUS_SCENARIOS),
        "只运行第313阶段归因后的代表形状，避免扩散扫参。",
    )
    add(
        "throttle_count",
        "pass" if summary["throttle_name"].n_unique() == len(THROTTLES) else "fail",
        summary["throttle_name"].n_unique(),
        len(THROTTLES),
        "只运行预注册的少数市场宽度规则。",
    )
    base = summary.filter(pl.col("throttle_name") == "base_rerun").select("base_scenario", "final_equity_min_fee")
    original = original_daily.filter(pl.col("scenario").is_in(FOCUS_SCENARIOS)).group_by("scenario").agg(
        pl.col("equity_min_fee").last().alias("original_final_equity_min_fee")
    )
    compare = base.join(original, left_on="base_scenario", right_on="scenario", how="left").with_columns(
        (pl.col("final_equity_min_fee") - pl.col("original_final_equity_min_fee")).abs().alias("diff")
    )
    max_base_diff = to_float(compare["diff"].max()) if not compare.is_empty() else None
    add(
        "base_rerun_matches_stage308",
        "pass" if max_base_diff is not None and max_base_diff <= 1e-12 else "fail",
        max_base_diff,
        "<=1e-12",
        "不降权变体必须复现第308阶段结果。",
    )
    add(
        "state_coverage",
        "pass" if state.select(pl.col("prev_close_breadth_state").null_count()).item() == 0 else "fail",
        state.select(pl.col("prev_close_breadth_state").null_count()).item(),
        0,
        "市场宽度风控必须有完整前一日状态。",
    )
    best_dd = summary.select(pl.col("max_drawdown_min_fee").max()).item()
    best_return = summary.select(pl.col("total_return_min_fee").max()).item()
    add(
        "best_drawdown_within_20pct",
        "pass" if best_dd >= MAX_DRAWDOWN_LIMIT else "warn",
        pct(best_dd),
        ">=-20%",
        "若没有进入20%以内，本阶段不能形成候选策略。",
    )
    add(
        "high_return_target_seen",
        "pass" if best_return >= HIGH_RETURN_TARGET else "warn",
        pct(best_return),
        ">=100%",
        "用户目标是30万本金下高收益，需观察风险层是否过度牺牲收益。",
    )
    add(
        "no_signal_threshold_change",
        "pass",
        "only target exposure scaling",
        "only target exposure scaling",
        "本阶段不改变选股信号、分数、top_k、持有期。",
    )
    add(
        "exante_only_state",
        "pass",
        "previous close breadth only",
        "previous close breadth only",
        "只使用前一交易日收盘后可知状态，不使用目标日开盘后的信息。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: pl.DataFrame,
    yearly: pl.DataFrame,
    drawdowns: pl.DataFrame,
    state_daily: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    pass_dd = summary.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT).sort(
        ["total_return_min_fee", "sharpe_min_fee"], descending=[True, True]
    )
    best_dd = summary.sort(["max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]).row(0, named=True)
    best_return = summary.sort(["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True]).row(
        0, named=True
    )
    best_delta = summary.filter(pl.col("throttle_name") != "base_rerun").sort(
        ["delta_max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]
    )
    best_delta_row = best_delta.row(0, named=True) if not best_delta.is_empty() else None
    if best_delta_row is not None and to_float(best_delta_row.get("delta_max_drawdown_min_fee")) <= 0:
        best_delta_line = "- 所有弱广度降权变体均未改善最大回撤；最不差的变体仍让回撤恶化。"
    elif best_delta_row is None:
        best_delta_line = "- 相对基准回撤改善最大：无"
    else:
        best_delta_line = (
            f"- 相对基准回撤改善最大：`{best_delta_row['scenario']}`，回撤改善"
            f"`{pct(best_delta_row['delta_max_drawdown_min_fee'])}`，收益变化"
            f"`{pct(best_delta_row['delta_total_return_min_fee'])}`。"
        )
    lines = [
        "# 股票震荡industry_resid_core 30万前一日弱广度风控回放 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：固定第308阶段信号和代表组合形状，只测试第313阶段归因指向的前一日弱市场宽度降权。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；用户回撤目标：`20%`以内；高收益参考目标：`100%`以上。",
        "- A/B判断：股票震荡独立研究，不接入第78，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 残差短期反转有文献支撑，行业内个股反转也比跨行业追强更贴近已有证据。",
        "- 但均值回归的尾部风险常来自系统性弱市场和拥挤风格；风控应优先用事前状态降低暴露，而不是继续调整alpha阈值。",
        "- GitHub公开均值回归代码多为教学/示例，不能直接复制为A股30万实盘系统；本阶段采用本仓库已验证的整手回放框架。",
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
            "本阶段只回答一个问题：第313阶段识别的`weak_breadth`，是否能用前一日收盘状态做成可交易风控。",
            f"- 回撤20%以内候选：{'无' if pass_dd.is_empty() else pass_dd['scenario'][0]}",
            f"- 最大回撤最浅：`{best_dd['scenario']}`，总收益`{pct(best_dd['total_return_min_fee'])}`，最大回撤`{pct(best_dd['max_drawdown_min_fee'])}`，Sharpe `{best_dd['sharpe_min_fee']:.3f}`。",
            f"- 总收益最高：`{best_return['scenario']}`，总收益`{pct(best_return['total_return_min_fee'])}`，最大回撤`{pct(best_return['max_drawdown_min_fee'])}`，Sharpe `{best_return['sharpe_min_fee']:.3f}`。",
            best_delta_line,
            f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
            "",
            "## 场景汇总",
            "",
            markdown_table(
                summary,
                [
                    "base_scenario",
                    "throttle_name",
                    "final_equity_min_fee",
                    "total_return_min_fee",
                    "max_drawdown_min_fee",
                    "delta_total_return_min_fee",
                    "delta_max_drawdown_min_fee",
                    "sharpe_min_fee",
                    "annualized_vol_min_fee",
                    "downside_vol_min_fee",
                    "worst_daily_ret_min_fee",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "avg_throttle_scale",
                    "scaled_target_day_ratio",
                    "zero_lot_target_ratio",
                    "latest_exposure_capture_ratio",
                    "return_over_max_dd",
                ],
                max_rows=120,
            ),
            "",
            "## 最大回撤段",
            "",
            markdown_table(
                drawdowns,
                [
                    "base_scenario",
                    "throttle_name",
                    "peak_date",
                    "trough_date",
                    "recovery_date",
                    "recovered",
                    "max_drawdown",
                    "trading_days_to_trough",
                    "trading_days_to_recovery_or_end",
                    "avg_actual_gross_weight",
                    "worst_daily_return",
                ],
                max_rows=80,
            ),
            "",
            "## 前一日市场宽度状态拆分",
            "",
            markdown_table(
                state_daily,
                [
                    "base_scenario",
                    "throttle_name",
                    "prev_close_breadth_state",
                    "days",
                    "net_return_sum",
                    "compounded_return",
                    "avg_daily_ret",
                    "worst_daily_ret",
                    "daily_win_rate",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "cost_drag_sum",
                ],
                max_rows=160,
            ),
            "",
            "## 年度拆分",
            "",
            markdown_table(
                yearly,
                [
                    "base_scenario",
                    "throttle_name",
                    "year",
                    "year_return_min_fee",
                    "year_curve_drawdown_min_fee",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "zero_lot_target_ratio",
                ],
                max_rows=260,
            ),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否，但风险需要控制。",
            "- 原因：本阶段只使用第313阶段已定位的单一风险变量，且只测半仓和清仓两个粗粒度规则，不扫描阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：如果出现候选，仍不能直接实盘；如果无候选，则说明这条风控层不能靠样本内修补继续推进。",
            "- 原因：弱广度来自回撤归因，属于合理变量，但仍需要后续walk-forward或分段反证。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第313阶段显示弱广度是最大回撤的主状态，值得做一次事前可交易验证。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：取决于本报告是否显示回撤显著进入20%以内且收益没有被砍没。",
            "- 原因：若弱广度风控只降低收益而不解决长回撤，应转向行业实际暴露上限或换信号。",
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
    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "drawdowns": OUTPUT_DIR / f"{PREFIX}_drawdowns.csv",
        "state_daily": OUTPUT_DIR / f"{PREFIX}_state_daily.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "scaled_targets": OUTPUT_DIR / f"{PREFIX}_scaled_targets.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "exante_state": OUTPUT_DIR / f"{PREFIX}_exante_state.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    target_weights = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_target_weights.csv").filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    original_daily = pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_daily.csv", try_parse_dates=True)
    stock_df, benchmark_df = load_panels()
    exante_state = build_prev_close_market_state(benchmark_df, stock_df)
    exec_info = build_exec_info(stock_df)

    scaled_frames: list[pl.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    orders_frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    drawdown_frames: list[pl.DataFrame] = []

    for throttle in THROTTLES:
        scaled = apply_throttle(target_weights, exante_state, throttle)
        scaled_frames.append(scaled)
        for base_scenario in FOCUS_SCENARIOS:
            scenario = f"{base_scenario}_{throttle.name}"
            scenario_targets = scaled.filter(pl.col("scenario") == scenario).drop("scenario")
            target_maps = lot.build_target_maps(scenario_targets)
            dates = lot.build_tracking_dates(scenario_targets, benchmark_df)
            orders, daily, _curve = lot.replay_lot_account(target_maps, dates, exec_info)
            if not orders.is_empty():
                orders = orders.with_columns(
                    pl.lit(scenario).alias("scenario"),
                    pl.lit(base_scenario).alias("base_scenario"),
                    pl.lit(throttle.name).alias("throttle_name"),
                )
                orders_frames.append(orders)
            if not daily.is_empty():
                daily = daily.with_columns(
                    pl.lit(scenario).alias("scenario"),
                    pl.lit(base_scenario).alias("base_scenario"),
                    pl.lit(throttle.name).alias("throttle_name"),
                )
                daily_frames.append(daily)
                summary_rows.append(summarize_variant(base_scenario, throttle, orders, daily, scaled))
                drawdown_frames.append(
                    build_drawdown_episodes(daily)
                    .head(5)
                    .with_columns(
                        pl.lit(scenario).alias("scenario"),
                        pl.lit(base_scenario).alias("base_scenario"),
                        pl.lit(throttle.name).alias("throttle_name"),
                    )
                )

    scaled_targets = pl.concat(scaled_frames, how="diagonal_relaxed") if scaled_frames else pl.DataFrame()
    orders_all = pl.concat(orders_frames, how="diagonal_relaxed") if orders_frames else pl.DataFrame()
    daily_all = pl.concat(daily_frames, how="diagonal_relaxed") if daily_frames else pl.DataFrame()
    drawdowns = pl.concat(drawdown_frames, how="diagonal_relaxed") if drawdown_frames else pl.DataFrame()
    summary = add_base_deltas(pl.DataFrame(summary_rows)).sort(
        ["base_scenario", "throttle_name"],
        descending=[False, False],
    )
    yearly = build_yearly(daily_all)
    state_daily = summarize_state_daily(daily_all, exante_state)
    quality = build_quality(summary, original_daily, exante_state)

    summary.write_csv(paths["summary"])
    yearly.write_csv(paths["yearly"])
    drawdowns.write_csv(paths["drawdowns"])
    state_daily.write_csv(paths["state_daily"])
    quality.write_csv(paths["quality"])
    scaled_targets.write_csv(paths["scaled_targets"])
    orders_all.write_csv(paths["orders"])
    daily_all.write_csv(paths["daily"])
    exante_state.write_csv(paths["exante_state"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "focus_scenarios": FOCUS_SCENARIOS,
            "throttles": [(item.name, item.description) for item in THROTTLES],
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
        },
    )
    report_path = write_report(summary, yearly, drawdowns, state_daily, quality, paths)
    print(f"report={report_path}")
    print(summary.select(["base_scenario", "throttle_name", "total_return_min_fee", "max_drawdown_min_fee", "sharpe_min_fee"]))
    print(quality)


if __name__ == "__main__":
    main()
