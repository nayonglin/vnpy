# Stage162 completed-row全日期预收盘bar分片021-040

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 08:02 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage154 缺口计划的全日期 `C_full_preclose_daily_bar` 数据回补分片；不新增策略、不修改 Stage079/C3/Stage103 交易规则。
- 是否重要突破：否，属于 Stage161 后的稳定扩展；重要性在于继续补齐真实预收盘一致回放的数据底座。
- 是否触发A/B：否。本阶段没有新策略候选。

## 外部调研与判断

- 参考资料：
  - https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html
  - https://github.com/shinnytech/tqsdk-python
- 我的判断：
  - TqSdk 官方文档说明 `TqBacktest` 回测模式会在区间内推进行情、K线和Tick；`TqApi` 支持 `disable_print` 控制提示输出。GitHub README 也说明 TqSdk 提供历史数据、K线级回测和策略开发能力。
  - 本阶段继续沿用 Stage158-161 形成的 `completed_previous_row` 语义。它不是收益优化，也不构成参数选择；它只是保证后续预收盘信号bar和成交窗口使用同一时点可见信息，避免把同日完整日K字段误当成可交易优势。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：
  - `STAGE459_STAGE_NAME=Stage162`
  - `STAGE459_OUTPUT_PREFIX=qmt_roll_stage462_completed_preclose_full_dates_shard`
  - `STAGE459_MODEL_TAG=stage462_completed_preclose_full_dates_021_040_v1`
  - `STAGE459_START_SPAN=21`
  - `STAGE459_MAX_SPANS=20`
  - `STAGE459_MAX_DATES_PER_SYMBOL=0`
  - `STAGE459_MAX_SECONDS_PER_SYMBOL=900`
  - `STAGE459_RAW_SUBDIR=tqsdk_stage462_completed_preclose_full_dates_shard`
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage154 缺口计划中 `plan_rank=21-40` 对应合约的全部目标缺口日期。
- 账户规模：不涉及权益回测；Stage079 baseline 仍为 `615,000` 账户资金口径。
- 成本口径：不涉及成交成本；只抽取分钟K并合成预收盘可见OHLCVOI。
- 样本过滤：`MAX_DATES_PER_SYMBOL=0`，即所选span内不截断日期。
- 策略/归因口径：按交易日开始至 `14:55` 前已完成1分钟K合成 `open/high/low/close/volume/open_interest`，并检查 `14:55-15:00` 填充窗口是否存在可用OHLC。

## 运行命令

```bash
STAGE459_STAGE_NAME=Stage162 \
STAGE459_OUTPUT_PREFIX=qmt_roll_stage462_completed_preclose_full_dates_shard \
STAGE459_MODEL_TAG=stage462_completed_preclose_full_dates_021_040_v1 \
STAGE459_START_SPAN=21 \
STAGE459_MAX_SPANS=20 \
STAGE459_MAX_DATES_PER_SYMBOL=0 \
STAGE459_MAX_SECONDS_PER_SYMBOL=900 \
STAGE459_RAW_SUBDIR=tqsdk_stage462_completed_preclose_full_dates_shard \
.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage459_completed_preclose_full_bar_shard.py
```

缓存复验使用同一命令重跑，状态变为 `cached_raw=20`，`elapsed_seconds` 合计 `0.0`。

## 结果

| 指标 | 结果 |
| --- | ---: |
| 覆盖span | 21-40 |
| 唯一合约 | 20 |
| 目标缺口日期 | 1,721 |
| full_bar_ready | 1,721 |
| full_bar_ready_rate | 100.0000% |
| failed_symbol_count | 0 |
| 首次抽取状态 | `extracted=20` |
| 缓存复验状态 | `cached_raw=20` |
| 缓存复验耗时合计 | 0.0秒 |
| 已完成分钟K | 590,715 |
| 正成交量分钟K | 590,690 |
| 最小预收盘bar数 | 220 |
| 最小填充窗口bar数 | 4 |
| 合成预收盘成交量 | 850,778,302 |
| 填充窗口成交量 | 16,229,425 |

