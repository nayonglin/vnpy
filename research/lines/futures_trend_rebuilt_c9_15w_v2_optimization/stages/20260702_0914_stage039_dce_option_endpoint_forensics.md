# Stage039 DCE 商品期权端点法证

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T09:14:21
- 阶段性质：只读端点法证/复水候选审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：AKShare 主分支 `cons.py`、AKShare 期权文档、DCE 官网、CEIC DCE 期权持仓日频说明、DCE 旧导出端点抓包资料。
- 我的判断：Stage038 的 DCE `JSONDecodeError` 更像当前 JSON 端点或调用方式失效；鸡蛋期权数据本身存在，但公共端点能否稳定复水还要靠旧 export parser、hash、发布时间和连续覆盖证明。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage039_dce_option_endpoint_forensics.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage039_dce_option_endpoint_forensics.py`
- 新增参数：`STAGE039_ENABLE_NETWORK_PROBE=1`、`STAGE039_REQUEST_TIMEOUT_SECONDS=15`、`STAGE039_MAX_PROBES=20`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage039_dce_endpoint_no_recovery_candidate_switch_source`
- best_next_direction：`use_vendor_or_tqsdk_history_for_dce_options`
- probe_count：`20`
- json_endpoint_failure_count：`5`
- endpoint_recovery_candidate_count：`0`
- schema_ready_probe_count：`0`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Endpoint family summary

| endpoint_family        |   probe_count |   http_200_count |   parseable_probe_count |   endpoint_recovery_candidate_count |   schema_ready_probe_count | probe_statuses                                                                    | blocking_reasons                                                    |
|:-----------------------|--------------:|-----------------:|------------------------:|------------------------------------:|---------------------------:|:----------------------------------------------------------------------------------|:--------------------------------------------------------------------|
| akshare_json_dcereport |            10 |                0 |                       0 |                                   0 |                          0 | endpoint_probe_failed,json_endpoint_not_returning_json_needs_alternative_endpoint | dce_json_endpoint_not_json,http_412_or_error_non_json,request_error |
| legacy_export_form     |            10 |                0 |                       0 |                                   0 |                          0 | endpoint_probe_failed                                                             | probe_not_ok,request_error                                          |

## Probe results

