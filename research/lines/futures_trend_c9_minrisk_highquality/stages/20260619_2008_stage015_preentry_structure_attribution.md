# Stage015 入场前/入场刻结构只读归因

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 20:08 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因 / 入场前与入场刻结构审计 / 视觉分析
- 是否重要突破：否。发现若干保护性线索，但未形成可交易规则。
- 是否触发A/B：否。没有候选接入正式版本，不修改正式配置。

## 外部调研与判断

- 参考资料：
  - `Intraday Momentum: The First Half-Hour Return Predicts the Last Half-Hour Return`：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2552752
  - `Trend Following Strategies: A Practical Guide`：https://papers.ssrn.com/sol3/Delivery.cfm/5140633.pdf?abstractid=5140633&mirid=1
  - `A Guide to Trend Following Strategies`：https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID4438260_code412374.pdf?abstractid=4438260&mirid=1
  - `pysystemtrade` backtesting 文档：https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
  - `PyTrendFollow`：https://github.com/chrism2671/PyTrendFollow
- 我的判断：
  - 外部资料支持日内路径有信息量，也支持趋势跟随收益来自右尾和仓位路径。
  - Stage014 已经证明“入场后 30m 默认最小风险观察”会切断右尾，所以 Stage015 只审计开仓前/开仓瞬间可见字段。
  - 当前发现的 `ai_rank_4_6`、`entry_open_aligned`、`first_bar_aligned` 更像“不要减仓的保护条件”，不是“可以默认减仓的坏信号过滤器”。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage015_preentry_structure_attribution.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增只读 broad bucket 审计口径。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `2026-06-15`
- 账户规模：`150000`
- 成本口径：沿用官方 C9/15w Stage010 closed lots；本阶段不重跑交易引擎。
- 样本过滤：Stage010 官方 closed lots `399` 笔；Stage861 entry-instant minute 可用 `333` 笔。
- 策略/归因口径：
  - 只读字段：`entry_context/signal/direction/risk_multiplier/loss_streak/active_positions/ai_rank/rsi/stop_distance/recovery/breakout/portfolio_drawdown/same_direction_active`
  - 入场刻字段：`entry_open_relation/first_bar_relation/first_bar_body/first_bar_adverse_wick`
  - broad bucket：事件数 `>=10`、年份 `>=4`、产品 `>=5`，且不是全样本常量 bucket。
  - Stage014 delta overlap：按事件匹配 lot 分摊，避免一笔 Stage014 事件多 lot 时重复计算。

## 结果

- 官方期末权益：沿用 Stage010/Stage013 官方 C9/15w，`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`
- 官方 Sharpe：`1.6331`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- 官方胜率：`53.2560%`
- Stage015 closed-lot realized PnL 合计：`43,054,612.60`
- 正收益合计：`67,549,795.00`
- 负收益合计：`-24,495,182.40`
- broad bucket：`60`
- informative broad bucket：`58`
- 关键只读线索：
  - `ai_rank_bucket=rank_4_6`：`53` 笔、`16` 产品、`7` 年，官方 PnL `19,563,063.00`，`7/7` 年正收益，正收益覆盖 `33.7802%`，负收益覆盖 `13.2899%`，正负覆盖差 `+20.4903pp`，Stage014 分摊 delta `-6,084,227.60`。
  - `entry_open_relation_bucket=entry_open_aligned`：`127` 笔、`13` 产品、`9` 年，官方 PnL `26,028,878.20`，`9/9` 年正收益，正收益覆盖 `49.2020%`，负收益覆盖 `29.4221%`，正负覆盖差 `+19.7799pp`，Stage014 分摊 delta `-17,888,722.10`。
  - `first_bar_relation_bucket=first_bar_aligned`：`130` 笔、`14` 产品、`9` 年，官方 PnL `25,526,918.70`，`9/9` 年正收益，正收益覆盖 `49.2045%`，负收益覆盖 `31.4782%`，正负覆盖差 `+17.7263pp`，Stage014 分摊 delta `-17,540,200.50`。
  - `breakout_bucket=no_breakout`：`281` 笔、`35` 产品、`9` 年，官方 PnL `36,429,653.80`，但覆盖样本 `70.4261%` 且仍捕获 `57.2283%` 负收益，不适合作为硬过滤。
  - `risk_multiplier_bucket=risk_normal`、`portfolio_dd_0_5`、`flat_entry` 等高净值 bucket 本质上接近官方主样本，不能解读为独立规则。

## 视觉分析

