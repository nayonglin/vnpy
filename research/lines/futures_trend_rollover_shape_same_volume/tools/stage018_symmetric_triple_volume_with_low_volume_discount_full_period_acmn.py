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
import stage017_long_triple_volume_with_low_volume_discount_full_period_aclm as s17


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage018"

SUMMARY_PATH = OUTPUT_DIR / "stage018_acmn_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage018_acmn_comparison.csv"
CURVE_PATH = OUTPUT_DIR / "stage018_acmn_curve.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / "stage018_full_n_entry_risk.csv"
TRADES_PATH = OUTPUT_DIR / "stage018_full_n_trades.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / "stage018_full_n_trade_events.csv"
RISK_CONTRACT_PATH = OUTPUT_DIR / "stage018_full_n_risk_split_contract_summary.csv"
DECISION_PATH = OUTPUT_DIR / "stage018_decision.json"
CHART_PATH = OUTPUT_DIR / "stage018_full_period_equity_acmn.png"

ARMS: tuple[dict[str, Any], ...] = (
    {"arm": "A", "profile": "stage018_A_official_live_c9_15w", "label": "A: Official C9/150k", "plot_label": "A Official", "color": "#2563eb", "high_volume_ratio_threshold": 1.0, "high_volume_multiplier": 1.0, "low_volume_ratio_threshold": 0.0, "low_volume_multiplier": 1.0, "long_only": False},
    {"arm": "C", "profile": "stage018_C_rollover_continuation", "label": "C: Official + rollover continuation", "plot_label": "C Rollover", "color": "#dc2626", "high_volume_ratio_threshold": 1.0, "high_volume_multiplier": 1.0, "low_volume_ratio_threshold": 0.0, "low_volume_multiplier": 1.0, "long_only": False},
    {"arm": "M", "profile": "stage018_M_long_triple_volume_hit_15_low_half_05", "label": "M: Long >3x x1.5, <0.5x x0.5; short x1.0", "plot_label": "M Long Only", "color": "#7c3aed", "high_volume_ratio_threshold": 3.0, "high_volume_multiplier": 1.5, "low_volume_ratio_threshold": 0.5, "low_volume_multiplier": 0.5, "long_only": True},
    {"arm": "N", "profile": "stage018_N_symmetric_triple_volume_hit_15_low_half_05", "label": "N: Both directions >3x x1.5, <0.5x x0.5", "plot_label": "N Long + Short", "color": "#f59e0b", "high_volume_ratio_threshold": 3.0, "high_volume_multiplier": 1.5, "low_volume_ratio_threshold": 0.5, "low_volume_multiplier": 0.5, "long_only": False},
)

REUSED_ARMS = {"A", "C", "M"}
NEW_RUN_ARMS = {"N"}
REUSED_SOURCE_STAGE = "Stage017"
REUSED_SOURCE_COMMIT = "89c042d9e82900580ae8046dd399267436a4c15e"

COMPARISONS: tuple[tuple[str, str, str], ...] = (
    ("A_vs_C", "A", "C"),
    ("A_vs_M", "A", "M"),
    ("C_vs_M", "C", "M"),
    ("A_vs_N", "A", "N"),
    ("C_vs_N", "C", "N"),
    ("M_vs_N", "M", "N"),
)

METRICS = s17.METRICS


def _load_reused_arms() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(s17.SUMMARY_PATH)
    curve = pd.read_csv(s17.CURVE_PATH)
    summary = summary[summary["experiment_arm"].astype(str).isin(REUSED_ARMS)].copy()
    curve = curve[curve["experiment_arm"].astype(str).isin(REUSED_ARMS)].copy()
    if len(summary) != len(REUSED_ARMS) or set(summary["experiment_arm"].astype(str)) != REUSED_ARMS:
        raise RuntimeError("stage018_reused_summary_identity_mismatch")
    if set(curve["experiment_arm"].astype(str)) != REUSED_ARMS:
        raise RuntimeError("stage018_reused_curve_identity_mismatch")
    counts = curve.groupby("experiment_arm").size().to_dict()
    if len(set(counts.values())) != 1:
        raise RuntimeError("stage018_reused_curve_length_mismatch")
    return summary, curve


