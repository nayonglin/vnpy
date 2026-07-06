# Stage090 GTJA JD margin batch gate

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T17:57:07
- 阶段性质：只读数据覆盖/解析验收；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- `gtja_calendar_public_page`：https://www.gtjaqh.com/pc/calendar?date=20260625；GTJA public calendar exposes margin ratio, limit ratio and special contract adjustments for JD.
- `akshare_futures_rule_docs`：https://akshare.akfamily.xyz/data/futures/futures.html；AKShare documents futures_rule as GTJA futures calendar with margin and special adjustment fields.
- `dce_daily_trading_parameters`：https://www.dce.com.cn/dceg/channel/list/488.html；DCE official daily trading parameters remain preferred if accessible; GTJA is a broker reconstruction route.

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage090_gtja_jd_margin_batch_gate.py`
- 新增参数：`sleep=0.0`、`timeout=10.0`、`max_dates=8`
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage090_gtja_batch_coverage_incomplete_not_accepted`
- full_required_run：`False`
- required_unique_dates：`8`
- required_jd_day_rows：`8`
- gtja_parse_ok_dates：`0`
- candidate_daily_margin_rows：`0`
- missing_candidate_daily_margin_rows：`8`
- adjustment_rows：`0`
- accepted_candidate_count：`0`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Source Audit

| candidate_id                     | source_type                                   |   required_unique_dates |   parse_ok_dates |   required_rows |   candidate_rows |   missing_rows |   adjustment_rows | has_broker_margin_ratio   | has_exchange_margin_ratio   | has_source_hash   | has_publish_or_effective_time   | accepted_for_jd_contract_daily_margin_history   | pit_acceptance   | reject_reason                                     | detail                                                                                                       |
|:---------------------------------|:----------------------------------------------|------------------------:|-----------------:|----------------:|-----------------:|---------------:|------------------:|:--------------------------|:----------------------------|:------------------|:--------------------------------|:------------------------------------------------|:-----------------|:--------------------------------------------------|:-------------------------------------------------------------------------------------------------------------|
| gtja_pc_calendar_direct_jd_batch | broker_calendar_margin_history_reconstruction |                       8 |                0 |               8 |                0 |              8 |                 0 | False                     | False                       | True              | False                           | False                                           | rejected         | missing_exchange_margin_or_publish_effective_time | GTJA direct page can reconstruct broker margin candidates for available dates; not accepted for true ledger. |

## Coverage Summary

| metric                             |   value | detail                                                                                  |
|:-----------------------------------|--------:|:----------------------------------------------------------------------------------------|
| required_jd_day_rows               |       8 |                                                                                         |
| required_unique_dates              |       8 |                                                                                         |
| gtja_parse_ok_dates                |       0 |                                                                                         |
| candidate_margin_dates             |       0 |                                                                                         |
| missing_candidate_dates            |       8 | 2020-01-02,2020-01-03,2020-01-06,2020-01-07,2020-01-08,2020-01-09,2020-01-10,2020-01-13 |
| candidate_daily_margin_rows        |       0 |                                                                                         |
| accepted_daily_margin_rows         |       0 |                                                                                         |
| contract_count_with_candidate_rows |       0 |                                                                                         |
| required_contract_count            |       1 |                                                                                         |
| special_adjustment_required_rows   |       0 |                                                                                         |

## Date Audit Samples

