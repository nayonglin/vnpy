---
name: futures-live-automation-startup
description: Start, install, restart, verify, or troubleshoot this repo's C9/15w official futures live automations, including launchd day/night Stage930 session daemons, Stage929 timed reports, Stage935 monthly AI pool update, Stage934 health checks, and the standard Chinese workflow for “启动自动化” or “检查自动化”.
---

# Futures Live Automation Startup

Use this skill when the user asks to start, restart, install, or check the official live automation for this repo. This skill is an execution SOP, not an alpha research guide.

## Required First Reads

1. Read `work-type.txt`.
2. Read `research/registry.md`.
3. Read `skills/futures-live-execution-sop/SKILL.md`.
4. Read `examples/portfolio_backtesting/qmt_roll_official_live_config.py`.
5. For monthly AI pool questions, read `research/lines/futures_trend/SOP_stage78_monthly_ai_pool.md`.

Start and end with:

- Overfitting judgment: yes/no and why.
- Continued-value judgment: yes/no and why.

## Current Live Profile

- Current profile: `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`.
- Current line: `futures_trend_stage819_intraday_rules`.
- Current capital: `150000`.
- Python: `.py311/bin/python`.
- Current automation qualification state: C9/15w production-readonly; real submit remains fail closed until the release manifest, installed runtime, CTP read-only chain, and activation receipt all pass.
- Do not fall back to old Stage372/20w, Stage653, Stage78-1, old 30w, or research candidates unless the user explicitly asks for a comparison.

## Standard Automation Set

The safe C9/15w qualification set is:

- `local.qmt-roll.official-live.15w.c9-readonly-day-session`
  - Starts Stage930 at 08:55.
  - Runs Stage930 with `--execution-profile c9-15w --mode dry-run --submit-mode disabled --runtime-profile production-readonly --stage179-execution-mode warm`.
- `local.qmt-roll.official-live.15w.c9-readonly-night-session`
  - Starts Stage930 at 20:55.
  - Uses the same C9/15w production-readonly and no-submit contract as the day job.
- `local.qmt-roll.official-live.15w.c9-readonly-postclose-precompute`
  - Runs Stage909 at 16:35 for the latest completed session.
  - Precomputes the C9/15w shadow artifacts without calling broker order APIs.
- `local.qmt-roll.official-live.15w.postclose`
  - Runs Stage929 post-close report at 16:35.
  - Stage929 runs Stage935 AI-pool preflight before generating the report.
  - The post-close report is a signal/reporting job. It should not hard-require a live CTP read-only refresh, because 16:35 can fall inside clearing or an unavailable front window.
- `local.qmt-roll.official-live.15w.day-close-readonly`
  - Runs Stage907 production-live read-only refresh at 15:05.
  - This is a best-effort account/position/contract snapshot after the day session, before the 16:35 signal email.
  - Do not move the only run to 15:01 without adding snapshot-preservation logic; a too-early failed refresh can overwrite a previously usable Stage174 latest snapshot.
  - It must never submit orders; it only runs `run_qmt_roll_stage907_official_live_readonly_refresh_gate.py --mode refresh`.
- `local.qmt-roll.official-live.15w.evening-report`
  - Runs Stage929 evening report at 21:05.
  - Stage929 runs Stage935 AI-pool preflight before generating the report.
- `local.qmt-roll.official-live.15w.monthly-ai-pool`
  - Runs Stage935 at 18:20.
  - This is a standalone backup/health check. It is not the only protection before reports or trading.
  - Stage935 checks whether Stage182 monthly AI pool is stale versus the latest complete month. It only refreshes Stage183/Stage182 when stale or forced.

Stage930 day/night read-only session daemons also run Stage935 AI-pool preflight at startup. If the pool is stale and Stage935 cannot update it, Stage930 must fail closed instead of generating new open-order intents from an old pool.

The deleted `local.qmt-roll.official-live.15w.c9-day-session` and `local.qmt-roll.official-live.15w.c9-night-session` jobs are legacy armed entrypoints. Keep them disabled and uninstalled; never recreate or bootstrap them from an old checkout.

## Install Or Reload LaunchAgents

Install the three `c9-readonly-*` plists from `examples/portfolio_backtesting/launchd/` into `~/Library/LaunchAgents/`. Do not install an armed real-submit plist during qualification.

Use `launchctl bootout gui/$(id -u)/<label>` before bootstrap when reloading an existing label. Ignore bootout "not found" errors.

Bootstrap and enable each label with:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<label>.plist
launchctl enable gui/$(id -u)/<label>
```

Do not hand-edit installed plists. Edit repo plists first, copy them to `~/Library/LaunchAgents/`, then reload.

## Verification

Run:

```bash
.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage934_official_live_automation_health_check.py
```

Require Stage934 to show:

- day and night C9/15w read-only Stage930 launchd labels loaded;
- day-close Stage907 read-only launchd label loaded;
- monthly AI pool launchd label loaded;
- installed arguments match repo arguments;
- Stage930 process present during a trading session, or scheduled-ready outside session;
- latest Stage930 and Stage935 summaries have `order_api_called_count=0`; any non-zero value fails read-only qualification.
- latest Stage930 summary includes `ai_pool_preflight.automation_status` equal to `monthly_ai_pool_already_current` or `monthly_ai_pool_updated`.

Also check:

```bash
launchctl list | rg 'qmt-roll.official-live.15w'
```

## Monthly AI Pool

Manual check:

```bash
.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py --mode check --email-policy never
```

Normal automated run:

```bash
.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py --mode run --email-policy changes
```

Rules:

- The AI pool is monthly, not daily.
- Do not pass `--allow-incomplete-month` to Stage182 for formal live use.
- Do not change AI ranking logic during startup work.
- Use `--force` only after verifying the expected complete-month eval date.
- Stage935 must not call broker order APIs.
- Stage929 report generation and Stage930 session startup must not continue if Stage935 reports `monthly_ai_pool_update_needed`, `monthly_ai_pool_update_blocked`, or `monthly_ai_pool_exception`.

## Kickstart Rules

Only kickstart a read-only session daemon when the user asks for immediate start or when fixing a missed read-only observation during an active or imminent trading session:

```bash
launchctl kickstart -k gui/$(id -u)/local.qmt-roll.official-live.15w.c9-readonly-night-session
```

Do not kickstart either deleted armed label. Do not bypass the release manifest, activation receipt, Stage927/931, kill switch, read-only account/position gate, or continuous-auction submit guards. Starting the read-only launchd job is allowed; forcing an order is not.

## Fail Closed

Stop and report blockers if any of these happen:

- wrong live profile or old capital path is being used;
- `ctp_live.local.env` or CTP runtime guard is ambiguous for live account checks;
- Stage934 reports launchd not loaded or installed arguments do not match repo;
- Stage935 cannot resolve the expected monthly eval date;
- Stage182 current or refreshed pool fails safety validation;
- Stage930 is absent during an execution session;
- Stage927/931 blocks real submit;
- broker/account/position state is stale, missing, divergent, or unknown.

## Reporting Back

Report in Chinese:

- which labels were installed/reloaded;
- Stage934 health status and blockers/warnings;
- latest Stage935 status, expected eval date, current Stage182 eval date, and Top9 products when available;
- whether any order/cancel API was called;
- overfitting and continued-value judgments.

If code, plists, or skill files changed, record a stage file under `research/lines/futures_trend_stage819_intraday_rules/stages/`.
