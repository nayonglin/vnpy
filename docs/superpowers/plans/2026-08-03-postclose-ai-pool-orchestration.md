# C9/15w Post-close AI Pool Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three clock-coupled post-close support jobs with one receipt-driven coordinator that refreshes market data, updates the monthly AI pool when needed, regenerates shadow, issues the daily receipt, sends the final report, and suppresses downstream duplicate failure mail.

**Architecture:** Keep all seven production `launchd` labels and their current calendar times. The `postclose-precompute` label becomes the only side-effecting coordinator; `postclose-report` becomes a read-only receipt watchdog and `monthly-ai-pool` becomes a conditional one-shot retry. A new private pipeline receipt module owns run identity, stage transitions, atomic persistence, validation, and retry eligibility; Stage947 owns subprocess orchestration and email disposition.

**Tech Stack:** Python 3.11 from `.py311`, `unittest`, `unittest.mock`, JSON receipts, POSIX file locking, atomic `os.replace`, macOS `launchd`, existing Stage173/909/935/929 workers, Stage948 activation.

## Global Constraints

- Base commit is exactly `cc5ddf64f80711c0e3324b84bbbd3758c6581c26`; the existing Stage174 candidate worktree and branch must remain unchanged.
- Current official profile remains `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`, `c9-15w`, capital `150000`, capital label `15w`.
- Keep exactly seven production labels; do not rename labels, change stable root, or add CTP credentials to support-job environments.
- Preserve schedules: coordinator `16:35`, watchdog `16:55`, conditional retry `18:20` on weekdays.
- The AI pool is checked daily but updated only when the prior complete month-end eval date is absent.
- No strategy, AI ranking, TopN, training window, risk, stop, retry, product, or execution parameter changes.
- No CTP/native connection is permitted in coordinator, watchdog, retry, unit tests, or integration tests.
- Every path must report `send_order_api_called_count=0`, `cancel_order_api_called_count=0`, and `order_api_called_count=0`.
- Any source/manifest/receipt mismatch, incomplete evidence, unsafe file mode, nonzero API counter, SIGSEGV, handshake, or unexpected native access fails closed.
- Never stop, kill, bootout, or kickstart an active production job or warm executor.
- Production installation must wait until Stage174 `cc5ddf64...` has been activated first and all production PIDs later return to zero naturally.

---

## File Map

- Create `examples/portfolio_backtesting/qmt_roll_official_live_postclose_pipeline.py`: pipeline receipt schema, validation, atomic persistence, lock acquisition, stage transition, completion/failure, retry eligibility.
- Create `tests/test_official_live_postclose_pipeline.py`: receipt, security, transition, API-zero, concurrency, and retry unit tests.
- Modify `examples/portfolio_backtesting/run_qmt_roll_stage947_official_live_production_support_launcher.py`: coordinator, worker sequencing, report validation, watchdog, retry, root-failure disposition.
- Modify `tests/test_stage947_production_support_launcher.py`: ordered coordinator, month-change, failure propagation, watchdog, retry, and mail assertions.
- Modify `examples/portfolio_backtesting/qmt_roll_official_live_failure_notify.py`: optional pipeline metadata without changing the existing dedupe identity for callers that omit it.
- Modify `tests/test_official_live_failure_notify.py`: pipeline metadata sanitization and same-root suppression.
- Modify `tests/test_stage179_launchd_lifecycle.py`: exact three support schedules, seven-label preservation, and no-submit environment assertions.
- Modify `examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py`: include the new runtime module and its test in the immutable surface.
- Modify `tests/test_stage179_release_manifest.py`: assert the new files are release-covered.
- Create `research/lines/futures_trend_stage819_intraday_rules/stages/20260803_HHMM_stage210_postclose_ai_pool_orchestration.md`: Chinese operational record and evidence.
- Update `research/lines/futures_trend_stage819_intraday_rules/LINE.md`: only after the implementation is reviewed and becomes a formal candidate.

