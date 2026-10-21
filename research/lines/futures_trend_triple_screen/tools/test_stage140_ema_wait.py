"""一个组合反例：真实fixture进程身份＋request＋三代离线runtime。"""
from __future__ import annotations
from datetime import datetime
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
ROOT = LINE.parents[2]
WAIT = TOOLS / "stage140_ema_wait.py"
EVIDENCE = LINE / "outputs/stage146_ema_wait_integration"


def raw(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path):
    data = path.read_bytes()
    return dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def canonical(value):
    return hashlib.sha256(json.dumps({k: v for k, v in value.items() if k != "request_sha256"}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


from types import SimpleNamespace
import signal
import threading
import time
from unittest.mock import patch


def assert_invocation_tree_cleanup(case):
    tools = Path(__file__).resolve().parents[2] / 'tools'
    # Once embedded in the test module, TOOLS is supplied by that module.
    if not tools.is_dir():
        tools = Path(__file__).resolve().parent
    sys.path.insert(0, str(tools))
    wait = importlib.import_module('stage140_ema_wait')
    program = '''from pathlib import Path
from types import SimpleNamespace
import importlib, json, os, sys, time
sys.path.insert(0, sys.argv[sys.argv.index('--fixture-tools')+1])
w=importlib.import_module('stage140_ema_wait')
w.SOURCE=Path(__file__)
role=sys.argv[sys.argv.index('--role')+1]
folder=Path(sys.argv[sys.argv.index('--fixture-folder')+1])
mode=sys.argv[sys.argv.index('--fixture-mode')+1]
if role=='worker':
    (folder/'worker.json').write_text(json.dumps({'pid':os.getpid(),'pgid':os.getpgrp()}))
    n=0
    while True:
        n+=1
        (folder/'heartbeat').write_text(str(n))
        time.sleep(.03)
else:
    if mode=='nonzero':
        import threading
        threading.Timer(.7,lambda:os._exit(3)).start()
    owner=SimpleNamespace(path=folder/'owner.json',sha256='fixture-only')
    runtime={'manifest_path':str(folder/'runtime.json'),'manifest_sha256':'fixture-only'}
    w._invoke(owner,'worker',['--fixture-tools',str(Path(w.__file__).parent),'--fixture-folder',str(folder),'--fixture-mode',mode],runtime,30)
'''
    for mode in ('timeout', 'interrupt', 'nonzero'):
        with case.subTest(cleanup_mode=mode), tempfile.TemporaryDirectory(prefix='ema-tree-fixture-') as tmp:
            folder = Path(tmp)
            script = folder / 'fixture_process.py'
            script.write_text(program)
            owner = SimpleNamespace(path=folder/'owner.json', sha256='fixture-only')
            runtime = dict(manifest_path=str(folder/'runtime.json'), manifest_sha256='fixture-only')
            timer = None
            try:
                if mode == 'interrupt':
                    timer = threading.Timer(1.3, lambda: os.kill(os.getpid(), signal.SIGINT))
                    timer.start()
                expected = {'timeout': subprocess.TimeoutExpired, 'interrupt': KeyboardInterrupt, 'nonzero': ValueError}[mode]
                with patch.object(wait, 'SOURCE', script), case.assertRaises(expected):
                    wait._invoke(owner, 'provider', ['--fixture-tools', str(tools), '--fixture-folder', str(folder), '--fixture-mode', mode], runtime, 1.3 if mode=='timeout' else 5)
                if timer:
                    timer.cancel()
                    timer = None
                case.assertTrue((folder/'worker.json').is_file(), 'fixture worker must really start')
                first = (folder/'heartbeat').read_text()
                time.sleep(.18)
                second = (folder/'heartbeat').read_text()
                case.assertEqual(first, second, 'descendant heartbeat continued after '+mode)
            finally:
                if timer:
                    timer.cancel()
                identity = folder/'worker.json'
                if identity.exists():
                    pid = json.loads(identity.read_text())['pid']
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass


class EmaWaitIntegrationTest(unittest.TestCase):
    def test_owner_request_and_runtime_descendants(self):
        assert_invocation_tree_cleanup(self)
        self.assertTrue(WAIT.is_file(), "EMA-only typed owner and runtime wait adapter is not implemented")
        wait = importlib.import_module("stage140_ema_wait")
        checkpoint = importlib.import_module("stage140_ema_checkpoint")
        env = os.environ.copy()
        for key in ["PYTHONPATH", "STAGE109_MANIFEST", "STAGE109_MANIFEST_SHA256", "STAGE140_RUNTIME_MANIFEST", "STAGE140_RUNTIME_SHA256", *wait.ENDPOINTS]:
            env.pop(key, None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        with tempfile.TemporaryDirectory(prefix="stage146_fixture_") as temp:
            out = Path(temp).resolve() / "EMA_LIMIT" / "fixture_run"
            out.mkdir(parents=True)
            changed_source = out / "fixture_source.txt"
            changed_source.write_text("fixture source\n")
            source_paths = wait.required_sources() | {changed_source}
            source_bindings = {str(p): binding(p) for p in source_paths}
            fixture_identity = dict(account_id="EMA_LIMIT", mechanism_id="stage124_ema_limit_v1", attempt=1, fixture_only=True)
            review_path = out / "fixture_integration_review.json"
            review = dict(schema="stage140_ema_integration_review_v1", independent_review=True, fixture_only=True, p0_findings=0, p1_findings=0, source_bindings=source_bindings)
            review_sha = write(review_path, review)
            preflight = dict(schema="stage140_ema_preflight_v1", **fixture_identity, source_bindings=source_bindings, data_bindings={}, integration_review_path=str(review_path), integration_review_sha256=review_sha)
            preflight_path = out / "preflight_used.json"
            preflight_sha = write(preflight_path, preflight)
            ready_path = out / "fixture_readiness.json"
            readiness = dict(schema="stage140_ema_execution_readiness_v1", **fixture_identity, issued_by="fixture_only", financial_execution_authorized=False, fixture_execution_authorized=True, independent_integration_accepted=True,
                preflight_sha256=preflight_sha, source_bindings=source_bindings, data_bindings={}, integration_review_path=str(review_path), integration_review_sha256=review_sha,
                limits_decision=dict(action="inherit_original_limits", wait_seconds=1800, run_seconds=7200))
            readiness_sha = write(ready_path, readiness)
            command = [sys.executable, "-u", "-c", "import sys; print('fixture_child_ready',flush=True); sys.stdin.read()", "--run", "--preflight", str(preflight_path), "--preflight-sha256", preflight_sha, "--readiness", str(ready_path), "--readiness-sha256", readiness_sha, "--global-attempt", "12"]
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(process.stdout.readline().strip(), "fixture_child_ready")
                started_at = datetime.now().astimezone().isoformat()
                context = dict(schema="stage140_ema_run_context_v1", **fixture_identity, run_id="fixture_run", global_attempt=12, output_directory=str(out), started_at=started_at,
                    preflight_path=str(preflight_path), preflight_sha256=preflight_sha, preflight_bytes=preflight_path.stat().st_size,
                    readiness_path=str(ready_path), readiness_sha256=readiness_sha, readiness_bytes=ready_path.stat().st_size,
                    integration_review_path=str(review_path), integration_review_sha256=review_sha, integration_review_bytes=review_path.stat().st_size,
                    source_bindings=source_bindings, data_bindings={}, writer="stage140_ema_checkpoint.py", writer_source_sha256=binding(TOOLS / "stage140_ema_checkpoint.py")["sha256"])
                context_path = out / "run_context.json"
                context_sha = write(context_path, context)
                owner_path = out / "wait_owner.json"
                document = dict(schema="stage140_ema_owner_v1", **fixture_identity, run_id="fixture_run", global_attempt=12, account_output=str(out), wait_root=str(out / "data_wait"), run_started_at=started_at,
                    engine_pid=process.pid, process_identity=wait.process_identity(process.pid), runner_path=str(TOOLS / "stage140_run_ema_account.py"),
                    run_context_path=str(context_path), run_context_sha256=context_sha, run_context_bytes=context_path.stat().st_size,
                    preflight_path=str(preflight_path), preflight_sha256=preflight_sha, preflight_bytes=preflight_path.stat().st_size,
                    execution_readiness_path=str(ready_path), execution_readiness_sha256=readiness_sha, execution_readiness_bytes=ready_path.stat().st_size,
                    integration_review_path=str(review_path), integration_review_sha256=review_sha, integration_review_bytes=review_path.stat().st_size,
                    source_fingerprints={p: v["sha256"] for p, v in source_bindings.items()}, source_bindings=source_bindings)
                owner_sha = write(owner_path, document)
                owner = wait._load_owner(owner_path, owner_sha, allow_fixture=True)
                self.assertIsInstance(owner.asset, checkpoint.BoundAsset)
                owner.verify(require_production=False)
                with self.assertRaisesRegex(ValueError, "fixture"):
                    wait.load_owner(owner_path, owner_sha)
                with self.assertRaisesRegex(ValueError, "fixture"):
                    wait.drive(owner, batch_id="fixture_must_not_drive")
                run = checkpoint.EmaRun("fixture_run", 1, 12, out, started_at, True)
                with self.assertRaisesRegex(ValueError, "fixture"):
                    wait.observe_owner(run, engine_pid=process.pid, process_identity=document["process_identity"], readiness=checkpoint.BoundAsset(ready_path, readiness_sha, ready_path.stat().st_size), integration_review=checkpoint.BoundAsset(review_path, review_sha, review_path.stat().st_size))
                request = dict(schema="stage021_exact_execution_minute_request_v1", request_sequence=1, execution_trade_date="2024-12-18", active_orders=[], requirements=[], execution_policy="fixture_only_no_market_data")
                request["request_sha256"] = canonical(request)
                request_path = out / "data_wait" / ("request_" + request["request_sha256"]) / "request.json"
                request_sha = write(request_path, request)
                write(request_path.with_name("request_fingerprint.json"), dict(request_sha256=request["request_sha256"], request_file_sha256=request_sha, request_path=str(request_path)))
                audit_path = out / "data_wait/audit.json"
                audit = [dict(status="waiting_for_independent_data", request_sha256=request["request_sha256"], request_path=str(request_path), request_file_sha256=request_sha, started_at=started_at, wait_seconds_max=1800)]
                write(audit_path, audit)
                actual = wait.current_request(owner)
                self.assertIsInstance(actual, wait.ActualRequest)
                self.assertEqual(actual.digest, request["request_sha256"])
                self.assertEqual(actual.file_sha, request_sha)
                bad = dict(document, schema="stage087_off_owner_v1", account_id="B_OFF")
                bad_path = out / "old_owner.json"
                with self.assertRaises(ValueError):
                    wait._load_owner(bad_path, write(bad_path, bad), allow_fixture=True)
                bad = dict(document, run_id="another_run")
                with self.assertRaises(ValueError):
                    wait._load_owner(bad_path, write(bad_path, bad), allow_fixture=True)
                with self.assertRaises(ValueError):
                    wait._load_owner(owner_path, "0" * 64, allow_fixture=True)
                changed_source.write_text("poison\n")
                with self.assertRaises(ValueError):
                    owner.verify(require_production=False)
                changed_source.write_text("fixture source\n")
                request_path.write_text("{}\n")
                with self.assertRaises(ValueError):
                    wait.current_request(owner)
                write(request_path, request)
                audit[-1]["request_path"] = str(Path(temp) / "another_run/request.json")
                write(audit_path, audit)
                with self.assertRaises(ValueError):
                    wait.current_request(owner)
                audit[-1]["request_path"] = str(request_path)
                audit[-1]["started_at"] = "2020-01-01T00:00:00+08:00"
                write(audit_path, audit)
                with self.assertRaisesRegex(ValueError, "budget|expired"):
                    wait.current_request(owner)
                audit[-1]["started_at"] = started_at
                write(audit_path, audit)
                base = [sys.executable, str(WAIT), "--owner", str(owner_path), "--owner-sha256", owner_sha]
                for role in ["drive", "provider", "worker", "resolve"]:
                    result = subprocess.run([*base, "--role", role, "--batch-id", "fixture_reject"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
                    self.assertNotEqual(result.returncode, 0, role)
                    self.assertIn("fixture", result.stdout + result.stderr, role)
                command = [*base, "--role", "probe", "--fixture-only-probe"]
                result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=55)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout[-1500:])
                probe = json.loads(result.stdout.splitlines()[-1])
                generations = probe["generations"]
                self.assertEqual(len(generations), 3)
                self.assertEqual(len({row["pid"] for row in generations}), 3)
                for index, row in enumerate(generations):
                    self.assertEqual(row["generation"], index)
                    self.assertEqual(row["sdk_version"], "3.10.2")
                    self.assertEqual(row["sdk_package"], str(ROOT / ".py311/lib/python3.11/site-packages/tqsdk"))
                    self.assertTrue(row["numeric_runtime_is_frozen"])
                    self.assertTrue(row["original_version_endpoint_guard_passed"])
                    self.assertFalse(row["credentials_read"])
                    self.assertFalse(row["sdk_imported"])
                    self.assertEqual(row["network_calls"], 0)
                    self.assertTrue(row["fixture_only"])
                    self.assertEqual(set(row["numeric_modules"]), {"numpy", "pandas", "scipy", "sklearn", "joblib"})
                    self.assertTrue(all(item["file"].startswith(row["frozen_site"] + "/") for item in row["numeric_modules"].values()))
                    if index:
                        self.assertEqual(row["ppid"], generations[index - 1]["pid"])
                invalid_env = env.copy()
                invalid_env["TQ_MD_URL"] = "invalid://fixture_offline"
                rejected = subprocess.run(command, cwd=ROOT, env=invalid_env, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(rejected.returncode, 0)
                EVIDENCE.mkdir(parents=True, exist_ok=True)
                sidecars = []
                runtime_folder = Path(probe["manifest_path"]).parent
                for file in [runtime_folder / "manifest.json", runtime_folder / "probe_terminal.json", *sorted((runtime_folder / "interpreters").glob("*.json"))]:
                    destination = EVIDENCE / "fixture_runtime_sidecars" / runtime_folder.name / file.relative_to(runtime_folder)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(file.read_bytes())
                    sidecars.append(dict(path=str(destination), **binding(destination)))
                write(EVIDENCE / "finite_test_evidence.json", dict(schema="stage146_finite_fixture_test_v1", fixture_only=True, fixture_engine_pid=process.pid, owner_binding_passed=True, production_owner_and_provider_reject_fixture=True,
                    poison_rejections=["old_B", "cross_run", "wrong_owner_SHA", "source", "request_bytes", "cross_run_request_path", "expired_wait", "endpoint_override"], probe=probe,
                    archived_sidecars=sidecars, fixture_owner_snapshot=document, credentials_read=False, network_calls=0, provider_packets_created=0, financial_runs=0))
            finally:
                process.communicate(input="", timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
