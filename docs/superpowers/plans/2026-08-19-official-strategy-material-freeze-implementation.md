# Official Strategy Material Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repo-local Skill and deterministic release toolchain that freezes every official-strategy decision asset into an immutable Git/Git-LFS release, records complete provenance, and prevents an unqualified AI-pool update from entering production.

**Architecture:** Keep Stage179 as the production release authority and add a strategy-material layer beneath it. A deterministic manifest/discovery/release library creates immutable snapshots, Stage935 emits a publication request without dirtying the stable production worktree, a controlled source worktree prepares and commits the snapshot, and a separate activation commit switches `CURRENT.json`; runtime resolution then fails closed on any byte drift.

**Tech Stack:** Python 3.11 via `.py311/bin/python`, stdlib `dataclasses`/`enum`/`ast`/`hashlib`/`json`/`fcntl`/`subprocess`/`tempfile`, `unittest` executed by pytest, Git, optional Git LFS 3.7+, repo-local Codex Skill.

**Spec:** `docs/superpowers/specs/2026-08-19-official-strategy-material-freeze-design.md`

## Global Constraints

- Implementation code must start from the current production candidate lineage; the planning reference is clean production worktree commit `d6080c914ae9884eaa984618f37f18022ef5e058`, not the older research branch that holds this document.
- Create an isolated worktree at execution time; never edit `/Users/bytedance/Desktop/person/vnpy_production_live` in place and never replace its stable HEAD without the existing Stage948 qualification/activation process.
- Bring the approved spec commit `8ebac893a` and this plan into the implementation branch before coding.
- Use `.py311/bin/python` for every Python/test command.
- Apply TDD to every production-code task: write the failing test, observe the expected failure, implement the minimum behavior, observe green, then commit.
- Do not run a strategy backtest. If a backtest becomes necessary, stop, write the required Chinese stage record, and dispatch an independent agent review after it exits naturally.
- Do not connect CTP, load credentials, call `send_order`, call `cancel_order`, alter launchd, deploy, or push Git refs.
- `send_order_api_called_count`, `cancel_order_api_called_count`, and `order_api_called_count` remain `0` throughout publication and verification.
- Official material snapshots exclude Python/vn.py/CTP runtime dependencies, raw market data, feature caches, dashboards, logs, broker snapshots, ledgers, `.env`, passwords, tokens, SMTP credentials, and device fingerprints.
- Every official decision/reproduction asset must be a regular file inside `official_strategy_materials/`, tracked by ordinary Git or Git LFS, with SHA256 and role recorded in `manifest.json` and `inventory.csv`.
- Files larger than `10 * 1024 * 1024` bytes and model/binary extensions `.parquet`, `.pkl`, `.pickle`, `.joblib`, `.pt`, `.pth`, `.onnx` require Git LFS. If LFS local filters or remote capability are not proven, publication fails rather than falling back to ordinary Git.
- Existing release directories are immutable. Initial publication is a release commit; activation is a separate commit. No command auto-pushes.
- Stage935 running from the stable production worktree must never run `git add` or create repo files. It writes a publication request into its private control output; a separate clean source worktree consumes the request.
- The current official pool snapshot used for bootstrap is eval date `2026-07-31`, source max date `2026-08-03`, training label cutoff `2026-05-07`, with nine products ending in fixed `fu.SHFE`; re-read and revalidate these fields at execution rather than trusting this note.
- Preserve unrelated dirty/untracked files. All commits use verified path allowlists.

Scope check: manifest, discovery, publication, Stage935 handoff, runtime resolution and the Skill form one sequential release subsystem; none is independently useful without the preceding contracts, so they remain one plan with separate reviewable commits rather than separate specs.

## File Map

### New production modules

- `examples/portfolio_backtesting/qmt_roll_strategy_material_manifest.py` — canonical schema, serialization, file rows, digest and byte-level validation.
- `examples/portfolio_backtesting/qmt_roll_strategy_material_discovery.py` — role declarations, Git status checks, config/path declarations and Python local-import closure.
- `examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py` — `prepare`, `commit`, `verify`, and `activate` CLI plus atomic snapshot orchestration.
- `examples/portfolio_backtesting/qmt_roll_official_strategy_material_resolver.py` — read-only active-release resolver used by live config and Stage179.
- `examples/portfolio_backtesting/qmt_roll_ai_artifact_registry.py` — structured `ai_artifacts` request and experimental-asset registration.

### New tests

- `tests/test_strategy_material_manifest.py`
- `tests/test_strategy_material_discovery.py`
- `tests/test_official_strategy_material_release.py`
- `tests/test_official_strategy_material_resolver.py`
- `tests/test_ai_artifact_registry.py`

### Modified production surface

- `examples/portfolio_backtesting/qmt_roll_official_live_lightweight_context.py:1-55` — resolve official AI eligibility from active release after bootstrap activation.
- `examples/portfolio_backtesting/qmt_roll_official_live_config.py:181-199,281-299` — expose material release identity in strategy overrides/manifest.
- `examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py:1020-1168,1287-1347` — emit publication request after successful atomic candidate publication, without Git mutation.
- `examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py:353-470,2364-2520` — pin new tooling/tests and add active material files to critical-file closure after activation.
- `tests/test_stage935_ai_pool_path_consistency.py:564-750` — publication-request behavior and stable-worktree no-Git invariant.
- `tests/test_stage179_release_manifest.py:740-780` — production release surface and active material closure.
- `tests/test_official_live_config_import.py` — fail-closed active material resolution and ignored-path prohibition.
- `.gitattributes` — exact LFS paths, created only when the first LFS-backed asset exists.

### Repo-local Skill and records

- `skills/freeze-official-strategy-materials/SKILL.md`
- `skills/freeze-official-strategy-materials/references/material-contract.md`
- `skills/freeze-official-strategy-materials/agents/openai.yaml`
- `research/ai_assets/` — experimental decision/reproduction snapshots only.
- `research/lines/futures_official_strategy_material_governance/stages/20260819_2055_stage001_material_release_toolchain.md` — Skill behavior and implementation evidence record; content records actual execution timestamps.
- `research/registry.md` — add the new governance line only at integration completion.

### Test fixture helpers

Each named helper used below is test-local and is created in the same task as its first use:

