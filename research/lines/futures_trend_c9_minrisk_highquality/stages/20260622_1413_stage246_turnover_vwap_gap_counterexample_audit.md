# Stage246 turnover_vwap_gap_30m 反例图谱审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 14:13`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因、formal feature 反例 atlas、交易化前阻断
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Berkeley/Haas《The market impact of large trading orders》：大订单的价格冲击会改变策略真实收益，成交量/价格接受度需要放在执行成本和冲击语境下理解。<https://haas.berkeley.edu/wp-content/uploads/hiddenImpact13.pdf>
  - GitHub `vivek-v-rao/Intraday-Vol`：高频成交量、价格和波动通常作为估计器与执行分析输入，不应从单个分位直接生成方向规则。<https://github.com/vivek-v-rao/Intraday-Vol>
  - QuantInsti VWAP 教程：VWAP 主要是日内价格-成交量基准和执行参考，常被用于比较成交质量，而不是天然 alpha。<https://blog.quantinsti.com/vwap-strategy/>
  - FMZ/GitHub 公开 VWAP 策略示例：VWAP 偏离可构造策略，但高度依赖阈值、品种和时段，本阶段只借鉴“必须看反例和执行语境”的审计思路，不复制策略。<https://github.com/fmzquant/strategies>
- 我的判断：
  - `turnover_vwap_gap_30m` 的第一性含义是最后价格相对 30 根成交额推导 VWAP 的偏离，按交易方向对齐后更像“价格接受度/执行压力”。
  - 它可能解释行情是否被成交确认，但顺向偏离过大也可能是冲击、追价、末端跳变或低分辨率 artefact。
  - 因此 Stage246 只允许固定分位和反例 atlas，不允许把“站上 VWAP/顺向偏离 VWAP”写成入场质量规则。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage246_turnover_vwap_gap_counterexample_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定使用 `quality_quintile_aligned_turnover_vwap_gap_30m`，其中 Q5 代表交易方向上最强顺向 close-vs-VWAP gap。
  - 固定组：`q1_strong_adverse_gap`、`q2_mild_adverse_gap`、`q3_neutral_gap`、`q4_mild_favorable_gap`、`q5_strong_favorable_gap`、`favorable_gap_q4q5`、`adverse_gap_q1q2`。
  - 固定 atlas 类别：`q3_tail`、`q2_bad`、`q4_bad`、`q5_bad`、`favorable_gap_bad`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage239 joined signal-label audit，共 `219` 个事件，并合并 Stage241 artifact audit。
- 账户规模：沿用官方曲线初始权益 `150,000`，本阶段不改变资金路径。
- 成本口径：沿用官方曲线；本阶段没有新增交易、滑点或手续费。
- 样本过滤：
  - 输入 Stage239 `joined_signal_label_audit`。
  - 输入 Stage241 `event_artifact_audit`。
  - 每个事件只使用 Stage180 cutoff-filtered predecision minute parquet。
  - atlas 只画决策前最后 `120` 根分钟 K，蓝线为方向标准化价格路径，橙线为 rolling aligned VWAP-gap。
- 策略/归因口径：
  - `risk_bad_label = bottom_loss_visual OR maxdd_context`
  - `right_tail_label = right_tail_visual`
  - `turnover_vwap_gap_30m = close / (sum(turnover_last30) / (sum(volume_last30) * inferred_multiplier)) - 1`
  - `aligned_turnover_vwap_gap_30m` 为按交易方向对齐后的 gap。
  - 本阶段只做只读审计，不创建策略规则，不运行 true engine。

## 结果

