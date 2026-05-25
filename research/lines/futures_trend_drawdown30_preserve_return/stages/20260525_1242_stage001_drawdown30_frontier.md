# Stage001 第78-1回撤30以内保收益前沿筛查

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-25 12:42 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：新研究线首轮可行性筛查；先做账户层/资金治理，不动78-1 alpha。
- 是否重要突破：否
- 是否触发A/B：是，`A=78-1正式基准`，`C=78-1+回撤压缩覆盖层`

## 外部调研与判断

- 参考资料：
  - SSRN/论文方向：波动率目标、尾部风险目标、drawdown-modulated sizing、trend following portfolio construction。
  - vn.py/GitHub方向：`risk_manager` 更偏前端风控和委托限制，适合落地交易闸门；策略回撤压缩仍需要策略层资金/组合预算。
- 我的判断：
  - 低过拟合优先级应是组合风险预算、资金软上限、单笔/总资金占用、相关性和波动风险，而不是改某几个品种或专门修2026弱窗口。
  - 如果“只在回撤发生后降风险”，容易错过恢复段，形成类似影子盘 `review` 的风险死锁，所以必须先验证真实引擎前沿。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage292_stage78_1_drawdown30_overlay_scan.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage293_stage78_1_drawdown30_engine_frontier.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `enable_incremental_margin_budget_gate`
  - `incremental_margin_budget_gate_usage_ratio`
  - `max_single_trade_capital_usage_ratio`
  - `max_capital_usage_ratio`
  - `enable_dynamic_sizing_equity_soft_cap`
  - `dynamic_sizing_equity_soft_cap_base/max/participation`
  - `dynamic_sizing_equity_soft_cap_margin_start_ratio/full_ratio`
  - `dynamic_sizing_equity_soft_cap_drawdown_start_ratio/full_ratio`
- 修改参数：无正式参数修改，仅研究脚本内候选配置。
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - 全样本：2020起点至今。
  - 弱窗口观察：2026年初至今。
- 账户规模：`500,000`
- 成本口径：沿用第78-1正式回测成本和滑点口径。
- 样本过滤：沿用78-1正式AI池、品种宇宙、fu卫星口径，不新增品种黑名单。
- 策略/归因口径：
  - Stage292：基于78-1日收益曲线做低自由度日级覆盖扫描，只作理论边界。
  - Stage293：落回真实策略引擎，做5个配置型风控候选。

## 结果

- A `A_baseline_78_1` 全样本：
  - 期末权益：`25,542,885`
  - 总收益：`5008.577%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
  - 胜率：见summary输出
- 最保收益候选 `C_single50_margin_budget`：
  - 期末权益：`26,264,470`
  - 总收益：`5152.894%`
  - 收益保留：`102.88%`
  - 最大回撤：`-39.7766%`
  - Sharpe：`1.2057`
  - 总交易次数：`880`
  - 结论：收益不降，但几乎没有压低回撤。
- 最接近回撤目标候选 `C_soft_cap_risk_first_ref`：
  - 期末权益：`11,461,100`
  - 总收益：`2192.220%`
  - 收益保留：`43.77%`
  - 最大回撤：`-29.3274%`
  - Sharpe：`1.3048`
  - 总交易次数：`860`
  - 结论：回撤进30以内，但收益下降过大，不满足“收益不显著降低”。
- 中间档 `C_soft_cap_mid_v1`：
  - 期末权益：`12,383,170`
  - 总收益：`2376.634%`
  - 收益保留：`47.45%`
  - 最大回撤：`-31.7648%`
  - Sharpe：`1.2610`
  - 结论：仍未进30以内，同时收益下降较大。
- 其他关键指标：
  - `C_margin_budget_rank1`：收益保留`92.12%`，最大回撤`-39.9534%`，回撤改善仅`0.11pp`。
  - `C_total80_single50_margin_budget`：收益保留`74.08%`，最大回撤`-36.2287%`，回撤改善`3.83pp`，不够。
  - Stage293全样本严格通过数：`0`
  - Stage293全样本研究通过数：`0`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage293_stage78_1_drawdown30_engine_frontier_report_stage293_stage78_1_drawdown30_engine_frontier_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage293_stage78_1_drawdown30_engine_frontier_summary_stage293_stage78_1_drawdown30_engine_frontier_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage293_stage78_1_drawdown30_engine_frontier_comparison_stage293_stage78_1_drawdown30_engine_frontier_v1.csv`
- daily/curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage293_stage78_1_drawdown30_engine_frontier_curves_stage293_stage78_1_drawdown30_engine_frontier_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage293_stage78_1_drawdown30_engine_frontier_decision_stage293_stage78_1_drawdown30_engine_frontier_v1.json`

## 结论

- 本阶段结论：
  - 只靠配置型资金治理，无法同时做到“最大回撤30以内”和“收益不显著降低”。
  - 这不是正式失败，而是说明前沿形状很清楚：保收益的闸门太弱，能降回撤的软上限明显牺牲复利。
- 是否进入下一步：是
- 下一步：
  - 做最大回撤段归因：拆最大回撤期间的品种、方向、信号来源、持仓集中度、相关性、开仓时市场状态。
  - 重点找“回撤发生前的风险状态过滤”，而不是继续扫软上限小数。
  - 如果归因显示回撤由少数超相关同向品种或特定入场拥挤造成，再设计入场前过滤；如果归因显示是趋势策略天然回撤，则接受收益/回撤前沿，不强行压30。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：仍不是过拟合。
- 原因：
  - 本轮没有改AI池、品种池、信号阈值或出场规则。
  - 候选是通用风险预算，不针对某一年或某个品种。
  - 失败结果也被保留，避免用小数扫参硬凑目标。

## 继续价值反思

- 运行前判断：有价值继续。
- 运行后判断：仍有价值，但方向要换。
- 原因：
  - 已经确定“资金软上限单独解决不了”这个边界，避免继续在低效方向消耗。
  - 下一步归因能回答回撤是否来自可识别风险状态；这是判断能否压到30以内的关键。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态和下一步。
- 是否更新 `research/registry.md`：是，新增本研究线索引。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段未形成正式候选或跨线合入结论。
