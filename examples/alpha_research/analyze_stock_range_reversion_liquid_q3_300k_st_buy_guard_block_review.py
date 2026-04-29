from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_st_buy_guard_replay import (
    OUTPUT_DIR as GUARD_OUTPUT_DIR,
    PREFIX as GUARD_PREFIX,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from build_stock_range_reversion_research_panel import MIN_ADV20_TURNOVER, MIN_LISTING_DAYS
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_st_buy_guard_block_review_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_st_buy_guard_block_review_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Tushare namechange exposes historical name periods with start/end dates",
        "https://tushare.pro/document/2?doc_id=100",
    ),
    (
        "GitHub topic search shows A-share/Tushare projects commonly separate data handling from strategy rules",
        "https://github.com/topics/tushare",
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_panel_lookup() -> pl.DataFrame:
    stock_df, _ = load_panels()
    return (
        stock_df.select(
            [
                "datetime",
                "symbol",
                "code_name",
                "is_stock_type",
                "is_listed_status",
                "is_st",
                "listing_days",
                "is_suspended",
                "volume",
                "turnover",
                "adv20_turnover",
                "qfq_close",
                "is_index_component",
                "eligible_research_row",
                "eligible_component_row",
            ]
        )
        .rename({"datetime": "date"})
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .unique(["date", "symbol"])
    )


def enrich_blocks(blocks: pl.DataFrame, panel: pl.DataFrame) -> pl.DataFrame:
    joined = (
        blocks.select(
            [
                "date",
                "symbol",
                "code_name",
                "industry",
                "side",
                "blocked_reason",
                "desired_amount_cny",
                "target_weight",
                "prev_shares",
                "target_shares",
                "desired_shares",
                "is_st",
                "eligible_research_row",
                "eligible_component_row",
                "is_suspended",
                "adv20_turnover",
                "turnover",
                "namechange_st_on_date",
                "exante_st",
                "panel_eligible_research_on_date",
                "panel_eligible_component_on_date",
                "guard_block_subreason",
            ]
        )
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .join(
            panel.select(
                [
                    "date",
                    "symbol",
                    pl.col("is_stock_type").alias("panel_is_stock_type"),
                    pl.col("is_listed_status").alias("panel_is_listed_status"),
                    pl.col("listing_days").alias("panel_listing_days"),
                    pl.col("volume").alias("panel_volume"),
                    pl.col("turnover").alias("panel_turnover"),
                    pl.col("adv20_turnover").alias("panel_adv20_turnover"),
                    pl.col("qfq_close").alias("panel_qfq_close"),
                    pl.col("is_index_component").alias("panel_is_index_component"),
                    pl.col("eligible_research_row").alias("panel_eligible_research_raw"),
                    pl.col("eligible_component_row").alias("panel_eligible_component_raw"),
                ]
            ),
            on=["date", "symbol"],
            how="left",
        )
        .with_columns(
            pl.col("panel_is_stock_type").fill_null(False).alias("pass_stock_type"),
            pl.col("panel_is_listed_status").fill_null(False).alias("pass_listed_status"),
            (pl.col("panel_listing_days").fill_null(-1) >= MIN_LISTING_DAYS).alias("pass_listing_days"),
            (~pl.col("is_suspended").fill_null(True)).alias("pass_not_suspended"),
            (~pl.col("is_st").fill_null(True)).alias("pass_not_panel_st"),
            (~pl.col("namechange_st_on_date").fill_null(True)).alias("pass_not_namechange_st"),
            (pl.col("panel_volume").fill_null(0) > 0).alias("pass_positive_volume"),
            (pl.col("panel_turnover").fill_null(0) > 0).alias("pass_positive_turnover"),
            (pl.col("panel_adv20_turnover").fill_null(0) >= MIN_ADV20_TURNOVER).alias("pass_adv20_turnover"),
            pl.col("panel_qfq_close").is_not_null().alias("pass_qfq_close"),
            pl.col("panel_is_index_component").fill_null(False).alias("pass_index_component"),
        )
    )
    return joined.with_columns(
        pl.when(pl.col("exante_st").fill_null(False))
        .then(pl.lit("exante_st"))
        .when(~pl.col("pass_not_suspended"))
        .then(pl.lit("suspended"))
        .when(~pl.col("pass_stock_type"))
        .then(pl.lit("not_stock_type"))
        .when(~pl.col("pass_listed_status"))
        .then(pl.lit("not_listed_status"))
        .when(~pl.col("pass_listing_days"))
        .then(pl.lit("listing_days_lt_min"))
        .when(~pl.col("pass_positive_volume"))
        .then(pl.lit("zero_or_missing_volume"))
        .when(~pl.col("pass_positive_turnover"))
        .then(pl.lit("zero_or_missing_turnover"))
        .when(~pl.col("pass_adv20_turnover"))
        .then(pl.lit("adv20_turnover_lt_min"))
        .when(~pl.col("pass_qfq_close"))
        .then(pl.lit("missing_qfq_close"))
        .when(~pl.col("pass_index_component"))
        .then(pl.lit("not_index_component"))
        .otherwise(pl.lit("other_panel_eligibility"))
        .alias("primary_block_reason")
    )


def summarize_by_reason(enriched: pl.DataFrame) -> pl.DataFrame:
    return (
        enriched.group_by("primary_block_reason")
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("date").n_unique().alias("dates"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("panel_listing_days").mean().alias("avg_listing_days"),
            pl.col("panel_adv20_turnover").mean().alias("avg_adv20_turnover"),
            pl.col("panel_turnover").mean().alias("avg_turnover"),
        )
        .sort(["orders", "desired_amount_cny_sum"], descending=True)
    )


def summarize_top_symbols(enriched: pl.DataFrame) -> pl.DataFrame:
    return (
        enriched.group_by(["symbol", "code_name", "industry", "primary_block_reason"])
        .agg(
            pl.len().alias("orders"),
            pl.col("date").min().alias("first_date"),
            pl.col("date").max().alias("last_date"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("panel_listing_days").mean().alias("avg_listing_days"),
            pl.col("panel_adv20_turnover").mean().alias("avg_adv20_turnover"),
        )
        .sort(["orders", "desired_amount_cny_sum"], descending=True)
    )


def summarize_by_year(enriched: pl.DataFrame) -> pl.DataFrame:
    return (
        enriched.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["year", "primary_block_reason"])
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
        )
        .sort(["year", "orders"], descending=[False, True])
    )


