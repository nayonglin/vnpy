# Stage189 completed-row全日期聚合审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 13:55 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据链路全量聚合审计；不新增策略、不修改 Stage079/C3 交易规则。
- 是否重要突破：是。Stage154 全部缺口键 `21,475/21,475` 完成 strict ready 聚合确认。
- 是否触发A/B：否。本阶段没有可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
  - TqSdk `TqBacktest` 文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.backtest.html`
  - TqSdk 批量回测文档：`https://doc.shinnytech.com/tqsdk/latest/advanced/backtest.html`
- 我的判断：
  - TqSdk 回测推进下的K线完成语义已被 Stage158-189 连续验证；`completed_previous_row` 可支撑冻结时点可见 OHLCVOI 聚合。
  - 本阶段完成的是数据可得性前置，不是策略 alpha 晋级。下一步应进入一致预收盘真实回放，再按 Stage079 硬约束和3/6个月体验目标评估策略候选。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage489_completed_preclose_full_dates_aggregate.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `MODEL_TAG=stage489_completed_preclose_full_dates_001_547_v1`
  - `OUTPUT_PREFIX=qmt_roll_stage489_completed_preclose_full_dates_aggregate`
  - 对比基准：`qmt_roll_stage454_preclose_signal_bar_data_readiness_required_keys_stage454_preclose_signal_bar_data_readiness_v1.csv`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage154 缺口计划全部 `plan_rank=1-547`。
- 账户规模：不适用，本阶段不重放账户权益。
- 成本口径：不适用，本阶段不计算交易成本。
- 样本过滤：聚合 Stage161-188 的全部全日期分片，不按收益/回撤筛选。
- 策略/归因口径：对每个 Stage154 缺口键验证 completed-row 合成预收盘完整bar是否具备 `open/high/low/close/volume/open_interest` 与同窗口 fill 数据。

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
| 分片数 | 28 |
| 覆盖span | `1-547` |
| 唯一span数 | 547 |
| 缺失span数 | 0 |
| 额外span数 | 0 |
| Stage154缺口键 | 21,475 |
| 已选择目标键 | 21,475 |
| strict full-bar ready | 21,475 |
| ready rate | 100.00% |
| required_missing_not_selected | 0 |
| selected_not_required_missing | 0 |
| duplicate_target_count | 0 |
| duplicate_synthetic_count | 0 |
| failed_symbol_count | 0 |
| timeout_count | 0 |
| 唯一合约数 | 455 |
| 唯一产品数 | 19 |
| 状态分布 | `cached_raw=543` |
| 已完成分钟K | 7,510,695 |
| 正成交量分钟K | 7,507,270 |
| 最少预收盘bar数 | 220 |
| 最少填充窗口bar数 | 4 |
| 合成预收盘成交量 | 11,196,387,379 |
| 填充窗口成交量 | 243,292,351 |

字段级复验：

| 字段 | 通过数 |
| --- | ---: |
| `valid_ohlc` | 21,475 |
| `volume_ok` | 21,475 |
| `open_interest_ok` | 21,475 |
| `fill_ok` | 21,475 |
| `full_bar_ready` | 21,475 |

决策：

`completed_preclose_full_dates_all_required_keys_ready_proceed_to_consistent_preclose_replay`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage489_completed_preclose_full_dates_aggregate_report_stage489_completed_preclose_full_dates_001_547_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage489_completed_preclose_full_dates_aggregate_summary_stage489_completed_preclose_full_dates_001_547_v1.csv`
- shard_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage489_completed_preclose_full_dates_aggregate_shard_summary_stage489_completed_preclose_full_dates_001_547_v1.csv`
- span_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage489_completed_preclose_full_dates_aggregate_span_summary_stage489_completed_preclose_full_dates_001_547_v1.csv`
- status_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage489_completed_preclose_full_dates_aggregate_status_summary_stage489_completed_preclose_full_dates_001_547_v1.csv`
- target_gap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage489_completed_preclose_full_dates_aggregate_target_gap_stage489_completed_preclose_full_dates_001_547_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage489_completed_preclose_full_dates_aggregate_decision_stage489_completed_preclose_full_dates_001_547_v1.json`

## 结论

- 本阶段结论：Stage154 全部 `21,475` 个缺口合约日键已完成 completed-row 预收盘完整bar strict ready 聚合确认。
- 是否进入下一步：是，进入一致预收盘真实回放。
- 下一步：用这些合成bar替换 Stage079/C3 在冻结时点看到的当日日K字段，并使用同一预声明成交窗口回放；只有真实回放满足硬约束后，才恢复3个月/6个月体验优化。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：聚合审计只验证固定缺口计划和字段完整性，没有使用收益、回撤或短持有分数做选择。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，且价值更高。
- 原因：数据可得性前置已经通过，可以结束旧同日收盘口径争论，进入真正可部署的预收盘一致回放。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage189 执行约束和阶段记录索引。
- 是否更新 `research/registry.md`：是，作为数据链重要突破更新当前研究线状态和下一步。
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要突破追加摘要。
