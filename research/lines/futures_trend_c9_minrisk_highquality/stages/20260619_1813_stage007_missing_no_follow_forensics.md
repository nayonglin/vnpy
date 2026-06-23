# Stage007 C9/15w missing/no-follow 覆盖与反证标签审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 18:13`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读分钟覆盖与负质量标签法证；不生成可执行候选，不触发 A/B。
- 是否重要突破：否，但进一步收窄了分钟级质量规则的可用边界。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - Concretum `Backtesting Data Quality: Can Your Data Provider Be Trusted?`：`https://concretumgroup.com/backtesting-data-quality-can-your-data-provider-be-trusted/`
  - Freqtrade `Lookahead analysis`：`https://www.freqtrade.io/en/stable/lookahead-analysis/`
  - SSRN `Trend Following Strategies: A Practical Guide`：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5140633`
  - Trademetria `Understanding MAE and MFE Metrics`：`https://trademetria.com/blog/understanding-mae-and-mfe-metrics-a-guide-for-traders/`
  - GitHub `pysystemtrade`：`https://github.com/pst-group/pysystemtrade`
- 我的判断：分钟级规则的第一性约束是逐根实时可见、不能向未来看、不能用缺失数据伪造高质量样本。外部资料对日内数据质量和 lookahead 的风险判断一致：缺失/陈旧分钟K会直接污染止损、目标、仓位和入场质量判断。Stage006 的 `missing_30m` 不能用插值补成交易规则；Stage007 只能拆分缺失原因，并把 `no_follow_30m` 当作负质量线索审计。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage007_missing_no_follow_forensics.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无交易参数；新增只读分类：
  - `missing_entry_day_minutes`
  - `missing_risk_fields`
  - `risk_repair_would_help`
  - `no_follow_30m` 年度/品种贡献审计
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：官方 C9/15w 资金曲线 `2018-01-01` 至 `2026-06-15`。
- 账户规模：当前官方正式口径 `150000`。
- 成本口径：本阶段不重新定价、不改成本；官方指标沿用 Stage001/005/006 基线。
- 样本过滤：读取 Stage006 lot features，closed_lots 形态参考样本 `373` 笔。
- 策略/归因口径：
  - 官方正式版：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `stage847_c9_15w_stage819_05r_stop_retry_live`。
  - 本阶段只做分钟覆盖、缺失原因和 closed-lot 贡献曲线；贡献图不是可执行逐日盯市回测。
  - 不插值、不用 nearest_after、不用未来分钟K修复 entry-day 缺口。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：本阶段未重算，沿用 Stage001 官方基线 `1.6331`。
- 总滑点：本阶段未重算，沿用 Stage001 官方基线 `2,730,130`。
- 总交易次数：本阶段未重算，沿用 Stage001 官方基线 `787`。
- 胜率：本阶段未重算，沿用 Stage001 官方基线 `53.2560%`。
- 其他关键指标：
  - 官方 broker10 峰值：`111.7365%`
  - closed_lots 参考样本：`373` 笔，净实现盈亏 `39,705,171.20`
  - `missing_entry_day_minutes`：`118` 笔、`17` 个品种、`9` 年，净实现盈亏 `3,274,435.00`，正收益覆盖 `17.0214%`
  - `missing_risk_fields`：`37` 笔、`13` 个品种、`7` 年，净实现盈亏 `2,332,153.80`
  - `risk_repair_would_help_lots`：`0`，说明用 `risk_amount/(volume*size)` 会计恒等式不能修复本轮缺失样本
  - `no_follow_30m`：`85` 笔，净实现盈亏 `-4,045,508.60`，正收益覆盖 `7.6538%`，负收益覆盖 `34.9352%`
  - `no_follow_30m` 只有 `1` 个正收益年份：`2024` 年 `+2,245,150.00`；其余 `2020/2021/2022/2023/2025/2026` 年均为负

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage007_missing_no_follow_forensics/qmt_roll_stage007_c9_minrisk_missing_no_follow_forensics_report_stage007_missing_no_follow_forensics_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage007_missing_no_follow_forensics/qmt_roll_stage007_c9_minrisk_missing_no_follow_forensics_summary_stage007_missing_no_follow_forensics_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage007_missing_no_follow_forensics/qmt_roll_stage007_c9_minrisk_missing_no_follow_forensics_decision_stage007_missing_no_follow_forensics_v1.json`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage007_missing_no_follow_forensics/qmt_roll_stage007_c9_minrisk_missing_no_follow_forensics_features_stage007_missing_no_follow_forensics_v1.csv`
- missing_bucket_stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage007_missing_no_follow_forensics/qmt_roll_stage007_c9_minrisk_missing_no_follow_forensics_missing_bucket_stats_stage007_missing_no_follow_forensics_v1.csv`
- no_follow_year_stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage007_missing_no_follow_forensics/qmt_roll_stage007_c9_minrisk_missing_no_follow_forensics_no_follow_year_stats_stage007_missing_no_follow_forensics_v1.csv`
- no_follow_product_stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage007_missing_no_follow_forensics/qmt_roll_stage007_c9_minrisk_missing_no_follow_forensics_no_follow_product_stats_stage007_missing_no_follow_forensics_v1.csv`
- contribution_curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage007_missing_no_follow_forensics/qmt_roll_stage007_c9_minrisk_missing_no_follow_forensics_contribution_curve_stage007_missing_no_follow_forensics_v1.csv`
- official path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage007_missing_no_follow_forensics/qmt_roll_stage007_c9_minrisk_missing_no_follow_forensics_official_path_chart_stage007_missing_no_follow_forensics_v1.png`
- contribution chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage007_missing_no_follow_forensics/qmt_roll_stage007_c9_minrisk_missing_no_follow_forensics_contribution_chart_stage007_missing_no_follow_forensics_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage007_missing_no_follow_forensics/qmt_roll_stage007_c9_minrisk_missing_no_follow_forensics_atlas_page001_stage007_missing_no_follow_forensics_v1.png` 至 `page006`

