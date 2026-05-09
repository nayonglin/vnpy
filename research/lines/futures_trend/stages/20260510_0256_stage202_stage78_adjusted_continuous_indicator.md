# Stage202 第78 复权连续主力指标只读验证

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 02:56
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读工程口径验证 / 复权连续主力指标
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py PortfolioStrategy文档：https://www.vnpy.com/docs/cn/community/app/portfolio_strategy.html
  - VeighNa社区关于`am.inited`/`ArrayManager`初始化的说明：https://www.vnpy.com/forum/topic/5392-if-not-am-inited-shi-ru-he-yu-xian-zhi-dao-kxian-shu-mu-shi-fou-zu-gou
  - vn.py GitHub组织：https://github.com/vnpy
- 我的判断：连续主力指标是对“换月导致合约级AM历史断裂”的工程验证；复权方法只用于减少换月跳价对指标的污染，不能按2015-2019收益挑选后直接合入正式版。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage202_stage78_adjusted_continuous_indicator.py`
- 修改脚本：无正式策略修改。
- 删除脚本：无。
- 新增参数：无正式新增；只读case包含`contract/raw/diff_back_adjust/ratio_back_adjust`。
- 修改参数：无正式修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2015-01-05 至 2019-12-31。
- 预加载区间：2014-01-05开始。
- 账户规模：200,000。
- 成本口径：沿用第78默认成本/滑点口径。
- baseline_contract_am：第78正式合约级AM。
- continuous_raw：未复权连续主力指标，真实主力合约执行。
- continuous_diff_back_adjust：差值后复权连续主力指标，真实主力合约执行。
- continuous_ratio_back_adjust：比值后复权连续主力指标，真实主力合约执行。

## 结果

| case | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 原始信号 | 候选 | 打开候选 | AM初始化product-days |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_contract_am | 190,420 | -4.79% | -9.3439% | -0.2785 | 1,440 | 16 | 17 | 15 | 9 | 298 |
| continuous_raw | 987,560 | 393.78% | -51.2181% | 0.9784 | 98,795 | 299 | 623 | 349 | 151 | 12,887 |
| continuous_diff_back_adjust | 248,760 | 24.38% | -44.7690% | 0.1597 | 50,195 | 319 | 625 | 348 | 162 | 12,887 |
| continuous_ratio_back_adjust | 95,770 | -52.115% | -63.4731% | -0.6179 | 29,560 | 220 | 623 | 407 | 112 | 12,887 |

- 换月调整次数：
  - 差值后复权：232次。
  - 比值后复权：232次。
- 年度恢复：
  - 差值后复权2015-2018原始信号分别为55、121、140、146。
  - 比值后复权2015-2018原始信号分别为56、122、139、144。
- 胜率：本阶段未计算回合胜率；重点是工程口径和风险边界。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage202_stage78_adjusted_continuous_indicator_report_stage202_stage78_adjusted_continuous_indicator_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage202_stage78_adjusted_continuous_indicator_yearly_summary_stage202_stage78_adjusted_continuous_indicator_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage202_stage78_adjusted_continuous_indicator_trades_stage202_stage78_adjusted_continuous_indicator_v1.csv`
- daily：无。
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage202_stage78_adjusted_continuous_indicator_stats_stage202_stage78_adjusted_continuous_indicator_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage202_stage78_adjusted_continuous_indicator_signal_mix_stage202_stage78_adjusted_continuous_indicator_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage202_stage78_adjusted_continuous_indicator_adjustments_stage202_stage78_adjusted_continuous_indicator_v1.csv`

## 结论

- 本阶段结论：连续主力指标方向确认能修复2015-2018信号断裂，但当前复权连续指标不能直接作为第78实盘口径。
- 差值后复权较未复权显著降低总滑点和收益/回撤极端性，但最大回撤仍为-44.7690%，超过用户实盘最大回撤40%边界。
- 比值后复权表现更差，期末权益95,770，总收益-52.115%，最大回撤-63.4731%，不宜继续作为主方向。
- 是否进入下一步：是，但方向应改为风险治理/执行口径反证，而不是继续优化复权收益。
- 下一步：对`continuous_diff_back_adjust`做2020-2026正式样本复跑、T+1成交和风险预算约束；若仍超过回撤边界，则连续指标只能作为诊断工具，不进入正式第78。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：验证本身不是过拟合；但如果选择差值复权作为正式版，有过拟合风险。
- 原因：差值复权在2015-2019表现相对最好，但仍未通过用户40%回撤约束，也尚未经过2020后正式样本和T+1执行反证。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但应降温。
- 原因：本阶段解决了“有没有信号”的争议，也说明简单连续指标修法风险过高；继续价值在于验证其是否能作为研究诊断或低权重辅助，而不是直接替代第78正式口径。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，待2020-2026/T+1反证后统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选或重要突破。
