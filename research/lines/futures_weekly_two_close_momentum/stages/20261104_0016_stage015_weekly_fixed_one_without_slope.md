# Stage015 固定一手关闭周均线斜率过滤

- 研究线 `futures_weekly_two_close_momentum`
- 冻结时间见文件名（上海时间），工作区 `weekly19-stop-reversal.local`
- 阶段性质为单项消融。L 为冻结对照，N 关闭底仓及加仓的周 MA5、MA10、MA20 同向斜率否决。两组均不启用 MA40。
- 保留同合约连续三周收盘单调与最近两根周 K 线实体方向、固定一手、断档后重出两周信号且最多加一手、周线止损及换月。使用已有开关 `--no-ma-slope-filter`，无新增代码或参数。
- 冻结区间 2015-01-05 至 2026-11-03，19 品种，起始 30 万元。沿用 L 的行情、主力映射、合约规格、成交日开盘代理、滑点账面口径和零手续费。
- 参考 [LEAN SimpleMovingAverage](https://github.com/QuantConnect/Lean/blob/master/Indicators/SimpleMovingAverage.cs) 的滚动窗口计算。均线值相邻周变化滞后于短期反弹。本次以有无固定过滤做同样本检验，沪铜案例仅用于核实执行。
- 运行前判断，无周期扫描或重新择参，有价值量化过滤对资金路径和尾部风险的影响。样本内结果保留为研究证据。

## 冻结校验

```text
2552df3bf5740bed8b7423ad1671041f110f716c8466d78ce32f37c8f1844e0c  research/lines/futures_weekly_two_close_momentum/outputs/stage013_L_2015_20261103/SHA256SUMS
73544211109c6df0ab2d56e47fd579545e3fab1586c8c9ad1f6fa1ef18db66e8  research/lines/futures_weekly_two_close_momentum/outputs/stage013_L_2015_20261103/inputs.json
6a064a252b98a43e1eef68ba0bc461e0c637441f8309d160aef96f7a2d5d4797  research/lines/futures_weekly_two_close_momentum/tools/run_weekly_portfolio.py
584f7835a13ef4af8f3681a25971ebad66cb6081fa8bbd3537d950606203cb28  research/lines/futures_weekly_two_close_momentum/tools/weekly_two_close_momentum.py
Python 3.11.5
../.py311/bin/python tools/run_weekly_portfolio.py outputs/stage015_N_2015_20261103 --week-body-filter --one-fixed-add --fresh-add-sequence --no-ma-slope-filter （路径以研究线为基准）
```
