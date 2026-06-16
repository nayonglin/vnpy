from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_phase_d_config import READONLY_POSITIONS_PATH
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage924_official_live_account_recovery_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage924_official_live_account_recovery_gate"
STAGE919_MODEL_TAG = "stage919_official_live_reconcile_attribution_audit_v1"
STAGE919_PREFIX = "qmt_roll_stage919_official_live_reconcile_attribution_audit"
STAGE920_MODEL_TAG = "stage920_official_live_account_sync_gate_v1"
STAGE920_PREFIX = "qmt_roll_stage920_official_live_account_sync_gate"

ALLOWED_RECOVERY_ACTIONS = {
    "manual_keep_fail_closed",
    "manual_flatten_or_reduce_then_refresh",
    "manual_accept_broker_as_non_strategy_position",
}


def _date_key(target_date: str) -> str:
    return target_date.replace("-", "") if target_date else "latest"


def _paths(target_date: str) -> dict[str, Path]:
    date_key = _date_key(target_date)
    return {
        "decision_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{date_key}_{MODEL_TAG}.csv",
        "ack_template_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_recovery_ack_template_{date_key}_{MODEL_TAG}.json",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _stage919_attribution_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE919_PREFIX}_attribution_{_date_key(target_date)}_{STAGE919_MODEL_TAG}.csv"


def _stage920_summary_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE920_PREFIX}_summary_{_date_key(target_date)}_{STAGE920_MODEL_TAG}.json"


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


def _read_json_maybe(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _to_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _to_int(value: Any, default: int = 0) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _fingerprint(frame: pd.DataFrame, target_date: str) -> str:
    if frame.empty:
        payload = {"target_date": target_date, "rows": []}
    else:
        columns = [
            "target_date",
            "vt_symbol",
            "direction",
            "shadow_volume",
            "broker_volume",
            "delta_broker_minus_shadow",
            "shadow_mark_price",
            "broker_avg_price",
            "c9_open_trade_date",
            "c9_open_trade_price",
            "c9_open_trade_volume",
            "account_origin_status",
        ]
        selected = frame.loc[:, [column for column in columns if column in frame.columns]].copy()
        selected = selected.sort_values([column for column in ["vt_symbol", "direction"] if column in selected.columns])
        payload = {"target_date": target_date, "rows": selected.to_dict(orient="records")}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


def _validate_ack(ack: dict[str, Any], *, target_date: str, fingerprint: str) -> tuple[bool, str]:
    if not ack:
        return False, "ack_missing"
    if ack.get("target_date") != target_date:
        return False, "ack_target_date_mismatch"
    if ack.get("official_live_version") != OFFICIAL_LIVE_VERSION:
        return False, "ack_live_version_mismatch"
    if ack.get("account_sync_fingerprint") != fingerprint:
        return False, "ack_fingerprint_mismatch"
    if ack.get("operator_acknowledged") is not True:
        return False, "operator_acknowledged_not_true"
    if str(ack.get("recovery_action", "")) not in ALLOWED_RECOVERY_ACTIONS:
        return False, "recovery_action_not_allowed"
    if not str(ack.get("operator", "")).strip():
        return False, "ack_operator_missing"
    if not str(ack.get("acknowledged_at", "")).strip():
        return False, "ack_time_missing"
    return True, "ack_valid"


def _ack_template(
    *,
    target_date: str,
    fingerprint: str,
    attribution: pd.DataFrame,
    broker_positions: pd.DataFrame,
) -> dict[str, Any]:
    return {
        "purpose": "manual account recovery acknowledgement template",
        "target_date": target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "account_sync_fingerprint": fingerprint,
        "operator_acknowledged": False,
        "recovery_action": "manual_keep_fail_closed",
        "allowed_recovery_actions": sorted(ALLOWED_RECOVERY_ACTIONS),
        "operator": "",
        "acknowledged_at": "",
        "notes": "",
        "broker_positions": broker_positions.to_dict(orient="records"),
        "current_attribution_rows": attribution.to_dict(orient="records"),
        "warning": (
            "This acknowledgement does not submit orders. It only records how the operator "
            "intends to resolve the current broker/shadow divergence before the automation chain is rerun."
        ),
    }


def _decision_status(
    *,
    ack_valid: bool,
    ack: dict[str, Any],
    divergent_count: int,
    broker_positions: pd.DataFrame,
) -> tuple[str, str, int]:
    if divergent_count == 0:
        return "account_recovery_not_required_aligned", "broker_shadow_aligned", 0
    if not ack_valid:
        return "account_recovery_ack_required_fail_closed", "operator_recovery_ack_missing_or_invalid", 1
    action = str(ack.get("recovery_action", ""))
    if action == "manual_keep_fail_closed":
        return "account_recovery_manual_keep_fail_closed", "operator_chose_keep_fail_closed", 1
    if action == "manual_flatten_or_reduce_then_refresh":
        if broker_positions.empty:
            return "account_recovery_manual_action_done_rerun_required", "broker_flat_after_manual_action_rerun_full_chain", 0
        return "account_recovery_manual_action_pending_fail_closed", "broker_positions_still_present_after_manual_action_ack", 1
    if action == "manual_accept_broker_as_non_strategy_position":
        return "account_recovery_non_strategy_position_ack_recorded_fail_closed", "non_strategy_position_must_remain_outside_c9_unattended_submit", 1
    return "account_recovery_unknown_action_fail_closed", "unknown_recovery_action", 1


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].to_markdown(index=False)


