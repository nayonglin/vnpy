# Stage092 C9 Phase D 真实账户差异来源归因审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-16 00:25 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方 C9 Phase D 全自动执行链路的只读归因审计
- 是否重要突破：是。首次把真实 broker 10 手 vs C9 shadow 12 手的账户来源差异做成可回归 Stage919 审计，并新增 Stage920 账户起点同步闸门。
- 是否触发A/B：否。本阶段不比较策略版本、不改 alpha。

## 外部调研与判断

- 参考资料：前序 Phase D 已复用 vn.py `MainEngine.send_order` 真实下单边界源码、FIA 自动化交易风险控制白皮书、CFTC 电子交易风险原则。
- 我的判断：全自动执行的核心不是“看到信号就下单”，而是信号、broker 状态、订单意图、成交回报、对账状态必须形成闭环；一旦 broker/shadow 来源不能解释，应 fail-closed，而不是自动用 shadow 回填 broker 或自动做差异平仓。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage919_official_live_reconcile_attribution_audit.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage920_official_live_account_sync_gate.py`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage913_official_live_phase_d_completion_audit.py`：新增 `reconcile_attribution` 与 `account_sync_guard` 完成度要求。
  - `examples/portfolio_backtesting/run_qmt_roll_stage916_official_live_order_boundary_static_audit.py`：将 Stage919/920 纳入订单边界静态扫描。
- 删除脚本：无
- 新增参数：Stage919 `--target-date`；Stage920 `--target-date`、`--ack-path`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：目标交易日 `2026-06-12`
- 账户规模：C9 live default `300000`
- 成本口径：本阶段无新增回测成本；只读执行归因
- 样本过滤：真实 broker 持仓、Stage901 当前 shadow 持仓、pending orders、trades、entry risk、trade events、Stage260/905/906/918 对账证据
- 策略/归因口径：以真实 broker 账户为执行事实源，C9 shadow 只作为理论目标，不允许回填真实账户

## 结果

- 期末权益：无新增回测；沿用 Stage901 2026 YTD shadow `265,860`
- 总收益：无新增回测；沿用 Stage901 `-11.38%`
- 最大回撤：无新增回测；沿用 Stage901 `-14.8955%`
- Sharpe：无新增回测；沿用 Stage901 `-1.1331`
- 总滑点：无新增回测；沿用 Stage901 `3,860`
- 总交易次数：无新增回测；沿用 Stage901 `27`
- 胜率：无新增回测；沿用 Stage901 非零日胜率 `45.7143%`
- 其他关键指标：
  - Stage919：`reconcile_attribution_divergent_origin_unresolved_fail_closed`
  - Stage919：真实 broker `MA609.CZCE long 10 @ 2847`，C9 shadow `MA609.CZCE long 12`，C9 当前开仓成交 `2026-06-12 3029 x 12`
  - Stage919：`auto_submit_permitted=0`，`fully_automatic_proven=0`，`order_api_called_count=0`
  - Stage916：`phase_d_order_boundary_static_audit_passed`，扫描 `20` 个 Phase D 文件，非授权下单引用 `0`
  - Stage909：已在 env gate + 确认文本下完成 `run`，Stage173 数据更新 exit `0`，官方 C9 shadow exit `0`，`shadow_refresh_status=shadow_refresh_completed`
  - Stage903：已完成完整控制器周期，shadow refresh `run`、production-live read-only refresh `refresh` 均成功，写出 launchd plist 模板，控制器仍 `phase_d_controller_dry_run_blocked`
  - Stage912：`phase_d_acceptance_passed_fail_closed`，`30/30` 通过，`order_api_called_count=0`
  - Stage920：`account_sync_operator_ack_required_fail_closed`，生成账户同步指纹 `93cc4a23f809d23e0b07829760bf885ed238ab6ac7d729556d8a5c4c98e474bf` 和人工确认模板，`auto_submit_permitted=0`
  - Stage913：`phase_d_completion_not_proven`，`passed=13`、`partial=4`、`incomplete=1`，唯一 blocked 仍是 `reconcile`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage919_official_live_reconcile_attribution_audit_report_20260612_stage919_official_live_reconcile_attribution_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage919_official_live_reconcile_attribution_audit_summary_20260612_stage919_official_live_reconcile_attribution_audit_v1.json`
- orders：不适用；本阶段不生成订单、不连接 CTP、不调用下单 API
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage919_official_live_reconcile_attribution_audit_evidence_20260612_stage919_official_live_reconcile_attribution_audit_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage913_official_live_phase_d_completion_audit_summary_20260616_003504_stage913_official_live_phase_d_completion_audit_v1.json`

## 结论

- 本阶段结论：当前不能确认 C9 已可全自动。系统层已能自动识别并阻断真实账户差异，但真实账户来源仍未能归因到当前 C9 shadow 开仓；因此必须继续 fail-closed。
- 是否进入下一步：是。
- 下一步：需要处理真实账户起点问题。优先人工确认 `MA609.CZCE` 10 手来源，若要支持 reduce-only reconciliation mode，必须另设人工确认和单独晋升闸门，不能直接放进无人值守自动执行。

## 过拟合反思

- 运行前判断：否。本阶段是执行对账归因，不改 C9 参数，不反馈历史收益。
- 运行后判断：否。Stage919 只读取 broker/shadow/闸门证据，并保持订单 API 为 `0`。
- 原因：它验证的是自动化执行纪律，不是在历史交易上寻找更优参数。

## 继续价值反思

