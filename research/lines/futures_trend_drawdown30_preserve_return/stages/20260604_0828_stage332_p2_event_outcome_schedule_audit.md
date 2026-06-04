# Stage332 P2 事件 outcome schedule 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 08:28 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：P2 公开源事件种子的 outcome maturity / fail-closed 审计
- 是否重要突破：否；这是协议闭合，不是 alpha 或正式候选突破
- 是否触发A/B：否；没有策略版本进入正式候选、paper 或白名单

## 外部调研与判断

- 参考资料：
  - Event study window selection: https://eventstudy.de/docs/window-selection
  - Event study data preparation: https://eventstudy.de/docs/data-preparation
  - Purged cross-validation overview: https://en.wikipedia.org/wiki/Purged_cross-validation
  - USDA WASDE release process: https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/world-agricultural-outlook-board/wasde-report
- 我的判断：
  - 事件研究不能只记录“来源出现过”，必须把事件日、入场日、20/63/126 交易日 outcome、重叠事件和估计窗口隔离开。
  - 当前 Stage631 的 `CY/SR` 只有公开源事件种子，不是可预测收益标签；如果没有事件后本地价格和成熟窗口，必须 fail-closed。
  - 本阶段最重要的结论不是收益，而是确认“还不能算收益”，防止把未成熟的基本面/舆情证据误用为 selector。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage632_p2_event_outcome_schedule_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - outcome horizons：`20/63/126` 个交易日
  - 本地产品代理：`CY.CZCE -> CY*.csv`，`SR.CZCE -> SR*.csv`
  - 主力日线代理规则：同一交易日优先选 `tradable_proxy=1`、成交量最大、持仓量最大的合约行，仅用于价格覆盖和 outcome 到期表，不作为 alpha
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - event seed：Stage631 event seed ledger，`received_at_utc=2026-06-04T00:02:05Z`
  - 本地日线：`examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04/CZCE/`
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：
  - 只使用 Stage631 已冻结 event seed ledger
  - 只检查 `CY.CZCE/SR.CZCE`
  - outcome 必须有事件后下一可交易日 entry 和对应 horizon close，缺任一项不得计算收益
- 策略/归因口径：
  - 不重放策略、不改交易规则、不生成 selector、不生成 paper/whitelist、不连接 CTP
  - `same_day_event_group_size>1` 的事件只记录为重叠事件簇，不能算独立 episode

## 结果

- 期末权益：不适用；本阶段不是收益回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`p2_event_outcome_schedule_created_outcomes_not_mature_selector_locked`
  - event seed rows：`3`
  - products covered：`2`
  - horizon rows：`9`
  - mature outcome rows：`0`
  - entry available rows：`0`
  - products with local price proxy：`2`
  - products with entry available after event：`0`
  - same-day overlap groups：`1`
  - selector rows：`0`
  - paper/whitelist rows：`0`
  - verified independent episode rows：`0`
  - hard gates：`11/11`
  - `CY.CZCE` 本地价格代理：`63` 个文件，`12075` raw rows，`1482` proxy rows，最新可交易代理日 `2026-03-13`
  - `SR.CZCE` 本地价格代理：`33` 个文件，`8044` raw rows，`1575` proxy rows，最新可交易代理日 `2026-03-13`
  - 事件日 `2026-06-04` 晚于本地最新可交易代理日 `83` 天，因此不能产生 entry 或 outcome return

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage632_p2_event_outcome_schedule_audit_report_stage632_p2_event_outcome_schedule_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage632_p2_event_outcome_schedule_audit_decision_stage632_p2_event_outcome_schedule_audit_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage632_p2_event_outcome_schedule_audit_outcome_schedule_stage632_p2_event_outcome_schedule_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage632_p2_event_outcome_schedule_audit_price_availability_stage632_p2_event_outcome_schedule_audit_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage632_p2_event_outcome_schedule_audit_gates_stage632_p2_event_outcome_schedule_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage632_p2_event_outcome_schedule_audit_chart_stage632_p2_event_outcome_schedule_audit_v1.png`

## 图表视觉复盘

- 左上图：`CY.CZCE/SR.CZCE` 两根红柱均显示最新本地可交易代理日为 `2026-03-13`，距离 `2026-06-04` 事件日 `83` 天；这是价格覆盖缺口，不是收益信号。
- 右上图：20/63/126 三个 horizon 在 `CY/SR` 上全部为 `0`，说明没有成熟 outcome。
- 左下图：`CY` 有 2 个事件 seed，max same-day group 也是 2，不能拆成两个独立 episode；`SR` 只有 1 个 seed。
- 右下图：所有 gate 为绿色，但其中多项是 fail-closed lock，例如 mature outcomes zero、entry available products zero；绿色不代表晋级。

## 结论

- 本阶段结论：
  - Stage631 的 `CY/SR` 事件种子已经可以被转成 20/63/126 交易日 outcome 到期表。
  - 但本地日线数据的最新可交易代理日期早于事件日，当前无法获得事件后 entry，也无法计算任何 horizon return。
  - 因此 P2 基本面/舆情路线继续保持 monitor-only；selector、paper、A/B、交易白名单全部继续为 `0`。
- 是否进入下一步：进入监控累计下一步，但不进入策略晋级。
- 下一步：
  - 继续按交易日运行 Stage629 -> Stage630 -> Stage631 -> Stage632，累计 PIT received_at、raw hash 和事件后价格。
  - 当每个产品/事件家族满足足量 PIT 日期、非重叠 episode 和成熟 outcome 后，再做 purged walk-forward 预测力审计。
  - 在 outcome 成熟前，不做宽池收益扫描，不做 paper，不把 CY/SR 事件种子接入真实交易。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有新增交易规则、没有调阈值、没有用收益选择品种。
  - 只把已有事件种子映射到固定的 20/63/126 交易日 schedule，并在数据不足时禁止计算收益。
  - 这降低了后验解释和数据偷看的风险。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但只能继续做证据累计，不能晋级。
- 原因：
  - 本阶段确认了 P2 source route 已能形成事件 seed，但 outcome 和价格覆盖还不成熟。
  - 下一步工作的边界更清楚：补 PIT、补事件后价格、做重叠清洗和 purged validation，而不是继续扫策略参数。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage332 当前状态。
- 是否更新 `research/registry.md`：是，更新当前阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是重要突破、路线废弃、正式候选或跨线合并。
