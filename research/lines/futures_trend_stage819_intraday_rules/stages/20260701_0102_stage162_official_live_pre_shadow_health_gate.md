# Stage162：当前实盘版预 shadow 健康闸门

- 研究线：`futures_trend_stage819_intraday_rules`
- 工作模式：`day`
- 执行时间：`2026-07-01 01:01 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 分支：`master`
- 当前 live profile：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w` / `stage847_c9_15w_stage819_05r_stop_retry_live`
- 本阶段性质：工程 health gate，不是 alpha 优化，不连接 CTP，不调用订单 API。

## 外部调研与判断

本阶段按用户约束不再做外部搜索；调研来源仅限当前仓库的 `memory.md`、`back_log.md`、`research/registry.md`、当前研究线 `LINE.md`、Stage154-161 记录、Stage160 healthcheck 输出，以及本地 SOP `skills/futures-live-execution-sop/SKILL.md`。

判断：当前最值得延续的历史路线不是继续尝试 1:1 复刻旧产物，也不是按旧收益反推参数，而是把已确认有价值的 C9 逻辑放在更严格的执行健康闸门后面。Stage160 已经把 profile、AI PIT、AI 池文件、实时止损重试状态机、订单 API 零调用、pending/signal 输出等关键点列为可检查项；Stage162 将其包装成可直接用于 shadow 或临时信号检查前的阻断闸门。

## 本次版本变更

新增文件：

- `examples/portfolio_backtesting/run_qmt_roll_stage162_official_live_pre_shadow_health_gate.py`

新增输出：

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage162_official_live_pre_shadow_health_gate_summary_stage162_official_live_pre_shadow_health_gate_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage162_official_live_pre_shadow_health_gate_report_stage162_official_live_pre_shadow_health_gate_v1.md`

新增参数：

- `--skip-run-stage160`：复用最近一次 Stage160 输出，不重复跑 healthcheck。
- `--fail-on-warn`：把 WARN 也作为阻断条件；默认只阻断 FAIL。

修改参数：无。

删除参数：无。

策略逻辑改动：无。未修改开仓、平仓、AI 选择、止损、重试、仓位、保证金闸门或邮件发送逻辑。

## 执行命令

```bash
.py311/bin/python -m py_compile \
  examples/portfolio_backtesting/analyze_qmt_roll_stage160_current_live_logic_healthcheck.py \
  examples/portfolio_backtesting/run_qmt_roll_stage162_official_live_pre_shadow_health_gate.py

.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage162_official_live_pre_shadow_health_gate.py

set +e
.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage162_official_live_pre_shadow_health_gate.py \
  --skip-run-stage160 --fail-on-warn >/tmp/stage162_fail_on_warn.out 2>&1
code=$?
echo "exit_code=$code"
test "$code" = 2

.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage162_official_live_pre_shadow_health_gate.py --skip-run-stage160
```

## 结果

默认口径：

- gate_status：`pass_with_warnings`
- exit_code：`0`
- FAIL：`0`
- WARN：`3`
- Stage160 决策：`stage160_no_p0_p1_logic_bug_found_with_p2_warnings`
- Stage160 检查项：`8 PASS / 3 WARN / 0 FAIL`
- order_api_called：`false`
- send_order_api_called_count：`0`
- cancel_order_api_called_count：`0`
- ctp_connected：`false`

严格口径：

- 命令：`--skip-run-stage160 --fail-on-warn`
- 预期：WARN 也阻断。
- 实测退出码：`2`
- 结论：严格模式可用于更保守的正式执行前检查；日常默认模式可继续 shadow，但必须显式暴露 WARN。

## WARN 清单

1. `broker10_cap_flat_entry_scope`
   - 现状：Stage830 broker10 cap 只处理 `flat_entry`。
   - 证据：当前 Stage847/Stage830/Stage901 输出里没有 `reverse_entry` 或 reverse trade event，因此不是已复现 bug。
   - 风险：如果未来出现 reverse entry，可能绕过 broker10 cap。
   - 等级：P2，建议下一阶段做 targeted test 或直接把 reverse path guard 写清楚。

2. `c9_synthetic_trade_datetime_semantics`
   - 现状：Stage847 合成 stop/retry 成交使用 `datetime=self.datetime`，同时在代理字段里记录分钟触发时间。
   - 判断：对日级回测 PnL 不是 P0，但对 TCA、实盘审计、分钟级成交语义有风险。
   - 等级：P2，建议后续把合成成交时间语义显式化。

3. `stage901_global_state_restore`
   - 现状：Stage901 临时修改 Stage660 全局状态，并在 `finally` 中恢复。
   - 判断：当前有恢复保护，不是已复现 bug。
   - 风险：工程边界脆弱，后续应收敛为显式 profile/context 注入。
   - 等级：P2。

## 回测指标

本阶段没有新增策略回测，不应把健康闸门结果当作收益指标。

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## 反过拟合反思

开始前判断：否。本阶段只检查当前实盘 profile、AI 文件、PIT、stop/retry 状态机、订单 API 调用和工程语义，不改任何策略参数。

结束后判断：否。Stage162 不使用收益反馈，不筛选月份、品种、方向、阈值或窗口；它只是把已发现的执行风险变成可复跑的 gate。

## 继续价值反思

开始前判断：有价值。当前最危险的不是再多跑一个收益表，而是实盘前是否存在 profile 漂移、AI 文件缺失、订单 API 误触发、pending/signal 漏看或实时止损重试语义失配。

结束后判断：有价值。`0 FAIL / 3 WARN` 说明没有发现 P0/P1 级执行差错，但三个 P2 风险仍值得继续收敛；下一步应优先做 Stage163 reverse-entry broker10 cap 的 targeted test/guard，而不是继续扫 C9 的小参数。

## 决策

决策：`stage162_gate_pass_with_p2_warnings_no_order_api`

解释：

- 可以把 Stage162 作为当前实盘 shadow 或临时信号检查前的只读健康闸门。
- 默认模式下 `WARN` 不阻断，但必须报告；严格模式下可用 `--fail-on-warn` 阻断。
- 本阶段未发现会导致当前版本立即执行错误的 P0/P1 逻辑 bug。
- 不代表当前重建版已经 1:1 复刻旧正式产物；只代表当前线上 profile 的执行前健康检查可复跑、可阻断。

## 后续 TODO

1. Stage163：针对 `reverse_entry` 路径补 broker10 cap targeted test 或工程 guard，确认未来不会绕过入口保证金闸门。
2. 后续：修正或明确 C9 synthetic trade datetime 语义，避免 TCA/实盘审计时把分钟触发时间和日级 engine 时间混淆。
3. 后续：把 Stage901 的 Stage660 全局状态临时修改收敛为显式 profile/context，降低并行或异常路径脆弱性。
4. 若要接入 daily shadow/临时信号邮件流程，应先由用户确认是否把 Stage162 作为 Stage929/930 前置 gate；本阶段不直接修改 launchd 或正式自动化链路。
