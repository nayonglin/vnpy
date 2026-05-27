# Stage080 C3现金边界叠加30万股票账户审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 03:05 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：固定组合层叠加审计；不修改78-1、C3、股票账户策略、AI池、品种、止损或仓位规则。
- 是否重要突破：否。
- 是否触发A/B：是。该阶段比较 C3 部署候选与组合层候选，但只做固定口径审计，不做参数优化。

## 外部调研与判断

- 参考资料：
  - TradingStrategy.ai walk-forward analysis：强调滚动样本验证可降低单次回测的过拟合风险，但设计本身也不能被反复调优。
  - Fidelity managed futures diversification：低相关策略/资产可改善组合回撤和波动，但前提是独立收益源真实存在。
- 我的判断：
  - Stage080 不能调 `30万/11.5万` 的资金比例，否则会变成资本小数拟合。
  - 本阶段只验证一个固定问题：在 Stage079 正常成本现金边界之外，再叠加 Stage075 的独立30万股票账户，是否比同资金现金对照显著更有经济含义。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage380_c3_cash_stock_overlay_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 期货下单资金：`500,000`
  - 股票账户资金：`300,000`
  - 外部现金：`115,000`
  - 账户总资金：`915,000`
  - 同资金现金对照：`50万C3 + 41.5万现金`
  - 滚动窗口：`252/504` 个交易日
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-27`
- 账户规模：候选账户总资金 `915,000`
- 成本口径：沿用 C3 和股票账户源曲线成本口径；本阶段不新增成本模型。
- 样本过滤：以 C3、78-1、30万股票账户公共日期为准。
- 策略/归因口径：
  - `78-1 50万 + 41.5万现金`
  - `C3 50万 + 41.5万现金`
  - `C3 50万 + 11.5万现金`
  - `C3 50万 + 30万股票账户`
  - `C3 50万 + 30万股票账户 + 11.5万现金`

## 结果

- 期末权益：`30,308,682.12`
- 总收益：`3212.4243%`
- 最大回撤：`-27.4358%`
- Sharpe：`1.6181`
- 总滑点：沿用 C3 源口径 `1,556,750`
- 总交易次数：沿用 C3 源口径 `757`；股票账户源数据成交 `16,617`
- 胜率：沿用 C3 源口径 `45.3826%`
- 其他关键指标：
  - 相对同资金现金对照收益差：`+22.0636pp`
  - 相对同资金现金对照最大回撤差：`+0.5538pp`
  - 相对 Stage079 正常成本现金边界收益差：`-1534.2099pp`
  - 相对 Stage079 正常成本现金边界回撤改善：`+2.2649pp`
  - 绝对利润相对 C3 保留：`100.6916%`
  - 年度冷启动回撤30以内通过率：`100%`
  - 季度冷启动回撤30以内通过率：`100%`
  - 252日滚动回撤30以内通过率：`100%`
  - 504日滚动回撤30以内通过率：`100%`
  - 年度冷启动跑赢同资金现金对照比例：`16.6667%`
  - 季度冷启动跑赢同资金现金对照比例：`13.6364%`
  - 252日滚动跑赢同资金现金对照比例：`37.9984%`
  - 504日滚动跑赢同资金现金对照比例：`30.7692%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage380_c3_cash_stock_overlay_audit_report_stage380_c3_cash_stock_overlay_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage380_c3_cash_stock_overlay_audit_aggregate_stage380_c3_cash_stock_overlay_audit_v1.csv`
- orders：无。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage380_c3_cash_stock_overlay_audit_window_stats_stage380_c3_cash_stock_overlay_audit_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage380_c3_cash_stock_overlay_audit_decision_stage380_c3_cash_stock_overlay_audit_v1.json`
- html：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage380_c3_cash_stock_overlay_audit_curves_stage380_c3_cash_stock_overlay_audit_v1.html`

## 结论

- 本阶段结论：固定叠加 `50万C3 + 30万股票账户 + 11.5万现金` 确实更平滑，最大回撤从 Stage079 的约 `-29.70%` 进一步降到 `-27.44%`，且所有年度、季度、252日、504日窗口回撤均在30以内；但它需要 `91.5万` 总资金，收益率相对 Stage079 下降 `1534.2099pp`，并且大多数多起点/滚动窗口跑不赢同资金现金对照。
- 是否进入下一步：仅作为“若用户接受更低收益率和91.5万资金占用”的 paper 备选，不作为当前主线正式候选。
- 下一步：主线仍优先保留 Stage079 正常成本部署边界；若继续追求更优解，应寻找新的低相关收益源或更强可承载工具，而不是继续叠现金/股票账户。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合，但不晋级。
- 原因：只验证固定既有候选组合，没有调权重、参数、窗口或品种；结果显示改善主要来自资本稀释和低波动资产叠加，经济增量不够稳定。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：继续价值有限。
- 原因：该组合能明显平滑曲线，适合回答“如果更稳但收益下降是否值得看”；但不适合作为当前目标的主线解，因为资本占用从 `61.5万` 升到 `91.5万`，收益率损失较大，且同资金现金对照胜率不足。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage080 不能正式晋级。
- 是否更新 `research/registry.md`：是，简要更新最新阶段状态。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；`memory.md` 暂不更新。
