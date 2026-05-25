# Stage012 真实引擎回撤门禁反证与外生事件数据判断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-25 17:20 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：A vs C 真实引擎验证 + 外生数据方向判断
- 是否重要突破：否，属于重要反证与路线切换依据
- 是否触发A/B：触发 A vs C；本阶段只验证部署/风控层，不改 alpha

## 外部调研与判断

- 参考资料：
  - AQR managed futures 研究：趋势策略长期价值来自跨资产趋势与危机期凸性，但回撤治理不能破坏趋势暴露。
  - SSRN《A Century of Evidence on Trend-Following Investing》：趋势跟随跨长历史有效，但长期有深回撤，需要用稳健风险预算而非短样本补丁治理。
  - EIA Weekly Petroleum Status Report：官方每周定时发布能源库存数据，时间戳明确，可用于点时化事件日历。
  - USDA WASDE：官方月度农产品供需报告，覆盖谷物、油籽、棉花等，适合做农产品事件风险日历。
  - CFTC COT：官方每周公布持仓结构，适合做境外定价品种的外生拥挤度/仓位情绪特征。
  - 国家发改委大宗商品监管公告：2021-2022 年多次涉及大宗商品保供稳价、期现联动监管、煤炭/铁矿/有色等风险提示，说明政策公告可能是国内商品尾部风险源。
- 我的判断：
  - 泛舆情数据不应作为第一优先。它可能有信号，但时间戳、版权、噪声、历史可得性和复现成本都高，容易变成“解释历史回撤”的过拟合工具。
  - 官方公告/定时报告更适合作为第一轮外生特征：发布时间明确、可审计、可点时化、可离线回放。
  - 如果要接入，应先做“事件风险覆盖层”，而不是直接用 LLM 预测涨跌。目标是减少政策/库存/供需发布日前后的尾部亏损，同时尽量保留趋势收益。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage311_stage78_1_drawdown_deleverage_engine_validation.py`
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无
- 新增参数：
  - `portfolio_drawdown_gate_entry_contexts`
  - `enable_portfolio_drawdown_deleverage`
  - `portfolio_drawdown_gate_reference_contract`
  - `portfolio_drawdown_gate_reference_volume`
- 修改参数：无正式参数修改；新增参数默认关闭，不影响 78-1 正式路径
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 到 `2026-04-30`，并补 `since_2022`、`since_2023`、`since_2024`、`ytd_2026`、`2022-2023`、`2024-2025`
- 账户规模：`500,000`
- 成本口径：沿用 78-1 真实引擎滑点口径，总手续费为 `0`
- 样本过滤：不改 AI 池、品种池、入场 alpha
- 策略/归因口径：
  - A：`official_stage78_1_defensive_50w_no_sizing_cap`
  - C1：`C_pressure040`
  - C2：`C_pressure040 + 组合回撤开仓门禁`
  - C3：`C_pressure040 + 组合回撤已有持仓降杠杆`
  - C4：`C_pressure040 + 开仓门禁 + 已有持仓降杠杆`

## 结果

### Stage310：动态回撤门禁落回真实入场/加仓引擎

- 最优保收益线索仍是 `C_pressure040`：
  - 期末权益：`25,429,055`
  - 总收益：`4985.811%`
  - 收益保留：`99.5455%`
  - 最大回撤：`-31.0767%`
  - Sharpe：`1.2650`
  - 总滑点：`2,047,490`
  - 总交易次数：`862`
  - 胜率：`45.0346%`
- `C_pressure040_ddgate_flat`：
  - 总收益：`3286.589%`
  - 收益保留：`65.619%`
  - 最大回撤：`-37.9653%`
  - 结论：收益下降但回撤没有压住。
- `C_pressure040_ddgate_all_entries`：
  - 总收益：`2922.759%`
  - 收益保留：`58.355%`
  - 最大回撤：`-38.0856%`
  - 结论：更差，不可继续。

### Stage311：动态回撤门禁落到已有持仓降杠杆

- `C_pressure040`：
  - 期末权益：`25,429,055`
  - 总收益：`4985.811%`
  - 收益保留：`99.5455%`
  - 最大回撤：`-31.0767%`
  - Sharpe：`1.2650`
  - 总滑点：`2,047,490`
  - 总交易次数：`862`
  - 胜率：`45.0346%`
- `C_pressure040_dd_deleverage`：
  - 期末权益：`4,762,560`
  - 总收益：`852.512%`
  - 收益保留：`17.0210%`
  - 最大回撤：`-36.9393%`
  - Sharpe：`0.7336`
  - 总滑点：`753,280`
  - 总交易次数：`1152`
  - 胜率：`49.5146%`
- `C_pressure040_dd_gate_deleverage`：
  - 期末权益：`9,193,350`
  - 总收益：`1738.670%`
  - 收益保留：`34.7139%`
  - 最大回撤：`-35.0566%`
  - Sharpe：`0.9158`
  - 总滑点：`958,490`
  - 总交易次数：`1162`
  - 胜率：`49.5913%`
- 其他关键指标：
  - Stage311 多周期没有候选同时满足“全样本最大回撤30以内 + 收益保留80%”。
  - 开仓门禁+降已有持仓只在 `ytd_2026` 和 `2024-2025` 这类短窗口降低回撤，但收益保留严重不足，不能推广。
- 历史模板字段：
  - 旧第78口径 `1,610,900 / 705.45% / -54.93% / Sharpe 0.661` 本阶段不适用；当前基准为第78-1 50万口径。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation_report_stage310_stage78_1_drawdown_gate_engine_validation_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage311_stage78_1_drawdown_deleverage_engine_validation_report_stage311_stage78_1_drawdown_deleverage_engine_validation_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation_summary_stage310_stage78_1_drawdown_gate_engine_validation_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage311_stage78_1_drawdown_deleverage_engine_validation_summary_stage311_stage78_1_drawdown_deleverage_engine_validation_v1.csv`
