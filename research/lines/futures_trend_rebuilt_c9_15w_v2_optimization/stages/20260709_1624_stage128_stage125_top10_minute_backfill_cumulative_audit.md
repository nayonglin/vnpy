# Stage128 Stage125 前十品种分钟补数累计审计

- 时间：2026-07-09T16:27:22
- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 类型：数据补齐验收，不是新策略版本，不是新回测
- decision：`stage128_stage125_top10_window_raw_minute_backfill_complete`
- expected_contract_count：`16`
- strict_entry_day_ready_count：`16`
- missing_entry_date_count：`0`
- total_raw_minute_rows：`33117`
- 策略变更：无
- true engine run：无
- 订单 API：`0`
- CTP：`False`
- Stage861 full-minute 源更新：`False`

## Summary

| metric                              |   value |
|:------------------------------------|--------:|
| expected_contract_count             |      16 |
| expected_entry_date_count           |      32 |
| raw_file_exists_count               |      16 |
| strict_entry_day_ready_count        |      16 |
| covered_entry_date_count            |      32 |
| missing_entry_date_count            |       0 |
| total_raw_minute_rows               |   33117 |
| duplicate_key_count                 |       0 |
| ohlc_null_count                     |       0 |
| ohlc_relation_error_count           |       0 |
| negative_volume_count               |       0 |
| stage861_full_minute_source_updated |   False |
| strategy_rule_changed               |   False |
| true_engine_run                     |   False |
| order_api_called                    |       0 |
| ctp_connected                       |   False |

## Contract Audit

