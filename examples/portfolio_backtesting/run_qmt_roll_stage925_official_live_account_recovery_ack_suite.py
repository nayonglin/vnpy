from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_stage924_official_live_account_recovery_gate import (
    READONLY_POSITIONS_PATH,
    _decision_status,
    _fingerprint,
    _read_csv_maybe,
    _read_json_maybe,
    _stage919_attribution_path,
    _stage920_summary_path,
    _to_int,
    _validate_ack,
)


MODEL_TAG = "stage925_official_live_account_recovery_ack_suite_v1"
OUTPUT_PREFIX = "qmt_roll_stage925_official_live_account_recovery_ack_suite"


def _date_key(target_date: str) -> str:
    return target_date.replace("-", "") if target_date else "latest"


def _paths(target_date: str) -> dict[str, Path]:
    date_key = _date_key(target_date)
    return {
        "cases_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_cases_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _base_ack(target_date: str, fingerprint: str, recovery_action: str) -> dict[str, Any]:
    return {
        "target_date": target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "account_sync_fingerprint": fingerprint,
        "operator_acknowledged": True,
        "recovery_action": recovery_action,
        "operator": "stage925_ack_suite",
        "acknowledged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notes": "Stage925 synthetic acknowledgement. Does not submit orders.",
    }


def _nonempty_positions_like(frame: pd.DataFrame) -> pd.DataFrame:
    if not frame.empty:
        return frame.copy()
    return pd.DataFrame(
        [
            {
                "vt_symbol": "STAGE925.MOCK",
                "direction": "long",
                "volume": 1,
                "price": 1.0,
                "pnl": 0.0,
            }
        ]
    )


def _expected_operator_required(status: str) -> int:
    if status in {
        "account_recovery_not_required_aligned",
        "account_recovery_manual_action_done_rerun_required",
    }:
        return 0
    return 1


def _case_row(
    *,
    case_id: str,
    target_date: str,
    fingerprint: str,
    ack: dict[str, Any],
    divergent_count: int,
    broker_positions: pd.DataFrame,
    expected_ack_valid: bool,
    expected_ack_reason: str,
    expected_status: str,
) -> dict[str, Any]:
    ack_valid, ack_reason = _validate_ack(ack, target_date=target_date, fingerprint=fingerprint)
    recovery_status, recovery_reason, operator_action_required = _decision_status(
        ack_valid=ack_valid,
        ack=ack,
        divergent_count=divergent_count,
        broker_positions=broker_positions,
    )
    expected_operator_required = _expected_operator_required(expected_status)
    passed = (
        ack_valid == expected_ack_valid
        and ack_reason == expected_ack_reason
        and recovery_status == expected_status
        and operator_action_required == expected_operator_required
    )
    return {
        "case_id": case_id,
        "passed": int(passed),
        "ack_valid": int(ack_valid),
        "expected_ack_valid": int(expected_ack_valid),
        "ack_reason": ack_reason,
        "expected_ack_reason": expected_ack_reason,
        "recovery_status": recovery_status,
        "expected_recovery_status": expected_status,
        "recovery_reason": recovery_reason,
        "operator_action_required": operator_action_required,
        "expected_operator_action_required": expected_operator_required,
        "divergent_count": divergent_count,
        "broker_positions_empty": int(broker_positions.empty),
        "auto_submit_permitted": 0,
        "order_api_called_count": 0,
    }


def _build_cases(target_date: str, fingerprint: str, divergent_count: int, broker_positions: pd.DataFrame) -> pd.DataFrame:
    nonempty_positions = _nonempty_positions_like(broker_positions)
    empty_positions = nonempty_positions.iloc[0:0].copy()
    valid_keep = _base_ack(target_date, fingerprint, "manual_keep_fail_closed")
    valid_flatten = _base_ack(target_date, fingerprint, "manual_flatten_or_reduce_then_refresh")
    valid_non_strategy = _base_ack(target_date, fingerprint, "manual_accept_broker_as_non_strategy_position")
    invalid_ack_status = (
        "account_recovery_not_required_aligned"
        if divergent_count == 0
        else "account_recovery_ack_required_fail_closed"
    )

    case_specs: list[dict[str, Any]] = [
        {
            "case_id": "missing_ack",
            "ack": {},
            "divergent_count": divergent_count,
            "broker_positions": broker_positions,
            "expected_ack_valid": False,
            "expected_ack_reason": "ack_missing",
            "expected_status": invalid_ack_status,
        },
        {
            "case_id": "wrong_target_date",
            "ack": {**valid_keep, "target_date": "1900-01-01"},
            "divergent_count": divergent_count,
            "broker_positions": broker_positions,
            "expected_ack_valid": False,
            "expected_ack_reason": "ack_target_date_mismatch",
            "expected_status": invalid_ack_status,
        },
        {
            "case_id": "wrong_live_version",
            "ack": {**valid_keep, "official_live_version": "wrong_live_version"},
            "divergent_count": divergent_count,
            "broker_positions": broker_positions,
            "expected_ack_valid": False,
            "expected_ack_reason": "ack_live_version_mismatch",
            "expected_status": invalid_ack_status,
        },
        {
            "case_id": "wrong_fingerprint",
            "ack": {**valid_keep, "account_sync_fingerprint": "bad_fingerprint"},
            "divergent_count": divergent_count,
            "broker_positions": broker_positions,
            "expected_ack_valid": False,
            "expected_ack_reason": "ack_fingerprint_mismatch",
            "expected_status": invalid_ack_status,
        },
        {
            "case_id": "operator_not_acknowledged",
            "ack": {**valid_keep, "operator_acknowledged": False},
            "divergent_count": divergent_count,
            "broker_positions": broker_positions,
            "expected_ack_valid": False,
            "expected_ack_reason": "operator_acknowledged_not_true",
            "expected_status": invalid_ack_status,
        },
        {
            "case_id": "disallowed_recovery_action",
            "ack": {**valid_keep, "recovery_action": "auto_flatten_and_submit"},
            "divergent_count": divergent_count,
            "broker_positions": broker_positions,
            "expected_ack_valid": False,
            "expected_ack_reason": "recovery_action_not_allowed",
            "expected_status": invalid_ack_status,
        },
        {
            "case_id": "operator_missing",
            "ack": {**valid_keep, "operator": ""},
            "divergent_count": divergent_count,
            "broker_positions": broker_positions,
            "expected_ack_valid": False,
            "expected_ack_reason": "ack_operator_missing",
            "expected_status": invalid_ack_status,
        },
        {
            "case_id": "ack_time_missing",
            "ack": {**valid_keep, "acknowledged_at": ""},
            "divergent_count": divergent_count,
            "broker_positions": broker_positions,
            "expected_ack_valid": False,
            "expected_ack_reason": "ack_time_missing",
            "expected_status": invalid_ack_status,
        },
        {
            "case_id": "valid_keep_fail_closed",
            "ack": valid_keep,
            "divergent_count": max(1, divergent_count),
            "broker_positions": nonempty_positions,
            "expected_ack_valid": True,
            "expected_ack_reason": "ack_valid",
            "expected_status": "account_recovery_manual_keep_fail_closed",
        },
        {
            "case_id": "valid_flatten_broker_still_present_fail_closed",
            "ack": valid_flatten,
            "divergent_count": max(1, divergent_count),
            "broker_positions": nonempty_positions,
            "expected_ack_valid": True,
            "expected_ack_reason": "ack_valid",
            "expected_status": "account_recovery_manual_action_pending_fail_closed",
        },
        {
            "case_id": "valid_flatten_broker_empty_rerun_required",
            "ack": valid_flatten,
            "divergent_count": max(1, divergent_count),
            "broker_positions": empty_positions,
            "expected_ack_valid": True,
            "expected_ack_reason": "ack_valid",
            "expected_status": "account_recovery_manual_action_done_rerun_required",
        },
        {
            "case_id": "valid_non_strategy_position_fail_closed",
            "ack": valid_non_strategy,
            "divergent_count": max(1, divergent_count),
            "broker_positions": nonempty_positions,
            "expected_ack_valid": True,
            "expected_ack_reason": "ack_valid",
            "expected_status": "account_recovery_non_strategy_position_ack_recorded_fail_closed",
        },
        {
            "case_id": "aligned_no_recovery_required",
            "ack": {},
            "divergent_count": 0,
            "broker_positions": empty_positions,
            "expected_ack_valid": False,
            "expected_ack_reason": "ack_missing",
            "expected_status": "account_recovery_not_required_aligned",
        },
    ]
    rows = [
        _case_row(
            case_id=str(spec["case_id"]),
            target_date=target_date,
            fingerprint=fingerprint,
            ack=spec["ack"],
            divergent_count=int(spec["divergent_count"]),
            broker_positions=spec["broker_positions"],
            expected_ack_valid=bool(spec["expected_ack_valid"]),
            expected_ack_reason=str(spec["expected_ack_reason"]),
            expected_status=str(spec["expected_status"]),
        )
        for spec in case_specs
    ]
    return pd.DataFrame(rows)


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].to_markdown(index=False)


