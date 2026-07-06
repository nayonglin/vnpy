# Stage115 jd atomic retry backfill

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T23:02:49
- 阶段性质：数据补齐流程修正；先临时下载、strict gate 验收、再发布；不回测收益、不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考：TqSdk DataDownloader/TqBacktest 文档、vn.py BarData 语义。
- 我的判断：Stage114 的超时半成品说明“下载器输出目录”和“回测可发现目录”必须隔离；Stage115 只解决数据准入，不代表策略收益提升。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage115_jd_atomic_retry_backfill.py`
- 新增参数：`STAGE115_ENABLE_DOWNLOAD`、`STAGE115_MAX_SYMBOLS`、`STAGE115_MAX_SECONDS_PER_SYMBOL`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage115_jd_atomic_retry_success_margin_still_blocked`
- download_enabled：`True`
- planned_contract_count：`2`
- downloaded_status_count：`2`
- temp_strict_ready_count：`2`
- published_count：`2`
- quarantined_count：`0`
- published_minute_rows：`31050`
- before_remaining_jd_not_ready：`10`
- after_remaining_jd_not_ready：`8`
- after_minute_missing：`14`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## 2026-07-05 23:03 全量 Stage112 复核

- 复核脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage112_strict_minute_content_gate.py`
- 复核记录：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260705_2303_stage112_strict_minute_content_gate.md`
- 复核结论：`minute_file_ready_count=25`，`strict_ready_count=25`，`strict_failed_count=0`，`minute_missing_count=14`，`remaining_jd_not_ready_count=8`。
- 阻塞仍在：`jd_margin_history_ready=False`，所以 `ready_for_true_ledger_replay=False`。
- 口径说明：本阶段有效 published 文件只有 `jd2501.DCE` 和 `jd2205.DCE`；临时下载目录已无残留文件，`quarantined_count=0`。

## Summary

|   before_strict_ready |   before_minute_missing |   before_remaining_jd_not_ready |   published_count |   quarantined_count |   stale_quarantined_count |   after_strict_ready |   after_minute_missing |   after_remaining_jd_not_ready |
|----------------------:|------------------------:|--------------------------------:|------------------:|--------------------:|--------------------------:|---------------------:|-----------------------:|-------------------------------:|
|                    23 |                      16 |                              10 |                 2 |                   0 |                         0 |                   25 |                     14 |                              8 |

## Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows |   stage112_expected_jd_day_rows | priority                 | output_path                                                                                                                                                                             | final_output_path                                                                                                                                           |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|--------------------------------:|:-------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| jd2501.DCE    | jd.DCE              | DCE.jd2501  | 2024-09-09           | 2024-12-13         | 2024-09-09                | 2024-12-14              |                    63 |                           14175 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2501_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2501_minute_backtest.csv |
| jd2205.DCE    | jd.DCE              | DCE.jd2205  | 2021-12-13           | 2022-04-06         | 2021-12-13                | 2022-04-07              |                    75 |                           16875 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2205_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2205_minute_backtest.csv |

## Download Status

| contract_vt   | tq_symbol   | download_start_datetime   | download_end_datetime   | status     |   rows | first_bar_datetime   | last_bar_datetime   |   elapsed_seconds | output_path                                                                                                                                                                             | sha256                                                           | message   |
|:--------------|:------------|:--------------------------|:------------------------|:-----------|-------:|:---------------------|:--------------------|------------------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------|:----------|
| jd2501.DCE    | DCE.jd2501  | 2024-09-09 00:00:00       | 2024-12-14 00:00:00     | downloaded |  14175 | 2024-09-09 09:00:00  | 2024-12-13 14:59:00 |            243.3  | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2501_minute_backtest.csv | aa34cb26576014ecaef398a0d4fbd136b7abc1229b199b5cd5ff4fbd40a3f2a7 |           |
| jd2205.DCE    | DCE.jd2205  | 2021-12-13 00:00:00       | 2022-04-07 00:00:00     | downloaded |  16875 | 2021-12-13 09:00:00  | 2022-04-06 14:59:00 |            285.25 | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2205_minute_backtest.csv | a0fc34d80f9fcd20f110307e4e02761a69b23f1b0a311d23f27a1a4bef4c7271 |           |

