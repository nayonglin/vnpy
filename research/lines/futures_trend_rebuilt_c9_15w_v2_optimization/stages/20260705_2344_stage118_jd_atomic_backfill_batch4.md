# Stage118 jd atomic retry backfill

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T23:44:17
- 阶段性质：数据补齐流程修正；先临时下载、strict gate 验收、再发布；不回测收益、不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考：TqSdk DataDownloader/TqBacktest 文档、vn.py BarData 语义。
- 我的判断：Stage114 的超时半成品说明“下载器输出目录”和“回测可发现目录”必须隔离；Stage118 只解决数据准入，不代表策略收益提升。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage118_jd_atomic_backfill_batch4.py`
- 新增参数：`STAGE118_ENABLE_DOWNLOAD`、`STAGE118_MAX_SYMBOLS`、`STAGE118_MAX_SECONDS_PER_SYMBOL`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage118_jd_atomic_batch4_success_margin_still_blocked`
- download_enabled：`True`
- planned_contract_count：`2`
- downloaded_status_count：`2`
- temp_strict_ready_count：`2`
- published_count：`2`
- quarantined_count：`0`
- published_minute_rows：`38250`
- before_remaining_jd_not_ready：`4`
- after_remaining_jd_not_ready：`2`
- after_minute_missing：`8`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## 2026-07-05 23:44 全量 Stage112 复核

- 复核脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage112_strict_minute_content_gate.py`
- 复核记录：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260705_2344_stage112_strict_minute_content_gate.md`
- 复核结论：`minute_file_ready_count=31`，`strict_ready_count=31`，`strict_failed_count=0`，`minute_missing_count=8`，`remaining_jd_not_ready_count=2`。
- 发布口径：`jd2105.DCE` 与 `jd2109.DCE` 均为 temp strict-ready 后 `os.replace` 同设备发布；`publish_device_match=True`，`quarantined_count=0`，临时目录无残留文件。
- 额外护栏：Stage118 已修正旧 final 替换顺序，先检查 temp/final 父目录设备一致，再隔离旧 final 和 `os.replace`；本次未触发旧 final 替换。
- 阻塞仍在：`jd_margin_history_ready=False`，所以 `ready_for_true_ledger_replay=False`。

## Summary

|   before_strict_ready |   before_minute_missing |   before_remaining_jd_not_ready |   published_count |   quarantined_count |   stale_quarantined_count |   after_strict_ready |   after_minute_missing |   after_remaining_jd_not_ready |
|----------------------:|------------------------:|--------------------------------:|------------------:|--------------------:|--------------------------:|---------------------:|-----------------------:|-------------------------------:|
|                    29 |                      10 |                               4 |                 2 |                   0 |                         0 |                   31 |                      8 |                              2 |

## Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows |   stage112_expected_jd_day_rows | priority                 | output_path                                                                                                                                                                              | final_output_path                                                                                                                                           |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|--------------------------------:|:-------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| jd2105.DCE    | jd.DCE              | DCE.jd2105  | 2020-12-09           | 2021-04-14         | 2020-12-09                | 2021-04-15              |                    84 |                           18900 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/tmp_downloads/DCE/jd2105_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2105_minute_backtest.csv |
| jd2109.DCE    | jd.DCE              | DCE.jd2109  | 2021-04-15           | 2021-08-18         | 2021-04-15                | 2021-08-19              |                    86 |                           19350 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/tmp_downloads/DCE/jd2109_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2109_minute_backtest.csv |

## Download Status

| contract_vt   | tq_symbol   | download_start_datetime   | download_end_datetime   | status     |   rows | first_bar_datetime   | last_bar_datetime   |   elapsed_seconds | output_path                                                                                                                                                                              | sha256                                                           | message   |
|:--------------|:------------|:--------------------------|:------------------------|:-----------|-------:|:---------------------|:--------------------|------------------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------|:----------|
| jd2105.DCE    | DCE.jd2105  | 2020-12-09 00:00:00       | 2021-04-15 00:00:00     | downloaded |  18900 | 2020-12-09 09:00:00  | 2021-04-14 14:59:00 |            325.64 | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/tmp_downloads/DCE/jd2105_minute_backtest.csv | c4b92156c88e3e3b3e8f1f84564ff36484bdcda7f0c3a2c942398dba3fcafc9b |           |
| jd2109.DCE    | DCE.jd2109  | 2021-04-15 00:00:00       | 2021-08-19 00:00:00     | downloaded |  19350 | 2021-04-15 09:00:00  | 2021-08-18 14:59:00 |            328.81 | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/tmp_downloads/DCE/jd2109_minute_backtest.csv | e6b1bd9730eed5ae57f2f83a10c55451bd2b513716b18249b01610f6ab0d4ebb |           |

