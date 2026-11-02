from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage929_official_live_15w_timed_cycle as stage929  # noqa: E402


def test_stage929_early_ai_preflight_passes_explicit_ready_time(tmp_path: Path) -> None:
    args = argparse.Namespace(ai_pool_preflight_mode="check", ai_pool_timeout_seconds=30,
                              ai_pool_data_ready_time="15:10")
    completed = stage929.subprocess.CompletedProcess([], 0, stdout=json.dumps({
        "automation_status": "monthly_ai_pool_already_current", "order_api_called_count": 0,
    }))
    with patch.object(stage929.subprocess, "run", return_value=completed) as run:
        stage929._run_stage935_preflight(args, tmp_path / "commands.log")
    command = run.call_args.args[0]
    assert command[command.index("--data-ready-time") + 1] == "15:10"


@pytest.mark.parametrize("ready,age,limit", [(0,0,300),(1,900,300),(1,0,0),(1,None,300)])
def test_postclose_old_or_missing_account_cannot_claim_no_action(ready, age, limit) -> None:
    wrapper = {
        "phase": "post-close", "target_date": "2026-10-19", "ai_pool_preflight": {},
        "account_snapshot": {"balance": 123456, "nonzero_position_rows": 0},
        "signal_details": [], "blocked_candidate_details": [],
        "execution_consistency_audit": {"stage906_broker_snapshot_ready": ready,
            "stage906_readonly_snapshot_age_seconds": age,
            "stage906_max_snapshot_age_seconds": limit},
    }
    stage903 = {"pending_order_count": 0,"order_api_called_count": 0,"stage905_ready_count": 0}
    with patch.object(stage929, "send_official_live_email_notification", return_value={}) as send:
        stage929._send_report_email({"report_md":Path("report.md"),"summary_json":Path("summary.json")},
                                   wrapper, stage903, policy="always")
    body = send.call_args.kwargs["body"]
    assert "账户对账未就绪" in body
    assert "没有需要自动执行的开仓或平仓指令" not in body
    assert "123456" not in body


def test_postclose_fresh_validated_account_is_still_displayed() -> None:
    wrapper = {"phase":"post-close", "target_date":"2026-10-19", "signal_details":[],
        "blocked_candidate_details":[], "account_snapshot":{"balance":123456},
        "execution_consistency_audit":{"stage906_broker_snapshot_ready":1,
            "stage906_readonly_snapshot_age_seconds":30,"stage906_max_snapshot_age_seconds":300}}
    with patch.object(stage929, "send_official_live_email_notification", return_value={}) as send:
        stage929._send_report_email({"report_md":Path("report.md"),"summary_json":Path("summary.json")},
                                   wrapper, {"order_api_called_count":0}, policy="always")
    assert "账户对账未就绪" not in send.call_args.kwargs["body"]
    assert "123456" in send.call_args.kwargs["body"]


@pytest.mark.parametrize("age_fields", [{}, {"readonly_snapshot_age_seconds":None},
                                      {"readonly_snapshot_age_seconds":"invalid"}])
def test_postclose_raw_summary_missing_age_stays_unknown_through_email(age_fields) -> None:
    raw = {"broker_snapshot_ready":1, "max_snapshot_age_seconds":300, **age_fields}
    wrapper = {"phase":"post-close", "target_date":"2026-10-19", "signal_details":[],
               "blocked_candidate_details":[], "account_snapshot":{"balance":123456}}
    stage903 = {"target_date":"2026-10-19", "order_api_called_count":0}
    with (
        patch.object(stage929, "_read_json", side_effect=lambda path:
                     raw if path == stage929._stage906_summary_path("2026-10-19") else {}),
        patch.object(stage929, "_read_csv_maybe", return_value=pd.DataFrame()),
        patch.object(stage929, "send_official_live_email_notification", return_value={}) as send,
    ):
        audit = stage929._build_execution_consistency_audit(wrapper, stage903)
        wrapper["execution_consistency_audit"] = audit
        stage929._send_report_email({"report_md":Path("report.md"),"summary_json":Path("summary.json")},
                                   wrapper, stage903, policy="always")
    assert audit["stage906_readonly_snapshot_age_seconds"] is None
    json.dumps(audit, allow_nan=False)
    assert "账户对账未就绪" in send.call_args.kwargs["body"]
    assert "123456" not in send.call_args.kwargs["body"]


