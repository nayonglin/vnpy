from __future__ import annotations

import argparse
import builtins
import errno
import hashlib
import importlib
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import traceback
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any


LINE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
PORTFOLIO_DIR = PRODUCTION_ROOT / "examples/portfolio_backtesting"
FONT_CACHE_FIXTURE = LINE_ROOT / "materials/fontlist-v390.json"
RELEASE_ATTESTATION = LINE_ROOT / "materials/release_manifest_commit_attestation.json"
SANDBOX_EXECUTABLE = Path("/usr/bin/sandbox-exec")
EXPECTED_PRODUCTION_HEAD = "d492ee072aa5a9d71477235d79f17d2a5db59db3"
EXPECTED_RELEASE_ID = "m0005_20260901T165450+0800_1961d98ccb2b"
EXPECTED_RELEASE_COMMIT = "e3bff060154736e18e3dff1268ca55137c39d462"
EXPECTED_STRATEGY_VERSION = "ai_top10_plus_fu_official_live_v1"
EXPECTED_OFFICIAL_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
EXPECTED_MANIFEST_IDENTITY = "4d92133bd67821a421bf6017c477015e79a3a8e36889ae4eb527bb11a31956a5"
EXPECTED_CAPITAL = 150_000.0
EXPECTED_MATPLOTLIB_VERSION = "3.10.8"
EXPECTED_FONT_MANAGER_VERSION = 390
EXPECTED_FONT_CACHE_SHA256 = "13e74b8b71bc612a81a67da228ab73c718d92ffb80896f3bdf481c0119938479"
EXPECTED_RELEASE_ATTESTATION_SHA256 = "e4e8a149173b58c208533492723d02184a2fd5bf36c3ff7c7110b4fe2a1a0d9a"


HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
RELEASE_ATTESTATION_FIELDS = {
    "schema_version",
    "repo_root",
    "current_relative_path",
    "current_sha256",
    "manifest_relative_path",
    "manifest_sha256",
    "manifest_git_blob_oid",
    "release_commit",
    "release_id",
    "strategy_version",
    "manifest_identity_sha256",
}
FONT_CACHE_FIELDS = {
    "_version",
    "_FontManager__default_weight",
    "default_size",
    "defaultFamily",
    "ttflist",
    "afmlist",
    "__class__",
}
SENSITIVE_COUNTER_KEYS = (
    "label_value_read_count",
    "label_build_count",
    "model_fit_count",
    "prediction_count",
    "candidate_strategy_run_count",
    "holdout_read_count",
    "network_connection_count",
    "ctp_connection_count",
    "account_query_count",
    "order_api_called_count",
    "production_file_write_count",
    "sensitive_module_import_count",
    "subprocess_spawn_count",
)


class ImportPreflightError(RuntimeError):
    pass


def zero_sensitive_counters() -> dict[str, int]:
    return {key: 0 for key in SENSITIVE_COUNTER_KEYS}


def _sensitive_python_call_counter(
    module_name: str,
    function_name: str,
) -> str | None:
    module_lower = module_name.lower()
    function_lower = function_name.lower()
    if module_lower.startswith(("sklearn", "xgboost", "lightgbm", "catboost")):
        if function_lower == "fit" or function_lower.endswith("_fit"):
            return "model_fit_count"
        if function_lower in {"predict", "predict_proba", "inplace_predict"}:
            return "prediction_count"
    if "ctp" in module_lower or "gateway" in module_lower:
        if function_lower in {
            "send_order",
            "cancel_order",
            "reqorderinsert",
            "reqorderaction",
        }:
            return "order_api_called_count"
        if function_lower in {
            "query_account",
            "query_position",
            "reqqrytradingaccount",
            "reqqryinvestorposition",
        }:
            return "account_query_count"
        if function_lower in {"connect", "reconnect", "reqauthenticate", "requserlogin"}:
            return "ctp_connection_count"
    if "label" in function_lower and function_lower.startswith(("build", "make", "create")):
        return "label_build_count"
    if module_lower.startswith(("train_qmt_roll_ai", "validate_qmt_roll_ai")):
        return "candidate_strategy_run_count"
    return None


class NetworkBlock:
    def __init__(self) -> None:
        self.attempts = 0
        self._originals: dict[str, Any] = {}

    def __enter__(self) -> "NetworkBlock":
        self._originals = {
            "connect": socket.socket.connect,
            "connect_ex": socket.socket.connect_ex,
            "create_connection": socket.create_connection,
            "getaddrinfo": socket.getaddrinfo,
            "gethostbyname": socket.gethostbyname,
            "gethostbyname_ex": socket.gethostbyname_ex,
            "gethostbyaddr": socket.gethostbyaddr,
        }
        owner = self

        def blocked(*_args: Any, **_kwargs: Any) -> None:
            owner.attempts += 1
            raise ImportPreflightError("network_connection_forbidden")

        socket.socket.connect = blocked  # type: ignore[method-assign]
        socket.socket.connect_ex = blocked  # type: ignore[method-assign]
        socket.create_connection = blocked
        socket.getaddrinfo = blocked
        socket.gethostbyname = blocked
        socket.gethostbyname_ex = blocked
        socket.gethostbyaddr = blocked
        return self

    def __exit__(self, *_args: Any) -> None:
        socket.socket.connect = self._originals["connect"]  # type: ignore[method-assign]
        socket.socket.connect_ex = self._originals["connect_ex"]  # type: ignore[method-assign]
        socket.create_connection = self._originals["create_connection"]
        socket.getaddrinfo = self._originals["getaddrinfo"]
        socket.gethostbyname = self._originals["gethostbyname"]
        socket.gethostbyname_ex = self._originals["gethostbyname_ex"]
        socket.gethostbyaddr = self._originals["gethostbyaddr"]


