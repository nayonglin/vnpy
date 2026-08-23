from __future__ import annotations

from datetime import datetime
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from uuid import uuid4

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import stage001_rollover_shape_same_volume_ac as s1
import stage007_directional_boost_multicycle_acd as s7
import stage010_directional_double_volume_full_period_acfh as s10
import stage013_long_only_asymmetric_double_volume_multicycle_achij as s13


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage014"

SUMMARY_PATH = OUTPUT_DIR / "stage014_achjk_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage014_achjk_comparison.csv"
CURVE_PATH = OUTPUT_DIR / "stage014_achjk_curve.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / "stage014_full_k_entry_risk.csv"
TRADES_PATH = OUTPUT_DIR / "stage014_full_k_trades.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / "stage014_full_k_trade_events.csv"
RISK_CONTRACT_PATH = OUTPUT_DIR / "stage014_full_k_risk_split_contract_summary.csv"
DECISION_PATH = OUTPUT_DIR / "stage014_decision.json"
CHART_PATH = OUTPUT_DIR / "stage014_full_period_equity_achjk.png"

ARMS: tuple[dict[str, Any], ...] = (
    {"arm": "A", "profile": "stage014_A_official_live_c9_15w", "label": "A: Official C9/150k", "plot_label": "A Official", "color": "#2563eb", "volume_ratio_threshold": 1.0, "confirmation_multiplier": 1.0, "nonconfirmation_multiplier": 1.0, "long_only": False},
    {"arm": "C", "profile": "stage014_C_rollover_continuation", "label": "C: Official + rollover continuation", "plot_label": "C Rollover", "color": "#dc2626", "volume_ratio_threshold": 1.0, "confirmation_multiplier": 1.0, "nonconfirmation_multiplier": 1.0, "long_only": False},
    {"arm": "H", "profile": "stage014_H_double_volume_hit_12", "label": "H: C + both-confirmed x1.2 otherwise x1.0", "plot_label": "H Hit 1.2 / Miss 1.0", "color": "#ea580c", "volume_ratio_threshold": 2.0, "confirmation_multiplier": 1.2, "nonconfirmation_multiplier": 1.0, "long_only": False},
    {"arm": "J", "profile": "stage014_J_long_hit_15_miss_05_short_10", "label": "J: C + long hit x1.5/miss x0.5; short x1.0", "plot_label": "J Long 1.5 / 0.5; Short 1.0", "color": "#7c3aed", "volume_ratio_threshold": 2.0, "confirmation_multiplier": 1.5, "nonconfirmation_multiplier": 0.5, "long_only": True},
    {"arm": "K", "profile": "stage014_K_long_hit_15_otherwise_10", "label": "K: C + long hit x1.5 otherwise x1.0; short x1.0", "plot_label": "K Long Hit 1.5 / Otherwise 1.0", "color": "#0891b2", "volume_ratio_threshold": 2.0, "confirmation_multiplier": 1.5, "nonconfirmation_multiplier": 1.0, "long_only": True},
)

REUSED_ARMS = {"A", "C", "H", "J"}
NEW_RUN_ARMS = {"K"}
REUSED_SOURCE_STAGE = "Stage013"
REUSED_SOURCE_COMMIT = "9cc2391b9"

COMPARISONS: tuple[tuple[str, str, str], ...] = (
    ("A_vs_C", "A", "C"),
    ("A_vs_H", "A", "H"),
    ("C_vs_H", "C", "H"),
    ("A_vs_J", "A", "J"),
    ("C_vs_J", "C", "J"),
    ("H_vs_J", "H", "J"),
    ("A_vs_K", "A", "K"),
    ("C_vs_K", "C", "K"),
    ("H_vs_K", "H", "K"),
    ("J_vs_K", "J", "K"),
)

METRICS = s10.METRICS


