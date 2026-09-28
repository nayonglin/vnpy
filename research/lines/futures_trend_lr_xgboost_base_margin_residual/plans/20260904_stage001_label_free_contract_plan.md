# LR Base-Margin Residual Stage001 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute the one-shot, label-free m0005 identity, causal-feature parity, and actual 60-trading-day PIT-fold qualification for `futures_trend_lr_xgboost_base_margin_residual`.

**Architecture:** A pure feature module reproduces only the causal half of the frozen formal feature builder and derives a value-free label-end calendar and expanding folds. A separate runner verifies immutable inputs, imports the frozen release only for daily source aggregation, compares feature-only projections against the old formal panel and current published pool, enforces all preregistered gates, then atomically publishes a manifest-backed evidence bundle inside the new line.

**Tech Stack:** Python 3.11 via `.py311/bin/python`, pandas, NumPy, pytest, SHA256 JSON manifests.

**Spec:** `research/lines/futures_trend_lr_xgboost_base_margin_residual/stages/20260904_1532_stage000_base_margin_residual_design.md`

## Global Constraints

- Stage001 must not read columns beginning with `future_`, `target_`, or `sample_weight_` from any CSV.
- Stage001 must not import XGBoost, fit or predict any model, call the strategy engine, connect CTP, call order APIs, or write outside this research line.
- All nine frozen input SHA256 values must match before and after execution.
- Final output is `research/lines/futures_trend_lr_xgboost_base_margin_residual/artifacts/stage001_label_free_contract/`; it must not already exist and publication must be atomic.

---

### Task 1: Pure Causal Feature and PIT Core

**Files:**
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_residual/tests/test_causal_formal_features.py`
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_residual/tools/causal_formal_features.py`

**Interfaces:**
- Consumes: a formal product-daily DataFrame containing only same-day and historical source columns.
- Produces: `build_causal_rolling_features(daily)`, `build_label_free_monthly_samples(featured)`, `build_label_end_calendar(dates, eval_dates)`, and `build_pit_fold_plan(calendar)`.

- [ ] **Step 1: Write failing tests for exact trailing-window semantics and forbidden future columns**

```python
def test_causal_features_ignore_future_outlier():
    baseline = build_causal_rolling_features(daily_fixture(future_value=1.0))
    changed = build_causal_rolling_features(daily_fixture(future_value=1_000_000.0))
    assert_frame_equal(baseline.query("date <= '2024-01-31'"), changed.query("date <= '2024-01-31'"))

def test_monthly_panel_contains_no_forbidden_columns():
    panel, features = build_label_free_monthly_samples(feature_fixture())
    assert len(features) == 108
    assert not any(name.startswith(("future_", "target_", "sample_weight_")) for name in panel)
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_lr_xgboost_base_margin_residual/tests/test_causal_formal_features.py -q`

Expected: collection fails because `causal_formal_features.py` does not exist.

- [ ] **Step 3: Implement the minimal causal rolling builder and monthly feature projection**

Copy the frozen sum/mean column contracts and rolling formulas exactly, but omit `_rolling_future_sum` and every future/target/weight column. Sort by`product_vt_symbol,date`, use the production `min_periods`, and derive the exact sorted 108 feature names from the three frozen windows.

- [ ] **Step 4: Add failing tests for the 60-trading-day label end and whole-month PIT purge**

```python
def test_label_end_is_the_sixtieth_future_trading_date():
    calendar = build_label_end_calendar(dates, [dates[0]], horizon=3)
    assert calendar.loc[0, "label_end"] == dates[3]

def test_pit_fold_excludes_label_ending_after_test_date():
    folds = build_pit_fold_plan(label_calendar_fixture(), minimum_train_months=2)
    assert folds.loc[0, "pit_violation_rows"] == 0
    assert "2024-02-29" not in folds.loc[0, "train_eval_dates"]
```

- [ ] **Step 5: Implement deterministic label-end and expanding-fold plans**

