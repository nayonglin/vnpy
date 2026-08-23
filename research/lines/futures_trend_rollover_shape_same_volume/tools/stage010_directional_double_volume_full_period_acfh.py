from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import stage001_rollover_shape_same_volume_ac as s1
import stage002_rollover_shape_shrink_to_allowed_abc as s2
import stage007_directional_boost_multicycle_acd as s7


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage010"

SUMMARY_PATH = OUTPUT_DIR / "stage010_acfh_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage010_acfh_comparison.csv"
CURVE_PATH = OUTPUT_DIR / "stage010_acfh_curve.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / "stage010_full_h_entry_risk.csv"
TRADES_PATH = OUTPUT_DIR / "stage010_full_h_trades.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / "stage010_full_h_trade_events.csv"
VOLUME_CONTRACT_PATH = OUTPUT_DIR / "stage010_full_h_volume_contract_summary.csv"
DECISION_PATH = OUTPUT_DIR / "stage010_decision.json"

ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm": "A",
        "profile": "stage010_A_official_live_c9_15w",
        "rollover_candidate": False,
        "risk_boost": False,
        "volume_confirmation": False,
        "volume_ratio_threshold": 1.0,
        "label": "A: Official C9/150k",
    },
    {
        "arm": "C",
        "profile": "stage010_C_rollover_continuation",
        "rollover_candidate": True,
        "risk_boost": False,
        "volume_confirmation": False,
        "volume_ratio_threshold": 1.0,
        "label": "C: Official + rollover continuation",
    },
    {
        "arm": "F",
        "profile": "stage010_F_direction_and_volume_gt_1x",
        "rollover_candidate": True,
        "risk_boost": True,
        "volume_confirmation": True,
        "volume_ratio_threshold": 1.0,
        "label": "F: C + 30D direction and recent volume > 1x prior risk x1.2",
    },
    {
        "arm": "H",
        "profile": "stage010_H_direction_and_volume_gt_2x",
        "rollover_candidate": True,
        "risk_boost": True,
        "volume_confirmation": True,
        "volume_ratio_threshold": 2.0,
        "label": "H: C + 30D direction and recent volume > 2x prior risk x1.2",
    },
)

COMPARISONS: tuple[tuple[str, str, str], ...] = (
    ("A_vs_C", "A", "C"),
    ("A_vs_F", "A", "F"),
    ("C_vs_F", "C", "F"),
    ("A_vs_H", "A", "H"),
    ("C_vs_H", "C", "H"),
    ("F_vs_H", "F", "H"),
)

METRICS = (
    "end_equity",
    "total_return_pct",
    "max_dd_pct",
    "sharpe",
    "total_slippage",
    "total_trade_count",
    "nonzero_daily_win_rate_pct",
)