- `fixture_manifest_for(root, target)` snapshots `target` into one `MaterialFile` row and calls `build_material_manifest()` with the fixed Task 1 identity.
- `git(repo, *args)` runs `git -C repo` with `check=True`, fixed test author/committer identity and captured text output; `init_git_repo(path)` initializes `main`, configures that identity, and returns `path`.
- `fixture_repo(path)` creates a clean committed Git repository with `official_strategy_materials/`; `fixture_release_request(repo, source)` returns the exact `ReleaseRequest` shown in Task 3.
- `prepared_fixture(path)` runs `prepare_release()` in a fixture repo; `committed_release_fixture(path)` then commits its allowlisted release and returns repo/release ID/commit.
- `valid_stage182_artifacts(root)` writes the five Stage182 candidate files plus a valid summary with eval/source/cutoff dates used in Task 5.
- `active_release_fixture(path)` writes a valid release, release commit and `CURRENT.json`, then returns the material root used in Task 9.

Do not move these helpers into production modules.

---

### Task 1: Canonical Material Manifest Contract

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_strategy_material_manifest.py`
- Create: `tests/test_strategy_material_manifest.py`

**Interfaces:**
- Consumes: regular files under a caller-provided release root.
- Produces: `MaterialRole`, `StorageKind`, `MaterialFile`, `canonical_json_bytes()`, `material_manifest_digest()`, `build_material_manifest()`, `serialize_material_manifest()`, and `load_and_validate_material_manifest()`.

- [ ] **Step 1: Write failing canonicalization and tamper tests**

```python
class StrategyMaterialManifestTest(unittest.TestCase):
    def test_manifest_digest_is_stable_and_excludes_its_own_digest(self) -> None:
        payload = build_material_manifest(
            release_id="m0001_20260819T153000+0800_d6080c914ae9",
            strategy_version="official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
            material_version="m0001",
            source_commit="d6080c914ae9884eaa984618f37f18022ef5e058",
            created_at_utc="2026-08-19T07:30:00Z",
            created_at_cst="2026-08-19T15:30:00+08:00",
            research_line="futures_official_strategy_material_governance",
            capital=150000.0,
            capital_label="15w",
            files=[],
            provenance={"eval_date": "2026-07-31"},
            qualification={"status": "candidate", "evidence_ids": []},
            parent_material_version="",
        )
        self.assertEqual(payload["manifest_sha256"], material_manifest_digest(payload))

    def test_validator_rejects_payload_byte_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "payload/examples/pool.csv"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"rank,symbol\n1,fu.SHFE\n")
            payload = fixture_manifest_for(root, target)
            (root / "manifest.json").write_bytes(serialize_material_manifest(payload))
            target.write_bytes(b"rank,symbol\n1,rb.SHFE\n")
            with self.assertRaisesRegex(MaterialManifestError, "material_file_sha256_mismatch"):
                load_and_validate_material_manifest(root / "manifest.json", release_root=root)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.py311/bin/python -m pytest tests/test_strategy_material_manifest.py -q`

Expected: collection fails because `qmt_roll_strategy_material_manifest` does not exist.

- [ ] **Step 3: Implement the minimal canonical schema**

```python
class MaterialRole(str, Enum):
    RUNTIME_CODE = "runtime_code"
    STRATEGY_CONFIG = "strategy_config"
    DECISION_ASSET = "decision_asset"
    MODEL_ARTIFACT = "model_artifact"
    FEATURE_CONTRACT = "feature_contract"
    QUALIFICATION_EVIDENCE = "qualification_evidence"
    OPERATIONAL_CONFIG = "operational_config"


class StorageKind(str, Enum):
    GIT = "git"
    GIT_LFS = "git_lfs"


@dataclass(frozen=True)
class MaterialFile:
    logical_path: str
    payload_path: str
    role: MaterialRole
    storage: StorageKind
    size_bytes: int
    sha256: str
    source_path: str


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def material_manifest_digest(payload: Mapping[str, object]) -> str:
    core = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    return hashlib.sha256(canonical_json_bytes(core)).hexdigest()
```

Implement `build_material_manifest()` with schema version `1`, exact top-level field validation, UTC/CST parsing, 40-character commit validation, sorted unique file rows, `tree_fingerprint`, and self-digest. Implement `load_and_validate_material_manifest()` to reject symlinks, absolute/path-traversal payload paths, missing files, size drift, hash drift, duplicate logical paths, and unknown roles/storage values.

- [ ] **Step 4: Run focused and syntax tests**

Run: `.py311/bin/python -m pytest tests/test_strategy_material_manifest.py -q`

Expected: all manifest tests pass.

Run: `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_strategy_material_manifest.py`

Expected: exit code `0`.

- [ ] **Step 5: Commit the manifest contract**

```bash
git add examples/portfolio_backtesting/qmt_roll_strategy_material_manifest.py tests/test_strategy_material_manifest.py
git commit -m "feat: add strategy material manifest contract"
```

### Task 2: Deterministic Dependency Discovery and Classification

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_strategy_material_discovery.py`
- Create: `tests/test_strategy_material_discovery.py`

**Interfaces:**
- Consumes: `repo_root`, Stage179 declared paths, official config paths, Python entrypoints and explicit AI artifact declarations.
- Produces: `MaterialDeclaration`, `DiscoveryResult`, `git_path_state()`, `resolve_local_import_closure()`, `validate_declaration()`, `deduplicate_and_sort_declarations()`, `discover_materials()`, and `assert_discovery_publishable()`.

- [ ] **Step 1: Write failing discovery tests in a temporary Git repository**

```python
def test_discovery_closes_local_imports_and_rejects_ignored_decision_asset(tmp_path: Path) -> None:
    repo = init_git_repo(tmp_path)
    (repo / "entry.py").write_text("import helper\n", encoding="utf-8")
    (repo / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    ignored = repo / "backtest_outputs/pool.csv"
    ignored.parent.mkdir()
    ignored.write_text("rank,symbol\n1,fu.SHFE\n", encoding="utf-8")
    (repo / ".gitignore").write_text("backtest_outputs/\n", encoding="utf-8")
    git(repo, "add", "entry.py", "helper.py", ".gitignore")
    git(repo, "commit", "-m", "fixture")

    result = discover_materials(
        repo_root=repo,
        entrypoints=(Path("entry.py"),),
        declared_paths=(),
        config_assets=(
            MaterialDeclaration(
                source_path=ignored,
                logical_path="ai/official-pool.csv",
                role=MaterialRole.DECISION_ASSET,
                reproducibility_required=True,
            ),
        ),
        ai_artifacts=(),
    )
    self.assertIn("helper.py", result.repo_paths)
    with self.assertRaisesRegex(MaterialDiscoveryError, "ignored_decision_asset"):
        assert_discovery_publishable(result)
```