- orders：无
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation_curves_stage310_stage78_1_drawdown_gate_engine_validation_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage311_stage78_1_drawdown_deleverage_engine_validation_curves_stage311_stage78_1_drawdown_deleverage_engine_validation_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation_decision_stage310_stage78_1_drawdown_gate_engine_validation_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage311_stage78_1_drawdown_deleverage_engine_validation_decision_stage311_stage78_1_drawdown_deleverage_engine_validation_v1.json`

## 结论

- 本阶段结论：
  - `dd10_30_min850` 在日收益覆盖层好看，但落回真实交易引擎后不成立。
  - 回撤后才挡新仓/减已有仓，很难同时压住最大回撤并保留趋势收益。
  - 当前内部风控最强线索仍是 `C_pressure040`，但它卡在 `-31.0767%`，离目标只差约 `1.08pp`，不应再靠小数阈值硬凑。
  - 用户提出的舆情/政府公告方向值得开新子路线，但第一阶段应只做“官方事件风险日历/公告强度”而不是泛舆情预测。
- 是否进入下一步：是，但不继续扫组合回撤门禁。
- 下一步：
  1. 构建点时化外生事件表：NDRC/交易所风险公告、EIA、WASDE、CFTC COT、国内宏观定时数据。
  2. 先只做观测归因：这些事件是否覆盖 `C_pressure040` 最大回撤窗口和短期急跌日。
  3. 若覆盖率有效，再设计低自由度 C 方案：事件日前后冻结新增同向风险、对相关风险簇降 `10%-15%` 暴露、或者只提升 review 层级。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：Stage310/311 的机制验证不是过拟合；继续微调参数会过拟合。
- 原因：
  - 本阶段没有按单品种黑名单、具体年份或具体亏损日打补丁。
  - 新参数默认关闭，且以真实引擎验证覆盖层能否成立。
  - 但 `C_pressure040` 已经接近目标，继续调 `0.39/0.41` 或 `0.84/0.86` 属于边界救援，不应继续。
  - 外生事件数据如果使用发布后才知道的信息、新闻回填、LLM事后总结，也会产生未来函数。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：继续有价值，但方向应切换。
- 原因：
  - 内生回撤后降风险已经被多次反证，继续做的边际价值下降。
  - 外生官方事件数据有第一性原理支撑：政策监管、库存/供需报告、仓位拥挤变化可能引发商品期货跳变和趋势中断。
  - 这些数据如果点时化处理，可以成为低过拟合的风险覆盖层，而不是预测 alpha。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，最新关键阶段应更新到 Stage012。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 重要摘要；`memory.md` 暂不追加，除非后续外生事件线跑出候选。
