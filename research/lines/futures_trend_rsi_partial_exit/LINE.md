# futures_trend_rsi_partial_exit

- 中文名：期货趋势 RSI 分批止盈研究线
- 资产/策略：商品期货趋势 / `78-1` (`official_stage78_1_defensive_50w_no_sizing_cap`)
- 研究定位：独立研究线，不修改 `78-1` 默认逻辑；仅通过 A/B 对照评估“RSI 极端过热时分批减仓”是否具备跨周期收益-风险优势
- 当前状态：Stage001 启动（A vs C 单变量消融）

## 问题与假设

- 问题：趋势策略的大部分收益来自少数大赢家；“过热分批止盈”可能减少回撤/回吐，但也可能截断右尾（降低穿越周期能力）。
- 假设：`RSI >= 95` 属于极端过热信号，触发频次较低；如果在极端过热处减半仓，可能降低回撤或滑点敏感性，但可能牺牲长趋势的最大收益。

## 实验边界（反过拟合）

- 只做一个候选版本：打开 `enable_rsi_partial_exit`，并固定阈值 `rsi_partial_exit_threshold=95`、比例 `rsi_partial_exit_ratio=0.5`。
- 不做阈值/比例网格搜索；若首轮结果不稳健，直接停止（避免“调参救版本”）。
- 评价以多周期、起始年鲁棒性、弱周期存活与成本压力为主；不以单段收益提升作为升级依据。

## A/B/C 设计

说明：`run_backtest()` 的默认 setting 中存在 `enable_rsi_partial_exit=True` 的默认值，因此本研究线会用“显式开/关”来做消融，避免被隐式默认值污染口径。

- A：`78-1 + RSI 分批止盈显式关闭`（`enable_rsi_partial_exit=False`）
- C：`78-1 + RSI 分批止盈显式开启`（`enable_rsi_partial_exit=True`，阈值`95`，比例`0.5`）
- B：不设（该模块脱离 `78-1` 信号逻辑没有独立评估意义）

## 产物约定

- 代码入口：`examples/portfolio_backtesting/run_qmt_roll_stage247_stage78_1_rsi_partial_exit_ablation_suite.py`（计划新增）
- 记录目录：`research/lines/futures_trend_rsi_partial_exit/stages/`