def _run_arm(
    metadata: dict[str, Any],
    arm: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    original_overrides = s1._overrides

    def experiment_overrides(
        *,
        candidate: bool,
        volume_policy: str = "exact_or_skip",
        history_mode: str = "target_contract_only",
    ) -> dict[str, Any]:
        overrides = original_overrides(
            candidate=candidate,
            volume_policy=volume_policy,
            history_mode=history_mode,
        )
        overrides.update(
            {
                "enable_directional_30d_risk_boost": bool(arm["risk_boost"]),
                "directional_30d_risk_boost_lookback": 30,
                "directional_30d_risk_boost_multiplier": 1.2,
                "directional_30d_risk_boost_require_volume_expansion": bool(
                    arm["volume_confirmation"]
                ),
                "directional_30d_volume_recent_days": 10,
                "directional_30d_volume_prior_days": 10,
                "directional_30d_volume_ratio_threshold": float(
                    arm["volume_ratio_threshold"]
                ),
            }
        )
        return overrides

    try:
        s1._overrides = experiment_overrides
        summary, curve, frames = s1._run_arm(
            profile_name=str(arm["profile"]),
            candidate=bool(arm["rollover_candidate"]),
            metadata=metadata,
            volume_policy="shrink_to_allowed",
            history_mode=(
                "backwards_ratio_continuous"
                if bool(arm["rollover_candidate"])
                else "target_contract_only"
            ),
            label=str(arm["label"]),
        )
    finally:
        s1._overrides = original_overrides

    summary = summary.copy()
    summary["experiment_arm"] = str(arm["arm"])
    curve = curve.copy()
    curve["experiment_arm"] = str(arm["arm"])
    return summary, curve, frames


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    by_arm = summary.set_index("experiment_arm")
    rows: list[dict[str, Any]] = []
    for comparison_name, left_arm, right_arm in COMPARISONS:
        left = by_arm.loc[left_arm]
        right = by_arm.loc[right_arm]
        rows.append(
            {
                "comparison": comparison_name,
                "left_arm": left_arm,
                "right_arm": right_arm,
                "left_end_equity": float(left["end_equity"]),
                "right_end_equity": float(right["end_equity"]),
                "left_return_pct": float(left["total_return_pct"]),
                "right_return_pct": float(right["total_return_pct"]),
                "delta_return_pct": float(right["total_return_pct"] - left["total_return_pct"]),
                "left_max_dd_pct": float(left["max_dd_pct"]),
                "right_max_dd_pct": float(right["max_dd_pct"]),
                "dd_worsening_pp": max(
                    0.0, float(left["max_dd_pct"] - right["max_dd_pct"])
                ),
                "left_sharpe": float(left["sharpe"]),
                "right_sharpe": float(right["sharpe"]),
                "delta_sharpe": float(right["sharpe"] - left["sharpe"]),
                "left_slippage": float(left["total_slippage"]),
                "right_slippage": float(right["total_slippage"]),
                "left_trades": int(left["total_trade_count"]),
                "right_trades": int(right["total_trade_count"]),
                "left_win_rate_pct": float(left["nonzero_daily_win_rate_pct"]),
                "right_win_rate_pct": float(right["nonzero_daily_win_rate_pct"]),
                "left_survival_pass": int(left["account_survival_pass"]),
                "right_survival_pass": int(right["account_survival_pass"]),
                "left_broker100_pass": int(left["broker10_100_pass"]),
                "right_broker100_pass": int(right["broker10_100_pass"]),
                "left_broker10_peak_pct": float(left["max_broker10_margin_to_equity_pct"]),
                "right_broker10_peak_pct": float(right["max_broker10_margin_to_equity_pct"]),
                "left_days_over_100pct": int(left["days_over_100pct"]),
                "right_days_over_100pct": int(right["days_over_100pct"]),
            }
        )
    return pd.DataFrame(rows)


def _volume_contract_summary(entry_risk: pd.DataFrame) -> pd.DataFrame:
    required = {
        "direction",
        "entry_context",
        "directional_30d_risk_boost_enabled",
        "directional_30d_volume_confirmation_enabled",
        "directional_30d_risk_boost_aligned",
        "directional_30d_volume_ratio_threshold",
        "directional_30d_recent_volume_sum",
        "directional_30d_prior_volume_sum",
        "directional_30d_risk_boost_applied",
        "directional_30d_risk_boost_multiplier",
        "risk_amount_before_directional_30d_boost",
        "target_risk_amount",
    }
    empty = {
        "group_type": "total",
        "group_value": "all",
        "diagnostic_intent_count": 0,
        "price_aligned_count": 0,
        "boost_applied_count": 0,
        "boost_suppressed_by_volume_count": 0,
        "threshold_contract_pass": 0,
        "risk_amount_contract_pass": 0,
    }
    if entry_risk.empty or not required.issubset(entry_risk.columns):
        return pd.DataFrame([empty])

    frame = entry_risk.copy()
    numeric_columns = sorted(required - {"direction", "entry_context"})
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[
        frame["directional_30d_risk_boost_enabled"].eq(1)
        & frame["directional_30d_volume_confirmation_enabled"].eq(1)
    ].copy()

    def summarize(group_type: str, group_value: str, group: pd.DataFrame) -> dict[str, Any]:
        aligned = group["directional_30d_risk_boost_aligned"].fillna(0).astype(int).eq(1)
        threshold_exact = np.isclose(
            group["directional_30d_volume_ratio_threshold"].to_numpy(dtype="float64"),
            2.0,
            rtol=0.0,
            atol=1e-12,
        )
        volume_confirmed = (
            group["directional_30d_prior_volume_sum"].gt(0)
            & group["directional_30d_recent_volume_sum"].gt(
                group["directional_30d_prior_volume_sum"]
                * group["directional_30d_volume_ratio_threshold"]
            )
        )
        expected_applied = aligned & volume_confirmed
        applied = group["directional_30d_risk_boost_applied"].fillna(0).astype(int).eq(1)
        expected_multiplier = np.where(expected_applied, 1.2, 1.0)
        expected_risk = group["risk_amount_before_directional_30d_boost"] * expected_multiplier
        valid_risk = (
            applied.eq(expected_applied)
            & group["risk_amount_before_directional_30d_boost"].notna()
            & group["target_risk_amount"].notna()
            & np.isclose(
                group["directional_30d_risk_boost_multiplier"].to_numpy(dtype="float64"),
                expected_multiplier,
                rtol=0.0,
                atol=1e-12,
            )
            & np.isclose(
                group["target_risk_amount"].to_numpy(dtype="float64"),
                expected_risk.to_numpy(dtype="float64"),
                rtol=1e-12,
                atol=1e-9,
            )
        )
        return {
            "group_type": group_type,
            "group_value": group_value,
            "diagnostic_intent_count": int(len(group)),
            "price_aligned_count": int(aligned.sum()),
            "boost_applied_count": int(applied.sum()),
            "boost_suppressed_by_volume_count": int((aligned & ~applied).sum()),
            "threshold_contract_pass": int(
                len(group) > 0 and bool(np.asarray(threshold_exact).all())
            ),
            "risk_amount_contract_pass": int(
                len(group) > 0 and bool(np.asarray(valid_risk).all())
            ),
        }

    rows = [summarize("total", "all", frame)]
    for column, group_type in (("direction", "direction"), ("entry_context", "entry_context")):
        for value, group in frame.groupby(column, sort=True, dropna=False):
            rows.append(summarize(group_type, str(value), group))
    return pd.DataFrame(rows)


def _decision(
    comparison: pd.DataFrame,
    volume_contract: pd.DataFrame,
) -> dict[str, Any]:
    full_rows: list[dict[str, Any]] = []
    for comparison_name, _, _ in COMPARISONS:
        row = comparison[comparison["comparison"].eq(comparison_name)].iloc[0]
        gates = s7._full_period_gates(row)
        full_rows.append(
            {"comparison": comparison_name, "gates": gates, "pass": bool(all(gates.values()))}
        )

    total = volume_contract[volume_contract["group_type"].astype(str).eq("total")].iloc[0]
    aligned_count = int(total["price_aligned_count"])
    applied_count = int(total["boost_applied_count"])
    contract_gates = {
        "threshold_contract_pass": bool(int(total["threshold_contract_pass"]) == 1),
        "risk_amount_contract_pass": bool(int(total["risk_amount_contract_pass"]) == 1),
        "diagnostic_intents_present": bool(int(total["diagnostic_intent_count"]) > 0),
        "price_aligned_intents_present": bool(aligned_count > 0),
        "double_volume_boost_triggered": bool(applied_count > 0),
        "double_volume_gate_selective_le_30pct": bool(
            aligned_count > 0 and applied_count / aligned_count <= 0.30
        ),
    }
    promotion_comparisons = {"A_vs_H", "C_vs_H"}
    promotion_rows = [row for row in full_rows if row["comparison"] in promotion_comparisons]
    escalate = bool(all(contract_gates.values()) and all(row["pass"] for row in promotion_rows))
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage010",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "period": {"start": str(s1.START.date()), "end": str(s1.END.date())},
        "arms": {str(arm["arm"]): str(arm["profile"]) for arm in ARMS},
        "H_rule": {
            "price_direction_lookback_days": 30,
            "recent_volume_window": "T-9 through T, includes signal day",
            "prior_volume_window": "T-19 through T-10",
            "volume_condition": "recent 10-day sum strictly greater than 2.0 times prior 10-day sum",
            "risk_multiplier_when_both_confirm": 1.2,
            "risk_multiplier_otherwise": 1.0,
            "entry_context_scope": "flat, reverse, rollover reopen, regular add, donchian add, post-quality add",
        },
        "promotion_comparisons": sorted(promotion_comparisons),
        "volume_contract_gates": contract_gates,
        "full_period_gates": full_rows,
        "escalate_to_multicycle": escalate,
        "decision": (
            "run_double_volume_multicycle"
            if escalate
            else "stop_double_volume_boost_after_full_period"
        ),
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _validate_summary(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    expected = {str(arm["arm"]) for arm in ARMS}
    if len(summary) != len(ARMS) or set(summary["experiment_arm"].astype(str)) != expected:
        raise RuntimeError("stage010_arm_identity_mismatch")
    critical = [
        *METRICS,
        "account_survival_pass",
        "broker10_100_pass",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
    ]
    numeric = summary[critical].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy(dtype="float64")).all():
        raise RuntimeError("stage010_critical_metric_invalid")
    curve_equity = pd.to_numeric(curve.get("account_equity"), errors="coerce")
    if curve.empty or not np.isfinite(curve_equity.to_numpy(dtype="float64")).all():
        raise RuntimeError("stage010_curve_invalid")
    if set(curve["experiment_arm"].astype(str)) != expected:
        raise RuntimeError("stage010_curve_arm_identity_mismatch")


def main() -> None:
    metadata = s513._metadata()
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    full_h_frames: dict[str, pd.DataFrame] = {}
    for arm in ARMS:
        print(f"[stage010] arm={arm['arm']}", flush=True)
        summary, curve, frames = _run_arm(metadata, arm)
        summaries.append(summary)
        curves.append(curve)
        if str(arm["arm"]) == "H":
            full_h_frames = {key: value.copy() for key, value in frames.items()}

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    _validate_summary(summary, curve)
    comparison = _comparison(summary)
    entry_risk = full_h_frames.get("entry_risk", pd.DataFrame()).copy()
    trades = full_h_frames.get("trades", pd.DataFrame()).copy()
    trade_events = full_h_frames.get("trade_events", pd.DataFrame()).copy()
    volume_contract = _volume_contract_summary(entry_risk)
    decision = _decision(comparison, volume_contract)
    s2._publish_outputs_atomically(
        OUTPUT_DIR,
        {
            SUMMARY_PATH.name: summary,
            COMPARISON_PATH.name: comparison,
            CURVE_PATH.name: curve,
            ENTRY_RISK_PATH.name: entry_risk,
            TRADES_PATH.name: trades,
            TRADE_EVENTS_PATH.name: trade_events,
            VOLUME_CONTRACT_PATH.name: volume_contract,
        },
        decision,
        decision_filename=DECISION_PATH.name,
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
