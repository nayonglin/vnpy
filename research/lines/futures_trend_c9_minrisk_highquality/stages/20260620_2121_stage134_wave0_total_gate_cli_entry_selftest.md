# Stage134 Stage133 CLI release verdict 自测

- line_id：futures_trend_c9_minrisk_highquality
- 当前模式：day
- 记录时间：2026-06-20 21:21 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：Stage133 真实到货 CLI 入口自测；不做策略 alpha，不做 true engine，不做 A/B
- 是否重要突破：否；这是 Stage133 总闸门的可执行入口补齐
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Great Expectations checkpoint CLI：https://legacy.017.docs.greatexpectations.io/docs/0.15.50/guides/validation/how_to_validate_data_by_running_a_checkpoint/
  - Dagster blocking asset checks：https://docs.dagster.io/guides/test/asset-checks
  - Dagster asset checks API：https://docs.dagster.io/api/dagster/asset-checks
  - dbt sources/source freshness：https://docs.getdbt.com/docs/build/sources
  - dbt source command：https://docs.getdbt.com/reference/commands/source
  - OpenLineage facets：https://openlineage.io/docs/spec/facets/
- 我的判断：真实 W0 到货入口应该像 checkpoint/source freshness/blocking asset check 一样，输出机器可读的 release verdict，并且在失败时阻断下游，而不是只给人工解释。Stage133 原本有默认审计，但缺一个真实 `--drop-dir` CLI；Stage134 的目标就是证明这个 CLI 可以复跑、可解析、可恢复默认状态。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage134_wave0_total_gate_cli_entry_selftest.py`
- 修改脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage133_wave0_total_intake_downstream_gate_audit.py`
- 删除脚本：无
- 新增参数：
  - Stage133 `--drop-dir <drop_dir>`
  - Stage133 `--case-id <case_id>`
  - Stage133 `--expected-stage112-intake {0,1}`
  - Stage133 `--expected-downstream-release {0,1}`
  - Stage133 summary 新增 `cli_mode`、`cli_case_id`、`expected_stage112_intake`、`expected_downstream_release`、`release_verdict`
- 修改参数：
  - Stage133 无参默认审计保持 Stage133 行为；CLI 模式改用 CLI-specific expectations，不再套用默认空 drop + fixture 双 case 预期
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage131/Stage045 官方背景曲线 2018-2026；Stage134 本身不新增交易
- 账户规模：沿用当前 C9 min-risk 线背景口径
- 成本口径：沿用 Stage131 背景统计，总滑点 `2,730,130`
- 样本过滤：
  - CLI 空 drop：`outputs/stage125_wave0_receipt_preflight_audit/empty_drop`
  - CLI Stage131 fixture：`outputs/stage131_wave0_positive_drop_supergate_audit/positive_drop/contract_positive_fixture_drop`
  - 默认恢复审计：Stage133 无参默认
- 策略/归因口径：CLI release verdict 自测；不允许进入分钟规则，不允许 true engine

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26,017.63%`
- 最大回撤：`-45.08%`
- Sharpe：`1.633`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.09%`
- 其他关键指标：
  - decision：`stage134_stage133_cli_entry_selftests_passed_no_real_data_no_strategy`
  - command_count：`3`
  - command_returncode_zero_count：`3`
  - stage133_cli_case_count：`2`
  - stage133_default_restore_pass：`1`
  - cli_expected_release_match_count：`2`
  - downstream_release_allowed_count：`0`
  - expectation_pass_count：`12/12`
  - real_w0_data_delivered：`0`
  - real_stage112_intake_allowed_now：`0`
  - true_engine_allowed：`0`
  - strategy_feature_usable：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage134_wave0_total_gate_cli_entry_selftest/qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_report_stage134_wave0_total_gate_cli_entry_selftest_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage134_wave0_total_gate_cli_entry_selftest/qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_summary_stage134_wave0_total_gate_cli_entry_selftest_v1.csv`
- orders：无；本阶段不生成订单
- daily：无新增交易 daily；资金曲线沿用背景审计序列
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage134_wave0_total_gate_cli_entry_selftest/qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_command_audit_stage134_wave0_total_gate_cli_entry_selftest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage134_wave0_total_gate_cli_entry_selftest/qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_expectation_audit_stage134_wave0_total_gate_cli_entry_selftest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage134_wave0_total_gate_cli_entry_selftest/qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_stage133_summary_snapshots_stage134_wave0_total_gate_cli_entry_selftest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage134_wave0_total_gate_cli_entry_selftest/qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_stage133_case_snapshots_stage134_wave0_total_gate_cli_entry_selftest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage134_wave0_total_gate_cli_entry_selftest/qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_official_path_cli_release_status_stage134_wave0_total_gate_cli_entry_selftest_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage134_wave0_total_gate_cli_entry_selftest/qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_command_matrix_stage134_wave0_total_gate_cli_entry_selftest_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage134_wave0_total_gate_cli_entry_selftest/qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_expectation_matrix_stage134_wave0_total_gate_cli_entry_selftest_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage134_wave0_total_gate_cli_entry_selftest/qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_case_release_matrix_stage134_wave0_total_gate_cli_entry_selftest_v1.png`

## 视觉检查

- 官方路径图：资金、回撤、broker10 曲线非空；CLI fixture/default 分支有 Stage128 ready 蓝柱，但 downstream release 绿柱全为 `0`，表示不能进入分钟研究。
- 命令矩阵：三个 Stage133 入口 returncode 全部为 `0`，stdout JSON 全部可解析。
- 预期矩阵：`12/12` 全绿，覆盖 CLI 空 drop、CLI fixture、默认恢复、JSON 输出和订单/CTP 零调用。
- case release 矩阵：fixture/default 的 Stage128 ready 为 `1`，但 Stage112 rule ready、Stage113 indexed、downstream release 均为 `0`。

## 结论

- 本阶段结论：Stage133 已具备真实到货 CLI release verdict 形态。命令示例：
  - `stage133_wave0_total_intake_downstream_gate_audit.py --drop-dir <real_w0_drop> --case-id real_w0_total_gate --expected-stage112-intake 1`
  - 若需要 CI/自测式硬断言，可加 `--expected-downstream-release 1`
- 是否进入下一步：是，但真实 W0 未到货前仍不得做分钟规则、true engine、A/B 或正式候选。
- 下一步：等真实 W0 drop 到货后直接跑 Stage133 CLI；若仍无真实数据，下一步可做 CLI 文档/README 和“真实到货目录结构 preflight”，不要从 Stage131 fixture 提取交易信息。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只把数据 release gate CLI 化，未调任何收益参数、未筛选交易样本、未从 fixture 中学习信号。`release_verdict` 是工程阻断，不是 alpha。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Stage133 如果只能默认审计，真实 W0 到货时仍可能靠人工拼命令和解释输出。Stage134 证明 CLI 可执行、可解析、可恢复默认状态，让真实到货后可以用一个 verdict 决定是否进入分钟级 K 线/盘口研究。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否；这不是新增研究线或跨线合入
- 是否追加根目录 `memory.md/back_log.md`：否；这不是正式候选、重大突破或跨线合并
