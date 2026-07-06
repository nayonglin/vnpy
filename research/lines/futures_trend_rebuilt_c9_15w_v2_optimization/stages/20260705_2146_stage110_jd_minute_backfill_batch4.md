# Stage110 jd minute backfill batch4

- 状态：dry-run 预检记录，已被正式下载记录 `20260705_2157_stage110_jd_minute_backfill_batch4.md` 取代；本文件仅保留当时 plan-only 验证，不作为最终 Stage110 结论。

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T21:46:41
- 阶段性质：数据补齐；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 外部趋势跟随资料与 GitHub 示例支持分散/独立收益腿/风险预算方向；本阶段选择 data-first 继续补 Stage208/xsmom 真承载数据。
- 我的判断：下载分钟线只是在清阻塞，不代表策略收益改进；保证金历史未补前仍不能跑 true ledger replay。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage110_jd_minute_backfill_batch4.py`
- 新增参数：`STAGE110_ENABLE_DOWNLOAD`、`STAGE110_MAX_SYMBOLS`、`STAGE110_MAX_SECONDS_PER_SYMBOL`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage110_jd_minute_backfill_batch4_dry_plan_only`
- download_enabled：`False`
- planned_contract_count：`6`
- download_success_contract_count：`0`
- downloaded_minute_rows：`0`
- before_missing：`28`
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
| jd2601.DCE    | jd.DCE              | DCE.jd2601  | 2025-11-17           | 2025-12-17         | 2025-11-17                | 2025-12-18              |                    23 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2601_minute_backtest.csv |
| jd2605.DCE    | jd.DCE              | DCE.jd2605  | 2026-03-05           | 2026-04-08         | 2026-03-05                | 2026-04-09              |                    24 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2605_minute_backtest.csv |
| jd2508.DCE    | jd.DCE              | DCE.jd2508  | 2025-06-11           | 2025-07-14         | 2025-06-11                | 2025-07-15              |                    24 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2508_minute_backtest.csv |
| jd2403.DCE    | jd.DCE              | DCE.jd2403  | 2024-01-10           | 2024-02-20         | 2024-01-10                | 2024-02-21              |                    24 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2403_minute_backtest.csv |
| jd2603.DCE    | jd.DCE              | DCE.jd2603  | 2025-12-31           | 2026-02-11         | 2025-12-31                | 2026-02-12              |                    29 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2603_minute_backtest.csv |
| jd2006.DCE    | jd.DCE              | DCE.jd2006  | 2020-04-09           | 2020-05-27         | 2020-04-09                | 2020-05-28              |                    32 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2006_minute_backtest.csv |

## Backfill Status

_无记录_

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

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。本阶段只补 P0 鸡蛋分钟缺口，不按收益表现选择合约或参数。
- 运行后：否。下载成功只降低数据阻塞；保证金历史缺失前仍禁止 true ledger replay。

## 继续价值反思

- 运行前：有。Stage086 已排除低价值 stop/retry/预算锁路线，Stage208 真承载是更结构性的下一路。
- 运行后：有，但下一步必须继续补剩余 jd 分钟线并寻找逐日保证金；不能跳过数据口径硬跑。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_report_stage110_jd_minute_backfill_batch4_v1.md`
- backfill_plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_backfill_plan_stage110_jd_minute_backfill_batch4_v1.csv`
- backfill_status：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_backfill_status_stage110_jd_minute_backfill_batch4_v1.csv`
- file_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_file_manifest_stage110_jd_minute_backfill_batch4_v1.csv`
- before_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_before_minute_coverage_stage110_jd_minute_backfill_batch4_v1.csv`
- after_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_after_minute_coverage_stage110_jd_minute_backfill_batch4_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_input_audit_stage110_jd_minute_backfill_batch4_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_decision_stage110_jd_minute_backfill_batch4_v1.json`
