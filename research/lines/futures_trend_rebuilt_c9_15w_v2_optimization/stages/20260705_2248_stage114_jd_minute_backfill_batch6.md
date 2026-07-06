# Stage114 jd minute backfill batch6

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T22:48:15
- 阶段性质：数据补齐；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 外部趋势跟随资料与 GitHub 示例支持分散/独立收益腿/风险预算方向；本阶段选择 data-first 继续补 Stage208/xsmom 真承载数据。
- 我的判断：下载分钟线只是在清阻塞，不代表策略收益改进；保证金历史未补前仍不能跑 true ledger replay。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage114_jd_minute_backfill_batch6.py`
- 新增参数：`STAGE114_ENABLE_DOWNLOAD`、`STAGE114_MAX_SYMBOLS`、`STAGE114_MAX_SECONDS_PER_SYMBOL`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage114_jd_minute_backfill_batch6_partial_success_margin_still_blocked`
- download_enabled：`True`
- planned_contract_count：`4`
- download_success_contract_count：`2`
- downloaded_minute_rows：`55571`
- before_missing：`18`
- after_missing：`14`
- remaining_jd_missing：`8`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## 2026-07-05 22:50 严格门禁复核与半成品隔离

- 复核结论：Stage114 wrapper 的 `after_missing=14/remaining_jd_missing=8` 是“文件存在”口径，不是有效数据口径；不能作为后续 true ledger replay 的准入依据。
- 有效新增：`jd2505.DCE`、`jd2005.DCE` 两个文件在 Stage112 strict gate 下通过。
- 隔离半成品：`jd2501.DCE`、`jd2205.DCE` 均为 `timeout_after_240s` 后留下的部分 CSV，已从 discoverable 数据目录移动到 `outputs/stage114_jd_minute_backfill_batch6/quarantine_timeout_partial/`，保留证据但不允许被回测脚本误读。
- 隔离后 Stage112 严格门禁：`minute_file_ready_count=23`，`strict_ready_count=23`，`strict_failed_count=0`，`minute_missing_count=16`，`remaining_jd_not_ready_count=10`，`ready_for_true_ledger_replay=False`。
- 当前权威口径：以 `20260705_2250_stage112_strict_minute_content_gate.md` 为准；Stage114 原始 `downloaded_minute_rows=55571` 包含两个 timeout 半成品的行数，只能用于下载诊断，不能用于数据 ready 统计。

## 独立 Agent 评估

- 评估 agent：`019f32c3-1bbf-7f21-b651-a5a0c4395924`
- 评估时间：2026-07-05 22:54 左右
- 结论：Stage114 原始记录和 22:50 追加修正基本准确；隔离动作合理；没有看到 `jd2501/jd2205` 半成品留在 Stage052 分钟线可发现路径。
- 置信度：整体约 `0.90+`；Stage112 当前结果可复算，`rows=39/minute_file_ready=23/minute_missing=16/strict_ready=23/strict_failed=0/remaining_jd_not_ready=10`。
- 高风险发现：Stage049/109 true-ledger readiness 仍可能主要按 `*_minute_backtest.csv` 文件存在扫描；未来分钟和保证金补齐前，必须把 Stage112 strict 全通过作为硬前置，或改 Stage049/109 只消费 strict-ready manifest。
- 中风险发现：旧下载器会把 timeout partial 写入最终可发现目录，这是 Stage114 污染根因；后续补数必须走 Stage115 atomic 流程，先临时目录下载、strict audit、通过才 publish。
- 继续建议：可以继续下一批补数，但不得继续使用 Stage114/110/113 这种旧直写模式；Stage114 的 after_coverage 历史 CSV 只能作为诊断旧口径，不再作为准入依据。

## Backfill Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows | priority                 | output_path                                                                                                                                                 |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|:-------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| jd2505.DCE    | jd.DCE              | DCE.jd2505  | 2025-01-15           | 2025-04-15         | 2025-01-15                | 2025-04-16              |                    58 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2505_minute_backtest.csv |
| jd2501.DCE    | jd.DCE              | DCE.jd2501  | 2024-09-09           | 2024-12-13         | 2024-09-09                | 2024-12-14              |                    63 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2501_minute_backtest.csv |
| jd2005.DCE    | jd.DCE              | DCE.jd2005  | 2020-01-02           | 2020-04-08         | 2020-01-02                | 2020-04-09              |                    63 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2005_minute_backtest.csv |
| jd2205.DCE    | jd.DCE              | DCE.jd2205  | 2021-12-13           | 2022-04-06         | 2021-12-13                | 2022-04-07              |                    75 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2205_minute_backtest.csv |

## Backfill Status