- 运行前判断：是。全自动前必须证明差异来源可解释，或证明系统会自动 fail-closed。
- 运行后判断：是。当前已证明系统能 fail-closed，但没有证明真实账户已经与 C9 shadow 同步。
- 原因：只要真实账户起点不清楚，任何无人值守平仓/减仓都可能是在处理非 C9 来源持仓。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等待真实账户来源确认或 Phase D 完成度变化。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；目前是执行链路 fail-closed 证据增强，不是全自动完成或正式上线。

## 2026-06-16 00:50 补充：动态目标日与 2026-06-15 shadow/实盘只读对账

- 本次补充性质：Phase D 全自动架构继续落地；不是 C9 参数优化，不触发 A/B。
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage922_official_live_target_date_resolver.py`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`：新增 `--target-date-mode latest-completed`，常驻控制器每轮先解析最新已完成交易日。
  - `examples/portfolio_backtesting/run_qmt_roll_stage921_official_live_scheduler_audit.py`：把 launchd 固定日期审计升级为 latest-completed resolver 审计。
  - `examples/portfolio_backtesting/run_qmt_roll_stage916_official_live_order_boundary_static_audit.py`：纳入 Stage922 静态订单边界扫描。
  - `examples/portfolio_backtesting/run_qmt_roll_stage913_official_live_phase_d_completion_audit.py`：新增 `target_date_resolver` 完成度要求。
  - `examples/portfolio_backtesting/run_qmt_roll_stage920_official_live_account_sync_gate.py`：归因文件缺失时改为 fail-closed，避免并行竞态误判空差异为同步。
- 删除脚本：无
- 新增参数：
  - Stage903 `--target-date-mode {official-summary,latest-completed}`、`--target-date-data-ready-time`、`--target-date-as-of`
  - Stage922 `--as-of`、`--data-ready-time`
- 修改参数：无
- 删除参数：无

### 新增回测/执行证据

- Stage922：解析最新已完成交易日为 `2026-06-15`；初次运行时发现 official summary 与 Stage173 bars 仍停在 `2026-06-12`，状态 `target_date_resolved_requires_refresh_fail_closed`，`auto_submit_permitted=0`，`order_api_called_count=0`。
- Stage909：按 `2026-06-15` 运行 `run` 模式，Stage173 数据更新 exit `0`，官方 C9 shadow exit `0`，`shadow_refresh_status=shadow_refresh_completed`。
- Stage901 2026 YTD shadow 更新后：
  - 期末权益：`264,540`
  - 总收益：`-11.82%`
  - 最大回撤：`-15.2224%`
  - Sharpe：`-1.1786`
  - 总滑点：`3,980`
  - 总交易次数：`28`
  - 非零日胜率：`44.4444%`
  - `deployable_pass=1`
  - 目标日信号：`MA609.CZCE` `Short Close` `12` 手，理论价 `3000`，原因 `long_risk_cluster_heat_deleverage`
  - 更新后 shadow 当前持仓为空；pending orders 为空。
- Stage907 production-live read-only refresh：`readonly_refresh_completed_snapshot_ready`，`positions_received`，`order_api_called_count=0`。
- 真实 CTP 只读持仓：`MA609.CZCE` 多 `10` 手，均价 `2847`，浮亏约 `-8000`；账户余额 `148,985.67`，可用 `97,739.67`。
- Stage260：`trade_date=2026-06-15`，`risk_level=normal`，但 `executable_count=0`、`skipped_position_mismatch_count=1`、`order_api_called_count=0`。
- Stage906：`reconcile_divergent_fail_closed`，shadow position rows `0`，broker position rows `1`，`order_api_called_count=0`。
- Stage918：`reconcile_policy_blocked_fail_closed`，`divergent_count=1`，`manual_action_candidate_count=0`，`auto_submit_permitted=0`。
- Stage919：`reconcile_attribution_divergent_origin_unresolved_fail_closed`，真实 broker `MA609.CZCE long 10 @ 2847`，C9 最新 shadow 已空仓；C9 相关开仓仍是 `2026-06-12 3029 x 12`，未能解释 broker 10 手来源，`fully_automatic_proven=0`。
- Stage920：修复后 `account_sync_operator_ack_required_fail_closed`，`divergent_count=1`，fingerprint `a8fbff327e2c3ef15513ea2f5149833096ce7cc503aa5cabc872fb158e5ad39c`。
- Stage903：动态目标日完整 dry-run controller 结果 `phase_d_controller_dry_run_blocked`；Stage922/Stage909/Stage907/Stage902/Stage904 均到位，但 Stage906 divergent 阻断；`order_api_called_count=0`。
- Stage921：`scheduler_template_dynamic_target_ready_fail_closed`，launchd 模板不再包含固定 `--target-date`，改为 `--target-date-mode latest-completed --target-date-data-ready-time 16:30`。
- Stage916：`phase_d_order_boundary_static_audit_passed`，扫描 `22` 个 Phase D 文件，允许 `send_order` 引用 `2`，非授权引用 `0`。
- Stage913：`phase_d_completion_not_proven`，`passed=16`、`partial=3`、`incomplete=1`，唯一 hard block 为 `reconcile`；`order_api_called_count=0`。

### 判断

