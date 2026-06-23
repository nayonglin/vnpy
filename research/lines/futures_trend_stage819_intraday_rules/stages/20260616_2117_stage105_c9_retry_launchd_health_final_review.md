# Stage105 C9/15w retry-open 与自动化守护最终复审修复

## 基本信息

- 记录时间：2026-06-16 21:17 CST
- 所属研究线：`futures_trend_stage819_intraday_rules`
- 当前官方实盘版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 是否重要突破版本：是，执行安全与守护状态从“代码闸门已修”推进到“独立复审无 P0/P1/P2，并有机器可读健康检查”
- 策略/参数是否变化：否，不改 C9 信号、`0.5R`、重试次数、品种、方向、资金口径或回测样本

## 调研与判断

- 外部调研结论：独立 agent 对照 vn.py `Status`/`MainEngine.send_order` 行为和 Apple launchd `ProgramArguments` 用法复审；结论是 unknown/active order fail-closed、send_order 空返回停止处理、LaunchAgent 直接 Python 入口均符合工程约束。
- 本地判断：本阶段不是 alpha 优化，不存在通过样本反推策略参数的问题；核心是实盘执行语义和守护进程可观测性。
- 继续价值判断：有价值。全自动交易的风险不只在信号，还在“没发单却消耗 retry 机会”“launchd 看似安装但实际没跑”“旧错误日志误导判断”等执行层细节。

## 本次改动

### 新增

- `examples/portfolio_backtesting/run_qmt_roll_stage934_official_live_automation_health_check.py`
  - 只读检查 day/night launchd、postclose/evening report launchd、`screen` 兜底、Stage930 最新 summary、Stage930 进程、订单 API 计数。
  - 输出 latest summary/report，避免以后只靠人工看零散日志判断自动化是否运行。

### 修改

- `examples/portfolio_backtesting/run_qmt_roll_stage904_official_live_c9_intraday_monitor.py`
  - retry-open 是否已尝试，改为只认真正进入执行链路的 ledger event：`send_order_called`、`submitted_to_ctp`、成交/拒单、post-send unknown、残留 active/unknown、撤单等。
  - `final_pre_send_gate_blocked_after_reserve` 不再消耗 C9 retry once 机会。
- `examples/portfolio_backtesting/run_qmt_roll_stage905_official_live_executor_dry_run.py`
  - 新增 unknown/blank order status 检查；只要只读订单快照出现未知状态，就提前阻断意图，不让它走到 Stage931 才发现。
- `examples/portfolio_backtesting/qmt_roll_official_live_execution_ledger.py`
  - open intent 的 `final_pre_send_gate_blocked_after_reserve` 从永久 duplicate blocker 改为短暂 throttle 后重新评估。
  - post-send unknown / cancel 后 residual active/unknown 仍作为重复开仓/平仓阻断。
- `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-day-session.plist`
- `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-night-session.plist`
- `/Users/bytedance/Library/LaunchAgents/local.qmt-roll.official-live.15w.c9-day-session.plist`
- `/Users/bytedance/Library/LaunchAgents/local.qmt-roll.official-live.15w.c9-night-session.plist`
  - day/night session daemon 从 shell supervisor 入口改为 direct Python：`.py311/bin/python run_qmt_roll_stage930_official_live_c9_session_daemon.py`
  - 解决夜盘 launchd 旧 shell supervisor 触发 `Operation not permitted / exit 126` 的部署风险。

### 删除

- 无策略逻辑删除。
- 临时 direct-Python LaunchAgent 探针 `local.qmt-roll.stage930.direct-python-probe.plist` 已卸载并删除。

## 验证结果

- `py_compile` 通过：
  - `qmt_roll_official_live_execution_ledger.py`
  - `run_qmt_roll_stage904_official_live_c9_intraday_monitor.py`
  - `run_qmt_roll_stage905_official_live_executor_dry_run.py`
  - `run_qmt_roll_stage927_official_live_real_submit_arming_gate.py`
  - `run_qmt_roll_stage930_official_live_c9_session_daemon.py`
  - `run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`
  - `run_qmt_roll_stage934_official_live_automation_health_check.py`
