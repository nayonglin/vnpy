# Stage016 交叉稳定性只读审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 20:19 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因 / Stage015 入场结构交集稳定性 / 资金曲线视觉分析
- 是否重要突破：否。主交集稳定但样本小，且不能转化为普世最小风险规则。
- 是否触发A/B：否。没有新候选接入正式版本，不修改正式配置。

## 外部调研与判断

- 参考资料：
  - `Trend Following Strategies: A Practical Guide`：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5140633
  - `A Guide to Trend Following Strategies`：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4438260
  - `pysystemtrade` backtesting 文档：https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
  - `PyTrendFollow`：https://github.com/chrism2671/PyTrendFollow
- 我的判断：
  - 外部趋势跟随资料强调时间尺度、分散化、杠杆敏感和稳健风控；开源系统也强调配置隔离、账户曲线和完整回测路径。
  - 没有资料支持把少数历史入场交集直接转成实盘仓位规则。
  - 所以本阶段只做 `ai_rank_4_6` 与 `entry_open_aligned/first_bar_aligned` 的交叉稳定性审计，不写交易规则、不触发 A/B。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage016_intersection_stability_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增只读交集标签。
- 修改参数：无
- 删除参数：无
- 正式配置/执行链路/CTP：无修改、未连接、未调用下单。

## 回测/归因参数

- 数据区间：沿用 Stage015/Stage010 官方 C9/15w closed lots 与官方资金曲线。
- 账户规模：`150000`
- 基准：当前官方正式 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 样本：官方 closed lots `399` 笔。
- 交集标签：
  - `ai_rank_4_6`
  - `entry_open_aligned`
  - `first_bar_aligned`
  - `entry_or_first_aligned`
  - `ai4_6_entry_or_first_aligned`
  - 以及补集/对照标签。
- 评估口径：事件数、产品数、年份数、正负收益覆盖、年度 PnL、Stage014 漏右尾 delta overlap、closed-lot 贡献曲线、年度热图、分钟 K atlas。

## 结果

- 官方期末权益：沿用 Stage010/Stage013 官方 C9/15w，`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`
- 官方 Sharpe：`1.6331`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- 官方胜率：`53.2560%`
- Stage016 closed-lot realized PnL 合计：`43,054,612.60`
- 正收益合计：`67,549,795.00`
- 负收益合计：`-24,495,182.40`

### 主交集

- `ai4_6_entry_or_first_aligned`
  - 笔数：`24`
  - 产品：`10`
  - 年份：`7`
  - 官方 PnL：`10,677,322.50`
  - 净 PnL 占比：`24.7995%`
  - 正收益覆盖：`17.7929%`
  - 负收益覆盖：`5.4776%`
  - 正负覆盖差：`+12.3153pp`
  - 胜率：`62.5000%`
  - 年度表现：`7/7` 年正收益，最小年 PnL `59,070.00`
  - Stage014 delta overlap：`-6,625,869.00`，占 Stage014 分摊 delta `27.0408%`
  - 决策：只读稳定性标签，不进入交易规则。

### 补集

- `not_ai4_6_or_not_aligned`
  - 笔数：`375`
  - 产品：`35`
  - 年份：`9`
  - 官方 PnL：`32,377,290.10`
  - 净 PnL 占比：`75.2005%`
  - 正收益覆盖：`82.2071%`
  - 负收益覆盖：`94.5224%`
  - 年度表现：`8` 年正收益、`1` 年负收益
  - 大赢家：`22` 笔，大赢家 PnL `27,213,520.00`
  - 决策：不能把补集默认最小风险。补集仍承载大部分右尾收益。

### 其他关键点

- `entry_open_aligned` 与 `entry_and_first_aligned` 均为 `127` 笔，说明当前 Stage861 第一根分钟K里 entry open 与 first bar close 标签高度重叠，不能把它们当两个独立证据。
- `ai_rank_4_6` 单桶 `53` 笔、`16` 产品、`7` 年，官方 PnL `19,563,063.00`，但仍捕获 `13.2899%` 负收益。
- `entry_open_aligned/first_bar_aligned` 单桶 `127-130` 笔，9 年全正，但负收益捕获仍约 `29.4%-31.5%`，不是低风险充分条件。

## 视觉分析

