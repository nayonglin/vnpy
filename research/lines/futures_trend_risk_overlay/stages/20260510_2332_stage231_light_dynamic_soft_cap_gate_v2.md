# Stage231 轻量动态软上限收益恢复版v2验证

- line_id：`futures_trend_risk_overlay`
- 当前模式：`day`
- 记录时间：`2026-05-10 23:32 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：风险覆盖层A vs C验证
- 是否重要突破：否。收益恢复不足，尾部风险明显回升
- 是否触发A/B：是，`A=78-1`，`C=78-1+light_dynamic_soft_cap_gate_v2`

## 外部调研与判断

- 参考资料：
  - CTA/趋势策略资料强调应按组合波动、回撤与风险预算动态调整头寸，而不是依赖单一品种补丁。
  - 动态仓位管理资料强调回撤后降风险、恢复后再逐步放大，但过度调阈值容易变成参数拟合。
- 我的判断：
  - Stage230已经证明长期暴露曲线治理有效。
  - Stage231只允许一轮收益恢复边界测试，不做网格扫参。
  - 如果收益仍不到`3000%+`且尾部风险回升，就停止本轮覆盖层参数优化。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage231_risk_overlay_light_dynamic_soft_cap_gate_v2.py`
- 修改脚本：无。
- 新增参数：无。
- 修改参数：无正式参数修改，仅实验覆盖：
  - `enable_dynamic_sizing_equity_soft_cap=True`
  - `dynamic_sizing_equity_soft_cap_base=2_000_000`
  - `dynamic_sizing_equity_soft_cap_max=7_500_000`
  - `dynamic_sizing_equity_soft_cap_participation=0.60`
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
  - C：`light_dynamic_soft_cap_gate_v2`

## 结果

- A `baseline_78_1` 全样本：
  - 期末权益：`25,542,885`
  - 总收益：`5008.5770%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
  - 胜率：`43.2432%`
- C `light_dynamic_soft_cap_gate_v2` 全样本：
  - 期末权益：`13,528,570`
  - 总收益：`2605.7140%`
  - 最大回撤：`-33.8956%`
  - Sharpe：`1.2466`
  - 总滑点：`976,260`
  - 总交易次数：`866`
  - 胜率：`43.4783%`
- 多周期：
  - C在`2020-2021`独立阶段收益优于A：`617.9890%` vs `583.0930%`
  - C在`2022-2023`独立阶段收益优于A：`128.0300%` vs `123.7880%`
  - C对`2026`冷启动无改善，结果与A相同：`-9.8920%`
  - C在`since_2023`窗口最大回撤略差于A：`-36.8454%` vs `-36.2713%`
- 滑点压力：
  - A `5x`滑点：总收益`3434.0570%`，最大回撤`-66.4314%`
  - C `5x`滑点：总收益`1824.7060%`，最大回撤`-41.3505%`
- Monte Carlo：
  - A daily亏损概率`2.0%`，C为`0.4%`
  - A daily回撤超过40%概率`95.9%`，C为`51.4%`
  - A trade-block破产/穿仓概率`52.6%`，C为`26.2%`
  - A trade-block回撤超过40%概率`88.6%`，C为`72.6%`
- 与Stage230 v1对比：
  - v1全样本收益`2192.2200%`，v2提升到`2605.7140%`
  - v1 trade-block破产/穿仓概率`16.5%`，v2回升到`26.2%`
  - v2仍未达到`3000%+`收益目标，且尾部风险显著回升

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage231_risk_overlay_light_dynamic_soft_cap_gate_v2_report_stage231_risk_overlay_light_dynamic_soft_cap_gate_v2.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage231_risk_overlay_light_dynamic_soft_cap_gate_v2_summary_stage231_risk_overlay_light_dynamic_soft_cap_gate_v2.csv`
- orders：无。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage231_risk_overlay_light_dynamic_soft_cap_gate_v2_daily_stage231_risk_overlay_light_dynamic_soft_cap_gate_v2.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage231_risk_overlay_light_dynamic_soft_cap_gate_v2_monte_carlo_summary_stage231_risk_overlay_light_dynamic_soft_cap_gate_v2.csv`

## 结论

- 本阶段结论：
  - Stage231未通过预声明目标：收益没有恢复到`3000%+`，尾部风险从Stage230的`16.5%`回升到`26.2%`。
  - 不合入`78-1`，也不继续调`base/max/participation`。
  - Stage230仍是风险覆盖层中最接近尾部风险目标的候选，但收益不足；Stage231证明放松上限的收益-风险交换不划算。
- 是否进入下一步：是，但不再做本轮参数优化。
- 下一步：
  - 转向部署资金分层方案：账户层面分生产资金、锁盈资金、扩张资金，而不是继续在策略参数内拟合收益-风险平衡。
  - 仅保留Stage230作为“风险优先账户”的参考候选，不作为`78-1`正式默认。

## 过拟合反思

- 运行前判断：可控，因为只允许一轮收益恢复。
- 运行后判断：继续调参将明显进入过拟合区。
- 原因：收益恢复与尾部风险回升高度同步，继续小步调参只是在找历史曲线折中点。

## 继续价值反思

- 运行前判断：有。需要验证Stage230是否能恢复收益。
- 运行后判断：本轮参数优化继续价值低。
- 原因：v2未达目标且风险回升；更有价值的是账户部署层治理，而不是继续策略层调参。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，将下一步切换为部署资金分层方案。
- 是否追加根目录 `memory.md/back_log.md`：追加`back_log.md`，`memory.md`补充Stage231停止结论。
