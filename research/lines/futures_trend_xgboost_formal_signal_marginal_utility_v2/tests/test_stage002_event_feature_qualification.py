from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


LINE_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = LINE_ROOT / "tools/stage002_event_feature_qualification.py"


@pytest.fixture()
def module():
    spec = importlib.util.spec_from_file_location(
        "stage002_event_feature_qualification_test",
        MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def test_collect_input_files_replaces_v1_admin_with_v2_contract(
    module,
    monkeypatch,
) -> None:
    def forbidden_subprocess(*_args, **_kwargs):
        raise AssertionError("input discovery must not spawn a process")

    monkeypatch.setattr(subprocess, "run", forbidden_subprocess)
    files = module.collect_input_files()

    assert len(files) == 1416
    assert {
        "stage002_runner",
        "stage002_feature_tool",
        "stage002_tests",
        "v2_line",
        "v2_stage000_import_preregistration",
        "v2_stage001_import_report",
        "v2_stage001_preflight_tool",
        "v2_stage001_preflight_tests",
        "v2_font_cache",
        "v2_release_attestation",
        "v2_stage002_preregistration",
        "v2_stage001_summary",
        "v2_stage001_a1_receipt",
        "v2_stage001_a2_receipt",
    }.issubset(files)
    assert {
        "stage001_runner",
        "stage001_worker_bootstrap",
        "stage001_feature_tool",
        "stage001_preregistration",
        "stage001_pre_ai_boundary_remediation",
        "stage001_plan",
        "stage001_feature_tests",
        "stage001_runner_tests",
    }.isdisjoint(files)
    assert all(path.is_file() for path in files.values())


def test_build_input_manifest_is_process_free_and_reproducible(module, monkeypatch) -> None:
    def forbidden_subprocess(*_args, **_kwargs):
        raise AssertionError("manifest construction must not spawn a process")

    monkeypatch.setattr(subprocess, "run", forbidden_subprocess)
    first = module.build_input_manifest()
    second = module.build_input_manifest()

    assert first == second
    assert first["schema_version"] == 1
    assert first["stage"] == "stage002_event_feature_qualification"
    assert first["line_id"] == "futures_trend_xgboost_formal_signal_marginal_utility_v2"
    assert first["input_file_count"] == 1416
    assert set(first["files"]) == set(module.collect_input_files())
    assert re.fullmatch(r"[0-9a-f]{64}", first["input_logical_key_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", first["file_contract_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", first["runtime_contract_sha256"])


def test_claim_execution_is_exclusive_and_binds_input_contract(module, tmp_path) -> None:
    claim_path = tmp_path / "stage002_claim.json"
    manifest = {
        "input_file_count": 1416,
        "input_logical_key_sha256": "a" * 64,
        "file_contract_sha256": "b" * 64,
        "runtime_contract_sha256": "c" * 64,
    }

    claim = module.claim_execution(claim_path, manifest)

    assert claim["stage"] == module.STAGE
    assert claim["line_id"] == module.LINE_ID
    assert claim["replay_permitted"] is False
    assert re.fullmatch(r"[0-9a-f]{64}", claim["campaign_nonce"])
    assert claim["input_file_count"] == 1416
    assert claim["input_logical_key_sha256"] == "a" * 64
    assert claim["file_contract_sha256"] == "b" * 64
    assert claim["runtime_contract_sha256"] == "c" * 64
    assert json.loads(claim_path.read_text(encoding="utf-8")) == claim
    assert os.stat(claim_path).st_mode & 0o777 == 0o600

    with pytest.raises(module.Stage002Error, match="execution_claim_exists"):
        module.claim_execution(claim_path, manifest)

    assert json.loads(claim_path.read_text(encoding="utf-8")) == claim


def _one_file_manifest(module) -> dict[str, object]:
    files = {
        "only": {
            "path": "/tmp/only",
            "size": 4,
            "mtime_ns": 5,
            "sha256": "d" * 64,
        }
    }
    runtime = {"python_version": "test"}
    return {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "formal_identity": {"release": "frozen"},
        "files": files,
        "input_file_count": 1,
        "input_logical_key_sha256": module._logical_key_sha256(
            {"only": Path("/tmp/only")}
        ),
        "file_contract_sha256": module._file_contract_sha256(files),
        "runtime": runtime,
        "runtime_contract_sha256": module.hashlib.sha256(
            module._stable_json_bytes(runtime)
        ).hexdigest(),
    }


def _write_freeze(module, path: Path, manifest: dict[str, object]) -> dict[str, object]:
    freeze = {
        "schema_version": 1,
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "execution_authorized": True,
        "input_file_count": manifest["input_file_count"],
        "input_logical_key_sha256": manifest["input_logical_key_sha256"],
        "file_contract_sha256": manifest["file_contract_sha256"],
        "runtime_contract_sha256": manifest["runtime_contract_sha256"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(freeze), encoding="utf-8")
    return freeze


def test_validate_current_input_manifest_accepts_only_exact_current_contract(
    module,
    monkeypatch,
) -> None:
    recorded = _one_file_manifest(module)
    monkeypatch.setattr(module, "EXPECTED_INPUT_FILE_COUNT", 1)
    monkeypatch.setattr(module, "build_input_manifest", lambda: recorded)

    assert module.validate_current_input_manifest(recorded) == recorded

    drifted = json.loads(json.dumps(recorded))
    drifted["files"]["only"]["sha256"] = "e" * 64
    drifted["file_contract_sha256"] = module._file_contract_sha256(drifted["files"])
    monkeypatch.setattr(module, "build_input_manifest", lambda: drifted)

    with pytest.raises(module.Stage002Error, match="current_input_manifest_drift"):
        module.validate_current_input_manifest(recorded)


def test_stage002_thresholds_match_preregistration(module) -> None:
    feature_module = module.load_feature_module()

    thresholds = module.stage002_thresholds(feature_module)

    assert thresholds.min_events == 150
    assert thresholds.min_events_per_full_year == 24
    assert thresholds.min_events_per_direction == 40
    assert thresholds.min_products == 15
    assert thresholds.min_unique_per_feature == 2
    assert thresholds.min_high_cardinality_features == 8
    assert thresholds.high_cardinality_unique_values == 10
    assert thresholds.full_years == (2023, 2024, 2025)


def test_prepare_stage002_worker_root_copies_bound_database(module, tmp_path) -> None:
    source_database = tmp_path / "source.db"
    source_database.write_bytes(b"frozen-database")
    expected_sha256 = module.hashlib.sha256(source_database.read_bytes()).hexdigest()

    paths = module.prepare_stage002_worker_root(
        tmp_path / "A1",
        source_database=source_database,
        expected_database_sha256=expected_sha256,
    )

    assert paths["database"].read_bytes() == b"frozen-database"
    assert module._file_identity(paths["database"])["sha256"] == expected_sha256
    assert os.stat(paths["database"]).st_mode & 0o777 == 0o600
    assert paths["setting"].read_text(encoding="utf-8") == "{}\n"
    assert paths["font_cache"].is_file()


def test_extract_formal_event_features_runs_only_baseline_once_and_restores_trace(
    module,
) -> None:
    calls = {"replay": 0, "restore": 0}
    candidates = SimpleNamespace(copy=lambda: "candidate-copy")
    frames = {"entry_candidates": candidates}
    live_spec = SimpleNamespace(
        capital=SimpleNamespace(account_capital=150_000.0),
        profile="formal-profile",
    )

    def run_live_c9(metadata, start, end):
        assert metadata == "metadata"
        assert start == "2020-01-02"
        assert end == "2026-08-28"
        calls["replay"] += 1
        return object(), frames, live_spec

    context = {
        "s901": SimpleNamespace(
            s513=SimpleNamespace(_metadata=lambda: "metadata"),
            s847=SimpleNamespace(QmtRollPortfolioStrategyStage847C9StopRetry=object),
            _run_live_c9=run_live_c9,
        ),
        "live_config": SimpleNamespace(OFFICIAL_LIVE_PROFILE_NAME="formal-profile"),
    }
    fake_pd = SimpleNamespace(read_csv=lambda path: ("eligibility", path))

    def install_trace(strategy_class):
        assert strategy_class is object

        def restore():
            calls["restore"] += 1

        return restore

    v1 = SimpleNamespace(
        START="2020-01-02",
        END="2026-08-28",
        EXPECTED_CAPITAL=150_000.0,
        pd=fake_pd,
        _active_formal_identity=lambda: {"eligibility_path": "/formal.csv"},
        _install_correlation_trace_instrumentation=install_trace,
    )
    feature_module = SimpleNamespace(
        build_formal_root_event_features=lambda rows, eligibility, identity: {
            "rows": rows,
            "eligibility": eligibility,
            "identity": identity,
        }
    )

    features, formal = module.extract_formal_event_features(
        context,
        v1=v1,
        feature_module=feature_module,
    )

    assert calls == {"replay": 1, "restore": 1}
    assert formal == {"eligibility_path": "/formal.csv"}
    assert features == {
        "rows": "candidate-copy",
        "eligibility": ("eligibility", "/formal.csv"),
        "identity": formal,
    }


def test_worker_command_uses_sandbox_and_isolated_interpreter(module, tmp_path) -> None:
    paths = {
        "profile": tmp_path / "worker.sb",
        "worker_root": tmp_path / "A1",
        "runtime": tmp_path / "A1/runtime",
        "receipt": tmp_path / "A1/receipt.json",
        "feature": tmp_path / "A1/event_features.csv",
    }
    manifest_path = tmp_path / "input_manifest.json"
    probe = tmp_path / ".sandbox_probe_A1"

    command = module.worker_command(paths, "A1", manifest_path, probe)

    assert command[:3] == ["/usr/bin/sandbox-exec", "-f", str(paths["profile"])]
    assert command[3:7] == [str(Path(sys.executable).resolve()), "-I", "-S", "-B"]
    assert command[7] == str(module.Path(module.__file__).resolve())
    assert command[8:] == [
        "--worker",
        "--worker-id",
        "A1",
        "--worker-root",
        str(paths["worker_root"]),
        "--runtime-root",
        str(paths["runtime"]),
        "--receipt-path",
        str(paths["receipt"]),
        "--feature-path",
        str(paths["feature"]),
        "--external-probe-path",
        str(probe),
        "--attestation-path",
        str(module.RELEASE_ATTESTATION.resolve()),
        "--manifest-path",
        str(manifest_path),
    ]


def _qualified_feature_frame(module):
    feature_module = module.load_feature_module()
    rows = []
    years = (2023, 2024, 2025)
    for index in range(180):
        row = {column: "frozen" for column in feature_module.OUTPUT_COLUMNS}
        row.update(
            {
                "event_id": f"event-{index:04d}",
                "decision_date": f"{years[index % 3]}-{index % 12 + 1:02d}-15",
                "product_vt_symbol": f"p{index % 20:02d}.SHFE",
                "direction": "long" if index % 2 == 0 else "short",
                "entry_context": "flat_entry",
                "candidate_status": "opened",
                "is_opened": 1,
            }
        )
        for offset, feature in enumerate(feature_module.FEATURE_COLUMNS):
            row[feature] = float((index + offset) % 20)
        rows.append(row)
    return feature_module.pd.DataFrame(rows, columns=feature_module.OUTPUT_COLUMNS)


def test_evaluate_stage002_features_applies_reproducibility_and_frozen_gates(
    module,
) -> None:
    a1 = _qualified_feature_frame(module)
    a2 = a1.copy()

    result = module.evaluate_stage002_features(a1, a2)

    assert result["passed"] is True
    assert result["worker_comparison"]["atol"] == 1e-12
    assert result["worker_comparison"]["max_abs_numeric_diff"] == 0.0
    assert result["qualification"]["metrics"]["yearly_counts"] == {
        "2023": 60,
        "2024": 60,
        "2025": 60,
    }
    assert result["qualification"]["metrics"]["high_cardinality_feature_count"] == 12


def test_evaluate_stage002_features_rejects_numeric_worker_drift(module) -> None:
    a1 = _qualified_feature_frame(module)
    a2 = a1.copy()
    a2.loc[0, "directional_rsi"] += 1e-6

    with pytest.raises(module.Stage002Error, match="worker_reproducibility_failed"):
        module.evaluate_stage002_features(a1, a2)


def test_guarded_extraction_allows_one_formal_replay_and_nothing_sensitive(
    module,
    tmp_path,
) -> None:
    preflight = module.load_preflight_module()
    calls = {"replay": 0, "restore": 0}

    def _run_live_c9(_metadata, _start, _end):
        calls["replay"] += 1
        return (
            object(),
            {"entry_candidates": SimpleNamespace(copy=lambda: "candidate-copy")},
            SimpleNamespace(
                capital=SimpleNamespace(account_capital=150_000.0),
                profile="formal-profile",
            ),
        )

    context = {
        "s901": SimpleNamespace(
            s513=SimpleNamespace(_metadata=lambda: "metadata"),
            s847=SimpleNamespace(QmtRollPortfolioStrategyStage847C9StopRetry=object),
            _run_live_c9=_run_live_c9,
        ),
        "live_config": SimpleNamespace(OFFICIAL_LIVE_PROFILE_NAME="formal-profile"),
    }

    def install_trace(_strategy_class):
        def restore():
            calls["restore"] += 1

        return restore

    v1 = SimpleNamespace(
        START="2020-01-02",
        END="2026-08-28",
        EXPECTED_CAPITAL=150_000.0,
        pd=SimpleNamespace(read_csv=lambda _path: "eligibility"),
        _active_formal_identity=lambda: {"eligibility_path": "/formal.csv"},
        _install_correlation_trace_instrumentation=install_trace,
    )
    feature_module = SimpleNamespace(
        build_formal_root_event_features=lambda *_args: "features"
    )

    features, formal, safety = module.run_guarded_extraction(
        worker_root=tmp_path,
        attestation={"frozen": True},
        preflight=preflight,
        v1=v1,
        feature_module=feature_module,
        context_importer=lambda _attestation: (
            context,
            [{"release": "checked"}],
            True,
        ),
    )

    assert features == "features"
    assert formal == {"eligibility_path": "/formal.csv"}
    assert calls == {"replay": 1, "restore": 1}
    assert safety["formal_replay_call_count"] == 1
    assert safety["network_connection_attempt_count"] == 0
    assert all(value == 0 for value in safety["sensitive_counters"].values())
    assert safety["release_adapter_call_count"] == 1
    assert safety["release_adapter_restored"] is True


def test_run_worker_writes_only_event_features_and_safety_receipt(
    module,
    monkeypatch,
    tmp_path,
) -> None:
    actual_v1 = module.load_v1_runner()
    actual_feature_module = module.load_feature_module()
    source_database = tmp_path / "source.db"
    source_database.write_bytes(b"database")
    database_sha = module.hashlib.sha256(source_database.read_bytes()).hexdigest()
    paths = module.prepare_stage002_worker_root(
        tmp_path / "A1",
        source_database=source_database,
        expected_database_sha256=database_sha,
    )
    paths["feature"] = paths["worker_root"] / "event_features.csv"
    manifest = {
        "formal_identity": {"release": "frozen"},
        "files": {
            "source_database": {
                "path": str(source_database),
                "size": source_database.stat().st_size,
                "mtime_ns": source_database.stat().st_mtime_ns,
                "sha256": database_sha,
            }
        },
        "input_file_count": 1,
        "input_logical_key_sha256": "a" * 64,
        "file_contract_sha256": "b" * 64,
        "runtime_contract_sha256": "c" * 64,
    }
    manifest_path = tmp_path / "input_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    mpl_data = tmp_path / "mpl-data"
    mpl_data.mkdir()
    fake_preflight = SimpleNamespace(
        _validate_worker_bootstrap=lambda runtime: {"runtime": str(runtime)},
        prove_external_write_denied=lambda probe: {
            "write_denied": True,
            "probe": str(probe),
        },
        read_git_head_without_process=lambda _root: "production-head",
        PRODUCTION_ROOT=tmp_path / "production",
        EXPECTED_PRODUCTION_HEAD="production-head",
        EXPECTED_FONT_MANAGER_VERSION=390,
        EXPECTED_FONT_CACHE_SHA256=module._file_identity(paths["font_cache"])[
            "sha256"
        ],
        validate_portable_font_cache=lambda *args, **kwargs: {
            "sha256": module._file_identity(paths["font_cache"])["sha256"]
        },
        matplotlib_data_path=lambda: mpl_data,
        _load_release_attestation=lambda _path: {"frozen": True},
        python_site_packages=lambda: site_packages,
    )
    features = actual_feature_module.pd.DataFrame(
        [{"event_id": "event-1", "feature": 1.25}]
    )
    safety = {
        "sensitive_counters": actual_v1.zero_sensitive_counters(),
        "network_connection_attempt_count": 0,
        "formal_replay_call_count": 1,
        "release_adapter_call_count": 1,
        "release_adapter_calls": [{"release": "checked"}],
        "release_adapter_restored": True,
    }
    monkeypatch.setattr(module, "load_preflight_module", lambda: fake_preflight)
    monkeypatch.setattr(module, "load_v1_runner", lambda: actual_v1)
    monkeypatch.setattr(module, "load_feature_module", lambda: actual_feature_module)
    monkeypatch.setattr(
        module,
        "validate_current_input_manifest",
        lambda recorded: recorded,
    )
    monkeypatch.setattr(
        module,
        "run_guarded_extraction",
        lambda **_kwargs: (features, manifest["formal_identity"], safety),
    )

    receipt = module.run_worker_qualification(
        worker_id="A1",
        worker_root=paths["worker_root"],
        runtime_root=paths["runtime"],
        receipt_path=paths["receipt"],
        feature_path=paths["feature"],
        external_probe_path=tmp_path / ".sandbox_probe_A1",
        attestation_path=module.RELEASE_ATTESTATION,
        manifest_path=manifest_path,
    )

    assert receipt["status"] == "passed"
    assert receipt["event_count"] == 1
    assert receipt["formal_replay_call_count"] == 1
    assert receipt["sensitive_counters"] == actual_v1.zero_sensitive_counters()
    assert json.loads(paths["receipt"].read_text(encoding="utf-8")) == receipt
    assert paths["feature"].read_text(encoding="utf-8") == (
        "event_id,feature\nevent-1,1.25\n"
    )
    forbidden = {"return", "drawdown", "sharpe", "pnl", "label", "prediction"}
    assert forbidden.isdisjoint(receipt)


def test_run_cold_worker_validates_safety_receipt_before_accepting_output(
    module,
    monkeypatch,
    tmp_path,
) -> None:
    source_database = tmp_path / "source.db"
    source_database.write_bytes(b"database")
    source_identity = module._file_identity(source_database)
    manifest = {
        "formal_identity": {"release": "frozen"},
        "files": {"source_database": source_identity},
        "input_file_count": 1,
        "input_logical_key_sha256": "a" * 64,
        "file_contract_sha256": "b" * 64,
        "runtime_contract_sha256": "c" * 64,
    }
    manifest_path = tmp_path / "input_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        receipt_path = Path(command[command.index("--receipt-path") + 1])
        feature_path = Path(command[command.index("--feature-path") + 1])
        feature_path.write_text("event_id,feature\nevent-1,1.25\n", encoding="utf-8")
        preflight = module.load_preflight_module()
        receipt = {
            "status": "passed",
            "worker_id": "A1",
            "pid": 12345,
            "formal_identity": manifest["formal_identity"],
            "input_file_count": 1,
            "input_logical_key_sha256": "a" * 64,
            "file_contract_sha256": "b" * 64,
            "runtime_contract_sha256": "c" * 64,
            "event_count": 1,
            "event_feature_file": module._file_identity(feature_path),
            "sensitive_counters": preflight.zero_sensitive_counters(),
            "network_connection_attempt_count": 0,
            "formal_replay_call_count": 1,
            "release_adapter_call_count": 1,
            "release_adapter_restored": True,
        }
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.run_cold_worker(tmp_path / "attempt", "A1", manifest_path, manifest)

    assert result["receipt"]["status"] == "passed"
    assert result["feature_path"].read_text(encoding="utf-8").startswith("event_id")
    assert result["worker_root"].name == "A1"
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[:3] == [
        "/usr/bin/sandbox-exec",
        "-f",
        str(result["worker_root"] / "preflight.sb"),
    ]
    assert kwargs["cwd"] == result["worker_root"] / "runtime"
    assert kwargs["env"] == module.load_preflight_module().expected_worker_environment(
        result["worker_root"] / "runtime"
    )


def test_parent_claims_once_runs_two_workers_and_publishes_qualified_events(
    module,
    monkeypatch,
    tmp_path,
) -> None:
    manifest = _one_file_manifest(module)
    monkeypatch.setattr(module, "EXPECTED_INPUT_FILE_COUNT", 1)
    monkeypatch.setattr(module, "build_input_manifest", lambda: manifest)
    monkeypatch.setattr(
        module,
        "validate_current_input_manifest",
        lambda recorded: recorded,
    )
    feature_frame = _qualified_feature_frame(module)
    worker_calls = []

    def fake_worker(attempt, worker_id, manifest_path, recorded):
        assert recorded == manifest
        assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
        worker_calls.append(worker_id)
        worker_root = attempt / "workers" / worker_id
        runtime = worker_root / "runtime"
        runtime.mkdir(parents=True)
        (runtime / "database.db").write_bytes(b"temporary")
        feature_path = worker_root / "event_features.csv"
        feature_frame.to_csv(
            feature_path,
            index=False,
            lineterminator="\n",
            float_format="%.17g",
        )
        receipt_path = worker_root / "receipt.json"
        receipt = {
            "status": "passed",
            "worker_id": worker_id,
            "pid": 100 if worker_id == "A1" else 200,
            "event_count": len(feature_frame),
            "sensitive_counters": module.load_preflight_module().zero_sensitive_counters(),
            "network_connection_attempt_count": 0,
            "formal_replay_call_count": 1,
        }
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return {
            "worker_root": worker_root,
            "feature_path": feature_path,
            "receipt_path": receipt_path,
            "log_path": worker_root / "worker.log",
            "receipt": receipt,
        }

    monkeypatch.setattr(module, "run_cold_worker", fake_worker)
    final_dir = tmp_path / "artifacts/stage002"
    failure_dir = tmp_path / "artifacts/stage002_failed"
    claim_path = tmp_path / "stages/execution_state/claim.json"
    freeze_path = tmp_path / "stages/stage002a_freeze.json"
    _write_freeze(module, freeze_path, manifest)

    summary = module.run_parent_qualification(
        final_dir=final_dir,
        failure_dir=failure_dir,
        claim_path=claim_path,
        freeze_path=freeze_path,
    )

    assert worker_calls == ["A1", "A2"]
    assert summary["status"] == "passed"
    assert summary["event_count"] == 180
    assert summary["worker_ids"] == ["A1", "A2"]
    assert summary["worker_pids_distinct"] is True
    assert summary["formal_replay_call_count"] == 2
    assert summary["reviewer_started"] is False
    assert final_dir.is_dir()
    assert not failure_dir.exists()
    assert claim_path.is_file()
    assert (final_dir / "input_manifest.json").is_file()
    assert (final_dir / "input_contract_freeze.json").is_file()
    assert (final_dir / "event_features.csv").is_file()
    assert json.loads((final_dir / "summary.json").read_text(encoding="utf-8")) == summary
    assert not (final_dir / "workers/A1/runtime").exists()
    assert not (final_dir / "workers/A2/runtime").exists()
    forbidden = {"return", "drawdown", "sharpe", "pnl", "label", "prediction"}
    assert forbidden.isdisjoint(summary)


def test_parent_failure_consumes_claim_publishes_failure_and_removes_database_copy(
    module,
    monkeypatch,
    tmp_path,
) -> None:
    manifest = _one_file_manifest(module)
    monkeypatch.setattr(module, "EXPECTED_INPUT_FILE_COUNT", 1)
    monkeypatch.setattr(module, "build_input_manifest", lambda: manifest)

    def failed_worker(attempt, worker_id, _manifest_path, _recorded):
        runtime = attempt / "workers" / worker_id / "runtime"
        runtime.mkdir(parents=True)
        (runtime / "database.db").write_bytes(b"temporary")
        raise module.Stage002Error("synthetic_worker_failure")

    monkeypatch.setattr(module, "run_cold_worker", failed_worker)
    final_dir = tmp_path / "artifacts/stage002"
    failure_dir = tmp_path / "artifacts/stage002_failed"
    claim_path = tmp_path / "stages/execution_state/claim.json"
    freeze_path = tmp_path / "stages/stage002a_freeze.json"
    _write_freeze(module, freeze_path, manifest)

    with pytest.raises(module.Stage002Error, match="synthetic_worker_failure"):
        module.run_parent_qualification(
            final_dir=final_dir,
            failure_dir=failure_dir,
            claim_path=claim_path,
            freeze_path=freeze_path,
        )

    assert claim_path.is_file()
    assert failure_dir.is_dir()
    assert not final_dir.exists()
    assert not (failure_dir / "workers/A1/runtime").exists()
    failure = json.loads((failure_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["status"] == "failed"
    assert failure["error"] == "synthetic_worker_failure"
    assert failure["reviewer_started"] is False
    with pytest.raises(module.Stage002Error, match="execution_claim_exists"):
        module.claim_execution(claim_path, manifest)


def test_validate_frozen_input_contract_requires_exact_manifest_hashes(
    module,
    tmp_path,
) -> None:
    manifest = _one_file_manifest(module)
    freeze_path = tmp_path / "stage002a_freeze.json"
    freeze = _write_freeze(module, freeze_path, manifest)

    assert module.validate_frozen_input_contract(freeze_path, manifest) == freeze

    freeze["file_contract_sha256"] = "f" * 64
    freeze_path.write_text(json.dumps(freeze), encoding="utf-8")
    with pytest.raises(module.Stage002Error, match="frozen_input_contract_mismatch"):
        module.validate_frozen_input_contract(freeze_path, manifest)


def test_run_cli_uses_only_fixed_claim_freeze_and_artifact_paths(
    module,
    monkeypatch,
    capsys,
) -> None:
    captured = {}

    def fake_parent(**kwargs):
        captured.update(kwargs)
        return {"status": "passed", "stage": module.STAGE}

    monkeypatch.setattr(module, "run_parent_qualification", fake_parent)

    assert module.main(["--run"]) == 0
    assert captured == {
        "final_dir": module.FINAL_DIR,
        "failure_dir": module.FAILURE_DIR,
        "claim_path": module.CLAIM_PATH,
        "freeze_path": module.INPUT_FREEZE_PATH,
    }
    assert json.loads(capsys.readouterr().out)["status"] == "passed"
