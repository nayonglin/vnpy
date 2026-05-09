# Stage206 第78 fu合法映射信号漏斗复核

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 04:13
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据合法映射后的信号漏斗复核
- 是否重要突破：否，但确认早期无交易不是`fu`数据缺口导致
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py PortfolioStrategy文档：`load_bars`会影响策略初始化，`on_bars`收到K线后由ArrayManager更新指标；实盘与回测都需要足够历史K线让指标进入可用状态。
  - 连续期货资料：连续合约是拼接后的合成长期价格序列，不是可直接成交的真实合约。
  - TQSDK主连资料：主连映射用于找到真实主力合约，但映射不保证每个历史合约都有完整可交易K线。
- 我的判断：
  - Stage205已修复早期`fu`历史合法域，但信号仍要依赖合约级ArrayManager是否初始化。
  - 本阶段只看漏斗，不改规则；如果两组信号/候选/成交一致，则早期无交易不应再归因于`fu`数据缺口。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage206_stage78_fu_legal_signal_funnel.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 复用Stage205 `fu_legal_from_20180716`映射
- 修改参数：无第78正式参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：2015-01-05 至 2019-12-31
- 预加载：2014-01-05
- 账户规模：200,000
- 成本口径：沿用第78正式滑点，手续费为当前框架默认0
- 样本过滤：第78正式品种池、AI池、风控和入场规则不变
- 策略/归因口径：
  - baseline_original_mapping：原始全市场主力映射
  - fu_legal_from_20180716：2018-07-16前`fu.SHFE`不参与映射

## 结果

### 汇总

- baseline_original_mapping：
  - 期末权益：190,420
  - 总收益：-4.7900%
  - 最大回撤：-9.3439%
  - Sharpe：-0.2785
  - 总滑点：1,440
  - 总交易次数：16
  - raw_signal_count：17
  - candidate_count：15
  - opened_candidate_count：9
  - am_inited_product_days：298
- fu_legal_from_20180716：
  - 期末权益：190,420
  - 总收益：-4.7900%
  - 最大回撤：-9.3439%
  - Sharpe：-0.2785
  - 总滑点：1,440
  - 总交易次数：16
  - raw_signal_count：17
  - candidate_count：15
  - opened_candidate_count：9
  - am_inited_product_days：298

### 年度漏斗

- 2015：
  - baseline target_bar_product_days 2,608，am_inited_product_days 5，raw_signal_count 1，candidate_count 1，open_trade_count 0
  - fu_legal target_bar_product_days 2,608，am_inited_product_days 5，raw_signal_count 1，candidate_count 1，open_trade_count 0
- 2016：
  - baseline target_bar_product_days 2,766，am_inited_product_days 8，raw_signal_count 0
  - fu_legal target_bar_product_days 2,683，am_inited_product_days 8，raw_signal_count 0
- 2017：
  - baseline target_bar_product_days 2,708，am_inited_product_days 11，raw_signal_count 0
  - fu_legal target_bar_product_days 2,689，am_inited_product_days 11，raw_signal_count 0
- 2018：
  - baseline target_bar_product_days 3,054，am_inited_product_days 17，raw_signal_count 1，candidate_count 1，open_trade_count 0
  - fu_legal target_bar_product_days 3,054，am_inited_product_days 17，raw_signal_count 1，candidate_count 1，open_trade_count 0
- 2019：
  - 两组完全一致：am_inited_product_days 257，raw_signal_count 15，candidate_count 13，opened_candidate_count 9，trade_count 16

### 关键产品

- `fu.SHFE`：
  - baseline在2016/2017/2018分别有83/19/114个target bar，但am_inited_days均为0。
  - fu_legal在2016/2017移除映射，2018保留114个target bar，但am_inited_days仍为0。
  - 2019两组均有244个target bar、62个am_inited_days，产生两笔fu开仓及对应平仓。
- `SM.CZCE`：
  - 2015-2018 target bar覆盖存在，但am_inited_days均为0。
  - 2019两组均只有11个am_inited_days。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage206_stage78_fu_legal_signal_funnel_report_stage206_stage78_fu_legal_signal_funnel_v1.md`
- stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage206_stage78_fu_legal_signal_funnel_stats_stage206_stage78_fu_legal_signal_funnel_v1.csv`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage206_stage78_fu_legal_signal_funnel_summary_stage206_stage78_fu_legal_signal_funnel_v1.csv`
- product_readiness：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage206_stage78_fu_legal_signal_funnel_product_readiness_stage206_stage78_fu_legal_signal_funnel_v1.csv`
- signal_trace：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage206_stage78_fu_legal_signal_funnel_signal_trace_stage206_stage78_fu_legal_signal_funnel_v1.csv`
- candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage206_stage78_fu_legal_signal_funnel_entry_candidates_stage206_stage78_fu_legal_signal_funnel_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage206_stage78_fu_legal_signal_funnel_trades_stage206_stage78_fu_legal_signal_funnel_v1.csv`

## 结论

- 本阶段结论：
  - `fu_legal`修复了历史可交易域解释，但没有改变第78在2015-2019的信号、候选、成交和收益。
  - 2015-2017无交易的直接原因不是`fu`数据缺口，而是合约级ArrayManager初始化极少，导致信号函数调用和原始信号极少。
  - 2015、2018各有一个短信号候选，但被第78短侧规则拒绝；实际开仓集中在2019。
- 是否进入下一步：是，但不继续修复第78早期交易数。
- 下一步：
  - 2015-2017在2015起点报告中标记为“第78正式合约级规则的低/无交易冷启动段”。
  - 不为了早期交易数量放宽AM、短侧过滤器或连续复权指标。
  - 回到实盘前更有价值的任务：T+1执行审计、影子盘日报、真实数据接入。

## 过拟合反思

- 运行前判断：否。本阶段只做同参数漏斗复核。
- 运行后判断：否。
- 原因：
  - 两组结果完全一致，没有利用结果调参数或挑窗口。
  - 该结论反而约束我们不要为了2015-2017有交易而改策略。

## 继续价值反思

- 运行前判断：有价值。它能验证Stage205的覆盖率修复是否改变交易结论。
- 运行后判断：有价值，但这条早期数据修复线应收束。
- 原因：
  - 已确认早期覆盖率问题与交易结论解耦。
  - 继续深挖2015-2017以制造交易，边际价值低且过拟合风险高。

## 合入建议

- 是否更新本线 `LINE.md`：建议后续统一更新，标注2015-2017为低/无交易冷启动段。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
