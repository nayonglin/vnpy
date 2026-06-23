# Stage244 volume_zscore_60m Q4-vs-Q5 机制归因审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 13:54`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读机制归因、Q4/Q5 反例拆解、交易化前阻断
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Springer《High frequency trading strategies, market fragility and price spikes》：高频交易和订单行为可能放大价格跳变，成交量与冲击不能简单解释成单向 alpha。<https://link.springer.com/article/10.1007/s10479-018-3019-4>
  - SSRN《Persistence or Reversal? the Effects of Abnormal Trading Volume》：异常成交量可能带来短期延续，也可能随后反转，核心问题是区分信息性成交与流动性/拥挤成交。<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4346340>
  - Berkeley/Haas《The market impact of large trading orders》：大订单冲击随规模变化，交易成本和冲击会把看似有利的信号变成亏损路径。<https://haas.berkeley.edu/wp-content/uploads/hiddenImpact13.pdf>
  - Campbell/Grossman/Wang《Trading Volume and Serial Correlation in Stock Returns》：高成交量常与非信息性需求、流动性压力和价格反转相关，不能等价于趋势质量。<https://web.mit.edu/wangj/www/pap/CampbellGrossmanWang93.pdf>
  - GitHub `harshgupta1810/volume_analysis_stockmarket`：公开实践一般把成交量作为确认/背离/反转的辅助变量，而不是单独的交易方向。<https://github.com/harshgupta1810/volume_analysis_stockmarket>
- 我的判断：
  - Stage243 的 Q4 好、Q5 坏不是简单的“量越高越好”，更像“适度放量可能代表有信息的参与，极端放量可能混入冲击、止损拥挤、开盘/低分辨率或反转压力”。
  - 第一性原则上，成交量 z-score 只能说明流动性/参与异常；要成为最小风险搏最大收益规则，必须证明它跨年、跨交易所、跨方向且在干净上下文中稳定。
  - 因此 Stage244 只允许解释 Q4/Q5 差异，不允许扫阈值，不允许把 Q4 单桶写成规则。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage244_volume_q4_q5_mechanism_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定比较 `volume_q4` 与 `volume_q5`，不做阈值扫描。
  - 固定 artifact context 定义：`low_resolution_label`、`event_time_missing_label`、`last_bar_degenerate_ohlc`、`last_bar_single_tick`、`degenerate_nonzero_gap_flag`、`last_bar_open_clock_flag` 任一为真。
  - 固定 atlas 类别：`q5_clean_bad`、`q5_artifact_bad`、`q4_bad`、`q5_tail`、`q4_tail`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage243 event volume audit，共 `219` 个事件，并按 `request_id` 合并 Stage241 artifact audit。
- 账户规模：沿用官方曲线初始权益 `150,000`，本阶段不改变资金路径。
- 成本口径：沿用官方曲线；本阶段没有新增交易、滑点或手续费。
- 样本过滤：
  - 输入 Stage243 `event_volume_zscore_audit`。
  - 输入 Stage241 `event_artifact_audit`。
  - 只拆 `volume_zscore_quintile=4/5`，其他分位只作为上下文保留。
  - atlas 只画决策前最后 `120` 根分钟 K，蓝线为方向标准化价格路径，橙线为滚动 `volume_zscore`。
- 策略/归因口径：
  - `risk_bad_label = bottom_loss_visual OR maxdd_context`
  - `right_tail_label = right_tail_visual`
  - 本阶段只读审计，不创建策略规则，不运行 true engine，不触发 A/B。

## 结果

