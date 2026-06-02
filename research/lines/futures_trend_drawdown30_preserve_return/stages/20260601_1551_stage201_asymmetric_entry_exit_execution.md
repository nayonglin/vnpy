# Stage201 非对称执行回放审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 15:51 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行语义实验 / 真实窗口价格敏感性审计
- 是否重要突破：否，但形成明确反证
- 是否触发A/B：否。本阶段只改撮合语义，不新增可晋级策略版本。

## 外部调研与判断

- 参考资料：
  - QuantConnect Understanding Time：https://www.quantconnect.com/docs/v1/key-concepts/understanding-time
  - Backtrader broker `cheat-on-close` 文档源码：https://backtrader.readthedocs.io/en/latest/_modules/backtrader/brokers/bbroker.html
- 我的判断：
  - 事件驱动回测的基本原则是已完成 bar 信号只能在后续可用事件成交；QuantConnect 明确说明 bar 的 close 只有在下一 bar 起点才真正可见，Backtrader 也把同 bar close 成交称为 `Cheat-On-Close`。
  - 用户提出的“开仓 T+1、平仓当天”有研究价值，因为它区分开仓延迟与退出延迟；但若平仓信号仍依赖完整日K收盘价，则当天 14:55-15:00 成交只能作为半乐观上界，不能直接作为实盘语义。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage501_asymmetric_entry_exit_execution.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `ASYMM_VARIANT=stage079_entry_next_real_open_exit_same_1455_vwap`
  - 开仓成交：下一真实窗口，夜盘品种优先 `21:00-21:05 first_open`，否则次日 `09:00-09:05 first_open`
  - 平仓/减仓成交：当日 `14:55-15:00` VWAP
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：Stage079 口径 `50万C3下单 + 11.5万外部现金`，账户权益以 `615,000` 为基准
- 成本口径：沿用 C3/Stage079 原始手续费、滑点、合约乘数、保证金设置；另做 `1x/2x/3x/5x` 滑点压力
- 样本过滤：无日期、品种、坏窗口过滤
- 策略/归因口径：
  - 策略规则、品种池、AI池、入场/出场逻辑均不变
  - 只修改撮合层：`Open` 订单延迟到下一真实窗口，`Close` 订单当日真实窗口代理成交
  - 读取 Stage149 账本代理价，缺失时从本地分钟缓存重建，仍缺失则 fallback 到日线价格并计数

## 结果

- Stage079 baseline：
  - 期末权益：`31,040,650`
  - 总收益：`4947.2602%`
  - 最大回撤：`-29.7007%`
  - Sharpe：`1.3188`
  - Ulcer：`15.0874`
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 非零日胜率：`48.3478%`
- Stage201 非对称执行：
  - 期末权益：`34,465,734`
  - 总收益：`5504.1844%`
  - 最大回撤：`-48.0275%`
  - Sharpe：`1.1579`
  - Ulcer：`20.9964`
  - 总滑点：`2,075,660`
  - 总交易次数：`777`
  - 非零日胜率：`53.0933%`
  - 开仓下一真实窗口成交：`386` 笔
  - 平仓当日 14:55 VWAP 成交：`391` 笔
  - fallback：`31/777` 笔，其中开仓 `22`、平仓 `9`
  - 最大回撤窗口：`2021-09-16` 至 `2022-01-17`，峰值 `3,336,805`，谷值 `1,734,222`
- 3个月体验：
  - Stage079：p05 `-11.4702%`，中位 `13.5434%`，DD30破例 `0.0000%`，Ulcer P95 `17.7786`
  - Stage201：p05 `-23.7864%`，中位 `17.5438%`，DD30破例 `9.1400%`，Ulcer P95 `23.6232`
- 6个月体验：
  - Stage079：p05 `-2.0393%`，中位 `33.9947%`，DD30破例 `0.0000%`，Ulcer P95 `19.9011`
  - Stage201：p05 `-14.7034%`，中位 `31.9010%`，DD30破例 `29.6574%`，Ulcer P95 `28.3091`
- 成本压力：
  - `1x` 最大回撤 `-48.0275%`，劣于 Stage079 `-29.7007%`
  - `2x` 最大回撤 `-51.6543%`，劣于 Stage079 `-31.2917%`
  - `3x` 最大回撤 `-56.2813%`，劣于 Stage079 `-33.0035%`
  - `5x` 最大回撤 `-73.1105%`，劣于 Stage079 `-40.1055%`
- 其他关键指标：
  - rolling252 DD30 破例率：`38.5922%`
  - rolling504 DD30 破例率：`71.9580%`
  - 年度冷启动 DD30 通过率：`20.0000%`
  - 季度冷启动 DD30 通过率：`22.7273%`
  - 90日体验分：`-54.0594`
  - 180日体验分：`-429.1680`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage501_asymmetric_entry_exit_execution_report_stage501_asymmetric_entry_exit_execution_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage501_asymmetric_entry_exit_execution_summary_stage501_asymmetric_entry_exit_execution_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage501_asymmetric_entry_exit_execution_daily_stage501_asymmetric_entry_exit_execution_v1.csv`
- trade usage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage501_asymmetric_entry_exit_execution_trade_usage_stage501_asymmetric_entry_exit_execution_v1.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage501_asymmetric_entry_exit_execution_gate_stage501_asymmetric_entry_exit_execution_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage501_asymmetric_entry_exit_execution_chart_stage501_asymmetric_entry_exit_execution_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage501_asymmetric_entry_exit_execution_decision_stage501_asymmetric_entry_exit_execution_v1.json`

## 结论

- 本阶段结论：`asymmetric_execution_semantic_hard_fail_reject`。开仓 T+1 下一真实窗口、平仓当日真实窗口，并不能修复 Stage079 的真实执行问题；它把总收益推高到 `5504.1844%`，但回撤打到 `-48.0275%`，Sharpe 和 Ulcer 均劣化，3个月/6个月尾部持有体验显著恶化。
- 是否进入下一步：否，不作为晋级候选。
- 下一步：
  - 不继续救该非对称执行语义的小参数。
  - 若以后还讨论“当天平仓”，必须先证明平仓信号能在 14:55 前冻结，否则同 bar 信息问题仍在。
  - 当前更合理的路线是停止修补 Stage079 同日收盘执行假设，把 Stage079 仅保留为原始日线研究 baseline；新候选必须从一开始按真实可见数据和真实可成交时点设计。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但该路线不值得救参。
- 原因：本阶段只预先定义执行时点，不筛选日期、品种、坏窗口，也没有调策略参数；失败后应停止，不应改成按收益挑 `14:59`、夜盘/白盘、品种分支等小语义。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：该具体路线继续价值低，总研究线仍有价值。
- 原因：它直接回答了“只延迟开仓、当天退出是否能保住信号一致性和持有体验”。结果说明不能；继续在这个形状上修补容易变成执行语义过拟合。总研究线的价值转向真实可见数据下重新设计策略或寻找低自由度新风险源。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage201 执行约束。
- 是否更新 `research/registry.md`：是，当前最新阶段应从 Stage200 更新为 Stage201。
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要执行语义反证追加摘要。
