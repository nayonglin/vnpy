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
from collections.abc import Mapping
from pathlib import Path
from typing import Any


LINE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
METADATA_PREFLIGHT_TOOL = LINE_ROOT / "tools/stage001_metadata_side_effect_preflight.py"
V2_LINE_ROOT = (
    WORKSPACE_ROOT
    / "research/lines/futures_trend_xgboost_formal_signal_marginal_utility_v2"
)
V2_RUNNER = V2_LINE_ROOT / "tools/stage002_event_feature_qualification.py"
FEATURE_TOOL = V2_LINE_ROOT / "tools/formal_signal_event_features.py"
RELEASE_ATTESTATION = V2_LINE_ROOT / "materials/release_manifest_commit_attestation.json"
SANDBOX_EXECUTABLE = Path("/usr/bin/sandbox-exec")
STAGE002_TESTS = LINE_ROOT / "tests/test_stage002_event_feature_qualification.py"
STAGE002_PREREGISTRATION = (
    LINE_ROOT
    / "stages/20260905_1820_stage002_event_feature_qualification_preregistration.md"
)
STAGE001_RECORD = (
    LINE_ROOT
    / "stages/20260905_1817_stage001_metadata_side_effect_preflight_pass.md"
)
STAGE001_ARTIFACT = LINE_ROOT / "artifacts/stage001_metadata_side_effect_preflight"
EXPECTED_INPUT_FILE_COUNT = 1433
STAGE = "stage002_event_feature_qualification"
LINE_ID = "futures_trend_xgboost_formal_signal_marginal_utility_v3"
CANDIDATE_MODULE_NAME = (
    "run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest"
)
CANDIDATE_MODULE_PATH = (
    Path("/Users/bytedance/Desktop/person/vnpy_production_live")
    / "examples/portfolio_backtesting"
    / f"{CANDIDATE_MODULE_NAME}.py"
)
EXECUTION_STATE_DIR = LINE_ROOT / "stages/20260905_stage002_execution_state"
CLAIM_PATH = EXECUTION_STATE_DIR / "claim.json"
INPUT_FREEZE_PATH = LINE_ROOT / "stages/20260905_stage002a_input_contract_freeze.json"
ARTIFACT_ROOT = LINE_ROOT / "artifacts"
FINAL_DIR = ARTIFACT_ROOT / STAGE
FAILURE_DIR = ARTIFACT_ROOT / f"{STAGE}_failed"


class Stage002Error(RuntimeError):
    pass


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, Path(path).resolve(strict=True))
    if spec is None or spec.loader is None:
        raise Stage002Error(f"module_spec_failed:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_metadata_preflight_module() -> Any:
    return _load_module("v3_stage002_metadata_preflight_support", METADATA_PREFLIGHT_TOOL)


def load_v2_runner() -> Any:
    return _load_module("v3_stage002_v2_runner_support", V2_RUNNER)


def load_v1_runner() -> Any:
    return load_metadata_preflight_module().load_v1_runner()


def load_feature_module() -> Any:
    return load_v2_runner().load_feature_module()


def stage002_thresholds(feature_module: Any) -> Any:
    return load_v2_runner().stage002_thresholds(feature_module)


def evaluate_stage002_features(left: Any, right: Any) -> dict[str, Any]:
    v2 = load_v2_runner()
    try:
        return dict(v2.evaluate_stage002_features(left, right))
    except Exception as exc:
        raise Stage002Error(f"worker_reproducibility_failed:{exc}") from exc


def prepare_stage002_worker_root(
    worker_root: Path,
    *,
    source_database: Path,
    expected_database_sha256: str,
) -> dict[str, Path]:
    return dict(
        load_v2_runner().prepare_stage002_worker_root(
            Path(worker_root),
            source_database=Path(source_database),
            expected_database_sha256=expected_database_sha256,
        )
    )


def worker_command(
    paths: Mapping[str, Path],
    worker_id: str,
    manifest_path: Path,
    external_probe_path: Path,
) -> list[str]:
    if worker_id not in {"A1", "A2"}:
        raise Stage002Error("worker_id_invalid")
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
        "--feature-path",
        str(paths["feature"]),
        "--external-probe-path",
        str(external_probe_path),
        "--attestation-path",
        str(RELEASE_ATTESTATION.resolve(strict=True)),
        "--manifest-path",
        str(manifest_path),
    ]


