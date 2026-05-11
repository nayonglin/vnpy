# [OPEN] SimNow Snapshot Probe

- session_id: `simnow-snapshot-probe`
- started_at: `2026-05-11`
- owner: `GPT-5.4`
- scope: `Stage174/SimNow CTP readonly probe account/position snapshot debugging`

## Symptom

- TCP connectivity to some SimNow fronts is available.
- `vnpy_ctp` readonly probe reaches `connected_or_attempted_readonly`.
- No usable `account` / `position` snapshot is emitted.

## Expected

- Readonly probe should receive at least one broker/account related callback or a clear login/auth failure reason.

## Current Status

- hypotheses_defined: done
- instrumentation_added: done
- runtime_evidence_collected: done
- root_cause_confirmed: partial
- fix_applied: partial
- user_confirmed: pending

## Hypotheses

- H1: `CtpGateway` 没有真正进入登录后阶段，因此 account/position 回调不会出现。
  - 结论：部分否定。打到正确前置后，能看到 `交易服务器连接成功 / 授权验证成功 / 行情登录成功`，说明确实进入了更深阶段。
- H2: 登录失败信息存在，但被现有 probe 和运行方式掩盖了。
  - 结论：确认。修正前置覆盖问题后，明确拿到 `交易服务器登录失败，代码：140`。
- H3: 只是等待时间不够。
  - 结论：否定。`70s` 下仍然无 account/position，而且出现了明确登录失败原因。
- H4: 运行环境把目标前置覆盖掉了，导致一直没真正验证 `trading` 前置。
  - 结论：确认。`run_ctp_stage177_simnow_readonly_probe.sh` 会先 `source ctp_simnow.local.env`，修复前会把外部传入的 `SIMNOW_FRONT=trading` 覆盖回 `7x24`。

## Evidence

- pre-fix 证据：
  - Debug log 显示 `td_address=40001 / md_address=40011`，即使外部传入 `SIMNOW_FRONT=trading`。
  - 仅有 `连接登录 -> CTP` 一条日志，无 account/position。
- post-fix 证据：
  - Debug log 显示 `td_address=30001 / md_address=30011`，前置切换已生效。
  - `CTP` 日志明确给出：`交易服务器登录失败，代码：140，信息：首次登录必须修改密码`。

## Root Cause

- 本地根因：
  - `Stage177` wrapper 会覆盖调用方传入的 `SIMNOW_FRONT/CTP_TD_ADDRESS/CTP_MD_ADDRESS`，导致前置切换失效。
- 外部阻塞：
  - 当真正打到 `trading` 前置后，SimNow 账号被柜台拒绝，原因是首次登录必须修改密码。

## Local Fix Applied

- 已修复 `Stage177` wrapper 的环境变量优先级问题。
- 已给 `Stage174` probe 添加运行时插桩和日志归因能力，能把 `connection_target` 和 `log_analysis` 结构化输出到 summary。

## Remaining External Action

- 需要在 SimNow 侧先完成首次改密，之后再重跑 readonly probe，才能继续验证 account/position 快照是否恢复。

## Notes

- During early debugging, business logic changes are prohibited.
- First code change after this file must be instrumentation only.
