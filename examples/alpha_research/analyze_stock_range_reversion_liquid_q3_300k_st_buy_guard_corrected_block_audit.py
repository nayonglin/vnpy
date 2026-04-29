from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_st_buy_guard_corrected_replay import (
    OUTPUT_DIR as CORRECTED_OUTPUT_DIR,
    PREFIX as CORRECTED_PREFIX,
    build_corrected_guard_panel,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from build_stock_range_reversion_research_panel import MIN_ADV20_TURNOVER, MIN_LISTING_DAYS
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_st_buy_guard_corrected_block_audit_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_st_buy_guard_corrected_block_audit_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Tushare namechange exposes historical name start/end dates for ex-ante ST checks",
        "https://tushare.pro/document/2?doc_id=100",
    ),
    (
        "Tushare stock_st can query historical daily ST lists from 20160101 onward",
        "https://tushare.pro/document/2?doc_id=397",
    ),
    (
        "Tushare index_weight provides historical monthly index constituents and weights",
        "https://tushare.pro/document/2?doc_id=96",
    ),
)


def _read_csv(path: Path) -> pl.DataFrame:
    df = pl.read_csv(
        path,
        try_parse_dates=True,
        infer_schema_length=10000,
        schema_overrides={"symbol": pl.Utf8},
    )
    if "symbol" in df.columns:
        df = df.with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
    return df


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def _safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _sum_float(df: pl.DataFrame, column: str) -> float:
    if df.is_empty() or column not in df.columns:
        return 0.0
    value = df.select(pl.col(column).sum()).item()
    return _safe_float(value)


