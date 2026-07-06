# Stage089 jd margin endpoint probe

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T17:49:26
- 阶段性质：只读接口/数据源探针；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- `dce_daily_trading_parameters`：https://www.dce.com.cn/dceg/channel/list/488.html；DCE has a Daily Trading Parameters page, but terminal direct access was not available in this run.
- `dce_egg_contract_page`：https://www.dce.com.cn/dce/channel/list/127.html；DCE contract page states JD minimum trading margin and notes DCE may adjust margins by market conditions.
- `akshare_futures_docs`：https://akshare-hh.readthedocs.io/en/latest/data/futures/futures.html；AKShare docs expose a static futures margin table updated on 2021-09-03; this is not a PIT daily series.
- `akshare_github_docs`：https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md；GitHub docs were checked for futures data surface area; margin history must still be source-audited.

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage089_jd_margin_endpoint_probe.py`
- 新增参数：`SAMPLE_DATES=('20200102', '20200630', '20210104', '20210630', '20220104', '20220630', '20230103', '20230630', '20240102', '20240603', '20250102', '20250630', '20260102', '20260629')`
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage089_gtja_margin_route_candidate_but_no_accepted_daily_history`
- accepted_candidate_count：`0`
- rebuild_candidate_count：`1`
- gtja_sample_date_count：`14`
- gtja_ok_sample_count：`11`
- gtja_jd_sample_count：`11`
- gtja_contract_adjustment_count：`11`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Source Probe

| candidate_id                              | source_type                     | status   |   row_count |   jd_row_count | has_margin_columns   | has_contract_grain   | has_trade_date   | covers_required_range_probe   | accepted_for_jd_contract_daily_margin_history   | pit_acceptance                 | reject_reason                                                        | detail                                                                                                                                                                                    |
|:------------------------------------------|:--------------------------------|:---------|------------:|---------------:|:---------------------|:---------------------|:-----------------|:------------------------------|:------------------------------------------------|:-------------------------------|:---------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| akshare_futures_settle_dce                | exchange_settlement_api_wrapper | ok       |           0 |              0 | True                 | True                 | True             | False                         | False                                           | rejected                       | current_akshare_wrapper_unsupported_dce                              | DCE returns empty because wrapper has no DCE branch in installed akshare.                                                                                                                 |
| akshare_futures_contract_info_dce         | dce_contract_static_info        | error    |           0 |              0 | False                | False                | False            | False                         | False                                           | rejected                       | contract_static_info_not_margin_history                              | JSONDecodeError: Expecting value: line 1 column 1 (char 0)                                                                                                                                |
| akshare_futures_rule_gtja_jd_margin       | broker_calendar_margin_probe    | ok       |        1246 |             11 | True                 | False                | True             | False                         | False                                           | rebuild_candidate_not_accepted | sample_probe_only_needs_full_history_contract_expansion_publish_hash | sample_dates=14 ok=11 jd=11; earliest_ok=2021-01-04 latest_ok=2026-06-29; provides broker-like product margin and special adjustment text, but not yet a full contract-daily PIT dataset. |
| akshare_futures_fees_info_openctp_current | current_snapshot_openctp        | ok       |         869 |             12 | True                 | True                 | False            | False                         | False                                           | rejected                       | current_snapshot_not_history                                         | current snapshot update_time=2026-07-04 02:42:41                                                                                                                                          |
| akshare_futures_comm_info_9qihuo_current  | current_snapshot_9qihuo         | ok       |         245 |             12 | True                 | True                 | False            | False                         | False                                           | rejected                       | current_snapshot_not_history                                         | current snapshot price_update_time=2026-06-29 10:03:28.857                                                                                                                                |

## GTJA Rule Sample

| trade_date   | status   |   row_count |   jd_row_count |   jd_product_broker_margin_ratio | raw_adjustment                  | error                       |
|:-------------|:---------|------------:|---------------:|---------------------------------:|:--------------------------------|:----------------------------|
| 2020-01-02   | error    |           0 |              0 |                           nan    |                                 | ValueError: No tables found |
| 2020-06-30   | error    |           0 |              0 |                           nan    |                                 | KeyError: '合约乘数'        |
| 2021-01-04   | ok       |          85 |              1 |                             0.13 | JD2101合约交易保证金比例为24.0% |                             |
| 2021-06-30   | ok       |          91 |              1 |                             0.13 | JD2107合约交易保证金比例为14.0% |                             |
| 2022-01-04   | ok       |          91 |              1 |                             0.15 | JD2201合约交易保证金比例为26.0% |                             |
| 2022-06-30   | ok       |          91 |              1 |                             0.15 | JD2207合约交易保证金比例为16.0% |                             |
| 2023-01-03   | ok       |         103 |              1 |                             0.15 | JD2301合约交易保证金比例为26.0% |                             |
| 2023-06-30   | ok       |         107 |              1 |                             0.14 | JD2307合约交易保证金比例为16.0% |                             |
| 2024-01-02   | ok       |         122 |              1 |                             0.14 | JD2401合约交易保证金比例为26.0% |                             |
| 2024-06-03   | ok       |         122 |              1 |                             0.13 | JD2406合约交易保证金比例为26.0% |                             |
| 2025-01-02   | ok       |         137 |              2 |                             0.13 | JD2501合约交易保证金比例为26.0% |                             |
| 2025-06-30   | ok       |         139 |              2 |                             0.13 | JD2507合约交易保证金比例为16.0% |                             |
| 2026-01-02   | error    |           0 |              0 |                           nan    |                                 | ValueError: No tables found |
| 2026-06-29   | ok       |         158 |              2 |                             0.13 | JD2607合约交易保证金比例为16.0% |                             |