---

### Task 1: Private Pipeline Receipt State Machine

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_official_live_postclose_pipeline.py`
- Create: `tests/test_official_live_postclose_pipeline.py`

**Interfaces:**
- Produces: `new_postclose_pipeline_receipt(*, pipeline_run_id: str, schedule_date: str, target_date: str, source_commit: str, manifest_sha256: str, generated_at_utc: str) -> dict[str, Any]`
- Produces: `record_postclose_pipeline_stage(payload: Mapping[str, Any], *, stage: str, status: str, started_at_utc: str, finished_at_utc: str, blocker: str = "", outputs: Mapping[str, Any] | None = None) -> dict[str, Any]`
- Produces: `finish_postclose_pipeline_receipt(payload: Mapping[str, Any], *, status: str, root_blocker: str, email_disposition: Mapping[str, Any], daily_data_receipt_sha256: str = "", report_summary_sha256: str = "", retry_of: str = "", finished_at_utc: str) -> dict[str, Any]`
- Produces: `write_postclose_pipeline_receipt(path: Path, payload: Mapping[str, Any]) -> None`
- Produces: `load_and_validate_postclose_pipeline_receipt(path: Path, *, source_commit: str, manifest_sha256: str, schedule_date: str | None = None) -> dict[str, Any]`
- Produces: `postclose_pipeline_retry_eligible(payload: Mapping[str, Any]) -> bool`
- Produces: `open_postclose_pipeline_lock(path: Path) -> IO[str]`; uses non-blocking `fcntl.LOCK_EX | LOCK_NB` and raises `PostclosePipelineError("postclose_pipeline_lock_busy")`.

- [ ] **Step 1: Write schema and transition tests that fail because the module does not exist**

```python
def test_pipeline_requires_ordered_stages_and_zero_order_apis(self) -> None:
    payload = pipeline.new_postclose_pipeline_receipt(
        pipeline_run_id="a" * 32,
        schedule_date="2026-08-03",
        target_date="2026-08-03",
        source_commit="b" * 40,
        manifest_sha256="c" * 64,
        generated_at_utc="2026-08-03T08:35:00Z",
    )
    payload = pipeline.record_postclose_pipeline_stage(
        payload,
        stage="resolve-target",
        status="succeeded",
        started_at_utc="2026-08-03T08:35:00Z",
        finished_at_utc="2026-08-03T08:35:01Z",
    )
    self.assertEqual("running", payload["status"])
    self.assertEqual(0, payload["order_api_called_count"])
    with self.assertRaisesRegex(
        pipeline.PostclosePipelineError,
        "postclose_pipeline_stage_order_invalid",
    ):
        pipeline.record_postclose_pipeline_stage(
            payload,
            stage="generate-postclose-report",
            status="succeeded",
            started_at_utc="2026-08-03T08:35:02Z",
            finished_at_utc="2026-08-03T08:35:03Z",
        )
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `.py311/bin/python -m unittest tests.test_official_live_postclose_pipeline -v`

Expected: FAIL with `ModuleNotFoundError: qmt_roll_official_live_postclose_pipeline`.

- [ ] **Step 3: Implement the minimal canonical receipt schema and ordered transitions**

Define exact stage order:

```python
POSTCLOSE_PIPELINE_STAGES = (
    "resolve-target",
    "refresh-market-data",
    "check-monthly-ai-pool",
    "refresh-monthly-ai-pool",
    "refresh-shadow",
    "issue-daily-data-receipt",
    "generate-postclose-report",
)
```

Allow `refresh-monthly-ai-pool` status `skipped_not_required`; allow all later stages only after every earlier stage is `succeeded` or `skipped_not_required`. A terminal failure marks every later stage `skipped_upstream_failed` through `finish_postclose_pipeline_receipt`.

- [ ] **Step 4: Add atomic persistence, owner/mode validation, hash validation, and non-blocking lock tests**

