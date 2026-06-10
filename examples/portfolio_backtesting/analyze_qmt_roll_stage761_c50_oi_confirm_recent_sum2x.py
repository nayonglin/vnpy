from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import json

import pandas as pd

import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_winner_trade_forensics"
SOURCE_LINE_ID = "futures_trend_quarter_risk_no_streak"

OUTPUT_PREFIX = "qmt_roll_stage761_c50_oi_confirm_recent_sum2x"
MODEL_TAG = "stage761_c50_oi_confirm_recent_sum2x_v1"

BASE_VARIANT = s757.BASE_VARIANT
STAGE757_VARIANT = s757.CANDIDATE_VARIANT
CANDIDATE_VARIANT = "stage526_500k_force95_to80_r040_oi_confirm_sum5x2_r080_no_streak_no_recovery_stage761"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_STAGE748_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_stage748_{MODEL_TAG}.csv"
COMPARISON_STAGE757_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_stage757_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
RESTORE_GROUP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_restore_group_stats_{MODEL_TAG}.csv"
RESTORE_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_restore_lots_{MODEL_TAG}.csv"
YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_stats_{MODEL_TAG}.csv"
RECENT_SUM_REASON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_recent_sum_reason_stats_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

RECENT_SUM_DAYS = 5
RECENT_SUM_MIN_RATIO = 2.0


