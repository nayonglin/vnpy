# Stage179 predecision lookback 点时化独立验收

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 04:35 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage178 交付包 proof/hash/schema/point-in-time validator
- 是否重要突破：否，但发现并阻断 direct normalized file tail 泄漏风险
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：pandas rolling/window 端点语义、TqSdk 历史 tick 序列文档、vn.py bar 语义。
- 我的判断：即使 Stage178 自检通过，也不能直接把 normalized 文件交给 feature builder；必须独立检查 proof/hash/schema，并显式确认 `bar_end_ts <= decision_ts` 过滤后才可用。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage179_predecision_lookback_point_in_time_validator.py`
- 新增参数：`feature_cutoff_rule=bar_end_ts <= decision_ts`
- 修改/删除参数：无

## 回测/归因参数

- 数据区间：Stage178 写入的 `4` 个 Stage177 lookback 请求
- 样本过滤：只验收已存在 raw/normalized/proof 的请求；不按收益、年份、品种、方向筛选
- 策略/归因口径：只做文件/血缘/点时化验收；不写 feature table、不创建策略规则

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage179_point_in_time_validator_accepts_filtered_requests_blocks_direct_file_use_no_rule`
  - `present_triplet_count=4`
  - `proof_hash_schema_identity_ready_count=4`
  - `cutoff_filtered_coverage_pass_count=4/4`
  - `filtered_request_ready_count=4`
  - `direct_file_request_ready_count=1`
  - `post_decision_bar_count=3`
  - `feature_table_row_written_count=0`
  - `strategy_rule_created=0`
  - `true_engine_run=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage179_predecision_lookback_point_in_time_validator/qmt_roll_stage179_c9_minrisk_predecision_lookback_point_in_time_validator_report_stage179_predecision_lookback_point_in_time_validator_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage179_predecision_lookback_point_in_time_validator/qmt_roll_stage179_c9_minrisk_predecision_lookback_point_in_time_validator_summary_stage179_predecision_lookback_point_in_time_validator_v1.csv`
- quality：request/proof/normalized/window/gate CSV 与 5 张 PNG

## 结论

- 本阶段结论：4 个请求在 cutoff 过滤后全部可用，但 direct normalized file 只有 `1/4` 可直接用；另外 `3` 根 post-decision tail 必须被剔除。
- 是否进入下一步：是
- 下一步：Stage180 生成 cutoff-filtered 安全源或修 Stage178 为 end-exclusive；在此之前不得写 feature table。

## 过拟合反思

- 运行前判断：否。验收的是点时化与血缘，不看交易盈亏。
- 运行后判断：否。发现 direct file tail 后选择阻断直接使用，而不是为了推进特征表放宽。
- 原因：这一步强化了防泄漏纪律。

## 继续价值反思

- 运行前判断：是。Stage178 写入后必须有独立 validator。
- 运行后判断：是。Stage179 把可用性拆成 filtered-ready 和 direct-file-ready，避免后续无意泄漏。
- 原因：目标要求不能有任何过拟合和时间泄漏。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
