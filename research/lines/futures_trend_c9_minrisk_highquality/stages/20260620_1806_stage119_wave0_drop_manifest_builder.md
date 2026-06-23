# Stage119 W0 drop manifest builder

## 基本信息

- 时间：2026-06-20 18:06
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 阶段性质：W0 drop 扫描与 manifest 构建自测；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage119_drop_builder_selftest_passed_no_real_data_no_strategy`
- 重要突破版本：否。它补齐真实 W0 到货后的自动建 manifest 环节，但当前没有真实 W0 drop。

## 开始前反思

- 是否在过拟合：否。本阶段只做文件发现、request_id 配对、checksum 和 Stage117 接入，不读取收益分组、不筛品种、不生成交易规则。
- 是否还有价值继续：是。Stage117/118 已能验收 manifest，但真实数据到货时人工填 manifest 仍可能出错；Stage119 把 drop 目录到 manifest 的过程机械化，降低人为放水或漏填风险。

## 外部调研与判断

- Frictionless Data Package 资料强调数据资源需要 locator 与 metadata 描述。判断：W0 drop 不能只是一堆文件，必须构造成逐 request manifest。
- Apache Arrow Dataset 文档支持多文件数据集发现。判断：drop scanner 可以递归枚举文件，但最终仍必须按 request_id 明确绑定 raw/parquet/proof。
- Python `pathlib` 文档支持递归 glob。判断：扫描顺序必须排序，避免同一 drop 因文件系统顺序不同产生不同 manifest。
- NIST 数据完整性资料强调识别与保护资产、防止未授权修改。判断：Stage119 必须保留 raw sha256 和 proof，不允许只凭 parquet 可读就放行。

调研结论：drop builder 的职责是把交付文件变成可验收 manifest，不是替代 Stage117；最终能否进入 Stage112 仍由 Stage117 data hard gate 决定。

参考链接：

- https://specs.frictionlessdata.io/data-package/
- https://specs.frictionlessdata.io/data-resource/
- https://arrow.apache.org/docs/python/dataset.html
- https://docs.python.org/3/library/pathlib.html
- https://www.nccoe.nist.gov/data-integrity-identifying-and-protecting-assets-against-ransomware-and-other-destructive-events

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage119_wave0_drop_manifest_builder.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage119_wave0_drop_manifest_builder/`
- 新增核心输出：
  - `file_inventory`：递归扫描 drop 后的文件角色表。
  - `request_match_status`：逐 request 的 raw/parquet/proof 匹配状态。
  - `empty_drop_negative_built_manifest`：空 drop 负例 manifest。
  - `synthetic_drop_positive_built_manifest`：从 Stage118 synthetic fixture 自动重建的 manifest。
  - `stage117_gate_status` / `stage117_request_status`：builder 输出接入 Stage117 后的验收结果。

## 参数与结果变更

- 新增自测 case：
  - `empty_drop_negative`
  - `synthetic_drop_positive`
- 新增参数：
  - `real_w0_drop_scanned=0`
  - `real_w0_data_delivered=0`
  - `real_stage112_intake_allowed_now=0`
  - request_id 识别模式：`stage114_req_\\d{4}`
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前路径资金曲线做 drop builder 视觉检查。
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
| case_count | 2 |
| selftest_pass_count | 2 |
| selftest_fail_count | 0 |
| empty_drop_stage112_allowed | 0 |
| synthetic_drop_stage112_allowed | 1 |
| real_w0_drop_scanned | 0 |
| real_w0_data_delivered | 0 |
| real_stage112_intake_allowed_now | 0 |
| true_engine_allowed | 0 |
| strategy_feature_usable | 0 |

自测结果：

| case | file_count | raw/parquet/proof/all_three | hard_accept | Stage112 intake | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| empty_drop_negative | 0 | 0/0/0/0 | 0/41 | 0 | 通过 |
| synthetic_drop_positive | 125 | 41/41/41/41 | 41/41 | 1 | 通过 |

## 视觉产物

- official path builder status：`qmt_roll_stage119_c9_minrisk_wave0_drop_manifest_builder_official_path_builder_status_stage119_wave0_drop_manifest_builder_v1.png`
- match matrix：`qmt_roll_stage119_c9_minrisk_wave0_drop_manifest_builder_match_matrix_stage119_wave0_drop_manifest_builder_v1.png`
- gate matrix：`qmt_roll_stage119_c9_minrisk_wave0_drop_manifest_builder_gate_matrix_stage119_wave0_drop_manifest_builder_v1.png`
- inventory chart：`qmt_roll_stage119_c9_minrisk_wave0_drop_manifest_builder_inventory_chart_stage119_wave0_drop_manifest_builder_v1.png`

视觉观察：

- official path builder status 图明确标注 synthetic positive is not real W0；合成绿点只代表工具链可识别完整 drop。
- match matrix 显示空 drop `0/41`，合成 drop raw/parquet/proof/all_three 均为 `41/41`。
- gate matrix 显示空 drop 在所有 data hard gate 上失败，合成 drop 在 Stage117 上全通过。
- inventory chart 显示合成 drop 中 raw/parquet/proof 各 `41` 个，另有 `2` 个 ignored manifest 文件未参与 request 匹配。

## 结论

Stage119 证明：当真实 W0 drop 目录按 request_id 提供 raw/parquet/proof 时，工具可以自动重建 Stage117-compatible manifest；当 drop 为空时不会误放行。当前真实状态仍是 `real_w0_drop_scanned=0`、`real_w0_data_delivered=0`、`real_stage112_intake_allowed_now=0`，因此 true engine、A/B、正式候选和微观结构规则预检继续阻塞。

本阶段的有效进展是：未来 W0 到货后，可以先用 Stage119 从 drop 目录生成 manifest，再用 Stage117 做硬验收，减少手工填写 manifest 的风险。

## 后续规划和 TODO

1. 真实 W0 drop 到货后，运行 `stage119_wave0_drop_manifest_builder.py` 的真实 drop 版本或复用其函数生成 manifest。
2. 用生成的 manifest 跑 Stage117；只有真实 `41/41` hard accept 才进入 Stage112 intake。
3. 如果真实 drop 缺 proof、缺 raw sha256、缺 `ts_event/ts_recv` 或只有部分 request，不能做部分样本策略研究；继续补数据或回供应商合同。
4. 合成 drop 只保留为 builder 自测，不得进入 Stage112/113 或策略研究。

## 结束反思

- 是否在过拟合：否。Stage119 只做数据交付工程闭环，不涉及收益、参数、品种、年份或交易规则。
- 是否还有价值继续：有。它把真实数据到货后的人工步骤继续收窄为机械流程；但没有真实 W0 前，仍不能推进微观结构 alpha。