Use `label_end <= test_eval_date`, require at least24 eligible prior months, and emit only dates/counts. Never compute or accept label values.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_lr_xgboost_base_margin_residual/tests/test_causal_formal_features.py -q`

Expected: all tests pass.

### Task 2: Immutable Stage001 Runner

**Files:**
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_residual/tests/test_stage001_label_free_contract.py`
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_residual/tools/stage001_label_free_contract.py`

**Interfaces:**
- Consumes: the pure core, the nine exact frozen inputs, and `--authorized-label-free-audit`.
- Produces: a JSON decision plus `summary.json`, `input_identities.json`, `feature_contract.json`, `fold_plan.csv`, `report.md`, and `artifact_manifest.json`.

- [ ] **Step 1: Write failing tests for authorization, forbidden columns, gate assessment, line-local output, and existing-final refusal**

```python
def test_csv_projection_rejects_forbidden_columns():
    with pytest.raises(Stage001Error, match="forbidden_column"):
        assert_allowed_columns(["eval_date", "future_net_pnl_60d"])

def test_assessment_requires_feature_parity():
    summary = valid_summary()
    summary["historical_parity_max_abs_error"] = 1e-4
    assert assess_gates(summary)["all_gates_passed"] is False
```

- [ ] **Step 2: Run runner tests and verify RED**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_lr_xgboost_base_margin_residual/tests/test_stage001_label_free_contract.py -q`

Expected: collection fails because `stage001_label_free_contract.py` does not exist.

- [ ] **Step 3: Implement immutable identity checks, feature-only CSV reads, parity comparisons, gates, and atomic output**

The runner must insert the frozen release code directory into`sys.path`, import the formal module, configure only the two Stage183 source paths, call `build_product_daily`, and pass the result to the new causal core. It must never call the formal `add_rolling_features` or `build_monthly_samples` functions.

- [ ] **Step 4: Run all line tests and syntax checks**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_lr_xgboost_base_margin_residual/tests -q`

Expected: all tests pass.

Run: `.py311/bin/python -m py_compile research/lines/futures_trend_lr_xgboost_base_margin_residual/tools/causal_formal_features.py research/lines/futures_trend_lr_xgboost_base_margin_residual/tools/stage001_label_free_contract.py`

Expected: no output and exit code0.

### Task 3: Execute, Verify, and Record Stage001

**Files:**
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_residual/artifacts/stage001_label_free_contract/`
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_residual/stages/<timestamp>_stage001_label_free_contract_result.md`
- Modify: `research/lines/futures_trend_lr_xgboost_base_margin_residual/LINE.md`
- Modify: `research/registry.md`

**Interfaces:**
- Consumes: the tested runner and the user's standing authorization to continue label-free research.
- Produces: one frozen pass/fail decision. Pass permits only a separately preregistered Stage002; failure closes the line.

- [ ] **Step 1: Run the unique Stage001 audit**

Run: `.py311/bin/python research/lines/futures_trend_lr_xgboost_base_margin_residual/tools/stage001_label_free_contract.py --authorized-label-free-audit`

Expected: one pass/fail JSON decision with every label/model/backtest/order/production counter at0.

- [ ] **Step 2: Verify the published bundle without writing**

Run: `.py311/bin/python research/lines/futures_trend_lr_xgboost_base_margin_residual/tools/stage001_label_free_contract.py --verify-only`

Expected: all manifest sizes/SHA256 values and decision fields verify with0 errors.

- [ ] **Step 3: Record the exact Chinese result and update line/registry**

Record input identities, parameters, row/month/fold counts, parity errors, decision, non-applicable backtest metrics, reviewer reason, overfitting reflection, continued-value judgment, and the only permitted next stage. Do not modify root`memory.md` or`back_log.md`.

- [ ] **Step 4: Run final scoped verification**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_lr_xgboost_base_margin_residual/tests -q`

Expected: all tests pass.

Run: `git diff --check -- research/registry.md research/lines/futures_trend_lr_xgboost_base_margin_residual`

Expected: no whitespace errors.
