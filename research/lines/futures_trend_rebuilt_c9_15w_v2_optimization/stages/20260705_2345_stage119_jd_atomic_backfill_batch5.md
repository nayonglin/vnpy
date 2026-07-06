# Stage119 jd atomic retry backfill

- 状态：已被 2026-07-05 23:56 的真实下载运行替代；本文件仅保留 dry-run 计划证据，不作为最终 Stage119 结果。
- 后续真实记录：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260705_2356_stage119_jd_atomic_backfill_batch5.md`

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T23:45:08
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

- decision：`stage119_jd_atomic_batch5_plan_only`
- download_enabled：`False`
- planned_contract_count：`2`
- downloaded_status_count：`0`
- temp_strict_ready_count：`0`
- published_count：`0`
- quarantined_count：`0`
- published_minute_rows：`0`
- before_remaining_jd_not_ready：`2`
- after_remaining_jd_not_ready：`2`
- after_minute_missing：`8`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Summary

|   before_strict_ready |   before_minute_missing |   before_remaining_jd_not_ready |   published_count |   quarantined_count |   stale_quarantined_count |   after_strict_ready |   after_minute_missing |   after_remaining_jd_not_ready |
|----------------------:|------------------------:|--------------------------------:|------------------:|--------------------:|--------------------------:|---------------------:|-----------------------:|-------------------------------:|
|                    31 |                       8 |                               2 |                 0 |                   0 |                         0 |                   31 |                      8 |                              2 |

## Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows |   stage112_expected_jd_day_rows | priority                 | output_path                                                                                                                                                                              | final_output_path                                                                                                                                           |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|--------------------------------:|:-------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| jd2209.DCE    | jd.DCE              | DCE.jd2209  | 2022-04-07           | 2022-08-12         | 2022-04-07                | 2022-08-13              |                    88 |                           19800 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2209_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2209_minute_backtest.csv |
| jd2409.DCE    | jd.DCE              | DCE.jd2409  | 2024-04-10           | 2024-08-21         | 2024-04-10                | 2024-08-22              |                    92 |                           20700 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2409_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2409_minute_backtest.csv |

## Download Status

_无记录_

## Temp Strict Audit

| contract_vt   | download_status   |   download_rows | download_message   | temp_path                                                                                                                                                                                | final_output_path                                                                                                                                           | temp_exists   | strict_ready   |   strict_rows |   expected_jd_day_rows | blocking_reason   | first_bar_datetime   | last_bar_datetime   | sha256   |
|:--------------|:------------------|----------------:|:-------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------|:---------------|--------------:|-----------------------:|:------------------|:---------------------|:--------------------|:---------|
| jd2209.DCE    |                   |               0 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2209_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2209_minute_backtest.csv | False         | False          |             0 |                  19800 | missing_file      |                      |                     |          |
| jd2409.DCE    |                   |               0 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2409_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2409_minute_backtest.csv | False         | False          |             0 |                  20700 | missing_file      |                      |                     |          |

## Publish Manifest

| contract_vt   | download_status   | strict_ready   | action       | temp_path                                                                                                                                                                                | final_output_path                                                                                                                                           | old_final_quarantine_path   | temp_quarantine_path   | publish_device_match   | published_exists   |   strict_rows | sha256   | blocking_reason   |
|:--------------|:------------------|:---------------|:-------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------|:-----------------------|:-----------------------|:-------------------|--------------:|:---------|:------------------|
| jd2209.DCE    |                   | False          | no_temp_file | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2209_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2209_minute_backtest.csv |                             |                        | False                  | False              |             0 |          | missing_file      |
| jd2409.DCE    |                   | False          | no_temp_file | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage119_jd_atomic_backfill_batch5/tmp_downloads/DCE/jd2409_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2409_minute_backtest.csv |                             |                        | False                  | False              |             0 |          | missing_file      |

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
