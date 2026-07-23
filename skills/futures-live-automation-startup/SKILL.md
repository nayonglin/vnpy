---
name: futures-live-automation-startup
description: Start, install, restart, verify, or troubleshoot this repo's qualified C9/15w production-live launchd automation. Use for production activation, the seven canonical scheduled jobs, Stage945/947/948, cold-start readiness, activation or daily-receipt blockers, and Chinese requests such as “启动全部实盘定时任务” or “检查自动化”.
---

# Futures Live Automation Startup

Use this skill for the C9/15w production control plane. It is an execution SOP, not an alpha-research guide.

## Required First Reads

1. Read `work-type.txt`.
2. Read `research/registry.md`.
3. Read `skills/futures-live-execution-sop/SKILL.md`.
4. Read `examples/portfolio_backtesting/qmt_roll_official_live_config.py`.
5. Read `research/lines/futures_trend_stage819_intraday_rules/LINE.md`.
6. For monthly AI-pool questions, read `research/lines/futures_trend_stage819_intraday_rules/SOP_c9_15w_monthly_ai_pool.md`.

Start and end with:

- Overfitting judgment: yes/no and why.
- Continued-value judgment: yes/no and why.

## Current Production Contract

- Profile: `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`.
- Execution profile: `c9-15w`.
- Capital: `150000`.
- Stable root: `/Users/bytedance/Desktop/person/vnpy_production_live`.
- Private state root: `~/Library/Application Support/qmt-roll-stage179/production-live`.
- Python: stable-root `.py311/bin/python`.
- Cold-start boundary: `2026-07-23`; never backfill or chase pre-start theoretical positions.

Use stable HEAD plus these private artifacts as production authority:

- `release-manifest.json`
- `qualification-bundle/qualification.json`
- `activation/latest.json`
- `runtime/state/activation_receipt.json`
- `data-readiness/latest.json`

An arbitrary development checkout, release branch, or historical stage record cannot override them.

## Exact Seven-Job Surface

Only these production labels may be installed and loaded:

| Label suffix | Schedule | Owner and purpose |
| --- | --- | --- |
| `c9-production-live-day-session` | weekdays 08:55 and 13:25 | Stage945 `--session day` -> Stage930 |
| `c9-production-live-night-session` | weekdays 20:55 | Stage945 `--session night` -> Stage930 |
| `c9-production-live-day-close-readonly` | weekdays 15:12 | Stage947 -> Stage907 production read-only refresh |
| `c9-production-live-postclose-precompute` | weekdays 16:35 | Stage947 -> Stage909 C9 shadow + signed daily receipt |
| `c9-production-live-postclose-report` | weekdays 16:55 | Stage947 -> Stage929 report |
| `c9-production-live-monthly-ai-pool` | weekdays 18:20 | Stage947 -> Stage935 monthly check/update |
| `c9-production-live-health` | weekdays 09:03, 13:33, 21:03 | Stage947 -> Stage946 health |

The full prefix is `local.qmt-roll.official-live.15w.`.

Stage945 validates the exact owned launchd surface, committed activation, release identity, qualification, daily receipt, and cold-start boundary before Stage930. Stage947 applies the same stable-release authority to support jobs.

Treat `c9-readonly-*`, unprefixed legacy 15w jobs, Stage372 jobs, old C9 armed jobs, and Stage179 no-submit jobs as conflicting historical labels. They must be absent from disk and the launchd domain.

## Idempotent Start Decision

For “start all production tasks,” inspect before mutating:

1. Validate stable HEAD, manifest, qualification, activation audit, runtime receipt, installed plist fingerprints, and the exact owned launchd surface.
2. If the exact seven production jobs are already present on disk, in the launchd domain, loaded, and reboot-persistent with zero conflicts, return `already_active`; do not run Stage948 again and do not kickstart a session.
3. Only use Stage948 activation when jobs are absent or drifted and the prepared qualified generation is valid. Report the reason before mutation.
4. A stale or missing daily-data receipt is a trading-readiness blocker, not an installation defect. Do not reinstall launchd to repair it.

## Prepare and Activate

Do not copy individual plists or call `launchctl bootstrap` by hand. Stage948 owns stable-worktree preparation, atomic plist publication, conflict removal, bootout/bootstrap, verification, rollback journal, and activation audit.

Before preparation require:

- an exact clean source commit;
- all production-critical paths present;
- final qualification evidence with every P0/P1 count zero;
- two formal production CTP read-only captures;
- no secret printed or committed.

