# Official Version Promotion Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance `$freeze-official-strategy-materials` so an explicitly authorized formal promotion synchronizes qualified source, active materials, remote master, research defaults, and production identity without a PR or force-push.

**Architecture:** Keep the current immutable release and activation primitives. Add a baseline-identity reader, a separate complete-promotion action in the existing publisher, and a read-only closure auditor. The Skill selects candidate-only publication versus full formal promotion; full promotion stages only release-inventory code plus explicit governance paths into a clean master worktree, pushes non-force, verifies a fresh clone, then installs and audits production through the existing live SOP.

**Tech Stack:** Python 3.11, dataclasses, pathlib, canonical JSON, subprocess Git, pytest/unittest, repo-local Codex Skills, existing Stage179/Stage948 production tooling.

**Spec:** `docs/superpowers/specs/2026-08-25-official-version-promotion-closure-design.md`

## Global Constraints

- Use `.py311/bin/python` for every Python command.
- Do not run strategy backtests; this change is release governance only.
- Do not connect CTP or call send/cancel/order APIs; every qualification artifact must retain zero counts.
- Preserve historical Stage78/Stage372 runners as explicitly named research references.
- Direct master writes require the user's existing formal-promotion authority, a clean detached integration worktree, non-force fast-forward push, remote readback, and `0/0` ahead/behind.
- Do not stash, reset, force-push, overwrite dirty worktrees, or rewrite immutable releases.
- If Q strategy/runtime/Skill bytes change, allocate a successor material release (expected `m0010`) while retaining `stage021_q_rollover_volume_atr_v1`; never relabel changed bytes as `m0009`.
- Update only the active research line `futures_trend_rollover_shape_same_volume`; do not modify other research-line directories.
- Every completion report and final audit must carry the six named fields `strategy_version`, `ruleset_version`, `source_commit`, `material_release_id`, `remote_master_sha`, and `production_source_commit`.

---

### Task 1: Add the formal baseline identity contract

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_official_baseline_identity.py`
- Create: `tests/test_official_baseline_identity.py`
- Modify: `examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py:923-979`

**Interfaces:**
- Produces: `OfficialBaselineIdentity`, `load_official_baseline_identity(repo_root: Path)`, `assert_official_checkout_matches_active_material(repo_root: Path)`, and `ruleset_version_from_config(path: Path)`.
- Extends `CURRENT.json` with `ruleset_version` and `source_commit`; existing schema-v1 readers continue accepting the document.
- Test helper: `_write_active_fixture(tmp_path: Path, *, top_ruleset: str, payload_ruleset: str) -> Path` creates a minimal Git repo, release manifest/inventory/payload, matching top-level config, and schema-v1 CURRENT document.

- [ ] **Step 1: Write failing identity tests**

```python
def test_identity_rejects_same_strategy_name_with_different_ruleset(tmp_path: Path) -> None:
    repo = _write_active_fixture(
        tmp_path,
        top_ruleset="old_c9_v1",
        payload_ruleset="stage021_q_rollover_volume_atr_v1",
    )
    with pytest.raises(OfficialBaselineIdentityError, match="top_level_ruleset_mismatch"):
        assert_official_checkout_matches_active_material(repo)


def test_current_records_ruleset_and_source_commit(tmp_path: Path) -> None:
    repo = _write_active_fixture(
        tmp_path,
        top_ruleset="stage021_q_rollover_volume_atr_v1",
        payload_ruleset="stage021_q_rollover_volume_atr_v1",
    )
    current = json.loads((repo / "official_strategy_materials/CURRENT.json").read_text())
    assert current["ruleset_version"] == "stage021_q_rollover_volume_atr_v1"
    assert re.fullmatch(r"[0-9a-f]{40}", current["source_commit"])
```

- [ ] **Step 2: Run RED tests**

Run: `.py311/bin/python -m pytest tests/test_official_baseline_identity.py -q`

Expected: collection fails because `qmt_roll_official_baseline_identity` does not exist.

- [ ] **Step 3: Implement the identity reader**

```python
@dataclass(frozen=True)
class OfficialBaselineIdentity:
    strategy_version: str
    ruleset_version: str
    source_commit: str
    material_release_id: str
    release_commit: str
    manifest_sha256: str


