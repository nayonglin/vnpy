# Stage040 TqSdk 期权历史链 readiness 审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T09:22:57
- 阶段性质：授权 vendor 期权历史数据源 readiness；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk 官方介绍、TqSdk 专业版文档、DataDownloader 文档、TqSdk GitHub。
- 我的判断：DataDownloader 覆盖期货/期权/股票历史数据，是 DCE 公共端点失败后的合理 vendor 路线；但它是专业版能力，必须用 `TqAuth` 证明权限，再冻结下载 manifest、hash、PIT 发布时间和连续日历，不能把“已安装/有凭证”直接当成交易特征。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage040_tqsdk_option_history_readiness.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage040_tqsdk_option_history_readiness.py`
- 新增参数：`STAGE040_ENABLE_NETWORK_PROBE=0`、`STAGE040_NETWORK_PROBE_SYMBOL=CZCE.SR901`、`STAGE040_NETWORK_PROBE_START=2018-01-02`、`STAGE040_NETWORK_PROBE_END=2018-01-03`、`STAGE040_NETWORK_PROBE_DUR_SEC=86400`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage040_tqsdk_option_history_not_ready_credentials_or_permission_required`
- best_next_direction：`obtain_or_configure_tqsdk_professional_credentials_or_switch_vendor_source`
- schema_ready_source_count：`0`
- credential_pair_present_count：`0`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Module audit

| module_importable   | module_version   | module_file                                                                                | has_tqapi   | has_tqauth   | has_tqsim   | has_data_downloader   | import_error_type   | import_error_message   | import_notice_captured   |
|:--------------------|:-----------------|:-------------------------------------------------------------------------------------------|:------------|:-------------|:------------|:----------------------|:--------------------|:-----------------------|:-------------------------|
| True                | 3.9.4            | /Users/bytedance/Desktop/person/vnpy/.py311/lib/python3.11/site-packages/tqsdk/__init__.py | True        | True         | True        | True                  |                     |                        | True                     |

## Credential audit（已脱敏）

