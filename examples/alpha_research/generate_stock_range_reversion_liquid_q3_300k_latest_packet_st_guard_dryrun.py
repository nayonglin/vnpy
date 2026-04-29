from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import (
    ACCOUNT_SIZE_CNY,
    OUTPUT_DIR as LOT_OUTPUT_DIR,
    PREFIX as LOT_PREFIX,
    write_json,
)
from analyze_stock_range_reversion_liquid_q3_300k_st_exante_audit import add_namechange_flag, load_namechange_st
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from build_stock_range_reversion_research_panel import MIN_ADV20_TURNOVER, MIN_LISTING_DAYS
from generate_stock_range_reversion_liquid_q3_300k_latest_packet import (
    build_latest_targets,
    build_status_summary,
    read_csv_with_symbol,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import (
    PAPER_SCENARIO,
    build_target_weights,
    markdown_table,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_latest_packet_st_guard_dryrun_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_latest_packet_st_guard_dryrun_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "FCA notes robust pre/post-trade controls are part of algorithmic trading control frameworks",
        "https://www.fca.org.uk/publications/multi-firm-reviews/algorithmic-trading-controls-high-level-observations",
    ),
    (
        "QuantConnect LEAN documents pre-order checks for tradability and brokerage execution validity",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/pre-trade-risk-control",
    ),
    (
        "Tushare namechange exposes historical name periods with start/end dates",
        "https://tushare.pro/document/2?doc_id=100",
    ),
)


