---
name: stage78-simnow-shadow-sop
description: Use for Stage78-1 futures trend daily SimNow shadow/virtual trading SOP, monthly AI pool cadence, CTP/SimNow read-only checks, Phase B pre-submit gates, risk-level interpretation, and daily execution/reconciliation discipline. Trigger when the user asks about Stage78-1 virtual trading, shadow trading, SimNow, CTP, daily reports, AI pool timing, review/yellow-light risk status, order drafts, or whether a Stage78-1 signal may be submitted. Do not use for unrelated stock/range strategies or alpha optimization.
---

# Stage78-1 SimNow Shadow SOP

## Core Positioning

This skill is an execution-discipline guide, not an alpha-research guide.

- Line: `futures_trend`.
- Strategy: Stage78-1 official trend baseline.
- Capital: `500000` only. Treat old `30w` paths as historical references unless the user explicitly creates a new independent deployment variant.
- Account state source for virtual/live execution: broker/SimNow snapshot, not historical shadow holdings.
- Python: use `.py311/bin/python`.
- Secrets: never write, print, or store CTP/SimNow passwords in repo files, reports, stage records, or chat. Read credentials only from local environment variables or local secure config.

Before running anything, read:

1. `work-type.txt`
2. `research/registry.md`
3. `research/lines/futures_trend/LINE.md`
4. `research/lines/futures_trend/SOP_stage78_monthly_ai_pool.md` when AI pool timing matters

State at the start and end:

- Overfitting judgment: yes/no and why.
- Continued-value judgment: yes/no and why.

## Daily Shadow Workflow

Use this after a completed trading day, normally after market data for that day is available.

1. Identify the latest completed trading day. Do not assume calendar today is a complete trading day.
2. Update main-contract mapping and daily bars:
   - `examples/portfolio_backtesting/build_qmt_roll_stage173_forward_main_contract_data_update.py`
3. Use the current month AI pool for daily signals. Do not retrain or rerank the AI pool every day.
4. Run the canonical 50w Stage78-1 latest-AI-pool shadow runner:
   - `examples/portfolio_backtesting/run_qmt_roll_stage188_stage78_1_2026_cold_start_latest_ai_pool.py`
5. Read the generated daily report and signal plan.
6. Interpret risk level:
   - `base` or normal status: signal may proceed to broker-state gates.
   - `review`: shadow records continue, but SimNow/live execution may only close, reduce risk, or reconcile; do not open new positions.
   - missing/unknown risk state: fail closed.
7. Write a Chinese stage record under `research/lines/futures_trend/stages/`.

## Monthly AI Pool Cadence

The AI pool is monthly, not daily.

- Run monthly live inference only after the previous month last trading day has complete data.
- Daily reports should use the current month pool.
- If the month changed but the pool was not refreshed, say so and either refresh it or mark the daily report as stale-input risk.
- Do not modify the AI ranking logic during daily operations.

## SimNow Gate Workflow

Use this before any virtual order can be submitted.

1. Network probe:
   - `examples/portfolio_backtesting/run_ctp_stage179_simnow_network_probe.py`
2. Read-only CTP/vn.py probe during the intended SimNow service window:
   - `examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh --connect --wait-seconds 90`
3. Require:
   - market login success,
   - trading auth success,
   - trading login success,
   - settlement confirmation success,
   - fresh account snapshot,
   - position snapshot state is `confirmed_flat` or a concrete non-empty position snapshot.
4. If the snapshot is stale, missing, ambiguous, or login fails, stop.
5. Run the Phase B fresh pre-submit gate:
   - `examples/portfolio_backtesting/run_qmt_roll_stage251_phaseb_fresh_pre_submit_gate.py`
6. Confirm total real submit/send-order calls are still zero unless the user explicitly asked for a SimNow virtual order and the SimNow-only adapter is being used.

## Order Discipline

Default posture: dry-run first.

- A backtest, daily report, or shadow script must never directly call a real broker `send_order`.
- Do not submit a close order if SimNow confirms the account is flat and there is no matching position.
- If the strategy has historical shadow holdings but SimNow is flat, start SimNow virtual trading from the actual flat broker state and record the divergence.
- If risk is `review`, only close/reduce/reconcile orders can proceed.
- For first virtual execution after a connectivity change, use a 1-lot smoke test before normal strategy sizing.
- Real-money execution is out of scope for this skill unless the user explicitly asks for a separate live-trading gate review.

## Reconciliation

After SimNow execution or a dry-run gate:

- Compare theoretical target position, SimNow position, submitted order, fills, cancel state, average fill price, slippage, missed orders, and abnormal returns.
- Mark whether account state is aligned, divergent but explainable, or fail-closed.
- Record all output files and the exact command line used.
- Do not silently fix divergence by backfilling positions.

## User-Facing Report

When reporting results, include:

- latest completed data date,
- AI pool month/source,
- risk level and what it permits,
- target signal list,
- SimNow account state,
- gate status,
- whether any order API was called,
- whether tonight/next session has actionable orders,
- output file paths,
- overfitting judgment,
- continued-value judgment,
- next step.

## Stop Conditions

Stop and ask or fail closed when:

- credentials are requested in chat,
- the command would send a real-money order,
- broker state is missing or stale,
- old `30w` Stage78 paths appear in an active execution route,
- `review` risk tries to open a new position,
- SimNow is flat but the proposed action is close-only,
- AI pool is stale and the user is asking for an executable order.
