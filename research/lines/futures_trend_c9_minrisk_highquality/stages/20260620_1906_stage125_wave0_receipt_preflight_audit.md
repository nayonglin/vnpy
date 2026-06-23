# Stage125 W0 receipt preflight audit

## 基本信息

- 时间：2026-06-20 19:06
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：W0 drop 收货预检；只在 Stage123 全链路前筛查缺文件、重复角色、未知文件、SHA256 占位和 proof JSON 缺陷，不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage125_wave0_receipt_preflight_empty_drop_blocked_no_real_data_no_strategy`
- 重要突破版本：否。它增加真实 W0 到货前的快速收货筛查，但当前默认空 drop 正确阻断。
- 是否触发 A/B：否。没有策略候选。

## 开始前反思

- 是否在过拟合：否。本阶段只校验 Stage124 文件契约是否在 drop 目录中出现，不读收益标签、不设计交易条件、不筛产品/年份/方向。
- 是否还有价值继续：是。Stage123 是完整验收链路，但真实文件到货前若命名、角色、checksum 或 proof 格式错误，直接跑全链路会产生更长的排错路径；Stage125 先给出收货级可行动错误。

## 外部调研与判断

- Frictionless validation guide 强调 validation 应提供可理解的错误细节。判断：Stage125 不能只输出 pass/fail，应输出 request-level 缺失角色、proof 缺字段、checksum 状态和未知文件。
- Python `jsonschema` 文档说明 JSON 实例应按 schema/规则校验并报告验证错误。判断：proof JSON 至少要在 Stage125 进行必填字段、sequence gap、row_count、synthetic block 的结构化预检。
- Python `pathlib` 文档说明 `**` 通配会递归扫描目录。判断：receipt preflight 适合用 `Path.rglob` 遍历 drop，但要对大目录保持只读扫描，不做移动/删除。
- NIST FIPS 180-4 说明 SHA 系列摘要可用于检测消息是否改变。判断：Stage125 应读取 SHA256 manifest，识别占位符、非 SHA256 字符串和 raw 文件 digest mismatch。

调研结论：真实 W0 到货后，最稳健的路径是先做 receipt preflight，确认 123 个文件、checksum、proof JSON 和 request role 齐全，再进入 Stage123 全链路；这个前置检查只减少工程摩擦，不允许成为交易信号。

参考链接：

- https://v4.framework.frictionlessdata.io/docs/guides/validation-guide
- https://python-jsonschema.readthedocs.io/en/latest/validate/
- https://docs.python.org/3/library/pathlib.html
- https://csrc.nist.gov/pubs/fips/180-4/upd1/final

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage125_wave0_receipt_preflight_audit.py`
  - 默认扫描空 drop 负例：`outputs/stage125_wave0_receipt_preflight_audit/empty_drop`
  - 支持真实入口：`--drop-dir <real_drop_dir> --case-id real_w0_drop_preflight`
  - 读取 Stage124 delivery file contract 与 proof field contract。
  - 递归扫描 drop 文件，按 request_id 与 artifact role 归类 raw、normalized_parquet、proof。
  - 读取 SHA256/SHA256SUMS/`.sha256` 类文件，识别占位符、合法 SHA256 digest 和 raw digest match。
  - 审计 proof JSON 是否可读、12 个必填字段是否齐全、`sequence_gap_count=0`、`row_count>0`、是否被 synthetic/smoke 标记污染。
  - 输出 summary、file inventory、request receipt status、proof audit、checksum audit、unknown file inventory、gate status、report、decision JSON 和 4 张视觉图。

## 参数与结果变更

- 新增参数：
  - `expected_file_count=123`
  - `observed_known_file_count=0`
  - `unknown_file_count=0`
  - `request_count=41`
  - `role_complete_request_count=0`
  - `checksum_match_request_count=0`
  - `proof_ready_request_count=0`
  - `preflight_ready_request_count=0`
  - `gate_pass_count=5/10`
  - `data_hard_gate_pass_count=2/6`
  - `ready_for_stage123=0`
- 修改参数：无交易参数修改。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前官方路径资金曲线做 receipt preflight 视觉背景。
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
| expected files | 123 |
| observed known files | 0 |
| W0 requests | 41 |
| role complete requests | 0 |
| checksum match requests | 0 |
| proof ready requests | 0 |
| preflight ready requests | 0 |
| ready for Stage123 | 0 |
| real Stage112 intake | 0 |
| true engine allowed | 0 |
| strategy feature usable | 0 |

Gate 解释：

