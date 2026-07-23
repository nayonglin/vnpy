# Stage200 Production Receipt and Email Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore C9/15万 first-day shadow publication, make target-date resolution lightweight and deterministic, separate Stage935 control/data paths, and guarantee one safe best-effort launcher failure notification without changing trading semantics.

**Architecture:** Keep the existing Stage945/Stage947 launchd and `os.execve` ownership model. Add one standard-library live context for canonical paths, fix the statistical boundary at its source, make Stage922 a standard-library resolver, and add a locked/atomic failure-notification helper that launchers call only before downstream mail ownership transfers.

**Tech Stack:** Python 3.11 via `.py311/bin/python`, standard-library `csv/json/datetime/pathlib/fcntl/hashlib/tempfile`, pandas only in the existing Stage650/Stage935 business modules, `unittest`/`pytest`, Git worktrees, macOS launchd, and the existing Stage179 qualification/release/activation builders.

## Global Constraints

- Work only in `/Users/bytedance/Desktop/person/vnpy_stage179_production_live` on `codex/stage200-production-reliability-repair` until the final fast-forward into `master`; preserve the dirty main checkout at `/Users/bytedance/Desktop/person/vnpy`.
- Use research line `futures_trend_stage819_intraday_rules`; create one unique Stage200 stage record and do not modify another research line.
- Keep the sole production identity `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`, capital `150000`, profile `c9-15w`, and shadow start `2026-07-23`.
- Do not modify alpha, product selection, position sizing, entry price, order type, stop threshold, retry count, re-entry logic, risk limits, or any of the seven launchd labels/times.
- Preserve Stage945 -> Stage930 and Stage947 -> Stage907/909/929/935/946, including existing `os.execve` handoff. Do not add a supervisor or watchdog.
- Keep Stage901 `json.dumps(payload, allow_nan=False)`. Unknown non-finite values must still fail closed.
- Unit, integration, concurrency, and performance-smoke tests must not connect CTP, read production email secrets, send real email, or call send/cancel/order APIs.
- The final trusted production qualification alone may run its two formal CTP read-only captures through `ctp_live.local.env` and the formal framework; send/cancel/order API counts must be exactly `0/0/0`.
- Failure email is best-effort evidence only. It never changes the original exit code, never creates trading authority, never attaches files, and never includes raw exceptions, commands, environment values, CTP secrets, or SMTP secrets.
- Activation/owned-surface expected success skips, inactive sessions, pre-shadow-start dates, non-trading dates, health jobs, and non-canonical manual launcher invocations do not send fallback email.
- Use TDD for every behavior change: write RED, run and record the expected failure, implement the minimum GREEN change, run focused regression, then commit.
- After implementation, use a fresh independent agent for comprehensive review. P0 and P1 must be zero; every P2 must state whether it can affect production correctness.
- Any mismatch among final commit, tree fingerprint, review, qualification, release manifest, activation receipt, stable HEAD, launchd surface, or daily receipt remains fail-closed.

---

### Task 1: Fix First-Day Sharpe at the Statistical Boundary

**Files:**
- Modify: `examples/portfolio_backtesting/analyze_qmt_roll_stage650_stage526_200k_capital_reality_check.py:113-118`
- Modify: `tests/test_stage179_production_assets.py:1-45,677-780`
- Read/verify only: `examples/portfolio_backtesting/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py:542-660`

**Interfaces:**
- Consumes: `pd.Series` equity observations and Stage901 strict cohort publication.
- Produces: unchanged `_sharpe(equity: pd.Series) -> float`, with finite `0.0` for empty, one-observation, or zero-volatility series.

- [ ] **Step 1: Add RED and invariant tests**

Import Stage650 in `tests/test_stage179_production_assets.py`:

```python
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as stage650  # noqa: E402
```

Add these tests to `Stage179ProductionAssetsTest`:

```python
def test_stage650_sharpe_returns_zero_for_degenerate_equity_series(self) -> None:
    cases = {
        "empty": pd.Series(dtype=float),
        "single": pd.Series(
            [150_000.0],
            index=pd.to_datetime(["2026-07-23"]),
            dtype=float,
        ),
        "constant": pd.Series(
            [150_000.0, 150_000.0],
            index=pd.to_datetime(["2026-07-23", "2026-07-24"]),
            dtype=float,
        ),
    }
    for label, equity in cases.items():
        with self.subTest(label=label):
            self.assertEqual(0.0, stage650._sharpe(equity))


def test_stage650_sharpe_preserves_multi_day_result(self) -> None:
    equity = pd.Series(
        [100.0, 110.0, 105.0, 120.0],
        index=pd.date_range("2026-07-20", periods=4),
        dtype=float,
    )
    self.assertAlmostEqual(
        8.999777412294232,
        stage650._sharpe(equity),
        places=12,
    )


def test_stage901_publishes_single_day_metrics_as_strict_json(self) -> None:
    profile = replace(
        C9_15W_PROFILE,
        summary_path=self.signal_root / C9_15W_PROFILE.summary_path.name,
        signal_plan_path=self.signal_root / C9_15W_PROFILE.signal_plan_path.name,
        current_positions_path=self.signal_root / C9_15W_PROFILE.current_positions_path.name,
        pending_orders_path=self.signal_root / C9_15W_PROFILE.pending_orders_path.name,
        pending_orders_audit_path=self.signal_root / C9_15W_PROFILE.pending_orders_audit_path.name,
    )
    metrics = stage650._metrics(
        frame=pd.DataFrame([{
            "date": "2026-07-23",
            "account_equity": 150_000.0,
            "broker10_total_margin_exact": 0.0,
            "total_net_pnl": 0.0,
            "total_slippage": 0.0,
            "trade_count": 0,
        }]),
        spec=stage650.CapitalVariant(
            variant=C9_15W_PROFILE.profile_key,
            label="C9/15w first-day fixture",
            account_capital=C9_15W_PROFILE.capital,
            c3_capital=C9_15W_PROFILE.capital,
            risk_multiplier=1.0,
            product_cap_ratio=0.25,
            max_concurrent_positions=4,
            note="stage200 first-day fixture",
        ),
        cost_multiplier=1.0,
    )
    decision = {
        "analysis_end": "2026-07-23",
        "generated_at": "2026-07-23 16:35:00",
        "execution_profile": profile.profile_key,
        "official_live_version": profile.official_version,
        "capital": profile.capital,
        "capital_label": profile.capital_label,
        "current_variant": metrics,
    }
    published, pending, audit = stage901._publish_execution_artifact_cohort(
        decision=decision,
        signal_plan=pd.DataFrame(columns=["vt_symbol", "direction", "offset", "volume"]),
        current_positions=pd.DataFrame(columns=["vt_symbol", "direction", "end_pos"]),
        pending_orders=pd.DataFrame(columns=["vt_symbol", "direction", "offset", "volume"]),
        profile=profile,
    )
    persisted = json.loads(profile.summary_path.read_text(encoding="utf-8"))
    persisted_audit = json.loads(profile.pending_orders_audit_path.read_text(encoding="utf-8"))
    self.assertEqual(0.0, published["current_variant"]["sharpe"])
    self.assertEqual(0.0, persisted["current_variant"]["sharpe"])
    self.assertTrue(pending.empty)
    self.assertEqual(audit, persisted_audit)
    self.assertEqual(published["cohort_id"], persisted_audit["cohort_id"])


def test_stage901_strict_json_rejects_unknown_native_nan(self) -> None:
    with self.assertRaisesRegex(ValueError, "Out of range float values"):
        stage901._json_bytes({"unexpected_metric": float("nan")})
```

- [ ] **Step 2: Run RED and invariant controls**

Run:

```bash
.py311/bin/python -m pytest -vv --tb=short \
  tests/test_stage179_production_assets.py::Stage179ProductionAssetsTest::test_stage650_sharpe_returns_zero_for_degenerate_equity_series \
  tests/test_stage179_production_assets.py::Stage179ProductionAssetsTest::test_stage901_publishes_single_day_metrics_as_strict_json
```