- `path_bucket_chart`：
  - 官方权益台阶仍集中在 `2023` 后，Stage013 missed-right-tail marker 叠在这些台阶前后。
  - bucket 贡献曲线中，`entry_open_aligned` 与 `first_bar_aligned` 都是明显正贡献，但曲线的台阶仍依赖少数右尾，不能直接视为低风险过滤。
  - `ai_rank_4_6` 曲线更集中、更干净，但样本只有 `53` 笔、`7` 年，尚不足以直接生成规则。
- `bucket_scatter_chart`：
  - 好 bucket 大多位于正收益覆盖大于负收益覆盖的位置，但高收益 bucket 同时也捕获不少负收益。
  - 这说明单桶过滤无法天然解决“低风险保留 80% 收益”的目标，需要真引擎 A/C 才能判断资金路径。
- 分钟 atlas：
  - `OI309` 是第一根 adverse 但后续超大右尾，反证“第一根 adverse 就最小风险/不恢复”。
  - `jm2509/jm2401/OI305` 是较典型右尾，部分 first-bar aligned，但其价值在于开仓即保持官方仓位，而不是 30m 后恢复。
  - `SH405/au2412/ru2501` 显示 no-clean 或 first-bar adverse 仍可成为大赢家，继续说明不能把入场后短窗做硬过滤。
  - `SH607/lc2401/AP210/cu2307` 等亏损样本也有 flat_entry/risk_normal/高 RSI，说明开仓前字段单独不能区分坏信号。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage015_preentry_structure_attribution/qmt_roll_stage015_c9_minrisk_preentry_structure_attribution_report_stage015_preentry_structure_attribution_v1.md`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage015_preentry_structure_attribution/qmt_roll_stage015_c9_minrisk_preentry_structure_attribution_features_stage015_preentry_structure_attribution_v1.csv`
- bucket_stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage015_preentry_structure_attribution/qmt_roll_stage015_c9_minrisk_preentry_structure_attribution_bucket_stats_stage015_preentry_structure_attribution_v1.csv`
- bucket_year_stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage015_preentry_structure_attribution/qmt_roll_stage015_c9_minrisk_preentry_structure_attribution_bucket_year_stats_stage015_preentry_structure_attribution_v1.csv`
- selected_buckets：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage015_preentry_structure_attribution/qmt_roll_stage015_c9_minrisk_preentry_structure_attribution_selected_buckets_stage015_preentry_structure_attribution_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage015_preentry_structure_attribution/qmt_roll_stage015_c9_minrisk_preentry_structure_attribution_path_bucket_chart_stage015_preentry_structure_attribution_v1.png`
- scatter chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage015_preentry_structure_attribution/qmt_roll_stage015_c9_minrisk_preentry_structure_attribution_bucket_scatter_chart_stage015_preentry_structure_attribution_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage015_preentry_structure_attribution/qmt_roll_stage015_c9_minrisk_preentry_structure_attribution_atlas_page001_stage015_preentry_structure_attribution_v1.png` 至 `page004`

## 结论

- 本阶段结论：`stage015_preentry_structure_readonly_no_trade_rule`
- 是否进入下一步：是，但不进入交易规则。
- 下一步：
  - 不用 `first_bar_aligned/entry_open_aligned` 直接做满仓或最小风险规则；它们是保护右尾的观察标签。
  - 下一阶段可做只读组合交叉归因：`ai_rank_4_6` 与 `entry_open_aligned/first_bar_aligned` 的交集是否仍跨年、跨品种稳定，同时是否显著降低负收益捕获。
  - 若交集样本太小或集中在少数年份/品种，停止入场结构方向，转账户层外部资金分层/出金锁盈/独立 sleeve。

## 过拟合反思

- 运行前判断：否。本阶段预先限定为只读 broad bucket，不生成交易规则。
- 运行后判断：否。本阶段没有把最佳 bucket 合成为规则；但若现在把 `ai_rank_4_6 + entry_open_aligned` 直接接成策略，就是过拟合。
- 原因：当前线索来自历史 closed lots 归因，尚未经过冻结真实引擎、成本压力、多起点和视觉复验。

## 继续价值反思

- 运行前判断：有价值。Stage014 要求我们避开入场后最小风险闸门，改看入场前/入场刻可见信息。
- 运行后判断：有条件继续。线索有结构价值，但必须先做交叉只读稳定性；不能直接写真引擎。
- 原因：`ai_rank_4_6`、`entry_open_aligned`、`first_bar_aligned` 都有正偏和跨年表现，但也覆盖 Stage013 漏掉的右尾，说明它们更像右尾保护标签，不是风险过滤标签。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage015 只读结论和下一步边界。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、重要突破、路线废弃、跨线合并或记录体系迁移。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选或重大合入摘要。
