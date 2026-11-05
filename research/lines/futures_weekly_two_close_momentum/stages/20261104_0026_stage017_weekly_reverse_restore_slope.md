# Stage017 同日反手恢复周均线斜率过滤

- 研究线 `futures_weekly_two_close_momentum`，上海时间见文件名。候选 P 在 O 的参数上将 `ma_slope_filter` 从 false 改为 true，复用已有开关，无源码改动。O 是直接对照，L 是有同样斜率但无同日反手的补充对照。
- 普通开仓、断档后的加仓、止损后的反手开仓均使用周 MA5、MA10、MA20 的相邻周差值。同向全负拦多，全正拦空。历史不足沿用已有放行口径。平仓按原周线止损。保留固定一手、连续两周同向收盘变化、两根同向实体、最多一次断档加仓和同日先平后反手。三版均关闭 MA40。
- 冻结 19 品种、30 万元、2015-01-05 至 2026-11-03。沿用冻结主力映射、实物日线、合约规格、日开盘成交代理、静态保证金、既有滑点和零手续费。
- 参考 [LEAN SimpleMovingAverage](https://github.com/QuantConnect/Lean/blob/master/Indicators/SimpleMovingAverage.cs) 的滚动算术平均。已有斜率为相邻完成周的均线差值，本轮固定比较其否决作用，无择参扫描。以沪铜 2022-07-29 验证平仓与反手过滤分别执行。

冻结指纹

```text
2552df3bf5740bed8b7423ad1671041f110f716c8466d78ce32f37c8f1844e0c  research/lines/futures_weekly_two_close_momentum/outputs/stage013_L_2015_20261103/SHA256SUMS
73544211109c6df0ab2d56e47fd579545e3fab1586c8c9ad1f6fa1ef18db66e8  research/lines/futures_weekly_two_close_momentum/outputs/stage013_L_2015_20261103/inputs.json
9807fff6eac0d0d0b185d54b0b79e099adffafeb0095f4a8694c74a194651144  research/lines/futures_weekly_two_close_momentum/outputs/stage016_O_2015_20261103/SHA256SUMS
1e56b2bc65ca25430264b01bf5767cc4158790a88a673b09feff5f8ca7010a1d  research/lines/futures_weekly_two_close_momentum/outputs/stage016_O_2015_20261103/inputs.json
4b9b2070be92d7b0ae5448c359a08d28c2234dc03fbcf3534e245b9c45935fb3  research/lines/futures_weekly_two_close_momentum/tools/run_weekly_portfolio.py
584f7835a13ef4af8f3681a25971ebad66cb6081fa8bbd3537d950606203cb28  research/lines/futures_weekly_two_close_momentum/tools/weekly_two_close_momentum.py
```
