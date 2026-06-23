# Stage157 权威分钟 feature table builder 空跑

- 时间：2026-06-21 00:29 CST
- line_id：`futures_trend_c9_minrisk_highquality`
- 脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage157_authoritative_minute_feature_builder_empty_run.py`
- 输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage157_authoritative_minute_feature_builder_empty_run/`
- 决策：`stage157_authoritative_minute_feature_builder_empty_run_blocks_no_data_no_rule`
- 是否重要突破版本：否。本阶段是 feature table builder 的点时化空跑合同，不是收益候选。

## 本次调研和判断结论

外部参考：

- pandas `DataFrame.rolling` 官方文档：滚动窗口有明确的窗口边界、`closed` 语义和最小样本约束。
- pandas `merge_asof` 官方文档：`direction="backward"` 只取左表时点之前或等于的右表记录，适合点时化绑定。
- sklearn `TimeSeriesSplit` 官方文档：时间序列交叉验证不能用未来样本训练过去样本。
- sklearn data leakage 文档：任何预处理、特征筛选、标准化、模型选择都不能把测试/未来信息用于训练或构建。

判断：Stage157 只应该验证 builder 的点时化与空跑阻断，不应该继续在无真实分钟数据时发明规则。所有 feature row 必须来自 Stage153/156 全通过后的真实授权 1m OHLCV+OI；否则哪怕公式正确，也必须输出 0 行研究特征。

## 本次版本改动

新增：

- `stage157_authoritative_minute_feature_builder_empty_run.py`
- `feature_table_schema`：33 个未来 feature table 字段，含 provenance、时间戳、10 个 feature 及 ready flags。
- `build_plan`：10 个 Stage156 feature 的逐项 readiness 计划。
- `empty_run_audit`：657 个 required windows 的空跑阻断原因。
- `point_in_time_unit_selftest`：4 条内存级单元自测，验证 trailing features 不受未来 bar mutation 影响、短历史会阻断、feature 数量匹配合同、fixture 不提升为研究表。
- 5 张视觉图：官方资金路径 + builder 状态、build plan readiness、empty-run blocker、unit selftest、gate matrix。

修改：

- 无正式配置修改。
- 无策略规则修改。
- 无 true engine 修改。
- 无 A/B 修改。

删除：

- 无。

## 新增参数

这些不是交易参数，只是 builder 合同字段：

- `feature_table_schema_column_count=33`
- `build_plan_feature_count=10`
- `unit_selftest_count=4`

## 修改参数

无。

## 删除参数

无。

## 回测和指标

本阶段没有运行新回测、没有创建候选、没有进入 true engine。以下为沿用 Stage153 官方路径资金曲线的审计指标，用于每阶段视觉跟踪，不代表 Stage157 产生收益改进：

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- max broker10 margin/equity：`111.7365%`

新增结果：

- `stage153_request_count=233`
- `stage153_request_ready_count=0`
- `stage153_required_window_count=657`
- `stage153_window_coverage_pass_count=0`
- `stage156_feature_contract_count=10`
- `stage156_leakage_guard_pass_count=9`
- `feature_table_schema_column_count=33`
- `build_plan_ready_feature_count=0`
- `build_plan_blocked_feature_count=10`
- `empty_run_window_count=657`
- `empty_run_blocked_window_count=657`
- `feature_table_row_written_count=0`
- `feature_table_file_written=0`
- `unit_selftest_pass_count=4/4`
- `strategy_rule_created=0`
- `true_engine_run=0`
- `ab_triggered=0`
- `current_package_promotion_allowed=0`
- `strategy_feature_usable=0`

修改结果：

- 无。

删除结果：

- 无。

## 视觉分析

已生成并检查 5 张图均非空：

- `qmt_roll_stage157_c9_minrisk_authoritative_minute_feature_builder_empty_run_official_path_builder_empty_run_status_stage157_authoritative_minute_feature_builder_empty_run_v1.png`
- `qmt_roll_stage157_c9_minrisk_authoritative_minute_feature_builder_empty_run_build_plan_readiness_matrix_stage157_authoritative_minute_feature_builder_empty_run_v1.png`
- `qmt_roll_stage157_c9_minrisk_authoritative_minute_feature_builder_empty_run_empty_run_blocker_bar_stage157_authoritative_minute_feature_builder_empty_run_v1.png`
- `qmt_roll_stage157_c9_minrisk_authoritative_minute_feature_builder_empty_run_unit_selftest_matrix_stage157_authoritative_minute_feature_builder_empty_run_v1.png`
- `qmt_roll_stage157_c9_minrisk_authoritative_minute_feature_builder_empty_run_gate_status_matrix_stage157_authoritative_minute_feature_builder_empty_run_v1.png`

视觉结论：

- 官方路径资金图仍只是基线可视化，Stage157 没有改变交易路径。
- build plan 图显示 10 个 feature 全部有合同，但 `ready_window_count=0`。
- empty-run blocker 图显示 657 个窗口全部被 `missing_authoritative_request_package` 阻断。
- unit selftest 图显示 4/4 通过，尤其未来 bar 被改大后 trailing feature 不变。
- gate matrix 显示合同/自测通过，数据和窗口覆盖 hard gate 失败，策略/engine/A/B 全锁住。

## 过拟合反思

开始前判断：不是过拟合。原因是本轮不做收益优化、不调阈值、不使用 right-tail/bottom-loss 标签，只做 feature table builder 的点时化约束。

完成后判断：仍不是过拟合。虽然内存级 fixture 测了公式，但 fixture 没有写成研究 feature table；正式输出仍是 0 行 feature。当前阶段只证明“未来数据不能泄漏”和“无真实数据不生成样本”，没有对历史结果做任何拟合。

## 是否还有价值继续

开始前判断：有价值。Stage156 固定了 feature 合同，但还需要一个 builder 空跑来证明未来真实数据到达后不会因为工程路径把空数据、fixture 或未来 bar 泄漏进研究样本。

完成后判断：仍有价值，但继续方向必须更克制。Stage157 已经把 no-data builder 阻断链路建好；继续若还没有真实授权数据，应优先做 Stage158 的真实到货前 release checklist / hash-to-feature lineage 审计，或者等待真实 `incoming/stage152_authoritative_minute_ohlcv/...` 到货后重跑 Stage153/156/157。不能在 0 ready windows 上继续造分钟策略规则。

## TODO

1. 真实授权 raw/proof/normalized 到货后，先重跑 Stage153。
2. Stage153 全通过后，重跑 Stage156 和 Stage157，确认 feature row 只来自 `bar_end_ts <= decision_ts` 的闭合 bar。
3. 若进入 Stage158，优先做 hash/proof/feature-row lineage，证明每一行 feature 都能回溯到 raw_sha256、normalized_sha256、request_id、window_id。
4. 继续禁止 threshold search、product/year patch、right-tail/bottom-loss 标签、post-event 标签和数据 ready/missing 交易化。
