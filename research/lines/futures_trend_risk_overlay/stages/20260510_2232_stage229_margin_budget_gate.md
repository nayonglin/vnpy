# Stage229 保证金预算门禁v1验证

- line_id：`futures_trend_risk_overlay`
- 当前模式：`day`
- 记录时间：`2026-05-10 22:32 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：风险覆盖层A vs C验证
- 是否重要突破：否。收益保留优秀，但尾部路径风险改善不足
- 是否触发A/B：是，`A=78-1`，`C=78-1+margin_budget_gate_v1`

## 外部调研与判断

- 参考资料：
  - CTA风险管理资料强调保证金预算和新增仓门禁是实盘必要约束，但它主要控制瞬时拥挤，不必然改变长期路径风险。
  - Position sizing资料强调，穿仓风险既来自单日新增仓，也来自长期权益复利放大后的仓位水平。
- 我的判断：
  - Stage228显示静态分层出金存在收益-尾部风险跷跷板。
  - 保证金预算门禁更接近穿仓风险来源，值得先单独验证。
  - 如果门禁只能保收益但不能显著降破产概率，说明风险来自长期暴露曲线，而不仅是同日新增仓拥挤。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage229_risk_overlay_margin_budget_gate.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无正式参数修改，仅实验覆盖：
  - `enable_incremental_margin_budget_gate=True`
  - `incremental_margin_budget_gate_usage_ratio=0.90`
  - `incremental_margin_budget_gate_min_openable_candidates=2`
  - `incremental_margin_budget_gate_protected_selection_rank=1`
- 删除参数：无。

## 回测/归因参数

- 数据区间：
  - 多起点：`2020`、`2021`、`2022`、`2023`、`2024`、`2025`、`2026`
  - 独立阶段：`2020-2021`、`2022-2023`、`2024-2025`、`2026`
- 账户规模：`500,000`
- 成本口径：默认成本 + `1x/2x/3x/5x`滑点压力。
- 样本过滤：沿用`78-1`产品宇宙、AI选品、FU卫星规则和短空门禁。
- 策略/归因口径：
  - A：`baseline_78_1`
  - C：`margin_budget_gate_v1`

## 结果

- A `baseline_78_1` 全样本：
  - 期末权益：`25,542,885`
  - 总收益：`5008.5770%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
  - 胜率：`43.2432%`
- C `margin_budget_gate_v1` 全样本：
  - 期末权益：`23,570,400`
  - 总收益：`4614.0800%`
  - 最大回撤：`-39.9534%`
  - Sharpe：`1.1442`
  - 总滑点：`1,873,970`
  - 总交易次数：`878`
  - 胜率：`43.7923%`
- 多周期：
  - C在`2020-2021`独立阶段优于A：`592.9800%` vs `583.0930%`
  - C在`2022-2023`独立阶段优于A：`128.0300%` vs `123.7880%`
  - C在`2024-2025`独立阶段弱于A：`360.5180%` vs `418.5170%`
  - C对`2026`冷启动无改善，结果与A相同：`-9.8920%`
- 滑点压力：
  - A `5x`滑点：总收益`3434.0570%`，最大回撤`-66.4314%`
  - C `5x`滑点：总收益`3114.9040%`，最大回撤`-67.0281%`
  - C在极端滑点下最大回撤反而略差。
- Monte Carlo：
  - A daily亏损概率`2.0%`，C为`1.2%`
  - A daily回撤超过40%概率`95.9%`，C为`90.5%`
  - A trade-block破产/穿仓概率`52.6%`，C为`48.6%`
  - A trade-block回撤超过40%概率`88.6%`，C为`87.8%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage229_risk_overlay_margin_budget_gate_v1_report_stage229_risk_overlay_margin_budget_gate_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage229_risk_overlay_margin_budget_gate_v1_summary_stage229_risk_overlay_margin_budget_gate_v1.csv`
- orders：无。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage229_risk_overlay_margin_budget_gate_v1_daily_stage229_risk_overlay_margin_budget_gate_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage229_risk_overlay_margin_budget_gate_v1_monte_carlo_summary_stage229_risk_overlay_margin_budget_gate_v1.csv`

## 结论

- 本阶段结论：
  - 保证金预算门禁v1收益保留优秀，几乎不伤害`78-1`复利能力。
  - 但它对trade-block尾部路径风险改善很弱，破产/穿仓概率仅从`52.6%`降到`48.6%`。
  - 单独保证金门禁不应合入正式`78-1`，因为它没有解决本研究线的核心目标。
- 是否进入下一步：是。
- 下一步：
  - 不继续单独压低门禁比例，否则可能只是收益劣化版门禁。
  - 研究“轻量动态软上限 + 保证金触发”的组合：用保证金/回撤触发暴露降速，而不是长期静态出金或单日门禁。

## 过拟合反思

- 运行前判断：否。门禁是结构性保证金预算规则。
- 运行后判断：否，但继续调`0.90`到`0.80/0.70`的边际价值低，可能转向参数拟合。
- 原因：v1结果说明结构本身对尾部风险不敏感，单纯收紧比例大概率只是牺牲收益。

## 继续价值反思

- 运行前判断：有。需要验证保证金预算是否能直接治理穿仓风险。
- 运行后判断：有，但方向要修正。
- 原因：结果反证了“同日新增仓拥挤是主要穿仓源”的假设，后续应治理长期暴露曲线。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，将下一步切换为轻量动态软上限+保证金触发。
- 是否追加根目录 `memory.md/back_log.md`：追加`back_log.md`，`memory.md`补充Stage229结论。
