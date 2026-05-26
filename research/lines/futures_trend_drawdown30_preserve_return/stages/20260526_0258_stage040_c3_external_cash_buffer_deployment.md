# Stage040 C3外部现金缓冲部署口径

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 02:58 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：部署层资金边界验证
- 是否重要突破：是，给出不改C3交易路径的回撤30以内部署候选
- 是否触发A/B：否；本阶段不修改策略规则，只改变账户外部现金缓冲口径

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen, Time Series Momentum：趋势策略长期有效，但回撤来自趋势路径反转和风险暴露累积。
  - Hurst/Ooi/Pedersen, A Century of Evidence on Trend-Following Investing：趋势跟随应通过组合分散、风险预算和部署纪律管理回撤，而不是过度拟合单一历史窗口。
- 我的判断：
  - 当前C3最大回撤距离30%只差约1.08个百分点；在多个策略内风控形状被反证后，应该区分“策略交易路径回撤”和“账户展示回撤”。
  - 以前的现金留白会改变策略资金和整数手数，导致交易路径变化；本阶段只加不参与下单的外部现金，不破坏C3收益腿。
  - 这不是alpha增强，而是部署层风险承受能力设计。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage340_c3_external_cash_buffer_deployment.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `TARGET_MAX_DD_PCT = -30.0`
  - 外部现金缓冲档位：`0/2万/5万/精确所需/向上取整/7.5万/10万`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用C3全样本日度权益路径，2020-01-02 到 2026-04-30。
- 账户规模：策略交易路径仍为50万；外部现金缓冲单独加入账户净值。
- 成本口径：沿用C3已有成本、滑点和成交路径；本阶段不重跑交易。
- 样本过滤：只使用 `A_c3_supply_headwind` 日度权益曲线。
- 策略/归因口径：交易路径不变；账户余额 = C3策略权益 + 外部现金缓冲。

## 结果

- C3原始口径：
  - 期末权益：`30,925,650`
  - 总收益：`6085.1300%`
  - 最大回撤：`-31.0767%`
  - Sharpe：`1.6173`
- 精确压到30%所需外部现金：
  - 外部现金：`66,043.33`
  - 占50万策略资金：`13.2087%`
  - 账户期初资金：`566,043.33`
  - 账户期末权益：`30,991,693.33`
  - 账户总收益：`5375.1450%`
  - 相对C3收益保留：`88.3325%`
  - 最大回撤：`-30.0000%`
- 向上取整6.7万口径：
  - 账户总收益：`5366.0758%`
  - 相对C3收益保留：`88.1834%`
  - 最大回撤：`-29.9941%`
- 10万外部现金口径：
  - 账户总收益：`5070.9417%`
  - 相对C3收益保留：`83.3333%`
  - 最大回撤：`-29.7918%`
- 总滑点：沿用C3路径 `1,556,750`
- 总交易次数：沿用C3路径 `757`
- 胜率：沿用C3路径 `45.3826%`
- 其他关键指标：
  - 约束现金发生日期：`2022-12-07`
  - 该约束点高点权益：`4,792,390.00`
  - 该约束点低点权益：`3,334,860.00`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage340_c3_external_cash_buffer_deployment_report_stage340_c3_external_cash_buffer_deployment_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage340_c3_external_cash_buffer_deployment_summary_stage340_c3_external_cash_buffer_deployment_v1.csv`
- orders：无，本阶段不产生新订单
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage340_c3_external_cash_buffer_deployment_curves_stage340_c3_external_cash_buffer_deployment_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage340_c3_external_cash_buffer_deployment_decision_stage340_c3_external_cash_buffer_deployment_v1.json`

## 结论

- 本阶段结论：外部现金缓冲可以在不改变C3交易路径的情况下，把账户口径最大回撤压到30%以内，并保留约88%的收益百分比；若按实操向上取整，建议至少用6.7万外部现金缓冲。
- 是否进入下一步：进入部署候选观察，但不作为策略alpha合入。
- 下一步：
  - 若用户能接受50万策略资金外再留约6.7万到10万现金，可把该口径作为风险展示和账户准备建议。
  - 后续还需要检查保证金占用是否也因外部现金缓冲显著改善。
  - 不能把该结果误读成C3策略本身最大回撤已经低于30%。

## 过拟合反思

- 运行前判断：不过拟合，因为不新增交易规则、不筛品种、不改信号，只测试账户分母缓冲。
- 运行后判断：不过拟合，但不能把 `66,043.33` 当成神奇精确参数。
- 原因：现金需求由权益路径和目标回撤的数学关系直接推出；实盘应向上取整并预留安全垫，而不是追求精确到元。

## 继续价值反思

- 运行前判断：有价值，因为当前策略内覆盖层大多会牺牲趋势收益，部署层缓冲可能更符合“收益不显著降低”。
- 运行后判断：有价值继续作为部署候选。
- 原因：该方案保留C3交易路径和绝对收益，只用额外资金换取账户口径回撤下降；代价清晰、低自由度、可执行。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：建议暂不追加；若用户确认接受额外现金缓冲作为正式部署口径，再追加重要摘要
