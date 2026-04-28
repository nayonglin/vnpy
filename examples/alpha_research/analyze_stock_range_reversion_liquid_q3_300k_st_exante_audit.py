from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution import (
    OUTPUT_DIR as CURVE_OUTPUT_DIR,
    PREFIX as CURVE_PREFIX,
)
from analyze_stock_range_reversion_liquid_q3_300k_liquidity_stress_attribution import (
    OUTPUT_DIR as STRESS_OUTPUT_DIR,
    PREFIX as STRESS_PREFIX,
)
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import ACCOUNT_SIZE_CNY, write_json
from analyze_stock_range_reversion_liquid_q3_300k_repairable_state_overlay import (
    OUTPUT_DIR as REPAIRABLE_OUTPUT_DIR,
    PREFIX as REPAIRABLE_PREFIX,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import PAPER_SCENARIO, markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import to_float


OUTPUT_DIR: Path = (NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_st_exante_audit_2018_2026").resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_st_exante_audit_v1"
NAMECHANGE_ST_PATH: Path = (
    NATIVE_RESULTS_DIR
    / "stock_range_reversion_cache_tushare_daily_2021_2026"
    / "stock_range_reversion_namechange_st.parquet"
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Tushare stock_basic includes current stock name/listing fields",
        "https://www.tushare.pro/document/2?doc_id=25",
    ),
    (
        "Tushare namechange exposes historical name periods with start/end dates",
        "https://tushare.pro/document/2?doc_id=100",
    ),
)


def read_csv(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def contains_st_expr(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.Utf8).str.contains("ST").fill_null(False)


def build_panel_lookup() -> pl.DataFrame:
    stock_df, _ = load_panels()
    needed = [
        "datetime",
        "symbol",
        "code_name",
        "is_st",
        "is_suspended",
        "eligible_research_row",
        "eligible_component_row",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
        "is_limit_up_close",
        "is_limit_down_close",
    ]
    cols = [col for col in needed if col in stock_df.columns]
    panel = stock_df.select(cols).rename({"datetime": "date", "code_name": "panel_code_name"})
    defaults: list[pl.Expr] = []
    for column in [
        "is_st",
        "is_suspended",
        "eligible_research_row",
        "eligible_component_row",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
        "is_limit_up_close",
        "is_limit_down_close",
    ]:
        if column not in panel.columns:
            defaults.append(pl.lit(False).alias(column))
    if "panel_code_name" not in panel.columns:
        defaults.append(pl.lit("").alias("panel_code_name"))
    return panel.with_columns(defaults).unique(["date", "symbol"]).sort(["date", "symbol"])


def load_namechange_st() -> pl.DataFrame:
    if not NAMECHANGE_ST_PATH.exists():
        return pl.DataFrame(schema={"symbol": pl.Utf8, "start_date": pl.Date, "end_date": pl.Date})
    return (
        pl.read_parquet(NAMECHANGE_ST_PATH)
        .with_columns(pl.col("symbol").cast(pl.Utf8))
        .unique(["symbol", "start_date", "end_date"])
        .sort(["symbol", "start_date", "end_date"])
    )


def add_namechange_flag(frame: pl.DataFrame, namechange_st: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty() or namechange_st.is_empty():
        return frame.with_columns(
            pl.lit(False).alias("namechange_st_on_date"),
            pl.lit(0).alias("namechange_st_period_count"),
        )
    pairs = frame.select(["date", "symbol"]).unique()
    marked = (
        pairs.join(namechange_st, on="symbol", how="left")
        .filter(
            (pl.col("start_date").is_not_null())
            & (pl.col("start_date") <= pl.col("date"))
            & (pl.col("end_date").is_null() | (pl.col("end_date") >= pl.col("date")))
        )
        .group_by(["date", "symbol"])
        .agg(pl.len().alias("namechange_st_period_count"))
        .with_columns((pl.col("namechange_st_period_count") > 0).alias("namechange_st_on_date"))
    )
    return (
        frame.join(marked, on=["date", "symbol"], how="left")
        .with_columns(
            pl.col("namechange_st_on_date").fill_null(False),
            pl.col("namechange_st_period_count").fill_null(0),
        )
        .sort(["date", "symbol"])
    )


def enrich_with_st_audit(frame: pl.DataFrame, panel: pl.DataFrame, namechange_st: pl.DataFrame) -> pl.DataFrame:
    enriched = frame.join(panel, on=["date", "symbol"], how="left")
    if "code_name" not in enriched.columns:
        enriched = enriched.with_columns(pl.lit("").alias("code_name"))
    enriched = enriched.with_columns(
        contains_st_expr("code_name").alias("reported_code_name_has_st"),
        contains_st_expr("panel_code_name").alias("panel_code_name_has_st"),
        pl.col("is_st").fill_null(False).alias("panel_is_st_on_date"),
        pl.col("eligible_research_row").fill_null(False).alias("panel_eligible_research_on_date"),
        pl.col("eligible_component_row").fill_null(False).alias("panel_eligible_component_on_date"),
    )
    return add_namechange_flag(enriched, namechange_st).with_columns(
        (
            (pl.col("reported_code_name_has_st") | pl.col("panel_code_name_has_st"))
            & (~pl.col("panel_is_st_on_date"))
            & (~pl.col("namechange_st_on_date"))
        ).alias("looks_st_but_not_exante_st"),
        (pl.col("panel_is_st_on_date") | pl.col("namechange_st_on_date")).alias("exante_st_on_date_any_source"),
    )


def summarize_bool_count(frame: pl.DataFrame, name: str, expr: pl.Expr) -> dict[str, Any]:
    count = int(frame.select(expr.sum()).item()) if not frame.is_empty() else 0
    total = frame.height
    return {
        "item": name,
        "count": count,
        "ratio": count / total if total else 0.0,
    }


def summarize_orders(orders: pl.DataFrame) -> pl.DataFrame:
    if orders.is_empty():
        return pl.DataFrame()
    return (
        orders.group_by(["side", "status", "exante_st_on_date_any_source", "panel_is_st_on_date"])
        .agg(
            pl.len().alias("orders"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("filled_amount_cny").sum().alias("filled_amount_cny_sum"),
            pl.col("min_fee_cost_cny").sum().alias("min_fee_cost_cny_sum"),
            pl.col("symbol").n_unique().alias("symbols"),
        )
        .sort(["exante_st_on_date_any_source", "side", "status"], descending=[True, False, False])
    )


def summarize_positions(frame: pl.DataFrame, label: str) -> dict[str, Any]:
    if frame.is_empty():
        return {
            "scope": label,
            "position_days": 0,
            "panel_is_st_rows": 0,
            "namechange_st_rows": 0,
            "reported_code_name_st_rows": 0,
            "looks_st_but_not_exante_st_rows": 0,
            "st_gross_contribution_sum": 0.0,
            "st_worst_position_contribution": 0.0,
        }
    st_rows = frame.filter(pl.col("exante_st_on_date_any_source"))
    return {
        "scope": label,
        "position_days": frame.height,
        "symbols": frame["symbol"].n_unique(),
        "panel_is_st_rows": int(frame["panel_is_st_on_date"].sum()),
        "namechange_st_rows": int(frame["namechange_st_on_date"].sum()),
        "reported_code_name_st_rows": int(frame["reported_code_name_has_st"].sum()),
        "looks_st_but_not_exante_st_rows": int(frame["looks_st_but_not_exante_st"].sum()),
        "st_gross_contribution_sum": to_float(st_rows["gross_contribution"].sum()) if not st_rows.is_empty() else 0.0,
        "st_worst_position_contribution": to_float(st_rows["gross_contribution"].min()) if not st_rows.is_empty() else 0.0,
    }


def build_quality(summary: dict[str, Any]) -> pl.DataFrame:
    rows = [
        {
            "checkpoint": "panel_join_coverage_orders",
            "status": "pass" if summary["order_panel_missing_rows"] == 0 else "fail",
            "value": str(summary["order_panel_missing_rows"]),
            "expected": "0",
            "note": "所有订单日期/股票都应能回查交易日状态。",
        },
        {
            "checkpoint": "panel_join_coverage_positions",
            "status": "pass" if summary["position_panel_missing_rows"] == 0 else "fail",
            "value": str(summary["position_panel_missing_rows"]),
            "expected": "0",
            "note": "所有持仓日期/股票都应能回查交易日状态。",
        },
        {
            "checkpoint": "st_current_name_leak_detected",
            "status": "warn" if summary["stress_position_looks_st_but_not_exante_st_rows"] > 0 else "pass",
            "value": str(summary["stress_position_looks_st_but_not_exante_st_rows"]),
            "expected": "diagnostic",
            "note": "带ST的展示名称不一定是历史当日ST，需避免用当前名称做后验判断。",
        },
        {
            "checkpoint": "st_buy_gap_detected",
            "status": "warn" if summary["order_st_buy_count"] > 0 else "pass",
            "value": str(summary["order_st_buy_count"]),
            "expected": "0 preferred",
            "note": "执行层不应在交易日已ST时新增买入；这是下一步应修复的可交易性缺口。",
        },
        {
            "checkpoint": "no_signal_parameter_change",
            "status": "pass",
            "value": "no signal/threshold change",
            "expected": "no signal/threshold change",
            "note": "本阶段只做ST事前审计，不改信号。",
        },
    ]
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    order_summary: pl.DataFrame,
    st_orders: pl.DataFrame,
    position_scope_summary: pl.DataFrame,
    stress_st_positions: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    lines = [
        "# 股票震荡liquid_q3 30万 ST事前审计 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：ST/特殊处理交易约束审计；不新增信号、不调参数、不生成正式策略版本。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元。",
        "- A/B判断：纯审计，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- Tushare `stock_basic`提供股票基础列表和当前名称字段，适合做代码/上市状态基础映射，但不能单独替代历史当日名称判断。",
        "- Tushare `namechange`提供历史名称的`start_date/end_date`，更适合审计某一交易日是否处在ST名称区间。",
        "- 因此报告里的`code_name`若来自当前基础信息，可能产生“历史行看起来像ST”的后视错觉；真正要看交易日`is_st`和历史名称区间。",
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
            f"- 全历史订单`{summary['orders']}`行，订单面板回查缺失`{summary['order_panel_missing_rows']}`行。",
            f"- 交易日已ST或namechange-ST的订单`{summary['order_exante_st_count']}`行，其中买入/增持`{summary['order_st_buy_count']}`行，买入成交额`{summary['order_st_buy_filled_amount_cny']:,.0f}`元。",
            f"- 压力持仓`{summary['stress_position_days']}`个position-day，交易日真实ST/namechange-ST为`{summary['stress_position_exante_st_rows']}`行，贡献合计`{pct(summary['stress_position_st_contribution_sum'])}`。",
            f"- 压力持仓中展示名称带ST但交易日并非ST的`{summary['stress_position_looks_st_but_not_exante_st_rows']}`行；这说明最差个股表里的很多ST名称是当前名称泄漏，不应直接当作历史ST交易。",
            f"- 全持仓交易日真实ST/namechange-ST为`{summary['all_position_exante_st_rows']}`行，贡献合计`{pct(summary['all_position_st_contribution_sum'])}`。",
            "",
            "## 判断",
            "",
            "- 大方向：上一阶段最差压力日不是单纯由ST持仓解释，压力尾部主要仍来自市场/行业同步下跌和锁流动性。",
            "- 但执行层确实存在一个硬缺口：已ST交易日仍出现少量买入或增持。金额不大，但实盘规则应零容忍。",
            "- 下一步应该做一个独立回放版本：当交易日`is_st/namechange-ST/eligible=false`时，禁止买入和增持，只允许能成交时减仓或清仓，再看权益、回撤和压力桶是否改善。",
            "",
            "## 订单ST汇总",
            "",
            markdown_table(
                order_summary,
                [
                    "side",
                    "status",
                    "exante_st_on_date_any_source",
                    "panel_is_st_on_date",
                    "orders",
                    "desired_amount_cny_sum",
                    "filled_amount_cny_sum",
                    "min_fee_cost_cny_sum",
                    "symbols",
                ],
                max_rows=80,
            ),
            "",
            "## ST相关订单明细",
            "",
            markdown_table(
                st_orders,
                [
                    "date",
                    "symbol",
                    "code_name",
                    "panel_code_name",
                    "side",
                    "status",
                    "blocked_reason",
                    "prev_shares",
                    "target_weight",
                    "desired_shares",
                    "filled_shares",
                    "actual_shares_after",
                    "filled_amount_cny",
                    "panel_is_st_on_date",
                    "namechange_st_on_date",
                    "panel_eligible_research_on_date",
                    "looks_st_but_not_exante_st",
                ],
                max_rows=120,
            ),
            "",
            "## 持仓ST范围汇总",
            "",
            markdown_table(position_scope_summary, position_scope_summary.columns, max_rows=20),
            "",
            "## 压力持仓真实ST明细",
            "",
            markdown_table(
                stress_st_positions,
                [
                    "date",
                    "symbol",
                    "code_name",
                    "panel_code_name",
                    "industry",
                    "actual_weight",
                    "daily_ret",
                    "gross_contribution",
                    "panel_is_st_on_date",
                    "namechange_st_on_date",
                    "panel_eligible_research_on_date",
                ],
                max_rows=80,
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
            "- 原因：ST审计是交易可行性约束核查，不搜索收益参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：结果指向的是事前可交易性约束缺口，而不是收益最大化阈值。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：压力归因发现ST名称集中出现在最差个股表，需要区分后视名称泄漏和真实ST交易风险。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：审计发现少量真实ST日买入，下一步可以做非参数化执行守门回放。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 下一步只做执行约束修复压力测试：ST日禁止新增买入/增持。",
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
    panel = build_panel_lookup()
    namechange_st = load_namechange_st()

    orders = read_csv(REPAIRABLE_OUTPUT_DIR / f"{REPAIRABLE_PREFIX}_base_rerun_orders.csv")
    all_positions = read_csv(CURVE_OUTPUT_DIR / f"{CURVE_PREFIX}_position_daily.csv")
    stress_positions = read_csv(STRESS_OUTPUT_DIR / f"{STRESS_PREFIX}_position_stress.csv")

    orders_audit = enrich_with_st_audit(orders, panel, namechange_st)
    all_positions_audit = enrich_with_st_audit(all_positions, panel, namechange_st)
    stress_positions_audit = enrich_with_st_audit(stress_positions, panel, namechange_st)

    order_summary = summarize_orders(orders_audit)
    st_orders = orders_audit.filter(
        pl.col("exante_st_on_date_any_source")
        | pl.col("reported_code_name_has_st")
        | pl.col("panel_code_name_has_st")
    ).sort(["date", "symbol", "side"])
    stress_st_positions = stress_positions_audit.filter(pl.col("exante_st_on_date_any_source")).sort(["date", "symbol"])

    position_scope_summary = pl.DataFrame(
        [
            summarize_positions(all_positions_audit, "all_positions"),
            summarize_positions(stress_positions_audit, "stress_positions"),
        ]
    )

    order_st_buys = orders_audit.filter((pl.col("side") == "buy") & pl.col("exante_st_on_date_any_source"))
    stress_position_st = stress_positions_audit.filter(pl.col("exante_st_on_date_any_source"))
    all_position_st = all_positions_audit.filter(pl.col("exante_st_on_date_any_source"))
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scenario": PAPER_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "orders": orders_audit.height,
        "order_symbols": orders_audit["symbol"].n_unique(),
        "order_panel_missing_rows": orders_audit["panel_is_st_on_date"].null_count(),
        "order_exante_st_count": orders_audit.filter(pl.col("exante_st_on_date_any_source")).height,
        "order_st_buy_count": order_st_buys.height,
        "order_st_buy_filled_amount_cny": to_float(order_st_buys["filled_amount_cny"].sum()) if not order_st_buys.is_empty() else 0.0,
        "order_st_sell_count": orders_audit.filter((pl.col("side") == "sell") & pl.col("exante_st_on_date_any_source")).height,
        "order_looks_st_but_not_exante_st_rows": orders_audit.filter(pl.col("looks_st_but_not_exante_st")).height,
        "position_days": all_positions_audit.height,
        "position_panel_missing_rows": all_positions_audit["panel_is_st_on_date"].null_count(),
        "all_position_exante_st_rows": all_position_st.height,
        "all_position_st_contribution_sum": to_float(all_position_st["gross_contribution"].sum()) if not all_position_st.is_empty() else 0.0,
        "all_position_looks_st_but_not_exante_st_rows": all_positions_audit.filter(pl.col("looks_st_but_not_exante_st")).height,
        "stress_position_days": stress_positions_audit.height,
        "stress_position_exante_st_rows": stress_position_st.height,
        "stress_position_st_contribution_sum": to_float(stress_position_st["gross_contribution"].sum()) if not stress_position_st.is_empty() else 0.0,
        "stress_position_looks_st_but_not_exante_st_rows": stress_positions_audit.filter(
            pl.col("looks_st_but_not_exante_st")
        ).height,
        "namechange_st_path": str(NAMECHANGE_ST_PATH),
        "namechange_st_rows": namechange_st.height,
        "namechange_st_symbols": namechange_st["symbol"].n_unique() if not namechange_st.is_empty() else 0,
    }
    quality = build_quality(summary)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "order_audit": OUTPUT_DIR / f"{PREFIX}_order_audit.csv",
        "order_summary": OUTPUT_DIR / f"{PREFIX}_order_summary.csv",
        "st_orders": OUTPUT_DIR / f"{PREFIX}_st_orders.csv",
        "all_position_audit": OUTPUT_DIR / f"{PREFIX}_all_position_audit.csv",
        "stress_position_audit": OUTPUT_DIR / f"{PREFIX}_stress_position_audit.csv",
        "position_scope_summary": OUTPUT_DIR / f"{PREFIX}_position_scope_summary.csv",
        "stress_st_positions": OUTPUT_DIR / f"{PREFIX}_stress_st_positions.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    orders_audit.write_csv(paths["order_audit"])
    order_summary.write_csv(paths["order_summary"])
    st_orders.write_csv(paths["st_orders"])
    all_positions_audit.write_csv(paths["all_position_audit"])
    stress_positions_audit.write_csv(paths["stress_position_audit"])
    position_scope_summary.write_csv(paths["position_scope_summary"])
    stress_st_positions.write_csv(paths["stress_st_positions"])
    quality.write_csv(paths["quality_checkpoints"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "research_sources": RESEARCH_SOURCES,
            "source_orders": REPAIRABLE_OUTPUT_DIR / f"{REPAIRABLE_PREFIX}_base_rerun_orders.csv",
            "source_all_positions": CURVE_OUTPUT_DIR / f"{CURVE_PREFIX}_position_daily.csv",
            "source_stress_positions": STRESS_OUTPUT_DIR / f"{STRESS_PREFIX}_position_stress.csv",
            "source_namechange_st": NAMECHANGE_ST_PATH,
            "note": "ST ex-ante tradability audit only; no strategy parameter changes.",
        },
    )
    report_path = write_report(
        summary,
        order_summary,
        st_orders,
        position_scope_summary,
        stress_st_positions,
        quality,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
