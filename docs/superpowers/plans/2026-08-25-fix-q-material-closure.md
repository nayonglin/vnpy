# Q Formal Material Closure Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the Stage021-Q strategy engine to the formal source and make every future official release automatically include its local Python runtime dependency closure.

**Architecture:** The current official config advertises Q overrides, but the promoted top-level strategy engine ignores them because `qmt_roll_portfolio_strategy.py` was reverted and omitted from every release inventory. Restore the already-reviewed Q implementation, validate that the live strategy class consumes every configured override, and make the release builder trace local imports from production runtime entrypoints so future dependencies cannot silently disappear.

**Tech Stack:** Python 3.11, pytest/unittest, Git worktrees, immutable official material releases, Stage948 production installer.

**Spec:** `research/lines/futures_trend_rollover_shape_same_volume/LINE.md`

## Global Constraints

- Keep all CTP, order, send, and cancel API counts at zero.
- Rollover `shrink_to_allowed` must produce `min(previous_volume, allowed_volume)` and must never expand the old position.
- Do not overwrite an existing material release; create a new release and promote it through the controlled workflow.
- Do not edit or publish Git changes from the stable production worktree.
- Preserve the current monthly AI pool and bind it into the new immutable release.

---

### Task 1: Protect the runtime/config contract

**Files:**
- Modify: `tests/test_official_live_config_import.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`

**Interfaces:**
- Consumes: `build_official_live_strategy_overrides() -> dict[str, Any]` and `QmtRollPortfolioStrategyStage847C9StopRetry.parameters`.
- Produces: a test-protected guarantee that every formal override is consumed by the strategy class.

- [ ] Add a failing test that compares all live override keys with the concrete Stage847 strategy parameter set.
- [ ] Run only that test and confirm it fails on the missing Q parameters.
- [ ] Restore the frozen Stage021-Q strategy implementation from commit `b907562db36d38ca5e07c9b1eba8e3e5dd9e88c5`.
- [ ] Re-run the focused config and rollover tests and confirm the contract passes.

### Task 2: Close formal release imports automatically

**Files:**
- Modify: `tests/test_official_strategy_material_release.py`
- Modify: `examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py`
- Modify: `examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py`

**Interfaces:**
- Consumes: `DEFAULT_CRITICAL_FILES` and `discover_materials(...)`.
- Produces: official release discovery whose Python runtime entrypoints recursively include `qmt_roll_portfolio_strategy.py` and other tracked local imports.

- [ ] Add a failing release-discovery test using the real official critical-file set.
- [ ] Confirm the test fails because the strategy engine is absent from the current release discovery.
- [ ] Pass production Python critical files as discovery entrypoints and explicitly classify the core strategy as production critical.
- [ ] Re-run material discovery/release/identity tests and verify the generated inventory contains the core strategy.

### Task 3: Freeze, qualify, promote, and install

**Files:**
- Create: `research/lines/futures_trend_rollover_shape_same_volume/stages/20260825_HHMM_stage026_q_material_closure_fix.md`
- Create: a new immutable release under `official_strategy_materials/official_live_stage847_c9_15w_stage819_05r_stop_retry_once/releases/`.
- Modify through controlled tools: `official_strategy_materials/CURRENT.json` and remote `master` formal paths.

**Interfaces:**
- Consumes: fixed source commit, current Stage182 AI assets, qualification evidence, and controlled promotion confirmations.
- Produces: one active release whose source, payload, remote master, stable production installation, and seven launchd jobs share the same identity.

- [ ] Run focused and production qualification tests with zero order APIs.
- [ ] Commit the clean source fix and prepare/verify/commit a new immutable release.
- [ ] Activate and promote the release to remote `master`, then verify a fresh clone at ahead/behind `0/0`.
- [ ] Install from the verified remote SHA with Stage948 without connecting CTP.
- [ ] Run closure audit and a Stage901 shadow recomputation for `2026-08-25`; verify rollover never expands prior volume.
- [ ] Record Chinese evidence, remote SHA, production identity, launchd counts, fail-closed state, and zero order/send/cancel counts.
