# Stage112 strict minute content gate

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T22:10:42
- 阶段性质：只读严格数据验收；不下载、不回测收益、不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考：vn.py `BarData` / `BarGenerator`、TqSdk market data。
- 我的判断：这是对 Stage111 的数据闸门收紧，不是策略优化；通过也只代表现有分钟文件更可信。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage112_strict_minute_content_gate.py`
- 新增参数：无。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage112_strict_minute_existing_files_pass_margin_or_missing_files_blocked`
- manifest_contract_count：`39`
- minute_file_ready_count：`17`
- strict_ready_count：`17`
- minute_missing_count：`22`
- strict_failed_count：`0`
- remaining_jd_not_ready_count：`16`
- expected_jd_day_rows：`225`
- jd_margin_history_ready：`False`
- ready_for_true_ledger_replay：`False`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Summary

| product_vt_symbol   |   contract_count |   minute_file_ready |   strict_ready |   missing_file_count |   source_conflict_count |   strict_failed_count |
|:--------------------|-----------------:|--------------------:|---------------:|---------------------:|------------------------:|----------------------:|
| SH.CZCE             |                1 |                   0 |              0 |                    1 |                       0 |                     0 |
| SM.CZCE             |                1 |                   0 |              0 |                    1 |                       0 |                     0 |
| au.SHFE             |                1 |                   0 |              0 |                    1 |                       0 |                     0 |
| cu.SHFE             |                2 |                   0 |              0 |                    2 |                       0 |                     0 |
| jd.DCE              |               33 |                  17 |             17 |                   16 |                       0 |                     0 |
| lh.DCE              |                1 |                   0 |              0 |                    1 |                       0 |                     0 |

## Strict Failures

_无记录_

## Missing Files

| contract_vt   | product_vt_symbol   | priority                 | request_start_date   | request_end_date   |
|:--------------|:--------------------|:-------------------------|:---------------------|:-------------------|
| jd2005.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2020-01-02           | 2020-04-08         |
| jd2009.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2020-06-15           | 2020-08-18         |
| jd2101.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2020-10-22           | 2020-12-08         |
| jd2105.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2020-12-09           | 2021-04-14         |
| jd2109.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2021-04-15           | 2021-08-18         |
| jd2201.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2021-08-19           | 2021-12-10         |
| jd2205.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2021-12-13           | 2022-04-06         |
| jd2209.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2022-04-07           | 2022-08-12         |
| jd2301.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2022-08-15           | 2022-12-13         |
| jd2305.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2022-12-14           | 2023-04-13         |
| jd2309.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2023-04-14           | 2023-08-14         |
| jd2401.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2023-10-13           | 2023-12-14         |
| jd2405.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2024-02-21           | 2024-04-09         |
| jd2409.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2024-04-10           | 2024-08-21         |
| jd2501.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2024-09-09           | 2024-12-13         |
| jd2505.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2025-01-15           | 2025-04-15         |
| SH609.CZCE    | SH.CZCE             | P1_tail_contract_gap     | 2026-06-17           | 2026-06-30         |
| SM609.CZCE    | SM.CZCE             | P1_tail_contract_gap     | 2026-06-04           | 2026-06-30         |
| au2608.SHFE   | au.SHFE             | P1_tail_contract_gap     | 2026-05-26           | 2026-06-30         |
| cu2607.SHFE   | cu.SHFE             | P1_tail_contract_gap     | 2026-05-22           | 2026-06-23         |
| cu2608.SHFE   | cu.SHFE             | P1_tail_contract_gap     | 2026-06-24           | 2026-06-30         |
| lh2609.DCE    | lh.DCE              | P1_tail_contract_gap     | 2026-06-02           | 2026-06-30         |

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。本阶段只收紧数据 gate，不看收益、不调策略参数。
- 运行后：否。严格门槛只会降低错误数据通过概率，不会通过绩效筛选制造收益。

## 继续价值反思