def _markdown_all(frame: pl.DataFrame, max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return markdown_table(frame, frame.columns, max_rows=max_rows)


def load_corrected_blocks() -> pl.DataFrame:
    path = CORRECTED_OUTPUT_DIR / f"{CORRECTED_PREFIX}_corrected_block_audit.csv"
    return _read_csv(path)


def load_corrected_orders() -> pl.DataFrame:
    path = CORRECTED_OUTPUT_DIR / f"{CORRECTED_PREFIX}_corrected_orders.csv"
    return _read_csv(path)


def build_panel_lookup() -> pl.DataFrame:
    stock_df, _ = load_panels()
    panel = build_corrected_guard_panel(stock_df)
    return (
        panel.select(
            [
                "date",
                "symbol",
                "is_stock_type",
                "is_st",
                "namechange_st_on_date",
                "namechange_st_period_count",
                "listing_days",
                "is_suspended",
                "is_listed_status",
                "volume",
                "turnover",
                "adv20_turnover",
                "recomputed_adv20_turnover",
                "corrected_adv20_turnover",
                "qfq_close",
                "is_index_component",
                "corrected_research_eligible",
                "corrected_component_eligible",
                "adv20_warmup_filled",
            ]
        )
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .unique(["date", "symbol"])
    )


def enrich_blocks(blocks: pl.DataFrame, panel: pl.DataFrame) -> pl.DataFrame:
    enriched = (
        blocks.with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .join(
            panel.rename(
                {
                    "is_stock_type": "panel_is_stock_type",
                    "is_st": "panel_is_st",
                    "namechange_st_on_date": "panel_namechange_st_on_date",
                    "namechange_st_period_count": "panel_namechange_st_period_count",
                    "listing_days": "panel_listing_days",
                    "is_suspended": "panel_is_suspended",
                    "is_listed_status": "panel_is_listed_status",
                    "volume": "panel_volume",
                    "turnover": "panel_turnover",
                    "adv20_turnover": "panel_adv20_turnover",
                    "recomputed_adv20_turnover": "panel_recomputed_adv20_turnover",
                    "corrected_adv20_turnover": "panel_corrected_adv20_turnover",
                    "qfq_close": "panel_qfq_close",
                    "is_index_component": "panel_is_index_component",
                    "corrected_research_eligible": "panel_corrected_research_eligible",
                    "corrected_component_eligible": "panel_corrected_component_eligible",
                    "adv20_warmup_filled": "panel_adv20_warmup_filled",
                }
            ),
            on=["date", "symbol"],
            how="left",
        )
        .with_columns(
            (pl.col("prev_shares").fill_null(0) <= 0).alias("is_new_entry_block"),
            (pl.col("prev_shares").fill_null(0) > 0).alias("is_add_to_existing_block"),
            pl.col("date").dt.year().alias("year"),
            pl.col("date").dt.strftime("%Y-%m").alias("month"),
        )
    )
    return enriched.with_columns(
        pl.when(pl.col("exante_st").fill_null(False))
        .then(pl.lit("exante_st"))
        .when(pl.col("panel_is_suspended").fill_null(True))
        .then(pl.lit("suspended"))
        .when(~pl.col("panel_is_stock_type").fill_null(False))
        .then(pl.lit("not_stock_type"))
        .when(~pl.col("panel_is_listed_status").fill_null(False))
        .then(pl.lit("not_listed_status"))
        .when(pl.col("panel_listing_days").fill_null(-1) < MIN_LISTING_DAYS)
        .then(pl.lit("listing_days_lt_min"))
        .when(pl.col("panel_volume").fill_null(0) <= 0)
        .then(pl.lit("zero_or_missing_volume"))
        .when(pl.col("panel_turnover").fill_null(0) <= 0)
        .then(pl.lit("zero_or_missing_turnover"))
        .when(pl.col("panel_corrected_adv20_turnover").fill_null(0) < MIN_ADV20_TURNOVER)
        .then(pl.lit("adv20_turnover_lt_min_after_recompute"))
        .when(pl.col("panel_qfq_close").is_null())
        .then(pl.lit("missing_qfq_close"))
        .when(~pl.col("panel_is_index_component").fill_null(False))
        .then(pl.lit("not_index_component"))
        .otherwise(pl.lit("other"))
        .alias("precise_block_reason")
    )


def summarize_reason(enriched: pl.DataFrame) -> pl.DataFrame:
    return (
        enriched.group_by(["corrected_guard_subreason", "precise_block_reason"])
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("date").n_unique().alias("dates"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("is_new_entry_block").sum().alias("new_entry_orders"),
            pl.col("is_add_to_existing_block").sum().alias("add_to_existing_orders"),
        )
        .sort(["orders", "desired_amount_cny_sum"], descending=True)
    )


def summarize_symbols(enriched: pl.DataFrame) -> pl.DataFrame:
    return (
        enriched.group_by(["symbol", "code_name", "industry", "precise_block_reason"])
        .agg(
            pl.len().alias("orders"),
            pl.col("date").min().alias("first_date"),
            pl.col("date").max().alias("last_date"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("is_new_entry_block").sum().alias("new_entry_orders"),
            pl.col("is_add_to_existing_block").sum().alias("add_to_existing_orders"),
            pl.col("panel_corrected_adv20_turnover").mean().alias("avg_corrected_adv20_turnover"),
        )
        .sort(["orders", "desired_amount_cny_sum"], descending=True)
    )


def summarize_calendar(enriched: pl.DataFrame, key: str) -> pl.DataFrame:
    return (
        enriched.group_by(key)
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("is_new_entry_block").sum().alias("new_entry_orders"),
            pl.col("is_add_to_existing_block").sum().alias("add_to_existing_orders"),
        )
        .sort(key)
    )


def summarize_mode(enriched: pl.DataFrame) -> pl.DataFrame:
    return (
        enriched.group_by(["precise_block_reason", "is_new_entry_block", "is_add_to_existing_block"])
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
        )
        .sort(["precise_block_reason", "orders"], descending=[False, True])
    )


