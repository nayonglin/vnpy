# Stage121 W0 schema CLI entry selftest

## 基本信息

- 时间：2026-06-20 18:27
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage120 外部 manifest CLI 入口与回归自测；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage121_stage120_cli_entry_selftest_passed_no_real_data_no_strategy`
- 重要突破版本：否。它修复真实 W0 到货后的可运行入口，但当前没有真实 W0。
- 是否触发 A/B：否。没有策略候选。

## 开始前反思

- 是否在过拟合：否。本阶段只补数据验收 CLI 入口和自测，不读取收益 cohort、不设交易阈值、不筛产品/年份/方向。
- 是否还有价值继续：是。Stage120 已有 schema 合同，但没有外部 manifest 参数入口会导致真实 W0 到货时仍需人工改代码；这会增加验收自由度和操作风险。

## 外部调研与判断

- Great Expectations validation workflow 强调 checkpoint 可复用，并可在运行时指定 validation data。判断：Stage120 应该像 checkpoint 一样接受外部 manifest，而不是只写死 Stage116/119 路径。
- Frictionless validation guide 强调 CLI 和高层函数都应生成清晰 validation report。判断：Stage121 必须输出 case summary、gate matrix 和视觉图，而不是只看一次命令返回码。
- Click API 文档说明 CLI argument/option 应作为命令运行参数。判断：本阶段用标准库 `argparse` 实现轻量参数入口即可，不引入新依赖。

调研结论：真实 W0 到货后的验收链路必须是一条可复跑命令，而不是手动改 Python 常量；Stage121 的价值在于把 Stage120 从“固定样例审计”提升为“可接收真实 manifest 的 checkpoint”。

参考链接：

- https://docs.greatexpectations.io/docs/0.18/oss/guides/validation/validate_data_overview/
- https://framework.frictionlessdata.io/docs/guides/validating-data.html
- https://click.palletsprojects.com/en/stable/api/

## 本阶段改动

- 修改工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage120_wave0_schema_contract_audit.py`
  - 新增 `--manifest`
  - 新增 `--manifest-label`
  - 新增 `--skip-synthetic-selftest`
  - 修正无 synthetic 行时的 `synthetic_fixture_blocked_from_real_contract` gate 语义。
  - 修正 synthetic 缺口图按 `synthetic_like=1` 识别，而不是依赖固定 label。
- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage121_wave0_schema_cli_entry_selftest.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage121_wave0_schema_cli_entry_selftest/`

## 参数与结果变更

- 新增自测 case：
  - `default_no_args`
  - `cli_empty_template`
  - `cli_synthetic_manifest`
- 新增参数：
  - `stage120_default_restored=1`
  - `real_w0_schema_contract_pass=0`
  - `real_w0_data_delivered=0`
  - `real_stage112_intake_allowed_now=0`
- 修改参数：Stage120 现在允许传入外部 manifest。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前路径资金曲线做 CLI 自测视觉检查。
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

| case | returncode | real_w0_data_delivered | real_w0_schema_contract_pass | true_engine_allowed | test_pass |
| --- | ---: | ---: | ---: | ---: | ---: |
| default_no_args | 0 | 0 | 0 | 0 | 1 |
| cli_empty_template | 0 | 0 | 0 | 0 | 1 |
| cli_synthetic_manifest | 0 | 0 | 0 | 0 | 1 |

汇总：

| 项目 | 结果 |
| --- | ---: |
| case_count | 3 |
| test_pass_count | 3 |
| test_fail_count | 0 |
| stage120_default_restored | 1 |
| real_w0_data_delivered | 0 |
| real_w0_schema_contract_pass | 0 |
| real_stage112_intake_allowed_now | 0 |
| true_engine_allowed | 0 |
| strategy_feature_usable | 0 |

## 视觉产物

- official path CLI status：`qmt_roll_stage121_c9_minrisk_wave0_schema_cli_entry_selftest_official_path_cli_status_stage121_wave0_schema_cli_entry_selftest_v1.png`
- case gate matrix：`qmt_roll_stage121_c9_minrisk_wave0_schema_cli_entry_selftest_case_gate_matrix_stage121_wave0_schema_cli_entry_selftest_v1.png`
- case outcome chart：`qmt_roll_stage121_c9_minrisk_wave0_schema_cli_entry_selftest_case_outcome_chart_stage121_wave0_schema_cli_entry_selftest_v1.png`

视觉观察：

- official path CLI status 图继续把 W0 请求点放在权益、回撤、broker10 路径上；没有真实 W0 被接受。
- case gate matrix 显示三种入口都通过 schema planning 与锁定 gate，但 `real_w0_manifest_delivered` 和 `real_w0_schema_contract_pass` 全部失败。
- case outcome chart 显示三种入口 `test_pass=1`，同时 `real_w0_data_delivered=0`、`real_w0_schema_contract_pass=0`、`true_engine_allowed=0`。

## 结论

Stage121 证明：Stage120 现在可以作为真实 manifest 的 CLI checkpoint 使用。空 manifest 与 Stage119 synthetic manifest 都不会被误判为真实 schema contract 通过；自测结束后 Stage120 默认输出也已恢复。

当前真实状态仍是 `real_w0_data_delivered=0`、`real_w0_schema_contract_pass=0`、`real_stage112_intake_allowed_now=0`，因此 true engine、A/B、正式候选和微观结构/分钟规则预检继续阻塞。

## 后续规划和 TODO

1. 真实 W0 drop 到货后，运行 Stage119 生成 manifest。
2. 运行 Stage117 验证 raw/proof/time span/sha256/sequence proof。
3. 运行 Stage120 CLI：`stage120_wave0_schema_contract_audit.py --manifest <real_manifest.csv> --manifest-label real_w0_drop`。
4. 只有真实 Stage117 和 Stage120 都 `41/41` 通过，才允许进入 Stage112/113 intake。
5. 在真实 W0 到货前，不再用本地 synthetic、旧 OHLC 或 smoke 数据构造微观结构/分钟策略规则。

## 结束反思

- 是否在过拟合：否。Stage121 是验收入口回归，不涉及收益优化、参数搜索或样本筛选。
- 是否还有价值继续：有。它把真实数据到货后的操作从“改代码”变成“传 manifest 参数”，降低人为解释空间；但没有真实 W0 前仍不能推进 alpha。