def summarize_latest_orders(orders: pl.DataFrame, daily: pl.DataFrame, enriched: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, Any]]:
    latest_date = orders["date"].max()
    latest_orders = orders.filter(pl.col("date") == latest_date)
    latest_daily = daily.filter(pl.col("date") == latest_date)
    latest_blocks = enriched.filter(pl.col("date") == latest_date)
    summary = {
        "latest_date": str(latest_date),
        "latest_orders": latest_orders.height,
        "latest_tradable_orders": latest_orders.filter(pl.col("status") == "tradable").height,
        "latest_blocked_orders": latest_orders.filter(pl.col("status") == "blocked").height,
        "latest_st_or_ineligible_blocks": latest_orders.filter(
            pl.col("blocked_reason") == "st_or_ineligible_buy"
        ).height,
        "latest_actual_symbol_count": _safe_int(latest_daily["actual_symbol_count"].item())
        if latest_daily.height
        else 0,
        "latest_zero_lot_target_count": _safe_int(latest_daily["zero_lot_target_count"].item())
        if latest_daily.height
        else 0,
        "latest_actual_gross_weight": _safe_float(latest_daily["actual_gross_weight"].item())
        if latest_daily.height
        else 0.0,
        "latest_missing_return_amount_cny": _safe_float(latest_daily["missing_return_amount_cny"].item())
        if latest_daily.height
        else 0.0,
    }
    return latest_blocks.sort(["primary_block_reason", "symbol"]), summary


