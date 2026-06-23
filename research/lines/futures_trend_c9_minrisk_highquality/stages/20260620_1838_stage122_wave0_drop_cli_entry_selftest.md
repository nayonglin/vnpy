# Stage122 W0 drop CLI entry selftest

## 基本信息

- 时间：2026-06-20 18:38
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage119 外部 drop-dir CLI 入口与回归自测；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage122_stage119_drop_cli_entry_selftest_passed_no_real_data_no_strategy`
- 重要突破版本：否。它修复真实 W0 drop 到货后的可运行入口和相对路径问题，但当前没有真实 W0。
- 是否触发 A/B：否。没有策略候选。

## 开始前反思

- 是否在过拟合：否。本阶段只补 drop 目录验收 CLI 与路径规范化，不读取收益 cohort、不设交易阈值、不筛产品/年份/方向。
- 是否还有价值继续：是。Stage119 已能从 drop 目录自动生成 manifest，但没有 `--drop-dir` 入口时，真实 W0 到货仍需改 Python 常量；相对路径若不规范化，还会导致 Stage117 按 manifest 目录错误解析文件路径。

## 外部调研与判断

- Python `argparse` 文档说明命令行参数适合封装可复跑的入口。判断：Stage119 应接受 `--drop-dir`、`--case-id`、`--expected-stage112-intake`，避免真实数据到货时改代码。
- Python `pathlib` 文档支持路径解析与递归扫描。判断：CLI 传入的相对 drop 路径必须先 `resolve()` 成绝对路径，再写入 manifest；否则 Stage117 会按 manifest 目录解析相对文件路径。
- Frictionless validation 文档强调 validation report 应清晰输出。判断：Stage122 必须输出 case summary、Stage117 gate matrix 和资金路径图，不能只看命令 returncode。
- Great Expectations checkpoint 资料强调 validation data 在运行时指定。判断：Stage119 应与 Stage120 一样成为 checkpoint 式入口。

调研结论：真实 W0 到货后的第一步也必须是一条可复跑命令，而不是手工改脚本；drop path 必须规范成绝对路径，防止“文件存在但 verifier 找不到”的隐性失败。

参考链接：

- https://docs.python.org/3/library/argparse.html
- https://docs.python.org/3/library/pathlib.html
- https://framework.frictionlessdata.io/docs/guides/validating-data.html
- https://docs.greatexpectations.io/docs/0.18/oss/guides/validation/validate_data_overview/

## 本阶段改动

- 修改工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage119_wave0_drop_manifest_builder.py`
  - 新增 `--drop-dir`
  - 新增 `--case-id`
  - 新增 `--expected-stage112-intake`
  - 新增 `--skip-synthetic-selftest`
  - CLI drop 路径进入扫描前统一 `expanduser().resolve()`。
  - 图表从固定两个 case 改为动态 case，避免 CLI 自测或真实 drop 图表崩溃。
  - `real_w0_drop_scanned`、`real_w0_data_delivered`、`real_stage112_intake_allowed_now` 从硬编码 0 改为按 CLI real-candidate case 计算。
- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage122_wave0_drop_cli_entry_selftest.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage122_wave0_drop_cli_entry_selftest/`

## 参数与结果变更

- 新增自测 case：
  - `default_no_args`
  - `cli_empty_drop_relative`
  - `cli_synthetic_drop_relative`
- 新增参数：
  - `stage119_default_restored=1`
  - `relative_path_bug_guarded=1`
  - `real_w0_drop_scanned=0`
  - `real_w0_data_delivered=0`
  - `real_stage112_intake_allowed_now=0`
- 修改参数：Stage119 现在允许传入外部 drop 目录。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前路径资金曲线做 drop CLI 自测视觉检查。
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

| entry_case | returncode | decision | real_w0_drop_scanned | real_w0_data_delivered | true_engine_allowed | test_pass |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| default_no_args | 0 | `stage119_drop_builder_selftest_passed_no_real_data_no_strategy` | 0 | 0 | 0 | 1 |
| cli_empty_drop_relative | 0 | `stage119_drop_builder_selftest_passed_no_real_data_no_strategy` | 1 | 0 | 0 | 1 |
| cli_synthetic_drop_relative | 0 | `stage119_drop_builder_selftest_passed_no_real_data_no_strategy` | 0 | 0 | 0 | 1 |

Stage119 case 结果：

| case | file_count | raw/parquet/proof/all_three | hard_accept | Stage112 intake | synthetic_like | real_candidate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| empty_drop_negative | 0 | 0/0/0/0 | 0/41 | 0 | 0 | 0 |
| synthetic_drop_positive | 125 | 41/41/41/41 | 41/41 | 1 | 1 | 0 |
| cli_empty_drop | 0 | 0/0/0/0 | 0/41 | 0 | 0 | 1 |
| cli_synthetic_drop | 125 | 41/41/41/41 | 41/41 | 1 | 1 | 0 |

汇总：

| 项目 | 结果 |
| --- | ---: |
| case_count | 3 |
| test_pass_count | 3 |
| test_fail_count | 0 |
| stage119_default_restored | 1 |
| relative_path_bug_guarded | 1 |
| real_w0_drop_scanned | 0 |
| real_w0_data_delivered | 0 |
| real_stage112_intake_allowed_now | 0 |
| true_engine_allowed | 0 |
| strategy_feature_usable | 0 |

## 视觉产物

- official path drop CLI status：`qmt_roll_stage122_c9_minrisk_wave0_drop_cli_entry_selftest_official_path_drop_cli_status_stage122_wave0_drop_cli_entry_selftest_v1.png`
- case gate matrix：`qmt_roll_stage122_c9_minrisk_wave0_drop_cli_entry_selftest_case_gate_matrix_stage122_wave0_drop_cli_entry_selftest_v1.png`
- case outcome chart：`qmt_roll_stage122_c9_minrisk_wave0_drop_cli_entry_selftest_case_outcome_chart_stage122_wave0_drop_cli_entry_selftest_v1.png`

视觉观察：

- official path drop CLI status 图继续把 Stage119 默认自测点放在权益、回撤、broker10 路径上；标题明确 no real W0 accepted。
- case gate matrix 现在按 `entry_case:stage119_case` 展示，能看到 default 空负例失败、default synthetic 正例通过、CLI 空负例失败、CLI synthetic 相对路径正例通过。
- case outcome chart 显示 CLI 空 drop 会被识别为扫描过真实候选目录但不放行，CLI synthetic 不算真实 W0，三种入口 test 均通过。

## 结论

Stage122 证明：Stage119 现在可以作为真实 W0 drop 目录的 CLI checkpoint 使用；相对 drop 路径会先规范为绝对路径，避免 manifest 中相对文件路径导致 Stage117 找不到文件。空 drop 和 synthetic drop 都不会被误判为真实 W0 数据；自测结束后 Stage119 默认输出也已恢复。

当前真实状态仍是 `real_w0_drop_scanned=0`、`real_w0_data_delivered=0`、`real_stage112_intake_allowed_now=0`，因此 true engine、A/B、正式候选和微观结构/分钟规则预检继续阻塞。

## 后续规划和 TODO

1. 真实 W0 drop 到货后，运行：`stage119_wave0_drop_manifest_builder.py --drop-dir <real_drop_dir> --case-id real_w0_drop --expected-stage112-intake 1`。
2. 用 Stage119 生成的 manifest 跑 Stage117，确认真实 hard accept `41/41`。
3. 用 Stage120 CLI 验 canonical schema。
4. 只有 Stage117 与 Stage120 都通过，才进入 Stage112/113 intake。
5. 没有真实 W0 前，不再用本地 synthetic、旧 OHLC 或 smoke 数据构造微观结构/分钟策略规则。

## 结束反思

- 是否在过拟合：否。Stage122 是数据验收入口回归，不涉及收益优化、参数搜索或样本筛选。
- 是否还有价值继续：有。它把真实 W0 到货后的第一步从“改代码/手工路径解释”变成可复跑命令；但没有真实 W0 前仍不能推进 alpha。
