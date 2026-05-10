# Stage230 轻量动态软上限+保证金门禁v1验证

- line_id：`futures_trend_risk_overlay`
- 当前模式：`day`
- 记录时间：`2026-05-10 23:12 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：风险覆盖层A vs C验证
- 是否重要突破：是，首次把trade-block破产/穿仓概率压到接近目标区间，但收益低于预设目标
- 是否触发A/B：是，`A=78-1`，`C=78-1+light_dynamic_soft_cap_gate_v1`

## 外部调研与判断

- 参考资料：
  - CTA风险覆盖层和position sizing资料强调，尾部风险通常来自长期暴露曲线，而不是单日门禁本身。
  - Drawdown control资料强调，权益高水位后的暴露扩张应在保证金压力和回撤压力出现时降速。
- 我的判断：
  - Stage229反证“单独保证金门禁”不足以治理trade-block穿仓风险。
  - Stage230将治理点从“单日新增仓”推进到“长期sizing equity扩张曲线”，更接近风险来源。
  - 本次只做一组结构性参数，不扫网格。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage230_risk_overlay_light_dynamic_soft_cap_gate.py`
- 修改脚本：无。
- 新增参数：无。
- 修改参数：无正式参数修改，仅实验覆盖：
  - `enable_dynamic_sizing_equity_soft_cap=True`
  - `dynamic_sizing_equity_soft_cap_base=1_500_000`
  - `dynamic_sizing_equity_soft_cap_max=5_000_000`
  - `dynamic_sizing_equity_soft_cap_participation=0.45`
  - `dynamic_sizing_equity_soft_cap_margin_start_ratio=0.55`
  - `dynamic_sizing_equity_soft_cap_margin_full_ratio=0.80`
  - `dynamic_sizing_equity_soft_cap_drawdown_start_ratio=0.08`
  - `dynamic_sizing_equity_soft_cap_drawdown_full_ratio=0.22`
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
  - C：`light_dynamic_soft_cap_gate_v1`

## 结果

- A `baseline_78_1` 全样本：
  - 期末权益：`25,542,885`
  - 总收益：`5008.5770%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
  - 胜率：`43.2432%`
- C `light_dynamic_soft_cap_gate_v1` 全样本：
  - 期末权益：`11,461,100`
  - 总收益：`2192.2200%`
  - 最大回撤：`-29.3274%`
  - Sharpe：`1.3048`
  - 总滑点：`774,080`
  - 总交易次数：`860`
  - 胜率：`43.3180%`
- 多周期：
  - C在`2020起点至今`收益明显低于A，但最大回撤改善`10.73`个百分点，Sharpe提升到`1.3048`
  - C在`2022-2023`独立阶段收益略优于A：`128.0300%` vs `123.7880%`
  - C对`2026`冷启动无改善，结果与A相同：`-9.8920%`
- 滑点压力：
  - A `5x`滑点：总收益`3434.0570%`，最大回撤`-66.4314%`
  - C `5x`滑点：总收益`1572.9560%`，最大回撤`-37.1980%`
- Monte Carlo：
  - A daily亏损概率`2.0%`，C为`0.1%`
  - A daily回撤超过40%概率`95.9%`，C为`32.6%`
  - A trade-block破产/穿仓概率`52.6%`，C为`16.5%`
  - A trade-block回撤超过40%概率`88.6%`，C为`62.0%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage230_risk_overlay_light_dynamic_soft_cap_gate_v1_report_stage230_risk_overlay_light_dynamic_soft_cap_gate_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage230_risk_overlay_light_dynamic_soft_cap_gate_v1_summary_stage230_risk_overlay_light_dynamic_soft_cap_gate_v1.csv`
- orders：无。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage230_risk_overlay_light_dynamic_soft_cap_gate_v1_daily_stage230_risk_overlay_light_dynamic_soft_cap_gate_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage230_risk_overlay_light_dynamic_soft_cap_gate_v1_monte_carlo_summary_stage230_risk_overlay_light_dynamic_soft_cap_gate_v1.csv`

## 结论

- 本阶段结论：
  - Stage230是目前最接近风险目标的候选，trade-block破产/穿仓概率从`52.6%`降到`16.5%`。
  - 但收益低于预设`3000%+`目标，仅为`2192.2200%`，不直接合入`78-1`。
  - 该结果说明“长期暴露曲线治理”方向正确，比单独保证金门禁更有效。
- 是否进入下一步：是。
- 下一步：
  - 只做一轮“收益恢复版v2”：结构性放松上限，不做网格扫参。
  - 如果v2不能在`3000%+`收益与`10%-15%`破产/穿仓概率之间取得平衡，则停止本轮风险覆盖层优化，回到部署资金分层方案讨论。

## 过拟合反思

- 运行前判断：风险可控。参数来自风险结构，不是回看收益拟合。
- 运行后判断：仍可控，但下一步必须限制为一轮结构性验证。
- 原因：Stage230方向有效，但如果继续围绕`base/max/participation`细调，就会转向参数拟合。

## 继续价值反思

- 运行前判断：有。需要验证长期暴露曲线治理是否优于单独门禁。
- 运行后判断：有，但应设停止条件。
- 原因：Stage230显著降低尾部风险，但收益不足；仅值得再做一次收益恢复验证。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，将下一步标为收益恢复版v2。
- 是否追加根目录 `memory.md/back_log.md`：追加`back_log.md`，`memory.md`补充Stage230结论。
