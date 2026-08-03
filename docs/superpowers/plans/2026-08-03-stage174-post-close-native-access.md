# Stage174 Post-Close Native Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate every Stage174 TdApi/native read after `main_engine.close()`, preserve fail-closed evidence semantics, and install the qualified schema-v2 candidate through Stage948 without interrupting a live production session.

**Architecture:** Freeze the broker trading day while the CTP connection generation is valid, then make post-close evidence assembly consume only that Python string. Prove the boundary with a RED source-boundary regression plus a close-invalidating fake TdApi, keep normal vn.py shutdown, and permit production activation only after the exact candidate passes two formal read-only captures.

**Tech Stack:** Python 3.11 (`.py311/bin/python`), `unittest`/`pytest`, vn.py CTP gateway, Stage179 qualification builders, Stage948 production installer, macOS launchd.

## Global Constraints

- `main_engine.close()` 之后不得调用任何 TdApi/CTP native 方法。
- 缺失 `broker_trading_day` 必须正常 fail-closed，禁止关闭后 native 兜底。
- 不升级 `vnpy_ctp`，不采用 `os._exit()`，不改变 alpha、信号、数量、止损重试或报撤单路径。
- 不放宽 Stage927、Stage931、Stage948 或正式资格认证门禁。
- 不停止或打断当前生产会话；只有七个正式 launchd job 全部无 PID 时才允许激活。
- 正式资格必须包含两次独立 CTP 只读采集，且 send/cancel/order API 计数均为零。
- 所有仓库命令在 `/Users/bytedance/Desktop/person/vnpy_stage179_production_live` 执行，解释器固定为 `.py311/bin/python`。

---

### Task 1: Prove the Native Lifetime Bug RED, Then Apply the Minimal GREEN Fix

**Files:**
- Modify: `tests/test_stage174_query_bundle.py`
- Inspect: `examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py:1950-2010`

**Interfaces:**
- Consumes: `stage174._run_probe` and the existing mocked CTP reconnect fixture.
- Produces: tests that reject any `getTradingDay` reference after the first `main_engine.close()` call and observe zero post-close calls on a fake TdApi.

- [ ] **Step 1: Add the source-boundary regression**

Add `import inspect` and this test to `Stage174ReadonlyQueryBundleTest`:

```python
def test_run_probe_never_reads_native_trading_day_after_close(self) -> None:
    source = inspect.getsource(stage174._run_probe)
    post_close_source = source.split("main_engine.close()", 1)[1]

    self.assertNotIn("getTradingDay", post_close_source)
```

- [ ] **Step 2: Strengthen the existing mocked reconnect fixture**

In `test_mocked_ctp_slow_callbacks_rebuild_full_snapshot_after_reconnect`, add lifetime state to `FakeTdApi` and invalidate it in `FakeMainEngine.close()`:

```python
# FakeTdApi.__init__
self.native_closed = False
self.post_close_trading_day_calls = 0

# FakeTdApi.getTradingDay
if self.native_closed:
    self.post_close_trading_day_calls += 1
    raise AssertionError("native_trading_day_read_after_close")
return "20260719"

# FakeMainEngine.close
self.gateway.td_api.onFrontDisconnected(0)
self.gateway.td_api.native_closed = True
```

Declare a holder immediately before `FakeMainEngine`, populate it in
`add_gateway()`, and assert it after `_run_probe()`:

```python
fake_td_api_holder: dict[str, FakeTdApi] = {}

# FakeMainEngine.add_gateway, after self.gateway = gateway_class()
fake_td_api_holder["td_api"] = self.gateway.td_api

# after _run_probe returns
self.assertEqual(
    0,
    fake_td_api_holder["td_api"].post_close_trading_day_calls,
)
```

- [ ] **Step 3: Run only the new boundary test and verify RED**

Run:

