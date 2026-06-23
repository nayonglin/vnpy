# Stage245 realized_volatility_30m 反例图谱审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 14:03`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因、formal feature 反例 atlas、交易化前阻断
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Federal Reserve《Frequency of Observation and the Estimation of Integrated Volatility》：realized volatility 的估计会受采样频率和 market microstructure noise 影响，不同市场的可用采样频率差异很大。<https://www.federalreserve.gov/pubs/ifdp/2007/905/revision/ifdp905r.htm>
  - Ghysels/Santa-Clara/Valkanov《Predicting Volatility》：高频 5 分钟数据直接进入预测不一定优于日频聚合变量，外推有效性要看样本外表现，不能靠样本内分桶。<https://rady.ucsd.edu/_files/faculty-research/valkanov/predicting-volatility.pdf>
  - Bandi/Russell《Separating Microstructure Noise from Volatility》：高频价格记录中的波动同时包含真实波动和微观结构噪声，需要拆分理解。<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=642323>
  - GitHub `vivek-v-rao/Intraday-Vol`：公开工具把 intraday realized volatility 做成一组估计器、周期性调整和噪声鲁棒处理，不把单一 realized volatility 桶直接当方向交易信号。<https://github.com/vivek-v-rao/Intraday-Vol>
- 我的判断：
  - `realized_volatility_30m` 的第一性含义是“最近 30 根闭合分钟的 log return 标准差”，更像风险预算分母、止损距离和行情能量状态，不天然表示入场方向质量。
  - 低波动可能是趋势前压缩，也可能是流动性不足、延伸后钝化、低分辨率或开盘结构；如果只看历史标签挑中间桶，会非常容易过拟合。
  - Stage245 因此只允许固定分位反例审计，重点验证“低波动是否真低风险、是否保住右尾”，不允许把 Q2 或 Q5 写成规则。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage245_realized_volatility_counterexample_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定使用 Stage239 的 `quality_quintile_low_realized_volatility_30m`，其中 Q5 代表最低原始 `realized_volatility_30m`。
  - 固定组：`q1_highest_raw_vol`、`q2_mid_high_raw_vol`、`q3_mid_raw_vol`、`q4_low_raw_vol`、`q5_lowest_raw_vol`、`low_raw_vol_q4q5`、`high_raw_vol_q1q2`。
  - 固定 atlas 类别：`q2_tail`、`q2_bad`、`q3_bad`、`q5_bad`、`high_raw_vol_tail_miss`。
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
  - atlas 只画决策前最后 `120` 根分钟 K，蓝线为方向标准化价格路径，橙线为 rolling 30-bar realized volatility。
- 策略/归因口径：
  - `risk_bad_label = bottom_loss_visual OR maxdd_context`
  - `right_tail_label = right_tail_visual`
  - `realized_volatility_30m = std(log(close).diff(), ddof=1)` over last 31 closed bars / 30 returns。
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
  - `decision=stage245_low_realized_volatility_nonmonotonic_midbucket_blocks_true_engine_no_rule`
  - `event_volatility_row_count=219`
  - `stage239_universal_structure_watch_only=0`
  - `q2_count=44`
  - `q2_risk_bad_count=3`
  - `q2_risk_bad_rate=0.0681818182`
  - `q2_right_tail_count=7`
  - `q2_right_tail_rate=0.1590909091`
  - `q2_artifact_context_rate=0.7272727273`
  - `q3_count=44`
  - `q3_risk_bad_count=12`
  - `q3_risk_bad_rate=0.2727272727`
  - `q3_right_tail_count=2`
  - `q3_right_tail_rate=0.0454545455`
  - `q5_count=44`
  - `q5_risk_bad_count=9`
  - `q5_risk_bad_rate=0.2045454545`
  - `q5_right_tail_count=5`
  - `q5_right_tail_rate=0.1136363636`
  - `q5_artifact_context_rate=0.4772727273`
  - `low_raw_vol_q4q5_count=88`
  - `low_raw_vol_q4q5_risk_bad_count=16`
  - `low_raw_vol_q4q5_risk_bad_rate=0.1818181818`
  - `low_raw_vol_q4q5_right_tail_count=6`
  - `low_raw_vol_q4q5_right_tail_rate=0.0681818182`
  - `q3_minus_q2_risk_bad_rate=0.2045454545`
  - `q5_minus_q2_risk_bad_rate=0.1363636364`
  - `q5_minus_q2_right_tail_rate=-0.0454545455`
  - `low_raw_vol_q4q5_minus_q2_risk_bad_rate=0.1136363636`
  - `high_raw_vol_tail_miss_count=10`
  - `atlas_event_count=27`
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
  - 官方路径完全未变，Stage245 只读审计。
  - 图中直接标注 `Q2 risk=0.068 tail=0.159`、`Q3 risk=0.273`、`Q5 risk=0.205`，核心形态是非单调，不是低波动优势。
