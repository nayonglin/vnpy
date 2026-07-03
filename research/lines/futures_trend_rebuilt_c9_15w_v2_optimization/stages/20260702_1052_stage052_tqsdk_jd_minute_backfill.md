# Stage052 TqSdk jd 分钟缺口受控补数

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T10:54:57
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
- planned_contract_count：`3`
- download_success_contract_count：`3`
- downloaded_minute_rows：`6525`
- before_missing：`47`
- after_missing：`44`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Backfill Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows | priority                 | output_path                                                                                                                                                 |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|:-------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| jd2604.DCE    | jd.DCE              | DCE.jd2604  | 2026-02-12           | 2026-03-04         | 2026-02-12                | 2026-03-05              |                     9 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2604_minute_backtest.csv |
| jd2602.DCE    | jd.DCE              | DCE.jd2602  | 2025-12-18           | 2025-12-30         | 2025-12-18                | 2025-12-31              |                     9 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2602_minute_backtest.csv |
| jd2608.DCE    | jd.DCE              | DCE.jd2608  | 2026-06-15           | 2026-06-30         | 2026-06-15                | 2026-07-01              |                    11 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2608_minute_backtest.csv |

## Backfill Status

| contract_vt   | tq_symbol   | download_start_datetime   | download_end_datetime   | status     |   rows | first_bar_datetime   | last_bar_datetime   |   elapsed_seconds | output_path                                                                                                                                                 | sha256                                                           | message   |
|:--------------|:------------|:--------------------------|:------------------------|:-----------|-------:|:---------------------|:--------------------|------------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------|:----------|
| jd2604.DCE    | DCE.jd2604  | 2026-02-12 00:00:00       | 2026-03-05 00:00:00     | downloaded |   2025 | 2026-02-12 09:00:00  | 2026-03-04 14:59:00 |             51.58 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2604_minute_backtest.csv | 5309abf977cf4005394a8af0d63de12adaf90c8ea4173b952dcd0afbb07c8516 |           |
| jd2602.DCE    | DCE.jd2602  | 2025-12-18 00:00:00       | 2025-12-31 00:00:00     | downloaded |   2025 | 2025-12-18 09:00:00  | 2025-12-30 14:59:00 |             50.71 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2602_minute_backtest.csv | bff4a18b154f664f7e2a9039f73b18e359dfb3e6fedebff87119c72b0219a552 |           |
| jd2608.DCE    | DCE.jd2608  | 2026-06-15 00:00:00       | 2026-07-01 00:00:00     | downloaded |   2475 | 2026-06-15 09:00:00  | 2026-06-30 14:59:00 |             59.36 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2608_minute_backtest.csv | d1d26a56136b0272026bdd0115aab9ce5cbe5a14a72ab407a79243eab7a106c9 |           |

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
