from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_phase_d_submit_adapter import (
    PHASE_D_SUBMIT_CONFIRM_TEXT,
    PhaseDSubmitGate,
    submit_phase_d_orders,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage915_official_live_submit_adapter_boundary_suite_v1"
OUTPUT_PREFIX = "qmt_roll_stage915_official_live_submit_adapter_boundary_suite"


class FakeMainEngine:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send_order(self, req: Any, gateway_name: str) -> str:
        self.calls.append(
            {
                "symbol": req.symbol,
                "exchange": req.exchange.value,
                "direction": req.direction.value,
                "offset": req.offset.value,
                "volume": req.volume,
                "price": req.price,
                "reference": req.reference,
                "gateway_name": gateway_name,
            }
        )
        return f"FAKE.{len(self.calls)}"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "checks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{run_id}_{MODEL_TAG}.csv",
        "results_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_results_{run_id}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
    }


def _ready_row() -> dict[str, Any]:
    payload = {
        "symbol": "MA609",
        "exchange": "CZCE",
        "direction": "short",
        "type": "limit",
        "volume": 12,
        "price": 3010,
        "offset": "close",
        "reference": "Stage905PhaseD:BOUNDARY-001",
        "vt_symbol": "MA609.CZCE",
        "gateway_name": "CTP",
    }
    return {
        "intent_id": "BOUNDARY-001",
        "vt_symbol": "MA609.CZCE",
        "order_request_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
    }


def _gate(**kwargs: Any) -> PhaseDSubmitGate:
    defaults = {
        "mode": "live-real",
        "phase_d_ready": True,
        "executor_ready": True,
        "reconciliation_aligned": True,
        "kill_switch_active": False,
        "real_adapter_enabled": True,
        "real_submit_enabled": True,
        "confirm_text": PHASE_D_SUBMIT_CONFIRM_TEXT,
        "allow_real_broker_side_effects": True,
        "max_order_count_per_cycle": 3,
    }
    defaults.update(kwargs)
    return PhaseDSubmitGate(**defaults)


def _case(
    *,
    case_id: str,
    gate: PhaseDSubmitGate,
    main_engine: Any | None,
    expected_status: str,
    expected_send_count: int,
    expected_blocker: str = "",
) -> dict[str, Any]:
    result = submit_phase_d_orders([_ready_row()], gate=gate, main_engine=main_engine)[0]
    observed_send_count = int(result["send_order_api_called"])
    blockers = str(result["submit_blockers"])
    passed = (
        result["submit_status"] == expected_status
        and observed_send_count == expected_send_count
        and (not expected_blocker or expected_blocker in blockers)
    )
    fake_calls = len(main_engine.calls) if isinstance(main_engine, FakeMainEngine) else 0
    return {
        "case_id": case_id,
        "passed": int(passed),
        "submit_status": result["submit_status"],
        "expected_status": expected_status,
        "send_order_api_called": observed_send_count,
        "expected_send_order_api_called": expected_send_count,
        "fake_main_engine_calls": fake_calls,
        "expected_blocker": expected_blocker,
        "observed_blockers": blockers,
        "vt_orderid": result["vt_orderid"],
        "checked_at": result["checked_at"],
    }


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].to_markdown(index=False)


def _build_report(summary: dict[str, Any], results: pd.DataFrame) -> str:
    failed = results[results["passed"].eq(0)]
    return "\n".join(
        [
            "# Stage915 Official Live Submit Adapter Boundary Suite",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Official live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- Boundary status: `{summary['adapter_boundary_status']}`",
            f"- Failed: `{summary['failed_count']}`",
            f"- Fake send_order calls: `{summary['fake_send_order_called_count']}`",
            f"- Real broker order API calls: `{summary['real_broker_order_api_called_count']}`",
            "",
            "## Failed Cases",
            "",
            _to_markdown(failed, ["case_id", "submit_status", "expected_status", "observed_blockers"]),
            "",
            "## All Cases",
            "",
            _to_markdown(
                results,
                [
                    "case_id",
                    "passed",
                    "submit_status",
                    "send_order_api_called",
                    "fake_main_engine_calls",
                    "expected_blocker",
                    "vt_orderid",
                ],
            ),
            "",
            "## Notes",
            "",
            "- Stage915 uses FakeMainEngine only; it does not connect CTP.",
            "- The one positive submit case proves the adapter boundary can call an injected engine, not that live trading is approved.",
            "- Real Stage903 still does not call this adapter and remains fail-closed until broker state and reconciliation pass.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live Phase D submit adapter boundary suite.")
    parser.add_argument("--target-date", default="2026-06-12")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    dry_engine = FakeMainEngine()
    blocked_engine = FakeMainEngine()
    kill_engine = FakeMainEngine()
    live_engine = FakeMainEngine()
    rows = [
        _case(
            case_id="dry_run_never_submits",
            gate=_gate(mode="dry-run", real_adapter_enabled=False, real_submit_enabled=False, confirm_text="", allow_real_broker_side_effects=False),
            main_engine=dry_engine,
            expected_status="dry_run_ready_no_submit",
            expected_send_count=0,
            expected_blocker="mode_not_live_real",
        ),
        _case(
            case_id="live_real_missing_confirmation_blocks",
            gate=_gate(confirm_text=""),
            main_engine=blocked_engine,
            expected_status="blocked",
            expected_send_count=0,
            expected_blocker="live_submit_confirmation_missing",
        ),
        _case(
            case_id="kill_switch_blocks_submit",
            gate=_gate(kill_switch_active=True),
            main_engine=kill_engine,
            expected_status="blocked",
            expected_send_count=0,
            expected_blocker="kill_switch_active",
        ),
        _case(
            case_id="missing_main_engine_blocks_submit",
            gate=_gate(),
            main_engine=None,
            expected_status="blocked",
            expected_send_count=0,
            expected_blocker="main_engine_not_injected",
        ),
        _case(
            case_id="all_gates_pass_fake_submit_once",
            gate=_gate(),
            main_engine=live_engine,
            expected_status="submitted",
            expected_send_count=1,
        ),
    ]
    results = pd.DataFrame(rows)
    failed = results[results["passed"].eq(0)]
    fake_calls = int(results["fake_main_engine_calls"].sum())
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "adapter_boundary_status": "phase_d_submit_adapter_boundary_passed" if failed.empty and fake_calls == 1 else "phase_d_submit_adapter_boundary_failed",
        "case_count": int(len(results)),
        "passed_count": int(results["passed"].sum()),
        "failed_count": int(len(failed)),
        "fake_send_order_called_count": fake_calls,
        "real_broker_order_api_called_count": 0,
        "order_api_called_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "No. This is an execution adapter boundary test, not a strategy rule change.",
            "continue_before": "Yes. Full automation needs a tested submit boundary even before broker enablement.",
            "overfit_after": "No. Fake submit evidence does not change C9 signals.",
            "continue_after": "Yes. The adapter boundary is ready for later live adapter code review, but broker state is still missing.",
        },
    }
    results.to_csv(paths["checks_csv"], index=False, encoding="utf-8-sig")
    results.to_csv(paths["results_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, results), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
