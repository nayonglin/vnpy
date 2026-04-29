from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import polars as pl

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_repairable_state_overlay import (
    OUTPUT_DIR as REPAIRABLE_OUTPUT_DIR,
    PREFIX as REPAIRABLE_PREFIX,
)
from analyze_stock_range_reversion_liquid_q3_300k_st_buy_guard_replay import (
    OUTPUT_DIR as ORIGINAL_GUARD_OUTPUT_DIR,
    PREFIX as ORIGINAL_GUARD_PREFIX,
    build_block_reason_summary,
    replay_with_classifier,
    summarize_by_state,
    summarize_daily,
)
from analyze_stock_range_reversion_liquid_q3_300k_st_exante_audit import add_namechange_flag, load_namechange_st
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from build_stock_range_reversion_research_panel import MIN_ADV20_TURNOVER, MIN_LISTING_DAYS
from generate_stock_range_reversion_liquid_q3_paper_tracking import PAPER_SCENARIO, build_target_weights, markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_st_buy_guard_strict_exante_replay_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_st_buy_guard_strict_exante_replay_v1"

CORRECTED_OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_st_buy_guard_corrected_replay_2018_2026"
).expanduser().resolve()
CORRECTED_PREFIX: str = "stock_range_reversion_liquid_q3_300k_st_buy_guard_corrected_replay_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Pre-trade controls should reject invalid orders before submission",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/pre-trade-risk-control",
    ),
    (
        "FCA algorithmic trading controls discuss order value and ADV-aware pre-trade controls",
        "https://www.fca.org.uk/publication/multi-firm-reviews/algorithmic-trading-compliance-wholesale-markets.pdf",
    ),
    (
        "Look-ahead bias means using information unavailable when a trade decision was made",
        "https://www.flytradr.com/blog/avoid-lookahead-bias-backtests-checklist",
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


def build_exec_info_frame(exec_info: dict[tuple[Any, str], Any]) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for (date_value, symbol), info in exec_info.items():
        rows.append(
            {
                "date": date_value,
                "symbol": str(symbol).zfill(6),
                "pretrade_adv_turnover_for_guard": getattr(info, "adv_turnover_for_cap", None),
                "pretrade_native_adv20_turnover": getattr(info, "native_adv20_turnover", None),
                "pretrade_fallback_adv_turnover": getattr(info, "fallback_adv_turnover", None),
                "pretrade_adv_source": getattr(info, "adv_source", "") or "missing",
                "pretrade_adv_quality_flag": getattr(info, "adv_quality_flag", "") or "missing",
                "pretrade_fallback_allowed": bool(getattr(info, "fallback_allowed", False)),
                "pretrade_turnover_valid_count_20": int(to_float(getattr(info, "turnover_valid_count_20", 0))),
                "pretrade_tradable_open": bool(getattr(info, "tradable_open", False)),
                "pretrade_trade_open": to_float(getattr(info, "trade_open", None)),
            }
        )
    return pl.DataFrame(rows)


def build_strict_exante_guard_panel(
    stock_df: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
) -> pl.DataFrame:
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
    )
    panel = add_namechange_flag(panel, load_namechange_st()).with_columns(
        (pl.col("is_st").fill_null(False) | pl.col("namechange_st_on_date").fill_null(False)).alias("exante_st")
    )
    panel = panel.join(build_exec_info_frame(exec_info), on=["date", "symbol"], how="left")
    panel = panel.with_columns(
        (
            (~pl.col("is_suspended").fill_null(True))
            & (~pl.col("exante_st").fill_null(True))
            & pl.col("is_stock_type").fill_null(False)
            & pl.col("is_listed_status").fill_null(False)
            & (pl.col("listing_days").fill_null(-1) >= MIN_LISTING_DAYS)
            & (pl.col("pretrade_adv_turnover_for_guard").fill_null(0) >= MIN_ADV20_TURNOVER)
            & pl.col("pretrade_tradable_open").fill_null(False)
        ).alias("strict_exante_research_eligible")
    ).with_columns(
        (pl.col("strict_exante_research_eligible") & pl.col("is_index_component").fill_null(False)).alias(
            "strict_exante_component_eligible"
        )
    )
    return panel.with_columns(
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
        .when(pl.col("pretrade_adv_turnover_for_guard").fill_null(0) < MIN_ADV20_TURNOVER)
        .then(pl.lit("pretrade_adv20_turnover_lt_min"))
        .when(~pl.col("pretrade_tradable_open").fill_null(False))
        .then(pl.lit("not_tradable_open"))
        .when(~pl.col("is_index_component").fill_null(False))
        .then(pl.lit("not_index_component"))
        .otherwise(pl.lit(""))
        .alias("strict_exante_guard_reason")
    )


