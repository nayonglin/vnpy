# Stage011 焦点窗口持仓 PnL 归因

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 13:15 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读重跑与持仓归因；不改策略、不扫参数、不连接 CTP、不调用下单。
- 是否重要突破：是。补齐 Stage006 缺失的 positions 证据，并把 Stage010 的账户权益损失残差解释到日级持仓 PnL。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - AQR/Hurst-Ooi-Pedersen, `A Century of Evidence on Trend-Following Investing`。
  - Bailey/Borwein/Lopez de Prado/Zhu, `The Probability of Backtest Overfitting`。
  - Hood/Raughtigan, `Volatility Targeting Is Trendy`。
- 我的判断：左尾保护不能围绕 `2022-07 -> 2023-07` 单窗口做黑名单或阈值拟合；必须先用 positions 证明亏损来自已有仓位还是窗口后新增/交易仓位。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage011_focus_window_position_pnl.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：焦点窗口继承 Stage010：`2022-07-15 -> 2023-07-17`；source 继承 Stage010 覆盖的 `10` 个冷启动账户。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：每个 source 从各自起点重跑到 `2023-07-17`，归因窗口为 `2022-07-15` 到 `2023-07-17`。
- 账户规模：C9/15w live profile，沿用 Stage167/Stage006 口径。
- 成本口径：沿用当前 C9 引擎、滑点与手续费设置；不做成本倍数压力。
- 样本过滤：Stage010 焦点窗口覆盖的 `10` 个 source：`2018-01` 到 `2022-07`。
- 策略/归因口径：保存 `positions`，按窗口起点已有仓位 vs 窗口后新增/交易仓位分桶；按品种/方向拆 `net_pnl/holding_pnl/trading_pnl/slippage`。

## 结果

- 期末权益：不适用，本阶段不是完整候选回测。
- 总收益：不适用；焦点窗口持仓净损失合计 `-19,235,925`。
- 最大回撤：不适用；使用 Stage010 窗口回撤结果。
- Sharpe：不适用。
- 总滑点：窗口内 `813,190`，其中新增/交易仓位 `779,890`，已有仓位 `33,300`。
- 总交易次数：窗口内 `602`，其中新增/交易仓位 `564`，已有仓位 `38`。
- 胜率：不适用，本阶段按日级 positions PnL 归因。
- 其他关键指标：
  - 重新生成 curve rows：`7,985`。
  - positions rows：`1,758,359`。
  - window position rows：`1,186`。
  - 一致性最大差异：`9.31e-10`，可视为完全对齐。
  - 窗口起点已有仓位亏损：`7,324,390`，亏损占比 `38.08%`。
  - 窗口后新增/交易仓位亏损：`11,911,535`，亏损占比 `61.92%`。
  - 最大品种/方向拖累：`SM.CZCE short opened_or_traded_after_focus_start`，`net_pnl=-2,767,260`，其中 `holding_pnl=-4,021,660`、`trading_pnl=+1,310,360`。
  - 最大单日合计亏损：`2022-07-18`，跨 source 合计 `net_pnl=-6,539,320`，主要为 holding_pnl。
  - 保证金压力观察：`2022-11-28` 多个 source 的 broker10 margin/equity 接近 `90%`，但最大单日亏损 `2022-07-18` 主要不是高保证金日，而是 4 个活跃合约的隔夜/日级 holding_pnl 冲击。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage011_focus_window_position_pnl/rebuilt_c9_stage011_focus_window_position_pnl_report_stage011_focus_window_position_pnl_v1.md`
- summary：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage011_focus_window_position_pnl/rebuilt_c9_stage011_focus_window_position_pnl_source_bucket_summary_stage011_focus_window_position_pnl_v1.csv`
- orders：不适用。
- daily：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage011_focus_window_position_pnl/rebuilt_c9_stage011_focus_window_position_pnl_daily_summary_stage011_focus_window_position_pnl_v1.csv`
- quality：不适用。
- positions：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage011_focus_window_position_pnl/rebuilt_c9_stage011_focus_window_position_pnl_positions_stage011_focus_window_position_pnl_v1.csv`
- chart：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage011_focus_window_position_pnl/rebuilt_c9_stage011_focus_window_position_pnl_chart_stage011_focus_window_position_pnl_v1.png`

## 结论

- 本阶段结论：Stage009/010 左尾主要不是“已有仓位一路拖死”，而是窗口后新增/交易仓位贡献了约 `61.92%` 的净亏损；因此下一步更像是研究“账户状态差时的新开仓风险释放/风险预算闸门”，而不是单纯已有仓位减仓。
- 是否进入下一步：是。
- 下一步：Stage012 先做只读可见状态诊断，检查新增/交易仓位发生时的账户 drawdown、broker10、active products、same-direction 相关性、AI rank/质量标签、是否处于 2022-07-18/2022-11-28 这类集群风险环境；冻结一个不按品种/日期拟合的候选保护形状后，再做真实引擎。

## 过拟合反思

- 运行前判断：否。只补 positions 路径证据，不设计新规则、不选择参数。
- 运行后判断：否。没有将 `SM.CZCE short` 或 `2022-07-18` 反推成黑名单/日期规则。
- 原因：结论停留在机制层面：新增/交易仓位与 holding_pnl 左尾占主导，不能用单点品种/日期去修。

## 继续价值反思

- 运行前判断：是。Stage010 的 closed_lots 净额解释不了账户损失，必须拆 holding_pnl。
- 运行后判断：有。现在已经知道下一步应优先研究新增/交易仓位的账户状态闸门，而不是砍高质量加风险或按闭合 lot 黑名单。
- 原因：如果保护新增仓位能在多窗口减少左尾，同时不砍右尾，才可能接近用户目标；否则继续盲目加风险没有意义。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage011 结论和 Stage012 方向。
- 是否更新 `research/registry.md`：是，最新关键阶段更新到 Stage011。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段仍为本研究线内部归因，不是正式候选。
