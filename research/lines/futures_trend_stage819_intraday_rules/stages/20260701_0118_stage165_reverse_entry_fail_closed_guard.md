# Stage165：reverse_entry broker10 cap fail-closed guard

- 研究线：`futures_trend_stage819_intraday_rules`
- 工作模式：`day`
- 执行时间：`2026-07-01 01:18 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 分支：`master`
- 当前 live profile：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 本阶段性质：执行安全 guard + 单测 + 只读 shadow 验证，不做 alpha 优化，不连接 CTP，不调用订单 API。

## 外部调研与判断

按用户约束，本阶段不做外部搜索；只使用当前仓库源码、Stage160/162/163/164 输出、当前 official live SOP、本地测试和 Stage901 只读 shadow。

判断：Stage163 已证明当前 Stage830/847/901 输出没有 reverse 交易命中，因此这不是当前已复现 P0/P1 bug；Stage164 已补 `entry_context` 可观测性。剩下的问题是未来如果出现 `reverse_entry`，Stage830 原先对非 flat entry 只是 `not_flat_entry` 后返回原 sizing，会让反手开仓绕开 broker10 cap。直接把 flat-entry projected broker10 公式套到 reverse 又会因旧仓平仓保证金释放时序不明而双算/漏算。因此本阶段采用更保守的 fail-closed：cap 开启时，`reverse_entry` 只允许先平旧仓，不直接反手开新仓；后续若信号仍成立，再按 flat-entry 路径重新评估。

## 本次版本变更

修改文件：

- `examples/portfolio_backtesting/analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap.py`
- `examples/portfolio_backtesting/analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py`
- `examples/portfolio_backtesting/analyze_qmt_roll_stage160_current_live_logic_healthcheck.py`
- `tests/test_qmt_entry_context_diagnostics.py`

策略逻辑变化：

- Stage830 broker10 cap 开启且 `entry_context == "reverse_entry"` 时：
  - `selected_volume = 0`
  - `stage830_broker10_margin_cap_applied = 1`
  - `stage830_broker10_margin_cap_reason = "reverse_entry_fail_closed"`
  - 写入 `broker10_margin_cap_reverse_entry_fail_closed` 诊断事件
- flat-entry 原有 projected broker10 100% 降手数逻辑不变。
- 非 flat 且非 reverse 的路径仍保持原先 `not_flat_entry` 行为。

新增参数：无。

修改参数：无。

删除参数：无。

## TDD 过程

新增红灯测试：

```bash
.py311/bin/python -m unittest tests.test_qmt_entry_context_diagnostics
```

红灯结果：

- `test_stage830_broker10_cap_fail_closes_reverse_entry` 失败。
- 失败原因：Stage830 `_calculate_entry_sizing()` 中没有 `entry_context == "reverse_entry"` guard，也没有 `reverse_entry_fail_closed` reason。

实现最小 guard 后，绿灯：

```bash
.py311/bin/python -m unittest tests.test_qmt_entry_context_diagnostics tests.test_official_live_config_import
```

结果：`Ran 4 tests ... OK`

## 健康闸门验证

执行：

```bash
.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage162_official_live_pre_shadow_health_gate.py
```

结果：

- Stage160 check_count：`11`
- Stage160 status_counts：`9 PASS / 2 WARN`
- Stage162 gate_status：`pass_with_warnings`
- exit_code：`0`
- fail_count：`0`
- warn_count：`2`
- order_api_called：`false`
- send_order_api_called_count：`0`
- cancel_order_api_called_count：`0`
- ctp_connected：`false`

变化说明：

- 原 `broker10_cap_flat_entry_scope` WARN 已升级为 `broker10_cap_reverse_entry_guard` PASS。
- 仍保留的两个 P2 WARN：
  - `c9_synthetic_trade_datetime_semantics`
  - `stage901_global_state_restore`

## Stage901 只读 shadow 验证

按官方实盘 SOP，保持现有 Stage901 口径不变，只读重跑：

```bash
.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py \
  --analysis-start 2026-06-16 \
  --target-date 2026-06-30
```

结果：

- analysis_start：`2026-06-16`
- analysis_end：`2026-06-30`
- latest_available_data_date：`2026-06-30`
- AI 池最新 eval_date：`2026-05-29`
- AI 池最新品种：`SA/MA/OI/si/AP/FG/SM/jm/fu`
- risk_level：`normal`
- target_signal_count：`0`
- pending_order_count：`0`
- current_position_count：`1`
- order_api_called：`false`
- send_order_api_called_count：`0`
- cancel_order_api_called_count：`0`

解释：当前窗口没有 reverse 命中，因此本次 guard 不改变当前 Stage901 信号/持仓结论；它只收敛未来 reverse 信号触发时的执行边界。

## 回测指标

本阶段没有新增完整策略回测，不应把 guard 验证当成收益指标。

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## 逻辑 bug 判断

当前已复现 bug：否。

已修复潜在执行边界：是。

理由：

- 当前输出没有 reverse 事件，说明不是当前实盘已发生错误。
- 源码存在 long->short / short->long 反手路径；如果未来触发，旧逻辑会在 broker10 cap 开启时对 reverse 直接放行。
- 新逻辑选择 fail-closed，而不是用可能双算旧仓保证金的 post-close projection 公式。

## 反过拟合反思

开始前判断：否。目标是修执行边界，不基于收益、年份、品种、方向或窗口反推参数。

结束后判断：否。新增 guard 只在 future reverse_entry 且 broker10 cap 开启时生效；当前 Stage901 无 reverse 命中，结果不靠收益反馈成立。

## 继续价值反思

开始前判断：有价值。Stage160/163 已经暴露 reverse cap 是真实工程边界，继续修它比继续扫 C9 参数更接近当前目标。

结束后判断：有价值。当前健康闸门 WARN 从 `3` 降到 `2`，剩余风险更明确；下一步可以继续收敛 C9 synthetic trade datetime 或 Stage901 全局状态恢复。

## 决策

决策：`stage165_reverse_entry_fail_closed_guard_promoted_to_current_guard`

解释：

- 该 guard 不作为 alpha 优化或收益增强。
- 该 guard 是实盘执行安全边界：在不能可靠计算反手后保证金释放的情况下，先不允许同根/同日直接反手新开。
- 当前 official live shadow 没有 reverse 命中，信号和 pending 仍为 `0`，订单 API 仍为 `0`。

## 后续 TODO

1. Stage166：修正或显式化 C9 synthetic trade datetime 语义，避免 TCA/实盘审计混淆分钟触发时间和 engine 当前时间。
2. Stage167：把 Stage901 对 Stage660 全局状态的临时 mutation 改为更显式的 profile/context 注入，或至少补更强的恢复/并发检查。
3. 不继续扫 C9 的 R 倍数、重试次数、月份、品种、方向或窗口。
