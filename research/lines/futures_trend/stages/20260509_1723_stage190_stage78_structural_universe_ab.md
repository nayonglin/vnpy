# Stage190 第78结构基础池A/B实验

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-09 17:23 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：第78正式基准的品种基础池候选A/B验证
- 是否重要突破：否
- 是否触发A/B：是，触发 `skills/version-ab-experiment/SKILL.md`

## 外部调研与判断

- 参考资料：
  - Futures trend following / managed futures 的常见实践是先限定流动性、交易成本、保证金和可交易市场，再在其中做趋势信号与资产选择。
  - GitHub `amstrdm/mlm-trend-following` 采用固定流动期货合约池并叠加波动过滤，说明“先定义可交易宇宙”比无脑全市场交易更常见。
  - vn.py 是交易和回测框架，不替策略决定品种池；品种池必须由策略研究单独验证。
- 我的判断：
  - 全市场基础池研究有价值，但不能用历史收益TopN替代正式池。
  - 本阶段只允许验证“结构性可交易基础池”是否能承接第78，不继续调 TopN 或阈值救结果。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage190_stage78_structural_universe_ab.py`
- 修改脚本：
  - 同上：补充 B 臂关闭 AI 时的展示字段保护，避免后续报告误读。
- 删除脚本：无
- 新增参数：无策略参数；新增实验臂定义 A/B/C/D
- 修改参数：无正式第78参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30
- 账户规模：200,000
- 成本口径：沿用当前回测元数据滑点/手续费口径
- 样本过滤：完整第78正式基准对照 + 结构预筛基础池
- 策略/归因口径：
  - A：`official_stage78_defensive_v1`
  - B：第78机制 + 结构基础池，关闭月度AI过滤
  - C：第78机制 + 结构基础池 + `ai_structural_top8_entry_filter`
  - D：第78机制 + 结构基础池 + `simple_structural_top8_entry_filter`

## 结果

| 实验臂 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 官方第78 | 4,637,530 | 2218.765% | -36.9907% | 1.2922 | 261,740 | 782 | 42.1053% |
| B 结构池全开无AI | 672,750 | 236.375% | -52.8883% | 0.3328 | 254,020 | 1,431 | 40.4138% |
| C 结构池+AI top8 | 515,780 | 157.890% | -70.4333% | 0.3000 | 118,730 | 788 | 41.4392% |
| D 结构池+简单top8 | 519,070 | 159.535% | -51.5058% | 0.3042 | 144,400 | 806 | 41.1192% |

- 对比 A，C 期末权益低 `4,121,750`，总收益低 `2060.875` 个百分点，最大回撤恶化 `33.4426` 个百分点，Sharpe 低 `0.9922`。
- B 说明结构池全开会显著增加交易次数，且收益/回撤质量远弱于 A。
- D 回撤好于 C，但仍明显弱于 A，不具备替代或晋级价值。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage190_stage78_structural_universe_ab_report.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage190_stage78_structural_universe_ab_summary.csv`
- summary_json：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage190_stage78_structural_universe_ab_summary.json`
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage190_A_official_stage78_daily.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage190_B_stage78_structural_all_no_ai_daily.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage190_C_stage78_structural_ai_top8_daily.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage190_D_stage78_structural_simple_top8_daily.csv`
- quality：无单独 quality 文件

## 结论

- 本阶段结论：结构基础池候选未通过 A/B。不能替代第78正式品种池，也不应进入实盘影子主路径。
- 是否进入下一步：否，不继续扩大 TopN、调阈值或补丁式救结果。
- 下一步：
  - 保留结构池研究产物作为反例和后续归因材料。
  - 如继续研究，只能改为“诊断为什么新增品种破坏路径”，而不是做促晋级调参。
  - 实盘准备继续沿用官方第78与最新月度AI影子池流程。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但继续调参会变成过拟合。
- 原因：
  - 本阶段预先固定 A/B/C/D 和通过规则，未根据结果修改阈值。
  - 结果失败后立即停止，避免针对历史路径做 TopN/阈值补丁。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：作为晋级路线暂时否；作为反例归因仍有价值。
- 原因：
  - 结构池思路本身有第一性原理基础，但当前实现显著弱于官方第78。
  - 继续强行优化很可能只是把历史噪声拟合进品种池。

## 合入建议

- 是否更新本线 `LINE.md`：否，本阶段是失败候选验证，不改变正式状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 简要A/B结果；不追加 `memory.md`。
