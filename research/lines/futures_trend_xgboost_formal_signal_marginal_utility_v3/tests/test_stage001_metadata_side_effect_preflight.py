from __future__ import annotations

import importlib.util
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


LINE_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = LINE_ROOT / "tools/stage001_metadata_side_effect_preflight.py"
CANDIDATE_MODULE_NAME = (
    "run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest"
)


@pytest.fixture()
def module():
    spec = importlib.util.spec_from_file_location(
        "stage001_metadata_side_effect_preflight_test",
        MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def test_metadata_output_redirect_is_narrow_and_restores_after_exception(
    module,
    tmp_path,
) -> None:
    original_universe = Path("/formal/static18_plus_fu.csv")
    original_eligibility = Path("/formal/post_signal_eligibility.csv")
    candidate_module = SimpleNamespace(
        UNIVERSE_PATH=original_universe,
        AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH=original_eligibility,
    )
    worker_root = tmp_path / "A1"
    worker_root.mkdir()

    with pytest.raises(RuntimeError, match="synthetic failure"):
        with module.redirect_metadata_outputs(candidate_module, worker_root) as targets:
            assert candidate_module.UNIVERSE_PATH == (
                worker_root / "derived/static18_plus_fu.csv"
            )
            assert candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH == (
                worker_root / "derived/post_signal_eligibility.csv"
            )
            assert targets == {
                "universe": worker_root / "derived/static18_plus_fu.csv",
                "post_signal_eligibility": (
                    worker_root / "derived/post_signal_eligibility.csv"
                ),
            }
            raise RuntimeError("synthetic failure")

    assert candidate_module.UNIVERSE_PATH is original_universe
    assert (
        candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
        is original_eligibility
    )


def test_verify_derived_outputs_requires_byte_exact_frozen_files(
    module,
    tmp_path,
) -> None:
    expected = {
        "universe": tmp_path / "expected_universe.csv",
        "post_signal_eligibility": tmp_path / "expected_eligibility.csv",
    }
    generated = {
        "universe": tmp_path / "generated_universe.csv",
        "post_signal_eligibility": tmp_path / "generated_eligibility.csv",
    }
    expected["universe"].write_bytes(b"a,b\n1,2\n")
    expected["post_signal_eligibility"].write_bytes(b"x,y\n3,4\n")
    generated["universe"].write_bytes(expected["universe"].read_bytes())
    generated["post_signal_eligibility"].write_bytes(
        expected["post_signal_eligibility"].read_bytes()
    )

    result = module.verify_derived_outputs(generated, expected)

    assert result["universe"]["bytes_equal"] is True
    assert result["post_signal_eligibility"]["bytes_equal"] is True
    generated["universe"].write_bytes(b"a,b\n1,9\n")
    with pytest.raises(module.MetadataPreflightError, match="derived_output_mismatch:universe"):
        module.verify_derived_outputs(generated, expected)


def _valid_metadata() -> dict[str, object]:
    symbols = ["a2401.SHFE", "b2401.DCE"]
    return {
        "vt_symbols": symbols,
        "rates": {symbol: 0.0001 for symbol in symbols},
        "slippages": {symbol: 1.0 for symbol in symbols},
        "sizes": {symbol: 10 for symbol in symbols},
        "priceticks": {symbol: 1.0 for symbol in symbols},
        "margin_ratios": {symbol: 0.15 for symbol in symbols},
        "metadata_sources": {
            "a2401.SHFE": "tqsdk",
            "b2401.DCE": "static",
        },
        "source_symbol_by_contract": {
            "a2401.SHFE": "a.SHFE",
            "b2401.DCE": "b.DCE",
        },
        "product_symbols": ["a.SHFE", "b.DCE"],
    }


def test_metadata_contract_requires_complete_symbol_mappings(module) -> None:
    metadata = _valid_metadata()

    contract = module.metadata_contract(metadata)

    assert contract["vt_symbol_count"] == 2
    assert contract["product_symbol_count"] == 2
    assert contract["metadata_source_counts"] == {"static": 1, "tqsdk": 1}
    assert re.fullmatch(r"[0-9a-f]{64}", contract["metadata_sha256"])

    metadata["sizes"].pop("b2401.DCE")
    with pytest.raises(module.MetadataPreflightError, match="metadata_mapping_keys_invalid:sizes"):
        module.metadata_contract(metadata)


def test_guarded_metadata_preflight_has_zero_replay_and_restores_paths(
    module,
    monkeypatch,
    tmp_path,
) -> None:
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
    original_universe = Path("/formal/universe.csv")
    original_eligibility = Path("/formal/eligibility.csv")
    candidate_module = SimpleNamespace(
        __file__=str(candidate_file),
        UNIVERSE_PATH=original_universe,
        AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH=original_eligibility,
    )

    def _metadata():
        candidate_module.UNIVERSE_PATH.write_bytes(expected["universe"].read_bytes())
        candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH.write_bytes(
            expected["post_signal_eligibility"].read_bytes()
        )
        return _valid_metadata()

    context = {"s901": SimpleNamespace(s513=SimpleNamespace(_metadata=_metadata))}
    monkeypatch.setitem(sys.modules, CANDIDATE_MODULE_NAME, candidate_module)
    preflight = module.load_preflight_module()

    result = module.run_guarded_metadata_preflight(
        worker_root=worker_root,
        expected_outputs=expected,
        expected_candidate_module_path=candidate_file,
        attestation={"frozen": True},
        preflight=preflight,
        context_importer=lambda _attestation: (
            context,
            [{"release": "checked"}],
            True,
        ),
    )

    assert result["metadata"]["vt_symbol_count"] == 2
    assert result["formal_replay_call_count"] == 0
    assert result["network_connection_attempt_count"] == 0
    assert all(value == 0 for value in result["sensitive_counters"].values())
    assert result["release_adapter_call_count"] == 1
    assert result["release_adapter_restored"] is True
    assert result["metadata_output_paths_restored"] is True
    assert result["derived_outputs"]["universe"]["bytes_equal"] is True
    assert candidate_module.UNIVERSE_PATH is original_universe
    assert (
        candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
        is original_eligibility
    )


def test_collect_input_files_binds_v3_runtime_sources_and_v2_failure_evidence(
    module,
    monkeypatch,
) -> None:
    def forbidden_subprocess(*_args, **_kwargs):
        raise AssertionError("input discovery must not spawn a process")

    monkeypatch.setattr(subprocess, "run", forbidden_subprocess)
    files = module.collect_input_files()

    assert len(files) == 1420
    assert {
        "v3_runner",
        "v3_tests",
        "v3_line",
        "v3_preregistration",
        "v2_stage002_claim",
        "v2_stage002_failure",
        "v2_stage002_worker_failure",
        "v2_stage001_preflight_tool",
        "v2_font_cache",
        "v2_release_attestation",
        "source_structural_universe",
        "source_ai_top8_eligibility",
        "expected_post_signal_eligibility",
        "product_universe",
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
    assert all(path.is_file() and not path.is_symlink() for path in files.values())


def test_input_manifest_is_process_free_reproducible_and_exact_current(
    module,
    monkeypatch,
) -> None:
    def forbidden_subprocess(*_args, **_kwargs):
        raise AssertionError("manifest construction must not spawn a process")

    monkeypatch.setattr(subprocess, "run", forbidden_subprocess)
    first = module.build_input_manifest()
    second = module.build_input_manifest()

    assert first == second
    assert first["schema_version"] == 1
    assert first["stage"] == "stage001_metadata_side_effect_preflight"
    assert first["line_id"] == (
        "futures_trend_xgboost_formal_signal_marginal_utility_v3"
    )
    assert first["input_file_count"] == 1420
    assert set(first["files"]) == set(module.collect_input_files())
    assert re.fullmatch(r"[0-9a-f]{64}", first["input_logical_key_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", first["file_contract_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", first["runtime_contract_sha256"])
    assert module.validate_current_input_manifest(first) == first

    drifted = json.loads(json.dumps(first))
    drifted["files"]["v3_runner"]["sha256"] = "f" * 64
    drifted["file_contract_sha256"] = module._file_contract_sha256(
        drifted["files"]
    )
    monkeypatch.setattr(module, "build_input_manifest", lambda: drifted)

    with pytest.raises(module.MetadataPreflightError, match="current_input_manifest_drift"):
        module.validate_current_input_manifest(first)


def test_frozen_metadata_files_match_preregistered_identity(module) -> None:
    manifest = module.build_input_manifest()

    outputs = module.validate_frozen_metadata_files(manifest)

    assert outputs == {
        "universe": module.PRODUCT_UNIVERSE.resolve(strict=True),
        "post_signal_eligibility": (
            module.EXPECTED_POST_SIGNAL_ELIGIBILITY.resolve(strict=True)
        ),
    }
    drifted = json.loads(json.dumps(manifest))
    drifted["files"]["source_structural_universe"]["sha256"] = "e" * 64
    with pytest.raises(
        module.MetadataPreflightError,
        match="frozen_metadata_file_identity_mismatch:source_structural_universe",
    ):
        module.validate_frozen_metadata_files(drifted)


def test_worker_command_uses_sandbox_and_isolated_interpreter(
    module,
    tmp_path,
) -> None:
    paths = module.prepare_metadata_worker_root(tmp_path / "A1")
    manifest_path = tmp_path / "input_manifest.json"
    manifest_path.write_text("{}\n", encoding="utf-8")
    probe = tmp_path / ".sandbox_probe_A1"

    command = module.worker_command(paths, "A1", manifest_path, probe)

    assert command[:3] == [
        "/usr/bin/sandbox-exec",
        "-f",
        str(paths["profile"]),
    ]
    assert command[3:7] == [
        str(Path(sys.executable).resolve(strict=True)),
        "-I",
        "-S",
        "-B",
    ]
    assert "--worker" in command
    assert command[command.index("--worker-id") + 1] == "A1"
    assert command[command.index("--manifest-path") + 1] == str(
        manifest_path.resolve(strict=True)
    )
    assert command[command.index("--attestation-path") + 1] == str(
        module.V2_RELEASE_ATTESTATION.resolve(strict=True)
    )
    assert not (paths["runtime"] / ".vntrader/database.db").exists()


def test_run_metadata_worker_writes_only_safety_receipt_and_private_derivations(
    module,
    monkeypatch,
    tmp_path,
) -> None:
    paths = module.prepare_metadata_worker_root(tmp_path / "A1")
    manifest = {
        "formal_identity": {"release": "frozen"},
        "input_file_count": 1420,
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
        SENSITIVE_COUNTER_KEYS=module.load_preflight_module().SENSITIVE_COUNTER_KEYS,
    )
    zero_counters = {
        key: 0 for key in module.load_preflight_module().SENSITIVE_COUNTER_KEYS
    }
    derived = paths["worker_root"] / "derived"
    derived.mkdir()
    universe = derived / "static18_plus_fu.csv"
    eligibility = derived / "post_signal_eligibility.csv"
    universe.write_bytes(b"universe\n")
    eligibility.write_bytes(b"eligibility\n")
    guarded = {
        "candidate_module_path": str(tmp_path / "candidate.py"),
        "metadata": {
            "metadata_sha256": "d" * 64,
            "vt_symbol_count": 2,
            "product_symbol_count": 2,
            "metadata_fields": ["vt_symbols"],
            "metadata_source_counts": {"static": 2},
        },
        "derived_outputs": {
            "universe": {"bytes_equal": True, "generated": module._file_identity(universe)},
            "post_signal_eligibility": {
                "bytes_equal": True,
                "generated": module._file_identity(eligibility),
            },
        },
        "metadata_output_paths_restored": True,
        "sensitive_counters": zero_counters,
        "network_connection_attempt_count": 0,
        "formal_replay_call_count": 0,
        "release_adapter_call_count": 1,
        "release_adapter_calls": [{"release": "checked"}],
        "release_adapter_restored": True,
    }
    monkeypatch.setattr(module, "load_preflight_module", lambda: fake_preflight)
    monkeypatch.setattr(
        module,
        "validate_current_input_manifest",
        lambda recorded: recorded,
    )
    monkeypatch.setattr(
        module,
        "validate_frozen_metadata_files",
        lambda _recorded: {
            "universe": tmp_path / "expected_universe.csv",
            "post_signal_eligibility": tmp_path / "expected_eligibility.csv",
        },
    )
    monkeypatch.setattr(
        module,
        "run_guarded_metadata_preflight",
        lambda **_kwargs: guarded,
    )

    receipt = module.run_metadata_worker(
        worker_id="A1",
        worker_root=paths["worker_root"],
        runtime_root=paths["runtime"],
        receipt_path=paths["receipt"],
        external_probe_path=tmp_path / ".sandbox_probe_A1",
        attestation_path=module.V2_RELEASE_ATTESTATION,
        manifest_path=manifest_path,
    )

    assert receipt["status"] == "passed"
    assert receipt["metadata"]["metadata_sha256"] == "d" * 64
    assert receipt["formal_replay_call_count"] == 0
    assert receipt["network_connection_attempt_count"] == 0
    assert all(value == 0 for value in receipt["sensitive_counters"].values())
    assert receipt["metadata_output_paths_restored"] is True
    assert json.loads(paths["receipt"].read_text(encoding="utf-8")) == receipt
    forbidden = {"return", "drawdown", "sharpe", "pnl", "label", "prediction"}
    assert forbidden.isdisjoint(receipt)


def _synthetic_worker_receipt(module, worker_root: Path, worker_id: str, pid: int):
    derived = worker_root / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    universe = derived / "static18_plus_fu.csv"
    eligibility = derived / "post_signal_eligibility.csv"
    universe.write_bytes(b"universe\n")
    eligibility.write_bytes(b"eligibility\n")
    expected_universe = worker_root.parent.parent / "expected_universe.csv"
    expected_eligibility = worker_root.parent.parent / "expected_eligibility.csv"
    expected_universe.write_bytes(b"universe\n")
    expected_eligibility.write_bytes(b"eligibility\n")
    preflight = module.load_preflight_module()
    return {
        "schema_version": 1,
        "status": "passed",
        "stage": module.STAGE,
        "line_id": module.LINE_ID,
        "worker_id": worker_id,
        "pid": pid,
        "python_executable": str(Path(sys.executable).resolve(strict=True)),
        "python_version": sys.version,
        "bootstrap": {"isolated": True},
        "approved_sys_path": ["site-packages", "workspace"],
        "runtime_root": str(worker_root / "runtime"),
        "sandbox_probe": {"write_denied": True},
        "font_cache": {"sha256": "1" * 64},
        "release_attestation_sha256": "2" * 64,
        "production_head": "3" * 40,
        "formal_identity": {"release": "frozen"},
        "input_file_count": 1420,
        "input_logical_key_sha256": "a" * 64,
        "file_contract_sha256": "b" * 64,
        "runtime_contract_sha256": "c" * 64,
        "candidate_module_path": str(module.CANDIDATE_MODULE_PATH),
        "metadata": {
            "metadata_sha256": "d" * 64,
            "vt_symbol_count": 2,
            "product_symbol_count": 2,
            "metadata_fields": ["vt_symbols"],
            "metadata_source_counts": {"static": 2},
        },
        "derived_outputs": {
            "universe": {
                "bytes_equal": True,
                "generated": module._file_identity(universe),
                "expected": module._file_identity(expected_universe),
            },
            "post_signal_eligibility": {
                "bytes_equal": True,
                "generated": module._file_identity(eligibility),
                "expected": module._file_identity(expected_eligibility),
            },
        },
        "metadata_output_paths_restored": True,
        "sensitive_counters": preflight.zero_sensitive_counters(),
        "network_connection_attempt_count": 0,
        "formal_replay_call_count": 0,
        "release_adapter_call_count": 1,
        "release_adapter_calls": [{"release": "checked"}],
        "release_adapter_restored": True,
    }


def test_run_cold_worker_validates_receipt_and_private_outputs(
    module,
    monkeypatch,
    tmp_path,
) -> None:
    manifest = {
        "formal_identity": {"release": "frozen"},
        "input_file_count": 1420,
        "input_logical_key_sha256": "a" * 64,
        "file_contract_sha256": "b" * 64,
        "runtime_contract_sha256": "c" * 64,
    }
    manifest_path = tmp_path / "input_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        worker_root = Path(command[command.index("--worker-root") + 1])
        receipt_path = Path(command[command.index("--receipt-path") + 1])
        receipt = _synthetic_worker_receipt(module, worker_root, "A1", 12345)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.run_cold_worker(
        tmp_path / "attempt",
        "A1",
        manifest_path,
        manifest,
    )

    assert result["receipt"]["status"] == "passed"
    assert result["worker_root"].name == "A1"
    assert result["derived_paths"]["universe"].read_bytes() == b"universe\n"
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


def test_parent_runs_two_cold_workers_and_requires_portable_equality(
    module,
    monkeypatch,
    tmp_path,
) -> None:
    manifest = {
        "formal_identity": {"release": "frozen"},
        "input_file_count": 1420,
        "input_logical_key_sha256": "a" * 64,
        "file_contract_sha256": "b" * 64,
        "runtime_contract_sha256": "c" * 64,
    }
    monkeypatch.setattr(module, "build_input_manifest", lambda: manifest)
    monkeypatch.setattr(
        module,
        "validate_input_manifest_payload",
        lambda recorded: recorded,
    )
    monkeypatch.setattr(
        module,
        "validate_current_input_manifest",
        lambda recorded: recorded,
    )
    monkeypatch.setattr(
        module,
        "validate_frozen_metadata_files",
        lambda _recorded: {
            "universe": tmp_path / "expected_universe.csv",
            "post_signal_eligibility": tmp_path / "expected_eligibility.csv",
        },
    )
    calls = []

    def fake_worker(output, worker_id, manifest_path, recorded):
        assert recorded == manifest
        assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
        calls.append(worker_id)
        worker_root = output / "workers" / worker_id
        runtime = worker_root / "runtime"
        runtime.mkdir(parents=True)
        receipt = _synthetic_worker_receipt(
            module,
            worker_root,
            worker_id,
            100 if worker_id == "A1" else 200,
        )
        receipt_path = worker_root / "receipt.json"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return {
            "worker_root": worker_root,
            "receipt_path": receipt_path,
            "log_path": worker_root / "worker.log",
            "derived_paths": {
                "universe": worker_root / "derived/static18_plus_fu.csv",
                "post_signal_eligibility": (
                    worker_root / "derived/post_signal_eligibility.csv"
                ),
            },
            "receipt": receipt,
        }

    monkeypatch.setattr(module, "run_cold_worker", fake_worker)
    output = tmp_path / "stage001_metadata_preflight"

    summary = module.run_parent_metadata_preflight(output)

    assert calls == ["A1", "A2"]
    assert summary["status"] == "passed"
    assert summary["worker_ids"] == ["A1", "A2"]
    assert summary["worker_pids_distinct"] is True
    assert summary["portable_receipts_equal"] is True
    assert summary["metadata"]["metadata_sha256"] == "d" * 64
    assert summary["formal_replay_call_count"] == 0
    assert summary["reviewer_started"] is False
    assert all(value == 0 for value in summary["sensitive_counters"].values())
    assert json.loads((output / "summary.json").read_text(encoding="utf-8")) == summary
    assert not (output / "workers/A1/runtime").exists()
    assert not (output / "workers/A2/runtime").exists()


def test_preflight_source_never_calls_formal_replay() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    called_names = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            called_names.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            called_names.append(node.func.attr)

    assert "_run_live_c9" not in called_names


@pytest.mark.skipif(not Path("/usr/bin/sandbox-exec").is_file(), reason="macOS only")
def test_cli_runs_two_clean_metadata_workers_without_replay(tmp_path) -> None:
    output_argument = Path("stage001_metadata_preflight")
    output = tmp_path / output_argument

    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(MODULE_PATH),
            "--run",
            "--output-dir",
            str(output_argument),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "passed"
    assert summary["worker_count"] == 2
    assert summary["worker_ids"] == ["A1", "A2"]
    assert summary["worker_pids_distinct"] is True
    assert summary["portable_receipts_equal"] is True
    assert summary["formal_replay_call_count"] == 0
    assert summary["network_connection_attempt_count"] == 0
    assert all(value == 0 for value in summary["sensitive_counters"].values())
    assert summary["derived_outputs"]["universe"]["generated"] == {
        "size": 6272,
        "sha256": "72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34",
    }
    assert summary["derived_outputs"]["post_signal_eligibility"]["generated"] == {
        "size": 51303,
        "sha256": "fa5fb5c1cfe06ace44dadc92bd2cc1a77bd4ee74beeab362234952950ca5bb3b",
    }
    assert not (output / "workers/A1/runtime").exists()
    assert not (output / "workers/A2/runtime").exists()
