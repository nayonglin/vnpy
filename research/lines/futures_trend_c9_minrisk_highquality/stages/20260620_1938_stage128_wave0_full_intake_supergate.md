# Stage128 W0 full intake supergate

## 基本信息

- 时间：2026-06-20 19:38
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：W0 真实到货入口 supergate；把 Stage127 proof schema bridge、Stage125 receipt preflight、Stage123 intake chain 固定成一条顺序执行链。只做数据交付硬闸门，不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage128_full_intake_supergate_negative_selftests_passed_no_real_data`
- 重要突破版本：否。它是数据入口编排和 anti-selection 防线增强，不是 alpha 或正式候选。
- 是否触发 A/B：否。没有策略候选。

## 开始前反思

- 是否在过拟合：否。本阶段只编排既有数据验收阶段，不读取盈亏标签、不筛年份/品种/方向、不设交易阈值；默认只跑 empty drop 和 synthetic fixture 两个负例。
- 是否还有价值继续：是。Stage127、Stage125、Stage123 单独可运行，但真实 W0 到货时如果漏跑任一层，仍可能把格式不对、收货不全或 synthetic fixture 送进后续链路。Stage128 把顺序固定下来，减少人工操作错误。

## 外部调研与判断

- Python `subprocess` 官方文档说明推荐用 `subprocess.run()` 处理可覆盖的子进程调用，并可捕获 stdout/stderr 和 returncode。判断：Stage128 应用 `subprocess.run(..., capture_output=True, text=True, check=False)` 串联现有阶段，而不是重写它们的逻辑。
- Python `subprocess` 文档建议用参数序列并用 `sys.executable` 启动当前 Python 解释器。判断：Stage128 每一步都用 `.py311` 当前解释器和参数列表，不用 shell 字符串，减少路径/转义风险。
- Python `argparse` 官方文档用于命令行参数解析。判断：Stage128 应暴露 `--drop-dir` 和 `--expected-stage112-intake`，默认不带参数时跑负例自测。
- pandas `read_csv` 文档用于读取 CSV 数据。判断：Stage128 应读取 Stage127/125/123 的 summary/gate/request CSV，再汇总为自己的 case summary、step summary 和 supergate status。

调研结论：supergate 的正确形状是“编排与汇总”，不是复制已有验收逻辑。Stage128 只负责顺序、returncode、关键 gate 和可视化总览；任一子阶段不 ready 都不能放行。

参考链接：

- https://docs.python.org/3/library/subprocess.html
- https://docs.python.org/3/library/argparse.html
- https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage128_wave0_full_intake_supergate.py`
  - 默认运行两个负例 case：
    - `empty_drop_supergate`
    - `synthetic_fixture_supergate`
  - 每个 case 顺序执行：
    1. Stage127 proof schema bridge
    2. Stage125 receipt preflight
    3. Stage123 intake chain checkpoint
  - 汇总每一步 returncode、decision、stdout JSON 解析状态。
  - 汇总每个 case 的 `stage127_bridge_ready_count`、`stage125_ready_for_stage123`、`stage123_final_stage112_ready_count`、`final_supergate_ready`。
  - 输出 request-level supergate audit，把 Stage127 request proof bridge 和 Stage125 receipt request readiness 合并。
  - 运行结束后自动恢复 Stage127、Stage125、Stage123 默认输出，避免 Stage128 case 覆盖前面阶段的独立记录。
  - 输出 summary、case summary、step summary、supergate status、request audit、report、decision JSON 和 4 张视觉图。

## 参数与结果变更

- 新增参数：
  - `case_count=2`
  - `step_count=6`
  - `all_commands_returncode_zero=1`
  - `negative_selftest_pass=1`
  - `stage123_125_127_default_restored=1`
  - `full_supergate_ready_count=0`
  - `strategy_allowed_count=0`
  - `gate_pass_count=4/12`
  - `data_hard_gate_pass_count=0/4`
  - `real_w0_drop_scanned=0`
  - `real_w0_data_delivered=0`
  - `real_stage112_intake_allowed_now=0`
- 修改参数：无交易参数修改。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前官方路径资金曲线做 supergate 视觉背景。
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

| case | Stage127 bridge ready | Stage125 ready | Stage123 final ready | final supergate | strategy allowed |
| --- | ---: | ---: | ---: | ---: | ---: |
| empty_drop_supergate | 0 | 0 | 0 | 0 | 0 |
| synthetic_fixture_supergate | 0 | 0 | 0 | 0 | 0 |

Gate 解释：

