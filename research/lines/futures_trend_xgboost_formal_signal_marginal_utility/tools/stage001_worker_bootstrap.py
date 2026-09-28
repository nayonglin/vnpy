from __future__ import annotations

import argparse
import errno
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


STAGE = "stage001_formal_event_feature_qualification"
LINE_ID = "futures_trend_xgboost_formal_signal_marginal_utility"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CAPABILITY_FIELDS = frozenset(
    {
        "schema_version",
        "stage",
        "line_id",
        "campaign_nonce",
        "lease_id",
        "worker_id",
        "capability_nonce",
        "attempt_dir",
        "runtime_root",
        "output_dir",
        "input_manifest_path",
        "input_manifest_sha256",
        "sandbox_executable_path",
        "sandbox_executable_sha256",
        "sandbox_policy_mode",
        "sandbox_profile_path",
        "sandbox_profile_sha256",
        "sandbox_probe_path",
        "bootstrap_path",
        "bootstrap_sha256",
        "runner_path",
        "runner_sha256",
        "python_executable",
        "isolated_startup_sys_path",
        "approved_sys_path",
        "worker_environment",
        "parent_channel_secret_sha256",
        "claim_path",
        "event_path",
        "issued_at",
        "replay_permitted",
    }
)
EXPECTED_INTERPRETER_FLAGS = {
    "isolated": 1,
    "ignore_environment": 1,
    "no_site": 1,
    "no_user_site": 1,
    "safe_path": True,
    "dont_write_bytecode": 1,
}


