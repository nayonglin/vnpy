---
name: futures-multicycle-backtest-report
description: Use when a vn.py futures strategy candidate needs multicycle or multi-start robustness testing against an official baseline, especially for 1/2/3-year equity curves, semiannual starts, or a multicycle promotion audit. Do not use for single-window, attribution-only, or existing-curve requests.
---

# Futures Multicycle Backtest Report

## Core Contract

A valid report compares the official baseline with the candidate through independent full-period, 1Y, 2Y, and 3Y runs. The rolling schedule is exactly every eligible January 1 and June 1 start.

**REQUIRED SUB-SKILL:** Use `version-ab-experiment` for promotion or official-strategy combination.

Commit the frozen data cutoff, arms, costs, windows, metrics, and gates before results. State before-run overfitting and continued-value judgments.

## Required Windows

| Group | Required independent runs |
| --- | --- |
| Full period | One comparison from the common eligible start through the frozen cutoff |
| 1Y | Every January 1 and June 1 start that can complete one year |
| 2Y | Every January 1 and June 1 start that can complete two years |
| 3Y | Every January 1 and June 1 start that can complete three years |

Each duration needs at least one complete January and June start. Otherwise return `insufficient_multicycle_coverage`.

Every window starts a fresh engine, capital, positions, and account state. Warm-up uses only point-in-time prior data. Full-period curve slices are not independent windows. A terminal near-complete window may be shown with `*`, but is observation-only.

Record ending equity, return, max drawdown, Sharpe, slippage, trades, win rate, survival, and applicable margin gates. Fail on missing, non-finite, duplicate, or mismatched arm/window data.

## Fixed Report Shape

Lead with the promotion verdict, then report:

1. Verified official baseline and candidate identities.
2. Full-period metric comparison.
3. 1Y/2Y/3Y table with separate `combined`, `January`, and `June` results for every duration.
4. Weakest return, drawdown, Sharpe, cost, and survival windows.
5. Five images, displayed in this order:
   - full-period official versus candidate equity;
   - 1Y independent rolling equity grid;
   - 2Y independent rolling equity grid;
   - 3Y independent rolling equity grid;
   - multicycle aggregate summary.
6. Links to result CSVs, decision, and Chinese stage record.
7. Reviewer/tests and explicit production/CTP/order safety boundaries.
8. Before/after overfitting and continued-value judgments.

Order every grid by year, January first and June second. Titles show exact start date and duration. Keep colors, legend, and units consistent; explain `*` once.

## Decision Discipline

Full-period or one duration's advantage does not override a failed duration, January cohort, or June cohort. Complete-window gates decide. Do not rescue failures by changing starts, periods, products, parameters, or thresholds after results.

## Common Mistakes

| Wrong shape | Required shape |
| --- | --- |
| Recent 1Y/2Y/3Y trailing snapshots | Independent January and June rolling starts |
| Every-month schedule | Fixed semiannual January/June schedule |
| One combined cycle statistic | Combined plus January plus June breakdown |
| Full-curve slices | Fresh engine per window |
| Custom charts per experiment | The fixed five-image order above |
