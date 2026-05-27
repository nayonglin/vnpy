# Stage064 商品季节性卫星净值层筛查

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-26 20:30 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：低相关收益源净值层筛查；路线反证
- 是否重要突破：否
- 是否触发A/B：是。季节性卫星若有效可能与 C3/78-1 组合，因此按 A/B/C 隔离记录；本阶段不修改正式策略。

## 外部调研与判断

- 参考资料：
  - NBER `The Tactical and Strategic Value of Commodity Futures`：商品期货长期多头并不稳定，主动战术配置、动量和期限结构比单纯长期配置更有意义。https://www.nber.org/papers/w11222
  - ScienceDirect `Momentum strategies in commodity futures markets`：商品横截面动量有历史收益和低相关属性，但需要考虑保证金、换月和执行成本。https://www.sciencedirect.com/science/article/abs/pii/S037842660700026X
  - ScienceDirect `Return seasonality in commodity futures`：商品期货存在季节性效应，但近年效应有减弱迹象。https://www.sciencedirect.com/science/article/pii/S1059056024002934
- 我的判断：
  - Carry 与横截面动量在本线已被反证或承载失败；季节性仍是低相关收益源中可试的下一类。
  - 但季节性必须用点时化历史同月信息，不能事后挑月份、品种或行业。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage364_seasonality_satellite_screen.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 历史起点：`2015-01-01`
  - 同月历史回看：`5` 年
  - 单品种最少历史年份：`3`
  - 多空数量：做多前 `3`、做空后 `3`
  - 成本：`20bp * 换手`
  - C 组合粗权重：季节性卫星 `10%/20%/30%`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：特征历史 `2015-01-01` 至 `2026-04-30`；组合评估 `2020-01-01` 至 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：季节性卫星每月调仓，按换手扣 `20bp`
- 样本过滤：固定当前 `VT_SYMBOLS`，不做品种黑名单，不按结果筛月份
- 策略/归因口径：
  - A：`C3_supply_headwind`
  - B：季节性卫星独立净值
  - C：`C3 + 季节性卫星`

## 结果

- C3基准：
  - 期末权益：`30,925,650`
  - 总收益：`6085.1300%`
  - 最大回撤：`-31.0767%`
  - Sharpe：`1.3663`
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 胜率：`45.3826%`
- B：季节性卫星独立结果：
  - 总收益：`-50.5532%`
  - 最大回撤：`-51.2495%`
  - Sharpe：`-1.1398`
- C：组合全样本：
  - `90% C3 + 10% 季节性`：总收益 `3978.3366%`，收益保留 `65.3780%`，最大回撤 `-29.0333%`，Sharpe `1.5915`
  - `80% C3 + 20% 季节性`：总收益 `2550.3651%`，收益保留 `41.9114%`，最大回撤 `-26.9557%`，Sharpe `1.5583`
  - `70% C3 + 30% 季节性`：总收益 `1597.4155%`，收益保留 `26.2511%`，最大回撤 `-24.8439%`，Sharpe `1.5140`
- 多周期：
  - `90% C3 + 10% 季节性` 仅 `since_2024`、`phase_2024_2025`、`ytd_2026` 通过；全样本收益保留不达标。
  - `20%/30%` 卫星权重回撤更低，但收益保留显著不足。
- 其他关键指标：
  - 季节性特征数：`1029`
  - 卫星活跃天数：`1532`
  - 调仓次数：`76`
  - 平均日换手：`0.0587`
- 决策：`seasonality_satellite_screen_fail`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage364_seasonality_satellite_screen_report_stage364_seasonality_satellite_screen_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage364_seasonality_satellite_screen_summary_stage364_seasonality_satellite_screen_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage364_seasonality_satellite_screen_combo_daily_stage364_seasonality_satellite_screen_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage364_seasonality_satellite_screen_features_stage364_seasonality_satellite_screen_v1.csv`

## 结论

- 本阶段结论：季节性卫星能通过稀释 C3 把回撤压入 30% 内，但自身收益源为负，组合收益保留远低于 `80%`。这不是满足目标的低相关收益源。
- 是否进入下一步：不进入真实资金/保证金/整数手数验证。
- 下一步：停止当前月度季节性 top/bottom 形状；不要挑月份、挑品种或调 `10%` 附近权重小数。继续目标只能换更强的独立收益源或回到 Stage055 正常成本部署边界。

## 过拟合反思

- 运行前判断：不是过拟合。规则预先固定，只用历史同月信息，月初第一天不吃新信号收益。
- 运行后判断：不是过拟合；负结论应接受。
- 原因：没有用结果反向选择月份、品种或阈值。若继续救季节性参数，就是过拟合。

## 继续价值反思

- 运行前判断：有价值。Carry/xsmom 已被反证后，季节性是外部文献支持且与趋势不同源的低相关方向。
- 运行后判断：当前形状继续价值低，总研究线仍有价值。
- 原因：分散作用存在，但收益源质量不足。继续本形状只能靠稀释降回撤，不能满足“收益不显著降低”。

## 合入建议

- 是否更新本线 `LINE.md`：是，加入季节性卫星反证和禁止继续扫月历参数。
- 是否更新 `research/registry.md`：是，最新阶段改为 Stage064。
- 是否追加根目录 `memory.md/back_log.md`：是，作为低相关收益源路线反证与后续禁区。
