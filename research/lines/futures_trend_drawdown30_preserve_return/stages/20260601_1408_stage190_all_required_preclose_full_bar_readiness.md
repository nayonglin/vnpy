# Stage190 全required-key预收盘完整bar准备度审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 14:08 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行数据链路审计；不新增策略、不修改 Stage079/C3 交易规则。
- 是否重要突破：是，但属于“发现直接回放前置条件未满足”的负向突破。
- 是否触发A/B：否。没有产生可接入正式版本的新策略。

## 外部调研与判断

- 参考资料：
  - TqSdk 官方文档：`TqApi.get_kline_serial` / `TqBacktest` 回测 K 线随时间推进更新。
  - TqSdk GitHub：`shinnytech/tqsdk-python`，用于确认该路线属于逐时点 K 线推进语义，不应把最终日K直接用于冻结前决策。
  - 回测未来函数通用原则：决策时点、信号输入和成交窗口必须严格区分。
- 我的判断：
  - Stage189 证明的是 Stage154 缺口键 `21,475` 个全部可由 completed-row 方式恢复完整预收盘bar。
  - 但一致预收盘真实回放要求 Stage154 全部 `26,380` 个 required key 都能用同一套冻结前 OHLCVOI 和同一填充窗口。
  - 因此不能把“原本有 14:55-15:00 覆盖”的 `4,905` 个键自动当成完整冻结前日K；必须单独审计。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage490_all_required_preclose_full_bar_readiness.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `MIN_PRECLOSE_BAR_COUNT=200`
  - `MIN_FILL_BAR_COUNT=4`
  - `COMPLETED_RAW_ROOTS=tqsdk_stage462_completed_preclose_full_dates_shard,tqsdk_stage461_completed_preclose_full_dates_probe,tqsdk_stage459_completed_preclose_full_bar_shard`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage154 全 required key，对应 Stage079/C3 主力合约日键。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：全部 `26,380` 个 required key；Stage154 缺口键使用 Stage189 权威 synthetic 输出，Stage154 已覆盖键再用本地 completed raw cache 尝试合成。
- 策略/归因口径：只审计冻结前完整bar准备度，不运行策略收益。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - required key：`26,380`
  - strict full preclose ready：`22,509/26,380`
  - strict ready rate：`85.3260%`
  - gap：`3,871`
  - Stage154 缺口键：`21,475/21,475` ready，最少 preclose bar `220`，最少 fill bar `4`
  - Stage154 已覆盖键：`1,034/4,905` ready，ready rate `21.0805%`
  - gap 原因：`invalid_or_missing_ohlc=3,413`，`no_completed_raw_file=401`，`fill_window_missing=57`
  - 决策：`all_required_preclose_full_bar_not_ready_need_covered_key_backfill`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage490_all_required_preclose_full_bar_readiness_report_stage490_all_required_preclose_full_bar_readiness_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage490_all_required_preclose_full_bar_readiness_summary_stage490_all_required_preclose_full_bar_readiness_v1.csv`
- synthetic：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage490_all_required_preclose_full_bar_readiness_synthetic_stage490_all_required_preclose_full_bar_readiness_v1.csv`
- gap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage490_all_required_preclose_full_bar_readiness_gap_stage490_all_required_preclose_full_bar_readiness_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage490_all_required_preclose_full_bar_readiness_stage154_coverage_summary_stage490_all_required_preclose_full_bar_readiness_v1.csv`

## 结论

- 本阶段结论：
  - 不能直接进入一致预收盘真实回放。
  - Stage189 的缺口补齐结论仍然成立，但它只覆盖 Stage154 缺口键；全部 required key 还剩 `3,871` 个缺口，主要来自原本 Stage154 已覆盖 `14:55-15:00` 但没有完整冻结前 session 的键。
  - 当前没有任何策略版本晋级。若强行回放，会把一部分日K使用冻结前bar、一部分日K使用最终日K或不完整分钟窗口，结果不可用于晋级判断。
- 是否进入下一步：是。
- 下一步：
  - 先为 Stage154 已覆盖但 Stage190 不严格 ready 的 `3,871` 个键做 covered-key full-session backfill。
  - 全部 `26,380/26,380` strict ready 后，再做一致预收盘真实回放。
  - 真实回放过 Stage079 硬约束后，才恢复3个月/6个月体验优化。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只检查数据可得性与执行语义，不看收益曲线、不调参数、不筛选日期获利；`200/4` 只是防止把14:55局部窗口伪装成完整冻结前日K。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：这个审计阻止了混合数据口径进入策略回放。下一步补齐 `3,871` 个旧覆盖键有明确价值；如果不补，后续任何短持有体验优化都不具备真实可执行含义。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，Stage190 改变下一步路径。
- 是否追加根目录 `memory.md/back_log.md`：是，属于重要路线闸门修正。