def collect_input_files() -> dict[str, Path]:
    files = dict(load_metadata_preflight_module().collect_input_files())
    files.update(
        {
            "stage002_runner": Path(__file__).resolve(),
            "stage002_tests": STAGE002_TESTS,
            "stage002_preregistration": STAGE002_PREREGISTRATION,
            "stage002_feature_tool": FEATURE_TOOL,
            "v3_stage001_record": STAGE001_RECORD,
            "v3_stage001_summary": STAGE001_ARTIFACT / "summary.json",
            "v3_stage001_input_manifest": STAGE001_ARTIFACT / "input_manifest.json",
            "v3_stage001_a1_receipt": STAGE001_ARTIFACT / "workers/A1/receipt.json",
            "v3_stage001_a2_receipt": STAGE001_ARTIFACT / "workers/A2/receipt.json",
            "v3_stage001_a1_universe": (
                STAGE001_ARTIFACT / "workers/A1/derived/static18_plus_fu.csv"
            ),
            "v3_stage001_a2_universe": (
                STAGE001_ARTIFACT / "workers/A2/derived/static18_plus_fu.csv"
            ),
            "v3_stage001_a1_post_signal_eligibility": (
                STAGE001_ARTIFACT
                / "workers/A1/derived/post_signal_eligibility.csv"
            ),
            "v3_stage001_a2_post_signal_eligibility": (
                STAGE001_ARTIFACT
                / "workers/A2/derived/post_signal_eligibility.csv"
            ),
        }
    )
    if len(files) != EXPECTED_INPUT_FILE_COUNT:
        raise Stage002Error(
            f"input_inventory_count_mismatch:{len(files)}:{EXPECTED_INPUT_FILE_COUNT}"
        )
    for key, path in files.items():
        if path.is_symlink() or not path.is_file():
            raise Stage002Error(f"input_file_invalid:{key}:{path}")
    return dict(sorted(files.items()))


def _stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


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


def _require_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise Stage002Error(f"invalid_sha256:{field}")
    return value


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
        raise Stage002Error("input_manifest_schema_invalid")
    if recorded.get("schema_version") != 1:
        raise Stage002Error("input_manifest_version_invalid")
    if recorded.get("stage") != STAGE or recorded.get("line_id") != LINE_ID:
        raise Stage002Error("input_manifest_identity_invalid")
    files = recorded.get("files")
    if not isinstance(files, Mapping):
        raise Stage002Error("input_manifest_files_invalid")
    file_count = recorded.get("input_file_count")
    if (
        isinstance(file_count, bool)
        or not isinstance(file_count, int)
        or file_count != EXPECTED_INPUT_FILE_COUNT
        or len(files) != file_count
    ):
        raise Stage002Error("input_manifest_file_count_invalid")
    normalized_files: dict[str, dict[str, Any]] = {}
    for key, identity in files.items():
        if not isinstance(key, str) or not isinstance(identity, Mapping):
            raise Stage002Error("input_manifest_file_identity_invalid")
        if set(identity) != {"path", "size", "mtime_ns", "sha256"}:
            raise Stage002Error(f"input_manifest_file_identity_invalid:{key}")
        if not isinstance(identity.get("path"), str):
            raise Stage002Error(f"input_manifest_file_path_invalid:{key}")
        for field in ("size", "mtime_ns"):
            value = identity.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise Stage002Error(f"input_manifest_file_{field}_invalid:{key}")
        _require_sha256(identity.get("sha256"), f"files.{key}.sha256")
        normalized_files[key] = dict(identity)
    logical_paths = {
        key: Path(identity["path"]) for key, identity in normalized_files.items()
    }
    if _require_sha256(
        recorded.get("input_logical_key_sha256"),
        "input_logical_key_sha256",
    ) != _logical_key_sha256(logical_paths):
        raise Stage002Error("input_manifest_logical_key_sha_mismatch")
    if _require_sha256(
        recorded.get("file_contract_sha256"),
        "file_contract_sha256",
    ) != _file_contract_sha256(normalized_files):
        raise Stage002Error("input_manifest_file_contract_sha_mismatch")
    runtime = recorded.get("runtime")
    if not isinstance(runtime, Mapping):
        raise Stage002Error("input_manifest_runtime_invalid")
    if _require_sha256(
        recorded.get("runtime_contract_sha256"),
        "runtime_contract_sha256",
    ) != hashlib.sha256(_stable_json_bytes(runtime)).hexdigest():
        raise Stage002Error("input_manifest_runtime_sha_mismatch")
    if not isinstance(recorded.get("formal_identity"), Mapping):
        raise Stage002Error("input_manifest_formal_identity_invalid")
    return dict(recorded)


