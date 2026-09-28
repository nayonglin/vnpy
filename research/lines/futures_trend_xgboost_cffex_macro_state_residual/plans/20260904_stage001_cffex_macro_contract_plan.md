# CFFEX Macro State Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build and execute the label-free Stage001 contract that freezes official CFFEX archives, causal prior-day-OI main series, seven macro features, and the 39-column sector interaction panel for the formal 18-product AI ranker.

**Architecture:** One tested Python runner owns official archive acquisition, pure parsing/PIT/feature functions, durable execution telemetry, atomic artifact publication, and offline verification. Tests use in-memory synthetic ZIPs and local temporary directories; only the authorized production invocation accesses the network, and it writes exclusively under the new research line.

**Tech Stack:** Python 3.11 via `.py311/bin/python`, pandas, numpy, requests, pytest, ZIP/CSV/JSON/SHA256 standard-library APIs.

**Spec:** `research/lines/futures_trend_xgboost_cffex_macro_state_residual/stages/20260904_1710_stage000_cffex_macro_state_residual_design.md`

## Global Constraints

- Stage001 must not read target values, fit or predict any model, run a strategy backtest, read holdout, connect CTP, call order APIs, or write production/shared databases.
- Official source months are exactly `201906..202605`; aggregate source SHA256 is exactly `6309d58c005e4409d9961c2197ae67e2a31a9c1c7904a1254f5656ddd00e5e39`.
- Products are exactly `IF/IH/IC/T/TF/TS`; contract selection uses only the exact previous CFFEX trading day's OI, then volume, then symbol.
- Macro features, four sectors, 39 feature columns, 77 formal dates, 50 OOS dates, and all Stage001 gates are copied verbatim from the spec.
- Existing research lines, formal materials, production checkout, `.vntrader`, CTP, orders, email, and launchd are read-only or untouched.

---

### Task 1: Pure CFFEX Source And PIT Transformations

**Files:**
- Create: `research/lines/futures_trend_xgboost_cffex_macro_state_residual/tests/test_stage001_cffex_macro_contract.py`
- Create: `research/lines/futures_trend_xgboost_cffex_macro_state_residual/tools/stage001_cffex_macro_contract.py`

**Interfaces:**
- Produces: `month_range(start: str, end: str) -> list[str]`, `parse_month_archive(month: str, content: bytes) -> tuple[pd.DataFrame, list[str]]`, `build_prior_oi_main_series(bars: pd.DataFrame) -> pd.DataFrame`.
- Contract rows use `date/root/symbol/close/volume/open_interest`; selected rows add `prior_date/prior_open_interest/prior_volume/expected_prior_date/same_contract/roll_event/product_return`.

- [x] **Step 1: Write failing source and PIT tests**

```python
def test_prior_day_oi_wins_even_when_same_day_oi_flips():
    selected = stage001.build_prior_oi_main_series(_three_day_contract_fixture())
    assert selected.loc[selected["date"].eq(pd.Timestamp("2024-01-03")), "symbol"].item() == "IF2401"

def test_roll_day_return_is_zero():
    selected = stage001.build_prior_oi_main_series(_roll_fixture())
    roll = selected.loc[selected["roll_event"].eq(1)].iloc[0]
    assert roll["product_return"] == 0.0
```

- [x] **Step 2: Run the two tests and verify RED**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_cffex_macro_state_residual/tests/test_stage001_cffex_macro_contract.py -k 'prior_day or roll_day' -q`

Expected: collection/import failure because `stage001_cffex_macro_contract.py` does not exist.

- [x] **Step 3: Implement minimal parser and prior-day-OI selection**

Implement month generation, GBK CSV parsing, exact six-root filtering, numeric normalization, duplicate rejection, previous-market-day equality, deterministic tie-break, and zero roll returns. No downloader or artifact writer belongs in this step.

- [x] **Step 4: Run source/PIT tests and verify GREEN**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_cffex_macro_state_residual/tests/test_stage001_cffex_macro_contract.py -k 'archive or prior_day or stale or roll_day' -q`

Expected: all selected tests pass.

### Task 2: Macro Features And Sector Interaction Contract

**Files:**
- Modify: `research/lines/futures_trend_xgboost_cffex_macro_state_residual/tests/test_stage001_cffex_macro_contract.py`
- Modify: `research/lines/futures_trend_xgboost_cffex_macro_state_residual/tools/stage001_cffex_macro_contract.py`

**Interfaces:**
- Consumes: selected daily rows from Task 1 and literal formal eval dates/products.
- Produces: `build_daily_factors(selected: pd.DataFrame) -> pd.DataFrame`, `build_monthly_macro_features(factors: pd.DataFrame, eval_dates: Sequence[pd.Timestamp]) -> pd.DataFrame`, `build_interaction_panel(monthly: pd.DataFrame, products: Sequence[str]) -> tuple[pd.DataFrame, list[str]]`.

- [x] **Step 1: Write failing feature tests with hand-derived fixtures**

```python
def test_sector_mapping_covers_formal_products_once():
    panel, columns = stage001.build_interaction_panel(_macro_fixture(), stage001.FORMAL_PRODUCTS)
    assert panel.groupby("product_vt_symbol").size().eq(1).all()
    assert panel.filter(like="sector_").sum(axis=1).eq(1.0).all()
    assert len(columns) == 39

def test_nonmember_interactions_are_zero():
    panel, _ = stage001.build_interaction_panel(_macro_fixture(), ["au.SHFE", "AP.CZCE"])
    au = panel.loc[panel.product_vt_symbol.eq("au.SHFE")].iloc[0]
    assert au["cffex_equity_momentum_60d_x_agriculture"] == 0.0
```

