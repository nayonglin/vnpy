# Stage087 jd minute backfill batch3

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T17:34:39
- 阶段性质：数据补齐；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 外部趋势跟随资料与 GitHub 示例支持分散/独立收益腿/风险预算方向；本阶段选择 data-first 继续补 Stage208/xsmom 真承载数据。
- 我的判断：下载分钟线只是在清阻塞，不代表策略收益改进；保证金历史未补前仍不能跑 true ledger replay。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage087_jd_minute_backfill_batch3.py`
- 新增参数：`STAGE087_ENABLE_DOWNLOAD`、`STAGE087_MAX_SYMBOLS`、`STAGE087_MAX_SECONDS_PER_SYMBOL`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage087_jd_minute_backfill_batch3_success_margin_still_blocked`
- download_enabled：`True`
- planned_contract_count：`6`
- download_success_contract_count：`6`
- downloaded_minute_rows：`29250`
- before_missing：`34`
- after_missing：`28`
- remaining_jd_missing：`22`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Backfill Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows | priority                 | output_path                                                                                                                                                 |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|:-------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| jd2509.DCE    | jd.DCE              | DCE.jd2509  | 2025-07-15           | 2025-08-12         | 2025-07-15                | 2025-08-13              |                    21 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2509_minute_backtest.csv |
| jd2506.DCE    | jd.DCE              | DCE.jd2506  | 2025-04-16           | 2025-05-19         | 2025-04-16                | 2025-05-20              |                    21 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2506_minute_backtest.csv |
| jd2502.DCE    | jd.DCE              | DCE.jd2502  | 2024-12-16           | 2025-01-14         | 2024-12-16                | 2025-01-15              |                    21 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2502_minute_backtest.csv |
| jd2511.DCE    | jd.DCE              | DCE.jd2511  | 2025-09-11           | 2025-10-20         | 2025-09-11                | 2025-10-21              |                    22 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2511_minute_backtest.csv |
| jd2010.DCE    | jd.DCE              | DCE.jd2010  | 2020-08-19           | 2020-09-17         | 2020-08-19                | 2020-09-18              |                    22 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2010_minute_backtest.csv |
| jd2606.DCE    | jd.DCE              | DCE.jd2606  | 2026-04-09           | 2026-05-14         | 2026-04-09                | 2026-05-15              |                    23 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2606_minute_backtest.csv |

## Backfill Status

| contract_vt   | tq_symbol   | download_start_datetime   | download_end_datetime   | status     |   rows | first_bar_datetime   | last_bar_datetime   |   elapsed_seconds | output_path                                                                                                                                                 | sha256                                                           | message   |
|:--------------|:------------|:--------------------------|:------------------------|:-----------|-------:|:---------------------|:--------------------|------------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------|:----------|
| jd2509.DCE    | DCE.jd2509  | 2025-07-15 00:00:00       | 2025-08-13 00:00:00     | downloaded |   4725 | 2025-07-15 09:00:00  | 2025-08-12 14:59:00 |             88.21 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2509_minute_backtest.csv | a911d6f4f4e5ab40f08ab80e331c8f1b26bfdcaf549a279e0857e69bca39c088 |           |
| jd2506.DCE    | DCE.jd2506  | 2025-04-16 00:00:00       | 2025-05-20 00:00:00     | downloaded |   4725 | 2025-04-16 09:00:00  | 2025-05-19 14:59:00 |             87.28 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2506_minute_backtest.csv | d0a3945eac0161f3b30312dd408ddfa56549c614398b868a8a5e7cdaf11de6d0 |           |
| jd2502.DCE    | DCE.jd2502  | 2024-12-16 00:00:00       | 2025-01-15 00:00:00     | downloaded |   4725 | 2024-12-16 09:00:00  | 2025-01-14 14:59:00 |             87.96 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2502_minute_backtest.csv | 778a1bb68859b76b3d304f5fd00ff83ab508404785da3c01eadb1ce0b4aa430c |           |
| jd2511.DCE    | DCE.jd2511  | 2025-09-11 00:00:00       | 2025-10-21 00:00:00     | downloaded |   4950 | 2025-09-11 09:00:00  | 2025-10-20 14:59:00 |             91.15 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2511_minute_backtest.csv | f3542939cc06bd55556103f3b923c97de7c393bc9fd774acbed2b92f598f988d |           |
| jd2010.DCE    | DCE.jd2010  | 2020-08-19 00:00:00       | 2020-09-18 00:00:00     | downloaded |   4950 | 2020-08-19 09:00:00  | 2020-09-17 14:59:00 |             90.85 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2010_minute_backtest.csv | b8adf836237155e994ecd6668e0d48f9336bc4f8c2c7ef758654b4d9e9f51e88 |           |
| jd2606.DCE    | DCE.jd2606  | 2026-04-09 00:00:00       | 2026-05-15 00:00:00     | downloaded |   5175 | 2026-04-09 09:00:00  | 2026-05-14 14:59:00 |             96.54 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2606_minute_backtest.csv | 077cd176459ee7f1a3aeca61e0bfcc545c2ed31e621510d44dcd928571f9b66c |           |

