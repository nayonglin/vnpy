# Stage005 Stage074 proxy replay 路径归因

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02 03:05 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读代理重放，不新增交易规则，不修改官方实盘/CTP/邮件/launchd
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - pysystemtrade backtesting 文档与项目： https://github.com/pst-group/pysystemtrade
  - Alpha Architect: Trend Following - The Epitome of No Pain, No Gain https://alphaarchitect.com/trend-following-the-epitome-of-no-pain-no-gain/
  - quantstrat 策略开发流程示例： https://github.com/braverock/quantstrat/blob/master/sandbox/backtest_musings/strat_dev_process.Rmd
- 我的判断：
  - Stage004 只能把 Stage074 residual 标成 `unsplit equity delta`，但 Stage074 由 Stage070 代理曲线再做 start-reset ramp 得来，因此可以把 Stage070 每日增量拆为 Stage013 base PnL 与 Stage070 selected lot delta，再用同一 ramp 乘数映射回 Stage074 窗口。
  - 这一步仍不是“真实 engine”，但足以判断 residual 是否来自 AI proxy lot。如果 AI proxy delta 不是主要亏损来源，继续调 top8/active<3/ramp floor 会偏离目标。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage005_stage074_proxy_replay_attribution.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage005_stage074_proxy_replay_attribution.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `TARGET_VARIANT=full_market_ai_top8_and_active_positions_lt3`
  - `TOP_N_WINDOWS=1000`
  - `RAMP_FLOOR=0.35`
  - `RAMP_TRADING_DAYS=252`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage004 的 Stage074 ramp residual windows，底层曲线到 `2026-06-30`
- 账户规模：沿用 C9/15w 代理曲线
- 成本口径：Stage013 base 曲线内 `commission` / `slippage`
- 样本过滤：Stage004 top1000 中 `oracle_winner=stage074_ramp` 的 `929` 个窗口
- 策略/归因口径：
  - 用 Stage013 base curves 构造 `base_net_pnl/base_holding_pnl/base_trading_pnl/base_cost`
  - 用 Stage070 lot_deltas 构造 `proxy_delta_pnl`
  - 逐窗口从窗口起点重置 `0.35 -> 1.0 / 252 trading days` ramp，乘回 base 与 proxy 分量

## 结果

- 期末权益：不适用，归因审计非新回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：ramp 后 base slippage `34,934,330.9243`
- 总交易次数：不适用，Stage005 使用 daily component 与 lot delta，不是真实 positions engine
- 胜率：不适用
- 其他关键指标：
  - 决策：`stage005_stage074_residual_base_holding_dominant_stop_ai_proxy_tuning`
  - Stage074 ramp residual 窗口数：`929`
  - oracle 最差收益：`-23.6338%`
  - ramp 后 adjusted net pnl：`-393,618,593.7166`
  - ramp 后 base holding pnl：`-308,796,513.2470`
  - ramp 后 base trading pnl：`-52,599,097.9980`
  - ramp 后 base slippage：`34,934,330.9243`
  - ramp 后 Stage070 proxy delta pnl：`2,711,348.4527`
  - base holding loss share：`78.4507%`
  - base trading loss share：`13.5924%`
  - cost loss share：`8.8752%`
  - Stage070 proxy delta loss share：`0.1543%`
  - component validation max abs diff：`3.49e-10`
  - proxy lot 产品方向最差：`jm.DCE long`，ramp 后 `-12,666,913.9019`；但 `fu.SHFE long` ramp 后 `+13,621,059.7410`，整体 proxy delta 为正。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage005_stage074_proxy_replay_attribution/rebuilt_c9_v2_stage005_stage074_proxy_replay_attribution_report_stage005_stage074_proxy_replay_attribution_v1.md`
- summary：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage005_stage074_proxy_replay_attribution/rebuilt_c9_v2_stage005_stage074_proxy_replay_attribution_decision_stage005_stage074_proxy_replay_attribution_v1.json`
- orders：不适用
- daily：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage005_stage074_proxy_replay_attribution/rebuilt_c9_v2_stage005_stage074_proxy_replay_attribution_daily_components_stage005_stage074_proxy_replay_attribution_v1.csv.gz`
- quality：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage005_stage074_proxy_replay_attribution/rebuilt_c9_v2_stage005_stage074_proxy_replay_attribution_window_attribution_stage005_stage074_proxy_replay_attribution_v1.csv`

## 结论

- 本阶段结论：Stage074 residual 主要来自 Stage013 母本持仓路径，尤其是 base holding PnL；Stage070 AI proxy lot 不是主因，合计反而为正。
- 是否进入下一步：是。
- 下一步：停止沿 `full_market_ai_top8_and_active_positions_lt3`、top8、active<3、ramp floor/days、sleeve 数继续救参；下一步应做 Stage013 base holding 的 product/direction/position 级归因，或者直接写真实 engine 验证账户层结构，而不是继续优化 AI proxy。

## 过拟合反思

- 运行前判断：不过拟合，本阶段只重放代理分量，不设计新参数。
- 运行后判断：不过拟合。
- 原因：没有把窗口归因转换成品种/方向/日期黑名单，也没有新增交易阈值；只是反证“AI proxy 是 residual 主因”。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Stage005 把 Stage004 的 unsplit residual 拆开，直接排除了继续浅层调 AI proxy 的方向，并把下一步收敛到母本持仓路径或真实 engine。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、重要突破或跨线合入摘要
