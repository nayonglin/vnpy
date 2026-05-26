# Stage042 C3外部现金缓冲滑点压力验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 03:21 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：部署候选成本压力反证
- 是否重要突破：是，Stage041候选被修正为“正常成本可行，高滑点压力不通过”
- 是否触发A/B：否；不修改交易规则，只做成本压力审计

## 外部调研与判断

- 参考资料：
  - Futures Market Liquidity and the Trading Cost of Trend Following Strategies：趋势跟随的真实交易成本需要独立估计，实盘成本会影响回测到实盘的落地。
  - Trend-following trading strategies in commodity futures: A re-examination：商品期货趋势策略评估需要扣除合理交易成本。
  - Slippage in futures markets / Slippage Costs in Order Execution for a Public Futures Fund：滑点是期货交易的隐性执行成本，与市场流动性和下单方式相关。
- 我的判断：
  - Stage041 的 `11.5万`外部现金只证明了正常滑点口径下可行，不能直接推到实盘压力。
  - 若 2x/3x 滑点需要的外部现金超过收益保留80%允许上限，则该部署候选不能作为“稳健完成目标”的最终版本。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage342_c3_external_cash_slippage_stress.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 滑点倍数：`1x / 2x / 3x / 5x`
  - 外部现金档位：`0 / 11.5万 / 12.5万 / 20万 / 35万 / 60万`
  - 收益保留80%允许的最大外部现金：`125,000`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage336 多周期 C3 日度权益路径。
- 账户规模：策略交易路径仍为50万；外部现金单独加入账户权益。
- 成本口径：在已有1x滑点基础上，按每日滑点成本累计增加额外滑点，得到2x/3x/5x压力权益路径。
- 样本过滤：
  - `start_2020/start_2021/start_2022/start_2023/start_2024/start_2025/ytd_2026`
  - `weak_2021_full`
  - `phase_2024_2025`
- 策略/归因口径：不改信号、不改仓位、不改交易路径，只做成本压力后的账户权益审计。

## 结果

- 正常1x滑点：
  - 最大所需外部现金：`112,433.33`
  - `11.5万`通过多周期：`9/9`
  - `12.5万`通过多周期：`9/9`
- 2x滑点：
  - 最大所需外部现金：`318,850.00`
  - 所需现金对应收益保留：`61.0612%`
  - `11.5万`通过多周期：`4/9`
  - `12.5万`通过多周期：`4/9`
  - `11.5万`最大保证金/权益：`105.9772%`
  - `12.5万`最大保证金/权益：`105.5766%`
- 3x滑点：
  - 最大所需外部现金：`595,231.67`
  - 所需现金对应收益保留：`45.6524%`
  - `11.5万`通过多周期：`2/9`
  - `12.5万`通过多周期：`2/9`
- 5x滑点：
  - 最大所需外部现金：`3,340,748.33`
  - 所需现金对应收益保留：`13.0183%`
- 80%收益保留允许的最大外部现金：`125,000`
- 总滑点：
  - 1x：沿用C3原始滑点
  - 2x/3x/5x：按日额外滑点累计压力估算
- 总交易次数：沿用C3路径
- 胜率：沿用C3路径，本阶段不重算逐笔成交胜率

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage342_c3_external_cash_slippage_stress_report_stage342_c3_external_cash_slippage_stress_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage342_c3_external_cash_slippage_stress_window_summary_stage342_c3_external_cash_slippage_stress_v1.csv`
- orders：无
- daily：无新增逐日曲线文件，本阶段输出窗口汇总与现金需求
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage342_c3_external_cash_slippage_stress_decision_stage342_c3_external_cash_slippage_stress_v1.json`

## 结论

- 本阶段结论：`11.5万`外部现金候选只在正常滑点下成立；2x滑点压力下不满足“最大回撤30以内且收益保留80%”。
- 是否进入下一步：不能作为最终稳健版本；只能作为正常成本部署候选。
- 下一步：
  - 若目标包含 2x/3x 滑点压力，则单靠外部现金缓冲不可行，因为所需现金会显著压低收益保留。
  - 后续应回到真正低相关收益源，或研究执行层降低滑点，而不是继续加现金。

## 过拟合反思

- 运行前判断：不过拟合。
- 运行后判断：不过拟合。
- 原因：本阶段使用固定滑点倍数和固定现金档位，不根据单一窗口调整信号；结果是对候选进行反证，而不是救结果。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但外部现金路线价值下降。
- 原因：它明确了部署候选的适用边界：正常成本可行，高成本压力不满足目标。继续本线应优先找低相关收益源或降低真实执行成本。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为Stage041部署候选的压力反证摘要
