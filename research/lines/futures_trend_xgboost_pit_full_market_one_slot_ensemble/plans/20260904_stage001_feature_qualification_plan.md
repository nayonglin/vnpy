# Full-Market One-Slot Feature Qualification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run the Stage001 label-free PIT feature, label-plan, and walk-forward-fold qualification for `futures_trend_xgboost_pit_full_market_one_slot_ensemble`.

**Architecture:** A pure feature core receives frozen Stage002 coverage, mapping, contract bars, and catalog frames and returns raw product features, pairwise rank10-relative features, a value-free label plan, a fold plan, and diagnostics. A separate Stage001 runner verifies all frozen hashes, calls the core, enforces the predeclared exact gates, writes a temporary evidence bundle, verifies its manifest, and atomically publishes it inside the new research line.

**Tech Stack:** Python 3.11 via `.py311/bin/python`, pandas, NumPy, pytest, gzip CSV, SHA256 JSON manifest.

**Spec:** `research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/stages/20260904_1441_stage000_model_contract_design.md`

## Global Constraints

- Read only the nine exact frozen inputs and verify their SHA256 before and after execution.
- Stage001 must not import XGBoost, compute future label values, fit or predict any model, run the strategy engine, connect CTP, call order APIs, or write outside this research line.
- Product/exchange identity, winner lists, full-sample PnL, blacklists, and label-derived feature selection are forbidden.
- The only output root is `research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/artifacts/stage001_feature_qualification/`.
- Final output must not already exist; publish by renaming a line-local temporary directory after all gates and manifest checks pass.

---

### Task 1: Pure PIT Feature Core

**Files:**
- Create: `research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tools/full_market_one_slot_features.py`
- Create: `research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tests/test_full_market_one_slot_features.py`

**Interfaces:**
- Consumes: pandas frames for `coverage`, `monthly`, `mapping`, `bars`, and `catalog` plus `FeatureConfig`.
- Produces: `build_feature_bundle(...) -> FeatureBundle`, where `FeatureBundle` contains `raw_features`, `model_features`, `label_plan`, `fold_plan`, and `diagnostics`.

- [ ] **Step 1: Write failing tests for same-contract return splicing and trailing features**

```python
def test_same_contract_returns_do_not_treat_roll_gap_as_return():
    mapping, bars = roll_fixture(old_close=100.0, new_prev=200.0, new_today=202.0)
    returns = build_product_return_history(mapping, bars)
    assert returns.loc[returns["date"].eq("2024-02-01"), "log_return"].item() == pytest.approx(np.log(202.0 / 200.0))

def test_trailing_features_use_only_rows_at_or_before_eval_date():
    features = compute_trailing_features(history_with_future_outlier(), eval_dates=["2024-01-31"])
    assert features["future_bar_rows_used"].sum() == 0
    assert np.isfinite(features[RAW_PATH_FEATURES].to_numpy(float)).all()
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tests/test_full_market_one_slot_features.py -q`

Expected: collection fails because `full_market_one_slot_features.py` does not exist.

- [ ] **Step 3: Implement immutable config, same-contract returns, trailing path, liquidity, and curve descriptors**

```python
@dataclass(frozen=True)
class FeatureConfig:
    return_windows: tuple[int, ...] = (21, 63, 126, 252)
    efficiency_windows: tuple[int, ...] = (63, 126)
    volatility_windows: tuple[int, ...] = (21, 63)
    short_liquidity_window: int = 20
    long_liquidity_window: int = 60
    minimum_valid_ratio: float = 0.90
    minimum_nonzero_months: int = 44
    minimum_train_months: int = 24

def build_product_return_history(mapping: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    """Use each mapped contract's own previous-date close when computing daily return."""

def compute_product_features(...):
    """Return exactly the fourteen frozen raw features with PIT counters."""
```

- [ ] **Step 4: Add tests for curve maturity ordering, HHI, pairwise percentiles, and anchor zeros**

```python
def test_pairwise_features_have_exact_zero_anchor_and_no_identity_columns():
    result = build_pairwise_features(raw_fixture(), action_set_fixture())
    anchor = result[result["role"].eq("formal_rank10")]
    assert np.array_equal(anchor[PAIRWISE_FEATURES].to_numpy(float), np.zeros((1, 14)))
    assert "product_id" not in result.columns
    assert "exchange_id" not in result.columns
```

- [ ] **Step 5: Implement value-free label and strict expanding-fold plans**

```python
def build_label_plan(model_features: pd.DataFrame, all_eval_dates: list[pd.Timestamp]) -> pd.DataFrame:
    """Emit one candidate task per challenger with dates and label-value-read=false only."""

def build_fold_plan(label_plan: pd.DataFrame, *, minimum_train_months: int) -> pd.DataFrame:
    """Train only on months whose next_eval_date is strictly before test_eval_date."""
```

