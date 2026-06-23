# Stage038 订单事件回放原型审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 01:05 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读订单事件回放原型审计；不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API。
- 是否重要突破：否；本阶段证明 replay 账本还不够接近官方 ledger，属于进入分钟规则前的工程闸门。
- 是否触发A/B：否，`candidate_ready=0`，`ab_triggered=0`。

## 外部调研与判断

- 参考资料：
  - vn.py CTA backtesting 源码：BAR 模式使用 bar high/low 判断 limit/stop 是否穿越，并用 bar open 作为 best price 参与成交价计算：https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py
  - Backtrader order execution 文档：当前 bar 已经发生，Market 单在下一根 bar open 执行，Limit/Stop 用下一根 OHLC 做穿越推断：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - NautilusTrader backtesting 文档：bar 执行必须明确 close/open timestamp 语义，错误时间戳会产生 look-ahead；bar-only 需把 OHLC 转成事件序列撮合：https://nautilustrader.io/docs/latest/concepts/backtesting/
  - Zipline slippage 源码：订单成交应由独立 slippage/order processing 层处理，不能从成交结果倒推策略时间戳：https://github.com/quantopian/zipline/blob/master/zipline/finance/slippage.py
- 我的判断：Stage038 必须先生成独立 replay orders/trades，并用官方 ledger 做一致性审计；如果 replay 账本不够接近官方成交价和 intraday event，就不能基于它测试任何分钟进出场规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage038_order_event_replay_prototype_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；审计固定 `STOP_RETRY_R=0.5`、`MAX_RETRIES=1`、`MAX_MATCH_CALENDAR_DAYS=14`，仅复刻 C9 既有语义和信号日到开仓日匹配窗口。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage010 官方 C9/15w 路径、official entry candidates/trades/closed lots/intraday events 与 Stage861 full minute 源。
- 账户规模：`150,000`
- 成本口径：复用官方 C9/15w 成本口径；same-exit sensitivity 不重算手续费滑点，只审计 entry price delta。
- 样本过滤：不过滤产品、方向、年份、月份；opened candidates 与 official open trades 全部进入匹配审计。
- 策略/归因口径：
  - 用 opened entry candidates 匹配 initial official open trades。
  - 用 official open date 的 Stage861 第一根 bar open 作为 replay initial fill。
  - 按 replay fill、planned stop、C9 `0.5R stop/retry once` 和 C2 `1R stop before 1R confirm` 机械生成 replay event family。
  - 用 official closed lots 固定 exit/volume/size，生成 same-exit entry replay sensitivity 曲线；该曲线不是候选回测。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26,017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot `36.0902%`
