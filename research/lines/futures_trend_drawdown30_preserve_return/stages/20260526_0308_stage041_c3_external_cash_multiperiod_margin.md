# Stage041 C3外部现金缓冲多周期与保证金验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 03:08 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：部署候选复验
- 是否重要突破：是，Stage040的6.7万口径被修正为更稳健的11.5万部署候选
- 是否触发A/B：否；本阶段仍不修改策略交易规则，只验证账户资金边界

## 外部调研与判断

- 参考资料：
  - Time Series Momentum / A Century of Evidence on Trend-Following Investing：趋势跟随长期有效，但回撤治理应在组合构建、风险预算和部署纪律上处理。
  - Constant-collateral pyramiding trading strategies in futures markets：期货策略中，增加现金抵押或减少合约暴露都可以影响保证金压力和回撤边界。
  - Managed futures collateral/cash allocation相关研究：期货收益应区分交易路径收益和现金抵押/账户权益口径。
- 我的判断：
  - Stage040的6.7万只对全样本口径刚好有效，容易变成精确数字幻觉。
  - 真正可执行的部署候选必须同时通过多起点、弱窗口和保证金占用检查。
  - 外部现金缓冲不是alpha，也不是风险消失，而是用更大的账户权益承载同一套C3交易路径。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage341_c3_external_cash_multiperiod_margin.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定外部现金档位：`0 / 6.7万 / 7.5万 / 10万 / 11.5万 / 12.5万`
  - 多周期闸门：最大回撤 `>= -30%`；正收益窗口收益保留 `>= 80%`
  - 保证金观察：`60%/80%/100%` 三档
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：多起点与弱窗口沿用 Stage336 C3 100%风险资金日度权益路径。
- 账户规模：策略下单口径仍为50万；外部现金只加入账户权益。
- 成本口径：沿用C3已有成本、滑点和成交路径；不重跑下单。
- 样本过滤：
  - `start_2020/start_2021/start_2022/start_2023/start_2024/start_2025/ytd_2026`
  - `weak_2021_full`
  - `phase_2024_2025`
- 策略/归因口径：`account_equity = c3_strategy_equity + external_cash_buffer`

## 结果

- `6.7万`外部现金：
  - 多周期通过：`8/9`
  - 失败窗口：`start_2022`
  - `start_2022`最大回撤：`-31.8094%`
  - 最大保证金/权益：`101.2474%`
  - 100%拒绝线天数：`1`
- `10万`外部现金：
  - 多周期通过：`8/9`
  - `start_2022`最大回撤：`-30.4744%`
  - 最大保证金/权益：`100.0507%`
  - 100%拒绝线天数：`1`
- `11.5万`外部现金：
  - 多周期通过：`9/9`
  - `start_2022`总收益：`565.5902%`
  - `start_2022`收益保留：`81.3008%`
  - `start_2022`最大回撤：`-29.9039%`
  - 全样本账户总收益：`4947.2602%`
  - 全样本收益保留：`81.3008%`
  - 全样本最大回撤：`-29.7007%`
  - 最大保证金/权益：`99.5161%`
  - 100%拒绝线天数：`0`
- `12.5万`外部现金：
  - 多周期通过：`9/9`
  - 全样本收益保留：`80.0000%`
  - 全样本最大回撤：`-29.6403%`
  - 最大保证金/权益：`99.1629%`
- 各窗口压到30%所需现金最大值：
  - `start_2022` 需要 `112,433.33`
  - 占50万策略资金 `22.4867%`
- 总滑点：沿用C3路径
- 总交易次数：沿用C3路径
- 胜率：沿用C3路径

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage341_c3_external_cash_multiperiod_margin_report_stage341_c3_external_cash_multiperiod_margin_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage341_c3_external_cash_multiperiod_margin_window_summary_stage341_c3_external_cash_multiperiod_margin_v1.csv`
- orders：无
- daily：无新增日度曲线文件，本阶段使用 Stage336 日度权益源
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage341_c3_external_cash_multiperiod_margin_decision_stage341_c3_external_cash_multiperiod_margin_v1.json`

## 结论

- 本阶段结论：`6.7万`不是稳健部署口径；`11.5万`外部现金是当前最低一档通过多周期和保证金检查的部署候选。
- 是否进入下一步：进入部署候选，但需要用户确认是否能接受 `50万策略资金 + 11.5万现金缓冲` 的账户准备方式。
- 下一步：
  - 若用户接受，该口径可以进入实盘前SOP资金边界：策略仍按50万风险预算跑，账户准备至少61.5万，现金缓冲不参与信号放大。
  - 若用户不接受，则不能宣称已实现“30以内且收益不显著降低”；需要接受C3自然回撤约31%，或寻找真正低相关收益源。
  - 后续还应做滑点压力下的外部现金需求估算。

## 过拟合反思

- 运行前判断：不过拟合。
- 运行后判断：不过拟合，但修正了Stage040的伪精确风险。
- 原因：固定现金档位是资金部署口径，不改变交易规则；`11.5万`来自多周期和保证金边界，而不是为了某一笔交易做信号补丁。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但方向从“策略内改造”转为“资金部署候选”。
- 原因：它是目前唯一保留C3交易路径并稳定满足30%账户回撤边界的方式；缺点是需要用户多准备约23%的外部现金。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为部署候选摘要记录