- low-volatility quintile label rates：
  - Q2 看起来最好：风险坏账 `3/44=0.0682`，右尾 `7/44=0.1591`。
  - Q3 最差：风险坏账 `12/44=0.2727`，右尾只有 `2/44=0.0455`。
  - Q5 是最低原始波动，但风险坏账仍 `9/44=0.2045`，不是最小风险。
- fixed group label rates：
  - `low_raw_vol_q4q5` 风险坏账 `16/88=0.1818`，高于 Q2，右尾率 `0.0682` 低于 Q2。
  - `high_raw_vol_q1q2` 仍有 `10` 个右尾，不能把高/中高波动简单过滤掉。
- split delta：
  - Q3 相对 Q2 在 `2022/2023/2024/2025` 风险更高，在 CZCE/DCE/SHFE 多数截面也不优。
  - Q5 相对 Q2 在 `2022/2023/2025` 风险更高，同时右尾更低；这不符合“低波动更安全且保右尾”。
  - short 方向 Q5-Q2 风险差 `+0.1746` 且右尾差 `+0.1746`，好坏一起放大，不能做方向规则。
- scatter：
  - 风险坏账和右尾在原始 realized volatility 的低端、中端、高端都有分布，没有清晰边界。
  - LQ2/LQ3/LQ5 标记高度重叠，视觉上不支持单一阈值。
- volatility-efficiency joint heatmap：
  - `LQ5/EQ5` 风险坏账率 `0.4286`，右尾率 `0.2857`，右尾与坏账同在，不是稳定高质量组合。
  - `LQ2/EQ2` 右尾率 `0.2727` 且风险为 `0`，但样本 `n=11`，属于局部小格，不可 promotion。
