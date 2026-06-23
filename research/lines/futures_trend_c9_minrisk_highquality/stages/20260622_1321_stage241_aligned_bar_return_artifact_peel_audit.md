# Stage241 aligned bar return artefact peel audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 13:21`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage240 `aligned_bar_return_1m` 的退化最后 bar / 开盘 artefact 剥离审计
- 是否重要突破：否
- 是否触发A/B：否，`ab_triggered=0`

## 外部调研与判断

- 参考资料：
  - pandas `pct_change` 官方文档：相邻行变化适合拆分最后一根 bar 的方向贡献与去掉最后一根后的前置结构。
  - pandas `groupby` 官方文档：用于固定结构分组汇总，不做标签驱动阈值搜索。
  - Matplotlib `imshow` / annotated heatmap 官方示例：用于展示 original Q 与去掉最后一根后的 Q 转移矩阵。
  - GitHub `quantopian/alphalens` quantile tear sheet 资料：因子研究可做 quantile 分层和转移观察，但不能直接替代策略实现。
- 我的判断：Stage241 的核心不是把 Q5 再筛一遍，而是判断 Stage239/240 的 Q5 优势是否被最后一根退化/单 tick/gap 污染。如果污染严重，就不能把 `aligned_bar_return_1m` 当作最后一分钟趋势确认。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage241_aligned_bar_return_artifact_peel_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定结构剥离：`last_bar_degenerate_ohlc`、`last_bar_single_tick`、`degenerate_nonzero_gap_flag`
  - 固定去最后一根后的前一根方向收益 quintile：`without_last_1bar_quintile`
  - 固定 atlas 分类：`q5_degenerate_bad`、`q5_degenerate_tail`、`q5_nonartifact_tail`、`q5_nonartifact_bad`、`q5_drop_without_last`、`q5_persist_without_last`
  - `ATLAS_LOOKBACK_BARS=120`
  - `MIN_SPLIT_ROWS=4`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方路径曲线 `2018-2026`；Stage239 joined audit `219` 行；Stage180 cutoff-filtered predecision minute bars `219` 个事件。