- 两个 case 的 6 个阶段命令 returncode 全部为 `0`，说明编排路径可执行。
- `empty_drop_supergate` 被 Stage127/125/123 全链路阻断，符合预期。
- `synthetic_fixture_supergate` 即使 Stage125 能扫描到 `123` 个 known files，也被 Stage127 schema bridge、Stage125 proof/receipt readiness 和 Stage123 final gate 阻断，不能冒充真实 W0。
- `full_supergate_ready_count=0`、`strategy_allowed_count=0`，所以 Stage112/113、分钟策略预检、true engine、A/B 和正式候选继续阻塞。

## 视觉产物

- official path supergate status：`qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_official_path_supergate_status_stage128_wave0_full_intake_supergate_v1.png`
- case supergate matrix：`qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_case_supergate_matrix_stage128_wave0_full_intake_supergate_v1.png`
- step returncode chart：`qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_step_returncode_chart_stage128_wave0_full_intake_supergate_v1.png`
- request supergate matrix：`qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_request_supergate_matrix_stage128_wave0_full_intake_supergate_v1.png`

视觉观察：

- official path 图保留资金、回撤和 broker10 曲线；W0 request marker 只表示待验收窗口，不是交易信号。底部 case outcome 全为 0，说明没有任何 case 通过 supergate。
- case supergate matrix 显示三个阶段 returncode 均为绿色，但 Stage127 ready、Stage125 ready、Stage123 final ready、final supergate、strategy allowed 全红，清楚区分“命令跑通”和“数据放行”。
- step returncode chart 显示 `stage127_schema_bridge`、`stage125_receipt_preflight`、`stage123_intake_chain` 在两个 case 下全部 returncode=0。
- request supergate matrix 全红，说明 first case 的 41 个 request 没有任何一个完成 proof bridge、receipt preflight 或 full supergate。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage128_wave0_full_intake_supergate/qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_report_stage128_wave0_full_intake_supergate_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage128_wave0_full_intake_supergate/qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_summary_stage128_wave0_full_intake_supergate_v1.csv`
- case summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage128_wave0_full_intake_supergate/qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_case_summary_stage128_wave0_full_intake_supergate_v1.csv`
- step summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage128_wave0_full_intake_supergate/qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_step_summary_stage128_wave0_full_intake_supergate_v1.csv`
- supergate status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage128_wave0_full_intake_supergate/qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_supergate_status_stage128_wave0_full_intake_supergate_v1.csv`
- request audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage128_wave0_full_intake_supergate/qmt_roll_stage128_c9_minrisk_wave0_full_intake_supergate_request_supergate_audit_stage128_wave0_full_intake_supergate_v1.csv`

## 结论

Stage128 证明：真实 W0 到货后的入口已经可以用一条 supergate 固定为 Stage127 -> Stage125 -> Stage123，且默认 empty/synthetic 两类负例都不会被误放行。命令链路可执行，但没有真实 W0 时所有 data/final hard gate 仍失败。

当前真实状态仍是 `full_supergate_ready_count=0`、`real_w0_data_delivered=0`、`real_stage112_intake_allowed_now=0`、`true_engine_allowed=0`、`strategy_feature_usable=0`。因此微观结构/分钟规则预检、true engine、A/B 和正式候选继续阻塞。

## 后续规划和 TODO

1. 真实 W0 drop 到货后，只需要先跑：`.py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage128_wave0_full_intake_supergate.py --drop-dir <real_drop_dir> --expected-stage112-intake 1`
2. 只有 Stage128 `full_supergate_ready_count>0` 且 `strategy_allowed_count=0` 时，才允许继续 Stage112/113；仍不能直接进入策略研究。
3. Stage112/113 通过前，继续禁止用 synthetic、模板 proof、旧 OHLC、本地 Tq tick 或 smoke 数据构造分钟进出场规则。
4. 若真实 W0 迟迟不到，只能继续做数据入口防错、授权数据采购/落盘准备或外生数据覆盖审计，不能绕过 hard gate。

## 结束反思

- 是否在过拟合：否。Stage128 没有任何交易条件或收益参数，只是把数据验收顺序固定成不可跳步链路，并用 empty/synthetic 负例证明不会误放行。
- 是否还有价值继续：有。它把 Stage127/125/123 从多个独立脚本变成真实到货可执行的一键入口，降低未来手工操作误差；但它本身不推进 alpha，真正策略研究仍等待授权 W0 数据通过 Stage128、Stage112 和 Stage113。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage128 full intake supergate 状态。
- 是否更新 `research/registry.md`：否。本阶段不新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破或跨线合入。
