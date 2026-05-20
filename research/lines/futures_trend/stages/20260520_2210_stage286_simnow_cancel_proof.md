# Stage286 普通 SimNow 开平仓证据补充撤单记录

- line_id：`futures_trend`
- 当前模式：day
- 记录时间：2026-05-20 22:10 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：SimNow 执行链路证据补充
- 是否重要突破：否，属于 Stage285 证据补充
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段只执行既有 Stage78-1 SimNow SOP 与本地 CTP/SimNow 回报文件，未做新的外部策略调研。
- 我的判断：本次不是 alpha 优化，也不是参数选择；核心目标是给券商补齐“程序化撤单确实发出且最终回报为 Cancelled”的工程证据。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不涉及回测
- 账户规模：不涉及策略资金口径；执行环境为普通 SimNow `9999/trading` 测试环境
- 成本口径：不涉及
- 样本过滤：`MA609.CZCE` 最小 1 手测试
- 策略/归因口径：Stage78-1 执行链路 smoke proof，不改变策略逻辑

## 结果

- 期末权益：不涉及
- 总收益：不涉及
- 最大回撤：不涉及
- Sharpe：不涉及
- 总滑点：不涉及
- 总交易次数：不涉及策略交易统计
- 胜率：不涉及
- 其他关键指标：
  - 开平仓证据延续 Stage285：`Long/Open` 1 手与 `Short/Close` 1 手均 `All Traded`
  - 撤单测试委托：`CTP.1_-1097460188_1`
  - 撤单合约：`MA609.CZCE`
  - 撤单方向/开平：`Long/Open`
  - 撤单限价：`2872.0`
  - 撤单手数：`1`
  - 撤单成交：`0`
  - 最终状态：`Cancelled`
  - Stage258 控制台回报：`send_order_api_called_count=1`，`cancel_order_api_called_count=1`
  - 后验只读快照：`confirmed_flat / nonzero_position_rows=0`

## 输出文件

- evidence_html：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage285_simnow_open_close_cancel_evidence_20260520_220320.html`
- evidence_png：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage285_simnow_open_close_cancel_evidence_20260520_220320.png`
- cancel_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage258_simnow_smoke_order_summary_20260520_220053_stage258_simnow_smoke_order_v1.json`
- cancel_logs：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage258_simnow_smoke_order_logs_20260520_220053_stage258_simnow_smoke_order_v1.csv`
- post_orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_orders_stage174_ctp_vnpy_readonly_probe_v1.csv`
- post_positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_positions_stage174_ctp_vnpy_readonly_probe_v1.csv`

## 结论

- 本阶段结论：普通 SimNow `9999/trading` 下，程序化开仓、平仓、撤单三类链路均已形成可截图证据；撤单不是只看到本地调用，而是在后验只读订单快照里看到最终 `Cancelled` 状态。
- 是否进入下一步：是
- 下一步：若券商只要求证明程序化交易栈能力，可先发送本阶段截图；若券商要求必须在 `1010/41407/41415` 评测前置验收，则等待该路线的报单拒绝原因和终端信息上报格式闭环后再复刻开平仓/撤单。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本阶段没有调参、没有选择收益更好的品种或窗口，只是在测试环境补齐订单生命周期证据。

## 继续价值反思

- 运行前判断：有价值
- 运行后判断：有价值
- 原因：券商验收通常关心登录、认证、报单、撤单、成交、持仓回查是否闭环；撤单证据能减少“只会成交、不会撤单/回查”的执行风险。

## 合入建议

- 是否更新本线 `LINE.md`：是，补充 Stage286 证据摘要
- 是否更新 `research/registry.md`：是，将最新关键阶段更新到 Stage286
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是执行证据补充，不改变策略正式基准和研究结论
