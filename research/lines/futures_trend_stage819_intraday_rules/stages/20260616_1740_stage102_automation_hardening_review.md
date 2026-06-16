# Stage102 C9/15w 自动化执行安全 hardening 与复审

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-16 17:40 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方实盘自动化执行链路安全修复、dry-run 验证、独立 agent 复审
- 是否重要突破：是，修复了 live-real 自动开平仓前的 P0/P1 级执行安全缺口，并把 Stage927/Stage932 拆成 pre-smoke 与 real-submit 两级闸门
- 是否触发A/B：否；本轮只改执行安全状态机，不改 C9 alpha、参数、品种池或回测入口

## 外部调研与判断

- 参考资料：
  - vn.py / vnpy_ctp 本地源码语义：`MainEngine.send_order/cancel_order` 为网关透传；真实成交价格与成交量应来自 trade event；订单回报里的 `traded` 也必须用于 smoke 成交交叉验证。
  - Python `fcntl.flock` 语义：本地单机 JSONL ledger reserve 可在同一文件锁内读、判重、追加，避免并发重复预留。
  - 前序执行风控资料结论：自动交易必须有预交易闸门、幂等、撤单终态确认、kill switch、重启边界、对账闭环。
- 我的判断：
  - 本轮不涉及策略过拟合；风险来自执行状态机漏判，而不是样本选择。
  - 自动化链路现在没有发现新的 P0/P1 静态问题，但因为 Stage927 当前仍 fail-closed，不能称为已进入无人值守实盘自动交易。

## 本次变更

- 新增脚本：
  - 无。
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_official_live_execution_ledger.py`
    - close intent 增加 `residual_order_unknown_after_cancel` 硬阻断。
    - intent fingerprint 改为只按经济意图哈希，排除 `limit_price/source/source_reason/reference`，避免价格、来源、枚举 reference 变化绕过幂等。
  - `examples/portfolio_backtesting/run_qmt_roll_stage902_official_live_phase_d_readiness_gate.py`
    - 增加 `blocking_failure_count_for_reduce_close`，review 风险下普通 broker-matched 平仓/减仓不被 `official_risk_allows_new_orders` 误挡。
  - `examples/portfolio_backtesting/run_qmt_roll_stage905_official_live_executor_dry_run.py`
    - close intent 使用 reduce-close 专用 blocking count。
  - `examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`
    - 撤单后只要 `residual_volume > 0` 且订单状态未知或仍 active，就写入 residual blocker 和 ledger event，并 fail-closed。
  - `examples/portfolio_backtesting/run_qmt_roll_stage932_official_live_ctp_smoke_order.py`
    - submit-cancel 前增加 Phase D execution session gate、readonly active order gate、fresh tick age gate。
    - clean smoke 必须同时满足：撤单后明确非 active、trade rows 成交量为 0、final order `traded/volume_traded` 为 0。
    - 空合约文件不再崩溃，改为 fail-closed。
  - `examples/portfolio_backtesting/run_qmt_roll_stage927_official_live_real_submit_arming_gate.py`
    - Stage932 clean smoke 纳入 real-submit hard gate。
    - 增加 `pre_smoke_permitted` 与 `pre_smoke_blocking_failure_count`，用于允许一手 smoke；`real_submit_permitted` 仍要求 clean smoke，避免 Stage927/Stage932 循环依赖。
- 删除脚本：无。
- 新增参数：
  - Stage932：`--max-tick-age-seconds`。
- 修改参数：
  - 无。
- 删除参数：
  - 无。

## 回测/归因参数

- 数据区间：不适用。
- 账户规模：C9/15w 当前官方实盘口径。
- 成本口径：不适用。
- 样本过滤：不适用。
- 策略/归因口径：不改 C9 策略逻辑，仅执行链路 hardening。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - `py_compile`：Stage902/904/905/927/930/931/932 与 ledger 通过。
  - ledger 单元验证：fingerprint 排除 price/source/reference；`residual_order_unknown_after_cancel` close 硬阻断。
  - Stage905 单元验证：review 下 broker-matched 普通 close 可放行，新开仓仍受限。
  - Stage932 单元验证：active order gate 可阻断；`final_order_traded` 从 `traded/volume_traded` 交叉验证。
  - Stage927 dry-run：`real_submit_permitted=0`，`order_api_called_count=0`；当前仍 fail-closed。
  - Stage930 supervisor dry-run：`daemon_completed_max_cycles`，`order_api_called_count=0`。
  - launchd 状态：night/day 两个 LaunchAgent 已加载、当前 not running、无 KeepAlive、触发时间 20:55/08:55。
  - 最后独立复审：无 P0/P1，Stage927/Stage932 循环依赖已拆除。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_report_20260616_172343_stage930_official_live_c9_session_daemon_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_report_20260616_173739_stage932_official_live_ctp_smoke_order_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_c9_session_daemon_latest_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage927_official_live_real_submit_arming_gate_summary_20260616_stage927_official_live_real_submit_arming_gate_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_summary_20260616_173739_stage932_official_live_ctp_smoke_order_v1.json`
- orders：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_orders_20260616_173739_stage932_official_live_ctp_smoke_order_v1.csv`
- daily：不适用。
- quality：
  - 独立 agent 复审结论：Tesla 初审剩一个 P1；修复后 Newton 短复审无 P0/P1；Averroes 极短复审确认 Stage927/Stage932 无 arming 循环。

## 结论

- 本阶段结论：
  - 第三方 review 提出的执行安全 P0/P1 已逐项修复并复审通过。
  - 当前链路可继续保留 dry-run/read-only/report 自动化；real-submit 仍由 Stage927 fail-closed 阻断，直到 broker/影子对账、pre-smoke、clean smoke 证据满足。
- 是否进入下一步：
  - 是，但下一步是实盘前置状态恢复与受控 smoke，不是直接无人值守交易。
- 下一步：
  - 在真实 CTP env/runtime 可用且执行时段内，先刷新 readonly broker 快照和 Stage906 对账，使 `pre_smoke_permitted=1`。
  - 然后执行一手 Stage932 smoke；只有 `submit_cancel_confirmed/smoke_passed=1/trade_volume=0/final_order_traded=0` 后，Stage927 才允许后续 Stage931 live-real。
  - 若出现成交、撤单未知、残余 active 或 broker 快照陈旧，保持 fail-closed 并人工对账。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本轮全部是执行闸门、幂等、撤单终态、smoke 证据和 supervisor/launchd 安全边界，不修改策略参数、品种、方向、R 倍数、训练窗或样本。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：这些修复直接降低自动交易误下单、重复下单、误判 clean smoke、撤单状态未知继续重试的风险；继续推进的价值在于真实环境 gate 和 smoke 验收，而不是继续改策略。

## 合入建议

- 是否更新本线 `LINE.md`：建议后续合入时更新，说明 Stage102 执行安全 hardening 与 Stage927/932 两级闸门。
- 是否更新 `research/registry.md`：建议后续合入时更新当前研究线最新阶段。
- 是否追加根目录 `memory.md/back_log.md`：建议仅在完成真实 clean smoke 或首次真实自动开平仓后追加；本阶段先保留在线内 stage 记录。