- `git diff --check` 通过。
- 合成测试通过：
  - `final_pre_send_gate_blocked_after_reserve` 不被 Stage904 算作 retry 已尝试。
  - ledger 对 open final-pre-send gate 只 throttle，超过窗口允许重新评估。
  - `send_order_called` 仍永久阻断重复 open，并被 Stage904 算作 retry 已尝试。
  - Stage905 active order 计数与 unknown/blank order status 计数正常。
- launchd：
  - day/night repo plist 与安装 plist 已一致，`plutil -lint` 通过。
  - direct-Python 临时 dry-run LaunchAgent 能启动到 Stage930；因当前 screen 守护持锁，返回 `daemon_blocked_already_running`，说明 direct-Python 入口可由 launchd 执行。
- 运行态：
  - 当前 `screen` 会话 `qmt_c9_night_20260616` 存活。
  - Stage930 当前 `daemon_running`，`mode=live-real`，`submit_mode=live-real`。
  - 2026-06-16 21:16:56 健康检查：`healthy_stage930_live_real_daemon_running`，`blockers=[]`，`warnings=[]`，`cycle_count=7`，`order_api_called_count=0`。
  - Stage931 当前跳过原因：`ready_count=0;real_submit_permitted=0;controller_status=phase_d_controller_live_real_blocked;stage905_executor_status=executor_no_intents`，即今晚当前没有 ready 交易意图，不下单。
- 21:05 evening report launchd 已运行成功，`last exit code=0`，stderr 为空。

## 独立复审

- 新独立 agent `Bacon` 复审结论：未发现 P0/P1/P2 实质问题。
- 剩余 P3：
  - 当前夜盘真正运行的是 `screen` 兜底会话，不是 launchd 自然触发。
  - day/night launchd 已加载且 direct-Python 配置正确，但因为 20:55 已过且当前 Stage930 持锁，今晚无法再证明自然触发长跑；后续需要等下一次自然触发，或在停掉 screen 后做一次非下单 kickstart 验证。
  - 旧 `qmt_roll_stage930_launchd_c9_night_session.err.log` 里仍有 shell supervisor 的 `Operation not permitted` 残留，不能用旧日志误判当前 direct-Python plist。

## 回测/交易指标

- 本阶段不跑新回测。
- 期末权益：未变更
- 总收益：未变更
- 最大回撤：未变更
- Sharpe：未变更
- 总滑点：未变更
- 总交易次数：未变更
- 胜率：未变更
- 实盘订单 API：当前 Stage930 运行期间 `order_api_called_count=0`

## 结论

- C9/15w retry-open 自动化的“没发单却消耗一次 retry”的 P2 已修复。
- day/night launchd 的 shell supervisor 权限 P2 已用 direct-Python 入口修复并重载；直接 Python 启动路径已验证能进入 Stage930。
- 当前夜盘由 `screen` 临时兜底守护，健康检查为 healthy；但长期全自动仍需下一次 launchd 自然触发或停掉 screen 后做一次非下单 kickstart 证明。
- 现在没有交易信号 ready intent，所以没有真实下单；所有订单 API 计数为 `0`。

## 后续 TODO

- 等下一次日盘/夜盘 launchd 自然触发，确认 direct-Python session daemon 不再出现 `exit 126`。
- 把 Stage934 健康检查纳入关键邮件或每日巡检摘要，避免“launchd 已加载但守护没跑”的误判。
- 如果要彻底消除 Desktop/TCC 运行风险，后续应规划把 live runtime 迁到非 Desktop 路径；当前仓库体积约 `53G`，迁移前需要清理或使用轻量部署目录。

## 收尾反思

- 是否过拟合：否。本阶段完全是执行安全、订单状态语义、守护进程部署和可观测性修复，没有改策略参数或用行情样本反推规则。
- 是否值得继续：是，但继续方向应是自动化运行态验证、健康检查邮件化和部署目录治理，不是继续调整 C9 alpha。
