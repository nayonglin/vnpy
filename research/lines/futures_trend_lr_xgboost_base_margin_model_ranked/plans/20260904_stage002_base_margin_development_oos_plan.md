# Base-Margin Residual Development OOS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the single preregistered 50-fold development OOS comparison between strict-PIT formal LR and LR-initialized XGBoost residual correction, including Top10 future contribution and drawdown proxies.

**Architecture:** One tested runner rebuilds the frozen formal labeled panel, consumes the Stage001 fold plan, trains A and two deterministic copies of B per fold, records all OOS rows, constructs exact next-60-trading-day Top10 contribution paths, evaluates frozen technical/effect gates, and atomically publishes a manifest-backed bundle. A separate authorization receipt binds the preregistration, implementation, tests, and Stage001 inputs before any label access.

**Tech Stack:** Python 3.11, pandas, NumPy, scikit-learn, XGBoost 3.2.0, pytest, SHA256 manifests.

**Spec:** `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/stages/20260904_1554_stage002_base_margin_development_oos_preregistration.md`

## Global Constraints

- Run exactly once after creating a SHA-bound authorization receipt.
- Do not read any predecessor failed final; use only current-line Stage001 evidence and frozen source files.
- Do not run a true strategy engine, access sealed holdout, connect CTP, call order APIs, or write outside this line.
- Any effect output triggers an independent reviewer before another stage.

### Task 1: Pure Evaluation and Gate Functions

**Files:**
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/tests/test_stage002_base_margin_development_oos.py`
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/tools/stage002_base_margin_development_oos.py`

- [ ] **Step 1: Write failing tests for base-margin training, deterministic repetition, exact next-60 path boundaries, drawdown from zero, stable Top10 selection, yearly/leave-best summaries, and fail-closed gates**
- [ ] **Step 2: Run focused tests and verify RED because the Stage002 module is absent**
- [ ] **Step 3: Implement minimal pure helpers and actual XGBoost 3.2.0 residual fitting**
- [ ] **Step 4: Run focused tests and verify GREEN**

### Task 2: Immutable Runner and Authorization

**Files:**
- Modify: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/tools/stage002_base_margin_development_oos.py`
- Create after code freeze: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/stages/20260904_stage002_execution_authorization.json`

- [ ] **Step 1: Implement exact input identities, receipt validation, formal labeled-panel rebuild, Stage001 fold consumption, counters, and atomic publication**
- [ ] **Step 2: Run all current-line and predecessor tests plus `py_compile`**
- [ ] **Step 3: Compute prereg/code/test/input SHA values and create the authorization receipt without changing bound files afterward**
- [ ] **Step 4: Run a receipt-only preflight that performs zero label reads and zero fits**

### Task 3: Execute, Review, and Close or Advance

**Files:**
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/artifacts/stage002_base_margin_development_oos/`
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/stages/<timestamp>_stage002_base_margin_development_oos_result.md`
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/reviews/<timestamp>_stage002_independent_review.md`
- Modify: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/LINE.md`
- Modify: `research/registry.md`

- [ ] **Step 1: Execute the authorized runner exactly once**
- [ ] **Step 2: Verify manifest, row/fold/PIT/repeat counters, and rerun tests without rerunning the experiment**
- [ ] **Step 3: Spawn an independent reviewer with read-only scope over preregistration, code, tests, and frozen outputs**
- [ ] **Step 4: Record the reviewer findings, exact Chinese result, overfitting judgment, and pass/fail decision; never advance before review**
