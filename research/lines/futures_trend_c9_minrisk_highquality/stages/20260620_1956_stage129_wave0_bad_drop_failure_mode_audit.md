# Stage129 W0 bad-drop failure-mode audit

## 基本信息

- 时间：2026-06-20 19:56
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：W0 到货入口的 failure-mode 审计；专门构造“非空但错误”的 drop，验证 Stage128 full supergate 不会只拦空目录，而能拦住更接近真实供应交付错误的 proof-only、模板、错 request、时间覆盖不足和 synthetic/smoke 污染。只做本地验收和视觉 QA，不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage129_bad_drop_failure_modes_blocked_no_strategy`
- 重要突破版本：否。它是 W0 数据入口 hard gate 的负例覆盖增强，不是 alpha 或正式候选。
- 是否触发 A/B：否。没有策略候选。

## 开始前反思

- 是否在过拟合：否。本阶段不读取收益标签、不调交易阈值、不按品种/年份/方向筛选；只用固定 W0 `41` 个 request 合同构造数据验收负例，目标是防止坏数据误入 Stage112/113。
- 是否还有价值继续：是。真实 W0 到货前，最危险的不是空目录，而是“有 41 个 proof 文件但 proof 错位、时间不覆盖、只给 proof 不给 raw/parquet/checksum”。Stage129 正好补这类失败模式。

## 外部调研与判断

- NIST IR 8397 关于 combinatorial testing for software failure modes 的方法强调通过系统化 failure mode/invalid input 组合验证软件不会做不该做的事。判断：Stage129 应覆盖不同坏交付形态，而不是只跑 empty/synthetic 两个简单负例。
- Frictionless Data validation guide 把数据资源、schema 和 package 作为可验证对象。判断：W0 不能把 JSON schema valid 当作充分条件，必须继续验 request identity、time span、raw/parquet/checksum 和全链路 readiness。
- pytest `tmp_path` 文档强调测试应使用隔离的临时目录。判断：Stage129 的 bad drop 应写入独立 `outputs/stage129.../bad_drops/`，每次运行重建，不污染真实到货目录；运行后还要恢复 Stage128 默认输出。

调研结论：数据入口 gate 的稳健性来自“负例族 + 全链路验证”，不是单点 schema 检查。Stage129 因此复用 Stage128，而不是绕开 Stage127/125/123 自己判断。

参考链接：

- https://nvlpubs.nist.gov/nistpubs/ir/2021/NIST.IR.8397.pdf
- https://v4.framework.frictionlessdata.io/docs/guides/validation-guide
- https://docs.pytest.org/en/stable/how-to/tmp_path.html

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage129_wave0_bad_drop_failure_mode_audit.py`
  - 读取 Stage124 delivery file contract 和 Stage126 proof template/schema。
  - 在本阶段输出目录下生成 `5` 类 bad drop，每类 `41` 个 proof JSON，共 `205` 个本地负例 proof 文件。
  - 每个 bad drop 均通过 Stage128 CLI 执行：`stage128_wave0_full_intake_supergate.py --drop-dir <bad_drop_dir> --expected-stage112-intake 0`
  - 每个 Stage128 case 后立即捕获 summary/case/step/gate/request audit。
  - 最后自动恢复 Stage128 默认负例输出，避免污染 Stage128 记录。
  - 输出 summary、failure expectation、case summary、step summary、gate status、request audit、bad drop inventory、report、decision JSON 和 4 张视觉图。

构造的 5 类负例：

| failure case | 构造方式 | 预期阻断点 |
| --- | --- | --- |
| `template_proof_only_drop` | 把 41 个 Stage126 模板复制到交付 proof 路径 | schema/template/placeholder 阻断 |
| `valid_schema_proof_only_drop` | 41 个 schema-valid proof，但没有 raw/parquet/checksum | Stage127 可过，Stage125/123/full supergate 阻断 |
| `valid_schema_wrong_request_drop` | proof schema valid，但 payload `request_id` 与路径 request 合同错位 | Stage127 identity bridge 阻断 |
| `valid_schema_undercovered_span_drop` | proof schema valid，但 `last_ts_event=request_end-1min` | Stage127 request span bridge 阻断 |
| `synthetic_flag_schema_drop` | proof 含 synthetic/smoke vendor/dataset/flag | Stage126 schema 与 Stage125 synthetic block 阻断 |