Prepare from the intended qualified commit:

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python \
  /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/install_qmt_roll_stage948_official_live_production.py \
  --source-commit <40-char-commit> \
  --confirm-prepare I_UNDERSTAND_THIS_PREPARES_C9_15W_PRODUCTION_ASSETS
```

After inspecting the prepared stable HEAD, manifest, qualification bundle, staged plist fingerprints, rollback journal, and zero launchctl/CTP/order counts, activate:

```bash
/Users/bytedance/Desktop/person/vnpy_production_live/.py311/bin/python \
  /Users/bytedance/Desktop/person/vnpy_production_live/examples/portfolio_backtesting/install_qmt_roll_stage948_official_live_production.py \
  --activate-prepared \
  --confirm-activate I_UNDERSTAND_THIS_LOADS_C9_15W_PRODUCTION_LAUNCHD_JOBS
```

Activation is valid only when Stage948 reports `production_launchd_activated_no_ctp_connection`. Never replace the source commit merely to apply documentation or Skill changes; production code changes need a separately qualified release.

## Verification

Require all of the following:

1. Stable HEAD equals the manifest and activation source commit.
2. Qualification evidence is bound to that manifest and has no P0/P1 failure.
3. Activation audit status is successful and the runtime activation receipt validates.
4. Production labels equal exactly seven on disk, in the launchd domain, loaded, and reboot-persistent.
5. Conflicting owned labels equal zero.
6. Stage948 activation has CTP/send/cancel/order counts `0/0/0/0`.
7. Installed plist arguments and fingerprints equal the stable repo definitions.
8. Stage945/947 stdout and stderr logs contain no unresolved launch or security blocker.
9. Stage946 health either passes or explains a real fail-closed condition.

Useful read-only checks:

```bash
git -C /Users/bytedance/Desktop/person/vnpy_production_live rev-parse HEAD
launchctl list | rg 'qmt-roll\.(official-live|stage179)'
```

Read the private JSON artifacts directly for exact counts and identities. Do not infer activation from `launchctl list` alone.

## Cold-Start and Daily Receipt

- A pre-start target must exit Stage945 with `skipped_before_live_shadow_start`, Stage930/CTP/order counts zero, and successful process exit.
- Before the first eligible 16:35 cohort, Stage946 may report `production_support_daily_data_receipt_invalid`; this is expected fail-closed during a deliberate cold start, not a reason to reinstall or force a session.
- Stage947 `postclose-precompute` must generate the first same-target receipt after the cold-start date.
- After that eligible 16:35 run, a missing, stale, or identity-mismatched receipt is a real blocker. Do not bypass it, kickstart around it, or use an old shadow artifact.

## Monthly AI Pool

Stage947 owns production month-end handling:

- `monthly_ai_pool_already_current`: validate the existing receipt.
- `monthly_ai_pool_updated`: rerun the qualified Stage909 precompute and sign a new receipt bound to the updated pool.
- any other state: fail closed.

Do not pass `--allow-incomplete-month`, change ranking logic during startup, or run direct Stage182/183 as a substitute for Stage947.

## Restart and Kickstart Discipline

- Use Stage948 atomic activation for an install, upgrade, or full control-plane reload.
- Do not manually bootstrap individual production plists.
- Do not use `launchctl kickstart -k` to force a trading session or order.
- A one-off kickstart is only a diagnosed remediation after release, activation, receipt, exact surface, market window, and broker gates are already valid. Record why it was necessary.
- Never kickstart a legacy or conflicting label.

## Fail Closed

Stop and report when:

- stable HEAD, manifest, qualification, activation, receipt, or plist identities disagree;
- the owned launchd surface is not exact;
- an old capital/profile/label appears in the active route;
- production env or CTP runtime selection is ambiguous;
- the first eligible postclose receipt fails to materialize;
- Stage945/947 refuses the canonical owner or path;
- broker/account/position state is stale, missing, divergent, or unknown;
- any order API count is non-zero during prepare, activation, or read-only verification.

Do not “repair” a blocker by deleting receipts, copying plists, changing the cold-start date, backfilling positions, or bypassing Stage927/931.

## Reporting Back

Report in Chinese:

- stable source commit and profile;
- activation status;
- exact seven labels: disk/domain/loaded/reboot counts and conflict count;
- qualification P0/P1/P2;
- daily receipt target and validity;
- latest Stage945/947/946 status and blockers;
- whether any CTP/send/cancel/order API was called;
- whether the next session is eligible, fail-closed, or pre-start skipped;
- overfitting and continued-value judgments.

If code, plists, or Skill files changed, record a stage file under `research/lines/futures_trend_stage819_intraday_rules/stages/`.
