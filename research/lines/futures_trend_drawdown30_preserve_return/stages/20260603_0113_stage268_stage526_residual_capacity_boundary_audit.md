# Stage268 Stage526残余容量与换月边界审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-03 01:13 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读容量边界审计；不改策略、不改参数、不生成交易候选。
- 是否重要突破：否。它把容量未关账项拆细为可执行问题，但不改变 Stage526 收益/回撤路径。
- 是否触发A/B：否。不是可接入正式版本的新策略模块，只是扩池前的实盘可成交性审计。

## 外部调研与判断

- 参考资料：
  - 交易执行里的 POV / participation rate 思路强调按市场成交量自适应控制订单参与率；这和本阶段的订单量/日成交量闸门一致。
  - 期货 K 线数据源通常可提供成交量和持仓量，但日成交量/OI只能作为粗容量闸门，不能替代盘口深度、VWAP、真实成交滑点。
  - 国内期货夜盘/日盘分段、换月流动性衰减会造成旧合约尾部容量骤降，单纯看产品级历史中位成交量不够。
- 我的判断：
  - Stage526 的容量风险已从“覆盖缺口很大”收敛到“少数残余缺口 + 少数硬容量事件 + 旧合约换月流程”。
  - `fu2509.SHFE` 不应该被解释成 `fu` 产品黑名单，而应该解释成旧合约尾部换月执行问题。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage567_stage526_residual_capacity_boundary_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `SOFT_ORDER_VOLUME_PCT = 0.25`
  - `HARD_ORDER_VOLUME_PCT = 0.50`
  - `MAX_ORDER_VOLUME_PCT = 1.00`
  - `POSITION_OI_STRESS_PCT = 1.00`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage526 / Stage565 事件账本，2020-2026。
- 账户规模：Stage526 `50万` 下单口径。
- 成本口径：正常成本；本阶段不重算收益，只继承 Stage526 指标。
- 样本过滤：
  - 残余缺口：Stage267 未接受回填的 `8` 个 partial context 事件。
  - 硬容量事件：订单量/日成交量 `>0.50%` 或峰值持仓/OI `>1.00%` 的 Stage526 交易事件。
- 策略/归因口径：
  - 平仓/开仓/换月配对只做事件分类，不生成交易规则。
  - `1%` 日成交量视为严格容量关账线；`0.5%` 视为硬压力观察线。

## 结果

- 期末权益：`23,369,505`
- 总收益：`3699.9195%`
- 最大回撤：`-36.2670%`
- Sharpe：`1.6385`
- 总滑点：`1,342,190`
- 总交易次数：`905`
- 胜率：`53.6330%`
- 其他关键指标：
  - decision：`capacity_residual_actionable_not_closed`
  - 闸门：`4/7`
  - 残余缺口事件：`8`
  - 完整分钟日但成交量为0事件：`1`
  - partial zero volume 事件：`7`
  - 硬容量事件数：`5`
  - 超过 `1%` 日成交量事件数：`1`
  - 最大订单量/日成交量：`1.0381%`
  - 最大超 `1%` 手数：`18.37`
  - 开仓类硬容量压力事件：`1`
  - 换月边界事件：`1`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage567_stage526_residual_capacity_boundary_audit_report_stage567_stage526_residual_capacity_boundary_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage567_stage526_residual_capacity_boundary_audit_summary_stage567_stage526_residual_capacity_boundary_audit_v1.csv`
- residual_gap_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage567_stage526_residual_capacity_boundary_audit_residual_gap_events_stage567_stage526_residual_capacity_boundary_audit_v1.csv`
- hard_capacity_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage567_stage526_residual_capacity_boundary_audit_hard_capacity_events_stage567_stage526_residual_capacity_boundary_audit_v1.csv`
- roll_pair_context：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage567_stage526_residual_capacity_boundary_audit_roll_pair_context_stage567_stage526_residual_capacity_boundary_audit_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage567_stage526_residual_capacity_boundary_audit_gates_stage567_stage526_residual_capacity_boundary_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage567_stage526_residual_capacity_boundary_audit_decision_stage567_stage526_residual_capacity_boundary_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage567_stage526_residual_capacity_boundary_audit_chart_stage567_stage526_residual_capacity_boundary_audit_v1.png`

## 图表视觉分析

- 左上图显示残余缺口中 `7` 个是只有 16 根左右成交窗口片段且成交量为0，`1` 个是完整分钟日但成交量仍为0。后者是 `OI009.CZCE 2020-05-18`，不能被视为容量已验证。
- 右上图把硬容量事件分成两类：`fu2509.SHFE` 同时接近/略超成交量和 OI 1%线，`AP505.CZCE` 主要是持仓/OI超过1%；`lc2505.GFEX` 的成交量占比较高但 OI 压力不大。
- 左下图显示硬容量压力主要在平仓/换月侧，开仓类只有 `SM505.CZCE` 一次。这意味着未来实盘规则应同时包含“新开仓准入闸门”和“旧合约提前换月/拆单流程”，不能只做开仓过滤。
- 右下图显示真正超过 1% 线的只有 `fu2509.SHFE 2025-08-21`。它比 1% 线只多约 `18.37` 手，属于可操作的轻微超限，而不是不可承载尾部。

## 结论

- Stage526 容量风险不是大面积不可成交，而是少数残余证据和少数边界执行事件。
- `8` 个残余缺口需要真实日线成交量/OI补证，不能继续用本地片段数据关账。
- `fu2509.SHFE` 边界事件应解释为旧合约换月流动性衰减：同日有 `fu2510.SHFE` 开仓配对，新合约订单占日成交量仅 `0.1436%`，旧合约平仓占比 `1.0381%`。未来应考虑提前换月或拆单，而不是禁止 `fu`。
- 硬容量事件中只有 `1` 个开仓类压力，说明扩池准入的核心不是否决 Stage526，而是把候选品种和旧合约尾部纳入容量闸门。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只用固定容量阈值、固定换月配对逻辑和既有事件账本做分类，不按收益结果调参，不新增交易信号。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：Stage526 的容量问题已经从“泛泛的流动性疑虑”缩成可执行清单：补 `8` 个日线缺口、监控旧合约流动性衰减、建立真实滑点采样账本。下一步可以转向真实成交质量，而不是继续扫宽池参数。

## 合入建议

- 是否更新本线 `LINE.md`：是。Stage268 是 Stage267 后的容量边界收敛。
- 是否更新 `research/registry.md`：是。当前线最新关键阶段应从 Stage267 更新为 Stage268。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破或路线废弃；保留在本线 stage 与 LINE 即可。