| probe_id                      | target_product   | endpoint_family        |   http_status | content_type             |   body_size |   parseable_rows | parse_method   | probe_status                                                | blocking_reasons                                      |
|:------------------------------|:-----------------|:-----------------------|--------------:|:-------------------------|------------:|-----------------:|:---------------|:------------------------------------------------------------|:------------------------------------------------------|
| jd_DCE_json_20251016_http     | jd.DCE           | akshare_json_dcereport |           412 | text/html; charset=utf-8 |        3131 |                0 | text_utf-8     | json_endpoint_not_returning_json_needs_alternative_endpoint | dce_json_endpoint_not_json,http_412_or_error_non_json |
| jd_DCE_json_20251016_https    | jd.DCE           | akshare_json_dcereport |             0 |                          |           0 |                0 |                | endpoint_probe_failed                                       | request_error                                         |
| jd_DCE_legacy_20251016_www    | jd.DCE           | legacy_export_form     |           412 | text/html; charset=utf-8 |        3151 |                0 | text_utf-8     | endpoint_probe_failed                                       | probe_not_ok                                          |
| jd_DCE_legacy_20251016_portal | jd.DCE           | legacy_export_form     |             0 |                          |           0 |                0 |                | endpoint_probe_failed                                       | request_error                                         |
| jd_DCE_json_20260629_http     | jd.DCE           | akshare_json_dcereport |           412 | text/html; charset=utf-8 |        3143 |                0 | text_utf-8     | json_endpoint_not_returning_json_needs_alternative_endpoint | dce_json_endpoint_not_json,http_412_or_error_non_json |
| jd_DCE_json_20260629_https    | jd.DCE           | akshare_json_dcereport |             0 |                          |           0 |                0 |                | endpoint_probe_failed                                       | request_error                                         |
| jd_DCE_legacy_20260629_www    | jd.DCE           | legacy_export_form     |           412 | text/html; charset=utf-8 |        3145 |                0 | text_utf-8     | endpoint_probe_failed                                       | probe_not_ok                                          |
| jd_DCE_legacy_20260629_portal | jd.DCE           | legacy_export_form     |             0 |                          |           0 |                0 |                | endpoint_probe_failed                                       | request_error                                         |
| lh_DCE_json_20251016_http     | lh.DCE           | akshare_json_dcereport |           412 | text/html; charset=utf-8 |        3241 |                0 | text_utf-8     | json_endpoint_not_returning_json_needs_alternative_endpoint | dce_json_endpoint_not_json,http_412_or_error_non_json |
| lh_DCE_json_20251016_https    | lh.DCE           | akshare_json_dcereport |             0 |                          |           0 |                0 |                | endpoint_probe_failed                                       | request_error                                         |
| lh_DCE_legacy_20251016_www    | lh.DCE           | legacy_export_form     |           412 | text/html; charset=utf-8 |        3141 |                0 | text_utf-8     | endpoint_probe_failed                                       | probe_not_ok                                          |
| lh_DCE_legacy_20251016_portal | lh.DCE           | legacy_export_form     |             0 |                          |           0 |                0 |                | endpoint_probe_failed                                       | request_error                                         |
| m_DCE_json_20240603_http      | m.DCE            | akshare_json_dcereport |           412 | text/html; charset=utf-8 |        3137 |                0 | text_utf-8     | json_endpoint_not_returning_json_needs_alternative_endpoint | dce_json_endpoint_not_json,http_412_or_error_non_json |
| m_DCE_json_20240603_https     | m.DCE            | akshare_json_dcereport |             0 |                          |           0 |                0 |                | endpoint_probe_failed                                       | request_error                                         |
| m_DCE_legacy_20240603_www     | m.DCE            | legacy_export_form     |           412 | text/html; charset=utf-8 |        3107 |                0 | text_utf-8     | endpoint_probe_failed                                       | probe_not_ok                                          |
| m_DCE_legacy_20240603_portal  | m.DCE            | legacy_export_form     |             0 |                          |           0 |                0 |                | endpoint_probe_failed                                       | request_error                                         |
| pp_DCE_json_20251016_http     | pp.DCE           | akshare_json_dcereport |           412 | text/html; charset=utf-8 |        3099 |                0 | text_utf-8     | json_endpoint_not_returning_json_needs_alternative_endpoint | dce_json_endpoint_not_json,http_412_or_error_non_json |
| pp_DCE_json_20251016_https    | pp.DCE           | akshare_json_dcereport |             0 |                          |           0 |                0 |                | endpoint_probe_failed                                       | request_error                                         |
| pp_DCE_legacy_20251016_www    | pp.DCE           | legacy_export_form     |           412 | text/html; charset=utf-8 |        3153 |                0 | text_utf-8     | endpoint_probe_failed                                       | probe_not_ok                                          |
| pp_DCE_legacy_20251016_portal | pp.DCE           | legacy_export_form     |             0 |                          |           0 |                0 |                | endpoint_probe_failed                                       | request_error                                         |

## 过拟合反思

- 运行前判断：否。本阶段只定位 DCE 端点和导出接口，不做收益回测、不修改策略规则。
- 运行后判断：否。即使旧导出端点可解析，也只作为数据工程候选，不把返回行直接当 AI 特征。

## 继续价值反思

- 运行前判断：有。鸡蛋进入基础池后，DCE 期权链能否复水会影响新 PIT 信息源路线。
- 运行后判断：有但仍是数据工程价值；下一步必须先做 parser、hash、发布时间和连续覆盖，才能讨论 IV/skew 或 AI 选品。

## 输出文件

- probe_plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage039_dce_option_endpoint_forensics/rebuilt_c9_v2_stage039_dce_option_endpoint_forensics_probe_plan_stage039_dce_option_endpoint_forensics_v1.csv`
- probe_results：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage039_dce_option_endpoint_forensics/rebuilt_c9_v2_stage039_dce_option_endpoint_forensics_probe_results_stage039_dce_option_endpoint_forensics_v1.csv`
- family_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage039_dce_option_endpoint_forensics/rebuilt_c9_v2_stage039_dce_option_endpoint_forensics_family_summary_stage039_dce_option_endpoint_forensics_v1.csv`
- data_contract：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage039_dce_option_endpoint_forensics/rebuilt_c9_v2_stage039_dce_option_endpoint_forensics_data_contract_stage039_dce_option_endpoint_forensics_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage039_dce_option_endpoint_forensics/rebuilt_c9_v2_stage039_dce_option_endpoint_forensics_decision_stage039_dce_option_endpoint_forensics_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage039_dce_option_endpoint_forensics/rebuilt_c9_v2_stage039_dce_option_endpoint_forensics_report_stage039_dce_option_endpoint_forensics_v1.md`
