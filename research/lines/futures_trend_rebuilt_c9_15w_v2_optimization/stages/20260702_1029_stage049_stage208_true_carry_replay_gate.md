# Stage049 Stage208 真承载复建闸门

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T10:29:44
- 阶段性质：只读源依赖/数据合同审计；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Moskowitz/Ooi/Pedersen Time Series Momentum、AQR Demystifying Managed Futures、pysystemtrade backtesting 与成本/保证金/换手实现说明。
- 我的判断：Stage048 日级 sleeve 已经反证，xsmom 若继续只能走 Stage208 级真承载；但真承载必须先确认当前 C9 日级 PnL/保证金、Stage020 signals、产品规格、分钟成交覆盖全部齐全。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage049_stage208_true_carry_replay_gate.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage049_stage208_true_carry_gate.py`
- 新增参数：无交易参数
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage049_stage208_true_carry_replay_blocked_keep_readonly`
- ready_for_true_ledger_replay：`False`
- blocking_source_ids：`contract_specs_exact,current_minute_fill_bars`
- blocking_reasons：`contract_specs_exact:missing_exact_specs:jd.DCE;current_minute_fill_bars:missing_minute_contracts:47`
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
| current_minute_fill_bars             | False   |         482 | missing_minute_contracts:47 | minute_file_index=557                             |

## Contract Spec Blocking

| product_vt_symbol   |   size |   slippage |   price_tick |   margin_ratio | spec_source    | exact_spec_ready   | blocking_reason      |
|:--------------------|-------:|-----------:|-------------:|---------------:|:---------------|:-------------------|:---------------------|
| jd.DCE              |     10 |          1 |            1 |              0 | tqsdk_metadata | False              | missing_margin_ratio |

## Minute Coverage Blocking

| contract_vt   | product_vt_symbol   | minute_file_ready   | minute_file   |
|:--------------|:--------------------|:--------------------|:--------------|
| SH609.CZCE    | SH.CZCE             | False               |               |
| SM609.CZCE    | SM.CZCE             | False               |               |
| au2608.SHFE   | au.SHFE             | False               |               |
| cu2607.SHFE   | cu.SHFE             | False               |               |
| cu2608.SHFE   | cu.SHFE             | False               |               |
| jd2005.DCE    | jd.DCE              | False               |               |
| jd2006.DCE    | jd.DCE              | False               |               |
| jd2007.DCE    | jd.DCE              | False               |               |
| jd2009.DCE    | jd.DCE              | False               |               |
| jd2010.DCE    | jd.DCE              | False               |               |
| jd2011.DCE    | jd.DCE              | False               |               |
| jd2101.DCE    | jd.DCE              | False               |               |
| jd2105.DCE    | jd.DCE              | False               |               |
| jd2109.DCE    | jd.DCE              | False               |               |
| jd2201.DCE    | jd.DCE              | False               |               |
| jd2205.DCE    | jd.DCE              | False               |               |
| jd2209.DCE    | jd.DCE              | False               |               |
| jd2301.DCE    | jd.DCE              | False               |               |
| jd2305.DCE    | jd.DCE              | False               |               |
| jd2309.DCE    | jd.DCE              | False               |               |
| jd2310.DCE    | jd.DCE              | False               |               |
| jd2311.DCE    | jd.DCE              | False               |               |
| jd2401.DCE    | jd.DCE              | False               |               |
| jd2402.DCE    | jd.DCE              | False               |               |
| jd2403.DCE    | jd.DCE              | False               |               |
| jd2405.DCE    | jd.DCE              | False               |               |
| jd2409.DCE    | jd.DCE              | False               |               |
| jd2410.DCE    | jd.DCE              | False               |               |
| jd2501.DCE    | jd.DCE              | False               |               |
| jd2502.DCE    | jd.DCE              | False               |               |
| jd2505.DCE    | jd.DCE              | False               |               |
| jd2506.DCE    | jd.DCE              | False               |               |
| jd2507.DCE    | jd.DCE              | False               |               |
| jd2508.DCE    | jd.DCE              | False               |               |
| jd2509.DCE    | jd.DCE              | False               |               |
| jd2510.DCE    | jd.DCE              | False               |               |
| jd2511.DCE    | jd.DCE              | False               |               |
| jd2512.DCE    | jd.DCE              | False               |               |
| jd2601.DCE    | jd.DCE              | False               |               |
| jd2602.DCE    | jd.DCE              | False               |               |
| jd2603.DCE    | jd.DCE              | False               |               |
| jd2604.DCE    | jd.DCE              | False               |               |
| jd2605.DCE    | jd.DCE              | False               |               |
| jd2606.DCE    | jd.DCE              | False               |               |
| jd2607.DCE    | jd.DCE              | False               |               |
| jd2608.DCE    | jd.DCE              | False               |               |
| lh2609.DCE    | lh.DCE              | False               |               |

## 过拟合反思

- 运行前判断：否。本阶段不调 xsmom 参数，只审计 Stage208 级真承载所需数据合同是否满足。
- 运行后判断：否。若阻塞源未齐全，直接用默认保证金、fallback 成交或旧输出替代才是隐性过拟合/污染。

## 继续价值反思

- 运行前判断：有。Stage048 反证日级 sleeve 后，只有一次性真承载依赖闸门能决定 xsmom 是否继续。
- 运行后判断：有但不能直接跑真承载。先补齐阻塞源，否则会把 fallback 或默认保证金误当成策略证据。

## 输出文件

- source_table：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage049_stage208_true_carry_replay_gate/rebuilt_c9_v2_stage049_stage208_true_carry_replay_gate_source_table_stage049_stage208_true_carry_replay_gate_v1.csv`
- contract_spec_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage049_stage208_true_carry_replay_gate/rebuilt_c9_v2_stage049_stage208_true_carry_replay_gate_contract_spec_audit_stage049_stage208_true_carry_replay_gate_v1.csv`
- minute_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage049_stage208_true_carry_replay_gate/rebuilt_c9_v2_stage049_stage208_true_carry_replay_gate_minute_contract_coverage_stage049_stage208_true_carry_replay_gate_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage049_stage208_true_carry_replay_gate/rebuilt_c9_v2_stage049_stage208_true_carry_replay_gate_decision_stage049_stage208_true_carry_replay_gate_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage049_stage208_true_carry_replay_gate/rebuilt_c9_v2_stage049_stage208_true_carry_replay_gate_report_stage049_stage208_true_carry_replay_gate_v1.md`
