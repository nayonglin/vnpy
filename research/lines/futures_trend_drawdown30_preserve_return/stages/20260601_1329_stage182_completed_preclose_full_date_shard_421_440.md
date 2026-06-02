# Stage182 completed-row全日期预收盘bar分片421-440

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 13:29 CST
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
  - TqSdk 回测中 K线/quote 推进语义会直接影响冻结时点可见数据，不能继续用同日收盘或未完成 rolling row 口径解释 Stage079/Stage103 的真实部署表现。
  - 当前最有价值的不是策略参数晋级，而是把 `completed_previous_row` 的严格 OHLCVOI 数据链路补到全量缺口，后续再做一致预收盘真实回放与3个月/6个月持有体验优化。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `STAGE459_STAGE_NAME=Stage182`
  - `STAGE459_OUTPUT_PREFIX=qmt_roll_stage482_completed_preclose_full_dates_shard`
  - `STAGE459_MODEL_TAG=stage482_completed_preclose_full_dates_421_440_v1`
  - `STAGE459_START_SPAN=421`
  - `STAGE459_MAX_SPANS=20`
  - `STAGE459_MAX_DATES_PER_SYMBOL=0`
  - `STAGE459_MAX_SECONDS_PER_SYMBOL=900`
  - `STAGE459_RAW_SUBDIR=tqsdk_stage462_completed_preclose_full_dates_shard`
  - `STAGE459_DISABLE_TQSDK_PRINT=1`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage154 缺口计划中 `plan_rank=421-440` 对应合约的全部目标缺口日期。
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
| 覆盖span | `421-440` |
| span数 | 20 |
| 唯一合约数 | 18 |
| 目标缺口日期 | 265 |
| strict full-bar ready | 265 |
| ready rate | 100.00% |
| failed_symbol_count | 0 |
| 已完成分钟K | 126,270 |
| 正成交量分钟K | 126,204 |
| boundary_uncertain_count | 18 |
| 最少预收盘bar数 | 220 |
| 最少填充窗口bar数 | 4 |
| 合成预收盘成交量 | 123,827,695 |
| 填充窗口成交量 | 1,957,728 |
| 缓存复验状态 | `cached_raw=18` |
| raw cache文件数 | 391 |

字段级复验：

| 字段 | 通过数 |
| --- | ---: |
| `valid_ohlc` | 265 |
| `volume_ok` | 265 |
| `open_interest_ok` | 265 |
| `fill_ok` | 265 |
| `full_bar_ready` | 265 |

累计进度：

| 范围 | strict ready |
| --- | ---: |
| Stage161-181 `1-420` | 20,460 |
| Stage182 `421-440` | 265 |
| 合计 `1-440` | 20,725 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage482_completed_preclose_full_dates_shard_report_stage482_completed_preclose_full_dates_421_440_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage482_completed_preclose_full_dates_shard_summary_stage482_completed_preclose_full_dates_421_440_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage482_completed_preclose_full_dates_shard_decision_stage482_completed_preclose_full_dates_421_440_v1.json`
- status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage482_completed_preclose_full_dates_shard_extract_status_stage482_completed_preclose_full_dates_421_440_v1.csv`
- completed_minute_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage482_completed_preclose_full_dates_shard_completed_minute_bars_stage482_completed_preclose_full_dates_421_440_v1.csv`
- synthetic_preclose_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage482_completed_preclose_full_dates_shard_synthetic_preclose_bars_stage482_completed_preclose_full_dates_421_440_v1.csv`

## 结论

- 本阶段结论：`plan_rank=421-440` 全日期分片全部 strict ready，且缓存复验正常。前二十二个全日期分片合计 `20,725` 个缺口日期全部 strict ready。
- 是否进入下一步：是，进入后续分片；但不晋级任何策略候选。
- 下一步：继续 Stage183 `441-460`；待 Stage154 约 `21,475` 个缺口合约日键全量稳定后，再做一致预收盘真实回放和 Stage079 3个月/6个月体验优化。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只验证预声明数据规格的可获得性和缓存可复验，没有按收益、回撤或短持有体验选择品种/日期/参数。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：`1-440` 已累计 `20,725` 个缺口日期 strict ready，距离 Stage154 约 `21,475` 个缺口合约日键只剩最后几段；继续补完比在旧同日收盘口径上做 alpha 补丁更能接近可部署优化。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage182 执行约束和阶段记录索引。
- 是否更新 `research/registry.md`：否。按并行研究记录模式，普通分片不频繁修改总索引。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破或跨线合并。
