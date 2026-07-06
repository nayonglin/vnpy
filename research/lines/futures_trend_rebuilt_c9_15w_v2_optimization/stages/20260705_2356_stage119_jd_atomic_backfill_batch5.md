# Stage119 jd atomic retry backfill

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T23:56:44
- 阶段性质：数据补齐流程修正；先临时下载、strict gate 验收、再发布；不回测收益、不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考：TqSdk DataDownloader/TqBacktest 文档、vn.py BarData 语义。
- 我的判断：Stage114 的超时半成品说明“下载器输出目录”和“回测可发现目录”必须隔离；Stage119 只解决数据准入，不代表策略收益提升。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage119_jd_atomic_backfill_batch5.py`
- 新增参数：`STAGE119_ENABLE_DOWNLOAD`、`STAGE119_MAX_SYMBOLS`、`STAGE119_MAX_SECONDS_PER_SYMBOL`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage119_jd_atomic_batch5_success_margin_still_blocked`
- download_enabled：`True`
- planned_contract_count：`2`
- downloaded_status_count：`2`
- temp_strict_ready_count：`2`
- published_count：`2`
- quarantined_count：`0`
- published_minute_rows：`40500`
- before_remaining_jd_not_ready：`2`
- after_remaining_jd_not_ready：`0`
- after_minute_missing：`6`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- remaining_blockers：`non_jd_tail_minute_files=6`、`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Summary

|   before_strict_ready |   before_minute_missing |   before_remaining_jd_not_ready |   published_count |   quarantined_count |   stale_quarantined_count |   after_strict_ready |   after_minute_missing |   after_remaining_jd_not_ready |
|----------------------:|------------------------:|--------------------------------:|------------------:|--------------------:|--------------------------:|---------------------:|-----------------------:|-------------------------------:|
|                    31 |                       8 |                               2 |                 2 |                   0 |                         0 |                   33 |                      6 |                              0 |

## Stage112 最终门槛复核

- `manifest_contract_count`：`39`
- `minute_file_ready_count`：`33`
- `strict_ready_count`：`33`
- `strict_failed_count`：`0`
- `minute_missing_count`：`6`
- `remaining_jd_not_ready_count`：`0`
- `jd_margin_history_ready`：`False`
- `ready_for_true_ledger_replay`：`False`

说明：Stage119 已把 jd 分钟线缺口清零，但这不是全量数据就绪。当前仍缺 6 个非 jd 尾部分钟文件，以及 `jd.DCE` 精确逐日保证金历史；因此 Stage208 真承载回测仍不能放行。

剩余非 jd 分钟缺口：

| contract_vt | product_vt_symbol | request_start_date | request_end_date | blocking_reason |
| --- | --- | --- | --- | --- |
| SH609.CZCE | SH.CZCE | 2026-06-17 | 2026-06-30 | missing_file |
| SM609.CZCE | SM.CZCE | 2026-06-04 | 2026-06-30 | missing_file |
| au2608.SHFE | au.SHFE | 2026-05-26 | 2026-06-30 | missing_file |
| cu2607.SHFE | cu.SHFE | 2026-05-22 | 2026-06-23 | missing_file |
| cu2608.SHFE | cu.SHFE | 2026-06-24 | 2026-06-30 | missing_file |
| lh2609.DCE | lh.DCE | 2026-06-02 | 2026-06-30 | missing_file |

## Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows |   stage112_expected_jd_day_rows | priority                 | output_path                                                                                                                                                                              | final_output_path                                                                                                                                           |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|--------------------------------:|:-------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| jd2209.DCE    | jd.DCE              | DCE.jd2209  | 2022-04-07           | 2022-08-12         | 2022-04-07                | 2022-08-13              |                    88 |                           19800 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2209_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2209_minute_backtest.csv |
| jd2409.DCE    | jd.DCE              | DCE.jd2409  | 2024-04-10           | 2024-08-21         | 2024-04-10                | 2024-08-22              |                    92 |                           20700 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2409_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2409_minute_backtest.csv |

## Download Status

| contract_vt   | tq_symbol   | download_start_datetime   | download_end_datetime   | status     |   rows | first_bar_datetime   | last_bar_datetime   |   elapsed_seconds | output_path                                                                                                                                                                              | sha256                                                           | message   |
|:--------------|:------------|:--------------------------|:------------------------|:-----------|-------:|:---------------------|:--------------------|------------------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------|:----------|
| jd2209.DCE    | DCE.jd2209  | 2022-04-07 00:00:00       | 2022-08-13 00:00:00     | downloaded |  19800 | 2022-04-07 09:00:00  | 2022-08-12 14:59:00 |            336.72 | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2209_minute_backtest.csv | 882c5324d278ed77e4439c299a200102b79b7ad60d6a35c94cf4a46bf396cb6a |           |
| jd2409.DCE    | DCE.jd2409  | 2024-04-10 00:00:00       | 2024-08-22 00:00:00     | downloaded |  20700 | 2024-04-10 09:00:00  | 2024-08-21 14:59:00 |            342.91 | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2409_minute_backtest.csv | 13feb9bacce0ba1312f2ed7145cecd0b55cfe67bb4250e35172a1342b398575a |           |

## Temp Strict Audit

| contract_vt   | download_status   |   download_rows | download_message   | temp_path                                                                                                                                                                                | final_output_path                                                                                                                                           | temp_exists   | strict_ready   |   strict_rows |   expected_jd_day_rows | blocking_reason   | first_bar_datetime   | last_bar_datetime   | sha256                                                           |
|:--------------|:------------------|----------------:|:-------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------|:---------------|--------------:|-----------------------:|:------------------|:---------------------|:--------------------|:-----------------------------------------------------------------|
| jd2209.DCE    | downloaded        |           19800 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2209_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2209_minute_backtest.csv | True          | True           |         19800 |                  19800 |                   | 2022-04-07 09:00:00  | 2022-08-12 14:59:00 | 882c5324d278ed77e4439c299a200102b79b7ad60d6a35c94cf4a46bf396cb6a |
| jd2409.DCE    | downloaded        |           20700 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2409_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2409_minute_backtest.csv | True          | True           |         20700 |                  20700 |                   | 2024-04-10 09:00:00  | 2024-08-21 14:59:00 | 13feb9bacce0ba1312f2ed7145cecd0b55cfe67bb4250e35172a1342b398575a |

## Publish Manifest

| contract_vt   | download_status   | strict_ready   | action    | temp_path                                                                                                                                                                                | final_output_path                                                                                                                                           | old_final_quarantine_path   | temp_quarantine_path   | publish_device_match   | published_exists   |   strict_rows | sha256                                                           | blocking_reason   |
|:--------------|:------------------|:---------------|:----------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------|:-----------------------|:-----------------------|:-------------------|--------------:|:-----------------------------------------------------------------|:------------------|
| jd2209.DCE    | downloaded        | True           | published | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2209_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2209_minute_backtest.csv |                             |                        | True                   | True               |         19800 | 882c5324d278ed77e4439c299a200102b79b7ad60d6a35c94cf4a46bf396cb6a |                   |
| jd2409.DCE    | downloaded        | True           | published | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2409_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2409_minute_backtest.csv |                             |                        | True                   | True               |         20700 | 13feb9bacce0ba1312f2ed7145cecd0b55cfe67bb4250e35172a1342b398575a |                   |

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。本阶段只修下载发布口径和补缺失分钟线，不看收益曲线、不调策略参数。
- 运行后：否。atomic publish 只减少脏数据进入回测的概率，不会制造绩效。

## 继续价值反思

- 运行前：有。Stage114 证明超时半成品会污染存在性口径，必须先把下载流程改成严格验收发布。
- 运行后：有。若发布成功可继续补剩余 jd；若未成功，应继续降低批量或延长单合约超时，而不是跑 true ledger。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/rebuilt_c9_v2_stage119_jd_atomic_backfill_batch5_report_stage119_jd_atomic_backfill_batch5_v1.md`
- plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/rebuilt_c9_v2_stage119_jd_atomic_backfill_batch5_plan_stage119_jd_atomic_backfill_batch5_v1.csv`
- status：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/rebuilt_c9_v2_stage119_jd_atomic_backfill_batch5_download_status_stage119_jd_atomic_backfill_batch5_v1.csv`
- temp_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/rebuilt_c9_v2_stage119_jd_atomic_backfill_batch5_temp_strict_audit_stage119_jd_atomic_backfill_batch5_v1.csv`
- publish_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/rebuilt_c9_v2_stage119_jd_atomic_backfill_batch5_publish_manifest_stage119_jd_atomic_backfill_batch5_v1.csv`
- before_strict：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/rebuilt_c9_v2_stage119_jd_atomic_backfill_batch5_before_strict_manifest_stage119_jd_atomic_backfill_batch5_v1.csv`
- after_strict：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/rebuilt_c9_v2_stage119_jd_atomic_backfill_batch5_after_strict_manifest_stage119_jd_atomic_backfill_batch5_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/rebuilt_c9_v2_stage119_jd_atomic_backfill_batch5_summary_stage119_jd_atomic_backfill_batch5_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/rebuilt_c9_v2_stage119_jd_atomic_backfill_batch5_input_audit_stage119_jd_atomic_backfill_batch5_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/rebuilt_c9_v2_stage119_jd_atomic_backfill_batch5_decision_stage119_jd_atomic_backfill_batch5_v1.json`
