# Stage117 W0 delivery verifier

## 基本信息

- 时间：2026-06-20 17:50
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 阶段性质：只读 W0 到货验收器；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage117_wave0_delivery_missing_no_data_no_rule`
- 重要突破版本：否。它把 W0 到货验收变成可运行 verifier，但当前没有任何 W0 授权数据到货。

## 开始前反思

- 是否在过拟合：否。本阶段不看收益分组、不筛品种、不修改仓位，只验证 raw/data/proof、checksum、parquet schema、sequence gap 和时间覆盖。
- 是否还有价值继续：是。Stage116 已有 manifest 模板，但没有自动验收器；Stage117 让未来 W0 到货后可以机械判断是否允许 Stage112 intake，避免人工放水。

## 外部调研与判断

- Python `hashlib` 官方文档支持 SHA256 等摘要算法。判断：raw 文件必须逐文件校验 `raw_sha256`，不能只凭文件名或目录存在。
- Apache Arrow/Parquet 文档支持读取 Parquet metadata/schema。判断：normalized parquet 至少要能读 footer/schema，并含 `ts_event`、`ts_recv` 这类点时化字段；否则不能进入微观结构路径。
- Apache Arrow Dataset/partitioning 文档强调多文件数据集和分区字段。判断：验收器应按 request/manifest 审计，不按收益候选或 candidate-level partition 放行。
- NIST 信息质量标准强调 utility、integrity、objectivity。判断：W0 验收必须把完整性、可复验性和反挑样本锁作为硬闸门，不靠主观判断。

调研结论：W0 verifier 的核心不是“有没有看起来像数据的文件”，而是 raw hash、schema、timestamp、continuity proof 与 request span 是否可复验；否则继续阻塞策略研究。

参考链接：

- https://docs.python.org/3/library/hashlib.html
- https://arrow.apache.org/docs/python/parquet.html
- https://arrow.apache.org/docs/python/generated/pyarrow.parquet.read_metadata.html
- https://arrow.apache.org/docs/python/dataset.html
- https://arrow.apache.org/docs/python/generated/pyarrow.dataset.partitioning.html
- https://www.nist.gov/director/nist-information-quality-standards

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage117_wave0_delivery_verifier.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage117_wave0_delivery_verifier/`
- 新增核心输出：
  - `w0_request_delivery_status`：逐 request 的 raw/parquet/proof/checksum/schema/continuity/time span 状态。
  - `w0_delivery_gate_status`：W0 到货硬闸门。
  - `w0_delivery_issues`：逐 request 的缺失项清单。
  - `w0_file_audit`：文件存在、sha256、parquet 可读性和 proof 存在性审计。

## 参数与结果变更

- 新增参数：
  - `REQUIRED_PARQUET_FIELDS={ts_event, ts_recv}`
  - `manifest_path=Stage116 w0_delivery_manifest_template`
  - `stage112_intake_allowed_now=0`
  - `strategy_feature_usable=0`
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前路径资金曲线做 W0 delivery status 视觉检查。
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
| w0_request_count | 41 |
| w0_total_window_count | 70 |
| w0_hard_accept_request_count | 0 |
| w0_hard_accept_window_count | 0 |
| w0_hard_accept_window_coverage_pct | 0.0% |
| raw_file_exist_count | 0 |
| parquet_file_exist_count | 0 |
| proof_file_exist_count | 0 |
| sha256_match_count | 0 |
| parquet_readable_count | 0 |
| sequence_gap_zero_count | 0 |
| time_span_ok_count | 0 |
| issue_count | 574 |
| gate_pass_count | 4 / 15 |
| data_gate_pass_count | 0 / 11 |
| stage112_intake_allowed_now | 0 |
| true_engine_allowed | 0 |
| strategy_feature_usable | 0 |

Gate 解释：

- 已通过：manifest 非空、request 数匹配 W0 packet、request_id 唯一、策略权限锁为 `0`。
- 未通过：raw/parquet/proof 文件均为 `0/41`，raw sha256 匹配 `0/41`，parquet 可读 `0/41`，`ts_event/ts_recv` 字段证明 `0/41`，sequence gap zero `0/41`，row count positive `0/41`，request span 覆盖 `0/41`，hard accept `0/41`。

## 视觉产物

- official path delivery status：`qmt_roll_stage117_c9_minrisk_wave0_delivery_verifier_official_path_delivery_status_stage117_wave0_delivery_verifier_v1.png`
- gate status chart：`qmt_roll_stage117_c9_minrisk_wave0_delivery_verifier_gate_status_chart_stage117_wave0_delivery_verifier_v1.png`
- file completeness matrix：`qmt_roll_stage117_c9_minrisk_wave0_delivery_verifier_file_completeness_matrix_stage117_wave0_delivery_verifier_v1.png`
- request timeline status：`qmt_roll_stage117_c9_minrisk_wave0_delivery_verifier_request_timeline_status_stage117_wave0_delivery_verifier_v1.png`

视觉观察：

- official path delivery status 图中 W0 点全部为红色，明确表示这些资金曲线位置对应的数据未验收，不是交易信号。
- gate status chart 显示 4 个结构/反挑样本闸门通过，11 个 data hard gate 全失败。
- file completeness matrix 全红，说明没有任何 request 拥有可接受 raw/parquet/proof 组合。
- request timeline status 显示失败样本分布在 `2020-2025` 多个时段；这反证了不能用某个局部样本代替 W0 验收。

## 结论

Stage117 已完成 W0 到货 verifier。当前默认 manifest 仍无实际 raw/data/proof 文件，`w0_hard_accept_request_count=0`，`stage112_intake_allowed_now=0`，因此 Stage112 intake、true engine、A/B、正式候选和微观结构规则预检全部继续阻塞。

本阶段的有效进展是：未来 W0 数据到货后，可以直接把填好的 manifest 传给 `stage117_wave0_delivery_verifier.py`，用硬闸门决定是否进入 Stage112，而不需要人工解释或临时放行。

## 后续规划和 TODO

1. W0 到货后，先填 Stage116 manifest 的 raw_file、raw_sha256、normalized_parquet_file、proof_file、schema_hash、timestamp timezone、row_count、sequence_gap_count 和 continuity proof。
2. 使用 `stage117_wave0_delivery_verifier.py <manifest_path>` 复跑验收。
3. 只有 `data_gate_pass_count=11/11` 且 `hard_accept=41/41`，才允许进入 Stage112 intake；仍不得做策略研究。
4. 若 W0 缺少 `ts_event/ts_recv`、sequence gap proof 或 raw sha256，即使能读 parquet，也不能进入微观结构规则路径。

## 结束反思

- 是否在过拟合：否。本阶段只是数据完整性/客观性验收器，所有收益相关位置都标为未验收数据，不产生任何交易规则。
- 是否还有价值继续：有，但价值集中在真实 W0 到货后的复验；在 W0 仍为 `0/41` 前，继续做微观结构 alpha 只会变成无数据假设。