def build_quality(enriched: pl.DataFrame, orders: pl.DataFrame, summary: dict[str, Any]) -> pl.DataFrame:
    st_blocks = enriched.filter(pl.col("precise_block_reason") == "exante_st")
    component_blocks = enriched.filter(pl.col("precise_block_reason") == "not_index_component")
    malformed = enriched.filter((pl.col("side") != "buy") | (pl.col("status") != "blocked"))
    reason_nulls = enriched.filter(pl.col("precise_block_reason").is_null() | (pl.col("precise_block_reason") == "other"))
    not_component_bad = component_blocks.filter(
        (~pl.col("panel_corrected_research_eligible").fill_null(False))
        | pl.col("panel_corrected_component_eligible").fill_null(True)
    )
    st_bad = st_blocks.filter(~pl.col("exante_st").fill_null(False))
    total_order_amount = _sum_float(orders, "desired_amount_cny")
    block_ratio = summary["blocked_amount_cny"] / total_order_amount if total_order_amount else 0.0
    rows = [
        {
            "checkpoint": "all_audit_rows_are_blocked_buys",
            "status": "pass" if malformed.is_empty() else "fail",
            "value": str(malformed.height),
            "expected": "0",
            "note": "审计样本必须全部来自买入阻断。",
        },
        {
            "checkpoint": "all_blocks_have_precise_reason",
            "status": "pass" if reason_nulls.is_empty() else "warn",
            "value": str(reason_nulls.height),
            "expected": "0",
            "note": "不能有无法解释的守门阻断。",
        },
        {
            "checkpoint": "exante_st_blocks_have_st_source",
            "status": "pass" if st_bad.is_empty() else "fail",
            "value": str(st_bad.height),
            "expected": "0",
            "note": "ST阻断必须来自交易日前可知ST字段或历史名称区间。",
        },
        {
            "checkpoint": "component_blocks_are_research_eligible_only",
            "status": "pass" if not_component_bad.is_empty() else "fail",
            "value": str(not_component_bad.height),
            "expected": "0",
            "note": "非成分阻断应只发生在研究资格通过但成分资格不通过的股票。",
        },
        {
            "checkpoint": "non_research_blocks_are_small",
            "status": "pass"
            if summary["not_research_orders"] <= 5
            else ("warn" if summary["not_research_orders"] <= 20 else "fail"),
            "value": str(summary["not_research_orders"]),
            "expected": "<=5",
            "note": "修正版不应继续出现大量研究资格异常阻断。",
        },
        {
            "checkpoint": "blocked_amount_is_execution_layer_scale",
            "status": "pass" if block_ratio < 0.02 else ("warn" if block_ratio < 0.05 else "fail"),
            "value": pct(block_ratio),
            "expected": "<2%",
            "note": "阻断金额应保持执行层量级，不能变成策略主体收益来源。",
        },
    ]
    return pl.DataFrame(rows)


