# Stage140 W0 无人值守安装前状态面板

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 22:13 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：流程基础设施 / 安装前 dry-run 状态面板 / 不进入策略研究
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Apple Support：`launchd` 负责管理 macOS daemon/agent，用户通过 `launchctl` 载入或卸载任务；因此本阶段只允许使用 `launchctl print` 观察状态，不允许 `bootstrap/load/enable/kickstart`。
    https://support.apple.com/guide/terminal/script-management-with-launchd-apdc6c1077b-5d5d-4d35-9c19-60f2397b2369/mac
  - `plutil` man page：`plutil` 可用于检查 plist 语法，因此安装前应保留 `plutil -lint` 闸门。
    https://www.manpagez.com/man/1/plutil/
  - `launchd.plist` man page：`StartInterval`、`Disabled`、`ProgramArguments`、日志路径等 plist 键需要安装前审计。
    https://www.manpagez.com/man/5/launchd.plist/
- 我的判断：
  - Stage139 已经生成 inert 草案，但“可生成草案”和“当前可以安装”不是一回事；Stage140 应把安装前状态显式可视化，避免操作员把草案当成已批准任务。
  - 当前真实 W0 仍未到货，策略研究仍被数据硬闸门阻断；因此结论必须是可观察、不可安装、不可进入分钟规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage140_wave0_unattended_watch_preinstall_status_panel.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `LABEL=local.vnpy.c9-minrisk.w0-watch-smoke.draft`
  - `FORBIDDEN_LAUNCHCTL_SUBCOMMANDS={bootstrap, bootout, enable, disable, kickstart, load, unload, start, stop, submit, remove}`
  - 只读命令：`plutil -lint <stage139 plist>`、`launchctl print gui/<uid>/<label>`、`launchctl print user/<uid>/<label>`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage134 的官方路径曲线；本阶段未新增回测。
- 账户规模：沿用当前研究线 C9/minrisk 口径。
- 成本口径：沿用 Stage134 汇总口径，总滑点 `2,730,130`。
- 样本过滤：无新增样本过滤。
- 策略/归因口径：只做 Stage139 草案的安装前只读状态审计；不运行 Stage136/Stage138/Stage125/Stage133，不运行 true engine，不进入 A/B，不连接 CTP，不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage140_preinstall_status_panel_ready_waiting_real_w0_no_install`
  - `install_recommendation=do_not_install_waiting_real_w0`
  - `preinstall_status_ready=1`
  - `preinstall_audit_pass_count=18/18`
  - `gate_pass_count=4/4`
  - `readonly_command_count=3`
  - `launchctl_readonly_command_count=2`
  - `launchctl_mutating_command_count=0`
  - `plutil_lint_ok=1`
  - `launchctl_label_not_loaded=1`
  - `installed_launch_agent_count=0`
  - `stage136_monitor_ready=1`
  - `stage136_best_known_file_count=0/123`
  - `stage136_stage125_candidate_count=0`
  - `stage136_candidate_ready_count=0`
  - `stage136_command_executed=0`
  - `stage138_command_executed=0`
  - `stage125_command_executed=0`
  - `stage133_command_executed=0`
  - `stage133_release_allowed_now=0`
  - `official_config_changed=0`
  - `real_w0_data_delivered=0`
  - `real_stage112_intake_allowed_now=0`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage140_wave0_unattended_watch_preinstall_status_panel/qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel_report_stage140_wave0_unattended_watch_preinstall_status_panel_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage140_wave0_unattended_watch_preinstall_status_panel/qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel_summary_stage140_wave0_unattended_watch_preinstall_status_panel_v1.csv`
- orders：无
- daily：无新增 daily 回测输出
- quality：
  - `qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel_readonly_command_audit_stage140_wave0_unattended_watch_preinstall_status_panel_v1.csv`
  - `qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel_preinstall_audit_stage140_wave0_unattended_watch_preinstall_status_panel_v1.csv`
  - `qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel_gate_status_stage140_wave0_unattended_watch_preinstall_status_panel_v1.csv`
  - `qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel_operator_dashboard_stage140_wave0_unattended_watch_preinstall_status_panel_v1.md`
- 视觉图：
  - `qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel_official_path_preinstall_status_stage140_wave0_unattended_watch_preinstall_status_panel_v1.png`
  - `qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel_readonly_command_matrix_stage140_wave0_unattended_watch_preinstall_status_panel_v1.png`
  - `qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel_preinstall_audit_matrix_stage140_wave0_unattended_watch_preinstall_status_panel_v1.png`
  - `qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel_watch_artifact_status_stage140_wave0_unattended_watch_preinstall_status_panel_v1.png`
  - `qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel_gate_status_matrix_stage140_wave0_unattended_watch_preinstall_status_panel_v1.png`

## 结论

- 本阶段结论：
  - Stage140 安装前状态面板通过：Stage139 草案仍可 lint，launchctl 的 gui/user 域都未加载该 label，系统 LaunchAgents/LaunchDaemons 位置没有同名 plist。
  - 当前 recommendation 是 `do_not_install_waiting_real_w0`；这不是安装批准，也不是策略研究批准。
  - 真实 W0 仍未到货，Stage133 release 仍为 `0`，Stage112/113、分钟盘口研究、true engine、A/B 和正式候选继续全部阻断。
- 是否进入下一步：是，但只进入真实 W0 到货等待/验收链路，不进入策略规则。
- 下一步：
  - 若真实 W0 drop 到货，先运行 Stage125 receipt preflight，再运行 Stage133 release verdict；通过前不得继续策略研究。
  - 若继续无人值守方向，只能做“真实 drop 到货后的人工确认/通知草案”，仍不得自动安装或自动执行 Stage125/133。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有生成交易规则、参数阈值、过滤条件、品种/年份选择或收益优化，只做运维状态审计。
  - `launchctl print` 和 `plutil -lint` 是安装前状态观察，不参与回测收益和交易决策。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但不能继续堆过多流程外壳。
- 原因：
  - 有价值之处在于把“草案可安装但当前不该安装”的状态清楚写出来，避免真实数据未到时误触发自动化。
  - 边界是本阶段不产生 alpha；接下来真正有价值的进展仍然取决于真实 W0 数据到货并通过 Stage125/133/112/113。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage140 一条状态摘要。
- 是否更新 `research/registry.md`：否，本阶段不是突破、废弃、正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段只是当前线日常流程基础设施。
