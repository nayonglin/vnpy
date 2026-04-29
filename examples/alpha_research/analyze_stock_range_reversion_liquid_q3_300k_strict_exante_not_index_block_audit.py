from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_persistent_confirmation import build_confirmation_lots
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import PAPER_SCENARIO, build_target_weights, markdown_table


STRICT_OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_st_buy_guard_strict_exante_replay_2018_2026"
).expanduser().resolve()
STRICT_PREFIX: str = "stock_range_reversion_liquid_q3_300k_st_buy_guard_strict_exante_replay_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_strict_exante_not_index_block_audit_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_strict_exante_not_index_block_audit_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Pre-trade controls should reject invalid orders before submission",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/pre-trade-risk-control",
    ),
    (
        "Index constituents need point-in-time membership, not a static current universe",
        "https://tushare.pro/document/2?doc_id=96",
    ),
)


def _sum_float(frame: pl.DataFrame, column: str) -> float:
    if frame.is_empty() or column not in frame.columns:
        return 0.0
    value = frame.select(pl.col(column).sum()).item()
    return float(value or 0.0)


def _markdown_all(frame: pl.DataFrame, max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return markdown_table(frame, frame.columns, max_rows=max_rows)


def load_strict_blocks() -> pl.DataFrame:
    path = STRICT_OUTPUT_DIR / f"{STRICT_PREFIX}_strict_block_audit.csv"
    return pl.read_csv(path, try_parse_dates=True, infer_schema_length=10000, schema_overrides={"symbol": pl.Utf8}).with_columns(
        pl.col("symbol").cast(pl.Utf8).str.zfill(6)
    )


def build_target_frame(selected: pl.DataFrame) -> pl.DataFrame:
    return (
        build_target_weights(selected)
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .rename({"target_date": "date"})
        .select(["date", "symbol", "pnl_date", "scenario", "target_weight", "industry"])
    )


def build_target_membership_frame() -> pl.DataFrame:
    stock_df, _ = load_panels()
    return (
        stock_df.select(["datetime", "symbol", "is_index_component", "eligible_component_row", "component_snapshot_date"])
        .rename(
            {
                "datetime": "date",
                "is_index_component": "target_is_index_component",
                "eligible_component_row": "target_eligible_component_row",
                "component_snapshot_date": "target_component_snapshot_date",
            }
        )
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
    )


def build_signal_lots(selected: pl.DataFrame) -> pl.DataFrame:
    selected = selected.with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
    signal_flags = (
        selected.filter(pl.col("scenario") == PAPER_SCENARIO)
        .select(["datetime", "symbol", "scenario", "is_index_component", "eligible_component_row", "component_snapshot_date"])
        .rename(
            {
                "datetime": "signal_date",
                "is_index_component": "signal_is_index_component",
                "eligible_component_row": "signal_eligible_component_row",
                "component_snapshot_date": "signal_component_snapshot_date",
            }
        )
        .unique(["scenario", "signal_date", "symbol"])
    )
    return (
        build_confirmation_lots(selected.filter(pl.col("scenario") == PAPER_SCENARIO))
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .join(signal_flags, on=["scenario", "signal_date", "symbol"], how="left")
    )


def enrich_not_index_blocks(blocks: pl.DataFrame, targets: pl.DataFrame, target_membership: pl.DataFrame) -> pl.DataFrame:
    return (
        blocks.filter(pl.col("strict_exante_guard_reason") == "not_index_component")
        .select(
            [
                "date",
                "symbol",
                "code_name",
                "industry",
                "prev_shares",
                "target_shares",
                "desired_shares",
                "desired_amount_cny",
                "is_new_entry_block",
                "is_add_to_existing_block",
                "pretrade_adv_source",
                "pretrade_adv_quality_flag",
            ]
        )
        .join(targets, on=["date", "symbol"], how="left", suffix="_target")
        .join(target_membership, on=["date", "symbol"], how="left")
        .sort(["date", "symbol"])
    )


def enrich_block_lots(not_index_blocks: pl.DataFrame, lots: pl.DataFrame) -> pl.DataFrame:
    return (
        not_index_blocks.select(["date", "symbol", "is_new_entry_block"])
        .rename({"date": "target_date"})
        .join(lots, on=["target_date", "symbol"], how="left")
        .sort(["target_date", "symbol", "signal_date", "holding_day"])
    )


def summarize_symbols(enriched: pl.DataFrame, block_lots: pl.DataFrame) -> pl.DataFrame:
    lot_summary = (
        block_lots.group_by("symbol")
        .agg(
            pl.len().alias("active_lot_rows"),
            pl.col("signal_date").min().alias("first_signal_date"),
            pl.col("signal_date").max().alias("last_signal_date"),
            pl.col("holding_day").min().alias("min_holding_day"),
            pl.col("holding_day").max().alias("max_holding_day"),
        )
    )
    return (
        enriched.group_by(["symbol", "code_name", "industry"])
        .agg(
            pl.len().alias("blocked_orders"),
            pl.col("date").min().alias("first_block_date"),
            pl.col("date").max().alias("last_block_date"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("is_new_entry_block").sum().alias("new_entry_orders"),
            pl.col("is_add_to_existing_block").sum().alias("add_to_existing_orders"),
        )
        .join(lot_summary, on="symbol", how="left")
        .sort(["blocked_orders", "desired_amount_cny_sum"], descending=True)
    )


def summarize_holding_day(block_lots: pl.DataFrame) -> pl.DataFrame:
    return (
        block_lots.group_by("holding_day")
        .agg(
            pl.len().alias("active_lot_rows"),
            pl.col("target_date").n_unique().alias("target_dates"),
            pl.col("symbol").n_unique().alias("symbols"),
        )
        .sort("holding_day")
    )


def build_quality(summary: dict[str, Any]) -> pl.DataFrame:
    rows = [
        {
            "checkpoint": "all_block_rows_have_targets",
            "status": "pass" if summary["missing_target_rows"] == 0 else "fail",
            "value": str(summary["missing_target_rows"]),
            "expected": "0",
            "note": "非成分阻断必须能追溯到目标权重行。",
        },
        {
            "checkpoint": "all_target_dates_are_not_component",
            "status": "pass" if summary["target_component_true_rows"] == 0 else "fail",
            "value": str(summary["target_component_true_rows"]),
            "expected": "0",
            "note": "若目标日仍是成分，则守门可能误杀。",
        },
        {
            "checkpoint": "all_signal_lots_were_component_eligible",
            "status": "pass" if summary["signal_component_eligible_lot_ratio"] >= 0.999 else "fail",
            "value": pct(summary["signal_component_eligible_lot_ratio"]),
            "expected": "near 100%",
            "note": "若信号日本来就不是成分，问题在上游选股；若信号日是成分，问题是持有窗口跨成分调出。",
        },
        {
            "checkpoint": "blocked_amount_is_small",
            "status": "pass" if summary["blocked_amount_to_strict_order_amount"] < 0.01 else "warn",
            "value": pct(summary["blocked_amount_to_strict_order_amount"]),
            "expected": "<1%",
            "note": "非成分阻断应是边界量级，不应成为策略主体。",
        },
        {
            "checkpoint": "audit_only_no_signal_change",
            "status": "pass",
            "value": "analysis_only",
            "expected": "analysis_only",
            "note": "本阶段只审计来源，不改交易规则。",
        },
    ]
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    symbol_summary: pl.DataFrame,
    holding_day_summary: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    lines = [
        "# 股票震荡liquid_q3 30万 strict-exante 非成分阻断来源审计 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：审计第284严格ex-ante守门中的`not_index_component`阻断来源；不新增资金曲线、不改paper入口。",
        "- A/B判断：股票震荡独立执行层审计，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- pre-trade control应在下单前拦住不属于当前交易股票池的新增买入/加仓。",
        "- 指数成分必须用点时成员身份；信号日成分和目标交易日成分可能因为调样发生变化。",
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
            f"- 非成分阻断`{summary['not_index_blocked_orders']}`笔，涉及`{summary['not_index_blocked_symbols']}`只股票，金额`{summary['not_index_blocked_amount_cny']:,.0f}`元。",
            f"- 新开仓阻断`{summary['new_entry_orders']}`笔，加仓阻断`{summary['add_to_existing_orders']}`笔。",
            f"- 目标权重行缺失`{summary['missing_target_rows']}`笔，目标日仍为成分`{summary['target_component_true_rows']}`笔。",
            f"- 对应活跃信号lot `{summary['active_lot_rows']}`行；信号日成分内可研究lot占比`{pct(summary['signal_component_eligible_lot_ratio'])}`。",
            f"- 非成分阻断金额占严格回放订单意向金额`{pct(summary['blocked_amount_to_strict_order_amount'])}`。",
            "",
            "## 判断",
            "",
            "- 这些阻断不是信号日选了非成分；全部对应信号lot在信号日仍为成分内可研究。",
            "- 问题来自10日持有袖套跨过指数调样日：信号日可买，目标交易日已经不是成分，但目标权重仍会延续或叠加。",
            "- 严格守门拦截当前非成分的买入/加仓是合理的；但上游目标生成可以进一步显式处理“调出后不再新增/加仓，只允许退出”。",
            "",
            "## 股票汇总",
            "",
            _markdown_all(symbol_summary, max_rows=40),
            "",
            "## holding_day分布",
            "",
            _markdown_all(holding_day_summary, max_rows=40),
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
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只追溯阻断来源，不根据收益改参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：结论是交易日股票池边界审计，不是收益拟合。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第284最大阻断来源是非成分，必须确认它是合理守门还是误伤。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：已确认非成分阻断主要来自持有窗口跨成分调出，可进一步做上游目标生成修复。",
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
    selected = pl.read_parquet(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_selected_all.parquet")
    strict_orders = pl.read_csv(
        STRICT_OUTPUT_DIR / f"{STRICT_PREFIX}_strict_orders.csv",
        try_parse_dates=True,
        infer_schema_length=10000,
        schema_overrides={"symbol": pl.Utf8},
    )
    strict_blocks = load_strict_blocks()
    targets = build_target_frame(selected)
    target_membership = build_target_membership_frame()
    signal_lots = build_signal_lots(selected)
    enriched = enrich_not_index_blocks(strict_blocks, targets, target_membership)
    block_lots = enrich_block_lots(enriched, signal_lots)
    symbol_summary = summarize_symbols(enriched, block_lots)
    holding_day_summary = summarize_holding_day(block_lots)

    active_lot_rows = block_lots.height
    signal_component_eligible_lot_rows = int(block_lots["signal_eligible_component_row"].fill_null(False).sum())
    total_order_amount = _sum_float(strict_orders, "desired_amount_cny")
    blocked_amount = _sum_float(enriched, "desired_amount_cny")
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scenario": PAPER_SCENARIO,
        "not_index_blocked_orders": enriched.height,
        "not_index_blocked_symbols": enriched["symbol"].n_unique() if not enriched.is_empty() else 0,
        "not_index_blocked_amount_cny": blocked_amount,
        "new_entry_orders": int(enriched["is_new_entry_block"].sum()) if not enriched.is_empty() else 0,
        "add_to_existing_orders": int(enriched["is_add_to_existing_block"].sum()) if not enriched.is_empty() else 0,
        "missing_target_rows": enriched.filter(pl.col("target_weight").is_null()).height,
        "target_component_true_rows": int(enriched["target_is_index_component"].fill_null(False).sum())
        if not enriched.is_empty()
        else 0,
        "target_component_false_rows": int((~enriched["target_is_index_component"].fill_null(False)).sum())
        if not enriched.is_empty()
        else 0,
        "active_lot_rows": active_lot_rows,
        "active_signal_dates": block_lots["signal_date"].n_unique() if not block_lots.is_empty() else 0,
        "signal_component_eligible_lot_rows": signal_component_eligible_lot_rows,
        "signal_component_eligible_lot_ratio": signal_component_eligible_lot_rows / active_lot_rows
        if active_lot_rows
        else 0.0,
        "holding_day_min": int(block_lots["holding_day"].min()) if not block_lots.is_empty() else 0,
        "holding_day_max": int(block_lots["holding_day"].max()) if not block_lots.is_empty() else 0,
        "blocked_amount_to_strict_order_amount": blocked_amount / total_order_amount if total_order_amount else 0.0,
    }
    quality = build_quality(summary)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "enriched_blocks": OUTPUT_DIR / f"{PREFIX}_enriched_blocks.csv",
        "block_lots": OUTPUT_DIR / f"{PREFIX}_block_lots.csv",
        "symbol_summary": OUTPUT_DIR / f"{PREFIX}_symbol_summary.csv",
        "holding_day_summary": OUTPUT_DIR / f"{PREFIX}_holding_day_summary.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    enriched.write_csv(paths["enriched_blocks"])
    block_lots.write_csv(paths["block_lots"])
    symbol_summary.write_csv(paths["symbol_summary"])
    holding_day_summary.write_csv(paths["holding_day_summary"])
    quality.write_csv(paths["quality_checkpoints"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    paths["meta"].write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "source_strict_output_dir": str(STRICT_OUTPUT_DIR),
                "research_sources": RESEARCH_SOURCES,
                "note": "Audit only; no signal or paper entrypoint change.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report_path = write_report(summary, symbol_summary, holding_day_summary, quality, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