- 期末权益：`39,176,437.60`，官方路径未变
- 总收益：`26017.6251%`，官方路径未变
- 最大回撤：`-45.0827%`，官方路径未变
- Sharpe：未重算，本阶段不是新回测
- 总滑点：未新增
- 总交易次数：未新增
- 胜率：未重算
- 其他关键指标：
  - `decision=stage244_volume_q5_risk_rebound_not_artifact_only_blocks_q4_or_q5_rule_no_true_engine`
  - `event_mechanism_row_count=219`
  - `q4_count=44`
  - `q4_risk_bad_count=3`
  - `q4_risk_bad_rate=0.0681818182`
  - `q4_right_tail_count=5`
  - `q4_right_tail_rate=0.1136363636`
  - `q4_artifact_context_rate=0.7954545455`
  - `q4_bad_artifact_context_rate=1.0000000000`
  - `q4_clean_count=9`
  - `q4_clean_bad_count=0`
  - `q4_clean_bad_rate=0.0000000000`
  - `q5_count=44`
  - `q5_risk_bad_count=10`
  - `q5_risk_bad_rate=0.2272727273`
  - `q5_right_tail_count=5`
  - `q5_right_tail_rate=0.1136363636`
  - `q5_artifact_context_rate=0.7272727273`
  - `q5_bad_artifact_context_rate=0.6000000000`
  - `q5_clean_count=12`
  - `q5_clean_bad_count=4`
  - `q5_clean_bad_rate=0.3333333333`
  - `q5_minus_q4_risk_bad_rate=0.1590909091`
  - `q5_minus_q4_tail_rate=0.0000000000`
  - `q5_minus_q4_artifact_context_rate=-0.0681818182`
  - `atlas_event_count=23`
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
  - 官方路径完全未变，Stage244 只读拆解 `Q4 bad=3/44` 与 `Q5 bad=10/44`。
  - 图上标注 `Q5 clean_bad=4`，说明 Q5 风险反弹不能被完全解释成低分辨率、末根退化或开盘 artefact。
- Q4/Q5 mechanism flag rates：
  - Q4 的低分辨率率更高：`0.5455`，Q5 为 `0.3182`。
  - Q5 的末根退化、单 tick 和开盘钟点略高，但 Q5 总 artifact context 反而低于 Q4：`0.7273` vs `0.7955`。
  - 这说明 Q5 风险更高不是“Q5 伪影更多”这种简单解释。
- clean-vs-artifact label rates：
  - `volume_q4_clean` 样本只有 `9` 个，`risk_bad_rate=0` 但 `right_tail_rate=0.2222`，样本太小，不能直接 promotion。
  - `volume_q5_clean` 样本 `12` 个，`risk_bad_rate=0.3333`，说明干净上下文里极端放量也会失败。
  - `volume_q5_artifact` 风险率 `0.1875`，低于 Q5 clean，但仍高于 Q4 artifact 的 `0.0857`。
- split delta：
  - Q5 相对 Q4 的风险差在 `2021/2022/2023/2025` 为正，`2024` 为负，跨年份不稳定。
  - SHFE 的 Q5-Q4 风险差达到 `+0.4060`，CZCE 为 `+0.1000`，DCE 接近持平，交易所结构不一致。
  - 方向拆分上 short 的 Q5-Q4 风险差 `+0.3016`，long 为 `+0.1174`，不能写成统一方向规则。
- scatter：
  - 红色坏账和绿色右尾在 Q4/Q5 区间内混杂，没有形成可交易边界。
  - Q5 的红点包含低末端成交量占比和高末端成交量占比两类，不是一种单一形态。
- path shape medians：
  - Q5 坏例的 `directional_efficiency_30m_median=0.2899`，高于 Q4 坏例 `0.1158`，说明“路径更顺”并不自动更安全。
  - Q5 尾部好例末根方向收益中位数 `7.6394bps`，但这更像右尾中的末端确认，不能反推出普世入场规则。