Expected: both tests fail because `_sharpe()` returns NaN and strict Stage901 JSON rejects it.

Run:

```bash
.py311/bin/python -m pytest -vv --tb=short \
  tests/test_stage179_production_assets.py::Stage179ProductionAssetsTest::test_stage650_sharpe_preserves_multi_day_result \
  tests/test_stage179_production_assets.py::Stage179ProductionAssetsTest::test_stage901_strict_json_rejects_unknown_native_nan
```

Expected: `2 passed`; this proves normal multi-day behavior and the strict serializer remain unchanged before the fix.

- [ ] **Step 3: Implement the minimum finite-value guard**

Replace `_sharpe()` with:

```python
def _sharpe(equity: pd.Series) -> float:
    returns = equity.astype(float).pct_change().replace(
        [np.inf, -np.inf], np.nan
    ).fillna(0.0)
    std = float(returns.std(ddof=1))
    if not math.isfinite(std) or std <= 0:
        return 0.0
    return float(returns.mean() / std * math.sqrt(252.0))
```

Do not modify Stage901 `_json_safe()` or `_json_bytes()`.

- [ ] **Step 4: Run GREEN and commit**

Run:

```bash
.py311/bin/python -m pytest -q tests/test_stage179_production_assets.py -k "stage650_sharpe or stage901"
```

Expected: all selected tests pass; no warnings become exceptions and no production artifact is touched.

Commit:

```bash
git add \
  examples/portfolio_backtesting/analyze_qmt_roll_stage650_stage526_200k_capital_reality_check.py \
  tests/test_stage179_production_assets.py
git commit -m "fix(stage901): make first-day Sharpe finite"
```

---

### Task 2: Add a Standard-Library Production Live Context

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_official_live_lightweight_context.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_config.py:1-40,149-176`
- Modify: `tests/test_stage945_production_launcher.py`

**Interfaces:**
- Produces: canonical identity and path constants without importing pandas, TqSdk, vn.py, Plotly, strategy candidates, or backtest modules.
- Consumers: Task 3 Stage922, Task 4 Stage935, and Task 5 failure notification.

- [ ] **Step 1: Add a RED subprocess import-contract test**

Add `test_lightweight_context_reexports_canonical_identity_and_splits_roots` to `Stage945ProductionLauncherTest`. The child process must import the lightweight module and full config under temporary control/signal env, print JSON, and assert:

```python
blocked_roots = (
    "pandas",
    "numpy",
    "tqsdk",
    "plotly",
    "vnpy",
    "vnpy_portfoliostrategy",
    "build_qmt_roll_stage173_forward_main_contract_data_update",
    "main_contract_mapping",
    "run_qmt_alignment_backtest",
)

self.assertEqual([], payload["loaded_after_lightweight_import"])
self.assertEqual("official_live_stage847_c9_15w_stage819_05r_stop_retry_once", payload["version"])
self.assertEqual("Stage847-C9-15w", payload["alias"])
self.assertEqual("2026-07-23", payload["shadow_start"])
self.assertEqual(control.resolve(), Path(payload["control"]).resolve())
self.assertEqual(signal.resolve(), Path(payload["signal"]).resolve())
self.assertEqual((PORTFOLIO_DIR / "backtest_outputs").resolve(), Path(payload["data"]).resolve())
self.assertEqual(payload["lightweight_identity"], payload["full_config_identity"])
self.assertEqual(payload["lightweight_summary"], payload["full_config_summary"])
```

Run:

```bash
.py311/bin/python -m pytest -vv --tb=short \
  tests/test_stage945_production_launcher.py::Stage945ProductionLauncherTest::test_lightweight_context_reexports_canonical_identity_and_splits_roots
```

Expected: FAIL because the lightweight module does not exist.

- [ ] **Step 2: Create the exact lightweight constants module**

Create `qmt_roll_official_live_lightweight_context.py` with this public surface:

```python
from __future__ import annotations

import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DATA_ASSET_DIR = PROJECT_DIR / "backtest_outputs"
CONTROL_OUTPUT_DIR = Path(
    os.environ.get("OFFICIAL_LIVE_OUTPUT_DIR", str(DATA_ASSET_DIR))
).expanduser().resolve(strict=False)
SIGNAL_INPUT_DIR = Path(
    os.environ.get(
        "OFFICIAL_LIVE_SIGNAL_INPUT_DIR",
        os.environ.get("OFFICIAL_LIVE_OUTPUT_DIR", str(DATA_ASSET_DIR)),
    )
).expanduser().resolve(strict=False)

OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"
OFFICIAL_LIVE_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE = "2026-07-23"

OFFICIAL_LIVE_STAGE901_PREFIX = "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow"
OFFICIAL_LIVE_STAGE901_MODEL_TAG = "stage901_stage847_c9_2026_ytd_live_shadow_v1"
OFFICIAL_LIVE_SUMMARY_PATH = (
    SIGNAL_INPUT_DIR
    / f"{OFFICIAL_LIVE_STAGE901_PREFIX}_decision_{OFFICIAL_LIVE_STAGE901_MODEL_TAG}.json"
)
OFFICIAL_LIVE_AI_ELIGIBILITY_PATH = (
    DATA_ASSET_DIR
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_"
      "stage182_ai_product_pool_live_inference_v1.csv"
)

STAGE173_PREFIX = "qmt_roll_stage173_forward_main_contract_data_update"
STAGE173_MODEL_TAG = "stage173_forward_main_contract_data_update_v1"
STAGE173_SUMMARY_PATH = DATA_ASSET_DIR / f"{STAGE173_PREFIX}_summary_{STAGE173_MODEL_TAG}.json"
STAGE173_STATUS_PATH = DATA_ASSET_DIR / f"{STAGE173_PREFIX}_contract_bar_status_{STAGE173_MODEL_TAG}.csv"
ALL_FUTURES_MAPPING_PATH = DATA_ASSET_DIR / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
```

- [ ] **Step 3: Make full config re-export the same identity and paths**

Replace the duplicate top-level definitions in `qmt_roll_official_live_config.py` with imports and compatibility aliases:

```python
from qmt_roll_official_live_lightweight_context import (
    DATA_ASSET_DIR,
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    OFFICIAL_LIVE_STAGE901_MODEL_TAG,
    OFFICIAL_LIVE_STAGE901_PREFIX,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
    PROJECT_DIR,
    SIGNAL_INPUT_DIR,
)

OUTPUT_DIR = DATA_ASSET_DIR
OFFICIAL_LIVE_STAGE659_MODEL_TAG = OFFICIAL_LIVE_STAGE901_MODEL_TAG
OFFICIAL_LIVE_STAGE659_PREFIX = OFFICIAL_LIVE_STAGE901_PREFIX
```

Remove only the now-duplicated assignments. Preserve every unrelated candidate, capital, execution-policy, and output-path definition.

- [ ] **Step 4: Run GREEN and compatibility regression, then commit**

Run:

```bash
.py311/bin/python -m pytest -q \
  tests/test_stage945_production_launcher.py -k lightweight_context \
  tests/test_official_live_config_import.py \
  tests/test_stage179_official_execution_profile.py
```

Expected: all selected tests pass; subprocess output shows no blocked module after the lightweight-only import.

Commit:

```bash
git add \
  examples/portfolio_backtesting/qmt_roll_official_live_lightweight_context.py \
  examples/portfolio_backtesting/qmt_roll_official_live_config.py \
  tests/test_stage945_production_launcher.py
