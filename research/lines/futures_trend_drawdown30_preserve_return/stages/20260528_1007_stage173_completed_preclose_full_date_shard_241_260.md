# Stage173 completed-row全日期预收盘bar分片241-260

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 10:07 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage154 缺口计划的全日期 `C_full_preclose_daily_bar` 数据回补分片；不新增策略、不修改 Stage079/C3/Stage103 交易规则。
- 是否重要突破：否，属于 Stage161-172 后的稳定扩展。
- 是否触发A/B：否。本阶段没有新策略候选。

## 外部调研与判断

- 参考资料：
  - https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html
  - https://github.com/shinnytech/tqsdk-python
- 我的判断：
  - TqSdk 官方与项目资料支持 `TqBacktest`、`get_kline_serial` 这类历史K线和回测使用场景；但回测更新循环里的最新行可能仍在滚动变化，因此本线继续坚持 Stage158 已验证的 `completed_previous_row` 抽取语义。
  - 本阶段只补齐一致预收盘真实回放所需 OHLCVOI 信息集，不依据收益挑日期、合约、成交窗口或参数。
  - 你的“如果值得晋级可以不按目标来”的要求我采纳为独立判断：本阶段可晋级的是数据链路可信度，不是交易版本；在一致预收盘真实回放完成前，Stage079/Stage103/xsmom 仍不能因旧同日收盘口径的短持有表现而晋级。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：
  - `STAGE459_STAGE_NAME=Stage173`
  - `STAGE459_OUTPUT_PREFIX=qmt_roll_stage473_completed_preclose_full_dates_shard`
  - `STAGE459_MODEL_TAG=stage473_completed_preclose_full_dates_241_260_v1`
  - `STAGE459_START_SPAN=241`
  - `STAGE459_MAX_SPANS=20`
  - `STAGE459_MAX_DATES_PER_SYMBOL=0`
  - `STAGE459_MAX_SECONDS_PER_SYMBOL=900`
  - `STAGE459_RAW_SUBDIR=tqsdk_stage462_completed_preclose_full_dates_shard`
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage154 缺口计划中 `plan_rank=241-260` 对应合约的全部目标缺口日期。
- 账户规模：不涉及权益回测；Stage079 baseline 仍为 `615,000` 账户资金口径。
- 成本口径：不涉及成交成本；只抽取分钟K并合成预收盘可见 OHLCVOI。
- 样本过滤：`MAX_DATES_PER_SYMBOL=0`，即所选span内不截断日期。
- 策略/归因口径：按交易日开始至 `14:55` 前已完成1分钟K合成 `open/high/low/close/volume/open_interest`，并检查 `14:55-15:00` 填充窗口是否存在可用 OHLC。

## 运行命令

```bash
STAGE459_STAGE_NAME=Stage173 \
STAGE459_OUTPUT_PREFIX=qmt_roll_stage473_completed_preclose_full_dates_shard \
STAGE459_MODEL_TAG=stage473_completed_preclose_full_dates_241_260_v1 \
STAGE459_START_SPAN=241 \
STAGE459_MAX_SPANS=20 \
STAGE459_MAX_DATES_PER_SYMBOL=0 \
STAGE459_MAX_SECONDS_PER_SYMBOL=900 \
STAGE459_RAW_SUBDIR=tqsdk_stage462_completed_preclose_full_dates_shard \
.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage459_completed_preclose_full_bar_shard.py
```

缓存复验使用同一命令重跑，状态为 `cached_raw=20`。

## 结果

| 指标 | 结果 |
| --- | ---: |
| 覆盖span | 241-260 |
| 唯一合约 | 20 |
| 目标缺口日期 | 686 |
| full_bar_ready | 686 |
| full_bar_ready_rate | 100.0000% |
| failed_symbol_count | 0 |
| 缓存复验状态 | `cached_raw=20` |
| 已完成分钟K | 231,465 |
| 正成交量分钟K | 231,442 |
| 最小预收盘bar数 | 220 |
| 最小填充窗口bar数 | 4 |
| 合成预收盘成交量 | 376,198,303 |
| 填充窗口成交量 | 7,729,501 |
| 递归raw cache文件数 | 239 |

