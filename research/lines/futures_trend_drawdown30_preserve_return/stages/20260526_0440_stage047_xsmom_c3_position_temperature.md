# Stage047 横截面动量温度与 C3 持仓路径诊断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-26 04:40 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因诊断；不修改 C3 交易规则
- 是否重要突破：否，但是否定一条后续硬过滤方向的重要负结论
- 是否触发A/B：否，本阶段不形成交易候选，只判断 Stage045 横截面动量是否能作为 C3 持仓温度计

## 外部调研与判断

- 参考资料：
  - Moskowitz、Ooi、Pedersen 的 Time Series Momentum 研究显示期货时间序列动量有跨资产证据。
  - 商品期货横截面/时间序列动量相关研究显示横截面动量有独立经济含义，但也可能存在阶段性和成本敏感问题。
- 我的判断：
  - 横截面动量可以作为低相关收益源研究，但不能因 Stage045 净值层结果好，就直接当作 C3 的持仓过滤器。
  - 若它要承担“降回撤”角色，至少应在 C3 深回撤中解释主要亏损，并且全样本逆风桶不应是主要盈利来源。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage347_xsmom_c3_position_temperature.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `SPEC_NAME="mom_12m_skip1m"`
  - 温度分桶：`adverse/support/neutral/unavailable`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 到 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：沿用 C3 基准滑点口径，总滑点 `1,556,750`
- 样本过滤：所有 C3 活跃或交易过的日度持仓行
- 策略/归因口径：
  - C3 做多品种落在横截面动量空头篮子，或 C3 做空品种落在横截面动量多头篮子，标记为 `adverse`
  - C3 做多品种落在横截面动量多头篮子，或 C3 做空品种落在横截面动量空头篮子，标记为 `support`
  - 其他标记为 `neutral`

## 结果

- C3基准期末权益：`30,925,650`
- C3基准总收益：`6085.1300%`
- C3基准最大回撤：`-31.0767%`
- C3基准Sharpe：`1.3663`
- C3基准总滑点：`1,556,750`
- C3基准总交易次数：`757`
- C3基准胜率：`45.3826%`
- 其他关键指标：
  - 最大回撤窗口：`2021-05-12` 到 `2021-07-02`
  - 深回撤窗口 `adverse` 净损益：`-67,970`
  - 深回撤窗口 `support` 净损益：`-215,680`
  - 深回撤窗口 `neutral` 净损益：`-272,020`
  - 深回撤窗口 `adverse` 亏损占比：`12.2321%`
  - 全样本 `adverse` 净损益：`13,958,945`
  - 全样本 `support` 净损益：`2,814,890`
  - 全样本 `neutral` 净损益：`13,651,815`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage347_xsmom_c3_position_temperature_report_stage347_xsmom_c3_position_temperature_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage347_xsmom_c3_position_temperature_summary_stage347_xsmom_c3_position_temperature_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage347_xsmom_c3_position_temperature_daily_stage347_xsmom_c3_position_temperature_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage347_xsmom_c3_position_temperature_decision_stage347_xsmom_c3_position_temperature_v1.json`

## 结论

- 本阶段结论：决策 `xsmom_temperature_not_core_drawdown_explanation`。横截面动量逆风不是 C3 剩余最大回撤的核心解释。
- 是否进入下一步：不进入“横截面动量逆风硬过滤/硬门禁”方向。
- 下一步：
  - 保留 Stage045 的净值层因子价值线索，但不把它直接改造成 C3 持仓门禁。
  - 若继续动量路线，应考虑更大卫星资金、不同承载工具或纯组合层配置；若继续 C3 内部风控，应回到高点已有仓位路径风险释放，而不是新增开仓质量过滤。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段只用预先存在的 Stage045 月度横截面动量篮子和 C3 已有持仓做归因，不新增交易阈值。
- 运行后判断：本阶段不是过拟合；但如果继续把 `adverse` 做成硬过滤，就会过拟合。
- 原因：深回撤 `adverse` 只解释 `12.2321%` 亏损，且全样本 `adverse` 本身大幅盈利，硬过滤会砍掉大量历史利润而不是稳定治理尾部风险。

## 继续价值反思

- 运行前判断：有价值，因为 Stage045 净值层候选和 Stage046 真实期货腿不可行之间，需要判断它是否还能作为风险温度计。
- 运行后判断：这条“温度计硬过滤”继续价值低；总研究线仍有价值。
- 原因：负结论帮助收束研究，避免把漂亮的净值层相关性误用成 C3 的实盘门禁。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage047 负结论。
- 是否更新 `research/registry.md`：是，当前状态改为横截面动量温度计方向被反证。
- 是否追加根目录 `memory.md/back_log.md`：是，属于重要路线降级结论。
