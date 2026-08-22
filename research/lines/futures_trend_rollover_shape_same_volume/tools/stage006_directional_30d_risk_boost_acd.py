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


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage006"

BASE_PROFILE = "stage006_A_official_live_c9_15w"
ROLLOVER_PROFILE = "stage006_C_rollover_continuation"
BOOST_PROFILE = "stage006_D_rollover_plus_directional_30d_risk_1p2"

SUMMARY_PATH = OUTPUT_DIR / "stage006_acd_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage006_acd_comparison.csv"
CURVE_PATH = OUTPUT_DIR / "stage006_acd_curve.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / "stage006_entry_risk.csv"
BOOST_SUMMARY_PATH = OUTPUT_DIR / "stage006_boost_contract_summary.csv"
DECISION_PATH = OUTPUT_DIR / "stage006_decision.json"

ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm": "A",
        "profile": BASE_PROFILE,
        "rollover_candidate": False,
        "risk_boost": False,
        "label": "A: 当前正式 C9/15万",
    },
    {
        "arm": "C",
        "profile": ROLLOVER_PROFILE,
        "rollover_candidate": True,
        "risk_boost": False,
        "label": "C: 正式基线 + 换月连续历史形态续仓",
    },
    {
        "arm": "D",
        "profile": BOOST_PROFILE,
        "rollover_candidate": True,
        "risk_boost": True,
        "label": "D: C + 所有开仓30日方向一致时风险金额乘1.2",
    },
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