git commit -m "refactor(stage922): add lightweight live context"
```

---

### Task 3: Rewrite Stage922 as a Deterministic Lightweight Resolver

**Files:**
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage922_official_live_target_date_resolver.py:1-293`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage945_official_live_production_session_launcher.py:615-655`
- Modify: `tests/test_stage945_production_launcher.py`

**Interfaces:**
- Consumes: Task 2 context paths plus CSV/JSON fixtures.
- Produces: `build_target_date_resolution(*, as_of, data_ready_time, official_summary_path, stage173_summary_path, stage173_status_path, mapping_path) -> dict[str, Any]` and the existing compatible Stage922 CLI JSON/evidence files.

- [ ] **Step 1: Add RED dependency, path, and semantic tests**

Add `test_stage922_import_is_stdlib_lightweight_and_roots_are_split`. In a fresh child process import Stage922, inspect `sys.modules`, and assert none of these roots were loaded:

```python
(
    "pandas",
    "numpy",
    "tqsdk",
    "plotly",
    "vnpy",
    "vnpy_portfoliostrategy",
    "build_qmt_roll_stage173_forward_main_contract_data_update",
    "main_contract_mapping",
    "qmt_roll_official_live_config",
    "run_qmt_alignment_backtest",
)
```

Also assert `_paths("fixture")` is entirely under temporary `CONTROL_OUTPUT_DIR`, while data and signal inputs retain their separate roots. The subprocess timeout is only a 60-second deadlock guard; do not assert elapsed seconds.

Add `test_stage922_fixture_semantics_cover_ready_refresh_holiday_and_cold_start`. Build these temporary fixtures:

```text
mapping.csv dates: 2026-03-31, 2026-04-30, 2026-05-29, 2026-06-30,
                   2026-07-17, 2026-07-21, 2026-07-23
stage173-status.csv max_date rows: 2026-07-23, 2026-07-23, 2026-07-22
stage173-summary.json max_saved_date: 2026-07-23
official-summary.json analysis_start/end/latest: 2026-07-23
```

Call the exact public seam:

```python
ready = resolver.build_target_date_resolution(
    as_of=datetime.fromisoformat("2026-07-23T17:00:00"),
    data_ready_time="16:30",
    official_summary_path=official,
    stage173_summary_path=stage173_summary,
    stage173_status_path=stage173_status,
    mapping_path=mapping,
)
self.assertEqual("2026-07-23", ready["resolved_target_date"])
self.assertEqual(0, ready["requires_data_update"])
self.assertEqual(0, ready["requires_shadow_refresh"])
self.assertEqual("target_date_resolved_local_shadow_ready_fail_closed", ready["resolver_status"])
self.assertEqual(2, ready["stage173_target_contract_coverage"]["target_date_contract_count"])
self.assertEqual(3, ready["stage173_target_contract_coverage"]["contract_count"])
self.assertEqual(0, ready["order_api_called_count"])
```

Repeat with `2026-07-20T21:00:00` to resolve the mapping-authoritative holiday date `2026-07-17`; with `2026-07-23T16:00:00` to resolve `2026-07-21`; with stale Stage173/Stage901 summaries to set the correct refresh flags; and with an empty mapping to retain `weekday_fallback`.

Add `test_target_date_resolver_timeout_is_typed_fail_closed`:

```python
with (
    patch.object(
        launcher.subprocess,
        "run",
        side_effect=subprocess.TimeoutExpired(["stage922"], 60),
    ),
    self.assertRaisesRegex(
        launcher.ProductionSessionLaunchError,
        "^production_launcher_target_date_resolver_timeout$",
    ),
):
    launcher._resolve_target_date({})
```

Run:

```bash
.py311/bin/python -m pytest -vv --tb=short tests/test_stage945_production_launcher.py \
  -k "stage922 or target_date_resolver_timeout"
```

Expected: dependency/semantic tests fail against the heavy implementation, and timeout escapes as raw `TimeoutExpired`.

- [ ] **Step 2: Replace pandas helpers with standard-library helpers**

Stage922 imports only `argparse`, `csv`, `json`, `date/datetime/timedelta`, `Path`, `Any`, and Task 2 context constants. Implement these exact seams:

```python
def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _date_text(value: Any) -> str:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed is not None else ""


def _known_trading_dates(path: Path) -> list[date]:
    if not path.exists():
        return []
    observed: set[date] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            parsed = _parse_date(row.get("date"))
            if parsed is not None:
                observed.add(parsed)
    return sorted(observed)


def _latest_status_bar_date(rows: list[dict[str, str]]) -> str:
    dates = [parsed for row in rows if (parsed := _parse_date(row.get("max_date"))) is not None]
    return max(dates).isoformat() if dates else ""


def _status_contract_coverage(
    rows: list[dict[str, str]],
    target_date: str,
) -> dict[str, int | float]:
    contract_count = len(rows)
    target_count = sum(_date_text(row.get("max_date")) == target_date for row in rows)
    return {
        "contract_count": contract_count,
        "target_date_contract_count": target_count,
        "coverage_ratio": float(target_count / contract_count) if contract_count else 0.0,
    }
```

Use `date`/`timedelta` in `_previous_weekday` and `_wall_clock_cutoff_date`. Use `csv.DictWriter` for evidence CSV and a small Markdown escape/table formatter; do not reintroduce pandas just for reporting.

- [ ] **Step 3: Extract the pure resolver entry and keep CLI schema compatible**

Implement:

```python
def build_target_date_resolution(
    *,
    as_of: datetime,
    data_ready_time: str,
    official_summary_path: Path = OFFICIAL_LIVE_SUMMARY_PATH,
    stage173_summary_path: Path = STAGE173_SUMMARY_PATH,
    stage173_status_path: Path = STAGE173_STATUS_PATH,
    mapping_path: Path = ALL_FUTURES_MAPPING_PATH,
) -> dict[str, Any]:
    # Return the current Stage922 summary schema, including resolver_evidence,
    # refresh flags, source_files, identity, cold-start evidence, coverage,
    # and exact order_api_called_count=0.
```

The implementation must retain these statuses exactly:

```python
(
    "target_date_before_live_shadow_start_waiting_fail_closed",
    "target_date_resolver_blocked_fail_closed",
    "target_date_resolved_requires_refresh_fail_closed",
    "target_date_resolved_local_shadow_ready_fail_closed",
)
```

`main()` calls the pure entry, adds output paths, writes CSV/JSON/Markdown beneath `CONTROL_OUTPUT_DIR`, and prints the same JSON object. Preserve `trading_calendar_source` and all API-zero fields.

- [ ] **Step 4: Convert Stage945 timeout to a stable blocker**

Wrap only `subprocess.run` in `_resolve_target_date`:

```python
try:
    result = subprocess.run(
        [
            str(PYTHON_PATH),
            str(STAGE922_SCRIPT),
            "--data-ready-time",
            "16:30",
        ],
        cwd=REPO_ROOT,
        env=dict(environment),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        check=False,
    )
except subprocess.TimeoutExpired as exc:
    raise ProductionSessionLaunchError(
        "production_launcher_target_date_resolver_timeout",
        boundary="target-date-resolver",
    ) from exc
```

If `ProductionSessionLaunchError` has not yet gained `boundary`, add the backward-compatible constructor now:

```python
class ProductionSessionLaunchError(RuntimeError):
    def __init__(self, message: str, *, boundary: str = "pre-exec") -> None:
        super().__init__(message)
        self.boundary = boundary
```

- [ ] **Step 5: Run GREEN, a cold-process smoke, and commit**

Run:

```bash
.py311/bin/python -m pytest -q tests/test_stage945_production_launcher.py \
  -k "stage922 or target_date"
```

Run the CLI once with temporary control output and repository fixture inputs; record elapsed time as a diagnostic only:

```bash
OFFICIAL_LIVE_OUTPUT_DIR=/tmp/stage200-stage922-smoke \
  .py311/bin/python \
  examples/portfolio_backtesting/run_qmt_roll_stage922_official_live_target_date_resolver.py \
  --as-of 2026-07-23T17:00:00 --data-ready-time 16:30
```

Expected: exit 0, no forbidden imports in the hard test, output under `/tmp/stage200-stage922-smoke`, and order API count 0.

Commit:

```bash
git add \
  examples/portfolio_backtesting/run_qmt_roll_stage922_official_live_target_date_resolver.py \
  examples/portfolio_backtesting/run_qmt_roll_stage945_official_live_production_session_launcher.py \
  tests/test_stage945_production_launcher.py
