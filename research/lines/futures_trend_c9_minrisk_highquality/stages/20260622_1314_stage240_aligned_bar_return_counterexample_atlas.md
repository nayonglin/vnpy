# Stage240 aligned bar return counterexample atlas

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 13:14`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage239 `aligned_bar_return_1m` watch-only 线索的非标签化点时反例 atlas
- 是否重要突破：否
- 是否触发A/B：否，`ab_triggered=0`

## 外部调研与判断

- 参考资料：
  - pandas `DataFrame.rank` 官方文档：rank/tie 处理适合做固定分位分层，不适合隐含阈值优化。
  - SciPy `spearmanr` 官方文档：Spearman 用于非参数单调关系观察，不能替代交易规则验证。
  - GitHub `quantopian/alphalens`：因子研究通常先做 quantile/IC/分层归因，再进入组合实现；本阶段只对应前者。
  - Matplotlib `subplots` 官方文档：用于多面板 atlas，把反例和原型用统一视觉尺度展示。
- 我的判断：Stage240 不能把 Stage239 的 Q5 直接转交易。正确问题不是“最后一分钟同向就开大仓吗”，而是“当未来某个最小风险/延迟恢复规则想降风险时，最后一分钟同向是否能作为保护右尾的 veto 证据”。本阶段只做前置反例法证。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage240_aligned_bar_return_counterexample_atlas.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `ATLAS_LOOKBACK_BARS=120`
  - `DIAGNOSTIC_LOOKBACKS=[5,10,30,60]`
  - `MIN_SPLIT_ROWS=4`
  - atlas 分类：`q5_bad_counterexample`、`q5_right_tail_prototype`、`q1_right_tail_miss`、`q1_risk_bad_baseline`、`q5_ordinary_clean_reference`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方路径曲线 `2018-2026`；Stage239 joined audit `219` 行；Stage180 cutoff-filtered predecision minute bars `219` 个事件。
- 账户规模：继承官方曲线初始权益 `150,000`。
- 成本口径：本阶段不运行新回测；官方路径指标原样展示。
- 样本过滤：无策略过滤；atlas 仅抽取 Q1/Q5 的反例和原型做可视化。
- 策略/归因口径：只读视觉法证；atlas 只画 `bar_end_ts <= decision_ts` 的决策前分钟路径；不使用入场后价格生成特征，不创建策略规则、不运行 true engine、不触发 A/B、不改正式配置、不连接 CTP/SimNow、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`（官方路径未变）
- 总收益：`26017.6251%`（官方路径未变）
- 最大回撤：`-45.0827%`（官方路径未变）
- Sharpe：本阶段未重算；继承官方正式路径历史口径 `1.6331`
- 总滑点：本阶段未重算；继承官方正式路径历史口径 `2,730,130`
- 总交易次数：本阶段未重算；继承官方正式路径历史口径 `787`
- 胜率：本阶段未重算；继承官方正式路径历史口径 `53.2560%`
- 其他关键指标：
  - `decision=stage240_aligned_bar_return_visible_but_counterexamples_block_true_engine_no_rule`
  - `joined_row_count=219`
  - `event_microstructure_row_count=219`
  - `q1_count=43`
  - `q5_count=44`
  - `q1_risk_bad_count=10`，`q1_risk_bad_rate=0.2326`
  - `q5_risk_bad_count=3`，`q5_risk_bad_rate=0.0682`
  - `q1_right_tail_count=2`，`q1_right_tail_rate=0.0465`
  - `q5_right_tail_count=5`，`q5_right_tail_rate=0.1136`
  - `right_tail_label_count=18`
  - `q5_right_tail_coverage_rate=0.2778`
  - `q1_degenerate_last_bar_count=22/43=0.5116`
  - `q5_degenerate_last_bar_count=28/44=0.6364`
  - `atlas_event_count=22`
  - `atlas_page_count=5`
  - `visual_file_count=9`
  - `strategy_feature_usable=0`
  - `strategy_rule_created=0`
  - `true_engine_run=0`
  - `ab_triggered=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage240_aligned_bar_return_counterexample_atlas/qmt_roll_stage240_c9_minrisk_aligned_bar_return_counterexample_atlas_report_stage240_aligned_bar_return_counterexample_atlas_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage240_aligned_bar_return_counterexample_atlas/qmt_roll_stage240_c9_minrisk_aligned_bar_return_counterexample_atlas_summary_stage240_aligned_bar_return_counterexample_atlas_v1.csv`