## Parsed JD Adjustments

| trade_date   | contract_vt   |   broker_margin_ratio | raw_adjustment                  | source_system                      | accepted_for_true_ledger   | reject_reason                                  |
|:-------------|:--------------|----------------------:|:--------------------------------|:-----------------------------------|:---------------------------|:-----------------------------------------------|
| 2021-01-04   | jd2101.DCE    |                  0.24 | JD2101合约交易保证金比例为24.0% | akshare.futures_rule_gtja_calendar | False                      | sample_only_not_full_pit_contract_daily_series |
| 2021-06-30   | jd2107.DCE    |                  0.14 | JD2107合约交易保证金比例为14.0% | akshare.futures_rule_gtja_calendar | False                      | sample_only_not_full_pit_contract_daily_series |
| 2022-01-04   | jd2201.DCE    |                  0.26 | JD2201合约交易保证金比例为26.0% | akshare.futures_rule_gtja_calendar | False                      | sample_only_not_full_pit_contract_daily_series |
| 2022-06-30   | jd2207.DCE    |                  0.16 | JD2207合约交易保证金比例为16.0% | akshare.futures_rule_gtja_calendar | False                      | sample_only_not_full_pit_contract_daily_series |
| 2023-01-03   | jd2301.DCE    |                  0.26 | JD2301合约交易保证金比例为26.0% | akshare.futures_rule_gtja_calendar | False                      | sample_only_not_full_pit_contract_daily_series |
| 2023-06-30   | jd2307.DCE    |                  0.16 | JD2307合约交易保证金比例为16.0% | akshare.futures_rule_gtja_calendar | False                      | sample_only_not_full_pit_contract_daily_series |
| 2024-01-02   | jd2401.DCE    |                  0.26 | JD2401合约交易保证金比例为26.0% | akshare.futures_rule_gtja_calendar | False                      | sample_only_not_full_pit_contract_daily_series |
| 2024-06-03   | jd2406.DCE    |                  0.26 | JD2406合约交易保证金比例为26.0% | akshare.futures_rule_gtja_calendar | False                      | sample_only_not_full_pit_contract_daily_series |
| 2025-01-02   | jd2501.DCE    |                  0.26 | JD2501合约交易保证金比例为26.0% | akshare.futures_rule_gtja_calendar | False                      | sample_only_not_full_pit_contract_daily_series |
| 2025-06-30   | jd2507.DCE    |                  0.16 | JD2507合约交易保证金比例为16.0% | akshare.futures_rule_gtja_calendar | False                      | sample_only_not_full_pit_contract_daily_series |
| 2026-06-29   | jd2607.DCE    |                  0.16 | JD2607合约交易保证金比例为16.0% | akshare.futures_rule_gtja_calendar | False                      | sample_only_not_full_pit_contract_daily_series |

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。本阶段只审计数据接口，不调整交易规则或收益目标。
- 运行后：否。虽然发现 GTJA 样本可用，但没有把样本保证金直接当作策略输入。

## 继续价值反思

- 运行前：有。Stage088 已证明本地没有 accepted 源，需要判断外部接口路线。
- 运行后：有条件。GTJA 路线值得做一次批量覆盖/解析验收，但 DCE/vendor 官方逐日参数仍是优先级更高的数据源。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage089_jd_margin_endpoint_probe/rebuilt_c9_v2_stage089_jd_margin_endpoint_probe_report_stage089_jd_margin_endpoint_probe_v1.md`
- source_probe：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage089_jd_margin_endpoint_probe/rebuilt_c9_v2_stage089_jd_margin_endpoint_probe_source_probe_stage089_jd_margin_endpoint_probe_v1.csv`
- gtja_rule_sample：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage089_jd_margin_endpoint_probe/rebuilt_c9_v2_stage089_jd_margin_endpoint_probe_gtja_rule_sample_stage089_jd_margin_endpoint_probe_v1.csv`
- gtja_adjustments：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage089_jd_margin_endpoint_probe/rebuilt_c9_v2_stage089_jd_margin_endpoint_probe_gtja_jd_adjustments_stage089_jd_margin_endpoint_probe_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage089_jd_margin_endpoint_probe/rebuilt_c9_v2_stage089_jd_margin_endpoint_probe_input_audit_stage089_jd_margin_endpoint_probe_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage089_jd_margin_endpoint_probe/rebuilt_c9_v2_stage089_jd_margin_endpoint_probe_decision_stage089_jd_margin_endpoint_probe_v1.json`
