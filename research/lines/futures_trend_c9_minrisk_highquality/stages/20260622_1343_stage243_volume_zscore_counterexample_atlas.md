# Stage243 volume_zscore_60m 反例图谱审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 13:43`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因、formal feature 反例 atlas、交易化前阻断
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - SciPy `zscore` 官方文档：z-score 是相对样本均值和标准差的标准化距离，适合表达异常度，不天然代表收益方向。<https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.zscore.html>
  - pandas `rolling` 官方文档：滚动窗口统计需要明确窗口、`min_periods` 和是否包含当前观测，避免未来函数和口径漂移。<https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html>
  - Goyenko/Kelly/Moskowitz/Su/Zhang《Trading Volume Alpha》：成交量预测更直接连接交易成本、冲击成本和组合执行，不应被简单等同于收益 alpha。<https://www.edhec.edu/sites/default/files/2025-11/Scientific%20Paper%20Ruslan%20Goyenko.%20ssrn-4802345.pdf>
  - GitHub `KangOxford/Volume-Forecasting`：公开代码/说明也把成交量预测放在 LOB、VWAP 和最优执行语境下，而不是直接当方向性交易信号。<https://github.com/KangOxford/Volume-Forecasting>
  - GitHub `fmzquant/strategies` 的 z-score 示例：z-score 可做偏离度指标，但阈值信号容易依赖具体市场状态，本阶段只借鉴“先看极端/反例”的审计思路，不复制策略。<https://github.com/fmzquant/strategies/blob/master/Z-Score-with-Signals.md>
- 我的判断：
  - `volume_zscore_60m` 的第一性含义是“近 30 分钟平均成交量相对 60 分钟基线的异常度”，更接近流动性/拥挤/信息到达标签。
  - 它可能帮助解释右尾，但不能直接等价为高质量入场；极端放量既可能是趋势确认，也可能是冲击、止损拥挤或开盘/低分辨率 artefact。
  - 因此 Stage243 只允许做固定分位、固定高低量能组、分钟图谱和反例审计，不允许写规则。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage243_volume_zscore_counterexample_atlas.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定 `volume_zscore_60m` rank quintile。
  - 固定组：`high_volume_q4q5`、`low_volume_q1q2`、`mid_volume_q3`，并单独拆 `volume_q4` 与 `volume_q5`。
  - atlas 固定类别：`q5_bad`、`q5_tail`、`q4_tail`、`low_volume_tail_miss`、`high_volume_low_resolution`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage239 joined signal-label audit，共 `219` 个事件。
- 账户规模：沿用官方曲线初始权益 `150,000`，本阶段不改变资金路径。
- 成本口径：沿用官方曲线；本阶段没有新增交易、滑点或手续费。
- 样本过滤：
  - 输入 Stage239 `joined_signal_label_audit`。
  - 每个事件只使用 Stage180 cutoff-filtered predecision minute parquet。
  - atlas 只画决策前最后 `120` 根分钟 K，价格路径按交易方向标准化，橙线为滚动 `volume_zscore`。
- 策略/归因口径：
  - `risk_bad_label = bottom_loss_visual OR maxdd_context`
  - `right_tail_label = right_tail_visual`
  - `volume_zscore_60m = (mean(volume_last30) - mean(volume_last60)) / std(volume_last60, ddof=1)`
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
  - `decision=stage243_volume_zscore_weak_high_volume_structure_but_q5_counterexamples_block_true_engine_no_rule`
  - `event_volume_row_count=219`
  - `stage239_universal_structure_watch_only=1`
  - `high_volume_count=88`
  - `high_volume_risk_bad_count=13`
  - `high_volume_risk_bad_rate=0.1477272727`
  - `high_volume_right_tail_count=10`
  - `high_volume_right_tail_rate=0.1136363636`
  - `high_volume_right_tail_coverage_rate=0.5555555556`
  - `high_volume_low_resolution_rate=0.4318181818`
  - `low_volume_count=87`
  - `low_volume_risk_bad_count=20`
  - `low_volume_risk_bad_rate=0.2298850575`
  - `low_volume_right_tail_count=6`
  - `low_volume_right_tail_rate=0.0689655172`
  - `q4_risk_bad_count=3`
  - `q4_risk_bad_rate=0.0681818182`
  - `q4_right_tail_count=5`
  - `q4_right_tail_rate=0.1136363636`
  - `q5_risk_bad_count=10`
  - `q5_risk_bad_rate=0.2272727273`
  - `q5_right_tail_count=5`
  - `q5_right_tail_rate=0.1136363636`
  - `rank_corr_volume_vs_risk_bad=-0.0403650598`
  - `rank_corr_volume_vs_right_tail=0.0623254037`
  - `rank_corr_volume_vs_low_resolution=-0.0151969918`
  - `q5_not_better_than_q4_risk_block=1`
  - `high_volume_tail_coverage_block=0`
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
  - 官方路径完全未变，Stage243 只是只读审计。
  - 图中 `high_q4q5=88 risk=0.148 tail=0.114` 看起来优于低量能，但同图标注 `q5 risk=0.227`，说明极端放量不是单调优势。
- volume quintile label rates：
  - Q4 最干净：`risk_bad_rate=0.0682`，`right_tail_rate=0.1136`。
  - Q5 与 Q4 的右尾率相同，风险坏账却反弹到 `0.2273`。
  - Q4 低分辨率率 `0.5455`，提示成交量线索可能夹杂事件时间/开盘结构问题。
- group label rates：
  - `high_volume_q4q5` 聚合低风险、高右尾，但拆开后主要由 Q4 拉低风险。
  - `low_volume_q1q2` 仍有 `6` 个右尾，不能作为削仓/过滤规则。