- atlas：
  - `q2_tail` 页说明 Q2 确实覆盖一些右尾，但不少样本带 artifact context，形态包括先大幅趋势后横盘、末端跳变、低波动回落后再拉，不是统一压缩突破。
  - `q3_bad` 页显示低波动/中波动下也会出现顺势推进后失败、波动下降但价格已延伸后失败，说明“安静”不等于安全。
  - `q5_bad` 页显示最低波动坏例中有多个干净上下文，且波动持续下降仍走坏账，最低波动更像行情能量不足或延伸后钝化。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage245_realized_volatility_counterexample_audit/qmt_roll_stage245_c9_minrisk_realized_volatility_counterexample_audit_report_stage245_realized_volatility_counterexample_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage245_realized_volatility_counterexample_audit/qmt_roll_stage245_c9_minrisk_realized_volatility_counterexample_audit_summary_stage245_realized_volatility_counterexample_audit_v1.csv`
- orders：无
- daily：沿用官方曲线，本阶段未生成新 daily
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage245_realized_volatility_counterexample_audit/qmt_roll_stage245_c9_minrisk_realized_volatility_counterexample_audit_decision_stage245_realized_volatility_counterexample_audit_v1.json`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage245_realized_volatility_counterexample_audit/qmt_roll_stage245_c9_minrisk_realized_volatility_counterexample_audit_event_volatility_audit_stage245_realized_volatility_counterexample_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage245_realized_volatility_counterexample_audit/qmt_roll_stage245_c9_minrisk_realized_volatility_counterexample_audit_quintile_summary_stage245_realized_volatility_counterexample_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage245_realized_volatility_counterexample_audit/qmt_roll_stage245_c9_minrisk_realized_volatility_counterexample_audit_group_summary_stage245_realized_volatility_counterexample_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage245_realized_volatility_counterexample_audit/qmt_roll_stage245_c9_minrisk_realized_volatility_counterexample_audit_q2_q3_q5_split_summary_stage245_realized_volatility_counterexample_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage245_realized_volatility_counterexample_audit/qmt_roll_stage245_c9_minrisk_realized_volatility_counterexample_audit_volatility_efficiency_joint_matrix_stage245_realized_volatility_counterexample_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage245_realized_volatility_counterexample_audit/qmt_roll_stage245_c9_minrisk_realized_volatility_counterexample_audit_atlas_manifest_stage245_realized_volatility_counterexample_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage245_realized_volatility_counterexample_audit/qmt_roll_stage245_c9_minrisk_realized_volatility_counterexample_audit_gate_status_stage245_realized_volatility_counterexample_audit_v1.csv`

## 结论

- 本阶段结论：
  - `realized_volatility_30m` 不进入 true engine。它在 Stage239 就不是 watch-only，Stage245 进一步证明低波动不是普世低风险结构。
  - Q2 是样本内最诱人的中间偏高波动桶，但这不是第一性规则；Q3 和 Q5 的反例足以阻断任何“低波动/压缩释放风险”的浅规则。
  - 当前只能把 realized volatility 作为风险解释变量或止损/仓位尺度的背景项，不能作为入场质量筛选、加仓或恢复风险规则。
- 是否进入下一步：进入，但停止 volatility 分支交易化推进。
- 下一步：
  - 不扫 realized volatility 阈值、Q2 单桶、Q2+efficiency 小格、年份、交易所、方向或产品补丁。
  - 若继续 formal feature 线，转向 `turnover_vwap_gap_30m` 做固定分位、反例 atlas、跨 split 稳定性和视觉曲线审计。

## 过拟合反思

- 运行前判断：否。原因是 Stage245 固定使用 Stage239 已有分位和 Stage181 公式，不新增阈值、不选样本、不写规则。
- 运行后判断：当前阶段否，但把 Q2 或 `LQ2/EQ2` 写成规则会明显过拟合。
- 原因：
  - 本阶段只读审计没有 true engine、没有参数搜索、没有 split 补丁。
  - Q2 是样本内非单调中间桶，`LQ2/EQ2` 样本只有 `11` 个；任何 promotion 都是在用标签反推阈值。
  - 反例 atlas 同时展示 Q2 坏例、Q3 坏例、Q5 坏例和高波动右尾，避免只看成功样本。

## 继续价值反思

- 运行前判断：有价值。原因是 realized volatility 与风险预算和微观结构噪声有第一性关系，必须确认它能否作为低回撤目标的稳定背景状态。
- 运行后判断：有解释价值，但没有直接交易化价值。
- 原因：
  - 有价值：它帮助排除了“低波动即最小风险”的直觉误用，也解释了为什么部分右尾来自中高波动状态。
  - 无直接交易化价值：最低波动坏例明确，Q2 是样本内中间桶，跨 split 和联合矩阵都不稳。
  - 下一步更有价值的是审计价格相对成交额/VWAP 的 `turnover_vwap_gap_30m`，看是否有更接近执行冲击或价格接受度的结构。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage245 摘要。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、路线废弃正式合入、正式候选或跨线合并。
