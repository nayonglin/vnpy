# Stage044 · 含黄金 S19 日 K 固定一手逐半年回测

2026-11-04 19:42 上海时间。沿用 Stage043 的日 K 信号与含黄金 S19 的 19 个品种。固定一手，15 万元本金。冻结 Stage041 的 24 个自然半年起点，从 2015 至 2026 年每年 1 月和 7 月的首个交易日空仓起跑，统一截至 2026-11-04。保留原成交顺序、日开盘代理、静态保证金、逐手滑点、零手续费。资金不足后仍按原研究口径记账。

仅扩充起跑日期。以 Stage041 的含黄金周 K 一手账本作同起点对照，按每个起点记录累计收益、最大回撤、成交、胜率和资金缺口。2026 年初作为复现检查，与 Stage043 账本核对。冻结样本 24 组，单列失败和未知。参考 LEAN 的预热设计，起点前仅用历史行情计算指标，各窗口独立建账。[LEAN 指标预热](https://www.quantconnect.com/docs/v2/writing-algorithms/historical-data/warm-up-periods) · [vn.py 组合回测](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)
