# Stage004 Stage827 C2回撤恶化归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 16:03 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因；拆解 Stage827 C2 为什么收益更高但最大回撤更深
- 是否重要突破：否。C2 仍不晋级，但明确了失败机制。
- 是否触发A/B：否。仍是 Stage819 候选内部研究，不与 Stage372/20w 官方正式版做 promotion A/B/C。

## 外部调研与判断

- 参考资料：
  - Graham Capital 趋势跟随 primer：https://www.grahamcapital.com/blog/trend-following-primer/
  - AlphaTarget 趋势跟随风险与仓位管理：https://alphatarget.com/insights/trend-following-a-strategy-for-navigating-markets/
  - SSRN 趋势跟随中止损与交易频率研究：https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2349848_code1794015.pdf?abstractid=2349848&mirid=1
  - City, University of London 趋势跟随止损论文：https://openaccess.city.ac.uk/id/eprint/17842/8/BLACKBOX%20%20%20SSRN-id2126476.pdf
  - Stop-loss and re-entry 相关文献索引：https://www.semanticscholar.org/paper/Assessing-Stop-Loss-and-Re-Entry-Strategies-Klement/92428c679f6d1cc97d2e66d34087cadf90b69e5a
  - Concretum 趋势跟随仓位、vol targeting 与 pyramiding：https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/
- 我的判断：
  - 趋势策略里的日内止损不能只按单笔 closed lot 判断；它会释放保证金和权益，继而改变后续同一批机会的手数、风险预算和强平/去杠杆路径。
  - C2 的直接止损事件多数是在减亏，但组合层回撤更深，说明失败点是二阶资金路径，不是分钟止损触发本身。
  - 如果现在去按 2022 年、`fu.SHFE` 或 1R 倍数补丁化，属于明显过拟合；下一步只能做预声明、账户层、跨时期一致的风险预算归因或闸门。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage828_stage827_c2_drawdown_forensics.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `MODEL_TAG=stage828_stage827_c2_drawdown_forensics_v1`
  - 归因窗口：C2 自身峰值 `2022-03-09` 至自身谷值 `2022-06-29`
  - 对照口径：Stage827 A baseline vs Stage827 C2 engine
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage827 全路径结果，2018-01-01 至 2026-05-29；重点归因窗口为 2022-03-09 至 2022-06-29
- 账户规模：30万，沿用 Stage819 候选配置
- 成本口径：沿用 Stage819/Stage827 滑点、手续费和组合日线统计口径
- 样本过滤：
  - 不重跑策略逻辑，不新增交易规则。
  - 读取 Stage827 的 curve、closed_lots、intraday_events、entry_risk、trade_events。
  - 分拆直接 C2 止损事件、窗口内 lot 差异、品种方向贡献、保证金/权益路径和图像证据。
- 策略/归因口径：
  - A：Stage819 原始候选在 Stage827 engine 中的复现结果
  - C：Stage827 C2 `1R止损先于1R确认则退出` 组合路径
  - 本阶段只解释差异，不修改 Stage372/20w 官方正式版，不连接 CTP，不调用下单 API

## 结果

- A 期末权益：26,322,730
- A 总收益：8,674.24%
- A 最大回撤：-54.75%
- A Sharpe：1.436
- A 总滑点：2,149,150
- A 总交易次数：666
- A 胜率：53.11%
- C 期末权益：37,022,638.4
- C 总收益：12,240.88%
- C 最大回撤：-62.77%
- C Sharpe：1.458
- C 总滑点：2,512,570
- C 总交易次数：672
- C 胜率：53.15%
- 新增回测结果：
  - C2 自身峰值日：2022-03-09。
  - C2 自身谷值日：2022-06-29。
  - C2 谷值权益：4,542,658.4。
  - A 同日权益：5,601,205.0。
  - C-A 谷值权益差：-1,058,546.6。
  - C2 谷值回撤：-62.7688%。
  - A 同日回撤：-54.7546%。
  - C-A 回撤差：-8.0141pp。
  - 2022-03-09 至 2022-06-29 窗口内 C-A 净损益差：-774,050。
  - 窗口内 C 相对 A 的最大保证金/权益差：+45.7703pp。
  - C2 总触发事件：51 次；2022 年触发 8 次。
  - 2022 年 C2 直接事件合计是正贡献：C-A 直接 realized pnl delta 为 +605,911。
  - 2022 窗口 exposure diff 全部为 `both`，没有 C-only 或 A-only 新机会；C 的风险金额增加 476,609，手数增加 547。
  - 窗口内最差品种方向贡献是 `fu.SHFE long`：5 笔，C-A realized pnl delta -611,480，手数增加 122。
  - 最大单笔负差来自 `2022-04-18|fu2209.SHFE|long|long_case3|flat_entry|base`：A -365,000，C -790,000，C-A -425,000；C 路径没有逃开同一机会，反而以更差路径承担损失。
  - 全样本最差 C2-vs-A 回撤差日集中在 2020-10/11，说明 C2 的相对回撤恶化不是 2022 专属补丁问题；2022 是 C2 绝对最深谷值和正式失败点。