git commit -m "fix(stage922): remove heavy resolver dependencies"
```

---

### Task 4: Separate Stage935 Control Outputs from Data Assets

**Files:**
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py:14-66,210-404,469-567,682-749`
- Modify: `tests/test_stage947_production_support_launcher.py`

**Interfaces:**
- Consumes: Task 2 `CONTROL_OUTPUT_DIR`, `DATA_ASSET_DIR`, canonical Stage173/mapping/AI paths.
- Produces: Stage935 reports/lock under control root while all Stage173/182/183 inputs remain under data root.

- [ ] **Step 1: Add RED import/path and business-fixture tests**

Add `test_stage935_import_keeps_control_and_data_roots_separate` using a child process with temporary `OFFICIAL_LIVE_OUTPUT_DIR`. Assert:

```python
self.assertEqual(control.resolve(), Path(payload["lock"]).resolve().parent)
self.assertTrue(all(Path(path).resolve().parent == control.resolve() for path in payload["outputs"].values()))
self.assertEqual((PORTFOLIO_DIR / "backtest_outputs").resolve(), Path(payload["stage173"]).resolve().parent)
self.assertEqual(payload["stage182_combined"], payload["official_ai"])
self.assertEqual([], payload["forbidden_imports"])
```

The forbidden imports are `run_qmt_alignment_backtest`, `main_contract_mapping`, `qmt_roll_official_live_config`, and Stage173 builder.

Add `test_stage935_reads_successful_stage173_from_data_root_when_control_is_empty`. Create temporary mapping and Stage173/182/183 fixtures, patch all module path constants to the data fixture, leave the control directory empty, patch `_run_command` to return exit 0, and call `_run(args)`. Assert:

```python
self.assertEqual("monthly_ai_pool_updated", result["automation_status"])
self.assertNotIn("stage173_max_saved_date_not_resolved_target_date", result.get("blockers", []))
self.assertEqual(str(stage173_summary), result["stage173_summary"]["path"])
self.assertEqual([], list(control.iterdir()))
```

Run:

```bash
.py311/bin/python -m pytest -vv --tb=short tests/test_stage947_production_support_launcher.py \
  -k stage935
```

Expected: current paths point to private control root and the tests fail.

- [ ] **Step 2: Replace Stage935 root imports and constants**

Use only Task 2 context:

```python
from qmt_roll_official_live_lightweight_context import (
    ALL_FUTURES_MAPPING_PATH,
    CONTROL_OUTPUT_DIR,
    DATA_ASSET_DIR,
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    OFFICIAL_LIVE_VERSION,
    STAGE173_SUMMARY_PATH,
)
```

Define paths as:

```python
STAGE182_SUMMARY_PATH = DATA_ASSET_DIR / f"{STAGE182_OUTPUT_PREFIX}_summary_{STAGE182_MODEL_TAG}.json"
STAGE182_LIVE_ELIGIBILITY_PATH = DATA_ASSET_DIR / f"{STAGE182_OUTPUT_PREFIX}_eligibility_{STAGE182_MODEL_TAG}.csv"
STAGE182_COMBINED_ELIGIBILITY_PATH = OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
STAGE183_SUMMARY_PATH = DATA_ASSET_DIR / f"{STAGE183_OUTPUT_PREFIX}_summary_{STAGE183_MODEL_TAG}.json"
LOCK_PATH = CONTROL_OUTPUT_DIR / f"{OUTPUT_PREFIX}.lock"
```

Make `_paths()` and `main()` use `CONTROL_OUTPUT_DIR`. Remove imports from `main_contract_mapping`, `qmt_roll_official_live_config`, and `run_qmt_alignment_backtest`. Do not modify Stage173/182/183 generators.

- [ ] **Step 3: Run GREEN and commit**

Run:

```bash
.py311/bin/python -m pytest -q tests/test_stage947_production_support_launcher.py -k stage935
```

Expected: both new tests pass; no child command, network, data update, or email is executed.

Commit:

```bash
git add \
  examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py \
  tests/test_stage947_production_support_launcher.py
git commit -m "fix(stage935): separate control and data roots"
```

---

### Task 5: Build the Locked, Atomic, Secret-Safe Failure Notifier

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_official_live_failure_notify.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_email_notify.py:234-306`
- Create: `tests/test_official_live_failure_notify.py`

**Interfaces:**
- Consumes: Task 2 `CONTROL_OUTPUT_DIR` and existing `send_official_live_email_notification`.
- Produces: `normalize_official_live_failure_blocker(value, fallback) -> str` and `notify_official_live_failure(job, boundary, blocker, schedule_date, release_commit) -> dict[str, Any]`; never raises an ordinary exception.

- [ ] **Step 1: Add RED state-machine and safety tests**

Create `OfficialLiveFailureNotifyTest` with these exact cases:

- `test_sent_and_dry_run_are_terminal_for_same_fingerprint`: for each terminal status, invoke twice with identical inputs one hour apart; assert one fake-sender call and second result `suppressed_terminal`.
- `test_terminal_fingerprint_survives_interleaved_other_fingerprint`: send fingerprint A, then B, then A again; assert two physical fake sends and A's final call is `suppressed_terminal`.
- `test_nonterminal_statuses_observe_thirty_minute_cooldown`: for each of `send_failed`, `disabled`, `blocked_missing_config`, and `helper_failed`, assert calls at `T0` and `T0+1801s` but no call at `T0+1799s`.
- `test_reserved_crash_state_observes_cooldown`: write a valid `reserved` entry, assert suppression before 1,800 seconds and one retry after it.
- `test_release_date_job_boundary_and_blocker_change_fingerprint`: vary one input at a time and assert five distinct SHA-256 fingerprints.
- `test_mailer_exception_returns_helper_failed_without_recursion`: make the fake sender raise once, assert one call, `helper_failed`, and only the exception type in the safe result/state.
- `test_state_and_lock_are_0600_and_state_is_valid_atomic_json`: assert the real parent is owner-private, both files are `0600`, no temp file remains, and `json.loads` succeeds after each transition.
- `test_unsafe_parent_or_lock_symlink_returns_helper_failed_without_send`: cover a group-writable parent and a pre-existing lock symlink; assert safe `helper_failed`, zero fake sends, and no target-file mutation.
- `test_secret_sentinels_never_reach_subject_body_metadata_state_or_audit`: first inject `CTP_PASSWORD_SENTINEL`, `SMTP_PASSWORD_SENTINEL`, and `AUTH_CODE_SENTINEL` through rejected helper input and a fake-sender exception, then serialize every helper result/state/sender argument and assert none occurs. Separately patch `qmt_roll_official_live_email_notify._send_message` to raise `RuntimeError("SMTP_PASSWORD_SENTINEL")`, redirect `OUTPUT_DIR` and `EMAIL_AUDIT_LOG_PATH` to the temporary private directory, use a temporary enabled email config, call the common mailer, and assert both its reduced result and NDJSON audit contain `error_type="RuntimeError"` but no sentinel or raw `error` field.
- `test_one_hundred_fork_races_have_exactly_one_mailer_winner`: for each index 0-99, fork two processes against the same per-index fingerprint and fake counter; assert exactly one byte per index and 100 bytes total.

Every test calls the internal dependency-injected seam with temporary state/lock paths and a fake sender. The 100-round fork test starts two forked processes per fingerprint; the fake sender appends one byte to a locked local counter. Expected physical fake sends: exactly 100. It must not import or read `official_live_email.local.env`.

Run:

```bash
.py311/bin/python -m pytest -vv --tb=short tests/test_official_live_failure_notify.py
```

Expected: FAIL because the module and API do not exist.

- [ ] **Step 2: Implement the exact public and test seams**

The public signatures are `normalize_official_live_failure_blocker(value: str, *, fallback: str) -> str` and `notify_official_live_failure(*, job: str, boundary: str, blocker: str, schedule_date: str, release_commit: str = "") -> dict[str, Any]`.

The dependency-injected test seam is `_notify_official_live_failure(*, job: str, boundary: str, blocker: str, schedule_date: str, release_commit: str, state_path: Path, lock_path: Path, now: datetime, email_sender: Callable) -> dict[str, Any]`. Add `_failure_fingerprint(release_commit, schedule_date, job, boundary, blocker) -> str`, `_load_state(path) -> dict[str, Any]`, and `_atomic_write_state(path, payload) -> None` as deterministic private helpers used by both implementation and tests.

Use fixed paths:

```python
FAILURE_NOTIFICATION_STATE_PATH = (
    CONTROL_OUTPUT_DIR / "qmt_roll_official_live_failure_notification_state.json"
)
FAILURE_NOTIFICATION_LOCK_PATH = (
    CONTROL_OUTPUT_DIR / "qmt_roll_official_live_failure_notification.lock"
)
FAILURE_NOTIFICATION_COOLDOWN_SECONDS = 30 * 60
```

Normalize tokens with allowlist `[^a-zA-Z0-9_.:-]`, maximum 120 characters, and caller-provided stable fallback. Fingerprint exactly:

```python
hashlib.sha256(
    "\x1f".join((release_commit or "unknown", schedule_date, job, boundary, blocker)).encode("utf-8")
).hexdigest()
```

State transitions under one exclusive `fcntl.flock` are:

```text
missing -> reserved -> sent | dry_run_written
                    -> send_failed | disabled | blocked_missing_config | helper_failed