def _run_n_arm(metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    arm = next(item for item in ARMS if item["arm"] == "N")
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
                "directional_30d_risk_adjust_long_only": False,
                "directional_30d_risk_boost_require_volume_expansion": True,
                "directional_30d_volume_recent_days": 10,
                "directional_30d_volume_prior_days": 10,
                "directional_30d_volume_ratio_threshold": 3.0,
                "enable_directional_30d_low_volume_risk_discount": True,
                "directional_30d_low_volume_ratio_threshold": 0.5,
                "directional_30d_low_volume_risk_multiplier": 0.5,
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
    summary["experiment_arm"] = "N"
    curve = curve.copy()
    curve["experiment_arm"] = "N"
    return summary, curve, frames


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    original = s17.s15.s10.COMPARISONS
    try:
        s17.s15.s10.COMPARISONS = COMPARISONS
        return s17.s15.s10._comparison(summary)
    finally:
        s17.s15.s10.COMPARISONS = original


def _risk_split_contract_summary(entry_risk: pd.DataFrame) -> pd.DataFrame:
    required = {
        "direction", "entry_context", "directional_30d_risk_boost_enabled",
        "directional_30d_volume_confirmation_enabled", "directional_30d_risk_adjust_long_only",
        "directional_30d_risk_boost_aligned", "directional_30d_volume_ratio_threshold",
        "directional_30d_low_volume_discount_enabled", "directional_30d_low_volume_ratio_threshold",
        "directional_30d_low_volume_risk_multiplier", "directional_30d_recent_volume_sum",
        "directional_30d_prior_volume_sum", "directional_30d_risk_boost_applied",
        "directional_30d_low_volume_discount_applied", "directional_30d_risk_nonconfirmation_multiplier",
        "directional_30d_risk_boost_multiplier", "directional_30d_risk_boost_reason",
        "risk_amount_before_directional_30d_boost", "target_risk_amount",
    }
    empty = {
        "group_type": "total", "group_value": "all", "diagnostic_intent_count": 0,
        "long_high_volume_count": 0, "long_low_volume_count": 0, "long_base_volume_count": 0,
        "short_high_volume_count": 0, "short_low_volume_count": 0, "short_base_volume_count": 0,
        "threshold_contract_pass": 0, "risk_amount_contract_pass": 0,
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
        valid_volume = group["directional_30d_prior_volume_sum"].gt(0) & group["directional_30d_recent_volume_sum"].gt(0)
        high_volume = valid_volume & group["directional_30d_recent_volume_sum"].gt(group["directional_30d_prior_volume_sum"] * 3.0)
        low_volume = valid_volume & group["directional_30d_recent_volume_sum"].lt(group["directional_30d_prior_volume_sum"] * 0.5)
        high = aligned & high_volume & (long_mask | short_mask)
        low = low_volume & (long_mask | short_mask)
        long_high = long_mask & high
        long_low = long_mask & low
        long_base = long_mask & ~high & ~low
        short_high = short_mask & high
        short_low = short_mask & low
        short_base = short_mask & ~high & ~low
        expected_multiplier = np.select([low, high], [0.5, 1.5], default=1.0)
        expected_risk = group["risk_amount_before_directional_30d_boost"] * expected_multiplier
        boost_applied = group["directional_30d_risk_boost_applied"].fillna(0).astype(int).eq(1)
        discount_applied = group["directional_30d_low_volume_discount_applied"].fillna(0).astype(int).eq(1)
        threshold_ok = (
            group["directional_30d_risk_adjust_long_only"].eq(0)
            & group["directional_30d_low_volume_discount_enabled"].eq(1)
            & np.isclose(group["directional_30d_volume_ratio_threshold"], 3.0, rtol=0.0, atol=1e-12)
            & np.isclose(group["directional_30d_low_volume_ratio_threshold"], 0.5, rtol=0.0, atol=1e-12)
            & np.isclose(group["directional_30d_low_volume_risk_multiplier"], 0.5, rtol=0.0, atol=1e-12)
            & np.isclose(group["directional_30d_risk_nonconfirmation_multiplier"], 1.0, rtol=0.0, atol=1e-12)
            & (long_mask | short_mask)
        )
        risk_ok = (
            boost_applied.eq(high)
            & discount_applied.eq(low)
            & group["risk_amount_before_directional_30d_boost"].notna()
            & group["target_risk_amount"].notna()
            & np.isclose(group["directional_30d_risk_boost_multiplier"], expected_multiplier, rtol=0.0, atol=1e-12)
            & np.isclose(group["target_risk_amount"], expected_risk, rtol=1e-12, atol=1e-9)
        )
        return {
            "group_type": group_type,
            "group_value": group_value,
            "diagnostic_intent_count": int(len(group)),
            "long_high_volume_count": int(long_high.sum()),
            "long_low_volume_count": int(long_low.sum()),
            "long_base_volume_count": int(long_base.sum()),
            "short_high_volume_count": int(short_high.sum()),
            "short_low_volume_count": int(short_low.sum()),
            "short_base_volume_count": int(short_base.sum()),
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
        gates = s17.s15.s7._full_period_gates(row)
        full_rows.append({"comparison": comparison_name, "gates": gates, "pass": bool(all(gates.values()))})
    total = risk_contract[risk_contract["group_type"].astype(str).eq("total")].iloc[0]
    contract_gates = {
        "threshold_contract_pass": bool(int(total["threshold_contract_pass"]) == 1),
        "risk_amount_contract_pass": bool(int(total["risk_amount_contract_pass"]) == 1),
        "long_high_volume_present": bool(int(total["long_high_volume_count"]) > 0),
        "long_low_volume_present": bool(int(total["long_low_volume_count"]) > 0),
        "long_base_volume_present": bool(int(total["long_base_volume_count"]) > 0),
        "short_high_volume_present": bool(int(total["short_high_volume_count"]) > 0),
        "short_low_volume_present": bool(int(total["short_low_volume_count"]) > 0),
        "short_base_volume_present": bool(int(total["short_base_volume_count"]) > 0),
    }
    promotion_comparisons = {"A_vs_N", "C_vs_N"}
    promotion_rows = [row for row in full_rows if row["comparison"] in promotion_comparisons]
    escalate = bool(all(contract_gates.values()) and all(row["pass"] for row in promotion_rows))
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage018",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "period": {"start": str(s1.START.date()), "end": str(s1.END.date())},
        "arms": {str(arm["arm"]): str(arm["profile"]) for arm in ARMS},
        "run_provenance": {
            "candidate_freeze_commit": s17.s15.s13._git_head(),
            "reused_source_stage": REUSED_SOURCE_STAGE,
            "reused_source_commit": REUSED_SOURCE_COMMIT,
            "reused_arms": sorted(REUSED_ARMS),
            "new_arms": sorted(NEW_RUN_ARMS),
            "new_independent_run_count": 1,
        },
        "N_rule": {
            "price_direction_lookback_days_for_high_volume_boost": 30,
            "recent_volume_window": "T-9 through T, includes signal day",
            "prior_volume_window": "T-19 through T-10",
            "high_volume_condition": "direction aligned and recent sum strictly greater than 3.0 times prior sum",
            "high_volume_risk_multiplier": 1.5,
            "low_volume_condition": "recent sum strictly less than 0.5 times prior sum, independent of 30d direction alignment",
            "low_volume_risk_multiplier": 0.5,
            "other_risk_multiplier": 1.0,
            "directions": "long and short symmetric",
            "entry_context_scope": "flat, reverse, rollover reopen, regular add, donchian add, post-quality add",
        },
        "promotion_comparisons": sorted(promotion_comparisons),
        "risk_split_contract_gates": contract_gates,
        "full_period_gates": full_rows,
        "escalate_to_multicycle": escalate,
        "decision": "run_symmetric_triple_volume_with_low_volume_discount_multicycle" if escalate else "stop_symmetric_triple_volume_with_low_volume_discount_after_full_period",
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _validate_summary(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    expected = {str(arm["arm"]) for arm in ARMS}
    if len(summary) != len(ARMS) or set(summary["experiment_arm"].astype(str)) != expected:
        raise RuntimeError("stage018_arm_identity_mismatch")
    critical = [*METRICS, "account_survival_pass", "broker10_100_pass", "max_broker10_margin_to_equity_pct", "days_over_100pct"]
    numeric = summary[critical].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy(dtype="float64")).all():
        raise RuntimeError("stage018_critical_metric_invalid")
    curve_equity = pd.to_numeric(curve.get("account_equity"), errors="coerce")
    if curve.empty or not np.isfinite(curve_equity.to_numpy(dtype="float64")).all():
        raise RuntimeError("stage018_curve_invalid")
    if set(curve["experiment_arm"].astype(str)) != expected:
        raise RuntimeError("stage018_curve_arm_identity_mismatch")
    counts = curve.groupby("experiment_arm").size().to_dict()
    if len(set(counts.values())) != 1:
        raise RuntimeError("stage018_curve_length_mismatch")


def _plot_full(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        frame = curve[curve["experiment_arm"].astype(str).eq(str(arm["arm"]))].sort_values("date")
        ax.plot(pd.to_datetime(frame["date"]), frame["account_equity"] / 10_000.0, color=str(arm["color"]), lw=1.45, label=str(arm["plot_label"]))
    ax.set_title("Stage018 Full-Period Equity: Symmetric >3x 1.5 / <0.5x 0.5")
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
    temporary_dir = Path(tempfile.mkdtemp(prefix=".stage018.tmp-", dir=OUTPUT_DIR.parent))
    backup_dir = OUTPUT_DIR.with_name(f".stage018.backup-{uuid4().hex}")
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
    n_summary, n_curve, frames = _run_n_arm(metadata)
    summary = pd.concat([reused_summary, n_summary], ignore_index=True, sort=False)
    curve = pd.concat([reused_curve, n_curve], ignore_index=True, sort=False)
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
