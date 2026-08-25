---
name: version-ab-experiment
description: Use for valuable vn.py strategy candidates that may become formal, combine with the active official strategy, or need A/B/C validation. Trigger when the user asks to optimize from the live version, evaluate a valuable new version, run an A/B test, decide whether a candidate can be promoted, or prevent overfitting in version research. Do not use for pure attribution, monitor-only reports, or obviously low-value ideas unless the user asks to formalize them.
---

# Version A/B/C Experiment

## Core Rule

Use this skill only for versions with a plausible first-principles reason to matter. Do not run A/B/C for every idea.

Default baseline contract:

- `A =` the checkout identity returned by active `official_strategy_materials/CURRENT.json` plus `assert_official_checkout_matches_active_material()`.
- `B = new_module_standalone` when the module can be tested independently.
- `C = active formal baseline + new_module` as the real promotion candidate.

The current expected ruleset is `stage021_q_rollover_volume_atr_v1`, but resolve it from the active material instead of trusting this text. If checkout identity, remote master, and production identity differ, stop before creating a research branch or arm. Stage78 and Stage372 are historical controls only when the user explicitly names them.

The key decision is not whether `B` looks good. The key decision is whether `C` improves `A` without damaging path robustness.

## Trigger Gate

Before creating scripts or running backtests, classify the request:

- **Run A/B/C** when the idea may be integrated into the formal strategy: entry logic, exit logic, risk sizing, product pool, capital/margin governance, or portfolio-level guard.
- **Run A vs C only** when the idea is a deployment layer: capital size, margin cap, concurrency cap, single-trade cap.
- **Do not run A/B/C** for pure attribution, dashboards, monitoring labels, or post-mortem reports.
- **Stop immediately** if the idea only patches a known weak window, adds a single-product blacklist, or tunes small decimal thresholds without a structural reason.

State both judgments before running:

- Overfitting risk: yes/no and why.
- Continued value: yes/no and why.

## Required Workflow

1. Read `work-type.txt`, `back_log.md`, and `memory.md` enough to identify:
   - current work mode,
   - current formal baseline,
   - stopped branches,
   - known weak windows,
   - prior related tests.
2. Load `official_strategy_materials/CURRENT.json`, run `assert_official_checkout_matches_active_material()`, and compare the six formal identities with remote master and stable production. A mismatch stops the run; do not guess from a stage name or registry prose.
3. Define the candidate hypothesis in one sentence:
   - what structural problem it solves,
   - why it should generalize,
   - how it can interact with the active formal baseline.
4. Predeclare arms:
   - `A`: formal baseline,
   - `B`: standalone candidate, if meaningful,
   - `C`: baseline plus candidate.
5. Predeclare pass/fail metrics before seeing results:
   - full-period equity, return, max drawdown, Sharpe, slippage, trades, win rate,
   - start-year robustness,
   - quarterly or rolling walk-forward,
   - weak-window behavior,
   - slippage/cost pressure when trading count changes.
6. Use `.py311/bin/python` for all Python commands.
7. Run the smallest valid experiment first. Escalate only if `C` has real evidence against `A`.
8. Write Chinese results to the active research line stage file for every backtest; append `back_log.md` only for an important cross-line or formal-candidate milestone.
9. Update `memory.md` only when the result changes future research policy.

## Promotion Rules

Promote only when `C` beats or clearly improves `A` under the relevant objective.

Use this decision table:

| Result | Decision |
| --- | --- |
| `C` beats `A` full-period and passes robustness | Candidate can enter next validation stage |
| `B` beats `A`, but `C` does not | Keep as research branch, not formal |
| `C` improves return but worsens weak windows or drawdown materially | Do not promote |
| `C` wins only because of one favorable period | Do not promote |
| `C` needs extra threshold tweaks after failing | Stop; likely overfitting |
| Monitor-only signal works | Keep as review priority, not trading rule |

For the active formal baseline, return improvement alone is not enough. Risk path quality and weak-window survival matter more.

## Overfitting Controls

Reject or stop when any of these appear:

- tuning exact decimals after seeing results,
- adding product blacklists based on historical losers,
- patching one named weak window,
- adding multiple conditions to rescue a failed candidate,
- interpreting small-sample event rules as hard strategy rules,
- promoting a version that wins full-period but fails start-year or weak-window tests.

Acceptable low-overfit changes:

- structural capital or margin constraints,
- fixed deployment profiles,
- predeclared product-pool cadence,
- monitor-only labels,
- broad first-principles rules tested against multiple periods.

## Backtest Logging Requirements

Every backtest entry in `back_log.md` must include:

- minute-level timestamp,
- whether it is an important breakthrough,
- added, changed, and deleted parameters,
- new, changed, and deleted backtest results,
- ending equity,
- total return,
- max drawdown,
- Sharpe,
- total slippage,
- total trades,
- win rate,
- overfitting reflection before and after,
- continued-value reflection before and after,
- follow-up plan and TODO.

If no backtest is run, say so explicitly.

## Output Format

When reporting to the user in `day` mode, include:

- Current baseline.
- Candidate arms `A/B/C`.
- Result summary table.
- Promotion decision.
- Overfitting judgment.
- Whether continuing is valuable.
- Next step.

In `night` mode, continue autonomously until a candidate either fails, becomes a serious promotion candidate, or reaches a meaningful stopping point; still keep `back_log.md` and `memory.md` updated.
