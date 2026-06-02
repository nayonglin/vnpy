# Stage225 maxpos4现金边界审计

- 时间：2026-06-01 20:41 CST
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage525_maxpos4_cash_boundary.py`
- 性质：部署资金边界转换；不改策略、不改信号、不新增交易规则。
- 决策：`cash_boundary_only_middle_candidate`

## 开始前反思

- 是否过拟合：否。只把 Stage224 固定路径转换成不同外部现金口径。
- 是否值得继续：是。`r080_pc30_maxpos4` 只剩 1 天 broker100 超限，需要判断外部现金是否比旧硬通过壳更有资本效率。

## 结果

`r080_pc30_maxpos4`：

- 无现金：`4761.7772%/-36.0184%/Sharpe1.7207`，broker10最大 `112.7086%`，穿100 `1` 天。
- 压到 broker100 需要现金：`487,250.32`
- 对应初始资金：`1,102,250.32`
- 部署收益：`2656.8312%`
- 最大回撤：`-33.2242%`
- 2x成本最大回撤：`-34.9892%`

对比：

- `r080_pc25_u75` 无现金收益：`2734.1000%`
- `r070_pc30_u75` 无现金收益：`2581.3488%`

结论：`r080_pc30_maxpos4 + 48.7万现金` 只高于稳健壳 `r070_pc30_u75`，但低于收益优先硬壳 `r080_pc25_u75`，所以不是资本效率主候选。

图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage525_maxpos4_cash_boundary_chart_stage525_maxpos4_cash_boundary_v1.png`

视觉判断：现金一加，收益率斜率快速下滑；压到 broker100 后收益线落在两条旧硬壳之间，说明它只能做资金更宽账户的中间 paper，不是主线答案。

## 标准字段

- 新增参数：现金层级 `0 / required broker100 / round10k / required broker95 / required broker90`。
- 修改/删除参数：无。
- 总滑点/交易/胜率：`r080_pc30_maxpos4` 固定为 `1,647,100 / 909 / 53.9444%`。

## 结束反思

- 是否过拟合：否。
- 是否值得继续：是，但不继续 cash boundary；应测试 `cap25 + maxpos4` 是否能无现金解决最后尖峰。

