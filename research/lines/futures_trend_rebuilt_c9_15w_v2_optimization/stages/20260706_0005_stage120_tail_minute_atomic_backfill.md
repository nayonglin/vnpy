# Stage120 tail minute atomic backfill

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-06T00:05:47
- 阶段性质：补 6 个非 jd tail minute files；先临时下载、strict gate 验收、再发布；不回测收益、不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考：TqSdk TqBacktest/get_kline_serial 文档、vn.py BarData 语义。
- 我的判断：Stage120 只解决 2026 尾部非 jd 分钟数据准入，不代表策略收益提升；下载成功必须通过 Stage112 strict gate 才能发布。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage120_tail_minute_atomic_backfill.py`
- 新增参数：`STAGE120_ENABLE_DOWNLOAD`、`STAGE120_MAX_SYMBOLS`、`STAGE120_MAX_SECONDS_PER_SYMBOL`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage120_tail_minute_atomic_plan_only`
- download_enabled：`False`
- planned_contract_count：`6`
- downloaded_status_count：`0`
- temp_strict_ready_count：`0`
- published_count：`0`
- quarantined_count：`0`
- published_minute_rows：`0`
- before_remaining_jd_not_ready：`0`
- after_remaining_jd_not_ready：`0`
- after_minute_missing：`6`
- after_strict_failed：`0`
- jd_margin_history_ready：`False`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`tail_minute_files=6`
- remaining_blockers：`tail_minute_files=6, jd_contract_daily_margin_history`
- remaining_tail_minute_files：`SH609.CZCE, SM609.CZCE, au2608.SHFE, cu2607.SHFE, cu2608.SHFE, lh2609.DCE`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Summary

|   before_strict_ready |   before_minute_missing |   before_strict_failed |   before_remaining_jd_not_ready |   published_count |   quarantined_count |   stale_quarantined_count |   after_strict_ready |   after_minute_missing |   after_strict_failed |   after_remaining_jd_not_ready |
|----------------------:|------------------------:|-----------------------:|--------------------------------:|------------------:|--------------------:|--------------------------:|---------------------:|-----------------------:|----------------------:|-------------------------------:|
|                    33 |                       6 |                      0 |                               0 |                 0 |                   0 |                         0 |                   33 |                      6 |                     0 |                              0 |

## Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows |   stage112_expected_jd_day_rows | priority             | output_path                                                                                                                                                                                 | final_output_path                                                                                                                                            |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|--------------------------------:|:---------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| cu2607.SHFE   | cu.SHFE             | SHFE.cu2607 | 2026-05-22           | 2026-06-23         | 2026-05-22                | 2026-06-24              |                    22 |                               0 | P1_tail_contract_gap | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/SHFE/cu2607_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/SHFE/cu2607_minute_backtest.csv |
| au2608.SHFE   | au.SHFE             | SHFE.au2608 | 2026-05-26           | 2026-06-30         | 2026-05-26                | 2026-07-01              |                    25 |                               0 | P1_tail_contract_gap | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/SHFE/au2608_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/SHFE/au2608_minute_backtest.csv |
| lh2609.DCE    | lh.DCE              | DCE.lh2609  | 2026-06-02           | 2026-06-30         | 2026-06-02                | 2026-07-01              |                    20 |                               0 | P1_tail_contract_gap | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/DCE/lh2609_minute_backtest.csv  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/lh2609_minute_backtest.csv  |
| SM609.CZCE    | SM.CZCE             | CZCE.SM609  | 2026-06-04           | 2026-06-30         | 2026-06-04                | 2026-07-01              |                    18 |                               0 | P1_tail_contract_gap | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/CZCE/SM609_minute_backtest.csv  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/CZCE/SM609_minute_backtest.csv  |
| SH609.CZCE    | SH.CZCE             | CZCE.SH609  | 2026-06-17           | 2026-06-30         | 2026-06-17                | 2026-07-01              |                     9 |                               0 | P1_tail_contract_gap | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/CZCE/SH609_minute_backtest.csv  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/CZCE/SH609_minute_backtest.csv  |
| cu2608.SHFE   | cu.SHFE             | SHFE.cu2608 | 2026-06-24           | 2026-06-30         | 2026-06-24                | 2026-07-01              |                     5 |                               0 | P1_tail_contract_gap | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/SHFE/cu2608_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/SHFE/cu2608_minute_backtest.csv |

## Download Status

_无记录_

## Temp Strict Audit

