# Stage006 Stage013 base holding position 归因

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02 03:30 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 Stage013 positions 重放，不新增交易规则，不修改官方实盘/CTP/邮件/launchd
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - pysystemtrade backtesting/position accounting: https://github.com/pst-group/pysystemtrade
  - Alpha Architect: Trend Following - The Epitome of No Pain, No Gain https://alphaarchitect.com/trend-following-the-epitome-of-no-pain-no-gain/
  - quantstrat strategy development process: https://github.com/braverock/quantstrat/blob/master/sandbox/backtest_musings/strat_dev_process.Rmd
- 我的判断：
  - Stage005 已证明 Stage074 residual 不是 AI proxy lot 主导，而是 Stage013 base holding 主导。
  - 本阶段必须用真实 positions 校验 daily holding/trading/cost 能否对齐 Stage005 component；若能对齐，再看亏损来自窗口起点已有仓还是窗口后新增/交易仓。
  - 若新增/交易仓主导，下一步应审计入场候选状态、AI池、账户状态和开仓质量；若已有仓主导，才研究持仓降风险或退出结构。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage006_stage013_base_holding_position_attribution.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage006_stage013_base_holding_position_attribution.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `RAMP_FLOOR=0.35`
  - `RAMP_TRADING_DAYS=252`
  - Stage006 复用 Stage005 的 `929` 个 Stage074 ramp residual windows
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage005 `stage074_ramp` residual windows，最大窗口结束 `2024-03-27`
- 账户规模：C9/15w Stage013 base
- 成本口径：positions 内 `commission/slippage`
- 样本过滤：Stage005 中 `stage074_ramp` 胜出的 `929` 个窗口；source start months 共 `10` 个：`2018-01/2018-07/2019-01/2019-07/2020-01/2020-07/2021-01/2021-07/2022-01/2022-07`
- 策略/归因口径：
  - 调用 Stage013 `_run_live_stage013` 重放 positions。
  - 对每个 Stage005 window，从窗口起点重置 Stage074 ramp，并把 positions 的 `holding_pnl/trading_pnl/cost/net_pnl` 按日期乘回 ramp。
  - 用窗口起点已有 `end_pos/start_pos` 判断 `existing_at_window_start`，否则归为 `opened_or_traded_after_window_start`。

## 结果

- 期末权益：不适用，归因审计非新回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：positions 归因中已计入 scaled cost
- 总交易次数：positions 归因输出中保留 `trade_count`
- 胜率：不适用
- 其他关键指标：
  - 决策：`stage006_base_holding_new_positions_dominant_need_entry_signal_audit`
  - validation max abs diff：`3.49e-10`
  - window_count：`929`
  - row_count：`23,868`
  - stage074_scaled_net_pnl：`-396,329,942.1693`
  - stage074_scaled_holding_pnl：`-308,796,513.2470`
  - stage074_scaled_trading_pnl：`-52,599,097.9980`
  - stage074_scaled_cost：`34,934,330.9243`
  - holding_loss_share_pct：`81.5713%`
  - trading_loss_share_pct：`39.4819%`
  - cost_loss_share_pct：`4.1859%`
  - existing_at_window_start_holding_loss_share_pct：`28.1121%`
  - opened_after_window_start_holding_loss_share_pct：`71.8879%`
  - 最差 product/direction/source_bucket：`SM.CZCE short opened_or_traded_after_window_start`
    - scaled holding pnl：`-124,611,341.2470`
    - scaled trading pnl：`57,880,865.5936`
    - scaled cost：`1,740,412.8526`
    - scaled net pnl：`-68,470,888.5060`
  - 其次主要拖累：
    - `fu.SHFE long opened_or_traded_after_window_start` holding `-113,595,713.0518`
    - `sp.SHFE long opened_or_traded_after_window_start` holding `-107,750,304.8088`
    - `sp.SHFE long existing_at_window_start` holding `-90,457,372.6295`
    - `au.SHFE long existing_at_window_start` holding `-65,526,414.0637`

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage006_stage013_base_holding_position_attribution/rebuilt_c9_v2_stage006_stage013_base_holding_position_attribution_report_stage006_stage013_base_holding_position_attribution_v1.md`
- summary：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage006_stage013_base_holding_position_attribution/rebuilt_c9_v2_stage006_stage013_base_holding_position_attribution_decision_stage006_stage013_base_holding_position_attribution_v1.json`
- orders：不适用
- daily：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage006_stage013_base_holding_position_attribution/rebuilt_c9_v2_stage006_stage013_base_holding_position_attribution_positions_stage006_stage013_base_holding_position_attribution_v1.csv.gz`
- quality：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage006_stage013_base_holding_position_attribution/rebuilt_c9_v2_stage006_stage013_base_holding_position_attribution_window_validation_stage006_stage013_base_holding_position_attribution_v1.csv`

## 结论

- 本阶段结论：Stage013 base holding residual 可以被 positions 精确复原；主导亏损不是窗口起点已有仓，而是窗口后新增/交易仓位的 holding PnL，尤其 `SM.CZCE short`、`fu.SHFE long`、`sp.SHFE long`。
- 是否进入下一步：是。
- 下一步：不要直接做品种/方向黑名单；先做 Stage007 入场状态审计，检查这些新增/交易仓在入场日前后的 AI rank、AI score、账户状态、active positions、loss streak、OI/RSI/趋势状态、入场后 early adverse/giveback，确认是否存在可预声明、PIT 的“低质量新仓”特征。

## 过拟合反思

- 运行前判断：不过拟合，本阶段只重放 positions 并做路径归因。
- 运行后判断：不过拟合。
- 原因：没有把 `SM/fu/sp` 直接变成黑名单，也没有调阈值；只是把下一步从“AI proxy”定位到“新增仓入场质量审计”。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Stage006 明确了后续应审计新增仓入场状态，而不是继续做持仓起点降风险或 AI proxy 救参。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、重要突破或跨线合入摘要
