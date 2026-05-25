# Stage002 最大回撤归因与前置风控反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-25 12:56 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：最大回撤来源归因 + 两类前置风控候选验证
- 是否重要突破：否，但明确排除了两个直觉方向
- 是否触发A/B：是，`A=78-1正式基准`，`C=78-1+前置风险过滤`

## 外部调研与判断

- 参考资料：
  - 波动率目标和尾部风险目标文献认为仓位/风险缩放有助于降低尾部风险，但容易在趋势恢复段损失复利。
  - drawdown control 相关研究强调回撤调制需要处理“恢复机制”，否则容易在低点附近停滞。
  - vn.py 的前端风控更偏下单数量、撤单、流控；策略级回撤压缩仍需要策略内部的状态识别。
- 我的判断：
  - 第78-1的回撤不是交易成本造成，而是持仓方向在若干工业/能源品种上连续不利。
  - 直接“回撤后少开仓”会产生风险死锁；连续亏损降风险有一些改善，但无法单独达到目标。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage294_stage78_1_drawdown_source.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage295_stage78_1_drawdown_entry_brake.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage296_stage78_1_loss_streak_risk.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `enable_portfolio_drawdown_gate`
  - `portfolio_drawdown_gate_start_pct/full_pct/weight_floor`
  - `enable_rollover_reopen_drawdown_guard`
  - `rollover_reopen_max_portfolio_drawdown_pct`
  - `streak_risk_multipliers`
  - `streak_profit_recovery_mode=decrement`
- 修改参数：无正式参数修改，仅研究候选。
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - 全样本：2020起点至2026-04-30。
  - 弱窗口：2026年初至2026-04-30。
- 账户规模：`500,000`
- 成本口径：沿用第78-1正式回测成本和滑点口径。
- 样本过滤：沿用78-1正式AI池、品种宇宙、fu卫星口径。
- 策略/归因口径：
  - Stage294：使用正式日度权益、持仓变动、entry diagnostics 做最大回撤归因。
  - Stage295：只限制深回撤后的新增开仓，不主动平已有持仓。
  - Stage296：只修改连续亏损后的风险倍率，不改信号、品种和AI池。

## 结果

### Stage294 最大回撤来源

- 最大回撤窗口：
  - 高点：`2022-03-09`，权益`5,119,075`
  - 低点：`2022-12-07`，权益`3,062,955`
  - 最大回撤：`-40.1659%`
  - 恢复高点：`2023-04-17`
- 回撤期净亏损结构：
  - 高点后至低点净亏损约`-2,056,120`
  - 持仓损益约`-1,678,700`
  - 交易损益约`-35,590`
  - 滑点约`83,060`
  - 结论：主要是持仓方向亏损，不是手续费/滑点。
- 回撤期主要亏损品种：
  - `fu.SHFE`：净亏`-767,320`，亏损贡献`26.49%`
  - `jm.DCE`：净亏`-747,480`，亏损贡献`25.81%`
  - `sp.SHFE`：净亏`-498,400`，亏损贡献`17.21%`
  - `MA.CZCE`：净亏`-426,760`，亏损贡献`14.73%`

### Stage295 深回撤新增开仓刹车

- `C_dd_entry_brake_20_35_floor0`
  - 期末权益：`553,665`
  - 总收益：`10.733%`
  - 最大回撤：`-38.0865%`
  - Sharpe：`0.0897`
  - 总交易次数：`128`
  - 结论：策略基本被冻结，仍未压到30。
- `C_dd_entry_brake_15_30_floor0`
  - 期末权益：`628,900`
  - 总收益：`25.780%`
  - 最大回撤：`-29.8834%`
  - Sharpe：`0.2148`
  - 总交易次数：`247`
  - 结论：回撤进30以内，但收益几乎被吃光，不可推广。
- `C_dd_entry_brake_20_35_floor25`
  - 期末权益：`9,046,180`
  - 总收益：`1709.236%`
  - 最大回撤：`-38.2865%`
  - 结论：保留部分开仓后收益恢复，但回撤仍过高。

### Stage296 连续亏损风险倍率

- `C_loss_streak_moderate_reset`
  - 期末权益：`15,528,345`
  - 总收益：`3005.669%`
  - 收益保留：`60.01%`
  - 最大回撤：`-38.7287%`
  - Sharpe：`1.0264`
  - 结论：有一定改善，但远未达30。
- `C_loss_streak_aggressive_reset`
  - 期末权益：`13,570,875`
  - 总收益：`2614.175%`
  - 收益保留：`52.19%`
  - 最大回撤：`-37.0074%`
  - Sharpe：`1.0622`
  - 结论：回撤仅改善约`3.05pp`，收益下降明显。
- `C_loss_streak_moderate_decrement`
  - 期末权益：`1,495,590`
  - 总收益：`199.118%`
  - 收益保留：`3.98%`
  - 最大回撤：`-27.7152%`
  - Sharpe：`0.6700`
  - 结论：回撤进30以内，但风险恢复太慢，复利被破坏。

## 输出文件

- Stage294 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage294_stage78_1_drawdown_source_report_stage294_stage78_1_drawdown_source_v1.md`
- Stage294 product：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage294_stage78_1_drawdown_source_product_pnl_stage294_stage78_1_drawdown_source_v1.csv`
- Stage295 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage295_stage78_1_drawdown_entry_brake_summary_stage295_stage78_1_drawdown_entry_brake_v1.csv`
- Stage295 comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage295_stage78_1_drawdown_entry_brake_comparison_stage295_stage78_1_drawdown_entry_brake_v1.csv`
- Stage296 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage296_stage78_1_loss_streak_risk_summary_stage296_stage78_1_loss_streak_risk_v1.csv`
- Stage296 comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage296_stage78_1_loss_streak_risk_comparison_stage296_stage78_1_loss_streak_risk_v1.csv`

## 结论

- 本阶段结论：
  - 目标“最大回撤30以内，同时收益不显著降低”目前仍未达成。
  - 深回撤开仓刹车和连续亏损降风险都验证了同一个边界：只要规则足够强到压进30以内，就会明显破坏复利；规则温和时收益尚可，但回撤仍在37%-39%。
- 是否进入下一步：谨慎继续
- 下一步：
  - 不再继续扫回撤阈值或亏损倍率。
  - 下一条有价值方向是“产业/宏观风险簇暴露上限”：Stage294显示最大回撤由 `fu/jm/sp/MA` 等工业能源链条集中贡献，现有20日相关性门禁未识别这种风险。
  - 该方向需要先做只读归因：按产业簇统计全样本收益、回撤期损益、恢复期收益，确认不是用2022单窗口硬拟合。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：仍不是过拟合，但继续扫同类参数会变成过拟合。
- 原因：
  - 本轮规则均是通用前置风控，未指定年份、未拉黑单品种。
  - 失败结果清楚显示了收益-回撤前沿；若为了30%继续微调阈值，就是在用2022窗口塑形。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但要换机制。
- 原因：
  - 已确认三个方向的边界：资金软上限、深回撤新仓刹车、连续亏损降风险都不能单独解决。
  - 最大回撤归因指向“产业簇集中风险”，这是下一步更本质的研究方向。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否，尚无正式候选。