- 过拟合反思：否。本补充只做执行目标日解析、shadow 刷新、CTP 只读快照、对账和 fail-closed 审计，没有修改 C9 参数、品种、方向、R 倍数或信号逻辑。
- 继续价值反思：是。动态调度、日终刷新、只读快照和健康检查已经更接近无人值守，但真实 broker 与 C9 shadow 起点仍不一致；在该差异未人工确认或未通过单独 reduce-only 晋升前，不能确认全自动实盘可用。
- 当前结论：Phase D 自动化架构已覆盖信号计算、动态目标日、常驻模板、CTP runtime preflight、只读 broker refresh、执行闸门、盘中监控、executor dry-run、adapter 边界、kill switch、心跳、对账和归因；但因为真实账户 `MA609` 多 10 手不是当前 C9 shadow 的可解释持仓，正式全自动仍必须 fail-closed。

## 2026-06-16 01:01 补充：fail-closed incident 事件包与验收覆盖

- 本次补充性质：Phase D 运维闭环增强；不是 C9 参数优化，不触发 A/B。
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage923_official_live_fail_closed_incident.py`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`：控制器每轮在 Stage908 后自动调用 Stage923，产出 fail-closed 事件包。
  - `examples/portfolio_backtesting/run_qmt_roll_stage912_official_live_phase_d_acceptance_suite.py`：新增 Stage923 回归验收。
  - `examples/portfolio_backtesting/run_qmt_roll_stage913_official_live_phase_d_completion_audit.py`：新增 `fail_closed_incident` 完成度要求。
  - `examples/portfolio_backtesting/run_qmt_roll_stage916_official_live_order_boundary_static_audit.py`：纳入 Stage923 静态订单边界扫描。
- 删除脚本：无
- 新增参数：Stage923 `--target-date`
- 修改参数：无
- 删除参数：无

### 新增执行证据

- Stage923：`phase_d_fail_closed_operator_attention_required`，`operator_action_required=1`，`auto_submit_permitted=0`，`order_api_called_count=0`。
- Stage923 action package：
  - P0 `do_not_submit_unattended_orders`：automation enforced
  - P0 `keep_phase_d_fail_closed`：automation enforced
  - P0 `operator_confirm_broker_position_origin`：operator required，原因 `MA609.CZCE Long 10 @ 2847 pnl=-8000`
  - P0 `review_stage919_attribution`：operator required，原因 `unclassified_reconcile_divergence_fail_closed`
  - P1 `complete_or_reject_stage920_ack_template`：operator required，fingerprint `a8fbff327e2c3ef15513ea2f5149833096ce7cc503aa5cabc872fb158e5ad39c`
  - P1 `rerun_shadow_readonly_reconcile_after_manual_action`：automation pending external state
- Stage903 最新完整控制器：`phase_d_controller_dry_run_blocked`，动态目标日 `2026-06-15`，Stage909 refresh 完成、Stage907 production-live read-only refresh 完成、Stage923 incident 自动生成；`order_api_called_count=0`。
- Stage912：`phase_d_acceptance_passed_fail_closed`，`passed=34`、`failed=0`、`order_api_called_count=0`，已覆盖 Stage923。
- Stage916：`phase_d_order_boundary_static_audit_passed`，扫描 `23` 个 Phase D 文件，允许 `send_order` 引用 `2`，非授权引用 `0`。
- Stage921：`scheduler_template_dynamic_target_ready_fail_closed`，`warn=0`、`block=0`。
- Stage910：`controller_alive_fail_closed`，心跳新鲜，`order_api_called_count=0`。
- Stage913：`phase_d_completion_not_proven`，`passed=17`、`partial=3`、`incomplete=1`，唯一 hard block 仍是 `reconcile`，`order_api_called_count=0`。
- 代码卫生：`py_compile` 通过，`git diff --check` 通过；未发现残留 Stage903/CTP Python 进程。

### 判断

- 过拟合反思：否。Stage923 只把执行阻断状态打包成运维事件，不改变信号、参数、样本或回测逻辑。
- 继续价值反思：是。现在无人值守系统不仅能停住，还能自动说明为什么停、需要谁处理、处理后应重跑哪些链路；这让 Phase D 更接近真实生产运维。
- 当前结论：全自动架构的 fail-closed 运维闭环更完整，但仍不能确认可全自动实盘。真实账户 `MA609` 多 `10` 手与 C9 shadow 空仓不一致，且来源未解释；在该外部状态解决前，系统正确状态就是自动停住并要求人工确认。

## 2026-06-16 01:04 补充：Stage903 auto refresh 与 launchd dry-run 自动化模板