Test exact failure codes:

```python
"postclose_pipeline_parent_security_invalid"
"postclose_pipeline_file_security_invalid"
"postclose_pipeline_payload_invalid"
"postclose_pipeline_source_commit_mismatch"
"postclose_pipeline_manifest_mismatch"
"postclose_pipeline_schedule_date_mismatch"
"postclose_pipeline_order_api_nonzero"
"postclose_pipeline_lock_busy"
```

The writer must use a `0600` temporary file in a `0700` parent, `fsync` the file and parent directory, `os.replace`, then load and validate the final bytes.

- [ ] **Step 5: Implement retry eligibility exactly**

```python
def postclose_pipeline_retry_eligible(payload: Mapping[str, Any]) -> bool:
    return (
        payload.get("status") == "failed"
        and payload.get("retry_of", "") == ""
        and payload.get("root_stage") == "refresh-monthly-ai-pool"
        and payload.get("root_blocker") in {
            "production_support_monthly_ai_pool_process_failed",
            "production_support_monthly_ai_pool_not_qualified",
            "production_support_monthly_receipt_refresh_failed",
        }
        and payload.get("order_api_called_count") == 0
    )
```

- [ ] **Step 6: Run Task 1 tests and commit**

Run:

```bash
.py311/bin/python -m unittest tests.test_official_live_postclose_pipeline -v
git diff --check
```

Expected: all Task 1 tests PASS and `git diff --check` is silent.

Commit:

```bash
git add examples/portfolio_backtesting/qmt_roll_official_live_postclose_pipeline.py tests/test_official_live_postclose_pipeline.py
git commit -m "feat: add private postclose pipeline receipt"
```

---

### Task 2: Serialize Market Data, Monthly AI Pool, Shadow, Receipt, and Report

**Files:**
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage947_official_live_production_support_launcher.py`
- Modify: `tests/test_stage947_production_support_launcher.py`

**Interfaces:**
- Consumes: all Task 1 receipt and lock functions.
- Produces: `_build_stage173_market_data_command(target_date: str) -> list[str]`
- Produces: `_run_monthly_ai_pool_worker(*, command: list[str], environment: Mapping[str, str]) -> dict[str, Any]`
- Produces: `_run_postclose_report_worker(*, command: list[str], environment: Mapping[str, str]) -> dict[str, Any]`
- Produces: `_run_postclose_pipeline(*, environment: Mapping[str, str], manifest: Mapping[str, Any], retry_of: str = "") -> dict[str, Any]`
- Produces: `_decode_worker_summary(stdout: str, *, expected_model_tag: str) -> dict[str, Any]` with strict final-JSON and API-zero checks.

- [ ] **Step 1: Write the failing ordered-call test**

```python
def test_postclose_pipeline_orders_monthly_before_final_shadow(self) -> None:
    calls: list[str] = []

    def run(command, **kwargs):
        name = Path(command[1]).name
        calls.append(name)
        return self._successful_worker_result(name)

    with self._pipeline_fixture(), patch.object(
        launcher.subprocess, "run", side_effect=run
    ):
        result = launcher._run_postclose_pipeline(
            environment=self.environment,
            manifest=self.manifest,
        )

    self.assertEqual(
        [
            "build_qmt_roll_stage173_forward_main_contract_data_update.py",
            "run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py",
            "run_qmt_roll_stage909_official_live_shadow_refresh_gate.py",
            "run_qmt_roll_stage929_official_live_15w_timed_cycle.py",
        ],
        calls,
    )
    self.assertEqual("succeeded", result["status"])
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `.py311/bin/python -m unittest tests.test_stage947_production_support_launcher.Stage947ProductionSupportLauncherTest.test_postclose_pipeline_orders_monthly_before_final_shadow -v`

Expected: FAIL because `_run_postclose_pipeline` is absent.

- [ ] **Step 3: Add the Stage173 pre-update command and strict worker decoder**

The command must be:

```python
[
    str(PYTHON_PATH),
    str(STAGE173_SCRIPT),
    "--mapping-start", target_date[:7] + "-01",
    "--bar-start", target_date,
    "--end", target_date,
]
```

After Stage173 exits zero, call `_resolve_support_target_date` again and require the same target date before Stage935. The later Stage909 full run intentionally repeats its own data validation/update; this redundancy is accepted as a safety revalidation and ensures its final shadow always uses the post-Stage935 AI pool.

- [ ] **Step 4: Refactor Stage935 execution so coordinator owns sequencing**

`_run_monthly_ai_pool_worker` returns only these terminal statuses:

```python
{
    "monthly_ai_pool_updated",
    "monthly_ai_pool_already_current",
}
```

Do not let this helper invoke Stage909. Preserve Stage935's existing `--email-policy changes`, so `monthly_ai_pool_updated` sends its informational email before the report and `already_current` sends none.

- [ ] **Step 5: Run Stage909, issue receipt, then run and validate Stage929**

Require the Stage909 summary invariants already enforced by `_run_precompute_and_issue_daily_receipt`. Change that helper to return the loaded daily receipt so the coordinator can record `receipt_sha256`.

For Stage929 require:

```python
summary["model_tag"] == "stage929_official_live_15w_timed_cycle_v1"
summary["target_date"] == target_date
summary["order_api_called_count"] == 0
summary["email_notification"]["email_status"] in {"sent", "dry_run_written"}
```

Hash the canonical Stage929 summary bytes into `report_summary_sha256`.

- [ ] **Step 6: Add month-change and normal-day tests**

Normal day assertions:

```python
self.assertEqual("monthly_ai_pool_already_current", monthly_status)
self.assertEqual(1, report_send_count)
self.assertEqual(0, ai_update_send_count)
```

Month-change assertions:

```python
self.assertEqual("monthly_ai_pool_updated", monthly_status)
self.assertLess(ai_email_index, report_email_index)
self.assertEqual(new_ai_sha256, receipt["signal_bundle"]["ai_eligibility_sha256"])
```

- [ ] **Step 7: Add fail-closed stage propagation tests**

For failures in Stage173, Stage935, Stage909, receipt issue, and Stage929, assert:

```python
self.assertEqual("failed", receipt["status"])
self.assertEqual(expected_stage, receipt["root_stage"])
self.assertEqual(expected_blocker, receipt["root_blocker"])
self.assertTrue(all(
    row["status"] == "skipped_upstream_failed"
    for row in receipt["stages"][failed_index + 1:]
))
self.assertEqual(0, receipt["order_api_called_count"])
```

- [ ] **Step 8: Run Task 2 tests and commit**

Run:

```bash
.py311/bin/python -m unittest tests.test_stage947_production_support_launcher -v
.py311/bin/python -m unittest tests.test_official_live_postclose_pipeline -v
git diff --check
```

Expected: all tests PASS.

Commit:

```bash
git add examples/portfolio_backtesting/run_qmt_roll_stage947_official_live_production_support_launcher.py tests/test_stage947_production_support_launcher.py
git commit -m "feat: serialize production postclose pipeline"
```

---

### Task 3: Watchdog, Conditional Retry, and One Root Failure Email