class Stage001BootstrapError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_json_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_capability(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Stage001BootstrapError("bootstrap_capability_unreadable") from exc
    if not isinstance(payload, Mapping) or set(payload) != CAPABILITY_FIELDS:
        raise Stage001BootstrapError("bootstrap_capability_schema_invalid")
    return dict(payload)


def _interpreter_flags() -> dict[str, Any]:
    return {
        "isolated": int(sys.flags.isolated),
        "ignore_environment": int(sys.flags.ignore_environment),
        "no_site": int(sys.flags.no_site),
        "no_user_site": int(sys.flags.no_user_site),
        "safe_path": bool(sys.flags.safe_path),
        "dont_write_bytecode": int(sys.flags.dont_write_bytecode),
    }


def _read_parent_secret() -> str:
    raw = sys.stdin.buffer.readline(256)
    secret = raw.decode("ascii", errors="strict").strip()
    if HEX64.fullmatch(secret) is None:
        raise Stage001BootstrapError("bootstrap_parent_channel_secret_invalid")
    return secret


def _validate_bootstrap_inputs(
    args: argparse.Namespace,
    payload: Mapping[str, Any],
    parent_secret: str,
) -> dict[str, Any]:
    worker_id = str(args.worker)
    if (
        payload.get("schema_version") != 2
        or payload.get("stage") != STAGE
        or payload.get("line_id") != LINE_ID
        or payload.get("worker_id") != worker_id
        or payload.get("replay_permitted") is not False
        or HEX64.fullmatch(str(payload.get("campaign_nonce", ""))) is None
        or HEX64.fullmatch(str(payload.get("lease_id", ""))) is None
        or HEX64.fullmatch(str(payload.get("capability_nonce", ""))) is None
    ):
        raise Stage001BootstrapError("bootstrap_capability_identity_invalid")
    if hashlib.sha256(parent_secret.encode("ascii")).hexdigest() != payload.get(
        "parent_channel_secret_sha256"
    ):
        raise Stage001BootstrapError("bootstrap_parent_channel_secret_mismatch")

    capability = args.worker_capability.resolve(strict=True)
    attempt = Path(str(payload["attempt_dir"])).resolve(strict=True)
    worker_root = (attempt / "workers" / worker_id).resolve(strict=True)
    runtime = Path(str(payload["runtime_root"])).resolve(strict=True)
    output = Path(str(payload["output_dir"])).resolve(strict=False)
    manifest = Path(str(payload["input_manifest_path"])).resolve(strict=True)
    profile = Path(str(payload["sandbox_profile_path"])).resolve(strict=True)
    probe = Path(str(payload["sandbox_probe_path"])).resolve(strict=False)
    bootstrap = Path(str(payload["bootstrap_path"])).resolve(strict=True)
    runner = Path(str(payload["runner_path"])).resolve(strict=True)
    python = Path(str(payload["python_executable"])).resolve(strict=True)
    if capability != worker_root / "worker_capability.json":
        raise Stage001BootstrapError("bootstrap_capability_path_invalid")
    if args.runtime_root.resolve(strict=True) != runtime or runtime != worker_root / "runtime":
        raise Stage001BootstrapError("bootstrap_runtime_path_invalid")
    if args.worker_output.resolve(strict=False) != output or output != worker_root / "output":
        raise Stage001BootstrapError("bootstrap_output_path_invalid")
    if output.exists():
        raise Stage001BootstrapError("bootstrap_output_exists")
    if args.expected_manifest.resolve(strict=True) != manifest or manifest != (
        attempt / "input_manifest.json"
    ):
        raise Stage001BootstrapError("bootstrap_manifest_path_invalid")
    if _sha256(manifest) != payload.get("input_manifest_sha256"):
        raise Stage001BootstrapError("bootstrap_manifest_sha_drift")
    if profile != worker_root / "stage001.sb" or _sha256(profile) != payload.get(
        "sandbox_profile_sha256"
    ):
        raise Stage001BootstrapError("bootstrap_sandbox_profile_drift")
    if probe != attempt / f".sandbox_probe_{worker_id}" or probe.exists():
        raise Stage001BootstrapError("bootstrap_sandbox_probe_path_invalid")
    if bootstrap != Path(__file__).resolve() or _sha256(bootstrap) != payload.get(
        "bootstrap_sha256"
    ):
        raise Stage001BootstrapError("bootstrap_self_identity_drift")
    if _sha256(runner) != payload.get("runner_sha256"):
        raise Stage001BootstrapError("bootstrap_runner_identity_drift")
    if python != Path(sys.executable).resolve():
        raise Stage001BootstrapError("bootstrap_python_executable_drift")
    flags = _interpreter_flags()
    if flags != EXPECTED_INTERPRETER_FLAGS:
        raise Stage001BootstrapError("bootstrap_interpreter_flags_invalid")
    startup_sys_path = [str(value) for value in sys.path]
    if startup_sys_path != payload.get("isolated_startup_sys_path"):
        raise Stage001BootstrapError("bootstrap_startup_sys_path_drift")
    expected_environment = payload.get("worker_environment")
    if not isinstance(expected_environment, Mapping) or dict(os.environ) != dict(
        expected_environment
    ):
        raise Stage001BootstrapError("bootstrap_worker_environment_drift")
    approved_sys_path = payload.get("approved_sys_path")
    if not isinstance(approved_sys_path, list) or not approved_sys_path:
        raise Stage001BootstrapError("bootstrap_approved_sys_path_invalid")
    approved = [str(Path(str(value)).resolve(strict=True)) for value in approved_sys_path]
    if approved != approved_sys_path or len(set(approved)) != len(approved):
        raise Stage001BootstrapError("bootstrap_approved_sys_path_invalid")
    if any(value in startup_sys_path for value in approved):
        raise Stage001BootstrapError("bootstrap_approved_sys_path_not_disjoint")
    return {
        "attempt": attempt,
        "worker_root": worker_root,
        "runtime": runtime,
        "output": output,
        "manifest": manifest,
        "profile": profile,
        "probe": probe,
        "bootstrap": bootstrap,
        "runner": runner,
        "python": python,
        "flags": flags,
        "startup_sys_path": startup_sys_path,
        "approved_sys_path": approved,
    }


def _prove_external_write_denied(probe: Path) -> dict[str, Any]:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            probe,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except OSError as exc:
        if exc.errno not in {errno.EPERM, errno.EACCES}:
            raise Stage001BootstrapError(
                f"bootstrap_sandbox_probe_unexpected_errno:{exc.errno}"
            ) from exc
        return {
            "path": str(probe),
            "write_denied": True,
            "errno": int(exc.errno),
        }
    else:
        os.write(descriptor, b"sandbox-not-enforced\n")
        os.fsync(descriptor)
    finally:
        if descriptor is not None:
            os.close(descriptor)
    try:
        probe.unlink(missing_ok=True)
    finally:
        if probe.exists():
            raise Stage001BootstrapError("bootstrap_sandbox_probe_cleanup_failed")
    raise Stage001BootstrapError("bootstrap_sandbox_external_write_not_denied")


def _attestation(
    payload: Mapping[str, Any],
    validated: Mapping[str, Any],
    parent_secret: str,
    sandbox_probe: Mapping[str, Any],
) -> dict[str, Any]:
    forbidden_modules: list[str] = []
    approved_roots = [Path(value) for value in validated["approved_sys_path"]]
    startup_roots = [Path(value) for value in validated["startup_sys_path"]]
    for name, module in sorted(sys.modules.items()):
        file_value = getattr(module, "__file__", None)
        if not file_value:
            continue
        path = Path(str(file_value)).resolve(strict=False)
        if path == validated["bootstrap"]:
            continue
        under_approved = any(
            path == root or root in path.parents for root in approved_roots
        )
        under_startup = any(path == root or root in path.parents for root in startup_roots)
        if under_approved and not under_startup:
            forbidden_modules.append(str(name))
    if forbidden_modules:
        raise Stage001BootstrapError(
            "bootstrap_pre_import_module_boundary_violated:"
            + ",".join(forbidden_modules)
        )
    effective_sys_path = [
        *validated["startup_sys_path"],
        *validated["approved_sys_path"],
    ]
    return {
        "schema_version": 1,
        "attestation_type": "isolated_pre_import_sandbox_bootstrap",
        "stage": STAGE,
        "line_id": LINE_ID,
        "campaign_nonce": payload["campaign_nonce"],
        "lease_id": payload["lease_id"],
        "worker_id": payload["worker_id"],
        "capability_nonce": payload["capability_nonce"],
        "pid": os.getpid(),
        "python_executable": str(validated["python"]),
        "python_version": sys.version,
        "interpreter_flags": dict(validated["flags"]),
        "startup_sys_path": list(validated["startup_sys_path"]),
        "approved_sys_path": list(validated["approved_sys_path"]),
        "effective_sys_path": effective_sys_path,
        "pre_import_forbidden_modules": forbidden_modules,
        "worker_environment_sha256": _stable_json_sha256(dict(os.environ)),
        "parent_channel_secret_sha256": hashlib.sha256(
            parent_secret.encode("ascii")
        ).hexdigest(),
        "bootstrap_path": str(validated["bootstrap"]),
        "bootstrap_sha256": payload["bootstrap_sha256"],
        "runner_path": str(validated["runner"]),
        "runner_sha256": payload["runner_sha256"],
        "sandbox_probe": dict(sandbox_probe),
        "attested_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--worker", required=True, choices=("A1", "A2"))
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--worker-output", required=True, type=Path)
    parser.add_argument("--expected-manifest", required=True, type=Path)
    parser.add_argument("--worker-capability", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    parent_secret = _read_parent_secret()
    payload = _read_capability(args.worker_capability.resolve(strict=True))
    validated = _validate_bootstrap_inputs(args, payload, parent_secret)
    sandbox_probe = _prove_external_write_denied(validated["probe"])
    sys.path.extend(validated["approved_sys_path"])
    attestation = _attestation(payload, validated, parent_secret, sandbox_probe)
    if list(sys.path) != attestation["effective_sys_path"]:
        raise Stage001BootstrapError("bootstrap_effective_sys_path_drift")

    spec = importlib.util.spec_from_file_location(
        "stage001_formal_event_feature_qualification_worker",
        validated["runner"],
    )
    if spec is None or spec.loader is None:
        raise Stage001BootstrapError("bootstrap_runner_spec_invalid")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return int(
        runner._bootstrap_worker_main(
            args,
            parent_channel_secret=parent_secret,
            bootstrap_attestation=attestation,
        )
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Stage001BootstrapError as exc:
        print(f"{type(exc).__name__}:{exc}", file=sys.stderr)
        raise SystemExit(2) from exc