- [x] **Step 2: Run feature tests and verify RED**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_cffex_macro_state_residual/tests/test_stage001_cffex_macro_contract.py -k 'macro or sector or interaction' -q`

Expected: failures naming missing feature functions/constants.

- [x] **Step 3: Implement the exact seven macro and 39 interaction features**

Use 60-day compounded returns, 20/120 sample-volatility ratios, 60-day correlation, three-index breadth, and three-index momentum dispersion. Select values only on exact eval dates; no as-of fallback or fill value is allowed.

- [x] **Step 4: Run all pure transformation tests and verify GREEN**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_cffex_macro_state_residual/tests/test_stage001_cffex_macro_contract.py -q`

Expected: all current tests pass without warnings from production code.

### Task 3: Acquisition, Gates, Durable Telemetry, And Atomic Publication

**Files:**
- Modify: `research/lines/futures_trend_xgboost_cffex_macro_state_residual/tests/test_stage001_cffex_macro_contract.py`
- Modify: `research/lines/futures_trend_xgboost_cffex_macro_state_residual/tools/stage001_cffex_macro_contract.py`

**Interfaces:**
- Produces: `acquire_archives(raw_dir: Path, fetcher: Callable[[str], bytes]) -> tuple[list[dict[str, object]], pd.DataFrame]`, `evaluate_gates(...) -> tuple[dict[str, bool], list[str]]`, `verify_artifact_bundle(output_dir: Path) -> dict[str, object]`, and CLI modes `--authorized-label-free-audit` / `--verify-only`.
- Final bundle contains raw ZIPs, normalized/PIT/factor/monthly/panel tables, copied fold plan, identities, receipt, NDJSON ledger, summary, report, and manifest.

- [x] **Step 1: Write failing acquisition/gate/manifest tests**

```python
def test_archive_resume_rejects_corrupt_existing_zip(tmp_path):
    (tmp_path / "201906.zip").write_bytes(b"not-a-zip")
    with pytest.raises(stage001.Stage001Error, match="existing_archive_invalid"):
        stage001.acquire_archives(tmp_path, lambda month: b"unused", months=["201906"])

def test_manifest_verification_detects_mutation(tmp_path):
    bundle = _write_valid_bundle(tmp_path)
    (bundle / "monthly_macro_features.csv").write_text("mutated", encoding="utf-8")
    with pytest.raises(stage001.Stage001Error, match="manifest_mismatch"):
        stage001.verify_artifact_bundle(bundle)
```

- [x] **Step 2: Run acquisition/gate/manifest tests and verify RED**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_cffex_macro_state_residual/tests/test_stage001_cffex_macro_contract.py -k 'archive_resume or gate or manifest or atomic' -q`

Expected: failures naming missing runner behavior.

- [x] **Step 3: Implement network acquisition and fail-closed runner**

Use three bounded attempts per month, browser-like user-agent and CFFEX referer, exact ZIP validation, per-month SHA, aggregate SHA, nonce receipt before network access, append-only event ledger, temporary output directory, technical-failure bundle on exceptions, and `os.replace` publication only after every gate passes or a complete fail-close summary is built.

- [x] **Step 4: Run the complete Stage001 test file and verify GREEN**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_cffex_macro_state_residual/tests/test_stage001_cffex_macro_contract.py -q`

Expected: all tests pass.

- [x] **Step 5: Run syntax and existing-line regression checks**

Run: `.py311/bin/python -m py_compile research/lines/futures_trend_xgboost_cffex_macro_state_residual/tools/stage001_cffex_macro_contract.py`

Run: `.py311/bin/python -m pytest research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/tests research/lines/futures_trend_xgboost_pit_full_market_source_rebuild/tests -q`

Expected: syntax passes and existing `45` tests pass.

### Task 4: Execute The Single Authorized Label-Free Audit

**Files:**
- Create: `research/lines/futures_trend_xgboost_cffex_macro_state_residual/artifacts/stage001_cffex_macro_contract/`
- Create: `research/lines/futures_trend_xgboost_cffex_macro_state_residual/stages/<timestamp>_stage001_cffex_macro_contract_result.md`
- Modify: `research/lines/futures_trend_xgboost_cffex_macro_state_residual/LINE.md`
- Modify: `research/registry.md`

**Interfaces:**
- Consumes: frozen Stage000 spec, implementation/tests, formal pointer, predecessor fold plan, and public CFFEX archives.
- Produces: one immutable Stage001 decision and evidence bundle; pass permits only Stage002 preregistration, while fail closes this feature/source shape.

- [x] **Step 1: Execute Stage001 exactly once**

Run: `.py311/bin/python research/lines/futures_trend_xgboost_cffex_macro_state_residual/tools/stage001_cffex_macro_contract.py --authorized-label-free-audit`

Expected: either frozen pass decision or complete fail-close bundle; never labels, model fits, or backtest output.

- [x] **Step 2: Verify the published bundle offline**

Run: `.py311/bin/python research/lines/futures_trend_xgboost_cffex_macro_state_residual/tools/stage001_cffex_macro_contract.py --verify-only`

Expected: `artifact_bundle_valid=true` and manifest mismatches `0`.

- [x] **Step 3: Record Chinese results and update current-state indexes**

Write every source/PIT/feature/gate count, explicit non-applicable backtest metrics, overfitting reflection, continuation-value reflection, decision, and next step into the timestamped stage record, `LINE.md`, and the existing registry row. Do not append `back_log.md` or `memory.md` because no backtest or strategic policy change occurred.

- [x] **Step 4: Run final scoped verification**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_cffex_macro_state_residual/tests research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/tests research/lines/futures_trend_xgboost_pit_full_market_source_rebuild/tests -q`

Run: `git diff --check -- research/lines/futures_trend_xgboost_cffex_macro_state_residual research/registry.md`

Expected: all tests pass and diff check is clean.