```bash
.py311/bin/python -m pytest -q \
  tests/test_stage174_query_bundle.py::Stage174ReadonlyQueryBundleTest::test_run_probe_never_reads_native_trading_day_after_close
```

Expected: FAIL because current post-close code still contains `getTradingDay`.

- [ ] **Step 4: Preserve the RED evidence**

Record the exact failing assertion and command for the Stage209 research record. Do not commit the failing-only state.

#### Phase B: Remove the Post-Close Native Fallback and Prove Fail-Closed Behavior

**Files:**
- Modify: `examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py:1995-2005`
- Modify: `tests/test_stage174_query_bundle.py`

**Interfaces:**
- Consumes: the Python value already frozen in `summary["broker_trading_day"]` during the valid connection generation.
- Produces: `_frozen_broker_trading_day(summary: dict[str, Any]) -> str`, which cannot receive or call a TdApi.

- [ ] **Step 1: Add the frozen-state helper**

Immediately after `_clean_ctp_text`, add:

```python
def _frozen_broker_trading_day(summary: dict[str, Any]) -> str:
    """Return only the trading day frozen before native shutdown."""
    return _clean_ctp_text(summary.get("broker_trading_day"))
```

- [ ] **Step 2: Apply the minimal post-close implementation**

Replace the post-close fallback:

```python
broker_trading_day = _clean_ctp_text(
    summary.get("broker_trading_day")
    or getattr(td_api, "getTradingDay", lambda: "")()
)
```

with:

```python
broker_trading_day = _frozen_broker_trading_day(summary)
```

Do not change the earlier valid-generation call that freezes `summary["broker_trading_day"]`.

- [ ] **Step 3: Add explicit frozen-state tests**

Add this test to `Stage174ReadonlyQueryBundleTest`:

```python
def test_frozen_broker_trading_day_never_falls_back_to_native(self) -> None:
    self.assertEqual("", stage174._frozen_broker_trading_day({}))
    self.assertEqual(
        "20260719",
        stage174._frozen_broker_trading_day(
            {"broker_trading_day": " 20260719 "}
        ),
    )
```

The helper's interface accepts only the frozen summary. An empty value therefore stays empty and makes the existing bundle completeness checks fail closed. The close-invalidating fake in Task 1 separately proves the integrated lifetime boundary.

- [ ] **Step 4: Run the boundary and frozen-state tests and verify GREEN**

Run:

```bash
.py311/bin/python -m pytest -q \
  tests/test_stage174_query_bundle.py::Stage174ReadonlyQueryBundleTest::test_run_probe_never_reads_native_trading_day_after_close \
  tests/test_stage174_query_bundle.py::Stage174ReadonlyQueryBundleTest::test_frozen_broker_trading_day_never_falls_back_to_native \
  tests/test_stage174_query_bundle.py::Stage174ReadonlyQueryBundleTest::test_mocked_ctp_slow_callbacks_rebuild_full_snapshot_after_reconnect
```

Expected: all three pass; fake TdApi post-close count is zero.

- [ ] **Step 5: Confirm the native boundary mechanically**

Run:

```bash
rg -n "main_engine.close|getTradingDay" \
  examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py
```

Expected: every `getTradingDay` occurrence precedes `main_engine.close()`.

---

### Task 2: Run the Required Regression Matrix and Record Stage209

**Files:**
- Test: `tests/test_stage174_query_bundle.py`
- Test: `tests/test_official_live_late_retry_fill.py`
- Test: `tests/test_stage904_durable_state_integration.py`
- Create: `research/lines/futures_trend_stage819_intraday_rules/stages/20260803_1610_stage209_stage174_post_close_native_access_repair.md`

**Interfaces:**
- Consumes: the minimal Stage174 lifetime fix and the prior schema-v2 manual-fill adoption patch.
- Produces: a clean, exact candidate commit with Chinese evidence for RED/GREEN, regressions, scope, risk, and deployment boundary.

- [ ] **Step 1: Run syntax validation**

