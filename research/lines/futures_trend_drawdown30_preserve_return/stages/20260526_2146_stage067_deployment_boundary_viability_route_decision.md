# Stage067 部署边界可行性与路线决策

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 21:46 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：既有证据归档与路线决策；不新增交易规则
- 是否重要突破：是，明确供需补齐不是剩余主路径，当前最低过拟合可执行边界仍是部署层现金方案
- 是否触发A/B：否；本阶段不修改78-1/C3交易逻辑，不创建新策略候选。

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen `Time Series Momentum`：商品、股指、债券、外汇期货的时间序列动量证据支持趋势类收益源具有跨市场基础。
  - Hurst/Ooi/Pedersen `A Century of Evidence on Trend-Following Investing`：长期趋势跟随价值更多来自跨市场分散、风险预算和承受长期回撤，而不是事后弱窗口补丁。
  - 商品期货趋势/风险平价研究显示，风险预算有帮助，但本地 Stage033-035 已证明日收益层波动缩放落到真实期货引擎会破坏趋势腿，不能直接照搬。
- 我的判断：
  - 当前本线不是“还缺23年前供需数据”的问题，而是 C3 自然回撤边界约在 `-31%`。
  - 要进 `30%` 以内，要么接受部署层现金边界，要么找到新的可承载独立收益源。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage367_deployment_boundary_viability_route_decision.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无；只读取 Stage359/365/366 已有结果并生成决策表。
- 修改参数：无。
- 删除参数：无。

## 归因/审计参数

- 数据来源：
  - Stage359：2020-2026 供需补齐后 C3 复跑结果。
  - Stage365：正式78-1、C3、部署边界、净值层候选的平滑度审计。
  - Stage366：xsmom 净值层到真实期货承载的失败归因。
- 目标闸门：
  - 最大回撤 `>= -30%`
  - 收益保留 `>= 80%`
- 本阶段不重新计算成交、不修改AI池、不修改品种池、不修改开平仓逻辑。

## 结果

- 正式78-1：总收益 `5170.7870%`，最大回撤 `-40.1659%`，Ulcer `20.8635`，Sharpe `1.4316`。
- C3当前研究基准：总收益 `6085.1300%`，最大回撤 `-31.0767%`，Ulcer `16.2653`，Sharpe `1.6164`。
- `50万C3下单 + 11.5万外部现金`：总收益 `4947.2602%`，最大回撤 `-29.7007%`，收益保留 `81.3008%`，正常成本可部署，高滑点不通过。
- 供需补齐：
  - 23年之前不是没有供需数据，而是原工程 Stage316 只覆盖 2023-2026。
  - Stage058 已补齐 2020-2022，Stage059 合并供需信号 `51,524` 行。
  - 补齐供需 C3 全样本仅 `951.3010%/-48.0183%/Sharpe 0.8920`，显著差于现有 C3。
- xsmom：
  - 净值层仍有理论价值，但当前期货卫星承载方式失败。
  - 当前不再围绕 `7.5%`、`35/15`、`3万现金+xsmom overlay`、`min1_cheapest`、篮子数量或保证金优先顺序救援。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_deployment_boundary_viability_route_decision_report_stage367_deployment_boundary_viability_route_decision_v1.md`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_deployment_boundary_viability_route_decision_comparison_stage367_deployment_boundary_viability_route_decision_v1.csv`
- route_matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_deployment_boundary_viability_route_decision_route_matrix_stage367_deployment_boundary_viability_route_decision_v1.csv`
- supply_audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_deployment_boundary_viability_route_decision_supply_audit_stage367_deployment_boundary_viability_route_decision_v1.csv`
- annual_focus：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_deployment_boundary_viability_route_decision_annual_focus_stage367_deployment_boundary_viability_route_decision_v1.csv`
- rolling_focus：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_deployment_boundary_viability_route_decision_rolling_focus_stage367_deployment_boundary_viability_route_decision_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_deployment_boundary_viability_route_decision_decision_stage367_deployment_boundary_viability_route_decision_v1.json`

## 结论

- 本阶段结论：`normal_cost_deployment_boundary_is_current_best_low_overfit_route`。
- 23年前供需数据应该补齐，且已经补齐；但补齐后直套强逆风过滤已经反证，不能继续作为降回撤主路径。
- C3 已经明显优于正式78-1：收益更高，最大回撤从 `-40.1659%` 降到 `-31.0767%`，Ulcer 从 `20.8635` 降到 `16.2653`。
- 当前最低过拟合可执行方案仍是 Stage055：`50万C3下单 + 11.5万外部现金`，正常成本下最大回撤 `-29.7007%`，收益保留 `81.3008%`。
- 如果目标必须是“单策略、不增加外部现金、且高滑点也稳健进30以内”，当前仍未完成，下一步必须寻找全新的独立收益源或换承载工具。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段只汇总已冻结证据，不新增参数、不扫阈值。
- 运行后判断：不是过拟合。失败路线被停止，候选边界被限定使用条件，没有用结果反向调参。
- 风险提示：继续围绕供需阈值、7天有效期、xsmom `7.5%`、`35/15`、季节性 `10%` 等小数救援会转为过拟合。

## 继续价值反思

- 运行前判断：有价值。必须把供需补齐事实和当前部署边界固化，避免重复研究。
- 运行后判断：有价值，但继续方向必须变窄。
- 继续有价值的方向只有两类：接受 Stage055 正常成本部署边界；或者寻找新的独立收益源/承载工具。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为供需路线边界和当前最强部署边界摘要。
