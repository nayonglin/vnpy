---
name: "qmt-roll-validation"
description: "Runs the QMT roll backtest plus period sweep, Walk-Forward, and Monte Carlo validation. Invoke when working on this repo's portfolio strategy changes or before comparing strategy versions."
---

# QMT Roll Validation

## Purpose

This skill standardizes the validation workflow for the QMT roll portfolio strategy in this repository.

Use it when:

- the user asks to rerun the main backtest after strategy or parameter changes
- the user asks for multi-period validation
- the user asks for Walk-Forward validation
- the user asks for Monte Carlo validation
- the user asks whether the latest version is more robust, overfit, or stable
- a new agent needs the project-specific workflow, output files, and interpretation format

This skill is specific to the workspace rooted at:

`/Users/bytedance/Desktop/person/vnpy`

## Hard Rules

- Use the local interpreter: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- Always set `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- Run scripts from:
  `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting`
- Prefer the current strategy defaults defined in `run_qmt_roll_backtest.py` unless the user explicitly asks to change parameters
- Treat the latest exported CSV/JSON files as authoritative only after the corresponding script run has finished
- If a long batch script is still running, do not summarize from partial terminal output unless clearly marked as preliminary

## Strategy Context

Important project assumptions to preserve while validating:

- Execution model uses same-day close matching via `SameDayCloseBacktestingEngine`
- Position additions are disabled by default
- Sizing uses at most 1 million capital via `min(estimated_equity, base_capital)`
- Short entries only allow `short_case1a`
- Validation pipeline consists of:
  - `run_qmt_roll_backtest.py`
  - `run_qmt_roll_period_sweep.py`
  - `run_qmt_roll_walkforward.py`
  - `run_qmt_roll_monte_carlo.py`

## Canonical Commands

Run all commands from:

`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting`

Main backtest:

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python run_qmt_roll_backtest.py
```

Period sweep:

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python run_qmt_roll_period_sweep.py
```

Walk-Forward:

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python run_qmt_roll_walkforward.py
```

Monte Carlo:

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python run_qmt_roll_monte_carlo.py
```

## Standard Workflow

### 1. Verify Current Configuration

Before running anything:

- inspect `run_qmt_roll_backtest.py`
- confirm the active defaults such as:
  - `risk_ratio_of_total_assets`
  - `risk_ratio_open_interest_surge`
  - `risk_ratio_volume_open_interest_surge`
  - short enablement
  - add-position flags
  - pool/universe assumptions if changed recently

If the user just changed logic in `qmt_roll_portfolio_strategy.py`, also inspect the relevant function.

### 2. Run the Main Backtest

Run `run_qmt_roll_backtest.py` first.

Extract and report:

- end balance
- total return
- max drawdown percent
- sharpe ratio
- return-drawdown ratio
- total trade count

Primary output files:

- `backtest_outputs/qmt_roll_statistics.json`
- `backtest_outputs/qmt_roll_daily_equity.csv`
- `backtest_outputs/qmt_roll_trades_2020_2026_04.csv`
- `backtest_outputs/qmt_roll_entry_risk_diagnostics_2020_2026_04.csv`
- `backtest_outputs/qmt_roll_professional_dashboard.html`
- `backtest_outputs/qmt_roll_trade_review.html`

### 3. Run Multi-Period Validation

Run `run_qmt_roll_period_sweep.py`.

Use:

- `backtest_outputs/qmt_roll_period_sweep_summary.csv`

Focus on:

- `full_sample`
- `period_2020_2021`
- `period_2022_2023`
- `period_2024_2026`
- rolling windows such as `roll_2020_2022`, `roll_2021_2023`, `roll_2022_2024`, `roll_2023_2026`

Interpretation rules:

- strong early sample + weak 2022-2024 means stage sensitivity is still present
- if full-sample improves but weak windows degrade, say so explicitly
- do not describe the strategy as stable unless weak windows are also acceptable

### 4. Run Walk-Forward Validation

Run `run_qmt_roll_walkforward.py`.

Use:

- `backtest_outputs/qmt_roll_walkforward_train_summary.csv`
- `backtest_outputs/qmt_roll_walkforward_test_summary.csv`

What to summarize:

- number of test windows
- count of positive and negative test windows
- best and worst test windows
- selected risk ratio per window
- whether the chosen parameter meaningfully changes across windows

Important caution:

- if all `selected_risk_ratio` values are the same, or if train rows for different `risk_ratio` values are identical, explicitly call out that the parameter grid is not producing real discrimination
- in that case, say Walk-Forward is still useful for out-of-sample performance review, but not for proving parameter-selection effectiveness

### 5. Run Monte Carlo Validation

Run `run_qmt_roll_monte_carlo.py`.

Use:

- `backtest_outputs/qmt_roll_monte_carlo_summary.csv`
- `backtest_outputs/qmt_roll_monte_carlo_simulations.csv`

Focus on both methods:

- `daily_block_bootstrap`
- `trade_block_bootstrap`

Report:

- loss probability
- ruin probability
- probability of drawdown over 20%, 30%, 40%
- median return and median max drawdown
- 1% worst-case drawdown tail if relevant

Interpretation rules:

- if ruin probability is near 0, say tail survival is acceptable
- if 30%+ or 40%+ drawdown probability is still high, say tail drawdown risk remains meaningful
- compare daily-bootstrap and trade-bootstrap tails; the worse one should drive the warning tone

## Result Summary Template

Use a concise Chinese handoff in this shape:

- `已完成`:
  - list which scripts were rerun
- `主回测`:
  - end balance / return / max drawdown / sharpe / return-drawdown ratio
- `多周期`:
  - strongest window
  - weakest window
  - overall conclusion on stage sensitivity
- `Walk-Forward`:
  - positive vs negative windows
  - best and worst test periods
  - whether parameter grid actually discriminates
- `蒙特卡洛`:
  - ruin probability
  - tail drawdown probabilities
  - whether path robustness is acceptable
- `结论`:
  - one paragraph stating whether the latest version improved robustness, only improved full-sample results, or still needs work

## Environment Troubleshooting

If a run fails:

- if `python: command not found`, switch to the explicit interpreter above
- if `ModuleNotFoundError: vnpy`, make sure `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy` is set
- if a batch script is still running, wait for completion before trusting its CSV output
- if the terminal is busy, use another idle terminal instead of interrupting a running job

## When To Escalate

After running the workflow, propose a follow-up drill-down when needed:

- weak-window attribution for `2022-2024`
- decomposition by symbol, direction, or risk mode
- inspection of `volume_open_interest_surge` trades
- investigation of why Walk-Forward parameter choices do not separate

## Example Invocation

Invoke this skill when the user says things like:

- “帮我把回测和多周期、forward、蒙特卡洛都跑一遍”
- “这版改动后重新做完整验证”
- “看看这版是不是更稳，不要只看单次回测”
- “换个 agent 也能按固定流程跑验证吗”
