# Stage200 第78 AM长度矩阵只读验证

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 02:31
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读矩阵诊断 / 非正式策略优化
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py PortfolioStrategy文档：https://www.vnpy.com/docs/cn/community/app/portfolio_strategy.html
  - vn.py CTA回测文档：https://www.vnpy.com/docs/cn/community/app/cta_backtester.html
  - vn.py GitHub组织：https://github.com/vnpy
- 我的判断：vn.py组合策略示例强调`ArrayManager.update_bar`后要检查`am.inited`，未初始化时不应进入指标交易逻辑；因此本阶段矩阵是在验证指标初始化门槛，不是策略调参。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage200_stage78_am_length_matrix.py`
- 修改脚本：无正式策略修改；修正Stage199记录中“正式AM长度”为120。
- 删除脚本：无。
- 新增参数：无正式新增；只读矩阵使用`array_manager_size_floor=60/90/120/140`。
- 修改参数：无正式修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2015-01-05 至 2019-12-31。
- 预加载区间：2014-01-05开始。
- 账户规模：200,000。
- 成本口径：沿用第78默认成本/滑点口径。
- 样本过滤：第78正式配置`official_stage78_defensive_v1`，仅覆盖`array_manager_size_floor`做只读矩阵。
- 策略/归因口径：继续复用Stage199运行时埋点，统计AM初始化天数、信号函数调用、原始信号、候选、开仓、成交。

## 结果

| AM长度 | 是否正式第78 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总交易次数 | 原始信号 | 候选 | 打开候选 | AM初始化product-days |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 60 | 否 | 180,460 | -9.77% | -10.4954% | -0.3260 | 29 | 65 | 51 | 17 | 1,430 |
| 90 | 否 | 208,180 | 4.09% | -7.0604% | 0.1303 | 27 | 42 | 31 | 16 | 782 |
| 120 | 是 | 190,420 | -4.79% | -9.3439% | -0.2785 | 16 | 17 | 15 | 9 | 298 |
| 140 | 否 | 193,670 | -3.165% | -6.4400% | -0.1793 | 4 | 4 | 3 | 3 | 117 |

- 总滑点：
  - AM60：2,060
  - AM90：2,105
  - AM120：1,440
  - AM140：955
- 胜率：本阶段未计算回合胜率；重点是初始化和信号恢复。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage200_stage78_am_length_matrix_report_stage200_stage78_am_length_matrix_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage200_stage78_am_length_matrix_yearly_summary_stage200_stage78_am_length_matrix_v1.csv`
- orders：无逐笔新导出；矩阵统计以信号/成交聚合为主。
- daily：无。
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage200_stage78_am_length_matrix_stats_stage200_stage78_am_length_matrix_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage200_stage78_am_length_matrix_signal_mix_stage200_stage78_am_length_matrix_v1.csv`

## 结论

- 本阶段结论：Stage199根因成立。正式第78的AM=120在2015-2018显著限制指标初始化和信号函数调用；AM降到90或60会恢复早期信号与成交。但AM90在2015-2019表现最好只能视为诊断现象，不能直接晋升，因为这是针对早期样本改变指标历史窗口。
- 是否进入下一步：是。
- 下一步：做“连续主力序列算指标、真实主力合约执行”的只读验证，避免为了2015-2019专门调短AM长度。

## 过拟合反思

- 运行前判断：矩阵诊断本身不是过拟合。
- 运行后判断：本阶段不是过拟合，但直接选择AM90会有过拟合风险。
- 原因：我们没有把AM90合入正式版，只用它证明早期无信号来自AM初始化门槛；若按收益选AM90，就是针对2015-2019小样本调参。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：矩阵把“信号恢复”和“收益表现”分开了：短AM确实恢复信号，但不是足够干净的修法；连续主力指标方案更接近问题本质。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，待连续主力指标验证后统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选或重要突破。
