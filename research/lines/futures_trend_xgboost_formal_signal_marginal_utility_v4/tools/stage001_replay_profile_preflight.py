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
V3_LINE_ROOT = (
    WORKSPACE_ROOT
    / "research/lines/futures_trend_xgboost_formal_signal_marginal_utility_v3"
)
V3_STAGE002_TOOL = V3_LINE_ROOT / "tools/stage002_event_feature_qualification.py"
V3_METADATA_PREFLIGHT_TOOL = (
    V3_LINE_ROOT / "tools/stage001_metadata_side_effect_preflight.py"
)
V3_STAGE002_FAILURE = (
    V3_LINE_ROOT / "artifacts/stage002_event_feature_qualification_failed"
)
V2_LINE_ROOT = (
    WORKSPACE_ROOT
    / "research/lines/futures_trend_xgboost_formal_signal_marginal_utility_v2"
)
V2_FONT_CACHE = V2_LINE_ROOT / "materials/fontlist-v390.json"
V2_RELEASE_ATTESTATION = (
    V2_LINE_ROOT / "materials/release_manifest_commit_attestation.json"
)
V4_TESTS = LINE_ROOT / "tests/test_stage001_replay_profile_preflight.py"
V4_PREREGISTRATION = (
    LINE_ROOT
    / "stages/20260905_1847_stage000_replay_profile_side_effect_preflight_preregistration.md"
)
EXPECTED_INPUT_FILE_COUNT = 1446
STAGE = "stage001_replay_profile_side_effect_preflight"
LINE_ID = "futures_trend_xgboost_formal_signal_marginal_utility_v4"
CANDIDATE_MODULE_NAME = (
    "run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest"
)
CANDIDATE_MODULE_PATH = (
    Path("/Users/bytedance/Desktop/person/vnpy_production_live")
    / "examples/portfolio_backtesting"
    / f"{CANDIDATE_MODULE_NAME}.py"
)
SANDBOX_EXECUTABLE = Path("/usr/bin/sandbox-exec")
PROFILE_CONTRACT_KEYS = {
    "profile",
    "strategy_class",
    "spec_profile",
    "capital",
    "profile_override_count",
    "profile_override_keys",
    "profile_overrides_sha256",
    "live_override_count",
    "live_override_keys",
    "live_overrides_sha256",
    "combined_override_count",
    "combined_override_keys",
    "combined_overrides_sha256",
}
CAPITAL_CONTRACT_KEYS = {
    "variant",
    "label",
    "account_capital",
    "c3_capital",
    "risk_multiplier",
}


