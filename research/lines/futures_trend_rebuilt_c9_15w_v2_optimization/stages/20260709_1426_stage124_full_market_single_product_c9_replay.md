# Stage124 全品种单品种 C9 盈利能力 replay

- 时间：`2026-07-09 13:49 CST`
- 是否重要突破版本：否。本阶段是全品种产品适配度库存，不是策略晋级。
- 阶段性质：诊断/库存；每个产品单独跑当前 C9/15w 真引擎，AI 产品池过滤关闭。
- 回放区间：`2020-01-01` 到 `2026-06-30`；重点窗口 `2022-03-09 -> 2022-06-29`。
- 覆盖：请求 `57` 个 full-market eligible 产品，成功 `57`，失败 `0`。

## 本次版本变更

- 新增参数：`enable_ai_product_pool_filter=False` 仅用于单品种诊断；`product_universe_csv_path` 每次替换为单品种 universe。
- 修改参数：仅账户资金固定为当前 official live `150,000`，单品种 universe 替换；C9 核心入场/出场/成本/stop-retry 参数不改。
- 删除参数：无。
- 策略/实盘入口：未修改。

## 结果摘要

- 全样本盈利产品数：`26`。
- 2022 亏损窗口盈利产品数：`10`。

### 全样本 Top10

| product_vt_symbol   |   total_net_pnl |   total_return_pct |   max_drawdown_pct |   total_trade_count |   loss_window_daily_net_pnl |   full_2022_daily_net_pnl |
|:--------------------|----------------:|-------------------:|-------------------:|--------------------:|----------------------------:|--------------------------:|
| FG.CZCE             |     376839.2000 |           251.2261 |           -12.8486 |             58.0000 |                  -4560.0000 |               -12060.0000 |
| ag.SHFE             |     282585.0000 |           188.3900 |           -11.8659 |             62.0000 |                   5130.0000 |                 9000.0000 |
| OI.CZCE             |     101730.0000 |            67.8200 |           -25.8432 |             71.0000 |                  -2320.0000 |               -24010.0000 |
| SM.CZCE             |      98685.0000 |            65.7900 |           -21.8259 |             68.0000 |                 -21690.0000 |               -32910.0000 |
| ni.SHFE             |      95060.0000 |            63.3733 |           -12.9444 |             66.0000 |                  17860.0000 |                77730.0000 |
| ru.SHFE             |      88950.0000 |            59.3000 |           -16.5330 |             57.0000 |                 -10250.0000 |                -9300.0000 |
| jm.DCE              |      83760.6000 |            55.8404 |           -20.2818 |             71.0000 |                 -10980.0000 |                 3180.0000 |
| m.DCE               |      48430.0000 |            32.2867 |           -23.3698 |             71.0000 |                  23990.0000 |                51210.0000 |
| al.SHFE             |      37775.0000 |            25.1833 |           -29.8701 |             77.0000 |                 -28650.0000 |               -35300.0000 |
| y.DCE               |      28560.0000 |            19.0400 |           -14.9247 |             44.0000 |                   5840.0000 |                 8560.0000 |

### 2022 亏损窗口 Top10

| product_vt_symbol   |   loss_window_daily_net_pnl |   total_net_pnl |   full_2022_daily_net_pnl |   total_trade_count |
|:--------------------|----------------------------:|----------------:|--------------------------:|--------------------:|
| m.DCE               |                  23990.0000 |      48430.0000 |                51210.0000 |             71.0000 |
| ni.SHFE             |                  17860.0000 |      95060.0000 |                77730.0000 |             66.0000 |
| CY.CZCE             |                  14100.0000 |     -11875.0000 |                  175.0000 |             48.0000 |
| eb.DCE              |                  10800.0000 |     -16065.0000 |                 7825.0000 |             56.0000 |
| y.DCE               |                   5840.0000 |      28560.0000 |                 8560.0000 |             44.0000 |
| zn.SHFE             |                   5200.0000 |       6400.0000 |                 4050.0000 |             88.0000 |
| ag.SHFE             |                   5130.0000 |     282585.0000 |                 9000.0000 |             62.0000 |
| v.DCE               |                   4760.0000 |      -4465.0000 |                -4410.0000 |             51.0000 |
| PK.CZCE             |                   3870.0000 |     -13560.0000 |                 3000.0000 |             54.0000 |
| rr.DCE              |                     60.0000 |       -890.0000 |                -3150.0000 |             28.0000 |

