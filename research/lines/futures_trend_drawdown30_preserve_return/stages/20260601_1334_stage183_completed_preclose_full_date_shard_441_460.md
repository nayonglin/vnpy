# Stage183 completed-row全日期预收盘bar分片441-460

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 13:34 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：执行数据工程分片验证；不新增策略、不修改 Stage079/C3 交易规则。
- 是否重要突破：否。属于 Stage161 以来的连续全日期分片推进。
- 是否触发A/B：否。本阶段没有可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
  - TqSdk `TqBacktest` 文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.backtest.html`
  - TqSdk 批量回测文档：`https://doc.shinnytech.com/tqsdk/latest/advanced/backtest.html`
- 我的判断：
  - 回测中的K线推进语义会决定冻结时点可见字段，Stage079 后续3/6个月优化必须先统一到严格 completed-row OHLCVOI 口径。
  - 当前阶段只验证数据可得性和复验稳定性，不构成策略晋级。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `STAGE459_STAGE_NAME=Stage183`
  - `STAGE459_OUTPUT_PREFIX=qmt_roll_stage483_completed_preclose_full_dates_shard`
  - `STAGE459_MODEL_TAG=stage483_completed_preclose_full_dates_441_460_v1`
  - `STAGE459_START_SPAN=441`
  - `STAGE459_MAX_SPANS=20`
  - `STAGE459_MAX_DATES_PER_SYMBOL=0`
  - `STAGE459_MAX_SECONDS_PER_SYMBOL=900`
  - `STAGE459_RAW_SUBDIR=tqsdk_stage462_completed_preclose_full_dates_shard`
  - `STAGE459_DISABLE_TQSDK_PRINT=1`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage154 缺口计划中 `plan_rank=441-460` 对应合约的全部目标缺口日期。
- 账户规模：不适用，本阶段不重放账户权益。
- 成本口径：不适用，本阶段不计算交易成本。
- 样本过滤：按 Stage154 缺口计划固定顺序取 `20` 个span，不按表现筛选。
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
| 覆盖span | `441-460` |
| span数 | 20 |
| 唯一合约数 | 20 |
| 目标缺口日期 | 231 |
| strict full-bar ready | 231 |
| ready rate | 100.00% |
| failed_symbol_count | 0 |
| 已完成分钟K | 86,715 |
| 正成交量分钟K | 86,645 |
| boundary_uncertain_count | 20 |
| 最少预收盘bar数 | 220 |
| 最少填充窗口bar数 | 4 |
| 合成预收盘成交量 | 73,040,422 |
| 填充窗口成交量 | 1,537,856 |
| 缓存复验状态 | `cached_raw=20` |
| raw cache文件数 | 406 |

字段级复验：

| 字段 | 通过数 |
| --- | ---: |
| `valid_ohlc` | 231 |
| `volume_ok` | 231 |
| `open_interest_ok` | 231 |
| `fill_ok` | 231 |
| `full_bar_ready` | 231 |

累计进度：

| 范围 | strict ready |
| --- | ---: |
| Stage161-182 `1-440` | 20,725 |
| Stage183 `441-460` | 231 |
| 合计 `1-460` | 20,956 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage483_completed_preclose_full_dates_shard_report_stage483_completed_preclose_full_dates_441_460_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage483_completed_preclose_full_dates_shard_summary_stage483_completed_preclose_full_dates_441_460_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage483_completed_preclose_full_dates_shard_decision_stage483_completed_preclose_full_dates_441_460_v1.json`
- status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage483_completed_preclose_full_dates_shard_extract_status_stage483_completed_preclose_full_dates_441_460_v1.csv`
- completed_minute_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage483_completed_preclose_full_dates_shard_completed_minute_bars_stage483_completed_preclose_full_dates_441_460_v1.csv`
- synthetic_preclose_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage483_completed_preclose_full_dates_shard_synthetic_preclose_bars_stage483_completed_preclose_full_dates_441_460_v1.csv`

## 结论

- 本阶段结论：`plan_rank=441-460` 全日期分片全部 strict ready，且缓存复验正常。前二十三个全日期分片合计 `20,956` 个缺口日期全部 strict ready。
- 是否进入下一步：是，进入后续分片；但不晋级任何策略候选。
- 下一步：继续 Stage184 `461-480`；待 Stage154 约 `21,475` 个缺口合约日键全量稳定后，再做一致预收盘真实回放和 Stage079 3个月/6个月体验优化。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只验证预声明数据规格，没有按回测表现调参、选日期或选品种。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：`1-460` 已累计 `20,956` 个缺口日期 strict ready，剩余缺口已经很少，继续补完能让后续真实回放从数据层站稳。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage183 执行约束和阶段记录索引。
- 是否更新 `research/registry.md`：否。按并行研究记录模式，普通分片不频繁修改总索引。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破或跨线合并。
