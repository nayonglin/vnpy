# Stage141 - 执行时序 / T+1开盘缺口审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 03:30 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读执行风险审计；不新增交易规则，不调参数，不改变 Stage079/Stage103。
- 是否重要突破：是。重要性在于发现 Stage079/Stage103 对“同日收盘成交口径”存在显著执行时序敏感性，真实执行前必须单独审计。
- 是否触发A/B：否。本阶段不是新策略候选，只是 execution model stress audit。

## 外部调研与判断

- 参考资料：
  - Chevalier、Darolles，《Futures Market Liquidity and the Trading Cost of Trend Following Strategies》：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3523005
  - Bailey、Lopez de Prado，《The Deflated Sharpe Ratio》：https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
  - Bailey、Borwein、Lopez de Prado、Zhu，《The Probability of Backtest Overfitting》：https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
- 我的判断：趋势策略不能只审计信号和日线净值，还必须审计成交时序、开盘缺口和执行滑点。这个方向不是 alpha 优化，不应该按缺口日继续过滤日期/品种；它是决定 Stage103 能不能进入真实 paper/影子盘的执行前置。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage441_execution_timing_gap_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。新增审计口径为 `C3 T+1 next open`，不是策略参数。
- 修改参数：无。
- 删除参数：无。
- 修改正式策略：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`。
- 账户规模：`61.5万`，即 Stage079 `50万C3下单 + 11.5万外部现金`。
- 成本口径：沿用引擎默认正常成本；本阶段关注同日收盘成交 vs T+1 开盘成交。
- 样本过滤：无新增过滤。
- 策略/归因口径：
  - `stage079`：Stage079 同日收盘成交口径，用 Stage403 日度路径重建。
  - `stage079_c3_t1_next_open`：C3 主体用真实引擎按 T+1 开盘成交重跑，再加 `11.5万`现金。
  - `stage103_same_day_close`：Stage103 同日收盘成交口径。
  - `stage103_c3_t1_next_open_satellite_frozen`：C3 主体用 T+1 开盘成交，Stage103 的 xsmom 腿保持 Stage403 冻结日度路径，用于隔离 C3 执行时序风险。

## 结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | rolling252破30 | rolling504破30 | 年度/季度DD30通过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 同日 | 31,040,650 | 4947.2602% | -29.7007% | 1.6226 | 15.1468 | 0.0000 | 0.0000 | 100% / 100% |
| Stage079 C3 T+1 open | 32,778,250 | 5229.7967% | -52.7518% | 1.4928 | 19.2452 | 39.5785% | 59.6696% | 60.0000% / 52.3810% |
| Stage103 同日 | 31,730,915 | 5059.4984% | -28.9792% | 1.6835 | 14.3669 | 0.0000 | 0.0000 | 100% / 100% |
| Stage103 C3 T+1 open + frozen xsmom | 33,468,515 | 5342.0350% | -49.6765% | 1.5455 | 18.2071 | 47.9313% | 59.6696% | 60.0000% / 52.3810% |

注意：本阶段 Sharpe 使用 Stage087/当前短持有评估器的交易日序列口径，和早前 vn.py summary 口径数值不完全一致；本阶段只做同表内相对比较。

3个月/6个月体验关键变化：

| 版本 | 3个月分 | 6个月分 | 3个月p05 | 6个月p05 | 3个月DD30 | 6个月DD30 | 3个月Ulcer P95 | 6个月Ulcer P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 同日 | 100.0000 | 100.0000 | -11.4450% | -2.9854% | 0.0000 | 0.0000 | 17.5634 | 19.9628 |
| Stage103 同日 | 121.0947 | 124.5738 | -10.8615% | -2.0909% | 0.0000 | 0.0000 | 16.3254 | 19.2374 |
| Stage103 C3 T+1 open + frozen xsmom | 58.9674 | -28.5166 | -14.7426% | -7.5974% | 13.2671% | 28.5535% | 22.2699 | 26.7806 |

最差 T+1 相对同日成交日：

- `2025-04-07`：C3 同日 `+726,560`，T+1 open `-246,630`，单日差 `-973,190`。
- `2022-07-18`：C3 同日 `-932,620`，T+1 open `-1,535,350`，单日差 `-602,730`。
- `2025-12-29`：C3 同日 `-2,193,350`，T+1 open `-2,768,900`，单日差 `-575,550`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage441_execution_timing_gap_audit_report_stage441_execution_timing_gap_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage441_execution_timing_gap_audit_summary_stage441_execution_timing_gap_audit_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage441_execution_timing_gap_audit_horizon_stage441_execution_timing_gap_audit_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage441_execution_timing_gap_audit_score_stage441_execution_timing_gap_audit_v1.csv`
- delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage441_execution_timing_gap_audit_daily_delta_stage441_execution_timing_gap_audit_v1.csv`
- C3 T+1 daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage441_execution_timing_gap_audit_c3_t1_daily_stage441_execution_timing_gap_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage441_execution_timing_gap_audit_decision_stage441_execution_timing_gap_audit_v1.json`

## 结论

- 本阶段结论：Stage103 在同日收盘成交口径下仍是当前主候选，但在 `C3 T+1 next open` 执行时序压力下不再通过硬约束。这个结果不是“Stage103 alpha 失败”，而是“当前候选进入真实 paper/影子盘前，必须先把执行时序模型定清楚”。
- 是否进入下一步：是，但下一步优先级应切到执行模型审计。
- 下一步：
  - 不继续救 Stage115/136/OI/value 等旧路线小参数。
  - 优先做 Stage142：拆解 T+1 open 失败来源，是交易日开盘缺口、换月/连续合约拼接、还是 NextOpenDelayedExecutionEngine 与真实夜盘执行时段不一致。
  - 若真实执行计划是夜盘集合竞价/开盘后委托，而不是日线下一交易日白盘 open，则需要构造更贴近实盘的成交代理价，不能直接用日线 T+1 open 宣判。

## 过拟合反思

- 运行前判断：不是过拟合。执行时序审计不改变信号，不筛日期/品种。
- 运行后判断：不是过拟合。发现失败后没有按缺口日继续调过滤条件。
- 原因：本阶段只比较两个预声明成交模型；没有根据结果优化任何交易参数。

## 继续价值反思

- 运行前判断：继续有价值，因为 Stage103 要进入工程/影子盘必须先过执行模型。
- 运行后判断：继续有价值且优先级上升。
- 原因：如果同日收盘和 T+1 open 之间存在 20pp 以上最大回撤差异，继续优化 3/6个月指标可能是在错误成交假设上变精细，必须先定位执行差异来源。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage141 执行时序约束。
- 是否更新 `research/registry.md`：是，提示 Stage103 进入真实执行前需先完成执行模型审计。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；暂不追加 `memory.md`。
