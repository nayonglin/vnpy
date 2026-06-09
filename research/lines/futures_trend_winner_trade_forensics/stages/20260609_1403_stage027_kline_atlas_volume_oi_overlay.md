# Stage027 K线图册增加成交量与持仓量

- 时间：2026-06-09 14:03 CST
- line_id：`futures_trend_winner_trade_forensics`
- 工作模式：`day`
- 脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage752_theoretical_winner_kline_atlas.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage753_theoretical_loser_kline_atlas.py`
- 决策：`readonly_visual_overlay_no_strategy_change`

## 外部/GitHub调研结论

- `mplfinance` / `mplchart` 等开源项目普遍采用价格K线主图 + 成交量副图的方式，期货场景还常配合持仓量观察。
- 本地未新增依赖，继续使用 matplotlib 自绘；这样不会影响当前环境，也不会引入图表库版本变动。
- 调研判断：成交量和持仓量适合辅助人工识别“趋势扩张是否有资金参与”，但不能直接作为交易化规则。

## 本次变更

- 新增副图：每个交易面板拆为上方价格K线、下方成交量/持仓量。
- 成交量：使用本地日线CSV字段 `volume`，灰色柱状图。
- 持仓量：使用本地日线CSV字段 `close_oi`，青色曲线。
- 保留原标注：
  - 蓝线/蓝三角：开仓
  - 紫线/紫三角：平仓
  - 赢家浅黄持仓区
  - 失败浅红持仓区
- 不修改正式策略、不连接 CTP、不调用下单、不新增或修改任何策略参数。

## 重生成结果

- 赢家图册 Stage752：
  - 交易数：`29`
  - 页数：`8`
  - missing bars：`6`
  - 文件：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage752_theoretical_winner_kline_atlas_page01_stage752_theoretical_winner_kline_atlas_v1.png` 至 `page08`
- 失败图册 Stage753：
  - 交易数：`175`
  - 页数：`44`
  - missing bars：`26`
  - 文件：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage753_theoretical_loser_kline_atlas_page01_stage753_theoretical_loser_kline_atlas_v1.png` 至 `page44`

## 过拟合与继续价值反思

- 本次是否过拟合：否。只是增强图表信息密度，没有筛选规则、参数调优或策略改动。
- 是否有价值继续：有。成交量/持仓量能辅助区分趋势扩张、缩量反抽、持仓衰退后的失败，但后续若交易化，必须先做跨年份/跨品种只读统计。