| credential_key   | source_type   | source_path                                                        | source_exists   | present   | redacted_value   |
|:-----------------|:--------------|:-------------------------------------------------------------------|:----------------|:----------|:-----------------|
| TQSDK_ACCOUNT    | environment   |                                                                    | True            | False     |                  |
| TQSDK_PASSWORD   | environment   |                                                                    | True            | False     |                  |
| TQSDK_USER       | environment   |                                                                    | True            | False     |                  |
| TQSDK_PASS       | environment   |                                                                    | True            | False     |                  |
| TQ_USERNAME      | environment   |                                                                    | True            | False     |                  |
| TQ_PASSWORD      | environment   |                                                                    | True            | False     |                  |
| TQ_USER          | environment   |                                                                    | True            | False     |                  |
| TQAUTH_USER      | environment   |                                                                    | True            | False     |                  |
| TQAUTH_PASSWORD  | environment   |                                                                    | True            | False     |                  |
| TQSDK_ACCOUNT    | env_file      | /Users/bytedance/Desktop/person/vnpy/tqsdk.local.env               | False           | False     |                  |
| TQSDK_PASSWORD   | env_file      | /Users/bytedance/Desktop/person/vnpy/tqsdk.local.env               | False           | False     |                  |
| TQSDK_USER       | env_file      | /Users/bytedance/Desktop/person/vnpy/tqsdk.local.env               | False           | False     |                  |
| TQSDK_PASS       | env_file      | /Users/bytedance/Desktop/person/vnpy/tqsdk.local.env               | False           | False     |                  |
| TQ_USERNAME      | env_file      | /Users/bytedance/Desktop/person/vnpy/tqsdk.local.env               | False           | False     |                  |
| TQ_PASSWORD      | env_file      | /Users/bytedance/Desktop/person/vnpy/tqsdk.local.env               | False           | False     |                  |
| TQ_USER          | env_file      | /Users/bytedance/Desktop/person/vnpy/tqsdk.local.env               | False           | False     |                  |
| TQAUTH_USER      | env_file      | /Users/bytedance/Desktop/person/vnpy/tqsdk.local.env               | False           | False     |                  |
| TQAUTH_PASSWORD  | env_file      | /Users/bytedance/Desktop/person/vnpy/tqsdk.local.env               | False           | False     |                  |
| TQSDK_ACCOUNT    | env_file      | /Users/bytedance/Desktop/person/vnpy/official_live_tqsdk.local.env | False           | False     |                  |
| TQSDK_PASSWORD   | env_file      | /Users/bytedance/Desktop/person/vnpy/official_live_tqsdk.local.env | False           | False     |                  |
| TQSDK_USER       | env_file      | /Users/bytedance/Desktop/person/vnpy/official_live_tqsdk.local.env | False           | False     |                  |
| TQSDK_PASS       | env_file      | /Users/bytedance/Desktop/person/vnpy/official_live_tqsdk.local.env | False           | False     |                  |
| TQ_USERNAME      | env_file      | /Users/bytedance/Desktop/person/vnpy/official_live_tqsdk.local.env | False           | False     |                  |
| TQ_PASSWORD      | env_file      | /Users/bytedance/Desktop/person/vnpy/official_live_tqsdk.local.env | False           | False     |                  |
| TQ_USER          | env_file      | /Users/bytedance/Desktop/person/vnpy/official_live_tqsdk.local.env | False           | False     |                  |
| TQAUTH_USER      | env_file      | /Users/bytedance/Desktop/person/vnpy/official_live_tqsdk.local.env | False           | False     |                  |
| TQAUTH_PASSWORD  | env_file      | /Users/bytedance/Desktop/person/vnpy/official_live_tqsdk.local.env | False           | False     |                  |
| TQSDK_ACCOUNT    | env_file      | /Users/bytedance/Desktop/person/vnpy/ctp_live.local.env            | False           | False     |                  |
| TQSDK_PASSWORD   | env_file      | /Users/bytedance/Desktop/person/vnpy/ctp_live.local.env            | False           | False     |                  |
| TQSDK_USER       | env_file      | /Users/bytedance/Desktop/person/vnpy/ctp_live.local.env            | False           | False     |                  |
| TQSDK_PASS       | env_file      | /Users/bytedance/Desktop/person/vnpy/ctp_live.local.env            | False           | False     |                  |
| TQ_USERNAME      | env_file      | /Users/bytedance/Desktop/person/vnpy/ctp_live.local.env            | False           | False     |                  |
| TQ_PASSWORD      | env_file      | /Users/bytedance/Desktop/person/vnpy/ctp_live.local.env            | False           | False     |                  |
| TQ_USER          | env_file      | /Users/bytedance/Desktop/person/vnpy/ctp_live.local.env            | False           | False     |                  |
| TQAUTH_USER      | env_file      | /Users/bytedance/Desktop/person/vnpy/ctp_live.local.env            | False           | False     |                  |
| TQAUTH_PASSWORD  | env_file      | /Users/bytedance/Desktop/person/vnpy/ctp_live.local.env            | False           | False     |                  |
| TQSDK_ACCOUNT    | env_file      | /Users/bytedance/Desktop/person/vnpy/.env                          | False           | False     |                  |
| TQSDK_PASSWORD   | env_file      | /Users/bytedance/Desktop/person/vnpy/.env                          | False           | False     |                  |
| TQSDK_USER       | env_file      | /Users/bytedance/Desktop/person/vnpy/.env                          | False           | False     |                  |
| TQSDK_PASS       | env_file      | /Users/bytedance/Desktop/person/vnpy/.env                          | False           | False     |                  |
| TQ_USERNAME      | env_file      | /Users/bytedance/Desktop/person/vnpy/.env                          | False           | False     |                  |
| TQ_PASSWORD      | env_file      | /Users/bytedance/Desktop/person/vnpy/.env                          | False           | False     |                  |
| TQ_USER          | env_file      | /Users/bytedance/Desktop/person/vnpy/.env                          | False           | False     |                  |
| TQAUTH_USER      | env_file      | /Users/bytedance/Desktop/person/vnpy/.env                          | False           | False     |                  |
| TQAUTH_PASSWORD  | env_file      | /Users/bytedance/Desktop/person/vnpy/.env                          | False           | False     |                  |

