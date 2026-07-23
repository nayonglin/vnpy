# Stage199：production 控制面 Skill / SOP 对齐

## 基本信息

- 时间：2026-07-23 12:02 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 是否重要突破：是，属于生产执行文档与自动化控制面收口；不属于策略 alpha 突破。
- production stable：`4cff26c8597cc6b85349b75487aeec0482750996`
- 发布文档分支起点：`93d15cbb7`

## 本次目标

让 AGENTS、仓库执行 SOP、自动化启动 Skill、月度 AI 池 SOP 和全局官方影子盘 Skill 与当前 C9/15万 production-live 的真实调用链一致，消除旧 Stage372/Stage260/251、旧 launchd 标签、普通开发 checkout 和未签名 shadow 产物被误当成生产事实的风险。

## 变更摘要

1. `AGENTS.md`
   - 固化 production 事实源优先级：stable HEAD、release、qualification、activation、runtime receipt、daily receipt。
   - 固化 `2026-07-23` cold start，不回填、不追单 pre-start 理论仓位。
   - 固化 Stage948 管理的 7 个 production 标签，以及 Stage945/947 所有权。
2. `skills/futures-live-execution-sop/SKILL.md`
   - 当前研究线改为 `futures_trend_stage819_intraday_rules`。
   - 日常生产链改为 Stage947 -> Stage909 -> Stage901 -> daily receipt，交易会话改为 Stage945 -> Stage930。
   - Stage260/251 明确降级为 legacy SimNow-only 诊断。
3. `skills/futures-live-automation-startup/SKILL.md`
   - 从旧 production-readonly/Stage934 说明迁移到当前 7 个 `c9-production-live-*` 标签。
   - 安装与重载只允许 Stage948 原子流程。
   - 新增 `already_active` 幂等分支：7/7 已准确加载时直接返回，不重复 activate 或 kickstart。
4. 新增 `SOP_c9_15w_monthly_ai_pool.md`
   - 正式月更入口为 Stage947 -> Stage935。
   - AI 池变化后必须 Stage909 重算并重签 daily receipt。
   - Stage935 check 明确会写 lock/summary/report/latest 诊断产物，必须从 stable absolute path 运行，不再称为文件系统只读。
5. 全局 `futures-official-shadow`
   - 默认读取 production stable，不再默认读取普通开发 checkout。
   - exporter 审计副本写到独立 `readonly-audits`，不写 production repo/state 产物。
   - exporter 复用 Stage945 的 release/runtime receipt、qualification、exact seven-label surface、activation barrier 和 canonical daily receipt 完整验证；任一不一致 fail-closed。

## 参数与策略影响

- 新增策略参数：无。
- 修改策略参数：无。
- 删除策略参数：无。
- 资金口径：仍为 C9/15万。
- 交易价格、手数、止损、重进、委托类型：无变更。
- CTP、send、cancel、order API：均未调用。
- launchd：未安装、未重载、未 kickstart。

## 验证

- Skill validator：`3/3` 通过。
- Python：全局 exporter `py_compile` 通过。
- plist/Skill 映射：7 个标签及 `08:55/13:25、20:55、15:12、16:35、16:55、18:20、09:03/13:33/21:03` 全部一致。
- stable HEAD：仍为 `4cff26c8`，worktree clean。
- repo plist 与已安装 plist：`7/7` SHA256 一致。
- activation：`production_launchd_activated_no_ctp_connection`，loaded `7`，conflict `0`，CTP/send/cancel/order `0/0/0/0`。
- 当前旧 daily receipt 的 source commit 与 production manifest 不一致；新版 exporter 正确以 `production_authority_daily_receipt_source_commit_mismatch` fail-closed，exit `1`，未生成审计 artifact。
- `git diff --check`：通过。
- 独立 agent 首轮 review：`P0/P1/P2=0/1/2`；三项均修复。
- 独立 agent 复审：`P0/P1/P2=0/0/0`。

## 回测结果

本阶段未运行回测，不修改既有结果：

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A

## 判断

- 过拟合：否。本次只固定生产身份、调用链、回执和幂等启动语义，没有新增或调整任何 alpha 自由度。
- 是否继续有价值：是，但本阶段已收束。后续价值只在观察首个 `2026-07-23` 16:35 cohort/daily receipt 和 20:55 会话闸门；不应继续扩展文档分支或策略规则。

## 后续

1. 将本阶段文档变更提交并推送现有 release 分支。
2. 不把纯文档提交切换为新的 production stable commit；production runtime 继续使用已资格化的 `4cff26c8`。
3. 16:35 后只读核对新 receipt；若仍不匹配，保持 fail-closed，不重装 launchd。
