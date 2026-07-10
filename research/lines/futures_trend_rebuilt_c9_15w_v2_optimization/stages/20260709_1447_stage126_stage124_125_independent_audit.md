# Stage126 Stage124/125 全品种统计独立审计

## 基本信息

- 时间：2026-07-09 14:47 CST
- 研究线：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 类型：只读审计，不是新策略版本，不是新回测
- 审计对象：
  - Stage124 全品种单品种 C9/15w replay
  - Stage125 2022 亏损窗口盈利前十品种资金曲线
- 独立 agent：`Volta`
- 实盘入口改动：无
- CTP 连接：无
- 订单 API 调用：`0`

## 审计结论

结论：`有保留可接受`。

Stage124/125 的收益计算链路自洽，没有发现收益表之间的复算错误；但数据完整性不是全满，尤其分钟数据缺口较重。因此它适合作为“全品种单品种 C9 盈利能力库存”，不适合作为“可直接扩池上线”的充分证据。

## 实际统计的品种

来源：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv` 中 `eligible=1` 的 full-market 产品。

Stage124 `summary/status/daily_by_product` 均为 `57/57`，与 eligible 集合完全一致，无缺失、无多算。

- CFFEX：`IH.CFFEX`
- CZCE：`AP.CZCE`、`CF.CZCE`、`CY.CZCE`、`FG.CZCE`、`MA.CZCE`、`OI.CZCE`、`PF.CZCE`、`PK.CZCE`、`PR.CZCE`、`PX.CZCE`、`SA.CZCE`、`SF.CZCE`、`SH.CZCE`、`SM.CZCE`、`SR.CZCE`、`TA.CZCE`、`UR.CZCE`
- DCE：`a.DCE`、`c.DCE`、`cs.DCE`、`eb.DCE`、`fb.DCE`、`i.DCE`、`j.DCE`、`jd.DCE`、`jm.DCE`、`lh.DCE`、`m.DCE`、`p.DCE`、`pg.DCE`、`rr.DCE`、`v.DCE`、`y.DCE`
- GFEX：`lc.GFEX`、`si.GFEX`
- INE：`bc.INE`、`lu.INE`、`nr.INE`、`sc.INE`
- SHFE：`ag.SHFE`、`al.SHFE`、`ao.SHFE`、`au.SHFE`、`br.SHFE`、`bu.SHFE`、`cu.SHFE`、`fu.SHFE`、`hc.SHFE`、`ni.SHFE`、`pb.SHFE`、`rb.SHFE`、`ru.SHFE`、`sn.SHFE`、`sp.SHFE`、`ss.SHFE`、`zn.SHFE`

## 计算误差检查

本地复算：

- `product_summary.total_net_pnl` vs `daily_by_product.net_pnl` 汇总：误差 `0`
- `product_period_summary.daily_net_pnl` vs `daily_by_product` 对应窗口汇总：误差 `0`
- `end_equity - 150,000` vs `total_net_pnl`：误差 `0`
- 日期重复/乱序：未发现
- Stage125 的 `m/ni/CY/eb/y/zn/ag/v/PK/rr` 收益、交易数、期末重置权益：可从 Stage124 日级文件复算一致

独立 agent 复核：

- `product_summary.total_net_pnl` vs daily sum：最大误差约 `1.45e-11`
- `product_period_summary.daily_net_pnl` vs daily window sum：最大误差约 `1.45e-11`
- `closed_lot_realized_pnl` vs closed lots exit_date 聚合：最大误差约 `1.45e-11`
- Stage125 收益、交易数、active days、期末重置权益：全部可复算一致

判断：不存在实质计算误差；`1e-11` 级别是浮点误差。

## 数据完整性风险

不能说这些品种的数据都是全的。

- 产品数：`57`
- `ok` 状态：`57`
- 日级文件：`57`
- status 文件：`57`
- 实际结束日为 `2026-06-30`：`22`
- 实际结束日早于 `2026-06-30`：`35`
- 0 交易产品：`3`，即 `IH.CFFEX`、`bc.INE`、`sc.INE`
- `recent_bar_coverage_ratio < 0.8`：`7`，即 `c.DCE`、`CY.CZCE`、`PK.CZCE`、`PR.CZCE`、`jd.DCE`、`PX.CZCE`、`SF.CZCE`
- `trading_days < 1200`：`11`
- 分钟合约存在缺口：`54/57`
- 分钟请求合约全部加载：`3/57`，即 `lc.GFEX`、`si.GFEX`、`SA.CZCE`
- 分钟加载为 `0`：`38/57`

最重要的风险是分钟数据。Stage847 的开仓日 0.5R stop/retry 逻辑在找不到入场合约分钟线时会直接跳过该事件，因此分钟缺口会影响“开仓日实时止损/重试”的 1:1 精确性。

## Stage125 前十品种的数据完整性

Stage125 这 10 个品种在 `2022-03-09 -> 2022-06-29` 都有完整日级窗口行，每个产品窗口行数均为 `75`。但这 10 个品种的分钟加载数均为 `0`，所以它们的窗口资金曲线可以作为日级 C9 单品种账本，但不能声称已经包含完整分钟级开仓日 stop/retry。

| 品种 | 日级窗口行 | loss_window_daily_net_pnl | recent_bar_coverage_ratio | 缺分钟合约数 |
| --- | ---: | ---: | ---: | ---: |
| `m.DCE` | 75 | 23,990.0 | 1.0000 | 49 |
| `ni.SHFE` | 75 | 17,860.0 | 0.8125 | 89 |
| `CY.CZCE` | 75 | 14,100.0 | 0.7708 | 28 |
| `eb.DCE` | 75 | 10,800.0 | 0.8083 | 67 |
| `y.DCE` | 75 | 5,840.0 | 1.0000 | 49 |
| `zn.SHFE` | 75 | 5,200.0 | 0.9708 | 195 |
| `ag.SHFE` | 75 | 5,130.0 | 0.8417 | 44 |
| `v.DCE` | 75 | 4,760.0 | 1.0000 | 51 |
| `PK.CZCE` | 75 | 3,870.0 | 0.7875 | 22 |
| `rr.DCE` | 75 | 60.0 | 0.8542 | 67 |

## Stage125 口径说明

Stage125 图表为了让曲线统一从 `150,000` 起算，额外放入了 `2022-03-08` 作为基准点；收益仍只统计 `2022-03-09 -> 2022-06-29`。这不是收益计算错误，但最大回撤口径必须写清楚：它是“窗口开盘前资金 150,000 到窗口结束”的重置资金曲线回撤，不是“从第一条窗口收盘权益开始”的回撤。

## 输出

- 数据审计 CSV：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage126_stage124_125_audit/stage126_stage124_product_data_audit.csv`
- Stage124 复算问题 CSV：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage126_stage124_125_audit/stage126_recalc_issues.csv`
- Stage125 复算问题 CSV：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage126_stage124_125_audit/stage126_stage125_issues.csv`

## 后续建议

1. Stage124/125 可以继续作为候选池库存使用。
2. 下一步必须先给每个品种打标签：`full_sample_coverage`、`loss_window_coverage`、`zero_trade`、`minute_missing`、`minute_loaded`。
3. 如果要研究扩池，只能先选预声明候选池，再做组合级 true-engine A/B、流动性、保证金和分钟缺口审计。
4. 不能直接按单品种历史 PnL 排名扩池，更不能声称这些结果已经是全品种分钟级 1:1 精确版本。

## 外部调研判断

参考 `pysystemtrade` 的单规则/单品种回测框架和系统化交易回测原则，逐品种 replay 是合理的第一步；但真实晋级仍需要组合级仿真、成本、流动性和数据完整性硬闸门。结论：Stage124/125 的方向合理，但证据层级只能是候选库存，不是上线依据。

## 反过拟合与继续价值

- 反过拟合判断：本次是只读复算和独立审计，没有新增规则或调参，不构成过拟合。
- 继续价值判断：有价值，但只能沿着“数据质量过滤后的候选池研究”继续；如果直接围绕这 10 个品种扫权重、月份或窗口，就是过拟合。