## Permission probe

| network_probe_enabled   | permission_probe_symbol   | permission_probe_start   | permission_probe_end   |   permission_probe_dur_sec | permission_probe_status   |   download_probe_rows | download_probe_file_created   | error_type   | error_message   |
|:------------------------|:--------------------------|:-------------------------|:-----------------------|---------------------------:|:--------------------------|----------------------:|:------------------------------|:-------------|:----------------|
| False                   | CZCE.SR901                | 2018-01-02               | 2018-01-03             |                      86400 | skipped_no_credentials    |                     0 | False                         |              |                 |

## Readiness

| source_name           | module_importable   | module_version   | has_tqapi   | has_tqauth   | has_tqsim   | has_data_downloader   | credential_pair_present   | permission_probe_status   | readiness_status                                    | schema_ready_source   | rule_candidate_allowed   | blocking_reasons           |
|:----------------------|:--------------------|:-----------------|:------------|:-------------|:------------|:----------------------|:--------------------------|:--------------------------|:----------------------------------------------------|:----------------------|:-------------------------|:---------------------------|
| tqsdk_data_downloader | True                | 3.9.4            | True        | True         | True        | True                  | False                     | skipped_no_credentials    | installed_but_credentials_missing_no_download_probe | False                 | False                    | tqauth_credentials_missing |

## 过拟合反思

- 运行前判断：否。本阶段只审计授权数据源可得性，不做收益回测、不调阈值、不选品种方向。
- 运行后判断：否。输出仍停在数据合同和权限 readiness，没有把单次探针或安装状态交易化。

## 继续价值反思

- 运行前判断：有。Stage039 已证 DCE 公共端点不可恢复，授权 vendor 是期权路线继续前必须确认的现实路径。
- 运行后判断：有但前提明确：只有拿到权限并冻结 manifest/hash/日历后，才值得进入 IV/skew 只读信号审计。

## 输出文件

- module_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage040_tqsdk_option_history_readiness/rebuilt_c9_v2_stage040_tqsdk_option_history_readiness_module_audit_stage040_tqsdk_option_history_readiness_v1.csv`
- credential_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage040_tqsdk_option_history_readiness/rebuilt_c9_v2_stage040_tqsdk_option_history_readiness_credential_audit_stage040_tqsdk_option_history_readiness_v1.csv`
- probe_plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage040_tqsdk_option_history_readiness/rebuilt_c9_v2_stage040_tqsdk_option_history_readiness_probe_plan_stage040_tqsdk_option_history_readiness_v1.csv`
- permission_probe：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage040_tqsdk_option_history_readiness/rebuilt_c9_v2_stage040_tqsdk_option_history_readiness_permission_probe_stage040_tqsdk_option_history_readiness_v1.csv`
- readiness：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage040_tqsdk_option_history_readiness/rebuilt_c9_v2_stage040_tqsdk_option_history_readiness_readiness_stage040_tqsdk_option_history_readiness_v1.csv`
- data_contract：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage040_tqsdk_option_history_readiness/rebuilt_c9_v2_stage040_tqsdk_option_history_readiness_data_contract_stage040_tqsdk_option_history_readiness_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage040_tqsdk_option_history_readiness/rebuilt_c9_v2_stage040_tqsdk_option_history_readiness_decision_stage040_tqsdk_option_history_readiness_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage040_tqsdk_option_history_readiness/rebuilt_c9_v2_stage040_tqsdk_option_history_readiness_report_stage040_tqsdk_option_history_readiness_v1.md`