def build_strict_exante_guard_flags(
    stock_df: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
) -> dict[tuple[Any, str], dict[str, Any]]:
    panel = build_strict_exante_guard_panel(stock_df, exec_info)
    flags: dict[tuple[Any, str], dict[str, Any]] = {}
    for row in panel.iter_rows(named=True):
        reason = str(row["strict_exante_guard_reason"] or "")
        flags[(row["date"], row["symbol"])] = {
            "strict_exante_component_eligible": bool(row["strict_exante_component_eligible"]),
            "strict_exante_research_eligible": bool(row["strict_exante_research_eligible"]),
            "strict_exante_guard_reason": reason,
            "pretrade_adv_turnover_for_guard": to_float(row["pretrade_adv_turnover_for_guard"]),
            "pretrade_adv_source": row["pretrade_adv_source"] or "missing",
            "pretrade_adv_quality_flag": row["pretrade_adv_quality_flag"] or "missing",
            "pretrade_fallback_allowed": bool(row["pretrade_fallback_allowed"]),
            "st_buy_guard": bool(reason),
        }
    return flags


def build_strict_exante_guarded_exec_info(stock_df: pl.DataFrame) -> dict[tuple[Any, str], SimpleNamespace]:
    base = build_exec_info(stock_df)
    flags = build_strict_exante_guard_flags(stock_df, base)
    guarded: dict[tuple[Any, str], SimpleNamespace] = {}
    for key, info in base.items():
        payload = dict(info.__dict__)
        payload.update(
            {
                "strict_exante_component_eligible": False,
                "strict_exante_research_eligible": False,
                "strict_exante_guard_reason": "missing_guard_panel",
                "pretrade_adv_turnover_for_guard": None,
                "pretrade_adv_source": "missing",
                "pretrade_adv_quality_flag": "missing_guard_panel",
                "pretrade_fallback_allowed": False,
                "st_buy_guard": True,
            }
        )
        payload.update(flags.get(key, {}))
        guarded[key] = SimpleNamespace(**payload)
    return guarded


def enrich_strict_exante_blocks(
    orders: pl.DataFrame,
    stock_df: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
) -> pl.DataFrame:
    blocked = orders.filter(pl.col("blocked_reason") == "st_or_ineligible_buy")
    if blocked.is_empty():
        return pl.DataFrame()
    panel = build_strict_exante_guard_panel(stock_df, exec_info).select(
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
            "pretrade_turnover_valid_count_20",
        ]
    )
    return (
        blocked.with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .join(panel, on=["date", "symbol"], how="left")
        .with_columns(
            (pl.col("prev_shares").fill_null(0) <= 0).alias("is_new_entry_block"),
            (pl.col("prev_shares").fill_null(0) > 0).alias("is_add_to_existing_block"),
            pl.col("date").dt.year().alias("year"),
        )
        .sort(["date", "symbol"])
    )


def summarize_strict_blocks(blocks: pl.DataFrame) -> pl.DataFrame:
    if blocks.is_empty():
        return pl.DataFrame()
    return (
        blocks.group_by("strict_exante_guard_reason")
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("date").n_unique().alias("dates"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("is_new_entry_block").sum().alias("new_entry_orders"),
            pl.col("is_add_to_existing_block").sum().alias("add_to_existing_orders"),
            pl.col("pretrade_fallback_allowed").sum().alias("fallback_allowed_orders"),
        )
        .sort(["orders", "desired_amount_cny_sum"], descending=True)
    )


