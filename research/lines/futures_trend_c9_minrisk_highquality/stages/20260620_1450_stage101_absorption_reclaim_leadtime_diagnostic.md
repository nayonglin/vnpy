# Stage101 absorption/reclaim lead-time 可行动性诊断

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 14:50 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读 lead-time 可行动性诊断；不是真引擎、不生成交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Backtrader order creation/execution 文档：`https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/`
  - NautilusTrader backtesting 文档：`https://nautilustrader.io/docs/latest/concepts/backtesting/`
  - GitHub `hftbacktest`：`https://github.com/nkaz001/hftbacktest`
  - hftbacktest docs：`https://hftbacktest.readthedocs.io/en/py-v2.2.0/`
- 我的判断：bar 级别预检可以看路径结构，但只要动作点靠近止损或依赖同根内顺序，就不能当成可执行规则。Backtrader 明确强调当前 bar 已经发生，不能用正在观察的 close 去成交；NautilusTrader 也把 bar 数据视为低成本起点，精确时点敏感策略需要更高颗粒数据；hftbacktest 的核心也是 tick/order book/latency/queue。Stage101 的重点因此不是证明 `adverse_no_reclaim` 全负，而是证明它是否有足够提前量和不伤右尾的动作点。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage101_absorption_reclaim_leadtime_diagnostic.py`
- 修改脚本：无
- 删除脚本：无
- 新增诊断字段：
  - `bars_from_adverse_to_event`
  - `minutes_from_adverse_to_event`
  - `bars_from_reclaim_to_event`
  - `adverse_to_event_bucket`
  - `bad_state_stop`
  - `delayed_reclaim_progress`
  - `first_adverse_action_would_hit_right_tail`
- 新增 lead bucket：
  - `same_bar_event`
  - `one_bar_lead`
  - `two_to_five_bars`
  - `six_to_twenty_bars`
  - `gt_twenty_bars`
  - `no_adverse`
  - `no_event`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage100 preflight rows，共 `219` 笔 Stage045 timestamp-ready orders。
- 账户规模：沿用基准路径，仅作背景路径。
- 成本口径：沿用基准统计，总滑点 `2,730,130`。
- 样本过滤：无新增收益过滤；lead bucket 只用于只读诊断和 atlas 选择。
- 策略/归因口径：只读 lead-time 诊断，`leadtime_rule_allowed=0`、`true_engine_allowed=0`、`strategy_feature_usable=0`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot win rate `36.0902%`
- 其他关键指标：
  - `decision=stage101_leadtime_not_actionable_no_rule`
  - `timestamp_ready_order_count=219`
  - `bad_state_c9_stop_order_count=56`
  - `bad_state_same_bar_order_count=30`
  - `bad_state_le_one_bar_order_count=37`
  - `bad_state_le_one_bar_ratio=0.6607`
  - `bad_state_le_five_bar_order_count=41`
  - `bad_state_le_five_bar_ratio=0.7321`
  - `bad_state_median_bars_to_event=0.0000`
  - `bad_state_median_minutes_to_event=0.0000`
  - `bad_state_gt_twenty_bar_order_count=6`
  - `delayed_reclaim_right_tail_count=10`
  - `delayed_reclaim_bottom_loss_count=8`
  - `delayed_reclaim_progress_pnl_sum=27,195,110.00`
  - `promotion_gate_count=6`
  - `promotion_gate_pass_count=0`
  - `official_config_changed=0`、`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`

## 视觉观察

- official path chart：坏状态 stop 样本在主要权益阶段都有出现；底部 lead bucket 显示 `same_bar_event` 为最大桶，说明主要坏标签没有提前动作空间。
- lead bucket chart：`same_bar_event` `30` 笔、PnL `-2,330,541.70`；`one_bar_lead` `7` 笔；合计 `37/56=66.0714%` 只有 `0-1` 根提前量。`<=5` 根合计 `41/56=73.2143%`。
- state event lead chart：坏状态各 lead bucket 全负，但 delayed-reclaim/progress 的 `gt_twenty_bars` 承载 `19,439,310` 右尾贡献，说明“首次逆向测试”并非坏信号；直接在 first adverse touch 动作会伤右尾。
- atlas：`cu2203/fu2310` 展示少数长提前量坏样本，但要捕获它们必须引入等待窗口；`jm2509/OI309` 展示同样先有逆向测试但后续成为右尾，反证 first-adverse 动作。
- gate chart：六个 gate 全部 blocked；核心阻断是 `no_reclaim_confirmation_too_late`、`same_bar_stop_ordering_ambiguity` 和 `first_adverse_touch_hits_right_tail`。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage101_absorption_reclaim_leadtime_diagnostic/qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic_report_stage101_absorption_reclaim_leadtime_diagnostic_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage101_absorption_reclaim_leadtime_diagnostic/qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic_summary_stage101_absorption_reclaim_leadtime_diagnostic_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage101_absorption_reclaim_leadtime_diagnostic/qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic_decision_stage101_absorption_reclaim_leadtime_diagnostic_v1.json`
- leadtime rows：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage101_absorption_reclaim_leadtime_diagnostic/qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic_leadtime_rows_stage101_absorption_reclaim_leadtime_diagnostic_v1.csv`
- lead bucket summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage101_absorption_reclaim_leadtime_diagnostic/qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic_lead_bucket_summary_stage101_absorption_reclaim_leadtime_diagnostic_v1.csv`
- state event lead summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage101_absorption_reclaim_leadtime_diagnostic/qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic_state_event_lead_summary_stage101_absorption_reclaim_leadtime_diagnostic_v1.csv`
- promotion gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage101_absorption_reclaim_leadtime_diagnostic/qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic_promotion_gate_stage101_absorption_reclaim_leadtime_diagnostic_v1.csv`
- atlas manifest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage101_absorption_reclaim_leadtime_diagnostic/qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic_atlas_manifest_stage101_absorption_reclaim_leadtime_diagnostic_v1.csv`
- charts：
  - `qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic_official_path_chart_stage101_absorption_reclaim_leadtime_diagnostic_v1.png`
  - `qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic_lead_bucket_chart_stage101_absorption_reclaim_leadtime_diagnostic_v1.png`
  - `qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic_state_event_lead_chart_stage101_absorption_reclaim_leadtime_diagnostic_v1.png`
  - `qmt_roll_stage101_c9_minrisk_absorption_reclaim_leadtime_diagnostic_promotion_gate_chart_stage101_absorption_reclaim_leadtime_diagnostic_v1.png`
  - `atlas_page001` 至 `atlas_page005`

## 结论

- 本阶段结论：`adverse_no_reclaim` 的 lead-time 不具备可行动性，absorption/reclaim 分支应关闭。
- 原因：
  - 坏状态 `56` 笔中 `30` 笔首个 adverse touch 与 C9 stop 同根；`37` 笔只有 `0-1` 根提前量，中位提前量为 `0`。
  - 若试图在 first adverse touch 就行动，会命中 `10` 个 delayed-reclaim right-tail 样本；这不是高质量信号的最小风险，而是砍掉趋势右尾的前奏。
  - 少数长提前量坏样本需要等待窗口或深度条件才能捕获，这会变成参数救援。
- 下一步：不进入 true engine，不触发 A/B。不得继续围绕 adverse/reclaim/lead bucket 设窗口、深度、R 倍数、产品、方向、年份或月份。若继续当前目标，应换一个与 absorption/reclaim 无关的新第一性候选，或回到 Stage099 的授权盘口/队列/成交流数据工程路线。

## 过拟合反思

- 运行前判断：否。Stage101 只是验证 Stage100 负标签是否真的有可行动提前量。
- 运行后判断：否。结果明确关闭该分支，没有用少数 `gt_twenty_bars` 坏样本反推等待窗口。
- 原因：所有 gate 预先围绕可行动性和右尾保护，不涉及收益阈值、品种、方向、年份或月份切片。

## 继续价值反思

- 运行前判断：有价值。Stage100 显示 `adverse_no_reclaim` 全负但疑似后验，必须查提前量。
- 运行后判断：该分支继续调参没有价值；研究线继续有价值，但应换候选或补更细数据。
- 原因：`0-1` 根提前量占 `66.0714%`，说明大多数坏标签到确认时已经接近/到达官方 C9 stop；first adverse 又会误伤右尾。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage101 摘要和下一步边界。
- 是否更新 `research/registry.md`：否，不是正式候选、重要突破或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、重要突破或跨线合并。
