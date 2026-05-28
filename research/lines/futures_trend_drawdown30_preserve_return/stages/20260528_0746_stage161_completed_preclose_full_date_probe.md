# Stage161 completed-row全日期预收盘bar重缺口探针

- 生成时间：2026-05-28 07:46 CST
- 所属研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：数据链路全日期探针；不新增策略、不修改 Stage079/C3/Stage103 交易规则。
- 是否重要突破版本：是，数据工程层面的突破；不是策略候选突破。
- 决策：`completed_preclose_full_bar_shard_ready_extend_next_shard`
- 策略晋级：无。

## 开始反思

- 是否过拟合：否。本阶段不看收益、不筛选品种、不按结果调交易参数，只验证 Stage154 缺口计划中预收盘 `C_full_preclose_daily_bar` 的 completed-row 数据可得性。
- 是否有价值继续：是。Stage079/Stage103 的 3个月/6个月体验优化必须先建立在严格可见的预收盘 OHLCVOI 信息集上；否则后续候选可能只是同日收盘未来日K字段的幻觉。

## 外部调研与判断

- TqSdk 官方 `TqApi.get_kline_serial` 文档说明 K 线序列会随时间推进自动更新，适合在 `TqBacktest` 时间推进中观察已完成行。
- TqSdk `TqBacktest` 文档与 GitHub 项目说明其回测模式用于推进行情数据；Stage158/159 已用实测确认 `klines.iloc[-2]` 的 completed-row 语义能恢复真实分钟成交量。
- xtquant/QMT 数据接口仍作为备份，但当前判断是：继续优先 TqBacktest completed-row，不切换数据源。
- Walk-forward/滚动窗口反过拟合资料的共同结论是先保证信息集和 OOS/滚动评估纪律，再做优化；因此本阶段仍先修数据链路，不回到参数补丁。

参考：

- https://tqsdk-python.readthedocs.io/en/stable/reference/tqsdk.api.html
- https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.backtest.html
- https://github.com/shinnytech/tqsdk-python
- https://zsrl.github.io/xtquant-doc/xtquant/xtdata.html

## 本阶段改动

### 新增参数

- `STAGE459_STAGE_NAME`：允许复用 Stage459 回补脚本输出不同阶段名，本阶段重跑为 `Stage161`。
- `STAGE459_DISABLE_TQSDK_PRINT`：默认 `1`，传入 `TqApi(..., disable_print=True)`，后续分片避免 TqSdk 逐日账户日志刷屏。
- `cache_required_end` 状态列：记录 completed-row 缓存判定所需覆盖到的最后时间点。

### 修改参数/逻辑

- `MAX_DATES_PER_SYMBOL=0`：从 Stage160 的“每span前5个目标日抽样”升级为“所选span内全日期”。
- `START_SPAN=1`、`MAX_SPANS=20`：选择 Stage154 缺口计划中最重的前 20 个span作为压力探针。
- `MAX_SECONDS_PER_SYMBOL=900`：允许单合约长区间回放完成。
- 修正 `_load_cached` 覆盖判定：completed-row 语义下，缓存只需覆盖到 `FILL_END_TIME - 2min`，不再错误要求覆盖到 `15:10` 回测缓冲尾部。修复后同一分片缓存重跑从重新抽取变为 `cached_raw=20/20`。

### 删除参数

- 无。

## 运行命令

```bash
STAGE459_OUTPUT_PREFIX=qmt_roll_stage461_completed_preclose_full_dates_probe \
STAGE459_MODEL_TAG=stage461_completed_preclose_full_dates_001_020_v1 \
STAGE459_START_SPAN=1 \
STAGE459_MAX_SPANS=20 \
STAGE459_MAX_DATES_PER_SYMBOL=0 \
STAGE459_MAX_SECONDS_PER_SYMBOL=900 \
STAGE459_RAW_SUBDIR=tqsdk_stage461_completed_preclose_full_dates_probe \
.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage459_completed_preclose_full_bar_shard.py
```

缓存修复后复验：

```bash
STAGE459_STAGE_NAME=Stage161 \
STAGE459_OUTPUT_PREFIX=qmt_roll_stage461_completed_preclose_full_dates_probe \
STAGE459_MODEL_TAG=stage461_completed_preclose_full_dates_001_020_v1 \
STAGE459_START_SPAN=1 \
STAGE459_MAX_SPANS=20 \
STAGE459_MAX_DATES_PER_SYMBOL=0 \
STAGE459_MAX_SECONDS_PER_SYMBOL=900 \
STAGE459_RAW_SUBDIR=tqsdk_stage461_completed_preclose_full_dates_probe \
.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage459_completed_preclose_full_bar_shard.py
```