def _candidate_spec(metadata: dict[str, Any]) -> Any:
    base = s748._candidate_500k_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="Stage761 C50 OI confirm plus 5d OI sum >= 2x prior 5d restores 0.80 risk",
        note=(
            "Stage757 logic, but OI risk restore additionally requires the latest 5 completed "
            "open-interest values to sum at least 2x the prior 5 values."
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
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_r040_oi_sum5x2_r080_no_streak_stage761")


def _load_stage748_full_summary() -> pd.Series:
    return s757._load_base_full_summary()


def _load_stage757_summary() -> pd.Series:
    frame = pd.read_csv(s757.SUMMARY_PATH, encoding="utf-8-sig")
    full = frame[
        frame["variant"].astype(str).eq(STAGE757_VARIANT)
        & frame["window_name"].astype(str).eq("full_2020_20260430")
    ].copy()
    if full.empty:
        raise FileNotFoundError(f"missing Stage757 full summary: {s757.SUMMARY_PATH}")
    return full.iloc[0]


def _comparison_named(base: pd.Series, candidate: pd.Series, *, base_name: str, base_variant: str) -> pd.DataFrame:
    frame = s757._comparison(base, candidate)
    frame["base_variant"] = base_variant
    frame["candidate_variant"] = CANDIDATE_VARIANT
    frame["base_name"] = base_name
    frame["candidate_name"] = "stage761_sum5x2"
    return frame


def _risk_by_open_trade_extra(trades: pd.DataFrame, entry_risk: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return s757._risk_by_open_trade(trades, entry_risk)


def _add_recent_sum_fields(enriched: pd.DataFrame, trades: pd.DataFrame, entry_risk: pd.DataFrame) -> pd.DataFrame:
    data = enriched.copy()
    risk_by_open = _risk_by_open_trade_extra(trades, entry_risk)
    extra_fields = [
        "oi_price_confirm_recent_sum_ratio_required",
        "oi_price_confirm_recent_sum_days",
        "oi_price_confirm_recent_oi_sum",
        "oi_price_confirm_prior_oi_sum",
        "oi_price_confirm_recent_prior_oi_sum_ratio",
        "oi_price_confirm_recent_sum_ratio_passed",
    ]
    for field in extra_fields:
        data[field] = [
            risk_by_open.get(str(open_trade_id), {}).get(field, pd.NA)
            for open_trade_id in data["open_trade_id"].astype(str)
        ]
    return data


def _recent_sum_reason_stats(entry_risk: pd.DataFrame) -> pd.DataFrame:
    data = entry_risk.copy()
    if data.empty:
        return pd.DataFrame()
    data["oi_price_confirm_risk_restore_applied"] = pd.to_numeric(
        data.get("oi_price_confirm_risk_restore_applied", 0), errors="coerce"
    ).fillna(0)
    data["oi_price_confirm_oi_up"] = pd.to_numeric(data.get("oi_price_confirm_oi_up", 0), errors="coerce").fillna(0)
    data["oi_price_confirm_price_aligned"] = pd.to_numeric(
        data.get("oi_price_confirm_price_aligned", 0), errors="coerce"
    ).fillna(0)
    data["oi_price_confirm_recent_sum_ratio_passed"] = pd.to_numeric(
        data.get("oi_price_confirm_recent_sum_ratio_passed", 0), errors="coerce"
    ).fillna(0)
    data["base_oi_price_confirm_hit"] = (
        data["oi_price_confirm_oi_up"].eq(1) & data["oi_price_confirm_price_aligned"].eq(1)
    ).astype(int)
    grouped = (
        data.groupby("oi_price_confirm_risk_restore_reason", dropna=False)
        .agg(
            entry_rows=("entry_index", "count"),
            applied_rows=("oi_price_confirm_risk_restore_applied", "sum"),
            base_oi_price_confirm_rows=("base_oi_price_confirm_hit", "sum"),
            recent_sum_pass_rows=("oi_price_confirm_recent_sum_ratio_passed", "sum"),
            selected_volume=("selected_volume", "sum"),
        )
        .reset_index()
        .sort_values(["applied_rows", "entry_rows"], ascending=[False, False])
    )
    return grouped


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
    if float(applied["profit_rate_pct"]) < 50.0:
        watch.append("restore_trade_winrate_lt50")
    if reason.empty or int(reason["applied_rows"].sum()) == 0:
        hard_fail.append("no_oi_restore_trades_after_recent_sum_filter")
    decision = "c50_oi_confirm_recent_sum2x_candidate_watch" if not hard_fail else "c50_oi_confirm_recent_sum2x_not_promoted"
    return {
        "stage": "Stage761",
        "line_id": LINE_ID,
        "source_line_id": SOURCE_LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base_stage748": BASE_VARIANT,
        "base_stage757": STAGE757_VARIANT,
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
            "summary": str(SUMMARY_PATH),
            "comparison_stage748": str(COMPARISON_STAGE748_PATH),
            "comparison_stage757": str(COMPARISON_STAGE757_PATH),
            "cost": str(COST_PATH),
            "curve": str(CURVE_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "restore_group": str(RESTORE_GROUP_PATH),
            "restore_lots": str(RESTORE_LOTS_PATH),
            "year": str(YEAR_PATH),
            "recent_sum_reason": str(RECENT_SUM_REASON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame if max_rows is None else frame.head(max_rows)
    if data.empty:
        return "_empty_"
    return data.to_markdown(index=False)


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
        "# Stage761 C50 OI确认 + 5日OI合计2倍过滤",
        "",
        f"- 生成时间：`{datetime.now():%Y-%m-%d %H:%M CST}`",
        f"- 决策：`{decision['decision']}`",
        "- 口径：Stage757 基础上，只有 `最近5根已完成日线OI合计 >= 前5根OI合计 * 2.0` 时才恢复到等效 `0.80` 风险。",
        "- 不改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Summary",
        _md_table(summary),
        "",
        "## Vs Stage748",
        _md_table(comparison_stage748),
        "",
        "## Vs Stage757",
        _md_table(comparison_stage757),
        "",
        "## Restore Group",
        _md_table(restore_group),
        "",
        "## Recent Sum Reason",
        _md_table(reason),
        "",
        "## Year",
        _md_table(year, max_rows=30),
        "",
        "## Decision",
        "```json",
        json.dumps(s748._json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s757.s719.s513._metadata()
    spec = _candidate_spec(metadata)
    engine, frames, combined, forced_events = s757._run_engine(spec, metadata)

    trades = frames["trades"]
    entry_risk = frames["entry_risk"]
    entry_candidates = frames["entry_candidates"]
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")

    row, curve, cost_rows = s748._metric_row(
        combined,
        spec=spec,
        window_name="full_2020_20260430",
        window_label="Full 2020-2026",
        window_group="full",
        forced_events=forced_events,
    )
    summary = pd.DataFrame([row])
    cost = pd.DataFrame(cost_rows)
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")

    closed = s757.s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    enriched = s757._add_lot_features(closed, trades, entry_risk)
    enriched = _add_recent_sum_fields(enriched, trades, entry_risk)
    enriched.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")

    restore_group = s757._restore_group_stats(enriched)
    restore_group.to_csv(RESTORE_GROUP_PATH, index=False, encoding="utf-8-sig")
    restore_lots = enriched[pd.to_numeric(enriched["oi_price_confirm_risk_restore_applied"], errors="coerce").eq(1)].copy()
    restore_lots.to_csv(RESTORE_LOTS_PATH, index=False, encoding="utf-8-sig")
    year = s757._year_stats(enriched)
    year.to_csv(YEAR_PATH, index=False, encoding="utf-8-sig")
    reason = _recent_sum_reason_stats(entry_risk)
    reason.to_csv(RECENT_SUM_REASON_PATH, index=False, encoding="utf-8-sig")

    comparison_stage748 = _comparison_named(
        _load_stage748_full_summary(),
        summary.iloc[0],
        base_name="Stage748",
        base_variant=BASE_VARIANT,
    )
    comparison_stage757 = _comparison_named(
        _load_stage757_summary(),
        summary.iloc[0],
        base_name="Stage757",
        base_variant=STAGE757_VARIANT,
    )
    comparison_stage748.to_csv(COMPARISON_STAGE748_PATH, index=False, encoding="utf-8-sig")
    comparison_stage757.to_csv(COMPARISON_STAGE757_PATH, index=False, encoding="utf-8-sig")
    decision = _decision(comparison_stage748, comparison_stage757, restore_group, cost, reason)
    DECISION_PATH.write_text(json.dumps(s748._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, comparison_stage748, comparison_stage757, restore_group, reason, year, decision)

    print("SUMMARY")
    print(summary.to_string(index=False))
    print("\nCOMPARISON_STAGE748")
    print(comparison_stage748.to_string(index=False))
    print("\nCOMPARISON_STAGE757")
    print(comparison_stage757.to_string(index=False))
    print("\nRESTORE_GROUP")
    print(restore_group.to_string(index=False))
    print("\nRECENT_SUM_REASON")
    print(reason.to_string(index=False))
    print("\nYEAR")
    print(year.to_string(index=False))
    print("\nDECISION")
    print(json.dumps(s748._json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
