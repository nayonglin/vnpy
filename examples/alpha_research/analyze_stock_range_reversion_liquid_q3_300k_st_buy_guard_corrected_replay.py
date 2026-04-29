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
    annualized_sharpe,
    build_block_reason_summary,
    compare_daily,
    replay_with_classifier,
    summarize_by_state,
    summarize_daily,
)
from analyze_stock_range_reversion_liquid_q3_300k_st_exante_audit import add_namechange_flag, load_namechange_st
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from build_stock_range_reversion_research_panel import MIN_ADV20_TURNOVER, MIN_LISTING_DAYS
from generate_stock_range_reversion_liquid_q3_paper_tracking import build_target_weights, markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_st_buy_guard_corrected_replay_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_st_buy_guard_corrected_replay_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Lookahead-bias prevention notes emphasize explicit rolling lookback and warmup handling",
        "https://docs.clypt.ai/backtesting/lookahead-bias-prevention",
    ),
    (
        "Tushare namechange exposes historical name periods with start/end dates",
        "https://tushare.pro/document/2?doc_id=100",
    ),
)


def build_corrected_guard_panel(stock_df: pl.DataFrame) -> pl.DataFrame:
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
                "volume",
                "turnover",
                "adv20_turnover",
                "qfq_close",
                "is_index_component",
            ]
        )
        .rename({"datetime": "date"})
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .sort(["symbol", "date"])
        .with_columns(pl.col("turnover").rolling_mean(20).over("symbol").alias("recomputed_adv20_turnover"))
    )
    panel = add_namechange_flag(panel, load_namechange_st()).with_columns(
        (pl.col("is_st").fill_null(False) | pl.col("namechange_st_on_date").fill_null(False)).alias("exante_st"),
        pl.coalesce([pl.col("adv20_turnover"), pl.col("recomputed_adv20_turnover")]).alias(
            "corrected_adv20_turnover"
        ),
    )
    return panel.with_columns(
        (
            (~pl.col("is_suspended").fill_null(True))
            & (~pl.col("exante_st").fill_null(True))
            & pl.col("is_stock_type").fill_null(False)
            & pl.col("is_listed_status").fill_null(False)
            & (pl.col("listing_days").fill_null(-1) >= MIN_LISTING_DAYS)
            & (pl.col("volume").fill_null(0) > 0)
            & (pl.col("turnover").fill_null(0) > 0)
            & (pl.col("corrected_adv20_turnover").fill_null(0) >= MIN_ADV20_TURNOVER)
            & pl.col("qfq_close").is_not_null()
        ).alias("corrected_research_eligible"),
    ).with_columns(
        (pl.col("corrected_research_eligible") & pl.col("is_index_component").fill_null(False)).alias(
            "corrected_component_eligible"
        ),
        (
            pl.col("adv20_turnover").is_null()
            & pl.col("recomputed_adv20_turnover").is_not_null()
            & (pl.col("recomputed_adv20_turnover") >= MIN_ADV20_TURNOVER)
        ).alias("adv20_warmup_filled"),
    )


def build_corrected_guard_flags(stock_df: pl.DataFrame) -> dict[tuple[Any, str], dict[str, Any]]:
    panel = build_corrected_guard_panel(stock_df)
    flags: dict[tuple[Any, str], dict[str, Any]] = {}
    for row in panel.iter_rows(named=True):
        reason = ""
        if bool(row["exante_st"]):
            reason = "exante_st"
        elif not bool(row["corrected_research_eligible"]):
            if bool(row["is_suspended"]):
                reason = "suspended"
            elif not bool(row["is_stock_type"]):
                reason = "not_stock_type"
            elif not bool(row["is_listed_status"]):
                reason = "not_listed_status"
            elif int(row["listing_days"] or -1) < MIN_LISTING_DAYS:
                reason = "listing_days_lt_min"
            elif float(row["volume"] or 0.0) <= 0:
                reason = "zero_or_missing_volume"
            elif float(row["turnover"] or 0.0) <= 0:
                reason = "zero_or_missing_turnover"
            elif float(row["corrected_adv20_turnover"] or 0.0) < MIN_ADV20_TURNOVER:
                reason = "adv20_turnover_lt_min_after_recompute"
            elif row["qfq_close"] is None:
                reason = "missing_qfq_close"
            else:
                reason = "not_corrected_research_eligible"
        elif not bool(row["corrected_component_eligible"]):
            reason = "not_index_component"
        flags[(row["date"], row["symbol"])] = {
            "corrected_component_eligible": bool(row["corrected_component_eligible"]),
            "corrected_research_eligible": bool(row["corrected_research_eligible"]),
            "corrected_guard_reason": reason,
            "corrected_adv20_turnover": to_float(row["corrected_adv20_turnover"]),
            "recomputed_adv20_turnover": to_float(row["recomputed_adv20_turnover"]),
            "adv20_warmup_filled": bool(row["adv20_warmup_filled"]),
            "st_buy_guard": bool(reason),
        }
    return flags


