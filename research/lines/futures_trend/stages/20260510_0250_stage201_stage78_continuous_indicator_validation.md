# Stage201 第78 连续主力指标只读验证

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 02:50
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读工程口径验证 / 非正式策略优化
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py PortfolioStrategy文档：https://www.vnpy.com/docs/cn/community/app/portfolio_strategy.html
  - VeighNa社区关于`am.inited`/`ArrayManager`初始化的说明：https://www.vnpy.com/forum/topic/5392-if-not-am-inited-shi-ru-he-yu-xian-zhi-dao-kxian-shu-mu-shi-fou-zu-gou
  - vn.py GitHub组织：https://github.com/vnpy
- 我的判断：vn.py组合策略的正常生命周期是先用K线推进`ArrayManager`，`am.inited`后才计算指标和发信号。本阶段验证的是“换月导致合约级AM历史断裂”，不是引入外部策略逻辑。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage201_stage78_continuous_indicator_validation.py`
- 修改脚本：无正式策略修改。
- 删除脚本：无。
- 新增参数：无正式新增。
- 修改参数：无正式修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2015-01-05 至 2019-12-31。
- 预加载区间：2014-01-05开始。
- 账户规模：200,000。
- 成本口径：沿用第78默认成本/滑点口径。
- baseline：第78正式合约级AM，信号和执行都使用当日真实主力合约自己的AM。
- continuous_indicator_raw：按品种维护连续主力AM，信号用连续主力AM，执行仍使用当日真实主力合约。
- 关键限制：连续序列为未复权主力拼接，换月跳价可能污染均线/MACD，不能直接作为正式版。

## 结果

| case | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 原始信号 | 候选 | 打开候选 | AM初始化product-days |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_contract_am | 190,420 | -4.79% | -9.3439% | -0.2785 | 1,440 | 16 | 17 | 15 | 9 | 298 |
| continuous_indicator_raw | 987,560 | 393.78% | -51.2181% | 0.9784 | 98,795 | 299 | 623 | 349 | 151 | 12,887 |

- 年度信号恢复：
  - 2015：baseline原始信号1条、成交0笔；continuous原始信号56条、成交21笔。
  - 2016：baseline原始信号0条、成交0笔；continuous原始信号123条、成交124笔。
  - 2017：baseline原始信号0条、成交0笔；continuous原始信号139条、成交93笔。
  - 2018：baseline原始信号1条、成交0笔；continuous原始信号148条、成交51笔。
  - 2019：baseline原始信号15条、成交16笔；continuous原始信号157条、成交10笔。
- 胜率：本阶段未计算回合胜率；重点是信号链路和工程口径。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage201_stage78_continuous_indicator_validation_report_stage201_stage78_continuous_indicator_validation_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage201_stage78_continuous_indicator_validation_yearly_summary_stage201_stage78_continuous_indicator_validation_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage201_stage78_continuous_indicator_validation_trades_stage201_stage78_continuous_indicator_validation_v1.csv`
- daily：无。
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage201_stage78_continuous_indicator_validation_stats_stage201_stage78_continuous_indicator_validation_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage201_stage78_continuous_indicator_validation_signal_mix_stage201_stage78_continuous_indicator_validation_v1.csv`

## 结论

- 本阶段结论：Stage199/200根因进一步成立。2015-2018不是无行情或无信号，而是合约级AM在换月后历史断裂；按品种连续推进AM后，早期信号与成交显著恢复。
- 但`continuous_indicator_raw`不能直接合入第78：未复权拼接造成交易暴增，总滑点接近98,795，最大回撤扩大到-51.2181%，超过用户实盘最大回撤40%边界。
- 是否进入下一步：是。
- 下一步：做“复权连续主力指标”只读验证，至少比较未复权、差值后复权、比值后复权三类指标序列；执行仍落真实主力合约。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：验证本身不是过拟合，但不能按收益采纳未复权连续指标。
- 原因：本阶段没有选择参数上线，只验证工程口径；但未复权拼接结果收益高、回撤也高，若直接采纳就是把拼接噪声当alpha。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：本阶段把“数据是否存在”和“合约级指标历史是否连续”分清了，明确下一步应处理换月复权，而不是调短AM或责怪AI池。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，待复权连续主力指标验证后统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选或重要突破。