| contract_vt   | product_vt_symbol   | raw_minute_path                                                                                                                                                                  | exists   |   rows | first_bar_datetime   | last_bar_datetime   | sha256                                                           |   entry_date_count | entry_dates                                 |   covered_entry_date_count | missing_entry_dates   |   duplicate_key_count |   ohlc_null_count |   ohlc_relation_error_count |   negative_volume_count | read_error   | strict_entry_day_ready   |
|:--------------|:--------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:---------|-------:|:---------------------|:--------------------|:-----------------------------------------------------------------|-------------------:|:--------------------------------------------|---------------------------:|:----------------------|----------------------:|------------------:|----------------------------:|------------------------:|:-------------|:-------------------------|
| ni2204.SHFE   | ni.SHFE             | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/SHFE/ni2204_minute_backtest.csv | True     |    465 | 2022-03-04 00:00:00  | 2022-03-04 23:59:00 | 62488c8b3edc9fbf53829feb012fd3dbd5552c427a04495f3afa60bd636c63cd |                  1 | 2022-03-04                                  |                          1 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| m2209.DCE     | m.DCE               | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/DCE/m2209_minute_backtest.csv   | True     |  10455 | 2022-04-26 09:00:00  | 2022-06-13 22:59:00 | 6fa5091fb01d94c142b75ed1b8a032856302e55885b6fde128f2c68a44609f8a |                  4 | 2022-04-26|2022-05-23|2022-06-01|2022-06-13 |                          4 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| ni2205.SHFE   | ni.SHFE             | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/SHFE/ni2205_minute_backtest.csv | True     |    405 | 2022-04-25 09:00:00  | 2022-04-25 23:59:00 | ac073319c398f49bf03af02a685cb8bdd6d8c476e697acc12391c6e2b3fd1980 |                  1 | 2022-04-25                                  |                          1 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| ag2212.SHFE   | ag.SHFE             | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/SHFE/ag2212_minute_backtest.csv | True     |  14502 | 2022-06-24 00:00:00  | 2022-10-26 23:59:00 | 312add09fc003ed5b53dc49d58fd425ab90d7ce6421d6c8c269575b4f36f7b31 |                  4 | 2022-06-24|2022-08-17|2022-10-13|2022-10-26 |                          4 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| zn2205.SHFE   | zn.SHFE             | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/SHFE/zn2205_minute_backtest.csv | True     |    285 | 2022-04-01 00:00:00  | 2022-04-01 14:59:00 | 605a34d3eb833025fef18a0ece4fdd503d445c95585feb705f96694435369d73 |                  1 | 2022-04-01                                  |                          1 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| CY209.CZCE    | CY.CZCE             | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/CZCE/CY209_minute_backtest.csv  | True     |   1380 | 2022-05-16 09:00:00  | 2022-08-25 22:59:00 | 8617b3fcaca1bc351de7a551104dbc890e04b8a36c9ee9eff6bc4c54e317018d |                  4 | 2022-05-16|2022-05-19|2022-06-09|2022-08-25 |                          4 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| m2205.DCE     | m.DCE               | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/DCE/m2205_minute_backtest.csv   | True     |   1380 | 2021-12-10 09:00:00  | 2022-03-09 22:59:00 | ef58a0ce24c5aa73733e27ce0b5b91157d0f1fcc6654c9dcc24bbfe312e8f2fb |                  4 | 2021-12-10|2022-01-05|2022-02-07|2022-03-09 |                          4 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| eb2207.DCE    | eb.DCE              | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/DCE/eb2207_minute_backtest.csv  | True     |    345 | 2022-05-30 09:00:00  | 2022-05-30 22:59:00 | a6e75cef1a216ae07c6057cefca77a9e352f011360b52deb2e7870a454a58ec3 |                  1 | 2022-05-30                                  |                          1 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| y2209.DCE     | y.DCE               | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/DCE/y2209_minute_backtest.csv   | True     |    690 | 2022-04-15 09:00:00  | 2022-08-16 22:59:00 | d11752ea5ce8109252109bac21274f9cea4fc1577707a86e99fc9357df3759ad |                  2 | 2022-04-15|2022-08-16                       |                          2 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| zn2204.SHFE   | zn.SHFE             | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/SHFE/zn2204_minute_backtest.csv | True     |    465 | 2022-03-08 00:00:00  | 2022-03-08 23:59:00 | 2ed4325ebdfcebc60be219d40a0314bb874d34080567597a44c647e501135ad4 |                  1 | 2022-03-08                                  |                          1 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| PK210.CZCE    | PK.CZCE             | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/CZCE/PK210_minute_backtest.csv  | True     |    225 | 2022-05-19 09:00:00  | 2022-05-19 14:59:00 | 96665f3d60eb38b458ff65ff8a93d3596614b13870cc63aba18c3fa533cd8823 |                  1 | 2022-05-19                                  |                          1 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| eb2206.DCE    | eb.DCE              | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/DCE/eb2206_minute_backtest.csv  | True     |    345 | 2022-05-09 09:00:00  | 2022-05-09 22:59:00 | 10382202b8b786ba05d0d23ad12c3375fa1aa9ebcef01ccc39324c522afca3b2 |                  1 | 2022-05-09                                  |                          1 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| v2205.DCE     | v.DCE               | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/DCE/v2205_minute_backtest.csv   | True     |    690 | 2022-01-17 09:00:00  | 2022-03-25 22:59:00 | b82b49b19fdef5323aea8372f624e8142c017a959a39bfa378aebfcd74a839a0 |                  2 | 2022-01-17|2022-03-25                       |                          2 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| v2209.DCE     | v.DCE               | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/DCE/v2209_minute_backtest.csv   | True     |    345 | 2022-05-19 09:00:00  | 2022-05-19 22:59:00 | 470d862ac748b2d1c78625b835877651eb070ff9117ebc2c4240a45d2d2ba57a |                  1 | 2022-05-19                                  |                          1 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| PK204.CZCE    | PK.CZCE             | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/CZCE/PK204_minute_backtest.csv  | True     |    450 | 2022-01-27 09:00:00  | 2022-03-02 14:59:00 | 790c01ee4d6f8fafba7ab3cdf333d7ee80d555e04ba8787e96c4e09d1cd4bb64 |                  2 | 2022-01-27|2022-03-02                       |                          2 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |
| rr2205.DCE    | rr.DCE              | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill/DCE/rr2205_minute_backtest.csv  | True     |    690 | 2022-02-16 09:00:00  | 2022-03-07 22:59:00 | b4dad1d1fd30dc477384d7d680b120399ea0e9f7abeb7fc6bb2c92776915a94b |                  2 | 2022-02-16|2022-03-07                       |                          2 |                       |                     0 |                 0 |                           0 |                       0 |              | True                     |

## 后续

- 若要让 Stage124/125 重跑时使用这些数据，需要合并到 Stage861 覆盖版 full-minute 源，或在 Stage124 前显式注入 overlay。
- 这次补的是 Stage125 2022 亏损窗口前十品种的 entry-day raw 分钟线，不等于全市场、全合约、全持仓周期分钟线已经完整。

## 反思

- 运行前过拟合反思：否。本阶段只做数据覆盖审计，不按结果调参或筛选策略。
- 运行后过拟合反思：否。补齐和验收 raw 分钟输入只提高输入完整性，不构成策略优化。
- 运行前继续价值反思：有。Stage126 指出 Stage125 前十品种分钟加载为 0，必须先验收 raw 分钟输入。
- 运行后继续价值反思：有。raw entry-day 数据已可用；下一步若要影响回测，需要合并到 Stage861 覆盖源或让 Stage124 显式读取 overlay。
