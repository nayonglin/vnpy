# Stage267 外部数据双路线统一验收闸门

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-22 17:20 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读双路线外部数据验收 orchestrator；不创建策略规则
- 是否重要突破：否，属于验收链合流与防误触发闸门
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Great Expectations Checkpoint：https://docs.greatexpectations.io/docs/0.18/reference/learn/terms/checkpoint/
  - Dagster Asset Checks：https://docs.dagster.io/guides/test/asset-checks
  - Apache Airflow Sensors：https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/sensors.html
  - dbt Data Tests：https://docs.getdbt.com/docs/build/data-tests
- 我的判断：数据验收应分成“到货检测”和“质量验证/下游放行”两层。文件到货只是必要条件，不是策略证据；只有 Stage265/266 validator 接受后，才允许进入 Stage260 或 Stage112/113/141。Stage267 的正确形状是统一 acceptance orchestrator，而不是继续新增交易规则或阈值。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage267_external_data_acceptance_orchestrator.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增 route-level orchestrator 账本和下游 gate cascade
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage251 官方 A 臂 `2018-01-02` 至 `2026-06-15`
- 账户规模：沿用官方 A 臂 15 万口径
- 成本口径：沿用 Stage251 官方 A 臂
- 样本过滤：无新增交易样本；聚合 Stage263 route contract、Stage264 inbox monitor、Stage265 replay validator、Stage266 W0 validator
- 策略/归因口径：不创建策略规则、不运行 true engine、不触发 A/B、不连接 CTP/SimNow、不调用 order API

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - `decision=stage267_external_acceptance_orchestrator_no_accepted_package_no_rule`
  - external_route_count `2`
  - contract_packet_ready_route_count `2/2`
  - accepted_route_count `0/2`
  - strategy_rule_allowed_route_count `0/2`
  - true_engine_allowed_route_count `0/2`
  - local_minute_missing_count `0`
  - coverage debt rows `5`
  - external_missing_unit_total `746`，拆分为 W0 required_window `485`、W0 request `41`、execution replay entry_decision `219`、accepted_same_source_replay_file `1`
  - cascade gate `2/14`，只通过两条路线的 contract packet；inbox package detected、validator accepted、coverage ready、downstream release、Stage141 promotion、strategy rule 全未通过
  - false positive rejection ledger `7` 类：minute OHLCV/OI only、smoke/dry-run、read-only account、adapter/pending order、ordinary backtest ledger、partial external package、manual spreadsheet/screenshot
  - 视觉文件 `6` 张，像素方差检查全部非空

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage267_external_data_acceptance_orchestrator/qmt_roll_stage267_c9_minrisk_external_data_acceptance_orchestrator_report_stage267_external_data_acceptance_orchestrator_v1.md`
- runbook：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage267_external_data_acceptance_orchestrator/qmt_roll_stage267_c9_minrisk_external_data_acceptance_orchestrator_ACCEPTANCE_RUNBOOK_stage267_external_data_acceptance_orchestrator_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage267_external_data_acceptance_orchestrator/qmt_roll_stage267_c9_minrisk_external_data_acceptance_orchestrator_summary_stage267_external_data_acceptance_orchestrator_v1.csv`
- route status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage267_external_data_acceptance_orchestrator/qmt_roll_stage267_c9_minrisk_external_data_acceptance_orchestrator_route_acceptance_status_stage267_external_data_acceptance_orchestrator_v1.csv`
- coverage debt：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage267_external_data_acceptance_orchestrator/qmt_roll_stage267_c9_minrisk_external_data_acceptance_orchestrator_coverage_debt_ledger_stage267_external_data_acceptance_orchestrator_v1.csv`
- downstream gate cascade：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage267_external_data_acceptance_orchestrator/qmt_roll_stage267_c9_minrisk_external_data_acceptance_orchestrator_downstream_gate_cascade_stage267_external_data_acceptance_orchestrator_v1.csv`
- false positive rejection：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage267_external_data_acceptance_orchestrator/qmt_roll_stage267_c9_minrisk_external_data_acceptance_orchestrator_false_positive_rejection_ledger_stage267_external_data_acceptance_orchestrator_v1.csv`
- quality：6 张 PNG，分别覆盖官方资金路径、路线 acceptance heatmap、coverage debt、downstream gate cascade、false positive rejection、next action

## 结论

- 本阶段结论：Stage267 已把 Stage264/265/266 合成统一验收闸门。当前不是“还要继续补本地覆盖”，而是两条外部路线都没有 accepted package：W0 路线由 Stage266 阻断在 `no_authorized_w0_drop_root_or_files`，执行回放路线由 Stage265 阻断在 `no_broker_production_execution_replay_package`。
- 是否进入下一步：进入下一步只在真实包到货后触发。W0 accepted 后才允许 Stage112/113 intake 与 Stage141；replay accepted 后才允许 Stage260 field/source audit、tail atlas 与 Stage141。
- 下一步：当前唯一 allowed action 是 `if_no_packages_keep_stage264_265_266_monitoring`，不得恢复本地 OHLCV/OI、价量/OI 小组合或普通 backtest ledger 作为策略证据。

## 过拟合反思

- 运行前判断：不是过拟合，因为本阶段只做数据质量 orchestration，不改交易规则。
- 运行后判断：仍不是过拟合，因为输出只由预先定义的 route contract、inbox monitor 和 validator gate 组成，没有按收益、年份、品种、方向或阈值选择。
- 原因：Stage267 的作用是阻断假阳性数据进入策略层；它不会提高历史表现，也不会生成候选策略。

## 继续价值反思

- 运行前判断：有价值，因为 Stage265/266 分别验收两条路线，但缺一个统一“能不能放行下游”的总闸门。
- 运行后判断：有价值但接近本地可做事项上限。当前能本地继续做的只剩监控和验收复跑；真正目标推进依赖真实 W0 或 broker/production replay 包到货。
- 原因：统一闸门减少误操作风险；但没有外部数据，不能凭空证明高质量分钟入退场信号。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage267 摘要。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选、跨线合并或路线废弃。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段为当前线日常验收工具合流。