- [ ] **Step 6: Run the focused tests and verify GREEN**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tests/test_full_market_one_slot_features.py -q`

Expected: all feature-core tests pass.

### Task 2: Stage001 Evidence Runner

**Files:**
- Create: `research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tools/stage001_feature_qualification.py`
- Create: `research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tests/test_stage001_feature_qualification.py`

**Interfaces:**
- Consumes: `build_feature_bundle(...)`, the exact Stage000 input paths and hashes, and `--authorized-feature-audit`.
- Produces: `run_stage001(...) -> dict[str, Any]` and an atomic evidence bundle with CSV/JSON/report/manifest files.

- [ ] **Step 1: Write failing tests for authorization, exact input identities, line-local outputs, and atomic publish**

```python
def test_stage001_requires_explicit_authorization(tmp_path):
    with pytest.raises(Stage001Error, match="authorization_required"):
        run_stage001(authorized=False, paths=fake_paths(tmp_path))

def test_output_path_must_stay_inside_line(tmp_path):
    with pytest.raises(Stage001Error, match="output_outside_line"):
        assert_line_local_output(tmp_path / "line", tmp_path / "elsewhere")
```

- [ ] **Step 2: Run the runner tests and verify RED**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tests/test_stage001_feature_qualification.py -q`

Expected: collection fails because `stage001_feature_qualification.py` does not exist.

- [ ] **Step 3: Implement the runner and exact Stage001 gates**

```python
EXPECTED = {
    "action_months": 48,
    "feature_rows": 1819,
    "anchor_rows": 48,
    "challenger_rows": 1771,
    "label_months": 47,
    "label_tasks": 1729,
    "active_folds": 23,
    "effect_evaluable_folds": 22,
    "inference_only_folds": 1,
}

def assess_bundle(bundle: FeatureBundle) -> dict[str, Any]:
    """Evaluate every Stage000 gate without inspecting future label values."""

def publish_bundle(bundle: FeatureBundle, summary: dict[str, Any], paths: OutputPaths) -> None:
    """Write temp, verify manifest, then os.replace temp directory to final."""
```

- [ ] **Step 4: Add tests that fail closed on future rows, nonzero anchor deltas, wrong row counts, labels, and existing final output**

```python
@pytest.mark.parametrize("mutation", ["future_row", "anchor_nonzero", "label_column", "row_count"])
def test_assessment_rejects_contract_violation(valid_bundle, mutation):
    broken = mutate_bundle(valid_bundle, mutation)
    assert assess_bundle(broken)["all_gates_passed"] is False
```

- [ ] **Step 5: Run all new-line tests and syntax checks**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tests -q`

Expected: all tests pass.

Run: `.py311/bin/python -m py_compile research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tools/full_market_one_slot_features.py research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tools/stage001_feature_qualification.py`

Expected: no output and exit code 0.

### Task 3: Execute and Close Stage001

**Files:**
- Create: `research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/artifacts/stage001_feature_qualification/`
- Create: `research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/stages/<timestamp>_stage001_feature_qualification_result.md`
- Modify: `research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/LINE.md`
- Modify: `research/registry.md`

**Interfaces:**
- Consumes: the tested Stage001 CLI and explicit user authorization represented by `--authorized-feature-audit`.
- Produces: a frozen pass/fail decision. Pass permits only Stage002 label-proxy preregistration; failure closes the line.

- [ ] **Step 1: Run the unique Stage001 audit**

Run: `.py311/bin/python research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tools/stage001_feature_qualification.py --authorized-feature-audit`

Expected: one JSON summary with either the exact pass or fail decision and zero label/model/backtest/order/production counts.

- [ ] **Step 2: Independently recompute manifest and contract invariants**

Run: `.py311/bin/python -m pytest research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tests -q`

Expected: all tests pass after artifact publication.

Run: `.py311/bin/python research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble/tools/stage001_feature_qualification.py --verify-only`

Expected: all manifest sizes/SHA256 values, frozen input hashes, row counts, PIT counters, and decision fields verify with zero errors and no writes.

- [ ] **Step 3: Write the Chinese result record and update line/registry only**

Record exact inputs, parameters, output hashes, all gate results, no-backtest metrics as not applicable, reviewer reason, overfitting reflection, continued-value decision, and the next permitted stage. Do not append root `back_log.md` or `memory.md` because Stage001 produces no backtest.

- [ ] **Step 4: Final scoped verification**

Run: `git diff --check -- research/registry.md`

Expected: no whitespace errors.

Run: `rg -n '[[:blank:]]+$' research/lines/futures_trend_xgboost_pit_full_market_one_slot_ensemble`

Expected: no output.
