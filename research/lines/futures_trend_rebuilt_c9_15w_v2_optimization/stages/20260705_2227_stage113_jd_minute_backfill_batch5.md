# Stage113 jd minute backfill batch5

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T22:27:23
- 阶段性质：数据补齐；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 外部趋势跟随资料与 GitHub 示例支持分散/独立收益腿/风险预算方向；本阶段选择 data-first 继续补 Stage208/xsmom 真承载数据。
- 我的判断：下载分钟线只是在清阻塞，不代表策略收益改进；保证金历史未补前仍不能跑 true ledger replay。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage113_jd_minute_backfill_batch5.py`
- 新增参数：`STAGE113_ENABLE_DOWNLOAD`、`STAGE113_MAX_SYMBOLS`、`STAGE113_MAX_SECONDS_PER_SYMBOL`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage113_jd_minute_backfill_batch5_success_margin_still_blocked`
- download_enabled：`True`
- planned_contract_count：`4`
- download_success_contract_count：`4`
- downloaded_minute_rows：`35325`
- before_missing：`22`
- after_missing：`18`
- remaining_jd_missing：`12`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Backfill Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows | priority                 | output_path                                                                                                                                                 |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|:-------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| jd2405.DCE    | jd.DCE              | DCE.jd2405  | 2024-02-21           | 2024-04-09         | 2024-02-21                | 2024-04-10              |                    33 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2405_minute_backtest.csv |
| jd2101.DCE    | jd.DCE              | DCE.jd2101  | 2020-10-22           | 2020-12-08         | 2020-10-22                | 2020-12-09              |                    34 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2101_minute_backtest.csv |
| jd2401.DCE    | jd.DCE              | DCE.jd2401  | 2023-10-13           | 2023-12-14         | 2023-10-13                | 2023-12-15              |                    45 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2401_minute_backtest.csv |
| jd2009.DCE    | jd.DCE              | DCE.jd2009  | 2020-06-15           | 2020-08-18         | 2020-06-15                | 2020-08-19              |                    45 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2009_minute_backtest.csv |

## Backfill Status

| contract_vt   | tq_symbol   | download_start_datetime   | download_end_datetime   | status     |   rows | first_bar_datetime   | last_bar_datetime   |   elapsed_seconds | output_path                                                                                                                                                 | sha256                                                           | message   |
|:--------------|:------------|:--------------------------|:------------------------|:-----------|-------:|:---------------------|:--------------------|------------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------|:----------|
| jd2405.DCE    | DCE.jd2405  | 2024-02-21 00:00:00       | 2024-04-10 00:00:00     | downloaded |   7425 | 2024-02-21 09:00:00  | 2024-04-09 14:59:00 |            132.74 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2405_minute_backtest.csv | d4b1df4cb4fca4bc4d776ce9031b167842156bb0ee2e3e778603283969b3a97f |           |
| jd2101.DCE    | DCE.jd2101  | 2020-10-22 00:00:00       | 2020-12-09 00:00:00     | downloaded |   7650 | 2020-10-22 09:00:00  | 2020-12-08 14:59:00 |            135.28 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2101_minute_backtest.csv | 68a469c1217ee34b09fdc277775f3f7fb0f4ce76e8a548f91d142cd1b4c2b4ec |           |
| jd2401.DCE    | DCE.jd2401  | 2023-10-13 00:00:00       | 2023-12-15 00:00:00     | downloaded |  10125 | 2023-10-13 09:00:00  | 2023-12-14 14:59:00 |            176.26 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2401_minute_backtest.csv | 7b4655de5006f66e6471791900285707bbca84c153f14f2418198b5a7e103339 |           |
| jd2009.DCE    | DCE.jd2009  | 2020-06-15 00:00:00       | 2020-08-19 00:00:00     | downloaded |  10125 | 2020-06-15 09:00:00  | 2020-08-18 14:59:00 |            175.57 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2009_minute_backtest.csv | 3b13bf8136ae9937a45377a657858734bea675bbc7dc78438c13cbc2828a511c |           |

## 本地内容验收

- 4 个新增 CSV 均存在，`sha256` 已记录。
- OHLC 空值：`0`。
- `vt_symbol + bar_datetime` 重复：`0`。
- 时间窗验收：
  - `jd2405.DCE`：`7,425` 行，`2024-02-21 09:00:00` 至 `2024-04-09 14:59:00`。
  - `jd2101.DCE`：`7,650` 行，`2020-10-22 09:00:00` 至 `2020-12-08 14:59:00`。
  - `jd2401.DCE`：`10,125` 行，`2023-10-13 09:00:00` 至 `2023-12-14 14:59:00`。
  - `jd2009.DCE`：`10,125` 行，`2020-06-15 09:00:00` 至 `2020-08-18 14:59:00`。
- Stage112 strict gate 复验：新增后 `minute_file_ready_count=21`，`strict_ready_count=21`，`strict_failed_count=0`，`minute_missing_count=18`，`remaining_jd_not_ready_count=12`，`ready_for_true_ledger_replay=false`。