def _build_report(summary: dict[str, Any], decision: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage924 Official Live Account Recovery Gate",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Official live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- Target date: `{summary['target_date']}`",
            f"- Recovery status: `{summary['recovery_status']}`",
            f"- Ack valid: `{summary['ack_valid']}`",
            f"- Auto submit permitted: `{summary['auto_submit_permitted']}`",
            f"- Order API calls: `{summary['order_api_called_count']}`",
            "",
            "## Decision",
            "",
            _to_markdown(
                decision,
                [
                    "target_date",
                    "recovery_status",
                    "recovery_reason",
                    "operator_action_required",
                    "next_required_step",
                    "broker_positions",
                ],
            ),
            "",
            "## Notes",
            "",
            "- Stage924 does not connect CTP, submit orders, cancel orders, or mutate broker/shadow state.",
            "- A valid recovery acknowledgement never permits unattended live submit by itself.",
            "- After any manual broker action, rerun Stage909, Stage907, Stage260, Stage906, Stage919, Stage920, Stage924, and Stage913.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live account recovery gate.")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--ack-path", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)
    attribution = _read_csv_maybe(_stage919_attribution_path(args.target_date))
    stage920 = _read_json_maybe(_stage920_summary_path(args.target_date))
    broker_positions = _read_csv_maybe(READONLY_POSITIONS_PATH)
    fingerprint = _fingerprint(attribution, args.target_date)
    ack = _read_json_maybe(args.ack_path)
    ack_valid, ack_reason = _validate_ack(ack, target_date=args.target_date, fingerprint=fingerprint)
    divergent_count = (
        int((pd.to_numeric(attribution.get("delta_broker_minus_shadow"), errors="coerce").fillna(0.0).abs() > 1e-9).sum())
        if not attribution.empty
        else _to_int(stage920.get("divergent_count"), 0)
    )
    recovery_status, recovery_reason, operator_action_required = _decision_status(
        ack_valid=ack_valid,
        ack=ack,
        divergent_count=divergent_count,
        broker_positions=broker_positions,
    )
    next_required_step = (
        "rerun_full_phase_d_chain"
        if recovery_status == "account_recovery_manual_action_done_rerun_required"
        else "manual_operator_resolution_required"
        if operator_action_required
        else "continue_monitoring"
    )
    decision = pd.DataFrame(
        [
            {
                "target_date": args.target_date,
                "recovery_status": recovery_status,
                "recovery_reason": recovery_reason,
                "operator_action_required": operator_action_required,
                "next_required_step": next_required_step,
                "broker_positions": _broker_position_text(broker_positions),
                "account_sync_fingerprint": fingerprint,
                "ack_valid": int(ack_valid),
                "ack_reason": ack_reason,
                "auto_submit_permitted": 0,
                "order_api_called_count": 0,
            }
        ]
    )
    template = _ack_template(
        target_date=args.target_date,
        fingerprint=fingerprint,
        attribution=attribution,
        broker_positions=broker_positions,
    )
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "recovery_status": recovery_status,
        "recovery_reason": recovery_reason,
        "operator_action_required": operator_action_required,
        "account_sync_fingerprint": fingerprint,
        "ack_path": str(Path(args.ack_path).resolve()) if args.ack_path else "",
        "ack_valid": int(ack_valid),
        "ack_reason": ack_reason,
        "divergent_count": divergent_count,
        "auto_submit_permitted": 0,
        "order_api_called_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "source_files": {
            "stage919_attribution": str(_stage919_attribution_path(args.target_date)),
            "stage920_summary": str(_stage920_summary_path(args.target_date)),
            "readonly_positions": str(READONLY_POSITIONS_PATH),
        },
        "judgement": {
            "overfit_before": "No. Stage924 is a recovery gate for execution state, not a strategy change.",
            "continue_before": "Yes. Full automation needs a safe re-entry gate after manual account intervention.",
            "overfit_after": "No. The gate does not feed back into C9 signals or parameters.",
            "continue_after": "Yes. Resolve the external broker/shadow divergence, then rerun the evidence chain.",
        },
    }
    decision.to_csv(paths["decision_csv"], index=False, encoding="utf-8-sig")
    paths["ack_template_json"].write_text(json.dumps(template, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, decision), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