字段分解：

| 字段 | 通过数 |
| --- | ---: |
| `valid_ohlc` | 1,721 |
| `volume_ok` | 1,721 |
| `open_interest_ok` | 1,721 |
| `fill_ok` | 1,721 |
| `full_bar_ready` | 1,721 |

Stage079 baseline 核心指标本阶段未重跑、未改变：

| 指标 | Stage079 baseline | 本阶段影响 |
| --- | ---: | --- |
| 期末权益 | `31,040,650` | 未评估，未变更策略 |
| 总收益 | `4,947.2602%` | 未评估，未变更策略 |
| 最大回撤 | `-29.7007%` | 未评估，未变更策略 |
| Sharpe | `1.3182` | 未评估，未变更策略 |
| Ulcer | `15.0931` | 未评估，未变更策略 |
| 总滑点 | 沿用 Stage079 | 未评估 |
| 总交易次数 | 沿用 Stage079 | 未评估 |
| 胜率 | 沿用 Stage079 | 未评估 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage462_completed_preclose_full_dates_shard_report_stage462_completed_preclose_full_dates_021_040_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage462_completed_preclose_full_dates_shard_summary_stage462_completed_preclose_full_dates_021_040_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage462_completed_preclose_full_dates_shard_decision_stage462_completed_preclose_full_dates_021_040_v1.json`
- status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage462_completed_preclose_full_dates_shard_extract_status_stage462_completed_preclose_full_dates_021_040_v1.csv`
- completed_minute_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage462_completed_preclose_full_dates_shard_completed_minute_bars_stage462_completed_preclose_full_dates_021_040_v1.csv`
- synthetic_preclose_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage462_completed_preclose_full_dates_shard_synthetic_preclose_bars_stage462_completed_preclose_full_dates_021_040_v1.csv`
- raw cache：`examples/portfolio_backtesting/downloaded_futures/tqsdk_stage462_completed_preclose_full_dates_shard/`

## 结论

- 本阶段结论：`plan_rank=21-40` 全日期分片全部 strict ready，且缓存复验正常。Stage160 的抽样结论已经在第二个全日期分片上继续成立。
- 是否进入下一步：进入下一步数据回补；仍不进入策略候选晋级。
- 下一步：继续 `41-60` 等全日期分片；覆盖更多span后新增全日期聚合器，确认 Stage154 约 `21,475` 个缺口合约日键全部 strict ready，再恢复一致预收盘真实回放和3/6个月体验优化。

## 过拟合反思

- 运行前判断：否。本阶段只做数据链路覆盖，不看收益，不筛选好窗口，不调整交易规则。
- 运行后判断：否。结果只证明数据可得性和缓存可复验；没有根据收益或持有体验指标改变任何参数。
- 原因：选择 `21-40` 是按 Stage154 缺口计划顺序推进，不是按表现挑选；`MAX_DATES_PER_SYMBOL=0` 避免只抽取容易日期。

## 继续价值反思

- 运行前判断：有价值。Stage079/Stage103 的同日收盘口径已经被 Stage141-153 证明不具备直接部署安全性，短持有体验优化必须先回到一致预收盘可见信息集。
- 运行后判断：仍有价值。前 `40` 个全日期span合计 `3,842` 个缺口日期全部 strict ready，说明全量回补可执行，下一步继续扩展比回到旧alpha补丁更重要。
- 原因：只有全日期 OHLCVOI 稳定后，后续任何3个月/6个月体验改善才可能被认为是策略真实改善，而不是执行口径幻觉。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage162 执行约束和阶段记录索引。
- 是否更新 `research/registry.md`：否，本阶段为增量分片，未改变全线最新关键结论；等全日期聚合完成再更新总索引更合适。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、路线废弃或跨线合并；等全日期聚合/真实预收盘回放形成关键结论再追加。
