# Stage100 absorption reclaim 分钟候选只读预检

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 14:42 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读分钟候选预检；不是真引擎、不生成交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Backtrader order 文档：`https://www.backtrader.com/docu/order/`
  - Backtrader order creation/execution 文档：`https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/`
  - NautilusTrader backtesting 文档：`https://nautilustrader.io/docs/latest/concepts/backtesting/`
  - vn.py `BarGenerator` 源码：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`
  - GitHub `hftbacktest`：`https://github.com/nkaz001/hftbacktest`
  - GitHub `nautilus_trader`：`https://github.com/nautechsystems/nautilus_trader`
- 我的判断：分钟级执行候选必须先区分“当时可见的可行动信号”和“等官方事件发生后才知道的路径标签”。order/replay 文档和开源高频回放项目都强调事件顺序、bar 内歧义、延迟和成交语义；因此本阶段只做 preflight，不允许把 `C9 stop` 后验展开包装成低风险入场规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage100_absorption_reclaim_preflight.py`
- 修改脚本：无
- 删除脚本：无
- 新增候选 spec：
  - 使用 Stage045 已校准 `timestamp_ready=1` replay 子集。
  - 入场后若先出现持仓方向逆向测试，再由后续分钟收盘价重新收回开仓价，标记为 `delayed_absorption_reclaim`。
  - 如果逆向测试和收回开仓价发生在同一根分钟K，标记为 `same_bar_adverse_reclaim_ambiguous`，不允许交易化。
  - 如果 C9 first event 前没有逆向测试，标记为 `direct_no_adverse_before_c9_event`。
  - 如果逆向测试后到 C9 first event 前没有收回开仓价，标记为 `adverse_no_reclaim_before_c9_event`。
- 新增参数：
  - `EPS=1e-10`
  - `MAX_ATLAS_BARS=90`
  - `MAXDD_START=2022-05-30`
  - `MAXDD_END=2023-03-09`
  - `ATLAS_ROWS=20`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage045 timestamp-ready initial orders，共 `219` 笔。
- 账户规模：沿用基准路径，仅作背景路径。
- 成本口径：沿用基准统计，总滑点 `2,730,130`。
- 样本过滤：无新增收益过滤；right-tail/bottom-loss 只用于视觉 cohort。
- 策略/归因口径：只读 preflight，`preflight_rule_allowed=0`、`true_engine_allowed=0`、`strategy_feature_usable=0`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot win rate `36.0902%`
- 其他关键指标：
  - `decision=stage100_absorption_reclaim_preflight_mixed_no_rule`
  - `timestamp_ready_order_count=219`
  - `acceptance_state_count=4`
  - `delayed_absorption_reclaim_order_count=76`
  - `delayed_absorption_reclaim_pnl_sum=21,670,547.30`
  - `right_tail_visual_count=18`
  - `bottom_loss_visual_count=18`
  - `maxdd_context_order_count=24`
  - `same_bar_ambiguity_order_count=1`
  - `pnl_mixed_state_count=2`
  - `tail_conflict_state_count=2`
  - `adverse_no_reclaim_c9_stop_order_count=56`
  - `delayed_reclaim_c9_progress_order_count=37`
  - `delayed_reclaim_c9_progress_pnl_sum=27,195,110.00`
  - `promotion_gate_count=5`
  - `promotion_gate_pass_count=0`
  - `official_config_changed=0`、`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`

## 视觉观察

- official path chart：四类 acceptance state 都分布在主要权益阶段。红色 `adverse_no_reclaim_before_c9_event` 在 2022-2023 回撤段较多，但这只是路径形态，不自动等于可提前交易信号。
- state contribution chart：`adverse_no_reclaim_before_c9_event` 贡献曲线单调向下，合计 `-4,577,374.70`；但 state-event 交叉显示它 `56/56` 都是 `C9 stop`，说明它主要是官方止损前路径的后验描述。
- state summary chart：`delayed_absorption_reclaim` 净 PnL 很高，但同时包含 `10` 个 right-tail 和 `8` 个 bottom-loss；`direct_no_adverse_before_c9_event` 也包含 `8` 个 right-tail 和 `7` 个 bottom-loss。这两个状态不能作为低风险开关。
- promotion gate chart：right-tail protection、bottom-loss separation、state PnL mixture、same-bar ordering ambiguity、tail state conflict 全部 blocked。
- atlas：`OI309/jm2509` 显示 delayed reclaim 可以承载大右尾；`cu2307/ru2409` 显示同一 delayed reclaim 也会落到大亏；`lh2411/sp2301` 等 adverse-no-reclaim 样本在 C9 stop 前没有收回开仓价，但动作时点高度接近现有止损语义。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage100_absorption_reclaim_preflight/qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_report_stage100_absorption_reclaim_preflight_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage100_absorption_reclaim_preflight/qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_summary_stage100_absorption_reclaim_preflight_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage100_absorption_reclaim_preflight/qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_decision_stage100_absorption_reclaim_preflight_v1.json`
- preflight rows：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage100_absorption_reclaim_preflight/qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_preflight_rows_stage100_absorption_reclaim_preflight_v1.csv`
- state summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage100_absorption_reclaim_preflight/qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_state_summary_stage100_absorption_reclaim_preflight_v1.csv`
- state event summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage100_absorption_reclaim_preflight/qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_state_event_summary_stage100_absorption_reclaim_preflight_v1.csv`
- promotion gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage100_absorption_reclaim_preflight/qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_promotion_gate_stage100_absorption_reclaim_preflight_v1.csv`
- atlas manifest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage100_absorption_reclaim_preflight/qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_atlas_manifest_stage100_absorption_reclaim_preflight_v1.csv`
- charts：
  - `qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_official_path_chart_stage100_absorption_reclaim_preflight_v1.png`
  - `qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_state_contribution_chart_stage100_absorption_reclaim_preflight_v1.png`
  - `qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_state_summary_chart_stage100_absorption_reclaim_preflight_v1.png`
  - `qmt_roll_stage100_c9_minrisk_absorption_reclaim_preflight_promotion_gate_chart_stage100_absorption_reclaim_preflight_v1.png`
  - `atlas_page001` 至 `atlas_page005`

## 结论

- 本阶段结论：absorption/reclaim 思路与旧 no-follow、hard-exit、min-risk、breakeven、reentry-candle 不同构，但当前 preflight 不能 promotion。
- 原因：
  - `delayed_absorption_reclaim` 和 `direct_no_adverse_before_c9_event` 同时承载 right-tail 与 bottom-loss，不能直接决定开仓、恢复、降仓或退出。
  - `adverse_no_reclaim_before_c9_event` 虽然全负，但 `56/56` 都对应 `C9 stop`，属于官方止损事件前路径的后验展开，不能直接当成入场时可见的独立信号。
  - 同根逆向测试并收回开仓价有 bar 内排序歧义，必须保持不可交易。
- 下一步：不进入 true engine，不触发 A/B。若继续本分支，只允许 Stage101 做 lead-time 可行动性诊断：测量 adverse touch 到 C9 stop 的提前量、是否多数只有 `0-1` 根、是否会和 delayed-reclaim 右尾混淆；不得扫 reclaim bar、adverse depth、窗口、品种、方向、年份或月份。

## 过拟合反思

- 运行前判断：否。候选 spec 来自“逆向测试后市场是否重新接受开仓价”的第一性执行语义，不根据收益选择阈值。
- 运行后判断：否。虽然发现 `adverse_no_reclaim` 全负，但我没有把它写成规则；因为它完全对应 `C9 stop`，直接交易化会把后验止损事件伪装成先验信号。
- 原因：right-tail/bottom-loss 只用于视觉 cohort，所有 promotion gate 预设为只读失败条件；没有扫窗口、阈值、品种、方向、年份或月份。

## 继续价值反思

- 运行前判断：有价值。Stage099 指向回到 timestamp-ready replay，新候选必须不同构；absorption/reclaim 可以检验“市场承接风险”而非再看 no-follow。
- 运行后判断：有有限价值。这个 spec 不值得进 true engine，但它揭示了一个重要边界：干净的负状态如果只在 C9 stop 时才确认，就没有行动价值。
- 原因：下一步价值只在 lead-time 可行动性审计，而不是在 absorption/reclaim 上调参。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage100 摘要和 Stage101 边界。
- 是否更新 `research/registry.md`：否，不是正式候选、重要突破或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、重要突破或跨线合并。
