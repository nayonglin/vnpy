# Stage158 权威分钟 feature row lineage 审计

- 时间：2026-06-21 00:37 CST
- line_id：`futures_trend_c9_minrisk_highquality`
- 脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage158_authoritative_minute_feature_lineage_audit.py`
- 输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage158_authoritative_minute_feature_lineage_audit/`
- 决策：`stage158_authoritative_minute_feature_lineage_audit_blocks_no_data_no_rule`
- 是否重要突破版本：否。本阶段是 raw/proof/normalized/window 到 feature row 的血缘合同，不是收益候选。

## 本次调研和判断结论

外部参考：

- W3C PROV-DM：用 entity、activity、agent 以及 `used`、`wasGeneratedBy`、`wasDerivedFrom`、`wasAssociatedWith` 描述数据来源和责任链。
- NIST FIPS 180-4：SHA-256 可用于文件摘要和篡改检测，但 hash 只证明字节一致，不证明市场真实性。
- Apache Parquet concepts：Parquet 文件由 row group、column chunk、page 构成；未来 normalized parquet 的 row-group metadata 也应纳入 lineage。
- Apache Arrow `RowGroupMetaData`：可读取 row group 行数、列数、排序列等 metadata，用于真实 parquet 到货后的 lineage 摘要。

判断：Stage158 不应生成 feature table 或策略规则，而应规定未来每一行 feature 必须能回溯到 `request_id/window_id/proof_sha256/raw_sha256/normalized_sha256/proof_schema_sha256/feature_schema_sha256/feature_cutoff_ts`。这是防过拟合和防数据污染的基础工程，不是 alpha 研究。

## 本次版本改动

新增：

- `stage158_authoritative_minute_feature_lineage_audit.py`
- `prov_lineage_contract`：16 条 PROV 风格 lineage 合同。
- `feature_row_lineage_schema`：39 个 future feature row lineage 字段，且已校验无重复字段。
- `empty_lineage_audit`：657 个 required windows 的 lineage 空跑审计。
- `lineage_unit_selftest`：5 条内存级单元自测，覆盖完整 lineage、raw 篡改、normalized 篡改、缺 proof 阻断、unit lineage 不提升为 feature table。
- 5 张视觉图：官方资金路径 + lineage 状态、lineage contract/schema、empty lineage blocker、selftest、gate matrix。

修改：

- 无正式配置修改。
- 无策略规则修改。
- 无 true engine 修改。
- 无 A/B 修改。

删除：

- 无。

## 新增参数

这些不是交易参数，只是 lineage 合同字段：

- `prov_lineage_contract_count=16`
- `feature_row_lineage_schema_column_count=39`
- `lineage_selftest_count=5`

## 修改参数

无。

## 删除参数

无。

## 回测和指标

本阶段没有运行新回测、没有创建候选、没有进入 true engine。以下为沿用 Stage153 官方路径资金曲线的审计指标，用于每阶段视觉跟踪，不代表 Stage158 产生收益改进：

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
- `stage157_feature_table_schema_column_count=33`
- `stage157_feature_table_row_written_count=0`
- `prov_lineage_contract_count=16`
- `feature_row_lineage_schema_column_count=39`
- `feature_schema_sha256_present=1`
- `feature_build_plan_sha256_present=1`
- `proof_schema_sha256_present=1`
- `proof_schema_file_sha256_present=1`
- `lineage_audit_window_count=657`
- `lineage_pass_window_count=0`
- `lineage_blocked_window_count=657`
- `lineage_selftest_pass_count=5/5`
- `feature_table_file_written=0`
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

- `qmt_roll_stage158_c9_minrisk_authoritative_minute_feature_lineage_audit_official_path_lineage_status_stage158_authoritative_minute_feature_lineage_audit_v1.png`
- `qmt_roll_stage158_c9_minrisk_authoritative_minute_feature_lineage_audit_lineage_contract_matrix_stage158_authoritative_minute_feature_lineage_audit_v1.png`
- `qmt_roll_stage158_c9_minrisk_authoritative_minute_feature_lineage_audit_empty_lineage_blocker_bar_stage158_authoritative_minute_feature_lineage_audit_v1.png`
- `qmt_roll_stage158_c9_minrisk_authoritative_minute_feature_lineage_audit_lineage_selftest_matrix_stage158_authoritative_minute_feature_lineage_audit_v1.png`
- `qmt_roll_stage158_c9_minrisk_authoritative_minute_feature_lineage_audit_gate_status_matrix_stage158_authoritative_minute_feature_lineage_audit_v1.png`

视觉结论：

- 官方路径资金图仍只是基线可视化，Stage158 没有改变交易路径。
- lineage contract 图显示 entity/activity/agent 与 schema 字段已覆盖。
- blocker 图显示 657 个窗口全部因 `missing_authoritative_request_package` 被阻断。
- selftest 图显示 5/5 通过，raw 与 normalized bytes 改动均能被 hash 检出，缺 proof 会阻断。
- gate matrix 显示输入/合同/自测通过，数据、覆盖、lineage pass hard gate 失败，策略/engine/A/B 全锁住。

## 过拟合反思

开始前判断：不是过拟合。原因是本轮不做收益优化、不调阈值、不使用标签，只做 feature row 的来源可追溯合同。

完成后判断：仍不是过拟合。Stage158 没有生成 feature table，更没有跑策略；内存 selftest 只验证 hash/lineage 机制，不参与研究样本。所有真实窗口仍被阻断在 `missing_authoritative_request_package`，没有任何空数据或 fixture 被转成可研究特征。

## 是否还有价值继续

开始前判断：有价值。Stage157 固定了 builder 空跑，但未来真实数据到货后仍需要证明每一行 feature 能回溯到 proof/raw/normalized/window，防止“看似有特征，实则无来源”的污染。

完成后判断：仍有价值，但继续方向应保持在数据链路或等待真实数据。Stage158 已把 hash/proof/feature-row lineage 固定住；下一步如果真实数据未到，最多做 Stage159 的 operator release checklist / lineage runbook，不应继续制造策略规则。如果真实授权 1m OHLCV+OI 到货，应重跑 Stage153/156/157/158，再考虑只读 feature atlas。

## TODO

1. 真实授权 raw/proof/normalized 到货后，先重跑 Stage153，再重跑 Stage156/157/158。
2. Stage158 通过后，未来每一行 feature 都必须附带 `feature_row_id`、`request_id`、`window_id`、`proof_sha256`、`source_raw_sha256`、`source_normalized_sha256`、`feature_cutoff_ts`。
3. 若进入 Stage159，优先做 operator release checklist / lineage runbook，明确真实数据到货后的命令顺序和失败原因。
4. 继续禁止 threshold search、product/year patch、right-tail/bottom-loss 标签、post-event 标签和数据 ready/missing 交易化。
