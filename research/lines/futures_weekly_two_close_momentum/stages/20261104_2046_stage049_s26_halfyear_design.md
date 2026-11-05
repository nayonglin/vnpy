# Stage049 · S26 逐半年冷启动

2026-11-04 20:46（上海时间）。沿用 Stage048 的 S26 与 Stage037/038/041 的 S19，周 K、多空、固定一手、15 万元本金、原到期保护及滑点、零手续费。冻结 2015–2026 年每年 1 月 1 日和 7 月 1 日为 24 个日历起点，取该日之后的首个交易日空仓启动，统一至 2026-11-04。使用交易前可见的历史预热，保留日开盘代理。24 组 S26 重新跑，S19 复用已复核的 24 组独立账本。

Stage048 行情、引擎、品种清单和结果固定。每窗记录收益、最大回撤、Sharpe、完整交易、胜率、滑点、开盘前与逐笔成交后及收盘保证金缺口、非正权益日。缺口继续按理论成交记账。核对相同起点原 19 品种成交及新增品种的净损益。最后由独立状态机和账本复核全部窗口。参考 LEAN 预热及 vn.py 逐日盯市做法。[LEAN 指标预热](https://www.quantconnect.com/docs/v2/writing-algorithms/historical-data/warm-up-periods) · [vn.py 组合回测代码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)

2022 年选池偏差仍在。比较有助于观察起点和初始保证金压力。各窗口终点相同，样本彼此重叠，不将胜出比例解释为独立样本胜率。