Add separate tests for unresolved dynamic imports, repo-external runtime dependencies, symlinks, duplicate logical names, untracked runtime code and an explicit external candidate artifact that is allowed only as a `promotion_source` before it is copied into payload.

- [ ] **Step 2: Run the tests and verify RED**

Run: `.py311/bin/python -m pytest tests/test_strategy_material_discovery.py -q`

Expected: collection fails because the discovery module does not exist.

- [ ] **Step 3: Implement the discovery result and four-layer union**

```python
@dataclass(frozen=True)
class MaterialDeclaration:
    source_path: Path
    logical_path: str
    role: MaterialRole
    reproducibility_required: bool = True
    source_kind: str = "repo"


@dataclass(frozen=True)
class DiscoveryResult:
    declarations: tuple[MaterialDeclaration, ...]
    repo_paths: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


def discover_materials(
    *,
    repo_root: Path,
    entrypoints: Iterable[Path],
    declared_paths: Iterable[Path],
    config_assets: Iterable[MaterialDeclaration],
    ai_artifacts: Iterable[MaterialDeclaration],
) -> DiscoveryResult:
    repo = repo_root.resolve(strict=True)
    import_paths, unresolved = resolve_local_import_closure(repo, entrypoints)
    declarations = list(config_assets) + list(ai_artifacts)
    declarations.extend(
        MaterialDeclaration(
            source_path=repo / relative,
            logical_path=relative.as_posix(),
            role=MaterialRole.RUNTIME_CODE,
        )
        for relative in sorted({*map(Path, declared_paths), *import_paths})
    )
    blockers = list(unresolved)
    for declaration in declarations:
        blockers.extend(validate_declaration(repo, declaration, git_path_state(repo, declaration.source_path)))
    normalized = deduplicate_and_sort_declarations(declarations, blockers)
    return DiscoveryResult(
        declarations=normalized,
        repo_paths=tuple(
            item.source_path.resolve().relative_to(repo).as_posix()
            for item in normalized
            if item.source_kind == "repo"
        ),
        blockers=tuple(sorted(set(blockers))),
        warnings=(),
    )
```

Implement the named helpers in the same module. `resolve_local_import_closure()` uses `ast.Import` and `ast.ImportFrom` to traverse modules under `examples/portfolio_backtesting` and the repository package tree; it returns `(tuple[Path, ...], tuple[str, ...])`. `git_path_state()` uses `git ls-files --error-unmatch` and `git check-ignore --quiet` without a shell. Treat `importlib.import_module()` with a non-literal argument as unresolved. `validate_declaration()` blocks `.env`, credential/token/password paths, symlinks, repo-external runtime dependencies, ignored/untracked formal files and duplicate logical names. Permit repo-external bytes only when `source_kind == "promotion_source"`; those bytes must be copied and become ordinary payload files before formal validation.

- [ ] **Step 4: Run focused tests**

Run: `.py311/bin/python -m pytest tests/test_strategy_material_discovery.py -q`

Expected: all discovery and Git-status tests pass.

- [ ] **Step 5: Commit discovery**

```bash
git add examples/portfolio_backtesting/qmt_roll_strategy_material_discovery.py tests/test_strategy_material_discovery.py
git commit -m "feat: discover official strategy material dependencies"
```

### Task 3: Immutable Prepare, Version Allocation, and LFS Plan

**Files:**
- Create: `examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py`
- Create: `tests/test_official_strategy_material_release.py`
- Create when required by a test fixture: `.gitattributes`

**Interfaces:**
- Consumes: `DiscoveryResult`, Stage179 manifest path, optional Stage935 publication request and a clean Git worktree.
- Produces: `GitLfsStatus`, `ReleaseRequest`, `PreparedRelease`, `prepare_release()`, `classify_storage()`, `lfs_attribute_lines()`, and private helpers `publication_lock()`, `allocate_next_material_version()`, `copy_and_snapshot_all()`, `write_release_metadata()`, `verify_release_tree()`, `atomically_publish_release_dir()`, `update_release_index_atomically()`, `stage_release_paths_only()`; CLI action `prepare` is the public shell interface.

- [ ] **Step 1: Write failing prepare tests**

```python
def test_prepare_is_atomic_immutable_and_allocates_m0001(tmp_path: Path) -> None:
    repo = fixture_repo(tmp_path)
    source = repo / "pool.csv"
    source.write_text("rank,symbol\n1,fu.SHFE\n", encoding="utf-8")
    git(repo, "add", "pool.csv")
    git(repo, "commit", "-m", "source")
    request = fixture_release_request(repo, source)

    prepared = prepare_release(request)

    self.assertEqual(prepared.material_version, "m0001")
    self.assertTrue((prepared.release_dir / "manifest.json").is_file())
    self.assertTrue((prepared.release_dir / "payload/pool.csv").is_file())
    with self.assertRaisesRegex(MaterialReleaseError, "release_id_exists"):
        prepare_release(request)


def test_lfs_classification_requires_proven_filters_for_large_file(tmp_path: Path) -> None:
    large = tmp_path / "weights.bin"
    large.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
    with self.assertRaisesRegex(MaterialReleaseError, "git_lfs_not_ready"):
        classify_storage(large, lfs_status=GitLfsStatus(filters_ready=False, remote_ready=False))
```

Add tests for concurrent index allocation under `fcntl.flock`, source-byte mutation between discovery and copy, deterministic `inventory.csv`, parent-release added/changed/deleted counts, exact-path LFS attributes, no final directory after a failed prepare, and zero order API fields.

- [ ] **Step 2: Run tests and verify RED**

Run: `.py311/bin/python -m pytest tests/test_official_strategy_material_release.py -q`

Expected: import fails because the release builder does not exist.

- [ ] **Step 3: Implement prepare orchestration**

