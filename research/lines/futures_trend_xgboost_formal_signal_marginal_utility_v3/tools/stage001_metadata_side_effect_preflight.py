from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import traceback
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any


LINE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
V1_LINE_ROOT = (
    WORKSPACE_ROOT
    / "research/lines/futures_trend_xgboost_formal_signal_marginal_utility"
)
V1_RUNNER = V1_LINE_ROOT / "tools/stage001_formal_event_feature_qualification.py"
V2_LINE_ROOT = (
    WORKSPACE_ROOT
    / "research/lines/futures_trend_xgboost_formal_signal_marginal_utility_v2"
)
V2_PREFLIGHT_TOOL = (
    V2_LINE_ROOT / "tools/stage001_import_preflight.py"
)
V2_STAGE002_RUNNER = V2_LINE_ROOT / "tools/stage002_event_feature_qualification.py"
V2_STAGE002_TESTS = V2_LINE_ROOT / "tests/test_stage002_event_feature_qualification.py"
V2_STAGE002_CLAIM = V2_LINE_ROOT / "stages/20260905_stage002_execution_state/claim.json"
V2_STAGE002_FAILURE = (
    V2_LINE_ROOT / "artifacts/stage002_event_feature_qualification_failed/failure.json"
)
V2_STAGE002_WORKER_FAILURE = (
    V2_LINE_ROOT
    / "artifacts/stage002_event_feature_qualification_failed/workers/A1/failure_receipt.json"
)
V2_FONT_CACHE = V2_LINE_ROOT / "materials/fontlist-v390.json"
V2_RELEASE_ATTESTATION = V2_LINE_ROOT / "materials/release_manifest_commit_attestation.json"
V2_STAGE001_ARTIFACT = V2_LINE_ROOT / "artifacts/stage001_import_preflight"
V3_TESTS = LINE_ROOT / "tests/test_stage001_metadata_side_effect_preflight.py"
V3_PREREGISTRATION = (
    LINE_ROOT
    / "stages/20260905_1749_stage000_metadata_side_effect_preflight_preregistration.md"
)
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
PRODUCTION_OUTPUTS = PRODUCTION_ROOT / "examples/portfolio_backtesting/backtest_outputs"
PRODUCT_UNIVERSE = (
    WORKSPACE_ROOT
    / "examples/portfolio_backtesting/backtest_outputs"
    / "qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_static18_plus_fu_universe.csv"
)
SOURCE_STRUCTURAL_UNIVERSE = (
    PRODUCTION_OUTPUTS
    / "qmt_roll_full_market_structural_prefilter_eligible_full_market_structural_prefilter_v1.csv"
)
SOURCE_AI_TOP8_ELIGIBILITY = (
    PRODUCTION_OUTPUTS
    / "qmt_roll_ai_product_pool_shadow_portfolio_eligibility_ai_product_pool_shadow_v1.csv"
)
EXPECTED_POST_SIGNAL_ELIGIBILITY = (
    PRODUCTION_OUTPUTS
    / "qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_ai_top8_plus_fu_satellite_post_signal_eligibility.csv"
)
EXPECTED_INPUT_FILE_COUNT = 1420
STAGE = "stage001_metadata_side_effect_preflight"
LINE_ID = "futures_trend_xgboost_formal_signal_marginal_utility_v3"
SANDBOX_EXECUTABLE = Path("/usr/bin/sandbox-exec")
FROZEN_METADATA_FILES = {
    "product_universe": {
        "path": PRODUCT_UNIVERSE,
        "size": 6272,
        "sha256": "72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34",
    },
    "source_structural_universe": {
        "path": SOURCE_STRUCTURAL_UNIVERSE,
        "size": 7943,
        "sha256": "dc389dce4f6d404061127390deea04e15b7cd641f6bb6c265f9721a7c65fc309",
    },
    "source_ai_top8_eligibility": {
        "path": SOURCE_AI_TOP8_ELIGIBILITY,
        "size": 70446,
        "sha256": "63c976a09f035fd1b7e57401de5da2d48c2b9538382ede8fe28fbc71d6017242",
    },
    "expected_post_signal_eligibility": {
        "path": EXPECTED_POST_SIGNAL_ELIGIBILITY,
        "size": 51303,
        "sha256": "fa5fb5c1cfe06ace44dadc92bd2cc1a77bd4ee74beeab362234952950ca5bb3b",
    },
}
V1_ADMIN_INPUT_KEYS = {
    "stage001_runner",
    "stage001_worker_bootstrap",
    "stage001_feature_tool",
    "stage001_preregistration",
    "stage001_pre_ai_boundary_remediation",
    "stage001_plan",
    "stage001_feature_tests",
    "stage001_runner_tests",
}
CANDIDATE_MODULE_NAME = (
    "run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest"
)
CANDIDATE_MODULE_PATH = (
    Path("/Users/bytedance/Desktop/person/vnpy_production_live")
    / "examples/portfolio_backtesting"
    / f"{CANDIDATE_MODULE_NAME}.py"
)


