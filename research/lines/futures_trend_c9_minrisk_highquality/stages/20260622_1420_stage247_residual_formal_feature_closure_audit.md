# Stage247 residual formal feature 闭环审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 14:20`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读闭环、formal residual feature 复核、路线收束
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Phylaktis/Manalis《Futures trading and market microstructure of the underlying security》：高频场景下成交量、波动、流动性会同时变化，市场质量不一定因交易活跃而改善。<https://www.bayes.citystgeorges.ac.uk/__data/assets/pdf_file/0008/69965/Phylaktis.pdf>
  - Cartea/Jaimungal/Penalva 相关执行示例：按市场成交速度参与更偏执行调度问题，而不是方向 alpha。<https://gist.github.com/sebjai/e5cdaf69a60976889e970039fba9d866>
  - AIMS《Power laws in market microstructure》：市场冲击、成交量和尾部分布有复杂关系，单一量价形态不宜直接简化为稳定收益信号。<https://www.aimsciences.org/article/doi/10.3934/fmf.2023003>
  - GitHub/公开回测库 `stratestic`：公开策略库强调回测与分析工具化，不能把预实现指标或局部分桶直接当生产规则。<https://github.com/diogomatoschaves/stratestic>
- 我的判断：
  - `range_ratio_1m`、`directional_efficiency_30m`、`volume_participation_30m` 在 Stage239 已未通过 watch-only，继续单独深挖很容易退化成单桶救参。
  - 这三个特征的第一性含义分别是短噪声地板、趋势路径效率、成交参与充分度；它们适合解释形态，不足以单独决定入场质量。
  - Stage247 的目标不是找最后一个参数，而是把 formal feature 线闭环，明确哪些方向停止交易化推进。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage247_residual_formal_feature_closure_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定 residual feature 集合：`low_range_ratio_1m`、`directional_efficiency_30m`、`volume_participation_30m`。
  - 只读取 Stage239 `feature_rank_correlation_audit`、`feature_quintile_audit`、`feature_stability_audit`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage239 的 `219` 个事件汇总结果。
- 账户规模：沿用官方曲线初始权益 `150,000`，本阶段不改变资金路径。
- 成本口径：沿用官方曲线；本阶段没有新增交易、滑点或手续费。
- 样本过滤：
  - 只看 residual non-watch formal features。
  - 不重新计算分钟特征，不新增阈值，不重新选择样本。
- 策略/归因口径：
  - 继承 Stage239 的 `risk_bad_label`、`right_tail_label` 和 fixed quality quintile。
  - 本阶段只做只读闭环，不创建策略规则，不运行 true engine。

## 结果

- 期末权益：`39,176,437.60`，官方路径未变
- 总收益：`26017.6251%`，官方路径未变
- 最大回撤：`-45.0827%`，官方路径未变
- Sharpe：未重算，本阶段不是新回测
- 总滑点：未新增
- 总交易次数：未新增
- 胜率：未重算
- 其他关键指标：
  - `decision=stage247_residual_formal_features_closed_no_true_engine_no_rule`
  - `residual_feature_count=3`
  - `residual_watch_only_count=0`
  - `closed_feature_count=3`
  - `range_ratio_q4_row_count=14`
  - `range_ratio_q5_row_count=74`
  - `range_ratio_q5_risk_bad_rate=0.1891891892`
  - `range_ratio_q5_right_tail_rate=0.1216216216`
  - `directional_efficiency_q4_risk_bad_rate=0.1363636364`
  - `directional_efficiency_q5_risk_bad_rate=0.2272727273`
  - `directional_efficiency_q5_right_tail_rate=0.0681818182`
  - `volume_participation_nonempty_quintile_count=2`
  - `visual_file_count=5`
  - `strategy_feature_usable=0`
  - `strategy_rule_created=0`
  - `true_engine_run=0`
  - `ab_triggered=0`
  - `official_config_changed=0`
  - `ctp_or_simnow_connected=0`
  - `order_api_called=0`

## 图像分析

- 官方资金/回撤图：
  - 官方路径完全未变，Stage247 只读闭环。
  - 图上标注 residual features `3`、watch-only `0`、true engine `0`，说明没有新增交易路径。
- residual feature label rate grid：
  - `low_range_ratio_1m` 的 Q5 有 `74` 行、Q4 只有 `14` 行，分桶受 ties 影响；Q5 虽有较高右尾，但风险也不低。
  - `directional_efficiency_30m` 的 Q5 风险 `0.2273`，高于 Q4 的 `0.1364`，且右尾不占优。
  - `volume_participation_30m` 只有 Q1 和 Q3 两个非空桶，Q3 包含 `210` 行，几乎没有横截面排序能力。
