# Stage284 低单笔风险扩池 selector A/B 启动协议冻结

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-03 23:34 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读协议/闸门审计；不改策略；不做收益回测；不生成交易候选。
- 是否重要突破：否，但属于防止扩池路线过拟合的重要协议冻结。
- 是否触发A/B：触发 `skills/version-ab-experiment/SKILL.md` 判断；本阶段只预声明 A/B/C，不启动 A/B 回测。

## 外部调研与判断

- 参考资料：
  - A Century of Evidence on Trend-Following Investing：https://research.cbs.dk/en/publications/a-century-of-evidence-on-trend-following-investing-executive-summ
  - Optimal Allocation of Trend Following Strategies：https://arxiv.org/abs/1410.8409
  - pysystemtrade 风险预算/相关性/分散实现：https://github.com/robcarver17/pysystemtrade
  - CTA 趋势跟踪跨品种分散与相关性讨论：https://www.iasg.com/blog/2019/11/29/commodity-trading-advisors-ctas-in-perspective
- 我的判断：
  - 外部 CTA/趋势跟踪资料支持跨市场分散、风险预算和相关性治理，但不支持事后赢家白名单。
  - 本地 Stage257/264/282 已经说明：低单笔风险扩池方向有价值，但简单宽池不是答案，瓶颈是 point-in-time selector。
  - 所以本阶段不应提前做收益回测，而应冻结未来真正开跑 A/B/C 前的 arms、selector 特征、同族 tie-break、IC/bucket 规则和禁止事项。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage584_breadth_selector_ab_launch_protocol.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `MIN_FORWARD_RUNS=20`
  - `MIN_FORWARD_DATES=20`
  - `MIN_READY_ROUTES_PER_P0=2`
  - `MIN_EVENT_READY_PRODUCTS=5`
  - `MAX_AVG_PAIRWISE_ABS_CORR=0.20`
  - `MAX_PAIRWISE_ABS_CORR=0.50`
  - `MAX_FAMILY_BUDGET_PCT=20.0`
  - `MAX_PRODUCT_RISK_UNIT=0.20`
  - `MAX_SELECTOR_TRIALS=1`
  - `MIN_MEAN_SPEARMAN_IC=0.05`
  - `MIN_POSITIVE_IC_RATE_PCT=60.0`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不适用；读取 Stage582/571/561/560 既有输出。
- 账户规模：不适用；本阶段不做收益回测。
- 成本口径：不适用。
- 样本过滤：
  - P0 只认 Stage582 watchlist：`y.DCE/c.DCE/v.DCE/lu.INE/ao.SHFE`。
  - 只使用 point-in-time route readiness、Stage561 qualified forward runs/dates、同族预算和外部 route priority。
- 策略/归因口径：
  - A：`A_stage526_control`，即 Stage526 控制组。
  - B：`B_breadth_selector_sleeve_standalone`，只验证低单笔风险扩池是否有独立趋势来源。
  - C：`C_stage526_plus_breadth_selector_sleeve`，真实可晋级候选；Stage526 core 不被新 sleeve 替换。
  - 本阶段明确禁止 B/C 收益回测，直到所有硬闸门通过。

## 结果

- 期末权益：不适用；本阶段无收益回测。Stage526 参考口径仍为 `23,369,505`。
- 总收益：不适用。Stage526 参考口径仍为 `3699.9195%`。
- 最大回撤：不适用。Stage526 参考口径仍为 `-36.2670%`。
- Sharpe：不适用。Stage526 参考口径仍为 `1.6385`。
- 总滑点：不适用。Stage526 参考口径仍为 `1,342,190`。
- 总交易次数：不适用。Stage526 参考口径仍为 `905`。
- 胜率：不适用。Stage526 参考口径仍为 `53.6330%`。
- 其他关键指标：
  - 决策：`breadth_selector_ab_launch_not_allowed_protocol_frozen`
  - `launch_allowed=false`
  - 硬闸门：`5/10`
  - P0 数量：`5`
  - P0 route-ready：`3/5`
  - P0 event-ready：`2/5`
  - P0 平均/最大 peer abs corr：`0.0347909153 / 0.0508425482`
  - Stage561 forward runs/dates：`2/20`、`2/20`
  - qualified runs/dates：`2/20`、`2/20`
  - 同族 tie-break：已冻结，`grains_oilseeds=y/c` 同向 sleeve 只允许 point-in-time selector 最高分 top1；若 selector 不可用或打平，不给该 family 增加 sleeve 风险。

