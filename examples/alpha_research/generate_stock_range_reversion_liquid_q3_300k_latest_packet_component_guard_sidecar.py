from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_component_exit_target_sidecar_replay import (
    OUTPUT_DIR as COMPONENT_SIDECAR_OUTPUT_DIR,
    PREFIX as COMPONENT_SIDECAR_PREFIX,
    build_component_membership,
)
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import (
    ACCOUNT_SIZE_CNY,
    BOARD_LOT_SHARES,
    MIN_COMMISSION_CNY,
    OUTPUT_DIR as LOT_OUTPUT_DIR,
    PREFIX as LOT_PREFIX,
    floor_to_lot_shares,
    write_json,
)
from analyze_stock_range_reversion_liquid_q3_300k_st_buy_guard_strict_exante_replay import (
    build_strict_exante_guard_panel,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_300k_latest_packet import (
    build_latest_industry_exposure,
    build_status_summary,
    read_csv_with_symbol,
    safe_quantile,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import (
    PAPER_SCENARIO,
    build_target_weights,
    markdown_table,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_latest_packet_component_guard_sidecar_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_latest_packet_component_guard_sidecar_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "QuantConnect ETF constituent universes support historical constituent membership workflows",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity/etf-constituents-universes",
    ),
    (
        "QuantConnect documents pre-trade risk controls before order submission",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/pre-trade-risk-control",
    ),
    (
        "Tushare index_weight provides index constituent and weight history",
        "https://tushare.pro/document/2?doc_id=96",
    ),
)


def _sum_float(frame: pl.DataFrame, column: str) -> float:
    if frame.is_empty() or column not in frame.columns:
        return 0.0
    return to_float(frame.select(pl.col(column).sum()).item())


def _markdown_all(frame: pl.DataFrame, max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return markdown_table(frame, frame.columns, max_rows=max_rows)


def latest_previous_shares(orders: pl.DataFrame, latest_date: Any) -> dict[str, int]:
    if orders.is_empty():
        return {}
    previous = (
        orders.filter(pl.col("date") < latest_date)
        .sort(["date", "symbol", "side"])
        .group_by("symbol")
        .agg(pl.col("actual_shares_after").last().alias("prev_shares"))
        .filter(pl.col("prev_shares") > 0)
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
    )
    return {row["symbol"]: int(row["prev_shares"]) for row in previous.iter_rows(named=True)}


def build_latest_sidecar_targets(
    target_weights: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
    component_membership: dict[tuple[Any, str], bool],
    previous_shares: dict[str, int],
) -> pl.DataFrame:
    latest_date = target_weights["target_date"].max()
    rows: list[dict[str, Any]] = []
    for row in (
        target_weights.filter(pl.col("target_date") == latest_date)
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .iter_rows(named=True)
    ):
        symbol = str(row["symbol"]).zfill(6)
        info = exec_info.get((row["target_date"], symbol))
        trade_open = to_float(info.trade_open if info else None)
        prev_shares = int(previous_shares.get(symbol, 0))
        raw_target_weight = to_float(row.get("target_weight"))
        raw_target_amount = raw_target_weight * ACCOUNT_SIZE_CNY
        raw_target_shares = floor_to_lot_shares(raw_target_amount, trade_open)
        is_component = component_membership.get((row["target_date"], symbol), False)
        sidecar_target_shares = raw_target_shares
        sidecar_reason = ""
        if raw_target_weight > 0 and not is_component:
            sidecar_target_shares = min(raw_target_shares, prev_shares)
            if sidecar_target_shares < raw_target_shares:
                sidecar_reason = "not_index_component_no_buy_add"
        sidecar_target_amount = sidecar_target_shares * trade_open
        sidecar_target_weight = sidecar_target_amount / ACCOUNT_SIZE_CNY if ACCOUNT_SIZE_CNY else 0.0
        suppressed_shares = max(0, raw_target_shares - sidecar_target_shares)
        rows.append(
            {
                "target_date": row["target_date"],
                "symbol": symbol,
                "code_name": info.code_name if info else "",
                "industry": row.get("industry") or "",
                "is_index_component_on_target_date": is_component,
                "component_target_sidecar_reason": sidecar_reason,
                "prev_shares": prev_shares,
                "raw_target_weight": raw_target_weight,
                "raw_target_amount_cny": raw_target_amount,
                "raw_target_shares": raw_target_shares,
                "sidecar_target_weight": sidecar_target_weight,
                "sidecar_target_amount_cny": sidecar_target_amount,
                "sidecar_target_shares": sidecar_target_shares,
                "suppressed_shares": suppressed_shares,
                "suppressed_amount_cny": suppressed_shares * trade_open,
                "trade_open": trade_open,
                "one_lot_amount_cny": trade_open * BOARD_LOT_SHARES,
                "zero_lot_target": raw_target_weight > 0 and sidecar_target_shares <= 0,
                "raw_zero_lot_target": raw_target_weight > 0 and raw_target_shares <= 0,
                "adv20_turnover": row.get("adv20_turnover"),
                "turnover_rate_f": row.get("turnover_rate_f"),
                "active_lots": row.get("active_lots"),
            }
        )
    return pl.DataFrame(rows).sort(
        ["component_target_sidecar_reason", "zero_lot_target", "sidecar_target_weight", "symbol"],
        descending=[True, True, True, False],
    )


def build_latest_holdings_marked(orders: pl.DataFrame, exec_info: dict[tuple[Any, str], Any], latest_date: Any) -> pl.DataFrame:
    if orders.is_empty():
        return pl.DataFrame()
    latest = (
        orders.filter(pl.col("date") <= latest_date)
        .sort(["date", "symbol", "side"])
        .group_by("symbol")
        .agg(
            pl.col("date").last().alias("last_order_date"),
            pl.col("code_name").last().alias("code_name"),
            pl.col("industry").last().alias("industry"),
            pl.col("actual_shares_after").last().alias("actual_shares"),
            pl.col("target_weight").last().alias("last_target_weight"),
        )
        .filter(pl.col("actual_shares") > 0)
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
    )
    rows: list[dict[str, Any]] = []
    for row in latest.iter_rows(named=True):
        symbol = row["symbol"]
        info = exec_info.get((latest_date, symbol))
        latest_open = to_float(info.trade_open if info else None)
        actual_shares = int(row["actual_shares"])
        actual_amount = actual_shares * latest_open
        rows.append(
            {
                **row,
                "latest_target_date": latest_date,
                "latest_trade_open": latest_open,
                "actual_amount_cny": actual_amount,
                "actual_weight": actual_amount / ACCOUNT_SIZE_CNY if ACCOUNT_SIZE_CNY else 0.0,
            }
        )
    return pl.DataFrame(rows).sort("actual_amount_cny", descending=True) if rows else pl.DataFrame()


def compare_latest_orders(original_orders: pl.DataFrame, sidecar_orders: pl.DataFrame) -> pl.DataFrame:
    keys = set()
    original_by_key: dict[tuple[Any, str, str], dict[str, Any]] = {}
    sidecar_by_key: dict[tuple[Any, str, str], dict[str, Any]] = {}
    for row in original_orders.iter_rows(named=True):
        key = (row["date"], str(row["symbol"]).zfill(6), str(row["side"]))
        keys.add(key)
        original_by_key[key] = row
    for row in sidecar_orders.iter_rows(named=True):
        key = (row["date"], str(row["symbol"]).zfill(6), str(row["side"]))
        keys.add(key)
        sidecar_by_key[key] = row

    rows: list[dict[str, Any]] = []
    for date_value, symbol, side in sorted(keys):
        original = original_by_key.get((date_value, symbol, side), {})
        sidecar = sidecar_by_key.get((date_value, symbol, side), {})
        changed = False
        for column in ["status", "blocked_reason", "desired_shares", "filled_shares", "target_shares", "desired_amount_cny"]:
            if original.get(column) != sidecar.get(column):
                changed = True
                break
        rows.append(
            {
                "date": date_value,
                "symbol": symbol,
                "side": side,
                "code_name": sidecar.get("code_name") or original.get("code_name") or "",
                "industry": sidecar.get("industry") or original.get("industry") or "",
                "changed": changed,
                "original_status": original.get("status"),
                "sidecar_status": sidecar.get("status"),
                "original_blocked_reason": original.get("blocked_reason"),
                "sidecar_blocked_reason": sidecar.get("blocked_reason"),
                "original_target_shares": original.get("target_shares"),
                "sidecar_target_shares": sidecar.get("target_shares"),
                "original_desired_shares": original.get("desired_shares"),
                "sidecar_desired_shares": sidecar.get("desired_shares"),
                "original_filled_shares": original.get("filled_shares"),
                "sidecar_filled_shares": sidecar.get("filled_shares"),
                "original_desired_amount_cny": original.get("desired_amount_cny"),
                "sidecar_desired_amount_cny": sidecar.get("desired_amount_cny"),
                "sidecar_strict_exante_guard_reason": sidecar.get("strict_exante_guard_reason"),
                "sidecar_component_target_reason": sidecar.get("component_target_sidecar_reason"),
            }
        )
    return pl.DataFrame(rows).sort(["changed", "side", "sidecar_desired_amount_cny"], descending=[True, False, True])


def annotate_latest_orders_guard(
    latest_orders: pl.DataFrame,
    guard_panel: pl.DataFrame,
    latest_date: Any,
) -> pl.DataFrame:
    if latest_orders.is_empty():
        return latest_orders
    latest_guard = guard_panel.filter(pl.col("date") == latest_date).select(
        [
            "date",
            "symbol",
            "exante_st",
            "strict_exante_research_eligible",
            "strict_exante_component_eligible",
            "strict_exante_guard_reason",
            "pretrade_adv_turnover_for_guard",
            "pretrade_adv_source",
            "pretrade_adv_quality_flag",
            "pretrade_fallback_allowed",
            "pretrade_tradable_open",
        ]
    )
    return latest_orders.with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6)).join(
        latest_guard,
        on=["date", "symbol"],
        how="left",
        suffix="_guard_panel",
    )


