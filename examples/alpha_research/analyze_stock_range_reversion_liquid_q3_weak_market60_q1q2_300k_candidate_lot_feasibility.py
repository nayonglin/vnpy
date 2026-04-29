from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import (
    ACCOUNT_SIZE_CNY,
    BOARD_LOT_SHARES,
    MIN_COMMISSION_CNY,
    build_latest_holdings,
    build_order_summary,
    build_quality_checkpoints,
    build_target_maps,
    build_tracking_dates,
    replay_lot_account,
    summarize_orders,
    write_json,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    HORIZON,
    NATIVE_RESULTS_DIR,
    build_lots,
    build_symbol_daily,
    pct,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_momentum_pullback_attribution_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_momentum_pullback_attribution_v1"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_weak_market60_q1q2_300k_candidate_lot_feasibility_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_weak_market60_q1q2_300k_candidate_lot_feasibility_v1"

PRIMARY_SCENARIO: str = "weak_market60_q1q2_diagnostic"
REALLOCATED_SCENARIO: str = "weak_market60_q1q2_reallocated"
CANDIDATE_SCENARIOS: tuple[str, ...] = (PRIMARY_SCENARIO, REALLOCATED_SCENARIO)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "SSE trading mechanism: board lot buy orders",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
    (
        "SZSE trading rules: board lots",
        "https://www.szse.cn/enSzhk/tradeMechanism/tradeRules/index.html",
    ),
    (
        "SSE trading fees reference",
        "https://english.sse.com.cn/start/taxes/",
    ),
)


def read_selected() -> pl.DataFrame:
    return pl.read_csv(
        SOURCE_DIR / f"{SOURCE_PREFIX}_selected_variants.csv",
        try_parse_dates=True,
        schema_overrides={
            "symbol": pl.Utf8,
            "vt_symbol": pl.Utf8,
            "bs_code": pl.Utf8,
            "code": pl.Utf8,
        },
    ).filter(pl.col("scenario").is_in(CANDIDATE_SCENARIOS))


def build_candidate_target_weights(selected: pl.DataFrame) -> pl.DataFrame:
    lots = build_lots(selected)
    symbol_daily = build_symbol_daily(lots)
    keep_cols = [
        col
        for col in [
            "scenario",
            "target_date",
            "symbol",
            "target_weight",
            "industry",
            "market",
            "adv20_turnover",
            "turnover_rate_f",
            "circ_mv",
            "total_mv",
        ]
        if col in symbol_daily.columns
    ]
    return symbol_daily.select(keep_cols).unique(subset=["scenario", "target_date", "symbol"]).sort(
        ["scenario", "target_date", "symbol"]
    )


