# Stage020 2021最大回撤归因

- 研究线：`futures_trend_drawdown30_preserve_return`
- 时间：2026-05-25 20:38 CST
- 基准版本：`official_stage78_1_defensive_50w_no_sizing_cap`
- 阶段性质：只读归因，不改策略。
- 是否重要突破：否，但明确下一步不应继续调供需/风险缩放。

## 开始前反思

- 是否过拟合：否。归因只解释已出现的最差回撤，不直接生成交易规则。
- 是否有价值继续：是。C3 与 C_pressure040 的全样本最差回撤完全重合，必须先知道问题来自哪里。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage320_2021_pressure040_drawdown_attribution.py`
- 修改正式78-1参数：无。
- 新增正式参数：无。
- 删除参数：无。

## 回撤窗口

- 峰值日：`2021-05-12`
- 谷底日：`2021-07-02`
- 峰值权益：`1,788,060`
- 谷底权益：`1,232,390`
- 最大回撤：`-31.0767%`

本次归因回放到 `2021-08-31`，用于定位最差窗口；不是新的完整收益候选。因此完整全样本收益字段仍参考 Stage018/019。

## 品种亏损贡献

| 品种 | 净损益 | 持仓损益 | 交易次数 | 最大绝对持仓 |
| --- | ---: | ---: | ---: | ---: |
| hc.SHFE | -151,140 | -149,380 | 3 | 55 |
| FG.CZCE | -107,020 | -104,480 | 3 | 35 |
| SM.CZCE | -94,330 | -89,920 | 5 | 73 |
| rb.SHFE | -74,340 | -74,200 | 1 | 14 |
| SA.CZCE | -67,380 | -63,960 | 4 | 36 |
| jm.DCE | -56,730 | -56,280 | 3 | 5 |

最差单日：

- `2021-05-13`：净损益 `-222,210`
- `2021-05-14`：净损益 `-152,280`
- `2021-06-11`：净损益 `-69,450`

## 结论

- `C_pressure040/C3` 的剩余最差回撤主要来自黑色建材簇同步失血，而不是供需数据覆盖期内的开仓质量问题。
- 供需数据从 2023 后才有覆盖，天然修不了 2021 最大回撤。
- 下一步若继续，应验证“黑色建材簇风险治理”是否能低过拟合地解决；但不能直接做单品种黑名单。

## 结束后反思

- 是否过拟合：归因本身不是，但如果据此永久限制某个品种/产业且不做多周期验证，就会过拟合。
- 是否有价值继续：有价值，下一步只允许测试宽口径风险簇上限或条件触发，不能做单日补丁。

## 输出文件

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage320_2021_pressure040_drawdown_attribution_report_stage320_2021_pressure040_drawdown_attribution_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage320_2021_pressure040_drawdown_attribution_product_summary_stage320_2021_pressure040_drawdown_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage320_2021_pressure040_drawdown_attribution_daily_summary_stage320_2021_pressure040_drawdown_attribution_v1.csv`

