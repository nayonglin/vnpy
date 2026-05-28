# Stage111 Stage103 股票现金槽位跨资产审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 21:34 CST`
- 修正时间：`2026-05-27 21:52 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 组合层审计；固定 Stage103 `broker10_guard`，测试 11.5 万现金槽位是否可由真实整手股票账户和保守现金收益替代。
- 是否重要突破：是，产生组合层研究候选；但 Stage112 进一步确认不能升为部署候选。
- 是否触发A/B：是。A 为 Stage079，C0 为 Stage103，C1 为 Stage103 + 现金年化2%，C2 为 Stage103 + 真实整手股票现金槽位。

## 口径修正

- 原始 Stage111 输出曾误用股票账户 `2018-2020` 已累积净值，导致 2020 公共起点权益被抬高。
- 已在脚本中修正：股票腿和线性缩放诊断均按 `2020-01-02` 公共起点重新归一化，确保总账户仍为 `61.5万` 口径。
- 修正后，最强短持有分候选从 `10万股票 + 1.5万现金` 变为 `5万股票 + 6.5万现金年化2%`。

## 外部调研与判断

- 参考资料：AQR managed futures、AIMA managed futures varying correlations、系统化趋势跟踪开源实现。
- 我的判断：继续在商品趋势内部叠加动量/拥挤阈值已经边际价值低，跨资产低相关来源更符合第一性原理；但股票槽位替换现金缓冲，必须单独审计流动性。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage411_stage103_stock_cashslot_audit.py`
- 修改脚本：修正股票账户公共起点归一化。
- 删除脚本：无。
- 新增参数：股票真实整手槽位 `25,000 / 50,000 / 100,000` 元；现金年化 `2%`；诊断项 `115,000` 元股票净值线性缩放。
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`。
- 账户规模：总账户 `615,000` 元，固定不增加总资金。
- 成本口径：复用 Stage403 当前 78-1/C3/Stage103 日度 PnL 与 `combo_slippage`；股票腿复用 Stage370 真实整手账户最小佣金路径，并按公共起点归一化。
- 策略/归因口径：
  - Stage079：`50万C3下单 + 11.5万现金`。
  - Stage103：Stage079 + `xsmom_vt10_q_momq_round_half_true_broker10_guard`。
  - Stage111：`Stage103核心权益 - 11.5万现金 + 股票整手账户 + 剩余现金/现金收益`。

## 结果

- Stage079：
  - 期末权益：`31,040,650`
  - 总收益：`4947.2602%`
  - 最大回撤：`-29.7007%`
  - Sharpe：`1.3188`
  - Ulcer：`15.0874`
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 胜率：`45.3826%`
- Stage103 `broker10_guard`：
  - 期末权益：`31,730,915`
  - 总收益：`5059.4984%`
  - 最大回撤：`-28.9792%`
  - Sharpe：`1.3681`
  - Ulcer：`14.3132`
  - 总滑点：`1,569,265`
  - 总交易次数：约 `1217`
  - 胜率：C3逐笔胜率沿用 `45.3826%`；xsmom卫星仍是日级信号手数模拟。
- Stage103 + 11.5万现金年化2%：
  - 期末权益：`31,746,269.59`
  - 总收益：`5061.9951%`
  - 最大回撤：`-28.9181%`
  - Sharpe：`1.3700`
  - Ulcer：`14.2707`
  - 3个月/6个月体验分：`122.5050 / 134.9949`
- Stage103 + 5万真实股票整手 + 6.5万现金年化2%：
  - 期末权益：`31,746,022.93`
  - 总收益：`5061.9549%`
  - 最大回撤：`-28.9631%`
  - Sharpe：`1.3695`
  - Ulcer：`14.2690`
  - 252/504日滚动破30回撤率：`0% / 0%`
  - 年度/季度冷启动回撤30内通过率：`100% / 100%`
  - 3个月/6个月体验分：`122.2976 / 135.9356`
  - 3个月/6个月8项改善：`7/8` 与 `6/8`
- Stage103 + 10万真实股票整手 + 1.5万现金年化2%：
  - 期末权益：`31,764,611.32`
  - 总收益：`5064.9775%`
  - 最大回撤：`-28.9826%`
  - Sharpe：`1.3691`
  - Ulcer：`14.2624`
  - 3个月/6个月体验分：`123.2569 / 139.0540`
  - 但相对 Stage103 的最大回撤和成本压力不通过，因此不作为 Stage111 增量候选。

## 短持有体验

- Stage111 修正后最强增量候选 `5万股票+6.5万现金年化2%`：
  - 3个月：5%分位 `-10.8425%`，中位 `13.5800%`，正收益率 `74.7411%`，年化低于5%概率 `27.7803%`，最差回撤 `-28.9631%`，破20回撤率 `16.6141%`，Ulcer P95 `16.4424`，P95最长水下 `88` 天。
  - 6个月：5%分位 `-0.5872%`，中位 `35.8676%`，正收益率 `94.4158%`，年化低于5%概率 `8.3998%`，最差回撤 `-28.9631%`，破20回撤率 `35.7109%`，Ulcer P95 `19.0983`，P95最长水下 `167` 天。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage411_stage103_stock_cashslot_audit_report_stage411_stage103_stock_cashslot_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage411_stage103_stock_cashslot_audit_summary_stage411_stage103_stock_cashslot_audit_v1.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage411_stage103_stock_cashslot_audit_gate_stage411_stage103_stock_cashslot_audit_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage411_stage103_stock_cashslot_audit_horizon_stage411_stage103_stock_cashslot_audit_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage411_stage103_stock_cashslot_audit_cost_stress_stage411_stage103_stock_cashslot_audit_v1.csv`
- diagnostic：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage411_stage103_stock_cashslot_audit_marginal_diagnostic_stage411_stage103_stock_cashslot_audit_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage411_stage103_stock_cashslot_audit_daily_stage411_stage103_stock_cashslot_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage411_stage103_stock_cashslot_audit_decision_stage411_stage103_stock_cashslot_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage411_stage103_stock_cashslot_audit_chart_stage411_stage103_stock_cashslot_audit_v1.png`

## 结论

- 本阶段结论：修正公共起点后，`Stage103 + 5万真实股票整手 + 6.5万现金年化2%` 是 Stage111 的指标层增量候选；`Stage103 + 11.5万现金年化2%` 是更干净的现金管理增强。
- 是否进入下一步：是，但必须先做流动性与鲁棒性审计；Stage112 已完成并确认不能升部署。
- 下一步：固定候选只做 paper/执行复核，不继续扫股票槽位小数、现金收益率或股票策略参数。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合；公共起点修正确认后，10万版本被降级，避免了隐含加资金导致的误判。
- 原因：未修改策略参数、股票池或择时规则，只做粗档位组合与口径修正。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值但边界变窄；继续价值在执行/流动性复核，不在继续参数优化。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，需以 Stage112 修正摘要覆盖旧 Stage111 判断。