## 新增回测/回补结果

| 指标 | 结果 |
| --- | ---: |
| 覆盖span | 1-20 |
| 唯一合约 | 20 |
| 目标缺口日期 | 2,121 |
| full_bar_ready | 2,121 |
| full_bar_ready_rate | 100.0000% |
| failed_symbol_count | 0 |
| 首次抽取状态 | `extracted=20` |
| 首次抽取耗时合计 | 611.09秒 |
| 单合约最大耗时 | 57.83秒 |
| 缓存复验状态 | `cached_raw=20` |
| 已完成分钟K | 672,045 |
| 正成交量分钟K | 671,253 |
| 最小预收盘bar数 | 220 |
| 最小填充窗口bar数 | 4 |
| 合成预收盘成交量 | 1,260,963,070 |
| 填充窗口成交量 | 31,613,144 |

字段分解复核：

| 字段 | 通过数 |
| --- | ---: |
| `valid_ohlc` | 2,121 |
| `volume_ok` | 2,121 |
| `open_interest_ok` | 2,121 |
| `fill_ok` | 2,121 |

## Stage079核心指标影响

本阶段不跑策略权益，不改变 Stage079 baseline，不新增资金占用，因此 Stage079 当前权威核心指标保持不变：

| 指标 | Stage079 baseline | 本阶段 |
| --- | ---: | --- |
| 账户资金口径 | 615,000 | 未变 |
| 全周期总收益 | 4,947.2602% | 未评估，未变更策略 |
| 最大回撤 | -29.7007% | 未评估，未变更策略 |
| Sharpe | 1.3182 | 未评估，未变更策略 |
| Ulcer | 15.0931 | 未评估，未变更策略 |
| 总滑点 | 沿用 Stage079 | 未评估 |
| 总交易次数 | 沿用 Stage079 | 未评估 |
| 胜率 | 沿用 Stage079 | 未评估 |
| 期末权益 | 沿用 Stage079 | 未评估 |

## 判断

1. `1-20` 是 Stage154 缺口计划中目标日期最多的一组，合计 `2,121` 个缺口日期。该组全日期 strict ready，说明 Stage160 的抽样通过不是只在前5日偶然成立。
2. `fill_bar_count_min=4` 仍可接受，因为 completed-row 在 14:55-15:00 窗口通常只能稳定看到截至 14:58 的已完成行；这与后续真实预声明成交窗口一致，但必须在一致回放中明确执行语义。
3. 首次抽取 20 合约耗时约 10.18 分钟，按 20 span 分片全量跑 547 span 是可行的，但需要批处理、断点缓存和安静输出。
4. 本阶段没有任何策略候选晋级。值得晋级的是 `completed-row full-date backfill` 数据链路。

## 输出文件

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage461_completed_preclose_full_dates_probe_summary_stage461_completed_preclose_full_dates_001_020_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage461_completed_preclose_full_dates_probe_decision_stage461_completed_preclose_full_dates_001_020_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage461_completed_preclose_full_dates_probe_report_stage461_completed_preclose_full_dates_001_020_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage461_completed_preclose_full_dates_probe_synthetic_preclose_bars_stage461_completed_preclose_full_dates_001_020_v1.csv`
- `examples/portfolio_backtesting/downloaded_futures/tqsdk_stage461_completed_preclose_full_dates_probe/`

## 后续规划和TODO

1. 按 `20` span 左右为默认作业单位，继续跑 `21-40`、`41-60` 等全日期分片；优先覆盖全部 `547` span。
2. 新增/复用聚合器，聚合 Stage461 全日期分片，确认 `约21,475` 个缺口合约日键全部 strict ready。
3. 全日期 `C_full_preclose_daily_bar` 稳定后，才恢复一致预收盘真实回放。
4. 一致预收盘真实回放完成后，再按用户定义硬约束和 3/6个月短持有体验评分重审 Stage079/Stage103/新候选。

## 结束反思

- 是否过拟合：否。没有使用收益目标做选择，没有参数扫描，也没有新增交易规则；只验证数据链路和缓存工程。
- 是否仍有价值继续：是。Stage161 已证明重缺口全日期回补可行，下一步全量分片是通向真实预收盘回放的必要条件。