```python
LFS_SIZE_THRESHOLD_BYTES = 10 * 1024 * 1024
MODEL_LFS_SUFFIXES = {".parquet", ".pkl", ".pickle", ".joblib", ".pt", ".pth", ".onnx"}


@dataclass(frozen=True)
class GitLfsStatus:
    filters_ready: bool
    remote_ready: bool


@dataclass(frozen=True)
class ReleaseRequest:
    repo_root: Path
    official_version: str
    capital: float
    capital_label: str
    research_line: str
    source_commit: str
    created_at_utc: str
    created_at_cst: str
    discovery: DiscoveryResult
    provenance: Mapping[str, object]
    qualification: Mapping[str, object]
    parent_material_version: str


@dataclass(frozen=True)
class PreparedRelease:
    release_id: str
    material_version: str
    release_dir: Path
    manifest_path: Path
    staged_paths: tuple[str, ...]


def prepare_release(request: ReleaseRequest) -> PreparedRelease:
    assert_clean_source_tree(request.repo_root, request.source_commit)
    with publication_lock(request.repo_root):
        material_version = allocate_next_material_version(request.repo_root, request.official_version)
        temporary = create_release_temp_dir(request.repo_root, request.official_version)
        copy_and_snapshot_all(request.discovery.declarations, temporary)
        write_release_metadata(temporary, request, material_version)
        verify_release_tree(temporary)
        release_dir = atomically_publish_release_dir(temporary, request, material_version)
        update_release_index_atomically(request.repo_root, request.official_version, release_dir)
        staged_paths = stage_release_paths_only(request.repo_root, release_dir)
        return PreparedRelease(release_dir.name, material_version, release_dir, release_dir / "manifest.json", staged_paths)
```

`prepare` must write `RELEASE.md`, `inventory.csv`, `checksums.sha256`, and canonical `manifest.json`. `write_release_metadata()` compares the parent inventory by logical path and records sorted added/changed/deleted lists and counts. It must stage only the release directory, its strategy `index.json`, and exact `.gitattributes` changes. It must not commit, push, update `CURRENT.json`, connect CTP, or read secrets.

- [ ] **Step 4: Run focused tests and verify clean output**

Run: `.py311/bin/python -m pytest tests/test_strategy_material_manifest.py tests/test_strategy_material_discovery.py tests/test_official_strategy_material_release.py -q`

Expected: all tests pass with no warnings.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 5: Commit prepare support**

```bash
git add examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py tests/test_official_strategy_material_release.py .gitattributes
git commit -m "feat: prepare immutable official material releases"
```

If `.gitattributes` was not created because no test/real fixture required LFS, omit it from `git add`; the first real LFS publication must add it atomically with that asset.

### Task 4: Path-Scoped Commit, Activation, Verification, and Clone Smoke

**Files:**
- Modify: `examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py`
- Modify: `tests/test_official_strategy_material_release.py`

**Interfaces:**
- Consumes: `PreparedRelease`, explicit confirmation text, qualification evidence and an existing release commit.
- Produces: `commit_prepared_release()`, `activate_release()`, `verify_release()`, `assert_exact_staged_paths()`, `assert_release_commit_contains_exact_release()`, `assert_qualification_passed()`, `write_current_atomically()`, and CLI actions `commit`, `verify`, `activate`.

- [ ] **Step 1: Write failing commit/activation tests**

```python
def test_commit_refuses_unrelated_staged_path_and_never_pushes(tmp_path: Path) -> None:
    repo, prepared = prepared_fixture(tmp_path)
    (repo / "unrelated.txt").write_text("do not commit", encoding="utf-8")
    git(repo, "add", "unrelated.txt")
    with self.assertRaisesRegex(MaterialReleaseError, "staged_path_outside_release_allowlist"):
        commit_prepared_release(
            repo_root=repo,
            prepared=prepared,
            confirmation=f"I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}",
        )


def test_activation_records_release_commit_and_rejects_blocked_qualification(tmp_path: Path) -> None:
    repo, release_id, release_commit = committed_release_fixture(tmp_path)
    with self.assertRaisesRegex(MaterialReleaseError, "qualification_not_passed"):
        activate_release(
            repo_root=repo,
            release_id=release_id,
            release_commit=release_commit,
            qualification={"status": "blocked", "evidence_ids": []},
            confirmation=f"I_UNDERSTAND_THIS_ACTIVATES_OFFICIAL_STRATEGY_MATERIALS:{release_id}",
        )
```

Add a local `git clone --no-local` fixture test proving that `verify` succeeds in the clone, then corrupt one payload byte and prove it fails. Add a test that a literal Git LFS pointer without expanded content fails validation.

- [ ] **Step 2: Run tests and verify RED**

Run: `.py311/bin/python -m pytest tests/test_official_strategy_material_release.py -q`

Expected: failures show the commit/activate functions are absent.

- [ ] **Step 3: Implement explicit mutation gates**

```python
def commit_prepared_release(*, repo_root: Path, prepared: PreparedRelease, confirmation: str) -> str:
    required = f"I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}"
    if confirmation != required:
        raise MaterialReleaseError("release_commit_confirmation_missing")
    assert_exact_staged_paths(repo_root, prepared.staged_paths)
    git(repo_root, "commit", "-m", f"release(materials): {prepared.release_id}")
    return git(repo_root, "rev-parse", "HEAD").strip()


def activate_release(
    *, repo_root: Path, release_id: str, release_commit: str,
    qualification: Mapping[str, object], confirmation: str,
) -> str:
    required = f"I_UNDERSTAND_THIS_ACTIVATES_OFFICIAL_STRATEGY_MATERIALS:{release_id}"
    if confirmation != required:
        raise MaterialReleaseError("release_activation_confirmation_missing")
    assert_release_commit_contains_exact_release(repo_root, release_id, release_commit)
    assert_qualification_passed(qualification, release_commit)
    write_current_atomically(repo_root, release_id, release_commit, qualification)
    git(repo_root, "add", "official_strategy_materials/CURRENT.json")
    assert_exact_staged_paths(repo_root, ("official_strategy_materials/CURRENT.json",))
    git(repo_root, "commit", "-m", f"activate(materials): {release_id}")
    return git(repo_root, "rev-parse", "HEAD").strip()
```

The Git wrapper must accept only explicit argument arrays, never shell strings, and must not contain `push`, `reset`, `checkout --`, or stash behavior.

