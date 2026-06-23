# Stage039 订单事件回放语义修复审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 01:17 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读 replay 语义修复审计；不新增交易规则，不改正式配置，不连接 CTP，不调用订单 API。
- 是否重要突破：否。属于分钟回放底座修复，不是收益候选或正式候选。
- 是否触发A/B：否。`candidate_ready=0`，`ab_triggered=0`，`rule_added=0`，`official_config_changed=0`。

## 外部调研与判断

- 参考资料：
  - vn.py `BacktestingEngine`：https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py
  - Backtrader order execution： https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - Backtrader broker/order docs： https://www.backtrader.com/docu/broker/
  - NautilusTrader backtesting docs： https://nautilustrader.io/docs/latest/concepts/backtesting/
- 我的判断：
  - vn.py BAR 模式在每根 bar 上用 open/high/low 定义限价/停止单是否成交，且订单撮合是前向事件流，不是事后用成交价反推时间戳。
  - Backtrader 和 NautilusTrader 也都强调 Market/Limit/Stop、OHLC 顺序和 timestamp convention 必须明确。
  - 因此 Stage038 后的下一步应先修 replay 语义，不应马上写分钟进出场规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage039_order_event_replay_semantics_repair_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无策略参数；新增审计 variant：
  - `stage038_first_stage861_open`
  - `initial_only_official_open_anchor`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage010 官方 C9/15w full path，`2018-01` 起至 `2026-06` 口径。
- 账户规模：`150,000`
- 成本口径：沿用官方 C9/15w ledger，总滑点 `2,730,130`。
- 样本过滤：
  - official open trades 共 `387` 条。
  - 识别 C9 synthetic reentry open：`order_id` 形如 `.stage847_c9.2`，共 `54` 条。
  - initial strategy open：`333` 条。
  - opened candidates：`326`，matched initial orders：`324`，Stage861 replay ready：`322`。
- 策略/归因口径：
  - 本阶段不是策略回测，只比较 replay 语义一致性。
  - variant A：沿 Stage038，用 first Stage861 bar open 作为 replay fill。
  - variant B：排除 reentry open 后，用 official open price 作为事件语义锚点。

## 结果

- 官方期末权益：`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`
- 官方 Sharpe：`1.6331`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- closed-lot 胜率：`36.0902%`
- 其他关键指标：
  - Stage038 first Stage861 open event-family match rate：`67.0807%`
  - official open anchor event-family match rate：`97.5155%`
  - official open anchor mismatch orders：`8`
  - first-stop time match：从 `38` 提升到 `122`
  - reentry time match：从 `16` 提升到 `54`
  - retry-failed time match：从 `9` 提升到 `26`
  - C2 hit time match：从 `4` 提升到 `13`
  - same-exit first Stage861 open 曲线最大回撤约 `-59.4614%`，仍显著偏离 official。
  - official open anchor same-exit 曲线与 official 基本重合，因为它使用官方成交价锚点；这不是可交易候选，只是语义校准。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage039_order_event_replay_semantics_repair_audit/qmt_roll_stage039_c9_minrisk_order_event_replay_semantics_repair_audit_report_stage039_order_event_replay_semantics_repair_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage039_order_event_replay_semantics_repair_audit/qmt_roll_stage039_c9_minrisk_order_event_replay_semantics_repair_audit_summary_stage039_order_event_replay_semantics_repair_audit_v1.csv`
- orders：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage039_order_event_replay_semantics_repair_audit/qmt_roll_stage039_c9_minrisk_order_event_replay_semantics_repair_audit_variant_replay_ledger_stage039_order_event_replay_semantics_repair_audit_v1.csv`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage039_order_event_replay_semantics_repair_audit/qmt_roll_stage039_c9_minrisk_order_event_replay_semantics_repair_audit_same_exit_semantics_curve_stage039_order_event_replay_semantics_repair_audit_v1.csv`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage039_order_event_replay_semantics_repair_audit/qmt_roll_stage039_c9_minrisk_order_event_replay_semantics_repair_audit_event_confusion_stage039_order_event_replay_semantics_repair_audit_v1.csv`
- 视觉：
  - same-exit semantics path chart
  - event match rate chart
  - official anchor confusion chart
  - official-anchor mismatch atlas 2 页

## 结论

- 本阶段结论：
  - Stage038 的主要偏差不是 C9/C2 公式本身，而是成交锚点。first Stage861 bar open 替换 official open 后会造成路径级执行误差。
  - 把 C9 synthetic reentry open 从 initial matching pool 剥离，并用 official open price 做事件语义锚点后，event-family 复现率提升到 `97.5155%`。
  - 但 official open price 仍不是可执行分钟 timestamp。它可以作为事件归因底座，不能直接拿来测试分钟级实盘规则。
- 是否进入下一步：是，但下一步仍是数据工程/语义审计，不是策略候选。
- 下一步：
  - 审计 `_resolve_trade_price` 的 proxy 来源，重建 official open price 对应的可执行 timestamp/proxy ledger。
  - 若无法点时化 official open anchor，就不得用它做分钟开仓、恢复、降仓或退出规则。

## 过拟合反思

- 运行前判断：否。本阶段只修账本语义，预期不会产生交易规则，也没有按年份、品种、方向、月份筛选。
- 运行后判断：否。
- 原因：
  - 没有新增任何收益候选、阈值或筛选条件。
  - 剩余 `8` 笔 mismatch 没有被包装成规则，反而明确标记为边界数据问题。
  - 视觉 atlas 显示 mismatch 是首根/早段触线、zero/near-zero risk 或分钟源边界，不能交易化。

## 继续价值反思

- 运行前判断：有。Stage038 的 67% match 说明 replay 底座还不可信，必须先修。
- 运行后判断：有。
- 原因：
  - 97.5% event-family 复现率证明事件公式已基本对齐，下一步问题收敛到成交价 proxy 和 timestamp。
  - 这能避免后续分钟规则建立在错误成交锚点上，价值高于继续扫策略参数。
  - 但在 `_resolve_trade_price` 点时化前，不应进入新规则实验。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage039 摘要和下一步。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破、正式候选或路线废弃。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段只是本线 replay 底座修复审计。
