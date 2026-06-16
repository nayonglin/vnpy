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
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage920_official_live_account_sync_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage920_official_live_account_sync_gate"
STAGE919_MODEL_TAG = "stage919_official_live_reconcile_attribution_audit_v1"
STAGE919_PREFIX = "qmt_roll_stage919_official_live_reconcile_attribution_audit"

ALLOWED_ACK_ACTIONS = {
    "manual_accept_broker_as_start_baseline",
    "manual_flatten_or_reduce_then_refresh",
    "manual_keep_fail_closed",
}


def _date_key(target_date: str) -> str:
    return target_date.replace("-", "") if target_date else "latest"


def _paths(target_date: str) -> dict[str, Path]:
    date_key = _date_key(target_date)
    return {
        "state_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_{date_key}_{MODEL_TAG}.csv",
        "ack_template_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_ack_template_{date_key}_{MODEL_TAG}.json",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _stage919_attribution_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE919_PREFIX}_attribution_{_date_key(target_date)}_{STAGE919_MODEL_TAG}.csv"


def _stage919_summary_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE919_PREFIX}_summary_{_date_key(target_date)}_{STAGE919_MODEL_TAG}.json"


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


def _ack_template(target_date: str, fingerprint: str, attribution: pd.DataFrame) -> dict[str, Any]:
    return {
        "purpose": "manual account sync acknowledgement template",
        "target_date": target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "account_sync_fingerprint": fingerprint,
        "operator_acknowledged": False,
        "ack_action": "manual_keep_fail_closed",
        "allowed_ack_actions": sorted(ALLOWED_ACK_ACTIONS),
        "operator": "",
        "acknowledged_at": "",
        "notes": "",
        "current_attribution_rows": attribution.to_dict(orient="records"),
        "warning": (
            "Do not edit this into a valid acknowledgement unless the real broker position origin "
            "has been manually confirmed outside the unattended automation loop."
        ),
    }


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
    if str(ack.get("ack_action", "")) not in ALLOWED_ACK_ACTIONS:
        return False, "ack_action_not_allowed"
    if not str(ack.get("operator", "")).strip():
        return False, "ack_operator_missing"
    if not str(ack.get("acknowledged_at", "")).strip():
        return False, "ack_time_missing"
    return True, "ack_valid"


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].to_markdown(index=False)


def _build_report(summary: dict[str, Any], state: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage920 Official Live Account Sync Gate",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Official live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- Target date: `{summary['target_date']}`",
            f"- Account sync status: `{summary['account_sync_status']}`",
            f"- Divergent count: `{summary['divergent_count']}`",
            f"- Ack valid: `{summary['ack_valid']}`",
            f"- Auto submit permitted: `{summary['auto_submit_permitted']}`",
            f"- Order API calls: `{summary['order_api_called_count']}`",
            "",
            "## State",
            "",
            _to_markdown(
                state,
                [
                    "vt_symbol",
                    "direction",
                    "shadow_volume",
                    "broker_volume",
                    "delta_broker_minus_shadow",
                    "broker_avg_price",
                    "c9_open_trade_price",
                    "account_origin_status",
                    "sync_decision",
                ],
            ),
            "",
            "## Notes",
            "",
            "- Stage920 is a fail-closed account genesis gate. It does not connect CTP, submit orders, or cancel orders.",
            "- The generated acknowledgement template is evidence, not permission. It must be copied and completed deliberately before this gate can validate it.",
            "- Even a valid acknowledgement does not submit orders; it only records the manual account-sync decision for later gates.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live account sync gate.")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--ack-path", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)
    attribution = _read_csv_maybe(_stage919_attribution_path(args.target_date))
    stage919_summary = _read_json_maybe(_stage919_summary_path(args.target_date))
    attribution_aligned = stage919_summary.get("attribution_status") == "reconcile_attribution_aligned"
    fingerprint = _fingerprint(attribution, args.target_date)
    ack = _read_json_maybe(args.ack_path)
    ack_valid, ack_reason = _validate_ack(ack, target_date=args.target_date, fingerprint=fingerprint)

    attribution_missing = attribution.empty and not attribution_aligned
    divergent_count = 0
    if not attribution_missing and not attribution.empty:
        divergent_count = int(
            (
                pd.to_numeric(attribution.get("delta_broker_minus_shadow"), errors="coerce")
                .fillna(0.0)
                .abs()
                > 1e-9
            ).sum()
        )
    if attribution_missing:
        account_sync_status = "account_sync_attribution_missing_fail_closed"
    elif divergent_count == 0:
        account_sync_status = "account_sync_aligned_auto_progress_allowed"
    elif ack_valid:
        account_sync_status = "account_sync_manual_ack_recorded_fail_closed"
    elif args.ack_path:
        account_sync_status = "account_sync_ack_invalid_fail_closed"
    else:
        account_sync_status = "account_sync_operator_ack_required_fail_closed"

    state = attribution.copy()
    if state.empty:
        state = pd.DataFrame(
            [
                {
                    "target_date": args.target_date,
                    "sync_decision": account_sync_status,
                    "account_sync_fingerprint": fingerprint,
                }
            ]
        )
    else:
        state["sync_decision"] = account_sync_status
        state["account_sync_fingerprint"] = fingerprint
        state["ack_valid"] = int(ack_valid)
        state["ack_reason"] = ack_reason

    template = _ack_template(args.target_date, fingerprint, attribution)
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "account_sync_status": account_sync_status,
        "account_sync_fingerprint": fingerprint,
        "divergent_count": divergent_count,
        "ack_path": str(Path(args.ack_path).resolve()) if args.ack_path else "",
        "ack_valid": int(ack_valid),
        "ack_reason": ack_reason,
        "auto_submit_permitted": 0,
        "order_api_called_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "source_files": {
            "stage919_attribution": str(_stage919_attribution_path(args.target_date)),
            "stage919_summary": str(_stage919_summary_path(args.target_date)),
        },
        "judgement": {
            "overfit_before": "No. Stage920 is an account-sync execution gate, not a strategy parameter.",
            "continue_before": "Yes. Fully automatic execution requires an auditable account genesis state.",
            "overfit_after": "No. The gate only records broker/shadow sync status and keeps order APIs at zero.",
            "continue_after": "Yes. Current account divergence still requires manual origin confirmation.",
        },
    }
    state.to_csv(paths["state_csv"], index=False, encoding="utf-8-sig")
    paths["ack_template_json"].write_text(json.dumps(template, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, state), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