def _run_arm(metadata: dict[str, Any], arm: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
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


def _boost_contract_summary(entry_risk: pd.DataFrame) -> pd.DataFrame:
    required = {
        "profile",
        "direction",
        "entry_context",
        "directional_30d_risk_boost_enabled",
        "directional_30d_risk_boost_aligned",
        "directional_30d_risk_boost_multiplier",
        "risk_amount_before_directional_30d_boost",
        "target_risk_amount",
    }
    if entry_risk.empty or not required.issubset(entry_risk.columns):
        return pd.DataFrame(
            [
                {
                    "group_type": "total",
                    "group_value": "all",
                    "entry_count": 0,
                    "aligned_count": 0,
                    "unaligned_count": 0,
                    "risk_amount_contract_pass": 0,
                }
            ]
        )

    boost = entry_risk[entry_risk["profile"].astype(str).eq(BOOST_PROFILE)].copy()
    boost = boost[
        pd.to_numeric(boost["directional_30d_risk_boost_enabled"], errors="coerce")
        .fillna(0)
        .astype(int)
        .eq(1)
    ].copy()
    for column in [
        "directional_30d_risk_boost_aligned",
        "directional_30d_risk_boost_multiplier",
        "risk_amount_before_directional_30d_boost",
        "target_risk_amount",
    ]:
        boost[column] = pd.to_numeric(boost[column], errors="coerce")

    def summarize(group_type: str, group_value: str, frame: pd.DataFrame) -> dict[str, Any]:
        aligned = frame["directional_30d_risk_boost_aligned"].fillna(0).astype(int).eq(1)
        expected_multiplier = np.where(aligned, 1.2, 1.0)
        expected_risk = frame["risk_amount_before_directional_30d_boost"] * expected_multiplier
        valid = (
            frame["risk_amount_before_directional_30d_boost"].notna()
            & frame["target_risk_amount"].notna()
            & np.isclose(
                frame["directional_30d_risk_boost_multiplier"].to_numpy(dtype="float64"),
                expected_multiplier,
                rtol=0.0,
                atol=1e-12,
            )
            & np.isclose(
                frame["target_risk_amount"].to_numpy(dtype="float64"),
                expected_risk.to_numpy(dtype="float64"),
                rtol=1e-12,
                atol=1e-9,
            )
        )
        return {
            "group_type": group_type,
            "group_value": group_value,
            "entry_count": int(len(frame)),
            "aligned_count": int(aligned.sum()),
            "unaligned_count": int((~aligned).sum()),
            "risk_amount_contract_pass": int(len(frame) > 0 and bool(np.asarray(valid).all())),
        }

    rows = [summarize("total", "all", boost)]
    for column, group_type in [("direction", "direction"), ("entry_context", "entry_context")]:
        for value, group in boost.groupby(column, sort=True, dropna=False):
            rows.append(summarize(group_type, str(value), group))
    return pd.DataFrame(rows)


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    by_arm = summary.set_index("experiment_arm")
    rows: list[dict[str, Any]] = []
    for comparison_name, left_arm, right_arm in [
        ("A_vs_C", "A", "C"),
        ("C_vs_D", "C", "D"),
        ("A_vs_D", "A", "D"),
    ]:
        left = by_arm.loc[left_arm]
        right = by_arm.loc[right_arm]
        row: dict[str, Any] = {
            "comparison": comparison_name,
            "left_arm": left_arm,
            "right_arm": right_arm,
        }
        for metric in METRICS:
            left_value = float(left[metric])
            right_value = float(right[metric])
            row[f"left_{metric}"] = left_value
            row[f"right_{metric}"] = right_value
            row[f"delta_{metric}"] = right_value - left_value
        rows.append(row)
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, boost_summary: pd.DataFrame) -> dict[str, Any]:
    by_arm = summary.set_index("experiment_arm")
    c = by_arm.loc["C"]
    d = by_arm.loc["D"]
    total = boost_summary[boost_summary["group_type"].astype(str).eq("total")].iloc[0]
    gates = {
        "directional_boost_contract_pass": bool(int(total["risk_amount_contract_pass"]) == 1),
        "directional_boost_triggered": bool(int(total["aligned_count"]) > 0),
        "D_return_not_below_C": bool(float(d["total_return_pct"]) >= float(c["total_return_pct"])),
        "D_dd_noninferior_2pp_vs_C": bool(
            max(0.0, float(c["max_dd_pct"]) - float(d["max_dd_pct"])) <= 2.0
        ),
        "D_sharpe_noninferior_002_vs_C": bool(float(d["sharpe"]) >= float(c["sharpe"]) - 0.02),
        "D_slippage_not_above_10pct_vs_C": bool(
            float(d["total_slippage"]) <= float(c["total_slippage"]) * 1.10
        ),
        "D_account_survival": bool(int(d["account_survival_pass"]) == 1),
        "D_broker100_not_worse_than_C": bool(
            int(d["broker10_100_pass"]) >= int(c["broker10_100_pass"])
        ),
    }
    escalate = bool(all(gates.values()))
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage006",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "period": {"start": str(s1.START.date()), "end": str(s1.END.date())},
        "arms": {str(arm["arm"]): str(arm["profile"]) for arm in ARMS},
        "candidate": {
            "enable_rollover_shape_same_volume_reopen": True,
            "rollover_shape_history_mode": "backwards_ratio_continuous",
            "rollover_shape_volume_policy": "shrink_to_allowed",
            "enable_directional_30d_risk_boost": True,
            "directional_30d_risk_boost_lookback": 30,
            "directional_30d_risk_boost_multiplier": 1.2,
            "entry_context_scope": "all risk-budget entry contexts",
        },
        "predeclared_gates": gates,
        "escalate_to_multicycle": escalate,
        "decision": (
            "run_stage007_multicycle"
            if escalate
            else "stop_directional_30d_risk_boost_after_full_period"
        ),
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _validate_summary(summary: pd.DataFrame) -> None:
    if len(summary) != len(ARMS) or set(summary["experiment_arm"].astype(str)) != {"A", "C", "D"}:
        raise RuntimeError("stage006_arm_identity_mismatch")
    critical = [*METRICS, "account_survival_pass", "broker10_100_pass"]
    numeric = summary[critical].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy(dtype="float64")).all():
        raise RuntimeError("stage006_critical_metric_invalid")


def main() -> None:
    metadata = s513._metadata()
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    entry_risks: list[pd.DataFrame] = []
    for arm in ARMS:
        print(f"[stage006] arm={arm['arm']}", flush=True)
        summary, curve, frames = _run_arm(metadata, arm)
        summaries.append(summary)
        curves.append(curve)
        entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
        if not entry_risk.empty:
            entry_risk["profile"] = str(arm["profile"])
            entry_risks.append(entry_risk)

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    entry_risk = pd.concat(entry_risks, ignore_index=True, sort=False)
    _validate_summary(summary)
    comparison = _comparison(summary)
    boost_summary = _boost_contract_summary(entry_risk)
    decision = _decision(summary, boost_summary)
    s2._publish_outputs_atomically(
        OUTPUT_DIR,
        {
            SUMMARY_PATH.name: summary,
            COMPARISON_PATH.name: comparison,
            CURVE_PATH.name: curve,
            ENTRY_RISK_PATH.name: entry_risk,
            BOOST_SUMMARY_PATH.name: boost_summary,
        },
        decision,
        decision_filename=DECISION_PATH.name,
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
