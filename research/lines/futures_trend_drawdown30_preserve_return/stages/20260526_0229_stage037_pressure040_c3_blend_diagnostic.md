# Stage037 C_pressure040 与 C3 组合口径诊断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 02:29 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：口径纠错 / 同源组合诊断
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Moskowitz, Ooi, Pedersen, *Time Series Momentum*：趋势跟随收益跨资产存在，但风险控制不能只依赖同源信号的小权重切换。
  - Hurst, Ooi, Pedersen, *A Century of Evidence on Trend-Following Investing*：CTA 组合稳定性来自跨市场和低相关风险来源，而不是同一趋势规则的近邻版本重复叠加。
- 我的判断：
  - `C_pressure040` 和 `C3` 都来自第78-1趋势底座；C3 只是叠加供需强逆风过滤。若两者最大回撤路径重合，组合不会真正分散尾部风险。
  - 本阶段重点不是找更高收益，而是修正“`C_pressure040+C3`”与“`C3+低相关卫星`”的口径混淆。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage337_pressure040_c3_blend_diagnostic.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无；仅固定读取 Stage319 的 `C_pressure040` 与 `C3_supply_headwind` 权益曲线。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30，读取 Stage319 已生成曲线。
- 账户规模：50万口径。
- 成本口径：沿用 Stage319 真实引擎成本与滑点统计。
- 样本过滤：仅 `full_2020_2026`。
- 策略/归因口径：
  - 单版本：`C_pressure040`、`C3_supply_headwind`。
  - 组合：净值层权重前沿 `C_pressure040` 权重 `0/25/50/75/100%`，`C3` 权重互补。

## 结果

- `C_pressure040`
  - 期末权益：`25,429,055`
  - 总收益：`4985.8110%`
  - 最大回撤：`-31.0767%`
  - Sharpe：`1.2650`
  - 总滑点：`2,047,490`
  - 总交易次数：`862`
  - 胜率：`45.0346%`
- `C3_supply_headwind`
  - 期末权益：`30,925,650`
  - 总收益：`6085.1300%`
  - 最大回撤：`-31.0767%`
  - Sharpe：`1.3663`
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 胜率：`45.3826%`
- `50% C_pressure040 + 50% C3`
  - 期末权益：`28,177,352.50`
  - 总收益：`5535.4705%`
  - 最大回撤：`-31.0767%`
  - Sharpe：`1.5856`
  - 总滑点：净值组合未单独重算滑点；单腿滑点沿用 Stage319。
  - 总交易次数：净值组合未单独重算订单；单腿订单沿用 Stage319。
  - 胜率：净值组合不定义交易胜率。
  - 其他关键指标：两条日收益相关性 `0.9492`；最大回撤窗口均为 `2021-05-12` 至 `2021-07-02`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage337_pressure040_c3_blend_diagnostic_report_stage337_pressure040_c3_blend_diagnostic_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage337_pressure040_c3_blend_diagnostic_summary_stage337_pressure040_c3_blend_diagnostic_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage337_pressure040_c3_blend_diagnostic_daily_stage337_pressure040_c3_blend_diagnostic_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage337_pressure040_c3_blend_diagnostic_source_variants_stage337_pressure040_c3_blend_diagnostic_v1.csv`

## 结论

- 本阶段结论：`C_pressure040` 与 `C3` 是同源趋势版本，等权组合收益位于两者之间，但最大回撤没有任何改善，不能作为回撤30以内方案。
- 是否进入下一步：不沿该组合权重方向继续。
- 下一步：继续寻找真正低相关、真实资金下可交易的卫星腿，或转向账户部署层结构；不要再把 Stage323 的低相关卫星组合误记成 `C_pressure040+C3`。

## 过拟合反思

- 运行前判断：过拟合风险低。
- 运行后判断：否。
- 原因：本阶段没有新增可交易参数，只读取既有权益曲线做口径审计；没有根据结果调权重。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但该同源组合路线停止。
- 原因：排除了一个容易混淆且直觉上看似可行的组合方向，避免后续研究建立在错误口径上。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage037 结论。
- 是否更新 `research/registry.md`：是，更新最新关键阶段和下一步。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；这是口径纠错，不是正式候选或重要突破。