Run:

```bash
.py311/bin/python -m py_compile \
  examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py \
  examples/portfolio_backtesting/qmt_roll_official_live_late_retry_fill.py
```

Expected: exit 0 with no output.

- [ ] **Step 2: Run the required regression matrix**

Run:

```bash
.py311/bin/python -m pytest -q \
  tests/test_stage174_query_bundle.py \
  tests/test_official_live_late_retry_fill.py \
  tests/test_stage904_durable_state_integration.py \
  -p no:cacheprovider
```

Expected: all tests pass. A failure blocks qualification.

- [ ] **Step 3: Write the Stage209 Chinese record**

The record must state the minute-level change time, root cause (`TdApi::getTradingDay()` after close), the exact RED/GREEN commands and outcomes, changed/deleted/added parameters (all none), unchanged alpha/order semantics, test totals, qualification not yet claimed, rollback boundary, and these judgments:

```text
是否过拟合：否。修复约束 native 生命周期，不依赖行情样本、品种或收益参数。
是否值得继续：是。它解除正式只读资格认证的确定性崩溃，但仍保留全部 fail-closed 门禁。
```

Because no backtest is run, explicitly mark return, drawdown, Sharpe, slippage, trade count, and win-rate fields as `本次未运行回测，不新增或修改结果`.

- [ ] **Step 4: Inspect the exact diff**

Run:

```bash
git diff --check
git diff -- \
  examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py \
  tests/test_stage174_query_bundle.py \
  research/lines/futures_trend_stage819_intraday_rules/stages/20260803_1610_stage209_stage174_post_close_native_access_repair.md
```

Expected: only the lifetime fix, regression coverage, and truthful Stage209 record are present.

- [ ] **Step 5: Commit the repair**

Run:

```bash
git add \
  examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py \
  tests/test_stage174_query_bundle.py \
  research/lines/futures_trend_stage819_intraday_rules/stages/20260803_1610_stage209_stage174_post_close_native_access_repair.md
git commit -m "fix(stage174): forbid native reads after close"
git status --short
```

Expected: commit succeeds and the worktree is clean.

---

### Task 3: Freeze an Exact Reviewed Candidate and Build Formal Qualification

**Files/state:**
- Review: `a3c3853605c941041f14355c9c3fb0685b2dbaf7..HEAD`
- Create outside Git: `~/Library/Application Support/qmt-roll-stage179/production-live/independent-review/stage209-$stage209_candidate_commit.json`
- Create outside Git: a new sibling qualification bundle bound to the same commit.

**Interfaces:**
- Consumes: clean candidate commit, formal `ctp_live.local.env`, production CTP framework ordering, and current private production state.
- Produces: an independent report with no P0/P1 and a qualification bundle containing two valid formal read-only captures.

- [ ] **Step 1: Verify runtime and quiescence preconditions**

Run read-only checks for disk free space, `git status --short`, `git rev-parse HEAD`, `ctp_live.local.env` presence/permissions, CTP framework resolution, the seven expected launchd labels, and every label's PID. If any trading/session job still has a PID, wait for natural exit; do not stop, bootout, kickstart, or activate it.

- [ ] **Step 2: Review the exact candidate**

Review the full diff and test evidence for spec compliance, post-close native reachability, missing-day fail-closed behavior, schema-v2 compatibility, query-generation integrity, mutation firewall coverage, unchanged order behavior, and test confidence. Every finding must contain `finding_id`, severity `P0`/`P1`/`P2`, and status. Fix all P0/P1, rerun affected and full tests, update Stage209, commit, and restart exact-commit review.

- [ ] **Step 3: Create the private exact-commit review artifact**

After the exact review returns no findings, create a mode-`0600` report with this exact command. If the reviewer returns P2 findings, replace the empty `findings` list with those exact `finding_id`, `severity`, and `status` rows before writing; P0/P1 must be fixed before this step.

