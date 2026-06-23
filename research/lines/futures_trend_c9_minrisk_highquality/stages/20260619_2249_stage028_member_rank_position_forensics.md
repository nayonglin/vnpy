# Stage028 会员持仓排名结构只读法证

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-19 22:49 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：点时化会员持仓排名外生状态只读归因；不修改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - AKShare 期货数据文档，会员持仓排名：`https://akshare.akfamily.xyz/data/futures/futures.html`
  - AKShare GitHub README：`https://github.com/akfamily/akshare`
  - 上期所 Daily Ranking 页面：`https://www.shfe.com.cn/eng/reports/StatisticalData/DailyData/`
  - fushare GitHub：`https://github.com/LowinLi/fushare`
- 我的判断：
  - 会员持仓排名比 Stage027 的粗基差+仓单供需分更接近“风险由谁承接”的微观结构，方向上值得审计。
  - 但 AKShare 文档明确提示交易所排名口径不统一：大连偏品种总排名，上海/中金按合约排名后聚合，郑州较接近原始品种排名。因此它不能直接当成统一可交易阈值。
  - 本地缓存只覆盖 `2023-01-03` 至 `2026-04-17` 的 `15` 个产品，无法解释 C9 的 `2020-2022` 深回撤底座；本阶段只能做覆盖和视觉审计。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage028_member_rank_position_forensics.py`
- 修改脚本：
  - 无
- 删除脚本：
  - 无
- 新增参数：
  - `ROLLING_DAYS=120`
  - `MIN_ROLLING_DAYS=40`
  - `MAX_SIGNAL_AGE_DAYS=7`
  - 会员持仓方向分量：`0.25 * top20净持仓水平z + 0.75 * top20净多变化z`
  - 固定分桶：`score >= 0.35` 为 `member_supportive`，`score <= -0.35` 为 `member_headwind`，其余为 `member_neutral`
- 修改参数：
  - 无交易参数修改
- 删除参数：
  - 无

## 回测/归因参数

- 数据区间：
  - 官方 C9/15w closed-lot：`2018-01-15` 至 `2026-06-08`
  - 会员持仓缓存：`2023-01-03` 至 `2026-04-17`
- 账户规模：官方 C9/15w，`150,000`
- 成本口径：沿用官方 C9/15w closed-lot 与官方曲线；本阶段不新增成交和成本模拟
- 样本过滤：
  - official closed lots 全部保留，`399` 笔
  - 会员持仓缺失或滚动历史不足单独归为 `member_missing`，不删除
- 策略/归因口径：
  - 使用本地缓存 `examples/portfolio_backtesting/backtest_outputs/external_domestic_member_rank_cache/member_rank_sum_daily_20230101_20260417.csv`
  - 交易所会员排名按 `20:00` 可见处理，只允许影响下一交易日及之后
  - 每笔 official closed lot 按 `product` 和入场前 `prev_state_date` 日终向前 `merge_asof`，最大滞后 `7` 个自然日
  - 只读归因，不是真实交易引擎

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：
  - 官方交易胜率沿用 Stage011/Stage027 口径：`53.2560%`
  - 本阶段 closed-lot 胜率：`36.0902%`
- 其他关键指标：
  - 会员持仓原始缓存行数：`68,857`
  - 会员持仓特征行数：`11,753`
  - source products：`15`
  - official closed lots：`399`
  - member ready：`69`，覆盖率 `17.2932%`
  - `member_missing`：`330` 笔、`19` 产品、`9` 年，净 PnL `22,263,004.00`
  - `member_neutral`：`42` 笔、`13` 产品、`4` 年，净 PnL `21,148,733.60`
  - `member_headwind`：`14` 笔、`9` 产品、`4` 年，净 PnL `2,130,855.00`
  - `member_supportive`：`13` 笔、`9` 产品、`4` 年，净 PnL `-2,487,980.00`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage028_member_rank_position_forensics/qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_report_stage028_member_rank_position_forensics_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage028_member_rank_position_forensics/qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_decision_stage028_member_rank_position_forensics_v1.json`
