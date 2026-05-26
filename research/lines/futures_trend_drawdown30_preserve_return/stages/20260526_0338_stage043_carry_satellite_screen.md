# Stage043 期限结构Carry低相关卫星净值层筛查

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-26 03:38 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：低相关新收益源的最小可行筛查；不修改78-1/C3正式信号。
- 是否重要突破：否，反证当前 Carry/期限结构卫星形状。
- 是否触发A/B：是，属于可能组合接入的候选卫星，但本轮仅做净值层筛查，不进入真实引擎。

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen 的 Time Series Momentum 研究显示，趋势动量可在商品、股指、利率、外汇等期货资产上形成跨市场收益源。
  - Hilary Till 的 commodity futures term structure 研究，以及 momentum + term structure 组合文献，都支持“期限结构/Carry 可以是商品期货趋势之外的独立收益源”这个假设。
- 我的判断：
  - 期限结构/Carry 方向有第一性原理：反映库存、便利收益、融资和供需压力，不是单纯趋势信号的重复。
  - 但第78-1目标不是找一个“理论上有意义”的因子，而是找到能在 C3 弱窗口里提供足够收益、同时不牺牲复利的低相关腿。因此必须先做最小净值层筛查，失败就不继续调 top/bottom 数量或月份。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage343_carry_satellite_screen.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `TOP_N=3`
  - `BOTTOM_N=3`
  - `MIN_VALID_PRODUCTS=8`
  - `MIN_DAYS_TO_EXPIRY=15`
  - `MAX_LIQUID_CONTRACTS=4`
  - `COST_BPS_LIST=(0,5,10,20)`
  - `SATELLITE_WEIGHTS=(10%,20%,30%)`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：净值层组合按 `500,000` 初始资金重算。
- 成本口径：Carry 卫星按调仓换手扣 `0/5/10/20bp`，C3沿用既有日收益路径。
- 样本过滤：
  - 仅使用第78-1商品池。
  - 使用逐合约日线构造期限结构，合约到期月距离信号日少于15天的合约剔除。
  - 每个品种每天取流动性最高的4个合约，再用最近与最远合约计算期限结构斜率。
- 策略/归因口径：
  - 每月第一个交易日，用上一交易日 Carry 截面排序。
  - 做多近强远弱的前3个品种，做空近弱远强的后3个品种。
  - 与 C3 做净值层 `90/10`、`80/20`、`70/30` 组合。
  - 本阶段不做真实手数、保证金、换月成交和逐笔滑点，只有净值层通过后才进入真实引擎。

## 结果

- C3基准：
  - 期末权益：`30,925,650`
  - 总收益：`6085.1300%`
  - 最大回撤：`-31.0767%`
  - Sharpe：`1.6173`（日收益层）
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 胜率：`45.3826%`
- Carry卫星独立：
  - `0bp` 成本：总收益 `-24.3753%`，最大回撤 `-38.2565%`，Sharpe `-0.3555`
  - `10bp` 成本：总收益 `-28.2570%`，最大回撤 `-40.5789%`，Sharpe `-0.4330`
- 最接近保收益的组合：
  - `c3_90_carry_10_cost0bps`
  - 总收益：`4168.1379%`
  - 相对C3收益保留：`68.4971%`
  - 最大回撤：`-28.4718%`
  - Sharpe：`1.6106`
- 最接近低回撤的组合：
  - `c3_70_carry_30_cost0bps`
  - 总收益：`1841.7598%`
  - 相对C3收益保留：`30.2666%`
  - 最大回撤：`-23.0823%`
  - Sharpe：`1.5855`
- 多周期：
  - 没有任何组合通过“最大回撤30以内 + 收益保留80%”的多周期严格闸门。
  - `c3_90_carry_10_cost0bps` 在 `since_2024`、`phase_2024_2025`、`ytd_2026` 可通过，但在全样本、`since_2021`、`since_2022`、`since_2023` 收益保留不足。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage343_carry_satellite_screen_report_stage343_carry_satellite_screen_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage343_carry_satellite_screen_summary_stage343_carry_satellite_screen_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage343_carry_satellite_screen_combo_daily_stage343_carry_satellite_screen_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage343_carry_satellite_screen_window_summary_stage343_carry_satellite_screen_v1.csv`
- features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage343_carry_satellite_screen_term_structure_features_stage343_carry_satellite_screen_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage343_carry_satellite_screen_decision_stage343_carry_satellite_screen_v1.json`

## 结论

- 本阶段结论：`carry_satellite_screen_fail`
- 是否进入下一步：不进入真实引擎，不继续调当前 Carry 卫星形状。
- 下一步：
  - 不继续微调 `top/bottom` 数量、调仓月份、流动性合约数或成本小数。
  - 若继续低相关路线，需要寻找收益本身为正、弱窗口能互补的新独立收益源。
  - 另一条实际路线是验证实盘执行是否能稳定低于当前压力滑点；如果能，Stage041 的正常成本部署候选仍有现实价值。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本轮筛查不是过拟合，但继续救该 Carry 形状会过拟合。
- 原因：
  - 本轮使用经济含义清晰的期限结构因子、月度低换手、固定 top/bottom 档位和预声明成本档位。
  - 结果显示问题不是成本小数，而是 Carry 卫星自身收益为负、组合降回撤主要靠稀释 C3 暴露。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：当前 Carry 卫星形状继续价值低；总研究线仍有价值。
- 原因：
  - 它证伪了一个理论上合理、但当前实现不能保收益的低相关来源。
  - 剩余可继续方向应更偏“收益本身足够强的独立策略”或“真实执行成本验证”，而不是弱收益卫星稀释主策略。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Carry 卫星失败，避免重复微调。
- 是否更新 `research/registry.md`：是，最新阶段更新为 Stage043。
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段属于路线反证，应进入总账。
