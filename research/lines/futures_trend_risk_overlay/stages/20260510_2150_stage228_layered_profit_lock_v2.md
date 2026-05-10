# Stage228 多层阶梯分层出金v2验证

- line_id：`futures_trend_risk_overlay`
- 当前模式：`day`
- 记录时间：`2026-05-10 21:50 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：风险覆盖层A vs C验证
- 是否重要突破：否。v2改善收益保留，但尾部风险比v1回升，未达到预设目标
- 是否触发A/B：是，`A=78-1`，`C=78-1+layered_profit_lock_v2`

## 外部调研与判断

- 参考资料：
  - CTA和trend-following风险覆盖层资料强调，收益锁定应避免把账户长期压成低beta，但也必须真实降低尾部路径风险。
  - 分层出金的第一性目标是把“可继续加杠杆的风险资本”和“已锁定收益”分开，不是最大化回测收益。
- 我的判断：
  - v1单一`50%`锁定牺牲收益偏多，但风险下降明显。
  - v2采用早期少锁、后期多锁，意图保留中前期复利。
  - 若v2只提升收益但尾部风险明显回升，说明单纯调分层比例不是最有效方向，下一步应转向保证金预算门禁。

## 本次变更

- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage228_risk_overlay_layered_profit_lock_v2.py`
- 新增参数：
  - `layered_profit_lock_tiers`
- 修改参数：无正式参数修改；新增参数默认空，`78-1`不受影响。
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
  - C：`layered_profit_lock_v2`
- C候选参数：
  - `enable_layered_profit_lock_sizing=True`
  - `layered_profit_lock_base_equity=1_000_000`
  - `layered_profit_lock_start_equity=2_000_000`
  - `layered_profit_lock_ratio=0.25`
  - `layered_profit_lock_tiers="5000000:0.50,10000000:0.75"`

## 结果

- A `baseline_78_1` 全样本：
  - 期末权益：`25,542,885`
  - 总收益：`5008.5770%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
  - 胜率：`43.2432%`
- C `layered_profit_lock_v2` 全样本：
  - 期末权益：`15,205,135`
  - 总收益：`2941.0270%`
  - 最大回撤：`-39.2765%`
  - Sharpe：`1.1484`
  - 总滑点：`1,116,230`
  - 总交易次数：`876`
  - 胜率：`42.9864%`
- 多周期：
  - C在`11/11`个窗口没有扩大最大回撤
  - C在早期强复利窗口收益低于A，但比v1保留更多收益
  - C对`2026`冷启动仍无改善，结果与A相同：`-9.8920%`
- 滑点压力：
  - A `5x`滑点：总收益`3434.0570%`，最大回撤`-66.4314%`
  - C `5x`滑点：总收益`2048.0430%`，最大回撤`-49.2967%`
- Monte Carlo：
  - A daily亏损概率`2.0%`，C为`1.2%`
  - A daily回撤超过40%概率`95.9%`，C为`82.9%`
  - A trade-block破产/穿仓概率`52.6%`，C为`31.3%`
  - A trade-block回撤超过40%概率`88.6%`，C为`75.6%`
- 与Stage227 v1对比：
  - v1全样本收益`2517.0120%`，v2提升到`2941.0270%`
  - v1 trade-block破产/穿仓概率`24.3%`，v2回升到`31.3%`
  - v2接近`3000%+`收益目标，但远未达到`10%-15%`尾部风险目标

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage228_risk_overlay_layered_profit_lock_v2_report_stage228_risk_overlay_layered_profit_lock_v2.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage228_risk_overlay_layered_profit_lock_v2_summary_stage228_risk_overlay_layered_profit_lock_v2.csv`
- orders：无。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage228_risk_overlay_layered_profit_lock_v2_daily_stage228_risk_overlay_layered_profit_lock_v2.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage228_risk_overlay_layered_profit_lock_v2_monte_carlo_summary_stage228_risk_overlay_layered_profit_lock_v2.csv`

## 结论

- 本阶段结论：
  - v2比v1更能保留收益，但尾部风险控制不如v1。
  - v2不是正式合入候选，不能为了接近`3000%`收益目标而接受`31.3%`的trade-block破产/穿仓概率。
  - 单纯继续调分层锁定比例，可能开始走向收益-风险曲线拟合，边际价值下降。
- 是否进入下一步：是。
- 下一步：
  - 暂停分层比例微调。
  - 转向“保证金预算门禁”：只在组合保证金/新增保证金压力过高时限制新增仓，力求保留趋势复利，同时降低极端路径穿仓概率。

## 过拟合反思

- 运行前判断：否。多层阶梯锁定是结构性账户治理规则。
- 运行后判断：开始出现过拟合风险苗头。继续微调锁定比例容易围绕收益和MC指标找平衡点，而不是基于实盘约束设计规则。
- 原因：v2显示收益和尾部风险的跷跷板很明显，继续改`0.25/0.50/0.75`这类比例可能变成参数拟合。

## 继续价值反思

- 运行前判断：有。需要验证v1收益牺牲是否能通过阶梯锁定改善。
- 运行后判断：分层出金方向仍有价值，但本线下一步不应继续比例微调。
- 原因：v2证明收益可恢复，但尾部风险回升；更有价值的是改为保证金压力触发，而不是静态高水位触发。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，将下一步切换为保证金预算门禁。
- 是否追加根目录 `memory.md/back_log.md`：追加`back_log.md`，`memory.md`补充v2结论。
