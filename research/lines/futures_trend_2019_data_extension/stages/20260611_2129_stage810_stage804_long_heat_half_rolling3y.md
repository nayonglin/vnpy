# Stage810 Stage804 多头 heat 半平仓滚动三年验证

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-11 21:29 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：研究验证、滚动三年多周期回测
- 是否重要突破：否。它回答了 heat 不全平是否可替代 Stage804 的问题，但不构成升级候选。
- 是否触发A/B：否。未接入正式候选，不改正式配置。

## 外部调研与判断

- 参考资料：
  - Concretum Group：趋势跟随仓位管理、vol targeting、pyramiding 的风险收益权衡。
  - Quantpedia：稳健趋势跟随系统设计，强调多市场、多周期、端点外验证。
  - Investopedia：仓位 sizing 与单笔风险控制基础。
  - GitHub `amstrdm/mlm-trend-following`、`chrism2671/PyTrendFollow`：趋势跟随组合实现参考。
  - GitHub `kernc/backtesting.py` partial exits issue：部分平仓在回测实现中需要明确持仓层和成交口径。
- 我的判断：趋势系统不能系统性剪掉右尾赢家，但热度降杠杆也不是可以简单关闭的“噪音风控”。本阶段只测一个预声明结构：多头 heat 触发时不全平，而是单次减半；不扫 `30/50/70`，避免围绕 2025 右尾过拟合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage810_stage804_long_heat_half_rolling3y.py`
- 修改脚本：无正式策略脚本修改；新增研究 wrapper `QmtRollPortfolioStrategyLongHeatHalfDeleverage`。
- 删除脚本：无。
- 新增参数：
  - `long_heat_partial_deleverage_ratio=0.50`
  - `long_heat_partial_deleverage_skip_one_lot=True`
- 修改参数：
  - Stage804 多头 `long_risk_cluster_heat_deleverage` 从触发后全平 heat 层，改成同一持仓只执行一次 `50%` 减仓。
  - 1 手多头不减仓，避免减仓后归零。
  - 空头 heat 降杠杆保持原逻辑不变。
- 删除参数：无。

## 回测/归因参数

- 数据区间：完整三年滚动窗口，起点 `2018-01` 到 `2023-05`，共 `65` 个窗口；每个窗口结束日为 `start + 3 years - 1 day`，不固定到 2026-05。
- 账户规模：沿用 Stage804/Stage777 研究口径，初始资金 `500,000`。
- 成本口径：沿用现有回测成本、滑点和合约乘数口径。
- 样本过滤：只统计完整三年窗口。
- 策略/归因口径：
  - 基础为 Stage804：Stage777 + 多头更紧初始止损。
  - AM41、旧正式 AI 老师、OI 命中恢复风险资金到 `0.8`、不命中基础等效 `0.4`。
  - 关闭连败缩放和 recovery sleeve。
  - 本阶段只改多头 heat 去杠杆动作为单次减半。

## 结果

- 期末权益：窗口期末权益中位数 `3,608,550`
- 总收益：收益中位数 `621.710%`；p10 `77.9928%`；最小 `33.761%`；最大 `2572.982%`
- 最大回撤：回撤中位数 `-39.4923%`；最差 `-57.6596%`
- Sharpe：中位数 `1.6167`；p10 `0.7159`
- 总滑点：合计 `17,055,825`；窗口中位 `164,950`
- 总交易次数：合计 `17,722`；窗口中位 `293`
- 胜率：非零日胜率中位数 `53.7129%`
- 其他关键指标：
  - 正收益窗口 `65/65`
  - DD30 失败 `48/65`
  - DD40 失败 `30/65`
  - DD50 失败 `20/65`
  - DD60 失败 `0/65`
  - 多头 heat 半平仓触发 `288` 次，合计减仓 `13,929` 手。
  - 多头 heat 全平触发 `0` 次。
  - 空头 heat 平仓触发 `25` 次。
  - vs Stage804：收益胜出 `14/65`，回撤胜出 `14/65`；收益中位差 `-78.31pp`，回撤中位差 `-1.4474pp`；DD50 失败从 Stage804 的 `6/65` 增至 `20/65`。
  - vs Stage806：收益胜出 `46/65`，回撤胜出 `46/65`；收益中位差 `+35.684pp`，回撤中位差 `+1.7176pp`；DD50 失败从 Stage806 的 `28/65` 降至 `20/65`，DD60 从 `6/65` 降至 `0/65`。
  - 对 Stage804 改善最明显的是 2023 起点，例如 `2023-02` 收益高 `+212.309pp`，回撤改善 `+6.8576pp`。
  - 对 Stage804 恶化最明显的是 2019/2020 穿 2022 的窗口，例如 `2020-07` 收益低 `-465.058pp`，回撤恶化 `-8.4983pp`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage810_stage804_long_heat_half_rolling3y_report_stage810_stage804_long_heat_half_rolling3y_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage810_stage804_long_heat_half_rolling3y_summary_stage810_stage804_long_heat_half_rolling3y_v1.csv`