- 账户规模：继承官方曲线初始权益 `150,000`。
- 成本口径：本阶段不运行新回测；官方路径指标原样展示。
- 样本过滤：无交易过滤；只做结构分组和 atlas 抽样展示。
- 策略/归因口径：只读 artefact peel audit；不使用入场后价格生成特征，不创建策略规则、不运行 true engine、不触发 A/B、不改正式配置、不连接 CTP/SimNow、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`（官方路径未变）
- 总收益：`26017.6251%`（官方路径未变）
- 最大回撤：`-45.0827%`（官方路径未变）
- Sharpe：本阶段未重算；继承官方正式路径历史口径 `1.6331`
- 总滑点：本阶段未重算；继承官方正式路径历史口径 `2,730,130`
- 总交易次数：本阶段未重算；继承官方正式路径历史口径 `787`
- 胜率：本阶段未重算；继承官方正式路径历史口径 `53.2560%`
- 其他关键指标：
  - `decision=stage241_aligned_bar_q5_partly_artifact_peel_blocks_true_engine_no_rule`
  - `event_artifact_row_count=219`
  - `q5_count=44`
  - `q5_risk_bad_count=3`，`q5_risk_bad_rate=0.0682`
  - `q5_right_tail_count=5`，`q5_right_tail_rate=0.1136`
  - `q5_degenerate_last_bar_count=28`，`q5_degenerate_last_bar_rate=0.6364`
  - `q5_single_tick_last_bar_count=28`，`q5_single_tick_last_bar_rate=0.6364`
  - `q5_degenerate_nonzero_gap_count=28`
  - `q5_nonartifact_lastbar_count=16`
  - `q5_nonartifact_risk_bad_count=1`，`q5_nonartifact_risk_bad_rate=0.0625`
  - `q5_nonartifact_right_tail_count=1`，`q5_nonartifact_right_tail_rate=0.0625`
  - `q5_degenerate_right_tail_count=4`，`q5_degenerate_right_tail_rate=0.1429`
  - `q5_drop_without_last_1bar_count=19`，`q5_drop_without_last_1bar_rate=0.4318`
  - `q5_persist_without_last_1bar_count=15`，`q5_persist_without_last_1bar_rate=0.3409`
  - `atlas_event_count=20`
  - `atlas_page_count=6`
  - `visual_file_count=11`
  - `strategy_feature_usable=0`
  - `strategy_rule_created=0`
  - `true_engine_run=0`
  - `ab_triggered=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage241_aligned_bar_return_artifact_peel_audit/qmt_roll_stage241_c9_minrisk_aligned_bar_return_artifact_peel_audit_report_stage241_aligned_bar_return_artifact_peel_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage241_aligned_bar_return_artifact_peel_audit/qmt_roll_stage241_c9_minrisk_aligned_bar_return_artifact_peel_audit_summary_stage241_aligned_bar_return_artifact_peel_audit_v1.csv`
- orders：无，本阶段不运行 true engine
- daily：无，本阶段不运行 true engine
- quality：
  - `qmt_roll_stage241_c9_minrisk_aligned_bar_return_artifact_peel_audit_event_artifact_audit_stage241_aligned_bar_return_artifact_peel_audit_v1.csv`
  - `qmt_roll_stage241_c9_minrisk_aligned_bar_return_artifact_peel_audit_artifact_group_summary_stage241_aligned_bar_return_artifact_peel_audit_v1.csv`
  - `qmt_roll_stage241_c9_minrisk_aligned_bar_return_artifact_peel_audit_without_last_quintile_transition_stage241_aligned_bar_return_artifact_peel_audit_v1.csv`
  - `qmt_roll_stage241_c9_minrisk_aligned_bar_return_artifact_peel_audit_split_summary_stage241_aligned_bar_return_artifact_peel_audit_v1.csv`
  - `qmt_roll_stage241_c9_minrisk_aligned_bar_return_artifact_peel_audit_atlas_manifest_stage241_aligned_bar_return_artifact_peel_audit_v1.csv`
  - `qmt_roll_stage241_c9_minrisk_aligned_bar_return_artifact_peel_audit_gate_status_stage241_aligned_bar_return_artifact_peel_audit_v1.csv`
  - 11 张 PNG 视觉图全部非空，并已目视检查关键图。

## 视觉观察

- 官方资金/回撤路径图确认 Stage241 不改变正式路径，只做 artefact peel 审计。
- group label rate 图显示：`q5_all` 的低风险率仍存在，但 `q5_nonartifact_lastbar` 只剩 `16` 个事件，右尾率降到 `1/16=0.0625`；`q5_degenerate_last_bar` 承担 `4/5` 个 Q5 右尾。
- transition heatmap 显示原始 Q5 去掉最后一根后有 `14+5=19` 个掉到 Q1/Q2，只有 `7+8=15` 个仍在 Q4/Q5；原始 Q5 很大一部分由最后一根驱动。
- atlas 第 5 页显示多个原始 Q5 的前置路径并不强，最后红色单 tick/gap 把样本拉成 Q5；这不是可穿越周期的高质量状态。
- `q5_nonartifact_bad` 仍有 `ru2605.SHFE 2026-01-27`，说明即使剥离退化最后 bar，也不能直接用非 artefact Q5 放行风险。

## 结论

- 本阶段结论：Stage241 将 `aligned_bar_return_1m` 从“最后一分钟同向质量信号”降级为“最后 bar/gap 污染严重的弱线索”。它不能进入 true engine，也不能作为恢复官方风险、过滤或加仓规则。继续研究必须换成更稳的前置多 bar 状态，例如去掉最后一根后的 30/60 bar 方向结构、持续性、回撤热度，而不是最后一根本身。
- 是否进入下一步：是，但下一步应重构特征，不继续救最后一分钟信号。
- 下一步：Stage242 应基于 Stage241 event artifact audit，固定提出 `without_last_30bar` / `without_last_60bar` 的多 bar predecision persistence 只读审计，确认是否存在不依赖最后单 tick/gap 的普世结构；继续禁止 true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：如果根据标签挑选“保留哪些 Q5”就是过拟合；按退化 OHLC、single tick、去掉最后一根后的前一根方向收益做结构剥离，不是策略过拟合。
- 运行后判断：否，本阶段仍未形成交易规则，也没有用年份/品种/方向调参；但原始 `aligned_bar_return_1m` 作为交易信号的可信度被显著削弱。
- 原因：`28/44` 个 Q5 是退化且 single-tick 的非零 gap，`19/44` 去掉最后一根后掉到 Q1/Q2；这是数据结构污染，不是可交易 alpha。

## 继续价值反思

- 运行前判断：有价值。Stage240 已经发现 Q5 退化最后 bar 比例高，必须判断是不是 artefact。
- 运行后判断：仍有价值，但方向要改。继续研究 `aligned_bar_return_1m` 本身价值不大，应该转到去最后一根后的多 bar 前置结构。
- 原因：Q5 低风险优势没有完全消失，但右尾覆盖主要来自退化最后 bar，非 artefact 样本右尾仅 `1/16`；这不满足“高质量信号用最小风险搏最大收益”的要求。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage241 摘要。
- 是否更新 `research/registry.md`：否，仍在同一研究线内推进。
- 是否追加根目录 `memory.md/back_log.md`：否，不是重要突破、正式候选或路线废弃。
