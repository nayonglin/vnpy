# Stage180 cutoff-filtered predecision 安全源

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 04:35 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：点时化安全源派生，不是 feature table
- 是否重要突破：否，属于泄漏阻断后的安全源准备
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：pandas window endpoint 语义、vn.py tick/bar 聚合语义、Stage179 direct-file leakage audit。
- 我的判断：后续 feature builder 只能读取已经裁剪到 `bar_end_ts <= decision_ts` 的安全源；直接读 Stage178 normalized 文件会留下未来 bar 风险。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage180_cutoff_filtered_predecision_feature_source.py`
- 新增输出：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage180_cutoff_filtered_predecision_feature_source/filtered_sources/`
- 新增参数：`filter_expression=same vt_symbol AND extension_start_ts <= bar_end_ts <= decision_ts`
- 修改/删除参数：无

## 回测/归因参数

- 数据区间：Stage179 filtered-ready 的 `4` 个请求
- 样本过滤：只接受 Stage179 `stage179_filtered_ready=1`；不按收益/亏损筛选
- 策略/归因口径：只写 cutoff-filtered source parquet 与 lineage；不写 feature table、不创建策略规则

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage180_cutoff_filtered_predecision_source_ready_no_feature_table_no_rule`
  - `filtered_source_written_count=4`
  - `cutoff_filtered_source_ready_count=4`
  - `filtered_source_row_count=11882`
  - `filtered_positive_volume_row_count=11882`
  - `post_decision_removed_count=3`
  - `lineage_pass_count=4`
  - `feature_table_row_written_count=0`
  - `strategy_rule_created=0`
  - `true_engine_run=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage180_cutoff_filtered_predecision_feature_source/qmt_roll_stage180_c9_minrisk_cutoff_filtered_predecision_feature_source_report_stage180_cutoff_filtered_predecision_feature_source_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage180_cutoff_filtered_predecision_feature_source/qmt_roll_stage180_c9_minrisk_cutoff_filtered_predecision_feature_source_summary_stage180_cutoff_filtered_predecision_feature_source_v1.csv`
- quality：filtered source manifest、lineage、gate CSV 与 5 张 PNG
- filtered parquet：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage180_cutoff_filtered_predecision_feature_source/filtered_sources/`

## 结论

- 本阶段结论：4 个 cutoff-filtered 安全源均 ready，3 根 post-decision tail 已剔除，后续 Stage181 可在这 4 个源上材料化 Stage156 特征并做 lineage。
- 是否进入下一步：是
- 下一步：Stage181 只在 Stage180 安全源上材料化 feature rows；仍不允许策略规则、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。只做时间边界裁剪，不用收益结果。
- 运行后判断：否。Stage180 把 Stage179 发现的未来 bar 物理剔除，没有改变任何交易阈值。
- 原因：这是防泄漏基础设施，不是 alpha 挖掘。

## 继续价值反思

- 运行前判断：是。没有安全源，feature builder 容易误读 direct file。
- 运行后判断：是。已得到 `4` 个可追溯、cutoff-filtered 的前置分钟源，下一步可以小样本材料化特征并检查图形。
- 原因：这让“分钟级高质量信号”第一次接近可点时化特征输入。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
