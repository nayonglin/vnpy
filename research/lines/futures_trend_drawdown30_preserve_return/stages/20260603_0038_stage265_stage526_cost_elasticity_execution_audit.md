# Stage265 Stage526 成本弹性/执行偏差审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 00:38 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读执行归因；固定 Stage526，不新增交易候选。
- 是否重要突破：否，但明确了 3x 成本失败和 no-trade/buffer 的边界。
- 是否触发A/B：否。本阶段没有产生可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - Chevalier/Darolles《Futures Market Liquidity and the Trading Cost of Trend Following Strategies》：趋势跟随的交易成本要区分执行质量与管理决策，且市场波动/流动性变化会显著影响净表现。
  - NBER/Novy-Marx & Velikov `A Taxonomy of Anomalies and their Trading Costs`：交易成本会显著侵蚀策略，简单有效的成本治理通常是 buy/hold spread 或 no-trade 区域，而不是频繁追随微小信号变化。
  - `pysystemtrade` / Rob Carver：系统化期货组合中常用 buffering / shadow cost / 优化器来降低无意义换手。
- 我的判断：
  - 成本治理方向成立，但必须先判断成本是不是主因。
  - 若亏损段加回滑点后仍大幅亏损，执行优化只能改善边界，不能修复策略本体路径。
  - no-trade/buffer 只有在换月、微调仓或频繁 rebalance 成本占主导时才值得进入真实引擎；如果成本集中在正常开平仓，而 6天以后持仓贡献右尾，则宽泛 buffer 会有较大误伤风险。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage564_stage526_cost_elasticity_execution_audit.py`
- 修改脚本：
  - 无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - 诊断成本倍率网格：`1.00` 到 `5.00`，步长 `0.25`。
  - DD40 成本临界点二分求解。
  - 交易事件分类：`new_open_day`、`close_day`、`roll_or_contract_switch`、`reduce_day` 等。
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage526 全周期 `2020-2026`；重点坏窗口 `2022-03-09 -> 2022-12-07`。
- 账户规模：Stage526 组合口径，读取既有 `r080_pc25_maxpos4` 输出。
- 成本口径：
  - `1x` 为 Stage526 正常成本。
  - 额外成本用 `account_equity - (cost_multiplier - 1) * cum_slippage` 重构。
- 样本过滤：
  - Stage526 daily：`qmt_roll_stage526_productcap25_breadth_frontier_margin_daily_stage526_productcap25_breadth_frontier_v1.csv`
  - Stage526 positions：`qmt_roll_stage526_productcap25_breadth_frontier_positions_stage526_productcap25_breadth_frontier_v1.csv`
  - Stage537 segments：`qmt_roll_stage537_stage526_segment_lifecycle_audit_segments_stage537_stage526_segment_lifecycle_audit_v1.csv`
- 策略/归因口径：
  - 不改入场、出场、品种池、AI池、保证金门控。
  - 不做真实引擎候选，只做成本弹性、持仓段 gross/net 和交易事件类型归因。

## 结果

- 决策：`execution_cost_monitor_needed_no_trade_buffer_not_promoted`
- Stage526 参考：
  - 期末权益：`23,369,505`
  - 总收益：`3699.9195%`
  - 最大回撤：`-36.2670%`
  - Sharpe：`1.6385`
  - 总滑点：`1,342,190`
  - 总交易次数：`905`
  - 胜率：`53.6330%`
- 成本弹性：
  - DD40 成本临界倍率：`2.3226x`
  - `3x` 成本若要回到 DD40 以内，需要把 3x 场景下的滑点压力等效降低约 `33.8697%`。
  - `2.25x` 仍通过，最大回撤 `-39.7857%`；`2.50x` 失败，最大回撤 `-40.5284%`；`3.00x` 为 `-42.0555%`。
- 坏窗口：
  - `2022-03-09 -> 2022-12-07` 净 PnL：`-1,614,915`
  - 该窗口 `3x` 相对 `1x` 额外成本：`147,420`
  - 额外成本占窗口净亏损约 `9.13%`
  - 结论：成本会把 DD 推过线，但不是窗口亏损主因。
- 持仓段 gross/net：
  - `1-3` 天段净 PnL `-10,553,405`，加回滑点后的 gross PnL 仍为 `-10,234,935`。
  - `4-5` 天段净 PnL `-3,036,175`，gross 仍为 `-2,801,055`。
  - `6-10` 天段净 PnL `+5,286,535`。
  - `11-20` 天段净 PnL `+24,278,135`。
  - `21-60` 天段净 PnL `+6,133,230`。
  - `6-60` 天合计右尾 `+35,697,900`，说明宽泛 trade buffer / time stop 有误伤右尾风险。
- 交易事件：
  - `new_open_day`：`315` 个产品日，滑点 `629,685`，净 PnL `+1,439,640`。
  - `close_day`：`313` 个产品日，滑点 `584,155`，净 PnL `-609,885`。
  - `roll_or_contract_switch`：`25` 个产品日，滑点 `93,655`，仅占总产品日滑点 `7.0571%`，净 PnL `+530,255`。
  - `reduce_day`：`9` 个产品日，滑点 `19,615`，净 PnL `+1,011,065`。
  - 结论：换月/合约切换不是总成本主因；真正成本集中在正常开平仓，不能靠简单“减少换月”解决。

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_chart_stage564_stage526_cost_elasticity_execution_audit_v1.png`
- 左上：成本倍率曲线平滑下行，DD40 临界在 `2.32x` 附近；这说明 3x 压力是明确边界，而非单点异常。
- 右上：`1-3` 与 `4-5` 天段在 gross、1x net、3x net 下都为负；亏损不是被滑点“转负”的。
- 右上同时显示 `11-20` 天是主收益段，3x 成本下仍强正；这解释了为什么早退/粗 buffer 容易误伤。
- 左下：新开和平仓是成本主体，roll/switch 成本柱很小；执行优化不能只盯换月。
- 右下：坏窗口里 `2022-03`、`2022-08` 是路径亏损主冲击，橙色额外成本柱明显小于红色亏损柱。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_report_stage564_stage526_cost_elasticity_execution_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_decision_stage564_stage526_cost_elasticity_execution_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_chart_stage564_stage526_cost_elasticity_execution_audit_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_summary_stage564_stage526_cost_elasticity_execution_audit_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_gates_stage564_stage526_cost_elasticity_execution_audit_v1.csv`
- cost elasticity：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_cost_elasticity_stage564_stage526_cost_elasticity_execution_audit_v1.csv`
- segment cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_segment_cost_by_duration_stage564_stage526_cost_elasticity_execution_audit_v1.csv`
- event rows/summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_trade_event_rows_stage564_stage526_cost_elasticity_execution_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_trade_event_summary_stage564_stage526_cost_elasticity_execution_audit_v1.csv`
- product-day events/summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_product_day_events_stage564_stage526_cost_elasticity_execution_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_product_day_event_summary_stage564_stage526_cost_elasticity_execution_audit_v1.csv`
- bad window monthly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage564_stage526_cost_elasticity_execution_audit_bad_window_monthly_stage564_stage526_cost_elasticity_execution_audit_v1.csv`

