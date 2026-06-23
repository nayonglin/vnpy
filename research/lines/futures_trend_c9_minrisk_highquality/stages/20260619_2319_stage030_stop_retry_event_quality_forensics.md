# Stage030 C9 stop/retry 事件质量只读法证

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-19 23:19 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方 C9/15w stop/retry 事件归因与分钟 K atlas；不新增交易规则、不改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Clare/Seaton/Thomas/Smith, `Trend following, stop losses and the frequency of trading`：https://openaccess.city.ac.uk/id/eprint/17842/8/BLACKBOX%20%20%20SSRN-id2126476.pdf
  - Rob Carver / qoppac, `Dynamic trend following`：https://qoppac.blogspot.com/2020/12/dynamic-trend-following.html
  - Research Affiliates, `Stop the Losses!`：https://www.researchaffiliates.com/content/dam/ra/publications/pdf/1099-stop-the-losses.pdf
  - GitHub 参考实现检索：`PyTrendFollow`（https://github.com/chrism2671/PyTrendFollow）、`Statistical-Trading-Strategy-in-Futures-Markets`（https://github.com/DhyeyMavani2003/Statistical-Trading-Strategy-in-Futures-Markets）等趋势/通道/止损类项目，只作工程形态参考，不直接复制规则。
- 我的判断：趋势系统的止损/重入不是越复杂越好。外部资料共同提示，止损可以改善极端风险，但会伤害右尾和提高 whipsaw 成本；所以本阶段只做官方 C9/15w 已有 `0.5R stop/retry once` 的事件归因，不从历史成功/失败重入状态反推交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage030_stop_retry_event_quality_forensics.py`
- 修改脚本：同上；修正 `-1` bar index 哨兵值污染重入延迟统计，并将 JSON 中 NaN/Inf 规范为 `null`，追加 pandas `observed=False` 以保持复跑稳定。
- 删除脚本：无
- 新增参数：无交易参数；只读归因 bucket `FIRST_STOP_EARLY_BAR=30`、atlas 上限 `MAX_ATLAS_ROWS=24`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w closed lots `2018-01-15` 至 `2026-06-02`
- 账户规模：`150000`
- 成本口径：沿用官方 C9/15w 输出，总滑点 `2,730,130`
- 样本过滤：无过滤，官方 `399` 笔 closed lots 全量参与；Stage019 stop/retry event ledger 仅作事件时点和最终状态标签。
- 策略/归因口径：官方 closed-lot PnL 使用 Stage028 features；stop/retry 事件使用 Stage019 event ledger；绑定键固定为 `vt_symbol|direction|entry_date`。`final_state` 是未来归因标签，不是交易时可见特征。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot `36.0902%`
- 其他关键指标：
  - official closed lots：`399`
  - stop/retry event lots：`180`
  - stop/retry event keys：`125`
  - event net PnL：`-5,667,538.40`
  - flat stop net PnL：`-7,989,630.00`
  - open_after_reentry net PnL：`+2,322,091.60`
  - `no_event`：`219` 笔，净 PnL `48,722,151.00`
  - `flat_no_reentry`：`71` 笔，净 PnL `-5,933,249.00`
  - `flat_retry_failed`：`52` 笔，净 PnL `-2,056,381.00`
  - `open_after_reentry`：`57` 笔，净 PnL `+2,322,091.60`
  - `flat_retry_failed` 事件 median first stop bar `2`，median reentry latency `100.5` bars
  - `open_after_reentry` 事件 median first stop bar `8`，median reentry latency `61` bars

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage030_stop_retry_event_quality_forensics/qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_report_stage030_stop_retry_event_quality_forensics_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage030_stop_retry_event_quality_forensics/qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_summary_stage030_stop_retry_event_quality_forensics_v1.csv`
- orders：无
- daily：
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_path_stop_retry_state_chart_stage030_stop_retry_event_quality_forensics_v1.png`
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_stop_retry_contribution_chart_stage030_stop_retry_event_quality_forensics_v1.png`
- quality：
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_features_stage030_stop_retry_event_quality_forensics_v1.csv`
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_lot_state_summary_stage030_stop_retry_event_quality_forensics_v1.csv`
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_event_summary_stage030_stop_retry_event_quality_forensics_v1.csv`
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_state_year_matrix_stage030_stop_retry_event_quality_forensics_v1.csv`
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_state_product_matrix_stage030_stop_retry_event_quality_forensics_v1.csv`
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_first_stop_bucket_summary_stage030_stop_retry_event_quality_forensics_v1.csv`
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_quality_crosstab_stage030_stop_retry_event_quality_forensics_v1.csv`
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_state_year_heatmap_stage030_stop_retry_event_quality_forensics_v1.png`
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_product_state_heatmap_stage030_stop_retry_event_quality_forensics_v1.png`
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_first_stop_timing_chart_stage030_stop_retry_event_quality_forensics_v1.png`
  - `qmt_roll_stage030_c9_minrisk_stop_retry_event_quality_forensics_atlas_page001_stage030_stop_retry_event_quality_forensics_v1.png` 至 `atlas_page005`