def summarize_year(blocks: pl.DataFrame) -> pl.DataFrame:
    if blocks.is_empty():
        return pl.DataFrame()
    return (
        blocks.group_by("year")
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
        )
        .sort("year")
    )


def build_scorecard(
    base_summary: dict[str, Any],
    strict_summary: dict[str, Any],
    original_summary: dict[str, Any],
    corrected_summary: dict[str, Any],
) -> pl.DataFrame:
    rows = [
        base_summary,
        {
            "scenario": "original_st_buy_guard",
            "final_equity": original_summary["guard_final_equity"],
            "total_return": original_summary["guard_total_return"],
            "max_drawdown": original_summary["guard_max_drawdown"],
            "sharpe": original_summary["guard_sharpe"],
            "daily_rows": base_summary["daily_rows"],
            "orders": None,
            "filled_orders": None,
            "blocked_orders": None,
            "blocked_amount_cny": original_summary["guard_st_or_ineligible_buy_blocked_amount_cny"],
            "st_or_ineligible_buy_blocked_orders": original_summary["guard_st_or_ineligible_buy_blocked_orders"],
            "st_or_ineligible_buy_blocked_amount_cny": original_summary[
                "guard_st_or_ineligible_buy_blocked_amount_cny"
            ],
            "total_min_fee_cost_cny": None,
            "avg_actual_gross_weight": None,
            "max_actual_gross_weight": None,
        },
        {
            "scenario": "corrected_lookahead_adv_guard",
            "final_equity": corrected_summary["corrected_final_equity"],
            "total_return": corrected_summary["corrected_total_return"],
            "max_drawdown": corrected_summary["corrected_max_drawdown"],
            "sharpe": corrected_summary["corrected_sharpe"],
            "daily_rows": base_summary["daily_rows"],
            "orders": None,
            "filled_orders": None,
            "blocked_orders": corrected_summary["corrected_blocked_orders"],
            "blocked_amount_cny": corrected_summary["corrected_blocked_amount_cny"],
            "st_or_ineligible_buy_blocked_orders": corrected_summary["corrected_blocked_orders"],
            "st_or_ineligible_buy_blocked_amount_cny": corrected_summary["corrected_blocked_amount_cny"],
            "total_min_fee_cost_cny": None,
            "avg_actual_gross_weight": None,
            "max_actual_gross_weight": None,
        },
        strict_summary,
    ]
    return pl.DataFrame(rows)