| trade_date   | url                                                | requested_at        |   http_status |   response_bytes | response_sha256                                                  | parse_status   |   row_count |   jd_row_count | jd_product_broker_margin_ratio   | raw_adjustment   | error               |
|:-------------|:---------------------------------------------------|:--------------------|--------------:|-----------------:|:-----------------------------------------------------------------|:---------------|------------:|---------------:|:---------------------------------|:-----------------|:--------------------|
| 2020-01-02   | https://www.gtjaqh.com/pc/calendar?date=2020-01-02 | 2026-07-05T17:57:06 |           200 |            51889 | 50e9d5d425fb3fdab24eea506ce576ecf3667419ba018c55f66c74868db514fc | no_rule_table  |           0 |              0 |                                  |                  | no rule table found |
| 2020-01-03   | https://www.gtjaqh.com/pc/calendar?date=2020-01-03 | 2026-07-05T17:57:07 |           200 |            51889 | f759ce5f2193db68fd82f1ca9f276121b0e7c450c865eb4c63b6083855907e54 | no_rule_table  |           0 |              0 |                                  |                  | no rule table found |
| 2020-01-06   | https://www.gtjaqh.com/pc/calendar?date=2020-01-06 | 2026-07-05T17:57:07 |           200 |            51889 | e54c17ebed1d2c15abf148322fe4b4a4e6385d5a70571438a3079066251874b0 | no_rule_table  |           0 |              0 |                                  |                  | no rule table found |
| 2020-01-07   | https://www.gtjaqh.com/pc/calendar?date=2020-01-07 | 2026-07-05T17:57:07 |           200 |            51889 | c98285d6248df1321a7f7b325c07fb170399e80edc148c7ce360948948ff0158 | no_rule_table  |           0 |              0 |                                  |                  | no rule table found |
| 2020-01-08   | https://www.gtjaqh.com/pc/calendar?date=2020-01-08 | 2026-07-05T17:57:07 |           200 |            51889 | 5282f7e3e83ac69b81087dfa713898453503df14f9d8e34c3643850874e2f412 | no_rule_table  |           0 |              0 |                                  |                  | no rule table found |
| 2020-01-09   | https://www.gtjaqh.com/pc/calendar?date=2020-01-09 | 2026-07-05T17:57:07 |           200 |            51889 | 3573c072ca852349b0af7ca4e74fa06e0c98f340f62d5c59e4114aadc415c586 | no_rule_table  |           0 |              0 |                                  |                  | no rule table found |
| 2020-01-10   | https://www.gtjaqh.com/pc/calendar?date=2020-01-10 | 2026-07-05T17:57:07 |           200 |            51889 | 49617bd3adc8fa7c606c0889adcf5780bda44b966d036e6b49d6f80e8da13cd0 | no_rule_table  |           0 |              0 |                                  |                  | no rule table found |
| 2020-01-13   | https://www.gtjaqh.com/pc/calendar?date=2020-01-13 | 2026-07-05T17:57:07 |           200 |            51889 | 475790d6adb3ff21111eb7da2d711f1fa2607748f32d5fe4a913f8f980563ad3 | no_rule_table  |           0 |              0 |                                  |                  | no rule table found |

## Candidate Daily Margin Samples

| trade_date   | contract_vt   |   exchange_margin_ratio |   broker_margin_ratio |   jd_product_broker_margin_ratio |   special_broker_margin_ratio | special_raw_adjustment   |   source_system |   source_response_hash |   url | publish_or_effective_time   | accepted_for_jd_contract_daily_margin_history   | pit_acceptance   | blocking_reason                      |
|:-------------|:--------------|------------------------:|----------------------:|---------------------------------:|------------------------------:|:-------------------------|----------------:|-----------------------:|------:|:----------------------------|:------------------------------------------------|:-----------------|:-------------------------------------|
| 2020-01-02   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                          |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-03   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                          |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-06   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                          |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-07   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                          |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-08   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                          |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-09   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                          |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-10   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                          |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-13   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                          |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。只做数据覆盖和解析验收，不看收益、不调规则。
- 运行后：否。结果继续停在数据闸门，没有把 broker 样本直接用于策略。

## 继续价值反思

- 运行前：有。Stage089 reviewer 建议把 GTJA 路线一次性验清。
- 运行后：有条件。若覆盖不完整，应优先找 DCE/vendor；若覆盖完整，仍要补 exchange margin 或明确 broker-margin-only 的验收政策。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage090_gtja_jd_margin_batch_gate/rebuilt_c9_v2_stage090_gtja_jd_margin_batch_gate_report_stage090_gtja_jd_margin_batch_gate_v1.md`
- source_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage090_gtja_jd_margin_batch_gate/rebuilt_c9_v2_stage090_gtja_jd_margin_batch_gate_source_audit_stage090_gtja_jd_margin_batch_gate_v1.csv`
- required_jd_days：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage090_gtja_jd_margin_batch_gate/rebuilt_c9_v2_stage090_gtja_jd_margin_batch_gate_required_jd_days_stage090_gtja_jd_margin_batch_gate_v1.csv`
- gtja_date_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage090_gtja_jd_margin_batch_gate/rebuilt_c9_v2_stage090_gtja_jd_margin_batch_gate_gtja_date_audit_stage090_gtja_jd_margin_batch_gate_v1.csv`
- gtja_adjustments：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage090_gtja_jd_margin_batch_gate/rebuilt_c9_v2_stage090_gtja_jd_margin_batch_gate_gtja_adjustments_stage090_gtja_jd_margin_batch_gate_v1.csv`
- candidate_daily_margin：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage090_gtja_jd_margin_batch_gate/rebuilt_c9_v2_stage090_gtja_jd_margin_batch_gate_candidate_daily_margin_stage090_gtja_jd_margin_batch_gate_v1.csv`
- coverage_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage090_gtja_jd_margin_batch_gate/rebuilt_c9_v2_stage090_gtja_jd_margin_batch_gate_coverage_summary_stage090_gtja_jd_margin_batch_gate_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage090_gtja_jd_margin_batch_gate/rebuilt_c9_v2_stage090_gtja_jd_margin_batch_gate_input_audit_stage090_gtja_jd_margin_batch_gate_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage090_gtja_jd_margin_batch_gate/rebuilt_c9_v2_stage090_gtja_jd_margin_batch_gate_decision_stage090_gtja_jd_margin_batch_gate_v1.json`