**Files:**
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage947_official_live_production_support_launcher.py`
- Modify: `tests/test_stage947_production_support_launcher.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_failure_notify.py`
- Modify: `tests/test_official_live_failure_notify.py`

**Interfaces:**
- Consumes: Task 1 receipt loader/retry predicate and Task 2 coordinator.
- Produces: `_inspect_postclose_pipeline_watchdog(*, manifest: Mapping[str, Any], schedule_date: str) -> dict[str, Any]`
- Produces: `_run_postclose_pipeline_retry(*, environment: Mapping[str, str], manifest: Mapping[str, Any], schedule_date: str) -> dict[str, Any]`
- Extends: `notify_official_live_failure(..., pipeline_run_id: str = "", root_stage: str = "") -> dict[str, Any]`.

- [ ] **Step 1: Write watchdog state tests and verify RED**

Use a table test for `running`, `succeeded`, `failed`, missing, corrupt, wrong source, and wrong manifest receipts. Expected dispositions:

```python
{
    "running": "deferred_pipeline_running",
    "succeeded": "already_satisfied",
    "failed": "root_failure_already_recorded",
}
```

Missing/corrupt/mismatched receipt raises a specific `ProductionSupportLaunchError` at boundary `postclose-pipeline-watchdog`; it never invokes Stage929.

- [ ] **Step 2: Implement `postclose-report` as a read-only watchdog**

Change `launch_support_job` routing:

```python
if spec.job == "postclose-precompute":
    _run_postclose_pipeline(...)
    return
if spec.job == "postclose-report":
    _print_watchdog(_inspect_postclose_pipeline_watchdog(...))
    return
```

The watchdog must not acquire the coordinator lock, spawn workers, mutate receipts, kickstart jobs, or send mail for valid `running/succeeded/failed` receipts.

- [ ] **Step 3: Write retry qualification tests and verify RED**

Assert that only a first-run terminal AI-pool failure retries. These cases must not retry:

```python
"running"
"succeeded"
"failed at refresh-market-data"
"failed at refresh-shadow"
"failed with retry_of already set"
"failed with any nonzero API counter"
```

- [ ] **Step 4: Implement `monthly-ai-pool` as the 18:20 conditional retry**

For an eligible receipt call:

```python
_run_postclose_pipeline(
    environment=environment,
    manifest=manifest,
    retry_of=str(receipt["pipeline_run_id"]),
)
```

When receipt is `running`, return `deferred_pipeline_running`; when successful or ineligible, return a zero-API no-op disposition. A lock-busy retry is a no-op `deferred_pipeline_running`, not a failure email.

- [ ] **Step 5: Extend failure notification metadata without weakening dedupe**

Keep the fingerprint based on release commit, schedule date, canonical root job, boundary, and blocker. Add sanitized `pipeline_run_id` and `root_stage` to state entries, body, and email metadata. Coordinator failures always use canonical job `postclose-pipeline`, so `postclose-report` and `monthly-ai-pool` cannot create a different fingerprint for the same root failure.

- [ ] **Step 6: Add one-root-email tests**

```python
first = notify(..., job="postclose-pipeline", pipeline_run_id="a" * 32)
second = notify(..., job="postclose-pipeline", pipeline_run_id="a" * 32)
self.assertEqual("sent", first["notification_status"])
self.assertEqual("suppressed_terminal", second["notification_status"])
self.assertEqual(1, sender.call_count)
```

Also assert pipeline metadata rejects secrets and unsafe characters, and an email helper failure is recorded without changing `root_blocker`.

- [ ] **Step 7: Run Task 3 tests and commit**

Run:

```bash
.py311/bin/python -m unittest tests.test_stage947_production_support_launcher -v
.py311/bin/python -m unittest tests.test_official_live_failure_notify -v
.py311/bin/python -m unittest tests.test_official_live_postclose_pipeline -v
git diff --check
```

Expected: all tests PASS.

Commit:

```bash
git add examples/portfolio_backtesting/run_qmt_roll_stage947_official_live_production_support_launcher.py tests/test_stage947_production_support_launcher.py examples/portfolio_backtesting/qmt_roll_official_live_failure_notify.py tests/test_official_live_failure_notify.py
git commit -m "fix: dedupe postclose root failure notifications"
```

---

### Task 4: Preserve the Seven-label Release Surface

**Files:**
- Modify: `tests/test_stage179_launchd_lifecycle.py`
- Modify: `examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py`
- Modify: `tests/test_stage179_release_manifest.py`

**Interfaces:**
- Consumes: new runtime and test files from Tasks 1-3.
- Produces: immutable release coverage for `qmt_roll_official_live_postclose_pipeline.py` and `tests/test_official_live_postclose_pipeline.py`.

- [ ] **Step 1: Tighten launchd schedule and no-submit tests**

Add exact assertions:

```python
self.assertEqual({16 * 60 + 35}, precompute_minutes)
self.assertEqual({16 * 60 + 55}, report_minutes)
self.assertEqual({18 * 60 + 20}, monthly_minutes)
self.assertEqual(7, len(production_labels))
```

Assert every support job lacks `CTP_`, `OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED`, `--mode live-real`, and `--submit-mode live-real`.

- [ ] **Step 2: Run lifecycle test and verify any missing assertion fails before manifest edits**

Run: `.py311/bin/python -m unittest tests.test_stage179_launchd_lifecycle -v`

Expected: existing behavior passes except the new release-surface assertions added next.

- [ ] **Step 3: Add the new module and test to the release critical surface**

Add exact strings:

```python
"examples/portfolio_backtesting/qmt_roll_official_live_postclose_pipeline.py",
"tests/test_official_live_postclose_pipeline.py",
```

Add the runtime module and test to `DEFAULT_CRITICAL_FILES`, and add
`tests/test_official_live_postclose_pipeline.py` to
`PRODUCTION_REQUIRED_TEST_SUITES`. Update the manifest test to require both
critical-file entries, require the new suite, and reject a candidate missing
either file.

- [ ] **Step 4: Run release-surface tests and commit**

Run:

```bash
.py311/bin/python -m unittest tests.test_stage179_launchd_lifecycle -v
.py311/bin/python -m unittest tests.test_stage179_release_manifest -v
git diff --check
```

Expected: all tests PASS; plist files remain byte-identical to the base unless a test proves a required content change.

Commit:

```bash
git add tests/test_stage179_launchd_lifecycle.py examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py tests/test_stage179_release_manifest.py
git commit -m "test: pin postclose coordinator release surface"
```

---

### Task 5: Full Verification, Operational Record, and Candidate Review

**Files:**
- Create: `research/lines/futures_trend_stage819_intraday_rules/stages/20260803_HHMM_stage210_postclose_ai_pool_orchestration.md`
- Modify: `research/lines/futures_trend_stage819_intraday_rules/LINE.md`

**Interfaces:**
- Consumes: all implementation and test evidence from Tasks 1-4.
- Produces: a clean reviewed candidate and Chinese stage record; no production mutation.

- [ ] **Step 1: Run the targeted regression suite**

Run:

```bash
.py311/bin/python -m unittest \
  tests.test_official_live_postclose_pipeline \
  tests.test_stage947_production_support_launcher \
  tests.test_official_live_failure_notify \
  tests.test_stage179_launchd_lifecycle \
  tests.test_stage179_release_manifest \
  tests.test_stage946_production_health_check \
  tests.test_stage945_production_launcher -v
