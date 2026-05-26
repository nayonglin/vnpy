# Stage052 C3原路径 + xsmom overlay + 3万外部现金多周期反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 13:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage051固定候选的多周期、弱窗口和滑点压力反证
- 是否重要突破：重要反证
- 是否触发A/B：否；候选未通过多周期闸门，不进入正式 A/B

## 外部调研与判断

- 参考资料：沿用本线前置调研，商品趋势/动量可参考时间序列动量、波动缩放和非对称尾部风险研究；本阶段不新增外部资料。
- 我的判断：Stage051 的全样本结果只说明“该承载方式可能改善全周期账户口径”，但若多起点和滑点压力不稳，就不能视为穿越周期候选。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage352_xsmom_overlay_cash_multiperiod.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定候选：C3 50万原交易路径 + `min1_all_no_cap` xsmom overlay + 3万外部现金。
  - 账户口径：C3路径 `500,000` + 外部现金 `30,000`，账户权益口径 `530,000`。
  - 多周期窗口：`start_2020/start_2021/start_2022/start_2023/start_2024/start_2025/ytd_2026/weak_2021_full/phase_2024_2025`。
  - 滑点压力：`1x/2x/3x`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30，并按多个起点/弱窗口切分。
- 账户规模：C3按50万原路径；候选账户口径加3万外部现金。
- 成本口径：C3真实引擎原成本；xsmom整数手数overlay按 Stage346 合成成本；滑点压力为1x/2x/3x。
- 样本过滤：不筛品种、不改AI池、不改C3入场/出场。
- 策略/归因口径：C3每个窗口重新跑真实回测引擎；xsmom从窗口起点重新合成整数手数overlay。

## 结果

- 期末权益：`31,824,920`
- 总收益：`5904.7019%`
- 最大回撤：`-29.8729%`
- Sharpe：`1.6848`
- 总滑点：`1,566,700`
- 总交易次数：约 `1,207`
- 胜率：本阶段组合overlay没有统一成交级胜率口径；C3基准交易胜率沿用前置 C3 约 `45.3826%`
- 其他关键指标：
  - 全周期相对 C3 收益保留：`97.0349%`
  - 全周期最大保证金/权益：`99.6410%`
  - `start_2021`：候选收益 `5615.7670%`，最大回撤 `-30.0693%`，未过30%闸门。
  - `start_2022`：候选收益 `786.5283%`，最大回撤 `-33.0820%`，未过30%闸门。
  - `start_2024`：候选收益 `281.6311%`，最大回撤 `-31.7406%`，reject days `2`。
  - `start_2025`：候选收益 `233.9425%`，最大回撤 `-32.3720%`。
  - `ytd_2026`：候选收益 `-17.7566%`，最大回撤 `-53.1548%`。
  - `phase_2024_2025`：候选收益 `323.0934%`，最大回撤 `-29.8849%`，但 reject days `2`。
  - 2x滑点下全周期最大回撤 `-31.3158%`，reject days `2`。
  - 3x滑点下全周期最大回撤 `-33.8868%`，reject days `6`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage352_xsmom_overlay_cash_multiperiod_report_stage352_xsmom_overlay_cash_multiperiod_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage352_xsmom_overlay_cash_multiperiod_summary_stage352_xsmom_overlay_cash_multiperiod_v1.csv`
- orders：无统一订单文件；C3真实引擎与xsmom日级合成分别在阶段输出中体现。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage352_xsmom_overlay_cash_multiperiod_combo_daily_stage352_xsmom_overlay_cash_multiperiod_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage352_xsmom_overlay_cash_multiperiod_decision_stage352_xsmom_overlay_cash_multiperiod_v1.json`

## 结论

- 本阶段结论：决策 `fail_multiperiod_or_stress`。Stage051 的 `min1_all_no_cap + 3万外部现金` 只在全周期和少数起点好看，不能稳定把多周期最大回撤压入30以内，也无法通过2x/3x滑点压力。
- 是否进入下一步：该候选不进入下一步；停止围绕 `3万` 外部现金和 `min1_all_no_cap` overlay细节微调。
- 下一步：回到更低过拟合路径。当前可保留的现实候选仍是“C3原路径 + 约11.5万外部现金”的正常成本部署候选；若要追求更强目标，需要寻找真正独立、低相关、可交易且弱窗口互补的新收益源，而不是继续在同一条xsmom overlay上调小数。

## 过拟合反思

- 运行前判断：不是过拟合，因为固定 Stage051 唯一候选，不新增阈值搜索。
- 运行后判断：本阶段不是过拟合；失败后若继续调 `2.8万/3.2万` 或xsmom细节会过拟合。
- 原因：多周期反证显示问题来自路径不稳定和保证金边界，不是某个小数阈值偏差。

## 继续价值反思

- 运行前判断：有价值，因为全样本候选必须经多周期和滑点压力。
- 运行后判断：该候选继续价值低；总研究线仍有价值。
- 原因：本阶段缩小了搜索空间，确认“C3原路径+xsmom overlay+少量现金”不是稳健解；后续应换结构而不是救局部结果。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是