```bash
stage209_candidate_commit="$(git rev-parse HEAD)"
stage209_review_dir="$HOME/Library/Application Support/qmt-roll-stage179/production-live/independent-review"
STAGE209_SOURCE_COMMIT="$stage209_candidate_commit" \
STAGE209_REVIEW_DIR="$stage209_review_dir" \
.py311/bin/python - <<'PY'
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

repo = Path("/Users/bytedance/Desktop/person/vnpy_stage179_production_live")
sys.path.insert(0, str(repo / "examples" / "portfolio_backtesting"))
from build_qmt_roll_stage179_release_manifest import DEFAULT_CRITICAL_FILES
from qmt_roll_official_live_release_manifest import (
    release_critical_file_rows,
    release_tree_fingerprint,
)

source_commit = os.environ["STAGE209_SOURCE_COMMIT"]
review_dir = Path(os.environ["STAGE209_REVIEW_DIR"])
review_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
rows = release_critical_file_rows(
    repo_root=repo,
    critical_files=DEFAULT_CRITICAL_FILES,
)
payload = {
    "schema_version": 1,
    "artifact_kind": "independent_production_review_report",
    "review_id": f"stage209-native-safety-{source_commit[:12]}",
    "reviewer_identity": "codex-independent-stage209-review-v1",
    "reviewed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "source_commit": source_commit,
    "tree_fingerprint": release_tree_fingerprint(rows),
    "findings": [],
}
target = review_dir / f"stage209-{source_commit}.json"
target.write_text(
    json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    encoding="utf-8",
)
target.chmod(0o600)
print(target)
PY
```

Verify the emitted report's `source_commit` equals the still-clean `git rev-parse HEAD` and its mode is `0600`.

- [ ] **Step 4: Build a fresh trusted qualification bundle**

Freeze the verified 40-character `HEAD` in a task-specific shell variable, then run:

```bash
stage209_candidate_commit="$(git rev-parse HEAD)"
.py311/bin/python \
  examples/portfolio_backtesting/build_qmt_roll_stage179_production_qualification_bundle.py \
  --output-dir "$HOME/Library/Application Support/qmt-roll-stage179/production-live/qualification-bundle-stage209-$stage209_candidate_commit" \
  --repo-root /Users/bytedance/Desktop/person/vnpy_stage179_production_live \
  --review-report "$HOME/Library/Application Support/qmt-roll-stage179/production-live/independent-review/stage209-$stage209_candidate_commit.json" \
  --confirm-trusted-production-qualification-run I_APPROVE_RUNNING_EXACT_TESTS_AND_TWO_FORMAL_CTP_READONLY_CAPTURES
```

Expected: fixed test suites pass, both formal CTP captures exit normally, both query bundles are complete and source-bound, P0/P1 are zero, and all send/cancel/order/native-mutation counts are zero. Any SIGSEGV, handshake, source mismatch, incomplete evidence, counter anomaly, or nonzero exit blocks production.

- [ ] **Step 5: Promote the valid qualification bundle atomically**

Only after validating the new bundle, move the previous canonical `qualification-bundle` to a timestamped private backup and move the new sibling to canonical `qualification-bundle` within the same filesystem. Preserve directory mode `0700` and file mode `0600`. Do not delete the backup.

---

### Task 4: Build the Release and Activate Only Through Stage948

**Files/state:**
- Private release: `~/Library/Application Support/qmt-roll-stage179/production-live/release-manifest.json`
- Private activation receipt: `~/Library/Application Support/qmt-roll-stage179/production-live/runtime/state/activation_receipt.json`
- Stable: `/Users/bytedance/Desktop/person/vnpy_production_live`
- Launchd: exactly seven C9/15万 production labels.

**Interfaces:**
- Consumes: canonical qualification bound to the exact clean candidate commit.
- Produces: matching release manifest, activation receipt, stable worktree and seven-label launchd installation, with zero activation-side CTP/order calls.

