from __future__ import annotations

import errno
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest


LINE_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = LINE_ROOT / "tools/stage001_formal_event_feature_qualification.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "stage001_formal_event_feature_qualification",
        MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def module():
    return _load_module()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authorization(module, files: dict[str, Path]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "stage": module.STAGE,
        "scope": module.AUTHORIZATION_SCOPE,
        "decision": module.REQUIRED_REVIEW_DECISION,
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "bound_files": {
            key: {
                "path": str(path.resolve()),
                "sha256": _sha256(path),
            }
            for key, path in sorted(files.items())
        },
    }


def _patch_execution_paths(module, tmp_path: Path, monkeypatch):
    state_dir = tmp_path / "state"
    final_dir = tmp_path / "artifacts/final"
    failure_dir = tmp_path / "artifacts/failed"
    monkeypatch.setattr(module, "EXECUTION_STATE_DIR", state_dir)
    monkeypatch.setattr(module, "CLAIM_PATH", state_dir / "claim.json")
    monkeypatch.setattr(module, "EXECUTION_EVENT_PATH", state_dir / "event.json")
    monkeypatch.setattr(module, "ARTIFACT_PARENT", tmp_path / "artifacts")
    monkeypatch.setattr(module, "FINAL_DIR", final_dir)
    monkeypatch.setattr(module, "FAILURE_DIR", failure_dir)
    return state_dir, final_dir, failure_dir


def _create_test_execution_event(
    module,
    path: Path,
    *,
    campaign_nonce: str,
    lease_id: str,
) -> dict[str, object]:
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": campaign_nonce,
        "lease_id": lease_id,
        "replay_permitted": False,
    }
    module.create_exclusive_json(path.with_name("claim.json"), claim)
    module.create_execution_event(
        path,
        campaign_nonce=campaign_nonce,
        lease_id=lease_id,
    )
    return claim


def _current_execution_event_document(module, path: Path):
    with module._execution_event_lock(path) as lock_descriptor:
        event, data, name = module._read_current_execution_event(
            path,
            lock_descriptor=lock_descriptor,
        )
    return event, data, path.with_name(name)


def _current_execution_event(module, path: Path) -> dict[str, object]:
    event, _, _ = _current_execution_event_document(module, path)
    return event


def _seed_execution_event_history(
    module,
    path: Path,
    target: dict[str, object],
) -> dict[str, object]:
    target = dict(target)
    with module._execution_event_lock(path) as lock_descriptor:
        claim, claim_bytes = module._read_current_execution_claim(
            path,
            lock_descriptor=lock_descriptor,
        )
        current, current_bytes, current_name = module._read_current_execution_event(
            path,
            lock_descriptor=lock_descriptor,
        )
        target["created_at"] = current["created_at"]
        target["updated_at"] = current["created_at"]
        target_sequence = int(target["sequence"])
        while int(current["sequence"]) < target_sequence:
            next_sequence = int(current["sequence"]) + 1
            if next_sequence == target_sequence:
                payload = dict(target)
            else:
                payload = dict(current)
                payload.update(
                    {
                        "status": "running",
                        "phase": f"test_setup_sequence_{next_sequence}",
                        "sequence": next_sequence,
                        "updated_at": target["updated_at"],
                        "counters": module.zero_sensitive_counters(),
                        "error": None,
                    }
                )
                payload.pop("details", None)
            module._atomic_append_execution_event_locked(
                path,
                lock_descriptor=lock_descriptor,
                expected_current=current,
                expected_current_bytes=current_bytes,
                expected_current_entry=current_name,
                expected_claim=claim,
                expected_claim_bytes=claim_bytes,
                payload=payload,
            )
            current, current_bytes, current_name = (
                module._read_current_execution_event(
                    path,
                    lock_descriptor=lock_descriptor,
                )
            )
    assert current == target
    return target


def _event_frame() -> pd.DataFrame:
    feature_columns = (
        "formal_rank_percentile",
        "formal_score_margin_to_cutoff",
        "directional_rsi",
        "directional_ma_gap",
        "directional_ma_slope",
        "open_interest_change_pct",
        "stop_distance_pct",
        "portfolio_drawdown_pct",
        "margin_to_equity_before",
        "active_positions_fraction",
        "same_direction_correlation",
        "loss_streak",
    )
    rows: list[dict[str, object]] = []
    for index, (date, product, direction, score) in enumerate(
        (
            ("2024-01-02", "rb.SHFE", "long", 0.7123456789012),
            ("2024-02-02", "cu.SHFE", "short", 0.6123456789012),
        ),
        start=1,
    ):
        row: dict[str, object] = {
            "event_id": f"event-{index}",
            "formal_release_id": "m0005_20260901T165450+0800_1961d98ccb2b",
            "formal_strategy": "ai_top10_plus_fu_official_live_v1",
            "official_live_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
            "formal_material_manifest_sha256": "4d92133bd67821a421bf6017c477015e79a3a8e36889ae4eb527bb11a31956a5",
            "analysis_start": "2020-01-02",
            "analysis_end": "2026-08-28",
            "candidate_index": index,
            "decision_datetime": f"{date}T15:00:00+08:00",
            "decision_date": date,
            "product_vt_symbol": product,
            "contract_vt_symbol": product.replace(".", "2505."),
            "direction": direction,
            "signal": f"{direction}_case2",
            "entry_context": "flat_entry",
            "candidate_status": "opened",
            "is_opened": 1,
            "ai_eval_date": "2023-12-29" if index == 1 else "2024-01-31",
            "formal_score_type": "stage182_promoted_ai_probability_top10_plus_fixed_fu",
            "formal_score": score,
            "formal_rank": index,
            "formal_top_n": 11,
            "formal_model_count": 10,
            "formal_cutoff_score": 0.1,
            "same_direction_correlation_gate_enabled": 1,
            "same_direction_correlation_active_count": 0,
            "same_direction_correlation_corr_count": 0,
            "same_direction_correlation_candidate_return_count": 20,
            "same_direction_correlation_min_required_count": 12,
            "same_direction_correlation_candidate_history_available": 1,
            "same_direction_correlation_active_count_recomputed": 0,
            "same_direction_correlation_corr_count_recomputed": 0,
            "same_direction_correlation_max_corr_recomputed": 0.0,
            "same_direction_correlation_trace_exact": 1,
        }
        row.update(
            {
                feature: float(position + index) / 100.0
                for position, feature in enumerate(feature_columns, start=1)
            }
        )
        row["same_direction_correlation"] = 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def _formal_identity(module) -> dict[str, object]:
    return {
        "formal_release_id": module.EXPECTED_RELEASE_ID,
        "formal_strategy": module.EXPECTED_FORMAL_STRATEGY,
        "official_live_version": module.EXPECTED_OFFICIAL_VERSION,
        "formal_material_manifest_sha256": module.EXPECTED_FORMAL_MANIFEST_SHA256,
        "capital": module.EXPECTED_CAPITAL,
        "release_path": "/frozen/release",
        "manifest_file_sha256": "1" * 64,
        "eligibility_path": "/frozen/eligibility.csv",
        "eligibility_sha256": "2" * 64,
    }