- 本次补充性质：常驻自动化模板从“plan-only 心跳”升级为“按需自动刷新”；仍不启用真实 submit。
- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`：`--shadow-refresh-mode` 与 `--readonly-refresh-mode` 新增 `auto`；shadow 已就绪时自动降级为 `plan-only`，数据/summary 未就绪时才运行 Stage909；broker 只读快照未过期时自动降级为 `plan-only`，过期或不可用时才运行 Stage907 refresh。
  - `examples/portfolio_backtesting/run_qmt_roll_stage921_official_live_scheduler_audit.py`：新增 launchd 模板的 `auto` 刷新参数、确认文本和 env gate 审计，并确认未设置真实 submit env。
  - `examples/portfolio_backtesting/run_qmt_roll_stage913_official_live_phase_d_completion_audit.py`：修正 signal 完成度口径，允许“target shadow 已就绪且控制器 auto-skip refresh”作为通过证据。
- 新增参数：
  - Stage903 `--shadow-refresh-mode auto`
  - Stage903 `--readonly-refresh-mode auto`
- 修改参数：Stage903 launchd 模板现在写入：
  - `--target-date-mode latest-completed`
  - `--shadow-refresh-mode auto`
  - `--readonly-refresh-mode auto`
  - `--stage251-mode skip`
  - env：`OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED=1`、`OFFICIAL_LIVE_PHASE_D_REAL_ADAPTER_IMPLEMENTED=1`、`OFFICIAL_LIVE_PHASE_D_SHADOW_REFRESH_ENABLED=1`、`OFFICIAL_LIVE_PHASE_D_READONLY_REFRESH_ENABLED=1`
  - 未写入：`OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED`
- 删除参数：无

### 新增执行证据

- Stage903 auto dry-run：`phase_d_controller_dry_run_blocked`，目标日 `2026-06-15`，`stage909_requested_shadow_refresh_mode=auto`、`stage909_effective_shadow_refresh_mode=plan-only`，因为 Stage922 已证明本地 shadow 就绪；`stage907_requested_refresh_mode=auto`、`stage907_effective_refresh_mode=plan-only`，因为只读 broker 快照 age `232.870042s`，未超过 `300s`；`order_api_called_count=0`。
- Stage921：`scheduler_template_dynamic_target_ready_fail_closed`，`shadow_refresh_mode=auto`，`readonly_refresh_mode=auto`，`block=0`、`warn=0`，并确认 launchd env 未启用真实 submit。
- Stage916：`phase_d_order_boundary_static_audit_passed`，扫描 `23` 个 Phase D 文件，非授权下单引用 `0`。
- Stage913：`phase_d_completion_not_proven`，`passed=17`、`partial=3`、`incomplete=1`，唯一 hard block 仍是 `reconcile`；`order_api_called_count=0`。
- Stage910：`controller_alive_fail_closed`，心跳新鲜，`order_api_called_count=0`。

### 判断

- 过拟合反思：否。auto refresh 是执行调度策略，不影响 C9 交易规则、参数、信号或历史回测。
- 继续价值反思：是。常驻模板现在具备无人值守的必要动作：自动解析最新目标日、按需刷新 shadow、按需刷新 broker 只读快照、继续执行闸门/盘中监控/对账/incident；同时真实 submit env 保持关闭。
- 当前结论：Phase D 的“全自动 dry-run + fail-closed”架构已经更接近可部署，但仍不能确认“全自动实盘可交易”。原因没有变化：真实 broker `MA609.CZCE` 多 `10` 手与 C9 shadow 空仓不一致，Stage906 仍 `reconcile_divergent_fail_closed`。

## 2026-06-16 01:14 补充：Stage924 账户恢复闸门与最新 Phase D 验收

- 本次补充性质：继续补齐全自动执行架构中的“人工处理后如何安全重新入链”环节；不是 C9 参数优化，不触发 A/B。
- 外部调研判断：vn.py 的真实下单边界仍应集中在 `MainEngine.send_order -> gateway.send_order` 一类 adapter 路径；macOS 常驻调度可用 launchd 的 `RunAtLoad/KeepAlive`，但调度能力不能替代账户一致性、kill switch、对账和恢复闸门。
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage924_official_live_account_recovery_gate.py`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`：控制器每轮在 Stage923 fail-closed incident 后自动调用 Stage924，输出 account recovery gate 状态。
  - `examples/portfolio_backtesting/run_qmt_roll_stage912_official_live_phase_d_acceptance_suite.py`：新增 Stage924 验收项。
  - `examples/portfolio_backtesting/run_qmt_roll_stage913_official_live_phase_d_completion_audit.py`：新增 `account_recovery_gate` 完成度要求。
  - `examples/portfolio_backtesting/run_qmt_roll_stage916_official_live_order_boundary_static_audit.py`：纳入 Stage924 静态订单边界扫描。
- 新增参数：
  - Stage924 `--target-date`
  - Stage924 `--ack-path`
- 修改参数：无
- 删除参数：无

### 新增执行证据

- Stage924 单跑目标日 `2026-06-15`：`account_recovery_ack_required_fail_closed`，`divergent_count=1`，`ack_valid=0`，`ack_reason=ack_missing`，fingerprint `a8fbff327e2c3ef15513ea2f5149833096ce7cc503aa5cabc872fb158e5ad39c`，`auto_submit_permitted=0`，`order_api_called_count=0`。
- Stage924 生成 recovery ack template，允许的人工恢复动作仅包括：
  - `manual_keep_fail_closed`
  - `manual_flatten_or_reduce_then_refresh`
  - `manual_accept_broker_as_non_strategy_position`
  但任何有效 ack 本身都不允许无人值守真实提交；人工动作后必须重跑 shadow、readonly、Stage260、Stage906、Stage919、Stage920、Stage924、Stage913。
- Stage903 最新 auto dry-run：`phase_d_controller_dry_run_blocked`，目标日由 Stage922 解析为 `2026-06-15`；Stage909 因本地 shadow 已就绪自动降为 `plan-only`，Stage907 因只读快照 age `200.664476s` 未过期自动降为 `plan-only`；Stage260 `executable_count=0`、`skipped_position_mismatch_count=1`；Stage906 `reconcile_divergent_fail_closed`；Stage923 `phase_d_fail_closed_operator_attention_required`；Stage924 `account_recovery_ack_required_fail_closed`；`order_api_called_count=0`。
- Stage912 最新验收：`phase_d_acceptance_passed_fail_closed`，`passed=38`、`failed=0`，kill switch 原始和恢复状态均为关闭，`order_api_called_count=0`。
- Stage916 最新静态边界：`phase_d_order_boundary_static_audit_passed`，扫描 `24` 个 Phase D 文件，允许 `send_order` 引用 `2`，非授权引用 `0`，`order_api_called_count=0`。
- Stage921 最新调度审计：`scheduler_template_dynamic_target_ready_fail_closed`，`target_date_mode=latest_completed_resolver`，`shadow_refresh_mode=auto`，`readonly_refresh_mode=auto`，`poll_seconds=30`，`block=0`、`warn=0`，`order_api_called_count=0`。
- Stage910 最新健康检查：`controller_alive_fail_closed`，controller 状态 `phase_d_controller_dry_run_blocked`，心跳 age `8.016s`，kill switch 未启用，`order_api_called_count=0`。
- Stage913 最新完成度审计：`phase_d_completion_not_proven`，`passed=18`、`partial=3`、`incomplete=1`，`order_api_called_count=0`。唯一 blocked 仍是 `reconcile`；3 个 partial 分别是 `adapter`、`executor`、`execution_gate`，均由当前 broker/shadow 不一致导致无法产生可执行 intent。
- Stage913 口径补充：已把“账户已对齐且无交易意图”的 no-action idle 场景定义为可通过，避免未来无信号日被误判为 partial；当前结果仍为 `phase_d_completion_not_proven`，因为 `MA609` broker/shadow 尚未对齐。

### 当前阻塞

- 当前不能确认 C9 已可全自动实盘。硬阻塞不是 signal、daemon、heartbeat、kill switch 或静态下单边界，而是真实账户状态：
  - C9 shadow 在 `2026-06-15` 目标日后为空仓；
  - CTP production-live 只读快照仍有 `MA609.CZCE` 多 `10` 手，均价 `2847`，浮亏约 `-8000`；
  - Stage919 未能把该 10 手归因到当前 C9 shadow 的 `2026-06-12` `3029 x 12` 开仓与 `2026-06-15` 平仓路径；
  - 因此 Stage906 必须保持 `reconcile_divergent_fail_closed`，不能无人值守发送平仓、减仓或新开仓。

### 判断

- 过拟合反思：否。Stage924 和本轮 Phase D 验收只处理账户恢复、调度、静态边界、心跳和 fail-closed 行为，不改 C9 信号、参数、品种、方向、R 倍数、样本或回测口径。
- 继续价值反思：是，但价值已经从“继续写更多自动化脚本”转为“解决真实账户起点差异后复跑证据链”。工程链路已经能无人值守计算信号、刷新数据、刷新只读 broker、监控、执行 dry-run、对账、熔断、心跳、生成事件包和恢复模板；继续堆脚本不能替代账户真实状态一致。
- 当前结论：Phase D 的全自动 dry-run/fail-closed 架构已基本闭合；正式全自动实盘仍未确认，必须等 `MA609.CZCE` 真实持仓来源被人工确认、手动处理或明确隔离后，按 Stage924/Stage920 ack 重新跑全链路，直到 Stage906 `reconcile_aligned` 且 Stage913 不再有 blocked。

## 2026-06-16 01:22 补充：Stage925 恢复确认回归套件

- 本次补充性质：补齐 Stage924 账户恢复确认的回归测试矩阵，防止错误 ack、错日期、错指纹或非法恢复动作误放行；不是 C9 参数优化，不触发 A/B。
- 外部调研判断：自动交易风险控制资料继续支持当前方向，即所有订单必须先过 pre-trade controls、kill switch、持仓/委托监控和对账；vn.py 真实下单边界仍应集中在 `MainEngine.send_order -> gateway.send_order`，所以恢复确认只能作为重新入链依据，不能作为下单许可。
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage925_official_live_account_recovery_ack_suite.py`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage912_official_live_phase_d_acceptance_suite.py`：新增 Stage925 回归验收。
  - `examples/portfolio_backtesting/run_qmt_roll_stage913_official_live_phase_d_completion_audit.py`：新增 `account_recovery_ack_suite` 完成度要求。
  - `examples/portfolio_backtesting/run_qmt_roll_stage916_official_live_order_boundary_static_audit.py`：纳入 Stage925 静态订单边界扫描。
- 新增参数：Stage925 `--target-date`
- 修改参数：无
- 删除参数：无

### 新增执行证据

- Stage925：`account_recovery_ack_suite_passed_fail_closed`，`case_count=13`、`passed=13`、`failed=0`，当前 `divergent_count=1`、broker position rows `1`，fingerprint `a8fbff327e2c3ef15513ea2f5149833096ce7cc503aa5cabc872fb158e5ad39c`，`auto_submit_permitted=0`，`order_api_called_count=0`。
- Stage925 覆盖场景：
  - 缺失 ack：必须 `account_recovery_ack_required_fail_closed`
  - 错目标日期：必须 fail-closed
  - 错 live version：必须 fail-closed
  - 错 fingerprint：必须 fail-closed
  - `operator_acknowledged=false`：必须 fail-closed
  - 非法 `recovery_action=auto_flatten_and_submit`：必须 fail-closed
  - 缺 operator：必须 fail-closed
  - 缺 acknowledged_at：必须 fail-closed
  - 有效 `manual_keep_fail_closed`：仍 fail-closed
  - 有效 `manual_flatten_or_reduce_then_refresh` 但 broker 仍有仓：仍 fail-closed
  - 有效 `manual_flatten_or_reduce_then_refresh` 且 broker 已空：只允许 `rerun_required`，不允许提交
  - 有效 `manual_accept_broker_as_non_strategy_position`：仍 fail-closed
  - 已对齐且无差异：`account_recovery_not_required_aligned`
- Stage916：`phase_d_order_boundary_static_audit_passed`，扫描 `25` 个 Phase D 文件，允许 `send_order` 引用 `2`，非授权引用 `0`，`order_api_called_count=0`。
- Stage912：`phase_d_acceptance_passed_fail_closed`，`passed=43`、`failed=0`，kill switch 恢复为原始关闭状态，`order_api_called_count=0`。
- Stage903 最新 auto dry-run：`phase_d_controller_dry_run_blocked`，目标日 `2026-06-15`；因只读快照 age `693.938981s` 超过 `300s`，Stage907 自动执行 production-live read-only refresh，刷新成功；Stage260 仍 `skipped_position_mismatch_count=1`，Stage906 仍 `reconcile_divergent_fail_closed`，Stage923/924 均要求人工处理，`order_api_called_count=0`。
- Stage921：`scheduler_template_dynamic_target_ready_fail_closed`，动态目标日、auto shadow、auto readonly 均通过审计，`order_api_called_count=0`。
- Stage910：`controller_alive_fail_closed`，心跳 age `9.389s`，kill switch 未启用，`order_api_called_count=0`。
- Stage913：`phase_d_completion_not_proven`，`passed=19`、`partial=3`、`incomplete=1`，新增 Stage925 后通过项增加到 `19`；唯一 hard block 仍是 `reconcile`，`order_api_called_count=0`。

### 判断

- 过拟合反思：否。Stage925 只做恢复确认语义回归，不改 C9 信号、参数、样本、品种、方向或历史回测。
- 继续价值反思：是。无人值守系统最危险的不是“没有 ack”，而是“ack 写错却被当作通行证”；Stage925 现在把这类错误纳入自动验收。
- 当前结论：Phase D fail-closed 证据链进一步增强，但正式全自动仍未确认。当前必须继续把 `MA609.CZCE` broker 多 `10` 手视为未归因外部状态；没有 `reconcile_aligned` 前，任何恢复确认都不能触发真实下单。

## 2026-06-16 01:30 补充：Stage926 broker/shadow 对齐空跑集成证明

- 本次补充性质：补齐“broker/shadow 已对齐但无可执行订单”时的自动空跑证明；不是 C9 参数优化，不触发 A/B。
- 外部调研判断：CFTC/FIA 类自动交易风险控制资料强调 pre-trade controls、心跳、order size、仓位限制、message throttle、kill switch 和上线前测试；这支持我们把“无交易也要可证明空跑”纳入 Phase D，而不是只测试有订单时的路径。
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage926_official_live_aligned_idle_integration.py`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage912_official_live_phase_d_acceptance_suite.py`：新增 Stage926 回归验收。
  - `examples/portfolio_backtesting/run_qmt_roll_stage913_official_live_phase_d_completion_audit.py`：新增 `aligned_idle_integration_proof` 完成度要求。
  - `examples/portfolio_backtesting/run_qmt_roll_stage916_official_live_order_boundary_static_audit.py`：纳入 Stage926 静态订单边界扫描。
- 新增参数：Stage926 `--target-date`
- 修改参数：无
- 删除参数：无

### 新增执行证据

- Stage926：`aligned_idle_no_action_passed_fail_closed`，`passed=9`、`failed=0`，真实快照和子阶段输出均已恢复，`order_api_called_count=0`。
- Stage926 mock flat 子链路：
  - Stage260：`exec=0;flat=1`，表示目标日理论平仓信号遇到 broker 确认空仓时自动跳过，不生成订单。
  - Stage902：`phase_d_readiness_dry_run_passed_real_still_disabled`
  - Stage904：`intraday_monitor_ready`
  - Stage905：`executor_no_intents`
  - Stage906：`reconcile_aligned`
  - Stage908：`adapter_contract_blocked` 且 `live_submit_permitted=0`，无 intent 时不应进入提交。
- Stage916：`phase_d_order_boundary_static_audit_passed`，扫描 `26` 个 Phase D 文件，允许 `send_order` 引用 `2`，非授权引用 `0`，`order_api_called_count=0`。
- Stage912：`phase_d_acceptance_passed_fail_closed`，`passed=47`、`failed=0`，kill switch 恢复原始关闭状态，`order_api_called_count=0`。
- Stage903 最新 auto dry-run：`phase_d_controller_dry_run_blocked`，目标日 `2026-06-15`；Stage907 因只读快照 age `467.695709s` 自动刷新 production-live read-only，刷新成功；Stage260 仍 `skipped_position_mismatch_count=1`，Stage906 仍 `reconcile_divergent_fail_closed`，`order_api_called_count=0`。
- Stage921：`scheduler_template_dynamic_target_ready_fail_closed`，`block=0`、`warn=0`，`order_api_called_count=0`。
- Stage910：`controller_alive_fail_closed`，heartbeat age `8.733s`，kill switch 未启用，`order_api_called_count=0`。
- Stage913：`phase_d_completion_not_proven`，`passed=20`、`partial=3`、`incomplete=1`，新增 Stage926 后通过项增加到 `20`；未通过项仍为 `adapter/executor/execution_gate` partial 和 `reconcile` blocked，均源自真实账户 `MA609` 未对齐；`order_api_called_count=0`。

### 判断

- 过拟合反思：否。Stage926 只用固定 mock flat broker 快照验证无交易空跑语义，不改 C9 交易参数、信号或回测样本。
- 继续价值反思：是。无人值守系统不仅要会下单前阻断，还要会在无可执行订单时稳定空跑、保持心跳和对账；Stage926 证明该工程语义成立。
- 当前结论：Phase D 已新增“有意图 mock 路径”（Stage917）、“错误/有效恢复确认回归”（Stage925）和“对齐空跑路径”（Stage926）三类安全证据；但正式全自动仍未确认，因为真实 production-live broker 与 C9 shadow 仍未 `reconcile_aligned`。

## 2026-06-16 01:40 补充：Stage927 真实提交最终开关闸门

- 本次补充性质：补齐 Phase D “什么时候允许打开真实下单开关”的最终机器闸门；不是 C9 参数优化，不触发 A/B。
- 外部调研判断：自动交易风险控制资料继续支持把 pre-trade controls、持仓/委托限制、kill switch、心跳、调度、对账和上线前测试放在真实提交前；vn.py 的真实下单边界仍应集中在受控 adapter，而不是分散到 shadow/monitor/reconcile 脚本。
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage927_official_live_real_submit_arming_gate.py`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage912_official_live_phase_d_acceptance_suite.py`：新增 Stage927 fail-closed 验收项。
  - `examples/portfolio_backtesting/run_qmt_roll_stage913_official_live_phase_d_completion_audit.py`：新增 `real_submit_arming_gate` 完成度要求。
  - `examples/portfolio_backtesting/run_qmt_roll_stage916_official_live_order_boundary_static_audit.py`：纳入 Stage927 静态订单边界扫描。
- 新增参数：
  - Stage927 `--target-date`
  - Stage927 `--confirm-live-real`
- 修改参数：无
- 删除参数：无

### 新增执行证据

- Stage927：`real_submit_arming_blocked_fail_closed`，`blocking_failure_count=4`，`real_submit_permitted=0`，`auto_submit_permitted=0`，`env_real_submit_enabled=0`，`order_api_called_count=0`。
- Stage927 四个 blocker：
  - `completion_audit_proven`：Stage913 仍 `phase_d_completion_not_proven`。
  - `broker_shadow_reconcile_aligned`：Stage906 仍 `reconcile_divergent_fail_closed`，broker rows `1`、shadow rows `0`。
  - `no_unresolved_fail_closed_incident`：Stage923 仍 `phase_d_fail_closed_operator_attention_required`。
  - `account_recovery_not_required`：Stage924 仍 `account_recovery_ack_required_fail_closed`。
- Stage916：`phase_d_order_boundary_static_audit_passed`，扫描 `27` 个 Phase D 文件，允许 `send_order` 引用 `2`，非授权引用 `0`，`order_api_called_count=0`。
- Stage912：`phase_d_acceptance_passed_fail_closed`，`passed=51`、`failed=0`，kill switch 原始和恢复状态均为关闭，`order_api_called_count=0`。
- Stage903 最新 auto dry-run：目标日由 Stage922 解析为 `2026-06-15`，`phase_d_controller_dry_run_blocked`；Stage907 因只读快照 age `97.320639s` 未过期自动降为 `plan-only`；Stage260 `executable_count=0`、`skipped_position_mismatch_count=1`；Stage906 `reconcile_divergent_fail_closed`；Stage923/924 仍要求人工处理；`order_api_called_count=0`。
- Stage921：`scheduler_template_dynamic_target_ready_fail_closed`，`target_date_mode=latest_completed_resolver`，`shadow_refresh_mode=auto`，`readonly_refresh_mode=auto`，`poll_seconds=30`，`block=0`、`warn=0`，`order_api_called_count=0`。
- Stage910：`controller_alive_fail_closed`，controller 状态 `phase_d_controller_dry_run_blocked`，heartbeat age `6.658s`，kill switch 未启用，`order_api_called_count=0`。
- Stage913：`phase_d_completion_not_proven`，`passed=21`、`partial=3`、`incomplete=1`，新增 Stage927 后通过项增加到 `21`；未通过项仍为 `adapter/executor/execution_gate` partial 和 `reconcile` blocked，均源自真实账户 `MA609` 未对齐；`order_api_called_count=0`。

### 判断

- 过拟合反思：否。Stage927 只聚合既有执行证据，检查 real-submit env、确认文本、completion、reconcile、incident、recovery、scheduler、heartbeat 和静态边界，不改 C9 信号、参数、品种、方向、R 倍数、样本或回测结果。
- 继续价值反思：是，但继续写更多“放行前控制面”脚本的边际价值已经下降。现在真正的价值在于解决真实账户状态：确认 `MA609.CZCE` broker 多 `10` 手的来源，人工平/减/隔离并刷新只读快照，或明确作为非策略仓位后保持 C9 自动提交禁用。
- 当前结论：全自动架构已经具备信号、调度、read-only refresh、dry-run controller、盘中 monitor、executor、reconcile、incident、recovery、ack suite、aligned idle、kill switch、heartbeat、静态 order boundary 和最终 real-submit arming gate；但“可全自动真实下单”仍未确认。没有 Stage906 `reconcile_aligned` 和 Stage927 `real_submit_arming_ready_requires_explicit_enable`/`real_submit_arming_permitted_ready` 前，必须继续 fail-closed，禁止真实订单。

## 2026-06-16 11:40 补充：开盘后真实账户已平仓，Phase D 证据链进入可武装但需显式启用状态

- 本次补充性质：开盘阶段 production-live 只读复核与 Phase D 全链路验收；不是 C9 参数优化，不触发 A/B。
- 外部调研判断：沿用前序 vn.py/FIA/CFTC 自动交易执行控制结论；本次重点不是新增 alpha，而是验证真实账户成交后，自动化控制面能否从 fail-closed 恢复到可审计的 no-action idle 状态。
- 新增脚本：无。
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`：修正 `blocking_failure_count=0` 被 `or 999` 误判为 blocked；将 Stage260 空仓跳过且无 mismatch、无 blocker、无订单 API 调用的状态归类为 no-action idle；将 Stage908 `adapter_contract_no_intents_idle` 纳入通过路径。
  - `examples/portfolio_backtesting/run_qmt_roll_stage906_official_live_reconciliation_worker.py`：按最终订单状态折叠同一 `vt_orderid/orderid` 的多条状态回报，避免中间态 `Submitting/Part Traded` 被误判为 active order。
  - `examples/portfolio_backtesting/run_qmt_roll_stage908_official_live_submit_adapter_contract.py`：新增无可执行 intent 的 idle 语义，避免 no-action 周期误报 adapter blocked。
  - `examples/portfolio_backtesting/run_qmt_roll_stage913_official_live_phase_d_completion_audit.py`：认可 no-intents idle adapter 证据。
  - `examples/portfolio_backtesting/run_qmt_roll_stage920_official_live_account_sync_gate.py`：支持 Stage919 空 attribution 但 summary 已对齐时判定 aligned，修复空表 `fillna` 类型问题。
  - `examples/portfolio_backtesting/run_qmt_roll_stage925_official_live_account_recovery_ack_suite.py`：已对齐状态下 invalid ack 不再要求 fail-closed；有差异时仍必须 fail-closed。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

