# Stage137 W0 watched inbox 触发边界自测

- line_id：futures_trend_c9_minrisk_highquality
- 当前模式：day
- 记录时间：2026-06-20 21:47 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：Stage136 到货监控的 synthetic trigger-boundary selftest；不做策略 alpha，不做 true engine，不做 A/B
- 是否重要突破：否；这是监控触发边界和防误触发自测
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - pytest tmp_path：https://docs.pytest.org/en/stable/how-to/tmp_path.html
  - Python tempfile：https://docs.python.org/3/library/tempfile.html
  - Dagster sensors / duplicate run keys：https://docs.dagster.io/guides/automate/sensors
  - Dagster schedules and sensors API：https://docs.dagster.io/api/dagster/schedules-sensors
  - watchdog API event queue：https://pythonhosted.org/watchdog/api.html
- 我的判断：Stage136 是监控入口，必须先证明它在“空目录、未知文件、部分合同文件、命名完整文件、禁用 fixture”这些边界上给出正确提示，而不是等真实 W0 到货时才发现误触发。自测应使用隔离 fixture 目录，不写真实候选目录，不调用 Stage125/133；这符合临时目录隔离、sensor run key/skip reason 和重复事件去重的工程原则。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage137_wave0_watch_inbox_trigger_selftest.py`
- 修改脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage137_wave0_watch_inbox_trigger_selftest.py` 内部修正 expectation 图的缺失字段显示，避免把不适用字段画成失败
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 新增机制：
  - 复用 Stage136 的 `_scan_candidate_dirs` 与 `_trigger_status`。
  - 在 `outputs/stage137_wave0_watch_inbox_trigger_selftest/fixture_drops/` 构造隔离合成目录。
  - 覆盖 5 类触发边界：empty、unknown-only changed、partial known file、complete name-only、Stage131 forbidden fixture。
  - 明确 `stage125_command_executed_count=0`、`stage133_command_executed_count=0`。

## 回测/归因参数

- 数据区间：沿用 Stage131/Stage045 官方背景曲线 2018-2026；Stage137 本身不新增交易
- 账户规模：沿用当前 C9 min-risk 线背景口径
- 成本口径：沿用 Stage131 背景统计，总滑点 `2,730,130`
- 样本过滤：无交易样本过滤；只使用 synthetic trigger selftest fixture
- 策略/归因口径：watched inbox monitor trigger selftest；不允许进入分钟规则，不允许 true engine

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26,017.63%`
- 最大回撤：`-45.08%`
- Sharpe：`1.633`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.09%`
- 其他关键指标：
  - decision：`stage137_wave0_watch_inbox_trigger_selftests_passed_no_real_data_no_strategy`
  - selftest_pass：`1`
  - case_count：`5`
  - case_pass_count：`5`
  - expectation_pass_count：`39/39`
  - empty_wait_pass：`1`
  - unknown_changed_wait_pass：`1`
  - partial_stage125_only_pass：`1`
  - complete_prompt_stage133_pass：`1`
  - forbidden_fixture_block_pass：`1`
  - synthetic_complete_known_file_count：`123`
  - synthetic_complete_request_role_complete_count：`41`
  - stage125_command_executed_count：`0`
  - stage133_command_executed_count：`0`
  - stage133_release_allowed_now：`0`
  - real_w0_data_delivered：`0`
  - real_stage112_intake_allowed_now：`0`
  - true_engine_allowed：`0`
  - strategy_feature_usable：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage137_wave0_watch_inbox_trigger_selftest/qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest_report_stage137_wave0_watch_inbox_trigger_selftest_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage137_wave0_watch_inbox_trigger_selftest/qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest_decision_stage137_wave0_watch_inbox_trigger_selftest_v1.json`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage137_wave0_watch_inbox_trigger_selftest/qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest_summary_stage137_wave0_watch_inbox_trigger_selftest_v1.csv`
- orders：无；本阶段不生成订单
- daily：无新增交易 daily；资金曲线沿用背景审计序列
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage137_wave0_watch_inbox_trigger_selftest/qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest_case_trigger_audit_stage137_wave0_watch_inbox_trigger_selftest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage137_wave0_watch_inbox_trigger_selftest/qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest_expectation_audit_stage137_wave0_watch_inbox_trigger_selftest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage137_wave0_watch_inbox_trigger_selftest/qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest_case_snapshot_rows_stage137_wave0_watch_inbox_trigger_selftest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage137_wave0_watch_inbox_trigger_selftest/qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest_case_role_progress_stage137_wave0_watch_inbox_trigger_selftest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage137_wave0_watch_inbox_trigger_selftest/qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest_official_path_selftest_status_stage137_wave0_watch_inbox_trigger_selftest_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage137_wave0_watch_inbox_trigger_selftest/qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest_case_trigger_matrix_stage137_wave0_watch_inbox_trigger_selftest_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage137_wave0_watch_inbox_trigger_selftest/qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest_case_role_completeness_matrix_stage137_wave0_watch_inbox_trigger_selftest_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage137_wave0_watch_inbox_trigger_selftest/qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest_expectation_matrix_stage137_wave0_watch_inbox_trigger_selftest_v1.png`

## 视觉检查

- 官方路径/selftest 状态图：资金、回撤、broker10 曲线非空；底部 `selftest_pass=1`、`case_count=5`、`case_pass_count=5`、`stage133_release_allowed_now=0`。
- case trigger matrix：empty 不触发；unknown-only 只显示 changed；partial 只触发 Stage125 candidate；complete name-only 显示 Stage125 + Stage133 prompt；forbidden fixture 只显示 forbidden block；5 个 case expectation 全通过。
- role completeness matrix：complete name-only 与 forbidden fixture 都有 `100%` role completeness，但 forbidden case 仍被禁止，说明“文件完整”不是 release 充分条件。
- expectation matrix：`39/39` 全绿；缺失/不适用字段不再被误画成失败。

## 结论

- 本阶段结论：Stage136 的到货监控触发边界通过隔离自测。部分合同文件只会提示先跑 Stage125；命名完整合成样本只会提示 Stage125 -> Stage133，不会直接 release；Stage131 fixture 即使文件完整也被 forbidden gate 阻断。
- 是否进入下一步：是，但仍只能做数据入口层工作。
- 下一步：可以把 Stage136 + Stage137 组合成无人值守 smoke：先跑 Stage137 自测，过了再跑 Stage136 默认监控；真实数据未到货前继续禁止分钟规则、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只测试监控器在合成文件边界上的工程行为，不读取交易盈亏标签，不调交易参数，不筛年份、品种、方向或窗口。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：如果监控触发边界不可靠，真实 W0 到货后可能半交付误触发或 fixture 误触发。Stage137 把这些失败模式前置自测，降低后续进入 Stage112/113 前的流程风险；这比继续旧分钟源挖规则更贴近“授权、点时、可复验”的目标。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否；这不是新增研究线或跨线合入
- 是否追加根目录 `memory.md/back_log.md`：否；这不是正式候选、重大突破或跨线合并