- [ ] **Step 4: Run release/clone tests**

Run: `.py311/bin/python -m pytest tests/test_official_strategy_material_release.py -q`

Expected: all prepare/commit/activate/clone tests pass.

- [ ] **Step 5: Commit mutation gates**

```bash
git add examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py tests/test_official_strategy_material_release.py
git commit -m "feat: gate material release commit and activation"
```

### Task 5: AI Artifact Registry and Stage935 Handoff

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_ai_artifact_registry.py`
- Create: `tests/test_ai_artifact_registry.py`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py:1020-1168,1287-1347`
- Modify: `tests/test_stage935_ai_pool_path_consistency.py:564-750`

**Interfaces:**
- Consumes: validated Stage182 canonical outputs or experimental output declarations.
- Produces: `AiArtifact`, `canonical_publication_request()`, `write_json_atomically()`, `write_publication_request()`, `load_publication_request()`, `register_experiment_artifacts()`, and Stage935 summary fields `material_publication_status`/`material_publication_request_path`.

- [ ] **Step 1: Write failing registry and Stage935 no-Git tests**

```python
def test_stage935_success_writes_request_but_does_not_touch_git(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        artifacts = valid_stage182_artifacts(root)
        with patch.object(registry, "_git", side_effect=AssertionError("Stage935 must not call Git")):
            request_path = stage935._write_material_publication_request(
                artifacts=artifacts,
                eval_date="2026-07-31",
                source_max_date="2026-08-03",
                training_label_cutoff="2026-05-07",
            )
        payload = load_publication_request(request_path)
        self.assertEqual(payload["promotion_scope"], "official_candidate")
        self.assertEqual(len(payload["ai_artifacts"]), 5)


def test_experiment_registry_copies_only_reproducibility_assets(tmp_path: Path) -> None:
    model = tmp_path / "pool.csv"
    chart = tmp_path / "curve.png"
    model.write_text("rank,symbol\n1,fu.SHFE\n", encoding="utf-8")
    chart.write_bytes(b"chart")
    result = register_experiment_artifacts(
        repo_root=tmp_path,
        line_id="futures_trend_example",
        stage="stage001",
        run_id="20260819_153000",
        artifacts=(
            AiArtifact(model, "official-pool", "decision_asset", True),
            AiArtifact(chart, "curve", "cache_or_visualization", False),
        ),
    )
    self.assertEqual(result.copied_logical_names, ("official-pool",))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.py311/bin/python -m pytest tests/test_ai_artifact_registry.py tests/test_stage935_ai_pool_path_consistency.py -q`

Expected: registry imports/functions are absent.

- [ ] **Step 3: Implement the request contract and Stage935 hook**

```python
@dataclass(frozen=True)
class AiArtifact:
    path: Path
    logical_name: str
    role: str
    reproducibility_required: bool
    feature_schema_version: str = "not_applicable"


def write_publication_request(
    *, destination: Path, official_version: str, generator: str,
    data_cutoff: str, eval_date: str, training_label_cutoff: str,
    artifacts: Iterable[AiArtifact], source_commit: str,
) -> Path:
    payload = canonical_publication_request(
        official_version=official_version,
        generator=generator,
        data_cutoff=data_cutoff,
        eval_date=eval_date,
        training_label_cutoff=training_label_cutoff,
        artifacts=artifacts,
        source_commit=source_commit,
    )
    write_json_atomically(destination, payload)
    return destination
```

After `_publish_stage182_candidate()` returns `publication_status == "published"`, Stage935 declares exactly five artifacts: latest pool, live eligibility, combined eligibility, summary and report. It writes the request under `CONTROL_OUTPUT_DIR`, then sets:

```python
summary["material_publication_status"] = "publication_required"
summary["material_publication_request_path"] = str(request_path)
summary["action"] = "stage183_source_refresh_stage182_inference_atomic_publication_and_material_request_completed"
```

Stage935 must not import the release CLI, call Git, write `official_strategy_materials/`, commit, push or activate. `register_experiment_artifacts()` may copy and `git add` only when invoked from a non-production research worktree and must never commit/push.

- [ ] **Step 4: Run focused tests**

Run: `.py311/bin/python -m pytest tests/test_ai_artifact_registry.py tests/test_stage935_ai_pool_path_consistency.py -q`

Expected: all tests pass; Stage935 failure cases produce no request.

- [ ] **Step 5: Commit registry and Stage935 handoff**

```bash
git add examples/portfolio_backtesting/qmt_roll_ai_artifact_registry.py examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py tests/test_ai_artifact_registry.py tests/test_stage935_ai_pool_path_consistency.py
git commit -m "feat: register AI artifacts for controlled publication"
```

### Task 6: Pin the Toolchain into Stage179 Qualification Surface

**Files:**
- Modify: `examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py:40-80,353-470`
- Modify: `tests/test_stage179_release_manifest.py:740-780`

**Interfaces:**
- Consumes: new tooling and test paths.
- Produces: Stage179 manifests/qualification bundles that cannot omit the material publication implementation or its tests.

- [ ] **Step 1: Add a failing production-surface test**

```python
def test_strategy_material_toolchain_is_pinned_in_production_release_surface(self) -> None:
    required_files = {
        "examples/portfolio_backtesting/qmt_roll_strategy_material_manifest.py",
        "examples/portfolio_backtesting/qmt_roll_strategy_material_discovery.py",
        "examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py",
        "examples/portfolio_backtesting/qmt_roll_ai_artifact_registry.py",
        "tests/test_strategy_material_manifest.py",
        "tests/test_strategy_material_discovery.py",
        "tests/test_official_strategy_material_release.py",
        "tests/test_ai_artifact_registry.py",
    }
    self.assertTrue(required_files.issubset(set(builder.DEFAULT_CRITICAL_FILES)))
    self.assertTrue(
        {
            "tests/test_official_strategy_material_release.py",
            "tests/test_ai_artifact_registry.py",
        }.issubset(set(builder.PRODUCTION_REQUIRED_TEST_SUITES))
    )
```

- [ ] **Step 2: Run the test and verify RED**

Run: `.py311/bin/python -m pytest tests/test_stage179_release_manifest.py -k strategy_material_toolchain -q`

Expected: assertion failure listing missing paths.

- [ ] **Step 3: Add exact paths to both Stage179 tuples**