- `intersection_path_chart`：
  - 官方资金曲线的大台阶主要仍来自 Stage013 missed-right-tail 标记附近。
  - 主交集绿色贡献线较干净，但规模小；红色补集仍贡献官方大部分收益台阶。
  - 视觉结论：主交集可作为“不要延迟/不要减仓”的保护标签，但不能支持“其他交易默认最小风险”。
- `intersection_stability_scatter`：
  - `ai4_6_*aligned` 位于左下方，损失捕获少，但正收益覆盖也少。
  - 补集位于右上方，正负收益都捕获最多；这不是可以交易化切分的好/坏信号边界。
- `intersection_year_heatmap`：
  - 主交集 `7/7` 年为正，但 `2020/2021` 贡献很薄。
  - `aligned_not_ai4_6` 在 `2026` 已转负，补集 `2026` 也明显为负，说明不能声明该结构已穿越周期。
- 分钟 atlas：
  - page001：主交集赢家通常开仓瞬间已经顺势，说明延迟恢复风险会错过右尾。
  - page004：`OI309`、`jm2509`、`OI305`、`ru2501` 等主交集之外赢家仍贡献巨大，其中有 first-bar adverse 和非 `ai_rank_4_6`，直接反证只保留主交集的规则。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage016_intersection_stability_audit/qmt_roll_stage016_c9_minrisk_intersection_stability_audit_report_stage016_intersection_stability_audit_v1.md`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage016_intersection_stability_audit/qmt_roll_stage016_c9_minrisk_intersection_stability_audit_features_stage016_intersection_stability_audit_v1.csv`
- intersection_stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage016_intersection_stability_audit/qmt_roll_stage016_c9_minrisk_intersection_stability_audit_intersection_stats_stage016_intersection_stability_audit_v1.csv`
- intersection_year_stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage016_intersection_stability_audit/qmt_roll_stage016_c9_minrisk_intersection_stability_audit_intersection_year_stats_stage016_intersection_stability_audit_v1.csv`
- pair_matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage016_intersection_stability_audit/qmt_roll_stage016_c9_minrisk_intersection_stability_audit_pair_matrix_stage016_intersection_stability_audit_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage016_intersection_stability_audit/qmt_roll_stage016_c9_minrisk_intersection_stability_audit_intersection_path_chart_stage016_intersection_stability_audit_v1.png`
- stability scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage016_intersection_stability_audit/qmt_roll_stage016_c9_minrisk_intersection_stability_audit_intersection_stability_scatter_stage016_intersection_stability_audit_v1.png`
- year heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage016_intersection_stability_audit/qmt_roll_stage016_c9_minrisk_intersection_stability_audit_intersection_year_heatmap_stage016_intersection_stability_audit_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage016_intersection_stability_audit/qmt_roll_stage016_c9_minrisk_intersection_stability_audit_atlas_page001_stage016_intersection_stability_audit_v1.png` 至 `page005`

## 结论

- 本阶段结论：`stage016_intersection_stability_readonly_no_trade_rule`
- 是否进入下一步：入场结构路线只保留 forward-watch 价值，不进入真实引擎。
- 下一步：
  - 不把 `ai_rank_4_6 ∩ aligned` 写成交易规则。
  - 不做 `rank_1_3/4_6/7_9`、entry/first-bar、窗口、品种、方向、年份等交集救参。
  - 如果继续本目标，应优先转向不改变官方单笔路径的账户层外部资金分层、出金锁盈、独立 sleeve，或者仅对主交集做 forward watch 积累 OOS。

## 过拟合反思

- 运行前判断：否。本阶段只审计 Stage015 预声明交集，不生成新交易分支。
- 运行后判断：否。没有把主交集推广成规则；若现在推广，就是过拟合。
- 原因：主交集只有 `24` 笔，虽然跨 `7` 年和 `10` 产品，但历史右尾保护标签不能直接证明未来可交易；补集仍有大部分右尾。

## 继续价值反思

- 运行前判断：有价值。Stage015 的最佳只读线索需要验证是否跨年、跨品种稳定。
- 运行后判断：目标整体仍有价值，但入场结构路线继续价值有限。
- 原因：主交集适合做观察标签，不适合做最小风险规则；继续沿交集细分会快速进入过拟合。下一步应该换到账户层风险体验改善，且不破坏官方右尾。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage016 结论和后续边界。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、重要突破、路线废弃、跨线合并或记录体系迁移。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选或重大合入摘要。
