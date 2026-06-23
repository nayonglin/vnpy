# Stage005 C9/15w 信号质量分钟图谱只读归因

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 17:52`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因、视觉审计；不生成交易候选，不触发 A/B。
- 是否重要突破：否。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - SSRN `Trend Following Strategies: A Practical Guide`：`https://papers.ssrn.com/sol3/Delivery.cfm/5140633.pdf?abstractid=5140633&mirid=1`
  - SSRN `Position sizing methods for a trend following CTA`：`https://www.diva-portal.org/smash/get/diva2%3A730028/fulltext01.pdf`
  - SSRN `A Guide to Trend Following Strategies`：`https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID4438260_code412374.pdf?abstractid=4438260&mirid=1`
  - GitHub `pysystemtrade`：`https://github.com/pst-group/pysystemtrade`
- 我的判断：公开资料支持趋势策略应把重点放在长期稳健、成本压力、仓位风险和多市场共性，而不是事后筛年份或调单一阈值。Stage005 因此只做分钟形态归因，不把 `0.5R`、前 30 分钟斜率或单个样本形状直接转成规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage005_signal_quality_visual_forensics.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无交易参数；新增只读归因维度 `broker10_cap`、`top_winner`、`top_loser`、`stage004_restore_failure/open`，以及 `first_touch`、`first_30m_directional_r`、`entry_day_mfe_r`、`entry_day_mae_r`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：官方 C9/15w 资金曲线 `2018-01-01` 至 `2026-06-15`。
- 账户规模：当前官方正式口径 `150000`。
- 成本口径：沿用 Stage001/004 官方输出；本阶段不重新定价、不改变成本。
- 样本过滤：
  - `30` 个 Stage004/正式路径 broker10 cap 相关事件。
  - `4` 个 Stage004 restore 事件，其中 `3` 个同日失败。
  - C9 核心 closed_lots 参考样本 `373` 笔；选取 top winner `8` 笔、top loser `8` 笔做分钟 atlas。
- 策略/归因口径：官方正式版仍为 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `stage847_c9_15w_stage819_05r_stop_retry_live`。closed_lots 文件名沿用脚本输出中的 `official_closed_lots`，但内容是 Stage847/C9 core 30w closed_lots 形态参考，不把它当成 15w 资金指标来源。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：本阶段未重算，沿用 Stage001 官方基线 `1.6331`。
- 总滑点：本阶段未重算，沿用 Stage001 官方基线 `2,730,130`。
- 总交易次数：本阶段未重算，沿用 Stage001 官方基线 `787`。
- 胜率：本阶段未重算，沿用 Stage001 官方基线 `53.2560%`。
- 其他关键指标：
  - broker10 峰值：`111.7365%`
  - broker10 cap 事件：`30`
  - closed_lots 形态参考：`373`
  - top winner：`8`，总实现盈亏 `15,008,220`，median R `69.0333`
  - top loser：`8`，总实现盈亏 `-1,768,520`，median R `-5.2348`
  - Stage004 restore failure：`3`，`progress_first_pct=100%`，median first 30m directional R `6.5`，但总实现盈亏 `-5,785`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage005_signal_quality_visual_forensics/qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_report_stage005_signal_quality_visual_forensics_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage005_signal_quality_visual_forensics/qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_summary_stage005_signal_quality_visual_forensics_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage005_signal_quality_visual_forensics/qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_decision_stage005_signal_quality_visual_forensics_v1.json`
- bucket_stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage005_signal_quality_visual_forensics/qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_bucket_stats_stage005_signal_quality_visual_forensics_v1.csv`
- event_features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage005_signal_quality_visual_forensics/qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_event_features_stage005_signal_quality_visual_forensics_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage005_signal_quality_visual_forensics/qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_path_marker_chart_stage005_signal_quality_visual_forensics_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage005_signal_quality_visual_forensics/qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_atlas_page001_stage005_signal_quality_visual_forensics_v1.png` 至 `page006`

## 视觉观察

- 资金路径图显示 broker10/cap、top winner、top loser、restore failure 分布在多个年份和不同权益阶段，并不只集中在一个坏窗口；说明风险不是单一年份补丁可以解决。
- top winner 的早期顺势推进更强：median first 30m directional R 为 `8.0833`，entry-day MFE median 为 `19.625R`。
- 但 `progress_first` 不是充分条件：top loser 中 `CF101`、`jm2005`、`si2310` 也出现 progress-first；Stage004 的 `MA205/rb2205/ru2101` restore failure 全部 progress-first，且前 30 分钟和日内 MFE 看起来很强，最终仍失败。
- 因此不能把 Stage002/004 的 `0.5R 后恢复风险` 当作高质量信号定义。更接近本质的结构可能是“推进后是否持续低逆行、是否快速形成方向斜率并避免回到原入场风险区”，但这仍需下一阶段用入场后可见信息逐根验证，不能事后用最终 MFE/MAE 调阈值。

## 结论

- 本阶段结论：`stage005_readonly_no_trade_rule_yet`。只读归因有效地否定了“早期触及 `0.5R` 或 progress-first 就恢复满风险”的简单想法；它提供了下一步研究方向，但没有形成可接入正式版的规则。
- 是否进入下一步：是。
- 下一步：Stage006 应做冻结的只读/小候选验证：用前 `15/30/60` 分钟内可见的“低逆行热度 + 顺势斜率延续”作为执行层标签，先观察是否跨年份、跨品种同时区分 top winner 与 top loser；在通过前不得恢复为交易规则。

## 过拟合反思

- 运行前判断：否。本阶段没有调交易参数，只把既有失败候选和赢家/亏损样本放到同一图谱中做归因。
- 运行后判断：否，但下一步有过拟合风险。
- 原因：当前输出没有筛品种、年份、方向，也没有把视觉样本直接变成规则；风险在于下一阶段如果按 `8R`、`6.5R` 或个别图形调阈值，会重新落入样本内拟合。

## 继续价值反思

- 运行前判断：有。Stage002/003/004 已证明补丁式控仓会伤右尾，需要回到信号质量本身。
- 运行后判断：有。
- 原因：Stage005 证明了 `0.5R/progress-first` 太浅，同时也显示大赢家和大亏在“早期推进强度、逆行热度、日内持续性”上存在可研究差异；这值得继续做冻结规则验证，但不能跳过跨周期审计。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是候选合入、路线废弃、正式候选、跨线合并或记录体系迁移，只是只读归因。
