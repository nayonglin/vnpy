# Stage239 read-only universal signal quality audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 13:05`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage238 formal feature table 之后的只读通用信号质量结构审计
- 是否重要突破：否
- 是否触发A/B：否，`ab_triggered=0`

## 外部调研与判断

- 参考资料：
  - pandas `qcut` 官方文档：用于分位分桶，说明分桶本质是按样本分位/秩做等频离散化；本阶段实际采用 rank percentile 手写五分位，避免重复值导致 `qcut` 失败。
  - pandas `DataFrame.rank` 官方文档：确认默认 tie 使用平均秩，可用于稳定 rank percentile。
  - SciPy `spearmanr` 官方文档：Spearman 是非参数单调关系度量，适合做排序结构审计，不要求线性关系。
  - GitHub `machine-learning-for-trading` alpha factor research 资料：确认量化因子常用 rank correlation/quantile 分析先做信号研究，再进入交易实现。
- 我的判断：Stage239 不应该扫阈值或写 true engine。219 个样本里，Stage177 的 `right_tail_visual/bottom_loss_visual/maxdd_context` 是历史路径/视觉标签，不是点时可交易条件；正确用途是只读判断“高质量分钟上下文是否有普世排序结构”。如果排序结构不稳定，应继续保持 `strategy_rule_allowed=0`。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage239_read_only_universal_signal_quality_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定只读标签：`risk_bad_label = bottom_loss_visual OR maxdd_context`、`right_tail_label = right_tail_visual`、`ordinary_clean_label`
  - 固定 7 个 Stage238 候选特征的预声明质量方向
  - 固定 `5` 个 rank quintile，`Q5` 表示预声明高质量方向
  - 固定 split stability 最小样本数 `8`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：继承官方路径曲线 `2018-2026`；Stage239 绑定 Stage238 formal rows `219` 行。
- 账户规模：继承官方曲线初始权益 `150,000`。
- 成本口径：本阶段不运行新回测；官方路径指标原样展示。
- 样本过滤：无额外过滤，Stage238 formal feature table `219/219` 全量绑定 Stage177 extension contract。
- 策略/归因口径：只读 rank/quantile/Spearman 审计；不写策略规则、不运行 true engine、不触发 A/B、不改正式配置、不连接 CTP/SimNow、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`（官方路径未变）
- 总收益：`26017.6251%`（官方路径未变）
- 最大回撤：`-45.0827%`（官方路径未变）
- Sharpe：本阶段未重算；继承官方正式路径历史口径 `1.6331`
- 总滑点：本阶段未重算；继承官方正式路径历史口径 `2,730,130`
- 总交易次数：本阶段未重算；继承官方正式路径历史口径 `787`
- 胜率：本阶段未重算；继承官方正式路径历史口径 `53.2560%`
- 其他关键指标：
  - `decision=stage239_read_only_universal_signal_quality_structure_watch_only_no_rule`
  - `joined_row_count=219`
  - `candidate_feature_count=7`
  - `candidate_feature_missing_count=0`
  - `risk_bad_label_count=41`
  - `right_tail_label_count=18`
  - `ordinary_clean_label_count=76`
  - `low_resolution_label_count=93`
  - `event_time_missing_label_count=18`
  - `runway_ready_label_count=87`
  - `feature_quintile_row_count=35`
  - `feature_stability_row_count=91`
  - `universal_structure_watch_only_count=2`
  - `strategy_feature_usable=0`
  - `strategy_rule_created=0`
  - `true_engine_run=0`
  - `ab_triggered=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage239_read_only_universal_signal_quality_audit/qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit_report_stage239_read_only_universal_signal_quality_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage239_read_only_universal_signal_quality_audit/qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit_summary_stage239_read_only_universal_signal_quality_audit_v1.csv`
- orders：无，本阶段不运行 true engine
- daily：无，本阶段不运行 true engine
- quality：
  - `qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit_joined_signal_label_audit_stage239_read_only_universal_signal_quality_audit_v1.csv`
  - `qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit_feature_rank_correlation_audit_stage239_read_only_universal_signal_quality_audit_v1.csv`
  - `qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit_feature_quintile_audit_stage239_read_only_universal_signal_quality_audit_v1.csv`
  - `qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit_feature_stability_audit_stage239_read_only_universal_signal_quality_audit_v1.csv`
  - `qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit_label_distribution_audit_stage239_read_only_universal_signal_quality_audit_v1.csv`
  - `qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit_gate_status_stage239_read_only_universal_signal_quality_audit_v1.csv`
  - 6 张 PNG 视觉图全部非空，并已目视检查关键图。

## 结论

- 本阶段结论：Stage239 找到 `2` 个 watch-only 线索，但没有产生正式候选。`aligned_bar_return_1m` 的 Q5 风险标签率从 Q1 `0.2326` 降到 Q5 `0.0682`，右尾率从 `0.0465` 升到 `0.1136`，是当前最值得继续复核的分钟质量方向；`volume_zscore_60m` 聚合 rank 也过 watch-only gate，但风险热图不是单调下降，Q5 风险率回到 `0.2273`，只能作为弱线索。`volume_participation_30m` 只有 `5` 个唯一值且只形成 `2` 个非空 quintile，当前横截面排序信息不足。
- 是否进入下一步：是，但只进入“非标签化点时规则设计/人工复核”阶段，不进入 true engine、A/B 或正式候选。
- 下一步：Stage240 应把 `aligned_bar_return_1m` 的结构拆成不依赖历史视觉标签的点时化规则草案，例如“入场前最后闭合 bar 与交易方向一致时，是否只做恢复/禁降风险保护，而不是过滤或加仓”；先做事件路径法证和反例 atlas，再决定是否值得写真实组合引擎。

## 过拟合反思

- 运行前判断：如果用 Stage177 视觉标签直接调阈值，就是过拟合；如果只用预声明方向、五分位排序、跨年/跨交易所稳定性审计，则不是策略过拟合，只是证据链审计。
- 运行后判断：否，本阶段没有形成交易规则，也没有按年份/品种/方向选阈值；但是 watch-only 结论仍存在标签依赖，不能被解读为可交易 alpha。
- 原因：`risk_bad/right_tail` 标签来自历史路径归因，具备事后性；本阶段只检验“点时特征与历史风险/右尾上下文的排序关系”，所有策略 gate 仍保持 `0`。

## 继续价值反思

- 运行前判断：有价值。Stage238 已经把 219 行正式特征表固定下来，必须先看是否存在普世信号质量结构，否则继续写真引擎会盲目。
- 运行后判断：仍有价值，但价值集中在 `aligned_bar_return_1m` 的第一性方向；`volume_zscore_60m` 和其他特征目前不足以单独支撑规则。
- 原因：资金曲线视觉确认官方路径未变；风险热图显示 `aligned_bar_return_1m` 高质量端风险标签显著更低且右尾率更高，但稳定性矩阵仍有 `2022/2026` 或部分交易所反向，下一步必须先做反例法证，不能直接进入候选。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage239 摘要。
- 是否更新 `research/registry.md`：否，仍在同一研究线内推进。
- 是否追加根目录 `memory.md/back_log.md`：否，不是重要突破、正式候选或路线废弃。
