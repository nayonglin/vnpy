# Stage123 W0 intake chain checkpoint

## 基本信息

- 时间：2026-06-20 18:47
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：W0 到货后的 Stage119 -> Stage117 -> Stage120 一键链路 checkpoint；只做数据验收编排，不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage123_wave0_intake_chain_checkpoint_passed_no_real_data_no_strategy`
- 重要突破版本：否。它把真实 W0 drop 到货后的三段验收串成单命令，但当前没有真实 W0 数据通过。
- 是否触发 A/B：否。没有策略候选。

## 开始前反思

- 是否在过拟合：否。本阶段只验证数据到货验收链路，不读取收益 cohort 做阈值、不筛产品/年份/方向、不改变任何交易路径。
- 是否还有价值继续：是。Stage119、Stage117、Stage120 分别可运行，但真实到货时仍需要人工串命令；一键 checkpoint 能降低操作错误，并把 synthetic 自测与真实可放行状态严格分开。

## 外部调研与判断

- Great Expectations validation workflow 强调 checkpoint 式验证和运行时数据批次。判断：W0 到货后应该用固定验收链路对新 drop 执行同一批 gate，而不是临时改脚本或手工读 CSV。
- Frictionless validation guide 和 validate command 强调验证报告要明确指出 pass/fail 与错误位置。判断：Stage123 不能只看 returncode，必须输出 case summary、step summary、gate matrix 和最终放行字段。
- Python `subprocess` 文档说明可以捕获子进程 stdout/stderr 和 returncode。判断：Stage123 适合用 subprocess 串联 Stage119、Stage117、Stage120，并解析每段 JSON 决策，形成可复跑、可审计的链路 checkpoint。

调研结论：真实 W0 到货后的验收应该是「drop -> manifest -> 文件/proof/时间验收 -> canonical schema 验收 -> Stage112/113」的固定 checkpoint；任何 synthetic 或空 drop 只能用于管线自测，不得进入策略研究。

参考链接：

- https://docs.greatexpectations.io/docs/0.18/oss/guides/validation/validate_data_overview
- https://framework.frictionlessdata.io/docs/guides/validating-data.html
- https://framework.frictionlessdata.io/docs/console/validate.html
- https://docs.python.org/3/library/subprocess.html

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage123_wave0_intake_chain_checkpoint.py`
  - 新增真实入口参数：`--drop-dir`
  - 新增 case 标识：`--case-id`
  - 新增期望验收参数：`--expected-stage112-intake`
  - 新增输出恢复控制：`--no-restore`
  - 默认无参自测串联两个 case：`empty_drop_chain` 与 `synthetic_drop_chain`
  - 每个 case 依次执行 Stage119 drop manifest、Stage117 delivery verifier、Stage120 schema audit
  - 解析每段 JSON 决策，输出 case summary、step summary、gate status、Stage117 request status、report、decision JSON 和三张视觉图
  - 默认自测结束后恢复 Stage119、Stage117、Stage120 默认输出，避免 synthetic 覆盖默认真实状态
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage123_wave0_intake_chain_checkpoint/`

## 参数与结果变更

- 新增自测 case：
  - `empty_drop_chain`
  - `synthetic_drop_chain`
- 新增参数：
  - `case_count=2`
  - `test_pass_count=2`
  - `test_fail_count=0`
  - `final_stage112_ready_count=0`
  - `final_strategy_allowed_count=0`
  - `stage119_117_120_default_restored=1`
  - `real_w0_drop_scanned=0`
  - `real_w0_data_delivered=0`
  - `real_stage112_intake_allowed_now=0`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`
- 修改参数：无交易参数修改。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前官方路径资金曲线做链路 checkpoint 视觉背景。
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