```

`sent` and `dry_run_written` suppress permanently for the fingerprint. All other existing states suppress for 1,800 seconds. The state file is a versioned ledger, not a last-value slot:

```python
{
    "schema_version": 1,
    "updated_at": "UTC ISO-8601",
    "entries": {
        fingerprint: {
            "fingerprint": fingerprint,
            "release_commit": safe_commit,
            "schedule_date": safe_schedule_date,
            "job": safe_job,
            "boundary": safe_boundary,
            "blocker": safe_blocker,
            "status": notification_status,
            "updated_at": "UTC ISO-8601",
        },
    },
}
```

Before locking, require the state/lock parent paths to be identical, non-symlink directories owned by the current uid with no group/other permission bits; create a missing parent as `0700`, but never relax or silently rewrite an unsafe existing parent. Open the lock with `os.open(..., O_CREAT | O_RDWR | O_NOFOLLOW, 0o600)`, verify it is a current-user regular file, and reject a symlink or unsafe pre-existing file. Under the lock, inspect and update only `entries[fingerprint]`; never discard unrelated entries, so A -> B -> A remains suppressed for A. Hold the lock across reserve, one mailer call, and final state. Write the whole ledger through a same-directory `mkstemp`, `fchmod(0600)`, file `fsync`, `os.replace`, and parent-directory `fsync`; force the lock file to `0600`. Store only safe tokens, timestamps, fingerprint, and status.

Build this exact semantic content:

```python
subject = f"[C9/15w][生产任务失败][{safe_job}] {safe_blocker}"
body = "\n".join([
    "C9/15万生产任务在正常邮件生成前失败。",
    f"任务：{safe_job}",
    f"边界：{safe_boundary}",
    f"阻断码：{safe_blocker}",
    f"调度日期：{safe_schedule_date}",
    f"版本：{safe_commit[:12] or 'unknown'}",
    "send/cancel/order API：0/0/0",
    "正常信号邮件未生成，不能据此判断为无交易信号。",
])
```

Call the mailer once with `attachments=[]`, fixed event type `official_live_launcher_failure`, warning severity, and safe metadata only. Return a reduced safe result with `notification_status`, `fingerprint`, and API zeros. Catch all ordinary helper exceptions and return `helper_failed` plus `error_type=type(exc).__name__`; never include `repr(exc)`.

- [ ] **Step 3: Remove raw SMTP exception text from the common audit**

Change the existing mailer catch from raw representation to type-only evidence:

```python
except Exception as exc:
    result["email_status"] = "send_failed"
    result["error_type"] = type(exc).__name__
```

Do not change the meaning of `sent`: it still means the SMTP server accepted at least one recipient, not guaranteed inbox delivery.

- [ ] **Step 4: Run GREEN and commit**

Run:

```bash
.py311/bin/python -m pytest -q tests/test_official_live_failure_notify.py
```

Expected: all helper tests pass, including 100 fork races; no SMTP or CTP connection occurs.

Commit:

```bash
git add \
  examples/portfolio_backtesting/qmt_roll_official_live_failure_notify.py \
  examples/portfolio_backtesting/qmt_roll_official_live_email_notify.py \
  tests/test_official_live_failure_notify.py
git commit -m "feat(stage200): add safe launcher failure notification"
```

---

### Task 6: Integrate Failure Ownership into Stage945 and Stage947

**Files:**
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage945_official_live_production_session_launcher.py:615-655,980-1185`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage947_official_live_production_support_launcher.py:80-480`
- Modify: `tests/test_stage945_production_launcher.py`
- Modify: `tests/test_stage947_production_support_launcher.py`

**Interfaces:**
- Consumes: Task 5 notifier, Task 3 typed timeout, and existing mail ownership.
- Produces: one fallback before downstream ownership; unchanged success/skip/exit/`execve` semantics.

- [ ] **Step 1: Add Stage945 RED tests**

Add these exact Stage945 cases:

- `test_typed_failure_notifies_once_and_keeps_exit_two`: patch `launch_session` to raise a typed receipt blocker under canonical owner, then assert one notifier call, printed `blocked_fail_closed`, API zeros, and `SystemExit(2)`.
- `test_unexpected_failure_uses_stable_code_without_raw_exception`: raise `RuntimeError("CTP_PASSWORD_SENTINEL")`; assert stdout and notifier arguments contain only `production_launcher_unexpected_failure`.
- `test_noncanonical_owner_never_notifies`: use wrong ppid and label; assert notifier call count zero while the original owner blocker remains exit 2.
- `test_inactive_cold_start_and_nontrading_skips_never_notify`: exercise the three existing successful-return branches and assert no notifier call and no exit-code regression.
- `test_successful_exec_handoff_does_not_notify`: patch `os.execve` as the terminal observation and assert fallback is untouched.
- `test_night_schedule_date_before_0300_uses_previous_calendar_date`: assert `2026-07-24T01:00+08:00` maps to `2026-07-23`, while day session and night after 20:55 use the current date.

For `main()` tests patch `sys.argv`, `launch_session`, `notify_official_live_failure`, `os.getppid`, and `XPC_SERVICE_NAME`; capture stdout and `SystemExit`. Typed and unexpected failures must keep exit 2 and API zeros. A secret sentinel embedded in an unexpected exception must not appear in stdout or notifier arguments.

- [ ] **Step 2: Add Stage947 RED tests**

Add these exact Stage947 cases:

- `test_receipt_or_precompute_failure_notifies_once_before_exec`: inject each blocker under canonical launchd ownership; assert one fallback, no `execve`, and exit 2.
- `test_resolver_failure_is_adapted_and_notified_without_traceback`: raise Stage945 typed timeout; assert stable support blocker/boundary, no traceback text, API zeros, and exit 2.
- `test_monthly_five_owned_email_statuses_do_not_duplicate_fallback`: subtest all five owned statuses in a nonzero Stage935 final JSON; assert no fallback.
- `test_monthly_skipped_or_missing_email_result_uses_fallback`: subtest `skipped_by_policy`, absent field, and invalid final JSON; assert one fallback.
- `test_monthly_post_update_receipt_failure_uses_new_fallback_boundary`: Stage935 returns updated/sent, subsequent precompute fails; assert one `monthly-receipt-refresh` fallback.
- `test_health_and_noncanonical_owner_never_notify`: assert zero notifier calls for health or wrong ppid/label.
- `test_successful_report_handoff_keeps_execve_and_no_fallback`: assert the original `os.execve` call and environment are unchanged and notifier is untouched.

Owned Stage935 statuses are exactly:

```python
{
    "sent",
    "dry_run_written",
    "send_failed",
    "disabled",
    "blocked_missing_config",
}
```

Run:

```bash
.py311/bin/python -m pytest -vv --tb=short \
  tests/test_stage945_production_launcher.py \
  tests/test_stage947_production_support_launcher.py \
  -k "notif or resolver_failure or monthly"
