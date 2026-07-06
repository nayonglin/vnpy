# Stage115 jd atomic retry backfill

- 状态：`superseded_by_20260705_2302_stage115_jd_atomic_retry_backfill.md`
- 说明：本文件仅为 plan-only dry-run 记录；正式下载、strict audit、publish 结果以 `20260705_2302_stage115_jd_atomic_retry_backfill.md` 和 `20260705_2303_stage112_strict_minute_content_gate.md` 为准。

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T22:53:41
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

- decision：`stage115_jd_atomic_retry_plan_only`
- download_enabled：`False`
- planned_contract_count：`2`
- downloaded_status_count：`0`
- temp_strict_ready_count：`0`
- published_count：`0`
- quarantined_count：`0`
- published_minute_rows：`0`
- before_remaining_jd_not_ready：`10`
- after_remaining_jd_not_ready：`10`
- after_minute_missing：`16`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Summary

|   before_strict_ready |   before_minute_missing |   before_remaining_jd_not_ready |   published_count |   quarantined_count |   stale_quarantined_count |   after_strict_ready |   after_minute_missing |   after_remaining_jd_not_ready |
|----------------------:|------------------------:|--------------------------------:|------------------:|--------------------:|--------------------------:|---------------------:|-----------------------:|-------------------------------:|
|                    23 |                      16 |                              10 |                 0 |                   0 |                         0 |                   23 |                     16 |                             10 |

## Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows |   stage112_expected_jd_day_rows | priority                 | output_path                                                                                                                                                                             | final_output_path                                                                                                                                           |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|--------------------------------:|:-------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| jd2501.DCE    | jd.DCE              | DCE.jd2501  | 2024-09-09           | 2024-12-13         | 2024-09-09                | 2024-12-14              |                    63 |                           14175 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2501_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2501_minute_backtest.csv |
| jd2205.DCE    | jd.DCE              | DCE.jd2205  | 2021-12-13           | 2022-04-06         | 2021-12-13                | 2022-04-07              |                    75 |                           16875 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2205_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2205_minute_backtest.csv |

## Download Status

_无记录_

## Temp Strict Audit

| contract_vt   | download_status   |   download_rows | download_message   | temp_path                                                                                                                                                                               | final_output_path                                                                                                                                           | temp_exists   | strict_ready   |   strict_rows |   expected_jd_day_rows | blocking_reason   | first_bar_datetime   | last_bar_datetime   | sha256   |
|:--------------|:------------------|----------------:|:-------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------|:---------------|--------------:|-----------------------:|:------------------|:---------------------|:--------------------|:---------|
| jd2501.DCE    |                   |               0 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2501_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2501_minute_backtest.csv | False         | False          |             0 |                  14175 | missing_file      |                      |                     |          |
| jd2205.DCE    |                   |               0 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2205_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2205_minute_backtest.csv | False         | False          |             0 |                  16875 | missing_file      |                      |                     |          |

## Publish Manifest

| contract_vt   | download_status   | strict_ready   | action       | temp_path                                                                                                                                                                               | final_output_path                                                                                                                                           | quarantine_path   | published_exists   |   strict_rows | sha256   | blocking_reason   |
|:--------------|:------------------|:---------------|:-------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------|:-------------------|--------------:|:---------|:------------------|
| jd2501.DCE    |                   | False          | no_temp_file | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2501_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2501_minute_backtest.csv |                   | False              |             0 |          | missing_file      |
| jd2205.DCE    |                   | False          | no_temp_file | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage115_jd_atomic_retry_backfill/tmp_downloads/DCE/jd2205_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2205_minute_backtest.csv |                   | False              |             0 |          | missing_file      |

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