```

Expected: all tests PASS, no CTP/native process starts, and test logs contain no secrets.

- [ ] **Step 2: Run release/fault/static gates used by the current candidate**

Use the exact gate commands recorded by the current Stage174 plan and Task 3 report, but build evidence under this branch's private candidate directory. Require all process exit codes zero, no SIGSEGV/handshake/source mismatch, P0/P1 zero, and API counters zero.

- [ ] **Step 3: Write the Chinese Stage210 record**

Record minute-level time, base commit, candidate HEAD, changed files, exact schedules, failure fixture for missing `2026-07-31`, ordered worker evidence, email counts, targeted test counts, release coverage, API zero counts, overfit judgment, continued-value judgment, and deployment dependency on Stage174 first activation. State explicitly that no backtest was run because this is execution plumbing, not alpha research.

- [ ] **Step 4: Update LINE only after candidate gates pass**

Add a concise current-state entry naming Stage210 as a production-orchestration candidate. Do not call it installed, activated, or production-current.

- [ ] **Step 5: Commit the evidence record**

```bash
git add research/lines/futures_trend_stage819_intraday_rules/stages/20260803_*_stage210_postclose_ai_pool_orchestration.md research/lines/futures_trend_stage819_intraday_rules/LINE.md
git commit -m "docs: record postclose orchestration candidate"
```

- [ ] **Step 6: Request independent code review**

Reviewer scope:

```text
Review receipt security and transition integrity, subprocess ordering, Stage935-before-final-Stage909 semantics, one-root-email behavior, retry bounds, seven-label invariants, release manifest coverage, API-zero invariants, and whether any path can touch CTP/native APIs. Report P0/P1/P2/P3 and confidence.
```

Any P0/P1 blocks qualification. Fix impactful P2 findings before qualification; record non-impactful residuals in Stage210.

---

### Task 6: Separate Qualification and Stage948 Production Activation

**Files:**
- Evidence only under: `/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/`
- Update after activation: the Stage210 record and current line status.

**Interfaces:**
- Consumes: clean reviewed candidate from Task 5, current production SOP, Stage948 prepare/activate, and naturally quiescent production jobs.
- Produces: either a verified activation or a fail-closed qualification report; never a partial activation claim.

- [ ] **Step 1: Prove Stage174 base activation happened first**

Require stable root HEAD, release manifest, activation receipt, and seven labels to identify `cc5ddf64f80711c0e3324b84bbbd3758c6581c26` before this follow-up activation starts. If Stage174 is not active, do not merge the two release events; finish Stage174 first.

- [ ] **Step 2: Wait for natural quiescence**

Read-only inspect all seven jobs and child processes. If any label, session daemon, controller, child guard, Stage931 warm executor, or CTP probe has a PID, record waiting and stop this attempt. Do not stop, kill, bootout, kickstart, or run formal CTP capture.

- [ ] **Step 3: Run two formal read-only qualifications for the new candidate**

Use `ctp_live.local.env` and formal `vnpy_ctp/api/libs` framework priority. Require two complete independent captures, no SIGSEGV, no handshake/decode error, no source mismatch, complete signed evidence, and all API counters zero.

- [ ] **Step 4: Complete independent qualification review**

Require `P0=0`, `P1=0`, complete evidence, correct candidate HEAD, exact runtime/env, and zero API calls. Any failure leaves stable production unchanged.

- [ ] **Step 5: Run Stage948 prepare, inspect, then activate**

Only Stage948 may write the stable root, manifest, activation receipt, or installed plists. Do not use manual copy, checkout, launchctl mutation, or hot reload.

- [ ] **Step 6: Verify activated state**

Require:

```text
stable HEAD == reviewed candidate HEAD
manifest source_commit == stable HEAD
activation receipt manifest_sha256 == manifest manifest_sha256
exactly seven installed labels match release assets
no unexpected/conflicting labels
postclose pipeline parent is 0700 and receipt is 0600 when present
send/cancel/order API counters == 0/0/0
```

- [ ] **Step 7: Record final outcome and stop obsolete monitoring**

If activation succeeds, update Stage210/LINE with exact evidence and stop the obsolete heartbeat. If qualification or activation fails, record the blocker, keep stable unchanged, and retain monitoring only when a natural state change can unblock it.

---

## Plan Self-review

- Spec coverage: all goals, non-goals, stage sequence, receipt fields, seven-label roles, email semantics, locking, retry, fail-closed cases, tests, and two-step deployment order map to Tasks 1-6.
- Placeholder scan: no placeholder markers, deferred implementation, or unspecified error-handling steps remain.
- Type consistency: receipt constructors/transitions/loaders are defined in Task 1 and consumed with the same names in Tasks 2-3; coordinator/watchdog/retry interfaces are defined before release and qualification tasks consume them.
- Scope: this is one operational subsystem. Stage174 native access remains a prerequisite release, not part of this implementation.