class SensitiveOperationGuard:
    _forbidden_import_prefixes = (
        "xgboost",
        "sklearn",
        "lightgbm",
        "catboost",
        "vnpy_ctp",
        "vnpy.gateway.ctp",
    )
    _label_data_suffixes = {
        ".csv",
        ".json",
        ".parquet",
        ".feather",
        ".pkl",
        ".pickle",
    }
    _os_process_entrypoints = (
        "system",
        "popen",
        "posix_spawn",
        "posix_spawnp",
        "fork",
        "forkpty",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
    )

    def __init__(
        self,
        allowed_write_roots: tuple[Path, ...] | list[Path],
        *,
        allowed_formal_replay_count: int = 0,
    ) -> None:
        self.allowed_write_roots = tuple(Path(path).resolve() for path in allowed_write_roots)
        if not self.allowed_write_roots:
            raise ImportPreflightError("sensitive_guard_write_roots_empty")
        if (
            isinstance(allowed_formal_replay_count, bool)
            or not isinstance(allowed_formal_replay_count, int)
            or allowed_formal_replay_count < 0
        ):
            raise ImportPreflightError("formal_replay_allowance_invalid")
        self.allowed_formal_replay_count = allowed_formal_replay_count
        self.formal_replay_call_count = 0
        self.counters = zero_sensitive_counters()
        self._original_import: Any = None
        self._original_builtin_open: Any = None
        self._original_io_open: Any = None
        self._original_popen: Any = None
        self._original_os_process_functions: dict[str, Any] = {}
        self._original_fork_exec: Any = None
        self._previous_profile: Any = None
        self._previous_thread_profile: Any = None
        self._blocking = False

    def _block(self, counter: str, reason: str) -> None:
        if not self._blocking:
            self._blocking = True
            self.counters[counter] += 1
        raise ImportPreflightError(reason)

    def _resolve_path(self, value: Any) -> Path | None:
        if isinstance(value, int):
            return None
        try:
            path = Path(os.fsdecode(value)).expanduser()
        except (TypeError, ValueError):
            return None
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve(strict=False)

    def _check_open(self, file: Any, mode: str) -> None:
        path = self._resolve_path(file)
        if path is None:
            return
        if any(token in str(mode) for token in ("w", "a", "x", "+")):
            if not any(path == root or root in path.parents for root in self.allowed_write_roots):
                self._block(
                    "production_file_write_count",
                    f"file_write_forbidden:{path}",
                )
            return
        lower_name = path.name.lower()
        if path.suffix.lower() not in self._label_data_suffixes:
            return
        if "holdout" in lower_name:
            self._block("holdout_read_count", f"holdout_read_forbidden:{path}")
        if any(token in lower_name for token in ("label", "outcome", "target")):
            self._block("label_value_read_count", f"label_read_forbidden:{path}")

    def _guarded_builtin_open(self, file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        self._check_open(file, mode)
        return self._original_builtin_open(file, mode, *args, **kwargs)

    def _guarded_io_open(self, file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        self._check_open(file, mode)
        return self._original_io_open(file, mode, *args, **kwargs)

    def _guarded_import(
        self,
        name: str,
        globals: Mapping[str, Any] | None = None,
        locals: Mapping[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        lowered = str(name).lower()
        if lowered.startswith(self._forbidden_import_prefixes) or lowered.startswith(
            ("train_qmt_roll_ai", "validate_qmt_roll_ai")
        ):
            self._block(
                "sensitive_module_import_count",
                f"sensitive_import_forbidden:{name}",
            )
        return self._original_import(name, globals, locals, fromlist, level)

    def _guarded_process(self, *_args: Any, **_kwargs: Any) -> Any:
        self._block("subprocess_spawn_count", "subprocess_forbidden")

    def _profile(self, frame: Any, event: str, argument: Any) -> None:
        if self._blocking:
            return
        if event == "call":
            module_name = str(frame.f_globals.get("__name__", ""))
            function_name = str(frame.f_code.co_name)
        elif event == "c_call":
            module_name = str(getattr(argument, "__module__", ""))
            function_name = str(getattr(argument, "__name__", ""))
        else:
            return
        if function_name.lower() == "_run_live_c9":
            self.formal_replay_call_count += 1
            if self.formal_replay_call_count > self.allowed_formal_replay_count:
                self._block(
                    "candidate_strategy_run_count",
                    "formal_replay_limit_exceeded",
                )
            return
        counter = _sensitive_python_call_counter(module_name, function_name)
        if counter is not None:
            self._block(counter, f"sensitive_call_forbidden:{module_name}.{function_name}")

    def assert_no_sensitive_modules_loaded(self) -> None:
        loaded = sorted(
            name
            for name in sys.modules
            if str(name).lower().startswith(self._forbidden_import_prefixes)
        )
        if loaded:
            self._block(
                "sensitive_module_import_count",
                f"sensitive_module_preloaded:{','.join(loaded[:5])}",
            )

    def __enter__(self) -> "SensitiveOperationGuard":
        self._original_import = builtins.__import__
        self._original_builtin_open = builtins.open
        self._original_io_open = io.open
        self._original_popen = subprocess.Popen
        self._original_os_process_functions = {
            name: getattr(os, name)
            for name in self._os_process_entrypoints
            if hasattr(os, name)
        }
        self._original_fork_exec = getattr(subprocess, "_fork_exec", None)
        self._previous_profile = sys.getprofile()
        self._previous_thread_profile = threading.getprofile()
        builtins.__import__ = self._guarded_import
        builtins.open = self._guarded_builtin_open
        io.open = self._guarded_io_open
        subprocess.Popen = self._guarded_process
        for name in self._original_os_process_functions:
            setattr(os, name, self._guarded_process)
        if self._original_fork_exec is not None:
            subprocess._fork_exec = self._guarded_process
        sys.setprofile(self._profile)
        threading.setprofile(self._profile)
        return self

    def __exit__(self, *_args: Any) -> None:
        sys.setprofile(self._previous_profile)
        threading.setprofile(self._previous_thread_profile)
        builtins.__import__ = self._original_import
        builtins.open = self._original_builtin_open
        io.open = self._original_io_open
        subprocess.Popen = self._original_popen
        for name, function in self._original_os_process_functions.items():
            setattr(os, name, function)
        if self._original_fork_exec is not None:
            subprocess._fork_exec = self._original_fork_exec


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git_blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _read_json_mapping(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ImportPreflightError(f"{label}_not_regular")
    try:
        payload = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportPreflightError(f"{label}_json_invalid") from exc
    if not isinstance(payload, dict):
        raise ImportPreflightError(f"{label}_not_mapping")
    return payload


def _portable_font_rows(rows: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ImportPreflightError(f"font_cache_{label}_not_list")
    portable: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ImportPreflightError(f"font_cache_{label}_entry_invalid")
        value = str(raw.get("fname", ""))
        relative = PurePosixPath(value)
        if relative.is_absolute():
            continue
        if (
            not relative.parts
            or relative.parts[0] != "fonts"
            or ".." in relative.parts
            or "." in relative.parts
        ):
            raise ImportPreflightError(f"font_cache_{label}_path_invalid")
        portable.append(dict(raw))
    portable.sort(
        key=lambda item: json.dumps(
            item,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
    )
    return portable


def _font_cache_identity(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    ttf_rows = payload["ttflist"]
    afm_rows = payload["afmlist"]
    absolute_count = sum(
        PurePosixPath(str(row["fname"])).is_absolute()
        for row in [*ttf_rows, *afm_rows]
    )
    return {
        "font_manager_version": int(payload["_version"]),
        "ttf_count": len(ttf_rows),
        "afm_count": len(afm_rows),
        "absolute_path_count": int(absolute_count),
        "sha256": _sha256_bytes(path.read_bytes()),
    }


def build_portable_font_cache(
    source_path: Path,
    destination_path: Path,
    *,
    expected_version: int,
) -> dict[str, Any]:
    source = _read_json_mapping(Path(source_path), "font_cache_source")
    if set(source) != FONT_CACHE_FIELDS:
        raise ImportPreflightError("font_cache_source_schema_invalid")
    if source.get("_version") != expected_version:
        raise ImportPreflightError("font_cache_source_version_mismatch")
    payload = dict(source)
    payload["ttflist"] = _portable_font_rows(source["ttflist"], "ttf")
    payload["afmlist"] = _portable_font_rows(source["afmlist"], "afm")
    if not payload["ttflist"] or not payload["afmlist"]:
        raise ImportPreflightError("font_cache_portable_entries_empty")
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            payload,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return _font_cache_identity(destination, payload)


def validate_portable_font_cache(
    cache_path: Path,
    *,
    expected_version: int,
    matplotlib_data_path: Path,
) -> dict[str, Any]:
    cache = Path(cache_path)
    payload = _read_json_mapping(cache, "font_cache")
    if cache.name != f"fontlist-v{expected_version}.json":
        raise ImportPreflightError("font_cache_filename_mismatch")
    if set(payload) != FONT_CACHE_FIELDS or payload.get("__class__") != "FontManager":
        raise ImportPreflightError("font_cache_schema_invalid")
    if payload.get("_version") != expected_version:
        raise ImportPreflightError("font_cache_version_mismatch")
    data_root = Path(matplotlib_data_path).resolve(strict=True)
    for label in ("ttflist", "afmlist"):
        rows = payload.get(label)
        if not isinstance(rows, list) or not rows:
            raise ImportPreflightError(f"font_cache_{label}_empty")
        names: set[str] = set()
        for raw in rows:
            if not isinstance(raw, Mapping):
                raise ImportPreflightError(f"font_cache_{label}_entry_invalid")
            value = str(raw.get("fname", ""))
            relative = PurePosixPath(value)
            if (
                relative.is_absolute()
                or not relative.parts
                or relative.parts[0] != "fonts"
                or ".." in relative.parts
                or "." in relative.parts
                or value in names
            ):
                raise ImportPreflightError(f"font_cache_{label}_path_invalid")
            names.add(value)
            font = data_root.joinpath(*relative.parts)
            if font.is_symlink() or not font.is_file():
                raise ImportPreflightError(f"font_cache_{label}_font_missing:{value}")
            try:
                font.resolve(strict=True).relative_to(data_root)
            except ValueError as exc:
                raise ImportPreflightError(f"font_cache_{label}_path_escape") from exc
    identity = _font_cache_identity(cache, payload)
    if identity["absolute_path_count"] != 0:
        raise ImportPreflightError("font_cache_absolute_path_present")
    return identity


def _bound_path(repo_root: Path, relative_value: Any, label: str) -> Path:
    relative = PurePosixPath(str(relative_value))
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ImportPreflightError(f"{label}_relative_path_invalid")
    path = repo_root.joinpath(*relative.parts)
    if path.is_symlink() or not path.is_file():
        raise ImportPreflightError(f"{label}_not_regular")
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ImportPreflightError(f"{label}_path_escape") from exc
    return resolved


def verify_release_commit_attestation(
    repo_root: Path,
    manifest_path: Path,
    release_commit: str,
    attestation: Mapping[str, Any],
) -> dict[str, str]:
    if set(attestation) != RELEASE_ATTESTATION_FIELDS:
        raise ImportPreflightError("release_attestation_schema_invalid")
    if attestation.get("schema_version") != 1:
        raise ImportPreflightError("release_attestation_version_invalid")

    repo = Path(repo_root).resolve(strict=True)
    expected_repo = Path(str(attestation["repo_root"])).resolve(strict=True)
    if repo != expected_repo:
        raise ImportPreflightError("release_attestation_repo_mismatch")

    expected_commit = str(attestation["release_commit"])
    observed_commit = str(release_commit)
    if HEX40.fullmatch(expected_commit) is None or observed_commit != expected_commit:
        raise ImportPreflightError("release_attestation_commit_mismatch")

    current = _bound_path(
        repo,
        attestation["current_relative_path"],
        "release_attestation_current",
    )
    manifest = _bound_path(
        repo,
        attestation["manifest_relative_path"],
        "release_attestation_manifest",
    )
    if Path(manifest_path).resolve(strict=True) != manifest:
        raise ImportPreflightError("release_attestation_manifest_path_mismatch")

    current_bytes = current.read_bytes()
    current_sha = str(attestation["current_sha256"])
    if HEX64.fullmatch(current_sha) is None or _sha256_bytes(current_bytes) != current_sha:
        raise ImportPreflightError("release_attestation_current_sha_mismatch")

    manifest_bytes = manifest.read_bytes()
    manifest_sha = str(attestation["manifest_sha256"])
    if HEX64.fullmatch(manifest_sha) is None or _sha256_bytes(manifest_bytes) != manifest_sha:
        raise ImportPreflightError("release_attestation_manifest_sha_mismatch")
    blob_oid = str(attestation["manifest_git_blob_oid"])
    if HEX40.fullmatch(blob_oid) is None or _git_blob_oid(manifest_bytes) != blob_oid:
        raise ImportPreflightError("release_attestation_manifest_blob_mismatch")

    try:
        current_payload = json.loads(current_bytes)
        manifest_payload = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportPreflightError("release_attestation_json_invalid") from exc
    expected_identity = str(attestation["manifest_identity_sha256"])
    if HEX64.fullmatch(expected_identity) is None:
        raise ImportPreflightError("release_attestation_manifest_identity_invalid")
    expected_fields = {
        "activation_mode": "active",
        "release_commit": expected_commit,
        "release_id": str(attestation["release_id"]),
        "strategy_version": str(attestation["strategy_version"]),
        "manifest_sha256": expected_identity,
    }
    if any(current_payload.get(key) != value for key, value in expected_fields.items()):
        raise ImportPreflightError("release_attestation_current_identity_mismatch")
    if manifest_payload.get("manifest_sha256") != expected_identity:
        raise ImportPreflightError("release_attestation_manifest_identity_mismatch")

    return {
        "repo_root": str(repo),
        "manifest_path": str(manifest),
        "release_commit": expected_commit,
        "manifest_sha256": manifest_sha,
        "manifest_git_blob_oid": blob_oid,
    }


@contextmanager
def release_commit_attestation_adapter(
    resolver: Any,
    attestation: Mapping[str, Any],
):
    original = getattr(resolver, "_assert_release_commit", None)
    if not callable(original):
        raise ImportPreflightError("release_adapter_entrypoint_invalid")
    calls: list[dict[str, str]] = []

    def adapted(repo_root: Path, manifest_path: Path, release_commit: str) -> None:
        calls.append(
            verify_release_commit_attestation(
                repo_root,
                manifest_path,
                release_commit,
                attestation,
            )
        )

    resolver._assert_release_commit = adapted
    try:
        yield calls
    finally:
        resolver._assert_release_commit = original


def _git_directory(root: Path) -> Path:
    marker = root / ".git"
    if marker.is_dir():
        return marker.resolve(strict=True)
    if not marker.is_file():
        raise ImportPreflightError("production_git_marker_missing")
    text = marker.read_text(encoding="utf-8").strip()
    prefix = "gitdir: "
    if not text.startswith(prefix):
        raise ImportPreflightError("production_git_marker_invalid")
    value = Path(text[len(prefix) :])
    if not value.is_absolute():
        value = marker.parent / value
    return value.resolve(strict=True)


def read_git_head_without_process(root: Path) -> str:
    git_dir = _git_directory(Path(root).resolve(strict=True))
    head_text = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    if HEX40.fullmatch(head_text) is not None:
        return head_text
    prefix = "ref: "
    if not head_text.startswith(prefix):
        raise ImportPreflightError("production_git_head_invalid")
    reference = head_text[len(prefix) :]
    common_dir = git_dir
    common_marker = git_dir / "commondir"
    if common_marker.is_file():
        common_value = Path(common_marker.read_text(encoding="utf-8").strip())
        common_dir = (
            common_value
            if common_value.is_absolute()
            else (git_dir / common_value).resolve(strict=True)
        )
    for path in (git_dir / reference, common_dir / reference):
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if HEX40.fullmatch(value) is None:
                raise ImportPreflightError("production_git_reference_invalid")
            return value
    packed_refs = common_dir / "packed-refs"
    if packed_refs.is_file():
        for line in packed_refs.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith(("#", "^")):
                continue
            digest, name = line.split(" ", 1)
            if name == reference and HEX40.fullmatch(digest) is not None:
                return digest
    raise ImportPreflightError("production_git_reference_missing")


def python_site_packages() -> Path:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return (Path(sys.prefix) / "lib" / version / "site-packages").resolve(strict=True)


def matplotlib_data_path() -> Path:
    return (python_site_packages() / "matplotlib/mpl-data").resolve(strict=True)


def expected_worker_environment(runtime_root: Path) -> dict[str, str]:
    runtime = Path(runtime_root).resolve()
    return {
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


def prepare_worker_root(worker_root: Path) -> dict[str, Path]:
    root = Path(worker_root)
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    runtime = root / "runtime"
    for directory in (
        runtime,
        runtime / ".vntrader",
        runtime / "tmp",
        runtime / "mplconfig",
        runtime / "home",
    ):
        directory.mkdir(mode=0o700)
        os.chmod(directory, 0o700)
    setting = runtime / ".vntrader/vt_setting.json"
    setting.write_text("{}\n", encoding="utf-8")
    os.chmod(setting, 0o600)
    target_cache = runtime / f"mplconfig/fontlist-v{EXPECTED_FONT_MANAGER_VERSION}.json"
    shutil.copy2(FONT_CACHE_FIXTURE, target_cache)
    os.chmod(target_cache, 0o600)
    return {
        "worker_root": root.resolve(strict=True),
        "runtime": runtime.resolve(strict=True),
        "setting": setting.resolve(strict=True),
        "font_cache": target_cache.resolve(strict=True),
        "receipt": (root / "receipt.json").resolve(strict=False),
        "profile": (root / "preflight.sb").resolve(strict=False),
        "log": (root / "worker.log").resolve(strict=False),
    }


def sandbox_profile_text(worker_root: Path) -> str:
    allowed = json.dumps(str(Path(worker_root).resolve(strict=True)), ensure_ascii=True)
    return "\n".join(
        (
            "(version 1)",
            "(deny default)",
            "(allow process-exec)",
            "(deny process-fork)",
            "(allow sysctl-read)",
            "(allow mach-lookup)",
            "(allow file-read*)",
            f"(allow file-write* (subpath {allowed}))",
            '(allow file-write* (literal "/dev/null"))',
            "(deny network*)",
            "",
        )
    )


def _write_bytes_exclusive(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise ImportPreflightError("exclusive_write_failed")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    encoded = (
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    _write_bytes_exclusive(Path(path), encoded)


def write_sandbox_profile(path: Path, worker_root: Path) -> None:
    _write_bytes_exclusive(Path(path), sandbox_profile_text(worker_root).encode("utf-8"))


def prove_external_write_denied(probe: Path) -> dict[str, Any]:
    descriptor: int | None = None
    try:
        descriptor = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as exc:
        if exc.errno not in {errno.EPERM, errno.EACCES}:
            raise ImportPreflightError(
                f"sandbox_probe_unexpected_errno:{exc.errno}"
            ) from exc
        return {"write_denied": True, "errno": int(exc.errno)}
    else:
        os.write(descriptor, b"sandbox-not-enforced\n")
        os.fsync(descriptor)
    finally:
        if descriptor is not None:
            os.close(descriptor)
    Path(probe).unlink(missing_ok=True)
    raise ImportPreflightError("sandbox_external_write_not_denied")


def _worker_flags() -> dict[str, Any]:
    return {
        "isolated": int(sys.flags.isolated),
        "ignore_environment": int(sys.flags.ignore_environment),
        "no_site": int(sys.flags.no_site),
        "no_user_site": int(sys.flags.no_user_site),
        "dont_write_bytecode": int(sys.flags.dont_write_bytecode),
        "safe_path": bool(sys.flags.safe_path),
    }


def _validate_worker_bootstrap(runtime: Path) -> dict[str, Any]:
    expected_flags = {
        "isolated": 1,
        "ignore_environment": 1,
        "no_site": 1,
        "no_user_site": 1,
        "dont_write_bytecode": 1,
        "safe_path": True,
    }
    flags = _worker_flags()
    if flags != expected_flags:
        raise ImportPreflightError("worker_interpreter_flags_invalid")
    if Path.cwd().resolve() != runtime.resolve(strict=True):
        raise ImportPreflightError("worker_cwd_invalid")
    if dict(os.environ) != expected_worker_environment(runtime):
        raise ImportPreflightError("worker_environment_invalid")
    startup = [str(Path(value).resolve(strict=False)) for value in sys.path]
    if any("site-packages" in value for value in startup):
        raise ImportPreflightError("worker_site_packages_preloaded")
    if str(WORKSPACE_ROOT.resolve()) in startup:
        raise ImportPreflightError("worker_workspace_preloaded")
    return {"flags": flags, "startup_sys_path": startup}


def _load_release_attestation(path: Path) -> dict[str, Any]:
    source = Path(path)
    if source.resolve(strict=True) != RELEASE_ATTESTATION.resolve(strict=True):
        raise ImportPreflightError("release_attestation_path_invalid")
    if _sha256_bytes(source.read_bytes()) != EXPECTED_RELEASE_ATTESTATION_SHA256:
        raise ImportPreflightError("release_attestation_file_drift")
    payload = _read_json_mapping(source, "release_attestation")
    if set(payload) != RELEASE_ATTESTATION_FIELDS:
        raise ImportPreflightError("release_attestation_schema_invalid")
    return payload


def _module_identity(module: Any) -> str:
    value = getattr(module, "__file__", None)
    if not value:
        raise ImportPreflightError("production_module_file_missing")
    return str(Path(str(value)).resolve(strict=True))


def import_production_context_with_attestation(
    attestation: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]], bool]:
    production_path = str(PORTFOLIO_DIR.resolve(strict=True))
    if production_path not in sys.path:
        sys.path.insert(0, production_path)
    resolver = importlib.import_module("qmt_roll_official_strategy_material_resolver")
    original = resolver._assert_release_commit
    with release_commit_attestation_adapter(resolver, attestation) as calls:
        context = {
            "s901": importlib.import_module(
                "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow"
            ),
            "live_config": importlib.import_module("qmt_roll_official_live_config"),
            "contract_metadata": importlib.import_module("contract_metadata"),
            "portfolio_package": importlib.import_module("vnpy_portfoliostrategy"),
        }
    return context, calls, resolver._assert_release_commit is original


def run_worker_import_preflight(
    *,
    worker_id: str,
    worker_root: Path,
    runtime_root: Path,
    receipt_path: Path,
    external_probe_path: Path,
    attestation_path: Path,
) -> dict[str, Any]:
    if worker_id not in {"A1", "A2"}:
        raise ImportPreflightError("worker_id_invalid")
    root = Path(worker_root).resolve(strict=True)
    runtime = Path(runtime_root).resolve(strict=True)
    receipt = Path(receipt_path).resolve(strict=False)
    if runtime != root / "runtime" or receipt != root / "receipt.json":
        raise ImportPreflightError("worker_path_binding_invalid")
    bootstrap = _validate_worker_bootstrap(runtime)
    sandbox_probe = prove_external_write_denied(Path(external_probe_path))
    production_head = read_git_head_without_process(PRODUCTION_ROOT)
    if production_head != EXPECTED_PRODUCTION_HEAD:
        raise ImportPreflightError("production_head_drift")

    runtime_cache = runtime / f"mplconfig/fontlist-v{EXPECTED_FONT_MANAGER_VERSION}.json"
    cache_identity = validate_portable_font_cache(
        runtime_cache,
        expected_version=EXPECTED_FONT_MANAGER_VERSION,
        matplotlib_data_path=matplotlib_data_path(),
    )
    if cache_identity["sha256"] != EXPECTED_FONT_CACHE_SHA256:
        raise ImportPreflightError("font_cache_sha_drift")
    attestation = _load_release_attestation(Path(attestation_path))

    approved_paths = [str(python_site_packages()), str(WORKSPACE_ROOT.resolve(strict=True))]
    sys.path.extend(approved_paths)
    network = NetworkBlock()
    guard = SensitiveOperationGuard((root,))
    guard.assert_no_sensitive_modules_loaded()
    with network, guard:
        context, adapter_calls, adapter_restored = import_production_context_with_attestation(
            attestation
        )

    if network.attempts != 0:
        raise ImportPreflightError("worker_network_attempt_detected")
    if any(guard.counters.values()):
        raise ImportPreflightError("worker_sensitive_operation_detected")
    if len(adapter_calls) != 1 or not adapter_restored:
        raise ImportPreflightError("release_adapter_contract_failed")

    modules = {key: _module_identity(value) for key, value in context.items()}
    expected_modules = {
        "s901": str(
            (
                PORTFOLIO_DIR
                / "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py"
            ).resolve(strict=True)
        ),
        "live_config": str(
            (PORTFOLIO_DIR / "qmt_roll_official_live_config.py").resolve(strict=True)
        ),
        "contract_metadata": str(
            (PORTFOLIO_DIR / "contract_metadata.py").resolve(strict=True)
        ),
        "portfolio_package": str(
            (python_site_packages() / "vnpy_portfoliostrategy/__init__.py").resolve(
                strict=True
            )
        ),
    }
    if modules != expected_modules:
        raise ImportPreflightError("production_module_identity_mismatch")

    live_config = context["live_config"]
    formal_identity = {
        "official_live_version": str(live_config.OFFICIAL_LIVE_VERSION),
        "capital": float(live_config.OFFICIAL_LIVE_CAPITAL),
        "release_id": str(live_config.OFFICIAL_LIVE_MATERIAL_RELEASE_ID),
        "release_commit": str(live_config.OFFICIAL_LIVE_MATERIAL_RELEASE_COMMIT),
        "manifest_identity_sha256": str(
            live_config.OFFICIAL_LIVE_MATERIAL_MANIFEST_SHA256
        ),
        "strategy_version": str(
            live_config.OFFICIAL_LIVE_MATERIAL_STRATEGY_VERSION
        ),
    }
    expected_formal_identity = {
        "official_live_version": EXPECTED_OFFICIAL_VERSION,
        "capital": EXPECTED_CAPITAL,
        "release_id": EXPECTED_RELEASE_ID,
        "release_commit": EXPECTED_RELEASE_COMMIT,
        "manifest_identity_sha256": EXPECTED_MANIFEST_IDENTITY,
        "strategy_version": EXPECTED_STRATEGY_VERSION,
    }
    if formal_identity != expected_formal_identity:
        raise ImportPreflightError("formal_identity_mismatch")
    matplotlib_module = sys.modules.get("matplotlib")
    if str(getattr(matplotlib_module, "__version__", "")) != EXPECTED_MATPLOTLIB_VERSION:
        raise ImportPreflightError("matplotlib_version_mismatch")

    result = {
        "schema_version": 1,
        "status": "passed",
        "worker_id": worker_id,
        "pid": os.getpid(),
        "python_executable": str(Path(sys.executable).resolve(strict=True)),
        "python_version": sys.version,
        "bootstrap": bootstrap,
        "approved_sys_path": approved_paths,
        "runtime_root": str(runtime),
        "sandbox_probe": sandbox_probe,
        "font_cache": cache_identity,
        "release_attestation_sha256": EXPECTED_RELEASE_ATTESTATION_SHA256,
        "release_adapter_calls": adapter_calls,
        "release_adapter_restored": adapter_restored,
        "production_head": production_head,
        "modules": modules,
        "formal_identity": formal_identity,
        "sensitive_counters": guard.counters,
        "network_connection_attempt_count": network.attempts,
        "formal_replay_call_count": guard.counters["candidate_strategy_run_count"],
    }
    write_json_exclusive(receipt, result)
    return result


def portable_worker_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": receipt.get("schema_version"),
        "status": receipt.get("status"),
        "python_executable": receipt.get("python_executable"),
        "python_version": receipt.get("python_version"),
        "bootstrap": receipt.get("bootstrap"),
        "approved_sys_path": receipt.get("approved_sys_path"),
        "sandbox_write_denied": receipt.get("sandbox_probe", {}).get("write_denied"),
        "font_cache": receipt.get("font_cache"),
        "release_attestation_sha256": receipt.get("release_attestation_sha256"),
        "release_adapter_calls": receipt.get("release_adapter_calls"),
        "release_adapter_restored": receipt.get("release_adapter_restored"),
        "production_head": receipt.get("production_head"),
        "modules": receipt.get("modules"),
        "formal_identity": receipt.get("formal_identity"),
        "sensitive_counters": receipt.get("sensitive_counters"),
        "network_connection_attempt_count": receipt.get(
            "network_connection_attempt_count"
        ),
        "formal_replay_call_count": receipt.get("formal_replay_call_count"),
    }


def _worker_command(paths: Mapping[str, Path], worker_id: str, probe: Path) -> list[str]:
    return [
        str(SANDBOX_EXECUTABLE.resolve(strict=True)),
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
        str(probe),
        "--attestation-path",
        str(RELEASE_ATTESTATION.resolve(strict=True)),
    ]


def _run_cold_worker(output_root: Path, worker_id: str) -> dict[str, Any]:
    paths = prepare_worker_root(output_root / worker_id)
    if _sha256_bytes(paths["font_cache"].read_bytes()) != EXPECTED_FONT_CACHE_SHA256:
        raise ImportPreflightError("prepared_font_cache_sha_drift")
    write_sandbox_profile(paths["profile"], paths["worker_root"])
    probe = output_root / f".sandbox_probe_{worker_id}"
    if probe.exists():
        raise ImportPreflightError("sandbox_probe_preexists")
    with paths["log"].open("wb") as log:
        completed = subprocess.run(
            _worker_command(paths, worker_id, probe),
            cwd=paths["runtime"],
            env=expected_worker_environment(paths["runtime"]),
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
        log.flush()
        os.fsync(log.fileno())
    if completed.returncode != 0:
        failure = paths["receipt"].with_name("failure_receipt.json")
        detail = (
            failure.read_text(encoding="utf-8")
            if failure.is_file()
            else paths["log"].read_text(encoding="utf-8", errors="replace")
        )
        raise ImportPreflightError(
            f"worker_failed:{worker_id}:returncode={completed.returncode}:{detail[-4000:]}"
        )
    if not paths["receipt"].is_file():
        raise ImportPreflightError(f"worker_receipt_missing:{worker_id}")
    payload = _read_json_mapping(paths["receipt"], f"worker_{worker_id}_receipt")
    if payload.get("status") != "passed" or payload.get("worker_id") != worker_id:
        raise ImportPreflightError(f"worker_receipt_invalid:{worker_id}")
    return payload


def run_parent_import_preflight(output_dir: Path) -> dict[str, Any]:
    if not SANDBOX_EXECUTABLE.is_file():
        raise ImportPreflightError("sandbox_executable_missing")
    if _sha256_bytes(FONT_CACHE_FIXTURE.read_bytes()) != EXPECTED_FONT_CACHE_SHA256:
        raise ImportPreflightError("font_cache_fixture_drift")
    if _sha256_bytes(RELEASE_ATTESTATION.read_bytes()) != EXPECTED_RELEASE_ATTESTATION_SHA256:
        raise ImportPreflightError("release_attestation_fixture_drift")
    output = Path(output_dir).resolve(strict=False)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    receipts = [_run_cold_worker(output, worker_id) for worker_id in ("A1", "A2")]
    portable = [portable_worker_receipt(receipt) for receipt in receipts]
    counters = {
        key: sum(int(receipt["sensitive_counters"][key]) for receipt in receipts)
        for key in SENSITIVE_COUNTER_KEYS
    }
    summary = {
        "schema_version": 1,
        "status": "passed",
        "stage": "stage001_import_preflight",
        "line_id": "futures_trend_xgboost_formal_signal_marginal_utility_v2",
        "worker_count": len(receipts),
        "worker_ids": [str(receipt["worker_id"]) for receipt in receipts],
        "worker_pids_distinct": len({int(receipt["pid"]) for receipt in receipts})
        == len(receipts),
        "portable_receipts_equal": portable[0] == portable[1],
        "sensitive_counters": counters,
        "network_connection_attempt_count": sum(
            int(receipt["network_connection_attempt_count"]) for receipt in receipts
        ),
        "formal_replay_call_count": sum(
            int(receipt["formal_replay_call_count"]) for receipt in receipts
        ),
        "font_cache": receipts[0]["font_cache"],
        "formal_identity": receipts[0]["formal_identity"],
        "production_head": receipts[0]["production_head"],
        "release_attestation_sha256": EXPECTED_RELEASE_ATTESTATION_SHA256,
    }
    if (
        not summary["worker_pids_distinct"]
        or not summary["portable_receipts_equal"]
        or any(counters.values())
        or summary["network_connection_attempt_count"] != 0
        or summary["formal_replay_call_count"] != 0
    ):
        raise ImportPreflightError("parent_preflight_gate_failed")
    write_json_exclusive(output / "summary.json", summary)
    return summary


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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.run:
            if args.output_dir is None:
                raise ImportPreflightError("output_dir_required")
            summary = run_parent_import_preflight(args.output_dir)
            print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
            return 0
        required = {
            "worker_id": args.worker_id,
            "worker_root": args.worker_root,
            "runtime_root": args.runtime_root,
            "receipt_path": args.receipt_path,
            "external_probe_path": args.external_probe_path,
            "attestation_path": args.attestation_path,
        }
        if any(value is None for value in required.values()):
            raise ImportPreflightError("worker_arguments_incomplete")
        run_worker_import_preflight(
            worker_id=str(args.worker_id),
            worker_root=args.worker_root,
            runtime_root=args.runtime_root,
            receipt_path=args.receipt_path,
            external_probe_path=args.external_probe_path,
            attestation_path=args.attestation_path,
        )
        return 0
    except BaseException as exc:
        if args.worker and args.receipt_path is not None:
            failure_path = Path(args.receipt_path).with_name("failure_receipt.json")
            try:
                write_json_exclusive(
                    failure_path,
                    {
                        "schema_version": 1,
                        "status": "failed",
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