- 运行前：有。Stage111 独立评估指出若不收紧 manifest，后续批次可能继承偏宽口径。
- 运行后：有。若 strict 通过，可继续补剩余 jd；若失败，应先修数据而不是跑回测。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage112_strict_minute_content_gate/rebuilt_c9_v2_stage112_strict_minute_content_gate_report_stage112_strict_minute_content_gate_v1.md`
- strict_manifest：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage112_strict_minute_content_gate/rebuilt_c9_v2_stage112_strict_minute_content_gate_strict_manifest_stage112_strict_minute_content_gate_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage112_strict_minute_content_gate/rebuilt_c9_v2_stage112_strict_minute_content_gate_summary_stage112_strict_minute_content_gate_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage112_strict_minute_content_gate/rebuilt_c9_v2_stage112_strict_minute_content_gate_input_audit_stage112_strict_minute_content_gate_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage112_strict_minute_content_gate/rebuilt_c9_v2_stage112_strict_minute_content_gate_decision_stage112_strict_minute_content_gate_v1.json`

## 独立 Agent 评估

- 评估 agent：Nietzsche（`019f329e-7aa8-7383-9b04-fc818a3ccdb2`）
- 置信度：`0.94`
- 结论：Stage112 验收结论成立，是严格数据验收 gate，不是策略回测；未发现下载、CTP/实盘、订单、邮件、策略改动路径。
- 高风险 bug：未发现。
- 中风险 bug：未发现。
- 复算一致项：
  - `manifest_contract_count=39`，`minute_file_ready_count=17`，`strict_ready_count=17`，`minute_missing_count=22`，`strict_failed_count=0`，`remaining_jd_not_ready_count=16`，`expected_jd_day_rows=225`，`jd_margin_history_ready=false`，`ready_for_true_ledger_replay=false`。
  - 17 个 ready 文件全部通过：`sha256` 一致；OHLC/volume/OI 空值为 `0`；重复键为 `0`；高低价关系异常为 `0`；负 volume/OI 为 `0`；monotonic 全为 true；首日/末日匹配 request_start/request_end；`unique_trade_dates == observed_price_rows`；总行数等于 `observed_price_rows * 225`；每日行数 min/max 都是 `225`；session time 错误为 `0`。
  - 额外复核 session time set：missing/extra 都是 `0`。
  - 索引复核：`tqsdk_stage052_jd_minute_gap_backfill` 下 direct/recursive 都是 `25` 个文件，`0` conflict；其中 `17` 个属于 Stage050 manifest，`8` 个不在 manifest 内；`22` 个 manifest missing 合约在更大的 `downloaded_futures` 树里也没有可用同名文件。
  - 非 jd P1 缺失没有被误判为 strict failure：`6` 个 P1 缺失只进入 `minute_missing_count`，当前 `strict_failed_count=0`。
- 低风险点：
  - `run()` 会写 CSV/JSON/MD 和 stage record；数据/交易语义只读成立，但执行入口不是文件系统绝对只读。
  - 对 `vt_symbol` 只取首个非空值校验；当前 17 个文件无问题，未来若全空或单一错误 vt_symbol，诊断可能不够清晰。
  - failure reason 拼接只影响诊断文本，不影响 decision；未来如果出现“vt_symbol 错但 unique count=1”，blocking reason 可能不会明确写出该原因。
  - 当前 session set 由 `session_time_error=0 + 每日225行 + 无重复键 + 总行数匹配` 间接保证；建议后续把 missing/extra time set 显式写入 manifest。
- 建议：Stage112 可以作为当前数据严格验收 gate 采信；不要进入 true ledger replay，因为 `16` 个 jd 分钟缺口和 `jd_contract_daily_margin_history` 仍未解决。后续优先补剩余 `16` 个 jd P0 分钟文件与逐日保证金历史，补完后先跑同类 strict gate，再考虑真账本复演。
- 独立评估过拟合反思：否。本次只验数据完整性和数据合同，不看收益、不调参、不筛策略。
- 独立评估继续价值反思：有。继续做的价值在于补齐真承载数据阻塞；但在保证金历史和剩余 jd 分钟未补齐前，继续跑收益回测价值不高。
