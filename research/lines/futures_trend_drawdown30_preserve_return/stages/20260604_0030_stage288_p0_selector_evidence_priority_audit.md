# Stage288 P0 选品证据优先级审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 00:30 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读证据审计；不修改策略、不做收益回测、不生成交易白名单。
- 是否重要突破：否，但属于“低单笔风险 + 扩池 + 避高相关 + 选对品种”路线的重要边界。
- 是否触发 A/B：否。本阶段没有形成可接入正式版本的新策略；仍禁止 P0 白名单和 B/C 收益回测。

## 外部调研与判断

- 参考资料：
  - AQR `Trends Everywhere` / managed futures 资料：趋势跟踪长期价值来自多市场分散和风险预算，但分散不能替代真实 alpha。
  - 商品期货趋势/期限结构/库存相关研究：carry、basis、inventory、hedging pressure、OI 等更接近“趋势土壤”，但必须 point-in-time。
  - 开源方向：`pysystemtrade`、`PyPortfolioOpt`、HRP/risk parity 组合构造强调相关性、风险预算和 instrument diversification。
- 我的判断：
  - 用户提出的“减少单笔风险、扩大品种池、每年抓部分趋势，同时避免高相关”方向成立。
  - 但选品器不能来自 hindsight top6、上一年赢家或宽池参数小数；必须来自真实接收时间的 basis/inventory/event/sentiment 等 forward 账本。
  - 当前最值得做的是把 P0 池逐项拆成证据缺口，而不是继续跑收益曲线。

参考链接：

- https://www.aqr.com/insights/research/journal-article/trends-everywhere
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813
- https://github.com/robcarver17/pysystemtrade
- https://github.com/PyPortfolio/PyPortfolioOpt

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage588_p0_selector_evidence_priority_audit.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增输出：
  - P0 evidence matrix
  - product actions
  - route gaps
  - family tie-break
  - gates
  - decision
  - report
  - chart
- 新增参数/闸门：
  - `MIN_P0_PRODUCTS=5`
  - `MIN_FORWARD_RUNS=20`
  - `MIN_FORWARD_DATES=20`
  - `MIN_ROUTES_PER_P0=2`
  - `MAX_AVG_PAIRWISE_ABS_CORR=0.20`
  - `MAX_PAIRWISE_ABS_CORR=0.50`
  - `MAX_CORE_CORR_WATCH=0.10`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 审计输入

- Stage582 P0 watchlist：`qmt_roll_stage582_breadth_selector_operational_gate_watchlist_stage582_breadth_selector_operational_gate_v1.csv`
- Stage582 route matrix：`qmt_roll_stage582_breadth_selector_operational_gate_route_matrix_stage582_breadth_selector_operational_gate_v1.csv`
- Stage561 selector predictive protocol gates：`qmt_roll_stage561_selector_predictive_audit_protocol_gates_stage561_selector_predictive_audit_protocol_v1.csv`
- Stage571 source priority / data gaps。
- 外生 forward ledger 与 Stage572 真实事件账本。

## 结果

- 决策：`p0_selector_evidence_priority_not_ready`
- `promotion_allowed=false`
- `paper_selector_audit_allowed=false`
- `trading_whitelist_allowed=false`
- P0 产品数：`5`
- 至少两条点时化外生路线 ready：`3/5`
- 真实事件/舆情覆盖：`2/5`
- route gap rows：`5`
- 需要同族 tie-break 的产品族：`1`
- forward runs/dates：`2/20`、`2/20`
- gates：`3/8` 通过；hard gates `3/7` 通过。

### P0 证据矩阵

| 产品 | 证据分 | 主要状态 | 主要缺口 |
| --- | ---: | --- | --- |
| `y.DCE` | `95` | 三路齐全，但同族 tie-break 未冻 | `same_family_tiebreak` |
| `c.DCE` | `95` | 三路齐全，但同族 tie-break 未冻 | `same_family_tiebreak` |
| `v.DCE` | `75` | basis + inventory 齐全 | `sentiment_news_manual_event` |
| `ao.SHFE` | `35` | 只有 inventory | `basis_or_substitute_route, sentiment_news_manual_event` |
| `lu.INE` | `30` | 只有 inventory，且 core corr 观察位 | `basis_or_substitute_route, sentiment_news_manual_event, core_corr_watch` |

### 关键解释

