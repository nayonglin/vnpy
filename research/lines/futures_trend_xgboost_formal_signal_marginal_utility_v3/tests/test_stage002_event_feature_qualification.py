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
        "v3_stage002_event_feature_qualification_test",
        MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def test_collect_input_files_binds_v3_stage001_and_v2_failure_evidence(
    module,
    monkeypatch,
) -> None:
    def forbidden_subprocess(*_args, **_kwargs):
        raise AssertionError("input discovery must not spawn a process")

    monkeypatch.setattr(subprocess, "run", forbidden_subprocess)
    files = module.collect_input_files()

    assert len(files) == 1433
    assert {
        "stage002_runner",
        "stage002_tests",
        "stage002_preregistration",
        "stage002_feature_tool",
        "v3_stage001_record",
        "v3_stage001_summary",
        "v3_stage001_input_manifest",
        "v3_stage001_a1_receipt",
        "v3_stage001_a2_receipt",
        "v3_stage001_a1_universe",
        "v3_stage001_a2_universe",
        "v3_stage001_a1_post_signal_eligibility",
        "v3_stage001_a2_post_signal_eligibility",
        "v2_stage002_claim",
        "v2_stage002_failure",
        "source_database",
    }.issubset(files)
    assert all(path.is_file() and not path.is_symlink() for path in files.values())


