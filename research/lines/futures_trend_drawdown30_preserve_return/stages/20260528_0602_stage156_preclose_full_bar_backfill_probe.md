# Stage156 预收盘完整合成日K分片补数据探针

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 06:02 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：执行数据工程可行性探针；不新增策略、不修改 Stage079/C3 交易规则
- 是否重要突破：是。TqBacktest 小批次可抽取分钟 OHLC 与 close_oi，并能覆盖 `14:55-15:00` 填充窗口，但样本 `volume` 字段全为 0，严格 `C_full_preclose_daily_bar` 还不能进入真实回放。
- 是否触发A/B：否。没有形成新策略候选，也没有替代 Stage079/Stage103 的执行候选。

## 外部调研与判断

- 参考资料：
  - TqSdk 官方 `TqBacktest` 文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.backtest.html`
  - TqSdk 官方批量回测示例：`https://tqsdk-python.readthedocs.io/en/latest/advanced/backtest.html`
  - TqSdk 官方技术指标文档中 `CJL/OPI` 对成交量与持仓量字段的说明：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.ta.html`
- 我的判断：
  - `TqBacktest + get_kline_serial(..., 60)` 是当前账户权限下比 `DataDownloader` 更可行的历史分钟K抽取路径。
  - 但字段存在不等于字段可用。本批次 `open/high/low/close/open_oi/close_oi` 可用，`volume` 全为 0，不能直接满足 Stage155 预声明的 OHLCVOI 规格。
  - 不应为了推进回放而把 `volume` 静默设为 0 或用完整日线成交量替代；后者会引入冻结时点之后的未来信息。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage456_preclose_full_bar_backfill_probe.py`
- 修改脚本：无正式策略脚本修改；本阶段只写数据探针脚本。
- 删除脚本：无
- 新增参数：
  - `MODEL_TAG=stage456_preclose_full_bar_backfill_probe_v1`
  - `STAGE456_MAX_SPANS`
  - `STAGE456_MAX_DATES_PER_SYMBOL`
  - `STAGE456_MAX_SECONDS_PER_SYMBOL`
  - `STAGE456_SESSION_LOOKBACK_CALENDAR_DAYS`
  - `STAGE456_FREEZE_TIME=14:55`
  - `STAGE456_FILL_END_TIME=15:00`
  - `STAGE456_FORCE_REFRESH`
- 修改参数：无策略参数修改；脚本内严格要求 `preclose_volume.sum() > 0` 才判定 `volume_ok=1`。
- 删除参数：无

## 回测/归因参数

- 数据区间：从 Stage154 缺口下载计划中抽前 `2` 个 span，每个合约前 `3` 个目标交易日；覆盖目标日期 `2021-01-08/2021-01-11/2021-01-12` 与 `2023-12-08/2023-12-11/2023-12-12`。
- 账户规模：不适用；本阶段不跑交易收益。
- 成本口径：不适用；本阶段不生成订单或滑点。
- 样本过滤：`STAGE456_MAX_SPANS=2`，`STAGE456_MAX_DATES_PER_SYMBOL=3`，`STAGE456_MAX_SECONDS_PER_SYMBOL=120`。
- 策略/归因口径：只验证 Stage155 的 `C_full_preclose_daily_bar` 数据规格能否从分钟K合成：交易日开始至 `14:55` 前合成可见 `open/high/low/close/volume/open_interest`，并检查 `14:55-15:00` 成交填充窗口。

## 结果

- 期末权益：不适用；本阶段不跑策略收益。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：

| 指标 | 数值 |
| --- | ---: |
| selected_symbol_count | 2 |
| selected_target_dates | 6 |
| status_success_like_count | 2 |
| minute_bar_count | 1800 |
| full_bar_ready_count | 0 |
| full_bar_ready_rate | 0.0000 |
| boundary_uncertain_count | 2 |
| preclose_bar_count_min | 220 |
| fill_bar_count_min | 5 |

分合约抽取状态：

| 合约 | TqSdk合约 | 目标日期数 | 抽取行数 | 状态 | 耗时 |
| --- | --- | ---: | ---: | --- | ---: |
| `lh2109.DCE` | `DCE.lh2109` | 3 | 675 | `extracted` | 2.97s |
| `lc2407.GFEX` | `GFEX.lc2407` | 3 | 1125 | `extracted` | 3.77s |

字段可用性：

- `valid_ohlc=1`：6/6。
- `open_interest_ok=1`：6/6。
- `fill_ok=1`：6/6。
- `volume_ok=1`：0/6；诊断显示两个合约共 `1800` 根分钟K的 `volume min/max/sum` 均为 `0`。
- 因此 strict `full_bar_ready=1`：0/6。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage456_preclose_full_bar_backfill_probe_report_stage456_preclose_full_bar_backfill_probe_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage456_preclose_full_bar_backfill_probe_summary_stage456_preclose_full_bar_backfill_probe_v1.csv`
- targets：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage456_preclose_full_bar_backfill_probe_selected_targets_stage456_preclose_full_bar_backfill_probe_v1.csv`
- status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage456_preclose_full_bar_backfill_probe_extract_status_stage456_preclose_full_bar_backfill_probe_v1.csv`
- minute_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage456_preclose_full_bar_backfill_probe_minute_bars_stage456_preclose_full_bar_backfill_probe_v1.csv`
- synthetic_preclose_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage456_preclose_full_bar_backfill_probe_synthetic_preclose_bars_stage456_preclose_full_bar_backfill_probe_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage456_preclose_full_bar_backfill_probe_decision_stage456_preclose_full_bar_backfill_probe_v1.json`
- raw_cache：
  - `examples/portfolio_backtesting/downloaded_futures/tqsdk_stage456_preclose_full_bar_probe/DCE/lh2109_minute_backtest.csv`
  - `examples/portfolio_backtesting/downloaded_futures/tqsdk_stage456_preclose_full_bar_probe/GFEX/lc2407_minute_backtest.csv`

## 结论

- 本阶段结论：`full_preclose_bar_backfill_probe_partial_need_calendar_or_more_data`。
- 是否进入下一步：进入数据/物料性下一步，不进入策略候选晋级。
- 下一步：
  - Stage157 优先审计分钟 `volume` 的替代来源，或确认 TqBacktest 对历史过期合约分钟 `volume` 为 0 的原因。
  - 同时审计 Stage079 当前配置中 `volume/open_interest` 字段的实际物料性：若这些字段在 Stage079 真实路径中没有触发任何决策分支，才可以讨论降级为 `C_full_preclose_OHLC_OI`；否则必须找到真实冻结时点前的分钟成交量源。
  - 在上述问题解决前，不做全量 `547` span 补数，也不回到同日收盘口径继续优化 3个月/6个月体验。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只验证外部分钟K能否合成预收盘可见日K，没有筛选收益、日期、品种，也没有调整 Stage079/C3 的交易逻辑。把 `volume` 全0判为失败，是反过拟合约束的一部分。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有价值，但方向必须更窄。
- 原因：OHLC/OI 与填充窗口可用说明数据通路不是死路；`volume` 全0暴露了真实回放前必须解决的字段风险。继续做 Stage157 有价值，继续做 alpha 补丁或按收益挑成交语义价值低。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage156 后的执行约束。
- 是否更新 `research/registry.md`：是，最新关键阶段从 Stage155 更新为 Stage156。
- 是否追加根目录 `memory.md/back_log.md`：是。本阶段是执行口径数据工程的重要里程碑，应追加长期记忆与总账摘要。
