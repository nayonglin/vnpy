# Stage159 completed-row预收盘完整bar分片回补审计

- 时间：2026-05-28 06:31 CST
- 工作模式：day
- 研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：重要数据链路突破；不是策略候选晋级，不触发 A/B 接入
- 决策：`completed_preclose_full_bar_shard_ready_extend_next_shard`
- 晋级判断：数据链路晋级，策略版本不晋级；Stage079 baseline 不变

## 本阶段目的

Stage155 已固定预收盘一致回放的唯一可晋级规格为 `C_full_preclose_daily_bar`：必须用交易日开始至冻结时点的分钟K合成当日可见 `open/high/low/close/volume/open_interest`，再用同一预声明窗口成交。Stage156 小批次抽到的分钟K `volume=0` 曾阻断该路线；Stage158 证明原因主要是抽取了滚动未完成K线。Stage159 将完整bar回补脚本改为 `completed_previous_row` 语义，并扩大到 60 个缺口span验证。

## 外部调研与判断

- TqSdk 官方 API 文档中 `get_kline_serial` 分钟K字段包含 `open/high/low/close/volume/open_oi/close_oi`，因此分钟 OHLCVOI 字段理论上足以合成预收盘可见日K。
- TqSdk 回测文档说明回测模式会按历史数据推进，K线在创建与结束时更新；这与 Stage158 的观察一致：滚动最后一根未完成K线可能显示 `volume=0`，上一根已完成K线才可用于严格统计。
- GitHub 上的 `shinnytech/tqsdk-python` 仓库确认 TqSdk 是开源期货量化开发包，包含历史数据、回测、模拟与实盘链路；没有发现比官方 completed-row 语义更直接的现成修复方案。
- xtquant/QMT 分钟数据仍保留为备选数据源，但当前更低成本、更一致的路径是先修正 TqBacktest completed-row 抽取语义。
- 调研结论：不应该把 Stage156 直接判定为“天勤没有分钟成交量”；正确路线是 completed-row 分片回补，随后再做一致预收盘真实回放。

参考：

- TqSdk API 文档：https://tqsdk-python.readthedocs.io/en/stable/reference/tqsdk.api.html
- TqSdk Backtest 文档：https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.backtest.html
- TqSdk GitHub：https://github.com/shinnytech/tqsdk-python
- xtquant 数据接口文档：https://zsrl.github.io/xtquant-doc/xtquant/xtdata.html

## 代码与参数

新增脚本：

- `examples/portfolio_backtesting/analyze_qmt_roll_stage459_completed_preclose_full_bar_shard.py`

新增/固定参数：

- `STAGE459_MODEL_TAG=stage459_completed_preclose_full_bar_shard_v1`
- `STAGE459_OUTPUT_PREFIX=qmt_roll_stage459_completed_preclose_full_bar_shard`
- `STAGE459_RAW_SUBDIR=tqsdk_stage459_completed_preclose_full_bar_shard`
- `STAGE459_START_SPAN=1`
- `STAGE459_MAX_SPANS=60`
- `STAGE459_MAX_DATES_PER_SYMBOL=5`
- `STAGE459_MAX_SECONDS_PER_SYMBOL=180`
- `STAGE459_SESSION_LOOKBACK_CALENDAR_DAYS=3`
- `STAGE459_FREEZE_TIME=14:55`
- `STAGE459_FILL_END_TIME=15:00`
- `STAGE459_FORCE_REFRESH=0`

变更内容：

- 新增：在 `get_kline_serial(..., duration_seconds=60)` 推进时，当 K 线 `datetime` 发生变化，记录 `klines.iloc[-2]` 作为上一根已完成分钟K。
- 新增：按 Stage154 缺口计划分片抽取目标合约，在每个目标日合成截至 `14:55` 的预收盘可见 OHLCVOI，并统计 `14:55-15:00` 填充窗口。
- 未修改：C3、Stage079、Stage103 交易规则、参数、资金口径、下单规则。
- 删除：无。

## 回测/审计结果

