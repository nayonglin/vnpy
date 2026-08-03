# C9/15w 收盘后 AI 池与报告串行编排设计

## 背景

2026-08-03 的生产链路按三个独立 `launchd` 日历任务运行：

- `16:35`：`postclose-precompute`
- `16:55`：`postclose-report`
- `18:20`：`monthly-ai-pool`

当天是月初首个可用交易日。`postclose-precompute` 已把行情和 shadow 刷新到
`2026-08-03`，但正式 AI 池仍停留在 `2026-06-30`，缺少新月份要求的
`2026-07-31` 评估日。日数据回执因此未能签发，随后 `postclose-report` 又因旧回执
被拒绝。两次失败邮件都成功送达，但第二封只是第一处根因的下游连锁告警。

问题本质不是 SMTP、磁盘或策略参数，而是应用层依赖被拆成了互不等待的固定时钟。

## 目标

1. 将收盘后数据更新、月度 AI 池检查、shadow、日数据回执和收盘报告变成单一串行
   状态机。
2. AI 池只在确有月度缺口时更新；日常运行只做幂等新鲜度检查。
3. 上游失败时不启动依赖它的下游步骤，不产生重复根因邮件。
4. 保持所有订单 API 计数为零，不改变策略、品种、风险参数或实盘会话提交逻辑。
5. 保持现有七个 production launchd label，避免扩大 Stage948 激活和回滚表面。
6. 本改动作为 `cc5ddf64f80711c0e3324b84bbbd3758c6581c26` 之后的独立版本发布，
   不改变正在资格认证的 Stage174 候选身份。

## 非目标

- 不修改 Stage182/183 的 AI 排名、TopN、训练窗口或月末口径。
- 不把月度 AI 池改成每日训练。
- 不允许失败后绕过日数据回执继续生成可执行报告。
- 不在本改动中重启、停止或强杀任何活动 production job 或 warm executor。
- 不改变 CTP runtime、env、下单授权或 0.5R 止损/一次重试逻辑。

## 方案比较

### 方案 A：单一收盘后协调器（采用）

由现有 `postclose-precompute` label 在 `16:35` 启动一次协调器。协调器按依赖顺序调用
现有 worker，生成不可歧义的 pipeline receipt。`postclose-report` label 改为只读 watchdog；
`monthly-ai-pool` label 保留为 `18:20` 的条件式兜底重试。

优点是顺序由应用状态保证，不依赖任务耗时或机器唤醒时刻；失败归因和邮件去重都能在
同一状态机中完成。代价是需要增加 pipeline receipt 和 coordinator 级测试。

### 方案 B：只调整三个固定时间（拒绝）

例如把 AI 池提前到 `16:35`，预计算改为 `17:00`，报告改为 `17:20`。实现简单，但数据
更新时间或 AI 推理耗时一旦超过预留间隔仍会复现竞态；机器睡眠恢复也可能把多个任务
同时触发。

### 方案 C：保持顺序，只屏蔽重复邮件（拒绝）

只能减少噪音，无法修复旧 AI 池导致日回执无法签发的问题。

## 目标架构

### 1. Post-close coordinator

协调器拥有当天唯一的 `pipeline_run_id`，并按以下阶段运行：

1. `resolve-target`：解析最新已完成交易日并验证交易日历证据。
2. `refresh-market-data`：更新主力合约映射、日线和生产数据库。
3. `check-monthly-ai-pool`：计算本次必须覆盖的上一完整月末 eval date。
4. `refresh-monthly-ai-pool`：仅当正式池缺少该 eval date 时运行 Stage183/182/935。
5. `refresh-shadow`：使用最终 AI 池生成同一 target date 的 Stage901 cohort。
6. `issue-daily-data-receipt`：校验数据、数据库、AI 池和 Stage901 cohort 后原子签发回执。
7. `generate-postclose-report`：只有回执有效时才运行 Stage929 并发送正式收盘报告。
8. `complete`：写入 terminal pipeline receipt 和 API 零计数。

每个阶段必须记录 `started_at`、`finished_at`、`status`、`blocker`、输入摘要、产物路径和
订单 API 计数。协调器只允许阶段向前推进，不允许在同一 run 中跳过失败阶段。

### 2. Pipeline receipt

新增私有状态文件：

`production-live/postclose-pipeline/latest.json`

核心字段：

- `schema_version`
- `pipeline_run_id`
- `schedule_date`
- `target_date`
- `source_commit`
- `manifest_sha256`
- `status`: `running | succeeded | failed`
- `current_stage`
- `stages`
- `daily_data_receipt_sha256`
- `report_summary_sha256`
- `root_blocker`
- `email_disposition`
- `send_order_api_called_count`
- `cancel_order_api_called_count`
- `order_api_called_count`

写入采用现有私有状态的 owner/mode、临时文件、`fsync`、原子替换和读回校验模式。任何
source/manifest/run identity 不一致都 fail-closed。

### 3. 七个 launchd label 的职责

