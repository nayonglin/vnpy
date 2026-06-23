# Stage242 去最后一根后的多 bar 持久性审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 13:30`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因、图像反例审计、formal feature 交易化前阻断
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - pandas `pct_change` 官方文档：用于确认收益率变化计算语义，避免手写百分比变化造成口径漂移。<https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.pct_change.html>
  - pandas `groupby` 官方文档：用于固定分组统计、跨 split 汇总和分位组聚合。<https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.groupby.html>
  - Matplotlib `imshow` 官方文档：用于热力矩阵可视化，并保持图像审计可复验。<https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.imshow.html>
  - Alphalens GitHub / tear sheet 参考：参考其按分位数做因子审计、信息衰减和可视化 tear sheet 的研究范式，但本阶段没有复制其策略逻辑。<https://github.com/quantopian/alphalens> / <https://github.com/quantopian/alphalens/blob/master/alphalens/tears.py>
- 我的判断：
  - Stage241 已证明最后 1 根 bar 污染严重，因此 Stage242 不能再看 `aligned_bar_return_1m` 本身，而要只读观察去掉最后一根后的 30/60bar 方向持久性。
  - 分位数审计适合做“普世结构是否存在”的第一关，但不能因为某个小格子看起来好就写规则；尤其不能按年、品种、交易所补丁化。
  - 本阶段的本质问题是：多 bar 顺势是否同时降低坏账、覆盖右尾、跨 split 稳定。结果显示三者没有同时成立。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage242_without_last_multibar_persistence_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定 `without_last_30bar` 与 `without_last_60bar` 两个方向收益窗口。
  - 固定 rank quintile，不使用 bps 绝对阈值。
  - 固定组合组：`both_high_q4q5`、`both_low_q1q2`、`thirty_high_only`、`sixty_high_only`、`mixed_middle`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用当前官方 C9 审计样本，事件行 `219`。
- 账户规模：沿用官方曲线初始权益 `150,000`，本阶段不改变资金路径。
- 成本口径：沿用官方曲线；本阶段不新增交易、不新增滑点口径。
- 样本过滤：
  - 输入 Stage241 event artifact audit。
  - 每个事件只使用 `bar_end_ts <= decision_ts` 的决策前分钟数据。
  - 去掉最后一根 bar 后再计算 30/60bar 方向收益。
- 策略/归因口径：
  - `risk_bad_label = bottom_loss_visual OR maxdd_context`
  - `right_tail_label = right_tail_visual`
  - 本阶段只做只读归因，不创建交易规则，不运行 true engine。

## 结果

- 期末权益：`39,176,437.60`，官方路径未变
- 总收益：`26017.6251%`，官方路径未变
- 最大回撤：`-45.0827%`，官方路径未变
- Sharpe：未重算，本阶段不是新回测
- 总滑点：未新增
- 总交易次数：未新增
- 胜率：未重算
- 其他关键指标：
  - `decision=stage242_without_last_multibar_persistence_no_true_engine_no_rule`
  - `event_persistence_row_count=219`
  - `both_high_count=57`
  - `both_high_risk_bad_count=8`
  - `both_high_risk_bad_rate=0.1403508772`
  - `both_high_right_tail_count=4`
  - `both_high_right_tail_rate=0.0701754386`
  - `both_high_right_tail_coverage_rate=0.2222222222`
  - `both_high_ordinary_clean_rate=0.3157894737`
  - `both_low_count=57`
  - `both_low_risk_bad_count=12`
  - `both_low_risk_bad_rate=0.2105263158`
  - `both_low_right_tail_count=5`
  - `both_low_right_tail_rate=0.0877192982`
  - `rank_corr_30_vs_risk_bad=-0.0203698086`
  - `rank_corr_30_vs_right_tail=0.0120981717`
  - `rank_corr_60_vs_risk_bad=-0.0694364199`
  - `rank_corr_60_vs_right_tail=0.0904653242`
  - `atlas_event_count=25`
  - `atlas_page_count=5`
  - `visual_file_count=11`
  - `strategy_feature_usable=0`
  - `strategy_rule_created=0`
  - `true_engine_run=0`
  - `ab_triggered=0`
  - `official_config_changed=0`
  - `ctp_or_simnow_connected=0`
  - `order_api_called=0`

