# Stage110 jd minute backfill batch4

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T21:57:36
- 阶段性质：数据补齐；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 外部资料确认：TqSdk 官方文档支持 `TqBacktest` 历史回测模式和 `get_kline_serial` 读取 K 线；`DataDownloader` 更适合长期批量历史下载，但属于专业版下载工具。
- 我的判断：本阶段沿用 Stage051/052 已验证的 `TqBacktest + get_kline_serial` 受控补数路线。下载分钟线只是在清阻塞，不代表策略收益改进；保证金历史未补前仍不能跑 true ledger replay。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage110_jd_minute_backfill_batch4.py`
- 新增参数：`STAGE110_ENABLE_DOWNLOAD`、`STAGE110_MAX_SYMBOLS`、`STAGE110_MAX_SECONDS_PER_SYMBOL`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage110_jd_minute_backfill_batch4_success_margin_still_blocked`
- download_enabled：`True`
- planned_contract_count：`6`
- download_success_contract_count：`6`
- downloaded_minute_rows：`35100`
- before_missing：`28`
- after_missing：`22`
- remaining_jd_missing：`16`
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

| contract_vt   | tq_symbol   | download_start_datetime   | download_end_datetime   | status     |   rows | first_bar_datetime   | last_bar_datetime   |   elapsed_seconds | output_path                                                                                                                                                 | sha256                                                           | message   |
|:--------------|:------------|:--------------------------|:------------------------|:-----------|-------:|:---------------------|:--------------------|------------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------|:----------|
| jd2601.DCE    | DCE.jd2601  | 2025-11-17 00:00:00       | 2025-12-18 00:00:00     | downloaded |   5175 | 2025-11-17 09:00:00  | 2025-12-17 14:59:00 |             96.95 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2601_minute_backtest.csv | 4f10e43fb8f1ebde0311c4b824ac095f4c12d8be2c81572b20e0e607b6faec34 |           |
| jd2605.DCE    | DCE.jd2605  | 2026-03-05 00:00:00       | 2026-04-09 00:00:00     | downloaded |   5400 | 2026-03-05 09:00:00  | 2026-04-08 14:59:00 |            100.3  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2605_minute_backtest.csv | 58361cf917d9412805be547acf8ca6cfa2781b5bcab8bfd88da421966fa3d13c |           |
| jd2508.DCE    | DCE.jd2508  | 2025-06-11 00:00:00       | 2025-07-15 00:00:00     | downloaded |   5400 | 2025-06-11 09:00:00  | 2025-07-14 14:59:00 |            100.05 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2508_minute_backtest.csv | 8feba2702a80dfda2098e1c71426b9e7b23c10779a43bf1bb7e1596132c3b7aa |           |
| jd2403.DCE    | DCE.jd2403  | 2024-01-10 00:00:00       | 2024-02-21 00:00:00     | downloaded |   5400 | 2024-01-10 09:00:00  | 2024-02-20 14:59:00 |             99.8  | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2403_minute_backtest.csv | d53931f068fbcc6bc8feb4275deaae0a0d257d0df6d7033c483fa352d47581ca |           |
| jd2603.DCE    | DCE.jd2603  | 2025-12-31 00:00:00       | 2026-02-12 00:00:00     | downloaded |   6525 | 2025-12-31 09:00:00  | 2026-02-11 14:59:00 |            118.83 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2603_minute_backtest.csv | f8cdaf0714007acdc71bab32c3a578c70fe72aade2512f9b6aac6616088369a3 |           |
| jd2006.DCE    | DCE.jd2006  | 2020-04-09 00:00:00       | 2020-05-28 00:00:00     | downloaded |   7200 | 2020-04-09 09:00:00  | 2020-05-27 14:59:00 |            129.14 | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2006_minute_backtest.csv | 5a9d7af274be35a8f66b27635fc1967fb994a92b6a373e860fdc100684caa767 |           |

## 本地内容验收

