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
from analyze_stock_range_reversion_liquid_q3_300k_st_exante_audit import (
    RESEARCH_SOURCES as ST_AUDIT_RESEARCH_SOURCES,
    add_namechange_flag,
    load_namechange_st,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import (
    MAX_PARTICIPATION_ADV20,
    PAPER_SCENARIO,
    ROUNDTRIP_COST_BPS,
    build_target_weights,
    markdown_table,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_st_buy_guard_replay_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_st_buy_guard_replay_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = ST_AUDIT_RESEARCH_SOURCES


def annualized_sharpe(values: list[float]) -> float:
    return lot.annualized_sharpe(values)


def summarize_daily(daily: pl.DataFrame, orders: pl.DataFrame, scenario: str) -> dict[str, Any]:
    returns = [float(item) for item in daily["strategy_daily_ret_min_fee"].to_list()]
    equity = to_float(daily["equity_min_fee"].tail(1).item()) if not daily.is_empty() else 1.0
    blocked = orders.filter(pl.col("status") == "blocked") if not orders.is_empty() else pl.DataFrame()
    return {
        "scenario": scenario,
        "final_equity": equity,
        "total_return": equity - 1.0,
        "max_drawdown": to_float(daily["drawdown_min_fee"].min()) if not daily.is_empty() else 0.0,
        "sharpe": annualized_sharpe(returns),
        "daily_rows": daily.height,
        "orders": orders.height,
        "filled_orders": orders.filter(pl.col("filled_shares") > 0).height if not orders.is_empty() else 0,
        "blocked_orders": blocked.height,
        "blocked_amount_cny": to_float(blocked["desired_amount_cny"].sum()) if not blocked.is_empty() else 0.0,
        "st_or_ineligible_buy_blocked_orders": orders.filter(pl.col("blocked_reason") == "st_or_ineligible_buy").height
        if not orders.is_empty()
        else 0,
        "st_or_ineligible_buy_blocked_amount_cny": to_float(
            orders.filter(pl.col("blocked_reason") == "st_or_ineligible_buy")["desired_amount_cny"].sum()
        )
        if not orders.is_empty()
        else 0.0,
        "total_min_fee_cost_cny": to_float(orders["min_fee_cost_cny"].sum()) if not orders.is_empty() else 0.0,
        "avg_actual_gross_weight": to_float(daily["actual_gross_weight"].mean()) if not daily.is_empty() else 0.0,
        "max_actual_gross_weight": to_float(daily["actual_gross_weight"].max()) if not daily.is_empty() else 0.0,
    }


def build_guard_flags(stock_df: pl.DataFrame) -> dict[tuple[Any, str], dict[str, Any]]:
    panel = (
        stock_df.select(
            [
                "datetime",
                "symbol",
                "is_st",
                "eligible_research_row",
                "eligible_component_row",
            ]
        )
        .rename({"datetime": "date"})
        .with_columns(pl.col("symbol").cast(pl.Utf8))
        .unique(["date", "symbol"])
    )
    panel = add_namechange_flag(panel, load_namechange_st()).with_columns(
        pl.col("is_st").fill_null(False).alias("panel_is_st_on_date"),
        pl.col("eligible_research_row").fill_null(False).alias("panel_eligible_research_on_date"),
        pl.col("eligible_component_row").fill_null(False).alias("panel_eligible_component_on_date"),
        (pl.col("is_st").fill_null(False) | pl.col("namechange_st_on_date").fill_null(False)).alias(
            "exante_st_on_date_any_source"
        ),
    )
    flags: dict[tuple[Any, str], dict[str, Any]] = {}
    for row in panel.iter_rows(named=True):
        flags[(row["date"], row["symbol"])] = {
            "panel_is_st_on_date": bool(row["panel_is_st_on_date"]),
            "namechange_st_on_date": bool(row["namechange_st_on_date"]),
            "panel_eligible_research_on_date": bool(row["panel_eligible_research_on_date"]),
            "panel_eligible_component_on_date": bool(row["panel_eligible_component_on_date"]),
            "st_buy_guard": bool(row["exante_st_on_date_any_source"]) or not bool(row["panel_eligible_research_on_date"]),
        }
    return flags


def build_guarded_exec_info(stock_df: pl.DataFrame) -> dict[tuple[Any, str], SimpleNamespace]:
    base = build_exec_info(stock_df)
    flags = build_guard_flags(stock_df)
    guarded: dict[tuple[Any, str], SimpleNamespace] = {}
    for key, info in base.items():
        payload = dict(info.__dict__)
        payload.update(
            {
                "panel_is_st_on_date": False,
                "namechange_st_on_date": False,
                "panel_eligible_research_on_date": True,
                "panel_eligible_component_on_date": True,
                "st_buy_guard": False,
            }
        )
        payload.update(flags.get(key, {}))
        guarded[key] = SimpleNamespace(**payload)
    return guarded


def enrich_guard_blocks(orders: pl.DataFrame, stock_df: pl.DataFrame) -> pl.DataFrame:
    blocked = orders.filter(pl.col("blocked_reason") == "st_or_ineligible_buy")
    if blocked.is_empty():
        return pl.DataFrame()
    panel = (
        stock_df.select(
            [
                "datetime",
                "symbol",
                "is_st",
                "eligible_research_row",
                "eligible_component_row",
                "is_suspended",
                "adv20_turnover",
                "turnover",
            ]
        )
        .rename({"datetime": "date"})
        .with_columns(pl.col("symbol").cast(pl.Utf8))
        .unique(["date", "symbol"])
    )
    panel = add_namechange_flag(panel, load_namechange_st()).with_columns(
        (pl.col("is_st").fill_null(False) | pl.col("namechange_st_on_date").fill_null(False)).alias("exante_st"),
        pl.col("eligible_research_row").fill_null(False).alias("panel_eligible_research_on_date"),
        pl.col("eligible_component_row").fill_null(False).alias("panel_eligible_component_on_date"),
    )
    return (
        blocked.join(panel, on=["date", "symbol"], how="left")
        .with_columns(
            pl.when(pl.col("exante_st").fill_null(False))
            .then(pl.lit("exante_st"))
            .when(~pl.col("panel_eligible_research_on_date").fill_null(False))
            .then(pl.lit("not_eligible_research"))
            .otherwise(pl.lit("other"))
            .alias("guard_block_subreason")
        )
        .sort(["date", "symbol"])
    )


def summarize_guard_block_audit(guard_block_audit: pl.DataFrame) -> pl.DataFrame:
    if guard_block_audit.is_empty():
        return pl.DataFrame()
    return (
        guard_block_audit.group_by(["guard_block_subreason", "exante_st", "panel_eligible_research_on_date"])
        .agg(
            pl.len().alias("orders"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("adv20_turnover").mean().alias("avg_adv20_turnover"),
            pl.col("turnover").mean().alias("avg_turnover"),
        )
        .sort(["guard_block_subreason", "orders"], descending=[False, True])
    )


def replay_with_classifier(
    target_maps: dict[Any, dict[str, dict[str, Any]]],
    dates: list[Any],
    exec_info: dict[tuple[Any, str], Any],
    guard_enabled: bool,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    original = lot.classify_order

    def guarded_classify(side: str, info: Any | None) -> tuple[str, str]:
        status, reason = original(side, info)
        if status != "blocked" and guard_enabled and side == "buy" and bool(getattr(info, "st_buy_guard", False)):
            return "blocked", "st_or_ineligible_buy"
        return status, reason

    lot.classify_order = guarded_classify
    try:
        return lot.replay_lot_account(target_maps, dates, exec_info)
    finally:
        lot.classify_order = original


def build_block_reason_summary(orders: pl.DataFrame, scenario: str) -> pl.DataFrame:
    if orders.is_empty():
        return pl.DataFrame()
    return (
        orders.group_by(["status", "blocked_reason"])
        .agg(
            pl.len().alias("orders"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("filled_amount_cny").sum().alias("filled_amount_cny_sum"),
            pl.col("symbol").n_unique().alias("symbols"),
        )
        .with_columns(pl.lit(scenario).alias("scenario_variant"))
        .sort(["status", "blocked_reason"])
    )


def summarize_by_state(daily: pl.DataFrame, state: pl.DataFrame, scenario: str) -> pl.DataFrame:
    joined = daily.join(state.rename({"target_date": "date"}), on="date", how="left")
    if joined.is_empty() or "mr_environment_state" not in joined.columns:
        return pl.DataFrame()
    return (
        joined.group_by("mr_environment_state")
        .agg(
            pl.len().alias("days"),
            pl.col("strategy_daily_ret_min_fee").sum().alias("net_return_sum"),
            ((pl.col("strategy_daily_ret_min_fee") + 1).product() - 1).alias("compounded_return"),
            pl.col("strategy_daily_ret_min_fee").mean().alias("avg_daily_ret"),
            pl.col("strategy_daily_ret_min_fee").min().alias("worst_daily_ret"),
            (pl.col("strategy_daily_ret_min_fee") > 0).mean().alias("daily_win_rate"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
        )
        .with_columns(pl.lit(scenario).alias("scenario_variant"))
        .sort(["scenario_variant", "net_return_sum"])
    )


def compare_daily(base: pl.DataFrame, guard: pl.DataFrame) -> pl.DataFrame:
    return (
        base.select(
            [
                "date",
                pl.col("equity_min_fee").alias("base_equity_min_fee"),
                pl.col("strategy_daily_ret_min_fee").alias("base_daily_ret"),
                pl.col("actual_gross_weight").alias("base_actual_gross_weight"),
            ]
        )
        .join(
            guard.select(
                [
                    "date",
                    pl.col("equity_min_fee").alias("guard_equity_min_fee"),
                    pl.col("strategy_daily_ret_min_fee").alias("guard_daily_ret"),
                    pl.col("actual_gross_weight").alias("guard_actual_gross_weight"),
                ]
            ),
            on="date",
            how="inner",
        )
        .with_columns(
            (pl.col("guard_equity_min_fee") - pl.col("base_equity_min_fee")).alias("equity_delta"),
            (pl.col("guard_daily_ret") - pl.col("base_daily_ret")).alias("daily_ret_delta"),
            (pl.col("guard_actual_gross_weight") - pl.col("base_actual_gross_weight")).alias("gross_weight_delta"),
        )
        .sort("date")
    )


def build_quality(summary: dict[str, Any]) -> pl.DataFrame:
    rows = [
        {
            "checkpoint": "guard_blocks_st_or_ineligible_buys",
            "status": "pass" if summary["guard_st_or_ineligible_buy_blocked_orders"] > 0 else "warn",
            "value": str(summary["guard_st_or_ineligible_buy_blocked_orders"]),
            "expected": ">0 in this audit sample",
            "note": "审计已发现ST日买入，守门回放应阻断它们。",
        },
        {
            "checkpoint": "return_not_materially_destroyed",
            "status": "pass" if summary["delta_total_return"] > -0.02 else "warn",
            "value": pct(summary["delta_total_return"]),
            "expected": ">-2%",
            "note": "硬约束修复不应大幅破坏收益，否则要检查实现是否误杀。",
        },
        {
            "checkpoint": "drawdown_not_materially_worse",
            "status": "pass" if summary["delta_max_drawdown"] >= -0.01 else "warn",
            "value": pct(summary["delta_max_drawdown"]),
            "expected": ">=-1%",
            "note": "硬约束修复不应显著放大回撤。",
        },
        {
            "checkpoint": "no_signal_parameter_change",
            "status": "pass",
            "value": "no signal/threshold change",
            "expected": "no signal/threshold change",
            "note": "只修改执行层买入守门，不修改信号。",
        },
    ]
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    scorecard: pl.DataFrame,
    block_summary: pl.DataFrame,
    guard_block_summary: pl.DataFrame,
    state_summary: pl.DataFrame,
    worst_delta: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    lines = [
        "# 股票震荡liquid_q3 30万 ST/不可研究买入守门回放 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：交易可行性硬约束回放；不新增信号、不调收益参数。",
        f"- 账户规模：`{lot.ACCOUNT_SIZE_CNY:,.0f}`元。",
        "- A/B判断：执行约束压力测试，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 沿用上一阶段Tushare `stock_basic/namechange`判断：当前名称不能替代历史当日ST状态，交易日ST约束需要基于当日`is_st`或历史名称区间。",
        "- 这一步不是业绩优化，而是把实盘不会主动新增买入ST/不可研究股票的规则补入影子回放。",
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
            f"- ST/不可研究守门期末权益`{summary['guard_final_equity']:.4f}`，总收益`{pct(summary['guard_total_return'])}`，最大回撤`{pct(summary['guard_max_drawdown'])}`，Sharpe `{summary['guard_sharpe']:.4f}`。",
            f"- 守门阻断ST/不可研究买入`{summary['guard_st_or_ineligible_buy_blocked_orders']}`笔，阻断金额`{summary['guard_st_or_ineligible_buy_blocked_amount_cny']:,.0f}`元。",
            f"- 其中真实ST/namechange-ST买入阻断`{summary['guard_exante_st_buy_blocked_orders']}`笔，非ST但当日不可研究买入阻断`{summary['guard_non_st_ineligible_buy_blocked_orders']}`笔。",
            f"- 相对基准：总收益变化`{pct(summary['delta_total_return'])}`，最大回撤变化`{pct(summary['delta_max_drawdown'])}`，Sharpe变化`{summary['delta_sharpe']:.4f}`。",
            "",
            "## 判断",
            "",
            "- 这是应该保留的方向：它不是拟合收益，而是把已发现的真实交易约束前置。",
            "- 若收益/回撤影响很小，说明可以把ST日新增买入守门作为候选执行层修复继续验证。",
            "- 但本阶段仍不改正式paper入口；下一步应再检查最新订单和全历史阻断明细，确认没有误伤正常非ST交易。",
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
                    "avg_actual_gross_weight",
                    "max_actual_gross_weight",
                ],
                max_rows=20,
            ),
            "",
            "## 阻断原因",
            "",
            markdown_table(
                block_summary,
                [
                    "scenario_variant",
                    "status",
                    "blocked_reason",
                    "orders",
                    "desired_amount_cny_sum",
                    "filled_amount_cny_sum",
                    "symbols",
                ],
                max_rows=80,
            ),
            "",
            "## 守门阻断拆解",
            "",
            markdown_table(
                guard_block_summary,
                [
                    "guard_block_subreason",
                    "exante_st",
                    "panel_eligible_research_on_date",
                    "orders",
                    "desired_amount_cny_sum",
                    "symbols",
                    "avg_adv20_turnover",
                    "avg_turnover",
                ],
                max_rows=20,
            ),
            "",
            "## 市场状态归因",
            "",
            markdown_table(
                state_summary,
                [
                    "scenario_variant",
                    "mr_environment_state",
                    "days",
                    "net_return_sum",
                    "compounded_return",
                    "avg_daily_ret",
                    "worst_daily_ret",
                    "daily_win_rate",
                    "avg_actual_gross_weight",
                ],
                max_rows=80,
            ),
            "",
            "## 守门影响最大日期",
            "",
            markdown_table(
                worst_delta,
                [
                    "date",
                    "base_daily_ret",
                    "guard_daily_ret",
                    "daily_ret_delta",
                    "base_equity_min_fee",
                    "guard_equity_min_fee",
                    "equity_delta",
                    "gross_weight_delta",
                ],
                max_rows=40,
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
            "- 原因：ST买入守门来自交易可行性审计，不来自收益搜索。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：守门规则是事前可知的硬约束，且只禁止新增买入/增持，不按收益表现选择阈值。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：ST事前审计发现执行层真实缺口，需要看修复后的资金曲线影响。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：如果守门影响可控，它会提高实盘一致性；如果影响异常，则能暴露回放实现问题。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 下一步检查最新订单与全历史阻断样本，确认ST买入守门是否可作为执行层默认约束。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        if name.startswith("_"):
            continue
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
    guard_exec_info = build_guarded_exec_info(stock_df)
    base_orders, base_daily, base_curves = replay_with_classifier(target_maps, dates, base_exec_info, guard_enabled=False)
    guard_orders, guard_daily, guard_curves = replay_with_classifier(target_maps, dates, guard_exec_info, guard_enabled=True)

    base_summary = summarize_daily(base_daily, base_orders, "base_rerun")
    guard_summary = summarize_daily(guard_daily, guard_orders, "st_buy_guard")
    scorecard = pl.DataFrame([base_summary, guard_summary])
    daily_compare = compare_daily(base_daily, guard_daily)
    guard_block_audit = enrich_guard_blocks(guard_orders, stock_df)
    guard_block_summary = summarize_guard_block_audit(guard_block_audit)
    block_summary = pl.concat(
        [
            build_block_reason_summary(base_orders, "base_rerun"),
            build_block_reason_summary(guard_orders, "st_buy_guard"),
        ],
        how="vertical",
    )
    state = pl.read_csv(REPAIRABLE_OUTPUT_DIR / f"{REPAIRABLE_PREFIX}_repairable_state.csv", try_parse_dates=True)
    state_summary = pl.concat(
        [
            summarize_by_state(base_daily, state, "base_rerun"),
            summarize_by_state(guard_daily, state, "st_buy_guard"),
        ],
        how="vertical",
    )
    worst_delta = daily_compare.sort("daily_ret_delta").head(40)

    guard_st_block = guard_orders.filter(pl.col("blocked_reason") == "st_or_ineligible_buy")
    guard_exante_st_block = (
        guard_block_audit.filter(pl.col("guard_block_subreason") == "exante_st")
        if not guard_block_audit.is_empty()
        else pl.DataFrame()
    )
    guard_non_st_ineligible_block = (
        guard_block_audit.filter(pl.col("guard_block_subreason") == "not_eligible_research")
        if not guard_block_audit.is_empty()
        else pl.DataFrame()
    )
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scenario": PAPER_SCENARIO,
        "account_size_cny": lot.ACCOUNT_SIZE_CNY,
        "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
        "max_participation_adv20": MAX_PARTICIPATION_ADV20,
        "base_final_equity": base_summary["final_equity"],
        "base_total_return": base_summary["total_return"],
        "base_max_drawdown": base_summary["max_drawdown"],
        "base_sharpe": base_summary["sharpe"],
        "guard_final_equity": guard_summary["final_equity"],
        "guard_total_return": guard_summary["total_return"],
        "guard_max_drawdown": guard_summary["max_drawdown"],
        "guard_sharpe": guard_summary["sharpe"],
        "delta_final_equity": guard_summary["final_equity"] - base_summary["final_equity"],
        "delta_total_return": guard_summary["total_return"] - base_summary["total_return"],
        "delta_max_drawdown": guard_summary["max_drawdown"] - base_summary["max_drawdown"],
        "delta_sharpe": guard_summary["sharpe"] - base_summary["sharpe"],
        "guard_st_or_ineligible_buy_blocked_orders": guard_st_block.height,
        "guard_st_or_ineligible_buy_blocked_amount_cny": to_float(guard_st_block["desired_amount_cny"].sum())
        if not guard_st_block.is_empty()
        else 0.0,
        "guard_exante_st_buy_blocked_orders": guard_exante_st_block.height,
        "guard_exante_st_buy_blocked_amount_cny": to_float(guard_exante_st_block["desired_amount_cny"].sum())
        if not guard_exante_st_block.is_empty()
        else 0.0,
        "guard_non_st_ineligible_buy_blocked_orders": guard_non_st_ineligible_block.height,
        "guard_non_st_ineligible_buy_blocked_amount_cny": to_float(
            guard_non_st_ineligible_block["desired_amount_cny"].sum()
        )
        if not guard_non_st_ineligible_block.is_empty()
        else 0.0,
    }
    quality = build_quality(summary)
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
        "guard_orders": OUTPUT_DIR / f"{PREFIX}_guard_orders.csv",
        "guard_daily": OUTPUT_DIR / f"{PREFIX}_guard_daily.csv",
        "guard_curves": OUTPUT_DIR / f"{PREFIX}_guard_curves.csv",
        "daily_compare": OUTPUT_DIR / f"{PREFIX}_daily_compare.csv",
        "block_reason_summary": OUTPUT_DIR / f"{PREFIX}_block_reason_summary.csv",
        "guard_block_audit": OUTPUT_DIR / f"{PREFIX}_guard_block_audit.csv",
        "guard_block_summary": OUTPUT_DIR / f"{PREFIX}_guard_block_summary.csv",
        "state_summary": OUTPUT_DIR / f"{PREFIX}_state_summary.csv",
        "worst_delta": OUTPUT_DIR / f"{PREFIX}_worst_delta.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    scorecard.write_csv(paths["scorecard"])
    base_orders.write_csv(paths["base_orders"])
    base_daily.write_csv(paths["base_daily"])
    base_curves.write_csv(paths["base_curves"])
    guard_orders.write_csv(paths["guard_orders"])
    guard_daily.write_csv(paths["guard_daily"])
    guard_curves.write_csv(paths["guard_curves"])
    daily_compare.write_csv(paths["daily_compare"])
    block_summary.write_csv(paths["block_reason_summary"])
    guard_block_audit.write_csv(paths["guard_block_audit"])
    guard_block_summary.write_csv(paths["guard_block_summary"])
    state_summary.write_csv(paths["state_summary"])
    worst_delta.write_csv(paths["worst_delta"])
    quality.write_csv(paths["quality_checkpoints"])
    lot.write_json(paths["summary"], summary)
    lot.write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "research_sources": RESEARCH_SOURCES,
            "source_selected_all": FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_selected_all.parquet",
            "source_state": REPAIRABLE_OUTPUT_DIR / f"{REPAIRABLE_PREFIX}_repairable_state.csv",
            "note": "ST buy guard replay only; no signal parameter changes.",
        },
    )
    report_path = write_report(
        summary,
        scorecard,
        block_summary,
        guard_block_summary,
        state_summary,
        worst_delta,
        quality,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
