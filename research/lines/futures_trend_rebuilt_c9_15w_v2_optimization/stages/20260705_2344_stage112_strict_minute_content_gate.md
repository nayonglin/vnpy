# Stage112 strict minute content gate

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T23:44:30
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
- minute_file_ready_count：`31`
- strict_ready_count：`31`
- minute_missing_count：`8`
- strict_failed_count：`0`
- remaining_jd_not_ready_count：`2`
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
| jd.DCE              |               33 |                  31 |             31 |                    2 |                       0 |                     0 |
| lh.DCE              |                1 |                   0 |              0 |                    1 |                       0 |                     0 |

## Strict Failures

_无记录_

## Missing Files

| contract_vt   | product_vt_symbol   | priority                 | request_start_date   | request_end_date   |
|:--------------|:--------------------|:-------------------------|:---------------------|:-------------------|
| jd2209.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2022-04-07           | 2022-08-12         |
| jd2409.DCE    | jd.DCE              | P0_jd_true_carry_blocker | 2024-04-10           | 2024-08-21         |
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
