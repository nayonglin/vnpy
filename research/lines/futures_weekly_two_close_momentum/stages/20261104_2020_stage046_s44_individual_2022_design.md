# Stage046 · S44 原版周 K 一手逐品种 2022 回测

2026-11-04 20:20 上海时间。使用 Stage024 已验收的固定 44 品种行情与原 S 周 K 一手规则，采用 Stage025 五交易日到期保护。每次引擎只载入一个交易品种，分别以 150,000 元空仓开始。交易窗口为 2022-01-04 至 2022-12-30，历史数据仅供信号预热，年末持仓按收盘估值。沿用日开盘代理、原逐手滑点、零手续费和静态保证金。盈利以期末权益减本金计算，包括已实现和未实现损益。

固定尝试 44 个品种。2022 年未上市者单列。已上市但无成交者单列。保留每个品种的账本与数据缺项，汇总盈利排名。独立核对入场和资金账。与已有 19 品种组合账本的单品种成交交叉检查，用于核对同规则身份。固定 44 池为后来冻结的研究池，结论仅描述 2022 年。[LEAN 指标预热](https://www.quantconnect.com/docs/v2/writing-algorithms/historical-data/warm-up-periods) · [vn.py 组合回测](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)
