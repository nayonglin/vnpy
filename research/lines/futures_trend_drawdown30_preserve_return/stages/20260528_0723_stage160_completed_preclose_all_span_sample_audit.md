# Stage160 completed-row全span抽样聚合审计

- 时间：2026-05-28 07:23 CST
- 工作模式：day
- 研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：重要数据链路突破；不新增策略，不修改 Stage079/C3/Stage103 交易规则
- 决策：`completed_preclose_full_bar_all_span_sample_ready_extend_full_dates`
- 晋级判断：数据链路继续晋级；策略版本不晋级；Stage079 baseline 不变

## 本阶段目的

Stage159 只验证了 Stage154 缺口计划前 60 个span。Stage160 继续使用同一 completed-row 抽取语义，将 Stage154 的全部 `547` 个缺口span按 `60/60/60/60/60/60/60/60/67` 分片做抽样验证。每个span最多抽取前 `5` 个目标日，目的是确认全span层面的 TqBacktest completed-row OHLCVOI 链路是否稳定。

注意：本阶段仍是抽样验证，不是全目标日期回补。Stage154 缺口总量约 `21,475` 个合约日键，本阶段覆盖 `2,665` 个目标日；下一阶段必须改成全日期回补后，才能进入一致预收盘真实回放。

## 外部调研与判断

- TqSdk 官方 API 文档显示 `get_kline_serial` 分钟K包含 `open/high/low/close/volume/open_oi/close_oi` 字段，满足合成预收盘可见日K的最低字段要求。
- TqSdk 回测文档与 Stage158/159 的实测一致：回测推进中最后一根K线可能是未完成K线，严格统计应使用上一根已完成K线。
- GitHub `shinnytech/tqsdk-python` 未发现比官方 completed-row 语义更直接的现成修复方案。
- xtquant/QMT 分钟数据仍是备份，但当前主路径继续使用 TqBacktest completed-row，原因是同一数据链路已经跨全部缺口span抽样通过。

参考：

- TqSdk API 文档：https://tqsdk-python.readthedocs.io/en/stable/reference/tqsdk.api.html
- TqSdk Backtest 文档：https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.backtest.html
- TqSdk GitHub：https://github.com/shinnytech/tqsdk-python
- xtquant 数据接口文档：https://zsrl.github.io/xtquant-doc/xtquant/xtdata.html

## 代码与参数

新增脚本：

- `examples/portfolio_backtesting/analyze_qmt_roll_stage460_completed_preclose_full_bar_shard_aggregate.py`

复用脚本：

- `examples/portfolio_backtesting/analyze_qmt_roll_stage459_completed_preclose_full_bar_shard.py`

新增/固定参数：

- `STAGE459_MAX_DATES_PER_SYMBOL=5`
- `STAGE459_MAX_SECONDS_PER_SYMBOL=180`
- `STAGE459_SESSION_LOOKBACK_CALENDAR_DAYS=3`
- `STAGE459_FREEZE_TIME=14:55`
- `STAGE459_FILL_END_TIME=15:00`
- `STAGE459_FORCE_REFRESH=0`
- 分片：`1-60`、`61-120`、`121-180`、`181-240`、`241-300`、`301-360`、`361-420`、`421-480`、`481-547`

变更内容：

- 新增：Stage160 聚合脚本，读取 Stage159/Stage160 各分片 summary/targets/status，生成总览 CSV、分片汇总 CSV、decision JSON 与报告。
- 未修改：C3、Stage079、Stage103 交易规则、资金口径、持仓逻辑、下单规则。
- 删除：无。

## 回测/审计结果

本阶段是数据链路审计，不是策略收益回测；因此期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均不适用。Stage079 的既有账户 baseline 不变：正常成本口径 `50万C3下单 + 11.5万外部现金`。

全span抽样聚合：