- 期末权益：`39,176,437.60`，官方路径未变
- 总收益：`26017.6251%`，官方路径未变
- 最大回撤：`-45.0827%`，官方路径未变
- Sharpe：未重算，本阶段不是新回测
- 总滑点：未新增
- 总交易次数：未新增
- 胜率：未重算
- 其他关键指标：
  - `decision=stage246_aligned_turnover_vwap_gap_nonmonotonic_neutral_bucket_blocks_true_engine_no_rule`
  - `event_vwap_gap_row_count=219`
  - `stage239_universal_structure_watch_only=0`
  - `q2_count=44`
  - `q2_risk_bad_count=11`
  - `q2_risk_bad_rate=0.2500000000`
  - `q2_right_tail_count=5`
  - `q2_right_tail_rate=0.1136363636`
  - `q3_count=44`
  - `q3_risk_bad_count=5`
  - `q3_risk_bad_rate=0.1136363636`
  - `q3_right_tail_count=4`
  - `q3_right_tail_rate=0.0909090909`
  - `q4_count=44`
  - `q4_risk_bad_count=10`
  - `q4_risk_bad_rate=0.2272727273`
  - `q4_right_tail_count=4`
  - `q4_right_tail_rate=0.0909090909`
  - `q5_count=44`
  - `q5_risk_bad_count=7`
  - `q5_risk_bad_rate=0.1590909091`
  - `q5_right_tail_count=3`
  - `q5_right_tail_rate=0.0681818182`
  - `favorable_gap_q4q5_count=88`
  - `favorable_gap_q4q5_risk_bad_count=17`
  - `favorable_gap_q4q5_risk_bad_rate=0.1931818182`
  - `favorable_gap_q4q5_right_tail_count=7`
  - `favorable_gap_q4q5_right_tail_rate=0.0795454545`
  - `adverse_gap_q1q2_count=87`
  - `adverse_gap_q1q2_risk_bad_rate=0.2183908046`
  - `adverse_gap_q1q2_right_tail_rate=0.0804597701`
  - `q2_minus_q3_risk_bad_rate=0.1363636364`
  - `q4_minus_q3_risk_bad_rate=0.1136363636`
  - `q5_minus_q3_risk_bad_rate=0.0454545455`
  - `q5_minus_q3_right_tail_rate=-0.0227272727`
  - `atlas_event_count=28`
  - `atlas_page_count=5`
  - `visual_file_count=11`
  - `strategy_feature_usable=0`
  - `strategy_rule_created=0`
  - `true_engine_run=0`
  - `ab_triggered=0`
  - `official_config_changed=0`
  - `ctp_or_simnow_connected=0`
  - `order_api_called=0`

## 图像分析

- 官方资金/回撤图：
  - 官方路径完全未变，Stage246 只读审计。
  - 图中 Q3 neutral gap 风险最低，但这不是强顺向价格接受度，也不是可直接交易的突破信号。
- aligned VWAP-gap quintile label rates：
  - Q3 风险最低：`5/44=0.1136`，右尾 `4/44=0.0909`。
  - Q4 风险反弹到 `10/44=0.2273`，Q5 风险 `7/44=0.1591` 且右尾最低 `3/44=0.0682`。
  - Q5 artifact context 达 `0.8636`，强顺向 gap 很可能混入开盘/事件时间/末根结构。
- fixed group label rates：
  - `favorable_gap_q4q5` 风险 `0.1932`，高于 Q3，右尾 `0.0795`，低于 Q3。
  - `adverse_gap_q1q2` 与 favorable 聚合的风险/右尾差异很小，不能构成普世筛选。
- split delta：
  - SHFE 上 Q2/Q4/Q5 相对 Q3 风险都更高，Q5 artifact 也更高。
  - DCE 上部分极端 gap 相对 Q3 风险更低，说明交易所结构不一致。
  - 年份上 `2023/2025/2026` 的 Q2 或 Q4 风险差很大，稳定性不足。
- VWAP-gap/volume joint heatmap：
  - `GQ5/VQ1` 风险 `0.6667`、右尾 `0.3333`，但样本 `n=3`，不能救参。
  - 多个高右尾格同时小样本或高风险，用 volume + VWAP gap 组合会迅速退化成历史格子挖掘。
