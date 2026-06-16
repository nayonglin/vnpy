from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_SIGNAL_PLAN_PATH,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
)
from qmt_roll_official_live_phase_d_config import (
    READONLY_POSITIONS_PATH,
    READONLY_SUMMARY_PATH,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage923_official_live_fail_closed_incident_v1"
OUTPUT_PREFIX = "qmt_roll_stage923_official_live_fail_closed_incident"

STAGE260_MODEL_TAG = "stage260_official_live_daily_execution_gate_v1"
STAGE260_PREFIX = "qmt_roll_stage260_official_live_daily_execution_gate"
STAGE906_MODEL_TAG = "stage906_official_live_reconciliation_worker_v1"
STAGE906_PREFIX = "qmt_roll_stage906_official_live_reconciliation_worker"
STAGE913_MODEL_TAG = "stage913_official_live_phase_d_completion_audit_v1"
STAGE913_PREFIX = "qmt_roll_stage913_official_live_phase_d_completion_audit"
STAGE919_MODEL_TAG = "stage919_official_live_reconcile_attribution_audit_v1"
STAGE919_PREFIX = "qmt_roll_stage919_official_live_reconcile_attribution_audit"
STAGE920_MODEL_TAG = "stage920_official_live_account_sync_gate_v1"
STAGE920_PREFIX = "qmt_roll_stage920_official_live_account_sync_gate"


def _date_key(target_date: str) -> str:
    return target_date.replace("-", "") if target_date else "latest"


def _paths(target_date: str) -> dict[str, Path]:
    date_key = _date_key(target_date)
    return {
        "incident_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_incident_{date_key}_{MODEL_TAG}.json",
        "actions_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_actions_{date_key}_{MODEL_TAG}.csv",
        "evidence_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_evidence_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _target_summary(prefix: str, target_date: str, model_tag: str) -> Path:
    return OUTPUT_DIR / f"{prefix}_summary_{_date_key(target_date)}_{model_tag}.json"


def _target_csv(prefix: str, stem: str, target_date: str, model_tag: str) -> Path:
    return OUTPUT_DIR / f"{prefix}_{stem}_{_date_key(target_date)}_{model_tag}.csv"


def _latest(pattern: str) -> Path | None:
    rows = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _read_csv_maybe(path: str | Path | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _to_int(value: Any, default: int = 0) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _to_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _broker_position_text(positions: pd.DataFrame) -> str:
    if positions.empty:
        return "broker_positions_empty"
    parts: list[str] = []
    for row in positions.drop_duplicates().to_dict(orient="records"):
        vt_symbol = _clean(row.get("vt_symbol") or f"{_clean(row.get('symbol'))}.{_clean(row.get('exchange'))}")
        direction = _clean(row.get("direction"))
        volume = _to_float(row.get("volume"), 0.0)
        price = _to_float(row.get("price"), 0.0)
        pnl = _to_float(row.get("pnl"), 0.0)
        if vt_symbol and volume:
            parts.append(f"{vt_symbol} {direction} {volume:g} @ {price:g} pnl={pnl:g}")
    return "; ".join(parts) if parts else "broker_positions_no_nonzero_rows"


def _signal_text(signal_plan: pd.DataFrame) -> str:
    if signal_plan.empty:
        return "signal_plan_empty"
    parts: list[str] = []
    for row in signal_plan.to_dict(orient="records"):
        parts.append(
            " ".join(
                [
                    _clean(row.get("vt_symbol")),
                    _clean(row.get("direction")),
                    _clean(row.get("offset")),
                    f"vol={_to_float(row.get('volume'), 0.0):g}",
                    f"price={_to_float(row.get('theoretical_price'), 0.0):g}",
                    _clean(row.get("exit_reason")),
                ]
            ).strip()
        )
    return "; ".join(parts)


def _action_rows(
    *,
    incident_status: str,
    broker_positions: pd.DataFrame,
    attribution: pd.DataFrame,
    stage920: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = [
        {
            "priority": "P0",
            "action": "do_not_submit_unattended_orders",
            "owner": "automation",
            "status": "enforced",
            "reason": "auto_submit_permitted=0 until broker/shadow reconcile is aligned",
        },
        {
            "priority": "P0",
            "action": "keep_phase_d_fail_closed",
            "owner": "automation",
            "status": "enforced",
            "reason": incident_status,
        },
    ]
    if not broker_positions.empty:
        rows.append(
            {
                "priority": "P0",
                "action": "operator_confirm_broker_position_origin",
                "owner": "operator",
                "status": "required",
                "reason": _broker_position_text(broker_positions),
            }
        )
    if not attribution.empty:
        rows.append(
            {
                "priority": "P0",
                "action": "review_stage919_attribution",
                "owner": "operator",
                "status": "required",
                "reason": "; ".join(sorted(set(attribution.get("account_origin_status", pd.Series(dtype=str)).astype(str)))),
            }
        )
    rows.append(
        {
            "priority": "P1",
            "action": "complete_or_reject_stage920_ack_template",
            "owner": "operator",
            "status": "required" if stage920.get("account_sync_status") != "account_sync_aligned_auto_progress_allowed" else "not_required",
            "reason": f"fingerprint={stage920.get('account_sync_fingerprint', '')};status={stage920.get('account_sync_status', '')}",
        }
    )
    rows.append(
        {
            "priority": "P1",
            "action": "rerun_shadow_readonly_reconcile_after_manual_action",
            "owner": "automation",
            "status": "pending_external_state",
            "reason": "run Stage909/907/260/906/919/920/913 after account origin is resolved",
        }
    )
    return rows


def _evidence_rows(source_files: dict[str, str], payloads: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, path in source_files.items():
        rows.append({"evidence": name, "path": path, "value": ""})
    for key, value in payloads.items():
        rows.append({"evidence": key, "path": "", "value": value})
    return rows


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].to_markdown(index=False)


def _build_report(summary: dict[str, Any], actions: pd.DataFrame, evidence: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage923 Official Live Fail-Closed Incident",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Official live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- Target date: `{summary['target_date']}`",
            f"- Incident status: `{summary['incident_status']}`",
            f"- Operator action required: `{summary['operator_action_required']}`",
            f"- Auto submit permitted: `{summary['auto_submit_permitted']}`",
            f"- Order API calls: `{summary['order_api_called_count']}`",
            "",
            "## Required Actions",
            "",
            _to_markdown(actions, ["priority", "action", "owner", "status", "reason"]),
            "",
            "## Evidence",
            "",
            _to_markdown(evidence, ["evidence", "path", "value"]),
            "",
            "## Notes",
            "",
            "- Stage923 does not connect CTP, refresh market data, submit orders, or cancel orders.",
            "- It converts a fail-closed controller state into an auditable operator incident package.",
            "- The presence of an incident package is not permission to trade; it is evidence that unattended trading remains blocked.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live fail-closed incident package.")
    parser.add_argument("--target-date", required=True)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)

    official_summary = _read_json(OFFICIAL_LIVE_SUMMARY_PATH)
    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    stage260_path = _target_summary(STAGE260_PREFIX, args.target_date, STAGE260_MODEL_TAG)
    stage906_path = _target_summary(STAGE906_PREFIX, args.target_date, STAGE906_MODEL_TAG)
    stage913_path = _latest(f"{STAGE913_PREFIX}_summary_*_{STAGE913_MODEL_TAG}.json")
    stage919_path = _target_summary(STAGE919_PREFIX, args.target_date, STAGE919_MODEL_TAG)
    stage920_path = _target_summary(STAGE920_PREFIX, args.target_date, STAGE920_MODEL_TAG)
    stage260 = _read_json(stage260_path)
    stage906 = _read_json(stage906_path)
    stage913 = _read_json(stage913_path)
    stage919 = _read_json(stage919_path)
    stage920 = _read_json(stage920_path)
    broker_positions = _read_csv_maybe(READONLY_POSITIONS_PATH)
    signal_plan = _read_csv_maybe(OFFICIAL_LIVE_SIGNAL_PLAN_PATH)
    attribution_path = _target_csv(STAGE919_PREFIX, "attribution", args.target_date, STAGE919_MODEL_TAG)
    attribution = _read_csv_maybe(attribution_path)

    reconcile_divergent = stage906.get("reconciliation_status") == "reconcile_divergent_fail_closed"
    attribution_fail_closed = _to_int(stage919.get("fail_closed_required_count"), 0) > 0
    account_sync_required = stage920.get("account_sync_status") in {
        "account_sync_operator_ack_required_fail_closed",
        "account_sync_ack_invalid_fail_closed",
        "account_sync_attribution_missing_fail_closed",
    }
    if reconcile_divergent or attribution_fail_closed or account_sync_required:
        incident_status = "phase_d_fail_closed_operator_attention_required"
    elif stage913.get("completion_status") == "phase_d_completion_proven":
        incident_status = "phase_d_no_incident_completion_proven"
    else:
        incident_status = "phase_d_no_incident_monitor_only"

    operator_action_required = int(incident_status == "phase_d_fail_closed_operator_attention_required")
    auto_submit_permitted = 0
    source_files = {
        "official_summary": str(OFFICIAL_LIVE_SUMMARY_PATH),
        "readonly_summary": str(READONLY_SUMMARY_PATH),
        "readonly_positions": str(READONLY_POSITIONS_PATH),
        "signal_plan": str(OFFICIAL_LIVE_SIGNAL_PLAN_PATH),
        "stage260_summary": str(stage260_path),
        "stage906_summary": str(stage906_path),
        "stage913_summary": str(stage913_path) if stage913_path else "",
        "stage919_summary": str(stage919_path),
        "stage919_attribution": str(attribution_path),
        "stage920_summary": str(stage920_path),
    }
    payload_evidence = {
        "official_analysis_end": official_summary.get("analysis_end", ""),
        "latest_available_data_date": official_summary.get("latest_available_data_date", ""),
        "stage260_executable_count": stage260.get("executable_count", ""),
        "stage260_position_mismatch_count": stage260.get("skipped_position_mismatch_count", ""),
        "stage906_reconciliation_status": stage906.get("reconciliation_status", ""),
        "stage906_alignment": stage906.get("account_state_alignment", ""),
        "stage919_attribution_status": stage919.get("attribution_status", ""),
        "stage920_account_sync_status": stage920.get("account_sync_status", ""),
        "stage920_fingerprint": stage920.get("account_sync_fingerprint", ""),
        "broker_positions": _broker_position_text(broker_positions),
        "target_signal_list": _signal_text(signal_plan),
    }
    actions_df = pd.DataFrame(
        _action_rows(
            incident_status=incident_status,
            broker_positions=broker_positions,
            attribution=attribution,
            stage920=stage920,
        )
    )
    evidence_df = pd.DataFrame(_evidence_rows(source_files, payload_evidence))
    incident = {
        "incident_status": incident_status,
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "operator_action_required": operator_action_required,
        "auto_submit_permitted": auto_submit_permitted,
        "order_api_called_count": 0,
        "source_files": source_files,
        "evidence": payload_evidence,
        "actions": actions_df.to_dict(orient="records"),
    }
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "incident_status": incident_status,
        "operator_action_required": operator_action_required,
        "auto_submit_permitted": auto_submit_permitted,
        "order_api_called_count": 0,
        "stage906_reconciliation_status": stage906.get("reconciliation_status", ""),
        "stage919_attribution_status": stage919.get("attribution_status", ""),
        "stage920_account_sync_status": stage920.get("account_sync_status", ""),
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "source_files": source_files,
        "judgement": {
            "overfit_before": "No. Stage923 packages execution incidents only; it does not change strategy signals.",
            "continue_before": "Yes. Unattended automation needs an operator-attention path when fail-closed gates trigger.",
            "overfit_after": "No. The incident package does not feed back into C9 parameters.",
            "continue_after": "Yes. Resolve broker/shadow origin externally, then rerun the Phase D evidence chain.",
        },
    }
    paths["incident_json"].write_text(json.dumps(incident, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    actions_df.to_csv(paths["actions_csv"], index=False, encoding="utf-8-sig")
    evidence_df.to_csv(paths["evidence_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, actions_df, evidence_df), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
