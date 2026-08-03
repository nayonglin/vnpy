# Stage210 C9/15万收盘后 AI 池串行协调与失败邮件去重

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：官方实盘候选执行接线，尚未安装到 stable
- 记录时间：2026-08-03 18:29 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage174_postclose_orchestration` / `codex/stage174-postclose-orchestration`
- 阶段性质：生产执行编排与 fail-closed 修复，不是 alpha 研究
- 是否重要突破：是。消除月初 AI 池更新晚于日回执/邮件的结构性竞态，并把下游连锁失败收敛为一个根因通知。
- 是否触发A/B：否。不改策略、选品、资金、止损、重试或下单语义。

## 外部调研与判断

- 参考资料：Apple `launchd` 官方任务生命周期说明；Python 官方 `fcntl`、`os.replace` 和 `fsync` 语义；仓库内 Stage173/909/929/935/947/948 当前代码与 2026-08-03 生产失败证据。
- 调研结论：仅调整 plist 分钟不能保证依赖顺序，因为耗时、机器唤醒和月更路径都不稳定。保留七个 label 和当前时间，改由单一 receipt-driven coordinator 保证顺序，watchdog/retry 只读状态后再决定动作，更符合 `launchd` 的任务模型。
- 我的判断：本次问题的底层原因不是“邮件坏了”，而是 `16:35` 日回执在月度 AI 池仍停留 `2026-06-30` 时先执行，要求的 `2026-07-31` 截面缺失；`16:55` 报告随后消费无效回执，形成第二封下游失败邮件。正确修复点是依赖图和根因所有权，不是屏蔽邮件。

## 本次变更

- 基线提交：`cc5ddf64f80711c0e3324b84bbbd3758c6581c26`
- 实现审查提交：`0dcd4e208ce0618ac926981fb62d9c6e5cced347`
- 新增脚本：`qmt_roll_official_live_postclose_pipeline.py`，提供私有 receipt、顺序状态机、原子写、摘要校验、非阻塞锁、retry 身份和原失败 receipt 归档。
- 修改脚本：Stage947 改为 `16:35` coordinator、`16:55` receipt watchdog、`18:20` 条件式单次 retry；Stage935 新增 `updates` 邮件策略，只在 AI 池实际更新成功时发信息邮件；failure notifier 增加 pipeline 元数据但不改变 canonical dedupe 身份；release manifest 固定新模块与测试。
- 删除脚本：无。
- 新增参数：Stage935 `--email-policy updates`。
- 修改参数：生产 monthly-ai-pool worker 从 `changes` 改为 `updates`；七个 plist 的 label、weekday 和触发分钟均未改变。
- 删除参数：无。
- 固定执行顺序：行情刷新至 wall-clock cutoff → 权威 target date 重解析 → AI 池检查/按需更新 → 最终 Stage909 shadow → daily-data receipt → Stage929 收盘报告。
- 固定日程：coordinator `16:35`，watchdog `16:55`，条件式 retry `18:20`。
- 邮件语义：AI 池已是最新时只发 1 封最终报告；AI 池实际更新时先发 1 封更新成功邮件，再发 1 封最终报告；任一上游失败只由 canonical coordinator 发 1 封根因邮件，下游阶段全部 `skipped_upstream_failed`。

## 回测/归因参数

- 数据区间：不适用；未运行回测。
- 账户规模：官方实盘口径 `15w`，本次未修改。
- 成本口径：不适用。
- 样本过滤：不适用。
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` 保持不变。

## 结果

- 期末权益：不适用；未运行回测。
- 总收益：不适用；未运行回测。
- 最大回撤：不适用；未运行回测。
- Sharpe：不适用；未运行回测。
- 总滑点：不适用；未运行回测。
- 总交易次数：不适用；未运行回测。
- 胜率：不适用；未运行回测。
- 其他关键指标：最终扩大纯单元回归 `133 tests` 全部通过；独立复审最终 `P0/P1/P2/P3=0/0/0/0`；所有 coordinator/watchdog/retry receipt 与输出均要求 `send/cancel/order API=0/0/0`；测试未连接 CTP，未调用订单 API。
- 关键协议修复：按 Stage929 真实 stdout 的 `wrapper + stage903_summary` 嵌套结构校验；刷新后允许 target date 从旧映射前移，并要求 Stage935、Stage909、daily receipt、pipeline receipt、Stage929 日期完全一致。
- 重试证据：首次 AI 阶段失败才允许一次 retry；retry 开始前把原 receipt 归档为 `<pipeline_run_id>.json`，新 receipt 从创建时即绑定 `retry_of`，finalize 不得改绑。
- 发布覆盖：新运行模块与测试均进入 `DEFAULT_CRITICAL_FILES`，测试进入 `PRODUCTION_REQUIRED_TEST_SUITES`；七个 production label 与原日程保持不变。

## 输出文件

- design：`docs/superpowers/specs/2026-08-03-postclose-ai-pool-orchestration-design.md`
- plan：`docs/superpowers/plans/2026-08-03-postclose-ai-pool-orchestration.md`
- runtime receipt：生产激活后为 `~/Library/Application Support/qmt-roll-stage179/production-live/postclose-pipeline/latest.json`，父目录 `0700`、文件 `0600`。
- immutable retry evidence：生产激活并发生 retry 后为同目录 `<pipeline_run_id>.json`。
- tests：`tests/test_official_live_postclose_pipeline.py`、`tests/test_stage947_production_support_launcher.py`、`tests/test_official_live_failure_notify.py`、Stage179 release/lifecycle 测试。

## 结论

- 本阶段结论：代码候选和独立审查已通过，结构性调度与重复失败邮件问题在候选中已修复；但截至记录时仍未安装到实盘 stable。
- 未安装原因：前置 Stage174 `cc5ddf64...` 尚未完成正式双只读 qualification 和 Stage948 激活；当前 stable 仍为 `7c784eaf...`。生产 day-session PID `93628` 与 warm executor `43806/43818` 仍存活，磁盘仅约 `3.8 GiB` 可用，不能 hot-swap 或启动正式 CTP capture。
- 是否进入下一步：是，但必须严格串行。先等所有生产 PID 自然归零并让 Stage174 单独完成资格/激活；之后再次自然归零，为 Stage210 候选重新构建独立 qualification/release/activation 证据，只能通过 Stage948 prepare/activate 切换。
- 下一步：继续只读监控 PID 与磁盘；任何 SIGSEGV、handshake、source mismatch、不完整证据、P0/P1 或 API 非零均 fail-closed。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次只固定任务依赖、artifact 身份、失败传播、邮件所有权和安全门禁，没有根据收益、品种、日期或交易结果调参。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：月初旧 AI 池会稳定阻断回执并制造误导邮件，这是生产可用性问题；修复后根因和用户看到的邮件语义一致，且不扩大交易权限。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录候选已完成但受 Stage174 前置激活与自然 quiescence 阻断。
- 是否更新 `research/registry.md`：否。同一研究线未变更主策略状态。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加。只有 Stage948 正式激活成功后才作为生产里程碑写入总账。
