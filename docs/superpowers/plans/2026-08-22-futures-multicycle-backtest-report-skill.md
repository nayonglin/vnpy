# Futures Multicycle Backtest Report Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one repository Skill that standardizes official-baseline multicycle backtest reports and explicitly requires January and June independent starts for every 1/2/3-year duration.

**Architecture:** The deliverable is a single instruction file at `skills/futures-multicycle-backtest-report/SKILL.md`; it contains a positive experiment and output contract rather than executable code. Behavioral verification compares an independent agent's response to the same realistic request before and after loading the Skill.

**Tech Stack:** Markdown Skill frontmatter, Git, bundled Skill validator, independent agent behavioral review.

**Spec:** `docs/superpowers/specs/2026-08-22-futures-multicycle-backtest-report-skill-design.md`

## Global Constraints

- Only the Skill is added as the runtime capability; no renderer, validator, backtest engine, strategy parameter, formal material, production file, CTP path, or order path is added or modified.
- Every 1/2/3-year duration requires all eligible January 1 and June 1 independent cold starts and at least one complete start from each month.
- Full-period or one duration's advantage cannot override failures from another duration, January starts, or June starts.
- Integration is a non-force fast-forward push to `origin/master` without a PR.

---

### Task 1: Capture the no-Skill baseline failure

**Files:**
- Read: `docs/superpowers/specs/2026-08-22-futures-multicycle-backtest-report-skill-design.md`
- Create: none

**Interfaces:**
- Consumes: realistic prompt below, without the new Skill.
- Produces: verbatim baseline response and a checklist of omitted invariants in the current task commentary.

- [ ] **Step 1: Run the baseline scenario with an independent agent**

Use this exact prompt without attaching or describing the new Skill:

```text
请为一个准备与正式版比较的 vn.py 期货策略候选设计多周期稳健性回测报告。需要全周期、一年、两年、三年和资金曲线。时间有限，请直接给出你会采用的窗口、汇总和图片格式；不要执行回测或修改文件。
```

- [ ] **Step 2: Score the baseline**

Record whether it explicitly requires all five items:

```text
1. 1/2/3年每个周期均枚举全部可完整结束的1月1日起点。
2. 1/2/3年每个周期均枚举全部可完整结束的6月1日起点。
3. 每个窗口独立冷启动，不从完整曲线切片。
4. 周期汇总分别给combined、January、June。
5. 最终按固定顺序展示全周期、1Y、2Y、3Y、aggregate五张图。
```

Expected RED evidence: at least one item is absent or treated as optional. If all five are already explicit, stop and report that the proposed Skill adds no demonstrated behavioral value.

### Task 2: Write the minimal Skill

**Files:**
- Create: `skills/futures-multicycle-backtest-report/SKILL.md`

**Interfaces:**
- Consumes: design spec and exact omissions observed in Task 1.
- Produces: discoverable Skill `futures-multicycle-backtest-report`.

- [ ] **Step 1: Add frontmatter and trigger boundary**

Use this frontmatter:

```yaml
---
name: futures-multicycle-backtest-report
description: Use when a vn.py futures strategy candidate needs multicycle or multi-start robustness testing, official-baseline comparison, 1/2/3-year equity curves, semiannual starts, or a promotion audit.
---
```

- [ ] **Step 2: Add the positive experiment contract**

The Skill body must define a valid run as:

```text
- one full-period official/candidate independent comparison;
- rolling 1Y, 2Y, and 3Y independent runs;
- within every duration, every eligible January 1 start and every eligible June 1 start;
- at least one complete January and one complete June window per duration;
- near-complete terminal windows marked as observation-only;
- A as the verified official baseline and candidate arms named explicitly;
- frozen data end, costs, arms, gates, and window schedule before results.
```

State that a report with insufficient January or June coverage is an insufficient-coverage result, not a completed multicycle report. Require `version-ab-experiment` when the request concerns a valuable candidate or formal promotion.

- [ ] **Step 3: Add the positive report recipe**

