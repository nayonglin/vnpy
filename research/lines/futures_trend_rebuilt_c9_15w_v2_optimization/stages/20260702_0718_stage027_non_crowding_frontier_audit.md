# Stage027 非挤占结构候选前沿审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`day`
- 记录时间：2026-07-02 07:13 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读证据矩阵/路线选择
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：managed futures/trend following diversification、pysystemtrade capital correction、Hudson & Thames meta-labeling。
- 我的判断：当前最应该避免在同一批 AI 质量字段、rounding、权重和冷启动参数上救参；应把下一阶段限定为结构前沿或新 PIT 信息源。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage027_non_crowding_frontier_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；仅新增只读审计常量 `BASELINE_NEGATIVE_COUNT=330947`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用已冻结 Stage013/017/021/022/026/074/075/077/081 输出。
- 账户规模：复用各阶段原口径；本阶段不重新回测。
- 成本口径：复用各阶段原口径；本阶段不新增成本假设。
- 样本过滤：只读各阶段已输出的候选前沿。
- 策略/归因口径：统一比较严格 `>1` 年负窗口、到终点负窗口、收益保留和失败原因。

## 结果

- 期末权益：不适用，本阶段未回测。
- 总收益：不适用，本阶段未回测。
- 最大回撤：不适用，本阶段未回测。
- Sharpe：不适用，本阶段未回测。
- 总滑点：不适用，本阶段未回测。
- 总交易次数：不适用，本阶段未回测。
- 胜率：不适用，本阶段未回测。
- 其他关键指标：promoted_candidate_count `0`；frontier_signal_count `1`；best_next_direction `xsmom_confirmation_true_engine_or_new_pit_source`。

## 前沿表摘要

| stage    | variant                                                       | structure_family               | frontier_status   |   all_gt1y_negative_count |   to_final_negative_count |   min_retention |
|:---------|:--------------------------------------------------------------|:-------------------------------|:------------------|--------------------------:|--------------------------:|----------------:|
| Stage013 | stage013_guarded_quality_add_risk_proxy                       | ai_quality_add_risk            | diagnostic_only   |                    232390 |                         0 |       0.0698205 |
| Stage017 | best_non_c9_fixed_sleeve_blend                                | fixed_official_c9_blend        | diagnostic_only   |                    246495 |                       nan |       0.287259  |
| Stage021 | c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps                   | independent_sleeve             | diagnostic_only   |                    267868 |                         0 |       1.00048   |
| Stage074 | full_market_ai_top8_and_active_positions_lt3_cold_start_ramp  | cold_start_account_outer_layer | diagnostic_only   |                    304693 |                         0 |       0.365071  |
| Stage075 | full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | staggered_account_outer_layer  | diagnostic_only   |                    325602 |                         0 |     nan         |
| Stage022 | stage022_stage013_guarded_quality_xsmom12_not_opposed         | xsmom_confirmation             | frontier_signal   |                    231382 |                         0 |       1.08276   |
| Stage026 | stage026_engine                                               | ai_quality_add_risk            | reject            |                    394418 |                        24 |       0.747648  |
| Stage077 | jd_ai_top8_independent                                        | jd_independent_sleeve          | reject            |                       nan |                       nan |     nan         |
| Stage081 | account_injured_and_member_position_flow_aligned              | member_rank_external_pit       | reject            |                       nan |                       nan |     nan         |

## 结构族摘要

| structure_family               |   candidate_count |   dense_goal_count |   frontier_signal_count |   reject_count |   best_negative_count |   best_min_return_pct |   best_min_retention |
|:-------------------------------|------------------:|-------------------:|------------------------:|---------------:|----------------------:|----------------------:|---------------------:|
| xsmom_confirmation             |                 1 |                  1 |                       1 |              0 |                231382 |              -40.5376 |             1.08276  |
| ai_quality_add_risk            |                 2 |                  2 |                       0 |              1 |                232390 |              -40.5376 |             0.747648 |
| fixed_official_c9_blend        |                 1 |                  1 |                       0 |              0 |                246495 |              -49.2029 |             0.287259 |
| independent_sleeve             |                 1 |                  1 |                       0 |              0 |                267868 |              -54.8603 |             1.00048  |
| cold_start_account_outer_layer |                 1 |                  1 |                       0 |              0 |                304693 |              -23.6338 |             0.365071 |
| staggered_account_outer_layer  |                 1 |                  1 |                       0 |              0 |                325602 |              -31.7355 |           nan        |
| jd_independent_sleeve          |                 1 |                  0 |                       0 |              1 |                   nan |              nan      |           nan        |
| member_rank_external_pit       |                 1 |                  0 |                       0 |              1 |                   nan |              nan      |           nan        |

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage027_non_crowding_frontier_audit/rebuilt_c9_v2_stage027_non_crowding_frontier_audit_report_stage027_non_crowding_frontier_audit_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage027_non_crowding_frontier_audit/rebuilt_c9_v2_stage027_non_crowding_frontier_audit_frontier_table_stage027_non_crowding_frontier_audit_v1.csv`
- orders：无
- daily：无
- quality：无

## 结论

- 本阶段结论：`stage027_no_candidate_promoted_use_frontier_for_next_hypothesis`；没有任何候选可直接晋级或接实盘。
- 是否进入下一步：是，但只沿 Stage022 的 xsmom 确认前沿做真引擎，或转新 PIT 信息源；不做参数救参。
- 下一步：`xsmom_confirmation_true_engine_or_new_pit_source`。

## 过拟合反思

- 运行前判断：否。本阶段只读冻结输出，不新增交易规则、不按坏窗口、品种、方向、月份调参。
- 运行后判断：否。结论来自统一前沿表；若把失败候选继续改成相邻阈值、权重、rank 或 rounding，就是过拟合。
- 原因：本阶段只读冻结输出；继续救失败候选的相邻参数才是过拟合。

## 继续价值反思

- 运行前判断：有。Stage026 后需要决定下一步研究战场，否则容易继续在同一批字段上救参。
- 运行后判断：有，但只应沿前沿信号进入真实引擎或新 PIT 源；当前没有任何候选可直接接实盘。
- 原因：Stage026 已经反证质量加风险真引擎，下一步需要换结构或换信息源。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage027 路线选择。
- 是否更新 `research/registry.md`：是，更新二期线最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破或正式候选。
