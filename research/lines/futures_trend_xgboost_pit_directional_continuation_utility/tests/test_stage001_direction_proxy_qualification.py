from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import stat
import sys
import threading

import numpy as np
import pandas as pd
import pytest


LINE_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = LINE_DIR.parents[2]
TOOLS_DIR = LINE_DIR / "tools"
EXAMPLES_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (TOOLS_DIR, EXAMPLES_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import stage001_direction_proxy_qualification as qualification_module  # noqa: E402
from stage001_direction_proxy_qualification import (  # noqa: E402
    QualificationContract,
    _stream_query_evaluations,
    run_fixture_qualification,
    run_qualification,
    verify_bundle,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_source(path: Path, close: np.ndarray) -> None:
    dates = pd.bdate_range("2024-01-02", periods=len(close))
    open_ = close - 0.1
    frame = pd.DataFrame(
        {
            "trade_date": dates,
            "datetime": dates,
            "open": open_,
            "high": np.maximum(open_, close) + 0.02,
            "low": np.minimum(open_, close) - 0.02,
            "close": close,
            "volume": 100,
            "open_oi": 100,
            "close_oi": 100,
        }
    )
    future = pd.DataFrame(
        [
            {
                "trade_date": dates[-1] + pd.offsets.BDay(1),
                "datetime": dates[-1] + pd.offsets.BDay(1),
                "open": "DO_NOT_PARSE",
                "high": "DO_NOT_PARSE",
                "low": "DO_NOT_PARSE",
                "close": "DO_NOT_PARSE",
                "volume": 0,
                "open_oi": 0,
                "close_oi": 0,
            }
        ]
    )
    pd.concat([frame, future], ignore_index=True).to_csv(path, index=False)


def _fixture(tmp_path: Path) -> dict[str, object]:
    dates = pd.bdate_range("2024-01-02", periods=46)
    development_date = dates[-2].strftime("%Y-%m-%d")
    inference_date = dates[-1].strftime("%Y-%m-%d")
    panel = pd.DataFrame(
        [
            {"query_date": date, "product_vt_symbol": product, "main_contract_vt": contract, "feature": 0.5}
            for date in (development_date, inference_date)
            for product, contract in (
                ("rb.SHFE", "rb2405.SHFE"),
                ("zn.SHFE", "zn2405.SHFE"),
                ("fu.SHFE", "fu2405.SHFE"),
            )
        ]
    )
    panel_path = tmp_path / "panel.csv.gz"
    panel.to_csv(panel_path, index=False)

    formal = pd.DataFrame(
        [
            {"test_eval_date": development_date, "product_vt_symbol": "rb.SHFE", "role": "formal_rank10"},
            {"test_eval_date": development_date, "product_vt_symbol": "zn.SHFE", "role": "challenger"},
        ]
    )
    formal_path = tmp_path / "formal.csv"
    formal.to_csv(formal_path, index=False)

    expiry = pd.DataFrame(
        [
            {"query_date": development_date, "product_vt_symbol": product, "main_contract_vt": contract}
            for product, contract in (
                ("rb.SHFE", "rb2405.SHFE"),
                ("zn.SHFE", "zn2405.SHFE"),
                ("fu.SHFE", "fu2405.SHFE"),
            )
        ]
    )
    expiry_path = tmp_path / "expiry.csv.gz"
    expiry.to_csv(expiry_path, index=False)

    rb_path = tmp_path / "rb2405.csv"
    zn_path = tmp_path / "zn2405.csv"
    _write_source(rb_path, np.linspace(100.0, 150.0, len(dates)))
    _write_source(zn_path, np.linspace(150.0, 100.0, len(dates)))
    source_manifest_path = tmp_path / "source_manifest.json"
    source_manifest_path.write_text(
        json.dumps(
            {
                "source_files": [
                    {
                        "tq_symbol": "SHFE.rb2405",
                        "path": str(rb_path),
                        "sha256": _sha256(rb_path),
                        "source_kind": "fixture",
                        "normalised_rows": len(dates),
                    },
                    {
                        "tq_symbol": "SHFE.zn2405",
                        "path": str(zn_path),
                        "sha256": _sha256(zn_path),
                        "source_kind": "fixture",
                        "normalised_rows": len(dates),
                    },
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    metadata_path = tmp_path / "metadata.csv"
    pd.DataFrame(
        [
            {"vt_symbol": "rb.SHFE", "symbol_kind": "product_cont", "price_tick": 1.0, "volume_multiple": 10},
            {"vt_symbol": "zn.SHFE", "symbol_kind": "product_cont", "price_tick": 5.0, "volume_multiple": 5},
        ]
    ).to_csv(metadata_path, index=False)

    contract = QualificationContract(
        expected_panel_rows=6,
        expected_panel_qids=2,
        expected_panel_products=3,
        expected_fixed_fu_rows=2,
        expected_model_rows=4,
        expected_model_qids=2,
        expected_model_products=2,
        expected_qid_width_min=2,
        expected_qid_width_median=2.0,
        expected_qid_width_max=2,
        expected_development_rows=2,
        expected_development_qids=1,
        expected_development_products=2,
        expected_inference_rows=2,
        expected_inference_qids=1,
        expected_formal_action_dates=1,
        expected_formal_development_dates=1,
        expected_formal_inference_dates=0,
        min_observable_per_development_qid=2,
        min_active_development_qids=1,
        required_direction_years=(2024,),
        expected_explicit_cost_products=1,
        expected_fallback_cost_products=1,
        require_runtime_identity=False,
    )
    return {
        "panel_path": panel_path,
        "formal_plan_path": formal_path,
        "source_manifest_path": source_manifest_path,
        "product_metadata_path": metadata_path,
        "expiry_paths_path": expiry_path,
        "contract": contract,
        "rates": {"rb.SHFE": 0.0},
        "slippages": {"rb.SHFE": 1.0},
        "sizes": {"rb.SHFE": 10},
        "priceticks": {"rb.SHFE": 1.0},
    }


def test_runner_builds_pass_bundle_without_future_or_model_access(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    output_dir = tmp_path / "bundle"

    summary = run_fixture_qualification(
        fixture_root=tmp_path,
        output_dir=output_dir,
        **fixture,
    )

    assert summary["decision"] == "stage001_direction_proxy_qualification_pass_allow_label_preregistration_only"
    assert summary["gate_fail_count"] == 0
    assert summary["model_row_count"] == 4
    assert summary["development_row_count"] == 2
    assert summary["inference_only_row_count"] == 2
    assert summary["direction_long_count"] > 0
    assert summary["direction_short_count"] > 0
    assert summary["formula_mismatch_count"] == 0
    assert summary["post_query_bar_usage_count"] == 0
    assert summary["future_ohlc_numeric_parse_count"] == 0
    assert summary["future_ohlc_field_access_count"] == 0
    for key in (
        "future_close_value_read_count",
        "future_return_compute_count",
        "label_generate_count",
        "logistic_fit_count",
        "xgboost_fit_count",
        "model_predict_count",
        "strategy_backtest_count",
        "true_engine_run_count",
        "sealed_holdout_read_count",
        "ctp_call_count",
        "order_api_call_count",
        "production_write_count",
    ):
        assert summary[key] == 0
    audit = pd.read_csv(output_dir / "direction_proxy_audit.csv.gz")
    assert audit["direction_proxy"].notna().all()
    assert set(audit["direction_proxy"].astype(int)) == {-1, 1}
    verification = verify_bundle(output_dir)
    assert verification["error_count"] == 0


def test_runner_fails_closed_when_frozen_observable_width_gate_fails(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    base = fixture["contract"]
    fixture["contract"] = QualificationContract(
        **{
            **base.__dict__,
            "min_observable_per_development_qid": 3,
        }
    )

    summary = run_fixture_qualification(
        fixture_root=tmp_path,
        output_dir=tmp_path / "failed_bundle",
        **fixture,
    )

    assert summary["decision"] == "stage001_direction_proxy_qualification_fail_close_no_future_labels"
    assert summary["gate_fail_count"] >= 1
    assert "development_qid_observable_width" in summary["failed_gates"]
    assert summary["future_close_value_read_count"] == 0
    assert verify_bundle(tmp_path / "failed_bundle")["error_count"] == 0


def test_stream_rejects_nonnumeric_ohlc_on_or_before_query_date(tmp_path: Path) -> None:
    source_path = tmp_path / "invalid_observable.csv"
    source_path.write_text(
        "trade_date,open,high,low,close\n"
        "2024-01-02,100,101,99,100\n"
        "2024-01-03,DO_NOT_PARSE,102,100,101\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="could not convert string to float"):
        _stream_query_evaluations(
            source_path,
            "rb2405.SHFE",
            [pd.Timestamp("2024-01-03")],
        )


def test_production_runner_rejects_caller_supplied_fixture_paths(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)

    with pytest.raises(TypeError, match="unexpected keyword argument 'output_dir'"):
        run_qualification(output_dir=tmp_path / "bypass_bundle", **fixture)


def test_authorization_bindings_reject_file_drift(tmp_path: Path) -> None:
    bound_file = tmp_path / "bound.txt"
    bound_file.write_text("frozen\n", encoding="utf-8")
    payload = {"bound_sha256": {"bound": _sha256(bound_file)}}

    qualification_module._validate_authorization_bindings(
        payload,
        {"bound": bound_file},
    )
    bound_file.write_text("drifted\n", encoding="utf-8")

    with pytest.raises(ValueError, match="authorization_binding_mismatch"):
        qualification_module._validate_authorization_bindings(
            payload,
            {"bound": bound_file},
        )


def test_execution_event_is_exclusive_across_concurrent_consumers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_path = tmp_path / "stage001_execution_event.json"
    monkeypatch.setattr(qualification_module, "EXECUTION_EVENT_PATH", event_path)
    authorization = {
        "line_id": qualification_module.LINE_ID,
        "stage": qualification_module.STAGE,
        "allowed_run_count": 1,
        "nonce": "fixture-nonce",
    }
    worker_count = 8
    barrier = threading.Barrier(worker_count)

    def consume() -> str:
        barrier.wait()
        try:
            qualification_module._consume_execution_lease(authorization)
        except FileExistsError:
            return "already_consumed"
        return "consumed"

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        outcomes = list(pool.map(lambda _index: consume(), range(worker_count)))

    assert outcomes.count("consumed") == 1
    assert outcomes.count("already_consumed") == worker_count - 1
    event = json.loads(event_path.read_text(encoding="utf-8"))
    assert event["status"] == "started"
    assert event["nonce"] == "fixture-nonce"
    assert stat.S_IMODE(event_path.stat().st_mode) == 0o600


def test_execution_exception_is_durably_retained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_path = tmp_path / "stage001_execution_event.json"
    monkeypatch.setattr(qualification_module, "EXECUTION_EVENT_PATH", event_path)
    authorization = {
        "line_id": qualification_module.LINE_ID,
        "stage": qualification_module.STAGE,
        "allowed_run_count": 1,
        "nonce": "failure-nonce",
    }
    lease = qualification_module._consume_execution_lease(authorization)

    qualification_module._record_execution_failure(lease, RuntimeError("fixture failure"))

    event = json.loads(event_path.read_text(encoding="utf-8"))
    assert event["status"] == "failed_exception"
    assert event["error"] == "RuntimeError:fixture failure"
    assert event["nonce"] == lease.nonce
    assert event["lease_id"] == lease.lease_id
    assert event["started_at"] == lease.consumed_at
    assert event["finished_at"]
    assert not list(tmp_path.glob(".stage001_execution_event.json.tmp-*"))


def test_production_runner_rejects_authorization_replay_with_mutated_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_path = tmp_path / "stage001_execution_event.json"
    monkeypatch.setattr(qualification_module, "EXECUTION_EVENT_PATH", event_path)
    authorization = {
        "line_id": qualification_module.LINE_ID,
        "stage": qualification_module.STAGE,
        "allowed_run_count": 1,
        "nonce": "receipt-nonce",
        "bound_sha256": {
            key: _sha256(path)
            for key, path in qualification_module.AUTHORIZATION_BINDING_PATHS.items()
        },
    }
    lease = qualification_module._consume_execution_lease(authorization)
    replay = {**authorization, "tampered_after_lease": True}
    monkeypatch.setattr(
        qualification_module,
        "_run_qualification_core",
        lambda **_kwargs: {"decision": "must_not_run", "gate_fail_count": 0},
    )

    with pytest.raises(ValueError, match="production_execution_lease_mismatch"):
        run_qualification(
            execution_lease=lease,
            authorization_receipt=replay,
        )


def test_production_execution_records_runner_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_path = tmp_path / "stage001_execution_event.json"
    monkeypatch.setattr(qualification_module, "EXECUTION_EVENT_PATH", event_path)
    monkeypatch.setattr(qualification_module, "OUTPUT_DIR", tmp_path / "bundle")
    authorization = {
        "line_id": qualification_module.LINE_ID,
        "stage": qualification_module.STAGE,
        "allowed_run_count": 1,
        "nonce": "runner-failure-nonce",
    }

    def fail_run(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("runner exploded")

    monkeypatch.setattr(qualification_module, "run_qualification", fail_run)

    with pytest.raises(RuntimeError, match="runner exploded"):
        qualification_module._execute_production_qualification(authorization)

    event = json.loads(event_path.read_text(encoding="utf-8"))
    assert event["status"] == "failed_exception"
    assert event["error"] == "RuntimeError:runner exploded"


def test_direct_input_drift_during_run_fails_identity_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    original_normalise = qualification_module._normalise_inputs

    def normalise_then_drift(
        panel_path: Path,
        formal_plan_path: Path,
        expiry_paths_path: Path,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        result = original_normalise(panel_path, formal_plan_path, expiry_paths_path)
        formal_path = Path(formal_plan_path)
        formal_path.write_text(
            formal_path.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )
        return result

    monkeypatch.setattr(qualification_module, "_normalise_inputs", normalise_then_drift)
    output_dir = tmp_path / "drift_bundle"

    summary = run_fixture_qualification(
        fixture_root=tmp_path,
        output_dir=output_dir,
        **fixture,
    )

    assert summary["decision"] == "stage001_direction_proxy_qualification_fail_close_no_future_labels"
    assert "input_identity_contract" in summary["failed_gates"]
    identities = json.loads((output_dir / "input_identities.json").read_text(encoding="utf-8"))
    assert identities["before"]["formal_plan"]["sha256"] != identities["after"]["formal_plan"]["sha256"]
    assert set(identities["drift"]) == {"formal_plan"}
    upstream = json.loads((output_dir / "upstream_verification.json").read_text(encoding="utf-8"))
    assert set(upstream["input_identity_drift"]) == {"formal_plan"}


def test_same_execution_lease_cannot_enter_production_core_concurrently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_path = tmp_path / "stage001_execution_event.json"
    claim_path = tmp_path / "stage001_execution_claim.json"
    monkeypatch.setattr(qualification_module, "EXECUTION_EVENT_PATH", event_path)
    monkeypatch.setattr(qualification_module, "EXECUTION_CLAIM_PATH", claim_path)
    authorization = {
        "line_id": qualification_module.LINE_ID,
        "stage": qualification_module.STAGE,
        "allowed_run_count": 1,
        "nonce": "same-lease-nonce",
        "bound_sha256": {
            key: _sha256(path)
            for key, path in qualification_module.AUTHORIZATION_BINDING_PATHS.items()
        },
    }
    lease = qualification_module._consume_execution_lease(authorization)
    first_entered = threading.Event()
    release_first = threading.Event()
    call_count = 0
    call_count_lock = threading.Lock()

    def controlled_core(**_kwargs: object) -> dict[str, object]:
        nonlocal call_count
        with call_count_lock:
            call_count += 1
            invocation = call_count
        if invocation == 1:
            first_entered.set()
            assert release_first.wait(timeout=10)
        return {"decision": "fixture", "gate_fail_count": 0}

    monkeypatch.setattr(qualification_module, "_run_qualification_core", controlled_core)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            run_qualification,
            execution_lease=lease,
            authorization_receipt=authorization,
        )
        assert first_entered.wait(timeout=10)
        try:
            with pytest.raises(FileExistsError):
                run_qualification(
                    execution_lease=lease,
                    authorization_receipt=authorization,
                )
        finally:
            release_first.set()
        assert first.result(timeout=10)["decision"] == "fixture"

    with pytest.raises(FileExistsError):
        run_qualification(
            execution_lease=lease,
            authorization_receipt=authorization,
        )
    assert call_count == 1
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    assert claim["lease_id"] == lease.lease_id
    assert claim["authorization_digest"] == lease.authorization_digest
    assert stat.S_IMODE(claim_path.stat().st_mode) == 0o600


def test_authorization_binding_drift_after_validation_fails_input_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    bound_file = tmp_path / "authorization_bound.py"
    bound_file.write_text("frozen = True\n", encoding="utf-8")
    bound_sha = _sha256(bound_file)
    event_path = tmp_path / "stage001_execution_event.json"
    claim_path = tmp_path / "stage001_execution_claim.json"
    output_dir = tmp_path / "production_bundle"
    monkeypatch.setattr(qualification_module, "EXECUTION_EVENT_PATH", event_path)
    monkeypatch.setattr(qualification_module, "EXECUTION_CLAIM_PATH", claim_path)
    monkeypatch.setattr(qualification_module, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(qualification_module, "PANEL_PATH", fixture["panel_path"])
    monkeypatch.setattr(qualification_module, "FORMAL_PLAN_PATH", fixture["formal_plan_path"])
    monkeypatch.setattr(qualification_module, "SOURCE_MANIFEST_PATH", fixture["source_manifest_path"])
    monkeypatch.setattr(qualification_module, "PRODUCT_METADATA_PATH", fixture["product_metadata_path"])
    monkeypatch.setattr(qualification_module, "EXPIRY_PATHS_PATH", fixture["expiry_paths_path"])
    monkeypatch.setattr(qualification_module, "PRODUCTION_EXTRA_INPUT_PATHS", {})
    monkeypatch.setattr(
        qualification_module,
        "AUTHORIZATION_BINDING_PATHS",
        {"bound": bound_file},
    )
    monkeypatch.setattr(
        qualification_module,
        "EXPECTED_INPUT_SHA256",
        {
            "panel": _sha256(fixture["panel_path"]),
            "formal_plan": _sha256(fixture["formal_plan_path"]),
            "source_manifest": _sha256(fixture["source_manifest_path"]),
            "product_metadata": _sha256(fixture["product_metadata_path"]),
            "expiry_paths": _sha256(fixture["expiry_paths_path"]),
        },
    )
    authorization = {
        "line_id": qualification_module.LINE_ID,
        "stage": qualification_module.STAGE,
        "allowed_run_count": 1,
        "nonce": "post-validation-drift",
        "bound_sha256": {"bound": bound_sha},
    }
    lease = qualification_module._consume_execution_lease(authorization)
    original_claim = qualification_module._claim_execution_lease

    def claim_then_drift(active_lease: object) -> dict[str, object]:
        claim = original_claim(active_lease)
        bound_file.write_text("frozen = False\n", encoding="utf-8")
        return claim

    monkeypatch.setattr(qualification_module, "_claim_execution_lease", claim_then_drift)

    summary = run_qualification(
        execution_lease=lease,
        authorization_receipt=authorization,
    )

    identity_gate = next(
        gate for gate in summary["gates"] if gate["gate"] == "input_identity_contract"
    )
    assert identity_gate["passed"] is False
    mismatches = identity_gate["observed"]["expected_sha_mismatches"]
    assert mismatches["authorization_bound"]["expected"] == bound_sha
    assert mismatches["authorization_bound"]["actual"] == _sha256(bound_file)