- 通过项：Stage124 file contract available、Stage124 proof contract available、strategy locks zero、receipt no duplicate roles、receipt unknown files zero。
- 阻塞项：`receipt_known_file_count=0/123`、`receipt_request_roles_complete=0/41`、`receipt_checksum_manifest_ready=0/41`、`receipt_proof_json_ready=0/41`、`preflight_ready_for_stage123=0/41`。
- 空 drop 被正确阻断；没有任何真实 W0 数据被识别为可进入 Stage123。

## 视觉产物

- official path receipt status：`qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_official_path_receipt_status_stage125_wave0_receipt_preflight_audit_v1.png`
- role completeness matrix：`qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_role_completeness_matrix_stage125_wave0_receipt_preflight_audit_v1.png`
- request role matrix：`qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_request_role_matrix_stage125_wave0_receipt_preflight_audit_v1.png`
- issue bar chart：`qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_issue_bar_chart_stage125_wave0_receipt_preflight_audit_v1.png`

视觉观察：

- official path receipt status 图显示所有 W0 request 在资金、回撤和 broker10 背景上均为红点；这表示 not ready for Stage123，不是交易信号。
- role completeness matrix 显示 raw、normalized_parquet、proof 各自 expected `41`，observed_unique 全为 `0`。
- request role matrix 逐 request 展示三类角色全红，说明没有任何 request 达到收货完整。
- issue bar chart 将当前阻塞定位到 known file count、request roles complete、checksum manifest ready、proof json ready 和 final Stage123 readiness；duplicate role 与 unknown file 在空 drop 中通过。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage125_wave0_receipt_preflight_audit/qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_report_stage125_wave0_receipt_preflight_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage125_wave0_receipt_preflight_audit/qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_summary_stage125_wave0_receipt_preflight_audit_v1.csv`
- file inventory：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage125_wave0_receipt_preflight_audit/qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_file_inventory_stage125_wave0_receipt_preflight_audit_v1.csv`
- request receipt status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage125_wave0_receipt_preflight_audit/qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_request_receipt_status_stage125_wave0_receipt_preflight_audit_v1.csv`
- proof JSON audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage125_wave0_receipt_preflight_audit/qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_proof_json_audit_stage125_wave0_receipt_preflight_audit_v1.csv`
- checksum audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage125_wave0_receipt_preflight_audit/qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_checksum_manifest_audit_stage125_wave0_receipt_preflight_audit_v1.csv`
- unknown file inventory：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage125_wave0_receipt_preflight_audit/qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_unknown_file_inventory_stage125_wave0_receipt_preflight_audit_v1.csv`
- gate status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage125_wave0_receipt_preflight_audit/qmt_roll_stage125_c9_minrisk_wave0_receipt_preflight_audit_receipt_preflight_gate_status_stage125_wave0_receipt_preflight_audit_v1.csv`

## 结论

Stage125 证明：W0 收货预检工具已可运行，并且默认空 drop 被正确阻断。它能在 Stage123 全链路前定位缺文件、重复角色、未知文件、checksum 占位/不匹配、proof JSON 缺字段和 synthetic/smoke 污染风险。

当前真实状态仍是 `observed_known_file_count=0`、`preflight_ready_request_count=0`、`ready_for_stage123=0`、`real_w0_data_delivered=0`、`real_stage112_intake_allowed_now=0`、`true_engine_allowed=0`、`strategy_feature_usable=0`。因此 Stage112/113、微观结构/分钟规则预检、true engine、A/B 和正式候选继续阻塞。

## 后续规划和 TODO

1. 真实 W0 drop 到货后，先运行：`.py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage125_wave0_receipt_preflight_audit.py --drop-dir <real_drop_dir> --case-id real_w0_drop_preflight`
2. 只有 Stage125 `ready_for_stage123=1` 时，再运行 Stage123 全链路：`.py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage123_wave0_intake_chain_checkpoint.py --drop-dir <real_drop_dir> --case-id real_w0_drop --expected-stage112-intake 1 --no-restore`
3. 即使 Stage125 通过，也不能进入策略研究；必须继续通过 Stage123、Stage112 和 Stage113。
4. 在真实 W0 通过前，不再用 synthetic、旧 OHLC、本地 Tq tick、smoke 或 Stage932 类数据构造微观结构/分钟策略规则。

## 结束反思

- 是否在过拟合：否。Stage125 没有引入任何收益阈值或交易条件，只是对文件收货完整性、checksum 和 proof JSON 做机械预检。
- 是否还有价值继续：有。它把真实数据到货后的排错路径提前到 receipt 层，能减少误把不完整 drop 送入 Stage123/112/113 的风险；但真正推进 alpha 仍取决于授权 W0 数据通过后续 hard gate。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage125 收货预检状态。
- 是否更新 `research/registry.md`：否。本阶段不新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破或跨线合入。