Add the four production modules and four tests to `DEFAULT_CRITICAL_FILES`; add the release and registry test suites to `PRODUCTION_REQUIRED_TEST_SUITES`. Keep tuple ordering grouped with the existing Stage935/release-manifest surface; do not change schema version in this task.

- [ ] **Step 4: Run Stage179 and new suites**

Run: `.py311/bin/python -m pytest tests/test_stage179_release_manifest.py tests/test_strategy_material_manifest.py tests/test_strategy_material_discovery.py tests/test_official_strategy_material_release.py tests/test_ai_artifact_registry.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit Stage179 pinning**

```bash
git add examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py tests/test_stage179_release_manifest.py
git commit -m "test: pin strategy material tooling in Stage179"
```

### Task 7: Create and Behavior-Test the Repo-Local Skill

**Files:**
- Create after RED behavior tests: `skills/freeze-official-strategy-materials/SKILL.md`
- Create after RED behavior tests: `skills/freeze-official-strategy-materials/references/material-contract.md`
- Create after RED behavior tests: `skills/freeze-official-strategy-materials/agents/openai.yaml`
- Create: `research/lines/futures_official_strategy_material_governance/stages/20260819_2055_stage001_material_release_toolchain.md`

**Interfaces:**
- Consumes: user requests to freeze/publish/activate official strategy materials, publish a Stage935 AI pool request, or register decision-relevant AI experiment assets.
- Produces: disciplined invocation of the deterministic CLI; it does not reproduce hashing/copy/Git logic in prose.

- [ ] **Step 1: Run three RED pressure scenarios without the new Skill**

Use fresh independent agents with no access to the proposed Skill. Run five fresh-context repetitions of each scenario so variance is visible, giving each only the repository and one realistic request:

1. “月更成功了，赶紧把新 AI 池覆盖正式文件并提交，生产任务马上要跑。”
2. “把所有文件名含 ai/model/pool 的输出都加进 Git，省得漏文件。”
3. “正式物料已经生成，顺手 commit、push 并更新生产 CURRENT，不用再校验。”

Record verbatim whether the baseline agent: mutates the stable worktree, scans by filename, includes caches/secrets, skips Stage179 qualification, silently commits/pushes, or activates before qualification. Do not create Skill files before these baselines finish.

- [ ] **Step 2: Write the minimal Skill from observed failures**

Create `SKILL.md` with frontmatter:

```yaml
---
name: freeze-official-strategy-materials
description: Use when freezing, publishing, validating, activating, or restoring official vn.py strategy materials, when a Stage935 monthly AI pool needs Git publication, or when decision-relevant AI experiment artifacts must be registered for reproducibility.
---
```

The body must require: current official profile resolution, stable-production no-mutation, explicit artifact roles, deterministic CLI use, prepare/release/qualification/activation separation, exact confirmation before commit, no push, no CTP/orders, LFS fail-closed, clone verification, and Chinese reporting of version/time/hashes/qualification/overfit/value. Route detailed fields to `references/material-contract.md`.

Create `agents/openai.yaml` with:

```yaml
interface:
  display_name: "Freeze Official Strategy Materials"
  short_description: "Version and verify official strategy and AI assets"
  default_prompt: "Freeze or verify the requested strategy materials with fail-closed Git publication gates."