- orders：无，本阶段不下单、不生成订单
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage028_member_rank_position_forensics/qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_daily_active_share_stage028_member_rank_position_forensics_v1.csv`
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage028_member_rank_position_forensics/qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_member_features_stage028_member_rank_position_forensics_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage028_member_rank_position_forensics/qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_features_stage028_member_rank_position_forensics_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage028_member_rank_position_forensics/qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_bucket_summary_stage028_member_rank_position_forensics_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage028_member_rank_position_forensics/qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_path_member_rank_state_chart_stage028_member_rank_position_forensics_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage028_member_rank_position_forensics/qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_cohort_contribution_chart_stage028_member_rank_position_forensics_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage028_member_rank_position_forensics/qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_bucket_year_heatmap_stage028_member_rank_position_forensics_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage028_member_rank_position_forensics/qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_member_score_scatter_stage028_member_rank_position_forensics_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage028_member_rank_position_forensics/qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_product_member_rank_heatmap_stage028_member_rank_position_forensics_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage028_member_rank_position_forensics/qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_source_coverage_chart_stage028_member_rank_position_forensics_v1.png`

## 视觉结论

- path chart：会员持仓 ready share 直到 `2023` 后才零散出现，`2020-2022` 主回撤底座几乎全是 `member_missing`，不能解释全周期最大回撤。
- contribution chart：`member_headwind` 橙线最终净正 `+213万`，不是坏信号集合；`member_neutral` 承担主要右尾，`member_supportive` 反而净亏。
- bucket-year heatmap：`member_supportive` 在 `2023/2024/2025/2026` 都为负，但总样本只有 `13` 笔，不能从小样本近端窗口反推普世规则。
- scatter：会员净多流量和净持仓水平空间里盈亏点混杂，未形成稳定可分边界。
- product heatmap：DCE/GFEX 主右尾产品如 `jm.DCE/lh.DCE/si.GFEX/lc.GFEX` 大量落在 missing，说明当前缓存不是 C9 全产品会员持仓视图。

## 结论

- 本阶段结论：`stage028_member_rank_no_candidate_coverage_too_low_for_c9`
- 是否进入下一步：不进入交易候选，不触发 A/B，不写 true engine。
- 下一步：
  - 停止用当前 2023-2026/15品种会员持仓缓存做阈值分支；不扫 TopN、rolling window、level/flow 权重、`0.35` 阈值、产品、方向、年份或交易所。
  - 若继续会员持仓路线，只允许先做数据工程型覆盖审计：补 `2020-2022` 与 DCE/GFEX/CZCE/SHFE 口径一致性，再重新只读绑定；补齐前只保留为 forward watch/风险解释标签。
  - 若不补数据，下一条研究应换到新的外生源或暂停历史 closed-lot 内反推，避免把近端 69 笔切成规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否；但继续围绕 69 笔 ready 样本扫参数会变成过拟合。
- 原因：
  - 本阶段使用公开交易所会员持仓排名和本地缓存，公式和阈值在运行前固定，未按亏损年份、产品、方向或具体交易调参。
  - 运行后已经明确覆盖不足且 bucket 关系不具备普世性；若继续改变 TopN、zscore 窗口、权重或阈值以救结果，就会把近端小样本噪声包装成规则。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：当前缓存没有交易化价值；会员持仓路线只有在补齐历史和产品覆盖后才有继续价值。
- 原因：
  - 有价值部分在于验证了本地确有会员持仓缓存和点时化绑定路径，可以作为未来 forward watch 的数据骨架。
  - 没有交易化价值部分在于全样本 ready 只有 `17.2932%`，无法解释 `2020-2022` 回撤，且 headwind 净正、supportive 净负，视觉和指标都不支持直接削仓。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage028 覆盖不足和停止边界。
- 是否更新 `research/registry.md`：否，非重要突破、非路线废弃、非正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要合入摘要。
