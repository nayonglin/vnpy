# 第337阶段：简单超跌母本早期反转兑现/失败归因

## 时间

- 运行时间：2026-04-29 22:52 CST
- 当前模式：day

## 本阶段性质

- 本阶段是信号层归因，不是策略回测。
- 不新增交易规则，不修改交易参数，不修改第78，不修改`stock_range_paper_v1`。
- 不触发A/B实验。

## 外部调研与判断

- 均值回归公开资料普遍强调：失败常来自入场过早、极端状态延续、缺少确认、止损/退出机制粗糙。
- 残差短反文献说明：剔除市场/因子后的短期反转有研究基础，但交易实现必须处理交易成本和状态暴露。
- GitHub公开均值回归项目多集中在RSI/Bollinger/pairs trading，能提供工程参考，但不能直接复制为A股30万整手策略。
- 本阶段判断：先验证“入场后1-3日的反转是否真实兑现、是否还能预测第4-10日剩余收益”，比继续扫组合预算更接近问题本质。

参考资料：

- https://setupalpha.com/blogs/articles/mean-reversion-strategy-failures-complete-fix-guide
- https://backtestme.com/guides/mean-reversion-strategies
- https://www.tradebeacon.io/blog/mean-reversion-trading-strategy-guide-rsi-bollinger-bands
- https://arxiv.org/abs/1411.5062
- https://www.efmaefm.org/0EFMSYMPOSIUM/2012/papers/017_update.pdf
- https://github.com/topics/mean-reversion-trading

## 新增脚本

- `examples/alpha_research/analyze_stock_range_reversion_liquid_q3_30w_simple_mother_early_confirmation_attribution.py`

## 输入与样本

- 输入目录：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_high_return_shape_grid_2018_2026`
- 输入文件：`stock_range_reversion_liquid_q3_30w_high_return_shape_grid_v1_selected.csv`
- 样本场景：
  - `top8_gross50_ind2`
  - `top5_gross50_ind2`
  - `top8_gross70_ind2`
  - `top5_gross70_ind2`
- 输入选中样本：`43,206`
- 账户规模：`300,000 CNY`

## 新增归因标签

- `entry_reversal_day`：入场当天收阳且`entry_ibs >= 0.60`。
- `entry_weak_close`：入场当天收阴且`entry_ibs <= 0.30`。
- `early_repair_1d`：入场后第1日收盘收益为正。
- `early_repair_3d`：入场后第3日累计收益为正。
- `fast_rebound_3d`：入场后3日内最大收盘反弹`>= 3%`。
- `no_bounce_3d`：入场后3日内最大收盘反弹`< 1%`。
- `early_breakdown_3d`：入场后3日内最大收盘跌幅`<= -5%`。
- `volume_repair_3d`：入场后3日内出现单日涨幅`>= 2%`且20日量比`>= 1.30`。
- `volume_failure_3d`：入场后3日内出现单日跌幅`<= -2%`且20日量比`>= 1.30`。
- `industry_repair_3d`：同日同行业选中篮子3日平均路径为正。
- `industry_failure_3d`：同日同行业选中篮子3日平均路径为负。
- `stock_leads_industry_3d`：个股3日路径领先同行业选中篮子超过`2pp`。
- `stock_lags_industry_3d`：个股3日路径落后同行业选中篮子超过`2pp`。

## 关键修正

- 最初只看`fwd_excess_ret_10`会把前3日已经发生的收益也算进去，容易把“已经反弹”误读为“后面还能反弹”。
- 本阶段最终候选额外要求`late_ret_4_10`仍有正向边际，并检查该边际的年度广度。
- 因此输出拆成两类：
  - `candidate_for_rule_probe`：整段10日解释力、坏尾部解释力、第4-10日剩余边际都通过。
  - `path_explanation_only`：能解释整段路径，但第4-10日剩余边际不足，暂不能写成交易规则。

## 质量检查

- `focus_scenario_count`：pass，固定4个简单母本形状。
- `flag_count`：pass，预注册13个旗标。
- `selected_rows`：pass，样本`43,206`。
- `primary_rule_probe_candidates`：pass，主母本出现`2`个可进入规则探针的旗标。
- `guard_rule_probe_candidates`：pass，top5护栏出现`2`个同步旗标。
- `broad_candidate_count`：pass，跨场景候选旗标`8`个。
- `no_trade_rule_change`：pass，本阶段只做归因。

## 核心结果

### 主母本：`top8_gross50_ind2`

- `fast_rebound_3d`
  - 覆盖率：`33.15%`
  - 10日超额边际：`+5.81pp`
  - 第4-10日剩余边际：`+0.22pp`
  - 坏尾部改善边际：`+16.66pp`
  - 剩余边际年度正向比例：`77.78%`
- `volume_repair_3d`
  - 覆盖率：`24.12%`
  - 10日超额边际：`+5.70pp`
  - 第4-10日剩余边际：`+0.77pp`
  - 坏尾部改善边际：`+13.74pp`
  - 剩余边际年度正向比例：`77.78%`

### 护栏母本：`top5_gross50_ind2`

- `volume_repair_3d`
  - 覆盖率：`23.34%`
  - 10日超额边际：`+5.69pp`
  - 第4-10日剩余边际：`+0.69pp`
  - 坏尾部改善边际：`+13.22pp`
  - 剩余边际年度正向比例：`66.67%`
- `fast_rebound_3d`
  - 覆盖率：`33.12%`
  - 10日超额边际：`+5.66pp`
  - 第4-10日剩余边际：`+0.06pp`
  - 坏尾部改善边际：`+16.71pp`
  - 剩余边际年度正向比例：`55.56%`

## 重要反证

- `early_repair_3d`、`industry_repair_3d`、`no_bounce_3d`、`early_breakdown_3d`都能解释10日结果，但第4-10日剩余边际不足或为负。
- 这说明多数“早期好/坏路径”只是已经发生的盈亏，不是后续可交易预测。
- `early_breakdown_3d`尤其不能简单写成硬止损：它的10日全段很差，但第4-10日反而常有修复，硬退出可能再次砍掉反弹alpha。
- 入场当天形态`entry_reversal_day`和`entry_weak_close`均被否决，不能作为入场确认。

## 产出文件

- `examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_early_confirmation_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_early_confirmation_v1_report.md`
- `examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_early_confirmation_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_early_confirmation_v1_flag_candidates.csv`
- `examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_early_confirmation_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_early_confirmation_v1_daily_bucket_summary.csv`

## 过拟合判断

- 当前阶段过拟合判断：否。
- 理由：本阶段没有用结果改交易规则，只做预注册旗标归因；并且主动加入`late_ret_4_10`检查，避免把前3日已实现收益当作未来预测。
- 风险：`fast_rebound_3d`和`volume_repair_3d`阈值仍来自同一数据上的归因，下一步如果做规则，必须预注册并做年度/滚动/邻域反证。

## 继续价值判断

- 继续价值判断：是。
- 理由：组合层预算已经多次证明不是主引擎；本阶段找到两个跨top8/top5同步、且第4-10日仍有剩余边际的早期确认线索。
- 但这不是正式候选，只能进入下一阶段规则探针或延长持有归因。

## 下一步

- 优先做第338阶段：`fast_rebound_3d`/`volume_repair_3d`确认后的续航归因。
- 先检查确认样本在第11-15日、第11-20日是否仍有延续边际，再决定是否做“确认后延长持有/预算倾斜”真实30万整手回放。
- 暂不做早期破位硬止损，因为第337阶段反证显示破位后的第4-10日常有修复，硬止损大概率误伤alpha。
