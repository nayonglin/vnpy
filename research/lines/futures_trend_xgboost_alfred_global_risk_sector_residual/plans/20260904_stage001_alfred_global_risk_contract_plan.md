# ALFRED Global Risk Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute one label-free Stage001 contract that freezes 231 ALFRED historical snapshots, three global-risk features, and the 15-column sector interaction panel for the formal 18-product AI ranker.

**Architecture:** One tested Python runner owns fold-date reconstruction, strict ALFRED snapshot parsing/acquisition, pure PIT feature transformations, gates, durable telemetry, atomic artifact publication, and offline verification. Tests use synthetic CSV bytes and local temporary directories; only the authorized Stage001 invocation accesses ALFRED, and it writes exclusively under the new research line.

**Tech Stack:** Python 3.11 via `.py311/bin/python`, pandas, numpy, fixed-argv `/usr/bin/curl` subprocess transport, pytest, CSV/JSON/NDJSON/SHA256 standard-library APIs.

**Spec:** `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/stages/20260904_1805_stage000_alfred_global_risk_sector_design.md`

## Global Constraints

- Stage001 must not read target values, fit or predict any model, run a strategy backtest, read holdout, connect CTP, call order APIs, or write production/shared databases.
- Series are exactly `DEXCHUS/DTWEXBGS/VIXCLS`; dates are exactly the 77 formal dates reconstructed from the frozen fold plan; source aggregate SHA256 is exactly `7d312d36015af3e6e09d0e6b3157f2a766bbb0a31ff26b20309161784404d20f`.
- Every snapshot uses its eval-date as ALFRED `vintage_date`, observation end `eval_date - 1 day`, and exact vintage-suffixed value column. Current FRED and third-party fallbacks are forbidden.
- Three state features, four sectors, 15 feature columns, 77 formal dates, 50 OOS dates, and all Stage001 gates are copied verbatim from the spec.
- Existing research lines, formal materials, production checkout, `.vntrader`, CTP, orders, email, and launchd are read-only or untouched.

---

### Task 1: Pure Snapshot Parsing And Feature Transformations

**Files:**
- Create: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tests/test_stage001_alfred_global_risk_contract.py`
- Create: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tools/stage001_alfred_global_risk_contract.py`

**Interfaces:**
- Produces: `parse_snapshot(series_id: str, eval_date: pd.Timestamp, content: bytes) -> pd.DataFrame`, `build_state_features(snapshots: Mapping[tuple[pd.Timestamp, str], pd.DataFrame], eval_dates: Sequence[pd.Timestamp]) -> pd.DataFrame`, and `build_interaction_panel(monthly: pd.DataFrame, products: Sequence[str]) -> tuple[pd.DataFrame, list[str]]`.

- [x] **Step 1: Write failing parser and PIT tests**

```python
def test_parse_snapshot_requires_exact_vintage_column():
    content = b"observation_date,DEXCHUS_20200124\n2020-01-22,6.93\n"
    with pytest.raises(stage001.Stage001Error, match="snapshot_column_mismatch"):
        stage001.parse_snapshot("DEXCHUS", pd.Timestamp("2020-01-23"), content)

def test_parse_snapshot_rejects_same_day_observation():
    content = b"observation_date,VIXCLS_20200123\n2020-01-23,12.0\n"
    with pytest.raises(stage001.Stage001Error, match="snapshot_future_observation"):
        stage001.parse_snapshot("VIXCLS", pd.Timestamp("2020-01-23"), content)
```

- [x] **Step 2: Run the parser tests and verify RED**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tests/test_stage001_alfred_global_risk_contract.py -k 'parse_snapshot' -q`

Expected: collection/import failure because `stage001_alfred_global_risk_contract.py` does not exist.

- [x] **Step 3: Implement strict parser and exact feature formulas**

Implement exact series/date/suffix checks, numeric positivity, duplicate-date rejection, strict pre-eval observations, two volatility-standardized 20-observation FX shocks, one 252-level VIX empirical percentile, the four fixed sectors, and 15 columns without static sector one-hot columns. Do not add downloader, labels, model APIs, or artifact writes in this task.

- [x] **Step 4: Run pure transformation tests and verify GREEN**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tests/test_stage001_alfred_global_risk_contract.py -k 'snapshot or feature or sector or interaction' -q`

Expected: all selected tests pass.

### Task 2: Acquisition, Gates, Durable Telemetry, And Atomic Publication

**Files:**
- Modify: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tests/test_stage001_alfred_global_risk_contract.py`
- Modify: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tools/stage001_alfred_global_risk_contract.py`

