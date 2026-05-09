# Stage210 第78 2015-2018 AI池/卫星过滤反事实

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 05:05
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：反事实归因测试
- 是否重要突破：否，属于早期无成交原因定位
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - 趋势跟踪资料普遍强调：系统应先拆分信号、过滤器、仓位和风控层，逐层做反事实归因，避免把所有无交易归咎于单一过滤器。
  - 自动化期货策略资料也强调：回测应区分 entry signal、risk sizing、execution 和 filters。
- 我的判断：
  - 本轮不能直接改第78正式参数，只做反事实覆盖层关闭。
  - 为避免误判，除用户指定的关闭AI/卫星过滤外，额外增加“放回默认全品种池”的参考层，用于区分静态品种池影响。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 反事实口径

- 回测窗口：`2015-01-05` 至 `2018-12-31`
- 策略版本：以 `official_stage78_defensive_v1` 为基准
- 账户规模：`200,000`
- 基础风险：`0.045`
- 执行模型：`SameDayCloseBacktestingEngine`
- 数据库：项目级 `/Users/bytedance/Desktop/person/vnpy/.vntrader/database.db`
- 运行门禁：
  - `TRADER_DIR=/Users/bytedance/Desktop/person/vnpy`
  - `TEMP_DIR=/Users/bytedance/Desktop/person/vnpy/.vntrader`
  - Stage196 2015哨兵数据检查通过

## 变体

- `official_stage78`
  - 官方第78基线
  - `enable_ai_product_pool_filter=True`
  - `product_universe_mode=stage78_static_pool`
  - `streak_risk_state_excluded_products=fu.SHFE`
- `no_ai_sat_keep_universe`
  - 关闭AI池/卫星过滤
  - 保留第78静态品种池
  - `enable_ai_product_pool_filter=False`
  - `ai_product_pool_eligibility_path=""`
  - `ai_product_pool_strategy=""`
  - `streak_risk_state_excluded_products=""`
- `no_ai_sat_full_universe`
  - 关闭AI池/卫星过滤
  - 放回默认全品种池
  - `product_universe_csv_path=""`

## 结果

- `official_stage78`
  - 期末权益：`0`
  - 总收益：`0.0000%`
  - 最大回撤：`0.0000%`
  - Sharpe：`0.0000`
  - 总交易次数：`0`
  - 候选快照：`2`
  - 实际成交：`0`
- `no_ai_sat_keep_universe`
  - 期末权益：`0`
  - 总收益：`0.0000%`
  - 最大回撤：`0.0000%`
  - Sharpe：`0.0000`
  - 总交易次数：`0`
  - 候选快照：`2`
  - 实际成交：`0`
- `no_ai_sat_full_universe`
  - 期末权益：`0`
  - 总收益：`0.0000%`
  - 最大回撤：`0.0000%`
  - Sharpe：`0.0000`
  - 总交易次数：`0`
  - 候选快照：`2`
  - 实际成交：`0`

## 候选归因

- 三组反事实的候选完全一致：
  - `2015-11-12`，`au.SHFE / au1512.SHFE`，方向 `short`，信号 `short_case2`
  - `2018-11-26`，`CF.CZCE / CF901.CZCE`，方向 `short`，信号 `short_case3`
- 三组 skip 原因完全一致：
  - `short_signal_rejected`：`2`
- 官方组 AI 池状态：
  - `ai_product_pool_enabled=1`
  - `ai_product_pool_allowed=1`
  - 未出现 `ai_product_pool_blocked`
- 代码原因：
  - `qmt_roll_portfolio_strategy.py` 中 `_can_open_short_signal()` 只允许 `short_case1a`
  - 本轮两个早期候选分别是 `short_case2` 和 `short_case3`，因此被核心短空信号门禁拒绝

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage210_stage78_2015_2018_ai_satellite_filter_counterfactual_summary_stage210_stage78_2015_2018_ai_satellite_filter_counterfactual_v1.csv`
- summary_json：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage210_stage78_2015_2018_ai_satellite_filter_counterfactual_summary_stage210_stage78_2015_2018_ai_satellite_filter_counterfactual_v1.json`
- skip_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage210_stage78_2015_2018_ai_satellite_filter_counterfactual_skip_summary_stage210_stage78_2015_2018_ai_satellite_filter_counterfactual_v1.csv`
- candidate_snapshots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage210_stage78_2015_2018_ai_satellite_filter_counterfactual_candidate_snapshots_stage210_stage78_2015_2018_ai_satellite_filter_counterfactual_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage210_stage78_2015_2018_ai_satellite_filter_counterfactual_trades_stage210_stage78_2015_2018_ai_satellite_filter_counterfactual_v1.csv`

## 结论

- 2015-2018无成交不是第78 AI池或FU卫星过滤导致。
- 关闭AI池/卫星过滤后，候选数、skip原因、成交数完全不变。
- 真正拦截点是第78核心短空门禁：新开空只允许 `short_case1a`，而早期只有 `short_case2/short_case3` 候选。
- 放回默认全品种池后仍没有新增候选，说明静态品种池也不是主要原因。

## 过拟合反思

- 运行前判断：否。本轮是固定参数下的过滤器反事实，不按收益调参。
- 运行后判断：否，但不能据此马上放开短空门禁。
- 原因：
  - 早期只有2个被拒候选，样本量太低。
  - 如果为了2015-2018有交易而放开 `short_case2/3`，高度可能是为低样本窗口调参。

## 继续价值反思

- 运行前判断：有价值。它直接回答“是否被AI/卫星过滤挡掉”。
- 运行后判断：有价值，但下一步不应直接改正式版。
- 下一步：
  - 如需继续归因，可做只放开 `short_case2/3` 的反事实，但必须覆盖 2015-2026 全样本和弱窗口，不得只看2015-2018。
  - 第78正式版不建议因本轮结果修改，继续保持 `short_case1a` 短空门禁。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，正式基准未改变。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