## 分位与组合观察

- 30bar quintile：
  - Q1：`risk_bad_rate=0.2558`，`right_tail_rate=0.0233`
  - Q2：`risk_bad_rate=0.1163`，`right_tail_rate=0.1395`
  - Q4：`risk_bad_rate=0.1136`，`right_tail_rate=0.1364`
  - Q5：`risk_bad_rate=0.2273`，`right_tail_rate=0.0455`
  - 结论：30bar 不是越强越好，Q5 反而风险高、右尾低，不能交易化。
- 60bar quintile：
  - Q1：`risk_bad_rate=0.1628`，`right_tail_rate=0.0000`
  - Q2：`risk_bad_rate=0.3182`，`right_tail_rate=0.1136`
  - Q4：`risk_bad_rate=0.1364`，`right_tail_rate=0.0682`
  - Q5：`risk_bad_rate=0.1364`，`right_tail_rate=0.1136`
  - 结论：60bar 有弱低风险迹象，但 Q2 高风险且右尾也不低，结构不单调。
- 组合组：
  - `both_high_q4q5`：`n=57`，`risk_bad_rate=0.1404`，`right_tail_rate=0.0702`
  - `both_low_q1q2`：`n=57`，`risk_bad_rate=0.2105`，`right_tail_rate=0.0877`
  - `sixty_high_only`：`n=31`，`risk_bad_rate=0.1290`，`right_tail_rate=0.1290`
  - `thirty_high_only`：`n=31`，`risk_bad_rate=0.2258`，`right_tail_rate=0.1290`
  - `mixed_middle`：`n=43`，`risk_bad_rate=0.2326`，`right_tail_rate=0.0233`
  - 结论：`both_high` 风险低于 `both_low`，但右尾率更低，只能解释“低风险倾向”，不能满足“最小风险搏最大收益”。`sixty_high_only` 是弱观察，不得直接救参。

## 图像分析

- 官方资金/回撤图：
  - 官方路径未变，只读审计没有改策略。
  - 图上标注 `both_high=57 risk=0.140 tail=0.070`、`both_low=57 risk=0.211`，说明 `both_high` 只在风险标签上略好，不能证明收益目标成立。
- 30/60bar 分位柱状图：
  - 30bar Q5 的红柱高、绿柱低，说明最强短窗顺势反而不是好质量。
  - 60bar Q5 比较温和，但 Q2 风险红柱最高，说明单窗口分位没有普世单调性。
- 组合柱状图：
  - `sixty_high_only` 同时低风险和右尾不低，但样本只有 `31`，且是 Stage241 失败后自然浮出的旁支，不能拿来当参数救援。
  - `both_high_q4q5` 并没有比 `both_low_q1q2` 捕获更多右尾，无法作为放大风险或恢复风险的规则。
- Q30/Q60 矩阵热图：
  - 右尾率最高的 `Q30=Q3/Q60=Q5` 只有 `5` 笔，不能代表普世结构。
  - 风险高格子散布在中低分位，说明“多 bar 顺势”不是风险坏账的充分反面。
- split delta 图：
  - `2022` both_high 明显改善风险，但 `2024` 反向；`2025` 右尾改善受样本小影响。
  - DCE 和 GFEX 的方向不稳，跨交易所稳定性不足。