- orders：无，本阶段不运行 true engine
- daily：无，本阶段不运行 true engine
- quality：
  - `qmt_roll_stage240_c9_minrisk_aligned_bar_return_counterexample_atlas_event_microstructure_audit_stage240_aligned_bar_return_counterexample_atlas_v1.csv`
  - `qmt_roll_stage240_c9_minrisk_aligned_bar_return_counterexample_atlas_cohort_summary_stage240_aligned_bar_return_counterexample_atlas_v1.csv`
  - `qmt_roll_stage240_c9_minrisk_aligned_bar_return_counterexample_atlas_split_summary_stage240_aligned_bar_return_counterexample_atlas_v1.csv`
  - `qmt_roll_stage240_c9_minrisk_aligned_bar_return_counterexample_atlas_nonlabel_rule_sketch_stage240_aligned_bar_return_counterexample_atlas_v1.csv`
  - `qmt_roll_stage240_c9_minrisk_aligned_bar_return_counterexample_atlas_atlas_manifest_stage240_aligned_bar_return_counterexample_atlas_v1.csv`
  - `qmt_roll_stage240_c9_minrisk_aligned_bar_return_counterexample_atlas_gate_status_stage240_aligned_bar_return_counterexample_atlas_v1.csv`
  - 9 张 PNG 视觉图全部非空，并已目视检查关键图。

## 视觉观察

- 官方资金/回撤路径图确认 Stage240 不改变正式路径，只挂载 q1/q5 事件摘要。
- Q5 bad counterexample atlas 显示 `lh2301.DCE 2022-11-23`、`SM205.CZCE 2022-01-12` 在决策前已有明显顺势推进，最后一根又大幅同向跳，但历史标签仍是 `maxdd_context/bottom_loss`；`ru2605.SHFE 2026-01-27` 则是前 120 根整体逆向后最后局部修复。结论：最后一分钟同向不是释放风险充分条件。
- Q5 right-tail atlas 显示右尾原型不是统一形态：有长期高位横盘、有末端尖跳、有先深度逆向再修复。这不支持单一最后一分钟规则。
- split heatmap 显示大多数有效年/交易所切片 Q5 风险率低于 Q1，但 `2026` 是红色反例且样本很小；因此不能按局部切片信号进入 true engine。
- Q5 退化最后一根 OHLC 比例 `28/44=63.64%`，高于 Q1 的 `22/43=51.16%`，说明该特征混有开盘前/决策前最后一分钟流动性或单 tick 结构，必须在下一步剥离。

## 结论

- 本阶段结论：`aligned_bar_return_1m` 有继续研究价值，但 Stage240 明确拦住浅规则。它不能作为过滤器、加仓器或“最后一分钟同向就释放风险”的规则；当前唯一合理的未来草案是保护性 veto：如果未来某个最小风险/延迟恢复规则要降低官方风险，`aligned_bar_return_1m` 可能只用于禁止误伤右尾，且必须先剥离退化最后 bar 与开盘结构。
- 是否进入下一步：是，但只进入 Stage241 的“退化最后 bar/开盘结构剥离审计”，仍不进入 true engine、A/B 或正式候选。
- 下一步：Stage241 应在不引入收益标签阈值的前提下，把 `aligned_bar_return_1m` 拆成 `last_bar_degenerate_ohlc`、决策前最后 5/30/60 bar 的方向结构、最后成交量占比等点时化组成，判断 Q5 的价值是否只是退化最后 bar 或夜盘/开盘 artefact。

## 过拟合反思

- 运行前判断：如果用 Q5 的历史标签优势直接写规则，是过拟合；如果固定只读 Q1/Q5 反例 atlas 并保持 gate=0，则不是策略过拟合。
- 运行后判断：否，本阶段没有交易规则、没有调阈值、没有按年份/品种/方向补丁化；但也没有证明策略有效。
- 原因：所有 Stage177 标签只用于反例分组，atlas 只画决策前可见分钟路径。反例显示单一最后 bar 方向无法穿越周期，尤其有 Q5 坏例和退化 bar 污染。

## 继续价值反思

- 运行前判断：有价值。Stage239 已经把线索收缩到 `aligned_bar_return_1m`，需要用视觉反例判断是否太浅。
- 运行后判断：仍有价值，但必须加深，不是直接写 true engine。
- 原因：Q5 相对 Q1 的风险坏标签率显著较低且右尾率较高，说明该方向不是噪声；但右尾覆盖只有 `5/18=27.78%`，且 Q5 仍有 `3` 个坏例与 `63.64%` 退化最后 bar，下一步必须先剥离 artefact。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage240 摘要。
- 是否更新 `research/registry.md`：否，仍在同一研究线内推进。
- 是否追加根目录 `memory.md/back_log.md`：否，不是重要突破、正式候选或路线废弃。
