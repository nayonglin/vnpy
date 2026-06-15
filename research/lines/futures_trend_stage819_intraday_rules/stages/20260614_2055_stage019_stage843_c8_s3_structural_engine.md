# Stage019 Stage843 C8 S3结构破坏真实引擎

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-14 20:55 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：冻结真实组合引擎 A/C；不改官方正式版、不改官方候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。C8 相对 C4 多赚但回撤、Sharpe、broker10 路径均恶化。
- 是否触发A/B：否。C8 未成为正式候选，不涉及第78/Stage372 正式基准接入。

## 外部调研与判断

- 参考资料：
  - CME futures order types：止损单是预定义风控工具，不能把止损触发直接当成 alpha 证明。[CME Futures Order Types](https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types)
  - CME position and risk management：仓位、保证金和可承受亏损必须与交易规则共同评估。[CME Position and Risk Management](https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management)
  - CFTC stop order study：止损触发受日内波动和市场微结构影响，不能只看单笔 gross 修复。[CFTC Stop Orders in Select Futures Markets](https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf)
  - vn.py GitHub：vn.py 提供基础设施，没有可直接复制的 Stage819 分钟级结构破坏规则。[vn.py GitHub](https://github.com/vnpy/vnpy)
- 我的判断：Stage842 的 S3 只读 gross `+4,103,675` 只能说明“有结构线索”，不能说明策略可用；必须通过真实资金联动、保证金和复利路径检验。C8 结果验证了这个判断：单笔 gross 改善会在组合路径里转化为更差 broker10 和更低 Sharpe。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage843_stage830_c4_s3_structural_break_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `enable_stage843_s3_structural_break_stop=True`
  - `stage843_structural_stop_r=0.5`
  - `stage843_required_stop_side_closes=2`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `2026-05-29`
- 账户规模：`300,000`
- 成本口径：沿用 Stage819/Stage830 回测成本、滑点和合约乘数口径。
- 样本过滤：全周期真实组合引擎；复用 Stage830 A/C4 基准产物，新增 C8 单臂真实回放。
- 策略/归因口径：
  - A：Stage827 baseline，即 Stage819 原始候选复现。
  - C2：`1R` 日内实时止损先于 `1R` 顺向确认则平仓。
  - C4：C2 + broker10 `100%` flat-entry 保证金入口闸门。
  - C8：C4 + S3。若 C2 未触发，入场日先触发 `0.5R` 逆向后，在重新站回入场价前连续两根1分钟K收在 `0.5R` 止损侧，则按第二根收盘价合成实时平仓；无重试。

## 结果

- 期末权益：C8 `33,052,106.4`；C4 `30,523,910.8`；A `26,322,730.0`
- 总收益：C8 `10917.3688%`；C4 `10074.6369%`；A `8674.2433%`
- 最大回撤：C8 `-51.4922%`；C4 `-50.7900%`；A `-54.7546%`
- Sharpe：C8 `1.3872`；C4 `1.4519`；A `1.4363`
- 总滑点：C8 `2,312,880`；C4 `2,079,430`；A `2,149,150`
- 总交易次数：C8 `686`；C4 `677`；A `666`
- 胜率：C8 `52.5699%`；C4 `53.6294%`；A `53.1069%`
- 其他关键指标：
  - C8 相对 C4：期末权益 `+2,528,195.6`，但最大回撤恶化 `-0.7023pp`，Sharpe 降 `-0.0647`，broker10 峰值恶化 `+20.2297pp`。
  - C8 max broker10 margin/equity `135.6309%`，C4 为 `115.4012%`，A 为 `90.6200%`。
  - C8 p95 broker10 margin/equity `62.1102%`，C4 为 `60.5631%`。
  - C8 structural stop events `43`，closed structural lots `43`。
  - C2 events `51`，cap events `25`，cap blocked `0`，cap reduced volume `511`。
  - C8 最大回撤峰值日 `2022-03-30`，谷值日 `2022-06-29`，谷值权益 `3,382,612.4`，弱于 C4 的 `3,827,167.8`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage843_stage830_c4_s3_structural_break_engine_report_stage843_stage830_c4_s3_structural_break_engine_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage843_stage830_c4_s3_structural_break_engine_summary_stage843_stage830_c4_s3_structural_break_engine_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage843_stage830_c4_s3_structural_break_engine_trades_stage843_stage830_c4_s3_structural_break_engine_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage843_stage830_c4_s3_structural_break_engine_curve_stage843_stage830_c4_s3_structural_break_engine_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage843_stage830_c4_s3_structural_break_engine_comparison_stage843_stage830_c4_s3_structural_break_engine_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage843_stage830_c4_s3_structural_break_engine_structural_stop_events_stage843_stage830_c4_s3_structural_break_engine_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage843_stage830_c4_s3_structural_break_engine_closed_lots_stage843_stage830_c4_s3_structural_break_engine_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage843_stage830_c4_s3_structural_break_engine_path_chart_stage843_stage830_c4_s3_structural_break_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage843_stage830_c4_s3_structural_break_engine_decision_stage843_stage830_c4_s3_structural_break_engine_v1.json`
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage843_stage830_c4_s3_structural_break_engine.py` 已通过。
  - 已视觉检查 path chart：C8 权益高于 C4，但 2022 回撤谷值更深，broker10 峰值明显高于 C4，图形与指标一致。

## 结论

- 本阶段结论：`stage843_c8_not_promoted_s3_structural_break_fullpath_failed`。C8 虽然提高期末权益，但没有同时改善 C4 的收益、回撤、Sharpe 与 broker10 路径；特别是 broker10 峰值升到 `135.6309%`，说明 S3 改变复利路径后释放/重排了更危险的后续持仓结构。
- 是否进入下一步：不进入年度起点压力、不进入成本压力、不进入官方候选、不触发 A/B。
- 下一步：停止 S3 结构破坏退出路线。若继续本研究线，应回到更本质的问题：日内退出后释放的保证金如何被组合再使用，或者改做入场侧质量控制，而不是继续扫连续K根数、OR长度、R倍数、品种、方向或年份。

## 过拟合反思

- 运行前判断：否。C8 完全冻结 Stage842 的 S3：`0.5R` 逆向 + 连续两根止损侧收盘 + 未重新站回入场；未扫参数。
- 运行后判断：否，但这条路线若继续救参会变成过拟合。
- 原因：真实引擎已给出明确反证：全量 gross 线索转为更差 Sharpe 和 broker10。继续调 `2/3/4` 根、`0.4R/0.6R`、OR长度或品种方向过滤，就是用结果救形状。

## 继续价值反思

- 运行前判断：有价值。Stage842 只读 gross 为正，需要真实资金联动检验。
- 运行后判断：S3 路线继续价值低；本研究线整体仍有价值。
- 原因：C8 多赚但更危险，说明“单笔左尾修复”不是最终目标，必须考虑止损释放资金后的组合再使用和 broker10 压力。下一条可做，但不应再沿 S3 阈值微调。

## 合入建议

- 是否更新本线 `LINE.md`：是，补充 Stage019 结论并停止 S3 结构破坏退出路线。
- 是否更新 `research/registry.md`：否，非正式候选、非重要突破、非跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，仅本线内部反证。
