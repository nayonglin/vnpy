# Stage096 Stage079趋势广度/拥挤度状态诊断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-27 18:40 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读状态变量归因；不修改默认交易规则。
- 是否重要突破：否。发现一个可验证风险状态桶，但不是可直接晋级候选。
- 是否触发A/B：否。本阶段不生成交易版本；只导出启动日前状态。

## 外部调研与判断

- 参考资料：
  - Moskowitz / Ooi / Pedersen, Time Series Momentum：https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
  - Hurst / Ooi / Pedersen, A Century of Evidence on Trend-Following Investing：https://research.cbs.dk/en/publications/a-century-of-evidence-on-trend-following-investing/
  - Baltas, Trend-Following, Risk-Parity and the Influence of Correlations：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2673124
- 我的判断：趋势跟随的核心不是“第几次信号”本身，而是趋势风险预算、信号广度、持仓分散度、相关性和拥挤状态。仓库内常规波动预算、暴涨冷却、失败记忆冷却已经被真实引擎反证，所以本阶段只做广度/拥挤度诊断，不直接改规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage396_stage079_breadth_crowding_state_diagnostic.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无正式策略参数；脚本内使用 `enable_weighted_env_gate=True` 且 `weighted_env_gate_weight_floor=1.0` 作为 no-op 探针，仅为了导出候选状态字段。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：Stage079 口径，50万 C3 下单 + 11.5万外部现金，总账户 `615,000`。
- 成本口径：正常成本；本阶段不做滑点压力交易候选，只做状态归因。
- 样本过滤：所有自然日启动窗口，90日和180日未来体验。
- 策略/归因口径：Stage079 真实引擎 no-op 探针；状态桶只使用启动日前已可观察的持仓/候选信息。

## 结果

- 期末权益：`31,040,650`
- 总收益：`4947.2602%`
- 最大回撤：`-29.7007%`
- Sharpe：`1.3188`
- Ulcer：`15.0874`
- 总滑点：`1,556,750`
- 总交易次数：`757`
- 胜率：`45.3826%`
- 其他关键指标：
  - Stage079 探针复验：rolling252/504 日破 30 回撤率 `0%/0%`，年度/季度冷启动回撤30内通过率 `100%/100%`。
  - 入口候选快照：`1,083` 行。
  - 强状态桶：`broad_active_3plus`。
  - `3个及以上品种持仓启动` 90日：样本 `447` 天，坏体验率 `66.4430%`，相对互补样本抬高 `28.6188pp`，DD20 触发率 `43.4004%`，相对互补样本抬高 `31.1682pp`，收益5%分位 `-13.4752%`。
  - `3个及以上品种持仓启动` 180日：样本 `438` 天，坏体验率 `63.0137%`，相对互补样本抬高 `25.4472pp`，DD20 触发率 `58.4475%`，相对互补样本抬高 `28.6188pp`，收益5%分位 `-0.5365%`。
  - 补充观察：4个及以上活跃品种的 DD20 触发更集中，但这是事后观察，不能继续围绕 `4/5/6` 扫上限。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage396_stage079_breadth_crowding_state_diagnostic_report_stage396_stage079_breadth_crowding_state_diagnostic_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage396_stage079_breadth_crowding_state_diagnostic_summary_stage396_stage079_breadth_crowding_state_diagnostic_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage396_stage079_breadth_crowding_state_diagnostic_daily_stage396_stage079_breadth_crowding_state_diagnostic_v1.csv`
- state：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage396_stage079_breadth_crowding_state_diagnostic_state_daily_stage396_stage079_breadth_crowding_state_diagnostic_v1.csv`
- bucket：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage396_stage079_breadth_crowding_state_diagnostic_bucket_summary_stage396_stage079_breadth_crowding_state_diagnostic_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage396_stage079_breadth_crowding_state_diagnostic_state_chart_stage396_stage079_breadth_crowding_state_diagnostic_v1.png`

## 结论

- 本阶段结论：用户关于“多次信号失败后会不会更好”的直觉不应直接做成第 N 次信号特征；更稳健的抽象是组合状态。Stage096 显示高活跃品种广度启动日确实对应更差的 3/6 个月水下体验，但这只是风险状态，不等同于 alpha 信号。
- 是否进入下一步：只允许一次固定真实引擎验证。
- 下一步：冻结 `最大并发活跃品种=3` 做 Stage097 真实引擎验证；不扫 `2/4/5`，不提高单笔风险补收益。

## 过拟合反思

- 运行前判断：否。状态桶在运行前按经济含义预声明，且只读归因。
- 运行后判断：当前阶段仍否；但如果围绕 `3/4/5`、相关阈值、保证金阈值继续扫，会变成过拟合。
- 原因：诊断用的是启动日前状态和全样本所有启动日，不把未来收益用于交易；但状态桶只有归因价值，不足以直接成为可部署规则。

## 继续价值反思

- 运行前判断：有价值。失败记忆路线已停止，需要验证更结构化的组合状态。
- 运行后判断：有一次继续价值。`broad_active_3plus` 是清晰的风险状态，值得只做一个真实引擎反证。
- 原因：它指向组合广度扩张后的持有体验风险；但若真实引擎失败，就停止并发上限路线。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage096 约束。
- 是否更新 `research/registry.md`：否，未产生正式候选。
- 是否追加根目录 `memory.md/back_log.md`：建议追加 `back_log.md`，因为这是短持有体验优化的重要反证前置。
