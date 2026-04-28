from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import (
    ACCOUNT_SIZE_CNY,
    LATEST_LOOKBACK_DAYS,
    MAX_PARTICIPATION_ADV20,
    PAPER_SCENARIO,
    ROUNDTRIP_COST_BPS,
    build_signal_audit,
    build_symbol_meta,
    build_target_maps,
    build_target_weights,
    build_tracking_dates,
    markdown_table,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking_v2_adv_quality import (
    FALLBACK_MIN_VALID_TURNOVER_DAYS,
    build_adv_quality_summary,
    build_block_reason_summary,
    replay_paper_orders,
    summarize_tracking,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_latest_paper_packet_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_latest_paper_packet_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    ("Backtrader volume filling", "https://www.backtrader.com/docu/filler/"),
    ("Backtrader slippage", "https://www.backtrader.com/docu/slippage/slippage/"),
    ("Zipline volume-share slippage source", "https://zipline.ml4trading.io/_modules/zipline/finance/slippage.html"),
)


def side_status_summary(orders: pl.DataFrame) -> pl.DataFrame:
    if orders.is_empty():
        return pl.DataFrame()
    return (
        orders.group_by(["side", "status", "blocked_reason"])
        .agg(
            pl.len().alias("orders"),
            pl.col("desired_weight").sum().alias("desired_weight_sum"),
            pl.col("filled_weight").sum().alias("filled_weight_sum"),
            pl.col("unfilled_weight").sum().alias("unfilled_weight_sum"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("filled_amount_cny").sum().alias("filled_amount_cny_sum"),
            pl.col("unfilled_amount_cny").sum().alias("unfilled_amount_cny_sum"),
        )
        .sort(["side", "status", "orders"], descending=[False, False, True])
    )


def latest_packet_summary(
    full_summary: dict[str, Any],
    latest_signals: pl.DataFrame,
    latest_targets: pl.DataFrame,
    latest_orders: pl.DataFrame,
) -> dict[str, Any]:
    blocked = latest_orders.filter(pl.col("status") == "blocked") if not latest_orders.is_empty() else pl.DataFrame()
    tradable = latest_orders.filter(pl.col("status") != "blocked") if not latest_orders.is_empty() else pl.DataFrame()
    latest_signal_date = latest_signals["signal_date"].max() if not latest_signals.is_empty() else None
    latest_target_date = full_summary.get("latest_target_date")
    alignment_note = (
        "信号日与目标执行日一致。"
        if latest_signal_date == latest_target_date
        else "本地数据尾部存在信号审计日晚于可执行目标日的情况；下单/纸面执行以latest_target_date为准，latest_signal_date只作为尾部信号审计。"
    )
    return {
        "scenario": PAPER_SCENARIO,
        "packet_created_at": datetime.now().isoformat(timespec="seconds"),
        "latest_signal_date": latest_signal_date,
        "latest_target_date": latest_target_date,
        "signal_target_alignment_note": alignment_note,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "max_participation_adv20": MAX_PARTICIPATION_ADV20,
        "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
        "fallback_min_valid_turnover_days": FALLBACK_MIN_VALID_TURNOVER_DAYS,
        "latest_signal_rows": latest_signals.height,
        "latest_signal_kept_rows": latest_signals.filter(pl.col("is_kept")).height if not latest_signals.is_empty() else 0,
        "latest_signal_filtered_rows": latest_signals.filter(~pl.col("is_kept")).height
        if not latest_signals.is_empty()
        else 0,
        "latest_target_count": latest_targets.height,
        "latest_target_gross_weight": float(latest_targets["target_weight"].sum() or 0.0)
        if not latest_targets.is_empty()
        else 0.0,
        "latest_order_count": latest_orders.height,
        "latest_tradable_order_count": tradable.height if not tradable.is_empty() else 0,
        "latest_blocked_order_count": blocked.height if not blocked.is_empty() else 0,
        "latest_desired_abs_change": float(latest_orders["desired_weight"].sum() or 0.0)
        if not latest_orders.is_empty()
        else 0.0,
        "latest_filled_abs_change": float(latest_orders["filled_weight"].sum() or 0.0)
        if not latest_orders.is_empty()
        else 0.0,
        "latest_unfilled_abs_change": float(latest_orders["unfilled_weight"].sum() or 0.0)
        if not latest_orders.is_empty()
        else 0.0,
        "full_history_final_equity": full_summary.get("final_equity"),
        "full_history_total_return": full_summary.get("total_return"),
        "full_history_max_drawdown": full_summary.get("max_drawdown"),
        "full_history_sharpe": full_summary.get("sharpe"),
        "full_history_fill_ratio": full_summary.get("overall_fill_ratio"),
    }


def write_report(
    packet_summary: dict[str, Any],
    recent_daily: pl.DataFrame,
    latest_signals: pl.DataFrame,
    latest_targets: pl.DataFrame,
    latest_orders: pl.DataFrame,
    latest_block_summary: pl.DataFrame,
    latest_adv_summary: pl.DataFrame,
    latest_side_summary: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    latest_blocked = latest_orders.filter(pl.col("status") == "blocked") if not latest_orders.is_empty() else pl.DataFrame()
    latest_tradable = latest_orders.filter(pl.col("status") != "blocked") if not latest_orders.is_empty() else pl.DataFrame()
    lines = [
        "# 股票震荡liquid_q3最新纸面交易包 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：新增交易日纸面跟踪入口，默认使用v3 ex-ante ADV质量口径；不新增信号、不调参数。",
        f"- 纸面候选：`{PAPER_SCENARIO}`。",
        f"- 最新信号日：`{packet_summary['latest_signal_date']}`；最新目标执行日：`{packet_summary['latest_target_date']}`。",
        f"- 尾部对齐提示：{packet_summary['signal_target_alignment_note']}",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 纸面交易入口应把目标权重、订单、成交约束、阻断原因拆分输出，便于后续和真实成交回报对账。",
        "- Backtrader/Zipline类框架都把成交量、滑点、订单成交放在执行层；本入口也只做执行流水，不改信号层。",
        "- A股版本必须额外记录一字涨跌停、停牌和ADV质量标签。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 最新执行摘要",
            "",
            f"- 最新信号候选`{packet_summary['latest_signal_rows']}`只，保留`{packet_summary['latest_signal_kept_rows']}`只，过滤`{packet_summary['latest_signal_filtered_rows']}`只。",
            f"- 最新目标持仓`{packet_summary['latest_target_count']}`只，目标总权重`{pct(packet_summary['latest_target_gross_weight'])}`。",
            f"- 最新订单`{packet_summary['latest_order_count']}`行，可交易`{packet_summary['latest_tradable_order_count']}`行，阻断`{packet_summary['latest_blocked_order_count']}`行。",
            f"- 最新计划换仓权重`{pct(packet_summary['latest_desired_abs_change'])}`，可成交权重`{pct(packet_summary['latest_filled_abs_change'])}`，未成交权重`{pct(packet_summary['latest_unfilled_abs_change'])}`。",
            f"- 全历史v3参考：期末权益`{packet_summary['full_history_final_equity']:.4f}`，最大回撤`{pct(packet_summary['full_history_max_drawdown'])}`，Sharpe `{packet_summary['full_history_sharpe']:.2f}`，填充率`{pct(packet_summary['full_history_fill_ratio'])}`。",
            "",
            "## 最新订单状态汇总",
            "",
            markdown_table(
                latest_side_summary,
                [
                    "side",
                    "status",
                    "blocked_reason",
                    "orders",
                    "desired_weight_sum",
                    "filled_weight_sum",
                    "unfilled_weight_sum",
                    "desired_amount_cny_sum",
                    "filled_amount_cny_sum",
                    "unfilled_amount_cny_sum",
                ],
            ),
            "",
            "## 最新ADV质量来源",
            "",
            markdown_table(
                latest_adv_summary,
                [
                    "adv_source",
                    "adv_quality_flag",
                    "orders",
                    "symbols",
                    "desired_weight_sum",
                    "filled_weight_sum",
                    "unfilled_weight_sum",
                    "filled_weight_ratio",
                    "fallback_allowed_orders",
                    "fallback_allowed_order_ratio",
                ],
            ),
            "",
            "## 最新阻断原因",
            "",
            markdown_table(
                latest_block_summary,
                [
                    "status",
                    "blocked_reason",
                    "orders",
                    "desired_weight_sum",
                    "filled_weight_sum",
                    "unfilled_weight_sum",
                ],
            ),
            "",
            "## 最新目标权重",
            "",
            markdown_table(
                latest_targets.sort(["target_weight", "symbol"], descending=[True, False]),
                [
                    "target_date",
                    "symbol",
                    "industry",
                    "target_weight",
                    "target_amount_cny",
                    "active_lots",
                    "adv20_turnover",
                    "turnover_rate_f",
                    "circ_mv",
                ],
                max_rows=120,
            ),
            "",
            "## 最新可交易订单",
            "",
            markdown_table(
                latest_tradable.sort(["side", "desired_weight", "symbol"], descending=[False, True, False]),
                [
                    "date",
                    "symbol",
                    "code_name",
                    "industry",
                    "side",
                    "status",
                    "desired_weight",
                    "filled_weight",
                    "actual_weight_after",
                    "adv_source",
                    "adv_quality_flag",
                    "fallback_allowed",
                    "turnover_valid_count_20",
                    "trade_open",
                ],
                max_rows=120,
            ),
            "",
            "## 最新阻断订单",
            "",
            markdown_table(
                latest_blocked.sort(["blocked_reason", "side", "symbol"]) if not latest_blocked.is_empty() else latest_blocked,
                [
                    "date",
                    "symbol",
                    "code_name",
                    "industry",
                    "side",
                    "status",
                    "blocked_reason",
                    "desired_weight",
                    "filled_weight",
                    "unfilled_weight",
                    "adv_source",
                    "adv_quality_flag",
                    "trade_open",
                    "is_suspended",
                    "is_oneword_limit_up",
                    "is_oneword_limit_down",
                ],
                max_rows=120,
            ),
            "",
            "## 最新信号审计",
            "",
            markdown_table(
                latest_signals.sort(["filter_status", "industry", "symbol"]),
                [
                    "signal_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "filter_status",
                    "basket_weight",
                    "volume_ratio_20",
                    "volume_ratio20_band",
                    "turnover_5_20_ratio",
                    "turnover_5_20_band",
                    "ret_5",
                    "ret_10",
                    "dist_ma20",
                    "top_age",
                ],
                max_rows=160,
            ),
            "",
            "## 最近日汇总",
            "",
            markdown_table(
                recent_daily,
                [
                    "date",
                    "target_symbol_count",
                    "actual_symbol_count",
                    "target_gross_weight",
                    "actual_gross_weight",
                    "desired_abs_change",
                    "filled_abs_change",
                    "fill_ratio",
                    "blocked_order_count",
                    "partial_order_count",
                    "strategy_equity",
                    "strategy_drawdown",
                ],
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只是把v3固定口径封装成最新交易包，不新增预测变量、不调阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：入口只输出可对账流水，不能提升历史收益；它降低的是操作混乱和事后解释空间。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：候选版本包已经成型，下一步需要稳定的一键入口来跟踪新增交易日。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：最新目标、订单、阻断、ADV质量和信号审计已经分表输出，后续可直接用于样本外纸面跟踪。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 后续每次数据更新后优先运行本入口，再记录新增交易日结果。",
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
    stock_df, benchmark_df = load_panels()

    signal_audit = build_signal_audit(selected_all)
    target_weights = build_target_weights(selected_all)
    target_maps = build_target_maps(target_weights)
    dates = build_tracking_dates(target_weights, benchmark_df)
    exec_info = build_exec_info(stock_df)
    symbol_meta = build_symbol_meta(signal_audit)
    orders, daily, curves = replay_paper_orders(target_maps, dates, exec_info, symbol_meta)
    full_summary = summarize_tracking(daily, orders)

    latest_signal_date = signal_audit["signal_date"].max() if not signal_audit.is_empty() else None
    latest_target_date = full_summary["latest_target_date"]
    latest_signals = signal_audit.filter(pl.col("signal_date") == latest_signal_date)
    latest_targets = target_weights.filter(pl.col("target_date") == latest_target_date)
    latest_orders = orders.filter(pl.col("date") == latest_target_date) if not orders.is_empty() else pl.DataFrame()
    recent_daily = daily.tail(LATEST_LOOKBACK_DAYS) if not daily.is_empty() else daily
    latest_block_summary = build_block_reason_summary(latest_orders)
    latest_adv_summary = build_adv_quality_summary(latest_orders)
    latest_side_summary = side_status_summary(latest_orders)
    packet_summary = latest_packet_summary(full_summary, latest_signals, latest_targets, latest_orders)

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "latest_signals": OUTPUT_DIR / f"{PREFIX}_latest_signals.csv",
        "latest_targets": OUTPUT_DIR / f"{PREFIX}_latest_targets.csv",
        "latest_orders": OUTPUT_DIR / f"{PREFIX}_latest_orders.csv",
        "latest_tradable_orders": OUTPUT_DIR / f"{PREFIX}_latest_tradable_orders.csv",
        "latest_blocked_orders": OUTPUT_DIR / f"{PREFIX}_latest_blocked_orders.csv",
        "latest_block_summary": OUTPUT_DIR / f"{PREFIX}_latest_block_summary.csv",
        "latest_adv_summary": OUTPUT_DIR / f"{PREFIX}_latest_adv_summary.csv",
        "latest_side_summary": OUTPUT_DIR / f"{PREFIX}_latest_side_summary.csv",
        "recent_daily": OUTPUT_DIR / f"{PREFIX}_recent_daily.csv",
        "curves": OUTPUT_DIR / f"{PREFIX}_curves.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    latest_blocked = latest_orders.filter(pl.col("status") == "blocked") if not latest_orders.is_empty() else pl.DataFrame()
    latest_tradable = latest_orders.filter(pl.col("status") != "blocked") if not latest_orders.is_empty() else pl.DataFrame()
    paths["summary"].write_text(json.dumps(packet_summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    latest_signals.write_csv(paths["latest_signals"])
    latest_targets.write_csv(paths["latest_targets"])
    latest_orders.write_csv(paths["latest_orders"])
    latest_tradable.write_csv(paths["latest_tradable_orders"])
    latest_blocked.write_csv(paths["latest_blocked_orders"])
    latest_block_summary.write_csv(paths["latest_block_summary"])
    latest_adv_summary.write_csv(paths["latest_adv_summary"])
    latest_side_summary.write_csv(paths["latest_side_summary"])
    recent_daily.write_csv(paths["recent_daily"])
    curves.write_csv(paths["curves"])
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "paper_scenario": PAPER_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "max_participation_adv20": MAX_PARTICIPATION_ADV20,
        "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
        "fallback_min_valid_turnover_days": FALLBACK_MIN_VALID_TURNOVER_DAYS,
        "execution口径": "v3 ex-ante ADV quality: native adv20 and fallback turnover are shifted one trading row per symbol.",
        "source_filter_output_dir": str(FILTER_OUTPUT_DIR),
        "research_sources": RESEARCH_SOURCES,
    }
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(
        packet_summary,
        recent_daily,
        latest_signals,
        latest_targets,
        latest_orders,
        latest_block_summary,
        latest_adv_summary,
        latest_side_summary,
        paths,
    )
    print(json.dumps(packet_summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