| contract_vt   | tq_symbol   | download_start_datetime   | download_end_datetime   | status     |   rows | first_bar_datetime   | last_bar_datetime   |   elapsed_seconds | output_path                                                                                                                                                 | sha256                                                           | message            |
|:--------------|:------------|:--------------------------|:------------------------|:-----------|-------:|:---------------------|:--------------------|------------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------|:-------------------|
| jd2505.DCE    | DCE.jd2505  | 2025-01-15 00:00:00       | 2025-04-16 00:00:00     | downloaded |  13050 | 2025-01-15 09:00:00  | 2025-04-15 14:59:00 |            224.77 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2505_minute_backtest.csv | 0c1fb96859fea2ead913ba6bb8af0ee1946276bfe8537b119b25e88fce030a3b |                    |
| jd2501.DCE    | DCE.jd2501  | 2024-09-09 00:00:00       | 2024-12-14 00:00:00     | timeout    |  14157 | 2024-09-09 09:00:00  | 2024-12-13 14:41:00 |            240.13 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2501_minute_backtest.csv | 9a6b6a10373d4ab2c12a9fff2ad136c66211c4a3b2899660e01baa7a4335c9ae | timeout_after_240s |
| jd2005.DCE    | DCE.jd2005  | 2020-01-02 00:00:00       | 2020-04-09 00:00:00     | downloaded |  14175 | 2020-01-02 09:00:00  | 2020-04-08 14:59:00 |            240.03 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2005_minute_backtest.csv | 06dc8e4feaaf2c48df0d54207049252e3cba26047d94caad7a63c8c7b7661b18 |                    |
| jd2205.DCE    | DCE.jd2205  | 2021-12-13 00:00:00       | 2022-04-07 00:00:00     | timeout    |  14189 | 2021-12-13 09:00:00  | 2022-03-18 09:13:00 |            240.4  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2205_minute_backtest.csv | ade8a4d7e42025f369a9553c2c340ea3eab4500a6369299267bcbb40dd5e17fe | timeout_after_240s |

## Remaining Missing

| contract_vt   | product_vt_symbol   | minute_file_ready   | minute_file   |
|:--------------|:--------------------|:--------------------|:--------------|
| jd2105.DCE    | jd.DCE              | False               |               |
| jd2109.DCE    | jd.DCE              | False               |               |
| jd2201.DCE    | jd.DCE              | False               |               |
| jd2209.DCE    | jd.DCE              | False               |               |
| jd2301.DCE    | jd.DCE              | False               |               |
| jd2305.DCE    | jd.DCE              | False               |               |
| jd2309.DCE    | jd.DCE              | False               |               |
| jd2409.DCE    | jd.DCE              | False               |               |
| SH609.CZCE    | SH.CZCE             | False               |               |
| SM609.CZCE    | SM.CZCE             | False               |               |
| au2608.SHFE   | au.SHFE             | False               |               |
| cu2607.SHFE   | cu.SHFE             | False               |               |
| cu2608.SHFE   | cu.SHFE             | False               |               |
| lh2609.DCE    | lh.DCE              | False               |               |

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。本阶段只补 P0 鸡蛋分钟缺口，不按收益表现选择合约或参数。
- 运行后：否。下载成功只降低数据阻塞；保证金历史缺失前仍禁止 true ledger replay。

## 继续价值反思

- 运行前：有。Stage086 已排除低价值 stop/retry/预算锁路线，Stage208 真承载是更结构性的下一路。
- 运行后：有，但下一步必须继续补剩余 jd 分钟线并寻找逐日保证金；不能跳过数据口径硬跑。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage114_jd_minute_backfill_batch6/rebuilt_c9_v2_stage114_jd_minute_backfill_batch6_report_stage114_jd_minute_backfill_batch6_v1.md`
- backfill_plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage114_jd_minute_backfill_batch6/rebuilt_c9_v2_stage114_jd_minute_backfill_batch6_backfill_plan_stage114_jd_minute_backfill_batch6_v1.csv`
- backfill_status：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage114_jd_minute_backfill_batch6/rebuilt_c9_v2_stage114_jd_minute_backfill_batch6_backfill_status_stage114_jd_minute_backfill_batch6_v1.csv`
- file_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage114_jd_minute_backfill_batch6/rebuilt_c9_v2_stage114_jd_minute_backfill_batch6_file_manifest_stage114_jd_minute_backfill_batch6_v1.csv`
- before_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage114_jd_minute_backfill_batch6/rebuilt_c9_v2_stage114_jd_minute_backfill_batch6_before_minute_coverage_stage114_jd_minute_backfill_batch6_v1.csv`
- after_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage114_jd_minute_backfill_batch6/rebuilt_c9_v2_stage114_jd_minute_backfill_batch6_after_minute_coverage_stage114_jd_minute_backfill_batch6_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage114_jd_minute_backfill_batch6/rebuilt_c9_v2_stage114_jd_minute_backfill_batch6_input_audit_stage114_jd_minute_backfill_batch6_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage114_jd_minute_backfill_batch6/rebuilt_c9_v2_stage114_jd_minute_backfill_batch6_decision_stage114_jd_minute_backfill_batch6_v1.json`
