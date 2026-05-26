# Stage033 C3波动率预算日收益层筛查

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-26 01:12 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：日收益层边界筛查，不修改正式 Stage78-1，不修改 C3 入场 alpha、AI 池或品种池。
- 是否重要突破：是，首次在 C3 底座上看到多组“收益保留 80%+ 且全样本回撤 30%以内”的账户层风险预算候选。
- 是否触发A/B：是。该方向若进入真实引擎，应按 A/C 方式隔离，不能覆盖正式基准。

## 外部调研与判断

- 参考资料：
  - Moskowitz、Ooi、Pedersen 的时间序列动量研究说明期货趋势策略常与风险缩放/风险预算结合使用：https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
  - Kim、Tse、Wald 对 Time Series Momentum and Volatility Scaling 的讨论：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2786955
- 我的判断：
  - 当前线前序 Stage031/032 已经确认 C3 剩余最大回撤主要来自高点已有仓位，而不是新增开仓质量。
  - 因此更合理的低过拟合方向不是继续调开仓过滤、品种黑名单、盈利回吐小数或回撤降仓阈值，而是账户层或组合层的风险预算。
  - 本轮只使用策略自身过去收益波动率，属于低自由度部署层假设；但日收益线性缩放不等于真实交易引擎，必须继续验证整数手数、保证金和持仓缩放路径。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage333_c3_volatility_budget_screen.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `LOOKBACKS=(20, 60, 120)`
  - `TARGET_ANNUAL_VOLS=(0.50, 0.60, 0.70)`
  - 风险缩放：`scale = min(1, target_vol / realized_vol)`，只降风险，不加杠杆。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage332 C3 日收益输出，覆盖 `2020-2026`。
- 账户规模：沿用 C3 日收益路径的 50万口径。
- 成本口径：沿用 C3 已实现日收益中的滑点和手续费结果；本轮不新增成本模型。
- 样本过滤：全样本 `full_2020_2026`，起点窗口 `start_2021/start_2022/start_2023/start_2024`，弱窗口 `weak_2021_drawdown`。
- 策略/归因口径：A 为 `A_c3_daily_linear`；C 为只根据过去日收益滚动波动率缩放每日风险暴露。

## 结果

- C3基准：
  - 期末权益：`30,925,650`
  - 总收益：`6085.1300%`
  - 最大回撤：`-31.0767%`
  - Sharpe（日收益层）：`1.6173`
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 胜率：沿用 C3 交易级结果 `45.3826%`
- 通过日收益层筛查的主要候选：
  - `C_vol_budget_lb20_target70`：总收益 `6559.0078%`，收益保留 `107.7875%`，最大回撤 `-28.3411%`，Sharpe `1.7187`，正收益起点窗口 `5/5` 严格通过。
  - `C_vol_budget_lb60_target70`：总收益 `6375.5521%`，收益保留 `104.7727%`，最大回撤 `-29.8349%`，Sharpe `1.6585`，正收益起点窗口 `5/5` 严格通过。
  - `C_vol_budget_lb60_target60`：总收益 `6196.5517%`，收益保留 `101.8310%`，最大回撤 `-28.3411%`，Sharpe `1.6903`，正收益起点窗口 `5/5` 严格通过。
  - `C_vol_budget_lb20_target60`：总收益 `5871.5354%`，收益保留 `96.4899%`，最大回撤 `-28.3411%`，Sharpe `1.7318`，正收益起点窗口 `5/5` 严格通过。
  - `C_vol_budget_lb60_target50`：总收益 `5711.0749%`，收益保留 `93.8530%`，最大回撤 `-28.3411%`，Sharpe `1.7375`，正收益起点窗口 `5/5` 严格通过。
- 其他关键指标：
  - `C_vol_budget_lb20_target70` 平均风险缩放 `0.9646`，最低缩放 `0.5577`，触发缩放交易日 `212`。
  - `C_vol_budget_lb60_target60` 平均风险缩放 `0.9549`，最低缩放 `0.6136`，触发缩放交易日 `395`。
  - `C_vol_budget_lb60_target70` 平均风险缩放 `0.9837`，最低缩放 `0.7159`，触发缩放交易日 `295`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage333_c3_volatility_budget_screen_report_stage333_c3_volatility_budget_screen_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage333_c3_volatility_budget_screen_summary_stage333_c3_volatility_budget_screen_v1.csv`
- stability：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage333_c3_volatility_budget_screen_stability_stage333_c3_volatility_budget_screen_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage333_c3_volatility_budget_screen_curves_stage333_c3_volatility_budget_screen_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage333_c3_volatility_budget_screen_decision_stage333_c3_volatility_budget_screen_v1.json`

## 结论

- 本阶段结论：决策标签为 `daily_screen_candidate_requires_real_engine`。日收益层出现多个候选，但只能说明“波动预算值得真实引擎验证”，不能直接作为正式策略结论。
- 是否进入下一步：进入。
- 下一步：
  - 只挑低自由度代表进入真实引擎，不扫小数：`lb20_target70`、`lb60_target60`、`lb60_target70`。
  - 在真实引擎中验证开仓缩放、已有持仓缩放、整数手数、保证金占用和成交成本。
  - 若真实引擎结果不能同时达到最大回撤30以内和收益保留80%以上，停止该方向，不再把 `0.67`、`55日` 等小数作为救援参数。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：目前仍不是过拟合，但存在“日收益层假阳性”的执行风险。
- 原因：
  - 参数来自标准窗口和粗年化波动目标，没有使用品种黑名单、特定年份补丁或回撤窗口特供规则。
  - 日收益缩放天然比真实期货交易更光滑，可能高估可执行性，所以必须进入真实引擎。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，且比前面盈利回吐/回撤降仓方向更值得推进。
- 原因：
  - Stage031 已确认剩余回撤来自高点已有仓位风险暴露；波动预算正好处理暴露规模，而不是事后补丁。
  - 本轮有多个粗档位同时通过，而不是单个孤立最优点，说明不像单点拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，因这是当前线从“暂无候选”转向“存在真实引擎验证候选”的重要阶段。
