# Stage026 期限结构 carry 对齐只读法证

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-19 22:20 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：点时化外生期限结构状态只读归因；不修改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Koijen/Moskowitz/Pedersen/Vrugt, Carry: https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2014/06/Carry.pdf
  - Moskowitz/Ooi/Pedersen, Time Series Momentum: https://elmwealth.com/wp-content/uploads/2017/06/timeseriesmomentum.pdf
  - Baltas/Kosowski, Improving Time-Series Momentum Strategies: https://www.cmegroup.com/education/files/improving-time-series-momentum-strategies.pdf
  - `pysystemtrade` GitHub: https://github.com/pst-group/pysystemtrade
- 我的判断：期限结构 carry 是入场前可见、比亏损年份/品种 cohort 更外生的候选信息源；但已有 Stage368/419 显示 basis/carry 卫星未能独立晋级，所以本阶段只做 C9 入场前对齐归因，不直接写交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage026_term_structure_carry_alignment_forensics.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 期限结构绑定最大滞后：`7` 个自然日
  - 静态 carry 对齐：long 对应 backwardation（`curve_slope < 0`），short 对应 contango（`curve_slope > 0`）
  - 动态 carry 对齐：沿用 Stage368 固定 `20` 日斜率变化信号
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w closed lot 入场 `2018-01-15` 至退出 `2026-06-08`；官方资金曲线至 `2026-06-15`。
- 账户规模：`150,000`
- 成本口径：官方 C9/15w 原始成本口径，总滑点 `2,730,130`
- 样本过滤：不删除缺失曲线样本；缺失单独归为 `curve_missing`
- 策略/归因口径：每笔 official closed lot 使用入场前 `prev_state_date`，按产品向前 `merge_asof` 绑定 Stage368 曲线特征，不使用未来曲线；只读归因，不是真实交易引擎。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot 胜率 `36.0902%`；官方交易胜率沿用前序固定口径 `53.2560%`
- 新增回测/归因结果：
  - official closed lots：`399`
  - curve ready：`269`，覆盖率 `67.4185%`
  - `static_carry_adverse`：`134` 笔、`18` 产品、`8` 年，净 PnL `27,665,275.20`，正收益覆盖 `53.6451%`，负收益覆盖 `34.9941%`
  - `dynamic_adverse`：`133` 笔、`17` 产品、`7` 年，净 PnL `24,058,642.90`
  - `static_dynamic_adverse`：`83` 笔、`15` 产品、`7` 年，净 PnL `19,700,142.80`
- 修改回测/归因结果：无
- 删除回测/归因结果：无

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage026_term_structure_carry_alignment_forensics/qmt_roll_stage026_c9_minrisk_term_structure_carry_alignment_forensics_report_stage026_term_structure_carry_alignment_forensics_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage026_term_structure_carry_alignment_forensics/qmt_roll_stage026_c9_minrisk_term_structure_carry_alignment_forensics_bucket_summary_stage026_term_structure_carry_alignment_forensics_v1.csv`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage026_term_structure_carry_alignment_forensics/qmt_roll_stage026_c9_minrisk_term_structure_carry_alignment_forensics_daily_active_share_stage026_term_structure_carry_alignment_forensics_v1.csv`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage026_term_structure_carry_alignment_forensics/qmt_roll_stage026_c9_minrisk_term_structure_carry_alignment_forensics_features_stage026_term_structure_carry_alignment_forensics_v1.csv`
- 资金曲线/状态图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage026_term_structure_carry_alignment_forensics/qmt_roll_stage026_c9_minrisk_term_structure_carry_alignment_forensics_path_carry_state_chart_stage026_term_structure_carry_alignment_forensics_v1.png`
- 分组贡献曲线：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage026_term_structure_carry_alignment_forensics/qmt_roll_stage026_c9_minrisk_term_structure_carry_alignment_forensics_cohort_contribution_chart_stage026_term_structure_carry_alignment_forensics_v1.png`
- 年度热图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage026_term_structure_carry_alignment_forensics/qmt_roll_stage026_c9_minrisk_term_structure_carry_alignment_forensics_bucket_year_heatmap_stage026_term_structure_carry_alignment_forensics_v1.png`
- 散点图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage026_term_structure_carry_alignment_forensics/qmt_roll_stage026_c9_minrisk_term_structure_carry_alignment_forensics_carry_scatter_stage026_term_structure_carry_alignment_forensics_v1.png`
- 产品热图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage026_term_structure_carry_alignment_forensics/qmt_roll_stage026_c9_minrisk_term_structure_carry_alignment_forensics_product_carry_heatmap_stage026_term_structure_carry_alignment_forensics_v1.png`

## 视觉分析

- path carry-state chart：active carry-state share 在深回撤前后没有稳定领先关系；2018-2019 多为缺失，2020 后 aligned/adverse 快速切换，不能作为稳健闸门。
- cohort contribution chart：`static_carry_adverse` 橙线自 2021 后持续上行，2025 出现最大右尾台阶；这直接反证“carry 逆向就应最小风险/削仓”。
- bucket-year heatmap：`static_carry_adverse` 在 `2021/2022/2023/2024/2025` 均为正，仅 `2026` 暂时负；`static_carry_aligned` 在 `2022/2026` 为负，年度关系非单调。
- scatter：盈亏点在 curve_slope 与 slope_change_20d 空间混杂，没有可解释的线性边界。
- product heatmap：`jm.DCE` 的 static adverse、`OI.CZCE` 的 static aligned 等产品块贡献很大，若按产品/交易所修补会进入过拟合。

## 结论

- 本阶段结论：`stage026_term_structure_no_candidate_nonmonotonic_or_right_tail_dominant`
- 是否进入下一步：本分支不进入交易引擎，不触发 A/B。
- 下一步：停止期限结构 carry 对齐/逆向阈值分支，不扫 `curve_slope`、`slope_change`、lookback、滞后天数、产品、方向、年份或交易所。若继续外生路线，应只考虑更直接、可点时取得的库存/仓单/供需/持仓结构变化；如果没有新增外生数据，应暂停历史内反推。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：继续扫该分支会过拟合。
- 原因：本阶段使用外部 carry/term-structure 第一性原理和入场前可见数据，没有按亏损结果调参；但结果显示 adverse 桶承载大额右尾，若再调阈值/窗口/品种就是用历史右尾和亏损形状救参。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：本分支继续价值低；本目标整体仍有价值。
- 原因：Stage026 排除了一个外生但粗粒度的期限结构解释变量，降低了后续误接规则的风险；目标若继续，需要更真实的外生供需数据或等待 forward watch，而不是在已有 closed lots 里继续切片。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage026 摘要和停止分支说明。
- 是否更新 `research/registry.md`：否，非正式候选、非重要突破、非路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破、非正式候选。