```

Expected: tests fail because launchers do not call the helper, Stage947 does not adapt the typed resolver error, and monthly return code is checked before final JSON.

- [ ] **Step 3: Add Stage945 failure reporting without changing expected skips**

Import `timedelta` alongside the existing `datetime`, and import Task 5 functions. Keep `ProductionSessionLaunchError(message, boundary="pre-exec")` backward compatible. Add:

```python
def _session_notification_schedule_date(session: str, now: datetime | None = None) -> str:
    current = (now or datetime.now().astimezone()).astimezone()
    day = current.date()
    if session == "night" and current.hour < 3:
        day -= timedelta(days=1)
    return day.isoformat()


def _canonical_session_owner(session: str) -> bool:
    spec = SESSION_SPECS[session]
    return os.getppid() == 1 and os.environ.get("XPC_SERVICE_NAME", "").strip() == spec.label
```

Factor blocked JSON printing into a helper that receives an already normalized blocker. In `main()`:

```python
try:
    launch_session(args)
except ProductionSessionLaunchError as exc:
    blocker = normalize_official_live_failure_blocker(
        str(exc), fallback="production_launcher_failure"
    )
    if _canonical_session_owner(args.session):
        notify_official_live_failure(
            job=f"{args.session}-session",
            boundary=exc.boundary,
            blocker=blocker,
            schedule_date=_session_notification_schedule_date(args.session),
        )
    _print_blocked(args.session, blocker)
    raise SystemExit(2)
except Exception:
    blocker = "production_launcher_unexpected_failure"
    if _canonical_session_owner(args.session):
        notify_official_live_failure(
            job=f"{args.session}-session",
            boundary="unexpected",
            blocker=blocker,
            schedule_date=_session_notification_schedule_date(args.session),
        )
    _print_blocked(args.session, blocker)
    raise SystemExit(2)
```

Do not add notification calls to activation barrier/owned-surface success-return branches, inactive sessions, cold-start skip, or non-trading-day skip. Do not change the final `os.execve`.

- [ ] **Step 4: Add Stage947 typed errors and monthly ownership**

Use:

```python
class ProductionSupportLaunchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        boundary: str = "pre-exec",
        downstream_email_attempted: bool = False,
    ) -> None:
        super().__init__(message)
        self.boundary = boundary
        self.downstream_email_attempted = downstream_email_attempted
```

Import Stage945 `ProductionSessionLaunchError`. Create `_resolve_support_target_date(environment: Mapping[str, str]) -> tuple[str, dict[str, Any]]` that calls the existing Stage945 `_resolve_target_date`, catches both `ProductionSessionLaunchError` and raw `subprocess.TimeoutExpired`, then raises `ProductionSupportLaunchError("production_support_target_date_resolver_failed", boundary="target-date-resolver")`. Replace every Stage947 direct `_resolve_target_date(environment)` call with this wrapper.

Add `_canonical_support_owner(job: str) -> bool`, using the existing support-job spec label, `os.getppid() == 1`, and exact `XPC_SERVICE_NAME` equality. This is the only ownership predicate used by support fallback notification.

For monthly Stage935, always attempt `_decode_final_json(result.stdout)` before checking `returncode`. If return code is nonzero, raise with boundary `monthly-stage935` and `downstream_email_attempted=True` only when `email_result.email_status` is one of the five owned statuses. `skipped_by_policy`, absent JSON, or invalid result remains false.

Wrap failures after a successful `monthly_ai_pool_updated` result—Stage909 precompute, receipt build, or receipt validation—as boundary `monthly-receipt-refresh` with `downstream_email_attempted=False`, because the earlier AI-pool email does not report the new receipt failure.

In Stage947 `main()`, normalize typed blockers and unexpected failures, print the existing fail-closed JSON with API zeros, and call fallback only when all are true:

```python
args.job != "health"
and _canonical_support_owner(args.job)
and not error.downstream_email_attempted
```

Keep manual owner mismatch silent and keep every existing `os.execve` path unchanged.

- [ ] **Step 5: Run GREEN and commit**

Run:

```bash
.py311/bin/python -m pytest -q \
  tests/test_stage945_production_launcher.py \
  tests/test_stage947_production_support_launcher.py
```

Expected: all launcher tests pass; fake notifier counts are exact; no raw secret appears; no real email/CTP/order call occurs.

Commit:

```bash
git add \
  examples/portfolio_backtesting/run_qmt_roll_stage945_official_live_production_session_launcher.py \
  examples/portfolio_backtesting/run_qmt_roll_stage947_official_live_production_support_launcher.py \
  tests/test_stage945_production_launcher.py \
  tests/test_stage947_production_support_launcher.py
git commit -m "fix(stage200): notify pre-handoff production failures"
```

---

### Task 7: Bind Every Changed Runtime Dependency into Production Qualification

**Files:**
- Modify: `examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py:49-78,349-471`
- Modify: `tests/test_stage179_release_manifest.py:699-731,2035-2090`

**Interfaces:**
- Consumes: all new/changed runtime modules and focused tests.
- Produces: release critical-file hashing and trusted qualification coverage for the exact Stage200 runtime surface.

- [ ] **Step 1: Add RED release-coverage assertions**

Extend `test_default_manifest_covers_runtime_and_deployment_boundary` with:

```python
required.update({
    "examples/portfolio_backtesting/analyze_qmt_roll_stage650_stage526_200k_capital_reality_check.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_lightweight_context.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_email_notify.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_failure_notify.py",
    "tests/test_official_live_failure_notify.py",
})
```

Add an assertion that `tests/test_official_live_failure_notify.py` is present in `PRODUCTION_REQUIRED_TEST_SUITES`.

Run:

```bash
.py311/bin/python -m pytest -vv --tb=short \
  tests/test_stage179_release_manifest.py::Stage179ReleaseManifestTest::test_default_manifest_covers_runtime_and_deployment_boundary
```

Expected: FAIL with the missing Stage200 paths.

- [ ] **Step 2: Extend the immutable release and trusted-test lists**

Add these four runtime files to `DEFAULT_CRITICAL_FILES`:

```python
"examples/portfolio_backtesting/analyze_qmt_roll_stage650_stage526_200k_capital_reality_check.py",
"examples/portfolio_backtesting/qmt_roll_official_live_lightweight_context.py",
"examples/portfolio_backtesting/qmt_roll_official_live_email_notify.py",
"examples/portfolio_backtesting/qmt_roll_official_live_failure_notify.py",
```

Add this test to both `PRODUCTION_REQUIRED_TEST_SUITES` and `DEFAULT_CRITICAL_FILES`:

```python
"tests/test_official_live_failure_notify.py",
```

Do not add env files, generated evidence, private state, or email audit files.

- [ ] **Step 3: Run GREEN and commit**

Run:

```bash
.py311/bin/python -m pytest -q tests/test_stage179_release_manifest.py
```

Expected: all release/qualification schema and immutable file-set tests pass.

Commit:

```bash
git add \
  examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py \
  tests/test_stage179_release_manifest.py
git commit -m "build(stage200): qualify receipt and email dependencies"
```

---

### Task 8: Run Complete Offline Verification and Record Stage200

**Files:**
- Create: `research/lines/futures_trend_stage819_intraday_rules/stages/20260723_2040_stage200_production_receipt_email_reliability.md`
- Verify: every file changed in Tasks 1-7

**Interfaces:**
- Consumes: final Stage200 candidate.
- Produces: a clean exact commit ready for independent review and fast-forward merge.

- [ ] **Step 1: Run focused production regression**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .py311/bin/python -m pytest -q \
  tests/test_stage179_production_assets.py \
  tests/test_official_live_config_import.py \
  tests/test_official_live_failure_notify.py \
  tests/test_stage945_production_launcher.py \
  tests/test_stage946_production_health_check.py \
  tests/test_stage947_production_support_launcher.py \
  tests/test_stage179_release_manifest.py \
  tests/test_stage179_launchd_lifecycle.py \
  tests/test_stage948_production_installer.py
```

