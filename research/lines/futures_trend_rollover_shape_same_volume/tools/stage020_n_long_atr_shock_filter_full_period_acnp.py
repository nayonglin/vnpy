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
import stage018_symmetric_triple_volume_with_low_volume_discount_full_period_acmn as s18


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage020"
SUMMARY_PATH = OUTPUT_DIR / "stage020_acnp_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage020_acnp_comparison.csv"
CURVE_PATH = OUTPUT_DIR / "stage020_acnp_curve.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / "stage020_full_p_entry_risk.csv"
TRADES_PATH = OUTPUT_DIR / "stage020_full_p_trades.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / "stage020_full_p_trade_events.csv"
ATR_FILTER_PATH = OUTPUT_DIR / "stage020_full_p_long_signal_atr_shock.csv"
ATR_CONTRACT_PATH = OUTPUT_DIR / "stage020_full_p_atr_filter_contract_summary.csv"
DECISION_PATH = OUTPUT_DIR / "stage020_decision.json"
CHART_PATH = OUTPUT_DIR / "stage020_full_period_equity_acnp.png"

ARMS: tuple[dict[str, Any], ...] = (
    {"arm": "A", "profile": "stage020_A_official_live_c9_15w", "label": "A: Official C9/150k", "plot_label": "A Official", "color": "#2563eb"},
    {"arm": "C", "profile": "stage020_C_rollover_continuation", "label": "C: Official + rollover continuation", "plot_label": "C Rollover", "color": "#dc2626"},
    {"arm": "N", "profile": "stage020_N_symmetric_triple_volume_hit_15_low_half_05", "label": "N: Both directions >3x x1.5, <0.5x x0.5", "plot_label": "N Long + Short", "color": "#7c3aed"},
    {
        "arm": "P",
        "profile": "stage020_P_n_plus_long_atr5_1x_shock_filter",
        "label": "P: N + block long entry when signal-day drop > 1x prior ATR5",
        "plot_label": "P N + Long 1x ATR Shock",
        "color": "#f59e0b",
        "base_arm": "N",
        "risk_adjust_long_only": False,
        "atr_period": 5,
        "atr_multiplier": 1.0,
        "entry_contexts": ("flat_entry", "reverse_entry", "rollover_reopen"),
    },
)

REUSED_ARMS = {"A", "C", "N"}
NEW_RUN_ARMS = {"P"}
REUSED_SOURCE_STAGE = "Stage018"
REUSED_SOURCE_COMMIT = "f1255875ee2a56024e241f4850ab9dc2be26425f"
COMPARISONS: tuple[tuple[str, str, str], ...] = (
    ("A_vs_C", "A", "C"),
    ("A_vs_N", "A", "N"),
    ("C_vs_N", "C", "N"),
    ("A_vs_P", "A", "P"),
    ("C_vs_P", "C", "P"),
    ("N_vs_P", "N", "P"),
)
METRICS = s17.METRICS
APPROVED_CONTEXTS = {"flat_entry", "reverse_entry", "rollover_reopen"}


def _load_reused_arms() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(s18.SUMMARY_PATH)
    curve = pd.read_csv(s18.CURVE_PATH)
    summary = summary[summary["experiment_arm"].astype(str).isin(REUSED_ARMS)].copy()
    curve = curve[curve["experiment_arm"].astype(str).isin(REUSED_ARMS)].copy()
    if len(summary) != len(REUSED_ARMS) or set(summary["experiment_arm"].astype(str)) != REUSED_ARMS:
        raise RuntimeError("stage020_reused_summary_identity_mismatch")
    if set(curve["experiment_arm"].astype(str)) != REUSED_ARMS:
        raise RuntimeError("stage020_reused_curve_identity_mismatch")
    if len(set(curve.groupby("experiment_arm").size().to_dict().values())) != 1:
        raise RuntimeError("stage020_reused_curve_length_mismatch")
    return summary, curve


def _p_overrides(
    *,
    candidate: bool,
    volume_policy: str = "exact_or_skip",
    history_mode: str = "target_contract_only",
    base_overrides: Any | None = None,
) -> dict[str, Any]:
    builder = base_overrides or s1._overrides
    overrides = builder(
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
            "enable_long_signal_atr_shock_filter": True,
            "long_signal_atr_shock_period": 5,
            "long_signal_atr_shock_multiplier": 1.0,
            "long_signal_atr_shock_entry_contexts": "flat_entry,reverse_entry,rollover_reopen",
        }
    )
    return overrides


