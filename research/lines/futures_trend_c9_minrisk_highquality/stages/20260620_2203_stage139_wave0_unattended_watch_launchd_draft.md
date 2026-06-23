# Stage139 W0 无人值守只读调度草案

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 22:03 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：流程基础设施 / 只读调度草案 / 不进入策略研究
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Apple Developer：`launchd` 可用于定时启动 daemon/agent，配置以 plist 管理，支持定时间隔启动。
    https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html
  - Python 官方 `plistlib`：用于结构化读写 Apple plist，适合生成后再反读校验。
    https://docs.python.org/3/library/plistlib.html
  - `launchd.plist` man page：plist 是被 `launchctl` 载入的参数集合，`ProgramArguments`、`StartInterval`、`StandardOutPath`、`StandardErrorPath` 等键应显式审计。
    https://www.manpagez.com/man/5/launchd.plist/
- 我的判断：
  - 当前问题不是继续确认正式版，而是让真实 W0 到货等待链路少依赖人工记忆；因此只应生成 inert draft，不应安装、不应加载、不应触发 Stage125/133。
  - `launchd` 草案保留 `Disabled=true`，cron 草案把真实行注释掉，二者都只指向 Stage138 smoke；这比直接上定时任务更符合当前“真实数据未到、策略研究禁止”的状态。
  - 本阶段不产生任何交易信号，不增加参数搜索空间，也不改变 Stage138/Stage136 的 release lock。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage139_wave0_unattended_watch_launchd_draft.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `LABEL=local.vnpy.c9-minrisk.w0-watch-smoke.draft`
  - `START_INTERVAL_SECONDS=900`
  - launchd plist `Disabled=true`
  - launchd plist `ProgramArguments=[.py311/bin/python, stage138_wave0_unattended_watch_smoke.py]`
  - cron draft `*/15 * * * * ... stage138_wave0_unattended_watch_smoke.py`，但整行保持注释状态
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage134/Stage138 的官方路径曲线；本阶段未新增回测。
- 账户规模：沿用当前研究线 C9/minrisk 口径。
- 成本口径：沿用 Stage134 汇总口径，总滑点 `2,730,130`。
- 样本过滤：无新增样本过滤。
- 策略/归因口径：只生成 Stage138 watch smoke 的 launchd/cron 草案；不运行 true engine，不进入 A/B，不连接 CTP，不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage139_launchd_cron_draft_ready_not_installed_no_strategy`
  - `draft_ready=1`
  - `launchd_plist_created=1`
  - `launchd_disabled_true=1`
  - `cron_draft_created=1`
  - `cron_draft_commented=1`
  - `runbook_created=1`
  - `config_audit_pass_count=19/19`
  - `artifact_gate_pass_count=15/15`
  - `gate_pass_count=6/6`
  - `stage138_smoke_pass=1`
  - `stage133_release_allowed_now=0`
  - `installed_launch_agent_count=0`
  - `launchctl_called=0`
  - `stage138_command_executed=0`
  - `stage125_command_executed=0`
  - `stage133_command_executed=0`
  - `official_config_changed=0`
  - `real_stage112_intake_allowed_now=0`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage139_wave0_unattended_watch_launchd_draft/qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_report_stage139_wave0_unattended_watch_launchd_draft_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage139_wave0_unattended_watch_launchd_draft/qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_summary_stage139_wave0_unattended_watch_launchd_draft_v1.csv`
- orders：无
- daily：无新增 daily 回测输出
- quality：
  - `qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_config_audit_stage139_wave0_unattended_watch_launchd_draft_v1.csv`
  - `qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_schedule_artifact_matrix_stage139_wave0_unattended_watch_launchd_draft_v1.csv`
  - `qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_gate_status_stage139_wave0_unattended_watch_launchd_draft_v1.csv`
  - `qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft.plist`
  - `qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_cron_draft.txt`
  - `qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_operator_runbook.md`
- 视觉图：
  - `qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_official_path_draft_status_stage139_wave0_unattended_watch_launchd_draft_v1.png`
  - `qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_launchd_safety_matrix_stage139_wave0_unattended_watch_launchd_draft_v1.png`
  - `qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_artifact_matrix_stage139_wave0_unattended_watch_launchd_draft_v1.png`
  - `qmt_roll_stage139_c9_minrisk_wave0_unattended_watch_launchd_draft_gate_status_matrix_stage139_wave0_unattended_watch_launchd_draft_v1.png`

## 结论

- 本阶段结论：
  - Stage139 只读调度草案可用：plist 可被 `plistlib` 反读，`plutil -lint` 返回 OK；cron 行保持注释；LaunchAgents/LaunchDaemons 位置没有同名安装文件。
  - 草案只指向 Stage138，不包含 Stage125/Stage133、CTP、order submit 或正式配置变量。
  - 当前仍无真实 W0 到货，release 仍锁住，不能进入 Stage112/113、微观结构/分钟规则、true engine、A/B 或正式候选。
- 是否进入下一步：是，但只进入“等待真实 W0 / 监控与验收自动化”的下一步，不进入策略规则。
- 下一步：
  - 若真实 W0 drop 到货，按 Stage125 -> Stage133 路径人工或受控运行验收。
  - 若继续自动化，只允许做 Stage140 的“安装前 dry-run 审计/状态面板”，仍不安装 launchd、不运行 Stage125/133、不改变 official config。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有新增交易规则、参数阈值、样本过滤或回测优化，只做调度配置的结构化生成与安全闸门。
  - 唯一新增的 `900` 秒是运维轮询间隔，不参与收益曲线或交易决策。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值边界清楚。
- 原因：
  - 有价值之处在于减少真实 W0 到货等待期间的人工漏检，并把“未安装、未触发、未放行”的状态写成可审计证据。
  - 边界是它不产生 alpha，也不能替代真实 W0 数据验收；继续推进必须围绕真实到货、Stage125/133/112/113 硬闸门，而不是借自动化名义做策略研究。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage139 一条状态摘要。
- 是否更新 `research/registry.md`：否，本阶段不是突破、废弃、正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段只是当前线日常流程基础设施。
