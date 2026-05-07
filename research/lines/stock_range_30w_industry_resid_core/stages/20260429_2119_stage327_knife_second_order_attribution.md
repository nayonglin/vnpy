# 第327阶段：接刀子二阶归因

- 记录时间：2026-04-29 21:19 CST
- 当前模式：day
- 当前研究线：`stock_range_30w_industry_resid_core`
- 本阶段性质：同一高波动/接刀子样本内部的好反弹与坏延续归因。
- 是否重要突破版本：否，不升级候选；但属于重要方向性发现。
- 账户规模：`300,000`元口径。
- 交易约束：本阶段不新增交易回放，不改参数，不改第78，不改paper线。
- 特征时间对齐：个股旗标和指数状态均使用上一交易日已知信息映射到下一交易日开盘目标。
- A/B判断：归因阶段，不触发正式A/B。

## 外部调研和判断

- 短期反转文献支持从普通价格反转转向残差/相对反转，避免把系统性趋势风险当作可套利回归。
- 流动性供给型反转和噪声交易通常伴随高波动；所以第326阶段看到接刀子旗标同时出现在好样本和坏样本里，并不矛盾。
- GitHub/博客示例适合作为流程参考，但不能替代A股整手、涨跌停、交易成本和本地股票池约束。

参考资料：

- [Short-term residual reversal](https://www.sciencedirect.com/science/article/pii/S1386418112000468)
- [Short-term reversals, returns to liquidity provision and immediacy costs](https://www.sciencedirect.com/science/article/pii/S0378426622000309)
- [Short-Term Reversals and Longer-Term Momentum around the World](https://academic.oup.com/rfs/article/38/12/3673/8240327)
- [Teddy Koker cross-sectional mean reversion backtest](https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/)
- [GitHub mean-reversion-trading topic](https://github.com/topics/mean-reversion-trading)

## 新增脚本

- `examples/alpha_research/analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution.py`

## 质量检查

- fail：`0`
- warn：`1`
- 接刀子样本：`66,976`行。
- 跨四场景稳定好桶候选：`39`个。
- 主场景`rule_context_good_gate`为正：pass，次开盘平均收益`0.2189%`。
- 主场景`rule_context_bad_gate`没有弱于好门：warn，坏门`0.3174%`，好门`0.2189%`。
- 结论：粗粒度“安全上下文门”被反证，不能策略化。

## 关键发现

- `knife_any`不是坏样本：
  - 全部目标样本次开盘平均收益`0.083%`。
  - `knife_any`次开盘平均收益`0.277%`，5日开盘平均收益`0.818%`。
  - `knife_2plus`次开盘平均收益`0.378%`，5日开盘平均收益`1.307%`。
- 越极端越有收益弹性，但尾部也更厚：
  - `limit_down_signal`次开盘平均收益`0.537%`，5日开盘平均收益`4.270%`。
  - 同时坏尾部占比`22.71%`，好尾部占比`25.00%`，说明这是高方差弹性来源，不是低风险过滤对象。
- 直觉型安全门被反证：
  - `rule_context_good_gate=True`次开盘`0.204%`。
  - `rule_context_bad_gate=True`反而为`0.314%`。
- 市场压力不是坏事：
  - `rule_market_not_stressed=False`次开盘`0.427%`。
  - `rule_market_not_stressed=True`只有`0.175%`。
- 技术结构破坏和模型损伤惩罚也不应简单剔除：
  - `rule_structure_not_broken=False` 5日`1.334%`，`True`为`0.598%`。
  - `rule_model_damage_low=False` 5日`3.329%`，`True`为`0.670%`。

## 解释

- 当前行业残差震荡线的收益更像“流动性冲击后的弹性补偿”，不是买温和回调。
- 常识里的“结构完整、市场不差、损伤低”在这批目标里不一定更赚钱；相反，压力更大的样本承担更厚尾部，但也提供更大的反弹弹性。
- 因此下一步不能做“安全门过滤”，而应该研究“高弹性样本的尾部控制”：保留弹性，但限制单日/单行业/单状态的损失贡献。

## 本阶段未做

- 没有新增策略回测。
- 没有修改仓位参数。
- 没有接入paper线。
- 没有接入第78。
- 没有把任何二阶规则升级为正式过滤器。

## 过拟合反思

- 运行前判断：中等。
- 原因：二阶规则来自第326失败后的机制假设和外部调研，不是按收益阈值细调；但仍是同一历史样本归因。
- 运行后判断：不升级候选，过拟合风险可控。
- 原因：本阶段主动记录反证结果，没有按最优桶继续调参；任何策略化都必须下一阶段预注册并做滚动/OOS。

## 继续价值反思

- 运行前判断：有价值。
- 原因：第326证明简单旗标误杀收益来源，二阶归因是更接近本质的一步。
- 运行后判断：有价值，但方向要调整。
- 原因：方向不是“过滤接刀子”，而是“保留高弹性冲击样本，同时控制厚尾损失”。

## 决策

- 不接入第78。
- 不升级正式股票候选。
- 不把`rule_context_good_gate`或`rule_context_bad_gate`策略化。
- 下一阶段转向高弹性样本的尾部控制探针，例如单行业/跌停/市场压力日的平滑权重或损失上限，而不是硬过滤。

## 输出文件

- 报告：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_v1_report.md`
- 样本明细：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_v1_enriched_targets.csv`
- 高波动总体画像：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_v1_cohort_summary.csv`
- 二阶规则画像：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_v1_rule_summary.csv`
- 二阶特征桶对比：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_v1_feature_contrast.csv`
- 质量检查：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_second_order_attribution_v1_quality_checkpoints.csv`