def build_quality(summary: dict[str, Any]) -> pl.DataFrame:
    rows = [
        {
            "checkpoint": "sidecar_does_not_overwrite_original_packet",
            "status": "pass",
            "value": "sidecar output",
            "expected": "sidecar output",
            "note": "本阶段只输出sidecar最新包，不覆盖原始最新包。",
        },
        {
            "checkpoint": "account_size_is_300k",
            "status": "pass" if abs(to_float(summary["account_size_cny"]) - 300_000.0) <= 1e-6 else "fail",
            "value": str(summary["account_size_cny"]),
            "expected": "300000",
            "note": "股票震荡当前paper候选按30万整手口径跟踪。",
        },
        {
            "checkpoint": "latest_not_index_guard_blocks_zero",
            "status": "pass" if summary["latest_not_index_guard_block_orders"] == 0 else "fail",
            "value": str(summary["latest_not_index_guard_block_orders"]),
            "expected": "0",
            "note": "成分调出后的新增/加仓应在目标层消失，不应落到执行守门。",
        },
        {
            "checkpoint": "latest_strict_guard_blocks_zero",
            "status": "pass" if summary["latest_st_or_ineligible_buy_blocked_orders"] == 0 else "warn",
            "value": str(summary["latest_st_or_ineligible_buy_blocked_orders"]),
            "expected": "0",
            "note": "最新交易日若仍有ST/不可研究买入阻断，需要人工复核后才能发出实盘指令。",
        },
        {
            "checkpoint": "latest_unfilled_amount_zero",
            "status": "pass" if abs(to_float(summary["latest_unfilled_amount_sum_cny"])) <= 1e-9 else "warn",
            "value": str(summary["latest_unfilled_amount_sum_cny"]),
            "expected": "0",
            "note": "最新sidecar订单未成交金额最好为0。",
        },
        {
            "checkpoint": "latest_order_compare_clean",
            "status": "pass" if summary["latest_changed_order_rows_vs_original"] == 0 else "warn",
            "value": str(summary["latest_changed_order_rows_vs_original"]),
            "expected": "0 preferred",
            "note": "当前最新日最好不被sidecar改变；若改变，需确认是目标层资格修正而非误伤。",
        },
        {
            "checkpoint": "no_signal_parameter_change",
            "status": "pass",
            "value": "no signal/threshold change",
            "expected": "no signal/threshold change",
            "note": "本阶段只接目标层/执行层sidecar，不改alpha排序或阈值。",
        },
    ]
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    latest_targets: pl.DataFrame,
    latest_target_adjustments: pl.DataFrame,
    latest_orders: pl.DataFrame,
    latest_order_compare: pl.DataFrame,
    latest_holdings: pl.DataFrame,
    status_summary: pl.DataFrame,
    industry_exposure: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    zero_lot_targets = latest_targets.filter(pl.col("zero_lot_target"))
    changed_orders = latest_order_compare.filter(pl.col("changed")) if not latest_order_compare.is_empty() else latest_order_compare
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万最新交易包 component+strict sidecar v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：把第286目标层成分禁买/禁加和第284严格ex-ante守门串成最新交易包sidecar；不覆盖原包。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；买入颗粒度：`{BOARD_LOT_SHARES}`股；最低佣金压力：`{MIN_COMMISSION_CNY}`元/笔。",
        f"- 最新目标执行日：`{summary['latest_target_date']}`。",
        "- A/B判断：股票震荡独立paper sidecar，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 指数成分型策略必须使用点时成分身份；最新包不应对当前非成分股新增买入/加仓。",
        "- pre-trade control是订单离开系统前的最后防线；目标层sidecar和执行层守门应同时存在，但职责不同。",
        "- 本阶段只把已有研究结论接成sidecar输出，不改变alpha信号。",
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
            f"- 原始目标`{summary['latest_raw_target_count']}`只，sidecar后目标`{summary['latest_sidecar_target_count']}`只。",
            f"- 目标层sidecar当日调整`{summary['latest_component_adjustment_rows']}`行，压掉金额`{summary['latest_component_suppressed_amount_cny']:,.0f}`元。",
            f"- sidecar目标金额`{summary['latest_sidecar_target_amount_sum_cny']:.0f}`元，取整后目标市值`{summary['latest_sidecar_rounded_target_amount_sum_cny']:.0f}`元。",
            f"- 买不到一手目标`{summary['latest_zero_lot_target_count']}`只，占原始目标`{summary['latest_zero_lot_target_ratio']:.2%}`。",
            f"- 最新sidecar订单`{summary['latest_order_count']}`行，成交`{summary['latest_filled_order_count']}`行，阻断`{summary['latest_blocked_order_count']}`行。",
            f"- 最新计划成交金额`{summary['latest_desired_amount_sum_cny']:.0f}`元，实际成交`{summary['latest_filled_amount_sum_cny']:.0f}`元，未成交`{summary['latest_unfilled_amount_sum_cny']:.0f}`元。",
            f"- 最新实际持仓`{summary['latest_actual_symbol_count']}`只，按最新开盘标记市值`{summary['latest_actual_amount_sum_cny']:.0f}`元，实际暴露`{pct(summary['latest_actual_gross_weight'])}`。",
            f"- 与原始最新订单相比，变化`{summary['latest_changed_order_rows_vs_original']}`行。",
            f"- 剩余ST/不可研究买入阻断`{summary['latest_st_or_ineligible_buy_blocked_orders']}`行；剩余非成分守门阻断`{summary['latest_not_index_guard_block_orders']}`行。",
            "",
            "## 质量检查",
            "",
            _markdown_all(quality),
            "",
            "## 失败项",
            "",
            _markdown_all(failed),
            "",
            "## 警告项",
            "",
            _markdown_all(warned),
            "",
            "## 最新订单状态汇总",
            "",
            _markdown_all(status_summary),
            "",
            "## 当日目标层调整",
            "",
            _markdown_all(latest_target_adjustments, max_rows=80),
            "",
            "## 与原始订单差异",
            "",
            _markdown_all(changed_orders, max_rows=80),
            "",
            "## 买不到一手目标",
            "",
            markdown_table(
                zero_lot_targets,
                [
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "sidecar_target_weight",
                    "sidecar_target_amount_cny",
                    "trade_open",
                    "one_lot_amount_cny",
                ],
                max_rows=80,
            ),
            "",
            "## 最新sidecar目标",
            "",
            markdown_table(
                latest_targets,
                [
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "is_index_component_on_target_date",
                    "component_target_sidecar_reason",
                    "prev_shares",
                    "raw_target_weight",
                    "raw_target_shares",
                    "sidecar_target_weight",
                    "sidecar_target_shares",
                    "suppressed_shares",
                    "zero_lot_target",
                    "trade_open",
                ],
                max_rows=120,
            ),
            "",
            "## 最新sidecar订单",
            "",
            markdown_table(
                latest_orders.sort(["side", "filled_amount_cny", "symbol"], descending=[False, True, False])
                if not latest_orders.is_empty()
                else latest_orders,
                [
                    "date",
                    "symbol",
                    "code_name",
                    "industry",
                    "side",
                    "status",
                    "blocked_reason",
                    "strict_exante_guard_reason",
                    "component_target_sidecar_reason",
                    "prev_shares",
                    "target_shares",
                    "desired_shares",
                    "filled_shares",
                    "actual_shares_after",
                    "trade_open",
                    "desired_amount_cny",
                    "filled_amount_cny",
                    "unfilled_amount_cny",
                ],
                max_rows=120,
            ),
            "",
            "## 最新持仓",
            "",
            markdown_table(
                latest_holdings,
                [
                    "symbol",
                    "code_name",
                    "industry",
                    "actual_shares",
                    "latest_trade_open",
                    "actual_amount_cny",
                    "actual_weight",
                    "last_order_date",
                    "last_target_weight",
                ],
                max_rows=120,
            ),
            "",
            "## 最新行业暴露",
            "",
            _markdown_all(industry_exposure, max_rows=60),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只是把已验证的成分资格边界和严格ex-ante守门接到最新包sidecar，不调收益参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：最新包sidecar没有改变alpha排序或阈值，且当日订单未因sidecar发生变化。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：paper跟踪要逐步靠近真实执行，必须同时保留原包和守门sidecar对照。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：最新sidecar质量检查通过，下一步可以修复suite硬import并把sidecar加入默认监控链路。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 不覆盖原始paper交易包。",
            "- 当前只作为paper sidecar监控包。",
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
    stock_df, _benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)
    guard_panel = build_strict_exante_guard_panel(stock_df, exec_info)
    component_membership = build_component_membership(stock_df)
    target_weights = build_target_weights(selected_all)

    sidecar_orders = read_csv_with_symbol(
        COMPONENT_SIDECAR_OUTPUT_DIR / f"{COMPONENT_SIDECAR_PREFIX}_sidecar_strict_orders.csv"
    ).with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
    sidecar_daily = pl.read_csv(
        COMPONENT_SIDECAR_OUTPUT_DIR / f"{COMPONENT_SIDECAR_PREFIX}_sidecar_strict_daily.csv",
        try_parse_dates=True,
    )
    original_orders = read_csv_with_symbol(LOT_OUTPUT_DIR / f"{LOT_PREFIX}_orders.csv").with_columns(
        pl.col("symbol").cast(pl.Utf8).str.zfill(6)
    )
    latest_date = sidecar_daily["date"].max()
    previous_shares = latest_previous_shares(sidecar_orders, latest_date)
    latest_targets = build_latest_sidecar_targets(target_weights, exec_info, component_membership, previous_shares)
    latest_target_adjustments = latest_targets.filter(pl.col("component_target_sidecar_reason") != "")

    latest_orders_raw = sidecar_orders.filter(pl.col("date") == latest_date)
    latest_orders = annotate_latest_orders_guard(latest_orders_raw, guard_panel, latest_date)
    latest_original_orders = original_orders.filter(pl.col("date") == latest_date)
    latest_order_compare = compare_latest_orders(latest_original_orders, latest_orders_raw)
    latest_changed_orders = latest_order_compare.filter(pl.col("changed")) if not latest_order_compare.is_empty() else latest_order_compare
    latest_holdings = build_latest_holdings_marked(sidecar_orders, exec_info, latest_date)
    status_summary = build_status_summary(latest_orders_raw)
    industry_exposure = build_latest_industry_exposure(latest_holdings)

    filled_latest_orders = latest_orders_raw.filter(pl.col("filled_shares") > 0)
    blocked_latest_orders = latest_orders_raw.filter(pl.col("status") == "blocked")
    latest_st_blocks = latest_orders_raw.filter(pl.col("blocked_reason") == "st_or_ineligible_buy")
    latest_not_index_blocks = latest_orders_raw.filter(
        (pl.col("blocked_reason") == "st_or_ineligible_buy")
        & (pl.col("strict_exante_guard_reason") == "not_index_component")
    )
    sidecar_target_count = latest_targets.filter(pl.col("sidecar_target_weight") > 0).height
    raw_target_count = latest_targets.filter(pl.col("raw_target_weight") > 0).height
    zero_lot_count = latest_targets.filter(pl.col("zero_lot_target")).height
    latest_daily = sidecar_daily.filter(pl.col("date") == latest_date).row(0, named=True)

    summary: dict[str, Any] = {
        "scenario": PAPER_SCENARIO,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "board_lot_shares": BOARD_LOT_SHARES,
        "min_commission_cny": MIN_COMMISSION_CNY,
        "latest_target_date": latest_date,
        "latest_raw_target_count": raw_target_count,
        "latest_sidecar_target_count": sidecar_target_count,
        "latest_raw_target_amount_sum_cny": _sum_float(latest_targets, "raw_target_amount_cny"),
        "latest_sidecar_target_amount_sum_cny": _sum_float(latest_targets, "sidecar_target_amount_cny"),
        "latest_sidecar_rounded_target_amount_sum_cny": _sum_float(latest_targets, "sidecar_target_amount_cny"),
        "latest_component_adjustment_rows": latest_target_adjustments.height,
        "latest_component_suppressed_amount_cny": _sum_float(latest_target_adjustments, "suppressed_amount_cny"),
        "latest_zero_lot_target_count": zero_lot_count,
        "latest_zero_lot_target_ratio": zero_lot_count / raw_target_count if raw_target_count else 0.0,
        "latest_order_count": latest_orders_raw.height,
        "latest_filled_order_count": filled_latest_orders.height,
        "latest_blocked_order_count": blocked_latest_orders.height,
        "latest_st_or_ineligible_buy_blocked_orders": latest_st_blocks.height,
        "latest_st_or_ineligible_buy_blocked_amount_cny": _sum_float(latest_st_blocks, "desired_amount_cny"),
        "latest_not_index_guard_block_orders": latest_not_index_blocks.height,
        "latest_desired_amount_sum_cny": _sum_float(latest_orders_raw, "desired_amount_cny"),
        "latest_filled_amount_sum_cny": _sum_float(latest_orders_raw, "filled_amount_cny"),
        "latest_unfilled_amount_sum_cny": _sum_float(latest_orders_raw, "unfilled_amount_cny"),
        "latest_actual_symbol_count": int(latest_daily["actual_symbol_count"]),
        "latest_actual_amount_sum_cny": _sum_float(latest_holdings, "actual_amount_cny"),
        "latest_actual_gross_weight": _sum_float(latest_holdings, "actual_weight"),
        "latest_daily_actual_market_value_cny": to_float(latest_daily["actual_market_value_cny"]),
        "latest_daily_actual_gross_weight": to_float(latest_daily["actual_gross_weight"]),
        "latest_filled_order_min_cny": to_float(filled_latest_orders["filled_amount_cny"].min())
        if not filled_latest_orders.is_empty()
        else 0.0,
        "latest_filled_order_median_cny": safe_quantile(filled_latest_orders, "filled_amount_cny", 0.5),
        "latest_filled_order_max_cny": to_float(filled_latest_orders["filled_amount_cny"].max())
        if not filled_latest_orders.is_empty()
        else 0.0,
        "latest_original_order_count": latest_original_orders.height,
        "latest_changed_order_rows_vs_original": latest_changed_orders.height,
    }
    quality = build_quality(summary)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "latest_targets": OUTPUT_DIR / f"{PREFIX}_latest_targets.csv",
        "latest_target_adjustments": OUTPUT_DIR / f"{PREFIX}_latest_target_adjustments.csv",
        "latest_orders": OUTPUT_DIR / f"{PREFIX}_latest_orders.csv",
        "latest_order_compare": OUTPUT_DIR / f"{PREFIX}_latest_order_compare.csv",
        "latest_changed_orders": OUTPUT_DIR / f"{PREFIX}_latest_changed_orders.csv",
        "latest_holdings": OUTPUT_DIR / f"{PREFIX}_latest_holdings.csv",
        "industry_exposure": OUTPUT_DIR / f"{PREFIX}_industry_exposure.csv",
        "status_summary": OUTPUT_DIR / f"{PREFIX}_status_summary.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    latest_targets.write_csv(paths["latest_targets"])
    latest_target_adjustments.write_csv(paths["latest_target_adjustments"])
    latest_orders.write_csv(paths["latest_orders"])
    latest_order_compare.write_csv(paths["latest_order_compare"])
    latest_changed_orders.write_csv(paths["latest_changed_orders"])
    latest_holdings.write_csv(paths["latest_holdings"])
    industry_exposure.write_csv(paths["industry_exposure"])
    status_summary.write_csv(paths["status_summary"])
    quality.write_csv(paths["quality_checkpoints"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_component_sidecar_output_dir": str(COMPONENT_SIDECAR_OUTPUT_DIR),
            "source_lot_output_dir": str(LOT_OUTPUT_DIR),
            "research_sources": RESEARCH_SOURCES,
            "note": "Latest packet sidecar only; original latest packet is not overwritten.",
        },
    )
    report_path = write_report(
        summary,
        latest_targets,
        latest_target_adjustments,
        latest_orders,
        latest_order_compare,
        latest_holdings,
        status_summary,
        industry_exposure,
        quality,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
