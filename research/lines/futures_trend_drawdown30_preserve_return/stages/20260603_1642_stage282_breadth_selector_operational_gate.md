# Stage282 低单笔风险扩池 selector 操作闸门

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-03 16:42 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读操作闸门审计；不生成交易候选；不做收益回测；不修改策略。
- 是否重要突破：否，但属于重要边界记录。
- 是否触发A/B：否。没有新增可晋级交易版本。

## 外部调研与判断

- 参考资料：
  - Trend-following trading strategies in commodity futures: A re-examination, Journal of Banking & Finance, 2010.
  - Optimal allocation of trend following strategies, Physica A, 2015.
  - Rob Carver / pysystemtrade 多品种系统化期货与分散工程：https://github.com/robcarver17/pysystemtrade
  - Portfolio stress testing applied to commodity futures, Computational Management Science, 2020.
- 我的判断：
  - 多市场趋势、低单笔风险、风险预算和相关性治理在第一性原理上成立。
  - 当前真正瓶颈不是品种数量，也不是 P0 品种之间相关性，而是 point-in-time selector 证据和外生数据路线覆盖不足。
  - 因此本阶段只允许把 `lu/v/y/ao/c` 转成 forward watchlist，不能把它们作为交易白名单。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage582_breadth_selector_operational_gate.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `P0_MIN_PRODUCTS=5`
  - `MIN_FORWARD_RUNS=20`
  - `MIN_FORWARD_DATES=20`
  - `MIN_ACTIVE_ROUTES_PER_PRODUCT=2`
  - `MAX_AVG_PAIRWISE_ABS_CORR=0.20`
  - `MAX_PAIRWISE_ABS_CORR=0.50`
  - `MAX_FAMILY_BUDGET_PCT=20.0`
  - `MAX_PRODUCT_RISK_UNIT=0.20`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage574/571/561 既有输出；不重跑交易引擎。
- 账户规模：不适用。
- 成本口径：不适用；本阶段不产生收益曲线。
- 样本过滤：
  - P0 只来自 Stage574 `P0_independent_material`。
  - 外生路线只认已写入 `external_state_forward_ledger` 且 `usable_for_forward_monitor=1` 的点时化记录。
  - 舆情/事件只认真实 `sentiment_news_manual_event_forward_ledger`，不把模板或历史回填计入。
- 策略/归因口径：
  - 不改 Stage526。
  - 不把历史赢家直接转成 selector。
  - 只输出当前 watchlist、route matrix、family budget 和 gate。

## 结果

- 期末权益：不适用；本阶段无收益回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`breadth_selector_operational_gate_not_ready`
  - 闸门通过：`2/7`
  - P0 watchlist：`y.DCE`、`c.DCE`、`v.DCE`、`lu.INE`、`ao.SHFE`
  - P0 平均/最大 pairwise abs corr：`0.0147 / 0.0508`
  - P0 中有至少两条外生路线 ready：`3/5`
  - P0 中有真实舆情/事件覆盖：`2/5`
  - 同族 tie-break 需求：`1` 个产品族，`grains_oilseeds = y.DCE/c.DCE`
  - forward runs/dates：`2/20`、`2/20`
  - `promotion_allowed=false`

## 图表视觉复盘

- 左上图：`lu.INE` 历史单品种 PnL 最高，但核心相关 `0.154` 也最高，仍在可观察范围内；`y/c/ao` 核心相关接近零，具备分散意义。
- 右上图：`y.DCE`、`c.DCE` 三条路线都 ready；`v.DCE` 只有 basis/inventory；`lu.INE`、`ao.SHFE` 只有 inventory，basis 为 `missing_product`，真实事件覆盖为 `0`。这说明 selector 缺口是可操作的数据缺口，不是相关性问题。
- 左下图：`grains_oilseeds` 同时有 `y/c` 两个 P0，必须设置同族同向 tie-break；不能因为两者都低相关就同时吃满风险。
- 右下图：只有 `p0_pool_exists` 与 `p0_pairwise_corr_ok` 通过，其余失败集中在外生路线、舆情覆盖、同族二选一和 `20/20` forward 样本深度。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage582_breadth_selector_operational_gate_report_stage582_breadth_selector_operational_gate_v1.md`
- watchlist：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage582_breadth_selector_operational_gate_watchlist_stage582_breadth_selector_operational_gate_v1.csv`
- route matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage582_breadth_selector_operational_gate_route_matrix_stage582_breadth_selector_operational_gate_v1.csv`
- family budget：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage582_breadth_selector_operational_gate_family_budget_stage582_breadth_selector_operational_gate_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage582_breadth_selector_operational_gate_gates_stage582_breadth_selector_operational_gate_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage582_breadth_selector_operational_gate_decision_stage582_breadth_selector_operational_gate_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage582_breadth_selector_operational_gate_chart_stage582_breadth_selector_operational_gate_v1.png`

## 结论

- 本阶段结论：`breadth_selector_operational_gate_not_ready`
- 是否进入下一步：进入 forward collection，不进入交易候选。
- 下一步：
  - 继续累计 Stage561 质量口径下的 `20/20` forward runs/dates。
  - 补 `lu.INE/ao.SHFE` 的 basis 或替代基本面路线，补 `v/lu/ao` 的真实事件/舆情覆盖。
  - 对 `y/c` 预注册同族同向 tie-break；没有事前排序前，不允许两个油脂油料 P0 同向同时吃满风险。
  - 达标后再按 Stage561 做固定 IC/bucket/paper sleeve 审计。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有扫参数、没有调整交易逻辑、没有用历史赢家生成交易白名单。
  - 输出明确禁止收益回测化 selector，直到 point-in-time 样本成熟。
  - 唯一新增的是操作 gate 和风险预算纪律。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但方向必须继续留在数据工程/forward monitor。
- 原因：
  - P0 池存在且相关性很低，说明方向不是空想。
  - 失败项清楚、可补：外生 route 覆盖、真实事件覆盖、同族 tie-break、`20/20` 样本深度。
  - 当前仍不能声明 Stage526/Stage079 实盘目标完成，尤其不能用该 P0 池替代正式交易品种。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，当前线最新阶段需要刷新。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 与 `memory.md` 的简短边界，防止误把 P0 watchlist 当交易白名单。
