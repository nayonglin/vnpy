# Stage090 GTJA JD margin batch gate

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T18:08:48
- 阶段性质：只读数据覆盖/解析验收；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- `gtja_calendar_public_page`：https://www.gtjaqh.com/pc/calendar?date=20260625；GTJA public calendar exposes margin ratio, limit ratio and special contract adjustments for JD.
- `akshare_futures_rule_docs`：https://akshare.akfamily.xyz/data/futures/futures.html；AKShare documents futures_rule as GTJA futures calendar with margin and special adjustment fields.
- `dce_daily_trading_parameters`：https://www.dce.com.cn/dceg/channel/list/488.html；DCE official daily trading parameters remain preferred if accessible; GTJA is a broker reconstruction route.

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage090_gtja_jd_margin_batch_gate.py`
- 新增参数：`sleep=0.02`、`timeout=10.0`、`max_dates=0`
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`stage090_gtja_batch_coverage_incomplete_not_accepted`
- full_required_run：`True`
- required_unique_dates：`1571`
- required_jd_day_rows：`1571`
- gtja_parse_ok_dates：`1465`
- candidate_daily_margin_rows：`1465`
- missing_candidate_daily_margin_rows：`106`
- adjustment_rows：`1671`
- accepted_candidate_count：`0`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Source Audit

| candidate_id                     | source_type                                   |   required_unique_dates |   parse_ok_dates |   required_rows |   candidate_rows |   missing_rows |   adjustment_rows | has_broker_margin_ratio   | has_exchange_margin_ratio   | has_source_hash   | has_publish_or_effective_time   | accepted_for_jd_contract_daily_margin_history   | pit_acceptance                 | reject_reason                                     | detail                                                                                                       |
|:---------------------------------|:----------------------------------------------|------------------------:|-----------------:|----------------:|-----------------:|---------------:|------------------:|:--------------------------|:----------------------------|:------------------|:--------------------------------|:------------------------------------------------|:-------------------------------|:--------------------------------------------------|:-------------------------------------------------------------------------------------------------------------|
| gtja_pc_calendar_direct_jd_batch | broker_calendar_margin_history_reconstruction |                    1571 |             1465 |            1571 |             1465 |            106 |              1671 | True                      | False                       | True              | False                           | False                                           | rebuild_candidate_not_accepted | missing_exchange_margin_or_publish_effective_time | GTJA direct page can reconstruct broker margin candidates for available dates; not accepted for true ledger. |

## Coverage Summary

| metric                             |   value | detail                                                                                                                                                                                                                                                                                                                                    |
|:-----------------------------------|--------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| required_jd_day_rows               |    1571 |                                                                                                                                                                                                                                                                                                                                           |
| required_unique_dates              |    1571 |                                                                                                                                                                                                                                                                                                                                           |
| gtja_parse_ok_dates                |    1465 |                                                                                                                                                                                                                                                                                                                                           |
| candidate_margin_dates             |    1465 |                                                                                                                                                                                                                                                                                                                                           |
| missing_candidate_dates            |     106 | 2020-01-02,2020-01-03,2020-01-06,2020-01-07,2020-01-08,2020-01-09,2020-01-10,2020-01-13,2020-01-14,2020-01-15,2020-01-16,2020-01-17,2020-01-20,2020-01-21,2020-01-22,2020-01-23,2020-02-03,2020-02-04,2020-02-05,2020-02-06,2020-02-07,2020-02-10,2020-02-11,2020-02-12,2020-02-13,2020-02-14,2020-02-17,2020-02-18,2020-02-19,2020-02-20 |
| candidate_daily_margin_rows        |    1465 |                                                                                                                                                                                                                                                                                                                                           |
| accepted_daily_margin_rows         |       0 |                                                                                                                                                                                                                                                                                                                                           |
| contract_count_with_candidate_rows |      40 |                                                                                                                                                                                                                                                                                                                                           |
| required_contract_count            |      41 |                                                                                                                                                                                                                                                                                                                                           |
| special_adjustment_required_rows   |       3 |                                                                                                                                                                                                                                                                                                                                           |

## Date Audit Samples

| trade_date   |   request_date | url                                              | requested_at        |   http_status |   response_bytes | response_sha256                                                  | parse_status   |   row_count |   jd_row_count |   jd_product_broker_margin_ratio | raw_adjustment   | error               |
|:-------------|---------------:|:-------------------------------------------------|:--------------------|--------------:|-----------------:|:-----------------------------------------------------------------|:---------------|------------:|---------------:|---------------------------------:|:-----------------|:--------------------|
| 2020-01-02   |       20200102 | https://www.gtjaqh.com/pc/calendar?date=20200102 | 2026-07-05T18:02:48 |           200 |            51971 | 7b3b5e8313c3ae4f3dc5beb2436dcc99d249cdbcea6215e7d896c781fd98dffd | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-03   |       20200103 | https://www.gtjaqh.com/pc/calendar?date=20200103 | 2026-07-05T18:02:49 |           200 |            51971 | 7c6779e751a8418119f2a93dca51e797f35fba480483ef27e3d29aa359f0ff2a | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-06   |       20200106 | https://www.gtjaqh.com/pc/calendar?date=20200106 | 2026-07-05T18:02:49 |           200 |            51971 | 9ffc1a53c4a4e1addd0fd3f26f0e0740faab8c0d03ccb6908ffd92e8109beb18 | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-07   |       20200107 | https://www.gtjaqh.com/pc/calendar?date=20200107 | 2026-07-05T18:02:49 |           200 |            51971 | 8535f84be14235db10d5c82973ad43f49f1f2c523fbf5c0a6167acf51ff01ef7 | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-08   |       20200108 | https://www.gtjaqh.com/pc/calendar?date=20200108 | 2026-07-05T18:02:49 |           200 |            51971 | fe57df837597faac47440418becc24e5892a86d49fc221d82cad75db1083b619 | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-09   |       20200109 | https://www.gtjaqh.com/pc/calendar?date=20200109 | 2026-07-05T18:02:49 |           200 |            51971 | 7bf29b7ac4b52dad3776a4fd7d98483f1d082341dad79db6686d39e68d26c48f | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-10   |       20200110 | https://www.gtjaqh.com/pc/calendar?date=20200110 | 2026-07-05T18:02:49 |           200 |            51971 | 6d30bc6ffadd595cab70e1d10a63dda88e61062563661b24b91497098ab9b17f | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-13   |       20200113 | https://www.gtjaqh.com/pc/calendar?date=20200113 | 2026-07-05T18:02:49 |           200 |            51971 | 5d358accdc46d13ca2a755998405fdc651377434f27f5282ad1af94190d67755 | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-14   |       20200114 | https://www.gtjaqh.com/pc/calendar?date=20200114 | 2026-07-05T18:02:49 |           200 |            51971 | d8bdd229544386d7a80a51542cdc9d34a7e6598dd740b04eb3e26a9fecb3e19d | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-15   |       20200115 | https://www.gtjaqh.com/pc/calendar?date=20200115 | 2026-07-05T18:02:50 |           200 |            51971 | 4421330b5cf7d34dec2aa621cae287d3446d746f934bab3433a9c696fdcdf41d | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-16   |       20200116 | https://www.gtjaqh.com/pc/calendar?date=20200116 | 2026-07-05T18:02:50 |           200 |            51971 | 16d9a6e694ebb8e0e1dd28d5feb2f269fbab5e5e0498161e21252ad5e68a7ecc | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-17   |       20200117 | https://www.gtjaqh.com/pc/calendar?date=20200117 | 2026-07-05T18:02:50 |           200 |            51971 | 66256f0b205dc7c7a4ff3627683f47cdc771ecd7fddb1969ad7bc59b8775067c | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-20   |       20200120 | https://www.gtjaqh.com/pc/calendar?date=20200120 | 2026-07-05T18:02:50 |           200 |            51971 | b680e73c4291513edb9b0617447eb3782a3c53059b225f34bef6bc910c8e78fc | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-21   |       20200121 | https://www.gtjaqh.com/pc/calendar?date=20200121 | 2026-07-05T18:02:50 |           200 |            51971 | f1ebaf63cad567bffa8dc94045a7b71ad8c3cde3ba366a7e6ebf47f39f8271a3 | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-22   |       20200122 | https://www.gtjaqh.com/pc/calendar?date=20200122 | 2026-07-05T18:02:50 |           200 |            51971 | 6c8607724a42e256493edcf195ee29858f9911ffe7014196ce6fb8c0210ab6a7 | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-01-23   |       20200123 | https://www.gtjaqh.com/pc/calendar?date=20200123 | 2026-07-05T18:02:50 |           200 |            51971 | 3ec00411ab23970ebec8ca7b25bfd060949baea3c23d0c1b3710e90904347b05 | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-02-03   |       20200203 | https://www.gtjaqh.com/pc/calendar?date=20200203 | 2026-07-05T18:02:50 |           200 |            51900 | 06737bac7fefde3fcaec680f34ae500cd34bcc140e6ace56f8600009de9455c9 | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-02-04   |       20200204 | https://www.gtjaqh.com/pc/calendar?date=20200204 | 2026-07-05T18:02:50 |           200 |            51900 | 88e282468b16e8b80b30ad897043082a87072b9eb17b3d5909346546ab23f4f6 | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-02-05   |       20200205 | https://www.gtjaqh.com/pc/calendar?date=20200205 | 2026-07-05T18:02:51 |           200 |            51900 | 0c4429b9e5dc96455b0fd91a280250916fb2cb669a3fe5500df5f1549bdf3cbb | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |
| 2020-02-06   |       20200206 | https://www.gtjaqh.com/pc/calendar?date=20200206 | 2026-07-05T18:02:51 |           200 |            51900 | 43f0760efa8e161ea4d2831a47c3f2e626dbcf50628fa6a97bddfdb29faf4871 | no_rule_table  |           0 |              0 |                              nan |                  | no rule table found |

## Candidate Daily Margin Samples

| trade_date   | contract_vt   |   exchange_margin_ratio |   broker_margin_ratio |   jd_product_broker_margin_ratio |   special_broker_margin_ratio |   special_raw_adjustment |   source_system |   source_response_hash |   url | publish_or_effective_time   | accepted_for_jd_contract_daily_margin_history   | pit_acceptance   | blocking_reason                      |
|:-------------|:--------------|------------------------:|----------------------:|---------------------------------:|------------------------------:|-------------------------:|----------------:|-----------------------:|------:|:----------------------------|:------------------------------------------------|:-----------------|:-------------------------------------|
| 2020-01-02   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-03   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-06   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-07   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-08   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-09   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-10   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-13   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-14   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-15   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-16   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-17   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-20   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-21   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-22   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-01-23   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-03   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-04   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-05   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-06   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-07   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-10   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-11   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-12   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-13   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-14   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-17   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-18   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-19   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |
| 2020-02-20   | jd2005.DCE    |                     nan |                   nan |                              nan |                           nan |                      nan |             nan |                    nan |   nan |                             | False                                           | missing          | missing_gtja_margin_for_required_day |

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

## 独立 agent 审查

- 审查 agent：`019f31c1-b06a-76c2-a65c-fe21ba345fde`
- 审查时间：2026-07-05 18:15 CST 左右
- 置信度：`0.90`
- 结论：Stage090 大方向正确，不应 accepted，不应跑 true ledger，应继续找 DCE/vendor 官方逐日参数；不建议把 GTJA 直接接入 true ledger。
- 严重风险：未发现脚本触碰官方实盘、CTP、邮件、launchd、真实引擎或下单路径；但若未来绕过 `accepted=False` 把 GTJA broker margin 当 `exchange_margin_ratio` 接 true ledger，则是严重风险。当前 CSV 的 `exchange_margin_ratio`、`publish_or_effective_time` 为空，`accepted=False` 已挡住。
- 中等风险：统计主口径可复核，`required_unique_dates=1571`、`gtja_parse_ok_dates=1465`、`candidate_daily_margin_rows=1465`、`missing=106`、`adjustment_rows=1671`、`accepted=0` 与 CSV 一致；但 `special_adjustment_required_rows=3` 只是当前解析器口径。GTJA 页面存在 `JD2005保证金24% JD2006保证金14%` 这种紧凑格式，当前正则未解析，真实主力特调命中至少应从 `3` 增到 `5`，进一步支持“不接入”。
- 低风险：日期请求修复正确，输出 `trade_date` 为 ISO，实际请求 `request_date` 为 `YYYYMMDD`；`header=1` 与 AKShare 对 GTJA calendar 的解析方式一致。
- 建议：GTJA 仅保留为 broker margin reconstruction 候选和交叉核验源；下一步转向 DCE 官方或 vendor/TqSdk/RQData 等能提供 `exchange_margin_ratio`、发布时间/生效时间、原始文件/hash、连续覆盖的数据合同。
- 审查后过拟合反思：否。该阶段是数据合同审查，没有看收益和调参。
- 审查后继续价值反思：有，但价值在补官方/授权数据合同，不在继续救 GTJA parser 到可上线。