- [ ] **Step 1: Build the production release manifest**

Run:

```bash
.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py \
  --output "$HOME/Library/Application Support/qmt-roll-stage179/production-live/release-manifest.json" \
  --release-id "stage209-stage174-native-safety-$(git rev-parse --short=12 HEAD)" \
  --execution-profile c9-15w \
  --allow-production-live \
  --production-qualification-evidence "$HOME/Library/Application Support/qmt-roll-stage179/production-live/qualification-bundle/qualification.json" \
  --confirm-production-live-manifest I_UNDERSTAND_THIS_BUILDS_A_C9_15W_PRODUCTION_LIVE_RELEASE_MANIFEST
```

Expected: exit 0 and manifest source commit equals clean `HEAD`.

- [ ] **Step 2: Build the activation receipt bound to the same evidence**

Run:

```bash
.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_stage179_activation_receipt.py \
  --output "$HOME/Library/Application Support/qmt-roll-stage179/production-live/runtime/state/activation_receipt.json" \
  --release-manifest "$HOME/Library/Application Support/qmt-roll-stage179/production-live/release-manifest.json" \
  --production-qualification-evidence "$HOME/Library/Application Support/qmt-roll-stage179/production-live/qualification-bundle/qualification.json" \
  --confirm-production-activation I_APPROVE_C9_15W_PRODUCTION_LIVE_ACTIVATION_RECEIPT \
  --repo-root /Users/bytedance/Desktop/person/vnpy_stage179_production_live
```

Expected: exit 0 and receipt source commit, release manifest digest, qualification digest and C9/15万 identity all match the candidate.

- [ ] **Step 3: Recheck activation quiescence**

Immediately before prepare/activate, verify disk/runtime guards again and confirm all seven jobs have no PID. Any live PID blocks activation and leaves stable untouched.

- [ ] **Step 4: Prepare through Stage948**

Run:

```bash
.py311/bin/python examples/portfolio_backtesting/install_qmt_roll_stage948_official_live_production.py \
  --source-commit "$(git rev-parse HEAD)" \
  --confirm-prepare I_UNDERSTAND_THIS_PREPARES_C9_15W_PRODUCTION_ASSETS
```

Expected: prepared source, qualification, release and runtime assets all bind to the same exact commit; no launchctl or CTP operation occurs.

- [ ] **Step 5: Activate the prepared release through Stage948**

Run:

```bash
.py311/bin/python examples/portfolio_backtesting/install_qmt_roll_stage948_official_live_production.py \
  --activate-prepared \
  --confirm-activate I_UNDERSTAND_THIS_LOADS_C9_15W_PRODUCTION_LAUNCHD_JOBS
```

Expected: `production_launchd_activated_no_ctp_connection`, exactly `7/7/7` production domain/installed/loaded surfaces, conflicts 0, rollback 0, and activation CTP/send/cancel/order counts `0/0/0/0`.

- [ ] **Step 6: Verify final production identity and health**

Verify:

```text
stable HEAD = release manifest source_commit = qualification source_commit = activation receipt source_commit
expected launchd labels = installed labels = loaded labels = exactly 7
activation CTP connect/query/send/cancel/order counts = 0
production stable worktree = clean
```

Run the Stage946 production health check in its read-only mode and inspect the latest summary. Do not manually start a trading session outside its scheduled window. If any identity, label, permission, health, or zero-API check fails, report the blocker and preserve/restore the prior stable release through Stage948 rollback semantics.

- [ ] **Step 7: Finish the Stage209 record without rewriting history**

Append the actual qualification/activation evidence IDs, timestamps, exact commit, seven-label counts, zero API counts, and final overfitting/value judgment to the Stage209 stage file, then commit that documentation only if doing so does not invalidate the already activated source-commit contract. If the release contract requires exact source immutability, create a follow-up deployment record instead and leave the activated commit unchanged.
