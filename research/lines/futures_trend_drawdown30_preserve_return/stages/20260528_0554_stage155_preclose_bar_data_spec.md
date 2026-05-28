# Stage155 预收盘一致回放数据规格审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 05:54 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：执行语义规格审计；不新增策略，不修改 Stage079/C3 交易规则。
- 是否重要突破：是。确认一致预收盘回放不能只补 `14:55 close/fill`，必须补完整预收盘合成日K字段。
- 是否触发A/B：否。本阶段没有产生可晋级策略版本。

## 外部调研与判断

- 参考资料：
  - ML4T execution semantics: https://ml4trading.io/docs/backtest/user-guide/execution-semantics/
  - Backtrader order execution: https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - NautilusTrader backtesting: https://nautilustrader.io/docs/latest/concepts/backtesting
  - TqSdk 1分钟K示例： https://tqsdk-python.readthedocs.io/en/latest/usage/ta.html
  - TqSdk 回测多行情序列： https://tqsdk-python.readthedocs.io/en/stable/usage/backtest.html
- 我的判断：
  - same-bar close execution 对生产部署有 look-ahead 风险；预收盘回放必须闭合信号可见时间、bar字段和成交价。
  - Stage153 的三种成交语义仍是“完整日线信号 + 预收盘成交价”，不能证明真实部署。
  - 当前策略在 `on_bars` 里先 `update_bar`，再生成信号；因此要模拟收盘前冻结，必须替换策略看到的当天bar，而不只是替换成交价。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage455_preclose_bar_data_spec.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `MODEL_TAG=stage455_preclose_bar_data_spec_v1`
  - 数据规格分为：
    - `A_fill_only_sensitivity`
    - `B_close_only_preclose_signal`
    - `C_full_preclose_daily_bar`
    - `D_confirmed_daily_signal_next_event`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage154 的 2020-01-02 至 2026-04-30 覆盖下界。
- 账户规模：不适用；本阶段不生成权益曲线。
- 成本口径：不适用；本阶段不撮合成交。
- 样本过滤：无。
- 策略/归因口径：
  - 静态扫描当前 `qmt_roll_portfolio_strategy.py` 和 `run_qmt_roll_backtest.py` 对 `BarData`、`ArrayManager`、行情 DataFrame 字段的依赖。
  - 复读 Stage154 的最低 `14:55-15:00` 覆盖率作为下界。
  - 输出可晋级/不可晋级的数据规格。

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
| 策略字段引用数 | 108 |
| 引擎字段引用数 | 5 |
| 是否依赖当前bar OHLC | 是 |
| 是否依赖 volume/open_interest | 是 |
| Stage154最低必需键 | 26,380 |
| Stage154已覆盖键 | 4,905 |
| Stage154缺口键 | 21,475 |
| Stage154最低覆盖率 | 18.5936% |
| 当前是否可晋级回放 | 否 |

字段依赖摘要：

| dependency_type | normalized_field | reference_count | function_count |
| --- | --- | ---: | ---: |
| array_manager_field | close | 2 | 2 |
| array_manager_field | high | 1 | 1 |
| array_manager_field | low | 1 | 1 |
| array_manager_field | open | 1 | 1 |
| array_manager_field | open_interest | 1 | 1 |
| array_manager_field | volume | 1 | 1 |
| bar_field | close | 52 | 27 |
| bar_field | high | 7 | 6 |
| bar_field | low | 7 | 6 |
| bar_field | open | 2 | 1 |
| history_or_dataframe_column | close | 15 | 12 |
| history_or_dataframe_column | high | 7 | 7 |
| history_or_dataframe_column | low | 7 | 7 |
| history_or_dataframe_column | open | 5 | 2 |
| history_or_dataframe_column | open_interest | 2 | 2 |
| history_or_dataframe_column | volume | 2 | 2 |

数据规格裁决：

| spec_id | 晋级允许 | 裁决 |
| --- | ---: | --- |
| `A_fill_only_sensitivity` | 0 | 只替换成交价，信号仍用完整日K，只能做敏感性审计。 |
| `B_close_only_preclose_signal` | 0 | 只替换 close 会保留 high/low/open/volume/OI 的未来字段。 |
| `C_full_preclose_daily_bar` | 1 | 唯一可用于未来晋级的预收盘一致回放规格。 |
| `D_confirmed_daily_signal_next_event` | 1 | 时间语义干净，但 Stage141-143 已显示 next-event 风险很差，只能做风险边界。 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage455_preclose_bar_data_spec_report_stage455_preclose_bar_data_spec_v1.md`
- dependency_refs：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage455_preclose_bar_data_spec_dependency_refs_stage455_preclose_bar_data_spec_v1.csv`
- dependency_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage455_preclose_bar_data_spec_dependency_summary_stage455_preclose_bar_data_spec_v1.csv`
- data_spec：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage455_preclose_bar_data_spec_data_spec_stage455_preclose_bar_data_spec_v1.csv`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage455_preclose_bar_data_spec_summary_stage455_preclose_bar_data_spec_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage455_preclose_bar_data_spec_decision_stage455_preclose_bar_data_spec_v1.json`

## 结论

- 决策标签：`full_preclose_ohlc_volume_oi_required_before_replay_no_alpha_optimization`
- 本阶段结论：当前没有策略候选晋级；唯一允许进入未来晋级回放的是 `C_full_preclose_daily_bar` 数据规格。
- 是否进入下一步：进入 Stage156 分片补数据可行性，不进入 alpha 优化。
- 下一步：
  - 用 TqBacktest 分片抽取主力合约交易日从本交易日开始至冻结时点的 1分钟K。
  - 合成预收盘日K：`open=首根可见分钟open`、`high=max(high)`、`low=min(low)`、`close=冻结时点close`、`volume=sum(volume)`、`open_interest=最后可见OI`。
  - 再把该合成bar接入 SameDayClose 引擎，成交价只能使用同一预声明窗口。

## 独立判断

- 继续优化 Stage079 的 3个月/6个月体验仍有价值，但必须先解决执行语义，否则结果会靠不可成交的日线收盘假设成立。
- 不按目标独立判断，本阶段也没有值得晋级的策略版本；值得晋级的是数据规格与执行一致性工程。
- 我不建议现在回头继续做特征补丁，因为 Stage141-155 已显示当前收益体验对成交语义极其敏感。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只做代码依赖和数据规格审计，不看收益曲线，不按结果筛参数、日期或品种；它是在减少未来回测自由度。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但方向更窄。
- 原因：3/6个月目标尚未完成，但在同日收盘口径上继续调 alpha 价值低；先完成 `C_full_preclose_daily_bar`，后续改善才有真实部署含义。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录只有完整预收盘合成日K规格可进入未来晋级。
- 是否更新 `research/registry.md`：是，本阶段改变下一步优先级。
- 是否追加根目录 `memory.md/back_log.md`：是，属于重要执行口径长期记忆。