字段分解：

| 字段 | 通过数 |
| --- | ---: |
| `valid_ohlc` | 686 |
| `volume_ok` | 686 |
| `open_interest_ok` | 686 |
| `fill_ok` | 686 |
| `full_bar_ready` | 686 |

累计状态：

| 范围 | 目标缺口日期 | strict ready |
| --- | ---: | ---: |
| Stage161 `1-20` | 2,121 | 2,121 |
| Stage162 `21-40` | 1,721 | 1,721 |
| Stage163 `41-60` | 1,653 | 1,653 |
| Stage164 `61-80` | 1,600 | 1,600 |
| Stage165 `81-100` | 1,548 | 1,548 |
| Stage166 `101-120` | 1,499 | 1,499 |
| Stage167 `121-140` | 1,394 | 1,394 |
| Stage168 `141-160` | 1,218 | 1,218 |
| Stage169 `161-180` | 1,039 | 1,039 |
| Stage170 `181-200` | 912 | 912 |
| Stage171 `201-220` | 842 | 842 |
| Stage172 `221-240` | 757 | 757 |
| Stage173 `241-260` | 686 | 686 |
| 合计 `1-260` | 16,990 | 16,990 |

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

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage473_completed_preclose_full_dates_shard_report_stage473_completed_preclose_full_dates_241_260_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage473_completed_preclose_full_dates_shard_summary_stage473_completed_preclose_full_dates_241_260_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage473_completed_preclose_full_dates_shard_decision_stage473_completed_preclose_full_dates_241_260_v1.json`
- status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage473_completed_preclose_full_dates_shard_extract_status_stage473_completed_preclose_full_dates_241_260_v1.csv`
- completed_minute_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage473_completed_preclose_full_dates_shard_completed_minute_bars_stage473_completed_preclose_full_dates_241_260_v1.csv`
- synthetic_preclose_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage473_completed_preclose_full_dates_shard_synthetic_preclose_bars_stage473_completed_preclose_full_dates_241_260_v1.csv`
- raw cache：`examples/portfolio_backtesting/downloaded_futures/tqsdk_stage462_completed_preclose_full_dates_shard/`

## 结论

- 本阶段结论：`plan_rank=241-260` 全日期分片全部 strict ready，且缓存复验正常。前十三个全日期分片合计 `16,990` 个缺口日期全部 strict ready。
- 是否进入下一步：进入下一步数据回补；仍不进入策略候选晋级。
- 我的晋级判断：值得晋级的是 `completed_previous_row` OHLCVOI 数据链路，不是任何收益候选。当前仍不能把 Stage103、Stage115 或其他体验候选按旧同日收盘口径晋级。
- 下一步：继续 `261-280` 等全日期分片；覆盖更多span后新增全日期聚合器，确认 Stage154 约 `21,475` 个缺口合约日键全部 strict ready，再恢复一致预收盘真实回放和3/6个月体验优化。

## 过拟合反思

- 运行前判断：否。本阶段只按 Stage154 缺口计划顺序补数据，不看收益，不调交易参数。
- 运行后判断：否。`241-260` 的结果只证明数据可得性和缓存可复验；没有根据表现筛选日期、品种或规则。
- 原因：`MAX_DATES_PER_SYMBOL=0` 覆盖所选span全部目标缺口日期，且分片按计划顺序推进。

## 继续价值反思

- 运行前判断：有价值。Stage141-153 已证明同日收盘和若干分钟成交语义不能直接晋级，必须补齐一致预收盘信息集。
- 运行后判断：仍有价值。前 `260` 个全日期span合计 `16,990` 个缺口日期全部 strict ready，说明全量回补路线稳定，下一步继续扩展比回到旧口径做短持有优化更稳健。
- 原因：只有全日期 OHLCVOI 稳定后，后续候选的3个月/6个月体验改善才可能被认定为真实可部署改进。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage173 执行约束和阶段记录索引。
- 是否更新 `research/registry.md`：否，本阶段为增量分片，未改变全线最新关键结论；等全日期聚合完成再更新总索引更合适。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、路线废弃或跨线合并；等全日期聚合/真实预收盘回放形成关键结论再追加。
