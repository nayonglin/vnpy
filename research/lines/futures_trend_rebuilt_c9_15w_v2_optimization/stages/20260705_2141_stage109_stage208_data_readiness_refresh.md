# Stage109 Stage208 数据就绪刷新

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05 21:41 CST
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据就绪刷新；不回测收益、不改策略、不连接 CTP、不调用订单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：DCE historical/trading parameter pages、TqSdk historical/backtest docs、pysystemtrade backtesting docs。
- 我的判断：Stage208/xsmom 真承载仍是结构性方向，但必须先补分钟成交窗口和 JD 逐日保证金；不能用默认保证金或旧输出替代。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage109_stage208_data_readiness_refresh.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：`NEXT_BATCH_SIZE=6`。
- 修改参数：无正式策略参数。
- 删除参数：无。

## 结果摘要

- 决策：`stage109_stage208_data_still_blocked_batch4_and_margin_needed`
- ready_for_true_ledger_replay：`False`
- source_blocking_ids：`contract_specs_exact,current_minute_fill_bars`
- current_minute_contract_missing：`28`
- manifest_missing：`28`
- manifest_jd_missing：`22`
- contract_spec_blocking_count：`1`
- jd_margin_history_ready：`False`
- next_batch_contract_count：`6`
- next_batch_contracts：`['jd2601.DCE', 'jd2605.DCE', 'jd2508.DCE', 'jd2403.DCE', 'jd2603.DCE', 'jd2006.DCE']`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Source Table

| source_id                            | ready   |   row_count | blocking_reason             | detail                                            |
|:-------------------------------------|:--------|------------:|:----------------------------|:--------------------------------------------------|
| current_c9_stage167_daily_pnl_margin | True    |        1571 |                             | start=2020-01-02 00:00:00 end=2026-06-30 00:00:00 |
| stage020_xsmom_signal_daily          | True    |        1571 |                             | active_rows=1410                                  |
| stage020_price_frame_daily           | True    |       27121 |                             | products=19 end_rows=19                           |
| contract_specs_exact                 | False   |          19 | missing_exact_specs:jd.DCE  | products=19                                       |
| current_minute_fill_bars             | False   |         482 | missing_minute_contracts:28 | minute_file_index=576                             |

## Missing Contract Specs

| product_vt_symbol   |   size |   slippage |   price_tick |   margin_ratio | spec_source    | exact_spec_ready   | blocking_reason      |
|:--------------------|-------:|-----------:|-------------:|---------------:|:---------------|:-------------------|:---------------------|
| jd.DCE              |     10 |          1 |            1 |              0 | tqsdk_metadata | False              | missing_margin_ratio |

## Missing Minute Coverage

| contract_vt   | product_vt_symbol   | minute_file_ready   | minute_file   |
|:--------------|:--------------------|:--------------------|:--------------|
| SH609.CZCE    | SH.CZCE             | False               |               |
| SM609.CZCE    | SM.CZCE             | False               |               |
| au2608.SHFE   | au.SHFE             | False               |               |
| cu2607.SHFE   | cu.SHFE             | False               |               |
| cu2608.SHFE   | cu.SHFE             | False               |               |
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
| lh2609.DCE    | lh.DCE              | False               |               |

## Manifest Missing

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

## Next Backfill Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | download_start_datetime   | download_end_datetime   |   observed_price_rows | priority                 | output_path                                                                                                                                                 |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:--------------------------|:------------------------|----------------------:|:-------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| jd2601.DCE    | jd.DCE              | DCE.jd2601  | 2025-11-17           | 2025-12-17         | 2025-11-17                | 2025-12-18              |                    23 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2601_minute_backtest.csv |
| jd2605.DCE    | jd.DCE              | DCE.jd2605  | 2026-03-05           | 2026-04-08         | 2026-03-05                | 2026-04-09              |                    24 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2605_minute_backtest.csv |
| jd2508.DCE    | jd.DCE              | DCE.jd2508  | 2025-06-11           | 2025-07-14         | 2025-06-11                | 2025-07-15              |                    24 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2508_minute_backtest.csv |
| jd2403.DCE    | jd.DCE              | DCE.jd2403  | 2024-01-10           | 2024-02-20         | 2024-01-10                | 2024-02-21              |                    24 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2403_minute_backtest.csv |
| jd2603.DCE    | jd.DCE              | DCE.jd2603  | 2025-12-31           | 2026-02-11         | 2025-12-31                | 2026-02-12              |                    29 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2603_minute_backtest.csv |
| jd2006.DCE    | jd.DCE              | DCE.jd2006  | 2020-04-09           | 2020-05-27         | 2020-04-09                | 2020-05-28              |                    32 | P0_jd_true_carry_blocker | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tqsdk_stage052_jd_minute_gap_backfill/DCE/jd2006_minute_backtest.csv |

## 标准回测指标

- 期末权益：不适用，本阶段只读数据依赖未重跑策略。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 决策

