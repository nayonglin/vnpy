# Stage158 已完成分钟K volume语义探针

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 06:18 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据抽取语义校验；不新增策略、不修改 Stage079/C3 交易规则
- 是否重要突破：是。Stage156 的 `volume=0` 阻断被修正为“滚动未完成K线抽取语义问题”，而不是 TqBacktest 分钟成交量源完全不可用。
- 是否触发A/B：否。没有形成新策略候选，也不接入正式版本。

## 外部调研与判断

- 参考资料：
  - TqSdk `get_kline_serial` 官方字段文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html`
  - TqSdk `TqBacktest` 官方说明：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html`
  - xtquant `get_market_data_ex/download_history_data` 文档：`https://zsrl.github.io/xtquant-doc/xtquant/xtdata.html`
- 我的判断：
  - TqSdk 官方文档显示分钟K本应包含 `volume/open_oi/close_oi`，tick 序列也有当日累计 `volume/open_interest`；因此 Stage156 的 `volume=0` 不应直接解释为数据源必然不可用。
  - `get_kline_serial` 是动态序列。分钟切换时，最后一根K可能是刚生成的未完成K，成交量天然可能为0；一致回放需要使用上一根已完成K。
  - 本阶段验证后，下一步应优先修正抽取语义并扩大分片，而不是立即转向外部付费数据源。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage458_completed_kline_volume_probe.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无
- 新增参数：
  - `MODEL_TAG=stage458_completed_kline_volume_probe_v1`
  - `STAGE458_MAX_SPANS`
  - `STAGE458_MAX_DATES_PER_SYMBOL`
  - `STAGE458_MAX_SECONDS_PER_SYMBOL`
  - `STAGE458_SESSION_LOOKBACK_CALENDAR_DAYS`
  - `STAGE458_FREEZE_TIME=14:55`
  - `STAGE458_FILL_END_TIME=15:00`
  - `capture_mode=rolling_last_row/completed_previous_row`
- 修改参数：无策略参数修改。
- 删除参数：无

## 回测/归因参数

- 数据区间：从 Stage154 缺口下载计划前 `10` 个 span 抽样，每个合约取前 `5` 个目标日。
- 账户规模：不涉及权益回测；仍以 Stage079 `50万C3下单 + 11.5万外部现金` 为唯一后续 baseline。
- 成本口径：不涉及成交成本回测。
- 样本过滤：没有按收益筛样本；只按 Stage154 缺口计划顺序取前 `10` 个合约。
- 策略/归因口径：
  - `rolling_last_row`：沿用 Stage156 的滚动最后一根K抽取语义。
  - `completed_previous_row`：分钟切换时取上一根已完成K，避免拿到刚生成的未完成K。

## 结果

| capture_mode | 合约数 | 目标日 | 分钟K数 | 正成交量分钟K | strict ready | ready rate | 合成成交量合计 | 填充窗口成交量合计 | 最少预收盘bar | 最少填充bar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| completed_previous_row | 10 | 50 | 17,730 | 17,585 | 50 | 100.0000% | 32,510,157 | 824,894 | 220 | 4 |
| rolling_last_row | 10 | 50 | 17,730 | 0 | 0 | 0.0000% | 0 | 0 | 220 | 5 |

- 期末权益：不适用。本阶段不跑策略权益。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - `completed_previous_row`：`full_bar_ready_count=50/50`。
  - `rolling_last_row`：`full_bar_ready_count=0/50`。
  - 10个抽样合约全部成功抽取，单合约耗时约 `3.17s-6.59s`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage458_completed_kline_volume_probe_report_stage458_completed_kline_volume_probe_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage458_completed_kline_volume_probe_summary_stage458_completed_kline_volume_probe_v1.csv`
- status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage458_completed_kline_volume_probe_extract_status_stage458_completed_kline_volume_probe_v1.csv`
- probe_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage458_completed_kline_volume_probe_probe_bars_stage458_completed_kline_volume_probe_v1.csv`
- synthetic_compare：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage458_completed_kline_volume_probe_synthetic_compare_stage458_completed_kline_volume_probe_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage458_completed_kline_volume_probe_decision_stage458_completed_kline_volume_probe_v1.json`

## 结论

- 本阶段结论：`completed_kline_volume_unblocks_strict_ohlcvoi_probe_extend_stage156_fix`。
- 是否进入下一步：进入数据工程下一步，不进入策略候选晋级。
- 不按目标的独立判断：
  - 本阶段仍不晋级任何策略版本，因为没有产生权益候选。
  - 但本阶段恢复了严格 `C_full_preclose_daily_bar` 路线的可行性：Stage156 的 `volume=0` 不是绝对数据阻断，而是应改为完成K线抽取。
  - 现在不应该转向外部数据采购或同日收盘alpha补丁；更合理路径是修正 Stage156 抽取语义，按分片扩大到 Stage154 的 `547` 个 span，再做一致预收盘真实回放。
- 下一步：
  - 新建或修正预收盘完整bar回补脚本，统一使用 `completed_previous_row`。
  - 先按 `20-60` 个 span 分片验证覆盖、边界日、夜盘/日盘品种差异，再决定是否跑全量 `547` span。
  - 完整 OHLCVOI 数据链路稳定后，才恢复 Stage079/Stage103 的3个月/6个月体验优化。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只比较同一数据源的K线完成语义，没有筛收益窗口、没有调交易参数、没有按指标选择曲线；结论是修正数据工程路径。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值且价值提高。
- 原因：它推翻了“必须先找外部分钟volume源”的悲观判断，给严格预收盘一致回放提供了可执行路径。继续做全量分片和真实回放比继续在同日收盘口径上扫3/6个月补丁更有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage158 后的执行约束。
- 是否更新 `research/registry.md`：是，最新关键阶段从 Stage157 更新为 Stage158。
- 是否追加根目录 `memory.md/back_log.md`：是。本阶段改变了后续数据工程方向，属于重要突破摘要。