- atlas：
  - `q5_clean_bad` 页显示 4 个无 artifact 上下文坏例，形态包括末端强拉后失败、震荡反抽后失败、短空中反向加速等，视觉上没有单一可切分规则。
  - `q5_artifact_bad` 页中多个样本伴随末端跳变、单 tick/gap 或低分辨率，但它只能解释 `6/10` 个 Q5 坏例。
  - `q4_bad` 页 3 个坏例全部带 artifact context，支持“Q4 看起来干净的一部分来自样本结构”，但 Q4 clean 样本量过小，不能升级为策略。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage244_volume_q4_q5_mechanism_audit/qmt_roll_stage244_c9_minrisk_volume_q4_q5_mechanism_audit_report_stage244_volume_q4_q5_mechanism_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage244_volume_q4_q5_mechanism_audit/qmt_roll_stage244_c9_minrisk_volume_q4_q5_mechanism_audit_summary_stage244_volume_q4_q5_mechanism_audit_v1.csv`
- orders：无
- daily：沿用官方曲线，本阶段未生成新 daily
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage244_volume_q4_q5_mechanism_audit/qmt_roll_stage244_c9_minrisk_volume_q4_q5_mechanism_audit_decision_stage244_volume_q4_q5_mechanism_audit_v1.json`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage244_volume_q4_q5_mechanism_audit/qmt_roll_stage244_c9_minrisk_volume_q4_q5_mechanism_audit_event_mechanism_audit_stage244_volume_q4_q5_mechanism_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage244_volume_q4_q5_mechanism_audit/qmt_roll_stage244_c9_minrisk_volume_q4_q5_mechanism_audit_mechanism_summary_stage244_volume_q4_q5_mechanism_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage244_volume_q4_q5_mechanism_audit/qmt_roll_stage244_c9_minrisk_volume_q4_q5_mechanism_audit_artifact_label_summary_stage244_volume_q4_q5_mechanism_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage244_volume_q4_q5_mechanism_audit/qmt_roll_stage244_c9_minrisk_volume_q4_q5_mechanism_audit_path_shape_summary_stage244_volume_q4_q5_mechanism_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage244_volume_q4_q5_mechanism_audit/qmt_roll_stage244_c9_minrisk_volume_q4_q5_mechanism_audit_q5_minus_q4_split_summary_stage244_volume_q4_q5_mechanism_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage244_volume_q4_q5_mechanism_audit/qmt_roll_stage244_c9_minrisk_volume_q4_q5_mechanism_audit_atlas_manifest_stage244_volume_q4_q5_mechanism_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage244_volume_q4_q5_mechanism_audit/qmt_roll_stage244_c9_minrisk_volume_q4_q5_mechanism_audit_gate_status_stage244_volume_q4_q5_mechanism_audit_v1.csv`

## 结论

- 本阶段结论：
  - Stage244 回答了 Stage243 的核心疑问：Q5 风险反弹不是纯 artifact。Q5 坏例 `10` 个，其中 `4` 个是干净上下文，Q5 clean 坏率 `0.3333`。
  - Q4 的坏例全部带 artifact context，但 Q4 clean 只有 `9` 个，不能把 Q4 单桶当作稳定规则。
  - 成交量分支当前只形成弱直觉：适度放量可能比低量能更有质量，极端放量需要警惕冲击/拥挤/反转；这不是可接入 true engine 的交易规则。
- 是否进入下一步：进入，但应停止 `volume_zscore_60m` 的交易化推进，只保留为解释/forward-watch。
- 下一步：
  - 不扫 `volume_zscore` 阈值、Q4 单桶、年份、交易所、方向或产品补丁。
  - 若继续 formal feature 线，优先转向 Stage238 的其他候选，如 `realized_volatility_30m` 或 `turnover_vwap_gap_30m`，继续按固定分位、反例 atlas、跨 split 稳定性和视觉曲线审计。
  - 若未来要把成交量用于策略，只能作为多条件中的风险解释项，必须先经过预声明 forward-watch，而不是从本次 Q4/Q5 差异反推规则。

## 过拟合反思

- 运行前判断：否。原因是 Stage244 只验证 Stage243 已暴露的 Q4/Q5 差异是否由 artifact 解释，不新增交易规则、不扫阈值。
- 运行后判断：当前阶段否，但把 Q4 或 “非 Q5” 写成规则会过拟合。
- 原因：
  - 本阶段固定比较 Q4/Q5，固定 artifact context，固定 atlas 类别；没有按年份、交易所、方向或产品救援。
  - Q4 优势来自样本内单桶且 clean 样本仅 `9` 个，直接使用会把历史偶然性包装成普世规则。
  - Q5 干净坏例证明“极端放量坏”也不能一刀切，因为 Q5 同时覆盖 `5` 个右尾。

## 继续价值反思

- 运行前判断：有价值。原因是 Stage243 显示高量能聚合覆盖 `55.56%` 右尾，但 Q5 风险反弹需要解释，否则无法判断是否继续。
- 运行后判断：有继续解释价值，但没有继续交易化价值。
- 原因：
  - 有价值：Stage244 把 Q5 风险反弹归因到“不是纯伪影”，这能防止后续误把极端成交量当高质量信号。
  - 无直接交易化价值：Q4 clean 样本小、Q5 clean 坏例明确、split 不稳，达不到穿越周期的规则标准。
  - 下一步更有价值的是换另一个 formal feature 做同样严苛的反例审计，而不是在 volume 分支继续挖阈值。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage244 摘要。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、路线废弃正式合入、正式候选或跨线合并。