- atlas：
  - `both_high_bad` 页显示 `fu2305.SHFE`、`MA305.CZCE`、`lh2301.DCE`、`rb2205.SHFE`、`SH607.CZCE` 等样本在去最后一根后仍有较强前置顺势，但最终仍是风险坏账。
  - `both_low_tail_miss` 页显示 `au2510.SHFE`、`OI305.CZCE`、`lh2505.DCE`、`fu2509.SHFE`、`si2509.GFEX` 等样本虽为低持久组仍进入右尾，说明按低持久削仓会误伤大赢家。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage242_without_last_multibar_persistence_audit/qmt_roll_stage242_c9_minrisk_without_last_multibar_persistence_audit_report_stage242_without_last_multibar_persistence_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage242_without_last_multibar_persistence_audit/qmt_roll_stage242_c9_minrisk_without_last_multibar_persistence_audit_summary_stage242_without_last_multibar_persistence_audit_v1.csv`
- orders：无
- daily：沿用官方曲线，本阶段未生成新 daily
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage242_without_last_multibar_persistence_audit/qmt_roll_stage242_c9_minrisk_without_last_multibar_persistence_audit_gate_status_stage242_without_last_multibar_persistence_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage242_without_last_multibar_persistence_audit/qmt_roll_stage242_c9_minrisk_without_last_multibar_persistence_audit_quintile_summary_stage242_without_last_multibar_persistence_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage242_without_last_multibar_persistence_audit/qmt_roll_stage242_c9_minrisk_without_last_multibar_persistence_audit_combo_summary_stage242_without_last_multibar_persistence_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage242_without_last_multibar_persistence_audit/qmt_roll_stage242_c9_minrisk_without_last_multibar_persistence_audit_split_summary_stage242_without_last_multibar_persistence_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage242_without_last_multibar_persistence_audit/qmt_roll_stage242_c9_minrisk_without_last_multibar_persistence_audit_q30_q60_matrix_summary_stage242_without_last_multibar_persistence_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage242_without_last_multibar_persistence_audit/qmt_roll_stage242_c9_minrisk_without_last_multibar_persistence_audit_atlas_manifest_stage242_without_last_multibar_persistence_audit_v1.csv`

## 结论

- 本阶段结论：
  - 去掉最后一根后，30/60bar 多 bar 方向持久性仍不足以成为 true engine 规则。
  - `both_high_q4q5` 有较低风险率，但右尾率不占优、右尾覆盖只有 `4/18=22.22%`，不符合“高质量信号时用最小风险搏最大收益”。
  - `both_low_q1q2` 仍包含 `5` 个右尾样本，不能作为削仓或过滤依据。
  - `aligned_bar_return_1m` 分支应停止交易化推进，只保留为解释/forward-watch 标签。
- 是否进入下一步：进入，但不是沿 `aligned_bar_return` 继续救参。
- 下一步：
  - Stage243 应转向 Stage239 的另一个 watch-only formal feature `volume_zscore_60m`，做同样的只读反例 atlas、分位稳定性、跨 split 审计。
  - 不做 `30/60` 窗口、分位、bps 阈值、年份、交易所、方向的参数救援。

## 过拟合反思

- 运行前判断：否。原因是本阶段预声明只看去最后一根后的 `30bar/60bar`，使用 rank quintile 和固定组合组，不以最终收益反推阈值。
- 运行后判断：否，但继续救参会立刻变成过拟合。
- 原因：
  - 本阶段没有跑 true engine、没有调策略参数、没有按 split 补丁化。
  - 结果中自然出现的 `sixty_high_only` 不被升级为候选规则，避免从小样本好看格子反推交易规则。
  - 视觉 atlas 明确保留反例，而不是只展示成功样本。

## 继续价值反思

- 运行前判断：有价值。原因是 Stage241 已证明最后一根污染重，必须确认更长的去最后一根路径是否仍有普世结构。
- 运行后判断：仍有研究价值，但这条子分支不再有交易化价值。
- 原因：
  - 有价值的是把 `aligned_bar_return` 线索从“似乎可用”降级到“解释标签”，避免后续误接 true engine。
  - 无交易化价值的原因是多 bar persistence 没有同时满足低风险、右尾覆盖、跨 split 稳定三项要求。
  - 后续价值应来自其他 formal feature 的反例审计，而不是继续围绕本分支救参数。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage242 摘要。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、路线废弃正式合入、正式候选或跨线合并。