- `y/c` 不是数据覆盖问题，而是同属 `grains_oilseeds`，未来若同向，必须预注册 top1-only 或其他 point-in-time tie-break；不能两个同时吃满 sleeve 风险。
- `v` 已具备 basis + inventory，下一步只缺 PVC/氯碱产业事件或新闻账本。
- `ao/lu` 当前只具备 inventory。`ao` 需要氧化铝 spot-basis 或替代基本面 route；`lu` 需要低硫燃油 spot-basis 或 bunker/fuel-oil spread route。
- `lu` 历史收益最高，但 `abs_core_daily_pnl_corr=0.1543`，超过 `0.10` 观察线；它不能因为历史 PnL 高就自动成为优先交易品种。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage588_p0_selector_evidence_priority_audit_report_stage588_p0_selector_evidence_priority_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage588_p0_selector_evidence_priority_audit_decision_stage588_p0_selector_evidence_priority_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage588_p0_selector_evidence_priority_audit_chart_stage588_p0_selector_evidence_priority_audit_v1.png`
- evidence matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage588_p0_selector_evidence_priority_audit_evidence_matrix_stage588_p0_selector_evidence_priority_audit_v1.csv`
- product actions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage588_p0_selector_evidence_priority_audit_product_actions_stage588_p0_selector_evidence_priority_audit_v1.csv`
- route gaps：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage588_p0_selector_evidence_priority_audit_route_gaps_stage588_p0_selector_evidence_priority_audit_v1.csv`
- family tie-break：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage588_p0_selector_evidence_priority_audit_family_tiebreak_stage588_p0_selector_evidence_priority_audit_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage588_p0_selector_evidence_priority_audit_gates_stage588_p0_selector_evidence_priority_audit_v1.csv`

## 图表视觉复盘

- 左上路线准备度：`y/c` 已经有 basis、inventory、event 三路；`v` 有 basis + inventory 但缺 event；`ao/lu` 只有 inventory，说明下一步数据工程优先级不是全池平均补，而是集中补 `v/ao/lu` 的事件与 `ao/lu` 的 basis 替代路线。
- 右上机会与核心相关：`lu` 历史非核心 PnL 最高，但明显越过 `0.10` core corr 观察线；`v` 处在较好的中间位置；`y/c` 更低相关但同族。
- 左下路线覆盖缺口：inventory 已 `5/5`，basis `3/5`，event `2/5`；所以当前瓶颈不是库存数据，而是 basis 替代和真实事件/舆情覆盖。
- 右下闸门：通过项只有 P0 池存在、pairwise corr 不拥挤、history backfill disabled；失败项集中在每个 P0 至少两条外生 route、事件覆盖、同族 tie-break 和 `20/20` forward 样本深度。

## 结论

- 本阶段结论：`p0_selector_evidence_priority_not_ready`。
- 是否进入下一步：进入，但只进入数据采集和协议补齐；不进入收益回测、P0 白名单或 A/B 交易版本。
- 下一步：
  - 为 `v.DCE` 补 PVC/氯碱相关真实事件/新闻账本。
  - 为 `lu.INE` 补低硫燃油/船燃/原油裂解/港口或库存事件账本，并补 forward-only basis 或替代 route。
  - 为 `ao.SHFE` 补氧化铝/铝土矿/冶炼/出口政策事件账本，并补 forward-only alumina spot-basis 或替代 route。
  - 冻结 `y.DCE/c.DCE` 同族同向 tie-break：没有 selector score 或打平时，该 family 不增加 sleeve 风险。
  - 继续累计 Stage561 `20` runs / `20` dates 后，再按冻结协议做一次 `63/126` 日 IC/bucket 审计。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段没有使用未来收益生成白名单，没有重跑交易收益，也没有根据结果调阈值。
  - P0 历史材料性只作为观察池输入，输出明确把 `promotion_allowed=false`、`paper_selector_audit_allowed=false`、`trading_whitelist_allowed=false` 写入 decision。
  - 对 `lu` 这种历史收益最高但 core corr 较高的产品没有优先交易化，反而标成观察位。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但路径更窄。
- 原因：
  - P0 池低相关成立，说明方向不是空想。
  - 缺口非常具体：`v/ao/lu` 事件覆盖、`ao/lu` basis 替代、`y/c` tie-break、`20/20` 样本深度。
  - 但现在还不能证明“能事前选中趋势品种”，因此继续价值在 forward 数据工程和固定预测力审计，不在新的宽池收益回测。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，当前线最新阶段需要刷新。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 简短边界；不追加 `memory.md`，因为不是突破或正式候选。
