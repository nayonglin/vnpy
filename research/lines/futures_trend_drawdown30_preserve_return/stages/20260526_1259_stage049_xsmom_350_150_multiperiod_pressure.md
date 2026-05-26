# Stage049 C3 35万 + 横截面动量卫星15万多周期压力反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-26 12:59 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage048候选的多周期与滑点压力复验
- 是否重要突破：重要反证
- 是否触发A/B：是，固定 C3 50万基准 vs C3 35万 + xsmom 15万候选

## 外部调研与判断

- 参考资料：复用 Stage045 商品横截面动量调研结论；本阶段是候选反证，不新增外部资料。
- 我的判断：真正能穿越周期的低相关卫星，不能只在全样本平滑后好看；必须在不同启动年份和成本压力下保住收益保留与回撤闸门。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage349_xsmom_350_150_multiperiod_pressure.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定候选：`C3 350,000 + xsmom卫星150,000`
  - 卫星执行：`min1_cheapest_cap`
  - 起始年份窗口：`2020`、`2021`、`2022`、`2023`、`2024`、`2025`、`2026 YTD`
  - 弱窗口：`2021全年`、`2024-2025`
  - 滑点压力：`1x/2x/3x/5x`
- 修改参数：无正式参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：最长 `2020-01-01` 至 `2026-04-30`
- 账户规模：总资金 `500,000`
- 成本口径：正常成本与 `2x/3x/5x` 滑点压力
- 样本过滤：不新增品种过滤，不根据失败窗口改规则
- 策略/归因口径：与 Stage048 完全同一候选，只扩大验证面

## 结果

- 期末权益：全样本候选 `26,147,995`
- 总收益：全样本候选 `5129.5990%`
- 最大回撤：全样本候选 `-27.9488%`
- Sharpe：全样本候选 `1.7013`
- 总滑点：全样本候选 `1,278,330`
- 总交易次数：全样本候选 `1199`
- 胜率：未输出逐笔胜率
- 其他关键指标：
  - `start_2021`：收益保留 `40.6752%`，候选最大回撤 `-28.3574%`
  - `start_2022`：收益保留 `47.8951%`，候选最大回撤 `-28.9592%`
  - `start_2023`：收益保留 `51.9342%`，候选最大回撤 `-28.1713%`
  - `ytd_2026`：候选总收益 `-32.4680%`，最大回撤 `-50.5798%`
  - `weak_2021_full`：收益保留 `74.5928%`，未过80%收益保留闸门
  - `3x` 滑点：候选最大回撤恶化到 `-30.4983%`
  - `5x` 滑点：候选最大回撤恶化到 `-36.5074%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage349_xsmom_350_150_multiperiod_pressure_report_stage349_xsmom_350_150_multiperiod_pressure_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage349_xsmom_350_150_multiperiod_pressure_summary_stage349_xsmom_350_150_multiperiod_pressure_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage349_xsmom_350_150_multiperiod_pressure_combo_daily_stage349_xsmom_350_150_multiperiod_pressure_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage349_xsmom_350_150_multiperiod_pressure_decision_stage349_xsmom_350_150_multiperiod_pressure_v1.json`

## 结论

- 本阶段结论：决策标签 `fail_multiperiod_or_stress`。Stage048候选不能晋级。
- 是否进入下一步：不进入该候选的下一步。
- 下一步：停止围绕 `35万C3 + 15万xsmom期货卫星` 微调；若继续动量方向，只能换承载方式、提高卫星资金口径、或做真正独立的组合层配置。

## 过拟合反思

- 运行前判断：不是过拟合，因为固定候选做反证，不再调资金小数。
- 运行后判断：本阶段不是过拟合；继续救这个形状会过拟合。
- 原因：失败来自多个启动年份收益保留不足、2026 YTD路径显著变差、3x滑点破30，而不是单个异常点。

## 继续价值反思

- 运行前判断：有价值，因为全样本候选必须经过多周期和成本压力验证。
- 运行后判断：该候选继续价值低；总研究线仍有价值。
- 原因：横截面动量因子本身仍可能有独立价值，但当前期货卫星资金承载方式不稳，继续调该形状不符合穿越周期原则。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要反证结论