## Temp Strict Audit

| contract_vt   | download_status   |   download_rows | download_message   | temp_path                                                                                                                                                                               | final_output_path                                                                                                                                           | temp_exists   | strict_ready   |   strict_rows |   expected_jd_day_rows | blocking_reason   | first_bar_datetime   | last_bar_datetime   | sha256                                                           |
|:--------------|:------------------|----------------:|:-------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------|:---------------|--------------:|-----------------------:|:------------------|:---------------------|:--------------------|:-----------------------------------------------------------------|
| jd2501.DCE    | downloaded        |           14175 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2501_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2501_minute_backtest.csv | True          | True           |         14175 |                  14175 |                   | 2024-09-09 09:00:00  | 2024-12-13 14:59:00 | aa34cb26576014ecaef398a0d4fbd136b7abc1229b199b5cd5ff4fbd40a3f2a7 |
| jd2205.DCE    | downloaded        |           16875 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2205_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2205_minute_backtest.csv | True          | True           |         16875 |                  16875 |                   | 2021-12-13 09:00:00  | 2022-04-06 14:59:00 | a0fc34d80f9fcd20f110307e4e02761a69b23f1b0a311d23f27a1a4bef4c7271 |

## Publish Manifest

| contract_vt   | download_status   | strict_ready   | action    | temp_path                                                                                                                                                                               | final_output_path                                                                                                                                           | quarantine_path   | published_exists   |   strict_rows | sha256                                                           | blocking_reason   |
|:--------------|:------------------|:---------------|:----------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------|:-------------------|--------------:|:-----------------------------------------------------------------|:------------------|
| jd2501.DCE    | downloaded        | True           | published | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2501_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2501_minute_backtest.csv |                   | True               |         14175 | aa34cb26576014ecaef398a0d4fbd136b7abc1229b199b5cd5ff4fbd40a3f2a7 |                   |
| jd2205.DCE    | downloaded        | True           | published | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2205_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2205_minute_backtest.csv |                   | True               |         16875 | a0fc34d80f9fcd20f110307e4e02761a69b23f1b0a311d23f27a1a4bef4c7271 |                   |

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。本阶段只修下载发布口径和补缺失分钟线，不看收益曲线、不调策略参数。
- 运行后：否。atomic publish 只减少脏数据进入回测的概率，不会制造绩效。

## 继续价值反思

- 运行前：有。Stage114 证明超时半成品会污染存在性口径，必须先把下载流程改成严格验收发布。
- 运行后：有。若发布成功可继续补剩余 jd；若未成功，应继续降低批量或延长单合约超时，而不是跑 true ledger。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/rebuilt_c9_v2_stage115_jd_atomic_retry_backfill_report_stage115_jd_atomic_retry_backfill_v1.md`
- plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/rebuilt_c9_v2_stage115_jd_atomic_retry_backfill_plan_stage115_jd_atomic_retry_backfill_v1.csv`
- status：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/rebuilt_c9_v2_stage115_jd_atomic_retry_backfill_download_status_stage115_jd_atomic_retry_backfill_v1.csv`
- temp_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/rebuilt_c9_v2_stage115_jd_atomic_retry_backfill_temp_strict_audit_stage115_jd_atomic_retry_backfill_v1.csv`
- publish_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/rebuilt_c9_v2_stage115_jd_atomic_retry_backfill_publish_manifest_stage115_jd_atomic_retry_backfill_v1.csv`
- before_strict：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/rebuilt_c9_v2_stage115_jd_atomic_retry_backfill_before_strict_manifest_stage115_jd_atomic_retry_backfill_v1.csv`
- after_strict：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/rebuilt_c9_v2_stage115_jd_atomic_retry_backfill_after_strict_manifest_stage115_jd_atomic_retry_backfill_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/rebuilt_c9_v2_stage115_jd_atomic_retry_backfill_summary_stage115_jd_atomic_retry_backfill_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/rebuilt_c9_v2_stage115_jd_atomic_retry_backfill_input_audit_stage115_jd_atomic_retry_backfill_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/rebuilt_c9_v2_stage115_jd_atomic_retry_backfill_decision_stage115_jd_atomic_retry_backfill_v1.json`