| 指标 | 结果 |
| --- | ---: |
| 分片数 | 9 |
| 覆盖span | 1-547 |
| 唯一span数 | 547 |
| 唯一合约数 | 455 |
| 产品数 | 19 |
| 抽样目标日 | 2,665 |
| strict ready | 2,665 / 2,665 |
| strict ready率 | 100.00% |
| 失败合约 | 0 |
| timeout | 0 |
| 已完成分钟K | 1,371,015 |
| 正成交量分钟K | 1,370,353 |
| 最少预收盘bar数 | 220 |
| 最少填充窗口bar数 | 4 |
| 合成预收盘成交量 | 1,734,402,227 |
| 填充窗口成交量 | 22,589,030 |

分片摘要：

| 分片 | span | 合约数 | 目标日 | 分钟K | 正成交量分钟K | strict ready | 失败 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 001-060 | 60 | 60 | 300 | 121,995 | 121,825 | 300/300 | 0 |
| 061-120 | 60 | 60 | 300 | 127,365 | 127,357 | 300/300 | 0 |
| 121-180 | 60 | 60 | 300 | 116,910 | 116,786 | 300/300 | 0 |
| 181-240 | 60 | 60 | 300 | 126,810 | 126,758 | 300/300 | 0 |
| 241-300 | 60 | 56 | 300 | 189,135 | 189,107 | 300/300 | 0 |
| 301-360 | 60 | 60 | 300 | 140,775 | 140,737 | 300/300 | 0 |
| 361-420 | 60 | 60 | 300 | 129,720 | 129,611 | 300/300 | 0 |
| 421-480 | 60 | 55 | 300 | 213,795 | 213,701 | 300/300 | 0 |
| 481-547 | 67 | 59 | 265 | 204,510 | 204,471 | 265/265 | 0 |

## 输出文件

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage460_completed_preclose_full_bar_shard_aggregate_summary_stage460_completed_preclose_full_bar_shard_001_547_sample5_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage460_completed_preclose_full_bar_shard_aggregate_shard_summary_stage460_completed_preclose_full_bar_shard_001_547_sample5_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage460_completed_preclose_full_bar_shard_aggregate_decision_stage460_completed_preclose_full_bar_shard_001_547_sample5_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage460_completed_preclose_full_bar_shard_aggregate_report_stage460_completed_preclose_full_bar_shard_001_547_sample5_v1.md`

## 结论

1. completed-row OHLCVOI 数据链路已经跨 Stage154 全部 `547` 个缺口span抽样通过，且 `timeout=0`、`failed_symbol_count=0`。
2. 本阶段仍不能晋级策略候选，因为它没有产生收益曲线，也没有做一致预收盘真实回放。
3. 当前路线值得继续，但下一步必须从“每span前5个目标日”升级到“全目标日期回补”；只有全日期 OHLCVOI 稳定后，才能重新评估 Stage079/Stage103 的 3个月、6个月体验优化。

## 后续规划

- 将 `STAGE459_MAX_DATES_PER_SYMBOL=0` 或改造脚本为批量全日期模式，按分片回补 Stage154 的全部缺口合约日键。
- 全日期回补后，生成完整 `C_full_preclose_daily_bar` 数据集。
- 用该数据集做一致预收盘真实回放：信号看到截至 `14:55` 的可见 OHLCVOI，成交使用预声明 `14:55-15:00` 窗口。
- 回放稳定后，再重新跑 Stage079/Stage103 与任何新候选的硬约束、3个月/6个月体验评分和成本压力。

## 过拟合与继续价值反思

- 是否过拟合：否。本阶段只做数据链路全span抽样验证，不看收益、不筛日期、不筛品种、不调策略参数；它把晋级条件收紧到真实可见字段一致。
- 是否仍有价值继续：是。目标是提升 Stage079 3/6个月持有体验，但不能建立在未来函数或不可成交口径上；Stage160 证明全span抽样可行，下一步全日期回补有明确价值。