def replay_scenario(
    scenario: str,
    target_weights: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
) -> tuple[dict[str, Any], pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    scenario_targets = target_weights.filter(pl.col("scenario") == scenario).drop("scenario")
    target_maps = build_target_maps(scenario_targets)
    dates = build_tracking_dates(scenario_targets, benchmark_df)
    orders, daily, curve = replay_lot_account(target_maps, dates, exec_info)
    if not orders.is_empty():
        orders = orders.with_columns(pl.lit(scenario).alias("scenario"))
    if not daily.is_empty():
        daily = daily.with_columns(pl.lit(scenario).alias("scenario"))
    if not curve.is_empty():
        curve = curve.with_columns(pl.lit(scenario).alias("scenario"))
    summary = summarize_orders(orders, daily)
    summary["scenario"] = scenario
    summary["target_weight_mode"] = (
        "original_weight_no_realloc" if scenario == PRIMARY_SCENARIO else "reallocated_capped"
    )
    order_summary = build_order_summary(orders).with_columns(pl.lit(scenario).alias("scenario")) if not orders.is_empty() else pl.DataFrame()
    latest_holdings = (
        build_latest_holdings(orders, daily).with_columns(pl.lit(scenario).alias("scenario"))
        if not orders.is_empty() and not daily.is_empty()
        else pl.DataFrame()
    )
    quality = build_quality_checkpoints(summary).with_columns(pl.lit(scenario).alias("scenario"))
    return summary, orders, daily, curve, order_summary, latest_holdings, quality


def write_report(
    scenario_summary: pl.DataFrame,
    order_summary: pl.DataFrame,
    latest_holdings: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    primary = scenario_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO).row(0, named=True)
    reallocated = scenario_summary.filter(pl.col("scenario") == REALLOCATED_SCENARIO).row(0, named=True)
    lines = [
        "# 股票震荡liquid_q3 weak_market60_q1q2 30万候选整手复放 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：候选版30万账户、100股整手、最低佣金、ADV参与率和开盘可交易性复放。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；整手：`{BOARD_LOT_SHARES}`股；最低佣金压力：`{MIN_COMMISSION_CNY}`元。",
        "- A/B判断：候选可执行性验证，不接入正式版本，不触发第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- A股买入必须考虑100股整手，30万账户会被价格和目标权重共同限制。",
        "- 执行约束应独立于alpha信号，不能把下单可行性反向调成收益过滤器。",
        "- 因此本阶段只复放账户颗粒度和交易约束，不改`60/10/q1q2`信号。",
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
            f"- 诊断组：期末权益`{primary['final_equity_min_fee']:.4f}`，总收益`{pct(primary['total_return_min_fee'])}`，最大回撤`{pct(primary['max_drawdown_min_fee'])}`，Sharpe `{primary['sharpe_min_fee']:.3f}`。",
            f"- 诊断组zero-lot目标比例：`{pct(primary['zero_lot_target_ratio'])}`；最新目标日实际持仓数`{primary['latest_actual_symbol_count']}`，最新实际暴露`{pct(primary['latest_actual_gross_weight'])}`。",
            f"- 重分配组：期末权益`{reallocated['final_equity_min_fee']:.4f}`，总收益`{pct(reallocated['total_return_min_fee'])}`，最大回撤`{pct(reallocated['max_drawdown_min_fee'])}`，Sharpe `{reallocated['sharpe_min_fee']:.3f}`。",
            f"- 重分配组zero-lot目标比例：`{pct(reallocated['zero_lot_target_ratio'])}`；最新目标日实际持仓数`{reallocated['latest_actual_symbol_count']}`，最新实际暴露`{pct(reallocated['latest_actual_gross_weight'])}`。",
            f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
            "- 初步判断：若zero-lot比例仍高，说明30万账户可以研究但不应急着实盘；应先看暴露捕获和订单稳定性。",
            "",
            "## 场景汇总",
            "",
            markdown_table(
                scenario_summary,
                [
                    "scenario",
                    "target_weight_mode",
                    "date_start",
                    "date_end",
                    "trading_days",
                    "final_equity_min_fee",
                    "total_return_min_fee",
                    "max_drawdown_min_fee",
                    "sharpe_min_fee",
                    "zero_lot_target_ratio",
                    "latest_target_date",
                    "latest_target_symbol_count",
                    "latest_actual_symbol_count",
                    "latest_actual_gross_weight",
                    "latest_zero_lot_target_count",
                    "latest_order_count",
                    "latest_unfilled_amount_sum_cny",
                ],
                max_rows=20,
            ),
            "",
            "## 订单状态汇总",
            "",
            markdown_table(
                order_summary,
                [
                    "scenario",
                    "side",
                    "status",
                    "blocked_reason",
                    "orders",
                    "desired_amount_sum_cny",
                    "filled_amount_sum_cny",
                    "unfilled_amount_sum_cny",
                ],
                max_rows=80,
            ),
            "",
            "## 最新持仓Top40",
            "",
            markdown_table(
                latest_holdings,
                [
                    "scenario",
                    "symbol",
                    "code_name",
                    "industry",
                    "actual_shares",
                    "last_trade_open",
                    "actual_amount_cny",
                    "actual_weight",
                    "last_target_weight",
                ],
                max_rows=40,
            ),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, ["scenario", "checkpoint", "status", "value", "expected", "note"], max_rows=100),
            "",
            "## 失败项",
            "",
            "无数据" if failed.is_empty() else markdown_table(failed, ["scenario", "checkpoint", "status", "value", "expected", "note"], max_rows=100),
            "",
            "## 警告项",
            "",
            "无数据" if warned.is_empty() else markdown_table(warned, ["scenario", "checkpoint", "status", "value", "expected", "note"], max_rows=100),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只做账户颗粒度和执行约束复放，不调信号、不扫阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否，但不能实盘化。",
            "- 原因：整手复放是硬约束验证；若结果好，也只能说明候选可继续paper，不代表真实交易闭环已成立。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第296-297阶段已经通过反证审计和walk-forward验证，下一步应看30万是否还能承载。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是，但仍属于候选研究。",
            "- 原因：30万整手复放能判断候选是否具备账户颗粒度；后续仍需独立live target/order recalc，不得污染当前paper线。",
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
    selected = read_selected()
    target_weights = build_candidate_target_weights(selected)
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    summaries: list[dict[str, Any]] = []
    order_frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    curve_frames: list[pl.DataFrame] = []
    order_summary_frames: list[pl.DataFrame] = []
    latest_holding_frames: list[pl.DataFrame] = []
    quality_frames: list[pl.DataFrame] = []
    for scenario in CANDIDATE_SCENARIOS:
        summary, orders, daily, curve, order_summary, latest_holdings, quality = replay_scenario(
            scenario,
            target_weights,
            benchmark_df,
            exec_info,
        )
        summaries.append(summary)
        order_frames.append(orders)
        daily_frames.append(daily)
        curve_frames.append(curve)
        order_summary_frames.append(order_summary)
        latest_holding_frames.append(latest_holdings)
        quality_frames.append(quality)

    scenario_summary = pl.DataFrame(summaries).sort("scenario")
    orders = pl.concat([frame for frame in order_frames if not frame.is_empty()], how="vertical")
    daily = pl.concat([frame for frame in daily_frames if not frame.is_empty()], how="vertical")
    curve = pl.concat([frame for frame in curve_frames if not frame.is_empty()], how="vertical")
    order_summary = pl.concat([frame for frame in order_summary_frames if not frame.is_empty()], how="vertical")
    latest_holdings = pl.concat([frame for frame in latest_holding_frames if not frame.is_empty()], how="vertical")
    quality = pl.concat(quality_frames, how="vertical")

    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "scenario_summary": OUTPUT_DIR / f"{PREFIX}_scenario_summary.csv",
        "target_weights": OUTPUT_DIR / f"{PREFIX}_target_weights.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "curve": OUTPUT_DIR / f"{PREFIX}_curve.csv",
        "order_summary": OUTPUT_DIR / f"{PREFIX}_order_summary.csv",
        "latest_holdings": OUTPUT_DIR / f"{PREFIX}_latest_holdings.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    scenario_summary.write_csv(paths["scenario_summary"])
    target_weights.write_csv(paths["target_weights"])
    orders.write_csv(paths["orders"])
    daily.write_csv(paths["daily"])
    curve.write_csv(paths["curve"])
    order_summary.write_csv(paths["order_summary"])
    latest_holdings.write_csv(paths["latest_holdings"])
    quality.write_csv(paths["quality_checkpoints"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "candidate_scenarios": CANDIDATE_SCENARIOS,
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "board_lot_shares": BOARD_LOT_SHARES,
            "min_commission_cny": MIN_COMMISSION_CNY,
            "horizon": HORIZON,
            "research_sources": RESEARCH_SOURCES,
        },
    )
    report_path = write_report(scenario_summary, order_summary, latest_holdings, quality, paths)
    print(f"report={report_path}")
    print(scenario_summary)
    print(quality)


if __name__ == "__main__":
    main()
