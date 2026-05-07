# 第324阶段：亏损来源/信号层过滤探针

- 记录时间：2026-04-29 18:00 CST
- 当前模式：day
- 当前研究线：`stock_range_30w_industry_resid_core`
- 本阶段性质：拆前10%亏损日来源，并测试少数减亏型行业/分数过滤探针。
- 账户规模：`300,000`元
- 回测区间：`2019-01-15` 到 `2026-04-27`
- 交易约束：100股整手，最小佣金5元压力，过滤释放现金不重分配。
- A/B判断：独立股票震荡研究线归因/探针，不接入第78，不触发正式A/B。

## 外部调研和判断

- 短期反转研究强调残差反转、行业内结构和行业/动态因子暴露，不能只看普通价格反转。
- 业界均值回归系统的核心风险不是少赚，而是买到继续下跌的尾部样本；因此在Stage323否定粗粒度risk-on之后，优先拆亏损来源，比继续找“好环境加仓”更接近本质。
- 本阶段不发明新alpha，只验证Stage323暴露出来的弱贡献行业和分数桶是否有减亏价值。

参考资料：

- [Short-term residual reversal](https://www.sciencedirect.com/science/article/pii/S1386418112000468)
- [Short-Term Return Reversal decomposition](https://therobusttrader.com/short-term-reversal-effect-in-stocks/)
- [Backtesting a Cross-Sectional Mean Reversion Strategy in Python](https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/)
- [Mean Reversion Trading risk management](https://www.tradewink.com/learn/mean-reversion-trading-strategy)
- [GitHub mean-reversion-trading topic](https://github.com/topics/mean-reversion-trading)

## 新增脚本

- `examples/alpha_research/analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe.py`

## 探针设计

- 基准形状固定4个：`top5_gross100_ind1`、`top5_gross70_ind1`、`top8_gross100_ind2`、`top8_gross70_ind2`。
- 过滤探针固定4个：
  - `half_stage323_weak_industries`：`软件服务/建筑工程`目标权重减半。
  - `drop_stage323_weak_industries`：剔除`软件服务/建筑工程`。
  - `drop_selected_score_top20`：剔除当日选中股票内部模型分数最高20%桶。
  - `drop_score_top20_and_weak_industries`：同时剔除高分20%桶和弱行业。
- 所有过滤释放的现金都不重分配，避免把过滤伪装成加仓。

## 质量检查

- fail：`0`
- warn：`2`
- 同时改善收益和回撤：`8/16`
- 改善回撤：`11/16`
- 30万高收益且回撤20%以内候选：`0/4`
- 主要warn：
  - `candidate_high_return_and_within_20pct`：仍未达到30万高收益/20%内回撤目标。
  - `exploratory_same_sample_filter`：弱行业来自同样本归因，必须滚动/OOS反证。

## 关键结果

- 收益最高过滤探针：
  - `industry_resid_core_h10_top8_gross100_ind2_drop_stage323_weak_industries`
  - 期末权益：`1.8299`
  - 总收益：`82.99%`
  - 最大回撤：`-30.26%`
  - Sharpe：`0.486`
- 回撤最浅过滤探针：
  - `industry_resid_core_h10_top5_gross70_ind1_drop_score_top20_and_weak_industries`
  - 期末权益：`1.2192`
  - 总收益：`21.92%`
  - 最大回撤：`-19.18%`
  - Sharpe：`0.291`
- 更有价值的低回撤形状：
  - `industry_resid_core_h10_top8_gross70_ind2_drop_stage323_weak_industries`
  - 期末权益：`1.5371`
  - 总收益：`53.71%`
  - 最大回撤：`-19.95%`
  - Sharpe：`0.486`
  - 相比基准收益提升约`16.67pp`，最大回撤改善约`6.44pp`。
- 第320候选形状`top5_gross70_ind1`：
  - 基准：总收益`34.60%`，最大回撤`-26.88%`，Sharpe `0.323`。
  - 剔除弱行业：总收益`50.27%`，最大回撤`-20.42%`，Sharpe `0.438`。
  - 弱行业减半：总收益`44.78%`，最大回撤`-22.76%`，Sharpe `0.395`。
  - 剔除高分20%和弱行业：总收益`21.92%`，最大回撤`-19.18%`，Sharpe `0.291`。

## 亏损来源观察

- 第320候选形状前10%亏损日的主要行业来源包括：`元器件`、`软件服务`、`通信设备`、`电气设备`、`半导体`、`汽车配件`、`专用机械`、`小金属`、`化学制药`、`化工原料`、`互联网`、`建筑工程`等。
- `软件服务/建筑工程`不是全部亏损来源，但它们在Stage323全样本贡献弱、在亏损尾部也有存在感；剔除它们能在多个形状里同时改善收益和回撤。
- 剔除选中分数最高20%桶整体不理想，说明当前模型分数不是一个可以直接单调加仓/减仓的权重函数。高分桶可能带尾部风险，但简单删除会误伤收益。
- 前10%亏损日的平均开盘到次开盘收益约`-3.4%`，前10%赚钱日约`+3.3%`；亏损日并没有被现有`damage_penalty`明显捕获，说明尾部更像“继续下跌/接刀子”，不是当前损伤惩罚能解释。

## 结论

- 这是一个重要的信号层线索，但不是正式候选。
- `软件服务/建筑工程`弱行业暴露过滤，比Stage323的粗粒度risk-on更有价值。
- 当前最值得保留的方向是“行业特异性反证/弱行业排除”，不是继续扩大好环境仓位。
- `drop_stage323_weak_industries`在收益和回撤上有较稳定的同向改善，但因为弱行业来自同样本归因，下一步必须做滚动/OOS反证。

## 过拟合反思

- 运行前判断：中等偏高。
- 原因：弱行业和分数桶来自同样本收益来源归因，任何过滤都有数据挖掘风险。
- 运行后判断：仍然不能升级候选。
- 原因：虽然`8/16`同向改善、`11/16`改善回撤，但同样本行业剔除必须经过滚动时期验证；否则容易把2019-2026某些行业阶段性弱势写成规则。

## 继续价值反思

- 判断：有价值继续。
- 原因：相比状态加仓，信号层过滤直接作用于亏损来源，而且多个基准形状同向改善。
- 下一步：做`软件服务/建筑工程`弱行业排除的滚动/OOS反证，并拆它们失败的原因是行业结构、流动性、模型分数错配，还是继续下跌特征没有捕获。

## 输出文件

- 报告：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe_v1_report.md`
- 汇总：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe_v1_summary.csv`
- 质量检查：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe_v1_quality_checkpoints.csv`