def _build_report(summary: dict[str, Any], cases: pd.DataFrame) -> str:
    failed = cases[cases["passed"].eq(0)] if not cases.empty else pd.DataFrame()
    return "\n".join(
        [
            "# Stage925 Official Live Account Recovery Ack Suite",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Official live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- Target date: `{summary['target_date']}`",
            f"- Suite status: `{summary['suite_status']}`",
            f"- Passed cases: `{summary['passed_count']}`",
            f"- Failed cases: `{summary['failed_count']}`",
            f"- Auto submit permitted: `{summary['auto_submit_permitted']}`",
            f"- Order API calls: `{summary['order_api_called_count']}`",
            "",
            "## Failed Cases",
            "",
            _to_markdown(
                failed,
                [
                    "case_id",
                    "ack_reason",
                    "expected_ack_reason",
                    "recovery_status",
                    "expected_recovery_status",
                    "operator_action_required",
                    "expected_operator_action_required",
                ],
            ),
            "",
            "## All Cases",
            "",
            _to_markdown(
                cases,
                [
                    "case_id",
                    "passed",
                    "ack_valid",
                    "ack_reason",
                    "recovery_status",
                    "operator_action_required",
                    "broker_positions_empty",
                ],
            ),
            "",
            "## Notes",
            "",
            "- Stage925 does not connect CTP, mutate broker files, submit orders, or cancel orders.",
            "- It validates Stage924 acknowledgement semantics in-process, including invalid acknowledgement rejection.",
            "- A valid acknowledgement never permits unattended live submit by itself.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage924 account recovery acknowledgement regression suite.")
    parser.add_argument("--target-date", required=True)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)
    attribution = _read_csv_maybe(_stage919_attribution_path(args.target_date))
    stage920 = _read_json_maybe(_stage920_summary_path(args.target_date))
    broker_positions = _read_csv_maybe(READONLY_POSITIONS_PATH)
    fingerprint = _fingerprint(attribution, args.target_date)
    divergent_count = (
        int((pd.to_numeric(attribution.get("delta_broker_minus_shadow"), errors="coerce").fillna(0.0).abs() > 1e-9).sum())
        if not attribution.empty
        else _to_int(stage920.get("divergent_count"), 0)
    )
    cases = _build_cases(args.target_date, fingerprint, divergent_count, broker_positions)
    failed = cases[cases["passed"].eq(0)] if not cases.empty else pd.DataFrame()
    order_api_called = int(cases.get("order_api_called_count", pd.Series(dtype=int)).max() or 0) if not cases.empty else 0
    auto_submit_permitted = int(cases.get("auto_submit_permitted", pd.Series(dtype=int)).max() or 0) if not cases.empty else 0
    suite_status = (
        "account_recovery_ack_suite_passed_fail_closed"
        if failed.empty and order_api_called == 0 and auto_submit_permitted == 0
        else "account_recovery_ack_suite_failed"
    )
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "suite_status": suite_status,
        "case_count": int(len(cases)),
        "passed_count": int(cases["passed"].sum()) if not cases.empty else 0,
        "failed_count": int(len(failed)),
        "current_divergent_count": int(divergent_count),
        "current_broker_position_rows": int(len(broker_positions)),
        "account_sync_fingerprint": fingerprint,
        "auto_submit_permitted": auto_submit_permitted,
        "order_api_called_count": order_api_called,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "source_files": {
            "stage919_attribution": str(_stage919_attribution_path(args.target_date)),
            "stage920_summary": str(_stage920_summary_path(args.target_date)),
            "readonly_positions": str(READONLY_POSITIONS_PATH),
        },
        "judgement": {
            "overfit_before": "No. Stage925 is an execution recovery gate regression suite.",
            "continue_before": "Yes. Full automation needs invalid recovery acknowledgements to remain fail-closed.",
            "overfit_after": "No. Ack cases do not feed back into C9 signals or parameters.",
            "continue_after": "Yes. Broker/shadow reconciliation still must align before live submit can be proven.",
        },
    }
    cases.to_csv(paths["cases_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, cases), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