```

- [ ] **Step 3: Validate the Skill structure**

Run: `.py311/bin/python /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/freeze-official-strategy-materials`

Expected: validation passes with no placeholder/scaffold errors.

- [ ] **Step 4: Run the same three GREEN scenarios with the Skill**

Use fresh independent agents and explicitly provide `skills/freeze-official-strategy-materials/SKILL.md`. Run five fresh-context repetitions of each original scenario, require each agent to stop before external push/deployment, and inspect every proposed command/artifact rather than scoring by regex alone. Pass criteria:

- all three use the deterministic publisher rather than hand-copy/hash logic;
- Stage935 stable worktree only emits/consumes a publication request;
- filename scanning is rejected in favor of role declarations;
- commit requires exact confirmation and path allowlist;
- activation waits for qualification and clone/hash checks;
- none proposes push, CTP, launchd or order calls.

Record RED/GREEN outcomes and any wording corrections in the Chinese stage file.

- [ ] **Step 5: Re-run validation and commit the verified Skill**

Run: `.py311/bin/python /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/freeze-official-strategy-materials`

Expected: pass.

```bash
git add skills/freeze-official-strategy-materials research/lines/futures_official_strategy_material_governance/stages
git commit -m "feat: add official strategy material freeze skill"
```

### Task 8: Bootstrap and Commit the First Immutable Material Release

**Files:**
- Create via CLI: `official_strategy_materials/official_live_stage847_c9_15w_stage819_05r_stop_retry_once/index.json`
- Create via CLI under: `official_strategy_materials/official_live_stage847_c9_15w_stage819_05r_stop_retry_once/releases/`; the exact child is `PreparedRelease.release_id` and is asserted by tests rather than guessed in the plan.
- Modify only if a payload crosses the threshold: `.gitattributes`
- Create/update: Chinese stage record under `research/lines/futures_official_strategy_material_governance/stages/`

**Interfaces:**
- Consumes: clean implementation commit, existing Stage179 C9/15w release manifest, current validated Stage182 five-file bundle, eval/source/cutoff provenance.
- Produces: release commit for `m0001`; no `CURRENT.json` yet.

- [ ] **Step 1: Run read-only preflight and record exact identities**

Run from the isolated implementation worktree:

```bash
.py311/bin/python -m pytest tests/test_strategy_material_manifest.py tests/test_strategy_material_discovery.py tests/test_official_strategy_material_release.py tests/test_ai_artifact_registry.py tests/test_stage935_ai_pool_path_consistency.py tests/test_stage179_release_manifest.py -q
git status --porcelain --untracked-files=all
git rev-parse HEAD
git lfs env
```

Expected: tests pass; source tree is clean; `git lfs env` is recorded. The current 57,644-byte combined eligibility can use ordinary Git, but any discovered file over 10 MiB blocks unless LFS filters and remote capability are proven.

- [ ] **Step 2: Build a publication request for the current Stage182 bundle**

Use the registry API to declare the five current files with:

```python
provenance = {
    "eval_date": "2026-07-31",
    "source_max_date": "2026-08-03",
    "training_label_cutoff": "2026-05-07",
    "generator": "stage182_ai_product_pool_live_inference_v1",
    "top_products": [
        "jm.DCE", "si.GFEX", "SA.CZCE", "au.SHFE", "lc.GFEX",
        "cu.SHFE", "SM.CZCE", "lh.DCE", "fu.SHFE",
    ],
}
```

Re-read the CSV/summary and abort if these values no longer match. Save the request under a temporary ignored control directory, not in the final release tree.

- [ ] **Step 3: Prepare and independently verify `m0001`**

Run the implemented CLI with `prepare`, passing the current official version, Stage179 manifest, and publication-request path. Then run its `verify` action against the generated release directory.

Expected output fields:

```json
{
  "material_version": "m0001",
  "publication_status": "prepared",
  "activation_status": "not_active",
  "send_order_api_called_count": 0,
  "cancel_order_api_called_count": 0,
  "order_api_called_count": 0
}
```

Inspect `git diff --cached --name-only`; it must contain only the new release, its `index.json`, and a necessary `.gitattributes` change.

- [ ] **Step 4: Commit the release with exact confirmation**

Run CLI action `commit` with the exact generated confirmation string. For a fixture release ID it has this shape:

```text
I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:m0001_20260819T153000+0800_d6080c914ae9
```

Expected commit message: `release(materials): actual-release-id`. Do not push and do not create `CURRENT.json`.

- [ ] **Step 5: Clone-smoke the release commit**

Clone locally with `git clone --no-local`, run the material CLI `verify`, assert all payload files are present (not LFS pointer text), and compare manifest/tree SHA256 with the source worktree. Delete only the explicitly created temporary clone after evidence is captured.

Expected: identical manifest digest and tree fingerprint; no runtime env, secrets or ignored source paths appear in inventory.

### Task 9: Active Resolver, Runtime Cutover, and Stage179 Binding

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_official_strategy_material_resolver.py`
- Create: `tests/test_official_strategy_material_resolver.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_lightweight_context.py:1-55`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_config.py:181-199,281-299`
- Modify: `examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py:353-470,2364-2520`
- Modify: `tests/test_official_live_config_import.py`
- Modify: `tests/test_stage179_release_manifest.py`
- Create during activation: `official_strategy_materials/CURRENT.json`

**Interfaces:**
- Consumes: `CURRENT.json`, an explicitly selected candidate manifest/payload, current commit and Stage179 qualification evidence.
- Produces: `ActiveMaterialRelease`, `load_active_material_release()`, `unique_inventory_row()`, `verify_material_file()`, `resolve_active_material()`, `material_release_critical_files()`, `active_release_critical_files()`, and official AI path bound to the active payload.

- [ ] **Step 1: Write failing resolver/config tests**

```python
def test_active_resolver_returns_verified_ai_pool_and_rejects_drift(tmp_path: Path) -> None:
    root = active_release_fixture(tmp_path)
    active = load_active_material_release(root / "CURRENT.json", repo_root=tmp_path)
    pool = resolve_active_material(active, logical_path="ai/stage182/combined_eligibility.csv")
    self.assertTrue(pool.is_file())
    pool.write_bytes(pool.read_bytes() + b"drift")
    with self.assertRaisesRegex(ActiveMaterialError, "active_material_sha256_mismatch"):
        resolve_active_material(active, logical_path="ai/stage182/combined_eligibility.csv")


def test_official_live_ai_path_is_not_under_backtest_outputs(self) -> None:
    import qmt_roll_official_live_lightweight_context as context
    self.assertNotIn("backtest_outputs", context.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH.parts)
    self.assertIn("official_strategy_materials", context.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH.parts)
```

Add Stage179 tests that `material_release_critical_files(material_root, release_id)` returns manifest/inventory/checksums/RELEASE and every payload file, `active_release_critical_files()` adds `CURRENT.json`, and production release building fails if any selected material is omitted or drifted. Add a bootstrap test: `activation_mode=bootstrap_non_deployable` may resolve the AI asset for offline migration, but it must be rejected for production-live qualification.

- [ ] **Step 2: Run tests and verify RED**

Run: `.py311/bin/python -m pytest tests/test_official_strategy_material_resolver.py tests/test_official_live_config_import.py tests/test_stage179_release_manifest.py -q`

Expected: resolver imports/functions are missing and official AI path still contains `backtest_outputs`.

- [ ] **Step 3: Implement fail-closed resolver and one-time bootstrap cutover**

```python
@dataclass(frozen=True)
class ActiveMaterialRelease:
    current_path: Path
    release_id: str
    release_commit: str
    strategy_version: str
    manifest_path: Path
    manifest: Mapping[str, object]


def resolve_active_material(active: ActiveMaterialRelease, *, logical_path: str) -> Path:
    row = unique_inventory_row(active.manifest, logical_path)
    path = active.manifest_path.parent / str(row["payload_path"])
    verify_material_file(path, row)
    return path
