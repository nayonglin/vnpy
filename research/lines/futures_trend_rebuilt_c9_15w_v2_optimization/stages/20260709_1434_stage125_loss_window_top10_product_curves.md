# Stage125 2022 亏损窗口盈利品种资金曲线

## 基本信息

- 时间：2026-07-09 14:34 CST
- 研究线：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 类型：Stage124 派生统计和绘图，不是新策略版本，不是新回测
- 输入：Stage124 全品种单品种 C9/15w replay 的 `daily_by_product` 与 period summary
- 窗口：`2022-03-09 -> 2022-06-29`
- 初始资金：`150,000`
- 口径：每日盯市 `net_pnl` 为收益主口径；`closed_lot_realized_pnl` 仅作为对照

## 本次没有策略改动

- 新增参数：无
- 修改参数：无
- 删除参数：无
- 代码策略逻辑改动：无
- 实盘入口改动：无
- CTP 连接：无
- 订单 API 调用：`0`

## 结果

| product | daily_net_pnl | window_return_pct | closed_lot_realized_pnl | trade_count | active_days | max_drawdown_pct | end_reset_equity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `m.DCE` | 23,990.0 | 15.99% | 24,650.0 | 10 | 23 | -8.57% | 173,990.0 |
| `ni.SHFE` | 17,860.0 | 11.91% | 56,700.0 | 3 | 4 | -11.13% | 167,860.0 |
| `CY.CZCE` | 14,100.0 | 9.40% | 2,200.0 | 5 | 28 | -1.68% | 164,100.0 |
| `eb.DCE` | 10,800.0 | 7.20% | 10,880.0 | 4 | 13 | -4.69% | 160,800.0 |
| `y.DCE` | 5,840.0 | 3.89% | 5,880.0 | 2 | 14 | -5.03% | 155,840.0 |
| `zn.SHFE` | 5,200.0 | 3.47% | 12,600.0 | 3 | 17 | -8.00% | 155,200.0 |
| `ag.SHFE` | 5,130.0 | 3.42% | 0.0 | 1 | 4 | -3.13% | 155,130.0 |
| `v.DCE` | 4,760.0 | 3.17% | 4,870.0 | 4 | 19 | -5.25% | 154,760.0 |
| `PK.CZCE` | 3,870.0 | 2.58% | 2,100.0 | 3 | 9 | -3.73% | 153,870.0 |
| `rr.DCE` | 60.0 | 0.04% | -1,140.0 | 1 | 1 | 0.00% | 150,060.0 |

## 输出

- 资金曲线：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage125_loss_window_top10_product_curves/stage125_loss_window_top10_product_reset_equity_curves.png`
- 收益条形图：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage125_loss_window_top10_product_curves/stage125_loss_window_top10_product_pnl_bar.png`
- 汇总 CSV：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage125_loss_window_top10_product_curves/stage125_loss_window_top10_product_summary.csv`
- 曲线 CSV：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage125_loss_window_top10_product_curves/stage125_loss_window_top10_product_curves.csv`

## 判断

- 这 10 个品种在 2022 亏损窗口单独跑 C9 确实是正贡献，但贡献结构并不均匀：`m/ni/CY/eb` 是主要贡献者，`rr` 基本只是微正。
- `ni` 的 daily PnL 和 closed-lot realized PnL 差异较大，说明窗口内存在跨窗口持仓或盯市/平仓口径差异，做组合扩池时必须以日级权益和组合保证金为准。
- 这一步不是扩池结论，只是确认“在当时窗口能赚钱的品种库存”。下一步若继续，应先把候选池预声明为 `m/ni/CY/eb/y/zn/ag/v/PK` 的收敛版，并做组合级 true-engine A/B、流动性/保证金/分钟缺口审计，而不是直接把 10 个品种加进正式版。

## 反过拟合与继续价值

- 反过拟合判断：本阶段不过拟合，因为只读取 Stage124 既有全品种结果，没有调参，没有按结果改策略。
- 继续价值判断：有继续价值，但只能作为候选池形成证据；如果继续直接在这 10 个品种上扫权重、扫月份或按 2022 窗口特化，就是过拟合。
