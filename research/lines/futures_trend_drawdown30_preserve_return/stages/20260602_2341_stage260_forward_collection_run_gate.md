# Stage260 Forward采集运行闸门

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 23:41 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：外生状态采集运行闸门；不做收益回测，不生成交易候选。
- 是否重要突破：否；但把“同日重复采集不得增加 selector 样本深度”固化为机器闸门。
- 是否触发A/B：否。没有形成可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - AQR managed futures / trend-following 资料：趋势策略长期稳健性依赖多市场分散、风险预算和低相关承载，但也明确存在模型风险和过度优化风险。
  - `pysystemtrade` / 系统化交易实践：多品种趋势组合需要 instrument diversification、相关性约束和风险预算；单纯扩大品种数不等于有效分散。
  - Point-in-time / look-ahead bias 资料：回测只能使用当时实际可得的数据，外生/舆情数据必须记录 `received_at`、来源、版本和原始 hash。
  - AKShare 期货数据文档：basis、inventory 等可作为 forward 采集源，但不同接口覆盖率和历史深度不同，不能默认回填历史 selector。
- 我的判断：用户提出的“降低单笔风险、扩大品种池、避高相关、选对品种”方向本质上是对的，但选品的关键不在继续扫 `risk/cap/corr/maxpos`，而在建立可穿越周期的事前信息源。当前 Stage258/259 已证明机会存在但数据资格不足，所以 Stage260 只做采集闸门，不做收益回测。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage560_forward_collection_run_gate.py`
- 修改脚本：无既有策略脚本修改。
- 删除脚本：无。
- 新增参数/闸门：
  - `MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT=20`
  - `MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT=20`
  - `MIN_ACTIVE_FORWARD_ROUTES=2`
  - `new_calendar_date_available`
  - `same_day_duplicate_policy_ok`
  - `ready_for_predictive_audit`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：当前外生 forward ledger，截至 `2026-06-02`。
- 账户规模：不适用，本阶段不做收益回测。
- 成本口径：不适用。
- 样本过滤：只读取 Stage549 已落盘 `external_state_forward_ledger.csv` 与 Stage559 舆情模板；不联网、不拉新数据、不回填历史。
- 策略/归因口径：采集运行闸门；检查同日重复运行是否可计入 selector 样本深度。

## 结果

- 决策：`same_day_collection_not_counted_selector_still_not_ready`
- 推荐动作：`skip_same_day_for_selector_depth_allow_operator_smoke_only`
- 当前日期：`2026-06-02`
- 最新账本日期：`2026-06-02`
- 下一次可计入 selector 样本深度日期：`2026-06-03`
- forward runs：`1/20`
- forward dates：`1/20`
- 剩余 runs/dates：`19/19`
- 同日 run 数：`1`
- 重复日期数：`0`
- active forward routes：`2/2`
- history selector ready 产品数：`0`
- sentiment template：`1`
- real sentiment/news ledger：`0`
- collection gates：`6/11` 通过。
- 失败项：
  - `new_calendar_date_available`：同日不可计数。
  - `enough_forward_runs`：`1 < 20`。
  - `enough_forward_dates`：`1 < 20`。
  - `sentiment_real_ledger_exists`：`0 < 1`。
  - `ready_for_predictive_audit`：未达标。
- Route健康度：
  - basis：`28/37` latest forward-ready，history-ready `0`。
  - inventory：`24/37` latest forward-ready，history-ready `0`。
  - member_detail：`0/37` latest forward-ready。
  - warehouse：`0/37` latest forward-ready。

## 回测指标

- 期末权益：不适用，本阶段不做收益回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：`runs=1/20`、`dates=1/20`、`sentiment ledger=0/1`、`active forward routes=2/2`。

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage560_forward_collection_run_gate_chart_stage560_forward_collection_run_gate_v1.png`
- 左上图清楚显示当前 `runs=1`、`dates=1`，与要求 `20/20` 差距明显。
- 右上图显示 basis `28`、inventory `24` 仍是可 forward 的两条主 route，member_detail/warehouse 为 `0`，history 紫柱全部为 `0`。
- 左下图显示失败集中在新自然日、样本深度、真实舆情账本和预测力审计；同日去重 policy 为 PASS。
- 右下图明确写出 `today=2026-06-02`、`latest ledger date=2026-06-02`、`next eligible date=2026-06-03`、`action=same-day skip; smoke only`。二次视觉检查后文本无裁切、无遮挡。

## 输出文件

- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage560_forward_collection_run_gate_decision_stage560_forward_collection_run_gate_v1.json`
- collection gate：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage560_forward_collection_run_gate_collection_gate_stage560_forward_collection_run_gate_v1.csv`
- route health：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage560_forward_collection_run_gate_route_latest_health_stage560_forward_collection_run_gate_v1.csv`
- date progress：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage560_forward_collection_run_gate_date_progress_stage560_forward_collection_run_gate_v1.csv`
- runbook：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage560_forward_collection_run_gate_runbook_stage560_forward_collection_run_gate_v1.md`
- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage560_forward_collection_run_gate_report_stage560_forward_collection_run_gate_v1.md`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage560_forward_collection_run_gate_chart_stage560_forward_collection_run_gate_v1.png`

## 结论

- 本阶段结论：Stage560 明确禁止把同日重复采集计入 selector 样本深度。当前外生状态方向仍是数据工程/paper 监控，不具备新的选品收益回测资格。
- 是否进入下一步：进入采集监控下一步，不进入策略晋级或 A/B。
- 下一步：
  - 等到 `2026-06-03` 或之后的真实新采集日，再运行 Stage549 追加外生 ledger。
  - 每个自然日最多一次计入 selector 样本深度；同日重复运行只作为 smoke 或源修复验证。
  - 按 Stage559 模板开始真实舆情/新闻/manual event 账本，先 paper，不交易。
  - 达到 `20` runs、`20` dates、至少 `1` 个真实 sentiment ledger 后，再做固定 3个月/6个月品种趋势收益排序预测力审计。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段不读取未来收益、不调交易参数，只建立采集样本闸门。
- 运行后判断：不是过拟合。它反而降低后续过拟合风险，因为它阻止同日重复采集、新闻回填和单次外生状态被误当成样本外证据。
- 原因：真正的 selector 必须在跨日 point-in-time 样本上验证；如果没有这层闸门，后续“选对品种”很容易退化成 hindsight。

## 继续价值反思

- 运行前判断：有价值。Stage258/259 的瓶颈是点时样本深度和舆情账本，而不是收益回测不足。
- 运行后判断：仍有价值，但下一步必须是跨日采集和舆情账本落盘；未达标前不做选品收益回测。
- 原因：扩池和低单笔风险方向只有在事前选品真的有信息优势时才成立；现在先把数据资格补齐，才有机会验证这件事是否可穿越周期。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为外生/舆情样本闸门边界。