## 参数与结果变更

- 新增参数：
  - `failure_case_count=5`
  - `generated_bad_drop_file_count=205`
  - `stage128_cli_run_count=5`
  - `stage128_returncode_zero=1`
  - `stage128_all_inner_commands_returncode_zero=1`
  - `stage128_default_restored=1`
  - `blocked_case_count=5`
  - `unexpected_pass_count=0`
  - `expectation_matched_count=5/5`
  - `full_supergate_ready_count=0`
  - `strategy_allowed_count=0`
  - `proof_schema_bridge_ready_case_count=1`
  - `stage125_proof_ready_case_count=3`
  - `real_w0_data_delivered=0`
  - `real_stage112_intake_allowed_now=0`
- 修改参数：无交易参数修改。
- 删除参数：无。
- 新增回测结果：无真实回测；复用当前官方路径资金曲线做 bad-drop gate 视觉背景。
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

| failure case | schema valid | identity match | span cover | Stage127 bridge ready | Stage125 proof ready | final supergate | unexpected pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| template_proof_only_drop | 0/41 | 41/41 | 41/41 | 0/41 | 0/41 | 0 | 0 |
| valid_schema_proof_only_drop | 41/41 | 41/41 | 41/41 | 41/41 | 41/41 | 0 | 0 |
| valid_schema_wrong_request_drop | 41/41 | 0/41 | 41/41 | 0/41 | 41/41 | 0 | 0 |
| valid_schema_undercovered_span_drop | 41/41 | 41/41 | 0/41 | 0/41 | 41/41 | 0 | 0 |
| synthetic_flag_schema_drop | 0/41 | 41/41 | 41/41 | 0/41 | 0/41 | 0 | 0 |

解释：

- `valid_schema_proof_only_drop` 是最重要的负例：它证明即使 `41/41` proof JSON schema、request identity、time span 都正确，缺 raw/parquet/checksum 时仍不能通过 full supergate。
- `valid_schema_wrong_request_drop` 与 `valid_schema_undercovered_span_drop` 证明 schema valid 不是充分条件，request identity 和 request span 是必要桥接。
- `template_proof_only_drop` 与 `synthetic_flag_schema_drop` 证明模板和 synthetic/smoke 污染不会因为文件存在而进入 Stage123。
- 5 个 case 的 Stage128 外层 returncode 与内部 Stage127/125/123 returncode 全部为 `0`，说明脚本执行成功；阻断来自数据 hard gate，不是程序崩溃。

## 视觉产物

- official path bad-drop failure status：`qmt_roll_stage129_c9_minrisk_wave0_bad_drop_failure_mode_audit_official_path_bad_drop_failure_status_stage129_wave0_bad_drop_failure_mode_audit_v1.png`
- bad-drop supergate matrix：`qmt_roll_stage129_c9_minrisk_wave0_bad_drop_failure_mode_audit_bad_drop_supergate_matrix_stage129_wave0_bad_drop_failure_mode_audit_v1.png`
- expected vs observed failure modes：`qmt_roll_stage129_c9_minrisk_wave0_bad_drop_failure_mode_audit_expected_vs_observed_failure_modes_stage129_wave0_bad_drop_failure_mode_audit_v1.png`
- request failure mode matrix：`qmt_roll_stage129_c9_minrisk_wave0_bad_drop_failure_mode_audit_request_failure_mode_matrix_stage129_wave0_bad_drop_failure_mode_audit_v1.png`

视觉观察：

