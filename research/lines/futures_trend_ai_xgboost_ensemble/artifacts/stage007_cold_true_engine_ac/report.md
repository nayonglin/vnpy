# Stage007 冷进程全周期真引擎A/A/C

- 决策：`FAIL`
- A1/A2逐日逐笔确定性：`PASS`
- A1、A2、C均为独立python -B冷进程；checkpoint复用为false。
- 49个月候选仍是开发样本，不是独立最终OOS。

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 交易次数 | 胜率 | broker10峰值 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A正式逻辑回归池 | 21,678,173.80 | 14352.1159% | -39.9147% | 1.585266 | 2,166,380 | 798 | 53.4954% | 93.5807% |
| C Stage006 XGBoost池 | 4,339,223.40 | 2792.8156% | -54.9828% | 1.204597 | 968,170 | 779 | 51.3629% | 93.5807% |

## 预声明全周期门

- `PASS` `input_identity_pass`
- `PASS` `baseline_reproduction_pass`
- `PASS` `coverage_pass`
- `FAIL` `total_return_strictly_higher`
- `FAIL` `max_drawdown_strictly_better`
- `FAIL` `sharpe_noninferior`
- `PASS` `slippage_le_105pct`
- `PASS` `trade_count_positive`
- `PASS` `account_survival_pass`
- `PASS` `broker10_peak_le_100pct`
- `PASS` `days_over_100pct_not_worse`

- 离线研究；未连接CTP，未调用订单API，未修改生产目录，未自动晋升。
