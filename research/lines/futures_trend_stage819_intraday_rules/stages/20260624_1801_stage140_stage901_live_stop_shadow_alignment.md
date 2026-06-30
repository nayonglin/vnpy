# Stage140 Stage901 对齐实盘实时止损成交

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-24 18:01 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘执行一致性修复 / 邮件口径修复
- 是否重要突破：是，修复 live shadow 与 Stage904/931 实盘实时止损成交事实不一致的问题
- 是否触发A/B：否，本阶段不改策略 alpha、AI 池、手数、止损阈值或回测参数

## 外部调研与判断

- 参考资料：本轮执行前按仓库要求做了快速外部资料扫描；通用交易系统资料强调止损成交、委托回报和账户对账应作为执行会计事实。最终实现依据以本仓库 `futures-live-execution-sop`、Stage904/905/906/931 execution ledger 与现有 fail-closed 纪律为准。
- 我的判断：影子盘不应只停留在日线理论回放。若 Stage904 实时止损已经通过 Stage931 成交，Stage901 的当前持仓、signal_plan 和 pending_orders 必须消费该成交事实，否则 16:35/21:05 邮件和 Stage260/906 闸门都会继续看到已经不存在的理论 FG 仓位或理论开仓。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2026-06-16` 至 `2026-06-24`
- 账户规模：`150000`
- 成本口径：Stage901 原成本口径，未修改
- 样本过滤：无新增过滤
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，只在 live shadow 输出层应用 Stage904/931 execution ledger 的已成交实时止损事实

## 结果

- 期末权益：`149550.0`
- 总收益：`-0.3%`
- 最大回撤：`-1.3131846377%`
- Sharpe：`-1.0194190685`
- 总滑点：`410`
- 总交易次数：`2`
- 胜率：Stage901 `nonzero_daily_win_rate_pct=50.0`
- 其他关键指标：
  - Stage901 live_stop_alignment：`event_count=2`
  - 有效实时止损扣减：`FG609.CZCE short 15 -> 0`
  - 修复错误 pending 重开后的强平：记录为 `live_bug_repair_close_not_subtracted_from_shadow`，不重复扣 shadow
  - Stage901 输出：`target_signal_count=0`、`pending_order_count=0`、`current_position_count=1`
  - current_positions 只剩 `rb2610.SHFE short 11`
  - Stage260：`signal_count=0`、`execution_candidate_count=0`、`executable_count=0`、`blocked_count=0`、订单 API `0`
  - Stage906 宽松 14400 秒快照验证：`reconcile_aligned`，position diff 为 `rb2610.SHFE short 11/11`
  - Stage929 `--email-policy never`：`signal_details=[]`，报告新增 `Shadow实时止损对齐：事件 2，扣减 1，移除持仓 1，抑制理论开仓 1，抑制pending 0`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_report_stage901_stage847_c9_2026_ytd_live_shadow_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_decision_stage901_stage847_c9_2026_ytd_live_shadow_v1.json`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_pending_orders_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_daily_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_live_stop_alignment_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`

## 结论

- 本阶段结论：已把 Stage901 shadow 输出与实盘实时止损成交对齐。2026-06-24 的 FG 理论开空不再出现在 signal_plan，也不再留在 shadow 当前持仓里；后续邮件和执行闸门看到的是 `signal=0/pending=0/current_position=rb short 11`。
- 是否进入下一步：是，进入后续自动化观察。
- 下一步：20:55/交易时段仍必须用 300 秒内 fresh broker/tick 重新跑提交闸门；若未来出现 Stage904 retry_open 成交，继续检查 Stage901 net stop/retry overlay 是否保持和 broker 对齐。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次没有根据 FG 盈亏去调参数，也没有改变 C9 信号、AI 池、R 倍数、止损价或手数公式；只是把已成交的实盘止损事实写入 shadow 会计状态。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：全自动交易最怕 shadow、broker、executor 三套状态分裂。本修复直接降低重复开仓、错误邮件、错误对账和错误手工追单风险。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage140 当前状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本次是本线执行一致性修复，不是新策略候选或跨线里程碑。