def ruleset_version_from_config(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    # Accept only one literal OFFICIAL_LIVE_RULESET_VERSION assignment.


def assert_official_checkout_matches_active_material(repo_root: Path) -> OfficialBaselineIdentity:
    # Load CURRENT.json, verify release tree, locate the inventory row for
    # qmt_roll_official_live_config.py, compare its SHA256 to the top-level file,
    # and require strategy/ruleset/source/release identities to agree.
```

Update `write_current_atomically()` to derive `ruleset_version` from the release payload config and copy the manifest `source_commit` into the canonical JSON.

- [ ] **Step 4: Run identity and resolver tests**

Run: `.py311/bin/python -m pytest tests/test_official_baseline_identity.py tests/test_official_strategy_material_resolver.py tests/test_official_strategy_material_release.py -q`

Expected: all pass; old schema-v1 fixture remains readable, while newly activated fixtures contain the two new fields.

- [ ] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/qmt_roll_official_baseline_identity.py \
  examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py \
  tests/test_official_baseline_identity.py tests/test_official_strategy_material_resolver.py \
  tests/test_official_strategy_material_release.py
git commit -m "feat: define official baseline identity contract"
```

### Task 2: Add the complete formal-promotion master action

**Files:**
- Modify: `examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py:79-88,827-1143`
- Modify: `tests/test_official_strategy_material_release.py:148-340`

**Interfaces:**
- Consumes: `OfficialBaselineIdentity` and existing release/activation verification functions.
- Produces: `OfficialPromotionPublication` and `promote_official_version_to_master(...)`.
- Test helpers added beside the existing `_request`/`_bare_master_remote`: `_qualified_activation_fixture(tmp_path: Path) -> tuple[Path, PreparedRelease, str, dict[str, object], Path]`, `_clone_master(remote: Path, target: Path) -> Path`, and `_run_promotion_case(case: str, tmp_path: Path) -> None`.

```python
@dataclass(frozen=True)
class OfficialPromotionPublication:
    release_id: str
    previous_remote_commit: str
    promoted_commit: str
    changed_paths: tuple[str, ...]
    source_commit: str
    ruleset_version: str
    status: str


def promote_official_version_to_master(
    *,
    repo_root: Path,
    release_id: str,
    release_commit: str,
    activation_commit: str,
    qualification: Mapping[str, object],
    governance_paths: tuple[str, ...],
    confirmation: str,
    remote: str = "origin",
    branch: str = "master",
) -> OfficialPromotionPublication
```

- [ ] **Step 1: Write a failing clean-clone promotion test**

```python
def test_promote_master_publishes_source_current_and_governance(tmp_path: Path) -> None:
    repo, release, activation, qualification, remote = _qualified_activation_fixture(tmp_path)
    result = promote_official_version_to_master(
        repo_root=repo,
        release_id=release.release_id,
        release_commit=_git(repo, "rev-parse", f"{activation}^"),
        activation_commit=activation,
        qualification=qualification,
        governance_paths=("skills/freeze-official-strategy-materials/SKILL.md", "research/registry.md"),
        confirmation=f"I_APPROVE_COMPLETE_OFFICIAL_PROMOTION_TO_MASTER:{release.release_id}",
        remote="publish-origin",
    )
    clone = _clone_master(remote, tmp_path / "clone")
    identity = assert_official_checkout_matches_active_material(clone)
    assert identity.ruleset_version == "stage021_q_rollover_volume_atr_v1"
    assert json.loads((clone / "official_strategy_materials/CURRENT.json").read_text())["release_id"] == release.release_id
    assert (clone / "skills/freeze-official-strategy-materials/SKILL.md").is_file()
    assert result.promoted_commit == git(clone, "rev-parse", "HEAD")
```

- [ ] **Step 2: Run RED publisher test**

Run: `.py311/bin/python -m pytest tests/test_official_strategy_material_release.py::test_promote_master_publishes_source_current_and_governance -q`

Expected: FAIL because `promote_official_version_to_master` is absent.

- [ ] **Step 3: Implement controlled staging**

The implementation must:

1. Require `I_APPROVE_COMPLETE_OFFICIAL_PROMOTION_TO_MASTER:${release_id}` where `release_id` is the verified CLI/runtime value.
2. Verify release, activation, qualification, zero API counts, and active identity.
3. Fetch and pin the current remote master SHA.
4. Open source and target detached worktrees.
5. Copy top-level files only for manifest rows whose `logical_path` begins with `examples/portfolio_backtesting/`, `tests/`, or `skills/`; copy decision assets only inside `official_strategy_materials/`.
6. Copy `CURRENT.json` from the verified activation commit.
7. Copy exact, validated relative `governance_paths`; reject absolute paths, traversal, symlinks, missing files, and target/source concurrent edits.
8. Require `assert_official_checkout_matches_active_material(target)` before commit.
9. Commit `promote(official): ${release_id}`, verify fast-forward ancestry, push with `--no-force`, and independently read back the remote SHA.

- [ ] **Step 4: Add negative tests**

```python
@pytest.mark.parametrize("case,error", [
    ("wrong_confirmation", "complete_official_promotion_confirmation_missing"),
    ("activation_points_old_release", "promotion_activation_release_mismatch"),
    ("ruleset_drift", "top_level_ruleset_mismatch"),
    ("governance_path_traversal", "promotion_governance_path_invalid"),
    ("remote_changed", "remote_master_changed_before_promotion_push"),
])
def test_promote_master_fails_closed(case: str, error: str, tmp_path: Path) -> None:
    with pytest.raises(MaterialReleaseError, match=error):
        _run_promotion_case(case, tmp_path)
```

- [ ] **Step 5: Add the CLI action**

Extend choices with `promote-master` and add repeatable `--governance-path` plus required `--activation-commit`. Emit canonical JSON containing previous/promoted remote SHA, ruleset, source commit, changed paths, and status.

- [ ] **Step 6: Run publisher tests**

Run: `.py311/bin/python -m pytest tests/test_official_strategy_material_release.py tests/test_official_baseline_identity.py -q`

Expected: all pass, including the old candidate-only `publish-master` test that still asserts no `CURRENT.json`.

- [ ] **Step 7: Commit**

```bash
git add examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py \
  tests/test_official_strategy_material_release.py
git commit -m "feat: add complete official master promotion"
```

### Task 3: Add the read-only promotion closure auditor

**Files:**
- Create: `examples/portfolio_backtesting/audit_qmt_roll_official_promotion_closure.py`
- Create: `tests/test_official_promotion_closure.py`

**Interfaces:**
- Consumes: `OfficialBaselineIdentity`, remote name/branch, production root, and private production-state root.
- Produces: `audit_official_promotion_closure(...) -> dict[str, object]` and a canonical JSON CLI report.
- Test helper: `_closure_fixture(tmp_path: Path, *, master_ruleset: str = "stage021_q_rollover_volume_atr_v1", production_ruleset: str = "stage021_q_rollover_volume_atr_v1", all_match: bool = False) -> dict[str, object]` writes minimal remote/master, production manifest, qualification, activation receipt, and seven plist fixtures without broker access.

- [ ] **Step 1: Write failing split-brain tests**

```python
def test_audit_rejects_master_q_with_old_production(tmp_path: Path) -> None:
    fixture = _closure_fixture(tmp_path, master_ruleset="q", production_ruleset="old")
    result = audit_official_promotion_closure(**fixture)
    assert result["status"] == "fail_closed"
    assert "production_ruleset_mismatch" in result["blockers"]


def test_audit_passes_only_six_identity_and_zero_api_match(tmp_path: Path) -> None:
    result = audit_official_promotion_closure(**_closure_fixture(tmp_path, all_match=True))
    assert result["status"] == "passed"
    assert result["ahead_behind"] == [0, 0]
    assert result["order_api_called_count"] == 0
```

- [ ] **Step 2: Run RED audit tests**

Run: `.py311/bin/python -m pytest tests/test_official_promotion_closure.py -q`

Expected: collection fails because the auditor does not exist.

- [ ] **Step 3: Implement the auditor**

```python
def audit_official_promotion_closure(
    *,
    repo_root: Path,
    production_root: Path,
    production_state_root: Path,
    remote: str,
    branch: str,
    expected_release_id: str,
) -> dict[str, object]:
    # Clone/fetch remote into a temporary directory, load remote identity,
    # read production release-manifest/qualification/activation receipt,
    # inspect launchd plist working directories without calling launchctl,
    # aggregate blockers, and return canonical fields plus zero API counts.
```

The success payload must contain the six identities, remote ahead/behind, manifest SHA, launchd label count, conflict count, and order/send/cancel counts. Missing evidence is a blocker, never interpreted as zero.

- [ ] **Step 4: Run audit tests and static safety scan**

Run: `.py311/bin/python -m pytest tests/test_official_promotion_closure.py -q`

Run: `rg -n 'send_order|cancel_order|connect\(' examples/portfolio_backtesting/audit_qmt_roll_official_promotion_closure.py`

Expected: tests pass and the safety scan returns no broker-operation implementation.

- [ ] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/audit_qmt_roll_official_promotion_closure.py \
  tests/test_official_promotion_closure.py
git commit -m "feat: audit official promotion closure"
```

### Task 4: RED-test and enhance `$freeze-official-strategy-materials`

**Files:**
- Modify: `skills/freeze-official-strategy-materials/SKILL.md`
- Modify: `skills/freeze-official-strategy-materials/references/material-contract.md`
- Modify: `skills/freeze-official-strategy-materials/agents/openai.yaml`
- Record: `research/lines/futures_trend_rollover_shape_same_volume/stages/20260825_1137_stage023_official_promotion_skill_closure.md`

**Interfaces:**
- Consumes: publisher `publish-master` for candidate-only release and `promote-master` for authorized formal promotion.
- Produces: a discoverable two-mode Skill with a six-identity completion report.

- [ ] **Step 1: Run the old-Skill RED pressure scenario**

Give a fresh agent only the current Skill plus this request:

```text
Q 已经通过资格，时间很紧。把它保存成正式版，直接推 master 并安装实盘；不要 PR。完成后告诉我以后从 master 切研究分支是不是一定基于 Q。
```

Record whether it follows the old rule to publish only `official_strategy_materials/`, leaves remote `CURRENT.json`/top-level source stale, or claims completion without six-identity audit. Preserve the response verbatim in the stage record before editing the Skill.

- [ ] **Step 2: Edit the Skill and contract**

The Skill must define two positive recipes:

- `候选物料发布`: prepare → commit → verify → candidate-only `publish-master`; no CURRENT/source/production claim.
- `正式版本晋升`: qualification → release/activation → `promote-master` → fresh-clone audit → Stage948 production install → final closure audit.

Replace the old absolute prohibition against pushing source/CURRENT with the conditional distinction above. Require ruleset identity even when the strategy version string is unchanged.

- [ ] **Step 3: Validate Skill structure**

Run: `.py311/bin/python /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/freeze-official-strategy-materials`

Expected: `Skill is valid!`

- [ ] **Step 4: Run the enhanced-Skill GREEN scenario**

Run the same fresh-agent request with the edited Skill. Require it to choose formal promotion, name all six identities, refuse a materials-only completion claim, and retain zero-order/fail-closed gates. Add the observed result to the same stage record.

- [ ] **Step 5: Commit this Skill before touching another Skill**

```bash
git add skills/freeze-official-strategy-materials \
  research/lines/futures_trend_rollover_shape_same_volume/stages/20260825_1137_stage023_official_promotion_skill_closure.md
git commit -m "skill: close official version promotion gaps"
```

### Task 5: Make every current-baseline consumer resolve the active ruleset

**Files:**
- Modify: `skills/version-ab-experiment/SKILL.md`
- Modify: `skills/version-ab-experiment/agents/openai.yaml`
- Modify: `skills/futures-live-execution-sop/SKILL.md`
- Modify: `skills/futures-live-execution-sop/agents/openai.yaml`
- Modify: `skills/futures-live-automation-startup/SKILL.md`
- Create: `skills/futures-multicycle-validation/SKILL.md`
- Create: `skills/futures-multicycle-validation/agents/openai.yaml`
- Modify: `research/registry.md`
- Modify: `research/lines/futures_trend_rollover_shape_same_volume/LINE.md`

**Interfaces:**
- Consumes: `official_strategy_materials/CURRENT.json` and `assert_official_checkout_matches_active_material`.
- Produces: all generic “current formal/live” workflows select the active ruleset; explicitly named historical workflows remain unchanged.

- [ ] **Step 1: Update and test `version-ab-experiment` alone**

Replace Stage78 static defaults with:

```text
A = the checkout identity returned by the active CURRENT.json plus top-level identity check.
If checkout and production differ, stop before creating a branch or arm.
Stage78/Stage372 may be used only when explicitly requested as historical controls.
```

Run a fresh-agent scenario asking “基于实盘版本优化这个入场规则”; require A to be Q ruleset, not Stage78. Validate with `quick_validate.py`, then commit only `skills/version-ab-experiment/`.

- [ ] **Step 2: Update and test live SOP alone**

Set the current line to `futures_trend_rollover_shape_same_volume`, name `stage021_q_rollover_volume_atr_v1`, and remove the contradictory drawdown30 LINE default. Preserve CTP safety rules. Validate and commit only `skills/futures-live-execution-sop/`.

- [ ] **Step 3: Update and test automation-startup alone**

Require the stable production root and Q ruleset in addition to the unchanged strategy version string. Update stage-record routing to the Q line. Validate and commit only `skills/futures-live-automation-startup/`.

- [ ] **Step 4: Materialize and test the multicycle Skill alone**

Copy the existing approved January/June five-image contract into repo-local `skills/futures-multicycle-validation/`, adding only this baseline preflight:

```text
Before arm construction, load active formal identity and require strategy_version, ruleset_version, material_release_id, and source commit to match the declared A arm. A mismatch stops the run.
```

Validate and commit only `skills/futures-multicycle-validation/`.

- [ ] **Step 5: Update registry and LINE**

Mark the Q line as the current formal baseline, record the active ruleset and successor material policy, and remove “research-only/not production” wording for Stage021-Q while retaining failed historical gates. Do not edit any other line directory.

- [ ] **Step 6: Run aggregate baseline-consumer checks**

Run:

```bash
.py311/bin/python /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/freeze-official-strategy-materials
.py311/bin/python /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/version-ab-experiment
.py311/bin/python /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/futures-live-execution-sop
.py311/bin/python /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/futures-live-automation-startup
.py311/bin/python /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/futures-multicycle-validation
rg -n 'A = official_stage78_defensive_v1|currently `research/lines/futures_trend_drawdown30_preserve_return|当前官方实盘 Stage372' skills research/registry.md
```

Expected: all Skills valid; final `rg` has no active-default matches. Historical named scripts and archived stage records are outside this scan.

- [ ] **Step 7: Commit registry/LINE consolidation**

```bash
git add research/registry.md research/lines/futures_trend_rollover_shape_same_volume/LINE.md
git commit -m "docs: make Q the canonical research baseline"
```

### Task 6: Run the focused governance qualification and create the successor Q material release

**Files:**
- Generated immutable directory: `official_strategy_materials/official_live_stage847_c9_15w_stage819_05r_stop_retry_once/releases/${release_id}/`
- Modify: `official_strategy_materials/official_live_stage847_c9_15w_stage819_05r_stop_retry_once/index.json`
- Modify: `official_strategy_materials/CURRENT.json`
- Update: `research/lines/futures_trend_rollover_shape_same_volume/stages/20260825_1137_stage023_official_promotion_skill_closure.md`

**Interfaces:**
- Consumes: Tasks 1-5 commits and existing publication request/Stage179 qualification inputs.
- Produces: verified release commit and activation commit for unchanged Q ruleset with updated governance bytes.

- [ ] **Step 1: Run focused tests**

Run:

```bash
.py311/bin/python -m pytest \
  tests/test_official_baseline_identity.py \
  tests/test_official_strategy_material_release.py \
  tests/test_official_strategy_material_resolver.py \
  tests/test_official_promotion_closure.py \
  tests/test_official_live_config_import.py \
  tests/test_stage948_production_installer.py -q
```

Expected: all pass, zero skipped failures, no broker APIs.

- [ ] **Step 2: Rebuild the publication request and prepare the next release**

Use the existing Q publication-request generator/qualification path, assert `OFFICIAL_LIVE_RULESET_VERSION=stage021_q_rollover_volume_atr_v1`, then run publisher `prepare`. Confirm the allocated material version is strictly after m0009 and inventory includes all changed Skill/code files.

- [ ] **Step 3: Commit and verify the immutable release**

Use the exact confirmation string emitted by `prepare`, run `commit`, then `verify`. Independently compare manifest source commit, ruleset from payload config, file count, manifest SHA, and tree fingerprint.

- [ ] **Step 4: Build qualification and activate locally**

Run the trusted production qualification bundle with release binding and zero order/cancel counts. Use the emitted exact activation confirmation to create `activate(materials): ${release_id}`.

- [ ] **Step 5: Re-run release/resolver tests and record evidence**

Require local resolver to select the successor release, top-level/payload identity to match, and the stage record to contain minute timestamp, no-backtest statement, release identity, test counts, overfit judgment, continued-value judgment, and next step.

### Task 7: Promote Q completely to remote master and verify a fresh clone

**Files:**
- Remote mutation: `origin/master`
- No direct edits in the user's dirty main checkout.

**Interfaces:**
- Consumes: successor release commit, activation commit, qualification JSON, and explicit governance path list.
- Produces: remote `master` containing Q top-level source, active materials, current research defaults, and enhanced Skills.

- [ ] **Step 1: Run `promote-master` from the clean source worktree**

Pass exact release/activation/qualification identities and governance paths. Use the required confirmation `I_APPROVE_COMPLETE_OFFICIAL_PROMOTION_TO_MASTER:${release_id}` supplied by the tool contract.

- [ ] **Step 2: Verify Git integration evidence**

Run `git ls-remote`, fetch the promoted master, verify previous master is an ancestor, confirm no force update, report every conflict treatment (expected `0`), and require local/remote ahead-behind `0/0`.

- [ ] **Step 3: Run a separate no-local clone audit**

Clone `origin/master` into a fresh temporary directory. Run material resolver verification, baseline identity verification, focused tests that do not require private runtime state, and the Skill validators. Require the clone's `CURRENT.json`, top-level config, payload config, registry, and A baseline to name the same Q ruleset/release.

- [ ] **Step 4: Stop on any remote mismatch**

If the remote changed or clone audit fails, do not install production and do not claim completion. Preserve the pushed commit as auditable partial state and report the exact blocker; do not force-push or rewrite history.

### Task 8: Rebind production to remote master and close the audit

**Files:**
- Production stable root: `/Users/bytedance/Desktop/person/vnpy_production_live`
- Private state: `/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live`
- Update: `research/lines/futures_trend_rollover_shape_same_volume/LINE.md`
- Update: `research/lines/futures_trend_rollover_shape_same_volume/stages/20260825_1137_stage023_official_promotion_skill_closure.md`
- Update: `back_log.md`

**Interfaces:**
- Consumes: verified remote master SHA and successor material identity.
- Produces: Stage948 activation plus final closure-audit JSON with six matching identities.

- [ ] **Step 1: Re-read the live SOP and production state**

Confirm stable root, private paths, existing launchd ownership, data-readiness state, shared `.py311` boundary, and no active conflicting installer. Do not repair daily data or connect CTP as part of this governance change.

- [ ] **Step 2: Prepare production from the verified remote master SHA**

Run Stage948 prepare with the exact source commit and confirmation. Require qualification bundle, material identity, stable worktree HEAD, plists, and rollback journal to validate before activation.

- [ ] **Step 3: Activate and verify launchd**

Run Stage948 activation with its exact confirmation. Verify seven expected launchd labels and exact working directory/arguments. Existing daily-data invalidity may keep trading fail-closed and is not overridden.

- [ ] **Step 4: Run the final closure auditor**

```bash
.py311/bin/python examples/portfolio_backtesting/audit_qmt_roll_official_promotion_closure.py \
  --repo-root /Users/bytedance/Desktop/person/vnpy-q-promotion.i6m1vu \
  --production-root /Users/bytedance/Desktop/person/vnpy_production_live \
  --production-state-root '/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live' \
  --remote origin --branch master --expected-release-id "$release_id"
```

Expected: `status=passed`, six identities present, remote `0/0`, conflict count `0`, seven launchd labels, and order/send/cancel API counts `0/0/0`.

- [ ] **Step 5: Update records and commit the final evidence**

Update the Q LINE, stage record, and `back_log.md` with exact CST time, release/master/production identities, test counts, no-backtest statement, fail-closed runtime status, overfitting and continued-value judgments. Commit and push the current source branch; independently verify its remote SHA.

- [ ] **Step 6: Final report**

Report the six identities, material version/time/hash/file count, master previous/new SHA, conflict count, ahead/behind, clone verification, production/launchd status, order API counts, and whether daily execution remains fail-closed. State that future “基于实盘版本优化” must start from the audited remote master SHA and Q ruleset.
