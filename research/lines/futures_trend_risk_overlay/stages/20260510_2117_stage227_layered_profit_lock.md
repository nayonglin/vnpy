# Stage227 分层出金/权益锁定多周期验证

- line_id：`futures_trend_risk_overlay`
- 当前模式：`day`
- 记录时间：`2026-05-10 21:17 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：风险覆盖层A vs C验证
- 是否重要突破：是，分层出金v1相比Stage226动态软上限更接近可用风险覆盖层，但仍不直接合入正式版
- 是否触发A/B：是，`A=78-1`，`C=78-1+layered_profit_lock_v1`

## 外部调研与判断

- 参考资料：
  - Trend-following overlay与CTA风险管理资料强调，覆盖层需要同时看收益、回撤、成本和路径尾部风险。
  - Drawdown control资料强调，大回撤恢复具有非线性不对称，风险治理要优先防止深回撤。
  - Position sizing与保证金预算资料强调，实盘应把权益增长和可再加杠杆资金分开管理。
- 我的判断：
  - 分层出金的本质不是降低策略alpha，而是把部分高水位利润从“可继续加杠杆的风险资本”转为“锁定权益”。
  - 相比Stage226动态软上限，分层出金更接近真实账户治理：赚到一定阶段后部分收益不再参与后续开仓sizing。
  - 本次只做一组结构性参数，不扫小数，避免把分层出金变成收益曲线拟合。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage227_risk_overlay_layered_profit_lock.py`
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无。
- 新增参数：
  - `enable_layered_profit_lock_sizing`
  - `layered_profit_lock_base_equity`
  - `layered_profit_lock_start_equity`
  - `layered_profit_lock_ratio`
- 修改参数：无正式参数修改；新增参数默认关闭，`78-1`不受影响。
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
  - C：`layered_profit_lock_v1`
- C候选参数：
  - `enable_layered_profit_lock_sizing=True`
  - `layered_profit_lock_base_equity=1_000_000`
  - `layered_profit_lock_start_equity=2_000_000`
  - `layered_profit_lock_ratio=0.50`

## 结果

- A `baseline_78_1` 全样本：
  - 期末权益：`25,542,885`
  - 总收益：`5008.5770%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
  - 胜率：`43.2432%`
- C `layered_profit_lock_v1` 全样本：
  - 期末权益：`13,085,060`
  - 总收益：`2517.0120%`
  - 最大回撤：`-39.2765%`
  - Sharpe：`1.1704`
  - 总滑点：`959,140`
  - 总交易次数：`866`
  - 胜率：`42.7918%`
- 多周期：
  - C在`since_2025`收益略高于A：`311.2360%` vs `308.2790%`
  - C在`2026`与A相同：`-9.8920%`
  - C在早期强复利窗口收益低于A，但Sharpe多数更高
  - C在`11/11`个窗口没有扩大最大回撤
- 滑点压力：
  - A `5x`滑点：总收益`3434.0570%`，最大回撤`-66.4314%`
  - C `5x`滑点：总收益`1749.7000%`，最大回撤`-48.6547%`
- Monte Carlo：
  - A daily亏损概率`2.0%`，C为`0.9%`
  - A daily回撤超过40%概率`95.9%`，C为`75.7%`
  - A trade-block破产/穿仓概率`52.6%`，C为`24.3%`
  - A trade-block回撤超过40%概率`88.6%`，C为`72.7%`
- 其他关键指标：
  - C相比A保留约`50.25%`全样本收益，同时将总滑点降约`51.27%`
  - C相比Stage226动态软上限收益更高：`2517.0120%` vs `1596.5390%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage227_risk_overlay_layered_profit_lock_report_stage227_risk_overlay_layered_profit_lock_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage227_risk_overlay_layered_profit_lock_summary_stage227_risk_overlay_layered_profit_lock_v1.csv`
- orders：无。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage227_risk_overlay_layered_profit_lock_daily_stage227_risk_overlay_layered_profit_lock_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage227_risk_overlay_layered_profit_lock_monte_carlo_summary_stage227_risk_overlay_layered_profit_lock_v1.csv`

## 结论

- 本阶段结论：
  - 分层出金v1是强线索：它比Stage226更好地保留收益，同时明显降低滑点压力和Monte Carlo尾部风险。
  - 分层出金v1还不是正式合入候选：trade-block破产/穿仓概率仍有`24.3%`，且全样本收益牺牲约一半。
  - 它证明“收益锁定型风险覆盖层”比“硬压sizing软上限”更适合继续研究。
- 是否进入下一步：是。
- 下一步：
  - 做分层出金v2：采用多层阶梯锁定，而不是单一`50%`锁定比例。
  - 目标是在保留`3000%+`全样本收益的同时，把trade-block破产/穿仓概率继续压到`10%-15%`以下。
  - 同时补一版“保证金预算门禁”对照，判断哪类覆盖层更适合实盘。

## 过拟合反思

- 运行前判断：否。分层出金是账户治理逻辑，不依赖具体品种、信号或窗口。
- 运行后判断：否。结果呈现合理的收益-风险交换，没有靠微调单点阈值制造完美曲线。
- 原因：C降低收益和尾部风险符合第一性预期，且多窗口中没有出现只赢单一窗口的异常。

## 继续价值反思

- 运行前判断：有。Stage226证明风险覆盖层方向成立，但收益牺牲过大。
- 运行后判断：有。Stage227在保留更多收益的同时把trade-block破产/穿仓概率从`52.6%`降到`24.3%`。
- 原因：方向有效但还不够实盘稳，值得继续做结构化v2，而不是停止。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，将下一步从Stage226更新为Stage227/v2。
- 是否追加根目录 `memory.md/back_log.md`：追加`back_log.md`；`memory.md`补充风险覆盖层最新结论。