def _load_reused_arms() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(s13.SUMMARY_PATH)
    curve = pd.read_csv(s13.CURVE_PATH)
    summary = summary[
        summary["window_id"].astype(str).eq("full_2018_2026")
        & summary["promotion_arm"].astype(str).isin(REUSED_ARMS)
    ].copy()
    curve = curve[
        curve["window_id"].astype(str).eq("full_2018_2026")
        & curve["promotion_arm"].astype(str).isin(REUSED_ARMS)
    ].copy()
    summary["experiment_arm"] = summary["promotion_arm"].astype(str)
    curve["experiment_arm"] = curve["promotion_arm"].astype(str)
    if len(summary) != len(REUSED_ARMS) or set(summary["experiment_arm"]) != REUSED_ARMS:
        raise RuntimeError("stage014_reused_summary_identity_mismatch")
    if set(curve["experiment_arm"]) != REUSED_ARMS:
        raise RuntimeError("stage014_reused_curve_identity_mismatch")
    counts = curve.groupby("experiment_arm").size().to_dict()
    if len(set(counts.values())) != 1:
        raise RuntimeError("stage014_reused_curve_length_mismatch")
    return summary, curve


def _run_k_arm(metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    arm = next(item for item in ARMS if item["arm"] == "K")
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
                "enable_directional_30d_risk_boost": True,
                "directional_30d_risk_boost_lookback": 30,
                "directional_30d_risk_boost_multiplier": 1.5,
                "directional_30d_risk_nonconfirmation_multiplier": 1.0,
                "directional_30d_risk_adjust_long_only": True,
                "directional_30d_risk_boost_require_volume_expansion": True,
                "directional_30d_volume_recent_days": 10,
                "directional_30d_volume_prior_days": 10,
                "directional_30d_volume_ratio_threshold": 2.0,
            }
        )
        return overrides

    try:
        s1._overrides = experiment_overrides
        summary, curve, frames = s1._run_arm(
            profile_name=str(arm["profile"]),
            candidate=True,
            metadata=metadata,
            volume_policy="shrink_to_allowed",
            history_mode="backwards_ratio_continuous",
            label=str(arm["label"]),
        )
    finally:
        s1._overrides = original_overrides

    summary = summary.copy()
    summary["experiment_arm"] = "K"
    curve = curve.copy()
    curve["experiment_arm"] = "K"
    return summary, curve, frames


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    original = s10.COMPARISONS
    try:
        s10.COMPARISONS = COMPARISONS
        return s10._comparison(summary)
    finally:
        s10.COMPARISONS = original


