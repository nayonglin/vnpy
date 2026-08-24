from __future__ import annotations

from datetime import datetime
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any
from uuid import uuid4

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import stage001_rollover_shape_same_volume_ac as s1
import stage017_long_triple_volume_with_low_volume_discount_full_period_aclm as s17
import stage018_symmetric_triple_volume_with_low_volume_discount_full_period_acmn as s18
import stage021_p_symmetric_atr_shock_filter_full_period_acpq as s21


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage023"
SUMMARY_PATH = OUTPUT_DIR / "stage023_acqr_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage023_acqr_comparison.csv"
CURVE_PATH = OUTPUT_DIR / "stage023_acqr_curve.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / "stage023_full_r_entry_risk.csv"
TRADES_PATH = OUTPUT_DIR / "stage023_full_r_trades.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / "stage023_full_r_trade_events.csv"
ATR_FILTER_PATH = OUTPUT_DIR / "stage023_full_r_signal_atr_shock.csv"
VOLUME_CONTRACT_PATH = OUTPUT_DIR / "stage023_full_r_volume_risk_contract_summary.csv"
ATR_CONTRACT_PATH = OUTPUT_DIR / "stage023_full_r_atr_filter_contract_summary.csv"
DECISION_PATH = OUTPUT_DIR / "stage023_decision.json"
CHART_PATH = OUTPUT_DIR / "stage023_full_period_equity_acqr.png"

LOW_VOLUME_RATIO_THRESHOLD = 0.8
LOW_VOLUME_RISK_MULTIPLIER = 0.5

ARMS: tuple[dict[str, Any], ...] = (
    {"arm": "A", "profile": "stage023_A_official_live_c9_15w", "label": "A: Official C9/150k", "plot_label": "A Official", "color": "#2563eb"},
    {"arm": "C", "profile": "stage023_C_rollover_continuation", "label": "C: Official + rollover continuation", "plot_label": "C Rollover", "color": "#dc2626"},
    {"arm": "Q", "profile": "stage023_Q_symmetric_atr_low_volume_05", "label": "Q: symmetric ATR + low volume <0.5x risk x0.5", "plot_label": "Q Low <0.5x", "color": "#f59e0b"},
    {
        "arm": "R",
        "profile": "stage023_R_q_low_volume_08_risk_half",
        "label": "R: Q + low volume <0.8x risk x0.5",
        "plot_label": "R Low <0.8x",
        "color": "#16a34a",
        "base_arm": "Q",
        "high_volume_ratio_threshold": 3.0,
        "high_volume_multiplier": 1.5,
        "low_volume_ratio_threshold": LOW_VOLUME_RATIO_THRESHOLD,
        "low_volume_multiplier": LOW_VOLUME_RISK_MULTIPLIER,
        "risk_adjust_long_only": False,
        "atr_filter_directions": ("long", "short"),
    },
)
REUSED_ARMS = {"A", "C", "Q"}
NEW_RUN_ARMS = {"R"}
REUSED_SOURCE_STAGE = "Stage021"
REUSED_SOURCE_COMMIT = "f64cccd77d7f144765a9e983bd3b2108cacfe1d6"
COMPARISONS: tuple[tuple[str, str, str], ...] = (
    ("A_vs_C", "A", "C"),
    ("A_vs_Q", "A", "Q"),
    ("C_vs_Q", "C", "Q"),
    ("A_vs_R", "A", "R"),
    ("C_vs_R", "C", "R"),
    ("Q_vs_R", "Q", "R"),
)
PROMOTION_COMPARISONS = {"A_vs_R", "C_vs_R"}
METRICS = s17.METRICS


