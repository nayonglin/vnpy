# Stage018 Stage842 止损后结构破坏taxonomy

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-14 20:44 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读 taxonomy + 分钟K视觉法证；不新增策略版本、不跑真实组合引擎、不连接 CTP、不调用下单。
- 是否重要突破：否。出现一个全量 gross 正线索，但 Stage841 子集为负且误伤右尾，不能定性为突破。
- 是否触发A/B：否。本阶段不是正式候选，也不涉及第78/Stage372正式基准接入。

## 外部调研与判断

- 参考资料：
  - CME futures order types：止损单是预定义风险控制工具，触发并不等同于策略判断已经正确。[CME Futures Order Types](https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types)
  - CME position and risk management：风险管理应围绕仓位、保证金和可承受亏损，而不是事后用单笔路径补参数。[CME Position and Risk Management](https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management)
  - CFTC stop order study：止损触发与日内波动、订单簿和市场微结构相关，不能把一次触发直接解释为趋势失败。[CFTC Stop Orders in Select Futures Markets](https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf)
  - vn.py GitHub：vn.py 提供 CTA/backtesting 基础设施，但没有可直接套用的 Stage819 候选分钟级结构破坏规则。[vn.py GitHub](https://github.com/vnpy/vnpy)
- 我的判断：Stage841 已证明固定时间 fail-fast 会误杀可恢复右尾，所以 Stage842 不再扫描 `120m/0.5R`。本阶段只检查能逐分钟实时观察的结构：OR15 反向破坏、重新站回入场、连续止损侧收盘。结论必须按“结构线索”理解，不能按“已找到策略”理解。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage842_stage841_structural_break_taxonomy.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定 taxonomy `S1_or15_adverse_touch_before_reclaim_or_dir`
  - 固定 taxonomy `S2_or15_adverse_close_before_reclaim`
  - 固定 taxonomy `S3_two_stop_side_closes_before_reclaim`
  - 固定 taxonomy `S4_no_prior_dir_or15_then_adverse_touch`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage825 Stage819 候选全周期 closed lots，`2018-01-01` 至 `2026-05-29`；叠加 Stage841 C7 fail-fast 事件法证。
- 账户规模：上游 Stage819/Stage825 口径 `300,000`。
- 成本口径：本阶段不新增成交，不计新增滑点；所有 delta 是只读 gross overlay 估算。
- 样本过滤：Stage825 全量 `341` 笔 closed lots；其中入场日分钟K覆盖 `227` 笔。Stage841 事件与 Stage825 baseline lot 可匹配 `24/25`，`event_id=9 AP110.CZCE short` 无同入口 baseline lot。
- 策略/归因口径：先定位入场日首次 `0.5R` 逆向触发，再判断触发后是否重新站回入场、是否重新突破信号方向 OR15、是否反向破坏 OR15、是否连续两根1分钟K收在止损侧；只读估算触发价退出对 baseline PnL 的 gross delta。

## 结果

- 期末权益：不适用，本阶段不跑新组合权益。
- 总收益：不适用，本阶段不跑新组合权益。
- 最大回撤：不适用，本阶段不跑新组合权益。
- Sharpe：不适用，本阶段不跑新组合权益。
- 总滑点：不适用，本阶段不生成新成交。
- 总交易次数：不适用，本阶段不生成新成交。
- 胜率：不适用，本阶段不生成新成交。
- 其他关键指标：
  - Stage825 全量 baseline PnL `+28,171,880`；入场日分钟K覆盖 `227/341`。
  - `0.5R` 逆向触发 `101` 笔；触发后仍有恢复形态 `62` 笔。
  - `no_same_day_recovery` `39` 笔，总 PnL `-12,251,975`，胜率 `7.6923%`，中位 R `-1.5874`。
  - 最佳只读形状 S3 `two_stop_side_closes_before_reclaim` 触发 `88` 笔，触发 baseline PnL `-13,930,500`，估算退出 PnL `-9,826,825`，gross delta `+4,103,675`。
  - S3 修亏损：亏损触发 `69` 笔，delta `+9,865,085`。
  - S3 误伤赢家：赢家触发 `18` 笔，delta `-5,726,410`。
  - S3 在 Stage841 可匹配事件中触发 `19` 笔，其中 `killed_c4_winner` `6` 笔、`saved_c4_loser` `8` 笔，Stage841 子集 delta `-3,643,210`。
  - S1 gross delta `+3,291,590`，但 Stage841 子集 delta `-3,856,530`。
  - S2 gross delta `+2,201,640`，但 Stage841 子集 delta `-4,217,330`。
  - S4 gross delta `-966,330`，直接否决。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage842_stage841_structural_break_taxonomy_report_stage842_stage841_structural_break_taxonomy_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage842_stage841_structural_break_taxonomy_summary_stage842_stage841_structural_break_taxonomy_v1.csv`
- orders：不适用；本阶段不生成新成交。
- daily：不适用；本阶段不生成新权益曲线。
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage842_stage841_structural_break_taxonomy_lot_taxonomy_stage842_stage841_structural_break_taxonomy_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage842_stage841_structural_break_taxonomy_rule_stats_stage842_stage841_structural_break_taxonomy_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage842_stage841_structural_break_taxonomy_bucket_stats_stage842_stage841_structural_break_taxonomy_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage842_stage841_structural_break_taxonomy_atlas_manifest_stage842_stage841_structural_break_taxonomy_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage842_stage841_structural_break_taxonomy_atlas_page001_stage842_stage841_structural_break_taxonomy_v1.png` 至 `page007`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage842_stage841_structural_break_taxonomy_decision_stage842_stage841_structural_break_taxonomy_v1.json`
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage842_stage841_structural_break_taxonomy.py` 已通过。
  - 已视觉检查 atlas page001、page004、page005：page001 的大亏损样本多为破止损侧后继续单边走弱，支持 S3 有结构含义；page004/page005 的误伤样本显示部分右尾会先连续收在止损侧后再恢复，证明 S3 仍会杀趋势右尾。

## 结论

- 本阶段结论：`stage842_s3_positive_gross_but_stage841_negative_not_promoted_engine_watch`。S3 比固定 `120m 0.5R fail-fast` 更贴近价格结构，全量只读 gross delta 为正；但它仍大量依赖砍亏损换收益，并且在 Stage841 事件子集为负，说明它没有真正解决“保留可恢复右尾”的核心问题。
- 是否进入下一步：不晋级、不进入官方候选、不触发 A/B。若继续，只能作为一次冻结真实引擎反证候选，而不是继续扫 taxonomy。
- 下一步：若继续 Stage019，只允许一个冻结版本 `C8 = C4 + S3_two_stop_side_closes_before_reclaim` 做真实组合引擎 A/C；不得同时扫连续根数、OR长度、止损R倍数、品种、方向或年份。若 C8 真实路径破坏 C4/Stage819 复利或 broker10，则停止结构破坏退出路线。

## 过拟合反思

- 运行前判断：否。四个 taxonomy 在运行前固定，来自 Stage017 的结构问题，不是按年份、品种、方向、R倍数救参。
- 运行后判断：暂时否，但风险上升。S3 全量正 delta 很容易诱导继续扫 `2/3/4` 根、`OR10/OR20` 或止损倍数；这样会变成过拟合。
- 原因：本阶段只证明一个粗形状“可能有价值且必须被真实引擎反证”，没有证明可以实盘。赢家误伤 `-5,726,410` 和 Stage841 子集 `-3,643,210` 是明确警告。

## 继续价值反思

- 运行前判断：有价值。Stage841 只解释 C7 失败，需要知道是否存在比固定时间窗更结构化的实时退出形状。
- 运行后判断：有价值但必须收窄。继续 taxonomy 扫描价值低；一个冻结真实引擎 C8 有价值，因为只有真实资金联动能检验 `+4,103,675` gross delta 是否会被复利路径、保证金和误伤右尾抵消。
- 原因：`no_same_day_recovery` 桶 `39` 笔总 PnL `-12,251,975`，说明左尾确实存在结构破坏；但 S3 在 Stage841 子集仍为负，说明不能只看全量 gross。

## 合入建议

- 是否更新本线 `LINE.md`：是，补充 Stage018 结论和 Stage019 约束。
- 是否更新 `research/registry.md`：否，非正式候选、非重要突破、非跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，仅本线内部只读归因。