def _risk_split_contract_summary(entry_risk: pd.DataFrame) -> pd.DataFrame:
    required = {
        "direction", "entry_context", "directional_30d_risk_boost_enabled",
        "directional_30d_volume_confirmation_enabled", "directional_30d_risk_adjust_long_only",
        "directional_30d_risk_boost_aligned", "directional_30d_volume_ratio_threshold",
        "directional_30d_recent_volume_sum", "directional_30d_prior_volume_sum",
        "directional_30d_risk_boost_applied", "directional_30d_risk_nonconfirmation_multiplier",
        "directional_30d_risk_boost_multiplier", "directional_30d_risk_boost_reason",
        "risk_amount_before_directional_30d_boost", "target_risk_amount",
    }
    empty = {
        "group_type": "total", "group_value": "all", "diagnostic_intent_count": 0,
        "long_confirmation_count": 0, "long_nonconfirmation_count": 0,
        "short_bypass_count": 0, "threshold_contract_pass": 0, "risk_amount_contract_pass": 0,
    }
    if entry_risk.empty or not required.issubset(entry_risk.columns):
        return pd.DataFrame([empty])

    frame = entry_risk.copy()
    numeric_columns = sorted(required - {"direction", "entry_context", "directional_30d_risk_boost_reason"})
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[
        frame["directional_30d_risk_boost_enabled"].eq(1)
        & frame["directional_30d_volume_confirmation_enabled"].eq(1)
    ].copy()

    def summarize(group_type: str, group_value: str, group: pd.DataFrame) -> dict[str, Any]:
        direction = group["direction"].astype(str).str.lower()
        long_mask = direction.eq("long")
        short_mask = direction.eq("short")
        aligned = group["directional_30d_risk_boost_aligned"].fillna(0).astype(int).eq(1)
        volume_confirmed = (
            group["directional_30d_prior_volume_sum"].gt(0)
            & group["directional_30d_recent_volume_sum"].gt(
                group["directional_30d_prior_volume_sum"]
                * group["directional_30d_volume_ratio_threshold"]
            )
        )
        long_confirmation = long_mask & aligned & volume_confirmed
        long_nonconfirmation = long_mask & ~long_confirmation
        short_bypass = (
            short_mask
            & group["directional_30d_risk_boost_reason"].astype(str).eq("direction_excluded")
            & group["directional_30d_risk_boost_aligned"].isna()
            & group["directional_30d_recent_volume_sum"].isna()
            & group["directional_30d_prior_volume_sum"].isna()
        )
        expected_multiplier = np.where(long_confirmation, 1.5, 1.0)
        expected_risk = group["risk_amount_before_directional_30d_boost"] * expected_multiplier
        applied = group["directional_30d_risk_boost_applied"].fillna(0).astype(int).eq(1)
        threshold_ok = (
            group["directional_30d_risk_adjust_long_only"].eq(1)
            & np.isclose(group["directional_30d_volume_ratio_threshold"], 2.0, rtol=0.0, atol=1e-12)
            & np.isclose(group["directional_30d_risk_nonconfirmation_multiplier"], 1.0, rtol=0.0, atol=1e-12)
            & (long_mask | short_bypass)
        )
        risk_ok = (
            applied.eq(long_confirmation)
            & group["risk_amount_before_directional_30d_boost"].notna()
            & group["target_risk_amount"].notna()
            & np.isclose(group["directional_30d_risk_boost_multiplier"], expected_multiplier, rtol=0.0, atol=1e-12)
            & np.isclose(group["target_risk_amount"], expected_risk, rtol=1e-12, atol=1e-9)
        )
        return {
            "group_type": group_type,
            "group_value": group_value,
            "diagnostic_intent_count": int(len(group)),
            "long_confirmation_count": int(long_confirmation.sum()),
            "long_nonconfirmation_count": int(long_nonconfirmation.sum()),
            "short_bypass_count": int(short_bypass.sum()),
            "threshold_contract_pass": int(len(group) > 0 and bool(np.asarray(threshold_ok).all())),
            "risk_amount_contract_pass": int(len(group) > 0 and bool(np.asarray(risk_ok).all())),
        }

    rows = [summarize("total", "all", frame)]
    for column, group_type in (("direction", "direction"), ("entry_context", "entry_context")):
        for value, group in frame.groupby(column, sort=True, dropna=False):
            rows.append(summarize(group_type, str(value), group))
    return pd.DataFrame(rows)


def _decision(comparison: pd.DataFrame, risk_contract: pd.DataFrame) -> dict[str, Any]:
    full_rows: list[dict[str, Any]] = []
    for comparison_name, _, _ in COMPARISONS:
        row = comparison[comparison["comparison"].eq(comparison_name)].iloc[0]
        gates = s7._full_period_gates(row)
        full_rows.append({"comparison": comparison_name, "gates": gates, "pass": bool(all(gates.values()))})
    total = risk_contract[risk_contract["group_type"].astype(str).eq("total")].iloc[0]
    contract_gates = {
        "threshold_contract_pass": bool(int(total["threshold_contract_pass"]) == 1),
        "risk_amount_contract_pass": bool(int(total["risk_amount_contract_pass"]) == 1),
        "long_confirmation_present": bool(int(total["long_confirmation_count"]) > 0),
        "long_nonconfirmation_present": bool(int(total["long_nonconfirmation_count"]) > 0),
        "short_bypass_present": bool(int(total["short_bypass_count"]) > 0),
    }
    promotion_comparisons = {"A_vs_K", "C_vs_K"}
    promotion_rows = [row for row in full_rows if row["comparison"] in promotion_comparisons]
    escalate = bool(all(contract_gates.values()) and all(row["pass"] for row in promotion_rows))
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage014",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "period": {"start": str(s1.START.date()), "end": str(s1.END.date())},
        "arms": {str(arm["arm"]): str(arm["profile"]) for arm in ARMS},
        "run_provenance": {
            "candidate_freeze_commit": s13._git_head(),
            "reused_source_stage": REUSED_SOURCE_STAGE,
            "reused_source_commit": REUSED_SOURCE_COMMIT,
            "reused_arms": sorted(REUSED_ARMS),
            "new_arms": sorted(NEW_RUN_ARMS),
            "new_independent_run_count": 1,
        },
        "K_rule": {
            "price_direction_lookback_days": 30,
            "recent_volume_window": "T-9 through T, includes signal day",
            "prior_volume_window": "T-19 through T-10",
            "volume_condition": "recent 10-day sum strictly greater than 2.0 times prior 10-day sum",
            "long_risk_multiplier_when_both_confirm": 1.5,
            "long_risk_multiplier_otherwise": 1.0,
            "short_risk_multiplier": 1.0,
            "entry_context_scope": "flat, reverse, rollover reopen, regular add, donchian add, post-quality add",
        },
        "promotion_comparisons": sorted(promotion_comparisons),
        "risk_split_contract_gates": contract_gates,
        "full_period_gates": full_rows,
        "escalate_to_multicycle": escalate,
        "decision": "run_long_only_confirmation_only_multicycle" if escalate else "stop_long_only_confirmation_only_after_full_period",
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _validate_summary(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    expected = {str(arm["arm"]) for arm in ARMS}
    if len(summary) != len(ARMS) or set(summary["experiment_arm"].astype(str)) != expected:
        raise RuntimeError("stage014_arm_identity_mismatch")
    critical = [*METRICS, "account_survival_pass", "broker10_100_pass", "max_broker10_margin_to_equity_pct", "days_over_100pct"]
    numeric = summary[critical].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy(dtype="float64")).all():
        raise RuntimeError("stage014_critical_metric_invalid")
    curve_equity = pd.to_numeric(curve.get("account_equity"), errors="coerce")
    if curve.empty or not np.isfinite(curve_equity.to_numpy(dtype="float64")).all():
        raise RuntimeError("stage014_curve_invalid")
    if set(curve["experiment_arm"].astype(str)) != expected:
        raise RuntimeError("stage014_curve_arm_identity_mismatch")
    counts = curve.groupby("experiment_arm").size().to_dict()
    if len(set(counts.values())) != 1:
        raise RuntimeError("stage014_curve_length_mismatch")


