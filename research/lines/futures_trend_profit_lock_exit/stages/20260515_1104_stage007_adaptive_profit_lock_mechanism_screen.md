# Stage007/Stage277 波动率自适应盈利锁机制屏

- line_id：`futures_trend_profit_lock_exit`
- 当前模式：`day`
- 记录时间：`2026-05-15 11:04 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：成交腿级机制屏，验证是否值得把 ATR/Chandelier 盈利保护接入完整组合引擎。
- 是否重要突破：否。
- 是否触发A/B：是，按 A/C 预声明执行；B 单独 Chandelier 退出不是完整交易系统，未单独评估。

## 外部调研与判断

- 参考资料：
  - StockCharts ChartSchool：Chandelier Exit 是基于 ATR 的移动止损，可用于定义趋势和 trailing stop。
  - MarketVolume：Chandelier Exit 由 Charles Le Beau 提出，常见默认参数为 22 period 与 3 倍 ATR。
  - StratBase/公开资料：ATR trailing stop 的核心是用波动率距离代替固定百分比距离，趋势日线常见 3x ATR。
  - GitHub 开源实现：能找到 ATR trailing stop / Chandelier Exit 的通用 Python/Pine/MQL 示例，但没有发现可直接照搬到本仓库 Stage78-1 的 vn.py 组合层实现。
- 我的判断：
  - 可借鉴的是“用波动率自适应止损距离”这一机制，而不是继续扫固定百分比小数。
  - 本阶段只用经典 `22/3` 参数做屏蔽实验，避免把 ATR 倍数也变成新的过拟合维度。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage277_adaptive_profit_lock_mechanism_screen.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 候选 C1：`current_plus_chandelier_22_3_after_5pct`
  - 候选 C2：`current_plus_chandelier_22_3_after_10pct`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage78-1 正式成交腿文件 `qmt_roll_official_stage78_1_trades_2020_2026_04.csv`。
- 账户规模：不适用。本阶段不是完整组合回测。
- 成本口径：沿用既有正式成交腿；本阶段只比较同一成交腿路径上的提前离场差异。
- 样本过滤：可加载日线数据的 `444` 个成交腿。
- 策略/归因口径：
  - A：当前 Stage78-1 固定盈利锁。
  - C：A + Chandelier/ATR 22日3倍保护层。
  - 生效阈值分别测试 `5%` 和 `10%` 最大收盘浮盈。
  - 通过闸门预声明：标准候选 `weighted_delta_sum > 0`、年份胜出至少 `5` 年、最差年份不低于 `-0.50`、正贡献腿数至少 `10`、top10 正贡献占比不高于 `85%`。

## 结果

- 期末权益：不适用，未运行完整组合回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - `current_plus_chandelier_22_3_after_5pct`
    - 交易腿：`444`
    - Chandelier 激活率：`22.97%`
    - 提前离场率：`0.00%`
    - weighted_delta_sum：`0.0`
    - positive_legs：`0`
    - negative_legs：`0`
    - year_win_count：`0`
    - pass_screen：`false`
  - `current_plus_chandelier_22_3_after_10pct`
    - 交易腿：`444`
    - Chandelier 激活率：`12.16%`
    - 提前离场率：`0.00%`
    - weighted_delta_sum：`0.0`
    - positive_legs：`0`
    - negative_legs：`0`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage277_adaptive_profit_lock_mechanism_screen_report_stage277_adaptive_profit_lock_mechanism_screen_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage277_adaptive_profit_lock_mechanism_screen_summary_stage277_adaptive_profit_lock_mechanism_screen_v1.csv`
- detail：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage277_adaptive_profit_lock_mechanism_screen_detail_stage277_adaptive_profit_lock_mechanism_screen_v1.csv`
- by_year：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage277_adaptive_profit_lock_mechanism_screen_by_year_stage277_adaptive_profit_lock_mechanism_screen_v1.csv`
- by_product：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage277_adaptive_profit_lock_mechanism_screen_by_product_stage277_adaptive_profit_lock_mechanism_screen_v1.csv`
- by_source：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage277_adaptive_profit_lock_mechanism_screen_by_source_stage277_adaptive_profit_lock_mechanism_screen_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage277_adaptive_profit_lock_mechanism_screen_decision_stage277_adaptive_profit_lock_mechanism_screen_v1.json`

## 结论

- 本阶段结论：标准 `22/3` Chandelier/ATR 保护层不值得接入正式 Stage78-1。它虽然在约 `23%` 的成交腿上激活，但没有任何一笔相对当前固定锁盈提前改善。
- 是否进入下一步：否，不进入完整组合引擎验证。
- 下一步：正式 Stage78-1 继续保持当前手工盈利锁档位；不要因为“ATR 更专业”就替换。若继续退出研究，应转向更本质的问题：当前止损触发/成交口径是否已经足够表达趋势末端，而不是再叠加一个同类 trailing stop。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合，但该方向没有增量。
- 原因：本阶段只测试经典 `22/3` 机制和两个已有锁盈层级阈值，没有按结果微调 ATR 倍数；失败说明当前固定锁盈/原有止损已经覆盖了这类保护。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：该 ATR/Chandelier 叠加方向不值得继续；盈利锁研究线保留记录即可。
- 原因：小实验已经证明它不产生增量，继续调 ATR 倍数会变成新的参数搜索。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage007 结论。
- 是否更新 `research/registry.md`：是，更新该研究线最新阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是完整回测，也不是正式候选或重要合入。
