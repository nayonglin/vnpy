# Stage118 W0 verifier selftest

## 基本信息

- 时间：2026-06-20 17:59
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 阶段性质：W0 verifier 合成数据自测；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage118_verifier_selftest_passed_no_strategy_no_real_data`
- 重要突破版本：否。它证明 Stage117 verifier 的正/负例边界，但没有任何真实 W0 授权数据到货。

## 开始前反思

- 是否在过拟合：否。本阶段只用合成 fixture 测验验收器，不读取收益标签、不筛品种、不生成交易规则。
- 是否还有价值继续：是。Stage117 能识别缺数据，但还需要证明“完整证据会放行、局部坏证据会阻断”，否则未来真实 W0 到货时验收工具本身可能成为薄弱环节。

## 外部调研与判断

- pytest `tmp_path` 文档强调测试用临时/隔离目录。判断：Stage118 的 synthetic fixture 必须独立放在 Stage118 输出目录，不能混入真实数据目录。
- Apache Arrow/Parquet 文档和 `write_table/read_metadata` API 支持写入并读取 Parquet schema/metadata。判断：自测应写出真实 Parquet 文件，覆盖 Stage117 的 footer/schema 读取路径。
- Python `tempfile` 和测试隔离资料强调测试资源不应污染生产状态。判断：合成 raw/parquet/proof 只能作为 verifier selftest，不得进入 Stage112/113 或任何策略研究。

调研结论：验收器不能只测失败路径。必须同时有完整正例和最小负例，才能证明未来 W0 manifest 的放行和阻断都是机械、可复验的。

参考链接：

- https://docs.pytest.org/en/stable/how-to/tmp_path.html
- https://arrow.apache.org/docs/python/parquet.html
- https://arrow.apache.org/docs/python/generated/pyarrow.parquet.write_table.html
- https://arrow.apache.org/docs/python/generated/pyarrow.parquet.read_metadata.html
- https://docs.python.org/3/library/tempfile.html

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage118_wave0_verifier_selftest.py`
- 修改工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage117_wave0_delivery_verifier.py`
  - 当且仅当全部 W0 request hard accept 时，`stage112_intake_allowed_now` 自动变为 `1`。
  - 默认空 manifest 仍输出 `stage117_wave0_delivery_missing_no_data_no_rule` 和 `stage112_intake_allowed_now=0`。
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage118_wave0_verifier_selftest/`
- 新增合成 fixture：
  - `synthetic_valid_manifest`：41 个 request 均有 synthetic raw/parquet/proof，sha256 正确。
  - `synthetic_bad_sha_manifest`：仅第一个 request 的 raw sha256 错误。

## 参数与结果变更

- 新增自测 case：
  - `empty_manifest_negative`
  - `synthetic_valid_positive`
  - `synthetic_bad_sha_negative`
- 新增参数：
  - `positive_case_stage112_allowed=1`
  - `empty_case_stage112_allowed=0`
  - `bad_sha_case_stage112_allowed=0`
  - `real_w0_data_delivered=0`
  - `real_stage112_intake_allowed_now=0`
- 修改参数：Stage117 的 `stage112_intake_allowed` gate 改为由 `all_requests_hard_accept` 派生。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前路径资金曲线做 verifier selftest 视觉检查。
- 修改回测结果：无。
- 删除回测结果：无。

当前路径指标保持不变：

| 指标 | 数值 |
| --- | ---: |
| 期末权益 | 39,176,437.60 |
| 总收益 | 26017.6251% |
| 最大回撤 | -45.0827% |
| Sharpe | 1.6331 |
| 总滑点 | 2,730,130 |
| 总交易次数 | 787 |
| 胜率 | 36.0902% |
| broker10 峰值 | 111.7365% |

## 关键结果

| 项目 | 结果 |
| --- | ---: |
| case_count | 3 |
| selftest_pass_count | 3 |
| selftest_fail_count | 0 |
| positive_case_stage112_allowed | 1 |
| empty_case_stage112_allowed | 0 |
| bad_sha_case_stage112_allowed | 0 |
| real_w0_data_delivered | 0 |
| real_stage112_intake_allowed_now | 0 |
| true_engine_allowed | 0 |
| strategy_feature_usable | 0 |

自测结果：

| case | 预期 | 观测 | 结论 |
| --- | --- | --- | --- |
| empty_manifest_negative | hard accept `0/41`，Stage112 intake `0` | hard accept `0/41`，Stage112 intake `0` | 通过 |
| synthetic_valid_positive | hard accept `41/41`，Stage112 intake `1` | hard accept `41/41`，Stage112 intake `1` | 通过 |
| synthetic_bad_sha_negative | hard accept `40/41`，Stage112 intake `0` | hard accept `40/41`，Stage112 intake `0` | 通过 |

## 视觉产物

- official path selftest status：`qmt_roll_stage118_c9_minrisk_wave0_verifier_selftest_official_path_selftest_status_stage118_wave0_verifier_selftest_v1.png`
- case gate pass chart：`qmt_roll_stage118_c9_minrisk_wave0_verifier_selftest_case_gate_pass_chart_stage118_wave0_verifier_selftest_v1.png`
- case gate matrix：`qmt_roll_stage118_c9_minrisk_wave0_verifier_selftest_case_gate_matrix_stage118_wave0_verifier_selftest_v1.png`
- case issue chart：`qmt_roll_stage118_c9_minrisk_wave0_verifier_selftest_case_issue_chart_stage118_wave0_verifier_selftest_v1.png`

视觉观察：

- official path selftest status 图明确标注 synthetic markers are tool tests only，所有点都只是 verifier 边界测试，不是策略信号。
- case gate pass chart 显示空 manifest 仅通过 `4/15`，完整合成正例通过 `15/15`，bad sha 负例通过 `12/15`。
- case gate matrix 显示 bad sha 只在 `raw_sha256_match`、`all_requests_hard_accept`、`stage112_intake_allowed` 三个关键门上失败，说明单点完整性错误能阻断全体放行。
- issue chart 使用 symlog 轴显示空 manifest `574` 个问题、完整正例 `0`、bad sha `1`。

## 结论

Stage118 证明 Stage117 verifier 的关键边界有效：缺数据不会误放行，完整证据能到达 Stage112-intake-only，单个 sha256 错误会阻断全体放行。当前真实状态仍是 `real_w0_data_delivered=0`、`real_stage112_intake_allowed_now=0`，因此 true engine、A/B、正式候选和微观结构规则预检继续阻塞。

本阶段的有效进展是：未来 W0 到货后，验收器本身已有正/负例保护，不需要临场相信脚本。

## 后续规划和 TODO

1. W0 真实数据到货后，填 Stage116 manifest 并先跑 Stage117。
2. 若 Stage117 全部 data hard gate 通过，再跑 Stage118 确认 verifier 自测仍通过。
3. 只有真实 manifest `41/41` hard accept，才进入 Stage112 intake；合成 fixture 永远不得进入 Stage112/113 或策略研究。
4. 如果真实数据只通过部分 request，不做补丁式筛样本；继续补齐 W0 或回到供应商数据合同。

## 结束反思

- 是否在过拟合：否。Stage118 是测试 verifier 的工程闭环，没有从历史盈亏或视觉位置生成规则。
- 是否还有价值继续：有。现在数据闸门不只是“理念上阻塞”，而是有可运行正/负例保护；下一步价值仍取决于真实授权 W0 数据。