- risk/tail heatmap：
  - 三个特征都不存在“Q5 低风险且高右尾”的稳定格局。
  - 局部好格要么样本过小，要么右尾和风险一起上升。
- top-bottom delta / ranking capacity：
  - `low_range_ratio_1m` 的 Q5-Q1 tail 为正，但 risk 也为正，不能满足低回撤目标。
  - `directional_efficiency_30m` 的 Q5-Q1 risk 为正、tail 接近 0，直接反证“越顺越好”。
  - `volume_participation_30m` unique value 只有 `5`，非空分位只有 `2`，不是可用排序特征。
- stability matrix：
  - `low_range_ratio_1m` 的 tail split 看起来好，但 risk split 和 exchange risk 不稳。
  - `directional_efficiency_30m` 在 risk/tail split 上普遍偏弱。
  - `volume_participation_30m` 的局部绿色来自有效 split 少和分桶稀疏，不是普世结构。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage247_residual_formal_feature_closure_audit/qmt_roll_stage247_c9_minrisk_residual_formal_feature_closure_audit_report_stage247_residual_formal_feature_closure_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage247_residual_formal_feature_closure_audit/qmt_roll_stage247_c9_minrisk_residual_formal_feature_closure_audit_summary_stage247_residual_formal_feature_closure_audit_v1.csv`
- orders：无
- daily：沿用官方曲线，本阶段未生成新 daily
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage247_residual_formal_feature_closure_audit/qmt_roll_stage247_c9_minrisk_residual_formal_feature_closure_audit_decision_stage247_residual_formal_feature_closure_audit_v1.json`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage247_residual_formal_feature_closure_audit/qmt_roll_stage247_c9_minrisk_residual_formal_feature_closure_audit_residual_feature_summary_stage247_residual_formal_feature_closure_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage247_residual_formal_feature_closure_audit/qmt_roll_stage247_c9_minrisk_residual_formal_feature_closure_audit_residual_quintile_summary_stage247_residual_formal_feature_closure_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage247_residual_formal_feature_closure_audit/qmt_roll_stage247_c9_minrisk_residual_formal_feature_closure_audit_residual_stability_summary_stage247_residual_formal_feature_closure_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage247_residual_formal_feature_closure_audit/qmt_roll_stage247_c9_minrisk_residual_formal_feature_closure_audit_gate_status_stage247_residual_formal_feature_closure_audit_v1.csv`

## 结论

- 本阶段结论：
  - Stage247 关闭剩余三个 residual formal features，不进入 true engine 或 A/B。
  - 至此 Stage238 的 7 个 candidate features 中，`aligned_bar_return_1m`、`volume_zscore_60m` 曾有 watch-only 价值但已被 Stage240-244 阻断；`realized_volatility_30m`、`turnover_vwap_gap_30m`、`range_ratio_1m`、`directional_efficiency_30m`、`volume_participation_30m` 均无单特征交易化价值。
  - 当前 formal feature 单变量路线阶段性收束，不能继续在这些分钟单特征里扫阈值、分位或小格组合。
- 是否进入下一步：进入，但应换路线。
- 下一步：
  - 若继续“最小风险搏最大收益”，必须换成更强的机制源：组合级账户风险、外生供需/持仓源、真实执行回放里的事件序列，或预声明的 forward-watch 多条件组合。
  - 不再围绕 Stage238 七个单特征做阈值、分位、年份、交易所、方向、产品补丁。

## 过拟合反思

- 运行前判断：否。原因是 Stage247 只读取 Stage239 汇总表，不新增阈值、不新增样本、不运行 true engine。
- 运行后判断：当前阶段否；继续在 residual 特征上找单桶会过拟合。
- 原因：
  - 三个 residual 特征都已在 Stage239 未通过 watch-only。
  - 本阶段把分桶稀疏、ties 失衡、Q5 风险反弹和 split 不稳明确记录，防止后续复挖。

## 继续价值反思

- 运行前判断：有价值。原因是必须把剩余 formal features 闭环，否则研究线会反复回到弱特征上。
- 运行后判断：这条单特征 formal feature 路线已无继续交易化价值，但记录闭环有价值。
- 原因：
  - 有价值：明确哪些方向不能再扫，降低后续过拟合风险。
  - 无直接交易化价值：没有任何 residual feature 能同时降低风险、保留右尾、跨 split 稳定。
  - 下一步必须换信息源或机制层级。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage247 摘要。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、路线废弃正式合入、正式候选或跨线合并。