def _load_reused_arms() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(s21.SUMMARY_PATH)
    curve = pd.read_csv(s21.CURVE_PATH)
    summary = summary[summary["experiment_arm"].astype(str).isin(REUSED_ARMS)].copy()
    curve = curve[curve["experiment_arm"].astype(str).isin(REUSED_ARMS)].copy()
    if len(summary) != len(REUSED_ARMS) or set(summary["experiment_arm"].astype(str)) != REUSED_ARMS:
        raise RuntimeError("stage023_reused_summary_identity_mismatch")
    if set(curve["experiment_arm"].astype(str)) != REUSED_ARMS:
        raise RuntimeError("stage023_reused_curve_identity_mismatch")
    if len(set(curve.groupby("experiment_arm").size().to_dict().values())) != 1:
        raise RuntimeError("stage023_reused_curve_length_mismatch")
    return summary, curve


def _r_overrides(
    *,
    candidate: bool,
    volume_policy: str = "exact_or_skip",
    history_mode: str = "target_contract_only",
    base_overrides: Any | None = None,
) -> dict[str, Any]:
    overrides = s21._q_overrides(
        candidate=candidate,
        volume_policy=volume_policy,
        history_mode=history_mode,
        base_overrides=base_overrides,
    )
    overrides["directional_30d_low_volume_ratio_threshold"] = LOW_VOLUME_RATIO_THRESHOLD
    overrides["directional_30d_low_volume_risk_multiplier"] = LOW_VOLUME_RISK_MULTIPLIER
    return overrides


