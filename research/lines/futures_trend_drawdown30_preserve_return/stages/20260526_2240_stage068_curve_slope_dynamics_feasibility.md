# Stage068 期限结构斜率变化卫星探针

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 22:40 CST
- 工作区/分支：当前工作区
- 阶段性质：低自由度独立收益源可行性探针；不修改第78-1或C3正式策略逻辑
- 是否重要突破：否，是路线反证
- 是否触发A/B：是，作为潜在 C3 组合卫星的 A/B/C 前置筛查

## 外部调研与判断

- 参考资料：
  - `A new strategy using term-structure dynamics of commodity futures`：商品期货期限结构动态斜率可能包含不同于静态 carry 和日度动量的独立信息。
  - `Exploiting the dynamics of commodity futures curves`：用期限结构曲线斜率变化预测商品期货收益存在研究依据。
- 我的判断：
  - 期限结构动态斜率有第一性原理价值，因为它来自同一品种不同到期合约的相对价格变化，不是单一主力趋势价格本身。
  - 但本阶段必须和同权重现金稀释对照；如果组合改善只来自降低 C3 暴露，而不是卫星腿自身正贡献，则不能晋级。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage368_curve_slope_dynamics_feasibility.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `SLOPE_CHANGE_DAYS=20`
  - `LIQUID_TOP_N=4`
  - `MAX_MONTHS_TO_MATURITY=24`
  - `MAX_NEAR_FAR_GAP_MONTHS=18`
  - `COST_BPS=2.0`
  - `SATELLITE_WEIGHTS=(0.10, 0.20)`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：卫星腿净值层固定 `2bps` 换手成本；C3成本沿用既有回测输出
- 样本过滤：
  - 使用官方78-1静态池加 `fu` 候选，共 `19` 个品种。
  - 每个交易日、每个品种取持仓量前 `4` 个合约，选择最近液态合约和下一远月合约。
- 策略/归因口径：
  - `C3_current_100`
  - `C3_cash_90_10`
  - `C3_slope_90_10`
  - `C3_cash_80_20`
  - `C3_slope_80_20`
  - `slope_dynamic_standalone`

## 结果

- 期末权益：
  - `C3_current_100`：`30,925,650.00`
  - `C3_slope_90_10`：`21,282,623.92`
  - `C3_slope_80_20`：`14,435,265.07`
  - `slope_dynamic_standalone`：`379,907.40`
- 总收益：
  - `C3_current_100`：`6085.1300%`
  - `C3_slope_90_10`：`4156.5248%`
  - `C3_slope_80_20`：`2787.0530%`
  - `slope_dynamic_standalone`：`-24.0185%`
- 最大回撤：
  - `C3_current_100`：`-31.0767%`
  - `C3_slope_90_10`：`-28.6985%`
  - `C3_slope_80_20`：`-26.2706%`
  - `slope_dynamic_standalone`：`-34.0797%`
- Sharpe：
  - `C3_current_100`：`1.6169`
  - `C3_slope_90_10`：`1.6080`
  - `C3_slope_80_20`：`1.5962`
  - `slope_dynamic_standalone`：`-0.6033`
- 总滑点：净值层无真实引擎滑点；C3沿用既有 `1,556,750`
- 总交易次数：净值层无真实引擎交易次数；C3沿用既有 `757`
- 胜率：净值层无真实引擎胜率；C3沿用既有 `45.3826%`
- 其他关键指标：
  - `C3_slope_90_10` 收益保留 `68.3063%`，低于 `80%` 闸门，且低于同权重现金稀释 `C3_cash_90_10` 的 `4266.2488%`。
  - `C3_slope_80_20` 收益保留 `45.8010%`，低于 `80%` 闸门，且低于同权重现金稀释 `C3_cash_80_20` 的 `2939.1430%`。
  - 决策：`fail_curve_slope_dynamic_satellite_not_promoted`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage368_curve_slope_dynamics_feasibility_report_stage368_curve_slope_dynamics_feasibility_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage368_curve_slope_dynamics_feasibility_summary_stage368_curve_slope_dynamics_feasibility_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage368_curve_slope_dynamics_feasibility_combo_daily_stage368_curve_slope_dynamics_feasibility_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage368_curve_slope_dynamics_feasibility_coverage_stage368_curve_slope_dynamics_feasibility_v1.csv`

## 结论

- 本阶段结论：期限结构斜率变化方向有经济含义，但当前净值层卫星腿自身为负收益，组合回撤改善主要来自降低 C3 暴露，且没有打败同权重现金稀释。
- 是否进入下一步：否。
- 下一步：不继续围绕 `20日`、持仓量前 `4`、近远月 gap、`10%/20%` 权重或成本小数救援；若继续期限结构方向，只能换成更结构化的曲线风险溢价/跨品种分组验证，并先要求独立腿为正收益。

## 过拟合反思

- 运行前判断：不是过拟合。规则来自外部期限结构动态研究和第一性原理，且预先固定窗口、权重和成本。
- 运行后判断：不是过拟合，但失败后继续调阈值、合约选择、品种或权重会变成过拟合。
- 原因：本阶段没有按结果搜索参数；失败依据是卫星腿自身负收益且不如现金稀释。

## 继续价值反思

- 运行前判断：有价值。原因是本线需要寻找真正独立收益源，而不是继续修补同源趋势。
- 运行后判断：当前形状继续价值低；总研究线仍有价值。
- 原因：该形状不能证明独立收益源贡献。下一步更应优先寻找可承载、正收益、低相关的独立腿，或接受 Stage055/067 的正常成本部署边界。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录为期限结构动态斜率路线反证。
- 是否更新 `research/registry.md`：是，最新阶段更新到 Stage068。
- 是否追加根目录 `memory.md/back_log.md`：是，作为 A/B 净值层回测与路线停止摘要。
