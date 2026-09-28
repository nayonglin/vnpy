from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


LINE_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = LINE_ROOT / "tools/stage001_replay_profile_preflight.py"


@pytest.fixture()
def module():
    spec = importlib.util.spec_from_file_location(
        "v4_stage001_replay_profile_preflight_test",
        MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def test_collect_input_files_binds_v3_failure_and_v4_contract(
    module,
    monkeypatch,
) -> None:
    def forbidden_subprocess(*_args, **_kwargs):
        raise AssertionError("input discovery must not spawn a process")

    monkeypatch.setattr(subprocess, "run", forbidden_subprocess)
    files = module.collect_input_files()

    assert len(files) == 1446
    assert {
        "v4_runner",
        "v4_tests",
        "v4_line",
        "v4_preregistration",
        "v3_stage002_freeze_json",
        "v3_stage002_freeze_record",
        "v3_stage002_claim",
        "v3_stage002_failure_record",
        "v3_stage002_failure",
        "v3_stage002_worker_failure",
        "v3_stage002_failed_input_manifest",
        "v3_stage002_failed_a1_universe",
        "v3_stage002_failed_a1_post_signal_eligibility",
        "source_database",
    }.issubset(files)
    assert all(path.is_file() and not path.is_symlink() for path in files.values())


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


def test_guarded_profile_preflight_spans_all_builders_without_replay(
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
    original_universe = Path("/formal/universe.csv")
    original_eligibility = Path("/formal/eligibility.csv")
    candidate_module = SimpleNamespace(
        __file__=str(candidate_file),
        UNIVERSE_PATH=original_universe,
        AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH=original_eligibility,
    )
    calls = {"metadata": 0, "profile": 0, "live_overrides": 0}

    def write_derivations():
        candidate_module.UNIVERSE_PATH.write_bytes(expected["universe"].read_bytes())
        candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH.write_bytes(
            expected["post_signal_eligibility"].read_bytes()
        )

    def metadata():
        calls["metadata"] += 1
        write_derivations()
        return _valid_metadata()

    capital = SimpleNamespace(
        variant="c9",
        label="C9",
        account_capital=300_000.0,
        c3_capital=300_000.0,
        risk_multiplier=0.4,
    )
    spec = SimpleNamespace(
        profile="c9-profile",
        capital=capital,
        overrides={"alpha": 1, "products": ("a", "b")},
    )

    def profile(_metadata):
        calls["profile"] += 1
        write_derivations()
        return {
            "profile": "c9-profile",
            "strategy_cls": dict,
            "spec": spec,
        }

    def live_overrides():
        calls["live_overrides"] += 1
        write_derivations()
        return {"account_capital": 150_000.0, "enabled": True}

    context = {
        "s901": SimpleNamespace(
            s513=SimpleNamespace(_metadata=metadata),
            s847=SimpleNamespace(_c9_profile=profile),
        ),
        "live_config": SimpleNamespace(
            build_official_live_strategy_overrides=live_overrides
        ),
    }
    monkeypatch.setitem(sys.modules, module.CANDIDATE_MODULE_NAME, candidate_module)

    result = module.run_guarded_replay_profile_preflight(
        worker_root=worker_root,
        expected_outputs=expected,
        expected_candidate_module_path=candidate_file,
        attestation={"frozen": True},
        preflight=preflight,
        metadata_preflight=metadata_preflight,
        context_importer=lambda _attestation: (
            context,
            [{"release": "checked"}],
            True,
        ),
    )

    assert calls == {"metadata": 1, "profile": 1, "live_overrides": 1}
    assert result["formal_replay_call_count"] == 0
    assert result["network_connection_attempt_count"] == 0
    assert all(value == 0 for value in result["sensitive_counters"].values())
    assert result["metadata_output_paths_restored"] is True
    assert result["derived_outputs"]["universe"]["bytes_equal"] is True
    assert result["profile_contract"]["profile"] == "c9-profile"
    assert re.fullmatch(
        r"[0-9a-f]{64}",
        result["profile_contract"]["combined_overrides_sha256"],
    )
    assert candidate_module.UNIVERSE_PATH is original_universe
    assert (
        candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
        is original_eligibility
    )


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
    assert first["stage"] == "stage001_replay_profile_side_effect_preflight"
    assert first["line_id"] == (
        "futures_trend_xgboost_formal_signal_marginal_utility_v4"
    )
    assert first["input_file_count"] == 1446
    assert set(first["files"]) == set(module.collect_input_files())
    assert re.fullmatch(r"[0-9a-f]{64}", first["input_logical_key_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", first["file_contract_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", first["runtime_contract_sha256"])
    assert module.validate_current_input_manifest(first) == first

    drifted = json.loads(json.dumps(first))
    drifted["files"]["v4_runner"]["sha256"] = "f" * 64
    drifted["file_contract_sha256"] = module._file_contract_sha256(
        drifted["files"]
    )
    monkeypatch.setattr(module, "build_input_manifest", lambda: drifted)

    with pytest.raises(
        module.ProfilePreflightError,
        match="current_input_manifest_drift",
    ):
        module.validate_current_input_manifest(first)


def test_profile_aliases_only_replace_verified_exact_paths(module) -> None:
    def contract(root, risk=0.4, unknown="/common/other.csv"):
        universe = f"{root}/derived/static18_plus_fu.csv"
        spec = SimpleNamespace(
            profile="c9",
            capital=SimpleNamespace(account_capital=150000),
            overrides={"universe": Path(universe), "risk": risk, "other": unknown},
        )
        return module.profile_contract(
            {"profile": "c9", "strategy_cls": dict, "spec": spec},
            {"universe": universe},
            verified_path_aliases={universe: "/frozen/universe.csv"},
        )

    assert contract("/A1") == contract("/A2")
    assert contract("/A1") != contract("/A2", risk=0.5)
    assert contract("/A1") != contract("/A2", unknown="/A2/other.csv")


def test_worker_command_targets_v4_under_sandbox(module, tmp_path) -> None:
    paths = module.prepare_profile_worker_root(tmp_path / "A1")
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
    assert command[7] == str(MODULE_PATH.resolve(strict=True))
    assert command[command.index("--worker-id") + 1] == "A1"
    assert command[command.index("--manifest-path") + 1] == str(
        manifest_path.resolve(strict=True)
    )
    assert command[command.index("--attestation-path") + 1] == str(
        module.V2_RELEASE_ATTESTATION.resolve(strict=True)
    )


def _profile_contract_payload() -> dict[str, object]:
    return {
        "profile": "c9-profile",
        "strategy_class": "formal.Strategy",
        "spec_profile": "c9-profile",
        "capital": {
            "variant": "c9",
            "label": "C9",
            "account_capital": 150_000.0,
            "c3_capital": 150_000.0,
            "risk_multiplier": 0.5,
        },
        "profile_override_count": 1,
        "profile_override_keys": ["alpha"],
        "profile_overrides_sha256": "4" * 64,
        "live_override_count": 1,
        "live_override_keys": ["account_capital"],
        "live_overrides_sha256": "5" * 64,
        "combined_override_count": 2,
        "combined_override_keys": ["account_capital", "alpha"],
        "combined_overrides_sha256": "6" * 64,
    }


def _synthetic_worker_result(
    module,
    output: Path,
    worker_id: str,
    pid: int,
    profile_contract_payload: dict[str, object],
) -> dict[str, object]:
    worker_root = output / "workers" / worker_id
    runtime = worker_root / "runtime"
    runtime.mkdir(parents=True)
    derived = {
        "universe": {
            "bytes_equal": True,
            "generated": {"size": 10, "sha256": "7" * 64},
            "expected": {"size": 10, "sha256": "7" * 64},
        },
        "post_signal_eligibility": {
            "bytes_equal": True,
            "generated": {"size": 20, "sha256": "8" * 64},
            "expected": {"size": 20, "sha256": "8" * 64},
        },
    }
    preflight = module.load_preflight_module()
    receipt = {
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
        "runtime_root": str(runtime),
        "sandbox_probe": {"write_denied": True},
        "font_cache": {"sha256": "1" * 64},
        "release_attestation_sha256": "2" * 64,
        "production_head": "3" * 40,
        "formal_identity": {"release": "frozen"},
        "input_file_count": 1446,
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
        "derived_outputs": derived,
        "metadata_output_paths_restored": True,
        "profile_contract": profile_contract_payload,
        "sensitive_counters": preflight.zero_sensitive_counters(),
        "network_connection_attempt_count": 0,
        "formal_replay_call_count": 0,
        "release_adapter_call_count": 1,
        "release_adapter_calls": [{"release": "checked"}],
        "release_adapter_restored": True,
    }
    receipt_path = worker_root / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return {
        "worker_root": worker_root,
        "receipt_path": receipt_path,
        "log_path": worker_root / "worker.log",
        "derived_paths": {},
        "receipt": receipt,
    }


def test_parent_requires_profile_portable_equality(module, monkeypatch, tmp_path) -> None:
    manifest = {
        "formal_identity": {"release": "frozen"},
        "input_file_count": 1446,
        "input_logical_key_sha256": "a" * 64,
        "file_contract_sha256": "b" * 64,
        "runtime_contract_sha256": "c" * 64,
    }
    monkeypatch.setattr(module, "build_input_manifest", lambda: manifest)
    monkeypatch.setattr(module, "validate_input_manifest_payload", lambda value: value)
    monkeypatch.setattr(module, "validate_current_input_manifest", lambda value: value)
    monkeypatch.setattr(module, "validate_frozen_metadata_files", lambda _value: {})
    calls: list[str] = []

    def equal_worker(output, worker_id, _manifest_path, _manifest):
        calls.append(worker_id)
        return _synthetic_worker_result(
            module,
            output,
            worker_id,
            100 if worker_id == "A1" else 200,
            _profile_contract_payload(),
        )

    monkeypatch.setattr(module, "run_cold_worker", equal_worker)
    output = tmp_path / "passed"
    summary = module.run_parent_profile_preflight(output)

    assert calls == ["A1", "A2"]
    assert summary["status"] == "passed"
    assert summary["worker_pids_distinct"] is True
    assert summary["portable_receipts_equal"] is True
    assert summary["profile_contracts_equal"] is True
    assert summary["profile_contract"] == _profile_contract_payload()
    assert summary["formal_replay_call_count"] == 0
    assert summary["reviewer_started"] is False
    assert not (output / "workers/A1/runtime").exists()
    assert not (output / "workers/A2/runtime").exists()

    def drifted_worker(output, worker_id, _manifest_path, _manifest):
        payload = _profile_contract_payload()
        if worker_id == "A2":
            payload["combined_overrides_sha256"] = "9" * 64
        return _synthetic_worker_result(
            module,
            output,
            worker_id,
            300 if worker_id == "A1" else 400,
            payload,
        )

    monkeypatch.setattr(module, "run_cold_worker", drifted_worker)
    failed_output = tmp_path / "failed"
    with pytest.raises(
        module.ProfilePreflightError,
        match="parent_profile_preflight_gate_failed",
    ):
        module.run_parent_profile_preflight(failed_output)
    failure = json.loads((failed_output / "failure.json").read_text(encoding="utf-8"))
    assert failure["reviewer_started"] is False


def test_preflight_source_never_calls_formal_replay_or_engine() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    called_names = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            called_names.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            called_names.append(node.func.attr)

    assert "_ensure_c9_minute_bars" not in called_names
    assert "_run_live_c9" not in called_names
    assert "_run_profile" not in called_names


@pytest.mark.skipif(not Path("/usr/bin/sandbox-exec").is_file(), reason="macOS only")
def test_cli_runs_two_clean_profile_workers_without_replay(tmp_path) -> None:
    output_argument = Path("stage001_profile_preflight")
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
    assert summary["profile_contracts_equal"] is True
    assert summary["formal_replay_call_count"] == 0
    assert summary["network_connection_attempt_count"] == 0
    assert all(value == 0 for value in summary["sensitive_counters"].values())
    assert re.fullmatch(
        r"[0-9a-f]{64}",
        summary["profile_contract"]["combined_overrides_sha256"],
    )
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
