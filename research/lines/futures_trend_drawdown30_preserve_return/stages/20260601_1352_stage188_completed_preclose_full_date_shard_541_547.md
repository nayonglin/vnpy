# Stage188 completed-row全日期预收盘bar尾部分片541-547

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 13:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：执行数据工程尾部分片验证；不新增策略、不修改 Stage079/C3 交易规则。
- 是否重要突破：是。Stage154 缺口计划 `1-547` 全日期分片层面完成，累计 `21,475/21,475` strict ready。
- 是否触发A/B：否。本阶段没有可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
  - TqSdk `TqBacktest` 文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.backtest.html`
  - TqSdk 批量回测文档：`https://doc.shinnytech.com/tqsdk/latest/advanced/backtest.html`
- 我的判断：
  - completed-row OHLCVOI 数据链路已经完成分片层面的最后缺口，下一步必须做全量聚合审计与一致预收盘真实回放，而不是立刻根据局部收益优化策略。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `STAGE459_STAGE_NAME=Stage188`
  - `STAGE459_OUTPUT_PREFIX=qmt_roll_stage488_completed_preclose_full_dates_shard`
  - `STAGE459_MODEL_TAG=stage488_completed_preclose_full_dates_541_547_v1`
  - `STAGE459_START_SPAN=541`
  - `STAGE459_MAX_SPANS=20`
  - `STAGE459_MAX_DATES_PER_SYMBOL=0`
  - `STAGE459_MAX_SECONDS_PER_SYMBOL=900`
  - `STAGE459_RAW_SUBDIR=tqsdk_stage462_completed_preclose_full_dates_shard`
  - `STAGE459_DISABLE_TQSDK_PRINT=1`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage154 缺口计划中 `plan_rank=541-547` 对应合约的全部目标缺口日期。
- 账户规模：不适用，本阶段不重放账户权益。
- 成本口径：不适用，本阶段不计算交易成本。
- 样本过滤：按 Stage154 缺口计划固定顺序取尾部 `7` 个span，不按表现筛选。
- 策略/归因口径：每个目标交易日使用交易日开始至 `14:55` 的已完成分钟K合成当日可见 `open/high/low/close/volume/open_interest`，并校验 `14:55-15:00` fill window。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：

| 指标 | 数值 |
| --- | ---: |
| 覆盖span | `541-547` |
| span数 | 7 |
| 唯一合约数 | 7 |
| 目标缺口日期 | 9 |
| strict full-bar ready | 9 |
| ready rate | 100.00% |
| failed_symbol_count | 0 |
| 已完成分钟K | 4,095 |
| 正成交量分钟K | 4,092 |
| boundary_uncertain_count | 7 |
| 最少预收盘bar数 | 220 |
| 最少填充窗口bar数 | 4 |
| 合成预收盘成交量 | 2,412,115 |
| 填充窗口成交量 | 25,727 |
| 缓存复验状态 | `cached_raw=7` |
| raw cache文件数 | 436 |

字段级复验：

| 字段 | 通过数 |
| --- | ---: |
| `valid_ohlc` | 9 |
| `volume_ok` | 9 |
| `open_interest_ok` | 9 |
| `fill_ok` | 9 |
| `full_bar_ready` | 9 |

累计进度：

| 范围 | strict ready |
| --- | ---: |
| Stage161-187 `1-540` | 21,466 |
| Stage188 `541-547` | 9 |
| 合计 `1-547` | 21,475 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage488_completed_preclose_full_dates_shard_report_stage488_completed_preclose_full_dates_541_547_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage488_completed_preclose_full_dates_shard_summary_stage488_completed_preclose_full_dates_541_547_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage488_completed_preclose_full_dates_shard_decision_stage488_completed_preclose_full_dates_541_547_v1.json`
- status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage488_completed_preclose_full_dates_shard_extract_status_stage488_completed_preclose_full_dates_541_547_v1.csv`
- completed_minute_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage488_completed_preclose_full_dates_shard_completed_minute_bars_stage488_completed_preclose_full_dates_541_547_v1.csv`
- synthetic_preclose_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage488_completed_preclose_full_dates_shard_synthetic_preclose_bars_stage488_completed_preclose_full_dates_541_547_v1.csv`

## 结论

- 本阶段结论：尾部 `plan_rank=541-547` 全部 strict ready。Stage154 缺口计划 `1-547` 分片累计 `21,475/21,475` 目标缺口日期 strict ready。
- 是否进入下一步：是，进入全量聚合审计；但不晋级任何策略候选。
- 下一步：做全量聚合确认 span/日期/字段/状态无遗漏；通过后再接一致预收盘真实回放和 Stage079 3个月/6个月体验优化。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只补尾部数据缺口，不根据收益、回撤、短持有分数反馈做任何策略选择。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：分片层面已经覆盖全部 `21,475` 个目标缺口日期，下一步聚合审计后就能推进真实一致预收盘回放，直接服务 Stage079 体验优化目标。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage188 执行约束和阶段记录索引。
- 是否更新 `research/registry.md`：聚合审计通过后再更新。
- 是否追加根目录 `memory.md/back_log.md`：聚合审计通过后作为重要数据链突破追加。