- official path 图中资金、回撤和 broker10 曲线保持官方路径不变；bad-drop marker 只是验收窗口位置，不是交易信号。
- 底部 case outcome 显示只有 `valid_schema_proof_only_drop` 的 Stage127 bridge ready 为 `41`，但它的 final supergate 和 unexpected pass 仍为 `0`，直观看到“schema/proof 过了仍不能放行”。
- bad-drop supergate matrix 中所有 case 的 `final_supergate_ready`、`unexpected_pass` 全红为 `0`；不同 case 的绿块只表示相应前置字段被正确识别。
- expected vs observed 图中 5 类负例的期望和观测完全一致，`expectation_matched_count=5/5`。
- request failure matrix 显示 request-level 阻断是成片一致的，不是少数 request 偶然失败。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage129_wave0_bad_drop_failure_mode_audit/qmt_roll_stage129_c9_minrisk_wave0_bad_drop_failure_mode_audit_report_stage129_wave0_bad_drop_failure_mode_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage129_wave0_bad_drop_failure_mode_audit/qmt_roll_stage129_c9_minrisk_wave0_bad_drop_failure_mode_audit_summary_stage129_wave0_bad_drop_failure_mode_audit_v1.csv`
- failure expectation：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage129_wave0_bad_drop_failure_mode_audit/qmt_roll_stage129_c9_minrisk_wave0_bad_drop_failure_mode_audit_failure_expectation_audit_stage129_wave0_bad_drop_failure_mode_audit_v1.csv`
- case summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage129_wave0_bad_drop_failure_mode_audit/qmt_roll_stage129_c9_minrisk_wave0_bad_drop_failure_mode_audit_failure_case_summary_stage129_wave0_bad_drop_failure_mode_audit_v1.csv`
- request audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage129_wave0_bad_drop_failure_mode_audit/qmt_roll_stage129_c9_minrisk_wave0_bad_drop_failure_mode_audit_failure_request_audit_stage129_wave0_bad_drop_failure_mode_audit_v1.csv`
- inventory：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage129_wave0_bad_drop_failure_mode_audit/qmt_roll_stage129_c9_minrisk_wave0_bad_drop_failure_mode_audit_bad_drop_file_inventory_stage129_wave0_bad_drop_failure_mode_audit_v1.csv`

## 结论

Stage129 证明：Stage128 full supergate 能拦住非空但错误的 W0 drop。尤其是 `valid_schema_proof_only_drop` 这种“proof 证据看起来全对，但 raw/parquet/checksum 缺失”的高风险形态也没有被误放行。

当前真实状态仍是 `full_supergate_ready_count=0`、`real_w0_data_delivered=0`、`real_stage112_intake_allowed_now=0`、`true_engine_allowed=0`、`strategy_feature_usable=0`。因此 Stage112/113、微观结构/分钟规则预检、true engine、A/B 和正式候选继续阻塞。

## 后续规划和 TODO

1. 真实 W0 drop 到货后，直接跑 Stage128 CLI；若失败，用 Stage129 的 failure atlas 对照定位是 template/schema、request identity、time span、raw/parquet/checksum 还是 synthetic/smoke 污染。
2. 若供应商只先给 proof，不给 raw/parquet/checksum，不能进入 Stage112/113；只能作为交付缺口回执。
3. 下一阶段可继续补一个 checksum/raw/parquet 层面的坏 drop failure mode，例如 raw 文件存在但 SHA256SUMS 指向错误 digest、parquet schema 不含 hard fields；仍不进入策略研究。
4. 没有真实 W0 通过 Stage128/112/113 前，不从本地旧 OHLC、synthetic、Tq smoke 或模板 proof 构造任何分钟进出场规则。

## 结束反思

- 是否在过拟合：否。Stage129 没有收益优化，也没有交易参数；它只扩大 bad-data failure-mode 覆盖，用固定合同验证 gate 是否防误放行。
- 是否还有价值继续：有。数据入口的负例覆盖越完整，后续真正拿到授权微观结构数据时越不容易把坏数据误当 alpha。但它本身不推进收益，下一步仍应服务于真实 W0 到货验收或 checksum/parquet failure-mode 补强。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage129 bad-drop failure-mode audit 状态。
- 是否更新 `research/registry.md`：否。本阶段不新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破或跨线合入。