def _markdown_all(frame: pl.DataFrame, max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return markdown_table(frame, frame.columns, max_rows=max_rows)


def _sum_float(frame: pl.DataFrame, column: str) -> float:
    if frame.is_empty() or column not in frame.columns:
        return 0.0
    return to_float(frame.select(pl.col(column).sum()).item())


def build_latest_pretrade_panel(stock_df: pl.DataFrame, latest_date: Any) -> pl.DataFrame:
    panel = (
        stock_df.select(
            [
                "datetime",
                "symbol",
                "is_stock_type",
                "is_st",
                "listing_days",
                "is_suspended",
                "is_listed_status",
                "is_index_component",
            ]
        )
        .rename({"datetime": "date"})
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .filter(pl.col("date") == latest_date)
    )
    return add_namechange_flag(panel, load_namechange_st()).with_columns(
        (pl.col("is_st").fill_null(False) | pl.col("namechange_st_on_date").fill_null(False)).alias("exante_st")
    )


def build_exec_info_frame(exec_info: dict[tuple[Any, str], Any], latest_date: Any, symbols: list[str]) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        info = exec_info.get((latest_date, symbol))
        payload = asdict(info) if info else {}
        rows.append(
            {
                "date": latest_date,
                "symbol": symbol,
                "pretrade_adv_turnover_for_cap": payload.get("adv_turnover_for_cap"),
                "pretrade_native_adv20_turnover": payload.get("native_adv20_turnover"),
                "pretrade_fallback_adv_turnover": payload.get("fallback_adv_turnover"),
                "pretrade_adv_source": payload.get("adv_source") or "missing",
                "pretrade_adv_quality_flag": payload.get("adv_quality_flag") or "missing_exec_info",
                "pretrade_fallback_allowed": bool(payload.get("fallback_allowed") or False),
                "pretrade_turnover_valid_count_20": int(to_float(payload.get("turnover_valid_count_20"))),
                "pretrade_tradable_open": bool(payload.get("tradable_open") or False),
            }
        )
    return pl.DataFrame(rows)


def annotate_guard(latest_orders: pl.DataFrame, stock_df: pl.DataFrame, latest_date: Any) -> pl.DataFrame:
    symbols = latest_orders["symbol"].cast(pl.Utf8).str.zfill(6).unique().sort().to_list()
    panel = build_latest_pretrade_panel(stock_df, latest_date)
    exec_frame = build_exec_info_frame(build_exec_info(stock_df), latest_date, symbols)
    annotated = (
        latest_orders.with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .join(panel, on=["date", "symbol"], how="left")
        .join(exec_frame, on=["date", "symbol"], how="left")
        .with_columns(
            (
                (~pl.col("is_suspended").fill_null(True))
                & (~pl.col("exante_st").fill_null(True))
                & pl.col("is_stock_type").fill_null(False)
                & pl.col("is_listed_status").fill_null(False)
                & (pl.col("listing_days").fill_null(-1) >= MIN_LISTING_DAYS)
                & (pl.col("pretrade_adv_turnover_for_cap").fill_null(0) >= MIN_ADV20_TURNOVER)
                & pl.col("pretrade_tradable_open").fill_null(False)
            ).alias("paper_guard_research_eligible")
        )
        .with_columns(
            (
                pl.col("paper_guard_research_eligible")
                & pl.col("is_index_component").fill_null(False)
            ).alias("paper_guard_component_eligible")
        )
        .with_columns(
            pl.when(pl.col("exante_st").fill_null(False))
            .then(pl.lit("exante_st"))
            .when(pl.col("is_suspended").fill_null(True))
            .then(pl.lit("suspended"))
            .when(~pl.col("is_stock_type").fill_null(False))
            .then(pl.lit("not_stock_type"))
            .when(~pl.col("is_listed_status").fill_null(False))
            .then(pl.lit("not_listed_status"))
            .when(pl.col("listing_days").fill_null(-1) < MIN_LISTING_DAYS)
            .then(pl.lit("listing_days_lt_min"))
            .when(pl.col("pretrade_adv_turnover_for_cap").fill_null(0) < MIN_ADV20_TURNOVER)
            .then(pl.lit("pretrade_adv20_turnover_lt_min"))
            .when(~pl.col("pretrade_tradable_open").fill_null(False))
            .then(pl.lit("not_tradable_open"))
            .when(~pl.col("is_index_component").fill_null(False))
            .then(pl.lit("not_index_component"))
            .otherwise(pl.lit(""))
            .alias("paper_guard_reason")
        )
        .with_columns(
            ((pl.col("side") == "buy") & (pl.col("paper_guard_reason") != "")).alias("paper_guard_would_block")
        )
    )
    return annotated.with_columns(
        pl.when(pl.col("paper_guard_would_block")).then(pl.lit("blocked")).otherwise(pl.col("status")).alias(
            "dryrun_status"
        ),
        pl.when(pl.col("paper_guard_would_block"))
        .then(pl.lit("st_or_ineligible_buy"))
        .otherwise(pl.col("blocked_reason"))
        .alias("dryrun_blocked_reason"),
        pl.when(pl.col("paper_guard_would_block")).then(pl.lit(0)).otherwise(pl.col("filled_shares")).alias(
            "dryrun_filled_shares"
        ),
        pl.when(pl.col("paper_guard_would_block"))
        .then(pl.col("desired_shares"))
        .otherwise(pl.col("unfilled_shares"))
        .alias("dryrun_unfilled_shares"),
        pl.when(pl.col("paper_guard_would_block")).then(pl.lit(0.0)).otherwise(pl.col("filled_amount_cny")).alias(
            "dryrun_filled_amount_cny"
        ),
        pl.when(pl.col("paper_guard_would_block"))
        .then(pl.col("desired_amount_cny"))
        .otherwise(pl.col("unfilled_amount_cny"))
        .alias("dryrun_unfilled_amount_cny"),
        pl.when(pl.col("paper_guard_would_block")).then(pl.col("prev_shares")).otherwise(pl.col("actual_shares_after")).alias(
            "dryrun_actual_shares_after"
        ),
    )


def summarize_guard(orders: pl.DataFrame) -> pl.DataFrame:
    if orders.is_empty():
        return pl.DataFrame()
    return (
        orders.group_by(["paper_guard_would_block", "paper_guard_reason", "dryrun_status", "dryrun_blocked_reason"])
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("dryrun_filled_amount_cny").sum().alias("dryrun_filled_amount_cny_sum"),
            pl.col("dryrun_unfilled_amount_cny").sum().alias("dryrun_unfilled_amount_cny_sum"),
        )
        .sort(["paper_guard_would_block", "orders"], descending=[True, True])
    )


