# Stage052 TqSdk jd 分钟缺口受控补数

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T11:13:34
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
- downloaded_minute_rows：`22050`
- before_missing：`39`
- after_missing：`34`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Backfill Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows | priority                 | output_path                                                                                                                                                 |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|:-------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| jd2011.DCE    | jd.DCE              | DCE.jd2011  | 2020-09-18           | 2020-10-21         | 2020-09-18                | 2020-10-22              |                    18 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2011_minute_backtest.csv |
| jd2512.DCE    | jd.DCE              | DCE.jd2512  | 2025-10-21           | 2025-11-14         | 2025-10-21                | 2025-11-15              |                    19 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2512_minute_backtest.csv |
| jd2311.DCE    | jd.DCE              | DCE.jd2311  | 2023-09-08           | 2023-10-12         | 2023-09-08                | 2023-10-13              |                    19 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2311_minute_backtest.csv |
| jd2607.DCE    | jd.DCE              | DCE.jd2607  | 2026-05-15           | 2026-06-12         | 2026-05-15                | 2026-06-13              |                    21 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2607_minute_backtest.csv |
| jd2510.DCE    | jd.DCE              | DCE.jd2510  | 2025-08-13           | 2025-09-10         | 2025-08-13                | 2025-09-11              |                    21 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2510_minute_backtest.csv |

## Backfill Status

| contract_vt   | tq_symbol   | download_start_datetime   | download_end_datetime   | status     |   rows | first_bar_datetime   | last_bar_datetime   |   elapsed_seconds | output_path                                                                                                                                                 | sha256                                                           | message   |
|:--------------|:------------|:--------------------------|:------------------------|:-----------|-------:|:---------------------|:--------------------|------------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------|:----------|
| jd2011.DCE    | DCE.jd2011  | 2020-09-18 00:00:00       | 2020-10-22 00:00:00     | downloaded |   4050 | 2020-09-18 09:00:00  | 2020-10-21 14:59:00 |             83.69 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2011_minute_backtest.csv | 7442d7729a16944d8b5d4fca2b66192ee458c6d0c0d22f1dc2e55fb966e1ee88 |           |
| jd2512.DCE    | DCE.jd2512  | 2025-10-21 00:00:00       | 2025-11-15 00:00:00     | downloaded |   4275 | 2025-10-21 09:00:00  | 2025-11-14 14:59:00 |             88.08 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2512_minute_backtest.csv | b515d5eceb5cefb25be191172db08f0574955d3129e06d35a91f653846ec605d |           |
| jd2311.DCE    | DCE.jd2311  | 2023-09-08 00:00:00       | 2023-10-13 00:00:00     | downloaded |   4275 | 2023-09-08 09:00:00  | 2023-10-12 14:59:00 |             90.21 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2311_minute_backtest.csv | 722f9fca46cbb9186eefa3f6da7c65c40def7b89adc4f802daa110c715f377a8 |           |
| jd2607.DCE    | DCE.jd2607  | 2026-05-15 00:00:00       | 2026-06-13 00:00:00     | downloaded |   4725 | 2026-05-15 09:00:00  | 2026-06-12 14:59:00 |             91.26 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2607_minute_backtest.csv | bfc0bee14ee785f24728b6e6994829e052a984120f3946a25a64265496cb6a73 |           |
| jd2510.DCE    | DCE.jd2510  | 2025-08-13 00:00:00       | 2025-09-11 00:00:00     | downloaded |   4725 | 2025-08-13 09:00:00  | 2025-09-10 14:59:00 |             94.77 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2510_minute_backtest.csv | 602fd350f8efa18cbf1c9e3f7a9080f761d0aee9182537c04c14a080ba5ff810 |           |

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