- atlas：
  - `q3_tail` 页说明中性 gap 能覆盖部分右尾，但样本形态异质，且多带 artifact context。
  - `q4_bad` 与 `q5_bad` 页显示顺向 gap 下仍有顺势后延伸失败、冲高回落、局部同向但全局钝化、末端突然拉高等坏账反例。
  - `favorable_gap_bad` 页说明强/温和顺向 gap 对执行状态有解释意义，但不能证明入场低风险。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage246_turnover_vwap_gap_counterexample_audit/qmt_roll_stage246_c9_minrisk_turnover_vwap_gap_counterexample_audit_report_stage246_turnover_vwap_gap_counterexample_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage246_turnover_vwap_gap_counterexample_audit/qmt_roll_stage246_c9_minrisk_turnover_vwap_gap_counterexample_audit_summary_stage246_turnover_vwap_gap_counterexample_audit_v1.csv`
- orders：无
- daily：沿用官方曲线，本阶段未生成新 daily
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage246_turnover_vwap_gap_counterexample_audit/qmt_roll_stage246_c9_minrisk_turnover_vwap_gap_counterexample_audit_decision_stage246_turnover_vwap_gap_counterexample_audit_v1.json`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage246_turnover_vwap_gap_counterexample_audit/qmt_roll_stage246_c9_minrisk_turnover_vwap_gap_counterexample_audit_event_vwap_gap_audit_stage246_turnover_vwap_gap_counterexample_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage246_turnover_vwap_gap_counterexample_audit/qmt_roll_stage246_c9_minrisk_turnover_vwap_gap_counterexample_audit_quintile_summary_stage246_turnover_vwap_gap_counterexample_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage246_turnover_vwap_gap_counterexample_audit/qmt_roll_stage246_c9_minrisk_turnover_vwap_gap_counterexample_audit_group_summary_stage246_turnover_vwap_gap_counterexample_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage246_turnover_vwap_gap_counterexample_audit/qmt_roll_stage246_c9_minrisk_turnover_vwap_gap_counterexample_audit_q3_q5_vs_extreme_split_summary_stage246_turnover_vwap_gap_counterexample_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage246_turnover_vwap_gap_counterexample_audit/qmt_roll_stage246_c9_minrisk_turnover_vwap_gap_counterexample_audit_vwap_volume_joint_matrix_stage246_turnover_vwap_gap_counterexample_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage246_turnover_vwap_gap_counterexample_audit/qmt_roll_stage246_c9_minrisk_turnover_vwap_gap_counterexample_audit_atlas_manifest_stage246_turnover_vwap_gap_counterexample_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage246_turnover_vwap_gap_counterexample_audit/qmt_roll_stage246_c9_minrisk_turnover_vwap_gap_counterexample_audit_gate_status_stage246_turnover_vwap_gap_counterexample_audit_v1.csv`

## 结论

- 本阶段结论：
  - `turnover_vwap_gap_30m` 不进入 true engine。它在 Stage239 不是 watch-only，Stage246 进一步证明“顺向 VWAP gap 越强越好”不成立。
  - Q3 neutral gap 是样本内低风险桶，但右尾不占优；Q5 strong favorable gap 右尾更低、artifact 更高。
  - 该特征可以作为执行状态/价格接受度解释变量，不能作为入场质量筛选、加仓或恢复风险规则。
- 是否进入下一步：进入，但停止 VWAP gap 分支交易化推进。
- 下一步：
  - 不扫 VWAP gap 阈值、Q3 单桶、Q5+volume 小格、年份、交易所、方向或产品补丁。
  - 下一阶段应做 residual formal candidate closure：把 Stage239 中未进入 watch-only 的 `range_ratio_1m`、`directional_efficiency_30m`、`volume_participation_30m` 一次性复核并形成“是否还有必要继续”的路线结论。

## 过拟合反思

- 运行前判断：否。原因是 Stage246 固定使用 Stage239 分位与 Stage181 公式，不新增阈值、不挑品种、不写规则。
- 运行后判断：当前阶段否，但把 Q3、Q5 或 VWAP gap+volume 小格写成规则会明显过拟合。
- 原因：
  - 本阶段只读审计，没有 true engine、没有参数搜索、没有 split 补丁。
  - Q3 是样本内中性桶，Q5 是高 artifact 桶；任何 promotion 都是在用标签反推局部结构。
  - 联合热图高右尾格样本很小，不能把小格子解释成普世规律。

## 继续价值反思

- 运行前判断：有价值。原因是 VWAP gap 与执行压力、价格接受度、成交确认有第一性关系，值得做一次固定反例审计。
- 运行后判断：有解释价值，但没有直接交易化价值。
- 原因：
  - 有价值：它解释了某些价格接受度状态，但同时暴露出强顺向 gap 的 artifact 和冲击风险。
  - 无直接交易化价值：风险非单调、右尾不占优、交易所 split 不稳。
  - 剩余价值在于把 formal feature 线做闭环，避免继续在弱特征里局部挖参。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage246 摘要。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、路线废弃正式合入、正式候选或跨线合并。