- orders：无单独订单文件；本阶段使用 trade events 统计 heat 半平仓。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage810_stage804_long_heat_half_rolling3y_curves_stage810_stage804_long_heat_half_rolling3y_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage810_stage804_long_heat_half_rolling3y_comparison_vs_stage804_806_stage810_stage804_long_heat_half_rolling3y_v1.csv`
- 图表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage810_stage804_long_heat_half_rolling3y_return_heatmap_stage810_stage804_long_heat_half_rolling3y_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage810_stage804_long_heat_half_rolling3y_dd_heatmap_stage810_stage804_long_heat_half_rolling3y_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage810_stage804_long_heat_half_rolling3y_selected_equity_curves_stage810_stage804_long_heat_half_rolling3y_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage810_stage804_long_heat_half_rolling3y_return_delta_vs_stage804_heatmap_stage810_stage804_long_heat_half_rolling3y_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage810_stage804_long_heat_half_rolling3y_dd_delta_vs_stage804_heatmap_stage810_stage804_long_heat_half_rolling3y_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage810_stage804_long_heat_half_rolling3y_return_delta_vs_stage806_heatmap_stage810_stage804_long_heat_half_rolling3y_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage810_stage804_long_heat_half_rolling3y_dd_delta_vs_stage806_heatmap_stage810_stage804_long_heat_half_rolling3y_v1.png`

## 结论

- 本阶段结论：Stage810 不升级为候选。它比 Stage806 的“多头 heat 完全关闭”稳健，说明 heat 去杠杆是有效风控；但它明显弱于 Stage804 的“多头 heat 全平”，说明简单平一半不能替代原 heat 防守。
- 是否进入下一步：不沿着 `50%` 半平仓继续推广，也不继续扫比例。
- 下一步：若继续研究，只能做更有结构含义的 heat 规则，例如“盈利且趋势确认的持仓只减半，亏损或未确认趋势仍全平”，或者把 sizing 风险距离与 heat 风控距离解耦；不能围绕 2025 年 jm/si 右尾做补丁。

## 过拟合反思

- 运行前判断：过拟合风险低到中等。低是因为本次只测固定 `50%`、不按年份/品种/阈值优化；中等是因为动机来自 Stage804 在 2025 年右尾被全平的问题。
- 运行后判断：本阶段没有明显过拟合，但继续扫半平比例会变成过拟合。
- 原因：结果呈现清晰的跨周期 trade-off。2023 起点确实改善，2019/2020/2021 穿 2022 的坏路径显著变差。这个形状不是一个可穿越周期的优势，而是用一部分坏尾部风险换一部分右尾参与权。

## 继续价值反思

- 运行前判断：有价值。它验证“全平是不是太强”的关键机制问题。
- 运行后判断：Stage810 这个具体形态无继续推广价值；但 heat 风控如何避免错杀右尾仍有研究价值。
- 原因：半平仓能证明二元全平/不平之间存在中间地带，但固定 50% 没有足够解释力，不能同时保护 2022 坏路径和 2025 右尾。

## 合入建议

- 是否更新本线 `LINE.md`：否，暂不改变研究线主状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 摘要；不追加 `memory.md`。
