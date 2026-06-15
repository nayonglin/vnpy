# Stage022 Stage846 Stage825入场质量只读法证

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-14 21:29 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读法证；读取 Stage825 逐笔分钟特征，不重新回测，不修改正式版、不修改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。P2 显示“实时止损+重回入场价允许重试”是正线索，但还不是策略版本。
- 是否触发A/B：否。本阶段没有产生可接入正式版或候选版的新策略实现。

## 外部调研与判断

- 参考资料：
  - CME futures order types：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types
  - CME position and risk management：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management
  - CFTC stop-loss order education：https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf
  - vn.py GitHub：https://github.com/vnpy/vnpy
- 我的判断：
  - 公开资料只支持“预先定义止损、仓位和风险纪律”这个方向，不支持复制某个 ORB/确认参数。
  - 对趋势系统来说，分钟级规则的核心不是更早证明趋势成立，而是先防止错误入场继续亏损，同时保留可恢复右尾。
  - 因此 Stage846 只做固定低自由度 taxonomy 和 gross proxy；任何真实晋级都必须走逐分钟引擎，检验成交、重试、资金复用和保证金路径。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage846_stage825_entry_quality_forensics.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-05-29`。
- 账户规模：沿用 Stage819 候选 `300,000` 口径；本阶段不重新计算组合成交。
- 成本口径：沿用 Stage825 输出；本阶段 proxy 不是组合回测，未新增滑点、手续费或资金复用。
- 样本过滤：Stage825 closed lots `341` 笔；入场日分钟K覆盖 `227` 笔，缺分钟 `114` 笔。缺分钟样本在 proxy 中保持原值，不做分钟规则断言。
- 策略/归因口径：
  - 入场质量 taxonomy：`target_first_05r`、`stop_first_recovered`、`stop_first_unrecovered_close_bad`、`neither_close_good/bad`、`missing_minutes`。
  - P1：`0.5R` 先止损且当天不重试，按 `-0.5R` 退出。
  - P2：`0.5R` 先实时止损；若当天重新穿越原入场价，假定允许一次重试并沿用原后续结果。
  - P3：OR15 未按信号方向突破则拒单的简单 gross proxy。
  - P4：60分钟内未达到 `1R` 顺向确认则拒单的右尾伤害测试。
  - P5：事后剔除 `0.5R` 先止损且当天未重回入场价的上限诊断，不是实时规则。

## 结果

- 期末权益：`26,322,730`
- 总收益：`8674.2433%`
- 最大回撤：`-54.7546%`
- Sharpe：`1.4363`
- 总滑点：`2,149,150`
- 总交易次数：`666`
- 胜率：`53.1069%`
- 其他关键指标：
  - 决策标签：`stage846_stop_retry_proxy_positive_but_needs_real_engine`。
  - `target_first_05r`：`125` 笔，总 PnL `+37,712,095`，`18` 个 big winners，big winner PnL `+26,596,810`；这是右尾核心，不能被确认过滤误伤。
  - `stop_first_unrecovered_close_bad`：`44` 笔，总 PnL `-12,322,385`，胜率 `11.36%`，median `R=-1.2554`，图谱显示多为入场后快速反向且全天无收复。
  - `stop_first_recovered`：`32` 笔，总 PnL `+1,100,820`，但 median `R=-0.7778`，说明“先错后恢复”有右尾也有噪音，不能 no-retry 一刀切。
  - P1 no-retry：受影响 `75` 笔，gross delta `+4,645,902.1`，但赢家损伤 `-6,926,278.4`，big winner 损伤 `-1,076,960`。
  - P2 stop+retry：受影响 `75` 笔，gross delta `+5,749,762.1`，亏损修复 `+7,780,490.5`，赢家损伤降到 `-1,998,228.4`，big winner 损伤 `-383,080`。
  - P3 OR15 简单拒单：受影响 `39` 笔，gross delta `+6,511,760`，但误伤赢家 `-2,129,050`、big winner `-878,590`；且 Stage834 的 OR15 close/hold 交易语义版本已经反证，不能直接晋级。
  - P4 60m 1R确认：受影响 `171` 笔，gross delta `-8,977,625`，赢家损伤 `-32,625,885`，big winner 损伤 `-15,693,510`，明确反证“必须快速确认才持有”的硬过滤。
  - P5 hindsight 上限：gross delta `+12,322,385`，但需要事后知道全天未收复，只能说明可分离空间，不是规则。
  - K线视觉：page001 的 `stop_first_unrecovered_close_bad` 样本多为入场后很快跌破/反向后全天不能收复；page004 的 `target_first_big_winner` 样本则常见初期横盘后再拉开，解释了硬性 60m 确认为何会杀右尾。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage846_stage825_entry_quality_forensics_report_stage846_stage825_entry_quality_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage846_stage825_entry_quality_forensics_taxonomy_summary_stage846_stage825_entry_quality_forensics_v1.csv`
