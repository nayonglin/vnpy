"""Fixed EMA_LIMIT wait ownership and data/provider orchestration.

All entry imports are stdlib.  Old OFF owner/CLI APIs are never called.  Only
the frozen data primitives and original SDK workers/guards are reused.
"""
from __future__ import annotations
import argparse
import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib
from importlib import metadata
import inspect
import io
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import textwrap
import time
from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from stage140_ema_checkpoint import BoundAsset, EmaRun

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve()
TOOLS, LINE = SOURCE.parent, SOURCE.parent.parent
ROOT = LINE.parents[2]
ACCOUNT_ROOT = LINE / "outputs/stage140_ema_account/EMA_LIMIT"
RUNNER = TOOLS / "stage140_run_ema_account.py"
ACCOUNT_ID, MECHANISM_ID = "EMA_LIMIT", "stage124_ema_limit_v1"
OWNER_SCHEMA = "stage140_ema_owner_v1"
ENDPOINTS = ("TQ_AUTH_URL", "TQ_MD_URL", "TQ_INS_URL", "TQ_TD_URL")
SITE = ROOT / ".py311/lib/python3.11/site-packages"
NUMERIC = {"numpy": "numpy", "pandas": "pandas", "scipy": "scipy", "sklearn": "scikit-learn", "joblib": "joblib"}


def _types():
    import stage140_ema_checkpoint as checkpoint
    return checkpoint


def _raw(path):
    path = Path(path).absolute()
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("ema_wait_regular_unlinked_file_required:" + str(path))
    return path.read_bytes()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _binding(path):
    data = _raw(path)
    return dict(sha256=_sha(data), bytes=len(data))


def _asset(path):
    path = Path(path).absolute()
    row = _binding(path)
    return _types().BoundAsset(path, row["sha256"], row["bytes"])


def _read(path, digest, size=None):
    raw = _raw(path)
    if _sha(raw) != digest or (size is not None and len(raw) != size):
        raise ValueError("ema_wait_bound_bytes_changed:" + str(path))
    return raw


def _json(path, digest=None, size=None):
    return json.loads(_raw(path) if digest is None else _read(path, digest, size))