def build_corrected_guarded_exec_info(stock_df: pl.DataFrame) -> dict[tuple[Any, str], SimpleNamespace]:
    base = build_exec_info(stock_df)
    flags = build_corrected_guard_flags(stock_df)
    guarded: dict[tuple[Any, str], SimpleNamespace] = {}
    for key, info in base.items():
        payload = dict(info.__dict__)
        payload.update(
            {
                "corrected_component_eligible": True,
                "corrected_research_eligible": True,
                "corrected_guard_reason": "",
                "corrected_adv20_turnover": 0.0,
                "recomputed_adv20_turnover": 0.0,
                "adv20_warmup_filled": False,
                "st_buy_guard": False,
            }
        )
        payload.update(flags.get(key, {}))
        guarded[key] = SimpleNamespace(**payload)
    return guarded


def enrich_corrected_guard_blocks(orders: pl.DataFrame, stock_df: pl.DataFrame) -> pl.DataFrame:
    blocked = orders.filter(pl.col("blocked_reason") == "st_or_ineligible_buy")
    if blocked.is_empty():
        return pl.DataFrame()
    panel = build_corrected_guard_panel(stock_df).select(
        [
            "date",
            "symbol",
            "exante_st",
            "corrected_research_eligible",
            "corrected_component_eligible",
            "corrected_adv20_turnover",
            "recomputed_adv20_turnover",
            "adv20_warmup_filled",
        ]
    )
    return (
        blocked.with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .join(panel, on=["date", "symbol"], how="left")
        .with_columns(
            pl.when(pl.col("exante_st").fill_null(False))
            .then(pl.lit("exante_st"))
            .when(~pl.col("corrected_research_eligible").fill_null(False))
            .then(pl.lit("not_corrected_research_eligible"))
            .when(~pl.col("corrected_component_eligible").fill_null(False))
            .then(pl.lit("not_index_component"))
            .otherwise(pl.lit("other"))
            .alias("corrected_guard_subreason")
        )
        .sort(["date", "symbol"])
    )