## 结论

- 本阶段结论：需要执行成本监控和滑点压降，但不晋级 no-trade/buffer 交易规则。
- 是否进入下一步：进入“执行监控/真实滑点采样/成交质量日报”方向；策略规则层暂不改。
- 下一步：
  - 对 Stage526 真实/影子盘建立成交滑点采样：按产品、时段、开平仓、换月、手数记录实际滑点。
  - 将 `2.3226x` 作为成本压力边界：若真实滑点长期高于约 `2.3x` 估计，Stage526 不能声明 DD40 稳定。
  - 若未来要做执行结构，只允许先做 paper 级别的“订单类型/分时/避免低流动性窗口”监控，不做信号级 no-trade gate。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段只读取固定 Stage526 输出，不用 2022 单窗口构造交易规则。
  - 结果主动否决了 no-trade/buffer 晋级，避免把成本压力误写成样本内过滤器。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：继续有价值，但价值从“策略改规则”转向“执行成本监控和真实滑点采样”。
- 原因：
  - 成本临界点 `2.3226x` 说明执行质量对 DD40 边界有真实影响。
  - 但坏窗口额外成本只占亏损 `9.13%`，持仓段 gross 亏损明显，说明继续靠交易规则省成本的边际收益有限。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是。该阶段明确 Stage526 的执行成本边界和后续监控方向。
