# Stage042 · 含黄金 S19 固定两手半年起点回放

2026-11-04 19:25 上海时间。使用 Stage041 含黄金 S19 全池，唯一交易规则改动为每个品种由固定开一手改为固定开两手。原规则触发平仓时平掉两手，换月承接两手，同日反手按两手开仓。本金 150,000 元，2015 至 2026 年每年 1 月和 7 月共 24 个独立空仓起点，统一截至 2026-11-04。复用 Stage041 验收对照、物理合约、交易日历、静态保证金、日开盘代理和逐手滑点，手续费 0 元。

在隔离入口执行已钉住源码的两手研究变体，逐笔对照原版。以每日权益重算回撤，并逐日记录开盘前、成交后及收盘的资金缺口和非正权益。资金不足后仍按信号记账。参考 vn.py 的组合成交核算和 CME 对保证金及权益变动的说明。结果用于离线手数归因。[vn.py](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py) · [CME 保证金说明](https://www.cmegroup.com/solutions/risk-management/performance-bonds-margins/faq-performance-bonds-margins.html)
