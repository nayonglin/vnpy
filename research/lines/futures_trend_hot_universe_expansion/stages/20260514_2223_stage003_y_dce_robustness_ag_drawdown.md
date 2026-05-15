# Stage003 y.DCE鲁棒性反证与ag.SHFE回撤来源拆解

- line_id：`futures_trend_hot_universe_expansion`
- 当前模式：day
- 记录时间：2026-05-14 22:23 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C鲁棒性反证 + 回撤归因
- 是否重要突破：是
- 是否触发A/B：是，按 `version-ab-experiment` 走 A/C；A=`official_stage78_1_static18_plus_fu`，C=`A + y.DCE`

## 外部调研与判断

- 参考资料：
  - vn.py/VeighNa：`https://github.com/vnpy/vnpy`
  - vn.py CTA Strategy：`https://github.com/vnpy/vnpy_ctastrategy`
  - vnpy_tqsdk：`https://pypi.org/project/vnpy_tqsdk/`
  - 趋势跟踪长期研究参考：`https://arxiv.org/abs/1404.3274`
- 我的判断：趋势扩池不能按“热门/全样本收益”决策，必须看多起点、冷启动、成本压力和弱窗口。趋势跟踪长期有效性的核心来自跨资产分散与风险纪律，而不是为单一历史阶段补一个品种。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage268_y_dce_robustness_ag_drawdown.py`
- 修改脚本：同上，补充静默回测日志与逐窗口缓存，避免长跑中断后丢结果。
- 删除脚本：无。
- 新增参数：
  - 候选品种：`y.DCE`
  - 回撤拆解品种：`ag.SHFE`
  - 起始年份：2020、2021、2022、2023、2024、2025、2026
  - 季度路径重置：2020Q1-2026Q2共26个季度
  - 最差季度真实重跑：4个
  - 滑点压力：1x、3x、5x
  - 滚动弱窗口：63/126/252交易日
- 修改参数：无正式Stage78-1执行参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30。
- 账户规模：50万。
- 成本口径：沿用Stage78-1滑点成本，另做1x/3x/5x滑点压力。
- 样本过滤：A=`static18 + fu.SHFE`；C=`static18 + fu.SHFE + y.DCE`。
- 策略/归因口径：固定第78-1逻辑，不为 `y.DCE` 或 `ag.SHFE` 单独调参。

## 结果

- Stage267全周期 `A static18+fu`：期末权益 `26,353,935`，总收益 `5170.7870%`，最大回撤 `-40.1659%`，Sharpe `1.1374`，总滑点 `2,057,380`，总交易次数 `883`，胜率 `43.3628%`。
- Stage267全周期 `C_y = A + y.DCE`：期末权益 `29,058,645`，总收益 `5711.7290%`，最大回撤 `-39.7260%`，Sharpe `1.1798`，总滑点 `2,218,170`，总交易次数 `933`，胜率 `43.6059%`。
- 起始年份反证：
  - C_y期末权益优于A：6/7。
  - C_y Sharpe优于A：5/7。
  - C_y回撤差异不差于-2pct：6/7。
  - 失败点：2026起点期末权益少 `3,130`，回撤差 `-2.0135pct`，Sharpe差 `-0.0262`；2025起点Sharpe也小幅低于A。
- 季度路径重置：
  - C_y期末权益优于A：25/26。
  - C_y回撤差异不差于-5pct：21/26。
  - 主要失败点：2025Q4 路径重置收益差 `-177.597pct`、回撤差 `-18.8832pct`、Sharpe差 `-2.8519`；2025Q1回撤差 `-102.5419pct`。
- 最差季度真实重跑：
  - 2025Q4：C_y期末权益 `952,905` vs A `944,275`，收益略好，但回撤更差 `-0.8579pct`。
  - 2025Q1：C_y期末权益 `2,781,450` vs A `2,548,825`，收益更好，但回撤更差 `-0.5937pct`、Sharpe略差。
  - 2026Q2：C_y期末权益 `464,000` vs A `459,500`，收益略好，回撤略好。
  - 2026Q1：C_y期末权益 `566,050` vs A `569,180`，收益/回撤/Sharpe均略差。
- 弱窗口：
  - 2020-2021：与A完全一致，说明 `y.DCE` 当时没有实际贡献。
  - 2022-02-07至2026-04-30：C_y收益差 `+380.699pct`，回撤改善 `+2.4991pct`，Sharpe差 `+0.0960`。
  - 2024-2025：C_y收益差 `+96.361pct`，回撤改善 `+5.6462pct`，Sharpe差 `+0.1660`。
  - 2026：C_y收益差 `-0.626pct`，回撤差 `-2.0135pct`，Sharpe差 `-0.0262`。
- 滑点压力：
  - 全周期5x滑点：C_y期末权益 `20,185,965` vs A `18,124,415`，收益差 `+412.310pct`，回撤改善 `+10.7357pct`，Sharpe差 `+0.0405`。
  - 2026 5x滑点：C_y期末权益 `1,273,940` vs A `1,071,455`，收益差 `+40.497pct`，回撤改善 `+0.8543pct`，Sharpe差 `+0.3493`。
- 滚动弱窗口：
  - 63/126/252日滚动窗口共4158个，C_y净Pnl弱于A的窗口393个。
  - 最差63日窗口为2025-08-14至2025-11-18，C_y净Pnl相对A少 `2,328,350`。
  - 最差126日窗口同样从2025-08-14开始，C_y净Pnl相对A少 `2,220,555`。
- ag.SHFE回撤来源：
  - +ag组合最大回撤事件：2025-07-25至2025-08-27，峰值权益 `29,463,580`，谷底 `22,990,310`，回撤 `-6,473,270`，事件回撤 `-21.9704%`，2025-11-17恢复。
  - 同事件期 +ag组合净Pnl `-5,279,010`，A净Pnl `-5,057,120`，+ag相对A多亏 `221,890`。
  - ag.SHFE自身事件期亏损 `-300,210`，不是最大回撤主因；主要亏损来自 `si.GFEX -1,544,400`、`jm.DCE -1,485,000`、`lh.DCE -1,364,000`。
  - ag.SHFE全年贡献：2024年 `+2,083,005`，2025年 `+17,744,220`，但2022/2023小亏；收益集中在2025，风险上仍不能忽略。

历史旧第78参考字段：期末权益 `1,610,900`、总收益 `705.45%`、最大回撤 `-54.93%`、Sharpe `0.661`、总滑点 `100`、总交易次数 `1000`。本阶段为当前第78-1/50万口径，不是旧口径复跑。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage268_y_dce_robustness_ag_drawdown_report_stage268_y_dce_robustness_ag_drawdown_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage268_y_dce_robustness_ag_drawdown_summary_stage268_y_dce_robustness_ag_drawdown_v1.json`
- start-year：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage268_y_dce_robustness_ag_drawdown_y_start_year_stage268_y_dce_robustness_ag_drawdown_v1.csv`
- quarter path reset：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage268_y_dce_robustness_ag_drawdown_y_quarter_cold_start_stage268_y_dce_robustness_ag_drawdown_v1.csv`
- quarter true rerun：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage268_y_dce_robustness_ag_drawdown_y_quarter_true_rerun_stage268_y_dce_robustness_ag_drawdown_v1.csv`
- weak window：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage268_y_dce_robustness_ag_drawdown_y_weak_window_backtest_stage268_y_dce_robustness_ag_drawdown_v1.csv`
- rolling weak window：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage268_y_dce_robustness_ag_drawdown_y_weak_rolling_stage268_y_dce_robustness_ag_drawdown_v1.csv`
- slippage stress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage268_y_dce_robustness_ag_drawdown_y_slippage_stress_stage268_y_dce_robustness_ag_drawdown_v1.csv`
- ag attribution：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage268_y_dce_robustness_ag_drawdown_ag_drawdown_product_contrib_stage268_y_dce_robustness_ag_drawdown_v1.csv`

## 结论

- 本阶段结论：`y.DCE` 不能直接升级为正式Stage78-1池；它是强研究线索，但没有通过起始年份与季度冷启动闸门。`ag.SHFE` 的最大回撤不是由ag单独造成，但+ag确实在事件期比A多亏，且全周期回撤越过40%边界，仍不能直接加入正式池。
- 是否进入下一步：是，但方向收缩。
- 下一步：
  1. 不把 `y.DCE` 直接接入正式池。
  2. 若继续研究，只看2025-08至2025-11这段滚动弱窗口的风险暴露归因，不允许为 `y.DCE` 单独调参。
  3. `ag.SHFE` 不做promotion；如果研究，必须从组合拥挤/金属链共同回撤解释，而不是单独美化ag收益。

## 过拟合反思

- 运行前判断：不是直接过拟合，但存在品种选择后的验证风险。
- 运行后判断：没有新增策略过拟合；反而阻止了把 `y/ag` 按全样本收益直接升级。
- 原因：本轮没有改阈值、没有调参数、没有按结果修补规则，只做固定A/C的多起点、多窗口和成本反证。`y.DCE` 因近期窗口不过关被保留为研究线索，说明流程没有被全周期漂亮收益绑架。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有价值，但不该继续盲目扩池。
- 原因：本轮已经回答了最关键的问题：`y.DCE` 不是垃圾线索，但也不够稳；`ag.SHFE` 高收益背后主要是2025行情和组合共同回撤，不具备直接进入正式执行池的风险证据。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，最新关键阶段改为Stage003。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；暂不追加 `memory.md`，因为没有正式基准变更。