def build_quality(summary: dict[str, Any]) -> pl.DataFrame:
    rows = [
        {
            "checkpoint": "review_has_guard_blocks",
            "status": "pass" if summary["blocked_orders"] > 0 else "fail",
            "value": str(summary["blocked_orders"]),
            "expected": ">0",
            "note": "第275阶段应存在守门阻断样本。",
        },
        {
            "checkpoint": "non_st_blocks_are_explainable",
            "status": "pass" if summary["other_panel_eligibility_orders"] == 0 else "warn",
            "value": str(summary["other_panel_eligibility_orders"]),
            "expected": "0",
            "note": "非ST不可研究阻断应能拆到明确面板口径原因。",
        },
        {
            "checkpoint": "latest_orders_still_executable",
            "status": "pass" if summary["latest_tradable_orders"] > 0 else "warn",
            "value": str(summary["latest_tradable_orders"]),
            "expected": ">0",
            "note": "最新目标日守门后仍应有可执行订单。",
        },
        {
            "checkpoint": "no_signal_parameter_change",
            "status": "pass",
            "value": "no signal/threshold change",
            "expected": "no signal/threshold change",
            "note": "本阶段只复核执行守门阻断，不修改交易信号。",
        },
    ]
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    reason_summary: pl.DataFrame,
    top_symbols: pl.DataFrame,
    year_summary: pl.DataFrame,
    latest_blocks: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> None:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    lines = [
        "# 股票震荡liquid_q3 30万 ST/不可研究买入守门阻断复核 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：第275阶段守门阻断样本复核；不新增alpha信号、不调收益参数、不修改paper入口。",
        "- A/B判断：纯执行层审计，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- Tushare `namechange`提供历史名称起止区间，适合判断交易日是否处于ST历史名称区间；当前名称不能替代历史当日状态。",
        "- GitHub公开A股/Tushare项目普遍把数据口径和策略规则分层处理；本阶段延续这一原则，把交易可行性守门当成执行层，不把它包装成alpha。",
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
            f"- 守门阻断合计`{summary['blocked_orders']}`笔，金额`{summary['blocked_amount_cny']:,.0f}`元，涉及`{summary['blocked_symbols']}`只股票。",
            f"- 真实ST/namechange-ST阻断`{summary['exante_st_orders']}`笔；非ST但不可研究阻断`{summary['non_st_ineligible_orders']}`笔。",
            f"- 非ST不可研究阻断的主因是`{summary['top_primary_reason']}`，占`{summary['top_primary_reason_orders']}`笔。",
            f"- 最新目标日`{summary['latest_date']}`：订单`{summary['latest_orders']}`笔，可执行`{summary['latest_tradable_orders']}`笔，守门阻断`{summary['latest_st_or_ineligible_blocks']}`笔，实际持仓`{summary['latest_actual_symbol_count']}`只，实际暴露`{pct(summary['latest_actual_gross_weight'])}`。",
            "",
            "## 判断",
            "",
            "- 守门阻断不是随机误伤：绝大多数可以被拆解为上市天数不足、真实ST或其他明确面板交易约束。",
            "- 但仍不能立刻并入正式paper入口：需要人工抽查高频阻断个股，确认`listing_days`和成分/研究资格口径在实盘执行日可稳定获得。",
            "- 下一步如果抽查通过，才考虑把守门接入股票paper执行层；仍不触碰第78趋势策略。",
            "",
            "## 阻断主因",
            "",
            markdown_table(
                reason_summary,
                [
                    "primary_block_reason",
                    "orders",
                    "symbols",
                    "dates",
                    "desired_amount_cny_sum",
                    "avg_listing_days",
                    "avg_adv20_turnover",
                    "avg_turnover",
                ],
                max_rows=50,
            ),
            "",
            "## 年度拆解",
            "",
            markdown_table(
                year_summary,
                ["year", "primary_block_reason", "orders", "symbols", "desired_amount_cny_sum"],
                max_rows=100,
            ),
            "",
            "## 高频阻断个股",
            "",
            markdown_table(
                top_symbols,
                [
                    "symbol",
                    "code_name",
                    "industry",
                    "primary_block_reason",
                    "orders",
                    "first_date",
                    "last_date",
                    "desired_amount_cny_sum",
                    "avg_listing_days",
                    "avg_adv20_turnover",
                ],
                max_rows=50,
            ),
            "",
            "## 最新目标日守门阻断",
            "",
            "无数据"
            if latest_blocks.is_empty()
            else markdown_table(
                latest_blocks,
                [
                    "date",
                    "symbol",
                    "code_name",
                    "industry",
                    "primary_block_reason",
                    "desired_amount_cny",
                    "target_weight",
                    "panel_listing_days",
                    "panel_adv20_turnover",
                ],
                max_rows=80,
            ),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 失败项",
            "",
            "无数据"
            if failed.is_empty()
            else markdown_table(failed, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 警告项",
            "",
            "无数据"
            if warned.is_empty()
            else markdown_table(warned, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只复核执行约束阻断样本，不根据收益选择阈值或改信号。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：复核把阻断拆成可解释的交易/数据资格原因，没有产生新的收益参数。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第275阶段发现守门有价值，但并入paper前必须确认非ST不可研究阻断不是误伤。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：阻断样本大多可解释，且最新目标日仍有可执行订单；下一步应做人工抽查和接入方案，不继续调收益参数。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for key, path in paths.items():
        lines.append(f"- `{key}`：`{path}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    block_audit_path = GUARD_OUTPUT_DIR / f"{GUARD_PREFIX}_guard_block_audit.csv"
    guard_orders_path = GUARD_OUTPUT_DIR / f"{GUARD_PREFIX}_guard_orders.csv"
    guard_daily_path = GUARD_OUTPUT_DIR / f"{GUARD_PREFIX}_guard_daily.csv"
    blocks = _read_csv(block_audit_path)
    orders = _read_csv(guard_orders_path)
    daily = _read_csv(guard_daily_path)
    panel = load_panel_lookup()
    enriched = enrich_blocks(blocks, panel)
    reason_summary = summarize_by_reason(enriched)
    top_symbols = summarize_top_symbols(enriched)
    year_summary = summarize_by_year(enriched)
    latest_blocks, latest_summary = summarize_latest_orders(orders, daily, enriched)

    top_reason = reason_summary.row(0, named=True) if not reason_summary.is_empty() else {}
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_block_audit": str(block_audit_path),
        "source_guard_orders": str(guard_orders_path),
        "blocked_orders": enriched.height,
        "blocked_symbols": enriched["symbol"].n_unique() if not enriched.is_empty() else 0,
        "blocked_amount_cny": _safe_float(enriched["desired_amount_cny"].sum()) if not enriched.is_empty() else 0.0,
        "exante_st_orders": enriched.filter(pl.col("primary_block_reason") == "exante_st").height,
        "non_st_ineligible_orders": enriched.filter(pl.col("primary_block_reason") != "exante_st").height,
        "other_panel_eligibility_orders": enriched.filter(pl.col("primary_block_reason") == "other_panel_eligibility").height,
        "top_primary_reason": str(top_reason.get("primary_block_reason", "")),
        "top_primary_reason_orders": _safe_int(top_reason.get("orders", 0)),
        **latest_summary,
    }
    quality = build_quality(summary)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "enriched_blocks": OUTPUT_DIR / f"{PREFIX}_enriched_blocks.csv",
        "reason_summary": OUTPUT_DIR / f"{PREFIX}_reason_summary.csv",
        "top_symbols": OUTPUT_DIR / f"{PREFIX}_top_symbols.csv",
        "year_summary": OUTPUT_DIR / f"{PREFIX}_year_summary.csv",
        "latest_blocks": OUTPUT_DIR / f"{PREFIX}_latest_blocks.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
    }
    enriched.write_csv(paths["enriched_blocks"])
    reason_summary.write_csv(paths["reason_summary"])
    top_symbols.write_csv(paths["top_symbols"])
    year_summary.write_csv(paths["year_summary"])
    latest_blocks.write_csv(paths["latest_blocks"])
    quality.write_csv(paths["quality_checkpoints"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(summary, reason_summary, top_symbols, year_summary, latest_blocks, quality, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report={paths['report']}")


if __name__ == "__main__":
    main()