**Interfaces:**
- Produces: `reconstruct_eval_dates(fold_plan: pd.DataFrame) -> tuple[list[pd.Timestamp], list[pd.Timestamp]]`, `build_snapshot_url(series_id: str, eval_date: pd.Timestamp) -> str`, `acquire_snapshots(raw_dir: Path, fetcher: Callable[[str], bytes]) -> tuple[list[dict[str, object]], dict[tuple[pd.Timestamp, str], pd.DataFrame]]`, `evaluate_gates(...) -> tuple[dict[str, bool], list[str]]`, `verify_artifact_bundle(output_dir: Path) -> dict[str, object]`, and CLI modes `--authorized-label-free-audit` / `--verify-only`.

- [x] **Step 1: Write failing fold, URL, resume, gate, manifest, and atomic-publication tests**

```python
def test_snapshot_url_is_strict_prior_day_vintage():
    url = stage001.build_snapshot_url("DEXCHUS", pd.Timestamp("2020-01-23"))
    assert "coed=2020-01-22" in url
    assert "vintage_date=2020-01-23" in url

def test_snapshot_resume_rejects_content_with_wrong_vintage(tmp_path):
    path = tmp_path / "2020-01-23_DEXCHUS.csv"
    path.write_bytes(b"observation_date,DEXCHUS_20200124\n2020-01-22,6.93\n")
    with pytest.raises(stage001.Stage001Error, match="existing_snapshot_invalid"):
        stage001.acquire_snapshots(tmp_path, lambda url: b"unused", eval_dates=[pd.Timestamp("2020-01-23")], series_ids=["DEXCHUS"])

def test_manifest_verification_detects_mutation(tmp_path):
    bundle = _write_valid_bundle(tmp_path)
    (bundle / "monthly_state_features.csv").write_text("mutated", encoding="utf-8")
    with pytest.raises(stage001.Stage001Error, match="manifest_mismatch"):
        stage001.verify_artifact_bundle(bundle)
```

- [x] **Step 2: Run acquisition/gate/manifest tests and verify RED**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tests/test_stage001_alfred_global_risk_contract.py -k 'url or resume or gate or manifest or atomic' -q`

Expected: failures naming missing runner behavior.

- [x] **Step 3: Implement the fail-closed Stage001 runner**

Use four bounded workers, five attempts per snapshot with bounded linear backoff, exact response validation before persistence, deterministic aggregate SHA, nonce receipt before network access, append-only NDJSON events including every retry, copied fold plan, input identity snapshots, temporary output directory, complete technical-failure bundle on exceptions, and `os.replace` final publication only after all outputs and recursive manifest are complete.

- [x] **Step 4: Run the complete Stage001 tests and syntax check**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tests/test_stage001_alfred_global_risk_contract.py -q`

Run: `.py311/bin/python -m py_compile research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tools/stage001_alfred_global_risk_contract.py`

Expected: all tests and compilation pass.

- [x] **Step 5: Run existing model-contract regressions**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/tests research/lines/futures_trend_xgboost_cffex_macro_state_residual/tests -q`

Expected: existing scoped tests pass unchanged.

### Task 3: Execute The Single Authorized Label-Free Audit

**Files:**
- Create: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/artifacts/stage001_alfred_global_risk_contract/`
- Create: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/stages/<timestamp>_stage001_alfred_global_risk_contract_result.md`
- Modify: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/LINE.md`
- Modify: `research/registry.md`

**Interfaces:**
- Consumes: frozen Stage000 spec, implementation/tests, formal pointer, predecessor fold plan, and public ALFRED snapshots.
- Produces: one immutable Stage001 decision and evidence bundle; pass permits only Stage002 preregistration, while fail closes this exact source/feature shape.

- [x] **Step 1: Execute one accepted Stage001 audit while preserving all technical attempts**

Run: `.py311/bin/python research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tools/stage001_alfred_global_risk_contract.py --authorized-label-free-audit`

Expected: every transport failure remains an immutable technical-failure bundle; the accepted run produces either the frozen pass decision or a complete semantic fail-close bundle, never labels, model fits, or backtest output.

- [x] **Step 2: Verify the published bundle offline**

Run: `.py311/bin/python research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tools/stage001_alfred_global_risk_contract.py --verify-only`

Expected: `artifact_bundle_valid=true` and manifest mismatches `0`.

- [x] **Step 3: Record Chinese results and update current-state indexes**

Write source/PIT/feature/gate counts, explicit non-applicable backtest metrics, overfitting reflection, continuation-value reflection, decision, and next step into the timestamped stage record, `LINE.md`, and the existing registry row. Do not append root `back_log.md` or `memory.md` because Stage001 creates no backtest or formal candidate.

- [x] **Step 4: Run final scoped verification**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tests research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/tests research/lines/futures_trend_xgboost_cffex_macro_state_residual/tests -q`

Run: `git diff --check -- research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual research/registry.md`

Expected: all tests pass and diff check is clean.