Expected: all selected tests pass; no CTP, SMTP, launchctl mutation, or order API call.

- [ ] **Step 2: Run full offline suite and existing 100-round process races**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .py311/bin/python -m pytest -q
```

Then run the explicit concurrency evidence:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .py311/bin/python -m pytest -q \
  tests/test_stage179_two_executor_process_race.py \
  tests/test_stage179_fault_matrix.py \
  tests/test_official_live_failure_notify.py -k "fork or race or cooldown"
```

Expected: full suite passes; existing lease/CAS tests complete 100 rounds with one winner; notifier fork test completes 100 rounds with one fake sender; API counts remain zero.

- [ ] **Step 3: Run static, manifest, shell, plist, and tracked-file checks**

Run:

```bash
.py311/bin/python -m py_compile \
  examples/portfolio_backtesting/analyze_qmt_roll_stage650_stage526_200k_capital_reality_check.py \
  examples/portfolio_backtesting/qmt_roll_official_live_lightweight_context.py \
  examples/portfolio_backtesting/qmt_roll_official_live_email_notify.py \
  examples/portfolio_backtesting/qmt_roll_official_live_failure_notify.py \
  examples/portfolio_backtesting/run_qmt_roll_stage922_official_live_target_date_resolver.py \
  examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py \
  examples/portfolio_backtesting/run_qmt_roll_stage945_official_live_production_session_launcher.py \
  examples/portfolio_backtesting/run_qmt_roll_stage947_official_live_production_support_launcher.py
bash -n examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_supervisor.sh
plutil -lint examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-production-live-*.plist
git diff --check
git ls-files --error-unmatch \
  examples/portfolio_backtesting/analyze_qmt_roll_stage650_stage526_200k_capital_reality_check.py \
  examples/portfolio_backtesting/qmt_roll_official_live_lightweight_context.py \
  examples/portfolio_backtesting/qmt_roll_official_live_email_notify.py \
  examples/portfolio_backtesting/qmt_roll_official_live_failure_notify.py \
  examples/portfolio_backtesting/run_qmt_roll_stage922_official_live_target_date_resolver.py \
  examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py \
  examples/portfolio_backtesting/run_qmt_roll_stage945_official_live_production_session_launcher.py \
  examples/portfolio_backtesting/run_qmt_roll_stage947_official_live_production_support_launcher.py
```

Expected: every command exits 0; seven plists remain unchanged and valid; all runtime dependencies are Git tracked.

- [ ] **Step 4: Run a clean Stage922 performance observation**

Use a new temporary control directory and a fresh child process. Record wall time and loaded-module evidence in the Stage200 record, but gate only on the forbidden import set and correct output/data roots.

Expected: resolver exits 0 well inside the retained 60-second guard in this observation; no timing threshold is added to unit tests.

- [ ] **Step 5: Write and commit the Chinese Stage200 record**

The stage record must state the actual minute, exact commits, changed files, test counts, cold-smoke observation, no backtest, and that independent review, production qualification, activation, and operational readback have not yet run at this commit. Do not pre-fill later evidence. Include these explicit values:

```text
新增策略参数：无
修改策略参数：无
删除策略参数：无
期末权益：不适用（未运行回测）
总收益：不适用（未运行回测）
最大回撤：不适用（未运行回测）
Sharpe：不适用（未运行回测）
总滑点：不适用（未运行回测）
总交易次数：不适用（未运行回测）
胜率：不适用（未运行回测）
过拟合：否；只修控制面与单样本统计退化语义
继续价值：是；进入独立 review 与 production qualification，不继续扩展 alpha
```

Commit the record and any final test-only corrections:

```bash
git add research/lines/futures_trend_stage819_intraday_rules/stages/*stage200_production_receipt_email_reliability.md
git commit -m "docs(stage200): record production reliability verification"
```

Ensure `git status --short` is empty after the commit.

---

### Task 9: Independent Review and Exact Fast-Forward into Master

**Files:**
- Review: exact `git diff e3ecda6991440354ff86f50dcb127276a0c2903b..HEAD` and all Stage200 tests/evidence
- Create outside Git: `~/Library/Application Support/qmt-roll-stage179/production-live/independent-review/stage200-$(git rev-parse HEAD).json`
- Update: `research/lines/futures_trend_stage819_intraday_rules/stages/20260723_2040_stage200_production_receipt_email_reliability.md` with the first review's factual result, then commit and perform a fresh exact-commit final review

**Interfaces:**
- Consumes: clean final feature commit.
- Produces: P0/P1-cleared independent report bound to exact commit/tree and the identical commit at `master`.

- [ ] **Step 1: Dispatch a fresh comprehensive reviewer**

The review prompt must cover:

```text
Spec compliance; first-day Sharpe semantics; strict JSON retention; Stage922 dependency
closure and date equivalence; Stage935 data/control roots; notifier atomicity, flock,
cooldown, crash window and secret redaction; Stage945/947 exit codes, expected skips,
manual-owner suppression, Stage935 duplicate suppression and monthly receipt-refresh
fallback; unchanged execve, launchd, alpha, price, quantity, CTP and order paths;
release critical-file and trusted-suite coverage; test confidence and missing cases.
```

Reviewer must return findings with IDs and severity `P0`, `P1`, or `P2`. Fix all P0/P1, rerun affected/full tests, and commit. Do not dismiss a finding without reproducing or disproving it.

- [ ] **Step 2: Record the first review result and freeze the candidate commit**

Update the exact Stage200 stage record with the first review's real reviewer identity, reviewed commit, P0/P1/P2 counts, resolved findings, any accepted P2 production impact, rerun commands, and final overfitting/value judgement. Do not add qualification or deployment claims. Commit this documentation update:

```bash
git add research/lines/futures_trend_stage819_intraday_rules/stages/20260723_2040_stage200_production_receipt_email_reliability.md
git commit -m "docs(stage200): record independent production review"
```

Expected: the worktree is clean. This new commit, including the truthful review record, is the candidate that must receive the final exact-commit review and all later qualification.

- [ ] **Step 3: Re-review the frozen commit and create the private canonical report**

Dispatch a fresh independent reviewer against the new exact `HEAD`. The reviewer must repeat the complete Step 1 scope and confirm that the Stage200 record itself is accurate. If the fresh review finds a P0/P1 or any factual record error, fix it, rerun affected/full tests, commit, and restart this step on the new `HEAD`.

Only after the fresh exact-commit review has no P0/P1 and requires no Git change, compute `source_commit` with `git rev-parse HEAD` and the critical-file `tree_fingerprint` using `DEFAULT_CRITICAL_FILES`, `release_critical_file_rows()`, and `release_tree_fingerprint()`. Write a mode-`0600` JSON report with these exact fields and value rules:

```python
payload = {
    "schema_version": 1,
    "artifact_kind": "independent_production_review_report",
    "review_id": f"stage200-production-reliability-{source_commit[:12]}",
    "reviewer_identity": "codex-independent-stage200-review-v1",
    "reviewed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "source_commit": source_commit,
    "tree_fingerprint": tree_fingerprint,
    "findings": review_findings,
}
```

`review_findings` is the exact final reviewer list, reduced to `finding_id`, `severity`, and `status`. Remaining P2 entries must already be accurately described in the committed Stage200 record; P0/P1 must be absent. Verify the report's `source_commit` equals the still-clean `HEAD` after writing it.

- [ ] **Step 4: Fast-forward master to the reviewed commit**

Verify no concurrent master movement:

