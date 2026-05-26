# Stage035 C3 波动预算机制消融

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 01:45 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：机制消融 / 方向停止判断
- 是否重要突破：否，但属于方向停止证据
- 是否触发A/B：是；延续 Stage034 的隔离验证，不接入正式基准

## 外部调研与判断

- 参考资料：
  - Moskowitz, Ooi, Pedersen, `Time Series Momentum`：波动率预算在趋势组合里常见，但需要稳定的可交易暴露调整方式。
  - Moreira and Muir, `Volatility-Managed Portfolios`：日收益层波动管理有理论依据，但真实交易中不能忽略整数手数、调仓不可逆和趋势利润段。
- 我的判断：
  - Stage034 的失败不能靠调小数救回来。必须先判断失败来自“新开仓缩放无效”还是“已有仓位减仓破坏趋势利润腿”。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage335_c3_volatility_budget_mechanism_ablation.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无，复用 Stage034 波动预算参数
- 修改参数：消融只固定 `20日/70%`，分别关闭或限制触发上下文
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30
- 账户规模：500,000
- 成本口径：沿用 C3 / Stage78-1 真实引擎口径，含滑点，佣金为 0
- 样本过滤：不新增品种过滤
- 策略/归因口径：固定 `lookback=20`、`target_annual_vol=0.70`，只拆机制，不新增参数网格

## 结果

### A：C3 原始

- 期末权益：30,925,650
- 总收益：6,085.1300%
- 最大回撤：-31.0767%
- Sharpe：1.3663
- 总滑点：1,556,750
- 总交易次数：757
- 胜率：45.3826%

### D：开仓加仓缩放

- 期末权益：29,443,170
- 总收益：5,788.6340%
- 收益保留：95.1275%
- 最大回撤：-32.5088%
- Sharpe：1.3572
- 总滑点：1,463,350
- 总交易次数：753
- 胜率：45.3581%
- 已有持仓缩放次数：0
- 平均 scale：0.9686
- 最低 scale：0.5017

### D：初始开仓缩放

- 期末权益：29,443,170
- 总收益：5,788.6340%
- 收益保留：95.1275%
- 最大回撤：-32.5088%
- Sharpe：1.3572
- 总滑点：1,463,350
- 总交易次数：753
- 胜率：45.3581%
- 已有持仓缩放次数：0
- 平均 scale：0.9686
- 最低 scale：0.5017

### D：仅已有仓位减仓

- 期末权益：8,677,835
- 总收益：1,635.5670%
- 收益保留：26.8781%
- 最大回撤：-39.0512%
- Sharpe：0.9833
- 总滑点：778,600
- 总交易次数：860
- 胜率：52.2634%
- 已有持仓缩放次数：111
- 平均 scale：0.9737
- 最低 scale：0.6258

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage335_c3_volatility_budget_mechanism_ablation_report_stage335_c3_volatility_budget_mechanism_ablation_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage335_c3_volatility_budget_mechanism_ablation_summary_stage335_c3_volatility_budget_mechanism_ablation_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage335_c3_volatility_budget_mechanism_ablation_comparison_stage335_c3_volatility_budget_mechanism_ablation_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage335_c3_volatility_budget_mechanism_ablation_daily_stage335_c3_volatility_budget_mechanism_ablation_v1.csv`
- scale_history：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage335_c3_volatility_budget_mechanism_ablation_scale_history_stage335_c3_volatility_budget_mechanism_ablation_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage335_c3_volatility_budget_mechanism_ablation_trade_events_stage335_c3_volatility_budget_mechanism_ablation_v1.csv`

## 结论

- 本阶段结论：当前波动预算形状应停止。开仓缩放几乎不伤收益，但不能压回撤；已有仓位减仓能大幅改变路径，但明显破坏趋势利润腿，收益保留只有 `26.8781%`，最大回撤还恶化到 `-39.0512%`。
- 是否进入下一步：不沿本形状继续调参。
- 下一步：回到更高层的风险治理判断。若仍追求回撤30以内，优先考虑部署层组合/账户层资金分配、真正低相关策略组合，或承认当前单策略 C3 的自然回撤边界约为 `-31%`，而不是继续用波动预算硬压。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：继续围绕当前波动预算调参会过拟合。
- 原因：本阶段只拆机制，没有新增 lookback/target 网格；结果已经显示本质矛盾不是参数细节，而是“趋势利润依赖高波动段”和“已有仓位减仓不可逆”之间的冲突。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：当前波动预算方向无继续价值；本研究线本身仍有价值。
- 原因：它明确排除了一个看似强、有理论基础、日收益层漂亮的方向，避免把不可交易的连续缩放误接入实盘。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为波动预算方向停止记录。