def _worker_receipt(
    module,
    worker_id: str,
    pid: int,
    root: Path,
    *,
    source_contract: str | None = None,
    database_sha: str | None = None,
    modules: dict[str, str] | None = None,
) -> dict[str, object]:
    worker_root = Path(root)
    runtime = worker_root / "runtime"
    trader = runtime / ".vntrader"
    output = worker_root / "output"
    trader.mkdir(parents=True)
    (runtime / "tmp").mkdir()
    (runtime / "mplconfig").mkdir()
    (runtime / "home").mkdir()
    output.mkdir()
    database_path = trader / "database.db"
    database_path.write_bytes(b"database-copy")
    setting_path = trader / "vt_setting.json"
    setting_path.write_text("{}\n", encoding="utf-8")
    profile_path = worker_root / "stage001.sb"
    profile_path.write_text(f"sandbox-{worker_id}\n", encoding="utf-8")
    capability_path = worker_root / "worker_capability.consumed.json"
    if worker_root.parent.name == "workers":
        attempt_dir = worker_root.parent.parent
    else:
        attempt_dir = worker_root.parent
    manifest_path = attempt_dir / "input_manifest.json"
    manifest_sha = _sha256(manifest_path) if manifest_path.is_file() else "0" * 64
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else None
    )
    if source_contract is None:
        source_contract = (
            str(manifest["file_contract_sha256"])
            if isinstance(manifest, dict) and "file_contract_sha256" in manifest
            else "c" * 64
        )
    startup_sys_path = module.isolated_startup_sys_path()
    approved_sys_path = module.approved_worker_sys_path()
    effective_sys_path = [*startup_sys_path, *approved_sys_path]
    worker_environment = module.worker_environment({}, runtime, worker_id)
    parent_channel_secret_sha256 = ("3" if worker_id == "A1" else "4") * 64
    bootstrap_path = module.WORKER_BOOTSTRAP.resolve()
    runner_path = Path(module.__file__).resolve()
    sandbox_probe_path = attempt_dir / f".sandbox_probe_{worker_id}"
    event_sequence = 3 if worker_id == "A1" else 5
    registered_event_path = module.EXECUTION_EVENT_PATH.with_name(
        module._execution_event_entry_name(
            module.EXECUTION_EVENT_PATH.name,
            event_sequence,
            "0" * 64,
        )
    ).resolve()
    capability_payload = {
        "schema_version": 2,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "worker_id": worker_id,
        "capability_nonce": ("1" if worker_id == "A1" else "2") * 64,
        "attempt_dir": str(attempt_dir.resolve()),
        "runtime_root": str(runtime.resolve()),
        "output_dir": str(output.resolve()),
        "input_manifest_path": str(manifest_path.resolve()),
        "input_manifest_sha256": manifest_sha,
        "sandbox_executable_path": str(module.SANDBOX_EXECUTABLE.resolve()),
        "sandbox_executable_sha256": _sha256(module.SANDBOX_EXECUTABLE),
        "sandbox_policy_mode": module.SANDBOX_POLICY_MODE,
        "sandbox_profile_path": str(profile_path.resolve()),
        "sandbox_profile_sha256": _sha256(profile_path),
        "sandbox_probe_path": str(sandbox_probe_path.resolve()),
        "bootstrap_path": str(bootstrap_path),
        "bootstrap_sha256": _sha256(bootstrap_path),
        "runner_path": str(runner_path),
        "runner_sha256": _sha256(runner_path),
        "python_executable": str(Path(sys.executable).resolve()),
        "isolated_startup_sys_path": startup_sys_path,
        "approved_sys_path": approved_sys_path,
        "worker_environment": worker_environment,
        "parent_channel_secret_sha256": parent_channel_secret_sha256,
        "claim_path": str(module.CLAIM_PATH.resolve()),
        "event_path": str(registered_event_path),
        "issued_at": "2026-09-05T07:59:59+08:00",
        "replay_permitted": False,
    }
    capability_path.write_text(
        json.dumps(
            capability_payload,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (worker_root / "worker.log").write_text(
        f"worker {worker_id} completed\n",
        encoding="utf-8",
    )
    feature_path = output / "event_features.csv"
    features = _event_frame()
    features.to_csv(feature_path, index=False, lineterminator="\n", float_format="%.17g")
    receipt = {
        "worker_id": worker_id,
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "pid": pid,
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": sys.version,
        "cwd": str(runtime),
        "runtime_root": str(runtime),
        "database": module._file_identity(database_path),
        "setting": module._file_identity(setting_path),
        "tmpdir": str(runtime / "tmp"),
        "mplconfigdir": str(runtime / "mplconfig"),
        "home": str(runtime / "home"),
        "sys_path": effective_sys_path,
        "source_file_contract_sha256": source_contract,
        "checkpoint_reuse_count": 0,
        "sensitive_counters": module.zero_sensitive_counters(),
        "started_at": "2026-09-05T08:00:00+08:00",
        "completed_at": "2026-09-05T08:01:00+08:00",
        "status": "completed",
        "analysis_start": "2020-01-02",
        "analysis_end": "2026-08-28",
        "capital": 150000.0,
        "official_live_version": module.EXPECTED_OFFICIAL_VERSION,
        "baseline_replay_count": 1,
        "network_connection_attempt_count": 0,
        "modules": modules
        or (
            module.expected_worker_modules(manifest)
            if isinstance(manifest, dict)
            else {
                "stage901": "/frozen/stage901.py",
                "live_config": "/frozen/live_config.py",
                "vnpy_portfoliostrategy": "/frozen/vnpy_portfoliostrategy/__init__.py",
                "feature_tool": "/frozen/formal_signal_event_features.py",
            }
        ),
        "sandbox_enforced": True,
        "sandbox_policy_mode": module.SANDBOX_POLICY_MODE,
        "sandbox_launch_executable": str(module.SANDBOX_EXECUTABLE),
        "sandbox_profile": module._file_identity(profile_path),
        "worker_capability": module._file_identity(capability_path),
        "bootstrap_attestation": {
            "schema_version": 1,
            "attestation_type": "isolated_pre_import_sandbox_bootstrap",
            "stage": module.STAGE,
            "line_id": module.LINE_ID,
            "campaign_nonce": "a" * 64,
            "lease_id": "b" * 64,
            "worker_id": worker_id,
            "capability_nonce": capability_payload["capability_nonce"],
            "pid": pid,
            "python_executable": str(Path(sys.executable).resolve()),
            "python_version": sys.version,
            "interpreter_flags": dict(module.BOOTSTRAP_INTERPRETER_FLAGS),
            "startup_sys_path": startup_sys_path,
            "approved_sys_path": approved_sys_path,
            "effective_sys_path": effective_sys_path,
            "pre_import_forbidden_modules": [],
            "worker_environment_sha256": hashlib.sha256(
                module._stable_json_bytes(worker_environment)
            ).hexdigest(),
            "parent_channel_secret_sha256": parent_channel_secret_sha256,
            "bootstrap_path": str(bootstrap_path),
            "bootstrap_sha256": _sha256(bootstrap_path),
            "runner_path": str(runner_path),
            "runner_sha256": _sha256(runner_path),
            "sandbox_probe": {
                "path": str(sandbox_probe_path.resolve()),
                "write_denied": True,
                "errno": errno.EPERM,
            },
            "attested_at": "2026-09-05T07:59:59+08:00",
        },
        "sensitive_guard_enforced": True,
        "event_count": len(features),
        "event_feature_sha256": module._frame_sha256(features),
        "event_feature_file": module._file_identity(feature_path),
        "formal_identity": _formal_identity(module),
        "feature_path": str(feature_path),
    }
    raw_receipt = dict(receipt)
    raw_receipt.pop("feature_path")
    (output / "receipt.json").write_text(
        json.dumps(raw_receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return receipt


def _success_summary(
    module,
    features: pd.DataFrame,
    inputs: dict[str, object] | None = None,
) -> dict[str, object]:
    inputs = inputs or _success_inputs(module)
    frame_sha = module._frame_sha256(features)
    worker_comparison = module.compare_worker_frames(features, features, atol=1e-12)
    worker_isolation = {
        "passed": True,
        "worker_ids": ["A1", "A2"],
        "distinct_pid": True,
        "distinct_runtime_root": True,
        "distinct_tmpdir": True,
        "distinct_mplconfigdir": True,
        "distinct_home": True,
        "database_sha256": inputs["files"]["source_database"]["sha256"],
        "event_count": len(features),
        "event_feature_sha256": frame_sha,
        "checkpoint_reuse_count": 0,
        "baseline_replay_count_per_worker": 1,
        "network_connection_attempt_count": 0,
        "sandbox_policy_mode": module.SANDBOX_POLICY_MODE,
        "sensitive_guard_enforced": True,
    }
    feature_qualification = module._load_feature_module().evaluate_feature_qualification(
        features
    )
    stage_gates = module.evaluate_stage001_gates(
        formal_identity_exact=True,
        execution_identity_exact=True,
        interval_exact=True,
        worker_isolation=worker_isolation,
        feature_qualification=feature_qualification,
        worker_comparison=worker_comparison,
        identity_stable=True,
        eligibility_trace_exact=True,
        fixed_fu_cutoff_excluded=True,
        forbidden_output_columns_absent=True,
        production_unchanged=True,
        event_ledger_durable=True,
        sensitive_counters=module.zero_sensitive_counters(),
    )
    return {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "created_at": "2026-09-05T10:00:00+08:00",
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "analysis_start": "2020-01-02",
        "analysis_end": "2026-08-28",
        "cold_worker_count": 2,
        "baseline_replay_count": 2,
        "formal_identity": inputs["formal_identity"],
        "worker_comparison": worker_comparison,
        "worker_isolation": worker_isolation,
        "feature_qualification": feature_qualification,
        "stage001_gates": stage_gates,
        "sensitive_counters": module.zero_sensitive_counters(),
        "decision": (
            "stage001_formal_event_feature_qualification_pass_require_independent_review"
            if stage_gates["passed"]
            else "stage001_formal_event_feature_qualification_fail_close_no_rerun"
        ),
        "trains_model": False,
        "reads_or_builds_labels": False,
        "publishes_backtest_performance": False,
        "independent_postrun_review_required": True,
        "replay_permitted": False,
    }


def _success_inputs(module) -> dict[str, object]:
    fake_identity = lambda path, digit: {
        "path": path,
        "size": 1,
        "mtime_ns": 1,
        "sha256": digit * 64,
    }
    files = {
        "source_database": {
            "path": "/frozen/database.db",
            "size": len(b"database-copy"),
            "mtime_ns": 1,
            "sha256": hashlib.sha256(b"database-copy").hexdigest(),
        },
        "python_executable": module._file_identity(Path(sys.executable).resolve()),
        "sandbox_executable": module._file_identity(module.SANDBOX_EXECUTABLE),
        "stage001_worker_bootstrap": module._file_identity(module.WORKER_BOOTSTRAP),
        "stage001_runner": module._file_identity(Path(module.__file__).resolve()),
        "stage001_feature_tool": module._file_identity(module.FEATURE_TOOL),
        "production_portfolio/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py": fake_identity(
            "/frozen/stage901.py", "3"
        ),
        "production_portfolio/qmt_roll_official_live_config.py": fake_identity(
            "/frozen/live_config.py", "4"
        ),
        "vnpy_portfoliostrategy/__init__.py": fake_identity(
            "/frozen/vnpy_portfoliostrategy/__init__.py", "5"
        ),
    }
    runtime = {
        "python_version": sys.version,
        "python_implementation": sys.implementation.name,
        "python_executable": str(Path(sys.executable).resolve()),
    }
    payload = {
        "schema_version": 1,
        "stage": module.STAGE,
        "created_at": "2026-09-05T09:58:00+08:00",
        "formal_identity": _formal_identity(module),
        "files": files,
        "input_file_count": len(files),
        "input_logical_key_sha256": module.logical_key_contract_sha256(files),
        "file_contract_sha256": hashlib.sha256(
            module._stable_json_bytes(module.file_contract_payload(files))
        ).hexdigest(),
        "runtime": runtime,
        "runtime_contract_sha256": hashlib.sha256(
            module._stable_json_bytes(runtime)
        ).hexdigest(),
    }
    return payload


def _success_authorization(module, inputs: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "stage": module.STAGE,
        "scope": module.AUTHORIZATION_SCOPE,
        "decision": module.REQUIRED_REVIEW_DECISION,
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "issued_at": "2026-09-05T09:59:00+08:00",
        "expires_at": "2026-09-05T11:00:00+08:00",
        "bound_files": {
            "stage001_runner": {
                "path": str(MODULE_PATH.resolve()),
                "sha256": _sha256(MODULE_PATH),
            }
        },
        "input_file_contract_sha256": inputs["file_contract_sha256"],
    }


def _success_claim(
    module,
    inputs: dict[str, object],
    authorization: dict[str, object],
    authorization_path: Path | None = None,
) -> dict[str, object]:
    authorization_path_value = (
        str(authorization_path.resolve())
        if authorization_path is not None
        else "/frozen/stage001_execution_authorization.json"
    )
    authorization_sha = (
        _sha256(authorization_path)
        if authorization_path is not None
        else "e" * 64
    )
    return {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "scope": module.AUTHORIZATION_SCOPE,
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "authorization_path": authorization_path_value,
        "authorization_sha256": authorization_sha,
        "authorization_payload_sha256": hashlib.sha256(
            module._stable_json_bytes(authorization)
        ).hexdigest(),
        "input_file_contract_sha256": inputs["file_contract_sha256"],
        "claimed_at": "2026-09-05T10:00:00+08:00",
        "replay_permitted": False,
    }


def _success_worker_receipts(module, attempt: Path) -> list[dict[str, object]]:
    inputs = _success_inputs(module)
    module._write_json(attempt / "input_manifest.json", inputs)
    workers = attempt / "workers"
    workers.mkdir(exist_ok=True)
    return [
        _worker_receipt(module, worker_id, pid, workers / worker_id)
        for worker_id, pid in (("A1", 101), ("A2", 102))
    ]


def _success_execution_event(
    module,
    *,
    features: pd.DataFrame,
    summary: dict[str, object],
    inputs: dict[str, object],
    authorization: dict[str, object],
    claim: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": claim["campaign_nonce"],
        "lease_id": claim["lease_id"],
        "status": "running",
        "phase": "publishing_success",
        "sequence": 6,
        "created_at": "2026-09-05T09:59:00+08:00",
        "updated_at": "2026-09-05T10:01:00+08:00",
        "counters": module.zero_sensitive_counters(),
        "error": None,
        "details": module._success_publish_event_details(
            features=features,
            summary=summary,
            input_before=inputs,
            authorization=authorization,
            claim=claim,
        ),
    }


def _publish_success_bundle_for_test(
    module,
    attempt: Path,
    *,
    features: pd.DataFrame,
    summary: dict[str, object],
    input_before: dict[str, object],
    input_after: dict[str, object],
    worker_receipts: list[dict[str, object]],
    authorization: dict[str, object],
    claim: dict[str, object],
    execution_event: dict[str, object] | None = None,
) -> dict[str, object]:
    _bind_success_current_state(
        module,
        attempt=attempt,
        inputs=input_before,
        authorization=authorization,
        claim=claim,
    )
    event = execution_event or _success_execution_event(
        module,
        features=features,
        summary=summary,
        inputs=input_before,
        authorization=authorization,
        claim=claim,
    )
    return module._publish_success_bundle(
        attempt,
        features=features,
        summary=summary,
        input_before=input_before,
        input_after=input_after,
        worker_receipts=worker_receipts,
        authorization=authorization,
        claim=claim,
        execution_event=event,
    )


def _bind_success_current_state(
    module,
    *,
    attempt: Path,
    inputs: dict[str, object],
    authorization: dict[str, object],
    claim: dict[str, object],
) -> Path:
    authorization_path = Path(str(claim["authorization_path"]))
    if not authorization_path.is_file():
        authorization_path = attempt.parent / f"{attempt.name}.authorization.json"
        module._write_json(authorization_path, authorization)
        claim["authorization_path"] = str(authorization_path.resolve())
        claim["authorization_sha256"] = _sha256(authorization_path)
    module.EXPECTED_INPUT_FILE_COUNT = inputs["input_file_count"]
    module.EXPECTED_INPUT_LOGICAL_KEY_SHA256 = inputs["input_logical_key_sha256"]
    module.build_input_manifest = lambda **_kwargs: json.loads(json.dumps(inputs))
    bound_files = authorization["bound_files"]
    module.authorization_bound_files = lambda: {
        key: Path(str(value["path"]))
        for key, value in bound_files.items()
    }
    return authorization_path


def test_compare_worker_frames_accepts_identical_and_tiny_numeric_noise(module) -> None:
    left = _event_frame()
    right = left.copy()
    right.loc[0, "formal_score"] += 5e-13

    result = module.compare_worker_frames(left, right, atol=1e-12)

    assert result["passed"] is True
    assert result["row_count"] == 2
    assert result["max_abs_numeric_diff"] == pytest.approx(5e-13)


@pytest.mark.parametrize(
    ("mutator", "error_code"),
    [
        (
            lambda frame: frame.assign(event_id=["changed", "event-2"]),
            "worker_event_identity_mismatch",
        ),
        (
            lambda frame: frame.assign(formal_score=[0.8, 0.6123456789012]),
            "worker_numeric_mismatch",
        ),
        (
            lambda frame: frame.iloc[:1].copy(),
            "worker_frame_shape_mismatch",
        ),
    ],
)
def test_compare_worker_frames_fails_closed_on_drift(module, mutator, error_code) -> None:
    with pytest.raises(module.Stage001Error, match=error_code):
        module.compare_worker_frames(_event_frame(), mutator(_event_frame()), atol=1e-12)


def test_create_exclusive_json_is_durable_private_and_non_reusable(module, tmp_path) -> None:
    path = tmp_path / "claim.json"
    module.create_exclusive_json(path, {"nonce": "a" * 64})

    assert json.loads(path.read_text(encoding="utf-8"))["nonce"] == "a" * 64
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(module.Stage001Error, match="exclusive_file_exists"):
        module.create_exclusive_json(path, {"nonce": "c" * 64})


def test_execution_event_persists_failure_and_sensitive_zero_counters(module, tmp_path) -> None:
    path = tmp_path / "execution_event.json"
    nonce = "a" * 64
    lease = "b" * 64
    _create_test_execution_event(
        module,
        path,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    module.update_execution_event(
        path,
        campaign_nonce=nonce,
        lease_id=lease,
        status="failed",
        phase="worker_a1",
        counters=module.zero_sensitive_counters(),
        error="synthetic_failure",
    )

    payload = _current_execution_event(module, path)
    assert payload["status"] == "failed"
    assert payload["phase"] == "worker_a1"
    assert payload["error"] == "synthetic_failure"
    assert payload["sequence"] == 2
    assert all(value == 0 for value in payload["counters"].values())


def test_execution_event_rejects_nonce_or_lease_substitution(module, tmp_path) -> None:
    path = tmp_path / "execution_event.json"
    _create_test_execution_event(
        module,
        path,
        campaign_nonce="a" * 64,
        lease_id="b" * 64,
    )

    with pytest.raises(module.Stage001Error, match="execution_event_binding_mismatch"):
        module.update_execution_event(
            path,
            campaign_nonce="c" * 64,
            lease_id="b" * 64,
            status="failed",
            phase="preflight",
            counters=module.zero_sensitive_counters(),
            error="wrong_nonce",
        )


@pytest.mark.parametrize(
    ("terminal_status", "next_status"),
    (("failed", "completed"), ("completed", "failed")),
)
def test_execution_event_terminal_status_cannot_be_reversed(
    module,
    tmp_path,
    terminal_status,
    next_status,
) -> None:
    path = tmp_path / "execution_event.json"
    nonce = "a" * 64
    lease = "b" * 64
    _create_test_execution_event(
        module,
        path,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    module.update_execution_event(
        path,
        campaign_nonce=nonce,
        lease_id=lease,
        status="running",
        phase="worker_a1",
        counters=module.zero_sensitive_counters(),
    )
    module.update_execution_event(
        path,
        campaign_nonce=nonce,
        lease_id=lease,
        status=terminal_status,
        phase="terminal",
        counters=module.zero_sensitive_counters(),
    )

    with pytest.raises(
        module.Stage001Error,
        match="execution_event_terminal_transition_invalid",
    ):
        module.update_execution_event(
            path,
            campaign_nonce=nonce,
            lease_id=lease,
            status=next_status,
            phase="reversed",
            counters=module.zero_sensitive_counters(),
        )

    assert _current_execution_event(module, path)["status"] == terminal_status


def test_execution_event_completed_status_cannot_be_rewritten_or_incremented(
    module,
    tmp_path,
) -> None:
    path = tmp_path / "execution_event.json"
    nonce = "a" * 64
    lease = "b" * 64
    _create_test_execution_event(
        module,
        path,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    module.update_execution_event(
        path,
        campaign_nonce=nonce,
        lease_id=lease,
        status="running",
        phase="publishing_success",
        counters=module.zero_sensitive_counters(),
    )
    module.update_execution_event(
        path,
        campaign_nonce=nonce,
        lease_id=lease,
        status="completed",
        phase="published",
        counters=module.zero_sensitive_counters(),
    )
    completed_bytes = path.read_bytes()

    with pytest.raises(
        module.Stage001Error,
        match="execution_event_terminal_transition_invalid",
    ):
        module.update_execution_event(
            path,
            campaign_nonce=nonce,
            lease_id=lease,
            status="completed",
            phase="published",
            counters=module.zero_sensitive_counters(),
        )

    assert path.read_bytes() == completed_bytes


def test_execution_event_lock_serializes_same_state_contenders(
    module,
    tmp_path,
) -> None:
    state_dir = tmp_path / "state"
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "replay_permitted": False,
    }
    module.create_execution_state(
        state_dir,
        claim=claim,
        campaign_nonce=claim["campaign_nonce"],
        lease_id=claim["lease_id"],
    )
    event_path = state_dir / "event.json"
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def hold_first_lock() -> None:
        with module._execution_event_lock(event_path):
            first_entered.set()
            assert release_first.wait(timeout=5)

    def enter_second_lock() -> None:
        assert first_entered.wait(timeout=5)
        with module._execution_event_lock(event_path):
            second_entered.set()

    first = threading.Thread(target=hold_first_lock)
    second = threading.Thread(target=enter_second_lock)
    first.start()
    assert first_entered.wait(timeout=5)
    second.start()
    assert not second_entered.wait(timeout=0.1)
    release_first.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert second_entered.is_set()


def test_execution_event_update_fails_closed_without_current_claim(
    module,
    tmp_path,
) -> None:
    path = tmp_path / "execution_event.json"
    nonce = "a" * 64
    lease = "b" * 64
    module.create_execution_event(path, campaign_nonce=nonce, lease_id=lease)
    original = path.read_bytes()

    with pytest.raises(module.Stage001Error, match="execution_event_claim_missing"):
        module.update_execution_event(
            path,
            campaign_nonce=nonce,
            lease_id=lease,
            status="running",
            phase="worker_a1",
            counters=module.zero_sensitive_counters(),
        )

    assert path.read_bytes() == original


def test_execution_event_update_fails_closed_on_current_claim_binding_drift(
    module,
    tmp_path,
) -> None:
    path = tmp_path / "execution_event.json"
    nonce = "a" * 64
    lease = "b" * 64
    _create_test_execution_event(
        module,
        path,
        campaign_nonce="c" * 64,
        lease_id=lease,
    )
    path.unlink()
    module.create_execution_event(path, campaign_nonce=nonce, lease_id=lease)
    original = path.read_bytes()

    with pytest.raises(
        module.Stage001Error,
        match="execution_event_claim_binding_mismatch",
    ):
        module.update_execution_event(
            path,
            campaign_nonce=nonce,
            lease_id=lease,
            status="running",
            phase="worker_a1",
            counters=module.zero_sensitive_counters(),
        )

    assert path.read_bytes() == original


def test_execution_event_update_rechecks_claim_immediately_before_write(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "execution_event.json"
    nonce = "a" * 64
    lease = "b" * 64
    claim = _create_test_execution_event(
        module,
        path,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    original = path.read_bytes()
    real_next = module._next_execution_event

    def build_event_then_replace_claim(*args, **kwargs):
        updated = real_next(*args, **kwargs)
        drifted = dict(claim)
        drifted["lease_id"] = "f" * 64
        module._atomic_replace_json(path.with_name("claim.json"), drifted)
        return updated

    monkeypatch.setattr(
        module,
        "_next_execution_event",
        build_event_then_replace_claim,
    )

    with pytest.raises(
        module.Stage001Error,
        match="execution_event_claim_binding_mismatch",
    ):
        module.update_execution_event(
            path,
            campaign_nonce=nonce,
            lease_id=lease,
            status="running",
            phase="worker_a1",
            counters=module.zero_sensitive_counters(),
        )

    assert path.read_bytes() == original


def test_execution_event_updates_append_immutable_hash_chained_entries(
    module,
    tmp_path,
) -> None:
    path = tmp_path / "event.json"
    nonce = "a" * 64
    lease = "b" * 64
    _create_test_execution_event(
        module,
        path,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    initial_bytes = path.read_bytes()

    module.update_execution_event(
        path,
        campaign_nonce=nonce,
        lease_id=lease,
        status="running",
        phase="worker_a1",
        counters=module.zero_sensitive_counters(),
    )
    module.update_execution_event(
        path,
        campaign_nonce=nonce,
        lease_id=lease,
        status="running",
        phase="worker_a2",
        counters=module.zero_sensitive_counters(),
    )

    entries = sorted(tmp_path.glob("event.seq-*.json"))
    assert path.read_bytes() == initial_bytes
    assert len(entries) == 2
    first_bytes = entries[0].read_bytes()
    assert entries[0].name == module._execution_event_entry_name(
        path.name,
        2,
        hashlib.sha256(initial_bytes).hexdigest(),
    )
    assert entries[1].name == module._execution_event_entry_name(
        path.name,
        3,
        hashlib.sha256(first_bytes).hexdigest(),
    )
    current = module.read_execution_event(path)
    assert current["sequence"] == 3
    assert current["phase"] == "worker_a2"


def test_execution_event_commit_fails_when_competitor_claims_next_sequence(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "event.json"
    nonce = "a" * 64
    lease = "b" * 64
    _create_test_execution_event(
        module,
        path,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    current = json.loads(path.read_text(encoding="utf-8"))
    competitor = module._next_execution_event(
        current,
        campaign_nonce=nonce,
        lease_id=lease,
        status="running",
        phase="competing_writer",
        counters=module.zero_sensitive_counters(),
        error=None,
        details=None,
    )
    competitor_bytes = module._json_document_bytes(competitor)
    real_link = module.os.link
    competition_injected = False

    def install_competitor_then_link(source, destination, *args, **kwargs):
        nonlocal competition_injected
        if not competition_injected:
            directory_descriptor = kwargs["dst_dir_fd"]
            temporary_name = ".competing-event.tmp"
            descriptor = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=directory_descriptor,
            )
            try:
                module._write_all(descriptor, competitor_bytes)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            real_link(
                temporary_name,
                destination,
                src_dir_fd=directory_descriptor,
                dst_dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
            os.unlink(temporary_name, dir_fd=directory_descriptor)
            competition_injected = True
        return real_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(module.os, "link", install_competitor_then_link)

    with pytest.raises(
        module.Stage001Error,
        match="execution_event_compare_and_swap_mismatch",
    ):
        module.update_execution_event(
            path,
            campaign_nonce=nonce,
            lease_id=lease,
            status="running",
            phase="stale_writer",
            counters=module.zero_sensitive_counters(),
        )

    assert competition_injected is True
    entries = sorted(tmp_path.glob("event.seq-*.json"))
    assert len(entries) == 1
    assert json.loads(entries[0].read_text(encoding="utf-8"))["phase"] == (
        "competing_writer"
    )


def test_execution_event_commit_never_overwrites_current_entry_mutated_at_link(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "event.json"
    nonce = "a" * 64
    lease = "b" * 64
    _create_test_execution_event(
        module,
        path,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    external = json.loads(path.read_text(encoding="utf-8"))
    external["phase"] = "external_current_mutation"
    external_bytes = module._json_document_bytes(external)
    real_link = module.os.link
    mutation_injected = False

    def mutate_current_then_link(source, destination, *args, **kwargs):
        nonlocal mutation_injected
        if not mutation_injected:
            module._atomic_replace_json(path, external)
            mutation_injected = True
        return real_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(module.os, "link", mutate_current_then_link)

    with pytest.raises(
        module.Stage001Error,
        match="execution_event_journal_chain_invalid",
    ):
        module.update_execution_event(
            path,
            campaign_nonce=nonce,
            lease_id=lease,
            status="running",
            phase="stale_writer",
            counters=module.zero_sensitive_counters(),
        )

    assert mutation_injected is True
    assert path.read_bytes() == external_bytes


def test_execution_event_commit_carries_initial_noncanonical_raw_bytes(
    module,
    tmp_path,
) -> None:
    path = tmp_path / "event.json"
    nonce = "a" * 64
    lease = "b" * 64
    _create_test_execution_event(
        module,
        path,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
    path.write_bytes(raw)

    module.update_execution_event(
        path,
        campaign_nonce=nonce,
        lease_id=lease,
        status="running",
        phase="worker_a1",
        counters=module.zero_sensitive_counters(),
    )

    entries = sorted(tmp_path.glob("event.seq-*.json"))
    assert path.read_bytes() == raw
    assert len(entries) == 1
    assert entries[0].name == module._execution_event_entry_name(
        path.name,
        2,
        hashlib.sha256(raw).hexdigest(),
    )
    assert module.read_execution_event(path)["sequence"] == 2


def test_execution_event_claim_read_detects_same_inode_in_place_drift(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "execution_event.json"
    claim_path = path.with_name("claim.json")
    nonce = "a" * 64
    lease = "b" * 64
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": nonce,
        "lease_id": lease,
        "replay_permitted": False,
        "audit_marker": "x",
    }
    drifted = dict(claim)
    drifted["audit_marker"] = "y"
    assert len(module._json_document_bytes(claim)) == len(
        module._json_document_bytes(drifted)
    )
    module.create_exclusive_json(claim_path, claim)
    module.create_execution_event(path, campaign_nonce=nonce, lease_id=lease)
    original = path.read_bytes()
    real_read = module.os.read
    drift_injected = False

    def read_then_mutate_claim(descriptor, size):
        nonlocal drift_injected
        block = real_read(descriptor, size)
        if block and not drift_injected:
            claim_path.write_bytes(module._json_document_bytes(drifted))
            drift_injected = True
        return block

    monkeypatch.setattr(module.os, "read", read_then_mutate_claim)

    with pytest.raises(
        module.Stage001Error,
        match="execution_event_claim_replaced",
    ):
        module.update_execution_event(
            path,
            campaign_nonce=nonce,
            lease_id=lease,
            status="running",
            phase="worker_a1",
            counters=module.zero_sensitive_counters(),
        )

    assert drift_injected is True
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    (
        ("claim", "execution_event_claim_binding_mismatch"),
        ("event", "execution_event_compare_and_swap_mismatch"),
        ("state_dir", "execution_event_lock_anchor_drift"),
    ),
)
def test_execution_event_update_rejects_drift_after_temp_write_before_replace(
    module,
    tmp_path,
    monkeypatch,
    mutation,
    error_code,
) -> None:
    state_dir = tmp_path / "state"
    path = state_dir / "event.json"
    nonce = "a" * 64
    lease = "b" * 64
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": nonce,
        "lease_id": lease,
        "replay_permitted": False,
        "authorization_sha256": "c" * 64,
    }
    module.create_execution_state(
        state_dir,
        claim=claim,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    expected_current_event = path.read_bytes()
    replacement_dir = tmp_path / "replacement_state"
    if mutation == "state_dir":
        module.create_execution_state(
            replacement_dir,
            claim=claim,
            campaign_nonce=nonce,
            lease_id=lease,
        )
    drift_injected = False

    def inject_drift(_path, _lock_descriptor):
        nonlocal drift_injected, expected_current_event
        drift_injected = True
        if mutation == "claim":
            changed_claim = dict(claim)
            changed_claim["authorization_sha256"] = "d" * 64
            module._atomic_replace_json(state_dir / "claim.json", changed_claim)
        elif mutation == "event":
            changed_event = json.loads(path.read_text(encoding="utf-8"))
            changed_event["phase"] = "external_event_drift"
            module._atomic_replace_json(path, changed_event)
            expected_current_event = path.read_bytes()
        else:
            os.replace(state_dir, tmp_path / "detached_original_state")
            os.replace(replacement_dir, state_dir)
            expected_current_event = path.read_bytes()

    monkeypatch.setattr(
        module,
        "_execution_event_before_replace_hook",
        inject_drift,
        raising=False,
    )

    with pytest.raises(module.Stage001Error, match=error_code):
        module.update_execution_event(
            path,
            campaign_nonce=nonce,
            lease_id=lease,
            status="running",
            phase="worker_a1",
            counters=module.zero_sensitive_counters(),
        )

    assert drift_injected is True
    assert path.read_bytes() == expected_current_event


def test_execution_event_update_rejects_claim_drift_during_dirfd_replace(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir = tmp_path / "state"
    path = state_dir / "event.json"
    nonce = "a" * 64
    lease = "b" * 64
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": nonce,
        "lease_id": lease,
        "replay_permitted": False,
        "authorization_sha256": "c" * 64,
    }
    module.create_execution_state(
        state_dir,
        claim=claim,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    drift_injected = False

    def drift_claim_before_commit(_path, _lock_descriptor):
        nonlocal drift_injected
        if not drift_injected:
            changed_claim = dict(claim)
            changed_claim["authorization_sha256"] = "d" * 64
            (state_dir / "claim.json").write_bytes(
                module._json_document_bytes(changed_claim)
            )
            drift_injected = True

    monkeypatch.setattr(
        module,
        "_execution_event_before_replace_hook",
        drift_claim_before_commit,
    )

    with pytest.raises(
        module.Stage001Error,
        match="execution_event_claim_binding_mismatch",
    ):
        module.update_execution_event(
            path,
            campaign_nonce=nonce,
            lease_id=lease,
            status="running",
            phase="worker_a1",
            counters=module.zero_sensitive_counters(),
        )

    assert drift_injected is True


def test_execution_event_dirfd_replace_cannot_target_replaced_state_directory(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir = tmp_path / "state"
    replacement_dir = tmp_path / "replacement_state"
    detached_dir = tmp_path / "detached_state"
    path = state_dir / "event.json"
    nonce = "a" * 64
    lease = "b" * 64
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": nonce,
        "lease_id": lease,
        "replay_permitted": False,
    }
    for directory in (state_dir, replacement_dir):
        module.create_execution_state(
            directory,
            claim=claim,
            campaign_nonce=nonce,
            lease_id=lease,
        )
    replacement_event = (replacement_dir / "event.json").read_bytes()
    drift_injected = False

    def replace_directory_before_commit(_path, _lock_descriptor):
        nonlocal drift_injected
        if not drift_injected:
            os.replace(state_dir, detached_dir)
            os.replace(replacement_dir, state_dir)
            drift_injected = True

    monkeypatch.setattr(
        module,
        "_execution_event_before_replace_hook",
        replace_directory_before_commit,
    )

    with pytest.raises(
        module.Stage001Error,
        match="execution_event_lock_anchor_drift",
    ):
        module.update_execution_event(
            path,
            campaign_nonce=nonce,
            lease_id=lease,
            status="running",
            phase="worker_a1",
            counters=module.zero_sensitive_counters(),
        )

    assert drift_injected is True
    assert path.read_bytes() == replacement_event


def test_execution_event_directory_lock_serializes_real_process_writers(
    module,
    tmp_path,
) -> None:
    state_dir = tmp_path / "state"
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "replay_permitted": False,
    }
    module.create_execution_state(
        state_dir,
        claim=claim,
        campaign_nonce=claim["campaign_nonce"],
        lease_id=claim["lease_id"],
    )
    child_script = r"""
import importlib.util
import sys
import time
from pathlib import Path

module_path, event_path, ready_path, attempted_path, entered_path, holding_path, release_path, done_path, phase, hold = sys.argv[1:]
spec = importlib.util.spec_from_file_location(f"stage001_lock_child_{phase}", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
event = Path(event_path)
real_flock = module.fcntl.flock

def traced_flock(descriptor, operation):
    if operation == module.fcntl.LOCK_EX:
        Path(attempted_path).write_text("attempted\n", encoding="utf-8")
    result = real_flock(descriptor, operation)
    if operation == module.fcntl.LOCK_EX:
        Path(entered_path).write_text("entered\n", encoding="utf-8")
    return result

module.fcntl.flock = traced_flock
Path(ready_path).write_text("ready\n", encoding="utf-8")
if hold == "1":
    with module._execution_event_lock(event):
        Path(holding_path).write_text("holding\n", encoding="utf-8")
        deadline = time.monotonic() + 10
        while not Path(release_path).exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("release_timeout")
            time.sleep(0.01)
module.update_execution_event(
    event,
    campaign_nonce="a" * 64,
    lease_id="b" * 64,
    status="running",
    phase=phase,
    counters=module.zero_sensitive_counters(),
)
Path(done_path).write_text("done\n", encoding="utf-8")
"""
    markers = {
        name: tmp_path / name
        for name in (
            "ready_a",
            "attempted_a",
            "entered_a",
            "holding_a",
            "release_a",
            "done_a",
            "ready_b",
            "attempted_b",
            "entered_b",
            "holding_b",
            "done_b",
        )
    }

    def launch(suffix: str, *, hold: bool):
        return subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-c",
                child_script,
                str(MODULE_PATH),
                str(state_dir / "event.json"),
                str(markers[f"ready_{suffix}"]),
                str(markers[f"attempted_{suffix}"]),
                str(markers[f"entered_{suffix}"]),
                str(markers[f"holding_{suffix}"]),
                str(markers["release_a"]),
                str(markers[f"done_{suffix}"]),
                f"process_{suffix}",
                "1" if hold else "0",
            ],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def wait_for(path: Path) -> None:
        deadline = time.monotonic() + 10
        while not path.exists():
            if time.monotonic() >= deadline:
                raise AssertionError(f"marker_timeout:{path.name}")
            time.sleep(0.01)

    first = launch("a", hold=True)
    second = None
    try:
        wait_for(markers["holding_a"])
        second = launch("b", hold=False)
        wait_for(markers["ready_b"])
        wait_for(markers["attempted_b"])
        assert not markers["entered_b"].exists()
        assert not markers["done_b"].exists()
        markers["release_a"].touch()
        first_stdout, first_stderr = first.communicate(timeout=10)
        second_stdout, second_stderr = second.communicate(timeout=10)
        assert first.returncode == 0, first_stdout + first_stderr
        assert second.returncode == 0, second_stdout + second_stderr
        assert markers["entered_b"].is_file()
    finally:
        markers["release_a"].touch(exist_ok=True)
        for process in (first, second):
            if process is not None and process.poll() is None:
                process.kill()
                process.communicate()

    event = _current_execution_event(module, state_dir / "event.json")
    assert event["status"] == "running"
    assert event["phase"] in {"process_a", "process_b"}
    assert event["sequence"] == 3


def test_execution_event_sensitive_counters_cannot_decrease(module, tmp_path) -> None:
    path = tmp_path / "execution_event.json"
    nonce = "a" * 64
    lease = "b" * 64
    counters = module.zero_sensitive_counters()
    counters["network_connection_count"] = 1
    _create_test_execution_event(
        module,
        path,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    module.update_execution_event(
        path,
        campaign_nonce=nonce,
        lease_id=lease,
        status="running",
        phase="worker_a1",
        counters=counters,
    )

    with pytest.raises(
        module.Stage001Error,
        match="execution_event_counter_regression:network_connection_count",
    ):
        module.update_execution_event(
            path,
            campaign_nonce=nonce,
            lease_id=lease,
            status="running",
            phase="worker_a2",
            counters=module.zero_sensitive_counters(),
        )


def test_execution_state_atomically_contains_claim_and_event(module, tmp_path) -> None:
    state_dir = tmp_path / "state"
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "replay_permitted": False,
    }

    module.create_execution_state(
        state_dir,
        claim=claim,
        campaign_nonce="a" * 64,
        lease_id="b" * 64,
    )

    assert json.loads((state_dir / "claim.json").read_text())["campaign_nonce"] == "a" * 64
    assert json.loads((state_dir / "event.json").read_text())["status"] == "claimed"
    assert (state_dir / "claim.json").stat().st_mode & 0o777 == 0o600
    assert (state_dir / "event.json").stat().st_mode & 0o777 == 0o600


def test_execution_state_publish_failure_preserves_recoverable_staging(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir, _, failure_dir = _patch_execution_paths(module, tmp_path, monkeypatch)
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "replay_permitted": False,
    }
    real_replace = module.os.replace

    def fail_fixed_state_publish(source, destination):
        if Path(destination) == state_dir:
            raise OSError("synthetic_state_rename_failure")
        return real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_fixed_state_publish)

    with pytest.raises(OSError, match="synthetic_state_rename_failure"):
        module.create_execution_state(
            state_dir,
            claim=claim,
            campaign_nonce="a" * 64,
            lease_id="b" * 64,
        )

    assert not state_dir.exists()
    staging = list(tmp_path.glob(".state.*.staging"))
    assert len(staging) == 1
    monkeypatch.setattr(module.os, "replace", real_replace)

    result = module.reconcile_execution_state()

    assert result["terminal"] == "failed"
    assert result["recovered_staging"] is True
    assert state_dir.is_dir()
    assert failure_dir.is_dir()


def test_execution_state_fsync_failure_preserves_recoverable_staging(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir, _, failure_dir = _patch_execution_paths(module, tmp_path, monkeypatch)
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "replay_permitted": False,
    }
    real_fsync_directory = module._fsync_directory

    def fail_staging_fsync(path):
        if Path(path).name.endswith(".staging"):
            raise OSError("synthetic_state_fsync_failure")
        return real_fsync_directory(path)

    monkeypatch.setattr(module, "_fsync_directory", fail_staging_fsync)

    with pytest.raises(OSError, match="synthetic_state_fsync_failure"):
        module.create_execution_state(
            state_dir,
            claim=claim,
            campaign_nonce="a" * 64,
            lease_id="b" * 64,
        )

    assert not state_dir.exists()
    staging = list(tmp_path.glob(".state.*.staging"))
    assert len(staging) == 1
    monkeypatch.setattr(module, "_fsync_directory", real_fsync_directory)

    result = module.reconcile_execution_state()

    assert result["terminal"] == "failed"
    assert result["recovered_staging"] is True
    assert state_dir.is_dir()
    assert failure_dir.is_dir()


def test_reconcile_recovers_process_crash_after_claim_before_event(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir, _, failure_dir = _patch_execution_paths(module, tmp_path, monkeypatch)
    nonce = "a" * 64
    lease = "b" * 64
    staging = tmp_path / f".state.{nonce}.{lease}.staging"
    script = """
import json
import os
import sys
from pathlib import Path

staging = Path(sys.argv[1])
nonce = sys.argv[2]
lease = sys.argv[3]
staging.mkdir(mode=0o700)
claim = {
    "schema_version": 1,
    "stage": "stage001_formal_event_feature_qualification",
    "line_id": "futures_trend_xgboost_formal_signal_marginal_utility",
    "campaign_nonce": nonce,
    "lease_id": lease,
    "replay_permitted": False,
}
path = staging / "claim.json"
path.write_text(json.dumps(claim) + "\\n", encoding="utf-8")
path.chmod(0o600)
os._exit(91)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(staging), nonce, lease],
        check=False,
    )
    assert completed.returncode == 91
    assert staging.is_dir()
    assert not state_dir.exists()

    result = module.reconcile_execution_state()

    assert result == {
        "reconciled": True,
        "recovered_staging": True,
        "terminal": "failed",
    }
    assert state_dir.is_dir()
    assert not staging.exists()
    assert failure_dir.is_dir()
    claim = json.loads((state_dir / "claim.json").read_text(encoding="utf-8"))
    event = _current_execution_event(module, state_dir / "event.json")
    assert claim["campaign_nonce"] == nonce
    assert claim["lease_id"] == lease
    assert claim["replay_permitted"] is False
    assert event["status"] == "failed"
    assert event["phase"] == "recovered_interrupted_execution"
    assert (state_dir / "claim.json").stat().st_mode & 0o777 == 0o600
    assert (state_dir / "event.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("fault_mode", ["empty", "truncated_event", "event_only"])
def test_reconcile_turns_incomplete_staging_into_terminal_failure(
    module,
    tmp_path,
    monkeypatch,
    fault_mode,
) -> None:
    state_dir, _, failure_dir = _patch_execution_paths(module, tmp_path, monkeypatch)
    nonce = "a" * 64
    lease = "b" * 64
    staging = tmp_path / f".state.{nonce}.{lease}.staging"
    staging.mkdir(mode=0o700)
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": nonce,
        "lease_id": lease,
        "replay_permitted": False,
    }
    if fault_mode == "truncated_event":
        module.create_exclusive_json(staging / "claim.json", claim)
        (staging / "event.json").write_text('{"status":', encoding="utf-8")
    elif fault_mode == "event_only":
        module.create_execution_event(
            staging / "event.json",
            campaign_nonce=nonce,
            lease_id=lease,
        )

    result = module.reconcile_execution_state()

    assert result["terminal"] == "failed"
    assert result["recovered_staging"] is True
    assert state_dir.is_dir()
    assert failure_dir.is_dir()
    recovered_claim = json.loads(
        (state_dir / "claim.json").read_text(encoding="utf-8")
    )
    recovered_event = _current_execution_event(module, state_dir / "event.json")
    assert recovered_claim["campaign_nonce"] == nonce
    assert recovered_claim["lease_id"] == lease
    assert recovered_claim["replay_permitted"] is False
    assert recovered_event["status"] == "failed"
    assert recovered_event["counters"] == module.zero_sensitive_counters()
    if fault_mode == "truncated_event":
        assert list(state_dir.glob("event.json.corrupt*"))


def test_reconcile_recovers_complete_pre_rename_staging_and_preserves_counters(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir, _, failure_dir = _patch_execution_paths(module, tmp_path, monkeypatch)
    nonce = "a" * 64
    lease = "b" * 64
    staging = tmp_path / f".state.{nonce}.{lease}.staging"
    staging.mkdir(mode=0o700)
    module.create_exclusive_json(
        staging / "claim.json",
        {
            "schema_version": 1,
            "stage": module.STAGE,
            "line_id": module.LINE_ID,
            "campaign_nonce": nonce,
            "lease_id": lease,
            "replay_permitted": False,
        },
    )
    module.create_execution_event(
        staging / "event.json",
        campaign_nonce=nonce,
        lease_id=lease,
    )
    counters = module.zero_sensitive_counters()
    counters["network_connection_count"] = 1
    module.update_execution_event(
        staging / "event.json",
        campaign_nonce=nonce,
        lease_id=lease,
        status="running",
        phase="worker_a1",
        counters=counters,
    )

    result = module.reconcile_execution_state()

    assert result["terminal"] == "failed"
    assert result["recovered_staging"] is True
    assert failure_dir.is_dir()
    event = _current_execution_event(module, state_dir / "event.json")
    assert event["status"] == "failed"
    assert event["counters"]["network_connection_count"] == 1
    assert not list(state_dir.glob("*.corrupt*"))


def test_reconcile_interrupted_claim_publishes_failure_without_replay(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir = tmp_path / "state"
    final_dir = tmp_path / "artifacts/final"
    failure_dir = tmp_path / "artifacts/failed"
    monkeypatch.setattr(module, "EXECUTION_STATE_DIR", state_dir)
    monkeypatch.setattr(module, "CLAIM_PATH", state_dir / "claim.json")
    monkeypatch.setattr(module, "EXECUTION_EVENT_PATH", state_dir / "event.json")
    monkeypatch.setattr(module, "ARTIFACT_PARENT", tmp_path / "artifacts")
    monkeypatch.setattr(module, "FINAL_DIR", final_dir)
    monkeypatch.setattr(module, "FAILURE_DIR", failure_dir)
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "replay_permitted": False,
    }
    module.create_execution_state(
        state_dir,
        claim=claim,
        campaign_nonce="a" * 64,
        lease_id="b" * 64,
    )
    module.update_execution_event(
        state_dir / "event.json",
        campaign_nonce="a" * 64,
        lease_id="b" * 64,
        status="running",
        phase="worker_a1",
        counters=module.zero_sensitive_counters(),
    )

    result = module.reconcile_execution_state()

    assert result["reconciled"] is True
    assert result["terminal"] == "failed"
    assert failure_dir.is_dir()
    event = _current_execution_event(module, state_dir / "event.json")
    assert event["status"] == "failed"
    assert event["phase"] == "recovered_interrupted_execution"
    assert event["counters"] == module.zero_sensitive_counters()


@pytest.mark.parametrize(
    "fault_phase",
    (
        "after_staging_mkdir",
        "after_receipt_write",
        "after_manifest_write",
        "after_pre_rename_fsync",
    ),
)
def test_reconcile_recovers_process_crash_during_failure_bundle_publish(
    module,
    tmp_path,
    monkeypatch,
    fault_phase,
) -> None:
    state_dir, _, failure_dir = _patch_execution_paths(module, tmp_path, monkeypatch)
    nonce = "a" * 64
    lease = "b" * 64
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": nonce,
        "lease_id": lease,
        "replay_permitted": False,
    }
    module.create_execution_state(
        state_dir,
        claim=claim,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    module.update_execution_event(
        state_dir / "event.json",
        campaign_nonce=nonce,
        lease_id=lease,
        status="running",
        phase="worker_a1",
        counters=module.zero_sensitive_counters(),
    )
    counters = module.zero_sensitive_counters()
    counters["network_connection_count"] = 1
    counters_path = tmp_path / "failure-counters.json"
    counters_path.write_text(json.dumps(counters) + "\n", encoding="utf-8")
    script = r"""
import importlib.util
import json
import os
import sys
from pathlib import Path

module_path = Path(sys.argv[1])
artifact_parent = Path(sys.argv[2])
failure_dir = Path(sys.argv[3])
nonce = sys.argv[4]
lease = sys.argv[5]
fault_phase = sys.argv[6]
counters = json.loads(Path(sys.argv[7]).read_text(encoding="utf-8"))
state_dir = Path(sys.argv[8])
spec = importlib.util.spec_from_file_location("stage001_failure_crash", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.ARTIFACT_PARENT = artifact_parent
module.FAILURE_DIR = failure_dir
module.EXECUTION_STATE_DIR = state_dir
module.CLAIM_PATH = state_dir / "claim.json"
module.EXECUTION_EVENT_PATH = state_dir / "event.json"

def fault(point):
    if point == fault_phase:
        os._exit(91)

module._failure_publish_fault_point = fault
module._publish_failure_bundle(
    None,
    error=RuntimeError("synthetic_failure"),
    campaign_nonce=nonce,
    lease_id=lease,
    phase="worker_a1",
    input_before=None,
    sensitive_counters=counters,
)
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(MODULE_PATH),
            str(module.ARTIFACT_PARENT),
            str(failure_dir),
            nonce,
            lease,
            fault_phase,
            str(counters_path),
            str(state_dir),
        ],
        check=False,
    )

    assert completed.returncode == 91
    assert len(list(module.ARTIFACT_PARENT.glob(".*.staging"))) == 1
    result = module.reconcile_execution_state()

    assert result["terminal"] == "failed"
    assert failure_dir.is_dir()
    assert not list(module.ARTIFACT_PARENT.glob(".*.staging"))
    receipt = json.loads(
        (failure_dir / "failure_receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["campaign_nonce"] == nonce
    assert receipt["lease_id"] == lease
    assert receipt["replay_permitted"] is False
    assert receipt["qualification_claim_permitted"] is False
    manifest = json.loads(
        (failure_dir / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest == module._artifact_manifest(failure_dir)
    event = _current_execution_event(module, state_dir / "event.json")
    assert event["status"] == "failed"
    assert event["counters"]["network_connection_count"] == 1
    assert receipt["sensitive_counters"]["network_connection_count"] == 1


def test_reconcile_recovers_failure_renamed_before_event_update(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir, _, failure_dir = _patch_execution_paths(module, tmp_path, monkeypatch)
    nonce = "a" * 64
    lease = "b" * 64
    module.create_execution_state(
        state_dir,
        claim={
            "schema_version": 1,
            "stage": module.STAGE,
            "line_id": module.LINE_ID,
            "campaign_nonce": nonce,
            "lease_id": lease,
            "replay_permitted": False,
        },
        campaign_nonce=nonce,
        lease_id=lease,
    )
    module.update_execution_event(
        state_dir / "event.json",
        campaign_nonce=nonce,
        lease_id=lease,
        status="running",
        phase="worker_a1",
        counters=module.zero_sensitive_counters(),
    )
    counters = module.zero_sensitive_counters()
    counters["sensitive_module_import_count"] = 1
    counters_path = tmp_path / "failure-counters.json"
    counters_path.write_text(json.dumps(counters) + "\n", encoding="utf-8")
    script = r"""
import importlib.util
import json
import os
import sys
from pathlib import Path

module_path = Path(sys.argv[1])
artifact_parent = Path(sys.argv[2])
failure_dir = Path(sys.argv[3])
nonce = sys.argv[4]
lease = sys.argv[5]
counters = json.loads(Path(sys.argv[6]).read_text(encoding="utf-8"))
state_dir = Path(sys.argv[7])
spec = importlib.util.spec_from_file_location("stage001_failure_rename_crash", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.ARTIFACT_PARENT = artifact_parent
module.FAILURE_DIR = failure_dir
module.EXECUTION_STATE_DIR = state_dir
module.CLAIM_PATH = state_dir / "claim.json"
module.EXECUTION_EVENT_PATH = state_dir / "event.json"

def fault(point):
    if point == "after_atomic_rename":
        os._exit(91)

module._failure_publish_fault_point = fault
module._publish_failure_bundle(
    None,
    error=RuntimeError("synthetic_failure"),
    campaign_nonce=nonce,
    lease_id=lease,
    phase="worker_a1",
    input_before=None,
    sensitive_counters=counters,
)
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(MODULE_PATH),
            str(module.ARTIFACT_PARENT),
            str(failure_dir),
            nonce,
            lease,
            str(counters_path),
            str(state_dir),
        ],
        check=False,
    )

    assert completed.returncode == 91
    assert failure_dir.is_dir()
    result = module.reconcile_execution_state()

    assert result["terminal"] == "failed"
    event = _current_execution_event(module, state_dir / "event.json")
    receipt = json.loads(
        (failure_dir / "failure_receipt.json").read_text(encoding="utf-8")
    )
    assert event["counters"]["sensitive_module_import_count"] == 1
    assert receipt["sensitive_counters"]["sensitive_module_import_count"] == 1


def test_reconcile_rejects_invalid_final_without_marking_completed(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir = tmp_path / "state"
    final_dir = tmp_path / "artifacts/final"
    failure_dir = tmp_path / "artifacts/failed"
    monkeypatch.setattr(module, "EXECUTION_STATE_DIR", state_dir)
    monkeypatch.setattr(module, "CLAIM_PATH", state_dir / "claim.json")
    monkeypatch.setattr(module, "EXECUTION_EVENT_PATH", state_dir / "event.json")
    monkeypatch.setattr(module, "ARTIFACT_PARENT", tmp_path / "artifacts")
    monkeypatch.setattr(module, "FINAL_DIR", final_dir)
    monkeypatch.setattr(module, "FAILURE_DIR", failure_dir)
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": "a" * 64,
        "lease_id": "b" * 64,
        "replay_permitted": False,
    }
    module.create_execution_state(
        state_dir,
        claim=claim,
        campaign_nonce="a" * 64,
        lease_id="b" * 64,
    )
    module.update_execution_event(
        state_dir / "event.json",
        campaign_nonce="a" * 64,
        lease_id="b" * 64,
        status="running",
        phase="publish",
        counters=module.zero_sensitive_counters(),
    )
    final_dir.mkdir(parents=True)
    (final_dir / "summary.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(module.Stage001Error, match="success_"):
        module.reconcile_execution_state()

    assert not failure_dir.exists()
    event = _current_execution_event(module, state_dir / "event.json")
    assert event["status"] == "running"
    assert event["phase"] == "publish"


def test_reconcile_rejects_conflicting_success_and_failure_terminals(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir, final_dir, failure_dir = _patch_execution_paths(
        module,
        tmp_path,
        monkeypatch,
    )
    nonce = "a" * 64
    lease = "b" * 64
    module.create_execution_state(
        state_dir,
        claim={
            "schema_version": 1,
            "stage": module.STAGE,
            "line_id": module.LINE_ID,
            "campaign_nonce": nonce,
            "lease_id": lease,
            "replay_permitted": False,
        },
        campaign_nonce=nonce,
        lease_id=lease,
    )
    final_dir.mkdir(parents=True)
    failure_dir.mkdir(parents=True)

    with pytest.raises(module.Stage001Error, match="execution_terminal_conflict"):
        module.reconcile_execution_state()

    event = json.loads((state_dir / "event.json").read_text(encoding="utf-8"))
    assert event["status"] == "claimed"


def test_worker_environment_isolated_and_strips_execution_credentials(module, tmp_path) -> None:
    base = {
        "PATH": "/attacker/bin",
        "CTP_USERID": "secret",
        "CTP_PASSWORD": "secret",
        "VNPY_CTP_AUTH_CODE": "secret",
        "ORDER_SUBMIT_ENABLED": "1",
        "LIVE_TRADING": "1",
        "PYTHONPATH": "/attacker/python",
        "PYTHONHOME": "/attacker/home",
        "PYTHONSTARTUP": "/attacker/startup.py",
        "PYTHONINSPECT": "1",
        "PYTHONWARNINGS": "error",
        "DYLD_INSERT_LIBRARIES": "/attacker/lib.dylib",
        "LD_PRELOAD": "/attacker/lib.so",
        "STAGE001_SANDBOX_ENFORCED": "1",
        "ARBITRARY_PARENT_VALUE": "must-not-cross-boundary",
    }
    runtime = (tmp_path / "runtime").resolve()

    environment = module.worker_environment(base, runtime, "A1")

    assert environment == {
        "HOME": str(runtime / "home"),
        "LANG": "C",
        "LC_ALL": "C",
        "MPLCONFIGDIR": str(runtime / "mplconfig"),
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "PATH": "/usr/bin:/bin",
        "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR": "1",
        "TMPDIR": str(runtime / "tmp"),
        "VECLIB_MAXIMUM_THREADS": "1",
    }


def test_network_block_counts_and_rejects_connection_attempt(module) -> None:
    block = module._NetworkBlock()

    with block:
        with pytest.raises(module.Stage001Error, match="worker_network_connection_forbidden"):
            import socket

            socket.socket().connect(("127.0.0.1", 1))

    assert block.attempts == 1


def test_network_block_counts_and_rejects_connect_ex_bypass(module) -> None:
    block = module._NetworkBlock()

    with block:
        with pytest.raises(module.Stage001Error, match="worker_network_connection_forbidden"):
            import socket

            socket.socket().connect_ex(("127.0.0.1", 9))

    assert block.attempts == 1


def test_os_sandbox_blocks_network_child_network_and_external_write(
    module,
    tmp_path,
) -> None:
    worker_root = tmp_path / "worker"
    worker_root.mkdir()
    profile = module.write_worker_sandbox_profile(worker_root)
    denied_path = tmp_path / "outside-worker.txt"
    probe = """
import errno
import json
import socket
import subprocess
import sys
from pathlib import Path

worker_root = Path(sys.argv[1])
denied_path = Path(sys.argv[2])
(worker_root / 'allowed.txt').write_text('ok', encoding='utf-8')
direct = socket.socket().connect_ex(('127.0.0.1', 9))
try:
    subprocess.run(['/usr/bin/true'], check=True)
except PermissionError:
    child_spawn_denied = True
else:
    child_spawn_denied = False
try:
    denied_path.write_text('forbidden', encoding='utf-8')
except PermissionError:
    write_denied = True
else:
    write_denied = False
print(json.dumps({'direct': direct, 'child_spawn_denied': child_spawn_denied, 'write_denied': write_denied}))
"""
    completed = subprocess.run(
        module.sandboxed_command(
            profile,
            [sys.executable, "-c", probe, str(worker_root), str(denied_path)],
        ),
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    assert observed == {
        "direct": errno.EPERM,
        "child_spawn_denied": True,
        "write_denied": True,
    }
    assert not denied_path.exists()


@pytest.mark.parametrize(
    ("module_name", "function_name", "counter"),
    [
        ("sklearn.fake", "fit", "model_fit_count"),
        ("xgboost.fake", "predict", "prediction_count"),
        ("vnpy_ctp.fake", "query_account", "account_query_count"),
        ("vnpy_ctp.fake", "send_order", "order_api_called_count"),
        ("vnpy_ctp.fake", "connect", "ctp_connection_count"),
    ],
)
def test_sensitive_operation_guard_blocks_profiled_calls(
    module,
    tmp_path,
    module_name,
    function_name,
    counter,
) -> None:
    namespace = {"__name__": module_name}
    exec(f"def {function_name}():\n    return None\n", namespace)
    guard = module._SensitiveOperationGuard((tmp_path,))

    with pytest.raises(module.SensitiveOperationBlockedError):
        with guard:
            namespace[function_name]()

    assert guard.counters[counter] == 1


def test_sensitive_operation_guard_blocks_subprocess_and_production_write(
    module,
    tmp_path,
) -> None:
    subprocess_guard = module._SensitiveOperationGuard((tmp_path,))
    with pytest.raises(module.SensitiveOperationBlockedError, match="subprocess"):
        with subprocess_guard:
            subprocess.Popen(["/usr/bin/true"])
    assert subprocess_guard.counters["subprocess_spawn_count"] == 1

    write_guard = module._SensitiveOperationGuard((tmp_path,))
    forbidden = module.PRODUCTION_ROOT / "stage001_forbidden_write_probe.tmp"
    with pytest.raises(module.SensitiveOperationBlockedError, match="file_write"):
        with write_guard:
            forbidden.write_text("must-not-exist", encoding="utf-8")
    assert write_guard.counters["production_file_write_count"] == 1
    assert not forbidden.exists()


@pytest.mark.parametrize("entrypoint", ["system", "posix_spawn"])
def test_sensitive_operation_guard_blocks_os_process_entrypoints(
    module,
    tmp_path,
    entrypoint,
) -> None:
    guard = module._SensitiveOperationGuard((tmp_path,))

    with pytest.raises(module.SensitiveOperationBlockedError, match="subprocess"):
        with guard:
            if entrypoint == "system":
                os.system("/usr/bin/true")
            else:
                os.posix_spawn("/usr/bin/true", ["true"], os.environ)

    assert guard.counters["subprocess_spawn_count"] == 1


def test_input_manifest_builder_never_imports_production_or_spawns_git(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    source.write_text("frozen", encoding="utf-8")
    files = {"source": source}
    monkeypatch.setattr(module, "EXPECTED_INPUT_FILE_COUNT", 1)
    monkeypatch.setattr(
        module,
        "EXPECTED_INPUT_LOGICAL_KEY_SHA256",
        module.logical_key_contract_sha256(files),
    )
    monkeypatch.setattr(module, "collect_input_files", lambda: files)
    monkeypatch.setattr(
        module,
        "_active_formal_identity",
        lambda: {"identity": "frozen"},
    )
    monkeypatch.setattr(module, "_runtime_contract", lambda: {"runtime": "frozen"})
    monkeypatch.setattr(
        module,
        "_import_production_context",
        lambda: (_ for _ in ()).throw(AssertionError("production_import_forbidden")),
    )
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("subprocess_forbidden")
        ),
    )

    manifest = module.build_input_manifest()

    assert manifest["input_file_count"] == 1
    assert manifest["formal_identity"] == {"identity": "frozen"}


def test_runtime_contract_does_not_spawn_subprocess(
    module,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("subprocess_forbidden")
        ),
    )

    runtime = module._runtime_contract()

    assert runtime["python_version"] == sys.version
    assert runtime["platform"]["sysname"] == os.uname().sysname


def test_sensitive_counters_merge_worker_failure_evidence(module) -> None:
    counters = module.zero_sensitive_counters()
    receipt = {"sensitive_counters": module.zero_sensitive_counters()}
    receipt["sensitive_counters"]["network_connection_count"] = 1

    merged = module.merge_sensitive_counters(counters, receipt)

    assert merged["network_connection_count"] == 1
    assert sum(merged.values()) == 1


def test_validate_authorization_requires_exact_bound_files_and_live_lease(
    module,
    tmp_path,
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("first\n", encoding="utf-8")
    second.write_text("second\n", encoding="utf-8")
    files = {"first": first, "second": second}
    authorization = _authorization(module, files)

    result = module.validate_authorization(authorization, files)

    assert result["campaign_nonce"] == "a" * 64
    assert result["lease_id"] == "b" * 64

    authorization["bound_files"].pop("second")
    with pytest.raises(module.Stage001Error, match="authorization_bound_file_keys_mismatch"):
        module.validate_authorization(authorization, files)


def test_validate_authorization_detects_sha_drift_and_expiry(module, tmp_path) -> None:
    path = tmp_path / "bound.txt"
    path.write_text("before\n", encoding="utf-8")
    files = {"bound": path}
    authorization = _authorization(module, files)
    path.write_text("after\n", encoding="utf-8")

    with pytest.raises(module.Stage001Error, match="authorization_bound_file_drift"):
        module.validate_authorization(authorization, files)

    path.write_text("before\n", encoding="utf-8")
    authorization = _authorization(module, files)
    authorization["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with pytest.raises(module.Stage001Error, match="authorization_expired"):
        module.validate_authorization(authorization, files)


def test_authorization_payload_and_sha_are_derived_from_one_bytes_read(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "authorization.json"
    original_bytes = b'{"decision":"ALLOW_STAGE001_UNIQUE_RUN"}\n'
    path.write_bytes(original_bytes)
    real_read_bytes = Path.read_bytes
    reads: list[bytes] = []

    def tracked_read_bytes(candidate: Path) -> bytes:
        if candidate == path:
            payload = (
                original_bytes
                if not reads
                else b'{"decision":"BLOCK_STAGE001_UNIQUE_RUN"}\n'
            )
            reads.append(payload)
            return payload
        return real_read_bytes(candidate)

    monkeypatch.setattr(Path, "read_bytes", tracked_read_bytes)

    payload, digest = module._read_json_mapping_bytes_once(
        path,
        "authorization",
    )

    assert len(reads) == 1
    assert payload == {"decision": "ALLOW_STAGE001_UNIQUE_RUN"}
    assert digest == hashlib.sha256(original_bytes).hexdigest()


def test_assert_identity_stable_detects_any_file_or_runtime_drift(module) -> None:
    before = {
        "file_contract_sha256": "a" * 64,
        "runtime_contract_sha256": "b" * 64,
        "files": {
            "one": {
                "path": "/frozen/one",
                "size": 1,
                "mtime_ns": 2,
                "sha256": "c" * 64,
            }
        },
        "runtime": {"python": "frozen"},
    }
    module.assert_identity_stable(before, dict(before))

    after = json.loads(json.dumps(before))
    after["files"]["one"]["path"] = "/substituted/one"
    with pytest.raises(module.Stage001Error, match="input_identity_item_drift:one:path"):
        module.assert_identity_stable(before, after)

    after = json.loads(json.dumps(before))
    after["files"]["extra"] = dict(after["files"]["one"])
    with pytest.raises(module.Stage001Error, match="input_identity_keys_drift"):
        module.assert_identity_stable(before, after)


def test_file_identity_records_path_size_mtime_and_sha(module, tmp_path) -> None:
    path = tmp_path / "input.txt"
    path.write_text("input\n", encoding="utf-8")

    identity = module._file_identity(path)

    assert set(identity) == {"path", "size", "mtime_ns", "sha256"}
    assert identity["mtime_ns"] == path.stat().st_mtime_ns

    contract = module.file_contract_payload({"input": identity})
    assert contract["input"]["path"] == str(path.resolve())


def test_input_inventory_freezes_count_and_logical_keys(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    one = tmp_path / "one"
    one.write_text("1", encoding="utf-8")
    files = {"one": one}
    expected_key_sha = module.logical_key_contract_sha256(files)
    monkeypatch.setattr(module, "EXPECTED_INPUT_FILE_COUNT", 1)
    monkeypatch.setattr(module, "EXPECTED_INPUT_LOGICAL_KEY_SHA256", expected_key_sha)

    module.validate_input_inventory(files)

    with pytest.raises(module.Stage001Error, match="input_inventory_count_mismatch"):
        module.validate_input_inventory({"one": one, "extra": one})


def test_worker_isolation_requires_distinct_processes_and_directories(
    module,
    tmp_path,
) -> None:
    modules = {
        "stage901": "/frozen/stage901.py",
        "live_config": "/frozen/live_config.py",
        "vnpy_portfoliostrategy": "/frozen/vnpy_portfoliostrategy/__init__.py",
        "feature_tool": "/frozen/formal_signal_event_features.py",
    }
    receipt_a1 = _worker_receipt(module, "A1", 101, tmp_path / "A1", modules=modules)
    receipt_a2 = _worker_receipt(module, "A2", 102, tmp_path / "A2", modules=modules)

    result = module.evaluate_worker_isolation(
        [receipt_a1, receipt_a2],
        expected_source_contract_sha256="c" * 64,
        expected_database_sha256=hashlib.sha256(b"database-copy").hexdigest(),
        expected_python_executable=Path(sys.executable).resolve(),
        expected_modules=modules,
        expected_formal_identity=_formal_identity(module),
        expected_campaign_nonce="a" * 64,
        expected_lease_id="b" * 64,
    )

    assert result["passed"] is True
    receipt_a2["pid"] = receipt_a1["pid"]
    with pytest.raises(module.Stage001Error, match="worker_process_not_distinct"):
        module.evaluate_worker_isolation(
            [receipt_a1, receipt_a2],
            expected_source_contract_sha256="c" * 64,
            expected_database_sha256=hashlib.sha256(b"database-copy").hexdigest(),
            expected_python_executable=Path(sys.executable).resolve(),
            expected_modules=modules,
            expected_formal_identity=_formal_identity(module),
            expected_campaign_nonce="a" * 64,
            expected_lease_id="b" * 64,
        )


@pytest.mark.parametrize(
    ("field", "value", "error_code"),
    [
        ("home", "/tmp/outside-home", "worker_path_outside_runtime:home"),
        ("cwd", "/tmp/wrong-cwd", "worker_cwd_not_runtime"),
        ("python_executable", "/tmp/python", "worker_python_executable_drift"),
        ("source_file_contract_sha256", "f" * 64, "worker_source_contract_drift"),
        ("baseline_replay_count", 0, "worker_baseline_replay_count_invalid"),
        ("network_connection_attempt_count", 1, "worker_network_attempt_detected"),
        ("sensitive_guard_enforced", False, "worker_sensitive_guard_missing"),
        ("sandbox_enforced", False, "worker_sandbox_missing"),
    ],
)
def test_worker_isolation_rejects_missing_or_drifted_receipt_fields(
    module,
    tmp_path,
    field,
    value,
    error_code,
) -> None:
    modules = {
        "stage901": "/frozen/stage901.py",
        "live_config": "/frozen/live_config.py",
        "vnpy_portfoliostrategy": "/frozen/vnpy_portfoliostrategy/__init__.py",
        "feature_tool": "/frozen/formal_signal_event_features.py",
    }
    receipt_a1 = _worker_receipt(module, "A1", 101, tmp_path / "A1", modules=modules)
    receipt_a2 = _worker_receipt(module, "A2", 102, tmp_path / "A2", modules=modules)
    receipt_a2[field] = value

    with pytest.raises(module.Stage001Error, match=error_code):
        module.evaluate_worker_isolation(
            [receipt_a1, receipt_a2],
            expected_source_contract_sha256="c" * 64,
            expected_database_sha256=hashlib.sha256(b"database-copy").hexdigest(),
            expected_python_executable=Path(sys.executable).resolve(),
            expected_modules=modules,
            expected_formal_identity=_formal_identity(module),
            expected_campaign_nonce="a" * 64,
            expected_lease_id="b" * 64,
        )


def test_worker_isolation_rejects_sys_path_module_and_setting_drift(
    module,
    tmp_path,
) -> None:
    modules = {
        "stage901": "/frozen/stage901.py",
        "live_config": "/frozen/live_config.py",
        "vnpy_portfoliostrategy": "/frozen/vnpy_portfoliostrategy/__init__.py",
        "feature_tool": "/frozen/formal_signal_event_features.py",
    }
    receipt_a1 = _worker_receipt(module, "A1", 101, tmp_path / "A1", modules=modules)
    receipt_a2 = _worker_receipt(module, "A2", 102, tmp_path / "A2", modules=modules)

    receipt_a2["sys_path"] = ["/drifted"]
    with pytest.raises(module.Stage001Error, match="worker_sys_path_drift"):
        module.evaluate_worker_isolation(
            [receipt_a1, receipt_a2],
            expected_source_contract_sha256="c" * 64,
            expected_database_sha256=hashlib.sha256(b"database-copy").hexdigest(),
            expected_python_executable=Path(sys.executable).resolve(),
            expected_modules=modules,
            expected_formal_identity=_formal_identity(module),
            expected_campaign_nonce="a" * 64,
            expected_lease_id="b" * 64,
        )

    receipt_a2 = _worker_receipt(
        module,
        "A2",
        102,
        tmp_path / "A2-module-drift",
        modules=modules,
    )
    receipt_a2["modules"] = {**modules, "stage901": "/drifted.py"}
    with pytest.raises(module.Stage001Error, match="worker_module_receipt_drift"):
        module.evaluate_worker_isolation(
            [receipt_a1, receipt_a2],
            expected_source_contract_sha256="c" * 64,
            expected_database_sha256=hashlib.sha256(b"database-copy").hexdigest(),
            expected_python_executable=Path(sys.executable).resolve(),
            expected_modules=modules,
            expected_formal_identity=_formal_identity(module),
            expected_campaign_nonce="a" * 64,
            expected_lease_id="b" * 64,
        )

    receipt_a2 = _worker_receipt(
        module,
        "A2",
        102,
        tmp_path / "A2-setting-drift",
        modules=modules,
    )
    receipt_a2["setting"]["sha256"] = "0" * 64
    with pytest.raises(module.Stage001Error, match="worker_setting_sha_mismatch"):
        module.evaluate_worker_isolation(
            [receipt_a1, receipt_a2],
            expected_source_contract_sha256="c" * 64,
            expected_database_sha256=hashlib.sha256(b"database-copy").hexdigest(),
            expected_python_executable=Path(sys.executable).resolve(),
            expected_modules=modules,
            expected_formal_identity=_formal_identity(module),
            expected_campaign_nonce="a" * 64,
            expected_lease_id="b" * 64,
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda attestation: attestation["interpreter_flags"].__setitem__(
            "isolated", 0
        ),
        lambda attestation: attestation.__setitem__(
            "pre_import_forbidden_modules", ["pandas"]
        ),
        lambda attestation: attestation["sandbox_probe"].__setitem__(
            "write_denied", False
        ),
    ],
)
def test_worker_isolation_rejects_forged_bootstrap_attestation(
    module,
    tmp_path,
    mutate,
) -> None:
    modules = {
        "stage901": "/frozen/stage901.py",
        "live_config": "/frozen/live_config.py",
        "vnpy_portfoliostrategy": "/frozen/vnpy_portfoliostrategy/__init__.py",
        "feature_tool": "/frozen/formal_signal_event_features.py",
    }
    receipt_a1 = _worker_receipt(module, "A1", 101, tmp_path / "A1", modules=modules)
    receipt_a2 = _worker_receipt(module, "A2", 102, tmp_path / "A2", modules=modules)
    mutate(receipt_a2["bootstrap_attestation"])

    with pytest.raises(
        module.Stage001Error,
        match="worker_bootstrap_attestation_binding_invalid",
    ):
        module.evaluate_worker_isolation(
            [receipt_a1, receipt_a2],
            expected_source_contract_sha256="c" * 64,
            expected_database_sha256=hashlib.sha256(b"database-copy").hexdigest(),
            expected_python_executable=Path(sys.executable).resolve(),
            expected_modules=modules,
            expected_formal_identity=_formal_identity(module),
            expected_campaign_nonce="a" * 64,
            expected_lease_id="b" * 64,
        )


@pytest.mark.parametrize(
    ("mutator", "error_code"),
    [
        (lambda receipt: receipt.pop("status"), "worker_receipt_schema_invalid"),
        (
            lambda receipt: receipt.__setitem__("status", "failed"),
            "worker_status_not_completed",
        ),
        (
            lambda receipt: receipt["formal_identity"].__setitem__(
                "formal_release_id", "drifted"
            ),
            "worker_formal_identity_drift",
        ),
        (
            lambda receipt: receipt.__setitem__("started_at", "not-a-time"),
            "worker_timestamp_invalid:started_at",
        ),
        (
            lambda receipt: receipt.update(
                {
                    "started_at": "2026-09-05T08:02:00+08:00",
                    "completed_at": "2026-09-05T08:01:00+08:00",
                }
            ),
            "worker_timestamp_order_invalid",
        ),
        (
            lambda receipt: receipt.__setitem__("event_count", 999),
            "worker_event_count_mismatch",
        ),
        (
            lambda receipt: receipt.__setitem__("event_feature_sha256", "0" * 64),
            "worker_event_feature_sha_mismatch",
        ),
    ],
)
def test_worker_isolation_rejects_invalid_completion_evidence(
    module,
    tmp_path,
    mutator,
    error_code,
) -> None:
    modules = {
        "stage901": "/frozen/stage901.py",
        "live_config": "/frozen/live_config.py",
        "vnpy_portfoliostrategy": "/frozen/vnpy_portfoliostrategy/__init__.py",
        "feature_tool": "/frozen/formal_signal_event_features.py",
    }
    receipt_a1 = _worker_receipt(module, "A1", 101, tmp_path / "A1", modules=modules)
    receipt_a2 = _worker_receipt(module, "A2", 102, tmp_path / "A2", modules=modules)
    mutator(receipt_a2)

    with pytest.raises(module.Stage001Error, match=error_code):
        module.evaluate_worker_isolation(
            [receipt_a1, receipt_a2],
            expected_source_contract_sha256="c" * 64,
            expected_database_sha256=hashlib.sha256(b"database-copy").hexdigest(),
            expected_python_executable=Path(sys.executable).resolve(),
            expected_modules=modules,
            expected_formal_identity=_formal_identity(module),
            expected_campaign_nonce="a" * 64,
            expected_lease_id="b" * 64,
        )


@pytest.mark.parametrize(
    ("relative_path", "error_code"),
    [
        ("runtime/.vntrader/database.db", "worker_database_identity_drift"),
        ("runtime/.vntrader/vt_setting.json", "worker_setting_identity_drift"),
        ("stage001.sb", "worker_sandbox_profile_identity_drift"),
        ("output/event_features.csv", "worker_event_feature_identity_drift"),
    ],
)
def test_worker_isolation_cross_checks_receipts_against_actual_files(
    module,
    tmp_path,
    relative_path,
    error_code,
) -> None:
    modules = {
        "stage901": "/frozen/stage901.py",
        "live_config": "/frozen/live_config.py",
        "vnpy_portfoliostrategy": "/frozen/vnpy_portfoliostrategy/__init__.py",
        "feature_tool": "/frozen/formal_signal_event_features.py",
    }
    receipt_a1 = _worker_receipt(module, "A1", 101, tmp_path / "A1", modules=modules)
    receipt_a2 = _worker_receipt(module, "A2", 102, tmp_path / "A2", modules=modules)
    (tmp_path / "A2" / relative_path).write_bytes(b"drifted-after-receipt\n")

    with pytest.raises(module.Stage001Error, match=error_code):
        module.evaluate_worker_isolation(
            [receipt_a1, receipt_a2],
            expected_source_contract_sha256="c" * 64,
            expected_database_sha256=hashlib.sha256(b"database-copy").hexdigest(),
            expected_python_executable=Path(sys.executable).resolve(),
            expected_modules=modules,
            expected_formal_identity=_formal_identity(module),
            expected_campaign_nonce="a" * 64,
            expected_lease_id="b" * 64,
        )


def test_stage_gates_include_reproducibility_scope_and_zero_sensitive_counts(module) -> None:
    feature_qualification = {
        "passed": True,
        "gates": {
            "event_count_min": True,
            "full_year_coverage_min": True,
            "direction_coverage_min": True,
            "product_coverage_min": True,
            "event_identity_unique": True,
            "root_open_semantics": True,
            "fixed_fu_excluded": True,
            "all_features_finite": True,
            "all_features_nonconstant": True,
            "high_cardinality_feature_count": True,
        },
    }
    comparison = {"passed": True}

    result = module.evaluate_stage001_gates(
        formal_identity_exact=True,
        execution_identity_exact=True,
        interval_exact=True,
        worker_isolation={"passed": True},
        feature_qualification=feature_qualification,
        worker_comparison=comparison,
        identity_stable=True,
        eligibility_trace_exact=True,
        fixed_fu_cutoff_excluded=True,
        forbidden_output_columns_absent=True,
        production_unchanged=True,
        event_ledger_durable=True,
        sensitive_counters=module.zero_sensitive_counters(),
    )

    assert result["passed"] is True
    assert len(result["gates"]) == 13
    assert all(result["gates"].values())
    assert tuple(result["gates"]) == module.STAGE001_GATE_NAMES

    counters = module.zero_sensitive_counters()
    counters["model_fit_count"] = 1
    failed = module.evaluate_stage001_gates(
        formal_identity_exact=True,
        execution_identity_exact=True,
        interval_exact=True,
        worker_isolation={"passed": True},
        feature_qualification=feature_qualification,
        worker_comparison=comparison,
        identity_stable=True,
        eligibility_trace_exact=True,
        fixed_fu_cutoff_excluded=True,
        forbidden_output_columns_absent=True,
        production_unchanged=True,
        event_ledger_durable=True,
        sensitive_counters=counters,
    )
    assert failed["passed"] is False
    assert failed["gates"]["11_no_label_model_candidate_or_holdout_operations"] is False


def test_atomic_publish_refuses_existing_final_and_leaves_no_partial(module, tmp_path) -> None:
    source = tmp_path / "attempt"
    source.mkdir()
    (source / "summary.json").write_text("{}\n", encoding="utf-8")
    final = tmp_path / "final"

    module.atomic_publish_directory(source, final)

    assert final.is_dir()
    assert not source.exists()
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    with pytest.raises(module.Stage001Error, match="final_directory_exists"):
        module.atomic_publish_directory(replacement, final)
    assert replacement.is_dir()


def test_atomic_publish_rename_failure_preserves_source_and_no_final(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "summary.json").write_text("{}\n", encoding="utf-8")
    final = tmp_path / "final"
    real_replace = module.os.replace

    def fail_final_rename(candidate, destination):
        if Path(destination) == final:
            raise OSError("synthetic_final_rename_failure")
        return real_replace(candidate, destination)

    monkeypatch.setattr(module.os, "replace", fail_final_rename)

    with pytest.raises(OSError, match="synthetic_final_rename_failure"):
        module.atomic_publish_directory(source, final)

    assert source.is_dir()
    assert not final.exists()


def test_success_publish_staging_is_sibling_of_final(module, tmp_path, monkeypatch) -> None:
    attempt = tmp_path / f".{module.STAGE}_{'a' * 12}"
    attempt.mkdir()
    (attempt / "input_manifest.json").write_text("{}\n", encoding="utf-8")
    receipts = _success_worker_receipts(module, attempt)
    final = tmp_path / "final"
    monkeypatch.setattr(module, "ARTIFACT_PARENT", tmp_path)
    monkeypatch.setattr(module, "FINAL_DIR", final)
    features = _event_frame()
    inputs = _success_inputs(module)
    authorization = _success_authorization(module, inputs)

    _publish_success_bundle_for_test(
        module,
        attempt,
        features=features,
        summary=_success_summary(module, features, inputs),
        input_before=inputs,
        input_after=inputs,
        worker_receipts=receipts,
        authorization=authorization,
        claim=_success_claim(module, inputs, authorization),
    )

    assert final.is_dir()
    assert not attempt.exists()


def test_success_publish_preserves_portable_worker_evidence_after_cleanup(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    attempt = tmp_path / f".{module.STAGE}_{'a' * 12}"
    attempt.mkdir()
    (attempt / "workers").mkdir()
    inputs = _success_inputs(module)
    module._write_json(attempt / "input_manifest.json", inputs)
    modules = module.expected_worker_modules(inputs)
    receipts = [
        _worker_receipt(
            module,
            worker_id,
            pid,
            attempt / "workers" / worker_id,
            modules=modules,
        )
        for worker_id, pid in (("A1", 101), ("A2", 102))
    ]
    final = tmp_path / "final"
    monkeypatch.setattr(module, "ARTIFACT_PARENT", tmp_path)
    monkeypatch.setattr(module, "FINAL_DIR", final)
    features = _event_frame()
    summary = _success_summary(module, features, inputs)
    authorization = _success_authorization(module, inputs)

    _publish_success_bundle_for_test(
        module,
        attempt,
        features=features,
        summary=summary,
        input_before=inputs,
        input_after=inputs,
        worker_receipts=receipts,
        authorization=authorization,
        claim=_success_claim(module, inputs, authorization),
    )

    assert final.is_dir()
    assert not attempt.exists()
    payload = json.loads((final / "worker_receipts.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert [item["worker_id"] for item in payload["workers"]] == ["A1", "A2"]
    assert str(attempt.resolve()) not in json.dumps(payload, sort_keys=True)
    for receipt in payload["workers"]:
        assert set(receipt) == module.PORTABLE_WORKER_RECEIPT_FIELDS
        assert receipt["receipt_type"] == "portable_post_cleanup"
        assert receipt["database"]["source_input_logical_key"] == "source_database"
        assert receipt["database"]["verified_before_cleanup"] is True
        assert "path" not in receipt["database"]
        assert receipt["worker_log_published"] is False
        assert "worker_log" not in receipt
        for field in ("cwd", "runtime_root", "tmpdir", "mplconfigdir", "home"):
            assert receipt[field]["removed_after_publish"] is True
            assert "ephemeral_relative_path" in receipt[field]
        for field in (
            "setting",
            "sandbox_profile",
            "event_feature_file",
            "worker_capability",
            "raw_worker_receipt",
        ):
            evidence = final / receipt[field]["relative_path"]
            assert evidence.is_file()
            assert _sha256(evidence) == receipt[field]["sha256"]
        raw_receipt_path = final / receipt["raw_worker_receipt"]["relative_path"]
        raw_receipt = json.loads(raw_receipt_path.read_text(encoding="utf-8"))
        assert set(raw_receipt) == module.WORKER_SUCCESS_RECEIPT_FIELDS - {
            "feature_path"
        }
        assert receipt["raw_worker_receipt_sha256"] == _sha256(raw_receipt_path)
        assert raw_receipt["worker_id"] == receipt["worker_id"]
        assert raw_receipt["event_count"] == receipt["event_count"]
        assert receipt["feature_path"] == receipt["event_feature_file"]["relative_path"]
    manifest = json.loads((final / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert "workers/A1/event_features.csv" in manifest["files"]
    assert "workers/A2/worker_receipt.raw.json" in manifest["files"]
    assert "workers/A2/worker_capability.consumed.json" in manifest["files"]
    assert "workers/A2/worker.log" not in manifest["files"]
    module._validate_success_bundle(final)


def test_success_publish_rejects_parent_receipt_that_differs_from_raw_worker_receipt(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    attempt = tmp_path / f".{module.STAGE}_{'a' * 12}"
    attempt.mkdir()
    (attempt / "input_manifest.json").write_text("{}\n", encoding="utf-8")
    receipts = _success_worker_receipts(module, attempt)
    receipts[1]["event_count"] = 999
    final = tmp_path / "final"
    monkeypatch.setattr(module, "ARTIFACT_PARENT", tmp_path)
    monkeypatch.setattr(module, "FINAL_DIR", final)
    features = _event_frame()
    inputs = _success_inputs(module)
    authorization = _success_authorization(module, inputs)

    with pytest.raises(module.Stage001Error, match="portable_raw_receipt_drift:A2"):
        _publish_success_bundle_for_test(
            module,
            attempt,
            features=features,
            summary=_success_summary(module, features, inputs),
            input_before=inputs,
            input_after=inputs,
            worker_receipts=receipts,
            authorization=authorization,
            claim=_success_claim(module, inputs, authorization),
        )

    assert not final.exists()
    assert attempt.is_dir()


def test_success_bundle_validation_rejects_tampered_raw_worker_receipt(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    attempt = tmp_path / f".{module.STAGE}_{'a' * 12}"
    attempt.mkdir()
    (attempt / "input_manifest.json").write_text("{}\n", encoding="utf-8")
    receipts = _success_worker_receipts(module, attempt)
    final = tmp_path / "final"
    monkeypatch.setattr(module, "ARTIFACT_PARENT", tmp_path)
    monkeypatch.setattr(module, "FINAL_DIR", final)
    features = _event_frame()
    inputs = _success_inputs(module)
    authorization = _success_authorization(module, inputs)
    _publish_success_bundle_for_test(
        module,
        attempt,
        features=features,
        summary=_success_summary(module, features, inputs),
        input_before=inputs,
        input_after=inputs,
        worker_receipts=receipts,
        authorization=authorization,
        claim=_success_claim(module, inputs, authorization),
    )
    raw = final / "workers/A1/worker_receipt.raw.json"
    raw.write_text(raw.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(module.Stage001Error, match="portable_relative_identity_drift"):
        module._validate_success_bundle(final)


def _publish_valid_success_bundle(
    module,
    tmp_path,
    monkeypatch,
    *,
    authorization_path: Path | None = None,
):
    attempt = tmp_path / f".{module.STAGE}_{'a' * 12}"
    attempt.mkdir()
    (attempt / "input_manifest.json").write_text("{}\n", encoding="utf-8")
    receipts = _success_worker_receipts(module, attempt)
    final = tmp_path / "final"
    monkeypatch.setattr(module, "ARTIFACT_PARENT", tmp_path)
    monkeypatch.setattr(module, "FINAL_DIR", final)
    features = _event_frame()
    inputs = _success_inputs(module)
    authorization = _success_authorization(module, inputs)
    if authorization_path is not None:
        module._write_json(authorization_path, authorization)
    claim = _success_claim(
        module,
        inputs,
        authorization,
        authorization_path=authorization_path,
    )
    _publish_success_bundle_for_test(
        module,
        attempt,
        features=features,
        summary=_success_summary(module, features, inputs),
        input_before=inputs,
        input_after=inputs,
        worker_receipts=receipts,
        authorization=authorization,
        claim=claim,
    )
    return final, features, inputs, authorization, claim


def _prepare_unpublished_success_bundle(module, tmp_path, monkeypatch):
    monkeypatch.setattr(module, "ARTIFACT_PARENT", tmp_path)
    monkeypatch.setattr(module, "FINAL_DIR", tmp_path / "final")
    attempt = tmp_path / f".{module.STAGE}_{'a' * 12}"
    attempt.mkdir()
    receipts = _success_worker_receipts(module, attempt)
    features = _event_frame()
    inputs = _success_inputs(module)
    authorization = _success_authorization(module, inputs)
    claim = _success_claim(module, inputs, authorization)
    authorization_path = _bind_success_current_state(
        module,
        attempt=attempt,
        inputs=inputs,
        authorization=authorization,
        claim=claim,
    )
    summary = _success_summary(module, features, inputs)
    execution_event = _success_execution_event(
        module,
        features=features,
        summary=summary,
        inputs=inputs,
        authorization=authorization,
        claim=claim,
    )
    return {
        "attempt": attempt,
        "receipts": receipts,
        "features": features,
        "inputs": inputs,
        "authorization": authorization,
        "authorization_path": authorization_path,
        "claim": claim,
        "summary": summary,
        "execution_event": execution_event,
    }


def _publish_prepared_success_bundle(module, prepared) -> dict[str, object]:
    return module._publish_success_bundle(
        prepared["attempt"],
        features=prepared["features"],
        summary=prepared["summary"],
        input_before=prepared["inputs"],
        input_after=prepared["inputs"],
        worker_receipts=prepared["receipts"],
        authorization=prepared["authorization"],
        claim=prepared["claim"],
        execution_event=prepared["execution_event"],
    )


def _publish_prepared_success_with_state(module, tmp_path, monkeypatch):
    state_dir, _, _ = _patch_execution_paths(module, tmp_path, monkeypatch)
    prepared = _prepare_unpublished_success_bundle(module, tmp_path, monkeypatch)
    module.create_execution_state(
        state_dir,
        claim=prepared["claim"],
        campaign_nonce=prepared["claim"]["campaign_nonce"],
        lease_id=prepared["claim"]["lease_id"],
    )
    prepared["execution_event"] = _seed_execution_event_history(
        module,
        module.EXECUTION_EVENT_PATH,
        prepared["execution_event"],
    )
    cleanup = _publish_prepared_success_bundle(module, prepared)
    return prepared, cleanup


def _make_worker_receipt_internally_consistent_after_mutation(
    module,
    final: Path,
    *,
    worker_id: str,
    field: str,
    value: object,
) -> None:
    receipts_path = final / "worker_receipts.json"
    receipts = json.loads(receipts_path.read_text(encoding="utf-8"))
    portable = next(item for item in receipts["workers"] if item["worker_id"] == worker_id)
    raw_path = final / portable["raw_worker_receipt"]["relative_path"]
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw[field] = value
    module._write_json(raw_path, raw)
    portable[field] = value
    portable["raw_worker_receipt"] = module._relative_artifact_identity(raw_path, final)
    portable["raw_worker_receipt_sha256"] = portable["raw_worker_receipt"]["sha256"]
    module._write_json(receipts_path, receipts)
    module._write_json(final / "artifact_manifest.json", module._artifact_manifest(final))


@pytest.mark.parametrize(
    ("field", "value", "error_code"),
    [
        ("status", "failed", "success_worker_status_not_completed"),
        ("baseline_replay_count", 2, "success_worker_baseline_replay_count_invalid"),
        ("capital", 149_999.0, "success_worker_capital_drift"),
        ("analysis_end", "2026-08-27", "success_worker_interval_drift"),
        ("sandbox_enforced", False, "success_worker_sandbox_missing"),
        ("sensitive_guard_enforced", False, "success_worker_sensitive_guard_missing"),
    ],
)
def test_success_bundle_rejects_internally_consistent_invalid_worker_semantics(
    module,
    tmp_path,
    monkeypatch,
    field,
    value,
    error_code,
) -> None:
    final, _, _, _, _ = _publish_valid_success_bundle(module, tmp_path, monkeypatch)
    _make_worker_receipt_internally_consistent_after_mutation(
        module,
        final,
        worker_id="A1",
        field=field,
        value=value,
    )

    with pytest.raises(module.Stage001Error, match=error_code):
        module._validate_success_bundle(final)


def test_success_publish_persists_exact_input_manifest_and_execution_event(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    final, _, inputs, _, _ = _publish_valid_success_bundle(module, tmp_path, monkeypatch)

    assert json.loads((final / "input_manifest.json").read_text(encoding="utf-8")) == inputs
    event = json.loads((final / "execution_event.json").read_text(encoding="utf-8"))
    assert event["status"] == "running"
    assert event["phase"] == "publishing_success"
    assert event["counters"] == module.zero_sensitive_counters()


def test_success_bundle_rejects_current_authorization_identity_drift(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    authorization_path = tmp_path / "stage001_execution_authorization.json"
    final, _, _, _, _ = _publish_valid_success_bundle(
        module,
        tmp_path,
        monkeypatch,
        authorization_path=authorization_path,
    )
    monkeypatch.setattr(
        module,
        "authorization_bound_files",
        lambda: {"stage001_runner": MODULE_PATH},
    )
    authorization_path.write_text(
        authorization_path.read_text(encoding="utf-8") + " ",
        encoding="utf-8",
    )

    with pytest.raises(
        module.Stage001Error,
        match="success_current_authorization_identity_drift",
    ):
        module._validate_success_bundle(
            final,
            revalidate_current_authorization=True,
        )


def test_success_current_running_event_must_equal_published_event(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    final, _, _, _, _ = _publish_valid_success_bundle(module, tmp_path, monkeypatch)
    publishing_event = json.loads(
        (final / "execution_event.json").read_text(encoding="utf-8")
    )
    current = json.loads(json.dumps(publishing_event))
    current["phase"] = "publish"

    with pytest.raises(
        module.Stage001Error,
        match="success_current_running_event_drift",
    ):
        module._validate_current_success_event(
            current,
            publishing_event=publishing_event,
            root=final,
        )


def test_success_publish_rejects_current_input_drift_before_final_rename(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    prepared = _prepare_unpublished_success_bundle(module, tmp_path, monkeypatch)
    drifted = json.loads(json.dumps(prepared["inputs"]))
    drifted["files"]["source_database"]["sha256"] = "f" * 64
    drifted["file_contract_sha256"] = hashlib.sha256(
        module._stable_json_bytes(module.file_contract_payload(drifted["files"]))
    ).hexdigest()
    monkeypatch.setattr(module, "build_input_manifest", lambda **_kwargs: drifted)

    with pytest.raises(
        module.Stage001Error,
        match="success_current_input_identity_drift",
    ):
        _publish_prepared_success_bundle(module, prepared)

    assert not module.FINAL_DIR.exists()


def test_success_publish_rejects_current_authorization_drift_before_final_rename(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    prepared = _prepare_unpublished_success_bundle(module, tmp_path, monkeypatch)
    authorization_path = prepared["authorization_path"]
    authorization_path.write_text(
        authorization_path.read_text(encoding="utf-8") + " ",
        encoding="utf-8",
    )

    with pytest.raises(
        module.Stage001Error,
        match="success_current_authorization_identity_drift",
    ):
        _publish_prepared_success_bundle(module, prepared)

    assert not module.FINAL_DIR.exists()


def test_success_publish_rejects_current_bound_file_drift_before_final_rename(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    prepared = _prepare_unpublished_success_bundle(module, tmp_path, monkeypatch)
    bound_file = tmp_path / "bound_runner.py"
    bound_file.write_text("before\n", encoding="utf-8")
    prepared["authorization"]["bound_files"] = {
        "bound_runner": {
            "path": str(bound_file.resolve()),
            "sha256": _sha256(bound_file),
        }
    }
    module._write_json(
        prepared["authorization_path"],
        prepared["authorization"],
    )
    prepared["claim"]["authorization_sha256"] = _sha256(
        prepared["authorization_path"]
    )
    prepared["claim"]["authorization_payload_sha256"] = hashlib.sha256(
        module._stable_json_bytes(prepared["authorization"])
    ).hexdigest()
    module.authorization_bound_files = lambda: {"bound_runner": bound_file}
    prepared["execution_event"] = _success_execution_event(
        module,
        features=prepared["features"],
        summary=prepared["summary"],
        inputs=prepared["inputs"],
        authorization=prepared["authorization"],
        claim=prepared["claim"],
    )
    bound_file.write_text("after\n", encoding="utf-8")

    with pytest.raises(
        module.Stage001Error,
        match="success_current_authorization_invalid",
    ):
        _publish_prepared_success_bundle(module, prepared)

    assert not module.FINAL_DIR.exists()


def test_success_publish_rejects_current_input_drift_after_final_rename(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    prepared = _prepare_unpublished_success_bundle(module, tmp_path, monkeypatch)
    drifted = json.loads(json.dumps(prepared["inputs"]))
    drifted["runtime"]["python_version"] = "drifted-after-rename"
    drifted["runtime_contract_sha256"] = hashlib.sha256(
        module._stable_json_bytes(drifted["runtime"])
    ).hexdigest()
    real_atomic_publish = module.atomic_publish_directory

    def publish_then_drift(source: Path, final: Path) -> None:
        real_atomic_publish(source, final)
        module.build_input_manifest = lambda **_kwargs: drifted

    monkeypatch.setattr(module, "atomic_publish_directory", publish_then_drift)

    with pytest.raises(
        module.Stage001Error,
        match="success_current_input_identity_drift",
    ):
        _publish_prepared_success_bundle(module, prepared)

    assert module.FINAL_DIR.is_dir()


def test_success_bundle_revalidates_complete_current_input_manifest(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    final, _, inputs, _, _ = _publish_valid_success_bundle(module, tmp_path, monkeypatch)
    drifted = json.loads(json.dumps(inputs))
    drifted["files"]["source_database"]["sha256"] = "f" * 64
    drifted["file_contract_sha256"] = hashlib.sha256(
        module._stable_json_bytes(module.file_contract_payload(drifted["files"]))
    ).hexdigest()
    monkeypatch.setattr(
        module,
        "build_input_manifest",
        lambda **_kwargs: drifted,
    )
    monkeypatch.setattr(module, "EXPECTED_INPUT_FILE_COUNT", inputs["input_file_count"])
    monkeypatch.setattr(
        module,
        "EXPECTED_INPUT_LOGICAL_KEY_SHA256",
        inputs["input_logical_key_sha256"],
    )

    with pytest.raises(module.Stage001Error, match="success_current_input_identity_drift"):
        module._validate_success_bundle(final, revalidate_current_inputs=True)


def test_correlation_trace_exposes_candidate_history_unavailable_before_peer_scan(
    module,
) -> None:
    class State:
        contract_vt_symbol = "cu2610.SHFE"
        direction = "long"

    class Strategy:
        enable_same_direction_correlation_gate = True
        same_direction_correlation_gate_lookback = 20
        states = {"cu.SHFE": State()}
        ams = {}

        @staticmethod
        def _history_return_vector(_history, _lookback):
            return pd.Series(dtype="float64").to_numpy()

        @staticmethod
        def get_pos(symbol):
            return 1 if symbol == "cu2610.SHFE" else 0

    trace = module._independent_correlation_trace(
        Strategy(),
        contract_vt_symbol="rb2610.SHFE",
        direction="long",
        history=pd.DataFrame({"close": [100.0]}),
        entry_context="flat_entry",
        original_snapshot={
            "same_direction_correlation_gate_enabled": 1,
            "same_direction_correlation_active_count": 0,
            "same_direction_correlation_corr_count": 0,
            "same_direction_correlation_max_corr": 0.0,
        },
    )

    assert trace["same_direction_correlation_candidate_history_available"] == 0
    assert trace["same_direction_correlation_active_count_recomputed"] == 1
    assert trace["same_direction_correlation_trace_exact"] == 0


def test_success_bundle_rejects_unexpected_file_even_with_recomputed_manifest(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    final, _, _, _, _ = _publish_valid_success_bundle(module, tmp_path, monkeypatch)
    (final / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
    module._write_json(final / "artifact_manifest.json", module._artifact_manifest(final))

    with pytest.raises(module.Stage001Error, match="success_file_set_drift"):
        module._validate_success_bundle(final)


def test_success_bundle_binds_published_features_to_both_workers(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    final, features, _, _, _ = _publish_valid_success_bundle(
        module,
        tmp_path,
        monkeypatch,
    )
    tampered = features.copy()
    tampered.loc[0, "formal_score"] += 0.01
    module._write_deterministic_gzip_csv(final / "event_features.csv.gz", tampered)
    module._write_json(final / "artifact_manifest.json", module._artifact_manifest(final))

    with pytest.raises(module.Stage001Error, match="success_event_feature_sha_drift"):
        module._validate_success_bundle(final)


def test_success_bundle_binds_summary_to_campaign_and_all_thirteen_gates(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    final, _, _, _, _ = _publish_valid_success_bundle(module, tmp_path, monkeypatch)
    summary = json.loads((final / "summary.json").read_text(encoding="utf-8"))
    summary["campaign_nonce"] = "f" * 64
    summary["stage001_gates"]["gates"].pop(module.STAGE001_GATE_NAMES[-1])
    module._write_json(final / "summary.json", summary)
    module._write_json(final / "artifact_manifest.json", module._artifact_manifest(final))

    with pytest.raises(module.Stage001Error, match="success_summary_"):
        module._validate_success_bundle(final)


def test_success_bundle_binds_authorization_to_execution_claim(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    final, _, _, _, _ = _publish_valid_success_bundle(module, tmp_path, monkeypatch)
    authorization = json.loads(
        (final / "authorization_receipt.json").read_text(encoding="utf-8")
    )
    authorization["lease_id"] = "f" * 64
    module._write_json(final / "authorization_receipt.json", authorization)
    module._write_json(final / "artifact_manifest.json", module._artifact_manifest(final))

    with pytest.raises(module.Stage001Error, match="success_authorization_binding_invalid"):
        module._validate_success_bundle(final)


def test_success_completion_revalidates_current_input_before_sequence_seven(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir, _, _ = _patch_execution_paths(module, tmp_path, monkeypatch)
    prepared = _prepare_unpublished_success_bundle(module, tmp_path, monkeypatch)
    module.create_execution_state(
        state_dir,
        claim=prepared["claim"],
        campaign_nonce=prepared["claim"]["campaign_nonce"],
        lease_id=prepared["claim"]["lease_id"],
    )
    prepared["execution_event"] = _seed_execution_event_history(
        module,
        module.EXECUTION_EVENT_PATH,
        prepared["execution_event"],
    )
    cleanup = _publish_prepared_success_bundle(module, prepared)
    drifted = json.loads(json.dumps(prepared["inputs"]))
    drifted["runtime"]["python_version"] = "drifted"
    drifted["runtime_contract_sha256"] = hashlib.sha256(
        module._stable_json_bytes(drifted["runtime"])
    ).hexdigest()
    monkeypatch.setattr(module, "build_input_manifest", lambda **_kwargs: drifted)

    with pytest.raises(
        module.Stage001Error,
        match="success_current_input_identity_drift",
    ):
        module._complete_success_publication(
            claim=prepared["claim"],
            publishing_event=prepared["execution_event"],
            counters=module.zero_sensitive_counters(),
            cleanup=cleanup,
        )

    event = _current_execution_event(module, module.EXECUTION_EVENT_PATH)
    assert event["status"] == "running"
    assert event["sequence"] == 6


def test_success_completion_revalidates_authorization_before_sequence_seven(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir, _, _ = _patch_execution_paths(module, tmp_path, monkeypatch)
    prepared = _prepare_unpublished_success_bundle(module, tmp_path, monkeypatch)
    module.create_execution_state(
        state_dir,
        claim=prepared["claim"],
        campaign_nonce=prepared["claim"]["campaign_nonce"],
        lease_id=prepared["claim"]["lease_id"],
    )
    prepared["execution_event"] = _seed_execution_event_history(
        module,
        module.EXECUTION_EVENT_PATH,
        prepared["execution_event"],
    )
    cleanup = _publish_prepared_success_bundle(module, prepared)
    authorization_path = prepared["authorization_path"]
    authorization_path.write_text(
        authorization_path.read_text(encoding="utf-8") + " ",
        encoding="utf-8",
    )

    with pytest.raises(
        module.Stage001Error,
        match="success_current_authorization_identity_drift",
    ):
        module._complete_success_publication(
            claim=prepared["claim"],
            publishing_event=prepared["execution_event"],
            counters=module.zero_sensitive_counters(),
            cleanup=cleanup,
        )

    event = _current_execution_event(module, module.EXECUTION_EVENT_PATH)
    assert event["status"] == "running"
    assert event["sequence"] == 6


def test_success_completion_is_exactly_idempotent_without_sequence_increment(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    prepared, cleanup = _publish_prepared_success_with_state(
        module,
        tmp_path,
        monkeypatch,
    )
    completion_args = {
        "claim": prepared["claim"],
        "publishing_event": prepared["execution_event"],
        "counters": module.zero_sensitive_counters(),
        "cleanup": cleanup,
    }

    module._complete_success_publication(**completion_args)
    completed, completed_bytes, completed_path = _current_execution_event_document(
        module,
        module.EXECUTION_EVENT_PATH,
    )
    module._complete_success_publication(**completion_args)

    assert completed["status"] == "completed"
    assert completed["sequence"] == 7
    repeated, repeated_bytes, repeated_path = _current_execution_event_document(
        module,
        module.EXECUTION_EVENT_PATH,
    )
    assert repeated == completed
    assert repeated_bytes == completed_bytes
    assert repeated_path == completed_path


def test_two_concurrent_success_completions_converge_on_exact_sequence_seven(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    prepared, cleanup = _publish_prepared_success_with_state(
        module,
        tmp_path,
        monkeypatch,
    )
    start = threading.Barrier(2)
    errors: list[BaseException] = []

    def complete() -> None:
        start.wait(timeout=5)
        try:
            module._complete_success_publication(
                claim=prepared["claim"],
                publishing_event=prepared["execution_event"],
                counters=module.zero_sensitive_counters(),
                cleanup=cleanup,
            )
        except BaseException as exc:
            errors.append(exc)

    contenders = [threading.Thread(target=complete) for _ in range(2)]
    for contender in contenders:
        contender.start()
    for contender in contenders:
        contender.join(timeout=10)

    assert not any(contender.is_alive() for contender in contenders)
    assert errors == []
    event = _current_execution_event(module, module.EXECUTION_EVENT_PATH)
    assert event["status"] == "completed"
    assert event["sequence"] == 7


def test_success_completion_compare_and_swap_rejects_concurrent_event_drift(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    prepared, cleanup = _publish_prepared_success_with_state(
        module,
        tmp_path,
        monkeypatch,
    )
    observed_drift: dict[str, object] = {}

    def drift_before_replace(path: Path, lock_descriptor: int) -> None:
        current, _, current_name = module._read_current_execution_event(
            path,
            lock_descriptor=lock_descriptor,
        )
        drifted = dict(current)
        drifted["phase"] = "concurrent_writer_drift"
        module._atomic_replace_json(path.with_name(current_name), drifted)
        observed_drift.update(drifted)

    monkeypatch.setattr(
        module,
        "_execution_event_before_replace_hook",
        drift_before_replace,
        raising=False,
    )

    with pytest.raises(
        module.Stage001Error,
        match="execution_event_compare_and_swap_mismatch",
    ):
        module._complete_success_publication(
            claim=prepared["claim"],
            publishing_event=prepared["execution_event"],
            counters=module.zero_sensitive_counters(),
            cleanup=cleanup,
        )

    assert _current_execution_event(
        module,
        module.EXECUTION_EVENT_PATH,
    ) == observed_drift


def test_reconcile_revalidates_current_inputs_after_attempt_cleanup(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    prepared, _ = _publish_prepared_success_with_state(
        module,
        tmp_path,
        monkeypatch,
    )
    attempt_path = Path(
        str(prepared["execution_event"]["details"]["attempt_dir"])
    )
    attempt_path.mkdir()
    (attempt_path / "interrupted.txt").write_text("pending cleanup\n", encoding="utf-8")
    drifted = json.loads(json.dumps(prepared["inputs"]))
    drifted["runtime"]["python_version"] = "drifted-during-recovery-cleanup"
    drifted["runtime_contract_sha256"] = hashlib.sha256(
        module._stable_json_bytes(drifted["runtime"])
    ).hexdigest()
    real_rmtree = module.shutil.rmtree

    def cleanup_then_drift(path, *args, **kwargs):
        result = real_rmtree(path, *args, **kwargs)
        if Path(path).resolve() == attempt_path.resolve():
            module.build_input_manifest = lambda **_kwargs: drifted
        return result

    monkeypatch.setattr(module.shutil, "rmtree", cleanup_then_drift)

    with pytest.raises(
        module.Stage001Error,
        match="success_current_input_identity_drift",
    ):
        module.reconcile_execution_state()

    event = _current_execution_event(module, module.EXECUTION_EVENT_PATH)
    assert event["status"] == "running"
    assert event["phase"] == "publishing_success"
    assert event["sequence"] == 6


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    (
        ("delete", "execution_event_claim_missing"),
        ("replace", "execution_event_claim_binding_mismatch"),
    ),
)
def test_reconcile_rejects_current_claim_drift_after_attempt_cleanup(
    module,
    tmp_path,
    monkeypatch,
    mutation,
    error_code,
) -> None:
    prepared, _ = _publish_prepared_success_with_state(
        module,
        tmp_path,
        monkeypatch,
    )
    attempt_path = Path(
        str(prepared["execution_event"]["details"]["attempt_dir"])
    )
    attempt_path.mkdir()
    (attempt_path / "interrupted.txt").write_text("pending cleanup\n", encoding="utf-8")
    original_event, original_event_bytes, original_event_path = (
        _current_execution_event_document(module, module.EXECUTION_EVENT_PATH)
    )
    original_journal_names = sorted(
        path.name for path in module.EXECUTION_STATE_DIR.glob("event.seq-*.json")
    )
    real_rmtree = module.shutil.rmtree

    def cleanup_then_mutate_claim(path, *args, **kwargs):
        result = real_rmtree(path, *args, **kwargs)
        if Path(path).resolve() == attempt_path.resolve():
            if mutation == "delete":
                module.CLAIM_PATH.unlink()
            else:
                drifted = json.loads(json.dumps(prepared["claim"]))
                drifted["authorization_sha256"] = "f" * 64
                module._atomic_replace_json(module.CLAIM_PATH, drifted)
        return result

    monkeypatch.setattr(module.shutil, "rmtree", cleanup_then_mutate_claim)

    with pytest.raises(module.Stage001Error, match=error_code):
        module.reconcile_execution_state()

    assert json.loads(original_event_path.read_bytes()) == original_event
    assert original_event_path.read_bytes() == original_event_bytes
    assert sorted(
        path.name for path in module.EXECUTION_STATE_DIR.glob("event.seq-*.json")
    ) == original_journal_names


def test_final_renamed_error_preserves_initial_and_reconcile_failures(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    _, final, _ = _patch_execution_paths(module, tmp_path, monkeypatch)
    calls = 0

    def reconcile_then_fail():
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"reconciled": False}
        raise module.Stage001Error("permanent_current_binding_drift")

    inputs = {"file_contract_sha256": "c" * 64}
    monkeypatch.setattr(module, "reconcile_execution_state", reconcile_then_fail)
    monkeypatch.setattr(module, "validate_prerun_decision", lambda: {"allowed": True})
    monkeypatch.setattr(module, "build_input_manifest", lambda: inputs)
    monkeypatch.setattr(
        module,
        "_read_json_mapping_bytes_once",
        lambda *_args: ({}, "d" * 64),
    )
    monkeypatch.setattr(
        module,
        "validate_authorization",
        lambda *_args, **_kwargs: {
            "campaign_nonce": "a" * 64,
            "lease_id": "b" * 64,
        },
    )
    monkeypatch.setattr(module, "create_execution_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "update_execution_event", lambda *_args, **_kwargs: None)

    def publish_final_then_fail(*_args, **_kwargs):
        final.mkdir(parents=True)
        raise RuntimeError("initial_completion_failure")

    monkeypatch.setattr(module, "_run_worker", publish_final_then_fail)

    with pytest.raises(module.Stage001Error) as raised:
        module.run_stage001(tmp_path / "authorization.json")

    message = str(raised.value)
    assert "initial=RuntimeError:initial_completion_failure" in message
    assert "reconcile=Stage001Error:permanent_current_binding_drift" in message
    assert isinstance(raised.value.__cause__, module.Stage001Error)
    assert str(raised.value.__cause__) == "permanent_current_binding_drift"


def test_nonfinal_failure_preserves_initial_publish_and_event_update_errors(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    _patch_execution_paths(module, tmp_path, monkeypatch)
    inputs = {"file_contract_sha256": "c" * 64}
    monkeypatch.setattr(module, "reconcile_execution_state", lambda: {})
    monkeypatch.setattr(module, "validate_prerun_decision", lambda: {"allowed": True})
    monkeypatch.setattr(module, "build_input_manifest", lambda: inputs)
    monkeypatch.setattr(
        module,
        "_read_json_mapping_bytes_once",
        lambda *_args: ({}, "d" * 64),
    )
    monkeypatch.setattr(
        module,
        "validate_authorization",
        lambda *_args, **_kwargs: {
            "campaign_nonce": "a" * 64,
            "lease_id": "b" * 64,
        },
    )
    monkeypatch.setattr(module, "create_execution_state", lambda *_args, **_kwargs: None)

    def update_event(*_args, **kwargs):
        if kwargs.get("status") == "failed":
            raise OSError("synthetic_event_update_failure")

    monkeypatch.setattr(module, "update_execution_event", update_event)
    monkeypatch.setattr(
        module,
        "_run_worker",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic_initial_worker_failure")
        ),
    )
    monkeypatch.setattr(
        module,
        "_publish_failure_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("synthetic_failure_publish_failure")
        ),
    )

    with pytest.raises(module.Stage001Error) as raised:
        module.run_stage001(tmp_path / "authorization.json")

    message = str(raised.value)
    assert "initial=RuntimeError:synthetic_initial_worker_failure" in message
    assert "failure_publish=OSError:synthetic_failure_publish_failure" in message
    assert "event_update=OSError:synthetic_event_update_failure" in message
    assert isinstance(raised.value.__cause__, OSError)
    assert str(raised.value.__cause__) == "synthetic_event_update_failure"


def test_reconcile_only_marks_completed_for_fully_valid_bound_success_bundle(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir, final, _ = _patch_execution_paths(module, tmp_path, monkeypatch)
    attempt = module.ARTIFACT_PARENT / f".{module.STAGE}_{'a' * 12}"
    attempt.mkdir(parents=True)
    (attempt / "input_manifest.json").write_text("{}\n", encoding="utf-8")
    receipts = _success_worker_receipts(module, attempt)
    features = _event_frame()
    inputs = _success_inputs(module)
    authorization = _success_authorization(module, inputs)
    authorization_path = tmp_path / "stage001_execution_authorization.json"
    module._write_json(authorization_path, authorization)
    claim = _success_claim(
        module,
        inputs,
        authorization,
        authorization_path=authorization_path,
    )
    publishing_event = _success_execution_event(
        module,
        features=features,
        summary=_success_summary(module, features, inputs),
        inputs=inputs,
        authorization=authorization,
        claim=claim,
    )
    module.create_execution_state(
        state_dir,
        claim=claim,
        campaign_nonce=claim["campaign_nonce"],
        lease_id=claim["lease_id"],
    )
    publishing_event = _seed_execution_event_history(
        module,
        state_dir / "event.json",
        publishing_event,
    )
    monkeypatch.setattr(module, "build_input_manifest", lambda **_kwargs: inputs)
    monkeypatch.setattr(module, "EXPECTED_INPUT_FILE_COUNT", inputs["input_file_count"])
    monkeypatch.setattr(
        module,
        "EXPECTED_INPUT_LOGICAL_KEY_SHA256",
        inputs["input_logical_key_sha256"],
    )
    monkeypatch.setattr(
        module,
        "authorization_bound_files",
        lambda: {"stage001_runner": MODULE_PATH},
    )
    _publish_success_bundle_for_test(
        module,
        attempt,
        features=features,
        summary=_success_summary(module, features, inputs),
        input_before=inputs,
        input_after=inputs,
        worker_receipts=receipts,
        authorization=authorization,
        claim=claim,
        execution_event=publishing_event,
    )

    result = module.reconcile_execution_state()

    assert result["terminal"] == "completed"
    event = _current_execution_event(module, state_dir / "event.json")
    assert event["status"] == "completed"
    assert final.is_dir()


def test_success_publish_is_terminal_before_attempt_cleanup(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    attempt = tmp_path / f".{module.STAGE}_{'a' * 12}"
    attempt.mkdir()
    (attempt / "input_manifest.json").write_text("{}\n", encoding="utf-8")
    receipts = _success_worker_receipts(module, attempt)
    final = tmp_path / "final"
    monkeypatch.setattr(module, "ARTIFACT_PARENT", tmp_path)
    monkeypatch.setattr(module, "FINAL_DIR", final)
    real_rmtree = module.shutil.rmtree

    def fail_attempt_cleanup(path, *args, **kwargs):
        if Path(path) == attempt:
            raise OSError("synthetic_cleanup_failure")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "rmtree", fail_attempt_cleanup)
    features = _event_frame()
    inputs = _success_inputs(module)
    authorization = _success_authorization(module, inputs)

    cleanup = _publish_success_bundle_for_test(
        module,
        attempt,
        features=features,
        summary=_success_summary(module, features, inputs),
        input_before=inputs,
        input_after=inputs,
        worker_receipts=receipts,
        authorization=authorization,
        claim=_success_claim(module, inputs, authorization),
    )

    assert final.is_dir()
    assert attempt.is_dir()
    assert cleanup["attempt_cleanup_completed"] is False
    assert "synthetic_cleanup_failure" in cleanup["attempt_cleanup_error"]


def test_artifact_manifest_paths_remain_valid_after_atomic_rename(module, tmp_path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "summary.json").write_text("{}\n", encoding="utf-8")

    manifest = module._artifact_manifest(staging)

    item = manifest["files"]["summary.json"]
    assert item["relative_path"] == "summary.json"
    assert "path" not in item


def test_public_parser_requires_run_and_authorization(module) -> None:
    parser = module.build_parser()

    parsed = parser.parse_args(["--run", "--authorization", "/tmp/auth.json"])
    assert parsed.run is True
    assert parsed.authorization == Path("/tmp/auth.json")
    with pytest.raises(SystemExit):
        parser.parse_args(["--authorization", "/tmp/auth.json"])


def test_direct_worker_cli_requires_parent_capability_before_output(
    module,
    tmp_path,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    output = tmp_path / "output"
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--worker",
            "A1",
            "--runtime-root",
            str(runtime),
            "--worker-output",
            str(output),
            "--expected-manifest",
            str(manifest),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "worker_arguments_missing" in completed.stderr
    assert not output.exists()


def test_forged_worker_environment_cannot_bypass_required_bootstrap(
    module,
    tmp_path,
) -> None:
    artifact_parent = tmp_path / "artifacts"
    nonce = "a" * 64
    lease = "b" * 64
    attempt = artifact_parent / f".{module.STAGE}_{nonce[:12]}"
    worker_root = attempt / "workers/A1"
    runtime = worker_root / "runtime"
    runtime.mkdir(parents=True)
    output = worker_root / "output"
    manifest = attempt / "input_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    profile = module.write_worker_sandbox_profile(worker_root)
    capability = worker_root / "worker_capability.json"
    capability.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "stage": module.STAGE,
                "line_id": module.LINE_ID,
                "campaign_nonce": nonce,
                "lease_id": lease,
                "worker_id": "A1",
                "capability_nonce": "c" * 64,
                "attempt_dir": str(attempt.resolve()),
                "runtime_root": str(runtime.resolve()),
                "output_dir": str(output.resolve()),
                "input_manifest_path": str(manifest.resolve()),
                "input_manifest_sha256": _sha256(manifest),
                "sandbox_profile_path": str(profile.resolve()),
                "sandbox_profile_sha256": _sha256(profile),
                "runner_path": str(MODULE_PATH.resolve()),
                "runner_sha256": _sha256(MODULE_PATH),
                "issued_at": "2026-09-05T08:00:00+08:00",
                "replay_permitted": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    script = r"""
import argparse
import importlib.util
import sys
from pathlib import Path

module_path = Path(sys.argv[1])
artifact_parent = Path(sys.argv[2])
state_dir = Path(sys.argv[3])
runtime = Path(sys.argv[4])
output = Path(sys.argv[5])
manifest = Path(sys.argv[6])
capability = Path(sys.argv[7])
spec = importlib.util.spec_from_file_location("stage001_forged_worker", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.ARTIFACT_PARENT = artifact_parent
module.EXECUTION_STATE_DIR = state_dir
module.CLAIM_PATH = state_dir / "claim.json"
module.EXECUTION_EVENT_PATH = state_dir / "event.json"
args = argparse.Namespace(
    worker="A1",
    runtime_root=runtime,
    worker_output=output,
    expected_manifest=manifest,
    worker_capability=capability,
)
try:
    module._worker_main(args)
except BaseException as exc:
    print(f"{type(exc).__name__}:{exc}", file=sys.stderr)
    raise SystemExit(2)
raise SystemExit(0)
"""
    environment = dict(os.environ)
    environment.update(
        {
            "STAGE001_WORKER_ID": "A1",
            "STAGE001_NETWORK_POLICY": "deny",
            "STAGE001_SANDBOX_ENFORCED": "1",
            "STAGE001_SANDBOX_POLICY_MODE": module.SANDBOX_POLICY_MODE,
            "STAGE001_SANDBOX_EXECUTABLE": str(
                module.SANDBOX_EXECUTABLE.resolve()
            ),
            "STAGE001_SANDBOX_PROFILE_PATH": str(profile.resolve()),
            "STAGE001_SANDBOX_PROFILE_SHA256": _sha256(profile),
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(MODULE_PATH),
            str(artifact_parent),
            str(tmp_path / "state"),
            str(runtime),
            str(output),
            str(manifest),
            str(capability),
        ],
        cwd=runtime,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "worker_bootstrap_attestation_required" in completed.stderr
    assert capability.is_file()
    assert not output.exists()


def test_unsandboxed_isolated_bootstrap_fails_before_capability_consumption(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir, _, _ = _patch_execution_paths(module, tmp_path, monkeypatch)
    nonce = "a" * 64
    lease = "b" * 64
    module.create_execution_state(
        state_dir,
        claim={
            "schema_version": 1,
            "stage": module.STAGE,
            "line_id": module.LINE_ID,
            "campaign_nonce": nonce,
            "lease_id": lease,
            "replay_permitted": False,
        },
        campaign_nonce=nonce,
        lease_id=lease,
    )
    module.update_execution_event(
        state_dir / "event.json",
        campaign_nonce=nonce,
        lease_id=lease,
        status="running",
        phase="worker_a1",
        counters=module.zero_sensitive_counters(),
    )
    attempt = module.ARTIFACT_PARENT / f".{module.STAGE}_{nonce[:12]}"
    worker_root = attempt / "workers/A1"
    runtime = worker_root / "runtime"
    runtime.mkdir(parents=True)
    output = worker_root / "output"
    manifest = attempt / "input_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    profile = module.write_worker_sandbox_profile(worker_root)
    capability, parent_secret = module._issue_worker_capability(
        "A1",
        attempt_dir=attempt,
        runtime_root=runtime,
        output_dir=output,
        input_manifest_path=manifest,
        sandbox_profile=profile,
        campaign_nonce=nonce,
        lease_id=lease,
        counters=module.zero_sensitive_counters(),
    )

    completed = subprocess.run(
        module.worker_bootstrap_command(
            "A1",
            runtime_root=runtime,
            output_dir=output,
            input_manifest_path=manifest,
            capability_path=capability,
        ),
        cwd=runtime,
        env=module.worker_environment(os.environ, runtime, "A1"),
        input=f"{parent_secret}\n",
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "bootstrap_sandbox_external_write_not_denied" in completed.stderr
    assert capability.is_file()
    assert not (worker_root / "worker_capability.consumed.json").exists()
    assert not output.exists()
    assert not (attempt / ".sandbox_probe_A1").exists()


def test_parent_capability_is_durably_bound_and_one_use(
    module,
    tmp_path,
    monkeypatch,
) -> None:
    state_dir, _, _ = _patch_execution_paths(module, tmp_path, monkeypatch)
    nonce = "a" * 64
    lease = "b" * 64
    claim = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "campaign_nonce": nonce,
        "lease_id": lease,
        "replay_permitted": False,
    }
    module.create_execution_state(
        state_dir,
        claim=claim,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    module.update_execution_event(
        state_dir / "event.json",
        campaign_nonce=nonce,
        lease_id=lease,
        status="running",
        phase="worker_a1",
        counters=module.zero_sensitive_counters(),
    )
    attempt = module.ARTIFACT_PARENT / f".{module.STAGE}_{nonce[:12]}"
    worker_root = attempt / "workers/A1"
    runtime = worker_root / "runtime"
    runtime.mkdir(parents=True)
    manifest = attempt / "input_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    output = worker_root / "output"
    profile = module.write_worker_sandbox_profile(worker_root)

    capability, parent_secret = module._issue_worker_capability(
        "A1",
        attempt_dir=attempt,
        runtime_root=runtime,
        output_dir=output,
        input_manifest_path=manifest,
        sandbox_profile=profile,
        campaign_nonce=nonce,
        lease_id=lease,
        counters=module.zero_sensitive_counters(),
    )
    capability_payload = json.loads(capability.read_text(encoding="utf-8"))
    assert parent_secret not in capability.read_text(encoding="utf-8")
    assert capability_payload["parent_channel_secret_sha256"] == hashlib.sha256(
        parent_secret.encode("ascii")
    ).hexdigest()
    bootstrap_command = module.worker_bootstrap_command(
        "A1",
        runtime_root=runtime,
        output_dir=output,
        input_manifest_path=manifest,
        capability_path=capability,
    )
    command = module.sandboxed_command(profile, bootstrap_command)
    environment = module.worker_environment(os.environ, runtime, "A1")
    capability_sha = _sha256(capability)

    wrong_secret = "f" * 64
    assert wrong_secret != parent_secret
    rejected = subprocess.run(
        command,
        cwd=runtime,
        env=environment,
        input=f"{wrong_secret}\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert rejected.returncode != 0
    assert "bootstrap_parent_channel_secret_mismatch" in rejected.stderr
    assert capability.is_file()
    assert _sha256(capability) == capability_sha
    assert not output.exists()

    completed = subprocess.run(
        command,
        cwd=runtime,
        env=environment,
        input=f"{parent_secret}\n",
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "file_contract_sha256" in completed.stderr
    assert not capability.exists()
    consumed = worker_root / "worker_capability.consumed.json"
    assert consumed.is_file()
    assert output.is_dir()
    second = subprocess.run(
        command,
        cwd=runtime,
        env=environment,
        input=f"{parent_secret}\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert second.returncode != 0
    assert consumed.is_file()


def test_source_contains_no_order_or_ctp_imports(module) -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    forbidden_imports = (
        "import vnpy_ctp",
        "from vnpy_ctp",
        "send_order(",
        "cancel_order(",
        "CtpGateway",
    )
    assert not any(token in source for token in forbidden_imports)