def _plot_full(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        frame = curve[curve["experiment_arm"].astype(str).eq(str(arm["arm"]))].sort_values("date")
        ax.plot(pd.to_datetime(frame["date"]), frame["account_equity"] / 10_000.0, color=str(arm["color"]), lw=1.45, label=str(arm["plot_label"]))
    ax.set_title("Stage014 Full-Period Equity: K Long Hit 1.5 / Otherwise 1.0")
    ax.set_ylabel("Equity (10k CNY)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _publish_atomically(frames: dict[str, pd.DataFrame], decision: dict[str, Any], chart: bytes) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary_dir = Path(tempfile.mkdtemp(prefix=".stage014.tmp-", dir=OUTPUT_DIR.parent))
    backup_dir = OUTPUT_DIR.with_name(f".stage014.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary_dir / filename, index=False, encoding="utf-8-sig")
        (temporary_dir / DECISION_PATH.name).write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (temporary_dir / CHART_PATH.name).write_bytes(chart)
        if OUTPUT_DIR.exists():
            os.replace(OUTPUT_DIR, backup_dir)
        try:
            os.replace(temporary_dir, OUTPUT_DIR)
        except Exception:
            if backup_dir.exists() and not OUTPUT_DIR.exists():
                os.replace(backup_dir, OUTPUT_DIR)
            raise
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
    finally:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir, ignore_errors=True)


def main() -> None:
    metadata = s513._metadata()
    reused_summary, reused_curve = _load_reused_arms()
    k_summary, k_curve, frames = _run_k_arm(metadata)
    summary = pd.concat([reused_summary, k_summary], ignore_index=True, sort=False)
    curve = pd.concat([reused_curve, k_curve], ignore_index=True, sort=False)
    _validate_summary(summary, curve)
    comparison = _comparison(summary)
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    trades = frames.get("trades", pd.DataFrame()).copy()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    risk_contract = _risk_split_contract_summary(entry_risk)
    decision = _decision(comparison, risk_contract)
    _publish_atomically(
        {
            SUMMARY_PATH.name: summary,
            COMPARISON_PATH.name: comparison,
            CURVE_PATH.name: curve,
            ENTRY_RISK_PATH.name: entry_risk,
            TRADES_PATH.name: trades,
            TRADE_EVENTS_PATH.name: trade_events,
            RISK_CONTRACT_PATH.name: risk_contract,
        },
        decision,
        _plot_full(curve),
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