本阶段是数据链路审计，不是策略收益回测；因此期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均不适用。Stage079 的既有账户 baseline 不变：正常成本口径 `50万C3下单 + 11.5万外部现金`。

| 运行 | span数 | 合约数 | 目标日 | 分钟K数 | 正成交量分钟K | strict ready | ready率 | 失败合约 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30-span初跑 | 30 | 30 | 150 | 61,965 | 61,817 | 150/150 | 100.00% | 0 |
| 60-span扩展 | 60 | 60 | 300 | 121,995 | 121,825 | 300/300 | 100.00% | 0 |

60-span最终补充指标：

- `status_success_like_count=60`
- `failed_symbol_count=0`
- `boundary_uncertain_count=60`
- 最少预收盘bar数：`220`
- 最少填充窗口bar数：`4`
- 合成预收盘成交量合计：`195,818,466`
- 填充窗口成交量合计：`3,505,999`
- 产品层覆盖样例：`AP.CZCE 30/30`、`CF.CZCE 30/30`、`SA.CZCE 20/20`、`rb.SHFE 20/20`、`ru.SHFE 20/20`、`fu.SHFE 25/25`、`sp.SHFE 20/20` 均为 100% ready。

## 输出文件

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage459_completed_preclose_full_bar_shard_selected_targets_stage459_completed_preclose_full_bar_shard_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage459_completed_preclose_full_bar_shard_extract_status_stage459_completed_preclose_full_bar_shard_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage459_completed_preclose_full_bar_shard_completed_minute_bars_stage459_completed_preclose_full_bar_shard_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage459_completed_preclose_full_bar_shard_synthetic_preclose_bars_stage459_completed_preclose_full_bar_shard_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage459_completed_preclose_full_bar_shard_span_summary_stage459_completed_preclose_full_bar_shard_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage459_completed_preclose_full_bar_shard_product_summary_stage459_completed_preclose_full_bar_shard_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage459_completed_preclose_full_bar_shard_summary_stage459_completed_preclose_full_bar_shard_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage459_completed_preclose_full_bar_shard_decision_stage459_completed_preclose_full_bar_shard_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage459_completed_preclose_full_bar_shard_report_stage459_completed_preclose_full_bar_shard_v1.md`
- 原始分钟缓存目录：`examples/portfolio_backtesting/downloaded_futures/tqsdk_stage459_completed_preclose_full_bar_shard/`

## 结论

1. 值得晋级的是数据链路：`completed_previous_row` 已完成分钟K抽取语义，在 60 个 Stage154 缺口span、60 个合约、300 个目标日上达到 `300/300` strict ready。
2. 不值得晋级任何策略候选：本阶段没有收益曲线、没有新策略、没有参数优化；Stage079 仍是当前正常成本 baseline，Stage103 仍因真实执行/一致预收盘路径未闭环而暂停真实 paper 晋级。
3. 该结果足以把路线从“寻找外部分钟volume源”推进到“全量分片回补 OHLCVOI”，但还不足以直接恢复 3/6 个月短持有体验优化。

## 后续规划

- 继续按同一脚本跑后续分片：`61-120`、`121-180`、`181-240`，直至覆盖 Stage154 的 `547` 个span。
- 若全部分片保持 strict ready，再合并全量 `C_full_preclose_daily_bar` 数据，并做一致预收盘真实回放。
- 只有一致预收盘真实回放稳定后，才重新评估 Stage079/Stage103 以及 3个月、6个月持有体验优化。
- 不回到同日收盘口径的 alpha 补丁；也不因 60-span 数据成功而直接晋级策略。

## 过拟合与继续价值反思

- 是否过拟合：否。这里没有看收益挑日期、挑品种、调参数，只修正 K 线完成语义并扩大数据覆盖验证；结论还主动限制策略晋级。
- 是否仍有价值继续：是。短持有体验优化如果要可部署，必须先证明预收盘可见日K可以稳定合成；Stage159 把这个关键前置从“疑似不可用”推进到“分片可用，值得全量验证”。