## 视觉观察

- 官方路径图显示 `no_follow_30m` 和缺失样本分布在多个年份和多个回撤/上升阶段，不是单一窗口标签。
- closed-lot 贡献图显示 `all_except_no_follow` 曲线明显高于全样本参考，`no_follow_30m` 曲线长期向下，说明它是值得继续研究的负质量线索。
- 但该图是 closed-lot 贡献，不是逐日盯市权益。它只能说明“排除 no_follow 可能有边际价值”，不能证明真实执行规则已经成立。
- atlas page001 的 no-follow 大亏样本如 `SH607`、`cu2307`、`lh2411`、`jm2601` 多数在前 30 分钟没有顺势展开，随后进入逆向或震荡拖累。
- atlas page003 明确给出反例：`SH405`、`au2412`、`CF205`、`SM505` 都属于 no-follow，但最终贡献大额正收益。因此 no-follow 不能做硬删除。
- atlas page004 显示 `missing_entry_day_minutes` 包含 `ru2501`、`hc2210`、`OI605`、`rb2210` 这类关键右尾，且 nearest_after 往往相隔 `11` 至 `20` 天，不能拿后续分钟K补 entry-day 事实。

## 结论

- 本阶段结论：`stage007_readonly_no_follow_promising_but_not_trade_rule`。
- 是否进入下一步：是，但仍停留在只读或数据修复层，不进入真实交易候选。
- 下一步：
  - 优先从权威历史分钟源修复 `missing_entry_day_minutes`，不能插值或用未来分钟K补。
  - 若暂时无法补数据，任何分钟规则都必须把缺失 entry-day 样本视为 hard coverage limitation，并默认不应用该分钟规则。
  - `no_follow_30m` 可以作为“不恢复风险/维持最小风险”的候选反证标签继续审计，但必须先设计冻结、负向、非删除式规则；不得把它做成直接砍仓或黑名单。

## 过拟合反思

- 运行前判断：否。Stage007 不是根据最终收益找阈值，而是拆分 Stage006 已暴露的数据覆盖问题，并检验 no-follow 是否跨年、跨品种稳定。
- 运行后判断：否，但如果把 `no_follow_30m` 直接包装成删除规则会过拟合。
- 原因：本阶段保留了反例和缺失右尾，没有因为 `all_except_no_follow` 曲线好看就晋级规则；同时拒绝对 missing 样本插值，避免把数据缺口伪装成 alpha。

## 继续价值反思

- 运行前判断：有。Stage006 已显示 no-follow 净贡献为负，但 missing 样本含右尾，必须先拆清楚。
- 运行后判断：有，但价值在边界约束和数据修复，不在立即写引擎。
- 原因：no-follow 跨 `6/7` 个年份为负，说明它是值得研究的负质量状态；但 `2024` 和多个大赢家反例说明硬删除会误伤右尾。下一步应先补数据或设计“只限制恢复风险、不砍正式右尾”的低自由度冻结规则。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。当前属于并行研究线日常推进，暂不频繁改总索引。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是候选合入、路线废弃、正式候选、跨线合并或记录体系迁移，只是只读法证。