```json
{
  "stage": "Stage109",
  "line_id": "futures_trend_rebuilt_c9_15w_v2_optimization",
  "model_tag": "stage109_stage208_data_readiness_refresh_v1",
  "generated_at": "2026-07-05T21:41:29",
  "decision": "stage109_stage208_data_still_blocked_batch4_and_margin_needed",
  "ready_for_true_ledger_replay": false,
  "source_blocking_ids": "contract_specs_exact,current_minute_fill_bars",
  "current_minute_contract_missing": 28,
  "manifest_missing": 28,
  "manifest_jd_missing": 22,
  "contract_spec_blocking_count": 1,
  "stage091_decision": "stage091_no_accepted_jd_margin_source_route_matrix_ready",
  "stage091_accepted_route_count": 0,
  "jd_margin_history_ready": false,
  "next_batch_contract_count": 6,
  "next_batch_contracts": [
    "jd2601.DCE",
    "jd2605.DCE",
    "jd2508.DCE",
    "jd2403.DCE",
    "jd2603.DCE",
    "jd2006.DCE"
  ],
  "next_batch_jd_contract_count": 6,
  "strategy_rule_created": false,
  "official_live_strategy_changed": false,
  "true_engine_run": false,
  "order_api_called": false,
  "send_order_api_called_count": 0,
  "cancel_order_api_called_count": 0,
  "ctp_connected": false,
  "formal_ab_triggered": false,
  "external_research_judgment": "DCE/供应商路线能提供历史行情或交易参数，但保证金会按合约和日期变化；独立 xsmom/carry sleeve 只有在分钟成交和逐日保证金都通过验收后才可回测。",
  "overfit_reflection_before": "否。本阶段只刷新数据依赖，不看收益、不调策略参数。",
  "overfit_reflection_after": "否。结论仍是数据阻塞；强行用默认保证金或 fallback 分钟线回测才会形成隐性过拟合。",
  "continue_value_before": "有。Stage108 已停止 base_stop 延迟退出，结构性路线回到独立收益腿数据就绪。",
  "continue_value_after": "有。这是当前剩余少数结构性路线；但未补保证金前不能跑策略回测。",
  "next_step": "继续小批量补 `next_backfill_plan` 的分钟合约；同时必须获取 DCE 注册门户或授权 vendor 的 `jd_contract_daily_margin_history`，否则禁止 true ledger replay。"
}
```

## 后续规划和 TODO

- 继续小批量补 `next_backfill_plan` 的分钟合约；同时必须获取 DCE 注册门户或授权 vendor 的 `jd_contract_daily_margin_history`，否则禁止 true ledger replay。

## 过拟合反思

- 运行前：否。本阶段只刷新数据依赖，不看收益、不调策略参数。
- 运行后：否。结论仍是数据阻塞；强行用默认保证金或 fallback 分钟线回测才会形成隐性过拟合。

## 继续价值反思

- 运行前：有。Stage108 已停止 base_stop 延迟退出，结构性路线回到独立收益腿数据就绪。
- 运行后：有。这是当前剩余少数结构性路线；但未补保证金前不能跑策略回测。

## 输出

- 报告：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage109_stage208_data_readiness_refresh/rebuilt_c9_v2_stage109_stage208_data_readiness_refresh_report_stage109_stage208_data_readiness_refresh_v1.md`
- source_table：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage109_stage208_data_readiness_refresh/rebuilt_c9_v2_stage109_stage208_data_readiness_refresh_source_table_stage109_stage208_data_readiness_refresh_v1.csv`
- contract_spec_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage109_stage208_data_readiness_refresh/rebuilt_c9_v2_stage109_stage208_data_readiness_refresh_contract_spec_audit_stage109_stage208_data_readiness_refresh_v1.csv`
- minute_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage109_stage208_data_readiness_refresh/rebuilt_c9_v2_stage109_stage208_data_readiness_refresh_minute_contract_coverage_stage109_stage208_data_readiness_refresh_v1.csv`
- manifest_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage109_stage208_data_readiness_refresh/rebuilt_c9_v2_stage109_stage208_data_readiness_refresh_manifest_coverage_stage109_stage208_data_readiness_refresh_v1.csv`
- next_backfill_plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage109_stage208_data_readiness_refresh/rebuilt_c9_v2_stage109_stage208_data_readiness_refresh_next_backfill_plan_stage109_stage208_data_readiness_refresh_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage109_stage208_data_readiness_refresh/rebuilt_c9_v2_stage109_stage208_data_readiness_refresh_input_audit_stage109_stage208_data_readiness_refresh_v1.csv`

## 独立 Agent 评估

- 评估 agent：Carson（`019f3283-660f-7dc1-82c9-e4f5fd2b2001`）
- 置信度：`0.88`
- 结论：Stage109 是数据就绪刷新，不改策略、不跑回测、不连接 CTP、不调用订单/邮件；`ready_for_true_ledger_replay=False` 的决策正确。
- 高风险 bug：未发现。
- 中风险 bug：未发现。
- 复算一致项：
  - 阻塞只有 `contract_specs_exact` 和 `current_minute_fill_bars`。
  - `contract_spec_blocking_count=1`，仅 `jd.DCE` 缺 `margin_ratio`。
  - 当前分钟覆盖 missing `28`；其中 `jd.DCE=22`，其余 `SH/SM/au/cu/lh` 合计 `6`。
  - manifest 总数 `39`、missing `28`、`jd` missing `22`。
  - 下一批补数计划为 `jd2601.DCE`、`jd2605.DCE`、`jd2508.DCE`、`jd2403.DCE`、`jd2603.DCE`、`jd2006.DCE`。
- 边界提醒：当前 `minute_file_ready` 是“文件路径存在”级别，不校验文件内容、时间窗、行数、hash；进入 true ledger replay 前必须补内容级验收。
- 独立评估过拟合反思：否。本阶段只复核数据依赖和阻塞状态，没有看收益、没有调参数、没有选择性救参。
- 独立评估继续价值反思：有价值继续，但只限于补齐 `jd` 分钟文件和 `jd` 逐日保证金历史；在 `jd_contract_daily_margin_history` ready 前，继续跑 true ledger replay 没有决策价值。
