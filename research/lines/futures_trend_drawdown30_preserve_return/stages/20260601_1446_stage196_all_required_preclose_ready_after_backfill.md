# Stage196 covered-key回补后全required-key预收盘完整bar复核

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 14:46 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行数据链路回补与全量复核；不新增策略、不修改 Stage079/C3 交易规则。
- 是否重要突破：是。Stage154 全部 required key 已达到一致预收盘真实回放的数据前置条件。
- 是否触发A/B：否。仍未产生策略候选。

## 外部调研与判断

- 参考资料：
  - TqSdk 官方 `TqBacktest` / `get_kline_serial` 文档与 GitHub 实现语义：K线在回测时间推进中更新，必须使用冻结时点前可见的已完成K线。
  - 回测防未来函数原则：信号输入、决策时点、成交窗口必须严格一致。
- 我的判断：
  - Stage190 发现的 `3,871` 个 gap 不是策略问题，而是 Stage154 原已覆盖 `14:55-15:00` 的 key 缺少完整 full-session preclose bar。
  - Stage191-195 用同一 completed-row 规则补齐 covered-key full-session；Stage196 用 Stage189 缺口 synthetic + Stage191-195 covered-key synthetic 做全量复核。
  - 现在才可以进入一致预收盘真实回放；之前如果直接回放，会混用最终日K和冻结前K线。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage491_covered_key_full_session_backfill_shard.py`
- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage490_all_required_preclose_full_bar_readiness.py`：增加 `STAGE490_*` 输出参数、额外 raw root、额外 synthetic glob 支持，避免覆盖 Stage190 历史输出。
- 删除脚本：无。
- 新增参数：
  - `STAGE491_START_SPAN`
  - `STAGE491_MAX_SPANS`
  - `STAGE491_MAX_DATES_PER_SYMBOL`
  - `STAGE490_EXTRA_COMPLETED_RAW_ROOTS`
  - `STAGE490_EXTRA_SYNTHETIC_GLOBS`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage154 全部 required key，`2020-01-02` 至 `2026-05-18`。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：全部 `26,380` 个主力合约日 key。
- 策略/归因口径：只做数据链路回补和全量复核，不运行策略收益。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - Stage191：`96/96` strict ready，0 failed/timeout
  - Stage192：`1,332/1,332` strict ready，0 failed/timeout
  - Stage193：`1,618/1,618` strict ready，0 failed/timeout
  - Stage194：`660/660` strict ready，0 failed/timeout
  - Stage195：`165/165` strict ready，0 failed/timeout
  - covered-key gap 合计：`3,871/3,871` strict ready
  - Stage196 全量复核：`26,380/26,380` strict ready，gap `0`
  - 最少 preclose bar：`220`
  - 最少 fill bar：`4`
  - 决策：`all_required_preclose_full_bar_ready_proceed_to_consistent_replay`

## 输出文件

- Stage191 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage491_covered_key_full_session_backfill_shard_report_stage491_covered_key_full_session_backfill_001_001_v1.md`
- Stage192 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage492_covered_key_full_session_backfill_shard_report_stage492_covered_key_full_session_backfill_002_020_v1.md`
- Stage193 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage493_covered_key_full_session_backfill_shard_report_stage493_covered_key_full_session_backfill_021_060_v1.md`
- Stage194 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage494_covered_key_full_session_backfill_shard_report_stage494_covered_key_full_session_backfill_061_100_v1.md`
- Stage195 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage495_covered_key_full_session_backfill_shard_report_stage495_covered_key_full_session_backfill_101_137_v1.md`
- Stage196 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage496_all_required_preclose_full_bar_after_all_backfill_report_stage496_all_required_preclose_full_bar_after_all_backfill_v1.md`
- Stage196 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage496_all_required_preclose_full_bar_after_all_backfill_summary_stage496_all_required_preclose_full_bar_after_all_backfill_v1.csv`
- Stage196 synthetic：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage496_all_required_preclose_full_bar_after_all_backfill_synthetic_stage496_all_required_preclose_full_bar_after_all_backfill_v1.csv`

## 结论

- 本阶段结论：
  - 数据前置正式通过：Stage154 全部 `26,380` 个 required key 均具备冻结前可见 OHLCVOI 和同一填充窗口。
  - 当前仍没有策略版本晋级。晋级判断必须等下一步一致预收盘真实回放，因为数据 ready 不等于收益/回撤 ready。
- 是否进入下一步：是。
- 下一步：
  - 实现一致预收盘真实回放：用 Stage196 synthetic bar 替换策略当日日K输入，并用同一 `14:55-15:00` 填充窗口成交。
  - 回放 Stage079/C3 后检查 hard gates、3个月/6个月体验和 fallback 成交/rollover 覆盖。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：只补齐固定数据链路，不看收益、不调策略、不选择获利日期；回补对象来自 Stage190 的全量 gap，不是收益驱动筛选。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：现在一致预收盘真实回放具备数据基础，下一步能回答 Stage079/C3 在真实冻结时点下是否还能过硬约束。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，属于关键数据链里程碑。