def _run_p_arm(metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    arm = next(item for item in ARMS if item["arm"] == "P")
    original_overrides = s1._overrides

    def experiment_overrides(*, candidate: bool, volume_policy: str = "exact_or_skip", history_mode: str = "target_contract_only") -> dict[str, Any]:
        return _p_overrides(
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
    summary["experiment_arm"] = "P"
    curve = curve.copy()
    curve["experiment_arm"] = "P"
    return summary, curve, frames


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    original = s17.s15.s10.COMPARISONS
    try:
        s17.s15.s10.COMPARISONS = COMPARISONS
        return s17.s15.s10._comparison(summary)
    finally:
        s17.s15.s10.COMPARISONS = original


def _atr_filter_contract_summary(diagnostics: pd.DataFrame) -> pd.DataFrame:
    required = {
        "direction", "entry_context", "long_signal_atr_shock_enabled", "long_signal_atr_shock_period",
        "long_signal_atr_shock_multiplier", "long_signal_atr_shock_atr", "long_signal_atr_shock_drop",
        "long_signal_atr_shock_threshold", "long_signal_atr_shock_blocked", "long_signal_atr_shock_reason",
        "long_signal_atr_shock_selected_volume_before", "long_signal_atr_shock_selected_volume_after",
    }
    empty = {
        "group_type": "total", "group_value": "all", "diagnostic_count": 0, "blocked_count": 0,
        "flat_entry_blocked_count": 0, "reverse_entry_blocked_count": 0, "rollover_reopen_blocked_count": 0,
        "configuration_contract_pass": 0, "blocking_contract_pass": 0,
    }
    if diagnostics.empty or not required.issubset(diagnostics.columns):
        return pd.DataFrame([empty])
    frame = diagnostics.copy()
    strings = {"direction", "entry_context", "long_signal_atr_shock_reason"}
    for column in required - strings:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    def summarize(group_type: str, group_value: str, group: pd.DataFrame) -> dict[str, Any]:
        direction = group["direction"].astype(str).str.lower()
        context = group["entry_context"].astype(str)
        relevant = direction.eq("long") & context.isin(APPROVED_CONTEXTS)
        valid = relevant & group["long_signal_atr_shock_atr"].gt(0) & group["long_signal_atr_shock_drop"].notna()
        expected = valid & group["long_signal_atr_shock_drop"].gt(group["long_signal_atr_shock_threshold"])
        blocked = group["long_signal_atr_shock_blocked"].fillna(0).astype(int).eq(1)
        config_ok = (
            group["long_signal_atr_shock_enabled"].eq(1)
            & group["long_signal_atr_shock_period"].eq(5)
            & np.isclose(group["long_signal_atr_shock_multiplier"], 1.0, rtol=0.0, atol=1e-12)
        )
        threshold_ok = ~valid | np.isclose(
            group["long_signal_atr_shock_threshold"], group["long_signal_atr_shock_atr"],
            rtol=1e-12, atol=1e-12, equal_nan=False,
        )
        before = group["long_signal_atr_shock_selected_volume_before"]
        after = group["long_signal_atr_shock_selected_volume_after"]
        blocking_ok = (
            blocked.eq(expected)
            & (~blocked | (before.gt(0) & after.eq(0) & group["long_signal_atr_shock_reason"].astype(str).eq("drop_strictly_above_threshold")))
            & (blocked | after.eq(before))
            & (relevant | ~blocked)
        )
        return {
            "group_type": group_type,
            "group_value": group_value,
            "diagnostic_count": int(len(group)),
            "blocked_count": int(blocked.sum()),
            "flat_entry_blocked_count": int((blocked & context.eq("flat_entry")).sum()),
            "reverse_entry_blocked_count": int((blocked & context.eq("reverse_entry")).sum()),
            "rollover_reopen_blocked_count": int((blocked & context.eq("rollover_reopen")).sum()),
            "configuration_contract_pass": int(len(group) > 0 and bool(np.asarray(config_ok & threshold_ok).all())),
            "blocking_contract_pass": int(len(group) > 0 and bool(np.asarray(blocking_ok).all())),
        }

    rows = [summarize("total", "all", frame)]
    for column, group_type in (("direction", "direction"), ("entry_context", "entry_context")):
        for value, group in frame.groupby(column, sort=True, dropna=False):
            rows.append(summarize(group_type, str(value), group))
    return pd.DataFrame(rows)


def _decision(comparison: pd.DataFrame, contract: pd.DataFrame) -> dict[str, Any]:
    full_rows: list[dict[str, Any]] = []
    for comparison_name, _, _ in COMPARISONS:
        row = comparison[comparison["comparison"].eq(comparison_name)].iloc[0]
        gates = s17.s15.s7._full_period_gates(row)
        full_rows.append({"comparison": comparison_name, "gates": gates, "pass": bool(all(gates.values()))})
    total = contract[contract["group_type"].astype(str).eq("total")].iloc[0]
    contract_gates = {
        "configuration_contract_pass": bool(int(total["configuration_contract_pass"]) == 1),
        "blocking_contract_pass": bool(int(total["blocking_contract_pass"]) == 1),
        "blocked_signal_present": bool(int(total["blocked_count"]) > 0),
    }
    promotion = {"A_vs_P", "C_vs_P"}
    promotion_rows = [row for row in full_rows if row["comparison"] in promotion]
    escalate = bool(all(contract_gates.values()) and all(row["pass"] for row in promotion_rows))
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage020",
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
        "P_rule": {
            "base": "N",
            "base_risk_scaling": "both long and short: aligned >3x volume uses 1.5; <0.5x volume uses 0.5; otherwise 1.0",
            "atr_filter_direction": "long only",
            "entry_contexts": sorted(APPROVED_CONTEXTS),
            "signal_day_drop": "previous close minus signal-day close",
            "atr": "simple mean of 5 true ranges from completed days strictly before signal day",
            "condition": "block only when signal-day drop is strictly greater than 1.0 times ATR5",
            "invalid_or_insufficient_history": "keep N behavior",
            "excluded_from_atr_filter": "short entries, all adds, C9 stop retry",
        },
        "promotion_comparisons": sorted(promotion),
        "atr_filter_contract_gates": contract_gates,
        "full_period_gates": full_rows,
        "escalate_to_multicycle": escalate,
        "decision": "run_n_long_atr_shock_filter_multicycle" if escalate else "stop_n_long_atr_shock_filter_after_full_period",
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _validate_summary(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    expected = {str(arm["arm"]) for arm in ARMS}
    if len(summary) != len(ARMS) or set(summary["experiment_arm"].astype(str)) != expected:
        raise RuntimeError("stage020_arm_identity_mismatch")
    critical = [*METRICS, "account_survival_pass", "broker10_100_pass", "max_broker10_margin_to_equity_pct", "days_over_100pct"]
    numeric = summary[critical].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy(dtype="float64")).all():
        raise RuntimeError("stage020_critical_metric_invalid")
    equity = pd.to_numeric(curve.get("account_equity"), errors="coerce")
    if curve.empty or not np.isfinite(equity.to_numpy(dtype="float64")).all():
        raise RuntimeError("stage020_curve_invalid")
    if set(curve["experiment_arm"].astype(str)) != expected or len(set(curve.groupby("experiment_arm").size())) != 1:
        raise RuntimeError("stage020_curve_identity_or_length_mismatch")


def _plot_full(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        frame = curve[curve["experiment_arm"].astype(str).eq(str(arm["arm"]))].sort_values("date")
        ax.plot(pd.to_datetime(frame["date"]), frame["account_equity"] / 10_000.0, color=str(arm["color"]), lw=1.45, label=str(arm["plot_label"]))
    ax.set_title("Stage020 Full-Period Equity: N + Long Signal-Day Drop > 1x Prior ATR5 Filter")
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
    temporary_dir = Path(tempfile.mkdtemp(prefix=".stage020.tmp-", dir=OUTPUT_DIR.parent))
    backup_dir = OUTPUT_DIR.with_name(f".stage020.backup-{uuid4().hex}")
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
    p_summary, p_curve, frames = _run_p_arm(metadata)
    summary = pd.concat([reused_summary, p_summary], ignore_index=True, sort=False)
    curve = pd.concat([reused_curve, p_curve], ignore_index=True, sort=False)
    _validate_summary(summary, curve)
    comparison = _comparison(summary)
    diagnostics = frames.get("long_signal_atr_shock", pd.DataFrame()).copy()
    contract = _atr_filter_contract_summary(diagnostics)
    decision = _decision(comparison, contract)
    _publish_atomically(
        {
            SUMMARY_PATH.name: summary,
            COMPARISON_PATH.name: comparison,
            CURVE_PATH.name: curve,
            ENTRY_RISK_PATH.name: frames.get("entry_risk", pd.DataFrame()).copy(),
            TRADES_PATH.name: frames.get("trades", pd.DataFrame()).copy(),
            TRADE_EVENTS_PATH.name: frames.get("trade_events", pd.DataFrame()).copy(),
            ATR_FILTER_PATH.name: diagnostics,
            ATR_CONTRACT_PATH.name: contract,
        },
        decision,
        _plot_full(curve),
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