## Temp Strict Audit

| contract_vt   | download_status   |   download_rows | download_message   | temp_path                                                                                                                                                                                | final_output_path                                                                                                                                           | temp_exists   | strict_ready   |   strict_rows |   expected_jd_day_rows | blocking_reason   | first_bar_datetime   | last_bar_datetime   | sha256                                                           |
|:--------------|:------------------|----------------:|:-------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------|:---------------|--------------:|-----------------------:|:------------------|:---------------------|:--------------------|:-----------------------------------------------------------------|
| jd2105.DCE    | downloaded        |           18900 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/tmp_downloads/DCE/jd2105_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2105_minute_backtest.csv | True          | True           |         18900 |                  18900 |                   | 2020-12-09 09:00:00  | 2021-04-14 14:59:00 | c4b92156c88e3e3b3e8f1f84564ff36484bdcda7f0c3a2c942398dba3fcafc9b |
| jd2109.DCE    | downloaded        |           19350 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/tmp_downloads/DCE/jd2109_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2109_minute_backtest.csv | True          | True           |         19350 |                  19350 |                   | 2021-04-15 09:00:00  | 2021-08-18 14:59:00 | e6b1bd9730eed5ae57f2f83a10c55451bd2b513716b18249b01610f6ab0d4ebb |

## Publish Manifest

| contract_vt   | download_status   | strict_ready   | action    | temp_path                                                                                                                                                                                | final_output_path                                                                                                                                           | old_final_quarantine_path   | temp_quarantine_path   | publish_device_match   | published_exists   |   strict_rows | sha256                                                           | blocking_reason   |
|:--------------|:------------------|:---------------|:----------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------|:-----------------------|:-----------------------|:-------------------|--------------:|:-----------------------------------------------------------------|:------------------|
| jd2105.DCE    | downloaded        | True           | published | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/tmp_downloads/DCE/jd2105_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2105_minute_backtest.csv |                             |                        | True                   | True               |         18900 | c4b92156c88e3e3b3e8f1f84564ff36484bdcda7f0c3a2c942398dba3fcafc9b |                   |
| jd2109.DCE    | downloaded        | True           | published | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/tmp_downloads/DCE/jd2109_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2109_minute_backtest.csv |                             |                        | True                   | True               |         19350 | e6b1bd9730eed5ae57f2f83a10c55451bd2b513716b18249b01610f6ab0d4ebb |                   |

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。本阶段只修下载发布口径和补缺失分钟线，不看收益曲线、不调策略参数。
- 运行后：否。atomic publish 只减少脏数据进入回测的概率，不会制造绩效。

## 继续价值反思

- 运行前：有。Stage114 证明超时半成品会污染存在性口径，必须先把下载流程改成严格验收发布。
- 运行后：有。若发布成功可继续补剩余 jd；若未成功，应继续降低批量或延长单合约超时，而不是跑 true ledger。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/rebuilt_c9_v2_stage118_jd_atomic_backfill_batch4_report_stage118_jd_atomic_backfill_batch4_v1.md`
- plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/rebuilt_c9_v2_stage118_jd_atomic_backfill_batch4_plan_stage118_jd_atomic_backfill_batch4_v1.csv`
- status：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/rebuilt_c9_v2_stage118_jd_atomic_backfill_batch4_download_status_stage118_jd_atomic_backfill_batch4_v1.csv`
- temp_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/rebuilt_c9_v2_stage118_jd_atomic_backfill_batch4_temp_strict_audit_stage118_jd_atomic_backfill_batch4_v1.csv`
- publish_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/rebuilt_c9_v2_stage118_jd_atomic_backfill_batch4_publish_manifest_stage118_jd_atomic_backfill_batch4_v1.csv`
- before_strict：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/rebuilt_c9_v2_stage118_jd_atomic_backfill_batch4_before_strict_manifest_stage118_jd_atomic_backfill_batch4_v1.csv`
- after_strict：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/rebuilt_c9_v2_stage118_jd_atomic_backfill_batch4_after_strict_manifest_stage118_jd_atomic_backfill_batch4_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/rebuilt_c9_v2_stage118_jd_atomic_backfill_batch4_summary_stage118_jd_atomic_backfill_batch4_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/rebuilt_c9_v2_stage118_jd_atomic_backfill_batch4_input_audit_stage118_jd_atomic_backfill_batch4_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage118_jd_atomic_backfill_batch4/rebuilt_c9_v2_stage118_jd_atomic_backfill_batch4_decision_stage118_jd_atomic_backfill_batch4_v1.json`
