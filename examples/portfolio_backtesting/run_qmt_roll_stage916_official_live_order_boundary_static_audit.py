from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from run_qmt_alignment_backtest import OUTPUT_DIR


PROJECT_DIR = Path(__file__).resolve().parent
MODEL_TAG = "stage916_official_live_order_boundary_static_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage916_official_live_order_boundary_static_audit"

PHASE_D_FILES = [
    "qmt_roll_official_live_phase_d_config.py",
    "qmt_roll_phase_d_submit_adapter.py",
    "run_qmt_roll_stage902_official_live_phase_d_readiness_gate.py",
    "run_qmt_roll_stage903_official_live_phase_d_controller.py",
    "run_qmt_roll_stage904_official_live_c9_intraday_monitor.py",
    "run_qmt_roll_stage905_official_live_executor_dry_run.py",
    "run_qmt_roll_stage906_official_live_reconciliation_worker.py",
    "run_qmt_roll_stage907_official_live_readonly_refresh_gate.py",
    "run_qmt_roll_stage908_official_live_submit_adapter_contract.py",
    "run_qmt_roll_stage909_official_live_shadow_refresh_gate.py",
    "run_qmt_roll_stage910_official_live_phase_d_health_check.py",
    "run_qmt_roll_stage911_official_live_kill_switch_manager.py",
    "run_qmt_roll_stage912_official_live_phase_d_acceptance_suite.py",
    "run_qmt_roll_stage913_official_live_phase_d_completion_audit.py",
    "run_qmt_roll_stage914_official_live_ctp_runtime_preflight.py",
    "run_qmt_roll_stage915_official_live_submit_adapter_boundary_suite.py",
    "run_qmt_roll_stage917_official_live_mock_broker_integration.py",
    "run_qmt_roll_stage918_official_live_reconcile_policy_audit.py",
    "run_qmt_roll_stage919_official_live_reconcile_attribution_audit.py",
    "run_qmt_roll_stage920_official_live_account_sync_gate.py",
    "run_qmt_roll_stage921_official_live_scheduler_audit.py",
    "run_qmt_roll_stage922_official_live_target_date_resolver.py",
    "run_qmt_roll_stage923_official_live_fail_closed_incident.py",
    "run_qmt_roll_stage924_official_live_account_recovery_gate.py",
    "run_qmt_roll_stage925_official_live_account_recovery_ack_suite.py",
    "run_qmt_roll_stage926_official_live_aligned_idle_integration.py",
    "run_qmt_roll_stage927_official_live_real_submit_arming_gate.py",
]

SEND_PATTERN = re.compile(r"\bsend_order\s*\(")
CANCEL_PATTERN = re.compile(r"\bcancel_order\s*\(")
REQ_INSERT_PATTERN = re.compile(r"\bReqOrderInsert\b")
REQ_ACTION_PATTERN = re.compile(r"\bReqOrderAction\b")

ALLOWED_SEND_CONTEXTS = {
    "qmt_roll_phase_d_submit_adapter.py": ("main_engine.send_order",),
    "run_qmt_roll_stage915_official_live_submit_adapter_boundary_suite.py": ("def send_order",),
}


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "matches_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_matches_{run_id}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
    }


def _line_allowed(filename: str, line: str, kind: str) -> bool:
    if kind != "send_order":
        return False
    allowed_snippets = ALLOWED_SEND_CONTEXTS.get(filename, ())
    return any(snippet in line for snippet in allowed_snippets)


def _scan_file(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    filename = path.name
    if not path.exists():
        return [
            {
                "file": filename,
                "line_number": 0,
                "kind": "file_missing",
                "line": "",
                "allowed": 0,
                "blocker": "phase_d_file_missing",
            }
        ]
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        checks = [
            ("send_order", SEND_PATTERN.search(line)),
            ("cancel_order", CANCEL_PATTERN.search(line)),
            ("ReqOrderInsert", REQ_INSERT_PATTERN.search(line)),
            ("ReqOrderAction", REQ_ACTION_PATTERN.search(line)),
        ]
        for kind, matched in checks:
            if not matched:
                continue
            allowed = _line_allowed(filename, line, kind)
            rows.append(
                {
                    "file": filename,
                    "line_number": idx,
                    "kind": kind,
                    "line": line.strip(),
                    "allowed": int(allowed),
                    "blocker": "" if allowed else "disallowed_order_boundary_reference",
                }
            )
    return rows


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].to_markdown(index=False)


def _build_report(summary: dict[str, Any], matches: pd.DataFrame) -> str:
    disallowed = matches[matches["allowed"].eq(0)] if not matches.empty else pd.DataFrame()
    return "\n".join(
        [
            "# Stage916 Official Live Order Boundary Static Audit",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Official live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- Static audit status: `{summary['static_audit_status']}`",
            f"- Allowed send_order references: `{summary['allowed_send_order_reference_count']}`",
            f"- Disallowed references: `{summary['disallowed_reference_count']}`",
            "",
            "## Disallowed References",
            "",
            _to_markdown(disallowed, ["file", "line_number", "kind", "line", "blocker"]),
            "",
            "## All Matches",
            "",
            _to_markdown(matches, ["file", "line_number", "kind", "allowed", "line"]),
            "",
            "## Notes",
            "",
            "- Stage916 is static only. It does not import gateways, connect CTP, submit, or cancel orders.",
            "- The only allowed real order boundary is `qmt_roll_phase_d_submit_adapter.py`; Stage915 is allowed only for FakeMainEngine.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Static order boundary audit for official Phase D files.")
    parser.add_argument("--target-date", default="2026-06-12")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    rows: list[dict[str, Any]] = []
    for filename in PHASE_D_FILES:
        rows.extend(_scan_file(PROJECT_DIR / filename))
    matches = pd.DataFrame(rows)
    disallowed_count = int((matches["allowed"].eq(0)).sum()) if not matches.empty else 0
    allowed_send_count = int((matches["kind"].eq("send_order") & matches["allowed"].eq(1)).sum()) if not matches.empty else 0
    static_status = (
        "phase_d_order_boundary_static_audit_passed"
        if disallowed_count == 0 and allowed_send_count == 2
        else "phase_d_order_boundary_static_audit_failed"
    )
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "static_audit_status": static_status,
        "scanned_file_count": len(PHASE_D_FILES),
        "match_count": int(len(matches)),
        "allowed_send_order_reference_count": allowed_send_count,
        "disallowed_reference_count": disallowed_count,
        "order_api_called_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "No. This is a static execution-boundary audit.",
            "continue_before": "Yes. Full automation needs a single auditable order boundary.",
            "overfit_after": "No. Static matches do not affect strategy signals.",
            "continue_after": "Yes. Keep this audit in acceptance before any real adapter enablement.",
        },
    }
    matches.to_csv(paths["matches_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, matches), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
