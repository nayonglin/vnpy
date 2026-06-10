from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import json

import pandas as pd

import analyze_qmt_roll_stage761_c50_oi_confirm_recent_sum2x as s761


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

OUTPUT_PREFIX = "qmt_roll_stage762_c50_oi_confirm_recent_sum15x"
MODEL_TAG = "stage762_c50_oi_confirm_recent_sum15x_v1"
CANDIDATE_VARIANT = "stage526_500k_force95_to80_r040_oi_confirm_sum5x15_r080_no_streak_no_recovery_stage762"

RECENT_SUM_DAYS = 5
RECENT_SUM_MIN_RATIO = 1.5


def _configure_stage761_globals() -> None:
    s761.OUTPUT_PREFIX = OUTPUT_PREFIX
    s761.MODEL_TAG = MODEL_TAG
    s761.CANDIDATE_VARIANT = CANDIDATE_VARIANT
    s761.SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    s761.COMPARISON_STAGE748_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_stage748_{MODEL_TAG}.csv"
    s761.COMPARISON_STAGE757_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_stage757_{MODEL_TAG}.csv"
    s761.COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
    s761.CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
    s761.TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
    s761.ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
    s761.ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
    s761.CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
    s761.RESTORE_GROUP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_restore_group_stats_{MODEL_TAG}.csv"
    s761.RESTORE_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_restore_lots_{MODEL_TAG}.csv"
    s761.YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_stats_{MODEL_TAG}.csv"
    s761.RECENT_SUM_REASON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_recent_sum_reason_stats_{MODEL_TAG}.csv"
    s761.DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    s761.REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    s761.RECENT_SUM_DAYS = RECENT_SUM_DAYS
    s761.RECENT_SUM_MIN_RATIO = RECENT_SUM_MIN_RATIO
    s761._candidate_spec = _candidate_spec
    s761._comparison_named = _comparison_named
    s761._decision = _decision
    s761._write_report = _write_report