```bash
git merge-base --is-ancestor master codex/stage200-production-reliability-repair
git status --short
git switch master
git merge --ff-only codex/stage200-production-reliability-repair
```

Expected: `master` advances to the exact reviewed commit with no merge commit and a clean worktree. If fast-forward is impossible, stop, rebase safely, rerun full verification/review, and regenerate the review artifact; do not force or create an unreviewed merge commit.

---

### Task 10: Requalify, Activate, Refresh Receipt, and Verify Production

**Files/state:**
- Source: clean `master` at the reviewed Stage200 commit
- Private qualification: `~/Library/Application Support/qmt-roll-stage179/production-live/qualification-bundle`
- Private release: `~/Library/Application Support/qmt-roll-stage179/production-live/release-manifest.json`
- Private activation receipt: `~/Library/Application Support/qmt-roll-stage179/production-live/runtime/state/activation_receipt.json`
- Stable worktree: `/Users/bytedance/Desktop/person/vnpy_production_live`
- Launchd: the existing seven production labels only

**Interfaces:**
- Consumes: reviewed master commit and formal readonly credentials/runtime.
- Produces: matching qualification/release/activation/stable/daily-receipt evidence and restored scheduled production support tasks.

- [ ] **Step 1: Build a new trusted qualification bundle without disturbing the current one**

Choose a non-trading activation window and confirm no production job is running. Build to a new sibling path:

```bash
.py311/bin/python \
  examples/portfolio_backtesting/build_qmt_roll_stage179_production_qualification_bundle.py \
  --output-dir "$HOME/Library/Application Support/qmt-roll-stage179/production-live/qualification-bundle-stage200-$(git rev-parse HEAD)" \
  --repo-root /Users/bytedance/Desktop/person/vnpy_stage179_production_live \
  --review-report "$HOME/Library/Application Support/qmt-roll-stage179/production-live/independent-review/stage200-$(git rev-parse HEAD).json" \
  --confirm-trusted-production-qualification-run I_APPROVE_RUNNING_EXACT_TESTS_AND_TWO_FORMAL_CTP_READONLY_CAPTURES
```

Expected: every required suite passes; two formal read-only captures are qualified; account/position/order/trade query bundles are complete; send/cancel/order API counts are `0/0/0`. Any native runtime, handshake, qualification, or API-count anomaly stops deployment.

After validation, rename the old canonical bundle to a timestamped private backup and the new bundle to `qualification-bundle` in the same parent directory. Preserve `0700` directories and `0600` files. This swap changes evidence only; while the canonical path is absent, launchers must remain fail-closed.

- [ ] **Step 2: Build the new release manifest and activation receipt**

Run:

```bash
.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py \
  --output "$HOME/Library/Application Support/qmt-roll-stage179/production-live/release-manifest.json" \
  --release-id "stage200-production-reliability-$(git rev-parse --short=12 HEAD)" \
  --execution-profile c9-15w \
  --allow-production-live \
  --production-qualification-evidence "$HOME/Library/Application Support/qmt-roll-stage179/production-live/qualification-bundle/qualification.json" \
  --confirm-production-live-manifest I_UNDERSTAND_THIS_BUILDS_A_C9_15W_PRODUCTION_LIVE_RELEASE_MANIFEST

.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_stage179_activation_receipt.py \
  --output "$HOME/Library/Application Support/qmt-roll-stage179/production-live/runtime/state/activation_receipt.json" \
  --release-manifest "$HOME/Library/Application Support/qmt-roll-stage179/production-live/release-manifest.json" \
  --production-qualification-evidence "$HOME/Library/Application Support/qmt-roll-stage179/production-live/qualification-bundle/qualification.json" \
  --confirm-production-activation I_APPROVE_C9_15W_PRODUCTION_LIVE_ACTIVATION_RECEIPT \
  --repo-root /Users/bytedance/Desktop/person/vnpy_stage179_production_live
```

Expected: both builders exit 0 and bind the same HEAD, tree fingerprint, qualification ID, C9/15万 identity, and formal runtime hashes.

- [ ] **Step 3: Move stable to the exact commit and let Stage948 prepare/activate**

Only after verifying all seven jobs have no running PID, switch the clean detached stable worktree to the reviewed master commit:

```bash
git -C /Users/bytedance/Desktop/person/vnpy_production_live \
  checkout --detach "$(git rev-parse HEAD)"
```

Prepare and activate through Stage948:

```bash
.py311/bin/python examples/portfolio_backtesting/install_qmt_roll_stage948_official_live_production.py \
  --source-commit "$(git rev-parse HEAD)" \
  --confirm-prepare I_UNDERSTAND_THIS_PREPARES_C9_15W_PRODUCTION_ASSETS

.py311/bin/python examples/portfolio_backtesting/install_qmt_roll_stage948_official_live_production.py \
  --activate-prepared \
  --confirm-activate I_UNDERSTAND_THIS_LOADS_C9_15W_PRODUCTION_LAUNCHD_JOBS
```

Expected: stable clean at exact HEAD; qualification/release/activation validate; activation status `production_launchd_activated_no_ctp_connection`; disk/domain/loaded/reboot surfaces are exactly `7/7/7`, conflicts 0, rollback 0, and activation itself reports CTP/send/cancel/order `0/0/0/0`.

- [ ] **Step 4: Refresh the new cohort and daily receipt through canonical launchd ownership**

Do not run Stage947 manually. Kickstart the already installed postclose-precompute label without `-k` only when it is not running:

```bash
/bin/launchctl kickstart \
  "gui/$(id -u)/local.qmt-roll.official-live.15w.c9-production-live-postclose-precompute"
```

Wait for the job to exit and inspect its stdout/stderr plus `data-readiness/latest.json`. Expected:

```text
Stage901 analysis_start=analysis_end=current resolved target
current_variant.sharpe is finite
strict canonical cohort and audit seal exist
daily receipt source_commit/manifest/target hashes match the new release
send/cancel/order API = 0/0/0
```

If it fails, verify one fallback notification audit entry for the exact fingerprint and stop; do not run reports or sessions and do not weaken the receipt gate.

- [ ] **Step 5: Run the missed production report and health checks**

After the daily receipt validates, kickstart the postclose-report label once. This is a real catch-up production report, not a test email:

```bash
/bin/launchctl kickstart \
  "gui/$(id -u)/local.qmt-roll.official-live.15w.c9-production-live-postclose-report"
```

Wait for the postclose-report job to exit and inspect its stdout/stderr and email audit. Only after it is terminal, kickstart health:

```bash
/bin/launchctl kickstart \
  "gui/$(id -u)/local.qmt-roll.official-live.15w.c9-production-live-health"
```

Expected: Stage922 resolves without timeout; Stage929 produces its normal signal/report email attempt; health is current and bound to the new release; email audit says `sent` or an explicit safe failure status. Do not claim inbox delivery until the user confirms reception.

- [ ] **Step 6: Final production readback**

Read back and cross-check:

```text
master HEAD == stable HEAD == qualification source_commit == release source_commit
release manifest tree == activation receipt tree
7 installed plist hashes == activation fingerprints
daily receipt release/target/hash cohort == current release
latest Stage922/935/947 paths obey data/control separation
failure notifier state/lock modes == 0600
no legacy/Stage372/readonly conflicting launchd labels
no unexpected process is running
send/cancel/order API counts == 0/0/0 for repair, activation and support catch-up
```

Do not manually kickstart day/night trading sessions. Leave them on their existing schedule; actual execution remains conditional on all existing broker, market, price, risk, authorization, and receipt gates.

Do not change any Git-tracked file after the final exact-commit review or production qualification. Keep qualification totals, formal read-only evidence, manifest/activation IDs, stable/launchd/daily-receipt status, email audit result, and final operational judgement in the existing private qualification/release/activation/health artifacts and in the final user handoff. If a durable post-deploy research note is later required, create it as a separate future stage and require a new qualification before that newer commit can become the production release. Never silently qualify one commit and deploy another.