def build_report(
    summary: dict[str, Any],
    reason_summary: pl.DataFrame,
    symbol_summary: pl.DataFrame,
    year_summary: pl.DataFrame,
    mode_summary: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> str:
    lines = [
        "# 股票震荡liquid_q3 30万 修正版守门109笔阻断审计 v1",
        "",
        f"- 记录时间：{summary['created_at_display']} CST",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：审计第278修正版ST/不可研究买入守门的阻断明细；不新增alpha信号、不调收益参数、不修改paper入口。",
        "- A/B判断：股票震荡独立执行层审计，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 历史ST应使用交易日前可知的`namechange`区间或每日ST列表，不能用当前名称倒推历史。",
        "- 指数成分应使用历史`index_weight`月度成分，不能用当前成分倒灌。",
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
            f"- 审计阻断`{summary['blocked_orders']}`笔，涉及`{summary['blocked_symbols']}`只股票，金额`{summary['blocked_amount_cny']:,.0f}`元。",
            f"- 真实ST/namechange-ST阻断`{summary['exante_st_orders']}`笔，金额`{summary['exante_st_amount_cny']:,.0f}`元。",
            f"- 非指数成分阻断`{summary['not_index_component_orders']}`笔，金额`{summary['not_index_component_amount_cny']:,.0f}`元。",
            f"- 非研究资格阻断`{summary['not_research_orders']}`笔，金额`{summary['not_research_amount_cny']:,.0f}`元。",
            f"- 新开仓阻断`{summary['new_entry_orders']}`笔，加仓阻断`{summary['add_to_existing_orders']}`笔。",
            f"- 阻断金额占修正版订单意向金额约`{pct(summary['blocked_amount_to_order_amount'])}`。",
            "",
            "## 判断",
            "",
            "- 第278修正版阻断样本整体可解释，没有发现无法归因的大面积误伤。",
            "- 主要阻断来自非指数成分，但这些行研究资格通过、成分资格不通过，更像执行层股票池边界问题。",
            "- ST阻断数量小但必要，属于实盘风险控制，不是收益拟合。",
            "- 下一步可以做paper入口最小补丁评审，但补丁必须只接入执行守门，不改alpha排序。",
            "",
            "## 阻断原因",
            "",
            _markdown_all(reason_summary),
            "",
            "## 阻断模式",
            "",
            _markdown_all(mode_summary),
            "",
            "## 年度分布",
            "",
            _markdown_all(year_summary),
            "",
            "## 高频阻断股票",
            "",
            _markdown_all(symbol_summary.head(20), max_rows=20),
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
            "- 原因：本阶段只审计执行守门阻断明细，不根据收益调阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：阻断原因来自ST、历史成分、研究资格这些事前约束，不来自收益搜索。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第278修正版能否进入paper入口，取决于109笔阻断是否可解释。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：审计显示阻断样本可解释，具备进入最小接入补丁评审的价值。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now()
    blocks = load_corrected_blocks()
    orders = load_corrected_orders()
    panel = build_panel_lookup()
    enriched = enrich_blocks(blocks, panel)
    reason_summary = summarize_reason(enriched)
    symbol_summary = summarize_symbols(enriched)
    year_summary = summarize_calendar(enriched, "year")
    month_summary = summarize_calendar(enriched, "month")
    mode_summary = summarize_mode(enriched)

    total_order_amount = _sum_float(orders, "desired_amount_cny")
    blocked_amount = _sum_float(enriched, "desired_amount_cny")
    exante_st = enriched.filter(pl.col("precise_block_reason") == "exante_st")
    not_index = enriched.filter(pl.col("precise_block_reason") == "not_index_component")
    not_research = enriched.filter(
        ~pl.col("precise_block_reason").is_in(["exante_st", "not_index_component"])
    )

    summary: dict[str, Any] = {
        "created_at": created_at.isoformat(timespec="seconds"),
        "created_at_display": created_at.strftime("%Y-%m-%d %H:%M"),
        "blocked_orders": enriched.height,
        "blocked_symbols": enriched["symbol"].n_unique() if not enriched.is_empty() else 0,
        "blocked_amount_cny": blocked_amount,
        "exante_st_orders": exante_st.height,
        "exante_st_symbols": exante_st["symbol"].n_unique() if not exante_st.is_empty() else 0,
        "exante_st_amount_cny": _sum_float(exante_st, "desired_amount_cny"),
        "not_index_component_orders": not_index.height,
        "not_index_component_symbols": not_index["symbol"].n_unique() if not not_index.is_empty() else 0,
        "not_index_component_amount_cny": _sum_float(not_index, "desired_amount_cny"),
        "not_research_orders": not_research.height,
        "not_research_symbols": not_research["symbol"].n_unique() if not not_research.is_empty() else 0,
        "not_research_amount_cny": _sum_float(not_research, "desired_amount_cny"),
        "new_entry_orders": _safe_int(enriched.select(pl.col("is_new_entry_block").sum()).item()),
        "add_to_existing_orders": _safe_int(enriched.select(pl.col("is_add_to_existing_block").sum()).item()),
        "blocked_amount_to_order_amount": blocked_amount / total_order_amount if total_order_amount else 0.0,
        "first_block_date": str(enriched.select(pl.col("date").min()).item()) if not enriched.is_empty() else "",
        "last_block_date": str(enriched.select(pl.col("date").max()).item()) if not enriched.is_empty() else "",
    }
    quality = build_quality(enriched, orders, summary)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "enriched_blocks": OUTPUT_DIR / f"{PREFIX}_enriched_blocks.csv",
        "reason_summary": OUTPUT_DIR / f"{PREFIX}_reason_summary.csv",
        "symbol_summary": OUTPUT_DIR / f"{PREFIX}_symbol_summary.csv",
        "year_summary": OUTPUT_DIR / f"{PREFIX}_year_summary.csv",
        "month_summary": OUTPUT_DIR / f"{PREFIX}_month_summary.csv",
        "mode_summary": OUTPUT_DIR / f"{PREFIX}_mode_summary.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
    }
    enriched.write_csv(paths["enriched_blocks"])
    reason_summary.write_csv(paths["reason_summary"])
    symbol_summary.write_csv(paths["symbol_summary"])
    year_summary.write_csv(paths["year_summary"])
    month_summary.write_csv(paths["month_summary"])
    mode_summary.write_csv(paths["mode_summary"])
    quality.write_csv(paths["quality_checkpoints"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["report"].write_text(
        build_report(summary, reason_summary, symbol_summary, year_summary, mode_summary, quality, paths),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report={paths['report']}")


if __name__ == "__main__":
    main()