### 2022 亏损窗口 Worst10

| product_vt_symbol   |   loss_window_daily_net_pnl |   total_net_pnl |   full_2022_daily_net_pnl |   total_trade_count |
|:--------------------|----------------------------:|----------------:|--------------------------:|--------------------:|
| MA.CZCE             |                 -33340.0000 |     -51191.0000 |               -25430.0000 |             68.0000 |
| al.SHFE             |                 -28650.0000 |      37775.0000 |               -35300.0000 |             77.0000 |
| SM.CZCE             |                 -21690.0000 |      98685.0000 |               -32910.0000 |             68.0000 |
| AP.CZCE             |                 -17800.0000 |       7887.2000 |               -37290.0000 |             58.0000 |
| TA.CZCE             |                 -16700.0000 |     -17470.0000 |               -27620.0000 |             69.0000 |
| pg.DCE              |                 -13360.0000 |     -23800.0000 |               -24600.0000 |             61.0000 |
| p.DCE               |                 -11440.0000 |     -37240.0000 |               -13140.0000 |             72.0000 |
| lu.INE              |                 -11410.0000 |      12730.0000 |                11660.0000 |             60.0000 |
| jm.DCE              |                 -10980.0000 |      83760.6000 |                 3180.0000 |             71.0000 |
| ru.SHFE             |                 -10250.0000 |      88950.0000 |                -9300.0000 |             57.0000 |

## 关键指标

- 期末权益：见 `product_summary`，本阶段不是单一组合权益。
- 总收益：见各产品 `total_return_pct`。
- 最大回撤：见各产品 `max_drawdown_pct`。
- Sharpe：见各产品 `sharpe`。
- 总滑点：见各产品 `total_slippage`。
- 总交易次数：见各产品 `total_trade_count`。
- 胜率：本阶段未以日胜率作为选品依据；后续若进入组合 A/B 再补。

## 反过拟合与继续价值

- 是否过拟合：否。未按结果新增阈值、黑名单或参数，只是固定口径全市场 replay。
- 是否还有价值继续：有。下一步可以用这个库存提出预声明候选池，再做组合级真实引擎 A/B；不能直接按历史 PnL 排名上线。

## 输出

- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage124_full_market_single_product_c9_replay/rebuilt_c9_v2_stage124_full_market_single_product_c9_replay_product_summary_stage124_full_market_single_product_c9_replay_v1.csv`
- period_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage124_full_market_single_product_c9_replay/rebuilt_c9_v2_stage124_full_market_single_product_c9_replay_product_period_summary_stage124_full_market_single_product_c9_replay_v1.csv`
- annual_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage124_full_market_single_product_c9_replay/rebuilt_c9_v2_stage124_full_market_single_product_c9_replay_annual_summary_stage124_full_market_single_product_c9_replay_v1.csv`
- closed_lots：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage124_full_market_single_product_c9_replay/rebuilt_c9_v2_stage124_full_market_single_product_c9_replay_closed_lots_stage124_full_market_single_product_c9_replay_v1.csv.gz`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage124_full_market_single_product_c9_replay/rebuilt_c9_v2_stage124_full_market_single_product_c9_replay_report_stage124_full_market_single_product_c9_replay_v1.md`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage124_full_market_single_product_c9_replay/rebuilt_c9_v2_stage124_full_market_single_product_c9_replay_decision_stage124_full_market_single_product_c9_replay_v1.json`