## 图表视觉复盘

- 左上图：只有 `A_stage526_control` 是绿灯，`B_breadth_selector_sleeve_standalone` 和 `C_stage526_plus_breadth_selector_sleeve` 都因 selector 证据不足被阻塞。
- 右上图：P0 的 `inventory` 覆盖全绿；`basis` 在 `lu/ao` 缺口；真实事件/舆情只覆盖 `y/c`，`v/lu/ao` 缺口明显。
- 左下图：`grains_oilseeds` 有 `y/c` 两个 P0，已冻结 top1-only tie-break；其他 `energy_oil/petrochem/base_metals` 均为单 P0 family。
- 右下图：闸门失败集中在 P0 route/event 覆盖、forward `20/20` 样本和 `selector_backtest_allowed_now`；pairwise corr 和 tie-break 已不是当前主瓶颈。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage584_breadth_selector_ab_launch_protocol_report_stage584_breadth_selector_ab_launch_protocol_v1.md`
- ab arms：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage584_breadth_selector_ab_launch_protocol_ab_arms_stage584_breadth_selector_ab_launch_protocol_v1.csv`
- selector blueprint：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage584_breadth_selector_ab_launch_protocol_selector_blueprint_stage584_breadth_selector_ab_launch_protocol_v1.csv`
- family tie-break：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage584_breadth_selector_ab_launch_protocol_family_tie_break_stage584_breadth_selector_ab_launch_protocol_v1.csv`
- launch gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage584_breadth_selector_ab_launch_protocol_launch_gates_stage584_breadth_selector_ab_launch_protocol_v1.csv`
- runbook：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage584_breadth_selector_ab_launch_protocol_runbook_stage584_breadth_selector_ab_launch_protocol_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage584_breadth_selector_ab_launch_protocol_decision_stage584_breadth_selector_ab_launch_protocol_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage584_breadth_selector_ab_launch_protocol_chart_stage584_breadth_selector_ab_launch_protocol_v1.png`

## 结论

- 本阶段结论：`breadth_selector_ab_launch_not_allowed_protocol_frozen`
- 是否进入下一步：进入 forward collection 和标签等待，不进入 B/C 收益回测。
- 下一步：
  - 继续累计 Stage561 qualified forward runs/dates 至 `20/20`。
  - 补 `lu/ao` 的 basis 或等价点时化基本面 route。
  - 补 `v/lu/ao` 真实事件/舆情账本覆盖。
  - 等 63/126 日标签成熟后，只允许一次冻结 IC/bucket 审计；通过后才做一次 frozen low-risk paper sleeve replay。
  - 未达硬闸门前，禁止 P0 交易白名单、B/C 收益回测、TopN/risk/corr/family cap 小数扫描、历史赢家/未来标签 selector。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段在 selector 标签成熟前冻结 A/B/C、特征、同族 tie-break 和 IC/bucket 通过线。
  - 不做收益回测，不用历史赢家做交易白名单，不扫风险/相关性/TopN 小数。
  - 结果明确阻止 B/C 启动，而不是为了跑出更好收益而放宽条件。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - 用户提出的低单笔风险扩池路线在第一性原理和本地 evidence 上仍成立。
  - 当前最大风险是未来样本成熟后规则漂移，本阶段把规则提前冻结，降低后续过拟合概率。
  - 后续有清晰可执行动作：继续真实 point-in-time 外生采集、补事件覆盖、等标签成熟再做固定审计。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是。该阶段影响扩池路线是否允许进入 A/B/C 回测。