- 修改回测结果：无。Stage827 的 C2 “收益更高但回撤恶化、不晋级”结论被保留。
- 删除回测结果：无

## 视觉复盘

- 路径图：
  - 2022 年 C2 权益线在 3 月峰值后更快跌到更低平台，6 月底形成 C2 自身最深谷值。
  - Drawdown 图中 C2 红线长期低于 A，说明不是单日异常，而是路径性劣化。
  - Broker10 margin/equity 图中 C2 多段显著高于 A，符合“释放资金后同机会仓位更大”的归因。
- 2022 C2 事件图：
  - `jm2205 long`、`MA209 short`、`MA209 long`、`jm2301 long`、`SA301 long` 等事件直接减亏。
  - `SA205 long`、`cu2203 long`、`lh2303 short` 等事件直接负贡献。
  - 整体看，直接止损本身并不是 2022 回撤恶化主因；真正问题是止损后组合资金路径重排。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage828_stage827_c2_drawdown_forensics_report_stage828_stage827_c2_drawdown_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage828_stage827_c2_drawdown_forensics_summary_stage828_stage827_c2_drawdown_forensics_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage828_stage827_c2_drawdown_forensics_daily_delta_stage828_stage827_c2_drawdown_forensics_v1.csv`
- lot diff：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage828_stage827_c2_drawdown_forensics_window_lot_diff_stage828_stage827_c2_drawdown_forensics_v1.csv`
- product attr：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage828_stage827_c2_drawdown_forensics_window_product_attr_stage828_stage827_c2_drawdown_forensics_v1.csv`
- C2 event impact：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage828_stage827_c2_drawdown_forensics_c2_event_impact_stage828_stage827_c2_drawdown_forensics_v1.csv`
- exposure diff：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage828_stage827_c2_drawdown_forensics_exposure_diff_stage828_stage827_c2_drawdown_forensics_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage828_stage827_c2_drawdown_forensics_decision_stage828_stage827_c2_drawdown_forensics_v1.json`
- path chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage828_stage827_c2_drawdown_forensics_path_chart_stage828_stage827_c2_drawdown_forensics_v1.png`
- 2022 event atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage828_stage827_c2_drawdown_forensics_2022_event_atlas_stage828_stage827_c2_drawdown_forensics_v1.png`

## 结论

- 本阶段结论：
  - Stage004 不支持 C2 晋级。C2 在组合路径中收益更高，但回撤恶化的机制已经明确：直接止损事件多为减亏，释放资金后在同一批机会上放大了手数和风险预算，使 2022 峰谷回撤更深。
  - 2022 窗口没有发现 C-only 新机会主导亏损，主要是 `both` 机会的规模差和保证金路径差。
  - `fu.SHFE long` 是窗口内最大负贡献方向，但不能据此做品种过滤，因为全样本回撤差还在 2020-10/11 出现过更大的相对恶化。
  - 日内实时止损可以保留为有效经验：它确实能让部分错单快速止损；但必须配套账户层风险预算/再入场纪律，不能单独接入候选。
- 是否进入下一步：是，但不是调参推进
- 下一步：
  - 只做低自由度、预声明的账户层归因：例如止损释放资金后是否需要维持原始风险预算上限、权益新高前不放大同类机会、或组合保证金/权益上限闸门。
  - 先做只读 counterfactual attribution，再决定是否写策略；不要直接改 `1R`、冷却天数、品种过滤或年份过滤。

## 过拟合反思

- 运行前判断：否。本阶段是只读归因，使用 Stage827 已冻结的 A/C 输出，不新增策略自由度。
- 运行后判断：否，但如果按本阶段暴露出来的 `fu.SHFE`、2022 窗口或某个 R 倍数做补丁，就是过拟合。
- 原因：
  - 归因解释的是组合路径机制，不是反推一个局部修复规则。
  - 全样本最差相对回撤差还出现在 2020-10/11，说明问题不是单一 2022 场景，不能用局部样本救参。

## 继续价值反思

- 运行前判断：有。Stage827 给出“收益大幅提高但回撤恶化”的矛盾结果，必须拆出直接事件与二阶资金路径。
- 运行后判断：有，但继续方向要收窄。
- 原因：
  - 有价值的是“日内止损 + 账户层风险预算”的框架，而不是 C2 裸规则。
  - 当前证据足以否决 C2 裸接入；也足以支持下一步只研究释放资金后的风险预算保持，而不是继续分钟阈值扫描。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新 Stage004 归因和下一步。
- 是否更新 `research/registry.md`：否。按并行研究记录纪律，暂不频繁改 registry。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、不是重要突破、不是跨线合并。