### 开盘只读复核证据

- 我没有发真实单；全程未设置 `OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED`，未传 `--confirm-live-real`。
- production-live 只读刷新显示：
  - `MA609.CZCE` 持仓行仍存在，但 `volume=0`，账户已确认空仓。
  - 订单 `17_-1727097214_110`：`MA609.CZCE Short Close`，价格 `2741.0`，数量 `10`，最终状态 `All Traded`。
  - 成交回报：`5 + 3 + 1 + 1 = 10` 手，时间均为 `2026-06-16T09:05:38+08:00`。
- Stage906：`reconcile_aligned`，shadow/broker position rows 均为 `0`，active broker order count 为 `0`，`order_api_called_count=0`。
- Stage918：`reconcile_policy_aligned_no_action`。
- Stage919：`reconcile_attribution_aligned`。
- Stage920：`account_sync_aligned_auto_progress_allowed`，fingerprint `339264c636f6a5b8defeb5c17c23d4107f8acb1ab6c467cc53705f7c99ae86c7`。

### 最新 Phase D 全链路结果

- Stage903：`phase_d_controller_dry_run_ready_real_disabled`，目标日 `2026-06-15`，latest-completed resolver 正常，production-live read-only refresh 自动执行并成功；Stage260 `executable_count=0`、`skipped_flat_count=1`、`skipped_position_mismatch_count=0`；Stage905 `executor_no_intents`；Stage908 `adapter_contract_no_intents_idle`；`order_api_called_count=0`。
- Stage912：`phase_d_acceptance_passed_fail_closed`，`passed=51`、`failed=0`，kill switch 原始和恢复状态均为关闭，`order_api_called_count=0`。
- Stage913：`phase_d_completion_proven`，`passed=25`、`partial=0`、`incomplete=0`，`order_api_called_count=0`。
- Stage921：`scheduler_template_dynamic_target_ready_fail_closed`，latest-completed 动态目标日、auto shadow、auto readonly、`poll_seconds=30` 均通过，`block=0`、`warn=0`。
- Stage910：`controller_alive_ready`，controller 状态 `phase_d_controller_dry_run_ready_real_disabled`，heartbeat age `9.186s`，kill switch 未启用。
- Stage927：`real_submit_arming_ready_requires_explicit_enable`，`evidence_blocker_count_before_env=0`，但 `env_real_submit_enabled=0`、`confirm_live_real_ok=0`，所以 `real_submit_permitted=0`、`auto_submit_permitted=0`。
- Stage916：`phase_d_order_boundary_static_audit_passed`，扫描 `27` 个 Phase D 文件，允许 `send_order` 引用 `2`，非授权引用 `0`。
- 代码卫生：`py_compile` 通过，`git diff --check` 通过；未发现残留 Stage9/CTP/vnpy 相关 Python 进程。

### 回测/执行指标

- 本次无新增历史回测；策略收益指标不变，沿用 Stage901 2026 YTD shadow：
  - 期末权益：`264,540`
  - 总收益：`-11.82%`
  - 最大回撤：`-15.2224%`
  - Sharpe：`-1.1786`
  - 总滑点：`3,980`
  - 总交易次数：`28`
  - 非零日胜率：`44.4444%`
- 本次新增的是执行证据，不是收益提升证据。

### 判断

- 过拟合反思：否。所有改动只修执行状态机、对账归类和验收预期，不改 C9 信号、止损、仓位、品种、方向、R 倍数或历史样本。
- 继续价值反思：是，但后续价值重心已经从继续堆闸门转为最小真实 adapter 启用流程。当前证据已经证明 dry-run 全自动链路可跑通，且真实提交前最终闸门会阻止无确认发单。
- 当前结论：Phase D 已达到“全自动 dry-run + 真实提交可武装但需显式启用”的状态。要进入真实无人值守，还必须由操作者明确打开 real-submit env 并传入确认文本；在此之前系统正确行为是自动计算、只读刷新、对账、心跳、调度和验收全部运行，但真实发单保持 `0`。