- orders：无，本阶段未生成订单。
- daily：无新增日度回测；使用 Stage825 full-period reference。
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage846_stage825_entry_quality_forensics_decision_stage846_stage825_entry_quality_forensics_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage846_stage825_entry_quality_forensics_quality_lots_stage846_stage825_entry_quality_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage846_stage825_entry_quality_forensics_proxy_lot_deltas_stage846_stage825_entry_quality_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage846_stage825_entry_quality_forensics_proxy_summary_stage846_stage825_entry_quality_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage846_stage825_entry_quality_forensics_proxy_yearly_stage846_stage825_entry_quality_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage846_stage825_entry_quality_forensics_entry_quality_chart_stage846_stage825_entry_quality_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage846_stage825_entry_quality_forensics_entry_quality_atlas_page001_stage846_stage825_entry_quality_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage846_stage825_entry_quality_forensics_entry_quality_atlas_page004_stage846_stage825_entry_quality_forensics_v1.png`

## 结论

- 本阶段结论：
  - “0.5R 实时止损后允许重回入场价重试”是当前最像人类交易直觉的正线索：它比 no-retry 更少伤害可恢复右尾，同时保留左尾修复。
  - 但 P2 仍是 lot-level gross proxy，不是完整组合引擎；它没有处理重试成交价、重试次数、释放资金后的后续新仓、broker10 路径和滑点变化。
  - `60m 1R` 快速确认硬过滤被反证；它杀掉太多慢启动大赢家，不符合趋势系统“让右尾长出来”的本质。
  - OR15 简单拒单代理为正，但与 Stage834 的交易语义验证冲突，只能保留为辅助观察，不能继续扫 OR 长度或 hold bars。
- 是否进入下一步：进入下一步，但只能做一个冻结真实引擎。
- 下一步：
  - 做 Stage847：冻结 `C9 = C4 + 0.5R 实时止损 + 原入场价重回后允许一次重试` 的分钟级真实组合引擎。
  - 不扫 `0.4/0.6R`、不扫 `15/30/60/120m`、不扫重试次数；先验证 P2 的成交、滑点、资金复用和 broker10 路径是否仍成立。

## 过拟合反思

- 运行前判断：否。Stage846 只读取 Stage825 固定输出，使用预声明 taxonomy 和 proxy，不按年份、品种、方向调参。
- 运行后判断：否，但下一步有过拟合风险。
- 原因：本阶段没有把 P3/P5 这类看起来更漂亮的 hindsight/拒单结果直接包装成策略；真正可继续的是机制更朴素的 P2。若继续扫描 R倍数、OR长度或确认分钟，就是过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage021 已排除复用压力簇冷却，必须回到入场质量本体。
- 运行后判断：有价值，但范围要收窄。
- 原因：P2 的收益结构符合“实时止损但不永久放弃趋势”的默会经验：错了先退，市场重新证明原方向后再试一次。它值得一次冻结真实引擎；如果真实资金路径失败，就停止该路线。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新 Stage022 状态和下一步 Stage847。
- 是否更新 `research/registry.md`：否，本阶段没有新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段还不是正式候选、重要突破或路线迁移。