def validate_current_input_manifest(recorded: Mapping[str, Any]) -> dict[str, Any]:
    expected = validate_input_manifest_payload(recorded)
    observed = build_input_manifest()
    validate_input_manifest_payload(observed)
    if observed != expected:
        raise Stage002Error("current_input_manifest_drift")
    return observed


def validate_frozen_input_contract(
    freeze_path: Path,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        payload = json.loads(
            Path(freeze_path).resolve(strict=True).read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Stage002Error("frozen_input_contract_read_failed") from exc
    if not isinstance(payload, Mapping):
        raise Stage002Error("frozen_input_contract_invalid")
    required = {
        "schema_version",
        "stage",
        "line_id",
        "execution_authorized",
        "input_file_count",
        "input_logical_key_sha256",
        "file_contract_sha256",
        "runtime_contract_sha256",
    }
    if set(payload) != required:
        raise Stage002Error("frozen_input_contract_schema_invalid")
    if (
        payload.get("schema_version") != 1
        or payload.get("stage") != STAGE
        or payload.get("line_id") != LINE_ID
        or payload.get("execution_authorized") is not True
    ):
        raise Stage002Error("frozen_input_contract_identity_invalid")
    expected = {
        field: manifest.get(field)
        for field in (
            "input_file_count",
            "input_logical_key_sha256",
            "file_contract_sha256",
            "runtime_contract_sha256",
        )
    }
    observed = {field: payload.get(field) for field in expected}
    for field in (
        "input_logical_key_sha256",
        "file_contract_sha256",
        "runtime_contract_sha256",
    ):
        _require_sha256(observed[field], field)
    if observed != expected:
        raise Stage002Error("frozen_input_contract_mismatch")
    return dict(payload)


def claim_execution(claim_path: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    input_file_count = manifest.get("input_file_count")
    if (
        isinstance(input_file_count, bool)
        or not isinstance(input_file_count, int)
        or input_file_count <= 0
    ):
        raise Stage002Error("invalid_input_file_count")
    payload = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "replay_permitted": False,
        "campaign_nonce": os.urandom(32).hex(),
        "input_file_count": input_file_count,
        "input_logical_key_sha256": _require_sha256(
            manifest.get("input_logical_key_sha256"),
            "input_logical_key_sha256",
        ),
        "file_contract_sha256": _require_sha256(
            manifest.get("file_contract_sha256"),
            "file_contract_sha256",
        ),
        "runtime_contract_sha256": _require_sha256(
            manifest.get("runtime_contract_sha256"),
            "runtime_contract_sha256",
        ),
    }
    destination = Path(claim_path).resolve(strict=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = _stable_json_bytes(payload) + b"\n"
    try:
        descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError as exc:
        raise Stage002Error("execution_claim_exists") from exc
    try:
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    parent_descriptor = os.open(destination.parent, os.O_RDONLY)
    try:
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)
    return payload


def extract_formal_event_features(
    context: Mapping[str, Any],
    *,
    worker_root: Path,
    expected_outputs: Mapping[str, Path],
    expected_candidate_module_path: Path,
    v1: Any,
    feature_module: Any,
    metadata_preflight: Any,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    candidate_module = sys.modules.get(CANDIDATE_MODULE_NAME)
    if candidate_module is None:
        raise Stage002Error("candidate_module_missing")
    module_file = Path(str(getattr(candidate_module, "__file__", ""))).resolve(
        strict=True
    )
    if module_file != Path(expected_candidate_module_path).resolve(strict=True):
        raise Stage002Error("candidate_module_identity_mismatch")
    original_universe = candidate_module.UNIVERSE_PATH
    original_eligibility = (
        candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
    )
    with metadata_preflight.redirect_metadata_outputs(
        candidate_module,
        Path(worker_root),
    ) as targets:
        metadata = context["s901"].s513._metadata()
    paths_restored = bool(
        candidate_module.UNIVERSE_PATH is original_universe
        and candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
        is original_eligibility
    )
    if not paths_restored:
        raise Stage002Error("metadata_output_paths_not_restored")
    derived_outputs = metadata_preflight.verify_derived_outputs(
        targets,
        expected_outputs,
    )
    metadata_summary = metadata_preflight.metadata_contract(metadata)

    formal = dict(v1._active_formal_identity())
    strategy_class = context["s901"].s847.QmtRollPortfolioStrategyStage847C9StopRetry
    restore_trace = v1._install_correlation_trace_instrumentation(strategy_class)
    try:
        combined, frames, live_spec = context["s901"]._run_live_c9(
            metadata,
            v1.START,
            v1.END,
        )
    finally:
        restore_trace()
    if float(live_spec.capital.account_capital) != float(v1.EXPECTED_CAPITAL):
        raise Stage002Error("worker_capital_drift")
    if str(live_spec.profile) != str(
        context["live_config"].OFFICIAL_LIVE_PROFILE_NAME
    ):
        raise Stage002Error("worker_profile_drift")
    candidate_frame = frames.get("entry_candidates")
    if candidate_frame is None:
        candidate_frame = v1.pd.DataFrame()
    candidates = candidate_frame.copy()
    del combined, frames, live_spec
    if bool(getattr(candidates, "empty", False)):
        raise Stage002Error("worker_entry_candidates_empty")
    eligibility = v1.pd.read_csv(formal["eligibility_path"])
    features = feature_module.build_formal_root_event_features(
        candidates,
        eligibility,
        formal,
    )
    del candidates, eligibility, metadata
    metadata_evidence = {
        "candidate_module_path": str(module_file),
        "metadata": metadata_summary,
        "derived_outputs": derived_outputs,
        "metadata_output_paths_restored": paths_restored,
    }
    return features, formal, metadata_evidence


def run_guarded_extraction(
    *,
    worker_root: Path,
    expected_outputs: Mapping[str, Path],
    expected_candidate_module_path: Path,
    attestation: Mapping[str, Any],
    preflight: Any,
    metadata_preflight: Any,
    v1: Any,
    feature_module: Any,
    context_importer: Any | None = None,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    root = Path(worker_root).resolve(strict=True)
    importer = context_importer or preflight.import_production_context_with_attestation
    network = preflight.NetworkBlock()
    guard = preflight.SensitiveOperationGuard(
        (root,),
        allowed_formal_replay_count=1,
    )
    guard.assert_no_sensitive_modules_loaded()
    with network, guard:
        context, adapter_calls, adapter_restored = importer(attestation)
        features, formal, metadata_evidence = extract_formal_event_features(
            context,
            worker_root=root,
            expected_outputs=expected_outputs,
            expected_candidate_module_path=expected_candidate_module_path,
            v1=v1,
            feature_module=feature_module,
            metadata_preflight=metadata_preflight,
        )

    counters = dict(guard.counters)
    if network.attempts != 0:
        raise Stage002Error("worker_network_attempt_detected")
    if any(counters.values()):
        raise Stage002Error("worker_sensitive_operation_attempt_detected")
    if guard.formal_replay_call_count != 1:
        raise Stage002Error(
            f"worker_formal_replay_count_invalid:{guard.formal_replay_call_count}"
        )
    if len(adapter_calls) != 1 or adapter_restored is not True:
        raise Stage002Error("worker_release_adapter_contract_failed")
    safety = {
        "sensitive_counters": counters,
        "network_connection_attempt_count": int(network.attempts),
        "formal_replay_call_count": int(guard.formal_replay_call_count),
        "release_adapter_call_count": len(adapter_calls),
        "release_adapter_calls": list(adapter_calls),
        "release_adapter_restored": bool(adapter_restored),
        "metadata_preflight": metadata_evidence,
    }
    return features, formal, safety


def _read_json_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Stage002Error(f"{label}_read_failed") from exc
    if not isinstance(payload, Mapping):
        raise Stage002Error(f"{label}_invalid")
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
                raise Stage002Error("exclusive_write_failed")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(destination.parent)


def _write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    _write_bytes_exclusive(Path(path), _stable_json_bytes(payload) + b"\n")


def _analysis_date(value: Any) -> str:
    date_method = getattr(value, "date", None)
    if callable(date_method):
        return date_method().isoformat()
    return str(value)


def run_worker_qualification(
    *,
    worker_id: str,
    worker_root: Path,
    runtime_root: Path,
    receipt_path: Path,
    feature_path: Path,
    external_probe_path: Path,
    attestation_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    if worker_id not in {"A1", "A2"}:
        raise Stage002Error("worker_id_invalid")
    root = Path(worker_root).resolve(strict=True)
    runtime = Path(runtime_root).resolve(strict=True)
    receipt_destination = Path(receipt_path).resolve(strict=False)
    feature_destination = Path(feature_path).resolve(strict=False)
    if runtime != root / "runtime":
        raise Stage002Error("worker_runtime_binding_invalid")
    if receipt_destination != root / "receipt.json":
        raise Stage002Error("worker_receipt_binding_invalid")
    if feature_destination != root / "event_features.csv":
        raise Stage002Error("worker_feature_binding_invalid")
    if receipt_destination.exists() or feature_destination.exists():
        raise Stage002Error("worker_output_preexists")
    probe = Path(external_probe_path).resolve(strict=False)
    if probe == root or root in probe.parents or probe.exists():
        raise Stage002Error("worker_sandbox_probe_invalid")

    manifest = _read_json_mapping(
        Path(manifest_path).resolve(strict=True),
        "worker_input_manifest",
    )
    source_database = manifest.get("files", {}).get("source_database", {})
    if not isinstance(source_database, Mapping):
        raise Stage002Error("worker_source_database_missing")
    expected_database_sha = _require_sha256(
        source_database.get("sha256"),
        "source_database.sha256",
    )
    database = runtime / ".vntrader/database.db"
    if _file_identity(database)["sha256"] != expected_database_sha:
        raise Stage002Error("worker_database_identity_drift")

    metadata_preflight = load_metadata_preflight_module()
    preflight = metadata_preflight.load_preflight_module()
    bootstrap = preflight._validate_worker_bootstrap(runtime)
    sandbox_probe = preflight.prove_external_write_denied(probe)
    production_head = preflight.read_git_head_without_process(
        preflight.PRODUCTION_ROOT
    )
    if production_head != preflight.EXPECTED_PRODUCTION_HEAD:
        raise Stage002Error("worker_production_head_drift")
    runtime_cache = runtime / (
        f"mplconfig/fontlist-v{preflight.EXPECTED_FONT_MANAGER_VERSION}.json"
    )
    font_cache = preflight.validate_portable_font_cache(
        runtime_cache,
        expected_version=preflight.EXPECTED_FONT_MANAGER_VERSION,
        matplotlib_data_path=preflight.matplotlib_data_path(),
    )
    if font_cache["sha256"] != preflight.EXPECTED_FONT_CACHE_SHA256:
        raise Stage002Error("worker_font_cache_drift")
    attestation = preflight._load_release_attestation(Path(attestation_path))

    approved_paths = [
        str(preflight.python_site_packages()),
        str(WORKSPACE_ROOT.resolve(strict=True)),
    ]
    added_paths = [path for path in approved_paths if path not in sys.path]
    sys.path.extend(added_paths)
    try:
        validate_current_input_manifest(manifest)
        expected_outputs = metadata_preflight.validate_frozen_metadata_files(manifest)
        v1 = load_v1_runner()
        feature_module = load_feature_module()
        features, formal, safety = run_guarded_extraction(
            worker_root=root,
            expected_outputs=expected_outputs,
            expected_candidate_module_path=CANDIDATE_MODULE_PATH,
            attestation=attestation,
            preflight=preflight,
            metadata_preflight=metadata_preflight,
            v1=v1,
            feature_module=feature_module,
        )
    finally:
        for path in reversed(added_paths):
            if path in sys.path:
                sys.path.remove(path)

    if formal != manifest.get("formal_identity"):
        raise Stage002Error("worker_formal_identity_drift")
    csv_payload = features.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    ).encode("utf-8")
    _write_bytes_exclusive(feature_destination, csv_payload)
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
        "database": _file_identity(database),
        "sandbox_probe": sandbox_probe,
        "font_cache": font_cache,
        "release_attestation_sha256": _file_identity(Path(attestation_path))[
            "sha256"
        ],
        "production_head": production_head,
        "formal_identity": formal,
        "analysis_start": _analysis_date(v1.START),
        "analysis_end": _analysis_date(v1.END),
        "input_file_count": manifest.get("input_file_count"),
        "input_logical_key_sha256": manifest.get("input_logical_key_sha256"),
        "file_contract_sha256": manifest.get("file_contract_sha256"),
        "runtime_contract_sha256": manifest.get("runtime_contract_sha256"),
        "event_count": int(len(features)),
        "event_feature_columns": [str(column) for column in features.columns],
        "event_feature_file": _file_identity(feature_destination),
        **safety,
    }
    _write_json_exclusive(receipt_destination, receipt)
    return receipt


def _portable_file_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "size": identity.get("size"),
        "sha256": identity.get("sha256"),
    }


def portable_metadata_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    derived = evidence.get("derived_outputs")
    if not isinstance(derived, Mapping):
        raise Stage002Error("metadata_derived_outputs_missing")
    portable_derived: dict[str, Any] = {}
    for key in ("universe", "post_signal_eligibility"):
        value = derived.get(key)
        if not isinstance(value, Mapping):
            raise Stage002Error(f"metadata_derived_output_missing:{key}")
        generated = value.get("generated")
        expected = value.get("expected")
        if not isinstance(generated, Mapping) or not isinstance(expected, Mapping):
            raise Stage002Error(f"metadata_derived_identity_missing:{key}")
        portable_derived[key] = {
            "bytes_equal": value.get("bytes_equal"),
            "generated": _portable_file_identity(generated),
            "expected": _portable_file_identity(expected),
        }
    metadata = evidence.get("metadata")
    if not isinstance(metadata, Mapping):
        raise Stage002Error("metadata_contract_missing")
    _require_sha256(metadata.get("metadata_sha256"), "metadata.metadata_sha256")
    return {
        "candidate_module_path": evidence.get("candidate_module_path"),
        "metadata": dict(metadata),
        "derived_outputs": portable_derived,
        "metadata_output_paths_restored": evidence.get(
            "metadata_output_paths_restored"
        ),
    }


def _validate_worker_metadata_evidence(
    evidence: Mapping[str, Any],
    worker_root: Path,
) -> dict[str, Any]:
    portable = portable_metadata_evidence(evidence)
    if (
        Path(str(portable["candidate_module_path"])).resolve(strict=True)
        != CANDIDATE_MODULE_PATH.resolve(strict=True)
        or portable["metadata_output_paths_restored"] is not True
    ):
        raise Stage002Error("worker_metadata_identity_invalid")
    derived_paths = {
        "universe": Path(worker_root) / "derived/static18_plus_fu.csv",
        "post_signal_eligibility": (
            Path(worker_root) / "derived/post_signal_eligibility.csv"
        ),
    }
    for key, path in derived_paths.items():
        observed = _file_identity(path)
        recorded = evidence["derived_outputs"][key].get("generated")
        if not isinstance(recorded, Mapping) or any(
            recorded.get(field) != observed[field]
            for field in ("path", "size", "mtime_ns", "sha256")
        ):
            raise Stage002Error(f"worker_metadata_derived_identity_invalid:{key}")
        if evidence["derived_outputs"][key].get("bytes_equal") is not True:
            raise Stage002Error(f"worker_metadata_derived_mismatch:{key}")
    return portable


def run_cold_worker(
    attempt_root: Path,
    worker_id: str,
    manifest_path: Path,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if worker_id not in {"A1", "A2"}:
        raise Stage002Error("worker_id_invalid")
    attempt = Path(attempt_root).resolve(strict=True)
    source_identity = manifest.get("files", {}).get("source_database", {})
    if not isinstance(source_identity, Mapping):
        raise Stage002Error("source_database_identity_missing")
    source_database = Path(str(source_identity.get("path", ""))).resolve(strict=True)
    paths = prepare_stage002_worker_root(
        attempt / "workers" / worker_id,
        source_database=source_database,
        expected_database_sha256=str(source_identity.get("sha256", "")),
    )
    paths["feature"] = paths["worker_root"] / "event_features.csv"
    preflight = load_metadata_preflight_module().load_preflight_module()
    preflight.write_sandbox_profile(paths["profile"], paths["worker_root"])
    probe = attempt / f".sandbox_probe_{worker_id}"
    if probe.exists():
        raise Stage002Error("sandbox_probe_preexists")
    command = worker_command(paths, worker_id, Path(manifest_path), probe)
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
        raise Stage002Error(
            f"worker_failed:{worker_id}:returncode={completed.returncode}:"
            f"{detail[-4000:]}"
        )
    if not paths["receipt"].is_file() or not paths["feature"].is_file():
        raise Stage002Error(f"worker_output_missing:{worker_id}")
    receipt = _read_json_mapping(paths["receipt"], f"worker_{worker_id}_receipt")
    if receipt.get("status") != "passed" or receipt.get("worker_id") != worker_id:
        raise Stage002Error(f"worker_receipt_status_invalid:{worker_id}")
    for field in (
        "input_file_count",
        "input_logical_key_sha256",
        "file_contract_sha256",
        "runtime_contract_sha256",
        "formal_identity",
    ):
        if receipt.get(field) != manifest.get(field):
            raise Stage002Error(f"worker_receipt_manifest_drift:{worker_id}:{field}")
    counters = receipt.get("sensitive_counters")
    if not isinstance(counters, Mapping) or set(counters) != set(
        preflight.SENSITIVE_COUNTER_KEYS
    ):
        raise Stage002Error(f"worker_sensitive_counter_schema_invalid:{worker_id}")
    if any(value != 0 for value in counters.values()):
        raise Stage002Error(f"worker_sensitive_counter_nonzero:{worker_id}")
    if (
        receipt.get("network_connection_attempt_count") != 0
        or receipt.get("formal_replay_call_count") != 1
        or receipt.get("release_adapter_call_count") != 1
        or receipt.get("release_adapter_restored") is not True
    ):
        raise Stage002Error(f"worker_safety_receipt_invalid:{worker_id}")
    observed_feature = _file_identity(paths["feature"])
    recorded_feature = receipt.get("event_feature_file")
    if not isinstance(recorded_feature, Mapping) or any(
        recorded_feature.get(field) != observed_feature[field]
        for field in ("path", "size", "mtime_ns", "sha256")
    ):
        raise Stage002Error(f"worker_feature_identity_invalid:{worker_id}")
    metadata_evidence = receipt.get("metadata_preflight")
    if not isinstance(metadata_evidence, Mapping):
        raise Stage002Error(f"worker_metadata_evidence_missing:{worker_id}")
    _validate_worker_metadata_evidence(metadata_evidence, paths["worker_root"])
    if probe.exists():
        raise Stage002Error(f"worker_sandbox_probe_created:{worker_id}")
    return {
        "worker_root": paths["worker_root"],
        "feature_path": paths["feature"],
        "receipt_path": paths["receipt"],
        "log_path": paths["log"],
        "receipt": receipt,
    }


def _remove_attempt_runtime_copies(attempt: Path) -> None:
    workers = Path(attempt) / "workers"
    if not workers.is_dir():
        return
    for runtime in workers.glob("*/runtime"):
        if runtime.is_dir():
            shutil.rmtree(runtime)


def run_parent_qualification(
    *,
    final_dir: Path,
    failure_dir: Path,
    claim_path: Path,
    freeze_path: Path,
) -> dict[str, Any]:
    if not SANDBOX_EXECUTABLE.is_file():
        raise Stage002Error("sandbox_executable_missing")
    final = Path(final_dir).resolve(strict=False)
    failure = Path(failure_dir).resolve(strict=False)
    if final.exists():
        raise Stage002Error("stage002_final_artifact_exists")
    if failure.exists():
        raise Stage002Error("stage002_failure_artifact_exists")
    manifest = build_input_manifest()
    validate_input_manifest_payload(manifest)
    freeze = validate_frozen_input_contract(freeze_path, manifest)
    claim = claim_execution(claim_path, manifest)
    attempt = final.with_name(
        f".{final.name}.attempt-{claim['campaign_nonce'][:12]}"
    )
    if attempt.exists():
        raise Stage002Error("stage002_attempt_exists")
    worker_results: list[dict[str, Any]] = []
    try:
        attempt.mkdir(parents=True, mode=0o700)
        manifest_path = attempt / "input_manifest.json"
        _write_json_exclusive(manifest_path, manifest)
        _write_json_exclusive(attempt / "input_contract_freeze.json", freeze)
        worker_results = [
            run_cold_worker(attempt, worker_id, manifest_path, manifest)
            for worker_id in ("A1", "A2")
        ]
        receipts = [result["receipt"] for result in worker_results]
        if len({int(receipt["pid"]) for receipt in receipts}) != 2:
            raise Stage002Error("worker_pids_not_distinct")
        v1 = load_v1_runner()
        feature_frames = [
            v1.pd.read_csv(result["feature_path"]) for result in worker_results
        ]
        for frame, receipt in zip(feature_frames, receipts, strict=True):
            if len(frame) != int(receipt["event_count"]):
                raise Stage002Error("worker_event_count_receipt_mismatch")
        evaluation = evaluate_stage002_features(*feature_frames)
        if evaluation.get("passed") is not True:
            raise Stage002Error("stage002_qualification_failed")
        validate_current_input_manifest(manifest)

        preflight = load_metadata_preflight_module().load_preflight_module()
        aggregate_counters = {
            key: sum(int(receipt["sensitive_counters"][key]) for receipt in receipts)
            for key in preflight.SENSITIVE_COUNTER_KEYS
        }
        if any(aggregate_counters.values()):
            raise Stage002Error("parent_sensitive_counter_nonzero")
        metadata_receipts = [
            portable_metadata_evidence(receipt["metadata_preflight"])
            for receipt in receipts
        ]
        metadata_equal = metadata_receipts[0] == metadata_receipts[1]
        if not metadata_equal:
            raise Stage002Error("worker_metadata_preflight_mismatch")
        top_level_features = attempt / "event_features.csv"
        _write_bytes_exclusive(
            top_level_features,
            Path(worker_results[0]["feature_path"]).read_bytes(),
        )
        thresholds = stage002_thresholds(load_feature_module())
        summary = {
            "schema_version": 1,
            "status": "passed",
            "stage": STAGE,
            "line_id": LINE_ID,
            "campaign_nonce": claim["campaign_nonce"],
            "reviewer_started": False,
            "input_contract_frozen": True,
            "input_file_count": manifest["input_file_count"],
            "input_logical_key_sha256": manifest["input_logical_key_sha256"],
            "file_contract_sha256": manifest["file_contract_sha256"],
            "runtime_contract_sha256": manifest["runtime_contract_sha256"],
            "formal_identity": manifest["formal_identity"],
            "worker_count": 2,
            "worker_ids": [str(receipt["worker_id"]) for receipt in receipts],
            "worker_pids_distinct": True,
            "formal_replay_call_count": sum(
                int(receipt["formal_replay_call_count"]) for receipt in receipts
            ),
            "network_connection_attempt_count": sum(
                int(receipt["network_connection_attempt_count"])
                for receipt in receipts
            ),
            "sensitive_counters": aggregate_counters,
            "metadata_preflight": {
                "portable_receipts_equal": metadata_equal,
                **metadata_receipts[0],
            },
            "event_count": int(len(feature_frames[0])),
            "event_feature_columns": [
                str(column) for column in feature_frames[0].columns
            ],
            "event_feature_file": {
                key: value
                for key, value in _file_identity(top_level_features).items()
                if key in {"size", "sha256"}
            },
            "thresholds": {
                "min_events": thresholds.min_events,
                "min_events_per_full_year": thresholds.min_events_per_full_year,
                "min_events_per_direction": thresholds.min_events_per_direction,
                "min_products": thresholds.min_products,
                "min_unique_per_feature": thresholds.min_unique_per_feature,
                "min_high_cardinality_features": (
                    thresholds.min_high_cardinality_features
                ),
                "high_cardinality_unique_values": (
                    thresholds.high_cardinality_unique_values
                ),
                "full_years": list(thresholds.full_years),
                "worker_numeric_atol": 1e-12,
            },
            **evaluation,
        }
        if (
            summary["formal_replay_call_count"] != 2
            or summary["network_connection_attempt_count"] != 0
        ):
            raise Stage002Error("parent_safety_gate_failed")
        _remove_attempt_runtime_copies(attempt)
        _write_json_exclusive(attempt / "summary.json", summary)
        os.rename(attempt, final)
        _fsync_directory(final.parent)
        return summary
    except BaseException as exc:
        _remove_attempt_runtime_copies(attempt)
        if attempt.exists():
            failure_payload = {
                "schema_version": 1,
                "status": "failed",
                "stage": STAGE,
                "line_id": LINE_ID,
                "campaign_nonce": claim["campaign_nonce"],
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
            }
            failure_path = attempt / "failure.json"
            if not failure_path.exists():
                _write_json_exclusive(failure_path, failure_payload)
            if failure.exists():
                raise Stage002Error("stage002_failure_artifact_already_exists") from exc
            os.rename(attempt, failure)
            _fsync_directory(failure.parent)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-id")
    parser.add_argument("--worker-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--receipt-path", type=Path)
    parser.add_argument("--feature-path", type=Path)
    parser.add_argument("--external-probe-path", type=Path)
    parser.add_argument("--attestation-path", type=Path)
    parser.add_argument("--manifest-path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.run:
            summary = run_parent_qualification(
                final_dir=FINAL_DIR,
                failure_dir=FAILURE_DIR,
                claim_path=CLAIM_PATH,
                freeze_path=INPUT_FREEZE_PATH,
            )
            print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
            return 0
        required = {
            "worker_id": args.worker_id,
            "worker_root": args.worker_root,
            "runtime_root": args.runtime_root,
            "receipt_path": args.receipt_path,
            "feature_path": args.feature_path,
            "external_probe_path": args.external_probe_path,
            "attestation_path": args.attestation_path,
            "manifest_path": args.manifest_path,
        }
        if any(value is None for value in required.values()):
            raise Stage002Error("worker_arguments_incomplete")
        run_worker_qualification(
            worker_id=str(args.worker_id),
            worker_root=args.worker_root,
            runtime_root=args.runtime_root,
            receipt_path=args.receipt_path,
            feature_path=args.feature_path,
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
