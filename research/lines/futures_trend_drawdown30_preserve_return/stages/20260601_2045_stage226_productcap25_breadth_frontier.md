# Stage226 cap25 + 活跃产品广度前沿

- 时间：2026-06-01 20:45 CST
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage526_productcap25_breadth_frontier.py`
- 性质：A/C 粗前沿；不改 alpha，不改入场/出场，不做日期或品种补丁。
- 决策：`productcap25_breadth_candidate_found`

## 开始前反思

- 是否过拟合：否。只测试已有粗档 `product cap25` 与整数 `max_concurrent_positions=5/4`，没有扫 `26/27/28/29`。
- 是否值得继续：是。Stage224 `pc30_maxpos4` 只剩 1 天超限，cap25 是结构性降低单产品尖峰的最小粗档。

## 结果

| 版本 | 总收益 | 收益保留vsStage079 | 最大回撤 | Sharpe | broker10最大 | 穿100 | 2x成本DD | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `r080_pc30_maxpos4_ref` | 4761.7772% | 96.2508% | -36.0184% | 1.7207 | 112.7086% | 1 | -38.0134% | 近通过但失败 |
| `r080_pc25_control` | 3729.0374% | 75.3758% | -35.4970% | 1.5768 | 116.2599% | 5 | -38.2630% | 保证金失败 |
| `r080_pc25_maxpos5` | 3517.8724% | 71.1075% | -35.8624% | 1.6020 | 109.3203% | 2 | -38.6275% | 保证金失败 |
| `r080_pc25_maxpos4` | 3699.9195% | 74.7872% | -36.2670% | 1.6385 | 99.7299% | 0 | -39.0565% | 硬通过 |

图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage526_productcap25_breadth_frontier_chart_stage526_productcap25_breadth_frontier_v1.png`

视觉判断：`r080_pc25_maxpos4` 是唯一落在 broker100 下方且收益保留超过65%的点；权益线虽低于 `pc30_maxpos4_ref`，但明显高于旧 usage75 壳。

## 标准字段

主候选 `r080_pc25_maxpos4`：

- 期末权益：`23,369,505`
- 总收益：`3699.9195%`
- 最大回撤：`-36.2670%`
- Sharpe：`1.6385`
- 总滑点：`1,342,190`
- 总交易次数：`905`
- 胜率：`53.6330%`
- 新增参数：`risk_multiplier=0.80`、`product cap=25%`、`max_concurrent_positions=4`
- 修改/删除参数：无正式参数变更。

## 结束反思

- 是否过拟合：目前否。候选来自两个粗结构约束的交集，非日期/品种补丁。
- 是否值得继续：是。它是 Stage214 以来第一个无现金、broker100通过、2x成本DD40通过且收益保留接近75%的真实可成交壳，必须进入鲁棒性和反过拟合审计。