## Remaining Missing

| contract_vt   | product_vt_symbol   | minute_file_ready   | minute_file   |
|:--------------|:--------------------|:--------------------|:--------------|
| jd2005.DCE    | jd.DCE              | False               |               |
| jd2006.DCE    | jd.DCE              | False               |               |
| jd2009.DCE    | jd.DCE              | False               |               |
| jd2101.DCE    | jd.DCE              | False               |               |
| jd2105.DCE    | jd.DCE              | False               |               |
| jd2109.DCE    | jd.DCE              | False               |               |
| jd2201.DCE    | jd.DCE              | False               |               |
| jd2205.DCE    | jd.DCE              | False               |               |
| jd2209.DCE    | jd.DCE              | False               |               |
| jd2301.DCE    | jd.DCE              | False               |               |
| jd2305.DCE    | jd.DCE              | False               |               |
| jd2309.DCE    | jd.DCE              | False               |               |
| jd2401.DCE    | jd.DCE              | False               |               |
| jd2403.DCE    | jd.DCE              | False               |               |
| jd2405.DCE    | jd.DCE              | False               |               |
| jd2409.DCE    | jd.DCE              | False               |               |
| jd2501.DCE    | jd.DCE              | False               |               |
| jd2505.DCE    | jd.DCE              | False               |               |
| jd2508.DCE    | jd.DCE              | False               |               |
| jd2601.DCE    | jd.DCE              | False               |               |
| jd2603.DCE    | jd.DCE              | False               |               |
| jd2605.DCE    | jd.DCE              | False               |               |
| SH609.CZCE    | SH.CZCE             | False               |               |
| SM609.CZCE    | SM.CZCE             | False               |               |
| au2608.SHFE   | au.SHFE             | False               |               |
| cu2607.SHFE   | cu.SHFE             | False               |               |
| cu2608.SHFE   | cu.SHFE             | False               |               |
| lh2609.DCE    | lh.DCE              | False               |               |

## 独立 Agent 评估

- 评估 agent：`019f31a1-b601-7892-8448-445cda1c55c9`。
- 结论：未发现严重问题；Stage087 窄结论成立；置信度 `0.86`。
- 复核结果：`download_success_contract_count=6`、`downloaded_minute_rows=29,250`、`before_missing=34`、`after_missing=28`、`remaining_jd_missing=22` 均复算一致；6 个文件 `sha256` 与 `file_manifest/status/input_audit` 一致，且均可被 Stage049 的 `downloaded_futures/*/*/*minute_backtest.csv` 索引发现。
- 中等风险：下载 CSV 的 `volume` 全部为 `0`，且所有行 `high==low`，只能证明文件覆盖减少，不能过度解释为高质量 OHLCV/成交窗口证据；后续 true ledger 若依赖成交量或 intrabar high/low，需要单独数据质量闸门。
- 低级风险：当前 CSV 内没有 `source_file_hash` 列，hash 存在于 `file_manifest/input_audit`；后续应明确文件级 `sha256` 即 source hash。

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。本阶段只补 P0 鸡蛋分钟缺口，不按收益表现选择合约或参数。
- 运行后：否。下载成功只降低数据阻塞；保证金历史缺失前仍禁止 true ledger replay。

## 继续价值反思

- 运行前：有。Stage086 已排除低价值 stop/retry/预算锁路线，Stage208 真承载是更结构性的下一路。
- 运行后：有，但下一步必须继续补剩余 jd 分钟线并寻找逐日保证金；不能跳过数据口径硬跑。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage087_jd_minute_backfill_batch3/rebuilt_c9_v2_stage087_jd_minute_backfill_batch3_report_stage087_jd_minute_backfill_batch3_v1.md`
- backfill_plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage087_jd_minute_backfill_batch3/rebuilt_c9_v2_stage087_jd_minute_backfill_batch3_backfill_plan_stage087_jd_minute_backfill_batch3_v1.csv`
- backfill_status：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage087_jd_minute_backfill_batch3/rebuilt_c9_v2_stage087_jd_minute_backfill_batch3_backfill_status_stage087_jd_minute_backfill_batch3_v1.csv`
- file_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage087_jd_minute_backfill_batch3/rebuilt_c9_v2_stage087_jd_minute_backfill_batch3_file_manifest_stage087_jd_minute_backfill_batch3_v1.csv`
- before_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage087_jd_minute_backfill_batch3/rebuilt_c9_v2_stage087_jd_minute_backfill_batch3_before_minute_coverage_stage087_jd_minute_backfill_batch3_v1.csv`
- after_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage087_jd_minute_backfill_batch3/rebuilt_c9_v2_stage087_jd_minute_backfill_batch3_after_minute_coverage_stage087_jd_minute_backfill_batch3_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage087_jd_minute_backfill_batch3/rebuilt_c9_v2_stage087_jd_minute_backfill_batch3_input_audit_stage087_jd_minute_backfill_batch3_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage087_jd_minute_backfill_batch3/rebuilt_c9_v2_stage087_jd_minute_backfill_batch3_decision_stage087_jd_minute_backfill_batch3_v1.json`
