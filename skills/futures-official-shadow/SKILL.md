---
name: futures-official-shadow
description: Use when users ask whether the canonical C9/15w production shadow has actionable futures orders today, tonight, tomorrow morning, or the next session, including open, close, and reconcile questions.
---

# Futures Official Shadow

## Purpose

Answer the execution question from the qualified production cohort: what, if anything, should be done tonight or next session.

Read the repo-local `skills/futures-live-execution-sop/SKILL.md` first. This skill extracts evidence; it never authorizes an ad-hoc broker submit.

## Repository copy and production identity

This skill is distributed with the repository. The absolute paths below identify
the original production host; cloning this repository does not establish a new
production root, qualification, activation, or daily receipt.

Before any query, resolve an explicitly identified, qualified production checkout
and its matching private state. Set `FIAN_PRODUCTION_REPO` and
`FIAN_PRODUCTION_STATE` to those verified locations, and `FIAN_AUDIT_OUTPUT` to a
private audit directory outside both roots. Set `FIAN_SKILL_REPO` to the checkout
containing this skill. If the original host is unavailable and no separately
verified production identity exists, report that production evidence is missing.
Do not substitute a research checkout or a mail-only runtime. Preserve every
identity, cold-start, read-only, and receipt check below.

## Original Production Authority

Use this order:

1. Stable root: `/Users/bytedance/Desktop/person/vnpy_production_live`.
2. Private state root: `/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live`.
3. Required artifacts:
   - `release-manifest.json`
   - `qualification-bundle/qualification.json`
   - `activation/latest.json`
   - `runtime/state/activation_receipt.json`
   - `data-readiness/latest.json`
4. Stable-root config and C9/15w Stage901 artifacts.

Use `/Users/bytedance/Desktop/person/vnpy` only for an explicitly requested offline diagnostic. Before doing so, require its HEAD/profile/config to match the production manifest or report the mismatch and do not call it the current official result.

## Hard Rules

- Use stable-root `.py311/bin/python`.
- Require execution profile `c9-15w`, capital `150000`, and capital label `15w`.
- Require stable HEAD, manifest, qualification, activation, and receipt identities to agree.
- Current cold-start boundary is `2026-07-23`. Do not report, backfill, reconcile into, or chase a pre-start theoretical position.
- Never call CTP `send_order` or `cancel_order`.
- Do not conclude from `signal_plan` alone. Stage901 canonical `pending_orders` is the primary next-session theoretical list.
- Require Stage901 decision identity, latest data date, and target date to match the signed production daily receipt.
- Use Stage901 `live_stop_alignment` so actual Stage904/931 fill evidence supersedes stale theoretical positions.
- Use `trade_event_diagnostics` for close/roll/deleverage reasons.
- Use `entry_candidate_snapshots` to explain opened and rejected flat-entry candidates.
- A historical Stage659-named wrapper may appear inside qualified Stage909. That filename is allowed only because current config resolves it to C9/Stage901; never fall back to Stage659/Stage372 strategy semantics.

## Workflow

1. Read:
   - stable-root `work-type.txt`
   - stable-root `research/registry.md`
   - stable-root `examples/portfolio_backtesting/qmt_roll_official_live_config.py`
   - stable-root `research/lines/futures_trend_stage819_intraday_rules/LINE.md`
   - stable-root `skills/futures-live-execution-sop/SKILL.md`
2. State at start:
   - Overfitting: normally no, because this checks a frozen production profile.
   - Continued value: normally yes, because it prevents missed, stale, or duplicate orders.
3. Resolve the target from the production Stage922/Stage909 cohort and `data-readiness/latest.json`; do not guess from calendar time.
4. Handle cold start:
   - target before `2026-07-23`: report `skipped_before_live_shadow_start`, no action, no backfill;
   - first eligible target without a valid postclose receipt: report fail-closed and no actionable order;
   - valid same-target receipt: continue.
5. Prefer the Stage947/Stage909-produced artifacts already bound to the receipt. Do not blindly update data or rerun shadow during an in-session query.
6. Only when the user explicitly requests a manual refresh, use the production Stage909 plan/run route under the repo SOP, with order APIs remaining zero. Never substitute a direct Stage173 + Stage901 chain for the production receipt workflow.
7. Export and cross-check the canonical evidence:

   ```bash
   "${FIAN_PRODUCTION_REPO:?verified production checkout required}/.py311/bin/python" \
     "${FIAN_SKILL_REPO:?skill checkout required}/skills/futures-official-shadow/scripts/export_official_shadow_events.py" \
     --repo-root "$FIAN_PRODUCTION_REPO" \
     --state-root "${FIAN_PRODUCTION_STATE:?verified production state required}" \
     --output-dir "${FIAN_AUDIT_OUTPUT:?private audit output required}" \
     --target-date YYYY-MM-DD
   ```

   The exporter reads production Stage901 artifacts and writes audit copies to the explicitly configured `FIAN_AUDIT_OUTPUT`, outside both the production repo and private state roots.
8. Require:
   - `execution_profile=c9-15w`
   - `capital=150000`
   - `capital_label=15w`
   - decision, receipt, and requested target dates match
   - send/cancel/order API counts are zero
9. Interpret:
   - `pending_orders`: primary theoretical next-session list.
   - `target_close_events`: close reasons.
   - `target_opened_candidates`: accepted new entries.
   - `target_entry_candidates`: rejected entries and `skip_reason`.
10. Bind to execution state:
   - close needs a matching current broker position;
   - an already-filled or live-stop-superseded action must not be repeated;
   - `normal` may proceed to broker gates;
   - `review` permits close/reduce/reconcile only;
   - missing/unknown risk or stale broker state fails closed.
11. Write the Chinese stage record under `research/lines/futures_trend_stage819_intraday_rules/stages/` only when the query materially refreshes or establishes new evidence. A pure readback need not mutate the repo.

## Report Shape

Lead with:

- tonight/next-session decision;
- pending orders;
- rejected candidates;
- risk and broker/receipt gates;
- send/cancel/order API counts.

For each pending order include:

- `vt_symbol`
- direction
- offset
- volume
- theoretical price
- reason when available

If there are no canonical pending orders, say there is no official theoretical order. If artifacts or receipt are invalid, say the system is fail-closed; do not turn missing evidence into “no signal.”

End with overfitting and continued-value judgments.

## Known Traps

- `signal_plan` empty does not prove there is no order.
- An old shadow holding does not prove the broker should be opened or closed.
- A valid launchd schedule does not prove the daily cohort is ready.
- A current Stage901 file without a matching signed receipt is not a production-actionable result.
- A historical Stage659 filename does not authorize Stage659/Stage372 semantics.
