from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage750_official_500k_vs_c50_monthly_start as s750
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_winner_trade_forensics"
SOURCE_LINE_ID = "futures_trend_quarter_risk_no_streak"

OUTPUT_PREFIX = "qmt_roll_stage758_a50_streak_oi_confirm_exemption"
MODEL_TAG = "stage758_a50_streak_oi_confirm_exemption_v1"

BASE_VARIANT = s750.A50_VARIANT
CANDIDATE_VARIANT = "stage526_500k_force95_to80_oi_confirm_streak_exempt_r080_pc25_maxpos4_stage758"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
RESTORE_GROUP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_restore_group_stats_{MODEL_TAG}.csv"
RESTORE_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_restore_lots_{MODEL_TAG}.csv"
YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_stats_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _candidate_spec(metadata: dict[str, Any]) -> Any:
    base = s750._official_500k_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="Stage758 A50 OI price confirm exempts loss-streak throttle",
        note=(
            "Stage750 official 500k logic unchanged, but if the latest completed daily bar has OI up "
            "and price aligned with the trade direction, the loss-streak risk multiplier is restored "
            "to 1.0. Effective formal risk remains 0.80; this does not lever normal non-throttled entries."
        ),
    )
    overrides = {
        **base.overrides,
        "enable_oi_price_confirm_risk_restore": True,
        "oi_price_confirm_risk_restore_multiplier": 1.00,
        "oi_price_confirm_risk_restore_entry_contexts": "flat_entry,reverse_entry,rollover_reopen",
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_500k_oi_streak_exempt_stage758")


def _load_base_full_summary() -> pd.Series:
    frame = pd.read_csv(s750.A50_SUMMARY_PATH, encoding="utf-8-sig")
    full = frame[
        frame["variant"].astype(str).eq(BASE_VARIANT)
        & frame["window_name"].astype(str).eq("mstart_2020_01")
    ].copy()
    if full.empty:
        raise FileNotFoundError(f"missing Stage750 A50 full summary: {s750.A50_SUMMARY_PATH}")
    return full.iloc[0]


def _comparison(base: pd.Series, candidate: pd.Series) -> pd.DataFrame:
    fields = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "p95_broker10_margin_to_equity_pct",
        "forced_margin_deleverage_count",
    ]
    row: dict[str, Any] = {
        "base_variant": BASE_VARIANT,
        "candidate_variant": CANDIDATE_VARIANT,
    }
    for field in fields:
        row[f"base_{field}"] = base.get(field)
        row[f"candidate_{field}"] = candidate.get(field)
    row["delta_end_equity"] = float(candidate["end_equity"]) - float(base["end_equity"])
    row["delta_return_pct"] = float(candidate["total_return_pct"]) - float(base["total_return_pct"])
    row["delta_max_dd_pp"] = float(candidate["max_dd_pct"]) - float(base["max_dd_pct"])
    row["delta_sharpe"] = float(candidate["sharpe"]) - float(base["sharpe"])
    row["delta_slippage"] = float(candidate["total_slippage"]) - float(base["total_slippage"])
    row["delta_trade_count"] = float(candidate["total_trade_count"]) - float(base["total_trade_count"])
    return pd.DataFrame([row])


def _decision(comparison: pd.DataFrame, restore_group: pd.DataFrame, cost: pd.DataFrame) -> dict[str, Any]:
    cmp = comparison.iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if float(cmp["candidate_max_dd_pct"]) < -40.0:
        hard_fail.append("candidate_full_dd40_fail")
    if float(cmp["delta_max_dd_pp"]) < -3.0:
        hard_fail.append("candidate_dd_worse_more_than_3pp")
    if float(cmp["delta_sharpe"]) < -0.15:
        hard_fail.append("candidate_sharpe_worse_more_than_0_15")
    if float(cmp["delta_end_equity"]) <= 0.0:
        hard_fail.append("candidate_no_full_return_improvement")
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].iloc[0]
    if int(cost2["deployable_pass"]) != 1:
        hard_fail.append("candidate_cost2_deployable_fail")
    applied = restore_group[restore_group["sample"].eq("causal_oi_restore_applied")].iloc[0]
    if int(applied["rows"]) < 30:
        watch.append("restore_sample_lt30")
    if float(applied["profit_rate_pct"]) < 50.0:
        watch.append("restore_trade_winrate_lt50")
    return {
        "stage": "Stage758",
        "line_id": LINE_ID,
        "source_line_id": SOURCE_LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base": BASE_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "decision": "a50_streak_oi_confirm_exemption_candidate_watch" if not hard_fail else "a50_streak_oi_confirm_exemption_not_promoted",
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "base_risk_multiplier": 0.80,
            "streak_risk_multipliers": "1.0,1.0,1.0,0.1",
            "restored_streak_risk_multiplier": 1.00,
            "enable_streak_entry_structure_risk_recovery": True,
            "enable_recovery_sleeve": True,
            "enable_oi_price_confirm_risk_restore": True,
            "causal_timing": "latest_completed_daily_bar",
        },
        "comparison": comparison.to_dict("records"),
        "restore_group": restore_group.to_dict("records"),
        "cost": cost.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "comparison": str(COMPARISON_PATH),
            "cost": str(COST_PATH),
            "curve": str(CURVE_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "restore_group": str(RESTORE_GROUP_PATH),
            "restore_lots": str(RESTORE_LOTS_PATH),
            "year": str(YEAR_PATH),
        },
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s719.s513._metadata()
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

    closed = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    enriched = s757._add_lot_features(closed, trades, entry_risk)
    enriched.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")

    restore_group = s757._restore_group_stats(enriched)
    restore_group.to_csv(RESTORE_GROUP_PATH, index=False, encoding="utf-8-sig")
    restore_lots = enriched[pd.to_numeric(enriched["oi_price_confirm_risk_restore_applied"], errors="coerce").eq(1)].copy()
    restore_lots.to_csv(RESTORE_LOTS_PATH, index=False, encoding="utf-8-sig")
    year = s757._year_stats(enriched)
    year.to_csv(YEAR_PATH, index=False, encoding="utf-8-sig")

    base = _load_base_full_summary()
    comparison = _comparison(base, summary.iloc[0])
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    decision = _decision(comparison, restore_group, cost)
    DECISION_PATH.write_text(json.dumps(s748._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("SUMMARY")
    print(summary.to_string(index=False))
    print("\nCOMPARISON")
    print(comparison.to_string(index=False))
    print("\nRESTORE_GROUP")
    print(restore_group.to_string(index=False))
    print("\nYEAR")
    print(year.to_string(index=False))
    print("\nDECISION")
    print(json.dumps(s748._json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