- 其他关键指标：
  - opened candidates：`326`
  - matched initial orders：`324`
  - Stage861 replay ready orders：`322`
  - initial matching 后 unmatched official open trades：`63`
  - replay first-bar open 与 official open 的绝对差：median `10.0000`，p90 `84.8000`，max `2040.0000`
  - event family match rate：`67.0807%`
  - first-stop time match：`38`
  - reentry time match：`16`
  - retry-failed time match：`9`
  - C2 hit time match：`4`
  - same-exit replay 期末权益：`32,983,217.60`
  - same-exit replay 总收益：`21,888.8117%`
  - same-exit replay 最大回撤：`-59.4614%`
  - same-exit replay Sharpe：`1.4517`
  - ready lots entry price delta PnL sum：`-6,193,220.00`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage038_order_event_replay_prototype_audit/qmt_roll_stage038_c9_minrisk_order_event_replay_prototype_audit_report_stage038_order_event_replay_prototype_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage038_order_event_replay_prototype_audit/qmt_roll_stage038_c9_minrisk_order_event_replay_prototype_audit_summary_stage038_order_event_replay_prototype_audit_v1.csv`
- orders：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage038_order_event_replay_prototype_audit/qmt_roll_stage038_c9_minrisk_order_event_replay_prototype_audit_order_replay_ledger_stage038_order_event_replay_prototype_audit_v1.csv`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage038_order_event_replay_prototype_audit/qmt_roll_stage038_c9_minrisk_order_event_replay_prototype_audit_same_exit_sensitivity_curve_stage038_order_event_replay_prototype_audit_v1.csv`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage038_order_event_replay_prototype_audit/qmt_roll_stage038_c9_minrisk_order_event_replay_prototype_audit_event_confusion_stage038_order_event_replay_prototype_audit_v1.csv`
- closed-lot sensitivity：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage038_order_event_replay_prototype_audit/qmt_roll_stage038_c9_minrisk_order_event_replay_prototype_audit_closed_lot_entry_price_sensitivity_stage038_order_event_replay_prototype_audit_v1.csv`
- 视觉：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage038_order_event_replay_prototype_audit/qmt_roll_stage038_c9_minrisk_order_event_replay_prototype_audit_same_exit_sensitivity_path_chart_stage038_order_event_replay_prototype_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage038_order_event_replay_prototype_audit/qmt_roll_stage038_c9_minrisk_order_event_replay_prototype_audit_event_confusion_chart_stage038_order_event_replay_prototype_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage038_order_event_replay_prototype_audit/qmt_roll_stage038_c9_minrisk_order_event_replay_prototype_audit_fill_delta_scatter_stage038_order_event_replay_prototype_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage038_order_event_replay_prototype_audit/qmt_roll_stage038_c9_minrisk_order_event_replay_prototype_audit_atlas_page001_stage038_order_event_replay_prototype_audit_v1.png`

## 视觉观察

- same-exit sensitivity path chart 显示 first Stage861 bar open 替换官方 entry 后，权益曲线从 `2021` 后系统性落后，`2022-2023` 回撤恶化到约 `-59%`，说明当前 replay fill 语义没有复现官方成交价。
- event confusion heatmap 主对角线不足，`no_intraday_event` 复现较多，但 C9/C2 事件存在明显串类：例如官方 `c9_flat_no_reentry` 被 replay 为 `c2_stop`、`c9_flat_retry_failed` 或 `open_no_intraday_event`。
- fill delta scatter 显示大价差集中在高价品种和部分跳开合约，正负 PnL 都有，不具备可交易单调关系。
- atlas page001 显示 mismatch 常来自 replay open 价、planned stop、同 bar stop/progress 保守顺序和官方 first-stop 时间不一致；这类差异是账本语义问题，不是 alpha 线索。

## 结论

- 本阶段结论：`stage038_order_event_replay_prototype_not_close_enough_no_trade_rule`。订单事件回放原型已能生成独立审计账本，但 first-minute fill 与官方 open price 差异、C9/C2 event family 串类和时间戳不匹配仍明显，不能作为新分钟规则测试底座。
- 是否进入下一步：进入 replay 账本修复，不进入候选、不进入 A/B。
- 下一步：先修 order replay 与官方 engine 的一致性，优先解释 candidate -> open trade 匹配、first tradable minute 选择、bar open/close timestamp、同 bar stop/progress 保守顺序、reentry synthetic trade 计数差异；一致性通过前不测试新的分钟进出场规则。

## 过拟合反思

- 运行前判断：否，但有风险。因为 replay 账本如果被拿来挑事件子集，会变成对官方历史成交差异的过拟合。
- 运行后判断：否。
- 原因：本阶段没有把 replay 结果写成收益规则，也没有筛产品、方向、年份、session、clock；same-exit 曲线明确标注为执行价敏感性审计，结论是阻止进一步交易化。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但继续方向必须是账本修复，不是策略优化。
- 原因：目标要求分钟级进出场，但 Stage036/037/038 连续证明真实开仓分钟和事件回放语义仍不足。修到账本一致，是避免以后所有分钟规则建立在伪时间戳上的必要前置工作。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage038 并把下一步收敛到 replay 语义修复。
- 是否更新 `research/registry.md`：否，本阶段不是跨线重大突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、路线废弃、正式候选、跨线合并或记录体系迁移。