def test_stage929_pool_threshold_uses_tenth_model_rank() -> None:
    pool = pd.DataFrame(
        {
            "strategy": ["ai_top10_plus_fu_official_live_v1"] * 11,
            "eval_date": ["2026-07-31"] * 11,
            "product_vt_symbol": [
                *[f"p{index}.TEST" for index in range(1, 11)],
                "fu.SHFE",
            ],
            "ai_rank": list(range(1, 12)),
            "predicted_product_suitability_probability": [
                1.0 - index * 0.01 for index in range(1, 12)
            ],
            "source_score_type": ["stage182_live"] * 11,
        }
    )

    threshold, product = stage929._pool_threshold(pool)

    assert threshold == 0.90
    assert product == "p10.TEST"


def test_stage929_explains_ai_selection_from_active_immutable_material() -> None:
    parts = stage929.STAGE182_LATEST_POOL_PATH.parts

    assert "official_strategy_materials" in parts
    assert "backtest_outputs" not in parts
    assert stage929.STAGE182_LATEST_POOL_PATH.is_file()


def test_stage929_pool_threshold_does_not_fallback_when_rank_ten_is_missing() -> None:
    pool = pd.DataFrame(
        {
            "product_vt_symbol": [f"p{index}.TEST" for index in range(1, 12)],
            "ai_rank": [*range(1, 10), 11, 12],
            "predicted_product_suitability_probability": [
                1.0 - index * 0.01 for index in range(1, 12)
            ],
        }
    )

    with pytest.raises(RuntimeError, match="official_ai_latest_pool_contract_invalid"):
        stage929._pool_threshold(pool)


def test_stage929_monthly_candidate_update_blocks_before_stage903(tmp_path: Path) -> None:
    args = argparse.Namespace(
        ai_pool_preflight_mode="run",
        ai_pool_timeout_seconds=30,
    )
    completed = stage929.subprocess.CompletedProcess(
        args=["stage935"],
        returncode=0,
        stdout=json.dumps(
            {
                "automation_status": "monthly_ai_pool_updated",
                "material_publication_status": "publication_required",
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            }
        ),
        stderr="",
    )

    with patch.object(stage929.subprocess, "run", return_value=completed):
        result = stage929._run_stage935_preflight(args, tmp_path / "commands.log")

    assert result["preflight_status"] == "ai_pool_preflight_blocked"
    assert result["allowed_to_continue"] == 0
    assert result["automation_status"] == "monthly_ai_pool_updated"


def test_stage929_execution_audit_rejects_unpublished_monthly_candidate() -> None:
    wrapper = {
        "target_date": "2026-08-28",
        "ai_pool_preflight": {
            "automation_status": "monthly_ai_pool_updated",
            "expected_eval_date": "2026-08-31",
            "current_eval_date": "2026-08-31",
        },
    }
    stage901_summary = {
        "analysis_end": "2026-08-28",
        "pending_order_count": 0,
        "minute_audit": {"source_exists": True, "loaded_symbol_count": 1},
    }

    def read_json(path: Path) -> dict[str, object]:
        if path == stage929.OFFICIAL_LIVE_SUMMARY_PATH:
            return stage901_summary
        if path == stage929._stage906_summary_path("2026-08-28"):
            return {"reconciliation_status": "reconcile_aligned"}
        return {}

    with (
        patch.object(stage929, "_read_json", side_effect=read_json),
        patch.object(stage929, "_read_csv_maybe", return_value=pd.DataFrame()),
    ):
        audit = stage929._build_execution_consistency_audit(
            wrapper,
            {"target_date": "2026-08-28", "pending_order_count": 0},
        )

    assert audit["ai_pool_consistency"] == "否"
