from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_market_state_overlay import build_prev_close_market_state
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import (
    ACCOUNT_SIZE_CNY,
    HIGH_RETURN_TARGET,
    MAX_DRAWDOWN_LIMIT,
    build_concentrated_selected,
    build_target_weights,
    read_source_candidates,
    summarize_daily_extra,
    write_json,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import FEATURE, HORIZON, NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_high_return_state_throttle_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_30w_high_return_state_throttle_v1"

TOP_KS: tuple[int, ...] = (5, 8)
BASKET_GROSS_WEIGHTS: tuple[float, ...] = (0.70, 1.00)
MAX_PER_INDUSTRY_VALUES: tuple[int, ...] = (1, 2)
OVERLAYS: tuple[tuple[str, str], ...] = (
    ("base", "不做市场状态降权。"),
    ("breadth_or_index_half", "若前一日市场宽度弱或中证1000跌超1%，下一目标日权重乘0.50。"),
    ("breadth_index_tiered", "若前一日宽度弱且指数跌超1%权重乘0.25，仅命中一个条件乘0.50。"),
    ("index_down_quarter_weak_half", "若前一日中证1000跌超1%权重乘0.25；否则若宽度弱乘0.50。"),
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "SSE trading mechanism: board lot constraints",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
    (
        "SZSE board lot rules",
        "https://www.szse.cn/enSzhk/tradeMechanism/tradeRules/index.html",
    ),
    (
        "Position sizing for systematic trading",
        "https://www.monstertradingsystems.com/position-sizing-models-for-systematic-trading/",
    ),
    (
        "Mean reversion position sizing risks",
        "https://setupalpha.com/blogs/articles/mean-reversion-strategy-failures-complete-fix-guide",
    ),
)


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result == result else default


def overlay_scale(name: str, weak_breadth: bool, index_down: bool) -> float:
    if name == "base":
        return 1.0
    if name == "breadth_or_index_half":
        return 0.5 if weak_breadth or index_down else 1.0
    if name == "breadth_index_tiered":
        if weak_breadth and index_down:
            return 0.25
        if weak_breadth or index_down:
            return 0.5
        return 1.0
    if name == "index_down_quarter_weak_half":
        if index_down:
            return 0.25
        if weak_breadth:
            return 0.5
        return 1.0
    raise ValueError(f"Unknown overlay: {name}")


def apply_overlay(target_weights: pl.DataFrame, state: pl.DataFrame, shape_scenario: str, overlay_name: str) -> pl.DataFrame:
    state_small = state.select(
        [
            "target_date",
            "prev_close_breadth_state",
            "prev_close_index_state",
            "prev_close_weak_breadth_flag",
            "prev_close_index_down_flag",
            "prev_universe_up_ratio",
            "prev_benchmark_close_to_close_ret",
        ]
    )
    rows: list[dict[str, Any]] = []
    for row in (
        target_weights.filter(pl.col("scenario") == shape_scenario)
        .join(state_small, on="target_date", how="left")
        .sort(["target_date", "industry", "symbol"])
        .iter_rows(named=True)
    ):
        weak_breadth = bool(row.get("prev_close_weak_breadth_flag") or False)
        index_down = bool(row.get("prev_close_index_down_flag") or False)
        scale = overlay_scale(overlay_name, weak_breadth, index_down)
        current = dict(row)
        current["shape_scenario"] = shape_scenario
        current["overlay_name"] = overlay_name
        current["overlay_scale"] = scale
        current["base_target_weight"] = current["target_weight"]
        current["target_weight"] = to_float(current["target_weight"]) * scale
        current["scenario"] = f"{shape_scenario}_{overlay_name}"
        rows.append(current)
    return pl.DataFrame(rows).sort(["scenario", "target_date", "symbol"]) if rows else pl.DataFrame()


def replay_variant(
    scenario: str,
    shape_meta: dict[str, Any],
    overlay_name: str,
    overlay_desc: str,
    scaled_targets: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
) -> tuple[dict[str, Any], pl.DataFrame, pl.DataFrame]:
    scenario_targets = scaled_targets.filter(pl.col("scenario") == scenario).drop("scenario")
    target_maps = lot.build_target_maps(scenario_targets)
    dates = lot.build_tracking_dates(scenario_targets, benchmark_df)
    orders, daily, _curve = lot.replay_lot_account(target_maps, dates, exec_info)
    if not orders.is_empty():
        orders = orders.with_columns(pl.lit(scenario).alias("scenario"))
    if not daily.is_empty():
        daily = daily.with_columns(pl.lit(scenario).alias("scenario"))
    summary = lot.summarize_orders(orders, daily)
    summary = summarize_daily_extra(summary, daily)
    summary.update(shape_meta)
    summary["scenario"] = scenario
    summary["overlay_name"] = overlay_name
    summary["overlay_description"] = overlay_desc
    summary["avg_overlay_scale"] = to_float(scenario_targets["overlay_scale"].mean()) if "overlay_scale" in scenario_targets.columns else 1.0
    summary["scaled_target_day_ratio"] = (
        scenario_targets.group_by("target_date")
        .agg(pl.col("overlay_scale").first().alias("overlay_scale"))
        .filter(pl.col("overlay_scale") < 0.999999)
        .height
        / daily.height
        if not daily.is_empty() and "overlay_scale" in scenario_targets.columns
        else 0.0
    )
    return summary, orders, daily


def build_yearly(daily: pl.DataFrame) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()
    return (
        daily.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["scenario", "year"])
        .agg(
            ((1 + pl.col("strategy_daily_ret_min_fee")).product() - 1).alias("year_return_min_fee"),
            pl.col("drawdown_min_fee").min().alias("year_curve_drawdown_min_fee"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            (pl.col("zero_lot_target_count").sum() / pl.col("target_symbol_count").sum()).alias("zero_lot_target_ratio"),
        )
        .sort(["scenario", "year"])
    )


def build_quality(summary: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in summary.iter_rows(named=True):
        scenario = row["scenario"]
        total_return = to_float(row.get("total_return_min_fee"))
        max_dd = to_float(row.get("max_drawdown_min_fee"))
        zero_ratio = to_float(row.get("zero_lot_target_ratio"))
        latest_capture = to_float(row.get("latest_exposure_capture_ratio"))
        rows.extend(
            [
                {
                    "scenario": scenario,
                    "checkpoint": "max_drawdown_within_20pct",
                    "status": "pass" if max_dd >= MAX_DRAWDOWN_LIMIT else "fail",
                    "value": pct(max_dd),
                    "expected": ">=-20%",
                    "note": "用户明确可接受的最大回撤边界。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "high_return_target",
                    "status": "pass" if total_return >= HIGH_RETURN_TARGET else "warn",
                    "value": pct(total_return),
                    "expected": ">=100%",
                    "note": "高收益目标，必须和回撤/稳定性一起看。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "zero_lot_target_ratio",
                    "status": "fail" if zero_ratio > 0.20 else "warn" if zero_ratio > 0.10 else "pass",
                    "value": pct(zero_ratio),
                    "expected": "<=10% preferred, <=20% hard",
                    "note": "30万账户仍需减少买不到一手。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "latest_exposure_capture_ratio",
                    "status": "fail" if latest_capture < 0.50 else "warn" if latest_capture < 0.70 else "pass",
                    "value": pct(latest_capture),
                    "expected": ">=70% preferred, >=50% hard",
                    "note": "最新目标日取整后目标市值捕获率。",
                },
            ]
        )
    return pl.DataFrame(rows).sort(["scenario", "checkpoint"])


def write_report(summary: pl.DataFrame, quality: pl.DataFrame, yearly: pl.DataFrame, paths: dict[str, Path]) -> Path:
    report_path = paths["report"]
    pass_dd = summary.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT).sort(
        ["total_return_min_fee", "sharpe_min_fee"], descending=[True, True]
    )
    best = pass_dd.row(0, named=True) if pass_dd.height else None
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    lines = [
        "# 股票震荡liquid_q3 30万高收益状态降权 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：固定信号和少数组合形状，测试前一日市场状态降权能否把高暴露版本压回20%回撤以内。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；最大回撤目标：`20%`以内。",
        f"- 形状：top_k `{TOP_KS}`，信号篮子总暴露 `{BASKET_GROSS_WEIGHTS}`，单行业最多 `{MAX_PER_INDUSTRY_VALUES}`只。",
        "- A/B判断：30万候选研究，不接入第78，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 小账户高收益必须靠较高暴露或集中度，但均值回归在系统性下跌中容易被打穿。",
        "- 更合理的系统形态是：固定alpha + 账户可承载的集中组合 + 前一日市场状态降权。",
        "- 本阶段仍是样本内压力测试，若出现候选，下一步必须做walk-forward。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(["", "## 核心摘要", ""])
    if best:
        lines.append(
            f"- 回撤20%以内最高收益候选：`{best['scenario']}`，期末权益`{best['final_equity_min_fee']:.4f}`，总收益`{pct(best['total_return_min_fee'])}`，最大回撤`{pct(best['max_drawdown_min_fee'])}`，Sharpe `{best['sharpe_min_fee']:.3f}`。"
        )
    else:
        lines.append("- 回撤20%以内候选：本轮无。")
    lines.extend(
        [
            f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
            "- 判断：状态降权若只能牺牲收益而不能显著压回撤，就说明30万高收益目标需要换信号或换周期。",
            "",
            "## 场景汇总",
            "",
            markdown_table(
                summary,
                [
                    "scenario",
                    "shape_top_k",
                    "shape_basket_gross_weight",
                    "shape_max_per_industry",
                    "overlay_name",
                    "avg_overlay_scale",
                    "scaled_target_day_ratio",
                    "final_equity_min_fee",
                    "total_return_min_fee",
                    "max_drawdown_min_fee",
                    "sharpe_min_fee",
                    "zero_lot_target_ratio",
                    "latest_exposure_capture_ratio",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "min_fee_equity_gap",
                ],
                max_rows=120,
            ),
            "",
            "## 回撤20%以内候选",
            "",
            "无数据"
            if pass_dd.is_empty()
            else markdown_table(
                pass_dd,
                [
                    "scenario",
                    "shape_top_k",
                    "shape_basket_gross_weight",
                    "shape_max_per_industry",
                    "overlay_name",
                    "final_equity_min_fee",
                    "total_return_min_fee",
                    "max_drawdown_min_fee",
                    "sharpe_min_fee",
                    "zero_lot_target_ratio",
                    "latest_exposure_capture_ratio",
                ],
                max_rows=80,
            ),
            "",
            "## 年度拆分",
            "",
            markdown_table(
                yearly,
                [
                    "scenario",
                    "year",
                    "year_return_min_fee",
                    "year_curve_drawdown_min_fee",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "zero_lot_target_ratio",
                ],
                max_rows=220,
            ),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, ["scenario", "checkpoint", "status", "value", "expected", "note"], max_rows=220),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：有风险。",
            "- 原因：在高收益和20%回撤约束下继续加状态阀门，容易变成样本内修补；因此只用少数已研究过的前一日市场状态变量。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：仍有风险。",
            "- 原因：任何通过的状态降权候选都必须再做walk-forward，否则不能认为可穿越周期。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第一版结构网格显示收益和回撤冲突，状态降权是下一条最自然路径。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：取决于是否出现回撤20%以内且收益明显高于低暴露版本的候选。",
            "- 原因：若状态降权无效，应换信号/周期，而不是继续堆过滤器。",
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
    base = read_source_candidates()
    shape_frames: list[pl.DataFrame] = []
    shape_meta: dict[str, dict[str, Any]] = {}
    for top_k in TOP_KS:
        for gross in BASKET_GROSS_WEIGHTS:
            for max_industry in MAX_PER_INDUSTRY_VALUES:
                frame = build_concentrated_selected(base, top_k, gross, max_industry)
                scenario = frame["scenario"][0]
                shape_meta[scenario] = frame.select(
                    "shape_top_k", "shape_basket_gross_weight", "shape_max_per_industry", "scenario_description"
                ).row(0, named=True)
                shape_frames.append(frame)
    selected = pl.concat(shape_frames, how="vertical")
    target_weights = build_target_weights(selected)
    stock_df, benchmark_df = load_panels()
    state = build_prev_close_market_state(benchmark_df, stock_df)
    exec_info = build_exec_info(stock_df)

    scaled_frames: list[pl.DataFrame] = []
    summaries: list[dict[str, Any]] = []
    orders_frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    for shape_scenario, meta in shape_meta.items():
        for overlay_name, overlay_desc in OVERLAYS:
            scaled = apply_overlay(target_weights, state, shape_scenario, overlay_name)
            scenario = f"{shape_scenario}_{overlay_name}"
            summary, orders, daily = replay_variant(
                scenario,
                meta,
                overlay_name,
                overlay_desc,
                scaled,
                benchmark_df,
                exec_info,
            )
            scaled_frames.append(scaled)
            summaries.append(summary)
            if not orders.is_empty():
                orders_frames.append(orders)
            if not daily.is_empty():
                daily_frames.append(daily)

    summary = pl.DataFrame(summaries).sort(
        ["total_return_min_fee", "max_drawdown_min_fee", "sharpe_min_fee"], descending=[True, True, True]
    )
    quality = build_quality(summary)
    scaled_targets = pl.concat(scaled_frames, how="vertical") if scaled_frames else pl.DataFrame()
    orders = pl.concat(orders_frames, how="vertical") if orders_frames else pl.DataFrame()
    daily = pl.concat(daily_frames, how="vertical") if daily_frames else pl.DataFrame()
    yearly = build_yearly(daily)

    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "scaled_targets": OUTPUT_DIR / f"{PREFIX}_scaled_targets.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "market_state": OUTPUT_DIR / f"{PREFIX}_market_state.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary.write_csv(paths["summary"])
    quality.write_csv(paths["quality"])
    yearly.write_csv(paths["yearly"])
    scaled_targets.write_csv(paths["scaled_targets"])
    orders.write_csv(paths["orders"])
    daily.write_csv(paths["daily"])
    state.write_csv(paths["market_state"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "feature": FEATURE,
            "horizon": HORIZON,
            "top_ks": TOP_KS,
            "basket_gross_weights": BASKET_GROSS_WEIGHTS,
            "max_per_industry_values": MAX_PER_INDUSTRY_VALUES,
            "overlays": OVERLAYS,
            "research_sources": RESEARCH_SOURCES,
        },
    )
    report_path = write_report(summary, quality, yearly, paths)
    print(f"report={report_path}")
    print(summary)
    print(quality)


if __name__ == "__main__":
    main()