- 6 个新增 CSV 均存在，`sha256` 已记录。
- OHLC 空值：`0`。
- `vt_symbol + bar_datetime` 重复：`0`。
- 时间窗验收：
  - `jd2601.DCE`：`5,175` 行，`2025-11-17 09:00:00` 至 `2025-12-17 14:59:00`。
  - `jd2605.DCE`：`5,400` 行，`2026-03-05 09:00:00` 至 `2026-04-08 14:59:00`。
  - `jd2508.DCE`：`5,400` 行，`2025-06-11 09:00:00` 至 `2025-07-14 14:59:00`。
  - `jd2403.DCE`：`5,400` 行，`2024-01-10 09:00:00` 至 `2024-02-20 14:59:00`。
  - `jd2603.DCE`：`6,525` 行，`2025-12-31 09:00:00` 至 `2026-02-11 14:59:00`。
  - `jd2006.DCE`：`7,200` 行，`2020-04-09 09:00:00` 至 `2020-05-27 14:59:00`。
- 边界：这是内容级基本验收，不等同于完整交易日历、session 完整性和跨源价格一致性验收；进入 true ledger replay 前仍需更严格 manifest。

## Remaining Missing

| contract_vt   | product_vt_symbol   | minute_file_ready   | minute_file   |
|:--------------|:--------------------|:--------------------|:--------------|
| jd2005.DCE    | jd.DCE              | False               |               |
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
| jd2405.DCE    | jd.DCE              | False               |               |
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

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_report_stage110_jd_minute_backfill_batch4_v1.md`
- backfill_plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_backfill_plan_stage110_jd_minute_backfill_batch4_v1.csv`
- backfill_status：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_backfill_status_stage110_jd_minute_backfill_batch4_v1.csv`
- file_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_file_manifest_stage110_jd_minute_backfill_batch4_v1.csv`
- before_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_before_minute_coverage_stage110_jd_minute_backfill_batch4_v1.csv`
- after_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_after_minute_coverage_stage110_jd_minute_backfill_batch4_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_input_audit_stage110_jd_minute_backfill_batch4_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage110_jd_minute_backfill_batch4/rebuilt_c9_v2_stage110_jd_minute_backfill_batch4_decision_stage110_jd_minute_backfill_batch4_v1.json`

## 独立 Agent 评估

- 评估 agent：Mendel（`019f3292-9011-7f31-b4ea-6aaa5f7c85ed`）
- 置信度：`0.91`
- 结论：Stage110 是 Stage087 风格的机械批次包装，核心下载/覆盖逻辑复用 Stage052；不改策略、不跑 true engine、不连接 CTP、不调用订单/邮件。
- 高风险 bug：未发现。
- 中风险 bug：未发现。
- 复算一致项：
  - `backfill_plan` 精确为 `jd2601.DCE`、`jd2605.DCE`、`jd2508.DCE`、`jd2403.DCE`、`jd2603.DCE`、`jd2006.DCE`。
  - `backfill_status` 为 `6/6 downloaded`，行数合计 `35,100`，逐文件行数为 `5,175/5,400/5,400/5,400/6,525/7,200`。
  - 6 个 CSV 均存在，`sha256` 可复算且与 status/manifest 一致。
  - OHLC 空值 `0`，`vt_symbol + bar_datetime` 重复 `0`，OHLC 高低关系异常 `0`。
  - 覆盖计数复算为 `before_missing=28`、`after_missing=22`、`remaining_jd_missing=16`。
  - `remaining_blocker=jd_contract_daily_margin_history`，`ready_for_true_ledger_replay=false`，策略/true engine/order/CTP 标记均为 false/0。
- 边界提醒：
  - dry-run 与正式下载共用输出文件名，正式输出覆盖 dry-run 输出；当前 dry-run stage 记录已标记为取代，人工审计语义可接受，但严格 provenance 不理想。
  - 当前 `file_manifest` 只有 rows/sha/discoverable，缺少机器可验的 OHLC 空值、重复键、时间窗、session 完整性、价格异常、交易日历覆盖；Stage111/112 不能只靠当前 manifest 放行 true ledger replay。
- 独立评估过拟合反思：否。本阶段只按 P0 缺口 manifest 补数据，没有按收益、回撤或 Sharpe 选择合约/参数。
- 独立评估继续价值反思：有。它降低了 Stage208/xsmom 真承载的数据阻塞，但不能被解读为策略优化成功。
