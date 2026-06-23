# Stage121 月度 AI 池自动化与启动 Skill 固化

## 基本信息

- 时间：2026-06-23 11:58 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 当前实盘版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 当前资金口径：15w
- 是否重要突破版本：否。属于执行自动化与 SOP 固化，不是 alpha 或策略参数突破。

## 调研与判断结论

- 外部调研：核对 Apple 官方 launchd 文档，per-user 后台任务应使用 LaunchAgent；任务命令放在 `ProgramArguments`，定时触发放在 `StartCalendarInterval`，日志用 `StandardOutPath` / `StandardErrorPath`。结论：继续沿用 macOS launchd 是合适方案，不另起 cron 或 Codex heartbeat。
- GitHub/代码调研：当前仓库已有 Stage929 定时报告、Stage930 日夜盘 session daemon、Stage934 健康检查和 Stage182/183 月度 AI 池链路；缺口是没有把 Stage182 月更刷新放进 launchd，也没有 repo-local skill 让后续 agent 标准化执行“启动自动化”。
- 本次判断：月度 AI 池应自动化，但不能每天重训或改变池子；采用“每日 18:20 触发、脚本先判断完整月 eval_date、已最新则 skip”的设计，兼顾月更设计和低扰动。

## 本次版本改动

新增：

- `examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py`
  - 新增 Stage935 月度 AI 池包装器。
  - 先通过 Stage922 口径解析最新完成交易日，再计算 Stage182 应使用的最新完整月 `eval_date`。
  - 当前池子已最新且安全校验通过时只写报告，不跑 Stage173/183/182。
  - 池子落后时按顺序执行 Stage173 数据补齐、Stage183 source refresh、Stage182 live inference。
  - 校验 Stage182 safety flags、combined eligibility 路径、Top9 行数、`source_max_date >= eval_date`。
  - 邮件策略默认 `changes`：只有更新、阻断或 check 发现需要更新时才发；日常已最新 skip 不发，避免手机邮箱被每日无效邮件打扰。
- `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.monthly-ai-pool.plist`
  - 每天 18:20 触发 Stage935。
  - 触发命令：`.py311/bin/python ...run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py --mode run --email-policy changes`
- `skills/futures-live-automation-startup/SKILL.md`
  - 固化“启动自动化/检查自动化”标准流程。
  - 覆盖 day/night Stage930、Stage929 两封定时报告、Stage935 月度 AI 池、Stage934 健康检查、kickstart 边界和 fail-closed 条件。

修改：

- `examples/portfolio_backtesting/run_qmt_roll_stage934_official_live_automation_health_check.py`
  - 健康检查新增月度 AI 池 launchd label 检查。
  - 新增 latest Stage935 summary 摘要，包括 `automation_status`、`expected_eval_date`、`current_eval_date`、`order_api_called_count` 和邮件状态。
  - `health_status` 现在要求月度 AI 池 LaunchAgent 也已加载且 repo/installed plist 参数一致。

删除：

- 无。

## 自动化安装结果

- 已安装并加载 `~/Library/LaunchAgents/local.qmt-roll.official-live.15w.monthly-ai-pool.plist`。
- `launchctl print gui/501/local.qmt-roll.official-live.15w.monthly-ai-pool` 显示：
  - state：`not running`
  - runs：`0`
  - schedule：18:20
  - program：`.py311/bin/python`
  - arguments 指向 Stage935。
- `launchctl list | rg 'qmt-roll.official-live.15w'` 显示五个 label 已存在：
  - day-session
  - night-session
  - postclose
  - evening-report
  - monthly-ai-pool

## 验证结果

- `py_compile`：
  - Stage934 通过。
  - Stage935 通过。
- `plutil -lint`：
  - monthly-ai-pool plist 通过。
- Stage935 check：
  - `automation_status=monthly_ai_pool_already_current`
  - `resolved_target_date=2026-06-22`
  - `expected_eval_date=2026-05-29`
  - `current_eval_date=2026-05-29`
  - Top9：`SA.CZCE, si.GFEX, FG.CZCE, MA.CZCE, OI.CZCE, jm.DCE, AP.CZCE, rb.SHFE, fu.SHFE`
  - `order_api_called_count=0`
  - `cancel_order_api_called_count=0`
  - `email_status=skipped_by_policy`
- Stage934 health：
  - `health_status=healthy_stage930_live_real_daemon_running`
  - blockers：无
  - warnings：无
  - Stage930 进程数：1
  - 月度 AI 池 launchd：loaded，repo/installed 参数一致
  - latest Stage935：`monthly_ai_pool_already_current`

## 回测记录

- 本阶段不是回测。
- 新增回测结果：无。
- 修改回测结果：无。
- 删除回测结果：无。
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 风险与边界

- Stage935 不触发任何 broker order API。
- Stage935 不改变 AI 排序逻辑，不使用 `--allow-incomplete-month`。
- 日常 18:20 触发时，如果 Stage182 已覆盖最新完整月，只会 skip。
- 自动化启动成功不等于强行下单；真实开仓仍必须通过 Stage927/931、只读账户/持仓、reconcile、kill switch 和连续竞价时间保护。
- 当前 Stage930 仍在运行，订单 API 为 0；如账户因为人工 rb 持仓与 shadow 不一致，实盘开新仓仍会按既有闸门 fail-closed，避免重复或错误报单。

## 反思

- 运行前过拟合反思：否。本次只做执行自动化，不改变策略参数、AI模型、品种筛选逻辑或回测样本。
- 运行前继续价值反思：是。月度 AI 池人工刷新会破坏原设计，启动流程靠口头记忆也会导致不同 agent 执行不一致。
- 运行后过拟合反思：否。Stage935 只按完整月份判断是否刷新，不根据交易输赢反向挑月份或品种。
- 运行后继续价值反思：是。后续应继续把“能自动启动、能 fail-closed、能被邮件/健康检查看懂”作为实盘工程主线，而不是继续改策略小参数。

## 后续规划

- 明天或今晚 18:20 后检查 Stage935 launchd 首次自然触发日志。
- 若下月第一个可用交易日后 Stage935 自动更新成功，复核 Stage182 `eval_date`、Top9、Stage929/930 是否读取新池。
- 如未来其他 agent 接手，只需先读 `skills/futures-live-automation-startup/SKILL.md` 并执行 Stage934 验收。