| contract_vt   | download_status   |   download_rows | download_message   | temp_path                                                                                                                                                                                   | final_output_path                                                                                                                                            | temp_exists   | strict_ready   |   strict_rows |   expected_jd_day_rows | blocking_reason   | first_bar_datetime   | last_bar_datetime   | sha256   |
|:--------------|:------------------|----------------:|:-------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------|:---------------|--------------:|-----------------------:|:------------------|:---------------------|:--------------------|:---------|
| cu2607.SHFE   |                   |               0 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/SHFE/cu2607_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/SHFE/cu2607_minute_backtest.csv | False         | False          |             0 |                      0 | missing_file      |                      |                     |          |
| au2608.SHFE   |                   |               0 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/SHFE/au2608_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/SHFE/au2608_minute_backtest.csv | False         | False          |             0 |                      0 | missing_file      |                      |                     |          |
| lh2609.DCE    |                   |               0 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/DCE/lh2609_minute_backtest.csv  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/lh2609_minute_backtest.csv  | False         | False          |             0 |                      0 | missing_file      |                      |                     |          |
| SM609.CZCE    |                   |               0 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/CZCE/SM609_minute_backtest.csv  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/CZCE/SM609_minute_backtest.csv  | False         | False          |             0 |                      0 | missing_file      |                      |                     |          |
| SH609.CZCE    |                   |               0 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/CZCE/SH609_minute_backtest.csv  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/CZCE/SH609_minute_backtest.csv  | False         | False          |             0 |                      0 | missing_file      |                      |                     |          |
| cu2608.SHFE   |                   |               0 |                    | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/SHFE/cu2608_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/SHFE/cu2608_minute_backtest.csv | False         | False          |             0 |                      0 | missing_file      |                      |                     |          |

## Publish Manifest

| contract_vt   | download_status   | strict_ready   | action       | temp_path                                                                                                                                                                                   | final_output_path                                                                                                                                            | old_final_quarantine_path   | temp_quarantine_path   | publish_device_match   | published_exists   |   strict_rows | sha256   | blocking_reason   |
|:--------------|:------------------|:---------------|:-------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------|:-----------------------|:-----------------------|:-------------------|--------------:|:---------|:------------------|
| cu2607.SHFE   |                   | False          | no_temp_file | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/SHFE/cu2607_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/SHFE/cu2607_minute_backtest.csv |                             |                        | False                  | False              |             0 |          | missing_file      |
| au2608.SHFE   |                   | False          | no_temp_file | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/SHFE/au2608_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/SHFE/au2608_minute_backtest.csv |                             |                        | False                  | False              |             0 |          | missing_file      |
| lh2609.DCE    |                   | False          | no_temp_file | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/DCE/lh2609_minute_backtest.csv  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/lh2609_minute_backtest.csv  |                             |                        | False                  | False              |             0 |          | missing_file      |
| SM609.CZCE    |                   | False          | no_temp_file | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/CZCE/SM609_minute_backtest.csv  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/CZCE/SM609_minute_backtest.csv  |                             |                        | False                  | False              |             0 |          | missing_file      |
| SH609.CZCE    |                   | False          | no_temp_file | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/CZCE/SH609_minute_backtest.csv  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/CZCE/SH609_minute_backtest.csv  |                             |                        | False                  | False              |             0 |          | missing_file      |
| cu2608.SHFE   |                   | False          | no_temp_file | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/tmp_downloads/SHFE/cu2608_minute_backtest.csv | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/SHFE/cu2608_minute_backtest.csv |                             |                        | False                  | False              |             0 |          | missing_file      |

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。本阶段只修下载发布口径和补缺失分钟线，不看收益曲线、不调策略参数。
- 运行后：否。atomic publish 只减少脏数据进入回测的概率，不会制造绩效。

## 继续价值反思

- 运行前：有。Stage119 已把 jd 分钟缺口清零，Stage112 仍显示 6 个非 jd tail minute files 阻塞 true ledger。
- 运行后：有。若发布成功可转向 jd 精确逐日保证金；若未成功，应先修数据而不是跑 true ledger。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/rebuilt_c9_v2_stage120_tail_minute_atomic_backfill_report_stage120_tail_minute_atomic_backfill_v1.md`
- plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/rebuilt_c9_v2_stage120_tail_minute_atomic_backfill_plan_stage120_tail_minute_atomic_backfill_v1.csv`
- status：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/rebuilt_c9_v2_stage120_tail_minute_atomic_backfill_download_status_stage120_tail_minute_atomic_backfill_v1.csv`
- temp_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/rebuilt_c9_v2_stage120_tail_minute_atomic_backfill_temp_strict_audit_stage120_tail_minute_atomic_backfill_v1.csv`
- publish_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/rebuilt_c9_v2_stage120_tail_minute_atomic_backfill_publish_manifest_stage120_tail_minute_atomic_backfill_v1.csv`
- before_strict：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/rebuilt_c9_v2_stage120_tail_minute_atomic_backfill_before_strict_manifest_stage120_tail_minute_atomic_backfill_v1.csv`
- after_strict：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/rebuilt_c9_v2_stage120_tail_minute_atomic_backfill_after_strict_manifest_stage120_tail_minute_atomic_backfill_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/rebuilt_c9_v2_stage120_tail_minute_atomic_backfill_summary_stage120_tail_minute_atomic_backfill_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/rebuilt_c9_v2_stage120_tail_minute_atomic_backfill_input_audit_stage120_tail_minute_atomic_backfill_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage120_tail_minute_atomic_backfill/rebuilt_c9_v2_stage120_tail_minute_atomic_backfill_decision_stage120_tail_minute_atomic_backfill_v1.json`
