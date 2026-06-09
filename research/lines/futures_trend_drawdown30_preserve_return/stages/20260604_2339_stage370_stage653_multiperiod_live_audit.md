# Stage370 Stage653 当前线上版本多周期检查报告

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-04 23:39 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：当前官方实盘版本 Stage653/20万的多周期、成本压力、保证金压力和可视化审计
- 是否重要突破：是，正式给出当前线上版本的多周期检查结论与风险边界。
- 是否触发A/B：否，本阶段不改策略、不接新候选、不做 A/B。

## 外部调研与判断

- 参考资料：
  - TradeStaq Backtesting Best Practices：强调 out-of-sample 与 walk-forward 复核。
  - GitHub `fxstr/walk-forward`：开源 walk-forward 回测框架，说明多窗口验证是常见工程形态。
  - CME Backtesting PDF：讨论样本切分和 OOS 检验的必要性。
- 我的判断：当前问题不是继续优化参数，而是把已确定线上版本固定住，做多起点、阶段窗口、年初至今、成本压力和保证金压力复核；这属于反过拟合检查，不属于调参。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage660_stage653_multiperiod_live_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无；脚本固定读取当前 official live profile。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 当前官方实盘版本：`official_live_stage653_20w_force95_to80`
- 策略体：`stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4`
- 账户规模：`200,000`
- 历史窗口口径：逐窗口独立重跑，20万 fresh capital，预热期只初始化指标；不重新训练、不重新调参。
- 历史数据区间：`2020-01-02` 至 `2026-04-30`
- 最新 YTD 口径：Stage659 最新 AI 池影子盘，`2026-01-05` 至 `2026-06-04`
- 成本口径：1x/2x/3x 滑点压力
- 样本过滤：仅当前官方实盘 profile；不回落到 Stage78。
- 策略/归因口径：只读审计；不连接 CTP，不读取账户，不调用下单。

## 结果

- 期末权益：全周期 `10,415,070`
- 总收益：全周期 `5107.5350%`
- 年化收益：全周期 `86.8222%`
- 最大回撤：全周期 `-38.8730%`
- Sharpe：全周期 `1.6384`
- 总滑点：全周期 `597,710`
- 总交易次数：全周期 `655`
- 胜率：非零日胜率 `52.3156%`
- 保证金：broker10 保证金/权益峰值 `83.3212%`，超 `90%/100%` 天数均为 `0`
- 强制减仓：全周期 `6` 次，合计 `317` 手
- 成本压力：
  - 1x：`10,415,070 / 5107.5350% / -38.8730% / Sharpe 1.6384`
  - 2x：`9,817,360 / 4808.6800% / -41.3142% / Sharpe 1.5633`
  - 3x：`9,219,650 / 4509.8250% / -43.9072% / Sharpe 1.4890`
- 关键多周期：
  - `since_2021`：`4,151,085 / 1975.5425% / -49.1004% / Sharpe 1.4846`，回撤失败。
  - `since_2022`：`160,760 / -19.6200% / -34.2150% / Sharpe -0.2795`，收益失败但生存/保证金过。
  - `since_2023`：`555,335 / 177.6675% / -17.3480% / Sharpe 1.2360`
  - `since_2024`：`510,615 / 155.3075% / -27.8942% / Sharpe 1.2993`
  - `since_2025`：`290,945 / 45.4725% / -18.4184% / Sharpe 1.1371`
  - `phase_2022_2023`：`135,540 / -32.2300% / -32.2300% / Sharpe -2.0381`
  - 最新 YTD：`201,140 / 0.5700% / -14.5394% / Sharpe 0.1943`，当前空仓。
- 任意启动体验：
  - 63日：p05 `-16.2778%`，正收益率 `75.8339%`
  - 126日：p05 `-8.0096%`，正收益率 `86.6999%`
  - 252日：p05 `4.6021%`，正收益率 `96.3281%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage660_stage653_multiperiod_live_audit_report_stage660_stage653_multiperiod_live_audit_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage660_stage653_multiperiod_live_audit_chart_stage660_stage653_multiperiod_live_audit_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage660_stage653_multiperiod_live_audit_summary_stage660_stage653_multiperiod_live_audit_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage660_stage653_multiperiod_live_audit_curves_stage660_stage653_multiperiod_live_audit_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage660_stage653_multiperiod_live_audit_checks_stage660_stage653_multiperiod_live_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage660_stage653_multiperiod_live_audit_decision_stage660_stage653_multiperiod_live_audit_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage660_stage653_multiperiod_live_audit_cost_stress_stage660_stage653_multiperiod_live_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage660_stage653_multiperiod_live_audit_annual_stage660_stage653_multiperiod_live_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage660_stage653_multiperiod_live_audit_monthly_stage660_stage653_multiperiod_live_audit_v1.csv`

## 结论

- 本阶段结论：决策 `stage653_multiperiod_audit_has_hard_fail`。当前线上版本正常成本下全周期和保证金闸门通过，最新 YTD 弱正且空仓；但 2x/3x 成本压力回撤失败，`since_2021` 回撤过深，`since_2022/phase_2022_2023` 独立启动收益为负，63日短周期左尾仍明显为负。
- 是否进入下一步：可以继续作为官方实盘观察/测试版本，但不能因为全周期收益高就扩大正常策略手数。
- 下一步：继续小规模/影子盘/TCA 校准；先把真实成交滑点、保证金口径、执行脚本缺陷复盘做完，再讨论是否开放更高仓位。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段固定线上版本，做多窗口和成本压力反证，没有新增阈值、品种过滤或信号参数；发现失败项也没有尝试救参数。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值在风控和执行校准，不在继续追收益。
- 原因：当前版本的收益弹性强，但多周期弱点清楚；继续推进应围绕真实 TCA、保证金和执行稳定性，而不是扩大手数。

## 合入建议

- 是否更新本线 `LINE.md`：是，登记 Stage370 多周期审计结论。
- 是否更新 `research/registry.md`：是，最新关键阶段推进到 Stage370。
- 是否追加根目录 `memory.md/back_log.md`：是，属于当前线上版本实盘前重要检查结论。
