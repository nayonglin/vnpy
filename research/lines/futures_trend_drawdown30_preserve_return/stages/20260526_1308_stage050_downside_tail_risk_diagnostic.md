# Stage050 C3下行半波动与左尾风险诊断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-26 13:08 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读风险状态归因
- 是否重要突破：重要反证
- 是否触发A/B：否，本阶段不生成交易候选，只判断是否值得进入A/C

## 外部调研与判断

- 参考资料：
  - `Time series momentum and volatility scaling`：商品/期货动量研究常讨论波动缩放。
  - `Asymmetry, tail risk and time series momentum`：中国商品期货 time-series momentum 中，非对称和尾部风险可能影响回撤。
- 我的判断：下行半波动、左尾分位和偏态有经济含义，但它们经常也是趋势策略高收益状态的一部分；必须先做点时化归因，不能看到回撤窗口有重叠就直接过滤。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage350_downside_tail_risk_diagnostic.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 入场日前 `20/60` 日方向收益下行半波动
  - 入场日前 `20/60` 日方向收益左尾 `q10/q05`
  - 入场日前 `20/60` 日方向收益偏态
  - 固定桶与诊断分位桶
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage328 C3 持仓回合，最长 `2020-01-01` 至 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：不重算交易成本，使用既有 C3 持仓回合损益
- 样本过滤：不删品种、不删年份、不按亏损窗口筛选
- 策略/归因口径：只读 C3 冻结路径；特征只使用入场日前已知日线

## 结果

- 期末权益：不适用，本阶段只读归因
- 总收益：C3 基准总收益沿用 `6085.1300%`
- 最大回撤：C3 基准最大回撤沿用 `-31.0767%`
- Sharpe：不适用，本阶段不生成新净值
- 总滑点：不适用
- 总交易次数：持仓回合 `379`
- 胜率：不适用
- 其他关键指标：
  - 决策标签：`downside_tail_diagnostic_no_promotion`
  - 高60日下行半波动桶全样本净损益：`15,807,720`
  - 低60日下行半波动桶全样本净损益：`14,476,285`
  - 高60日下行半波动桶在最大回撤窗口亏损占比：`58.3497%`
  - 高60日下行半波动桶最大回撤窗口净损益：`-36,230`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage350_downside_tail_risk_diagnostic_report_stage350_downside_tail_risk_diagnostic_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage350_downside_tail_risk_diagnostic_summary_stage350_downside_tail_risk_diagnostic_v1.csv`
- orders：无
- daily：无
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage350_downside_tail_risk_diagnostic_decision_stage350_downside_tail_risk_diagnostic_v1.json`

## 结论

- 本阶段结论：下行半波动/左尾风险不能直接作为 C3 开仓过滤、持仓门禁或降仓规则。
- 是否进入下一步：不进入真实引擎验证。
- 下一步：停止该具体风险状态方向；继续目标只能转向真正独立收益源、部署层候选，或重新界定 C3 自然回撤约 `-31%` 的可接受边界。

## 过拟合反思

- 运行前判断：不是过拟合，因为本阶段只做入场前已知风险特征归因，不新增交易参数。
- 运行后判断：本阶段不是过拟合；继续把分位桶调成过滤器会过拟合。
- 原因：高下行风险桶虽然覆盖最大回撤窗口部分亏损，但全样本净收益更高，说明它不是纯风险噪声。

## 继续价值反思

- 运行前判断：有价值，因为外部研究提示非对称/尾部风险可能改善趋势策略回撤。
- 运行后判断：该具体方向继续价值低；总研究线仍有价值。
- 原因：该变量不具备足够强的单调负面解释力，不能作为低过拟合规则推广。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要反证