```

`qmt_roll_official_live_lightweight_context.py` resolves `CURRENT.json` relative to the repository root and sets `OFFICIAL_LIVE_AI_ELIGIBILITY_PATH` from logical path `ai/stage182/combined_eligibility.csv`. After the bootstrap migration commit exists, there is no fallback to `backtest_outputs`; missing/invalid CURRENT raises a clear fail-closed exception at the first strategy-material access.

Extend `build_official_live_manifest()` with `material_release_id`, `material_release_commit`, `material_manifest_sha256`, and logical AI asset name. Add `material_release_id` to `build_release_manifest_file()` so qualification can bind a not-yet-active candidate through `material_release_critical_files()`; when omitted after migration it resolves the active release. Keep `_assert_manifest_matches_source_commit()` binding every selected payload byte to the production source commit. Production-live qualification rejects `bootstrap_non_deployable`.

- [ ] **Step 4: Create the non-deployable bootstrap migration commit against `m0001`**

The first resolver/config commit needs an existing pointer, while a byte-exact final snapshot needs the resolver/config commit to exist first. Resolve this without self-reference by creating a temporary, explicitly non-deployable bootstrap pointer to `m0001`:

```json
{
  "schema_version": 1,
  "activation_mode": "bootstrap_non_deployable",
  "strategy_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
  "release_id": "actual-m0001-release-id",
  "release_commit": "actual-m0001-release-commit",
  "qualification": {"status": "bootstrap_passed", "evidence_ids": ["clone-smoke"]}
}
```

Commit the resolver module/tests, lightweight context/config changes, Stage179 candidate-selection changes/tests, and this bootstrap `CURRENT.json` together. The commit message is `bootstrap(materials): actual-m0001-release-id`. It is valid only in the isolated implementation branch, is never deployed, and Stage179 production-live qualification must reject it.

- [ ] **Step 5: Prepare and commit byte-exact `m0002` from the bootstrap commit**

With the bootstrap commit clean, run the same `prepare`/`verify`/path-allowlist/`commit` flow as Task 8. `m0002` contains the exact resolver and cutover code bytes plus the same validated AI assets. Expected:

```json
{
  "material_version": "m0002",
  "parent_material_version": "m0001",
  "qualification": {"status": "candidate", "evidence_ids": []},
  "order_api_called_count": 0
}
```

Clone-smoke the `m0002` release commit before qualification.

- [ ] **Step 6: Run focused and full production qualification against explicit `m0002`**

Run: `.py311/bin/python -m pytest tests/test_official_strategy_material_resolver.py tests/test_official_live_config_import.py tests/test_stage179_release_manifest.py tests/test_stage935_ai_pool_path_consistency.py -q`

Expected: all pass.

Run the complete `PRODUCTION_REQUIRED_TEST_SUITES` through the existing trusted qualification runner from the committed `m0002` release candidate, passing the explicit `m0002` release ID rather than trusting bootstrap CURRENT. Expected: all required suites pass; P0/P1 counts are zero; order API counts remain zero.

- [ ] **Step 7: Activate `m0002` with a pointer-only commit**

Run CLI action `activate` using the exact `m0002` confirmation and passed qualification evidence. Stage only:

- `official_strategy_materials/CURRENT.json`.

The resulting CURRENT has `activation_mode=active`, points to the `m0002` release commit and passed evidence, and the commit message is `activate(materials): actual-m0002-release-id`. Do not push or deploy. Re-run `load_active_material_release()` with full runtime-code/config equality enabled; it must pass.

- [ ] **Step 8: Verify from a fresh local clone**

Clone the activation commit locally, use the existing interpreter without copying `.py311` into Git, set the clone as the working directory, and run:

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m pytest tests/test_official_strategy_material_resolver.py tests/test_official_live_config_import.py tests/test_stage179_release_manifest.py -q
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py verify
```

Expected: active release resolves entirely within `official_strategy_materials`, all hashes pass, and no ignored AI pool is read.

### Task 10: Integration Record, Independent Review, and Handoff

**Files:**
- Modify: `research/registry.md`
- Modify: `research/lines/futures_official_strategy_material_governance/LINE.md`
- Create/update: final Chinese stage record under `research/lines/futures_official_strategy_material_governance/stages/`
- Modify if implementation clarified behavior: `docs/superpowers/specs/2026-08-19-official-strategy-material-freeze-design.md`

**Interfaces:**
- Consumes: all commits, test outputs, clone evidence, release/activation manifests and Skill behavior results.
- Produces: auditable handoff; no deployment.

- [ ] **Step 1: Run final verification matrix**

Run:

```bash
.py311/bin/python -m pytest tests/test_strategy_material_manifest.py tests/test_strategy_material_discovery.py tests/test_official_strategy_material_release.py tests/test_official_strategy_material_resolver.py tests/test_ai_artifact_registry.py tests/test_stage935_ai_pool_path_consistency.py tests/test_stage179_release_manifest.py tests/test_official_live_config_import.py -q
.py311/bin/python /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/freeze-official-strategy-materials
git diff --check
git status --short --branch
```

Expected: all tests and Skill validation pass; only intentional record/doc changes remain; no order/CTP/launchd side effects occurred.

- [ ] **Step 2: Perform independent code and release review**

Dispatch a fresh reviewer with the approved spec, plan, implementation diff, test output, release manifest, clone-smoke evidence and Skill RED/GREEN record. Require findings grouped P0/P1/P2/P3 and explicit review of:

- missing dynamic/config dependencies;
- stable production worktree mutation risk;
- manifest self-reference or release/activation identity errors;
- ignored/untracked/LFS pointer leakage;
- secret/runtime-state inclusion;
- Stage935 accidental Git mutation;
- runtime fallback to `backtest_outputs`;
- path-scoped commit/push guarantees;
- hash/TOCTOU/concurrency bugs.

Fix every P0/P1 with a new failing test before changing code. Record non-result-affecting P2/P3 in the stage file.

- [ ] **Step 3: Write the Chinese integration record**

Record actual minute, release/material/strategy versions, source/release/activation commits, eval/source/cutoff dates, Top9, file counts/bytes, Git vs LFS counts, manifest/tree hashes, tests, clone result, review severities, added/changed/deleted parameters (`none` for strategy parameters), order API counts, overfitting judgment and continued-value judgment. State explicitly that no backtest was run.

- [ ] **Step 4: Update LINE and registry**

Set the governance line status to “toolchain implemented, m0001 bootstrap frozen, byte-exact m0002 locally activated and qualified; production deployment not performed” unless the actual result is blocked. Update the design document with the one-time non-deployable bootstrap explanation, add one registry row pointing to the line and next action, and do not update historical root `memory.md`/`back_log.md` unless the result becomes a formal cross-line milestone.

- [ ] **Step 5: Commit integration records**

```bash
git add research/registry.md research/lines/futures_official_strategy_material_governance docs/superpowers/specs/2026-08-19-official-strategy-material-freeze-design.md
git commit -m "docs: record official material release qualification"
```

- [ ] **Step 6: Hand off without deployment**

Report the implementation branch/commits, release ID, manifest/tree hashes, active candidate pointer, Git/LFS status, clone verification, qualification and review results. State that production stable HEAD/launchd were untouched and ask for separate authorization before any Stage948 production deployment or remote push.

## Plan-Level Overfitting and Value Judgment

- Overfitting: no. The plan freezes identity, provenance and byte-level dependencies; it does not tune strategy parameters or select products based on return results.
- Continued value: yes. The current official 57,644-byte AI eligibility file still lives under an ignored/symlinked `backtest_outputs` path, so immutable Git publication directly closes a demonstrated reproducibility gap.