Require this result order:

```text
1. promotion verdict;
2. official baseline and candidate identities;
3. full-period metric comparison;
4. 1Y/2Y/3Y table with combined, January, and June breakdowns;
5. weakest return, drawdown, Sharpe, cost, and survival windows;
6. five images in order: full-period, 1Y, 2Y, 3Y, aggregate;
7. CSV/decision/stage links, reviewer/tests, safety boundary;
8. before/after overfitting and continued-value judgments.
```

For each 1Y/2Y/3Y image, require chronological `(year, January)` then `(year, June)` pairing, accurate start date, consistent official/candidate colors and units, and `*` explanation for observation-only windows.

- [ ] **Step 4: Add common mistakes based on the RED evidence**

Include only demonstrated omissions plus these structural distinctions: independent engine versus curve slice, combined versus January/June breakdown, complete versus observation-only. Keep the Skill concise and self-contained.

### Task 3: Validate Skill behavior and structure

**Files:**
- Read: `skills/futures-multicycle-backtest-report/SKILL.md`
- Modify: `skills/futures-multicycle-backtest-report/SKILL.md` only if validation exposes ambiguity.

**Interfaces:**
- Consumes: completed Skill and the exact Task 1 scenario.
- Produces: validator pass and GREEN behavioral evidence covering all five baseline checklist items.

- [ ] **Step 1: Run structural validation**

Run:

```bash
/Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/futures-multicycle-backtest-report
```

Expected: validator reports success with no malformed frontmatter or scaffold placeholders.

- [ ] **Step 2: Run the same scenario with the Skill**

Give an independent agent the exact Task 1 prompt and instruct it to use `skills/futures-multicycle-backtest-report/SKILL.md`. Expected: all five checklist items are explicit and mandatory.

- [ ] **Step 3: Check concise discovery and formatting**

Run:

```bash
wc -w skills/futures-multicycle-backtest-report/SKILL.md
rg -n "January|June|1月|6月|1Y|2Y|3Y|full-period|independent" skills/futures-multicycle-backtest-report/SKILL.md
git diff --check
```

Expected: under 500 words where practical, all core discovery terms present, and no whitespace errors.

### Task 4: Independent review, commit, and direct master push

**Files:**
- Review: `docs/superpowers/specs/2026-08-22-futures-multicycle-backtest-report-skill-design.md`
- Review: `docs/superpowers/plans/2026-08-22-futures-multicycle-backtest-report-skill.md`
- Review: `skills/futures-multicycle-backtest-report/SKILL.md`

**Interfaces:**
- Consumes: verified Skill and evidence from Tasks 1-3.
- Produces: reviewed Git commits and exact remote `origin/master` readback.

- [ ] **Step 1: Request independent review**

Ask a reviewer to check trigger precision, January/June mandatory coverage, independent cold-start semantics, fixed five-image/report order, authorization boundaries, and whether the Skill adds unsupported executable behavior. Resolve all P0/P1 findings.

- [ ] **Step 2: Verify the exact diff**

Run:

```bash
git status --short
git diff --check
git diff --name-only origin/master...HEAD
```

Expected tracked scope: the design doc, this plan, and `skills/futures-multicycle-backtest-report/SKILL.md` only.

- [ ] **Step 3: Commit the Skill**

Run:

```bash
git add skills/futures-multicycle-backtest-report/SKILL.md
git commit -m "docs: add futures multicycle report skill"
```

- [ ] **Step 4: Reconcile latest remote master without force**

Run:

```bash
git fetch origin master
git rebase origin/master
/Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/futures-multicycle-backtest-report
git diff --check origin/master...HEAD
```

Expected: clean rebase and validation pass. If rebase conflicts, stop and resolve only files in this plan's scope before revalidating.

- [ ] **Step 5: Push and read back**

Run:

```bash
git push origin HEAD:master
git ls-remote origin refs/heads/master
git rev-parse HEAD
```

Expected: remote master SHA exactly equals local HEAD; no force and no PR.