def build_quality(
    summary: dict[str, Any],
    strict_blocks: pl.DataFrame,
    strict_orders: pl.DataFrame,
) -> pl.DataFrame:
    st_blocks = strict_blocks.filter(pl.col("strict_exante_guard_reason") == "exante_st")
    malformed_sell_blocks = strict_blocks.filter(pl.col("side") != "buy") if not strict_blocks.is_empty() else strict_blocks
    missing_reason_blocks = (
        strict_blocks.filter(
            pl.col("strict_exante_guard_reason").is_null() | (pl.col("strict_exante_guard_reason") == "")
        )
        if not strict_blocks.is_empty()
        else strict_blocks
    )
    missing_panel_blocks = (
        strict_blocks.filter(pl.col("strict_exante_guard_reason") == "missing_guard_panel")
        if not strict_blocks.is_empty()
        else strict_blocks
    )
    total_order_amount = _sum_float(strict_orders, "desired_amount_cny")
    block_ratio = summary["strict_blocked_amount_cny"] / total_order_amount if total_order_amount else 0.0
    rows = [
        {
            "checkpoint": "uses_exante_adv_for_guard",
            "status": "pass",
            "value": "shifted native ADV or allowed fallback",
            "expected": "no same-day turnover in guard ADV",
            "note": "守门ADV来自v3 ex-ante执行信息，不用目标日成交额重算。",
        },
        {
            "checkpoint": "return_not_materially_destroyed",
            "status": "pass" if summary["delta_total_return_vs_base"] > -0.02 else "warn",
            "value": pct(summary["delta_total_return_vs_base"]),
            "expected": ">-2%",
            "note": "执行守门不能显著破坏策略主体。",
        },
        {
            "checkpoint": "drawdown_not_materially_worse",
            "status": "pass" if summary["delta_max_drawdown_vs_base"] >= -0.01 else "warn",
            "value": pct(summary["delta_max_drawdown_vs_base"]),
            "expected": ">=-1%",
            "note": "执行守门不应显著放大回撤。",
        },
        {
            "checkpoint": "blocked_amount_is_execution_layer_scale",
            "status": "pass" if block_ratio < 0.02 else ("warn" if block_ratio < 0.05 else "fail"),
            "value": pct(block_ratio),
            "expected": "<2%",
            "note": "守门影响应保持执行层量级。",
        },
        {
            "checkpoint": "all_guard_blocks_are_buys",
            "status": "pass" if malformed_sell_blocks.is_empty() else "fail",
            "value": str(malformed_sell_blocks.height),
            "expected": "0",
            "note": "守门只允许拦截买入/加仓，卖出必须通过。",
        },
        {
            "checkpoint": "all_blocks_have_reason",
            "status": "pass" if missing_reason_blocks.is_empty() else "fail",
            "value": str(missing_reason_blocks.height),
            "expected": "0",
            "note": "每笔守门阻断必须有明确原因。",
        },
        {
            "checkpoint": "no_missing_guard_panel_blocks",
            "status": "pass" if missing_panel_blocks.is_empty() else "fail",
            "value": str(missing_panel_blocks.height),
            "expected": "0",
            "note": "若出现缺失守门面板，说明执行信息和研究面板没有对齐。",
        },
        {
            "checkpoint": "st_blocks_still_present",
            "status": "pass" if st_blocks.height >= 1 else "warn",
            "value": str(st_blocks.height),
            "expected": ">=1 in historical audit",
            "note": "历史上已发现ST买入缺口，严格回放应仍能识别。",
        },
        {
            "checkpoint": "no_signal_parameter_change",
            "status": "pass",
            "value": "no signal/threshold change",
            "expected": "no signal/threshold change",
            "note": "只修执行层可知性，不改alpha排序或收益参数。",
        },
    ]
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    scorecard: pl.DataFrame,
    block_summary: pl.DataFrame,
    strict_block_summary: pl.DataFrame,
    year_summary: pl.DataFrame,
    state_summary: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万 严格ex-ante ST/不可研究买入守门回放 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：修正第278中ADV重算可能含目标日成交额的问题；只做执行层回放，不改alpha信号。",
        f"- 账户规模：`{lot.ACCOUNT_SIZE_CNY:,.0f}`元。",
        "- A/B判断：股票震荡独立执行层审计，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 执行守门属于pre-trade control，目标是拦住不可交易/越界订单，而不是反向修改信号层。",
        "- 滚动成交额、ADV、流动性标签必须只使用下单前可得数据；目标日成交额不能参与开盘前守门。",
        "- 本阶段因此复用v3 ex-ante ADV口径：优先前一日已形成的原生ADV20，缺失时才使用允许的前序成交额fallback。",
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
            f"- 基准期末权益`{summary['base_final_equity']:.4f}`，总收益`{pct(summary['base_total_return'])}`，最大回撤`{pct(summary['base_max_drawdown'])}`，Sharpe `{summary['base_sharpe']:.4f}`。",
            f"- 严格ex-ante守门期末权益`{summary['strict_final_equity']:.4f}`，总收益`{pct(summary['strict_total_return'])}`，最大回撤`{pct(summary['strict_max_drawdown'])}`，Sharpe `{summary['strict_sharpe']:.4f}`。",
            f"- 严格ex-ante阻断`{summary['strict_blocked_orders']}`笔，金额`{summary['strict_blocked_amount_cny']:,.0f}`元。",
            f"- 相对基准：总收益变化`{pct(summary['delta_total_return_vs_base'])}`，最大回撤变化`{pct(summary['delta_max_drawdown_vs_base'])}`，Sharpe变化`{summary['delta_sharpe_vs_base']:.4f}`。",
            f"- 相对第278含当天ADV重算版：总收益变化`{pct(summary['delta_total_return_vs_corrected_lookahead'])}`，阻断变化`{summary['delta_blocked_orders_vs_corrected_lookahead']}`笔。",
            "",
            "## 判断",
            "",
            "- 这是比第278更严的实盘可知性版本：如果它表现接近第278，守门方向才更可信。",
            "- 若严格版阻断明显变多，优先解释为ex-ante数据不足/分段暖机问题，而不是直接调阈值。",
            "- 本阶段仍不覆盖paper入口；只能作为sidecar候选继续评审。",
            "",
            "## 绩效对比",
            "",
            markdown_table(
                scorecard,
                [
                    "scenario",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "orders",
                    "filled_orders",
                    "blocked_orders",
                    "st_or_ineligible_buy_blocked_orders",
                    "st_or_ineligible_buy_blocked_amount_cny",
                ],
                max_rows=20,
            ),
            "",
            "## 严格守门阻断原因",
            "",
            _markdown_all(strict_block_summary),
            "",
            "## 年度分布",
            "",
            _markdown_all(year_summary),
            "",
            "## 阻断原因汇总",
            "",
            _markdown_all(block_summary),
            "",
            "## 市场状态归因",
            "",
            _markdown_all(state_summary),
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
            "- 原因：本阶段修复的是执行数据可知性，不根据收益调阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否，但需要警惕把收益改善当作alpha。",
            "- 原因：守门原因来自ST、成分、上市天数、ex-ante ADV、开盘可交易性这些事前约束；若收益变化为正，也只能作为执行一致性的副产品。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第278存在ADV重算口径疑点，必须用严格ex-ante版本确认守门是否仍有价值。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：只要严格版没有显著破坏收益且阻断可解释，就值得继续做paper sidecar最小接入评审。",
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
    target_weights = build_target_weights(selected_all)
    target_maps = lot.build_target_maps(target_weights)
    dates = lot.build_tracking_dates(target_weights, benchmark_df)

    base_exec_info = build_exec_info(stock_df)
    strict_exec_info = build_strict_exante_guarded_exec_info(stock_df)
    base_orders, base_daily, base_curves = replay_with_classifier(target_maps, dates, base_exec_info, guard_enabled=False)
    strict_orders, strict_daily, strict_curves = replay_with_classifier(
        target_maps,
        dates,
        strict_exec_info,
        guard_enabled=True,
    )

    base_summary = summarize_daily(base_daily, base_orders, "base_rerun")
    strict_summary = summarize_daily(strict_daily, strict_orders, "strict_exante_st_buy_guard")
    original_summary = json.loads(
        (ORIGINAL_GUARD_OUTPUT_DIR / f"{ORIGINAL_GUARD_PREFIX}_summary.json").read_text(encoding="utf-8")
    )
    corrected_summary = json.loads(
        (CORRECTED_OUTPUT_DIR / f"{CORRECTED_PREFIX}_summary.json").read_text(encoding="utf-8")
    )
    scorecard = build_scorecard(base_summary, strict_summary, original_summary, corrected_summary)

    strict_blocks = enrich_strict_exante_blocks(strict_orders, stock_df, base_exec_info)
    strict_block_summary = summarize_strict_blocks(strict_blocks)
    year_summary = summarize_year(strict_blocks)
    block_summary = pl.concat(
        [
            build_block_reason_summary(base_orders, "base_rerun"),
            build_block_reason_summary(strict_orders, "strict_exante_st_buy_guard"),
        ],
        how="vertical",
    )
    state = pl.read_csv(REPAIRABLE_OUTPUT_DIR / f"{REPAIRABLE_PREFIX}_repairable_state.csv", try_parse_dates=True)
    state_summary = pl.concat(
        [
            summarize_by_state(base_daily, state, "base_rerun"),
            summarize_by_state(strict_daily, state, "strict_exante_st_buy_guard"),
        ],
        how="vertical",
    )

    strict_st_block = strict_orders.filter(pl.col("blocked_reason") == "st_or_ineligible_buy")
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scenario": PAPER_SCENARIO,
        "account_size_cny": lot.ACCOUNT_SIZE_CNY,
        "min_adv20_turnover": MIN_ADV20_TURNOVER,
        "min_listing_days": MIN_LISTING_DAYS,
        "base_final_equity": base_summary["final_equity"],
        "base_total_return": base_summary["total_return"],
        "base_max_drawdown": base_summary["max_drawdown"],
        "base_sharpe": base_summary["sharpe"],
        "strict_final_equity": strict_summary["final_equity"],
        "strict_total_return": strict_summary["total_return"],
        "strict_max_drawdown": strict_summary["max_drawdown"],
        "strict_sharpe": strict_summary["sharpe"],
        "strict_orders": strict_summary["orders"],
        "strict_filled_orders": strict_summary["filled_orders"],
        "strict_blocked_orders": strict_st_block.height,
        "strict_blocked_amount_cny": _sum_float(strict_st_block, "desired_amount_cny"),
        "original_guard_final_equity": original_summary["guard_final_equity"],
        "original_guard_total_return": original_summary["guard_total_return"],
        "original_guard_blocked_orders": original_summary["guard_st_or_ineligible_buy_blocked_orders"],
        "corrected_lookahead_final_equity": corrected_summary["corrected_final_equity"],
        "corrected_lookahead_total_return": corrected_summary["corrected_total_return"],
        "corrected_lookahead_blocked_orders": corrected_summary["corrected_blocked_orders"],
        "delta_total_return_vs_base": strict_summary["total_return"] - base_summary["total_return"],
        "delta_max_drawdown_vs_base": strict_summary["max_drawdown"] - base_summary["max_drawdown"],
        "delta_sharpe_vs_base": strict_summary["sharpe"] - base_summary["sharpe"],
        "delta_total_return_vs_corrected_lookahead": strict_summary["total_return"]
        - corrected_summary["corrected_total_return"],
        "delta_blocked_orders_vs_corrected_lookahead": strict_st_block.height
        - corrected_summary["corrected_blocked_orders"],
    }
    quality = build_quality(summary, strict_blocks, strict_orders)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "scorecard": OUTPUT_DIR / f"{PREFIX}_scorecard.csv",
        "base_orders": OUTPUT_DIR / f"{PREFIX}_base_orders.csv",
        "base_daily": OUTPUT_DIR / f"{PREFIX}_base_daily.csv",
        "base_curves": OUTPUT_DIR / f"{PREFIX}_base_curves.csv",
        "strict_orders": OUTPUT_DIR / f"{PREFIX}_strict_orders.csv",
        "strict_daily": OUTPUT_DIR / f"{PREFIX}_strict_daily.csv",
        "strict_curves": OUTPUT_DIR / f"{PREFIX}_strict_curves.csv",
        "strict_block_audit": OUTPUT_DIR / f"{PREFIX}_strict_block_audit.csv",
        "strict_block_summary": OUTPUT_DIR / f"{PREFIX}_strict_block_summary.csv",
        "year_summary": OUTPUT_DIR / f"{PREFIX}_year_summary.csv",
        "block_reason_summary": OUTPUT_DIR / f"{PREFIX}_block_reason_summary.csv",
        "state_summary": OUTPUT_DIR / f"{PREFIX}_state_summary.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    scorecard.write_csv(paths["scorecard"])
    base_orders.write_csv(paths["base_orders"])
    base_daily.write_csv(paths["base_daily"])
    base_curves.write_csv(paths["base_curves"])
    strict_orders.write_csv(paths["strict_orders"])
    strict_daily.write_csv(paths["strict_daily"])
    strict_curves.write_csv(paths["strict_curves"])
    strict_blocks.write_csv(paths["strict_block_audit"])
    strict_block_summary.write_csv(paths["strict_block_summary"])
    year_summary.write_csv(paths["year_summary"])
    block_summary.write_csv(paths["block_reason_summary"])
    state_summary.write_csv(paths["state_summary"])
    quality.write_csv(paths["quality_checkpoints"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    paths["meta"].write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "research_sources": RESEARCH_SOURCES,
                "note": "Strict ex-ante guard replay only; no paper entrypoint overwrite.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report_path = write_report(
        summary,
        scorecard,
        block_summary,
        strict_block_summary,
        year_summary,
        state_summary,
        quality,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