## Remaining Missing

| contract_vt   | product_vt_symbol   | minute_file_ready   | minute_file   |
|:--------------|:--------------------|:--------------------|:--------------|
| jd2005.DCE    | jd.DCE              | False               |               |
| jd2105.DCE    | jd.DCE              | False               |               |
| jd2109.DCE    | jd.DCE              | False               |               |
| jd2201.DCE    | jd.DCE              | False               |               |
| jd2205.DCE    | jd.DCE              | False               |               |
| jd2209.DCE    | jd.DCE              | False               |               |
| jd2301.DCE    | jd.DCE              | False               |               |
| jd2305.DCE    | jd.DCE              | False               |               |
| jd2309.DCE    | jd.DCE              | False               |               |
| jd2409.DCE    | jd.DCE              | False               |               |
| jd2501.DCE    | jd.DCE              | False               |               |
| jd2505.DCE    | jd.DCE              | False               |               |
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

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage113_jd_minute_backfill_batch5/rebuilt_c9_v2_stage113_jd_minute_backfill_batch5_report_stage113_jd_minute_backfill_batch5_v1.md`
- backfill_plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage113_jd_minute_backfill_batch5/rebuilt_c9_v2_stage113_jd_minute_backfill_batch5_backfill_plan_stage113_jd_minute_backfill_batch5_v1.csv`
- backfill_status：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage113_jd_minute_backfill_batch5/rebuilt_c9_v2_stage113_jd_minute_backfill_batch5_backfill_status_stage113_jd_minute_backfill_batch5_v1.csv`
- file_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage113_jd_minute_backfill_batch5/rebuilt_c9_v2_stage113_jd_minute_backfill_batch5_file_manifest_stage113_jd_minute_backfill_batch5_v1.csv`
- before_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage113_jd_minute_backfill_batch5/rebuilt_c9_v2_stage113_jd_minute_backfill_batch5_before_minute_coverage_stage113_jd_minute_backfill_batch5_v1.csv`
- after_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage113_jd_minute_backfill_batch5/rebuilt_c9_v2_stage113_jd_minute_backfill_batch5_after_minute_coverage_stage113_jd_minute_backfill_batch5_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage113_jd_minute_backfill_batch5/rebuilt_c9_v2_stage113_jd_minute_backfill_batch5_input_audit_stage113_jd_minute_backfill_batch5_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage113_jd_minute_backfill_batch5/rebuilt_c9_v2_stage113_jd_minute_backfill_batch5_decision_stage113_jd_minute_backfill_batch5_v1.json`

## 独立 Agent 评估

- 评估 agent：Nash（`019f32ae-5e5e-70b1-a81d-4b4ccb63c9da`）
- 置信度：`0.94`
- 结论：Stage113 是 jd P0 分钟数据补齐阶段，不是策略回测；未发现改策略、跑 true engine、连接 CTP、调用订单或邮件的证据。
- 高风险 bug：未发现。
- 中风险 bug：未发现。
- 复算一致项：
  - plan 为 `jd2405.DCE`、`jd2101.DCE`、`jd2401.DCE`、`jd2009.DCE`。
  - status 为 `downloaded=4/4`，总 rows=`35,325`。
  - 覆盖变化为 `before_missing=22`、`after_missing=18`、`remaining_jd_missing=12`。
  - 4 个 CSV 均存在，`sha256` 与 status/file_manifest 一致。
  - 内容验收全部通过：OHLC/volume/OI 空值 `0`，重复键 `0`，OHLC 高低异常 `0`，负 volume/OI `0`，monotonic 为 true；首末日期匹配 request_start/end；unique dates 等于 observed_price_rows；rows 等于 observed_price_rows * `225`；每日均 `225` 行；session time error `0`。
  - Stage112 后验 strict gate 一致：`minute_file_ready=21`、`strict_ready=21`、`strict_failed=0`、`minute_missing=18`、`remaining_jd_not_ready=12`、`ready_for_true_ledger_replay=false`。
- 低风险点：dry-run 记录已明确 superseded，但它列出的输出文件路径与正式 run 相同，当前已经指向正式输出，不再是 dry-run 当时的独立文件快照；由于 dry-run 文件本身保留了 plan-only 关键信息，不影响正式 Stage113 结论。
- 建议：后续继续补剩余 `12` 个 jd 分钟缺口和 jd 逐日保证金历史；在两者未补齐前，不应跑 true ledger replay。后续 dry-run 建议使用单独 tag 或输出目录，避免 superseded 记录的输出指针被正式产物覆盖。
- 独立评估过拟合反思：否。这里只验证数据完整性和文件内容，不基于收益选择参数、合约或策略规则。
- 独立评估继续价值反思：有，但价值只在清除 Stage208/xsmom 真承载的数据阻塞，不代表 alpha 或策略晋级。