class MetadataPreflightError(RuntimeError):
    pass


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, Path(path).resolve(strict=True))
    if spec is None or spec.loader is None:
        raise MetadataPreflightError(f"module_spec_failed:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_preflight_module() -> Any:
    return _load_module("v3_stage001_import_preflight_support", V2_PREFLIGHT_TOOL)


def load_v1_runner() -> Any:
    return _load_module("v3_stage001_v1_contract_support", V1_RUNNER)


def collect_input_files() -> dict[str, Path]:
    files = dict(load_v1_runner().collect_input_files())
    for key in V1_ADMIN_INPUT_KEYS:
        if files.pop(key, None) is None:
            raise MetadataPreflightError(f"v1_admin_input_missing:{key}")
    files.update(
        {
            "v3_runner": Path(__file__).resolve(),
            "v3_tests": V3_TESTS,
            "v3_line": LINE_ROOT / "LINE.md",
            "v3_preregistration": V3_PREREGISTRATION,
            "v2_stage002_runner": V2_STAGE002_RUNNER,
            "v2_stage002_tests": V2_STAGE002_TESTS,
            "v2_stage002_claim": V2_STAGE002_CLAIM,
            "v2_stage002_failure": V2_STAGE002_FAILURE,
            "v2_stage002_worker_failure": V2_STAGE002_WORKER_FAILURE,
            "v2_stage001_preflight_tool": V2_PREFLIGHT_TOOL,
            "v2_font_cache": V2_FONT_CACHE,
            "v2_release_attestation": V2_RELEASE_ATTESTATION,
            "v2_stage001_summary": V2_STAGE001_ARTIFACT / "summary.json",
            "v2_stage001_a1_receipt": V2_STAGE001_ARTIFACT / "A1/receipt.json",
            "v2_stage001_a2_receipt": V2_STAGE001_ARTIFACT / "A2/receipt.json",
            "source_structural_universe": SOURCE_STRUCTURAL_UNIVERSE,
            "source_ai_top8_eligibility": SOURCE_AI_TOP8_ELIGIBILITY,
            "expected_post_signal_eligibility": EXPECTED_POST_SIGNAL_ELIGIBILITY,
        }
    )
    if len(files) != EXPECTED_INPUT_FILE_COUNT:
        raise MetadataPreflightError(
            f"input_inventory_count_mismatch:{len(files)}:{EXPECTED_INPUT_FILE_COUNT}"
        )
    for key, path in files.items():
        if path.is_symlink() or not path.is_file():
            raise MetadataPreflightError(f"input_file_invalid:{key}:{path}")
    return dict(sorted(files.items()))


def _stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _require_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise MetadataPreflightError(f"invalid_sha256:{field}")
    return value


def _logical_key_sha256(files: Mapping[str, Path]) -> str:
    return hashlib.sha256(_stable_json_bytes(sorted(files))).hexdigest()


def _file_contract_sha256(files: Mapping[str, Mapping[str, Any]]) -> str:
    contract = {
        key: {
            "path": value["path"],
            "size": value["size"],
            "mtime_ns": value["mtime_ns"],
            "sha256": value["sha256"],
        }
        for key, value in sorted(files.items())
    }
    return hashlib.sha256(_stable_json_bytes(contract)).hexdigest()


def build_input_manifest() -> dict[str, Any]:
    v1 = load_v1_runner()
    source_files = collect_input_files()
    files = {key: _file_identity(path) for key, path in source_files.items()}
    uname = os.uname()
    runtime = {
        "python_version": sys.version,
        "python_implementation": sys.implementation.name,
        "python_executable": str(Path(sys.executable).resolve(strict=True)),
        "platform": {
            "os_name": os.name,
            "sys_platform": sys.platform,
            "sysname": uname.sysname,
            "release": uname.release,
            "version": uname.version,
            "machine": uname.machine,
        },
        "numpy_version": v1.np.__version__,
        "pandas_version": v1.pd.__version__,
        "repository": v1.repository_state(),
    }
    return {
        "schema_version": 1,
        "stage": STAGE,
        "line_id": LINE_ID,
        "formal_identity": v1._active_formal_identity(),
        "files": files,
        "input_file_count": len(files),
        "input_logical_key_sha256": _logical_key_sha256(source_files),
        "file_contract_sha256": _file_contract_sha256(files),
        "runtime": runtime,
        "runtime_contract_sha256": hashlib.sha256(
            _stable_json_bytes(runtime)
        ).hexdigest(),
    }


def validate_input_manifest_payload(recorded: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "stage",
        "line_id",
        "formal_identity",
        "files",
        "input_file_count",
        "input_logical_key_sha256",
        "file_contract_sha256",
        "runtime",
        "runtime_contract_sha256",
    }
    if set(recorded) != required:
        raise MetadataPreflightError("input_manifest_schema_invalid")
    if recorded.get("schema_version") != 1:
        raise MetadataPreflightError("input_manifest_version_invalid")
    if recorded.get("stage") != STAGE or recorded.get("line_id") != LINE_ID:
        raise MetadataPreflightError("input_manifest_identity_invalid")

    files = recorded.get("files")
    if not isinstance(files, Mapping):
        raise MetadataPreflightError("input_manifest_files_invalid")
    file_count = recorded.get("input_file_count")
    if (
        isinstance(file_count, bool)
        or not isinstance(file_count, int)
        or file_count != EXPECTED_INPUT_FILE_COUNT
        or len(files) != file_count
    ):
        raise MetadataPreflightError("input_manifest_file_count_invalid")
    normalized_files: dict[str, dict[str, Any]] = {}
    for key, identity in files.items():
        if not isinstance(key, str) or not isinstance(identity, Mapping):
            raise MetadataPreflightError("input_manifest_file_identity_invalid")
        if set(identity) != {"path", "size", "mtime_ns", "sha256"}:
            raise MetadataPreflightError(
                f"input_manifest_file_identity_invalid:{key}"
            )
        if not isinstance(identity.get("path"), str):
            raise MetadataPreflightError(f"input_manifest_file_path_invalid:{key}")
        for field in ("size", "mtime_ns"):
            value = identity.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise MetadataPreflightError(
                    f"input_manifest_file_{field}_invalid:{key}"
                )
        _require_sha256(identity.get("sha256"), f"files.{key}.sha256")
        normalized_files[key] = dict(identity)

    logical_paths = {
        key: Path(identity["path"]) for key, identity in normalized_files.items()
    }
    if _require_sha256(
        recorded.get("input_logical_key_sha256"),
        "input_logical_key_sha256",
    ) != _logical_key_sha256(logical_paths):
        raise MetadataPreflightError("input_manifest_logical_key_sha_mismatch")
    if _require_sha256(
        recorded.get("file_contract_sha256"),
        "file_contract_sha256",
    ) != _file_contract_sha256(normalized_files):
        raise MetadataPreflightError("input_manifest_file_contract_sha_mismatch")

    runtime = recorded.get("runtime")
    if not isinstance(runtime, Mapping):
        raise MetadataPreflightError("input_manifest_runtime_invalid")
    if _require_sha256(
        recorded.get("runtime_contract_sha256"),
        "runtime_contract_sha256",
    ) != hashlib.sha256(_stable_json_bytes(runtime)).hexdigest():
        raise MetadataPreflightError("input_manifest_runtime_sha_mismatch")
    if not isinstance(recorded.get("formal_identity"), Mapping):
        raise MetadataPreflightError("input_manifest_formal_identity_invalid")
    return dict(recorded)


def validate_current_input_manifest(recorded: Mapping[str, Any]) -> dict[str, Any]:
    expected = validate_input_manifest_payload(recorded)
    observed = build_input_manifest()
    validate_input_manifest_payload(observed)
    if observed != expected:
        raise MetadataPreflightError("current_input_manifest_drift")
    return observed


def validate_frozen_metadata_files(
    manifest: Mapping[str, Any],
) -> dict[str, Path]:
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise MetadataPreflightError("frozen_metadata_files_missing")
    for key, expected in FROZEN_METADATA_FILES.items():
        observed = files.get(key)
        if not isinstance(observed, Mapping):
            raise MetadataPreflightError(f"frozen_metadata_file_missing:{key}")
        expected_identity = {
            "path": str(Path(expected["path"]).resolve(strict=True)),
            "size": int(expected["size"]),
            "sha256": str(expected["sha256"]),
        }
        observed_identity = {
            "path": str(observed.get("path", "")),
            "size": observed.get("size"),
            "sha256": observed.get("sha256"),
        }
        if observed_identity != expected_identity:
            raise MetadataPreflightError(
                f"frozen_metadata_file_identity_mismatch:{key}"
            )
    return {
        "universe": PRODUCT_UNIVERSE.resolve(strict=True),
        "post_signal_eligibility": EXPECTED_POST_SIGNAL_ELIGIBILITY.resolve(
            strict=True
        ),
    }


def prepare_metadata_worker_root(worker_root: Path) -> dict[str, Path]:
    return dict(load_preflight_module().prepare_worker_root(Path(worker_root)))


def worker_command(
    paths: Mapping[str, Path],
    worker_id: str,
    manifest_path: Path,
    external_probe_path: Path,
) -> list[str]:
    if worker_id not in {"A1", "A2"}:
        raise MetadataPreflightError("worker_id_invalid")
    return [
        str(SANDBOX_EXECUTABLE),
        "-f",
        str(paths["profile"]),
        str(Path(sys.executable).resolve(strict=True)),
        "-I",
        "-S",
        "-B",
        str(Path(__file__).resolve(strict=True)),
        "--worker",
        "--worker-id",
        worker_id,
        "--worker-root",
        str(paths["worker_root"]),
        "--runtime-root",
        str(paths["runtime"]),
        "--receipt-path",
        str(paths["receipt"]),
        "--external-probe-path",
        str(Path(external_probe_path).resolve(strict=False)),
        "--attestation-path",
        str(V2_RELEASE_ATTESTATION.resolve(strict=True)),
        "--manifest-path",
        str(Path(manifest_path).resolve(strict=True)),
    ]


def _read_json_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MetadataPreflightError(f"{label}_read_failed") from exc
    if not isinstance(payload, Mapping):
        raise MetadataPreflightError(f"{label}_invalid")
    return dict(payload)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(Path(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes_exclusive(path: Path, payload: bytes) -> None:
    destination = Path(path)
    descriptor = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise MetadataPreflightError("exclusive_write_failed")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(destination.parent)


def _write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    _write_bytes_exclusive(Path(path), _stable_json_bytes(payload) + b"\n")


def _validate_guarded_result(
    result: Mapping[str, Any],
    preflight: Any,
) -> dict[str, Any]:
    counters = result.get("sensitive_counters")
    if not isinstance(counters, Mapping) or set(counters) != set(
        preflight.SENSITIVE_COUNTER_KEYS
    ):
        raise MetadataPreflightError("worker_sensitive_counter_schema_invalid")
    if any(value != 0 for value in counters.values()):
        raise MetadataPreflightError("worker_sensitive_counter_nonzero")
    if (
        result.get("network_connection_attempt_count") != 0
        or result.get("formal_replay_call_count") != 0
        or result.get("release_adapter_call_count") != 1
        or result.get("release_adapter_restored") is not True
        or result.get("metadata_output_paths_restored") is not True
    ):
        raise MetadataPreflightError("worker_safety_result_invalid")
    metadata = result.get("metadata")
    if not isinstance(metadata, Mapping):
        raise MetadataPreflightError("worker_metadata_contract_missing")
    _require_sha256(metadata.get("metadata_sha256"), "metadata.metadata_sha256")
    derived = result.get("derived_outputs")
    if not isinstance(derived, Mapping) or set(derived) != {
        "universe",
        "post_signal_eligibility",
    }:
        raise MetadataPreflightError("worker_derived_outputs_invalid")
    if any(
        not isinstance(value, Mapping) or value.get("bytes_equal") is not True
        for value in derived.values()
    ):
        raise MetadataPreflightError("worker_derived_output_mismatch")
    return dict(result)


def run_metadata_worker(
    *,
    worker_id: str,
    worker_root: Path,
    runtime_root: Path,
    receipt_path: Path,
    external_probe_path: Path,
    attestation_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    if worker_id not in {"A1", "A2"}:
        raise MetadataPreflightError("worker_id_invalid")
    root = Path(worker_root).resolve(strict=True)
    runtime = Path(runtime_root).resolve(strict=True)
    receipt_destination = Path(receipt_path).resolve(strict=False)
    if runtime != root / "runtime":
        raise MetadataPreflightError("worker_runtime_binding_invalid")
    if receipt_destination != root / "receipt.json":
        raise MetadataPreflightError("worker_receipt_binding_invalid")
    if receipt_destination.exists():
        raise MetadataPreflightError("worker_receipt_preexists")
    probe = Path(external_probe_path).resolve(strict=False)
    if probe == root or root in probe.parents or probe.exists():
        raise MetadataPreflightError("worker_sandbox_probe_invalid")

    manifest = _read_json_mapping(
        Path(manifest_path).resolve(strict=True),
        "worker_input_manifest",
    )
    preflight = load_preflight_module()
    bootstrap = preflight._validate_worker_bootstrap(runtime)
    sandbox_probe = preflight.prove_external_write_denied(probe)
    production_head = preflight.read_git_head_without_process(
        preflight.PRODUCTION_ROOT
    )
    if production_head != preflight.EXPECTED_PRODUCTION_HEAD:
        raise MetadataPreflightError("worker_production_head_drift")
    runtime_cache = runtime / (
        f"mplconfig/fontlist-v{preflight.EXPECTED_FONT_MANAGER_VERSION}.json"
    )
    font_cache = preflight.validate_portable_font_cache(
        runtime_cache,
        expected_version=preflight.EXPECTED_FONT_MANAGER_VERSION,
        matplotlib_data_path=preflight.matplotlib_data_path(),
    )
    if font_cache["sha256"] != preflight.EXPECTED_FONT_CACHE_SHA256:
        raise MetadataPreflightError("worker_font_cache_drift")
    attestation = preflight._load_release_attestation(Path(attestation_path))

    approved_paths = [
        str(preflight.python_site_packages()),
        str(WORKSPACE_ROOT.resolve(strict=True)),
    ]
    added_paths = [path for path in approved_paths if path not in sys.path]
    sys.path.extend(added_paths)
    try:
        validate_current_input_manifest(manifest)
        expected_outputs = validate_frozen_metadata_files(manifest)
        guarded = run_guarded_metadata_preflight(
            worker_root=root,
            expected_outputs=expected_outputs,
            expected_candidate_module_path=CANDIDATE_MODULE_PATH,
            attestation=attestation,
            preflight=preflight,
        )
        guarded = _validate_guarded_result(guarded, preflight)
    finally:
        for path in reversed(added_paths):
            if path in sys.path:
                sys.path.remove(path)

    receipt = {
        "schema_version": 1,
        "status": "passed",
        "stage": STAGE,
        "line_id": LINE_ID,
        "worker_id": worker_id,
        "pid": os.getpid(),
        "python_executable": str(Path(sys.executable).resolve(strict=True)),
        "python_version": sys.version,
        "bootstrap": bootstrap,
        "approved_sys_path": approved_paths,
        "runtime_root": str(runtime),
        "sandbox_probe": sandbox_probe,
        "font_cache": font_cache,
        "release_attestation_sha256": _file_identity(Path(attestation_path))[
            "sha256"
        ],
        "production_head": production_head,
        "formal_identity": manifest.get("formal_identity"),
        "input_file_count": manifest.get("input_file_count"),
        "input_logical_key_sha256": manifest.get("input_logical_key_sha256"),
        "file_contract_sha256": manifest.get("file_contract_sha256"),
        "runtime_contract_sha256": manifest.get("runtime_contract_sha256"),
        **guarded,
    }
    _write_json_exclusive(receipt_destination, receipt)
    return receipt


def _portable_file_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "size": identity.get("size"),
        "sha256": identity.get("sha256"),
    }


def portable_worker_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    derived = receipt.get("derived_outputs")
    if not isinstance(derived, Mapping):
        raise MetadataPreflightError("portable_derived_outputs_missing")
    portable_derived: dict[str, Any] = {}
    for key in ("universe", "post_signal_eligibility"):
        value = derived.get(key)
        if not isinstance(value, Mapping):
            raise MetadataPreflightError(f"portable_derived_output_missing:{key}")
        generated = value.get("generated")
        expected = value.get("expected")
        if not isinstance(generated, Mapping) or not isinstance(expected, Mapping):
            raise MetadataPreflightError(f"portable_derived_identity_missing:{key}")
        portable_derived[key] = {
            "bytes_equal": value.get("bytes_equal"),
            "generated": _portable_file_identity(generated),
            "expected": _portable_file_identity(expected),
        }
    return {
        "schema_version": receipt.get("schema_version"),
        "status": receipt.get("status"),
        "stage": receipt.get("stage"),
        "line_id": receipt.get("line_id"),
        "python_executable": receipt.get("python_executable"),
        "python_version": receipt.get("python_version"),
        "bootstrap": receipt.get("bootstrap"),
        "approved_sys_path": receipt.get("approved_sys_path"),
        "sandbox_write_denied": receipt.get("sandbox_probe", {}).get(
            "write_denied"
        ),
        "font_cache": receipt.get("font_cache"),
        "release_attestation_sha256": receipt.get(
            "release_attestation_sha256"
        ),
        "production_head": receipt.get("production_head"),
        "formal_identity": receipt.get("formal_identity"),
        "input_file_count": receipt.get("input_file_count"),
        "input_logical_key_sha256": receipt.get("input_logical_key_sha256"),
        "file_contract_sha256": receipt.get("file_contract_sha256"),
        "runtime_contract_sha256": receipt.get("runtime_contract_sha256"),
        "candidate_module_path": receipt.get("candidate_module_path"),
        "metadata": receipt.get("metadata"),
        "derived_outputs": portable_derived,
        "metadata_output_paths_restored": receipt.get(
            "metadata_output_paths_restored"
        ),
        "sensitive_counters": receipt.get("sensitive_counters"),
        "network_connection_attempt_count": receipt.get(
            "network_connection_attempt_count"
        ),
        "formal_replay_call_count": receipt.get("formal_replay_call_count"),
        "release_adapter_call_count": receipt.get("release_adapter_call_count"),
        "release_adapter_calls": receipt.get("release_adapter_calls"),
        "release_adapter_restored": receipt.get("release_adapter_restored"),
    }


def run_cold_worker(
    output_root: Path,
    worker_id: str,
    manifest_path: Path,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if worker_id not in {"A1", "A2"}:
        raise MetadataPreflightError("worker_id_invalid")
    output = Path(output_root).resolve(strict=False)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    output = output.resolve(strict=True)
    paths = prepare_metadata_worker_root(output / "workers" / worker_id)
    preflight = load_preflight_module()
    if (
        _file_identity(paths["font_cache"])["sha256"]
        != preflight.EXPECTED_FONT_CACHE_SHA256
    ):
        raise MetadataPreflightError("prepared_font_cache_sha_drift")
    preflight.write_sandbox_profile(paths["profile"], paths["worker_root"])
    probe = output / f".sandbox_probe_{worker_id}"
    if probe.exists():
        raise MetadataPreflightError("sandbox_probe_preexists")
    command = worker_command(paths, worker_id, manifest_path, probe)
    with paths["log"].open("wb") as log:
        completed = subprocess.run(
            command,
            cwd=paths["runtime"],
            env=preflight.expected_worker_environment(paths["runtime"]),
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
        log.flush()
        os.fsync(log.fileno())
    if completed.returncode != 0:
        failure_path = paths["receipt"].with_name("failure_receipt.json")
        detail = (
            failure_path.read_text(encoding="utf-8", errors="replace")
            if failure_path.is_file()
            else paths["log"].read_text(encoding="utf-8", errors="replace")
        )
        raise MetadataPreflightError(
            f"worker_failed:{worker_id}:returncode={completed.returncode}:"
            f"{detail[-4000:]}"
        )
    if not paths["receipt"].is_file():
        raise MetadataPreflightError(f"worker_receipt_missing:{worker_id}")
    receipt = _read_json_mapping(paths["receipt"], f"worker_{worker_id}_receipt")
    if receipt.get("status") != "passed" or receipt.get("worker_id") != worker_id:
        raise MetadataPreflightError(f"worker_receipt_status_invalid:{worker_id}")
    for field in (
        "formal_identity",
        "input_file_count",
        "input_logical_key_sha256",
        "file_contract_sha256",
        "runtime_contract_sha256",
    ):
        if receipt.get(field) != manifest.get(field):
            raise MetadataPreflightError(
                f"worker_receipt_manifest_drift:{worker_id}:{field}"
            )
    _validate_guarded_result(receipt, preflight)
    derived_paths = {
        "universe": paths["worker_root"] / "derived/static18_plus_fu.csv",
        "post_signal_eligibility": (
            paths["worker_root"] / "derived/post_signal_eligibility.csv"
        ),
    }
    recorded_outputs = receipt["derived_outputs"]
    for key, path in derived_paths.items():
        observed = _file_identity(path)
        recorded = recorded_outputs[key].get("generated")
        if not isinstance(recorded, Mapping) or any(
            recorded.get(field) != observed[field]
            for field in ("path", "size", "mtime_ns", "sha256")
        ):
            raise MetadataPreflightError(
                f"worker_derived_identity_invalid:{worker_id}:{key}"
            )
    if probe.exists():
        raise MetadataPreflightError(f"worker_sandbox_probe_created:{worker_id}")
    return {
        "worker_root": paths["worker_root"],
        "receipt_path": paths["receipt"],
        "log_path": paths["log"],
        "derived_paths": derived_paths,
        "receipt": receipt,
    }


def _remove_worker_runtimes(output: Path) -> None:
    workers = Path(output) / "workers"
    if not workers.is_dir():
        return
    for runtime in workers.glob("*/runtime"):
        if runtime.is_dir():
            shutil.rmtree(runtime)


def run_parent_metadata_preflight(output_dir: Path) -> dict[str, Any]:
    if not SANDBOX_EXECUTABLE.is_file():
        raise MetadataPreflightError("sandbox_executable_missing")
    preflight = load_preflight_module()
    if _file_identity(V2_FONT_CACHE)["sha256"] != preflight.EXPECTED_FONT_CACHE_SHA256:
        raise MetadataPreflightError("font_cache_fixture_drift")
    if (
        _file_identity(V2_RELEASE_ATTESTATION)["sha256"]
        != preflight.EXPECTED_RELEASE_ATTESTATION_SHA256
    ):
        raise MetadataPreflightError("release_attestation_fixture_drift")

    manifest = build_input_manifest()
    validate_input_manifest_payload(manifest)
    validate_frozen_metadata_files(manifest)
    output = Path(output_dir).resolve(strict=False)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    manifest_path = output / "input_manifest.json"
    _write_json_exclusive(manifest_path, manifest)
    worker_results: list[dict[str, Any]] = []
    try:
        worker_results = [
            run_cold_worker(output, worker_id, manifest_path, manifest)
            for worker_id in ("A1", "A2")
        ]
        receipts = [result["receipt"] for result in worker_results]
        portable = [portable_worker_receipt(receipt) for receipt in receipts]
        worker_pids_distinct = len({int(receipt["pid"]) for receipt in receipts}) == 2
        portable_receipts_equal = portable[0] == portable[1]
        validate_current_input_manifest(manifest)
        aggregate_counters = {
            key: sum(int(receipt["sensitive_counters"][key]) for receipt in receipts)
            for key in preflight.SENSITIVE_COUNTER_KEYS
        }
        summary = {
            "schema_version": 1,
            "status": "passed",
            "stage": STAGE,
            "line_id": LINE_ID,
            "reviewer_started": False,
            "input_file_count": manifest["input_file_count"],
            "input_logical_key_sha256": manifest["input_logical_key_sha256"],
            "file_contract_sha256": manifest["file_contract_sha256"],
            "runtime_contract_sha256": manifest["runtime_contract_sha256"],
            "formal_identity": manifest["formal_identity"],
            "worker_count": 2,
            "worker_ids": [str(receipt["worker_id"]) for receipt in receipts],
            "worker_pids_distinct": worker_pids_distinct,
            "portable_receipts_equal": portable_receipts_equal,
            "metadata": receipts[0]["metadata"],
            "derived_outputs": portable[0]["derived_outputs"],
            "metadata_output_paths_restored": all(
                receipt["metadata_output_paths_restored"] is True
                for receipt in receipts
            ),
            "sensitive_counters": aggregate_counters,
            "network_connection_attempt_count": sum(
                int(receipt["network_connection_attempt_count"])
                for receipt in receipts
            ),
            "formal_replay_call_count": sum(
                int(receipt["formal_replay_call_count"]) for receipt in receipts
            ),
            "release_adapter_call_count": sum(
                int(receipt["release_adapter_call_count"]) for receipt in receipts
            ),
            "release_adapter_restored": all(
                receipt["release_adapter_restored"] is True for receipt in receipts
            ),
            "production_head": receipts[0]["production_head"],
            "font_cache": receipts[0]["font_cache"],
            "release_attestation_sha256": receipts[0][
                "release_attestation_sha256"
            ],
        }
        if (
            not worker_pids_distinct
            or not portable_receipts_equal
            or not summary["metadata_output_paths_restored"]
            or any(aggregate_counters.values())
            or summary["network_connection_attempt_count"] != 0
            or summary["formal_replay_call_count"] != 0
            or summary["release_adapter_call_count"] != 2
            or summary["release_adapter_restored"] is not True
        ):
            raise MetadataPreflightError("parent_preflight_gate_failed")
        _remove_worker_runtimes(output)
        _write_json_exclusive(output / "summary.json", summary)
        return summary
    except BaseException as exc:
        _remove_worker_runtimes(output)
        failure_path = output / "failure.json"
        if not failure_path.exists():
            _write_json_exclusive(
                failure_path,
                {
                    "schema_version": 1,
                    "status": "failed",
                    "stage": STAGE,
                    "line_id": LINE_ID,
                    "reviewer_started": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "input_file_count": manifest["input_file_count"],
                    "input_logical_key_sha256": manifest[
                        "input_logical_key_sha256"
                    ],
                    "file_contract_sha256": manifest["file_contract_sha256"],
                    "runtime_contract_sha256": manifest[
                        "runtime_contract_sha256"
                    ],
                },
            )
        raise


def metadata_contract(metadata: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "vt_symbols",
        "rates",
        "slippages",
        "sizes",
        "priceticks",
        "margin_ratios",
        "metadata_sources",
        "source_symbol_by_contract",
        "product_symbols",
    }
    if set(metadata) != required:
        raise MetadataPreflightError("metadata_schema_invalid")
    symbols = [str(value) for value in metadata["vt_symbols"]]
    products = [str(value) for value in metadata["product_symbols"]]
    if not symbols or symbols != sorted(set(symbols)):
        raise MetadataPreflightError("metadata_vt_symbols_invalid")
    if not products or products != sorted(set(products)):
        raise MetadataPreflightError("metadata_product_symbols_invalid")
    symbol_set = set(symbols)
    for field in (
        "rates",
        "slippages",
        "sizes",
        "priceticks",
        "margin_ratios",
        "metadata_sources",
        "source_symbol_by_contract",
    ):
        values = metadata[field]
        if not isinstance(values, Mapping) or set(map(str, values)) != symbol_set:
            raise MetadataPreflightError(f"metadata_mapping_keys_invalid:{field}")
    source_counts: dict[str, int] = {}
    for value in metadata["metadata_sources"].values():
        key = str(value)
        source_counts[key] = source_counts.get(key, 0) + 1
    return {
        "metadata_sha256": hashlib.sha256(_stable_json_bytes(metadata)).hexdigest(),
        "metadata_fields": sorted(required),
        "vt_symbol_count": len(symbols),
        "product_symbol_count": len(products),
        "metadata_source_counts": dict(sorted(source_counts.items())),
    }


def _file_identity(path: Path) -> dict[str, Any]:
    source = Path(path).resolve(strict=True)
    stat_result = source.stat()
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "path": str(source),
        "size": int(stat_result.st_size),
        "mtime_ns": int(stat_result.st_mtime_ns),
        "sha256": digest.hexdigest(),
    }


def verify_derived_outputs(
    generated: Mapping[str, Path],
    expected: Mapping[str, Path],
) -> dict[str, dict[str, Any]]:
    required = {"universe", "post_signal_eligibility"}
    if set(generated) != required or set(expected) != required:
        raise MetadataPreflightError("derived_output_keys_invalid")
    result: dict[str, dict[str, Any]] = {}
    for key in sorted(required):
        generated_path = Path(generated[key])
        expected_path = Path(expected[key])
        if generated_path.is_symlink() or not generated_path.is_file():
            raise MetadataPreflightError(f"derived_output_invalid:{key}")
        if expected_path.is_symlink() or not expected_path.is_file():
            raise MetadataPreflightError(f"expected_output_invalid:{key}")
        generated_bytes = generated_path.read_bytes()
        expected_bytes = expected_path.read_bytes()
        if generated_bytes != expected_bytes:
            raise MetadataPreflightError(f"derived_output_mismatch:{key}")
        result[key] = {
            "bytes_equal": True,
            "generated": _file_identity(generated_path),
            "expected": _file_identity(expected_path),
        }
    return result


def run_guarded_metadata_preflight(
    *,
    worker_root: Path,
    expected_outputs: Mapping[str, Path],
    expected_candidate_module_path: Path,
    attestation: Mapping[str, Any],
    preflight: Any,
    context_importer: Any | None = None,
) -> dict[str, Any]:
    root = Path(worker_root).resolve(strict=True)
    importer = context_importer or preflight.import_production_context_with_attestation
    network = preflight.NetworkBlock()
    guard = preflight.SensitiveOperationGuard((root,))
    guard.assert_no_sensitive_modules_loaded()
    with network, guard:
        context, adapter_calls, adapter_restored = importer(attestation)
        candidate_module = sys.modules.get(CANDIDATE_MODULE_NAME)
        if candidate_module is None:
            raise MetadataPreflightError("candidate_module_missing")
        module_file = Path(str(getattr(candidate_module, "__file__", ""))).resolve(
            strict=True
        )
        if module_file != Path(expected_candidate_module_path).resolve(strict=True):
            raise MetadataPreflightError("candidate_module_identity_mismatch")
        original_universe = candidate_module.UNIVERSE_PATH
        original_eligibility = (
            candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
        )
        with redirect_metadata_outputs(candidate_module, root) as targets:
            metadata = context["s901"].s513._metadata()
        paths_restored = bool(
            candidate_module.UNIVERSE_PATH is original_universe
            and candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
            is original_eligibility
        )
        if not paths_restored:
            raise MetadataPreflightError("metadata_output_paths_not_restored")
        derived_outputs = verify_derived_outputs(targets, expected_outputs)
        contract = metadata_contract(metadata)

    counters = dict(guard.counters)
    if network.attempts != 0:
        raise MetadataPreflightError("network_attempt_detected")
    if any(counters.values()):
        raise MetadataPreflightError("sensitive_operation_detected")
    if guard.formal_replay_call_count != 0:
        raise MetadataPreflightError("formal_replay_detected")
    if len(adapter_calls) != 1 or adapter_restored is not True:
        raise MetadataPreflightError("release_adapter_contract_failed")
    return {
        "candidate_module_path": str(module_file),
        "metadata": contract,
        "derived_outputs": derived_outputs,
        "metadata_output_paths_restored": paths_restored,
        "sensitive_counters": counters,
        "network_connection_attempt_count": int(network.attempts),
        "formal_replay_call_count": int(guard.formal_replay_call_count),
        "release_adapter_call_count": len(adapter_calls),
        "release_adapter_calls": list(adapter_calls),
        "release_adapter_restored": bool(adapter_restored),
    }


@contextmanager
def redirect_metadata_outputs(
    candidate_module: Any,
    worker_root: Path,
) -> Iterator[dict[str, Path]]:
    root = Path(worker_root).resolve(strict=True)
    derived = root / "derived"
    derived.mkdir(mode=0o700)
    os.chmod(derived, 0o700)
    targets = {
        "universe": derived / "static18_plus_fu.csv",
        "post_signal_eligibility": derived / "post_signal_eligibility.csv",
    }
    original_universe = candidate_module.UNIVERSE_PATH
    original_eligibility = (
        candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
    )
    candidate_module.UNIVERSE_PATH = targets["universe"]
    candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH = targets[
        "post_signal_eligibility"
    ]
    try:
        yield targets
    finally:
        candidate_module.UNIVERSE_PATH = original_universe
        candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH = (
            original_eligibility
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--worker", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--worker-id")
    parser.add_argument("--worker-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--receipt-path", type=Path)
    parser.add_argument("--external-probe-path", type=Path)
    parser.add_argument("--attestation-path", type=Path)
    parser.add_argument("--manifest-path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.run:
            if args.output_dir is None:
                raise MetadataPreflightError("output_dir_required")
            summary = run_parent_metadata_preflight(args.output_dir)
            print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
            return 0
        required = {
            "worker_id": args.worker_id,
            "worker_root": args.worker_root,
            "runtime_root": args.runtime_root,
            "receipt_path": args.receipt_path,
            "external_probe_path": args.external_probe_path,
            "attestation_path": args.attestation_path,
            "manifest_path": args.manifest_path,
        }
        if any(value is None for value in required.values()):
            raise MetadataPreflightError("worker_arguments_incomplete")
        run_metadata_worker(
            worker_id=str(args.worker_id),
            worker_root=args.worker_root,
            runtime_root=args.runtime_root,
            receipt_path=args.receipt_path,
            external_probe_path=args.external_probe_path,
            attestation_path=args.attestation_path,
            manifest_path=args.manifest_path,
        )
        return 0
    except BaseException as exc:
        if args.worker and args.receipt_path is not None:
            failure_path = Path(args.receipt_path).with_name("failure_receipt.json")
            try:
                _write_json_exclusive(
                    failure_path,
                    {
                        "schema_version": 1,
                        "status": "failed",
                        "stage": STAGE,
                        "line_id": LINE_ID,
                        "worker_id": args.worker_id,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                )
            except BaseException:
                pass
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