def test_input_manifest_is_process_free_and_reproducible(module, monkeypatch) -> None:
    def forbidden_subprocess(*_args, **_kwargs):
        raise AssertionError("manifest construction must not spawn a process")

    monkeypatch.setattr(subprocess, "run", forbidden_subprocess)
    first = module.build_input_manifest()
    second = module.build_input_manifest()

    assert first == second
    assert first["schema_version"] == 1
    assert first["stage"] == "stage002_event_feature_qualification"
    assert first["line_id"] == (
        "futures_trend_xgboost_formal_signal_marginal_utility_v3"
    )
    assert first["input_file_count"] == 1433
    assert set(first["files"]) == set(module.collect_input_files())
    assert re.fullmatch(r"[0-9a-f]{64}", first["input_logical_key_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", first["file_contract_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", first["runtime_contract_sha256"])


def _valid_metadata() -> dict[str, object]:
    symbols = ["a2401.SHFE", "b2401.DCE"]
    return {
        "vt_symbols": symbols,
        "rates": {symbol: 0.0001 for symbol in symbols},
        "slippages": {symbol: 1.0 for symbol in symbols},
        "sizes": {symbol: 10 for symbol in symbols},
        "priceticks": {symbol: 1.0 for symbol in symbols},
        "margin_ratios": {symbol: 0.15 for symbol in symbols},
        "metadata_sources": {symbol: "static" for symbol in symbols},
        "source_symbol_by_contract": {
            "a2401.SHFE": "a.SHFE",
            "b2401.DCE": "b.DCE",
        },
        "product_symbols": ["a.SHFE", "b.DCE"],
    }


def test_extract_formal_events_redirects_metadata_then_runs_baseline_once(
    module,
    monkeypatch,
    tmp_path,
) -> None:
    calls = {"metadata": 0, "replay": 0, "restore": 0}
    candidate_file = tmp_path / "candidate.py"
    candidate_file.write_text("# identity\n", encoding="utf-8")
    expected = {
        "universe": tmp_path / "expected_universe.csv",
        "post_signal_eligibility": tmp_path / "expected_eligibility.csv",
    }
    expected["universe"].write_bytes(b"universe\n")
    expected["post_signal_eligibility"].write_bytes(b"eligibility\n")
    original_universe = Path("/formal/universe.csv")
    original_eligibility = Path("/formal/eligibility.csv")
    candidate_module = SimpleNamespace(
        __file__=str(candidate_file),
        UNIVERSE_PATH=original_universe,
        AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH=original_eligibility,
    )

    def metadata():
        calls["metadata"] += 1
        candidate_module.UNIVERSE_PATH.write_bytes(expected["universe"].read_bytes())
        candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH.write_bytes(
            expected["post_signal_eligibility"].read_bytes()
        )
        return _valid_metadata()

    candidates = SimpleNamespace(copy=lambda: "candidate-copy")
    live_spec = SimpleNamespace(
        capital=SimpleNamespace(account_capital=150_000.0),
        profile="formal-profile",
    )

    def run_live_c9(observed_metadata, start, end):
        assert observed_metadata == _valid_metadata()
        assert start == "2020-01-02"
        assert end == "2026-08-28"
        calls["replay"] += 1
        return object(), {"entry_candidates": candidates}, live_spec

    context = {
        "s901": SimpleNamespace(
            s513=SimpleNamespace(_metadata=metadata),
            s847=SimpleNamespace(QmtRollPortfolioStrategyStage847C9StopRetry=object),
            _run_live_c9=run_live_c9,
        ),
        "live_config": SimpleNamespace(OFFICIAL_LIVE_PROFILE_NAME="formal-profile"),
    }
    monkeypatch.setitem(
        sys.modules,
        module.CANDIDATE_MODULE_NAME,
        candidate_module,
    )

    def install_trace(strategy_class):
        assert strategy_class is object

        def restore():
            calls["restore"] += 1

        return restore

    v1 = SimpleNamespace(
        START="2020-01-02",
        END="2026-08-28",
        EXPECTED_CAPITAL=150_000.0,
        pd=SimpleNamespace(read_csv=lambda path: ("eligibility", path)),
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
    worker_root = tmp_path / "A1"
    worker_root.mkdir()

    features, formal, metadata_evidence = module.extract_formal_event_features(
        context,
        worker_root=worker_root,
        expected_outputs=expected,
        expected_candidate_module_path=candidate_file,
        v1=v1,
        feature_module=feature_module,
        metadata_preflight=module.load_metadata_preflight_module(),
    )

    assert calls == {"metadata": 1, "replay": 1, "restore": 1}
    assert formal == {"eligibility_path": "/formal.csv"}
    assert features["rows"] == "candidate-copy"
    assert metadata_evidence["metadata"]["vt_symbol_count"] == 2
    assert metadata_evidence["derived_outputs"]["universe"]["bytes_equal"] is True
    assert metadata_evidence["metadata_output_paths_restored"] is True
    assert candidate_module.UNIVERSE_PATH is original_universe
    assert (
        candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
        is original_eligibility
    )


def test_guarded_extraction_allows_one_replay_and_zero_other_sensitive_ops(
    module,
    monkeypatch,
    tmp_path,
) -> None:
    metadata_preflight = module.load_metadata_preflight_module()
    preflight = metadata_preflight.load_preflight_module()
    worker_root = tmp_path / "A1"
    worker_root.mkdir()
    candidate_file = tmp_path / "candidate.py"
    candidate_file.write_text("# identity\n", encoding="utf-8")
    expected = {
        "universe": tmp_path / "expected_universe.csv",
        "post_signal_eligibility": tmp_path / "expected_eligibility.csv",
    }
    expected["universe"].write_bytes(b"universe\n")
    expected["post_signal_eligibility"].write_bytes(b"eligibility\n")
    candidate_module = SimpleNamespace(
        __file__=str(candidate_file),
        UNIVERSE_PATH=Path("/formal/universe.csv"),
        AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH=Path("/formal/eligibility.csv"),
    )

    def metadata():
        candidate_module.UNIVERSE_PATH.write_bytes(expected["universe"].read_bytes())
        candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH.write_bytes(
            expected["post_signal_eligibility"].read_bytes()
        )
        return _valid_metadata()

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
            s513=SimpleNamespace(_metadata=metadata),
            s847=SimpleNamespace(QmtRollPortfolioStrategyStage847C9StopRetry=object),
            _run_live_c9=_run_live_c9,
        ),
        "live_config": SimpleNamespace(OFFICIAL_LIVE_PROFILE_NAME="formal-profile"),
    }
    monkeypatch.setitem(sys.modules, module.CANDIDATE_MODULE_NAME, candidate_module)

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
        worker_root=worker_root,
        expected_outputs=expected,
        expected_candidate_module_path=candidate_file,
        attestation={"frozen": True},
        preflight=preflight,
        metadata_preflight=metadata_preflight,
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
    assert safety["metadata_preflight"]["metadata"]["vt_symbol_count"] == 2
    assert safety["metadata_preflight"]["metadata_output_paths_restored"] is True


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


def test_manifest_validation_rejects_current_drift(module, monkeypatch) -> None:
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


def test_frozen_contract_and_claim_bind_exact_manifest(module, tmp_path) -> None:
    manifest = _one_file_manifest(module)
    monkeypatch_count = module.EXPECTED_INPUT_FILE_COUNT
    module.EXPECTED_INPUT_FILE_COUNT = 1
    try:
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
        freeze_path = tmp_path / "freeze.json"
        freeze_path.write_text(json.dumps(freeze), encoding="utf-8")
        assert module.validate_frozen_input_contract(freeze_path, manifest) == freeze

        claim_path = tmp_path / "execution_state/claim.json"
        claim = module.claim_execution(claim_path, manifest)
        assert claim["stage"] == module.STAGE
        assert claim["line_id"] == module.LINE_ID
        assert claim["replay_permitted"] is False
        assert re.fullmatch(r"[0-9a-f]{64}", claim["campaign_nonce"])
        assert os.stat(claim_path).st_mode & 0o777 == 0o600
        with pytest.raises(module.Stage002Error, match="execution_claim_exists"):
            module.claim_execution(claim_path, manifest)
    finally:
        module.EXPECTED_INPUT_FILE_COUNT = monkeypatch_count


def test_thresholds_remain_identical_to_unobserved_v2_contract(module) -> None:
    thresholds = module.stage002_thresholds(module.load_feature_module())

    assert thresholds.min_events == 150
    assert thresholds.min_events_per_full_year == 24
    assert thresholds.min_events_per_direction == 40
    assert thresholds.min_products == 15
    assert thresholds.min_unique_per_feature == 2
    assert thresholds.min_high_cardinality_features == 8
    assert thresholds.high_cardinality_unique_values == 10
    assert thresholds.full_years == (2023, 2024, 2025)


def test_prepare_worker_root_copies_bound_database(module, tmp_path) -> None:
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


def test_worker_command_uses_v3_sandboxed_isolated_entrypoint(module, tmp_path) -> None:
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
    assert command[3:7] == [
        str(Path(sys.executable).resolve(strict=True)),
        "-I",
        "-S",
        "-B",
    ]
    assert command[7] == str(MODULE_PATH.resolve(strict=True))
    assert command[command.index("--worker-id") + 1] == "A1"
    assert command[command.index("--manifest-path") + 1] == str(manifest_path)
    assert command[command.index("--attestation-path") + 1] == str(
        module.RELEASE_ATTESTATION.resolve(strict=True)
    )


def test_run_worker_publishes_only_unlabeled_features_and_safety_receipt(
    module,
    monkeypatch,
    tmp_path,
) -> None:
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
                "path": str(source_database.resolve(strict=True)),
                "size": source_database.stat().st_size,
                "mtime_ns": source_database.stat().st_mtime_ns,
                "sha256": database_sha,
            }
        },
        "input_file_count": 1433,
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
    actual_preflight = module.load_metadata_preflight_module().load_preflight_module()
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
        SENSITIVE_COUNTER_KEYS=actual_preflight.SENSITIVE_COUNTER_KEYS,
    )
    fake_metadata_preflight = SimpleNamespace(
        load_preflight_module=lambda: fake_preflight,
        validate_frozen_metadata_files=lambda _manifest: {
            "universe": tmp_path / "expected_universe.csv",
            "post_signal_eligibility": tmp_path / "expected_eligibility.csv",
        },
    )
    feature_module = module.load_feature_module()
    features = feature_module.pd.DataFrame(
        [{"event_id": "event-1", "feature": 1.25}]
    )
    metadata_evidence = {
        "candidate_module_path": str(module.CANDIDATE_MODULE_PATH),
        "metadata": {"metadata_sha256": "d" * 64},
        "derived_outputs": {
            "universe": {"bytes_equal": True},
            "post_signal_eligibility": {"bytes_equal": True},
        },
        "metadata_output_paths_restored": True,
    }
    safety = {
        "sensitive_counters": {
            key: 0 for key in actual_preflight.SENSITIVE_COUNTER_KEYS
        },
        "network_connection_attempt_count": 0,
        "formal_replay_call_count": 1,
        "release_adapter_call_count": 1,
        "release_adapter_calls": [{"release": "checked"}],
        "release_adapter_restored": True,
        "metadata_preflight": metadata_evidence,
    }
    fake_v1 = SimpleNamespace(START="2020-01-02", END="2026-08-28")
    monkeypatch.setattr(
        module,
        "load_metadata_preflight_module",
        lambda: fake_metadata_preflight,
    )
    monkeypatch.setattr(module, "load_v1_runner", lambda: fake_v1)
    monkeypatch.setattr(module, "load_feature_module", lambda: feature_module)
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
    assert receipt["metadata_preflight"] == metadata_evidence
    assert json.loads(paths["receipt"].read_text(encoding="utf-8")) == receipt
    assert paths["feature"].read_text(encoding="utf-8") == (
        "event_id,feature\nevent-1,1.25\n"
    )
    forbidden = {"return", "drawdown", "sharpe", "pnl", "label", "prediction"}
    assert forbidden.isdisjoint(receipt)


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
    return feature_module.pd.DataFrame(
        rows,
        columns=feature_module.OUTPUT_COLUMNS,
    )


