from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


LINE_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = LINE_ROOT / "tools/stage001_import_preflight.py"


@pytest.fixture()
def module():
    spec = importlib.util.spec_from_file_location("stage001_import_preflight_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git_blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _release_fixture(tmp_path: Path) -> tuple[Path, Path, str, dict[str, object]]:
    repo = tmp_path / "production"
    manifest_relative = "official_strategy_materials/strategy/releases/release-1/manifest.json"
    manifest = repo / manifest_relative
    manifest.parent.mkdir(parents=True)
    manifest_identity = "b" * 64
    manifest_bytes = (
        json.dumps(
            {"schema_version": 1, "manifest_sha256": manifest_identity},
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    manifest.write_bytes(manifest_bytes)

    current = repo / "official_strategy_materials/CURRENT.json"
    current_payload = {
        "schema_version": 1,
        "activation_mode": "active",
        "strategy_version": "strategy",
        "release_id": "release-1",
        "release_commit": "a" * 40,
        "manifest_sha256": manifest_identity,
    }
    current_bytes = (
        json.dumps(current_payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    )
    current.write_bytes(current_bytes)
    attestation = {
        "schema_version": 1,
        "repo_root": str(repo.resolve()),
        "current_relative_path": "official_strategy_materials/CURRENT.json",
        "current_sha256": _sha256_bytes(current_bytes),
        "manifest_relative_path": manifest_relative,
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "manifest_git_blob_oid": _git_blob_oid(manifest_bytes),
        "release_commit": "a" * 40,
        "release_id": "release-1",
        "strategy_version": "strategy",
        "manifest_identity_sha256": manifest_identity,
    }
    return repo, manifest, "a" * 40, attestation


def test_verify_release_commit_attestation_accepts_exact_bound_files(
    module,
    tmp_path,
) -> None:
    repo, manifest, release_commit, attestation = _release_fixture(tmp_path)

    observed = module.verify_release_commit_attestation(
        repo,
        manifest,
        release_commit,
        attestation,
    )

    assert observed == {
        "repo_root": str(repo.resolve()),
        "manifest_path": str(manifest.resolve()),
        "release_commit": "a" * 40,
        "manifest_sha256": attestation["manifest_sha256"],
        "manifest_git_blob_oid": attestation["manifest_git_blob_oid"],
    }


def test_release_commit_adapter_is_narrow_and_restores_original(module, tmp_path) -> None:
    repo, manifest, release_commit, attestation = _release_fixture(tmp_path)
    original_calls: list[tuple[object, ...]] = []

    def original(*args):
        original_calls.append(args)

    resolver = SimpleNamespace(_assert_release_commit=original)

    with module.release_commit_attestation_adapter(resolver, attestation) as calls:
        resolver._assert_release_commit(repo, manifest, release_commit)
        assert resolver._assert_release_commit is not original

    assert resolver._assert_release_commit is original
    assert original_calls == []
    assert calls == [
        {
            "repo_root": str(repo.resolve()),
            "manifest_path": str(manifest.resolve()),
            "release_commit": release_commit,
            "manifest_sha256": attestation["manifest_sha256"],
            "manifest_git_blob_oid": attestation["manifest_git_blob_oid"],
        }
    ]


def test_release_commit_adapter_restores_original_after_import_failure(module, tmp_path) -> None:
    _repo, _manifest, _release_commit, attestation = _release_fixture(tmp_path)

    def original(*_args):
        return None

    resolver = SimpleNamespace(_assert_release_commit=original)

    with pytest.raises(RuntimeError, match="import failed"):
        with module.release_commit_attestation_adapter(resolver, attestation):
            raise RuntimeError("import failed")

    assert resolver._assert_release_commit is original


def test_release_commit_attestation_rejects_manifest_drift(module, tmp_path) -> None:
    repo, manifest, release_commit, attestation = _release_fixture(tmp_path)
    manifest.write_bytes(manifest.read_bytes() + b"drift")

    with pytest.raises(module.ImportPreflightError, match="manifest_sha_mismatch"):
        module.verify_release_commit_attestation(
            repo,
            manifest,
            release_commit,
            attestation,
        )


def test_build_portable_font_cache_filters_host_fonts_and_validates_bundle(
    module,
    tmp_path,
) -> None:
    data_root = tmp_path / "mpl-data"
    (data_root / "fonts/ttf").mkdir(parents=True)
    (data_root / "fonts/afm").mkdir(parents=True)
    (data_root / "fonts/ttf/Alpha.ttf").write_bytes(b"alpha")
    (data_root / "fonts/ttf/Beta.ttf").write_bytes(b"beta")
    (data_root / "fonts/afm/Core.afm").write_bytes(b"core")
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                "_version": 390,
                "_FontManager__default_weight": "normal",
                "default_size": None,
                "defaultFamily": {"ttf": "Alpha", "afm": "Core"},
                "ttflist": [
                    {"fname": "/System/Library/Fonts/Host.ttf", "name": "Host"},
                    {"fname": "fonts/ttf/Beta.ttf", "name": "Beta"},
                    {"fname": "fonts/ttf/Alpha.ttf", "name": "Alpha"},
                ],
                "afmlist": [{"fname": "fonts/afm/Core.afm", "name": "Core"}],
                "__class__": "FontManager",
            }
        ),
        encoding="utf-8",
    )
    destination = tmp_path / "fontlist-v390.json"

    built = module.build_portable_font_cache(source, destination, expected_version=390)
    validated = module.validate_portable_font_cache(
        destination,
        expected_version=390,
        matplotlib_data_path=data_root,
    )

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert [row["fname"] for row in payload["ttflist"]] == [
        "fonts/ttf/Alpha.ttf",
        "fonts/ttf/Beta.ttf",
    ]
    assert built == validated
    assert built["font_manager_version"] == 390
    assert built["ttf_count"] == 2
    assert built["afm_count"] == 1
    assert built["absolute_path_count"] == 0
    assert built["sha256"] == _sha256_bytes(destination.read_bytes())


def test_sensitive_operation_guard_blocks_worker_subprocess(module, tmp_path) -> None:
    guard = module.SensitiveOperationGuard((tmp_path,))

    with pytest.raises(module.ImportPreflightError, match="subprocess_forbidden"):
        with guard:
            subprocess.Popen(["/usr/bin/true"])

    assert guard.counters["subprocess_spawn_count"] == 1
    assert sum(guard.counters.values()) == 1


def test_network_block_rejects_connection_attempt_and_restores_socket(module) -> None:
    original = socket.socket.connect
    blocker = module.NetworkBlock()

    with pytest.raises(module.ImportPreflightError, match="network_connection_forbidden"):
        with blocker:
            socket.socket().connect(("127.0.0.1", 1))

    assert blocker.attempts == 1
    assert socket.socket.connect is original


def test_sensitive_operation_guard_blocks_formal_replay_entrypoint(module, tmp_path) -> None:
    namespace = {"__name__": "production.shadow"}
    exec("def _run_live_c9():\n    return None\n", namespace)
    guard = module.SensitiveOperationGuard((tmp_path,))

    with pytest.raises(module.ImportPreflightError, match="formal_replay_limit_exceeded"):
        with guard:
            namespace["_run_live_c9"]()

    assert guard.counters["candidate_strategy_run_count"] == 1
    assert sum(guard.counters.values()) == 1


def test_sensitive_operation_guard_allows_exactly_one_authorized_formal_replay(
    module,
    tmp_path,
) -> None:
    namespace = {"__name__": "production.shadow"}
    exec("def _run_live_c9():\n    return 'completed'\n", namespace)
    guard = module.SensitiveOperationGuard(
        (tmp_path,),
        allowed_formal_replay_count=1,
    )

    with pytest.raises(module.ImportPreflightError, match="formal_replay_limit_exceeded"):
        with guard:
            assert namespace["_run_live_c9"]() == "completed"
            namespace["_run_live_c9"]()

    assert guard.formal_replay_call_count == 2
    assert guard.counters["candidate_strategy_run_count"] == 1


def test_frozen_materials_validate_against_current_runtime(module) -> None:
    attestation = json.loads(
        module.RELEASE_ATTESTATION.read_text(encoding="utf-8")
    )

    release = module.verify_release_commit_attestation(
        module.PRODUCTION_ROOT,
        module.PRODUCTION_ROOT / attestation["manifest_relative_path"],
        module.EXPECTED_RELEASE_COMMIT,
        attestation,
    )
    cache = module.validate_portable_font_cache(
        module.FONT_CACHE_FIXTURE,
        expected_version=module.EXPECTED_FONT_MANAGER_VERSION,
        matplotlib_data_path=module.matplotlib_data_path(),
    )

    assert release["manifest_sha256"] == attestation["manifest_sha256"]
    assert cache["sha256"] == module.EXPECTED_FONT_CACHE_SHA256
    assert cache["ttf_count"] == 38
    assert cache["afm_count"] == 60
    assert cache["absolute_path_count"] == 0


def test_preflight_source_never_calls_formal_replay() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    called_names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            called_names.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            called_names.append(node.func.attr)

    assert "_run_live_c9" not in called_names


@pytest.mark.skipif(not Path("/usr/bin/sandbox-exec").is_file(), reason="macOS only")
def test_run_import_preflight_uses_two_clean_workers_without_replay(tmp_path) -> None:
    output_argument = Path("stage001_import_preflight")
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
    assert all(value == 0 for value in summary["sensitive_counters"].values())
    assert summary["network_connection_attempt_count"] == 0
    assert (output / "A1/receipt.json").is_file()
    assert (output / "A2/receipt.json").is_file()