## 视觉观察

- 资金路径图显示，官方 C9/15w 主权益仍来自 `no_event` 交易；stop/retry 事件总体累计贡献自 2022 后持续下行，最终约 `-566.75万`。
- `open_after_reentry` 绿色线为正，最终约 `+232.21万`，但不足以覆盖 `flat_no_reentry` 和 `flat_retry_failed` 两条负贡献线。
- 年度热图显示 `flat_no_reentry` 与 `flat_retry_failed` 跨多个年份为负，不是单一年份问题；产品热图显示 MA/fu/jm/ru/rb/SM/AP/cu 等多产品负贡献，不能写品种黑名单。
- first-stop timing 图显示第一次 stop 发生很早并不能稳定区分成功/失败：`first_stop_0_4` 里三种状态都存在，且 `open_after_reentry` 也有明显亏损桶。
- minute atlas 显示最差 retry_failed 多数是开仓前几分钟打 0.5R 后重回入场，再次失败；最佳 open_after_reentry 也常依赖后续长时间重回，属于事后路径状态，不是开仓时可见高质量信号。

## 结论

- 本阶段结论：`stage030_stop_retry_forensics_no_candidate_future_state_not_tradable`
- 是否进入下一步：不进入交易规则、true engine 或 A/B。
- 下一步：若继续 stop/retry 路线，只允许寻找“重入当刻可见”的跨年跨品种结构，例如重入时的价差恢复质量、成交量/波动收缩、相对 entry/progress/stop 的路径结构；不得用 `open_after_reentry`、最终 PnL、产品、年份、方向、first-stop 单桶或重入等待长度反推规则。

## 过拟合反思

- 运行前判断：否。只读归因正式版已有 stop/retry 事件，不新增参数、不做筛选、不改引擎。
- 运行后判断：否。阶段决策明确把 `final_state` 定义为未来标签，并拒绝把成功重入状态交易化。
- 原因：真正过拟合风险来自下一步错误使用本阶段结果，例如“只保留 open_after_reentry”或按亏损产品/年份/first-stop bucket 补丁化；本阶段已经把这些路径标为禁止。

## 继续价值反思

- 运行前判断：有价值。stop/retry 是当前正式版分钟级风控核心，必须先知道它的事件贡献结构。
- 运行后判断：有价值，但价值转为归因约束与下一步特征边界，不是候选策略。
- 原因：事件总体净负说明 stop/retry 仍是 C9 左尾的重要账本；成功重入有右尾价值说明不能简单取消重试。下一步只有在“重入当刻可见信息”上找到普世结构，才值得写冻结引擎。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage030 摘要与下一步约束。
- 是否更新 `research/registry.md`：否；非正式候选、非重要突破、非跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段是本线内部只读归因，不是正式候选或重大突破。