- `postclose-precompute`：仍在 `16:35` 触发，但执行完整 coordinator。
- `postclose-report`：仍在 `16:55` 触发，只读检查 pipeline receipt：
  - `succeeded`：不重复运行、不重复发信；
  - `running`：记录 `deferred_pipeline_running`，不发失败邮件；
  - `failed`：确认根因邮件已处理后退出，不产生下游重复邮件；
  - receipt 缺失或身份不匹配：发一封 watchdog 根因邮件并 fail-closed。
- `monthly-ai-pool`：仍在 `18:20` 触发，作为条件式 retry/watchdog：
  - 当日 pipeline 已成功：退出 `already_satisfied`；
  - 根因是 AI 池更新失败且重试预算未使用：只重试一次完整 coordinator；
  - 其他根因：不重试、不改状态，只记录。
- 其余四个 label 的职责和时间不变。

固定保留七个 label 是为了让 Stage948 prepare/activate、manifest、receipt、health check 和
rollback 仍使用同一受控表面；业务顺序由 coordinator receipt 保证，而不是由日历分钟差保证。

## 邮件语义

### 成功路径

- AI 池无变化：不发 AI 池邮件，只发一封最终收盘报告。
- AI 池完成更新：先发一封“AI池已更新”信息邮件，最终回执有效后再发收盘报告。
- 邮件元数据必须包含 `pipeline_run_id`、`target_date`、阶段和 API 零计数。

### 失败路径

- 只由发现首个 terminal root blocker 的 coordinator 发一封失败邮件。
- 下游阶段写为 `skipped_upstream_failed`，不得再次发送失败邮件。
- watchdog 只有在 receipt 缺失、损坏或邮件 disposition 不完整时才补发；补发使用相同
  `pipeline_run_id + root_blocker` 去重键。
- 邮件发送失败不能改写业务根因；receipt 同时记录业务失败和 `email_status=send_failed`。

## 锁、重试和并发

- coordinator 使用私有、owner-only 的非阻塞锁，同一 schedule date 只允许一个 active run。
- `16:55` watchdog 不抢锁、不 kickstart coordinator。
- `18:20` 兜底最多重试一次，并要求原 run 已 terminal failed、根因为 AI 池更新链路、无活动
  coordinator PID。
- 重试创建新的 `pipeline_run_id`，同时引用 `retry_of`；不得覆盖原失败证据。
- 任何活动 production session/warm executor 的生命周期仍由原 SOP 管理，本协调器不得
  stop/kill/bootout/kickstart 它们。

## Fail-closed 条件

以下任一情况立即停止下游：

- 最新完整交易日或交易日历证据不明确；
- 月度 AI 池 eval date 缺失且刷新失败；
- Stage901 identity/cohort/hash 不一致；
- daily-data receipt 无效；
- source commit、manifest 或 activation receipt 不一致；
- pipeline receipt 不完整、权限不安全或无法原子校验；
- 任一 send/cancel/order API counter 非零；
- 非预期 CTP/native 调用、handshake、SIGSEGV 或 API 访问。

## 测试设计

### 单元测试

- 正常日：AI 池 current，Stage935 不更新，单封收盘报告。
- 月初日：旧池缺 eval date，先更新 AI 池，再生成 shadow/回执/报告。
- AI 池更新失败：下游全部 `skipped_upstream_failed`，仅一封根因邮件。
- receipt 签发失败：不运行 Stage929，仅一封回执根因邮件。
- 邮件发送失败：业务 blocker 不被覆盖，audit 保留 `send_failed`。
- watchdog 对 `running/succeeded/failed/missing/corrupt` 五类 receipt 的行为。
- 18:20 retry 的资格、单次预算和 `retry_of` 身份。
- 所有路径 API counter 必须为零。

### 集成测试

- 使用临时 production-state、假的 worker 和固定时钟跑完整 coordinator。
- 验证 Stage935 更新后，Stage901 使用的新 eligibility hash 与 daily receipt 完全一致。
- 验证 launchd 三个 support job 即使被同时调用，也只有 coordinator 能执行有副作用的 worker。
- 验证七个 plist label、stable root、环境变量和 Stage948 manifest surface 不漂移。

### 生产前验证

- 静态测试和 fault matrix 全通过。
- 独立 review 要求 `P0=0/P1=0`。
- 从新 candidate 重新构建 qualification 和 release manifest；不得复用 Stage174 的旧资格证据。
- 仅通过 Stage948 prepare/activate 发布；活动 production PID 存在时不得切换。
- 激活后核验 stable HEAD、manifest、activation receipt、七个 labels、pipeline receipt 和零 API。

## 发布顺序

1. 保持 Stage174 候选 `cc5ddf64f80711c0e3324b84bbbd3758c6581c26` 原样完成当前切换。
2. 本修复从该提交派生独立 candidate，完成实现、测试、review 和全新资格认证。
3. 等全部 production PID 自然归零后，通过 Stage948 发布本修复。
4. 首次生产验收覆盖一个正常日；月初分支用受控 fixture/plan-only 证据验证，不等待下个月才验收。

## 判断

- 过拟合：否。改动只固定数据依赖、月度口径、失败传播和邮件去重，不根据收益或信号结果调参。
- 继续价值：是。它消除月初旧 AI 池必然阻断回执的结构性竞态，并让邮件反映首个真实根因。

