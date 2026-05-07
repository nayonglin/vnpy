# 第329阶段 股票震荡30万持有路径归因

- line_id：`stock_range_30w_industry_resid_core`
- 当前模式：day
- 记录时间：2026-04-29 21:33 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实成交持仓路径归因，不新增策略回测版本
- 是否重要突破：中等偏重要；明确把亏损主因定位到持有中段
- 是否触发A/B：否，纯归因，不接第78

## 外部调研与判断

- 参考资料：
  - [Short-term residual reversal](https://www.sciencedirect.com/science/article/pii/S1386418112000468)
  - [Short-term reversals, returns to liquidity provision and immediacy costs](https://www.sciencedirect.com/science/article/pii/S0378426622000309)
  - [Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit](https://arxiv.org/abs/1411.5062)
  - [Empirical investigation of state-of-the-art mean reversion strategies for equity markets](https://arxiv.org/abs/1909.04327)
  - [GitHub mean-reversion-trading topic](https://github.com/topics/mean-reversion-trading)
- 我的判断：短期反转/残差反转更像流动性冲击修复，不适合在入场前用简单“接刀子”标签硬过滤；均值回归系统真正难点经常在退出时机、持有期限和交易成本约束。本阶段应该先拆真实持仓路径，判断亏损发生在首日、持有中段还是退出前。

## 本次变更

- 新增脚本：`examples/alpha_research/analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_holding_path_attribution.py`
- 修改脚本：无策略脚本修改；仅在新增归因脚本内修复Polars同层`with_columns`引用兼容问题，并把实数结论写入报告
- 删除脚本：无
- 新增参数：无交易参数；新增归因分桶`entry_interval`、`early_hold_interval`、`middle_hold_interval`、`exit_interval`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2019-01-15 到 2026-04-27
- 账户规模：30万现金账户口径，沿用既有整手可交易回放结果
- 成本口径：沿用源回放`min_fee`与`gross`日级字段；本阶段重建持仓贡献并验证毛收益可复原
- 样本过滤：固定四个代表形状，重点观察主低回撤场景`industry_resid_core_h10_top8_gross70_ind2`
- 策略/归因口径：不重跑新策略；从源`orders/daily/target_weights`重建真实持仓日，按持有路径、最差10%策略日、episode尾部和高弹性旗标归因

## 结果

- 期末权益：不适用，本阶段不是新策略回测
- 总收益：不适用，本阶段不是新策略回测
- 最大回撤：不适用，本阶段不是新策略回测
- Sharpe：不适用，本阶段不是新策略回测
- 总滑点：沿用源回放，不新增
- 总交易次数：沿用源回放，不新增
- 胜率：不适用，本阶段按持仓日/episode归因
- 其他关键指标：
  - 质量检查：`7/7 pass`，`0 fail`，`0 warn`
  - 持仓日：`179,355`
  - episode数量：`13,225`
  - 持仓贡献复原日级毛收益最大误差：`2.78e-17`
  - 主低回撤场景全样本路径贡献：`entry +0.0344`、`early +0.0406`、`middle +0.6835`、`exit +0.1467`
  - 主低回撤场景最差10%策略日：总贡献`-3.2922`，其中`middle_hold_interval -2.7629`，占亏损绝对值约`83.92%`
  - 四个代表形状合并最差10%策略日：总贡献`-17.3011`，其中`middle_hold_interval -14.3822`，占亏损绝对值约`83.13%`
  - 主低回撤场景worst10 episode：总贡献`-1.4926`，其中中段持有`-1.3849`，占亏损绝对值约`92.78%`
  - 主低回撤场景best10 episode：总贡献`+2.0989`，其中中段持有`+1.8852`，说明中段既是收益发动机，也是亏损主通道
  - 高弹性旗标聚合：`other_knife +0.4797`、`short_crash +0.3463`、`limitdown_signal +0.0318`、`high_volume_selloff -0.0182`、`non_knife +0.0656`

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_holding_path_attribution_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_holding_path_attribution_v1_report.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_holding_path_attribution_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_holding_path_attribution_v1_path_summary.csv`
- orders：沿用源回放订单，不新增订单
- daily：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_holding_path_attribution_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_holding_path_attribution_v1_position_path_daily.csv`
- quality：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_holding_path_attribution_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_holding_path_attribution_v1_quality_checkpoints.csv`

## 结论

- 本阶段结论：亏损主因不是首日买错，也不是退出当天滑落，而是持有中段的趋势失效/反转失败。中段持有同时贡献主要收益和主要亏损，说明不能简单缩短持有期或硬止损；要研究“反转没有兑现时如何降权”，而不是一刀切砍掉中段。
- 是否进入下一步：是
- 下一步：做预注册中段路径探针，包括持有第4-7日仍未兑现反弹减仓、持有中段跌破入场后低点/行业相对残差继续恶化减仓、按episode年龄平滑衰减预算，并做滚动/OOS反证。

## 过拟合反思

- 运行前判断：否，低到中等
- 运行后判断：否，但不能直接策略化
- 原因：本阶段只做路径定位，没有选参数、没有优化收益；但下一步若根据`middle_hold_interval`设计规则，必须预注册候选并做年度/滚动反证，否则很容易变成针对亏损样本的事后裁剪。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：第328阶段已经否定了入场前统一预算化，本阶段进一步说明风险集中在持有中段；这给下一步退出/减仓设计提供了明确方向。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否，非跨线合入
- 是否追加根目录 `memory.md/back_log.md`：否，尚未形成正式候选或跨线里程碑
