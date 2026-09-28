# ALFRED Global-Risk Development OOS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute one preregistered 50-fold development OOS A/B/C comparison where formal LR is A, frozen 15-feature standalone XGBoost is diagnostic B, and LR-initialized 15-feature sector residual XGBoost is candidate C.

**Architecture:** One tested runner verifies Stage001, joins its immutable interaction panel to the formal labeled panel, consumes the frozen fold plan, fits A plus two deterministic copies of B and C per fold, records 900 OOS rows, constructs exact next-60-trading-day A/C Top10 contribution paths, evaluates frozen technical/effect gates, and atomically publishes a manifest-backed bundle. A separate receipt binds the preregistration, implementation, tests, and all consumed inputs before label access.

**Tech Stack:** Python 3.11, pandas, NumPy, scikit-learn 1.8.0, XGBoost 3.2.0, pytest, SHA256 manifests.

**Spec:** `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/stages/20260904_2124_stage002_alfred_global_risk_development_oos_preregistration.md`

## Global Constraints

- Run exactly once after a SHA-bound receipt and a zero-label preflight.
- Do not read predecessor Stage002 result artifacts; only reuse audited code interfaces and current-line Stage001 evidence.
- Do not run a true strategy engine, access sealed holdout, connect CTP, call order APIs, or write outside this research line and `research/registry.md`.
- Any effect output requires an independent reviewer before closing or advancing.

### Task 1: Pure A/B/C, Path, Summary, and Gate Functions

**Files:**
- Create: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tests/test_stage002_alfred_global_risk_development_oos.py`
- Create: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tools/stage002_alfred_global_risk_development_oos.py`

- [x] **Step 1: Write failing tests for standalone/residual deterministic fits, frozen feature join, exact future path boundaries, zero-origin drawdown, stable A/C Top10, effect summaries, and gates**
- [x] **Step 2: Run focused tests and verify RED because the Stage002 module is absent**
- [x] **Step 3: Implement minimal pure helpers and actual XGBoost 3.2.0 fitting**
- [x] **Step 4: Run focused tests and verify GREEN**

### Task 2: Immutable Runner and Authorization

**Files:**
- Modify: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/tools/stage002_alfred_global_risk_development_oos.py`
- Create after code freeze: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/stages/20260904_stage002_execution_authorization.json`

- [x] **Step 1: Implement exact identities, receipt validation, formal labeled-panel rebuild, immutable 15-feature join, fold runner, counters, failure bundle, manifest, and atomic publication**
- [x] **Step 2: Run current-line and predecessor regression tests plus `py_compile`**
- [x] **Step 3: Freeze prereg/code/test/input SHA values in the single-run authorization receipt without modifying bound files afterward**
- [x] **Step 4: Run receipt-only preflight and prove zero label reads, fits, and output writes**

### Task 3: Execute, Review, and Close or Advance

**Files:**
- Create: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/artifacts/stage002_alfred_global_risk_development_oos/`
- Create: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/stages/<timestamp>_stage002_alfred_global_risk_development_oos_result.md`
- Create: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/reviews/<timestamp>_stage002_independent_review.md`
- Modify: `research/lines/futures_trend_xgboost_alfred_global_risk_sector_residual/LINE.md`
- Modify: `research/registry.md`

- [x] **Step 1: Execute the authorized Stage002 runner exactly once**
- [x] **Step 2: Verify manifest, rows/folds/PIT/repeat/join counters, and rerun tests without rerunning the experiment**
- [x] **Step 3: Dispatch an independent read-only reviewer over preregistration, code, tests, and frozen outputs**
- [x] **Step 4: Record reviewer findings, exact Chinese results, overfitting judgment, and pass/fail decision; never advance before review**
