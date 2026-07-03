# Stage052 TqSdk jd 分钟缺口受控补数

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T11:01:55
- 阶段性质：数据补齐；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk 官方参考、DataDownloader 文档、TqBacktest 文档。
- 我的判断：DataDownloader 更适合长期批量历史下载但属于专业版；本阶段用 Stage051 已验证的 TqBacktest 路线做受控补数。补数只减少数据阻塞，不代表策略有效。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage052_tqsdk_jd_minute_backfill.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage052_tqsdk_jd_minute_backfill.py`
- 新增参数：`STAGE052_ENABLE_DOWNLOAD`、`STAGE052_MAX_SYMBOLS`、`STAGE052_MAX_SECONDS_PER_SYMBOL`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage052_tqsdk_jd_minute_backfill_partial_success_margin_still_blocked`
- download_enabled：`True`
- planned_contract_count：`5`
- download_success_contract_count：`5`
- downloaded_minute_rows：`16650`
- before_missing：`44`
- after_missing：`39`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Backfill Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows | priority                 | output_path                                                                                                                                                 |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|:-------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| jd2410.DCE    | jd.DCE              | DCE.jd2410  | 2024-08-22           | 2024-09-06         | 2024-08-22                | 2024-09-07              |                    12 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2410_minute_backtest.csv |
| jd2007.DCE    | jd.DCE              | DCE.jd2007  | 2020-05-28           | 2020-06-12         | 2020-05-28                | 2020-06-13              |                    12 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2007_minute_backtest.csv |
| jd2507.DCE    | jd.DCE              | DCE.jd2507  | 2025-05-20           | 2025-06-10         | 2025-05-20                | 2025-06-11              |                    15 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2507_minute_backtest.csv |
| jd2402.DCE    | jd.DCE              | DCE.jd2402  | 2023-12-15           | 2024-01-09         | 2023-12-15                | 2024-01-10              |                    17 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2402_minute_backtest.csv |
| jd2310.DCE    | jd.DCE              | DCE.jd2310  | 2023-08-15           | 2023-09-07         | 2023-08-15                | 2023-09-08              |                    18 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2310_minute_backtest.csv |

## Backfill Status

| contract_vt   | tq_symbol   | download_start_datetime   | download_end_datetime   | status     |   rows | first_bar_datetime   | last_bar_datetime   |   elapsed_seconds | output_path                                                                                                                                                 | sha256                                                           | message   |
|:--------------|:------------|:--------------------------|:------------------------|:-----------|-------:|:---------------------|:--------------------|------------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------|:----------|
| jd2410.DCE    | DCE.jd2410  | 2024-08-22 00:00:00       | 2024-09-07 00:00:00     | downloaded |   2700 | 2024-08-22 09:00:00  | 2024-09-06 14:59:00 |             63.44 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2410_minute_backtest.csv | 310bb18ea34f6360b11cbd9a63df2428c26ab8b0d333fe175bbde946b6325704 |           |
| jd2007.DCE    | DCE.jd2007  | 2020-05-28 00:00:00       | 2020-06-13 00:00:00     | downloaded |   2700 | 2020-05-28 09:00:00  | 2020-06-12 14:59:00 |             62.88 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2007_minute_backtest.csv | d3f8f652c4427350e00d3f23b5ca54d96055abc929f6ea51bde973f9f429b0e9 |           |
| jd2507.DCE    | DCE.jd2507  | 2025-05-20 00:00:00       | 2025-06-11 00:00:00     | downloaded |   3375 | 2025-05-20 09:00:00  | 2025-06-10 14:59:00 |             75.95 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2507_minute_backtest.csv | 8c806815fae108dabf7e0129be070431a6831892dfe346ac7b10de23654eb9b7 |           |
| jd2402.DCE    | DCE.jd2402  | 2023-12-15 00:00:00       | 2024-01-10 00:00:00     | downloaded |   3825 | 2023-12-15 09:00:00  | 2024-01-09 14:59:00 |             84.15 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2402_minute_backtest.csv | afc8258653c0bda09df0334a57785438d9de7e4a00d741a045e56454beb3f2c1 |           |
| jd2310.DCE    | DCE.jd2310  | 2023-08-15 00:00:00       | 2023-09-08 00:00:00     | downloaded |   4050 | 2023-08-15 09:00:00  | 2023-09-07 14:59:00 |             88.78 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2310_minute_backtest.csv | e6147963801aa1216b320786d986eeb05fe8b23b774304068a277961d61b844b |           |

## 过拟合反思

- 运行前判断：否。本阶段补的是 Stage049 缺失的 jd 分钟源，不根据收益表现筛选参数。
- 运行后判断：否。下载成功只减少数据阻塞；保证金未补前仍禁止 true ledger replay。

## 继续价值反思

- 运行前判断：有。Stage051 已证明 TqSdk 可读 jd 1m K，下一步应把小窗口成功转成可被 Stage049 发现的文件。
- 运行后判断：有。若批次成功，继续扩大到剩余 jd 合约；并行寻找 jd 逐日保证金，二者缺一不可。

## 输出文件

- backfill_plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage052_tqsdk_jd_minute_backfill/rebuilt_c9_v2_stage052_tqsdk_jd_minute_backfill_backfill_plan_stage052_tqsdk_jd_minute_backfill_v1.csv`
- backfill_status：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage052_tqsdk_jd_minute_backfill/rebuilt_c9_v2_stage052_tqsdk_jd_minute_backfill_backfill_status_stage052_tqsdk_jd_minute_backfill_v1.csv`
- file_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage052_tqsdk_jd_minute_backfill/rebuilt_c9_v2_stage052_tqsdk_jd_minute_backfill_file_manifest_stage052_tqsdk_jd_minute_backfill_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage052_tqsdk_jd_minute_backfill/rebuilt_c9_v2_stage052_tqsdk_jd_minute_backfill_decision_stage052_tqsdk_jd_minute_backfill_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage052_tqsdk_jd_minute_backfill/rebuilt_c9_v2_stage052_tqsdk_jd_minute_backfill_report_stage052_tqsdk_jd_minute_backfill_v1.md`
