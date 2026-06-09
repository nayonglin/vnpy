from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage726_stage725_2022_failure_forensics as s726
import analyze_qmt_roll_stage727_official_sleeve_edge60_bypass as s727
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df, build_entry_risk_diagnostics_df


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage728_stage727_bypass_trigger_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage728_stage727_bypass_trigger_audit"
LINE_ID = "futures_trend_winner_trade_forensics"

WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("full_2020_20260430", "2020-01-01", "2026-04-30"),
    ("since_2022", "2022-01-01", "2026-04-30"),
    ("phase_2022_2023", "2022-01-01", "2023-12-31"),
    ("since_2026", "2026-01-01", "2026-04-30"),
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
RELEVANT_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_relevant_entry_risk_{MODEL_TAG}.csv"
REASONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reasons_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default)


def _run_candidate_window(
    metadata: dict[str, Any],
    window_name: str,
    start: str,
    end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    original_start = s726.ANALYSIS_START
    original_end = s726.ANALYSIS_END
    try:
        s726.ANALYSIS_START = pd.Timestamp(start)
        s726.ANALYSIS_END = pd.Timestamp(end)
        spec = s727._candidate_spec(metadata)
        print(f"[stage728] running {window_name} {spec.capital.variant}", flush=True)
        engine = s726._run_engine_for_spec(spec, metadata)
        risk = build_entry_risk_diagnostics_df(engine)
        candidates = build_entry_candidate_snapshots_df(engine)
    finally:
        s726.ANALYSIS_START = original_start
        s726.ANALYSIS_END = original_end

    for frame in (risk, candidates):
        if frame.empty:
            continue
        frame["window_name"] = window_name
        frame["variant"] = s727.CANDIDATE_VARIANT
        frame["model_tag"] = MODEL_TAG
    return risk, candidates


def _summarize(risk: pd.DataFrame, candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    reason_frames: list[pd.DataFrame] = []
    relevant_frames: list[pd.DataFrame] = []
    if risk.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    data = risk.copy()
    data["streak_entry_structure_risk_recovery_applied_num"] = _numeric(
        data,
        "streak_entry_structure_risk_recovery_applied",
    )
    data["recovery_sleeve_applied_num"] = _numeric(data, "recovery_sleeve_applied")
    data["recovery_sleeve_bypassed_num"] = _numeric(data, "recovery_sleeve_normal_risk_bypassed")
    data["recovery_sleeve_bypass_enabled_num"] = _numeric(data, "recovery_sleeve_normal_risk_bypass_enabled")
    data["selected_volume"] = _numeric(data, "selected_volume")
    data["recovery_sleeve_selected_volume_before_num"] = _numeric(
        data,
        "recovery_sleeve_selected_volume_before",
    )
    data["recovery_sleeve_selected_volume_after_num"] = _numeric(
        data,
        "recovery_sleeve_selected_volume_after",
    )
    data["edge_close_position"] = _numeric(
        data,
        "streak_entry_structure_risk_recovery_directional_edge_close_position",
        default=np.nan,
    )
    data["portfolio_drawdown_pct"] = _numeric(
        data,
        "streak_entry_structure_risk_recovery_portfolio_drawdown_pct",
        default=np.nan,
    )
    data["directional_edge60_passed"] = (
        (data["direction"].astype(str).eq("long") & data["edge_close_position"].ge(s727.LONG_CLOSE_POSITION_MIN))
        | (data["direction"].astype(str).eq("short") & data["edge_close_position"].le(s727.SHORT_CLOSE_POSITION_MAX))
    )
    data["account_drawdown_5pct_passed"] = data["portfolio_drawdown_pct"].le(s727.ACCOUNT_HEALTH_MAX_DRAWDOWN)
    data["bypass_condition_passed"] = data["directional_edge60_passed"] & data["account_drawdown_5pct_passed"]
    candidate_data = candidates.copy()
    if not candidate_data.empty:
        candidate_data["candidate_status"] = candidate_data.get("candidate_status", "").astype(str)

    for window_name, group in data.groupby("window_name", sort=False):
        reasons = (
            group.groupby(["recovery_sleeve_reason"], dropna=False)
            .size()
            .reset_index(name="entry_risk_count")
            .sort_values("entry_risk_count", ascending=False)
        )
        reasons["window_name"] = window_name
        reason_frames.append(reasons)

        relevant = group[
            group["streak_entry_structure_risk_recovery_applied_num"].eq(1.0)
            | group["recovery_sleeve_applied_num"].eq(1.0)
            | group["recovery_sleeve_bypassed_num"].eq(1.0)
        ].copy()
        if not relevant.empty:
            relevant_frames.append(relevant)

        candidate_group = candidate_data[candidate_data["window_name"].astype(str).eq(str(window_name))]
        opened_candidates = int(candidate_group["candidate_status"].eq("opened").sum()) if not candidate_group.empty else 0
        summary_rows.append(
            {
                "window_name": window_name,
                "entry_risk_rows": int(len(group)),
                "entry_candidate_rows": int(len(candidate_group)),
                "opened_candidate_rows": opened_candidates,
                "structure_recovery_applied_count": int(
                    group["streak_entry_structure_risk_recovery_applied_num"].eq(1.0).sum()
                ),
                "sleeve_applied_count": int(group["recovery_sleeve_applied_num"].eq(1.0).sum()),
                "bypass_enabled_count": int(group["recovery_sleeve_bypass_enabled_num"].eq(1.0).sum()),
                "bypass_trigger_count": int(group["recovery_sleeve_bypassed_num"].eq(1.0).sum()),
                "directional_edge60_pass_count": int(relevant["directional_edge60_passed"].sum())
                if not relevant.empty
                else 0,
                "account_drawdown_5pct_pass_count": int(relevant["account_drawdown_5pct_passed"].sum())
                if not relevant.empty
                else 0,
                "both_bypass_condition_pass_count": int(relevant["bypass_condition_passed"].sum())
                if not relevant.empty
                else 0,
                "sleeve_or_bypass_count": int(
                    (
                        group["recovery_sleeve_applied_num"].eq(1.0)
                        | group["recovery_sleeve_bypassed_num"].eq(1.0)
                    ).sum()
                ),
                "avg_selected_volume": float(group["selected_volume"].mean()),
                "max_selected_volume": float(group["selected_volume"].max()),
                "avg_edge_close_position_relevant": float(relevant["edge_close_position"].mean(skipna=True))
                if not relevant.empty
                else float("nan"),
                "min_portfolio_drawdown_relevant": float(relevant["portfolio_drawdown_pct"].min(skipna=True))
                if not relevant.empty
                else float("nan"),
                "max_portfolio_drawdown_relevant": float(relevant["portfolio_drawdown_pct"].max(skipna=True))
                if not relevant.empty
                else float("nan"),
            }
        )

    reasons = pd.concat(reason_frames, ignore_index=True, sort=False) if reason_frames else pd.DataFrame()
    relevant = pd.concat(relevant_frames, ignore_index=True, sort=False) if relevant_frames else pd.DataFrame()
    return pd.DataFrame(summary_rows), reasons, relevant


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _decision(summary: pd.DataFrame, reasons: pd.DataFrame) -> dict[str, Any]:
    bypass_count = int(summary["bypass_trigger_count"].sum()) if not summary.empty else 0
    sleeve_count = int(summary["sleeve_applied_count"].sum()) if not summary.empty else 0
    structure_count = int(summary["structure_recovery_applied_count"].sum()) if not summary.empty else 0
    if bypass_count <= 0:
        label = "stage727_empty_pass_no_bypass_trigger_not_promoted"
    else:
        label = "stage727_bypass_triggered_needs_pnl_attribution"
    directional_pass_count = int(summary["directional_edge60_pass_count"].sum()) if not summary.empty else 0
    account_drawdown_pass_count = int(summary["account_drawdown_5pct_pass_count"].sum()) if not summary.empty else 0
    both_condition_count = int(summary["both_bypass_condition_pass_count"].sum()) if not summary.empty else 0
    return {
        "stage": "Stage010",
        "script_stage": "Stage728",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "candidate": s727.CANDIDATE_VARIANT,
        "decision": label,
        "windows": [window[0] for window in WINDOWS],
        "total_structure_recovery_applied_count": structure_count,
        "total_sleeve_applied_count": sleeve_count,
        "total_bypass_trigger_count": bypass_count,
        "total_directional_edge60_pass_count": directional_pass_count,
        "total_account_drawdown_5pct_pass_count": account_drawdown_pass_count,
        "total_both_bypass_condition_pass_count": both_condition_count,
        "no_bypass_trigger": bypass_count <= 0,
        "reason_top": reasons.head(20).to_dict("records") if not reasons.empty else [],
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "relevant_entry_risk": str(RELEVANT_RISK_PATH),
            "reasons": str(REASONS_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s726.s650._md_table(frame, max_rows=max_rows)


def _write_report(summary: pd.DataFrame, reasons: pd.DataFrame, relevant: pd.DataFrame, decision: dict[str, Any]) -> None:
    relevant_cols = [
        "window_name",
        "datetime",
        "vt_symbol",
        "product",
        "direction",
        "signal",
        "risk_multiplier",
        "loss_streak",
        "streak_entry_structure_risk_recovery_applied",
        "recovery_sleeve_applied",
        "recovery_sleeve_normal_risk_bypassed",
        "recovery_sleeve_reason",
        "recovery_sleeve_selected_volume_before",
        "recovery_sleeve_selected_volume_after",
        "streak_entry_structure_risk_recovery_directional_edge_close_position",
        "streak_entry_structure_risk_recovery_portfolio_drawdown_pct",
        "directional_edge60_passed",
        "account_drawdown_5pct_passed",
        "bypass_condition_passed",
    ]
    existing_relevant_cols = [col for col in relevant_cols if col in relevant.columns]
    lines = [
        "# Stage728 Stage727 Bypass Trigger Audit",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 目的：审计 Stage727 的 `official sleeve + directional_edge60 normal-risk bypass` 是否真实触发。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=40),
        "",
        "## Recovery Sleeve Reasons",
        "",
        _md_table(reasons, max_rows=80),
        "",
        "## Relevant Entry Risk Rows",
        "",
        _md_table(relevant[existing_relevant_cols] if existing_relevant_cols else relevant, max_rows=80),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- total_bypass_trigger_count：`{decision['total_bypass_trigger_count']}`",
        f"- total_directional_edge60_pass_count：`{decision['total_directional_edge60_pass_count']}`",
        f"- total_account_drawdown_5pct_pass_count：`{decision['total_account_drawdown_5pct_pass_count']}`",
        f"- total_both_bypass_condition_pass_count：`{decision['total_both_bypass_condition_pass_count']}`",
        f"- total_sleeve_applied_count：`{decision['total_sleeve_applied_count']}`",
        f"- total_structure_recovery_applied_count：`{decision['total_structure_recovery_applied_count']}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s727.s707.s513._metadata()
    risk_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    for window_name, start, end in WINDOWS:
        risk, candidates = _run_candidate_window(metadata, window_name, start, end)
        if not risk.empty:
            risk_frames.append(risk)
        if not candidates.empty:
            candidate_frames.append(candidates)

    risk_all = pd.concat(risk_frames, ignore_index=True, sort=False) if risk_frames else pd.DataFrame()
    candidates_all = (
        pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    )
    summary, reasons, relevant = _summarize(risk_all, candidates_all)
    decision = _decision(summary, reasons)
    _write_report(summary, reasons, relevant, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    risk_all.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    candidates_all.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    relevant.to_csv(RELEVANT_RISK_PATH, index=False, encoding="utf-8-sig")
    reasons.to_csv(REASONS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
