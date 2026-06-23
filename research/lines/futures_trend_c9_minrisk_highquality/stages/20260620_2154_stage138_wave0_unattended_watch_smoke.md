# Stage138 W0 watched inbox 无人值守 smoke

- line_id：futures_trend_c9_minrisk_highquality
- 当前模式：day
- 记录时间：2026-06-20 21:54 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：Stage137 trigger selftest -> Stage136 watched inbox monitor 的一键依赖 smoke；不做策略 alpha，不做 true engine，不做 A/B
- 是否重要突破：否；这是数据入口无人值守前的 smoke 入口
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - GitHub Actions job dependencies：https://docs.github.com/actions/using-jobs/using-jobs-in-a-workflow
  - Kubernetes liveness/readiness/startup probes：https://kubernetes.io/docs/concepts/workloads/pods/probes/
  - Kubernetes probe configuration：https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
  - Dagster sensors / run keys：https://docs.dagster.io/guides/automate/sensors
  - Dagster schedules and sensors API：https://docs.dagster.io/api/dagster/schedules-sensors
  - launchd.plist man page：https://www.manpagez.com/man/5/launchd.plist/
- 我的判断：无人值守入口应先做 dependency gate：Stage137 自测失败时不得继续扫真实 inbox；Stage136 只产出 readiness/skip 状态，不自动触发 Stage125/133。这个形态更接近 CI 的 `needs`、Kubernetes readiness probe 和 Dagster sensor skip/run request 的组合，而不是直接把监控结果当成 release。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage138_wave0_unattended_watch_smoke.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 新增机制：
  - 子进程先执行 Stage137 trigger selftest。
  - 只有 Stage137 `selftest_pass=1` 且 `stage125_command_executed_count=0`、`stage133_command_executed_count=0` 时，才执行 Stage136 默认 watched inbox monitor。
  - 解析两个子命令 stdout JSON，生成 command audit、gate status、watch history tail 和资金/状态图。

## 回测/归因参数

- 数据区间：沿用 Stage131/Stage045 官方背景曲线 2018-2026；Stage138 本身不新增交易
- 账户规模：沿用当前 C9 min-risk 线背景口径
- 成本口径：沿用 Stage131 背景统计，总滑点 `2,730,130`
- 样本过滤：无交易样本过滤；只做数据入口 smoke
- 策略/归因口径：unattended watched inbox smoke；不允许进入分钟规则，不允许 true engine

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26,017.63%`
- 最大回撤：`-45.08%`
- Sharpe：`1.633`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.09%`
- 其他关键指标：
  - decision：`stage138_unattended_watch_smoke_passed_waiting_no_real_w0_no_strategy`
  - smoke_pass：`1`
  - command_count：`2`
  - command_pass_count：`2`
  - gate_pass_count：`6/6`
  - stage137_dependency_passed：`1`
  - stage137_selftest_pass：`1`
  - stage137_case_pass_count：`5`
  - stage137_expectation_pass_count：`39/39`
  - stage137_stage125_command_executed_count：`0`
  - stage137_stage133_command_executed_count：`0`
  - stage136_monitor_ready：`1`
  - stage136_prior_snapshot_available：`1`
  - stage136_arrival_detected_now：`0`
  - stage136_stage125_candidate_count：`0`
  - stage136_candidate_ready_count：`0`
  - stage136_best_known_file_count：`0/123`
  - stage133_release_allowed_now：`0`
  - real_w0_data_delivered：`0`
  - real_stage112_intake_allowed_now：`0`
  - true_engine_allowed：`0`
  - strategy_feature_usable：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage138_wave0_unattended_watch_smoke/qmt_roll_stage138_c9_minrisk_wave0_unattended_watch_smoke_report_stage138_wave0_unattended_watch_smoke_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage138_wave0_unattended_watch_smoke/qmt_roll_stage138_c9_minrisk_wave0_unattended_watch_smoke_decision_stage138_wave0_unattended_watch_smoke_v1.json`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage138_wave0_unattended_watch_smoke/qmt_roll_stage138_c9_minrisk_wave0_unattended_watch_smoke_summary_stage138_wave0_unattended_watch_smoke_v1.csv`
- orders：无；本阶段不生成订单
- daily：无新增交易 daily；资金曲线沿用背景审计序列
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage138_wave0_unattended_watch_smoke/qmt_roll_stage138_c9_minrisk_wave0_unattended_watch_smoke_command_audit_stage138_wave0_unattended_watch_smoke_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage138_wave0_unattended_watch_smoke/qmt_roll_stage138_c9_minrisk_wave0_unattended_watch_smoke_smoke_gate_status_stage138_wave0_unattended_watch_smoke_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage138_wave0_unattended_watch_smoke/qmt_roll_stage138_c9_minrisk_wave0_unattended_watch_smoke_official_path_smoke_status_stage138_wave0_unattended_watch_smoke_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage138_wave0_unattended_watch_smoke/qmt_roll_stage138_c9_minrisk_wave0_unattended_watch_smoke_command_dependency_matrix_stage138_wave0_unattended_watch_smoke_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage138_wave0_unattended_watch_smoke/qmt_roll_stage138_c9_minrisk_wave0_unattended_watch_smoke_gate_status_matrix_stage138_wave0_unattended_watch_smoke_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage138_wave0_unattended_watch_smoke/qmt_roll_stage138_c9_minrisk_wave0_unattended_watch_smoke_watch_history_tail_stage138_wave0_unattended_watch_smoke_v1.png`

## 视觉检查

- 官方路径/smoke 状态图：资金、回撤、broker10 曲线非空；底部显示 `smoke_pass=1`、`stage137_selftest_pass=1`、`stage136_monitor_ready=1`、`stage133_release_allowed_now=0`。
- command dependency matrix：Stage137 与 Stage136 两步均为 dependency passed、executed、stdout JSON parsed、pass now 全绿。
- gate status matrix：`stage137_selftest_passed`、`stage137_no_stage125_133_execution`、`stage136_monitor_ready`、`stage136_release_locked`、`stage136_no_real_w0_arrival_now`、`command_chain_returncode_json_ok` 全绿。
- watch history tail：Stage136 历史快照到本阶段为止均显示 known files `0`、ready candidates `0`、release allowed `0`。

## 结论

- 本阶段结论：Stage138 已把 Stage137 + Stage136 固化为一键无人值守 smoke。当前流程健康，但真实 W0 未到货，下游继续锁死。
- 是否进入下一步：是，但仍只能做数据入口层工作。
- 下一步：可以在下一阶段生成只读 launchd/cron 配置草案和运行手册，但不安装、不加载、不触发 Stage125/133；若真实 W0 出现，必须先看 Stage136 输出再人工/显式跑 Stage125。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只是命令依赖、stdout JSON、gate 状态和文件到货状态的工程 smoke，不读取交易盈亏标签，不调交易参数，不筛年份、品种、方向或窗口。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Stage136/137 单独可用但不够适合无人值守；Stage138 把“自测先行、监控后置、release 锁死”固化成一个可重复入口，真实数据到来前也能持续验证入口健康，降低未来误触发风险。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否；这不是新增研究线或跨线合入
- 是否追加根目录 `memory.md/back_log.md`：否；这不是正式候选、重大突破或跨线合并