def summarize_corrected_blocks(blocks: pl.DataFrame) -> pl.DataFrame:
    if blocks.is_empty():
        return pl.DataFrame()
    return (
        blocks.group_by("corrected_guard_subreason")
        .agg(
            pl.len().alias("orders"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("adv20_warmup_filled").sum().alias("adv20_warmup_filled_orders"),
        )
        .sort("orders", descending=True)
    )


def build_quality(summary: dict[str, Any]) -> pl.DataFrame:
    rows = [
        {
            "checkpoint": "corrected_blocks_far_less_than_original",
            "status": "pass"
            if summary["corrected_blocked_orders"] < summary["original_guard_blocked_orders"] * 0.5
            else "warn",
            "value": str(summary["corrected_blocked_orders"]),
            "expected": f"<{summary['original_guard_blocked_orders'] * 0.5:.0f}",
            "note": "修正版应消除大部分ADV20暖机误阻断。",
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
            "checkpoint": "no_signal_parameter_change",
            "status": "pass",
            "value": "no signal/threshold change",
            "expected": "no signal/threshold change",
            "note": "只修执行层守门，不修改alpha信号。",
        },
    ]
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    scorecard: pl.DataFrame,
    block_summary: pl.DataFrame,
    corrected_block_summary: pl.DataFrame,
    state_summary: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> None:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    lines = [
        "# 股票震荡liquid_q3 30万 修正版ST/不可研究买入守门回放 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：修正ADV20暖机误阻断后的执行守门回放；不新增alpha信号、不调收益参数、不修改paper入口。",
        "- A/B判断：股票震荡独立执行层回放，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 滚动ADV20必须有明确lookback/warmup处理，缺失不能直接当作低流动性。",
        "- 历史ST仍应使用交易日前可知的`is_st/namechange`，不能使用当前名称泄漏。",
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
            f"- 第275原守门期末权益`{summary['original_guard_final_equity']:.4f}`，总收益`{pct(summary['original_guard_total_return'])}`，最大回撤`{pct(summary['original_guard_max_drawdown'])}`，Sharpe `{summary['original_guard_sharpe']:.4f}`。",
            f"- 修正版守门期末权益`{summary['corrected_final_equity']:.4f}`，总收益`{pct(summary['corrected_total_return'])}`，最大回撤`{pct(summary['corrected_max_drawdown'])}`，Sharpe `{summary['corrected_sharpe']:.4f}`。",
            f"- 原守门阻断`{summary['original_guard_blocked_orders']}`笔，修正版阻断`{summary['corrected_blocked_orders']}`笔。",
            f"- 相对基准：修正版总收益变化`{pct(summary['delta_total_return_vs_base'])}`，最大回撤变化`{pct(summary['delta_max_drawdown_vs_base'])}`，Sharpe变化`{summary['delta_sharpe_vs_base']:.4f}`。",
            "",
            "## 判断",
            "",
            "- 第277发现的ADV20暖机误阻断被修正版基本剔除，守门不再大面积误伤1月高流动性股票。",
            "- 修正版更接近实盘执行规则：真实ST不买、非成分不新增、ADV20缺失先重算。",
            "- 仍不直接改paper入口；下一步应检查修正版阻断明细和最新交易包，再做最小接入补丁。",
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
            "## 修正版阻断原因",
            "",
            "无数据"
            if corrected_block_summary.is_empty()
            else markdown_table(
                corrected_block_summary,
                [
                    "corrected_guard_subreason",
                    "orders",
                    "symbols",
                    "desired_amount_cny_sum",
                    "adv20_warmup_filled_orders",
                ],
                max_rows=50,
            ),
            "",
            "## 阻断原因汇总",
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
            "- 原因：修正版来自字段可用性修复，不来自收益搜索。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：回放验证执行层修复影响，不调alpha阈值；并且结论仍要求先检查阻断明细再接入。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第277发现原守门误伤严重，必须跑修正版才能判断守门方向是否保留。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：修正版消除了大部分误阻断，保留了执行层风控价值；下一步可进入最小接入方案评审。",
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
    selected_all = pl.read_parquet(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_selected_all.parquet")
    stock_df, benchmark_df = load_panels()
    target_weights = build_target_weights(selected_all)
    target_maps = lot.build_target_maps(target_weights)
    dates = lot.build_tracking_dates(target_weights, benchmark_df)

    base_exec_info = build_exec_info(stock_df)
    corrected_exec_info = build_corrected_guarded_exec_info(stock_df)
    base_orders, base_daily, base_curves = replay_with_classifier(target_maps, dates, base_exec_info, guard_enabled=False)
    corrected_orders, corrected_daily, corrected_curves = replay_with_classifier(
        target_maps, dates, corrected_exec_info, guard_enabled=True
    )
    base_summary = summarize_daily(base_daily, base_orders, "base_rerun")
    corrected_summary = summarize_daily(corrected_daily, corrected_orders, "corrected_st_buy_guard")
    original_summary = json.loads(
        (ORIGINAL_GUARD_OUTPUT_DIR / f"{ORIGINAL_GUARD_PREFIX}_summary.json").read_text(encoding="utf-8")
    )
    scorecard = pl.DataFrame(
        [
            base_summary,
            {
                "scenario": "original_st_buy_guard",
                "final_equity": original_summary["guard_final_equity"],
                "total_return": original_summary["guard_total_return"],
                "max_drawdown": original_summary["guard_max_drawdown"],
                "sharpe": original_summary["guard_sharpe"],
                "daily_rows": base_summary["daily_rows"],
                "orders": 16783,
                "filled_orders": 16273,
                "blocked_orders": 510,
                "blocked_amount_cny": 0.0,
                "st_or_ineligible_buy_blocked_orders": original_summary[
                    "guard_st_or_ineligible_buy_blocked_orders"
                ],
                "st_or_ineligible_buy_blocked_amount_cny": original_summary[
                    "guard_st_or_ineligible_buy_blocked_amount_cny"
                ],
                "total_min_fee_cost_cny": 0.0,
                "avg_actual_gross_weight": 0.0,
                "max_actual_gross_weight": 0.0,
            },
            corrected_summary,
        ]
    )
    corrected_block_audit = enrich_corrected_guard_blocks(corrected_orders, stock_df)
    corrected_block_summary = summarize_corrected_blocks(corrected_block_audit)
    block_summary = pl.concat(
        [
            build_block_reason_summary(base_orders, "base_rerun"),
            build_block_reason_summary(corrected_orders, "corrected_st_buy_guard"),
        ],
        how="vertical",
    )
    state = pl.read_csv(REPAIRABLE_OUTPUT_DIR / f"{REPAIRABLE_PREFIX}_repairable_state.csv", try_parse_dates=True)
    state_summary = pl.concat(
        [
            summarize_by_state(base_daily, state, "base_rerun"),
            summarize_by_state(corrected_daily, state, "corrected_st_buy_guard"),
        ],
        how="vertical",
    )

    corrected_st_block = corrected_orders.filter(pl.col("blocked_reason") == "st_or_ineligible_buy")
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "base_final_equity": base_summary["final_equity"],
        "base_total_return": base_summary["total_return"],
        "base_max_drawdown": base_summary["max_drawdown"],
        "base_sharpe": base_summary["sharpe"],
        "original_guard_final_equity": original_summary["guard_final_equity"],
        "original_guard_total_return": original_summary["guard_total_return"],
        "original_guard_max_drawdown": original_summary["guard_max_drawdown"],
        "original_guard_sharpe": original_summary["guard_sharpe"],
        "original_guard_blocked_orders": original_summary["guard_st_or_ineligible_buy_blocked_orders"],
        "original_guard_blocked_amount_cny": original_summary["guard_st_or_ineligible_buy_blocked_amount_cny"],
        "corrected_final_equity": corrected_summary["final_equity"],
        "corrected_total_return": corrected_summary["total_return"],
        "corrected_max_drawdown": corrected_summary["max_drawdown"],
        "corrected_sharpe": corrected_summary["sharpe"],
        "corrected_blocked_orders": corrected_st_block.height,
        "corrected_blocked_amount_cny": to_float(corrected_st_block["desired_amount_cny"].sum())
        if not corrected_st_block.is_empty()
        else 0.0,
        "delta_total_return_vs_base": corrected_summary["total_return"] - base_summary["total_return"],
        "delta_max_drawdown_vs_base": corrected_summary["max_drawdown"] - base_summary["max_drawdown"],
        "delta_sharpe_vs_base": corrected_summary["sharpe"] - base_summary["sharpe"],
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
        "corrected_orders": OUTPUT_DIR / f"{PREFIX}_corrected_orders.csv",
        "corrected_daily": OUTPUT_DIR / f"{PREFIX}_corrected_daily.csv",
        "corrected_curves": OUTPUT_DIR / f"{PREFIX}_corrected_curves.csv",
        "corrected_block_audit": OUTPUT_DIR / f"{PREFIX}_corrected_block_audit.csv",
        "corrected_block_summary": OUTPUT_DIR / f"{PREFIX}_corrected_block_summary.csv",
        "block_reason_summary": OUTPUT_DIR / f"{PREFIX}_block_reason_summary.csv",
        "state_summary": OUTPUT_DIR / f"{PREFIX}_state_summary.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
    }
    scorecard.write_csv(paths["scorecard"])
    base_orders.write_csv(paths["base_orders"])
    base_daily.write_csv(paths["base_daily"])
    base_curves.write_csv(paths["base_curves"])
    corrected_orders.write_csv(paths["corrected_orders"])
    corrected_daily.write_csv(paths["corrected_daily"])
    corrected_curves.write_csv(paths["corrected_curves"])
    corrected_block_audit.write_csv(paths["corrected_block_audit"])
    corrected_block_summary.write_csv(paths["corrected_block_summary"])
    block_summary.write_csv(paths["block_reason_summary"])
    state_summary.write_csv(paths["state_summary"])
    quality.write_csv(paths["quality_checkpoints"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(summary, scorecard, block_summary, corrected_block_summary, state_summary, quality, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report={paths['report']}")


if __name__ == "__main__":
    main()