class ProfilePreflightError(RuntimeError):
    pass


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, Path(path).resolve(strict=True))
    if spec is None or spec.loader is None:
        raise ProfilePreflightError(f"module_spec_failed:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_v3_stage002_module() -> Any:
    return _load_module("v4_stage001_v3_stage002_support", V3_STAGE002_TOOL)


def load_metadata_preflight_module() -> Any:
    return _load_module("v4_stage001_metadata_preflight_support", V3_METADATA_PREFLIGHT_TOOL)


def load_v1_runner() -> Any:
    return load_metadata_preflight_module().load_v1_runner()


def collect_input_files() -> dict[str, Path]:
    files = dict(load_v3_stage002_module().collect_input_files())
    files.update(
        {
            "v4_runner": Path(__file__).resolve(),
            "v4_tests": V4_TESTS,
            "v4_line": LINE_ROOT / "LINE.md",
            "v4_preregistration": V4_PREREGISTRATION,
            "v3_stage002_freeze_json": (
                V3_LINE_ROOT / "stages/20260905_stage002a_input_contract_freeze.json"
            ),
            "v3_stage002_freeze_record": (
                V3_LINE_ROOT / "stages/20260905_1840_stage002a_input_contract_freeze.md"
            ),
            "v3_stage002_claim": (
                V3_LINE_ROOT / "stages/20260905_stage002_execution_state/claim.json"
            ),
            "v3_stage002_failure_record": (
                V3_LINE_ROOT
                / "stages/20260905_1843_stage002_unique_run_failed_replay_profile_write.md"
            ),
            "v3_stage002_failure": V3_STAGE002_FAILURE / "failure.json",
            "v3_stage002_worker_failure": (
                V3_STAGE002_FAILURE / "workers/A1/failure_receipt.json"
            ),
            "v3_stage002_failed_input_manifest": (
                V3_STAGE002_FAILURE / "input_manifest.json"
            ),
            "v3_stage002_failed_a1_universe": (
                V3_STAGE002_FAILURE / "workers/A1/derived/static18_plus_fu.csv"
            ),
            "v3_stage002_failed_a1_post_signal_eligibility": (
                V3_STAGE002_FAILURE
                / "workers/A1/derived/post_signal_eligibility.csv"
            ),
        }
    )
    if len(files) != EXPECTED_INPUT_FILE_COUNT:
        raise ProfilePreflightError(
            f"input_inventory_count_mismatch:{len(files)}:{EXPECTED_INPUT_FILE_COUNT}"
        )
    for key, path in files.items():
        if path.is_symlink() or not path.is_file():
            raise ProfilePreflightError(f"input_file_invalid:{key}:{path}")
    return dict(sorted(files.items()))


def _stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _normalize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_value(item)
            for key, item in sorted(value.items(), key=lambda row: str(row[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_normalize_value(item) for item in value)
    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            return _normalize_value(item_method())
        except (TypeError, ValueError):
            pass
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return _normalize_value(enum_value)
    raise ProfilePreflightError(
        f"profile_value_not_portable:{type(value).__module__}.{type(value).__qualname__}"
    )


def profile_contract(
    profile: Mapping[str, Any],
    live_overrides: Mapping[str, Any],
    *,
    verified_path_aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    spec = profile.get("spec")
    strategy_class = profile.get("strategy_cls")
    capital = getattr(spec, "capital", None)
    profile_overrides = getattr(spec, "overrides", None)
    if (
        spec is None
        or capital is None
        or not isinstance(profile_overrides, Mapping)
        or not isinstance(live_overrides, Mapping)
        or not isinstance(strategy_class, type)
    ):
        raise ProfilePreflightError("profile_contract_invalid")
    aliases = dict(verified_path_aliases or {})

    def portable(value: Any) -> Any:
        if isinstance(value, str):
            return aliases.get(value, value)
        if isinstance(value, dict):
            return {key: portable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [portable(item) for item in value]
        return value

    normalized_profile_overrides = portable(_normalize_value(profile_overrides))
    normalized_live_overrides = portable(_normalize_value(live_overrides))
    combined = {**normalized_profile_overrides, **normalized_live_overrides}
    capital_fields = {
        key: _normalize_value(getattr(capital, key, None))
        for key in (
            "variant",
            "label",
            "account_capital",
            "c3_capital",
            "risk_multiplier",
        )
    }
    return {
        "profile": str(profile.get("profile", "")),
        "strategy_class": (
            f"{strategy_class.__module__}.{strategy_class.__qualname__}"
        ),
        "spec_profile": str(getattr(spec, "profile", "")),
        "capital": capital_fields,
        "profile_override_count": len(normalized_profile_overrides),
        "profile_override_keys": sorted(normalized_profile_overrides),
        "profile_overrides_sha256": hashlib.sha256(
            _stable_json_bytes(normalized_profile_overrides)
        ).hexdigest(),
        "live_override_count": len(normalized_live_overrides),
        "live_override_keys": sorted(normalized_live_overrides),
        "live_overrides_sha256": hashlib.sha256(
            _stable_json_bytes(normalized_live_overrides)
        ).hexdigest(),
        "combined_override_count": len(combined),
        "combined_override_keys": sorted(combined),
        "combined_overrides_sha256": hashlib.sha256(
            _stable_json_bytes(combined)
        ).hexdigest(),
    }


def run_guarded_replay_profile_preflight(
    *,
    worker_root: Path,
    expected_outputs: Mapping[str, Path],
    expected_candidate_module_path: Path,
    attestation: Mapping[str, Any],
    preflight: Any,
    metadata_preflight: Any,
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
            raise ProfilePreflightError("candidate_module_missing")
        module_file = Path(str(getattr(candidate_module, "__file__", ""))).resolve(
            strict=True
        )
        if module_file != Path(expected_candidate_module_path).resolve(strict=True):
            raise ProfilePreflightError("candidate_module_identity_mismatch")
        original_universe = candidate_module.UNIVERSE_PATH
        original_eligibility = (
            candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
        )
        with metadata_preflight.redirect_metadata_outputs(
            candidate_module,
            root,
        ) as targets:
            metadata = context["s901"].s513._metadata()
            profile = context["s901"].s847._c9_profile(metadata)
            live_overrides = (
                context["live_config"].build_official_live_strategy_overrides()
            )
        paths_restored = bool(
            candidate_module.UNIVERSE_PATH is original_universe
            and candidate_module.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
            is original_eligibility
        )
        if not paths_restored:
            raise ProfilePreflightError("metadata_output_paths_not_restored")
        derived_outputs = metadata_preflight.verify_derived_outputs(
            targets,
            expected_outputs,
        )
        metadata_summary = metadata_preflight.metadata_contract(metadata)
        # Only byte-verified derived files share identities across worker roots.
        normalized_profile = profile_contract(
            profile,
            live_overrides,
            verified_path_aliases={
                str(targets[key]): str(expected_outputs[key]) for key in targets
            },
        )

    counters = dict(guard.counters)
    if network.attempts != 0:
        raise ProfilePreflightError("network_attempt_detected")
    if any(counters.values()):
        raise ProfilePreflightError("sensitive_operation_detected")
    if guard.formal_replay_call_count != 0:
        raise ProfilePreflightError("formal_replay_detected")
    if len(adapter_calls) != 1 or adapter_restored is not True:
        raise ProfilePreflightError("release_adapter_contract_failed")
    return {
        "candidate_module_path": str(module_file),
        "metadata": metadata_summary,
        "derived_outputs": derived_outputs,
        "metadata_output_paths_restored": paths_restored,
        "profile_contract": normalized_profile,
        "sensitive_counters": counters,
        "network_connection_attempt_count": int(network.attempts),
        "formal_replay_call_count": int(guard.formal_replay_call_count),
        "release_adapter_call_count": len(adapter_calls),
        "release_adapter_calls": list(adapter_calls),
        "release_adapter_restored": bool(adapter_restored),
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


def _require_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ProfilePreflightError(f"invalid_sha256:{field}")
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
        raise ProfilePreflightError("input_manifest_schema_invalid")
    if recorded.get("schema_version") != 1:
        raise ProfilePreflightError("input_manifest_version_invalid")
    if recorded.get("stage") != STAGE or recorded.get("line_id") != LINE_ID:
        raise ProfilePreflightError("input_manifest_identity_invalid")

    files = recorded.get("files")
    if not isinstance(files, Mapping):
        raise ProfilePreflightError("input_manifest_files_invalid")
    file_count = recorded.get("input_file_count")
    if (
        isinstance(file_count, bool)
        or not isinstance(file_count, int)
        or file_count != EXPECTED_INPUT_FILE_COUNT
        or len(files) != file_count
    ):
        raise ProfilePreflightError("input_manifest_file_count_invalid")
    normalized_files: dict[str, dict[str, Any]] = {}
    for key, identity in files.items():
        if not isinstance(key, str) or not isinstance(identity, Mapping):
            raise ProfilePreflightError("input_manifest_file_identity_invalid")
        if set(identity) != {"path", "size", "mtime_ns", "sha256"}:
            raise ProfilePreflightError(
                f"input_manifest_file_identity_invalid:{key}"
            )
        if not isinstance(identity.get("path"), str):
            raise ProfilePreflightError(f"input_manifest_file_path_invalid:{key}")
        for field in ("size", "mtime_ns"):
            value = identity.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ProfilePreflightError(
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
        raise ProfilePreflightError("input_manifest_logical_key_sha_mismatch")
    if _require_sha256(
        recorded.get("file_contract_sha256"),
        "file_contract_sha256",
    ) != _file_contract_sha256(normalized_files):
        raise ProfilePreflightError("input_manifest_file_contract_sha_mismatch")

    runtime = recorded.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ProfilePreflightError("input_manifest_runtime_invalid")
    if _require_sha256(
        recorded.get("runtime_contract_sha256"),
        "runtime_contract_sha256",
    ) != hashlib.sha256(_stable_json_bytes(runtime)).hexdigest():
        raise ProfilePreflightError("input_manifest_runtime_sha_mismatch")
    if not isinstance(recorded.get("formal_identity"), Mapping):
        raise ProfilePreflightError("input_manifest_formal_identity_invalid")
    return dict(recorded)


def validate_current_input_manifest(recorded: Mapping[str, Any]) -> dict[str, Any]:
    expected = validate_input_manifest_payload(recorded)
    observed = build_input_manifest()
    validate_input_manifest_payload(observed)
    if observed != expected:
        raise ProfilePreflightError("current_input_manifest_drift")
    return observed


def validate_frozen_metadata_files(
    manifest: Mapping[str, Any],
) -> dict[str, Path]:
    try:
        return dict(
            load_metadata_preflight_module().validate_frozen_metadata_files(manifest)
        )
    except BaseException as exc:
        if isinstance(exc, ProfilePreflightError):
            raise
        raise ProfilePreflightError(str(exc)) from exc


def load_preflight_module() -> Any:
    return load_metadata_preflight_module().load_preflight_module()


def prepare_profile_worker_root(worker_root: Path) -> dict[str, Path]:
    return dict(
        load_metadata_preflight_module().prepare_metadata_worker_root(
            Path(worker_root)
        )
    )


def worker_command(
    paths: Mapping[str, Path],
    worker_id: str,
    manifest_path: Path,
    external_probe_path: Path,
) -> list[str]:
    if worker_id not in {"A1", "A2"}:
        raise ProfilePreflightError("worker_id_invalid")
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


def _validate_profile_contract_payload(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or set(payload) != PROFILE_CONTRACT_KEYS:
        raise ProfilePreflightError("profile_contract_schema_invalid")
    for field in ("profile", "strategy_class", "spec_profile"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise ProfilePreflightError(f"profile_contract_string_invalid:{field}")
    capital = payload.get("capital")
    if not isinstance(capital, Mapping) or set(capital) != CAPITAL_CONTRACT_KEYS:
        raise ProfilePreflightError("profile_contract_capital_invalid")
    for prefix in ("profile", "live", "combined"):
        count = payload.get(f"{prefix}_override_count")
        keys = payload.get(f"{prefix}_override_keys")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or not isinstance(keys, list)
            or keys != sorted(set(keys))
            or any(not isinstance(key, str) for key in keys)
            or len(keys) != count
        ):
            raise ProfilePreflightError(
                f"profile_contract_override_index_invalid:{prefix}"
            )
        _require_sha256(
            payload.get(f"{prefix}_overrides_sha256"),
            f"profile_contract.{prefix}_overrides_sha256",
        )
    try:
        return json.loads(_stable_json_bytes(payload))
    except (TypeError, ValueError) as exc:
        raise ProfilePreflightError("profile_contract_not_portable") from exc


def _read_json_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfilePreflightError(f"{label}_read_failed") from exc
    if not isinstance(payload, Mapping):
        raise ProfilePreflightError(f"{label}_invalid")
    return dict(payload)


def run_profile_worker(
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
        raise ProfilePreflightError("worker_id_invalid")
    root = Path(worker_root).resolve(strict=True)
    runtime = Path(runtime_root).resolve(strict=True)
    receipt_destination = Path(receipt_path).resolve(strict=False)
    if runtime != root / "runtime":
        raise ProfilePreflightError("worker_runtime_binding_invalid")
    if receipt_destination != root / "receipt.json":
        raise ProfilePreflightError("worker_receipt_binding_invalid")
    if receipt_destination.exists():
        raise ProfilePreflightError("worker_receipt_preexists")
    probe = Path(external_probe_path).resolve(strict=False)
    if probe == root or root in probe.parents or probe.exists():
        raise ProfilePreflightError("worker_sandbox_probe_invalid")

    support = load_metadata_preflight_module()
    manifest = _read_json_mapping(
        Path(manifest_path).resolve(strict=True),
        "worker_input_manifest",
    )
    preflight = support.load_preflight_module()
    bootstrap = preflight._validate_worker_bootstrap(runtime)
    sandbox_probe = preflight.prove_external_write_denied(probe)
    production_head = preflight.read_git_head_without_process(
        preflight.PRODUCTION_ROOT
    )
    if production_head != preflight.EXPECTED_PRODUCTION_HEAD:
        raise ProfilePreflightError("worker_production_head_drift")
    runtime_cache = runtime / (
        f"mplconfig/fontlist-v{preflight.EXPECTED_FONT_MANAGER_VERSION}.json"
    )
    font_cache = preflight.validate_portable_font_cache(
        runtime_cache,
        expected_version=preflight.EXPECTED_FONT_MANAGER_VERSION,
        matplotlib_data_path=preflight.matplotlib_data_path(),
    )
    if font_cache["sha256"] != preflight.EXPECTED_FONT_CACHE_SHA256:
        raise ProfilePreflightError("worker_font_cache_drift")
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
        guarded = run_guarded_replay_profile_preflight(
            worker_root=root,
            expected_outputs=expected_outputs,
            expected_candidate_module_path=CANDIDATE_MODULE_PATH,
            attestation=attestation,
            preflight=preflight,
            metadata_preflight=support,
        )
        support._validate_guarded_result(guarded, preflight)
        guarded["profile_contract"] = _validate_profile_contract_payload(
            guarded["profile_contract"]
        )
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
    support._write_json_exclusive(receipt_destination, receipt)
    return receipt


def portable_worker_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    portable = load_metadata_preflight_module().portable_worker_receipt(receipt)
    profile_payload = receipt.get("profile_contract")
    if not isinstance(profile_payload, Mapping):
        raise ProfilePreflightError("portable_profile_contract_missing")
    portable["profile_contract"] = _validate_profile_contract_payload(
        profile_payload
    )
    return portable


def run_cold_worker(
    output_root: Path,
    worker_id: str,
    manifest_path: Path,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if worker_id not in {"A1", "A2"}:
        raise ProfilePreflightError("worker_id_invalid")
    output = Path(output_root).resolve(strict=False)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    output = output.resolve(strict=True)
    paths = prepare_profile_worker_root(output / "workers" / worker_id)
    support = load_metadata_preflight_module()
    preflight = support.load_preflight_module()
    if _file_identity(paths["font_cache"])["sha256"] != (
        preflight.EXPECTED_FONT_CACHE_SHA256
    ):
        raise ProfilePreflightError("prepared_font_cache_sha_drift")
    preflight.write_sandbox_profile(paths["profile"], paths["worker_root"])
    probe = output / f".sandbox_probe_{worker_id}"
    if probe.exists():
        raise ProfilePreflightError("sandbox_probe_preexists")
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
        raise ProfilePreflightError(
            f"worker_failed:{worker_id}:returncode={completed.returncode}:"
            f"{detail[-4000:]}"
        )
    if not paths["receipt"].is_file():
        raise ProfilePreflightError(f"worker_receipt_missing:{worker_id}")
    receipt = _read_json_mapping(paths["receipt"], f"worker_{worker_id}_receipt")
    if (
        receipt.get("status") != "passed"
        or receipt.get("worker_id") != worker_id
        or receipt.get("stage") != STAGE
        or receipt.get("line_id") != LINE_ID
    ):
        raise ProfilePreflightError(f"worker_receipt_status_invalid:{worker_id}")
    for field in (
        "formal_identity",
        "input_file_count",
        "input_logical_key_sha256",
        "file_contract_sha256",
        "runtime_contract_sha256",
    ):
        if receipt.get(field) != manifest.get(field):
            raise ProfilePreflightError(
                f"worker_receipt_manifest_drift:{worker_id}:{field}"
            )
    support._validate_guarded_result(receipt, preflight)
    _validate_profile_contract_payload(receipt.get("profile_contract", {}))
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
            raise ProfilePreflightError(
                f"worker_derived_identity_invalid:{worker_id}:{key}"
            )
    if probe.exists():
        raise ProfilePreflightError(f"worker_sandbox_probe_created:{worker_id}")
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


def _write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    load_metadata_preflight_module()._write_json_exclusive(Path(path), payload)


def run_parent_profile_preflight(output_dir: Path) -> dict[str, Any]:
    if not SANDBOX_EXECUTABLE.is_file():
        raise ProfilePreflightError("sandbox_executable_missing")
    support = load_metadata_preflight_module()
    preflight = support.load_preflight_module()
    if _file_identity(V2_FONT_CACHE)["sha256"] != (
        preflight.EXPECTED_FONT_CACHE_SHA256
    ):
        raise ProfilePreflightError("font_cache_fixture_drift")
    if _file_identity(V2_RELEASE_ATTESTATION)["sha256"] != (
        preflight.EXPECTED_RELEASE_ATTESTATION_SHA256
    ):
        raise ProfilePreflightError("release_attestation_fixture_drift")

    manifest = build_input_manifest()
    validate_input_manifest_payload(manifest)
    validate_frozen_metadata_files(manifest)
    output = Path(output_dir).resolve(strict=False)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    manifest_path = output / "input_manifest.json"
    _write_json_exclusive(manifest_path, manifest)
    try:
        worker_results = [
            run_cold_worker(output, worker_id, manifest_path, manifest)
            for worker_id in ("A1", "A2")
        ]
        receipts = [result["receipt"] for result in worker_results]
        portable = [portable_worker_receipt(receipt) for receipt in receipts]
        worker_pids_distinct = len({int(receipt["pid"]) for receipt in receipts}) == 2
        portable_receipts_equal = portable[0] == portable[1]
        profile_contracts_equal = (
            receipts[0]["profile_contract"] == receipts[1]["profile_contract"]
        )
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
            "profile_contracts_equal": profile_contracts_equal,
            "metadata": receipts[0]["metadata"],
            "profile_contract": receipts[0]["profile_contract"],
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
            or not profile_contracts_equal
            or not summary["metadata_output_paths_restored"]
            or any(aggregate_counters.values())
            or summary["network_connection_attempt_count"] != 0
            or summary["formal_replay_call_count"] != 0
            or summary["release_adapter_call_count"] != 2
            or summary["release_adapter_restored"] is not True
        ):
            raise ProfilePreflightError("parent_profile_preflight_gate_failed")
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
                raise ProfilePreflightError("output_dir_required")
            summary = run_parent_profile_preflight(args.output_dir)
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
            raise ProfilePreflightError("worker_arguments_incomplete")
        run_profile_worker(
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
