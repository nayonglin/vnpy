# PIT Full-Market Daily Ranker Stage001 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute one manifest-backed, label-free Stage001 contract that freezes the daily causal feature panel, same-contract 20-day label plan, formal monthly scoring plan, and purged walk-forward folds for a future full-market XGBRanker experiment.

**Architecture:** Keep reusable transformations in one pure module and all filesystem identities, counters, gates, staging, and publication in a separate runner. The runner reads only frozen source artifacts, never reads future close values for label construction, and publishes a deterministic evidence bundle only after every preregistered gate passes.

**Tech Stack:** Python 3.11, pandas, NumPy, pytest, gzip CSV, SHA256 manifests.

**Spec:** `research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/stages/20260904_2255_stage001_daily_ranker_contract_preregistration.md`

## Global Constraints

- Use `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`.
- Stage001 reads no entry/exit close values, computes no future return or relevance, performs no model fit/predict or strategy backtest, and touches no CTP/order/production path.
- Preserve the exact `1,067/57,528` base panel, `1,046/52,484` label plan, 48 formal action months, and 37 folds from the spec; failures close the line rather than changing gates.
- Reuse source artifacts read-only; do not modify the closed one-slot ensemble line.
- Do not commit in the shared dirty worktree unless the user explicitly requests it.

---

### Task 1: Causal Daily Feature Contract

**Files:**
- Create: `research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tools/daily_ranker_contract.py`
- Create: `research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tests/test_daily_ranker_contract.py`

**Interfaces:**
- Produces: `build_contract_bar_table(bars: pd.DataFrame) -> pd.DataFrame`
- Produces: `build_mapped_product_history(mapping: pd.DataFrame, contract_bars: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]`
- Produces: `build_base_query_panel(history: pd.DataFrame, contract_bars: pd.DataFrame, catalog: pd.DataFrame, metadata: pd.DataFrame, *, start: pd.Timestamp, capital: float, margin_ratio: float) -> pd.DataFrame`
- Produces: `compute_raw_features(base_panel: pd.DataFrame, history: pd.DataFrame, contract_bars: pd.DataFrame, catalog: pd.DataFrame) -> pd.DataFrame`
- Produces: `build_ranked_model_features(raw_features: pd.DataFrame) -> pd.DataFrame`
- Later tasks consume keys `query_date`, `product_vt_symbol`, `main_contract_vt`, and the frozen 17 raw plus 19 model feature columns.

- [x] **Step 1: Write RED tests for concrete-contract return causality and identity filtering**

Create fixtures where a product switches from contract A at 100 to contract B at 200. Assert the mapped return on the switch date uses B's own prior close, unresolved empty mappings are counted but absent, and duplicate resolved keys raise `ContractError`.

- [x] **Step 2: Run the causal identity tests and verify RED**

Run:

```bash
.py311/bin/python -m pytest research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tests/test_daily_ranker_contract.py -k 'contract_return or unresolved or duplicate' -q
```

Expected: collection/import failure because `daily_ranker_contract.py` is absent.

- [x] **Step 3: Implement normalized dates, strict resolved mapping, concrete-contract returns, and base eligibility**

Implement the frozen 252 mapping-day, 241 valid-return, positive metadata, `150000 * 0.15` margin semantics, at least two valid curve contracts, and no CFFEX. Every merge must declare cardinality and reject duplicates.

- [x] **Step 4: Write RED tests for all 17 raw features**

Use hand-computable constant and alternating return paths to assert exact momentum, efficiency, realized volatility, downside volatility, zero-origin max drawdown, liquidity ratios, front/next basis, full-curve slope, and HHI values. Assert every recorded source date is `<= query_date`.

- [x] **Step 5: Implement causal rolling and curve features**

Use only rows with `date <= query_date`. Require 90% valid same-contract returns for 21/63/126/252 windows. Keep only liquidity ratios nullable when their positive 20/60 windows miss 90%; curve and path failures raise `ContractError`.

- [x] **Step 6: Write RED tests for rank normalization and missing flags**

Assert `rank(method='average', pct=True)`, exact `0.5` neutralization for missing ratios, exact two 0/1 flags, no deletion, stable product ordering, and rejection of any other NaN/inf.

- [x] **Step 7: Implement 17 ranked features plus two missing flags and run Task 1 GREEN**

Run:

```bash
.py311/bin/python -m pytest research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tests/test_daily_ranker_contract.py -q
```

Expected: all Task 1 tests pass.

---

### Task 2: Label, Formal Scoring, and Purged Fold Plans

**Files:**
- Modify: `research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tools/daily_ranker_contract.py`
- Modify: `research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tests/test_daily_ranker_contract.py`

