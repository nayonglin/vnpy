# Stage123：C9/15w 自动化流程与代码整体 review

- 时间：2026-06-23 12:12 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 类型：实盘自动化代码审查，不改策略参数，不回测，不连接真实下单 API
- 当前实盘版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 当前资金口径：150,000

## 调研与判断结论

- 已按仓库 SOP 读取 `work-type.txt`、`research/registry.md`、`skills/futures-live-execution-sop/SKILL.md`、当前 live config、Stage929/930/934/935、Stage904/905/931、launchd plists 与 startup skill。
- 参考外部资料：Apple launchd 文档确认 `StartCalendarInterval`/`ProgramArguments` 是当前 LaunchAgent 合理接法；vn.py 官方 README 与 FIA automated trading risk controls 白皮书均支持本地 pre-trade controls、kill switch、订单/撤单/活动订单限制的方向。
- 判断：当前自动化主方向正确，Stage929/930 已接入 Stage935 AI 池预检查，Stage930 会话守护和 Stage904/905/931 分层 fail-closed 结构合理；但仍存在若干可导致“看似健康但不会自动下单”或“月更边界误判”的问题。

## 主要发现

1. P1：Stage935 月度 AI 池更新存在 stale calendar 自举问题。
   - `_known_trading_dates()` 和 `_expected_monthly_eval_date()` 只依赖本地 `ALL_FUTURES_MAPPING_PATH`。
   - 模拟 `--as-of 2026-07-01T17:00:00` 与 `--as-of 2026-07-06T17:00:00` 时，如果本地 mapping 仍停在 `2026-06-22`，Stage935 仍返回 `monthly_ai_pool_already_current`，`expected_eval_date=2026-05-29`，不会触发 Stage173。
   - 风险：跨月后如果 mapping 本身 stale，月更任务可能不知道需要先更新 mapping，进而继续使用旧 AI 池。
   - 建议：当 `known_trading_date_max < wall_clock_cutoff_date` 且差距足以跨过完整月边界时，必须先强制 Stage173 或 fail-closed，不能返回 already_current。

2. P1：Stage935 没有 singleton lock。
   - Stage929、Stage930 startup、18:20 launchd 和人工命令都可能触发 Stage935。
   - run 模式会调用 Stage173/183/182 并写固定 live AI 池文件；并发执行会有产物互相覆盖或 latest summary 混乱的风险。
   - 建议：增加 Stage935 lock file + `fcntl.flock`；preflight 调用可等待或 fail-closed。

3. P1/P2：Stage934 健康状态没有暴露“真实提交闸门是否 armed”。
   - 当前 Stage934 显示 `healthy_stage930_live_real_daemon_running`，但最新 Stage927 是 `real_submit_arming_blocked_fail_closed`、`real_submit_permitted=0`。
   - 阻断包括 `broker_shadow_reconcile_not_aligned`、`controller_not_live_real_clean_ready`、`fail_closed_incident_still_open`。
   - 风险：用户看到健康，但如果马上出现新开仓信号，Stage930 会因 `real_submit_permitted=0` 在 Stage931 前跳过真实提交。
   - 建议：Stage934 增加 execution readiness 分层状态，例如 `daemon_healthy_but_submit_blocked`，并把 Stage927/Stage931 blocker 写入邮件和健康报告。

4. P2：Stage934 未强制校验 Stage930 的 `ai_pool_preflight`。
   - startup skill 已要求健康检查确认 `ai_pool_preflight.automation_status in {monthly_ai_pool_already_current, monthly_ai_pool_updated}`。
   - 但 Stage934 目前只返回 latest Stage930 的 `latest_cycle` 等字段，没有把 `ai_pool_preflight` 纳入 blockers。
   - 建议：Stage934 读取 latest Stage930 summary 的 `ai_pool_preflight`，缺失或非通过时至少 warning，部署后新 summary 缺失时 blocker。

5. P2：Stage935 和 Stage929 的逻辑失败没有可靠转成进程非零退出码。
   - Stage935 捕获异常后写 `monthly_ai_pool_exception`，但 main 未 `sys.exit(2)`。
   - Stage929 设置 `wrapper_exit_code=2` 后仍只打印 JSON，不 `sys.exit(exit_code)`。
   - 风险：launchd 或系统层监控看到退出码 0，但业务逻辑实际 fail-closed。
   - 建议：业务阻断/异常先写报告和邮件，再返回非零退出码。

6. P2/P3：Stage931 止损平仓 final reprice 失败时会保留 Stage905 保护价继续走最终检查。
   - Stage905 已用 fresh tick 生成保护价，Stage931 也会尝试 final reprice。
   - 但如果 Stage931 临发单前拿不到 fresh tick，当前状态为 `skipped_no_fresh_tick_keep_stage905_price`，最终只检查订单/持仓，不把 reprice 失败变成 blocker。
   - 建议：对 `stage904_c9_intraday_close`，final fresh tick 缺失时直接 fail-closed，避免极端跳价时用旧保护价。

7. P3：Stage929 缺少手工验证禁发邮件参数。
   - Stage929 当前总会发送报告邮件，手工验证容易误发生产邮件。
   - 建议：增加 `--email-policy {always,changes,never}` 或 `--no-email`。

## 当前运行态摘要

- launchd：day/night Stage930、postclose、evening-report、monthly-ai-pool 五个 label 均 loaded。
- Stage930：当前有 1 个 day-session 进程，live-real/live-real，订单 API `0`。
- Stage935 当前真实时间 check：`monthly_ai_pool_already_current`，`resolved_target_date=2026-06-22`，`expected_eval_date=current_eval_date=2026-05-29`，订单 API `0`。
- Stage904 当前 rb 监控：broker 持仓 11 手空单，broker 成交均价能识别，0.5R 止损价为 3129；当前 blocked 是因为非连续撮合时段 tick stale，属于 fail-closed。
- Stage905 当前 rb pending open：因 broker 已有同方向 11 手仓位跳过，不会重复开仓。
- Stage927 当前：真实提交未放行，主要因为 broker/shadow 对账不一致和 2026-06-22 fail-closed incident 未关闭。

## 过拟合与继续价值

- 是否过拟合：否。本次只审执行自动化、监控和 fail-closed 语义，不调整 alpha、参数、品种池或回测样本。
- 是否仍有价值继续：是。现在的主要风险不是策略过拟合，而是执行自动化状态表达和月更边界不够硬；这些问题直接影响是否会按预期自动交易。

## 建议下一步

1. 先修 P1：Stage935 stale-calendar guard + singleton lock。
2. 再修 P1/P2：Stage934 区分 daemon health 与 submit readiness，并强制校验 Stage930 AI-pool preflight。
3. 再修 P2：Stage935/929 非零退出码。
4. 再修 P2/P3：Stage931 final reprice 缺 fresh tick 时 fail-closed。
5. 最后补 Stage929 `--email-policy never`，降低人工验证噪音。