def _atomic(path, value, *, replace=False):
    path = Path(path)
    if path.exists() and not replace:
        raise FileExistsError("ema_wait_refuses_overwrite:" + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp." + str(os.getpid()))
    with temp.open("xb") as handle:
        handle.write(_json_bytes(value)); handle.flush(); os.fsync(handle.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def required_sources():
    names = ["stage140_ema_checkpoint.py", "stage140_run_ema_account.py", "stage021_blocking_data_gate.py", "stage022_run_c0_qualified_wait.py", "stage045_exact_request_resolver.py", "stage052_generic_daily_source_resolver.py", "stage041_exact_daily_request_provider.py", "stage051_generic_exact_daily_recovery.py", "stage087_off_data_scope.py", "stage087_off_data_provider.py", "stage109_provider_runtime_launcher.py"]
    return {SOURCE, *(TOOLS / name for name in names)}


def process_identity(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError("ema_wait_real_positive_PID_required")
    result = subprocess.run(["ps", "-ww", "-p", str(pid), "-o", "lstart=", "-o", "args="], capture_output=True, text=True, check=True)
    if not result.stdout.strip():
        raise ValueError("ema_wait_owner_process_not_live")
    return result.stdout.strip()


def _clock(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("ema_wait_aware_clock_required")
    return parsed.astimezone(timezone.utc)


def _age(value):
    elapsed = (datetime.now(timezone.utc) - _clock(value)).total_seconds()
    if elapsed < -1:
        raise ValueError("ema_wait_clock_in_future")
    return max(elapsed, 0.)


def _argument(tokens, name):
    found = [tokens[i + 1] for i, item in enumerate(tokens[:-1]) if item == name]
    found.extend(item.split("=", 1)[1] for item in tokens if item.startswith(name + "="))
    if len(found) != 1:
        raise ValueError("ema_wait_actual_argv_required:" + name)
    return found[0]


@dataclass(frozen=True)
class EmaOwner:
    asset: BoundAsset
    document: dict

    @property
    def path(self):
        return self.asset.path

    @property
    def sha256(self):
        return self.asset.sha256

    @property
    def fixture_only(self):
        return self.document.get("fixture_only") is True

    def verify(self, *, require_production=True):
        value = _json(self.asset.path, self.asset.sha256, self.asset.bytes)
        if value != self.document:
            raise ValueError("ema_wait_owner_document_changed")
        _verify_owner(value, self.asset.path, require_production=require_production)
        return value


def _verify_owner(d, path, *, require_production):
    fixture = d.get("fixture_only") is True
    if require_production and fixture:
        raise ValueError("fixture_owner_forbidden_on_production_EMA_wait")
    if (d.get("schema") != OWNER_SCHEMA or d.get("account_id") != ACCOUNT_ID or d.get("mechanism_id") != MECHANISM_ID or type(d.get("attempt")) is not int or d.get("attempt") != 1 or type(d.get("fixture_only")) is not bool):
        raise ValueError("ema_wait_fixed_namespace_schema_required")
    run_id = d.get("run_id", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id) or type(d.get("global_attempt")) is not int or d["global_attempt"] < 1:
        raise ValueError("ema_wait_run_identity_invalid")
    output = Path(d["account_output"])
    if not output.is_absolute() or Path(path) != output / "wait_owner.json" or Path(d["wait_root"]) != output / "data_wait" or (not fixture and output != ACCOUNT_ROOT / run_id):
        raise ValueError("ema_wait_owner_output_or_wait_root_mismatch")
    docs = {}
    for label in ("run_context", "preflight", "execution_readiness", "integration_review"):
        docs[label] = _json(d[label + "_path"], d[label + "_sha256"], d[label + "_bytes"])
    c, p, r, review = (docs[k] for k in ("run_context", "preflight", "execution_readiness", "integration_review"))
    if Path(d["run_context_path"]) != output / "run_context.json" or Path(d["preflight_path"]) != output / "preflight_used.json":
        raise ValueError("ema_wait_actual_context_path_mismatch")
    for doc, schema in ((c, "stage140_ema_run_context_v1"), (p, "stage140_ema_preflight_v1"), (r, "stage140_ema_execution_readiness_v1")):
        if doc.get("schema") != schema or any(doc.get(k) != d[k] for k in ("account_id", "mechanism_id", "attempt", "fixture_only")):
            raise ValueError("ema_wait_context_preflight_readiness_identity_mismatch")
    if any(c.get(k) != d[k] for k in ("run_id", "global_attempt")) or c.get("output_directory") != str(output) or c.get("started_at") != d["run_started_at"]:
        raise ValueError("ema_wait_context_run_or_clock_mismatch")
    _clock(d["run_started_at"])
    if c.get("writer") != "stage140_ema_checkpoint.py" or c.get("writer_source_sha256") != _binding(TOOLS / "stage140_ema_checkpoint.py")["sha256"]:
        raise ValueError("ema_wait_checkpoint_writer_changed")
    for context_label, owner_label in (("preflight", "preflight"), ("readiness", "execution_readiness"), ("integration_review", "integration_review")):
        if any(c.get(context_label + "_" + suffix) != d[owner_label + "_" + suffix] for suffix in ("path", "sha256", "bytes")):
            raise ValueError("ema_wait_context_bound_asset_mismatch")
    sources = p.get("source_bindings", {})
    if (c.get("source_bindings") != sources or c.get("data_bindings") != p.get("data_bindings") or r.get("source_bindings") != sources or r.get("data_bindings") != p.get("data_bindings") or d.get("source_bindings") != sources or d.get("source_fingerprints") != {k: v["sha256"] for k, v in sources.items()}):
        raise ValueError("ema_wait_source_or_data_closure_mismatch")
    if not {str(s) for s in required_sources()}.issubset(sources):
        raise ValueError("ema_wait_required_source_closure_missing")
    for source, row in sources.items():
        if _binding(Path(source)) != row:
            raise ValueError("ema_wait_source_changed:" + source)
    if (r.get("preflight_sha256") != d["preflight_sha256"] or r.get("independent_integration_accepted") is not True or r.get("limits_decision") != dict(action="inherit_original_limits", wait_seconds=1800, run_seconds=7200)):
        raise ValueError("ema_wait_readiness_binding_or_original_limits_missing")
    if any(r.get("integration_review_" + suffix) != d["integration_review_" + suffix] for suffix in ("path", "sha256")):
        raise ValueError("ema_wait_readiness_integration_review_mismatch")
    if any(d.get(key, []) != r.get(key, []) for key in ("cache_receipts", "cache_daily_packets")):
        raise ValueError("ema_wait_cache_not_signed_in_actual_readiness")
    if fixture:
        if r.get("issued_by") != "fixture_only" or r.get("fixture_execution_authorized") is not True or r.get("financial_execution_authorized") is not False:
            raise ValueError("ema_wait_fixture_cannot_be_financial_authorization")
    elif r.get("issued_by") != "root" or r.get("financial_execution_authorized") is not True:
        raise ValueError("ema_wait_actual_root_readiness_required")
    if (review.get("independent_review") is not True or review.get("p0_findings") != 0 or review.get("p1_findings") != 0 or review.get("fixture_only", False) != fixture):
        raise ValueError("ema_wait_independent_integration_review_required")
    reviewed = review.get("source_bindings", {})
    for source in (SOURCE, RUNNER, TOOLS / "stage140_ema_checkpoint.py"):
        if reviewed.get(str(source)) != sources[str(source)]:
            raise ValueError("ema_wait_new_sources_not_independently_reviewed")
    if process_identity(d["engine_pid"]) != d["process_identity"]:
        raise ValueError("ema_wait_owner_PID_start_or_argv_changed")
    tokens = shlex.split(d["process_identity"])
    if "--run" not in tokens or Path(d["runner_path"]) != RUNNER or (not fixture and not any(Path(t).absolute() == RUNNER for t in tokens if t.endswith(".py"))):
        raise ValueError("ema_wait_actual_EMA_runner_command_required")
    if _argument(tokens, "--preflight-sha256") != d["preflight_sha256"] or _argument(tokens, "--readiness-sha256") != d["execution_readiness_sha256"] or int(_argument(tokens, "--global-attempt")) != d["global_attempt"]:
        raise ValueError("ema_wait_actual_argv_binding_mismatch")
    actual_preflight = Path(_argument(tokens, "--preflight"))
    if not actual_preflight.is_absolute():
        actual_preflight = ROOT / actual_preflight
    _read(actual_preflight, d["preflight_sha256"], d["preflight_bytes"])
    if Path(_argument(tokens, "--readiness")).absolute() != Path(d["execution_readiness_path"]):
        raise ValueError("ema_wait_actual_argv_readiness_path_mismatch")


def _load_owner(path, digest, *, allow_fixture=False):
    asset = _asset(path)
    if asset.sha256 != digest:
        raise ValueError("ema_wait_owner_SHA_mismatch")
    owner = EmaOwner(asset, _json(asset.path, digest, asset.bytes))
    owner.verify(require_production=not allow_fixture)
    return owner


def load_owner(path: Path, digest: str) -> EmaOwner:
    return _load_owner(path, digest)


def observe_owner(run: EmaRun, *, engine_pid: int, process_identity: str, readiness: BoundAsset, integration_review: BoundAsset) -> BoundAsset:
    if not isinstance(run, _types().EmaRun) or run.fixture_only:
        raise ValueError("fixture_or_untyped_run_cannot_observe_production_owner")
    if not all(isinstance(a, _types().BoundAsset) for a in (readiness, integration_review)):
        raise ValueError("ema_wait_typed_BoundAsset_required")
    context_asset = _asset(run.output / "run_context.json")
    c = _json(context_asset.path, context_asset.sha256, context_asset.bytes)
    p = _json(c["preflight_path"], c["preflight_sha256"], c["preflight_bytes"])
    _read(readiness.path, readiness.sha256, readiness.bytes)
    _read(integration_review.path, integration_review.sha256, integration_review.bytes)
    d = dict(schema=OWNER_SCHEMA, account_id=ACCOUNT_ID, mechanism_id=MECHANISM_ID, attempt=run.attempt, run_id=run.run_id, global_attempt=run.global_attempt, fixture_only=False,
        account_output=str(run.output), wait_root=str(run.output / "data_wait"), run_started_at=run.started_at, engine_pid=engine_pid, process_identity=process_identity, runner_path=str(RUNNER),
        run_context_path=str(context_asset.path), run_context_sha256=context_asset.sha256, run_context_bytes=context_asset.bytes,
        preflight_path=c["preflight_path"], preflight_sha256=c["preflight_sha256"], preflight_bytes=c["preflight_bytes"],
        execution_readiness_path=str(readiness.path), execution_readiness_sha256=readiness.sha256, execution_readiness_bytes=readiness.bytes,
        integration_review_path=str(integration_review.path), integration_review_sha256=integration_review.sha256, integration_review_bytes=integration_review.bytes,
        source_bindings=p["source_bindings"], source_fingerprints={k: v["sha256"] for k, v in p["source_bindings"].items()})
    ready = _json(readiness.path, readiness.sha256, readiness.bytes)
    for key in ("cache_receipts", "cache_daily_packets"):
        if key in ready:
            d[key] = ready[key]
    path = run.output / "wait_owner.json"
    _verify_owner(d, path, require_production=True)
    _atomic(path, d)
    return _asset(path)


@dataclass(frozen=True)
class ActualRequest:
    request: dict
    path: Path
    file_sha: str
    digest: str
    wait: dict
    inputs: dict


def _canonical(request):
    return _sha(json.dumps({k: v for k, v in request.items() if k != "request_sha256"}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def _request(owner, path, digest):
    owner.verify(require_production=not owner.fixture_only)
    path, root = Path(path).absolute(), Path(owner.document["wait_root"])
    if path.name != "request.json" or path.parent.parent != root:
        raise ValueError("ema_wait_request_outside_current_run")
    request = _json(path, digest)
    canonical = request.get("request_sha256")
    if request.get("schema") != "stage021_exact_execution_minute_request_v1" or _canonical(request) != canonical or path.parent.name != "request_" + canonical:
        raise ValueError("ema_wait_actual_request_canonical_mismatch")
    fingerprint_path = path.with_name("request_fingerprint.json")
    expected = dict(request_path=str(path), request_file_sha256=digest, request_sha256=canonical)
    if _json(fingerprint_path) != expected:
        raise ValueError("ema_wait_request_fingerprint_changed")
    audit = _json(root / "audit.json")
    if not isinstance(audit, list) or not audit or any(audit[-1].get(k) != v for k, v in dict(status="waiting_for_independent_data", **expected).items()):
        raise ValueError("ema_wait_request_is_not_latest_wait")
    wait = audit[-1]
    if wait.get("wait_seconds_max") != 1800 or _age(wait["started_at"]) >= 1800 or _age(owner.document["run_started_at"]) >= 7200:
        raise ValueError("ema_wait_request_budget_expired")
    return ActualRequest(request, path, digest, canonical, wait, {str(path): digest, str(fingerprint_path): _binding(fingerprint_path)["sha256"]})


def current_request(owner: EmaOwner) -> ActualRequest | None:
    owner.verify(require_production=not owner.fixture_only)
    root = Path(owner.document["wait_root"])
    audit = _json(root / "audit.json")
    if not audit or audit[-1].get("status") != "waiting_for_independent_data":
        return None
    return _request(owner, audit[-1]["request_path"], audit[-1]["request_file_sha256"])


def _current(owner, current):
    if not isinstance(current, ActualRequest):
        raise ValueError("ema_wait_typed_actual_request_required")
    fresh = _request(owner, current.path, current.file_sha)
    if fresh.digest != current.digest or fresh.request != current.request or fresh.wait != current.wait:
        raise ValueError("ema_wait_request_changed_after_observation")
    return fresh


def _scope():
    import stage087_off_data_scope as scope
    return scope


def _deps():
    if not os.environ.get("STAGE140_RUNTIME_MANIFEST"):
        raise ValueError("ema_wait_descendant_runtime_bootstrap_required")
    return _scope().deps()


def _sdk():
    import stage109_provider_runtime_launcher as launcher
    return launcher


def _runtime_manifest(owner, *, probe_only):
    owner.verify(require_production=not probe_only)
    _sdk().endpoints()
    folder = Path(owner.document["account_output"]) / "data_runtime" / uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    owner_bindings = {str(owner.path): _binding(owner.path)}
    for label in ("run_context", "preflight", "execution_readiness", "integration_review"):
        owner_bindings[owner.document[label + "_path"]] = _binding(Path(owner.document[label + "_path"]))
    value = dict(schema="stage140_ema_runtime_manifest_v1", probe_only=probe_only, fixture_only=owner.fixture_only, owner_path=str(owner.path), owner_sha256=owner.sha256,
        owner_bindings=owner_bindings, source_bindings=owner.document["source_bindings"], sdk_identity=_sdk().sdk_identity(),
        credentials_read=False, network_calls=0, source_closure_includes_future_runtime_sidecars=False)
    path = folder / "manifest.json"
    _atomic(path, value)
    return dict(manifest_path=str(path), manifest_sha256=_binding(path)["sha256"], fixture_only=owner.fixture_only)


def bootstrap_runtime(owner: EmaOwner) -> dict:
    runtime = _runtime_manifest(owner, probe_only=False)
    os.environ.update(STAGE140_RUNTIME_MANIFEST=runtime["manifest_path"], STAGE140_RUNTIME_SHA256=runtime["manifest_sha256"])
    _bootstrap(Path(runtime["manifest_path"]), runtime["manifest_sha256"])
    return runtime


def _bootstrap(path, digest):
    value = _json(path, digest)
    if value.get("schema") != "stage140_ema_runtime_manifest_v1":
        raise ValueError("ema_wait_invalid_runtime_manifest")
    owner = _load_owner(value["owner_path"], value["owner_sha256"], allow_fixture=value.get("probe_only") is True)
    if Path(path).parent.parent != Path(owner.document["account_output"]) / "data_runtime" or value.get("fixture_only") != owner.fixture_only:
        raise ValueError("ema_wait_runtime_not_owned")
    for group in ("source_bindings", "owner_bindings"):
        for source, expected in value[group].items():
            if _binding(Path(source)) != expected:
                raise ValueError("ema_wait_runtime_source_or_owner_changed")
    if value["source_bindings"] != owner.document["source_bindings"]:
        raise ValueError("ema_wait_runtime_source_closure_changed")
    _sdk().endpoints()
    import stage022_run_c0_qualified_wait as runtime
    saved = runtime.OUTPUT
    folder = Path(path).parent / "runtime" / str(os.getpid())
    try:
        runtime.OUTPUT = folder
        runtime.configure_runtime(folder / "shared_empty")
    finally:
        runtime.OUTPUT = saved
    numeric = {}
    for name, dist_name in NUMERIC.items():
        module = importlib.import_module(name)
        selected = next(d for d in metadata.distributions(path=[str(runtime.FROZEN_SITE)]) if d.metadata["Name"].lower().replace("_", "-") == dist_name)
        source = Path(module.__file__).resolve()
        if not source.is_relative_to(runtime.FROZEN_SITE) or module.__version__ != selected.version:
            raise ValueError("ema_wait_numeric_runtime_changed:" + name)
        numeric[name] = dict(file=str(source), version=module.__version__)
    _scope().deps()
    if "tqsdk" in sys.modules:
        raise ValueError("ema_wait_sdk_imported_before_real_selection")
    sys.path[:] = [str(SITE), *[p for p in sys.path if p != str(SITE)]]
    if not _scope().numeric_runtime_is_frozen():
        raise ValueError("ema_wait_numeric_guard_false")
    sdk = _sdk().sdk_identity()
    if sdk != value["sdk_identity"]:
        raise ValueError("ema_wait_real_sdk_binding_changed")
    receipt = dict(schema="stage140_ema_interpreter_identity_v1", pid=os.getpid(), ppid=os.getppid(), argv=sys.argv, python_executable=sys.executable,
        owner_path=str(owner.path), owner_sha256=owner.sha256, manifest_path=str(path), manifest_sha256=digest, fixture_only=owner.fixture_only,
        numeric_modules=numeric, frozen_site=str(runtime.FROZEN_SITE), numeric_runtime_is_frozen=True, credentials_read=False, network_calls=0, **sdk)
    _atomic(Path(path).parent / "interpreters" / ("pid_" + str(os.getpid()) + ".json"), receipt)
    return receipt


def _environment(runtime):
    env = os.environ.copy()
    for key in ("PYTHONPATH", "STAGE109_MANIFEST", "STAGE109_MANIFEST_SHA256"):
        env.pop(key, None)
    env.update(PYTHONDONTWRITEBYTECODE="1", STAGE140_RUNTIME_MANIFEST=runtime["manifest_path"], STAGE140_RUNTIME_SHA256=runtime["manifest_sha256"])
    return env


def _invoke(owner, role, arguments, runtime, timeout):
    command = [sys.executable, str(SOURCE), "--role", role, "--owner", str(owner.path), "--owner-sha256", owner.sha256, *map(str, arguments)]
    # Workers and recursive probes stay inside their first parent's session.
    # Only the outer invocation owns the group and can reap the entire tree.
    nested = role == "worker" or (role == "probe" and int(_argument(list(map(str, arguments)), "--probe-generation")) > 0)
    owns_session = not nested
    process = subprocess.Popen(command, cwd=ROOT, env=_environment(runtime), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=owns_session)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    finally:
        # Also reap descendants after a nonzero or successful parent exit.
        # A completed parent may have left children holding other pipes.
        try:
            if owns_session:
                os.killpg(process.pid, signal.SIGKILL)
            elif process.poll() is None:
                process.kill()
        except ProcessLookupError:
            pass
        process.wait()
        if process.stdout:process.stdout.close()
        if process.stderr:process.stderr.close()
    terminal = dict(subprocess_pid=process.pid, subprocess_returncode=process.returncode, terminal_observed=True)
    if process.returncode:
        error = ValueError("ema_wait_child_failed:" + str(process.returncode) + ":" + stdout[-700:] + stderr[-300:])
        error.terminal = terminal
        raise error
    lines = [line for line in stdout.splitlines() if line.strip()]
    return (json.loads(lines[-1]) if lines else {}), terminal


def _probe(owner, generation, runtime):
    receipt = _json(Path(runtime["manifest_path"]).parent / "interpreters" / ("pid_" + str(os.getpid()) + ".json"))
    import stage087_off_data_provider as provider
    lines, first = inspect.getsourcelines(provider.sdk_preflight)
    tree = ast.parse(textwrap.dedent("".join(lines)))
    stop_line = first + next(node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "load_credentials") - 1
    class BeforeCredentials(Exception):
        pass
    def trace(frame, event, arg):
        if frame.f_code is provider.sdk_preflight.__code__ and event == "line" and frame.f_lineno == stop_line:
            raise BeforeCredentials
        return trace
    previous, passed = sys.gettrace(), False
    try:
        sys.settrace(trace)
        try:
            provider.sdk_preflight(_scope().Bindings())
        except BeforeCredentials:
            passed = True
    finally:
        sys.settrace(previous)
    if not passed:
        raise ValueError("ema_wait_original_sdk_guard_not_observed")
    receipt.update(generation=generation, original_version_endpoint_guard_passed=True, full_sdk_preflight_completed=False)
    _atomic(Path(runtime["manifest_path"]).parent / "interpreters" / ("probe_" + str(os.getpid()) + ".json"), receipt)
    rows = [receipt]
    if generation < 2:
        result, _ = _invoke(owner, "probe", ["--probe-generation", generation + 1, "--fixture-only-probe"] if owner.fixture_only else ["--probe-generation", generation + 1], runtime, 45)
        rows.extend(result["generations"])
    return dict(generations=rows)


def _folder(owner, current):
    return Path(owner.document["account_output"]) / "data_scope" / ("request_" + current.digest)


def _bound_inputs(owner, current, b):
    _current(owner, current)
    b.bind(owner.path, owner.sha256)
    for label in ("run_context", "preflight", "execution_readiness", "integration_review"):
        b.bind(owner.document[label + "_path"], owner.document[label + "_sha256"])
    for source, digest in owner.document["source_fingerprints"].items():
        b.bind(source, digest)
    for source, digest in current.inputs.items():
        b.bind(source, digest)


def _gate_parse(current, path, digest):
    d = _deps()
    return d.gate._read_delivery(current.request, d.gate.QualifiedDelivery(Path(path), digest))


def _sign(owner, current, frames, checks, proofs, b):
    d = _deps()
    _bound_inputs(owner, current, b)
    data, accepted = d.generic.assemble_delivery(current.request, frames)
    existing, new = d.generic.request_key_scope(current.request)
    added = data.loc[[(str(r.vt_symbol), d.pd.Timestamp(r.bar_datetime)) in new for r in data.itertuples(index=False)]]
    if len(added) != len(new):
        raise ValueError("ema_wait_exact_new_physical_keys_mismatch")
    old_manifest = b.json(d.old.OLD / "input_manifest.json", d.frozen.OLD_MANIFEST_SHA)
    mapping = b.csv(d.old.MAPPING, old_manifest[str(d.old.MAPPING.relative_to(ROOT))])
    calendar = d.pd.DatetimeIndex(d.pd.to_datetime(sorted(mapping.date.unique())))
    disjoint = d.old.prove_read_disjointness(added,
        b.csv(d.old.A0 / "execution_anchor_requests.csv", "72b61783602257c16b1b8c0307b0da4221430204808fdc29f21124f7556fbb20"),
        b.csv(d.old.A0 / "minute_scan_requests.csv", "cedf3627a530985083839af071f997482dd417e3f2721ca21208b50b086a03ab"), calendar)
    if not disjoint["path_equivalent"] or disjoint["intersection_count"]:
        raise ValueError("ema_wait_new_keys_intersect_A0_reads")
    folder = _folder(owner, current) / "review"
    folder.mkdir(parents=True, exist_ok=False)
    data_path = folder / "delivery_minutes.csv"
    data.to_csv(data_path, index=False)
    b.bind(data_path)
    proof_path = folder / "completion_evidence.json"
    _atomic(proof_path, d.runtime.json_safe(proofs)); b.bind(proof_path)
    check_path = folder / "checks.json"
    _atomic(check_path, d.runtime.json_safe(dict(targets=checks, existing_keys=len(existing), new_keys=len(new), A0_disjointness=disjoint,
        old_value_comparison_delegated_to_actual021=True, commit_inheritance=False))); b.bind(check_path)
    b.unchanged()
    path = folder / "delivery_receipt.json"
    receipt = dict(schema=d.gate.RECEIPT_SCHEMA, independent_review=True, reviewer="stage140_ema_independent_exact_scope_reader", reviewer_pid=os.getpid(),
        qualified_research_data=True, p0_findings=0, p1_findings=0, p2_findings=0, request_sha256=current.digest, accepted_requirements=accepted,
        data_path=str(data_path), data_sha256=b.inputs[str(data_path)], source_fingerprints=b.inputs, owner_account_id=ACCOUNT_ID,
        owner_mechanism_id=MECHANISM_ID, owner_run_id=owner.document["run_id"], owner_sha256=owner.sha256, fixture_only=False,
        financial_replays=0, model_fits=0, network_connections_in_review=0, orders=0, response_written=False, production_qualified=False)
    _atomic(path, receipt)
    digest = _binding(path)["sha256"]
    _gate_parse(current, path, digest)
    result = dict(status="accepted", request_sha256=current.digest, receipt_path=str(path), receipt_sha256=digest,
        actual_stage021_parser_passed=True, fixture_only=False, response_written=False)
    _atomic(folder / "parse_result.json", result)
    return result


def _cached_minutes(owner, current, b):
    """Inherit only root-listed independent exact rights, never a physical raw row."""
    d = _deps(); cached = []
    allowed = [LINE / "outputs" / name for name in ("stage052_generic_daily_source_resolver", "stage048_general_provider_delivery", "stage043_exact_request_delivery", "stage046_original_provider_delivery", "stage087_off_data_scope", "stage140_ema_account")]
    trusted = {str(TOOLS / "stage052_generic_daily_source_resolver.py"): "5b2772c700f0ddabb5536df4be1bfe1f70e07d8fea43400abfa74c66ae727b78",
        str(TOOLS / "stage048_general_provider_delivery.py"): "3b220aadeb1e8091a35d84624b643c3a0b276c6e3f4be9874293a9abaecd785a",
        str(TOOLS / "stage046_original_provider_delivery.py"): "d0c1fb55b681ad3113a215cba1964e84eaff7c617875ef71ec27f9db018fe65b",
        str(LINE / "outputs/stage043_exact_request_delivery/review_provider_delivery.py"): "373493d9eb50647063044e53c2c669584f237345cf2a8edf8f5d0d282c1b1d54",
        str(TOOLS / "stage087_off_data_scope.py"): owner.document["source_fingerprints"][str(TOOLS / "stage087_off_data_scope.py")], str(SOURCE): owner.document["source_fingerprints"][str(SOURCE)]}
    for row in owner.document.get("cache_receipts", []):
        path = Path(row["receipt_path"]).absolute()
        if not any(path.is_relative_to(root) for root in allowed):
            raise ValueError("ema_wait_cache_not_root_whitelisted")
        receipt = b.json(path, row["receipt_sha256"])
        if receipt.get("fixture_only") is True:
            raise ValueError("ema_wait_fixture_cache_not_market_data")
        sources = receipt.get("source_fingerprints", {})
        if not any(sources.get(source) == digest for source, digest in trusted.items()):
            raise ValueError("ema_wait_cached_independent_reader_not_accepted")
        origins = []
        for source, digest in sources.items():
            b.bind(source, digest)
            if Path(source).name == "request.json":
                candidate = b.json(source, digest)
                if candidate.get("request_sha256") == receipt.get("request_sha256"):
                    origins.append(candidate)
        if len(origins) != 1 or _canonical(origins[0]) != origins[0]["request_sha256"]:
            raise ValueError("ema_wait_cached_original_request_not_unique")
        data, full, anchor, _ = d.gate._read_delivery(origins[0], d.gate.QualifiedDelivery(path, row["receipt_sha256"]))
        cached.append(dict(data=data, full=full, anchor=anchor, receipt=str(path)))
    return cached


def _contexts(owner, current, b):
    d = _deps(); f = d.frozen
    old_manifest = b.json(d.old.OLD / "input_manifest.json", f.OLD_MANIFEST_SHA)
    mapping = b.csv(d.old.MAPPING, old_manifest[str(d.old.MAPPING.relative_to(ROOT))])
    calendar = d.pd.DatetimeIndex(d.pd.to_datetime(sorted(mapping.date.unique())))
    targets, info = d.minute.packet_targets(current.request, calendar, 0)
    if not info["covers_whole_request"] or not 1 <= len(targets) <= 8:
        raise ValueError("ema_wait_one_to_eight_actual_targets_required")
    review = b.json(f.R013, f.R013_SHA)
    approved = f.daily013.approved_references(b.csv(review["qualified_daily_path"], review["source_fingerprints"][review["qualified_daily_path"]]),
        b.csv(review["target_qualification_path"], review["source_fingerprints"][review["target_qualification_path"]]), review)
    rejected = {(r["vt_symbol"], r["trade_date"]) for r in review["rejected_targets"]}
    contexts, missing = [], []
    for target in targets:
        symbol, day, kind = (target[k] for k in ("vt_symbol", "execution_trade_date", "requirement_kind"))
        native, exchange = symbol.rsplit(".", 1)
        path = d.old.PROJECT / "downloaded_futures/tqsdk_daily_2010_2026_04" / exchange / (native + ".csv")
        original = b.csv(path, old_manifest.get(str(path.relative_to(ROOT)))) if path.exists() else None
        try:
            daily, source = d.minute.choose_daily_reference(symbol, day, kind, original, approved, rejected)
        except ValueError as error:
            if str(error) != "qualified_daily_reference_missing":
                raise
            try:
                daily, _, _, _ = d.generic.recover_daily(b, symbol, day, review, current.request)
                source = "inherited_independent_exact_daily_source"
            except f.NeedRaw as error:
                if str(error) not in {"no_bound_daily_raw_for_actual_symbol", "bound_daily_raw_has_no_actual_target_day", "no_completed_bound_stage051_snapshot_for_actual_symbol"}:
                    raise
                try:
                    daily = _cached_daily(owner, current, symbol, day, b)
                    source = "root_listed_completed_daily_raw_independently_read"
                except f.NeedRaw:
                    missing.append(symbol); continue
        contexts.append(dict(target=target, daily=daily, daily_reference_source=source, grid=d.old.session_grid(symbol, day, calendar)))
    return contexts, sorted(missing), info


def _cached_daily(owner, current, symbol, day, b):
    """Read closed, explicitly accepted packet evidence without an old owner API."""
    d = _deps(); native, exchange = symbol.rsplit(".", 1)
    exact = _folder(owner, current) / "daily_packet"
    candidates = []
    if exact.exists():
        if not (exact / "terminal_observed.json").exists():
            raise ValueError("ema_wait_current_daily_packet_without_true_terminal")
        candidates.append(dict(packet_dir=str(exact), terminal_sha256=_binding(exact / "terminal_observed.json")["sha256"]))
    else:
        candidates.extend(owner.document.get("cache_daily_packets", []))
        for packet in sorted((Path(owner.document["account_output"]) / "data_scope").glob("request_*/daily_packet")):
            if (packet / "terminal_observed.json").exists():
                candidates.append(dict(packet_dir=str(packet), terminal_sha256=_binding(packet / "terminal_observed.json")["sha256"]))
    found = []
    for item in candidates:
        packet = Path(item["packet_dir"]).absolute()
        if not any(packet.is_relative_to(root) for root in (LINE / "outputs/stage087_off_data_scope", ACCOUNT_ROOT)):
            raise ValueError("ema_wait_daily_cache_outside_root_whitelist")
        terminal = b.json(packet / "terminal_observed.json", item["terminal_sha256"])
        manifest = b.json(packet / "packet_manifest.json")
        if manifest.get("family") != "daily" or manifest.get("fixture_only") is not False:
            raise ValueError("ema_wait_daily_cache_actual_ordinary_packet_required")
        if not any(r["vt_symbol"] == symbol for r in manifest.get("daily_targets", [])):
            continue
        old = manifest.get("schema") == "stage087_provider_packet_v1"
        if not old and manifest.get("schema") != "stage140_ema_provider_packet_v1":
            raise ValueError("ema_wait_unknown_daily_cache_source_family")
        expected_terminal = "stage087_provider_actual_tool_terminal_v1" if old else "stage140_ema_provider_actual_terminal_v1"
        driver = TOOLS / "stage087_off_data_scope.py" if old else SOURCE
        if (terminal.get("schema") != expected_terminal or terminal.get("terminal_observed") is not True or terminal.get("subprocess_returncode") != 0 or terminal.get("exit_code") != 0 or terminal.get("request_sha256") != manifest.get("request_sha256") or terminal.get("owner_sha256") != manifest.get("owner_sha256") or terminal.get("new_provider_connections") != 1 or terminal.get("new_daily_provider_connections") != 1 or terminal.get("new_minute_provider_connections") != 0 or terminal.get("provider_source_sha256") != owner.document["source_fingerprints"][str(TOOLS / "stage087_off_data_provider.py")]):
            raise ValueError("ema_wait_cached_daily_terminal_identity_mismatch")
        if old and terminal.get("driver_source_sha256") != owner.document["source_fingerprints"][str(driver)]:
            raise ValueError("ema_wait_cached_daily_unreviewed_reader")
        preflight = b.json(packet / "preflight.json", terminal["preflight_sha256"])
        for source, digest in preflight["source_fingerprints"].items():
            b.bind(source, digest)
        origin = b.json(manifest["request_path"], manifest["request_file_sha256"])
        if _canonical(origin) != manifest["request_sha256"]:
            raise ValueError("ema_wait_cached_daily_origin_request_changed")
        parent = b.json(packet / "network_attempt1/parent_receipt.json", terminal["parent_receipt_sha256"])
        if (parent.get("status") != "worker_terminal" or parent.get("exit_code") != 0 or parent.get("hard_kill") is not False or parent.get("all_inputs_unchanged") is not True or parent.get("automatic_retry") is not False or parent.get("elapsed_seconds", 601) >= 600 or parent.get("owner_sha256") != manifest["owner_sha256"] or parent.get("request_sha256") != manifest["request_sha256"] or parent.get("preflight_sha256") != terminal["preflight_sha256"]):
            raise ValueError("ema_wait_cached_daily_parent_not_true_zero")
        for name, digest in parent["artifact_sha256"].items():
            b.bind(packet / "network_attempt1" / name, digest)
        worker = b.json(packet / "network_attempt1/worker_receipt.json")
        if (worker.get("status") != "completed_all_targets_qualified" or worker.get("accepted") is not True or worker.get("provider_connections_attempted") != 1 or worker.get("TqSim_created") is not True or worker.get("owner_sha256") != manifest["owner_sha256"] or worker.get("request_sha256") != manifest["request_sha256"] or worker.get("independent_review_signed") is not False or worker.get("response_written") is not False):
            raise ValueError("ema_wait_cached_daily_worker_not_exact_success")
        raw_path = packet / "network_attempt1/raw" / exchange / (native + ".csv")
        raw = b.csv(raw_path)
        if not any(d.frozen.legal(r) and d.frozen.local_ns(d.frozen.integer(r["datetime"])).date().isoformat() == day for r in raw.to_dict("records")):
            continue
        b.bind(d.daily.DATABASE, d.daily.DB_SHA)
        daily, _, _, _ = d.generic.ordinary_raw_evidence(raw.to_dict("records"), symbol, day, _scope().query_daily_six(symbol, day))
        found.append((b.inputs[str(raw_path)], daily))
    if not found:
        raise d.frozen.NeedRaw("no_completed_root_listed_daily_packet_for_actual_target")
    if len({h for h, _ in found}) != 1:
        raise ValueError("ema_wait_cached_daily_snapshot_SHA_conflict")
    return found[0][1]


def resolve(owner: EmaOwner, current: ActualRequest) -> dict:
    owner.verify()
    _current(owner, current)
    d = _deps(); b = _scope().Bindings(); _bound_inputs(owner, current, b)
    existing = _folder(owner, current) / "review/parse_result.json"
    if existing.exists():
        result = b.json(existing)
        receipt = b.json(result["receipt_path"], result["receipt_sha256"])
        if receipt.get("owner_sha256") != owner.sha256 or receipt.get("request_sha256") != current.digest:
            raise ValueError("ema_wait_existing_review_identity_mismatch")
        for source, digest in receipt["source_fingerprints"].items():
            b.bind(source, digest)
        _gate_parse(current, result["receipt_path"], result["receipt_sha256"])
        return result
    contexts, missing, _ = _contexts(owner, current, b)
    if missing:
        return dict(status="needs_daily", family="daily", request_sha256=current.digest, symbols=missing)
    sources = {}
    for path, digest in d.frozen.SOURCE_MANIFESTS.items():
        inventory = b.json(path, digest)
        for row in inventory["sources"]:
            source = Path(row["path"])
            for context in contexts:
                symbol = context["target"]["vt_symbol"]; native, exchange = symbol.rsplit(".", 1)
                if source.name != native + "_completed_minute_backtest.csv" or source.parent.name != exchange:
                    continue
                if row.get("status") not in {None, "accepted_source_bytes"}:
                    raise ValueError("ema_wait_local_source_not_accepted")
                frame, check = d.local.read_bound_minute_source(source, row["sha256"], symbol)
                if frame is None:
                    raise ValueError("ema_wait_bound_local_source_unusable:" + str(check))
                b.bind(source, row["sha256"]); sources.setdefault(symbol, []).append(frame)
    cached = _cached_minutes(owner, current, b)
    frames, checks, proof_rows = {}, [], []
    for context in contexts:
        target = context["target"]; symbol, kind = target["vt_symbol"], target["requirement_kind"]
        required = context["grid"] if kind == "full_session" else context["grid"][:1]
        parts, completed = _scope()._raw_local_proofs(sources.get(symbol, []), required)
        for item in cached:
            allowed = item["full"] | item["anchor"] if kind == "anchor" else item["full"]
            chosen = item["data"].loc[[(str(r.vt_symbol), d.pd.Timestamp(r.bar_datetime)) in allowed and str(r.vt_symbol) == symbol and d.pd.Timestamp(r.bar_datetime) in required for r in item["data"].itertuples(index=False)]]
            if len(chosen):
                parts.append(chosen[d.gate.FIELDS]); completed.update(d.gate._keys(chosen))
        if not parts:
            continue
        frame = d.pd.concat(parts, ignore_index=True)
        duplicate = frame.loc[frame.bar_datetime.duplicated(keep=False)]
        if len(duplicate):
            groups = duplicate.groupby("bar_datetime")[d.old.VALUES]
            if not d.np.isclose(groups.min().to_numpy(), groups.max().to_numpy(), rtol=1e-12, atol=1e-8).all():
                raise ValueError("ema_wait_completed_source_conflict")
        frame = frame.drop_duplicates("bar_datetime").sort_values("bar_datetime")
        wanted = {(symbol, stamp) for stamp in required}
        if d.gate._keys(frame) != wanted or not wanted.issubset(completed):
            continue
        check = d.minute.qualify_target(frame, completed, dict(target, daily_reference=context["daily"]))
        if not check["accepted"]:
            raise ValueError("ema_wait_exact_local_daily_qualification_conflict:" + str(check))
        frames[(symbol, target["execution_trade_date"], kind)] = frame[d.gate.FIELDS]
        checks.append(check)
        proof_rows.extend(dict(vt_symbol=s, bar_datetime=t.isoformat(), completed=True) for s, t in wanted)
    if len(frames) == len(current.request["requirements"]):
        return _sign(owner, current, frames, checks, proof_rows, b)
    folder = _folder(owner, current); folder.mkdir(parents=True, exist_ok=True)
    path = folder / "daily_references.json"
    refs = dict(contexts=[dict(target=c["target"], daily=c["daily"], daily_reference_source=c["daily_reference_source"]) for c in contexts], source_fingerprints=b.inputs,
        owner_sha256=owner.sha256, request_sha256=current.digest)
    if path.exists():
        if _json(path) != refs:
            raise ValueError("ema_wait_daily_references_changed")
    else:
        _atomic(path, d.runtime.json_safe(refs))
    return dict(status="needs_provider", family="minute", request_sha256=current.digest, daily_references_path=str(path), daily_references_sha256=_binding(path)["sha256"])


def _prepare(owner, current, *, family, symbols=None, daily_references=None, references_sha=None):
    owner.verify(); _current(owner, current)
    d = _deps(); b = _scope().Bindings(); _bound_inputs(owner, current, b)
    if family not in {"daily", "minute"}:
        raise ValueError("ema_wait_daily_or_minute_packet_required")
    packet = _folder(owner, current) / (family + "_packet")
    if packet.exists():
        raise FileExistsError("ema_wait_one_packet_no_reprepare")
    manifest = dict(schema="stage140_ema_provider_packet_v1", family=family, packet_index=0, packet_count=1,
        owner_path=str(owner.path), owner_sha256=owner.sha256, request_path=str(current.path), request_file_sha256=current.file_sha, request_sha256=current.digest,
        fixture_only=False, independent_review_signed=False, response_written=False, financial_replays=0, orders=0)
    if family == "daily":
        _, missing, _ = _contexts(owner, current, b)
        if not symbols or len(set(symbols)) != len(symbols) or not set(symbols).issubset(missing):
            raise ValueError("ema_wait_only_actual_missing_daily_symbols")
        old_manifest = b.json(d.old.OLD / "input_manifest.json", d.frozen.OLD_MANIFEST_SHA)
        mapping = b.csv(d.old.MAPPING, old_manifest[str(d.old.MAPPING.relative_to(ROOT))])
        calendar = d.pd.DatetimeIndex(d.pd.to_datetime(sorted(mapping.date.unique())))
        targets = d.daily.database_targets(d.daily.select_requirements(current.request, symbols, calendar))
        manifest.update(daily_targets=targets.to_dict("records"), selected_symbols=sorted(symbols))
        b.bind(d.daily.DATABASE, d.daily.DB_SHA); b.bind(d.daily.FROZEN_013, d.daily.FROZEN_013_SHA)
    else:
        if Path(daily_references) != _folder(owner, current) / "daily_references.json":
            raise ValueError("ema_wait_daily_references_not_owned")
        refs = b.json(daily_references, references_sha)
        if refs["owner_sha256"] != owner.sha256 or refs["request_sha256"] != current.digest:
            raise ValueError("ema_wait_daily_reference_identity_changed")
        for source, digest in refs["source_fingerprints"].items():
            b.bind(source, digest)
        targets = [dict(c["target"], daily_reference=c["daily"]) for c in refs["contexts"]]
        if not 1 <= len(targets) <= 8:
            raise ValueError("ema_wait_packet_contract_limit")
        # Reuse the actual frozen session/start budget constructor.
        old_manifest = b.json(d.old.OLD / "input_manifest.json", d.frozen.OLD_MANIFEST_SHA)
        mapping = b.csv(d.old.MAPPING, old_manifest[str(d.old.MAPPING.relative_to(ROOT))])
        calendar = d.pd.DatetimeIndex(d.pd.to_datetime(sorted(mapping.date.unique())))
        canonical_targets, info = d.minute.packet_targets(current.request, calendar, 0)
        if [c["target"] for c in refs["contexts"]] != canonical_targets:
            raise ValueError("ema_wait_minute_actual_target_scope_mismatch")
        manifest.update(targets=targets, **info, daily_references_path=str(daily_references), daily_references_sha256=references_sha)
    import stage087_off_data_provider as provider
    sdk = provider.sdk_preflight(b)
    manifest["input_sha256"] = b.inputs
    packet.mkdir(parents=True, exist_ok=False)
    _atomic(packet / "packet_manifest.json", d.runtime.json_safe(manifest)); b.bind(packet / "packet_manifest.json")
    _atomic(packet / "preflight.json", dict(schema="stage140_ema_provider_preflight_v1", owner_sha256=owner.sha256, request_sha256=current.digest, family=family, source_fingerprints=b.inputs, **sdk))
    return dict(status="prepared_no_network", packet_dir=str(packet), request_sha256=current.digest)


def _read_packet(owner, current, packet, b):
    owner.verify(); _current(owner, current); packet = Path(packet)
    manifest = b.json(packet / "packet_manifest.json")
    preflight = b.json(packet / "preflight.json")
    if (manifest.get("schema") != "stage140_ema_provider_packet_v1" or manifest.get("fixture_only") is not False or
        manifest.get("owner_sha256") != owner.sha256 or manifest.get("request_sha256") != current.digest or
        packet != _folder(owner, current) / (manifest["family"] + "_packet") or preflight.get("schema") != "stage140_ema_provider_preflight_v1" or
        preflight.get("owner_sha256") != owner.sha256 or preflight.get("request_sha256") != current.digest):
        raise ValueError("ema_wait_provider_packet_identity_mismatch")
    for source, digest in preflight["source_fingerprints"].items():
        b.bind(source, digest)
    return manifest, preflight


def _remaining(owner, current):
    owner.verify(); _current(owner, current)
    return min(1800 - _age(current.wait["started_at"]), 7200 - _age(owner.document["run_started_at"]))


def _worker(owner, current, packet, parent_pid):
    owner.verify()
    if os.getppid() != parent_pid:
        raise ValueError("ema_wait_true_provider_parent_required")
    b = _scope().Bindings(); manifest, _ = _read_packet(owner, current, packet, b)
    attempt = Path(packet) / "network_attempt1"
    if not (attempt / "attempt_started.json").is_file():
        raise ValueError("ema_wait_durable_provider_attempt_required")
    import stage087_off_data_provider as provider
    provider.sdk_preflight(b)
    result = provider._daily_worker(manifest, attempt) if manifest["family"] == "daily" else provider._minute_worker(manifest, attempt)
    result.update(schema="stage140_ema_provider_worker_v1", worker_pid=os.getpid(), parent_pid=parent_pid, owner_sha256=owner.sha256, request_sha256=current.digest,
        automatic_retry=False, fixture_only=False, financial_replays=0, model_fits=0, orders=0, cancels=0, broker_or_ctp_connections=0,
        credential_values_saved=False, old_CSV_or_DB_written=False, independent_review_signed=False, response_written=False, production_qualified=False)
    _atomic(attempt / "worker_receipt.json", _deps().runtime.json_safe(result))
    if result.get("accepted") is not True:
        raise ValueError("ema_wait_provider_targets_failed")
    return dict(status=result["status"], accepted=True)


def _provider(owner, current, packet, runtime):
    owner.verify(); _current(owner, current)
    if _remaining(owner, current) < 840:
        raise ValueError("ema_wait_full_provider_reserve_unavailable")
    b = _scope().Bindings(); manifest, preflight = _read_packet(owner, current, packet, b)
    packet, began = Path(packet), time.monotonic()
    attempt = packet / "network_attempt1"
    if attempt.exists():
        raise FileExistsError("ema_wait_one_provider_attempt_no_retry")
    import stage087_off_data_provider as provider
    probe = _scope().Bindings(); provider.sdk_preflight(probe)
    if any(preflight["source_fingerprints"].get(p) != h for p, h in probe.inputs.items()):
        raise ValueError("ema_wait_sdk_preflight_drift")
    attempt.mkdir()
    _atomic(attempt / "attempt_started.json", dict(owner_sha256=owner.sha256, request_sha256=current.digest, provider_attempts_max=1, soft_seconds=570, hard_seconds=600, automatic_retry=False))
    killed, code, tool = False, -1, None
    try:
        _, tool = _invoke(owner, "worker", ["--request", current.path, "--request-file-sha256", current.file_sha, "--packet-dir", packet, "--parent-pid", os.getpid()], runtime, 600)
        code = tool["subprocess_returncode"]
    except subprocess.TimeoutExpired:
        killed, code = True, -9
    except ValueError as error:
        if hasattr(error, "terminal"):
            tool = error.terminal
            code = tool["subprocess_returncode"]
        raise
    finally:
        unchanged = all(_binding(Path(p))["sha256"] == h for p, h in preflight["source_fingerprints"].items())
        result = dict(schema="stage140_ema_provider_parent_v1", status="hard_timeout" if killed else "worker_terminal", exit_code=code, hard_kill=killed,
            all_inputs_unchanged=unchanged, elapsed_seconds=time.monotonic() - began, owner_sha256=owner.sha256, request_sha256=current.digest,
            preflight_sha256=_binding(packet / "preflight.json")["sha256"], provider_attempts_max=1, automatic_retry=False, parent_pid=os.getpid(),
            worker_tool_terminal=tool, financial_replays=0, model_fits=0, orders=0, cancels=0, broker_or_ctp_connections=0,
            credential_values_saved=False, old_CSV_or_DB_written=False, independent_review_signed=False, response_written=False,
            artifact_sha256={str(p.relative_to(attempt)): _binding(p)["sha256"] for p in attempt.rglob("*") if p.is_file()})
        _atomic(attempt / "parent_receipt.json", result)
    if code != 0 or not unchanged or result["elapsed_seconds"] >= 600:
        raise ValueError("ema_wait_provider_not_true_zero_within_original_budget")
    return dict(status="worker_terminal", exit_code=0, all_inputs_unchanged=True)


def _provider_evidence(owner, current, packet, b):
    manifest, preflight = _read_packet(owner, current, packet, b)
    terminal = b.json(Path(packet) / "terminal_observed.json")
    parent_path = Path(packet) / "network_attempt1/parent_receipt.json"
    parent = b.json(parent_path, terminal["parent_receipt_sha256"])
    if (terminal.get("schema") != "stage140_ema_provider_actual_terminal_v1" or terminal.get("terminal_observed") is not True or terminal.get("subprocess_returncode") != 0 or terminal.get("exit_code") != 0 or terminal.get("owner_sha256") != owner.sha256 or terminal.get("request_sha256") != current.digest or
        terminal.get("preflight_sha256") != b.inputs[str(Path(packet) / "preflight.json")] or parent.get("schema") != "stage140_ema_provider_parent_v1" or parent.get("status") != "worker_terminal" or parent.get("exit_code") != 0 or parent.get("hard_kill") is not False or parent.get("all_inputs_unchanged") is not True or parent.get("elapsed_seconds", 601) >= 600 or parent.get("automatic_retry") is not False or parent.get("owner_sha256") != owner.sha256 or parent.get("request_sha256") != current.digest):
        raise ValueError("ema_wait_true_parent_terminal_not_accepted")
    if (parent.get("preflight_sha256") != terminal["preflight_sha256"] or terminal.get("provider_source_sha256") != _binding(TOOLS / "stage087_off_data_provider.py")["sha256"] or
        terminal.get("driver_source_sha256") != owner.document["source_fingerprints"][str(SOURCE)] or terminal.get("new_provider_connections") != 1 or
        terminal.get("new_daily_provider_connections") != int(manifest["family"] == "daily") or terminal.get("new_minute_provider_connections") != int(manifest["family"] == "minute")):
        raise ValueError("ema_wait_provider_source_or_preflight_changed")
    for name, digest in parent["artifact_sha256"].items():
        b.bind(Path(packet) / "network_attempt1" / name, digest)
    worker = b.json(Path(packet) / "network_attempt1/worker_receipt.json")
    expected = "completed_all_targets_qualified" if manifest["family"] == "daily" else "all_target_minutes_completed"
    if (worker.get("schema") != "stage140_ema_provider_worker_v1" or worker.get("status") != expected or worker.get("accepted") is not True or worker.get("provider_connections_attempted") != 1 or worker.get("TqSim_created") is not True or worker.get("owner_sha256") != owner.sha256 or worker.get("request_sha256") != current.digest or worker.get("independent_review_signed") is not False or worker.get("response_written") is not False or worker.get("automatic_retry") is not False or any(worker.get(k) != 0 for k in ("financial_replays", "model_fits", "orders", "cancels", "broker_or_ctp_connections"))):
        raise ValueError("ema_wait_worker_exact_success_required")
    if worker.get("worker_pid") == os.getpid() or parent.get("parent_pid") == os.getpid():
        raise ValueError("ema_wait_provider_cannot_sign_own_independent_review")
    return manifest, parent


def _review(owner, current, packet, terminal_sha):
    d = _deps(); b = _scope().Bindings(); _bound_inputs(owner, current, b)
    b.bind(Path(packet) / "terminal_observed.json", terminal_sha)
    manifest, _ = _provider_evidence(owner, current, packet, b)
    if manifest["family"] != "minute":
        raise ValueError("ema_wait_021_delivery_requires_minute_packet")
    raw = d.old.normal_times(b.csv(Path(packet) / "network_attempt1/raw_completed_minutes.csv"))
    evidence = d.old.normal_times(b.csv(Path(packet) / "network_attempt1/completion_evidence.csv"))
    completed = _scope()._proofs(raw, evidence, network=True)
    expected = {(r["vt_symbol"], d.pd.Timestamp(t)) for r in current.request["requirements"] for t in r["required_timestamps"]}
    if d.gate._keys(raw) != expected or d.old.minute_keys(raw).has_duplicates:
        raise ValueError("ema_wait_provider_raw_not_exact_scope")
    refs = b.json(manifest["daily_references_path"], manifest["daily_references_sha256"])
    for source, digest in refs["source_fingerprints"].items():
        b.bind(source, digest)
    wanted = {(r["vt_symbol"], r["execution_trade_date"], r["requirement_kind"]): r for r in current.request["requirements"]}
    frames, checks = {}, []
    for context in refs["contexts"]:
        target = context["target"]; key = tuple(target[k] for k in ("vt_symbol", "execution_trade_date", "requirement_kind"))
        if wanted.get(key) != target:
            raise ValueError("ema_wait_daily_reference_scope_conflict")
        check = d.minute.qualify_target(raw, completed, dict(target, daily_reference=context["daily"]))
        if not check["accepted"]:
            raise ValueError("ema_wait_independent_minute_daily_qualification_failed")
        frames[key] = raw.loc[raw.vt_symbol.eq(key[0]) & raw.bar_datetime.isin(d.pd.to_datetime(target["required_timestamps"]))]
        checks.append(check)
    return _sign(owner, current, frames, checks, evidence.to_dict("records"), b)


def _publish(owner, current, result):
    _current(owner, current)
    path = Path(result["receipt_path"])
    if path != _folder(owner, current) / "review/delivery_receipt.json":
        raise ValueError("ema_wait_response_receipt_not_owned")
    receipt = _json(path, result["receipt_sha256"])
    if any(receipt.get(k) != v for k, v in dict(owner_sha256=owner.sha256, owner_run_id=owner.document["run_id"], owner_account_id=ACCOUNT_ID, owner_mechanism_id=MECHANISM_ID, fixture_only=False).items()):
        raise ValueError("ema_wait_receipt_owner_mismatch")
    for source, digest in receipt["source_fingerprints"].items():
        _read(source, digest)
    _gate_parse(current, path, result["receipt_sha256"])
    _current(owner, current)
    pointer = dict(schema="stage022_delivery_pointer_v1", request_sha256=current.digest, receipt_path=str(path), receipt_sha256=result["receipt_sha256"])
    response = current.path.with_name("response.json")
    if response.exists():
        if _json(response) != pointer:
            raise ValueError("ema_wait_existing_response_conflict")
    else:
        _atomic(response, pointer)
    return dict(response_path=str(response), response_sha256=_binding(response)["sha256"])


def drive(owner: EmaOwner, *, batch_id: str, max_connections: int = 4, budget_seconds: int = 3600) -> dict:
    owner.verify()
    if type(max_connections) is not int or not 1 <= max_connections <= 4 or not 840 <= budget_seconds <= 3600 or not re.fullmatch(r"[a-z0-9_-]+", batch_id):
        raise ValueError("ema_wait_original_bounded_batch_required")
    folder = Path(owner.document["account_output"]) / "data_scope/batches" / batch_id
    folder.mkdir(parents=True, exist_ok=False)
    runtime = bootstrap_runtime(owner)
    journal = dict(schema="stage140_ema_provider_batch_v1", owner_sha256=owner.sha256, provider_connections=0, max_provider_connections=max_connections, status="running", events=[], runtime=runtime)
    began = time.monotonic()
    def save():
        _atomic(folder / "journal.json", journal, replace=True)
    save()
    try:
        while time.monotonic() - began < budget_seconds:
            current = current_request(owner)
            if current is None:
                journal["status"] = "stopped_no_current_wait"; break
            if current.path.with_name("response.json").exists():
                time.sleep(.5); continue
            args = ["--request", current.path, "--request-file-sha256", current.file_sha]
            result, _ = _invoke(owner, "resolve", args, runtime, min(120, budget_seconds - (time.monotonic() - began)))
            if result.get("request_sha256") != current.digest:
                raise ValueError("ema_wait_resolver_wrong_request")
            if result["status"] == "accepted":
                _publish(owner, current, result); continue
            if result["status"] not in {"needs_daily", "needs_provider"}:
                raise ValueError("ema_wait_resolver_blocked")
            family = "daily" if result["status"] == "needs_daily" else "minute"
            packet = _folder(owner, current) / (family + "_packet")
            if packet.exists() and not (packet / "terminal_observed.json").exists():
                raise ValueError("ema_wait_existing_packet_no_terminal_no_retry")
            if not packet.exists():
                prepare = [*args, "--family", family]
                if family == "daily":
                    prepare += ["--symbols", *result["symbols"]]
                else:
                    prepare += ["--daily-references", result["daily_references_path"], "--daily-references-sha256", result["daily_references_sha256"]]
                _invoke(owner, "prepare", prepare, runtime, min(120, budget_seconds - (time.monotonic() - began)))
            if not (packet / "terminal_observed.json").exists():
                remaining = min(budget_seconds - (time.monotonic() - began), _remaining(owner, current))
                if remaining < 840 or journal["provider_connections"] >= max_connections:
                    journal["status"] = "stopped_budget_or_four_connections"; break
                journal["provider_connections"] += 1
                journal["events"].append(dict(request_sha256=current.digest, packet=str(packet), connection_reserved_durably=True))
                save()  # Never decrement: interruption consumes this reservation.
                _, tool = _invoke(owner, "provider", [*args, "--packet-dir", packet], runtime, min(660, remaining))
                b = _scope().Bindings(); parent_path = packet / "network_attempt1/parent_receipt.json"
                parent = b.json(parent_path)
                if parent.get("exit_code") != 0 or parent.get("all_inputs_unchanged") is not True or parent.get("hard_kill"):
                    raise ValueError("ema_wait_parent_terminal_failed")
                _atomic(packet / "terminal_observed.json", dict(schema="stage140_ema_provider_actual_terminal_v1", **tool, exit_code=0,
                    owner_sha256=owner.sha256, request_sha256=current.digest, parent_receipt_sha256=b.inputs[str(parent_path)],
                    preflight_sha256=_binding(packet / "preflight.json")["sha256"], provider_source_sha256=_binding(TOOLS / "stage087_off_data_provider.py")["sha256"],
                    driver_pid=os.getpid(), driver_source_sha256=owner.document["source_fingerprints"][str(SOURCE)], new_provider_connections=1, new_daily_provider_connections=int(family == "daily"), new_minute_provider_connections=int(family == "minute"), financial_replays=0, model_fits=0, orders=0))
            if family == "daily":
                continue
            result, _ = _invoke(owner, "review", [*args, "--packet-dir", packet, "--terminal-sha256", _binding(packet / "terminal_observed.json")["sha256"]], runtime, 120)
            _publish(owner, current, result)
            journal["events"].append(dict(request_sha256=current.digest, published=True)); save()
        else:
            journal["status"] = "stopped_batch_budget"
    except BaseException as error:
        journal.update(status="blocked", error_type=type(error).__name__, error=str(error)); save(); raise
    save()
    return journal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, choices=("resolve", "review", "drive", "prepare", "provider", "worker", "probe"))
    parser.add_argument("--owner", type=Path, required=True); parser.add_argument("--owner-sha256", required=True)
    parser.add_argument("--request", type=Path); parser.add_argument("--request-file-sha256")
    parser.add_argument("--batch-id"); parser.add_argument("--max-connections", type=int, default=4); parser.add_argument("--budget-seconds", type=int, default=3600)
    parser.add_argument("--family", choices=("daily", "minute")); parser.add_argument("--symbols", nargs="+")
    parser.add_argument("--daily-references", type=Path); parser.add_argument("--daily-references-sha256")
    parser.add_argument("--packet-dir", type=Path); parser.add_argument("--terminal-sha256"); parser.add_argument("--parent-pid", type=int)
    parser.add_argument("--fixture-only-probe", action="store_true"); parser.add_argument("--probe-generation", type=int, choices=range(3))
    args = parser.parse_args(argv)
    probing = args.role == "probe"
    if args.fixture_only_probe and not probing:
        raise ValueError("ema_wait_fixture_only_probe_cannot_run_provider")
    owner = _load_owner(args.owner, args.owner_sha256, allow_fixture=probing and args.fixture_only_probe)
    runtime_path, runtime_sha = os.environ.get("STAGE140_RUNTIME_MANIFEST"), os.environ.get("STAGE140_RUNTIME_SHA256")
    runtime = dict(manifest_path=runtime_path, manifest_sha256=runtime_sha) if runtime_path and runtime_sha else None
    if runtime is not None:
        identity = _bootstrap(Path(runtime_path), runtime_sha)
        if identity["owner_sha256"] != owner.sha256:
            raise ValueError("ema_wait_runtime_owner_argument_mismatch")
        manifest = _json(runtime_path, runtime_sha)
        if manifest["probe_only"] and not probing:
            raise ValueError("ema_wait_probe_runtime_cannot_launch_provider")
    if probing:
        if runtime is None:
            runtime = _runtime_manifest(owner, probe_only=True)
            result, terminal = _invoke(owner, "probe", ["--probe-generation", 0, "--fixture-only-probe"] if owner.fixture_only else ["--probe-generation", 0], runtime, 55)
            result.update(runtime, terminal=terminal)
            _atomic(Path(runtime["manifest_path"]).parent / "probe_terminal.json", result)
        else:
            if args.probe_generation is None:
                raise ValueError("ema_wait_probe_generation_required")
            result = _probe(owner, args.probe_generation, runtime)
    elif args.role == "drive":
        result = drive(owner, batch_id=args.batch_id, max_connections=args.max_connections, budget_seconds=args.budget_seconds)
    else:
        if runtime is None:
            raise ValueError("ema_wait_production_child_runtime_required")
        current = _request(owner, args.request, args.request_file_sha256)
        if args.role == "resolve":
            result = resolve(owner, current)
        elif args.role == "prepare":
            result = _prepare(owner, current, family=args.family, symbols=args.symbols, daily_references=args.daily_references, references_sha=args.daily_references_sha256)
        elif args.role == "provider":
            result = _provider(owner, current, args.packet_dir, runtime)
        elif args.role == "worker":
            result = _worker(owner, current, args.packet_dir, args.parent_pid)
        else:
            result = _review(owner, current, args.packet_dir, args.terminal_sha256)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps(dict(status="blocked", error_type=type(error).__name__, error=str(error), response_written=False), ensure_ascii=False))
        raise SystemExit(1)