def test_parent_claims_once_and_publishes_only_qualified_events(
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
    preflight = module.load_metadata_preflight_module().load_preflight_module()
    worker_calls = []

    def fake_worker(attempt, worker_id, manifest_path, recorded):
        assert recorded == manifest
        assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
        worker_calls.append(worker_id)
        worker_root = attempt / "workers" / worker_id
        runtime = worker_root / "runtime"
        runtime.mkdir(parents=True)
        (runtime / "database.db").write_bytes(b"temporary")
        derived = worker_root / "derived"
        derived.mkdir()
        universe = derived / "static18_plus_fu.csv"
        eligibility = derived / "post_signal_eligibility.csv"
        universe.write_bytes(b"universe\n")
        eligibility.write_bytes(b"eligibility\n")
        feature_path = worker_root / "event_features.csv"
        feature_frame.to_csv(
            feature_path,
            index=False,
            lineterminator="\n",
            float_format="%.17g",
        )
        receipt_path = worker_root / "receipt.json"
        metadata_evidence = {
            "candidate_module_path": str(module.CANDIDATE_MODULE_PATH),
            "metadata": {"metadata_sha256": "d" * 64},
            "derived_outputs": {
                "universe": {
                    "bytes_equal": True,
                    "generated": module._file_identity(universe),
                    "expected": {"size": 9, "sha256": "e" * 64},
                },
                "post_signal_eligibility": {
                    "bytes_equal": True,
                    "generated": module._file_identity(eligibility),
                    "expected": {"size": 12, "sha256": "f" * 64},
                },
            },
            "metadata_output_paths_restored": True,
        }
        receipt = {
            "status": "passed",
            "worker_id": worker_id,
            "pid": 100 if worker_id == "A1" else 200,
            "event_count": len(feature_frame),
            "event_feature_file": module._file_identity(feature_path),
            "metadata_preflight": metadata_evidence,
            "sensitive_counters": preflight.zero_sensitive_counters(),
            "network_connection_attempt_count": 0,
            "formal_replay_call_count": 1,
            "release_adapter_call_count": 1,
            "release_adapter_restored": True,
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
    freeze_path.parent.mkdir(parents=True)
    freeze_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "stage": module.STAGE,
                "line_id": module.LINE_ID,
                "execution_authorized": True,
                "input_file_count": manifest["input_file_count"],
                "input_logical_key_sha256": manifest[
                    "input_logical_key_sha256"
                ],
                "file_contract_sha256": manifest["file_contract_sha256"],
                "runtime_contract_sha256": manifest["runtime_contract_sha256"],
            }
        ),
        encoding="utf-8",
    )

    summary = module.run_parent_qualification(
        final_dir=final_dir,
        failure_dir=failure_dir,
        claim_path=claim_path,
        freeze_path=freeze_path,
    )

    assert worker_calls == ["A1", "A2"]
    assert summary["status"] == "passed"
    assert summary["event_count"] == 180
    assert summary["worker_pids_distinct"] is True
    assert summary["formal_replay_call_count"] == 2
    assert summary["metadata_preflight"]["portable_receipts_equal"] is True
    assert summary["metadata_preflight"]["metadata"]["metadata_sha256"] == "d" * 64
    assert summary["reviewer_started"] is False
    assert final_dir.is_dir() and not failure_dir.exists()
    assert claim_path.is_file()
    assert (final_dir / "event_features.csv").is_file()
    assert not (final_dir / "workers/A1/runtime").exists()
    assert not (final_dir / "workers/A2/runtime").exists()
    forbidden = {"return", "drawdown", "sharpe", "pnl", "label", "prediction"}
    assert forbidden.isdisjoint(summary)


def test_parent_failure_consumes_claim_and_removes_database_copy(
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
    freeze_path.parent.mkdir(parents=True)
    freeze_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "stage": module.STAGE,
                "line_id": module.LINE_ID,
                "execution_authorized": True,
                "input_file_count": manifest["input_file_count"],
                "input_logical_key_sha256": manifest[
                    "input_logical_key_sha256"
                ],
                "file_contract_sha256": manifest["file_contract_sha256"],
                "runtime_contract_sha256": manifest["runtime_contract_sha256"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(module.Stage002Error, match="synthetic_worker_failure"):
        module.run_parent_qualification(
            final_dir=final_dir,
            failure_dir=failure_dir,
            claim_path=claim_path,
            freeze_path=freeze_path,
        )

    assert claim_path.is_file()
    assert failure_dir.is_dir() and not final_dir.exists()
    assert not (failure_dir / "workers/A1/runtime").exists()
    failure = json.loads((failure_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["status"] == "failed"
    assert failure["reviewer_started"] is False
    with pytest.raises(module.Stage002Error, match="execution_claim_exists"):
        module.claim_execution(claim_path, manifest)


def test_run_cli_uses_only_fixed_v3_paths(module, monkeypatch, capsys) -> None:
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