**Interfaces:**
- Produces: `build_label_plan(base_panel: pd.DataFrame, bar_presence: pd.DataFrame, catalog: pd.DataFrame, global_dates: Sequence[pd.Timestamp]) -> tuple[pd.DataFrame, pd.DataFrame]`
- Produces: `build_formal_scoring_plan(base_panel: pd.DataFrame, coverage: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame`
- Produces: `build_purged_fold_plan(label_plan: pd.DataFrame, scoring_plan: pd.DataFrame, *, minimum_train_qids: int = 252) -> pd.DataFrame`
- The label plan may contain dates, identities, booleans, and reason codes only; it must not contain close, return, target, relevance, PnL, or score columns.

- [x] **Step 1: Write RED boundary tests for next-day entry and 21st-day exit plans**

Use a 25-date calendar and assert a query at index 0 maps to entry index 1 and exit index 21, keeps the same contract, rejects expiry before exit, rejects missing entry/exit rows, and never accepts a label-value column.

- [x] **Step 2: Implement label-plan and rejected-plan builders without close access**

Pass a `bar_presence` frame containing only `date` and `contract_vt_symbol`; make the implementation reject extra price columns. Return accepted and rejected plans with deterministic reason codes.

- [x] **Step 3: Write RED tests for formal action identities**

Assert exactly one formal rank10 per action date, challenger role disjointness, all eligible scoring products retained, and latest cutoff month allowed as inference-only even without a label plan.

- [x] **Step 4: Implement formal scoring plan**

Join only identity/eligibility flags from frozen coverage and monthly files. Do not copy formal scores into model features.

- [x] **Step 5: Write RED tests for purged folds**

Construct 260 synthetic qids and assert training includes only `label_end < test_eval_date`, minimum 252 mature qids, no future qid, an effect flag only when the test month has accepted plans, and latest inference-only behavior.

- [x] **Step 6: Implement fold planner and run Task 2 GREEN**

Run:

```bash
.py311/bin/python -m pytest research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tests/test_daily_ranker_contract.py -q
```

Expected: all pure contract tests pass with zero model dependencies.

---

### Task 3: Immutable Stage001 Runner and Evidence Bundle

**Files:**
- Create: `research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tools/stage001_daily_ranker_contract.py`
- Create: `research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tests/test_stage001_daily_ranker_contract.py`
- Create on successful execution: `research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/artifacts/stage001_daily_ranker_contract/`
- Create after execution: `research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/stages/<timestamp>_stage001_daily_ranker_contract_result.md`
- Modify after execution: `research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/LINE.md`
- Modify after execution: `research/registry.md`

**Interfaces:**
- Produces: `collect_input_identities() -> dict[str, dict[str, object]]`
- Produces: `assess_gates(summary: Mapping[str, object]) -> dict[str, object]`
- Produces CLI: `--run` for the one label-free build and `--verify-only` for offline manifest verification.
- Produces bundle files: `raw_feature_panel.csv.gz`, `model_feature_panel.csv.gz`, `label_plan.csv.gz`, `rejected_label_plan.csv.gz`, `formal_scoring_plan.csv`, `fold_plan.csv`, `feature_contract.json`, `input_identities.json`, `summary.json`, `report.md`, `artifact_manifest.json`.

- [x] **Step 1: Write RED tests for frozen SHA identities and forbidden-column/side-effect counters**

Monkeypatch small input files and assert path plus SHA checks, before/after stability, label/fit/predict/backtest/CTP/order/production counters fixed at zero, and rejection when any bound file changes.

- [x] **Step 2: Write RED tests for exact aggregate gates**

Build one passing summary with all preregistered exact counts and one failure per gate family. Assert pass decision `stage001_daily_ranker_contract_pass_allow_stage002_preregistration_only` only when every family passes; otherwise assert `stage001_daily_ranker_contract_fail_close_no_labels`.

- [x] **Step 3: Implement runner, staging directory, manifest, atomic publication, and verify-only mode**

Use a random staging suffix inside the line artifact directory. Hash every output except the manifest, write the manifest, verify it, `os.replace` staging to final, then verify final again. Never overwrite an existing final directory.

- [x] **Step 4: Run focused and predecessor regression tests**

Run:

```bash
.py311/bin/python -m pytest research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tests research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tests research/lines/futures_trend_xgboost_pit_full_market_source_rebuild/tests -q
.py311/bin/python -m py_compile research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tools/daily_ranker_contract.py research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tools/stage001_daily_ranker_contract.py
```

Expected: all tests and compilation pass.

- [x] **Step 5: Execute Stage001 once and verify the frozen bundle**

Run:

```bash
.py311/bin/python research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tools/stage001_daily_ranker_contract.py --run
.py311/bin/python research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tools/stage001_daily_ranker_contract.py --verify-only
```

Expected: either the exact pass decision or a manifest-backed fail-close result. Never change the spec or rerun a failed final bundle.

- [x] **Step 6: Record the Chinese result and close or preregister Stage002 only**

Record exact changes, parameters, counters, feature/query/fold metrics, required backtest fields as not applicable, overfitting judgment, and continuation judgment. Update only this line and the registry; do not append root `memory.md/back_log.md` unless the result is an important cross-line breakthrough.
