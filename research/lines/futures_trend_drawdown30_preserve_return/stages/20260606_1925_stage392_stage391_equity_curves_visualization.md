# Stage392 Stage387-391 资金曲线可视化

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-06 19:25 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：按用户要求，把 Stage391 关闭 AI 后放宽空头 case 的 A/C/C2，以及 Stage387-391 关键对照版本绘制资金曲线和回撤曲线。
- 是否重要突破：否。该阶段是可视化与复核，不是新策略或新回测。
- 是否触发A/B：否。只使用已生成的 Stage675-679 `curves/summary` CSV，不新增策略候选。

## 外部调研与判断

- 参考资料：本阶段未新增外部调研；沿用 Stage390/Stage391 已记录的 AQR 趋势跟踪和 `pysystemtrade` 风险/分散化判断。
- 我的判断：资金曲线可视化是必要复核，因为表格指标容易掩盖路径问题。当前图形清楚显示 Stage391 C 的路径弱于 Stage390 C，也远弱于 Stage387 固定四品种 C；Stage391 C2 虽然后段收益抬升，但全周期仍有 DD30 失败和成本压力。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/plot_stage391_no_ai_short_cases_equity_curves.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无交易参数；新增绘图输出目录 `examples/portfolio_backtesting/backtest_outputs/stage391_equity_plots/`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage675-679 已生成曲线，主图为 `full_2020_20260430`；另绘制 Stage391 C 的独立窗口 rebased NAV。
- 账户规模：`500,000`，沿用原回测结果。
- 成本口径：沿用原回测正常成本曲线，并在图例保留收益、最大回撤和 Sharpe。
- 样本过滤：不新增过滤；Stage390/391 no-AI 曲线仍为 `enable_ai_product_pool_filter=False`。
- 策略/归因口径：
  - Stage391 A/C/C2 全量资金曲线与回撤。
  - Stage390 vs Stage391 no-AI 全量 case 对照。
  - Stage387-391 主口径 C 对照。
  - Stage387-391 各阶段全量 case 分面图。
  - Stage391 C 各独立窗口 rebased NAV。

## 结果

- 期末权益：未新增回测结果；指标快照复用 Stage675-679 summary。
- 总收益：未新增回测结果。
- 最大回撤：未新增回测结果。
- Sharpe：未新增回测结果。
- 总滑点：未新增回测结果。
- 总交易次数：未新增回测结果。
- 胜率：未新增回测结果。
- 其他关键指标：
  - Stage391 C 图形路径显示长期低位震荡，最终 `601,605/20.3210%/-52.3961%/Sharpe0.2589`。
  - Stage391 C2 在 2025-2026 明显抬升，但仍为 `3,465,220/593.0440%/-33.5078%/Sharpe1.0047`，未过 DD30。
  - Stage387 C 仍是本组可视化里最干净的主口径路径：`4,634,210/826.8420%/-25.3045%/Sharpe1.3707`。

## 输出文件

- plot manifest：`examples/portfolio_backtesting/backtest_outputs/stage391_equity_plots/stage391_equity_plot_manifest.csv`
- metrics snapshot：`examples/portfolio_backtesting/backtest_outputs/stage391_equity_plots/stage387_to_391_full_window_metrics_snapshot.csv`
- Stage391 全 case：`examples/portfolio_backtesting/backtest_outputs/stage391_equity_plots/stage391_no_ai_short123_all_cases_full_equity_dd.png`
- Stage390 vs Stage391 no-AI：`examples/portfolio_backtesting/backtest_outputs/stage391_equity_plots/stage390_vs_stage391_no_ai_all_cases_full_nav_dd.png`
- Stage387-391 主口径 C：`examples/portfolio_backtesting/backtest_outputs/stage391_equity_plots/stage387_to_391_target_c_full_nav_dd.png`
- Stage387-391 分面：`examples/portfolio_backtesting/backtest_outputs/stage391_equity_plots/stage387_to_391_all_cases_full_nav_facets.png`
- Stage391 C 分窗口：`examples/portfolio_backtesting/backtest_outputs/stage391_equity_plots/stage391_c_all_windows_rebased_nav.png`

## 结论

- 本阶段结论：`stage391_equity_curves_visualized_no_new_promotion`。
- 是否进入下一步：不进入正式、不 A/B、不改策略。
- 下一步：若继续，只做只读归因，拆分 `short_case2/3` 对 C2 后段抬升和 C 主口径恶化的风险槽冲突贡献；不做 case、年份、品种或月份筛选优化。

## 过拟合反思

- 运行前判断：否。绘制资金曲线是结果复核，不是调参。
- 运行后判断：否。图形只暴露路径结构，没有新增选择规则。
- 原因：可视化没有用图形结果反向修改策略；它反而强化了不要按单个窗口救 Stage391 的约束。

## 继续价值反思

- 运行前判断：有价值。资金曲线能直接回答 Stage391 到底是平滑变差、后期变好还是全程噪声。
- 运行后判断：有价值但仅限归因。Stage391 C2 的后期抬升值得解释，Stage391 C 主口径不值得继续优化。
- 原因：图形显示主口径 C 与 Stage387 的差距不是单个尾部窗口造成的，而是长期路径质量不够；C2 的好处依赖更高并发和成本暴露，不能直接推广。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage392 可视化状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