def _candidate_spec(metadata: dict[str, Any]) -> Any:
    base = s761.s748._candidate_500k_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="Stage762 C50 OI confirm plus 5d OI sum >= 1.5x prior 5d restores 0.80 risk",
        note=(
            "Stage757 logic, but OI risk restore additionally requires the latest 5 completed "
            "open-interest values to sum at least 1.5x the prior 5 values."
        ),
    )
    overrides = {
        **base.overrides,
        "enable_oi_price_confirm_risk_restore": True,
        "oi_price_confirm_risk_restore_multiplier": 2.00,
        "oi_price_confirm_risk_restore_entry_contexts": "flat_entry,reverse_entry,rollover_reopen",
        "oi_price_confirm_risk_restore_require_recent_sum_ratio": True,
        "oi_price_confirm_risk_restore_recent_sum_days": RECENT_SUM_DAYS,
        "oi_price_confirm_risk_restore_recent_sum_min_ratio": RECENT_SUM_MIN_RATIO,
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_r040_oi_sum5x15_r080_no_streak_stage762")


def _comparison_named(base: pd.Series, candidate: pd.Series, *, base_name: str, base_variant: str) -> pd.DataFrame:
    frame = s761.s757._comparison(base, candidate)
    frame["base_variant"] = base_variant
    frame["candidate_variant"] = CANDIDATE_VARIANT
    frame["base_name"] = base_name
    frame["candidate_name"] = "stage762_sum5x15"
    return frame


def _decision(
    comparison_stage748: pd.DataFrame,
    comparison_stage757: pd.DataFrame,
    restore_group: pd.DataFrame,
    cost: pd.DataFrame,
    reason: pd.DataFrame,
) -> dict[str, Any]:
    cmp748 = comparison_stage748.iloc[0]
    cmp757 = comparison_stage757.iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if float(cmp748["candidate_max_dd_pct"]) < -40.0:
        hard_fail.append("candidate_full_dd40_fail_vs_stage748")
    if float(cmp757["delta_end_equity"]) < 0.0 and float(cmp757["delta_max_dd_pp"]) <= 0.0:
        hard_fail.append("worse_return_without_dd_improvement_vs_stage757")
    if float(cmp757["delta_sharpe"]) < -0.15:
        hard_fail.append("sharpe_worse_more_than_0_15_vs_stage757")
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].iloc[0]
    if int(cost2["deployable_pass"]) != 1:
        hard_fail.append("candidate_cost2_deployable_fail")
    applied = restore_group[restore_group["sample"].eq("causal_oi_restore_applied")].iloc[0]
    if int(applied["rows"]) < 30:
        watch.append("restore_sample_lt30")
    if pd.notna(applied["profit_rate_pct"]) and float(applied["profit_rate_pct"]) < 50.0:
        watch.append("restore_trade_winrate_lt50")
    if reason.empty or int(reason["applied_rows"].sum()) == 0:
        hard_fail.append("no_oi_restore_trades_after_recent_sum_filter")
    decision = "c50_oi_confirm_recent_sum15x_candidate_watch" if not hard_fail else "c50_oi_confirm_recent_sum15x_not_promoted"
    return {
        "stage": "Stage762",
        "line_id": s761.LINE_ID,
        "source_line_id": s761.SOURCE_LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base_stage748": s761.BASE_VARIANT,
        "base_stage757": s761.STAGE757_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "base_risk_multiplier": 0.40,
            "restored_risk_multiplier": 0.80,
            "strategy_internal_restore_multiplier": 2.00,
            "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
            "enable_recovery_sleeve": False,
            "enable_oi_price_confirm_risk_restore": True,
            "oi_price_confirm_risk_restore_require_recent_sum_ratio": True,
            "oi_price_confirm_risk_restore_recent_sum_days": RECENT_SUM_DAYS,
            "oi_price_confirm_risk_restore_recent_sum_min_ratio": RECENT_SUM_MIN_RATIO,
            "causal_timing": "latest_completed_daily_bar",
        },
        "comparison_stage748": comparison_stage748.to_dict("records"),
        "comparison_stage757": comparison_stage757.to_dict("records"),
        "restore_group": restore_group.to_dict("records"),
        "recent_sum_reason": reason.to_dict("records"),
        "cost": cost.to_dict("records"),
        "outputs": {
            "summary": str(s761.SUMMARY_PATH),
            "comparison_stage748": str(s761.COMPARISON_STAGE748_PATH),
            "comparison_stage757": str(s761.COMPARISON_STAGE757_PATH),
            "cost": str(s761.COST_PATH),
            "curve": str(s761.CURVE_PATH),
            "closed_lots": str(s761.CLOSED_LOTS_PATH),
            "restore_group": str(s761.RESTORE_GROUP_PATH),
            "restore_lots": str(s761.RESTORE_LOTS_PATH),
            "year": str(s761.YEAR_PATH),
            "recent_sum_reason": str(s761.RECENT_SUM_REASON_PATH),
            "report": str(s761.REPORT_PATH),
        },
    }


def _write_report(
    summary: pd.DataFrame,
    comparison_stage748: pd.DataFrame,
    comparison_stage757: pd.DataFrame,
    restore_group: pd.DataFrame,
    reason: pd.DataFrame,
    year: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage762 C50 OI确认 + 5日OI合计1.5倍过滤",
        "",
        f"- 生成时间：`{datetime.now():%Y-%m-%d %H:%M CST}`",
        f"- 决策：`{decision['decision']}`",
        "- 口径：Stage757 基础上，只有 `最近5根已完成日线OI合计 >= 前5根OI合计 * 1.5` 时才恢复到等效 `0.80` 风险。",
        "- 不改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Summary",
        s761._md_table(summary),
        "",
        "## Vs Stage748",
        s761._md_table(comparison_stage748),
        "",
        "## Vs Stage757",
        s761._md_table(comparison_stage757),
        "",
        "## Restore Group",
        s761._md_table(restore_group),
        "",
        "## Recent Sum Reason",
        s761._md_table(reason),
        "",
        "## Year",
        s761._md_table(year, max_rows=30),
        "",
        "## Decision",
        "```json",
        json.dumps(s761.s748._json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    s761.REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    _configure_stage761_globals()
    s761.main()


if __name__ == "__main__":
    main()
