# Model-Ranked Base-Margin Stage001 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Independently qualify the formal 18-product model layer, 10-ranked-plus-fixed-fu publication boundary, 108 causal features, and 50 actual-label-end PIT folds without reading labels.

**Architecture:** The new runner verifies the frozen predecessor tools but does not read predecessor artifacts. It independently rebuilds the m0005 daily and monthly feature panel, validates formal policy constants, splits the current published pool by `selection_role`, compares only the ten model-owned rows, enforces the fixed-fu null-feature contract, and atomically publishes a new evidence bundle.

**Tech Stack:** Python 3.11, pandas, NumPy, pytest, SHA256 manifests.

**Spec:** `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/stages/20260904_1547_stage000_model_ranked_boundary_design.md`

## Global Constraints

- Never read the predecessor final artifact directory.
- Never request CSV columns beginning with `future_`, `target_`, or `sample_weight_`.
- Do not import XGBoost, fit/predict, run a strategy backtest, connect CTP, call order APIs, or write outside this line.
- The final output must not exist and must be atomically published with a verified manifest.

### Task 1: Boundary Contract Tests and Runner

**Files:**
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/tests/test_stage001_model_ranked_contract.py`
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/tools/stage001_model_ranked_contract.py`

**Interfaces:**
- Consumes: frozen m0005 sources, policy, latest pool, old feature panel, and read-only predecessor tools.
- Produces: `classify_published_pool`, `assess_gates`, `run_stage001`, `--authorized-label-free-audit`, and `--verify-only`.

- [ ] **Step 1: Write failing tests for exact 10+1 ownership, fixed-fu null features, policy gates, and fail-closed mutations**
- [ ] **Step 2: Run the focused test and verify it fails because the runner is absent**
- [ ] **Step 3: Implement the minimal independent runner and reuse only frozen predecessor utility functions**
- [ ] **Step 4: Run focused tests, all predecessor tests, and `py_compile`**

### Task 2: Execute and Record the Unique Audit

**Files:**
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/artifacts/stage001_model_ranked_contract/`
- Create: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/stages/<timestamp>_stage001_model_ranked_contract_result.md`
- Modify: `research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/LINE.md`
- Modify: `research/registry.md`

- [ ] **Step 1: Run `.py311/bin/python research/lines/futures_trend_lr_xgboost_base_margin_model_ranked/tools/stage001_model_ranked_contract.py --authorized-label-free-audit` exactly once**
- [ ] **Step 2: Run the same tool with `--verify-only` and rerun both lines' tests**
- [ ] **Step 3: Record exact Chinese evidence, non-applicable backtest metrics, overfitting judgment, and the only permitted next stage**
- [ ] **Step 4: Run `git diff --check` and trailing-whitespace checks for the two scoped paths**