- split delta：
  - `2023/2025/CZCE` 对高量能较友好，但 `2021/2022` 风险反向，`2023` 右尾反向。
  - DCE 的高量能右尾弱于低量能，SHFE 风险改善有限。
  - 这不是跨周期、跨交易所稳定结构。
- volume-efficiency joint heatmap：
  - `VQ5/EQ5` 风险坏账率 `0.3571`，右尾率仅 `0.0714`，说明“高量能 + 高方向效率”也不能直接变成规则。
  - 少数绿色右尾格样本量很小，不能升级为普世规则。
- scatter：
  - 红点和绿点在正负量能 z-score 两侧都有分布，没有清晰分离边界。
- atlas：
  - `q5_bad` 页中 `rb2205.SHFE`、`SM205.CZCE`、`rb2305.SHFE`、`lh2301.DCE` 等高量能坏账样本显示，量能抬升常伴随急拉急跌、冲高回落、末端跳变或低分辨率。
  - `q5_tail` 页说明高量能确实能覆盖部分右尾，不能完全丢弃。
  - `low_volume_tail_miss` 页显示 `fu2209.SHFE`、`OI309.CZCE`、`jm2401.DCE`、`jm2405.DCE` 等低量能仍可成为右尾，低量能过滤会误伤大赢家。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage243_volume_zscore_counterexample_atlas/qmt_roll_stage243_c9_minrisk_volume_zscore_counterexample_atlas_report_stage243_volume_zscore_counterexample_atlas_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage243_volume_zscore_counterexample_atlas/qmt_roll_stage243_c9_minrisk_volume_zscore_counterexample_atlas_summary_stage243_volume_zscore_counterexample_atlas_v1.csv`
- orders：无
- daily：沿用官方曲线，本阶段未生成新 daily
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage243_volume_zscore_counterexample_atlas/qmt_roll_stage243_c9_minrisk_volume_zscore_counterexample_atlas_event_volume_zscore_audit_stage243_volume_zscore_counterexample_atlas_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage243_volume_zscore_counterexample_atlas/qmt_roll_stage243_c9_minrisk_volume_zscore_counterexample_atlas_quintile_summary_stage243_volume_zscore_counterexample_atlas_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage243_volume_zscore_counterexample_atlas/qmt_roll_stage243_c9_minrisk_volume_zscore_counterexample_atlas_group_summary_stage243_volume_zscore_counterexample_atlas_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage243_volume_zscore_counterexample_atlas/qmt_roll_stage243_c9_minrisk_volume_zscore_counterexample_atlas_split_summary_stage243_volume_zscore_counterexample_atlas_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage243_volume_zscore_counterexample_atlas/qmt_roll_stage243_c9_minrisk_volume_zscore_counterexample_atlas_volume_efficiency_joint_matrix_stage243_volume_zscore_counterexample_atlas_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage243_volume_zscore_counterexample_atlas/qmt_roll_stage243_c9_minrisk_volume_zscore_counterexample_atlas_atlas_manifest_stage243_volume_zscore_counterexample_atlas_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage243_volume_zscore_counterexample_atlas/qmt_roll_stage243_c9_minrisk_volume_zscore_counterexample_atlas_gate_status_stage243_volume_zscore_counterexample_atlas_v1.csv`

## 结论

- 本阶段结论：
  - `volume_zscore_60m` 比 Stage242 的多 bar persistence 更有继续观察价值，因为 `high_volume_q4q5` 覆盖 `10/18=55.56%` 右尾，且聚合风险低于低量能。
  - 但它不能进入 true engine：Q4 好、Q5 坏，结构非单调；低量能仍漏掉 `6` 个右尾；跨年/跨交易所不稳；atlas 中高量能坏账反例清晰。
  - 当前只能把 `volume_zscore_60m` 保留为“适度放量可能有质量，极端放量可能混入冲击”的解释/forward-watch 线索。
- 是否进入下一步：进入，但仍保持只读归因，不接规则。
- 下一步：
  - Stage244 可只读拆解 Q4 vs Q5 的差异：是否由低分辨率、末端单 tick、开盘 gap、方向效率分布、交易所/年份块或成交量路径形态造成。
  - 若 Q4 优势不能解释为普世机制，停止 volume 分支，转向 Stage238 其他 formal feature，如 `realized_volatility_30m` 或 `turnover_vwap_gap_30m`。
  - 禁止扫 `volume_zscore` 阈值、Q4 单桶、年份、交易所、方向或产品补丁。

## 过拟合反思

- 运行前判断：否。原因是 Stage243 固定使用 Stage239 已入选的 watch-only 特征，固定 rank quintile 和高/低量能组，不用最终收益反推阈值。
- 运行后判断：当前阶段否，但把 Q4 直接写成规则会过拟合。
- 原因：
  - 本阶段没有做 true engine、没有调参数、没有按 split 做救援。
  - Q4 是历史上看起来最好的单桶，若直接 promotion 就是在用样本内非单调形态反推规则。
  - atlas 同时展示 Q5 坏账、Q5 右尾和低量能漏右尾，避免只看成功样本。

## 继续价值反思

- 运行前判断：有价值。原因是 Stage239 显示 `volume_zscore_60m` 通过 watch-only gate，且它与流动性/冲击成本有第一性关系。
- 运行后判断：有继续归因价值，但没有直接交易化价值。
- 原因：
  - 有价值：高量能聚合确实覆盖超过一半右尾，说明它可能是高质量信号的组成部分。
  - 无直接交易化价值：Q5 风险反弹、低量能漏右尾、split 不稳，说明单独用量能会误伤或过拟合。
  - 后续必须先解释 Q4/Q5 差异的机制，而不是扫阈值。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage243 摘要。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、路线废弃正式合入、正式候选或跨线合并。