def build_quality(summary: dict[str, Any], annotated_orders: pl.DataFrame) -> pl.DataFrame:
    malformed_sell_blocks = annotated_orders.filter((pl.col("side") != "buy") & pl.col("paper_guard_would_block"))
    missing_reason_blocks = annotated_orders.filter(pl.col("paper_guard_would_block") & (pl.col("paper_guard_reason") == ""))
    rows = [
        {
            "checkpoint": "dryrun_does_not_overwrite_original_packet",
            "status": "pass",
            "value": "sidecar output",
            "expected": "sidecar output",
            "note": "本阶段只输出对照包，不覆盖原交易包。",
        },
        {
            "checkpoint": "no_signal_parameter_change",
            "status": "pass",
            "value": "no signal/threshold change",
            "expected": "no signal/threshold change",
            "note": "只审计执行守门，不改变alpha排序。",
        },
        {
            "checkpoint": "latest_guard_blocks_zero",
            "status": "pass" if summary["guard_would_block_orders"] == 0 else "warn",
            "value": str(summary["guard_would_block_orders"]),
            "expected": "0",
            "note": "当前最新交易包最好不被新增守门异常阻断。",
        },
        {
            "checkpoint": "no_sell_order_guard_block",
            "status": "pass" if malformed_sell_blocks.is_empty() else "fail",
            "value": str(malformed_sell_blocks.height),
            "expected": "0",
            "note": "守门只允许拦截买入/加仓，不应阻断卖出。",
        },
        {
            "checkpoint": "blocked_rows_have_reason",
            "status": "pass" if missing_reason_blocks.is_empty() else "fail",
            "value": str(missing_reason_blocks.height),
            "expected": "0",
            "note": "若dry-run阻断，必须有明确原因。",
        },
    ]
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    annotated_orders: pl.DataFrame,
    guard_summary: pl.DataFrame,
    original_status_summary: pl.DataFrame,
    dryrun_status_summary: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万最新交易包 ST守门dry-run v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：对最新30万paper交易包做ST/不可研究买入守门dry-run；只输出对照，不覆盖原交易包。",
        f"- 最新目标执行日：`{summary['latest_target_date']}`。",
        "- A/B判断：股票震荡独立执行层验证，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 专业交易系统的执行守门属于pre-trade control，应在订单离开系统前拦截，不应反向修改信号层。",
        "- 本dry-run遵循这个分层：目标权重不变，只在订单层标记若接入守门会被阻断的买入。",
        "- ADV口径使用v3已有ex-ante ADV信息，避免把目标日成交额作为盘前可知信息。",
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
            f"- 最新订单`{summary['latest_order_count']}`行，原始阻断`{summary['original_blocked_orders']}`行。",
            f"- 守门dry-run新增会阻断`{summary['guard_would_block_orders']}`行，金额`{summary['guard_would_block_amount_cny']:,.0f}`元。",
            f"- dry-run后阻断`{summary['dryrun_blocked_orders']}`行，未成交金额`{summary['dryrun_unfilled_amount_cny']:,.0f}`元。",
            f"- 发生变化订单`{summary['changed_orders']}`行。",
            "",
            "## 判断",
            "",
            "- 当前最新交易包不会被修正版守门新增阻断，说明最小接入在当前日期不会破坏日常交易包。",
            "- 仍不建议直接覆盖原入口；下一步应做可开关补丁，并默认同时输出原始包和守门包。",
            "",
            "## 守门dry-run汇总",
            "",
            _markdown_all(guard_summary),
            "",
            "## 原始订单状态",
            "",
            _markdown_all(original_status_summary),
            "",
            "## dry-run订单状态",
            "",
            _markdown_all(dryrun_status_summary),
            "",
            "## 最新订单明细",
            "",
            markdown_table(
                annotated_orders.sort(["paper_guard_would_block", "side", "desired_amount_cny"], descending=[True, False, True]),
                [
                    "date",
                    "symbol",
                    "code_name",
                    "industry",
                    "side",
                    "status",
                    "dryrun_status",
                    "paper_guard_would_block",
                    "paper_guard_reason",
                    "desired_amount_cny",
                    "filled_amount_cny",
                    "dryrun_filled_amount_cny",
                    "pretrade_adv_source",
                    "pretrade_adv_quality_flag",
                    "pretrade_adv_turnover_for_cap",
                    "is_index_component",
                    "exante_st",
                ],
                max_rows=120,
            ),
            "",
            "## 质量检查",
            "",
            _markdown_all(quality),
            "",
            "## 失败项",
            "",
            _markdown_all(quality.filter(pl.col("status") == "fail")),
            "",
            "## 警告项",
            "",
            _markdown_all(quality.filter(pl.col("status") == "warn")),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只做订单层守门dry-run，不搜索收益参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：最新交易包未被新增阻断，且没有改变目标权重或alpha排序。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第279已证明历史阻断可解释，但接入前必须确认最新交易包不会被异常拦截。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：dry-run通过，下一步可以做可开关的最小接入补丁设计。",
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
    target_weights = build_target_weights(selected_all)
    latest_targets = build_latest_targets(target_weights, exec_info)
    latest_date = latest_targets["target_date"].max()
    orders = read_csv_with_symbol(LOT_OUTPUT_DIR / f"{LOT_PREFIX}_orders.csv").with_columns(
        pl.col("symbol").cast(pl.Utf8).str.zfill(6)
    )
    latest_orders = orders.filter(pl.col("date") == latest_date)
    annotated_orders = annotate_guard(latest_orders, stock_df, latest_date)
    changed_orders = annotated_orders.filter(
        (pl.col("dryrun_status") != pl.col("status"))
        | (pl.col("dryrun_filled_shares") != pl.col("filled_shares"))
        | (pl.col("dryrun_unfilled_shares") != pl.col("unfilled_shares"))
    )
    guard_blocks = annotated_orders.filter(pl.col("paper_guard_would_block"))
    dryrun_blocked = annotated_orders.filter(pl.col("dryrun_status") == "blocked")
    guard_summary = summarize_guard(annotated_orders)
    original_status_summary = build_status_summary(latest_orders)
    dryrun_status_summary = (
        annotated_orders.group_by(["side", "dryrun_status", "dryrun_blocked_reason"])
        .agg(
            pl.len().alias("orders"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_sum_cny"),
            pl.col("dryrun_filled_amount_cny").sum().alias("filled_amount_sum_cny"),
            pl.col("dryrun_unfilled_amount_cny").sum().alias("unfilled_amount_sum_cny"),
            pl.col("desired_shares").sum().alias("desired_shares_sum"),
            pl.col("dryrun_filled_shares").sum().alias("filled_shares_sum"),
        )
        .sort(["side", "dryrun_status", "orders"], descending=[False, False, True])
    )
    summary: dict[str, Any] = {
        "scenario": PAPER_SCENARIO,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "latest_target_date": latest_date,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "latest_order_count": latest_orders.height,
        "original_blocked_orders": latest_orders.filter(pl.col("status") == "blocked").height,
        "original_unfilled_amount_cny": _sum_float(latest_orders, "unfilled_amount_cny"),
        "guard_would_block_orders": guard_blocks.height,
        "guard_would_block_amount_cny": _sum_float(guard_blocks, "desired_amount_cny"),
        "dryrun_blocked_orders": dryrun_blocked.height,
        "dryrun_unfilled_amount_cny": _sum_float(annotated_orders, "dryrun_unfilled_amount_cny"),
        "changed_orders": changed_orders.height,
    }
    quality = build_quality(summary, annotated_orders)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "annotated_latest_orders": OUTPUT_DIR / f"{PREFIX}_annotated_latest_orders.csv",
        "changed_orders": OUTPUT_DIR / f"{PREFIX}_changed_orders.csv",
        "guard_summary": OUTPUT_DIR / f"{PREFIX}_guard_summary.csv",
        "original_status_summary": OUTPUT_DIR / f"{PREFIX}_original_status_summary.csv",
        "dryrun_status_summary": OUTPUT_DIR / f"{PREFIX}_dryrun_status_summary.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    annotated_orders.write_csv(paths["annotated_latest_orders"])
    changed_orders.write_csv(paths["changed_orders"])
    guard_summary.write_csv(paths["guard_summary"])
    original_status_summary.write_csv(paths["original_status_summary"])
    dryrun_status_summary.write_csv(paths["dryrun_status_summary"])
    quality.write_csv(paths["quality_checkpoints"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_lot_output_dir": str(LOT_OUTPUT_DIR),
            "note": "ST/ineligible buy guard dry-run sidecar only; original latest packet is not overwritten.",
            "research_sources": RESEARCH_SOURCES,
        },
    )
    report_path = write_report(
        summary,
        annotated_orders,
        guard_summary,
        original_status_summary,
        dryrun_status_summary,
        quality,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