def _run_r_arm(metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    arm = next(item for item in ARMS if item["arm"] == "R")
    original_overrides = s1._overrides

    def experiment_overrides(
        *, candidate: bool, volume_policy: str = "exact_or_skip", history_mode: str = "target_contract_only"
    ) -> dict[str, Any]:
        return _r_overrides(
            candidate=candidate,
            volume_policy=volume_policy,
            history_mode=history_mode,
            base_overrides=original_overrides,
        )

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
    summary["experiment_arm"] = "R"
    curve = curve.copy()
    curve["experiment_arm"] = "R"
    return summary, curve, frames


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    original = s17.s15.s10.COMPARISONS
    try:
        s17.s15.s10.COMPARISONS = COMPARISONS
        return s17.s15.s10._comparison(summary)
    finally:
        s17.s15.s10.COMPARISONS = original


def _volume_risk_contract_summary(entry_risk: pd.DataFrame) -> pd.DataFrame:
    required = {
        "direction", "entry_context", "directional_30d_risk_boost_enabled",
        "directional_30d_volume_confirmation_enabled", "directional_30d_risk_adjust_long_only",
        "directional_30d_risk_boost_aligned", "directional_30d_volume_ratio_threshold",
        "directional_30d_low_volume_discount_enabled", "directional_30d_low_volume_ratio_threshold",
        "directional_30d_low_volume_risk_multiplier", "directional_30d_recent_volume_sum",
        "directional_30d_prior_volume_sum", "directional_30d_risk_boost_applied",
        "directional_30d_low_volume_discount_applied", "directional_30d_risk_nonconfirmation_multiplier",
        "directional_30d_risk_boost_multiplier", "risk_amount_before_directional_30d_boost",
        "target_risk_amount",
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
    strings = {"direction", "entry_context"}
    for column in required - strings:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[
        frame["directional_30d_risk_boost_enabled"].eq(1)
        & frame["directional_30d_volume_confirmation_enabled"].eq(1)
    ].copy()

    def summarize(group_type: str, group_value: str, group: pd.DataFrame) -> dict[str, Any]:
        direction = group["direction"].astype(str).str.lower()
        long_mask, short_mask = direction.eq("long"), direction.eq("short")
        valid_direction = long_mask | short_mask
        aligned = group["directional_30d_risk_boost_aligned"].fillna(0).astype(int).eq(1)
        valid_volume = group["directional_30d_prior_volume_sum"].gt(0) & group["directional_30d_recent_volume_sum"].gt(0)
        high_volume = valid_volume & group["directional_30d_recent_volume_sum"].gt(
            group["directional_30d_prior_volume_sum"] * 3.0
        )
        low_volume = valid_volume & group["directional_30d_recent_volume_sum"].lt(
            group["directional_30d_prior_volume_sum"] * LOW_VOLUME_RATIO_THRESHOLD
        )
        high = valid_direction & aligned & high_volume
        low = valid_direction & low_volume
        expected_multiplier = np.select([low, high], [LOW_VOLUME_RISK_MULTIPLIER, 1.5], default=1.0)
        expected_risk = group["risk_amount_before_directional_30d_boost"] * expected_multiplier
        boost_applied = group["directional_30d_risk_boost_applied"].fillna(0).astype(int).eq(1)
        discount_applied = group["directional_30d_low_volume_discount_applied"].fillna(0).astype(int).eq(1)
        threshold_ok = (
            group["directional_30d_risk_adjust_long_only"].eq(0)
            & group["directional_30d_low_volume_discount_enabled"].eq(1)
            & np.isclose(group["directional_30d_volume_ratio_threshold"], 3.0, rtol=0.0, atol=1e-12)
            & np.isclose(group["directional_30d_low_volume_ratio_threshold"], LOW_VOLUME_RATIO_THRESHOLD, rtol=0.0, atol=1e-12)
            & np.isclose(group["directional_30d_low_volume_risk_multiplier"], LOW_VOLUME_RISK_MULTIPLIER, rtol=0.0, atol=1e-12)
            & np.isclose(group["directional_30d_risk_nonconfirmation_multiplier"], 1.0, rtol=0.0, atol=1e-12)
            & valid_direction
        )
        risk_ok = (
            boost_applied.eq(high)
            & discount_applied.eq(low)
            & np.isclose(group["directional_30d_risk_boost_multiplier"], expected_multiplier, rtol=0.0, atol=1e-12)
            & np.isclose(group["target_risk_amount"], expected_risk, rtol=1e-12, atol=1e-9)
        )
        return {
            "group_type": group_type,
            "group_value": group_value,
            "diagnostic_intent_count": int(len(group)),
            "long_high_volume_count": int((long_mask & high).sum()),
            "long_low_volume_count": int((long_mask & low).sum()),
            "long_base_volume_count": int((long_mask & ~high & ~low).sum()),
            "short_high_volume_count": int((short_mask & high).sum()),
            "short_low_volume_count": int((short_mask & low).sum()),
            "short_base_volume_count": int((short_mask & ~high & ~low).sum()),
            "threshold_contract_pass": int(len(group) > 0 and bool(np.asarray(threshold_ok).all())),
            "risk_amount_contract_pass": int(len(group) > 0 and bool(np.asarray(risk_ok).all())),
        }

    rows = [summarize("total", "all", frame)]
    for column, group_type in (("direction", "direction"), ("entry_context", "entry_context")):
        for value, group in frame.groupby(column, sort=True, dropna=False):
            rows.append(summarize(group_type, str(value), group))
    return pd.DataFrame(rows)


def _atr_filter_contract_summary(diagnostics: pd.DataFrame) -> pd.DataFrame:
    required = {
        "direction", "entry_context", "long_signal_atr_shock_enabled", "short_signal_atr_shock_enabled",
        "long_signal_atr_shock_period", "long_signal_atr_shock_multiplier", "long_signal_atr_shock_atr",
        "long_signal_atr_shock_threshold", "signal_atr_shock_adverse_move", "signal_atr_shock_move_kind",
        "long_signal_atr_shock_blocked", "long_signal_atr_shock_reason",
        "long_signal_atr_shock_selected_volume_before", "long_signal_atr_shock_selected_volume_after",
    }
    empty = {
        "group_type": "total", "group_value": "all", "diagnostic_count": 0, "blocked_count": 0,
        "long_blocked_count": 0, "short_blocked_count": 0,
        "positive_volume_blocked_count": 0, "zero_volume_rule_hit_count": 0,
        "configuration_contract_pass": 0, "blocking_contract_pass": 0,
    }
    if diagnostics.empty or not required.issubset(diagnostics.columns):
        return pd.DataFrame([empty])
    frame = diagnostics.copy()
    strings = {"direction", "entry_context", "signal_atr_shock_move_kind", "long_signal_atr_shock_reason"}
    for column in required - strings:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    def summarize(group_type: str, group_value: str, group: pd.DataFrame) -> dict[str, Any]:
        direction = group["direction"].astype(str).str.lower()
        context = group["entry_context"].astype(str)
        relevant = direction.isin({"long", "short"}) & context.isin(s21.APPROVED_CONTEXTS)
        valid = relevant & group["long_signal_atr_shock_atr"].gt(0) & group["signal_atr_shock_adverse_move"].notna()
        expected = valid & group["signal_atr_shock_adverse_move"].gt(group["long_signal_atr_shock_threshold"])
        blocked = group["long_signal_atr_shock_blocked"].fillna(0).astype(int).eq(1)
        expected_kind = np.where(direction.eq("long"), "signal_day_drop", "signal_day_rise")
        expected_reason = np.where(
            direction.eq("long"),
            "drop_strictly_above_threshold",
            "rise_strictly_above_threshold",
        )
        config_ok = (
            group["long_signal_atr_shock_enabled"].eq(1)
            & group["short_signal_atr_shock_enabled"].eq(1)
            & group["long_signal_atr_shock_period"].eq(5)
            & np.isclose(group["long_signal_atr_shock_multiplier"], 1.0, rtol=0.0, atol=1e-12)
        )
        threshold_ok = ~valid | np.isclose(
            group["long_signal_atr_shock_threshold"], group["long_signal_atr_shock_atr"],
            rtol=1e-12, atol=1e-12, equal_nan=False,
        )
        kind_ok = ~relevant | group["signal_atr_shock_move_kind"].astype(str).eq(expected_kind)
        before = group["long_signal_atr_shock_selected_volume_before"]
        after = group["long_signal_atr_shock_selected_volume_after"]
        reason_ok = group["long_signal_atr_shock_reason"].astype(str).eq(expected_reason)
        blocking_ok = (
            blocked.eq(expected)
            & (~blocked | (after.eq(0) & reason_ok))
            & (blocked | after.eq(before))
            & before.ge(0)
            & (relevant | ~blocked)
        )
        return {
            "group_type": group_type,
            "group_value": group_value,
            "diagnostic_count": int(len(group)),
            "blocked_count": int(blocked.sum()),
            "long_blocked_count": int((blocked & direction.eq("long")).sum()),
            "short_blocked_count": int((blocked & direction.eq("short")).sum()),
            "positive_volume_blocked_count": int((blocked & before.gt(0)).sum()),
            "zero_volume_rule_hit_count": int((blocked & before.eq(0)).sum()),
            "configuration_contract_pass": int(len(group) > 0 and bool(np.asarray(config_ok & threshold_ok & kind_ok).all())),
            "blocking_contract_pass": int(len(group) > 0 and bool(np.asarray(blocking_ok).all())),
        }

    rows = [summarize("total", "all", frame)]
    for column, group_type in (("direction", "direction"), ("entry_context", "entry_context")):
        for value, group in frame.groupby(column, sort=True, dropna=False):
            rows.append(summarize(group_type, str(value), group))
    return pd.DataFrame(rows)


def _incremental_effect(summary: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    indexed = summary.set_index("experiment_arm")
    metrics = [
        "end_equity", "total_return_pct", "max_dd_pct", "sharpe", "total_slippage",
        "total_trade_count", "max_broker10_margin_to_equity_pct", "days_over_100pct",
    ]
    differences = {
        metric: float(indexed.loc["R", metric]) - float(indexed.loc["Q", metric])
        for metric in metrics
    }
    changed_metrics = [metric for metric, value in differences.items() if abs(value) > 1e-9]
    return {
        "changed_metrics": changed_metrics,
        "metric_differences": differences,
        "actual_trade_count": int(len(frames.get("trades", pd.DataFrame()))),
        "effect_present": bool(changed_metrics),
    }


def _decision(
    comparison: pd.DataFrame,
    volume_contract: pd.DataFrame,
    atr_contract: pd.DataFrame,
    incremental: dict[str, Any],
) -> dict[str, Any]:
    full_rows: list[dict[str, Any]] = []
    for comparison_name, _, _ in COMPARISONS:
        row = comparison[comparison["comparison"].eq(comparison_name)].iloc[0]
        gates = s17.s15.s7._full_period_gates(row)
        full_rows.append({"comparison": comparison_name, "gates": gates, "pass": bool(all(gates.values()))})
    volume_total = volume_contract[volume_contract["group_type"].astype(str).eq("total")].iloc[0]
    atr_total = atr_contract[atr_contract["group_type"].astype(str).eq("total")].iloc[0]
    contract_gates = {
        "volume_threshold_contract_pass": bool(int(volume_total["threshold_contract_pass"]) == 1),
        "volume_risk_amount_contract_pass": bool(int(volume_total["risk_amount_contract_pass"]) == 1),
        "long_low_volume_present": bool(int(volume_total["long_low_volume_count"]) > 0),
        "short_low_volume_present": bool(int(volume_total["short_low_volume_count"]) > 0),
        "atr_configuration_contract_pass": bool(int(atr_total["configuration_contract_pass"]) == 1),
        "atr_blocking_contract_pass": bool(int(atr_total["blocking_contract_pass"]) == 1),
        "atr_positive_volume_block_present": bool(int(atr_total["positive_volume_blocked_count"]) > 0),
        "incremental_effect_present": bool(incremental["effect_present"]),
    }
    promotion_rows = [row for row in full_rows if row["comparison"] in PROMOTION_COMPARISONS]
    escalate = bool(all(contract_gates.values()) and all(row["pass"] for row in promotion_rows))
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage023",
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
        "R_rule": {
            "base": "Q",
            "changed_parameter_only": "directional_30d_low_volume_ratio_threshold: 0.5 -> 0.8",
            "low_volume_condition": "recent 10d volume strictly less than 0.8 times prior 10d volume",
            "low_volume_risk_multiplier": LOW_VOLUME_RISK_MULTIPLIER,
            "equal_boundary": "0.8 is not discounted",
            "preserved": "both-side >3x x1.5 scaling and both-side 1x ATR5 adverse-move entry filters",
        },
        "precheck": {
            "Q_valid_volume_intents": 374,
            "Q_low_05_count": 6,
            "R_projected_low_08_count": 62,
            "new_band_05_to_08_count": 56,
        },
        "promotion_comparisons": sorted(PROMOTION_COMPARISONS),
        "contract_gates": contract_gates,
        "incremental_effect": incremental,
        "full_period_gates": full_rows,
        "escalate_to_multicycle": escalate,
        "decision": "run_r_low_volume_08_multicycle" if escalate else "stop_r_low_volume_08_after_full_period",
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _validate_summary(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    expected = {str(arm["arm"]) for arm in ARMS}
    if len(summary) != len(ARMS) or set(summary["experiment_arm"].astype(str)) != expected:
        raise RuntimeError("stage023_arm_identity_mismatch")
    critical = [*METRICS, "account_survival_pass", "broker10_100_pass", "max_broker10_margin_to_equity_pct", "days_over_100pct"]
    numeric = summary[critical].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy(dtype="float64")).all():
        raise RuntimeError("stage023_critical_metric_invalid")
    equity = pd.to_numeric(curve.get("account_equity"), errors="coerce")
    if curve.empty or not np.isfinite(equity.to_numpy(dtype="float64")).all():
        raise RuntimeError("stage023_curve_invalid")
    if set(curve["experiment_arm"].astype(str)) != expected or len(set(curve.groupby("experiment_arm").size())) != 1:
        raise RuntimeError("stage023_curve_identity_or_length_mismatch")


def _plot_full(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        frame = curve[curve["experiment_arm"].astype(str).eq(str(arm["arm"]))].sort_values("date")
        ax.plot(pd.to_datetime(frame["date"]), frame["account_equity"] / 10_000.0, color=str(arm["color"]), lw=1.45, label=str(arm["plot_label"]))
    ax.set_title("Stage023 Full-Period Equity: Q vs R Low-Volume Threshold 0.5 to 0.8")
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
    temporary_dir = Path(tempfile.mkdtemp(prefix=".stage023.tmp-", dir=OUTPUT_DIR.parent))
    backup_dir = OUTPUT_DIR.with_name(f".stage023.backup-{uuid4().hex}")
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
    r_summary, r_curve, frames = _run_r_arm(metadata)
    summary = pd.concat([reused_summary, r_summary], ignore_index=True, sort=False)
    curve = pd.concat([reused_curve, r_curve], ignore_index=True, sort=False)
    _validate_summary(summary, curve)
    comparison = _comparison(summary)
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    diagnostics = frames.get("long_signal_atr_shock", pd.DataFrame()).copy()
    volume_contract = _volume_risk_contract_summary(entry_risk)
    atr_contract = _atr_filter_contract_summary(diagnostics)
    incremental = _incremental_effect(summary, frames)
    decision = _decision(comparison, volume_contract, atr_contract, incremental)
    _publish_atomically(
        {
            SUMMARY_PATH.name: summary,
            COMPARISON_PATH.name: comparison,
            CURVE_PATH.name: curve,
            ENTRY_RISK_PATH.name: entry_risk,
            TRADES_PATH.name: frames.get("trades", pd.DataFrame()).copy(),
            TRADE_EVENTS_PATH.name: frames.get("trade_events", pd.DataFrame()).copy(),
            ATR_FILTER_PATH.name: diagnostics,
            VOLUME_CONTRACT_PATH.name: volume_contract,
            ATR_CONTRACT_PATH.name: atr_contract,
        },
        decision,
        _plot_full(curve),
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


def rebuild_from_published() -> None:
    summary = pd.read_csv(SUMMARY_PATH)
    curve = pd.read_csv(CURVE_PATH)
    _validate_summary(summary, curve)
    comparison = _comparison(summary)
    entry_risk = pd.read_csv(ENTRY_RISK_PATH)
    diagnostics = pd.read_csv(ATR_FILTER_PATH)
    volume_contract = _volume_risk_contract_summary(entry_risk)
    atr_contract = _atr_filter_contract_summary(diagnostics)
    frames = {
        "entry_risk": entry_risk,
        "trades": pd.read_csv(TRADES_PATH),
        "trade_events": pd.read_csv(TRADE_EVENTS_PATH),
        "long_signal_atr_shock": diagnostics,
    }
    incremental = _incremental_effect(summary, frames)
    decision = _decision(comparison, volume_contract, atr_contract, incremental)
    _publish_atomically(
        {
            SUMMARY_PATH.name: summary,
            COMPARISON_PATH.name: comparison,
            CURVE_PATH.name: curve,
            ENTRY_RISK_PATH.name: entry_risk,
            TRADES_PATH.name: frames["trades"],
            TRADE_EVENTS_PATH.name: frames["trade_events"],
            ATR_FILTER_PATH.name: diagnostics,
            VOLUME_CONTRACT_PATH.name: volume_contract,
            ATR_CONTRACT_PATH.name: atr_contract,
        },
        decision,
        _plot_full(curve),
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if "--rebuild-from-published" in sys.argv:
        rebuild_from_published()
    else:
        main()