| case | Stage119 rc | Stage117 rc | Stage120 rc | Stage119 intake | Stage117 intake | Stage120 real schema | final Stage112 ready | final strategy | test pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `empty_drop_chain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `synthetic_drop_chain` | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 |

链路解释：

- `empty_drop_chain` 证明空 drop 不会误放行，Stage117、Stage120 和最终 ready 都为 `0`。
- `synthetic_drop_chain` 证明 Stage117 能识别完整 synthetic 证据，但 Stage119 real-candidate 标记为 `0`，Stage120 real schema contract 为 `0`，最终 Stage112 ready 仍为 `0`。
- 两个 case 的命令 returncode 都是 `0`，说明编排层可运行；最终放行字段全为 `0`，说明没有真实数据进入 Stage112 或策略层。

## 视觉产物

- official path chain status：`qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_official_path_chain_status_stage123_wave0_intake_chain_checkpoint_v1.png`
- chain gate matrix：`qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_chain_gate_matrix_stage123_wave0_intake_chain_checkpoint_v1.png`
- case outcome chart：`qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_case_outcome_chart_stage123_wave0_intake_chain_checkpoint_v1.png`

视觉观察：

- official path chain status 图显示资金、回撤、broker10 路径仍是当前官方背景；标题明确 no real W0 final accepted，红绿点只是链路状态标记，不是交易规则信号。
- chain gate matrix 显示两条链路 command returncode 均通过；empty drop 在 Stage117/Stage120 data gate 失败；synthetic drop 虽 Stage117 intake 为 `1`，但 Stage119 real intake 与 Stage120 real schema contract 均为 `0`，且 synthetic final block 为通过。
- case outcome chart 显示 `test_pass=1` 与 `final_stage112_ready=0` 可以同时成立：前者是管线自测通过，后者是没有真实 W0 放行。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage123_wave0_intake_chain_checkpoint/qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_report_stage123_wave0_intake_chain_checkpoint_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage123_wave0_intake_chain_checkpoint/qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_summary_stage123_wave0_intake_chain_checkpoint_v1.csv`
- case summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage123_wave0_intake_chain_checkpoint/qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_case_summary_stage123_wave0_intake_chain_checkpoint_v1.csv`
- step summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage123_wave0_intake_chain_checkpoint/qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_step_summary_stage123_wave0_intake_chain_checkpoint_v1.csv`
- gate status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage123_wave0_intake_chain_checkpoint/qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_gate_status_stage123_wave0_intake_chain_checkpoint_v1.csv`
- request status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage123_wave0_intake_chain_checkpoint/qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_stage117_request_status_stage123_wave0_intake_chain_checkpoint_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage123_wave0_intake_chain_checkpoint/qmt_roll_stage123_c9_minrisk_wave0_intake_chain_checkpoint_decision_stage123_wave0_intake_chain_checkpoint_v1.json`

## 结论

Stage123 证明：Stage119 -> Stage117 -> Stage120 已经能作为一条真实 W0 到货后的链路 checkpoint 使用；空 drop 不会误放行，synthetic drop 不会被误认为真实 W0，默认输出能在自测后恢复。

当前真实状态仍是 `real_w0_drop_scanned=0`、`real_w0_data_delivered=0`、`real_stage112_intake_allowed_now=0`、`true_engine_allowed=0`、`strategy_feature_usable=0`。因此 Stage112/113、微观结构/分钟规则预检、true engine、A/B 和正式候选继续阻塞。

## 后续规划和 TODO

1. 真实 W0 drop 到货后直接运行：`.py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage123_wave0_intake_chain_checkpoint.py --drop-dir <real_drop_dir> --case-id real_w0_drop --expected-stage112-intake 1 --no-restore`
2. 只有 `final_stage112_ready_count=1`、`stage120_real_schema_contract_pass=1` 且 Stage117 request 全部 hard accept 时，才进入 Stage112/113 intake。
3. 在真实 W0 通过前，不再用 synthetic、旧 OHLC、本地 Tq tick、smoke 或 Stage932 类数据构造微观结构/分钟策略规则。
4. 若继续推进当前线，在没有真实 W0 的情况下，只能做 procurement/forward-capture 验收清单或外部数据落盘检查，不做 alpha。

## 结束反思

- 是否在过拟合：否。Stage123 没有用收益结果挑规则，也没有参数扫描；它只把既有数据 hard gate 串成可复跑 checkpoint。
- 是否还有价值继续：有，但价值边界很清楚。工程链路已经可用，下一步的真正增量来自真实授权 W0 数据到货；没有真实数据前继续造交易规则没有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage123 链路 checkpoint 状态。
- 是否更新 `research/registry.md`：否。本阶段不新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破或跨线合入。
