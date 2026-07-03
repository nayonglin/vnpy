# Stage004 oracle 剩余亏损窗口路径归因

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02 02:58 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因，不新增交易规则，不修改官方实盘/CTP/邮件/launchd
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Man Group: Trend Following and Drawdowns: Is This Time Different? https://www.man.com/insights/is-this-time-different
  - Interactive Brokers: PnL Explain vs PnL Predict https://www.interactivebrokers.com/campus/ibkr-quant-news/pnl-explain-vs-pnl-predict-why-this-distinction-actually-matters/
  - GitHub pysystemtrade: https://github.com/pst-group/pysystemtrade
- 我的判断：
  - 趋势系统左尾不能先假设是 AI 选品或 OI 阈值问题；如果剩余亏损主要来自持仓路径或只有资金曲线的 ramp 残差，继续扫 topN、ramp floor、OI share 会加重过拟合。
  - Stage003 已证明 Stage052+Stage074 的 oracle 上界仍失败，Stage004 应先做 PnL explain，把剩余窗口拆成 holding/trading/cost/proxy_delta/unsplit equity-delta。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage004_oracle_residual_path_attribution.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage004_oracle_residual_path_attribution.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `TOP_N_WINDOWS=1000`
  - `RAMP_FLOOR=0.35`
  - `RAMP_TRADING_DAYS=252`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage003 oracle worst windows；底层曲线覆盖 `2018-01` 到 `2026-06-30`
- 账户规模：沿用上游 C9/15w 代理曲线
- 成本口径：读取曲线内 `commission` / `slippage`；Stage074 panel 无成本拆分
- 样本过滤：Stage003 oracle 剩余亏损窗口按 `oracle_return_pct` 最差取 top1000
- 策略/归因口径：
  - 若 oracle winner 为 Stage052，则用 `stage052_account_equity`、`stage052_daily_delta`、base `holding_pnl/trading_pnl/cost` 做 base+proxy 拆分。
  - 若 oracle winner 为 Stage074 ramp，则用 Stage074 raw equity 自窗口起点重置 ramp 后计算 equity delta；因 Stage074 panel 无 positions/holding/trading 明细，归为 `unsplit_equity_delta_pnl`。

## 结果

- 期末权益：不适用，归因审计非新回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：`8,805,370`，仅来自可拆分的 Stage052 proxy winner 窗口
- 总交易次数：Stage074 ramp winner 无交易明细；可拆分窗口内交易次数见 window attribution
- 胜率：不适用
- 其他关键指标：
  - 决策：`stage004_stage074_ramp_residual_dominant_need_true_position_replay`
  - 归因窗口数：`1000`
  - oracle 最差收益：`-23.6338%`
  - Stage074 ramp 胜出窗口：`929/1000 = 92.9%`
  - Stage052 proxy 胜出窗口：`71/1000 = 7.1%`
  - `unsplit_equity_delta_pnl`：`-393,618,593.7166`
  - `unsplit_loss_share_pct`：`90.9413%`
  - `holding_loss_share_pct`：`11.8586%`
  - `trading_loss_share_pct`：`1.7706%`
  - `cost_loss_share_pct`：`2.0344%`
  - broker10 压力窗口：`54`
  - active>=4 压力窗口：`71`

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage004_oracle_residual_path_attribution/rebuilt_c9_v2_stage004_oracle_residual_path_attribution_report_stage004_oracle_residual_path_attribution_v1.md`
- summary：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage004_oracle_residual_path_attribution/rebuilt_c9_v2_stage004_oracle_residual_path_attribution_source_summary_stage004_oracle_residual_path_attribution_v1.csv`
- orders：不适用
- daily：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage004_oracle_residual_path_attribution/rebuilt_c9_v2_stage004_oracle_residual_path_attribution_window_attribution_stage004_oracle_residual_path_attribution_v1.csv`
- quality：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage004_oracle_residual_path_attribution/rebuilt_c9_v2_stage004_oracle_residual_path_attribution_decision_stage004_oracle_residual_path_attribution_v1.json`

## 结论

- 本阶段结论：Stage003 oracle 剩余最差窗口主要不是 Stage052 的可拆分 holding/trading 问题，而是 Stage074 ramp 胜出窗口占绝对多数；当前 Stage074 只有资金曲线，无法精确回答亏损来自哪些品种、方向、持仓还是交易实现。
- 是否进入下一步：是。
- 下一步：不要继续扫 Stage052/Stage074 简单组合、OI 阈值、ramp floor/days 或 sleeve 数；应重放 Stage074 对应 `full_market_ai_top8_and_active_positions_lt3` 的真实 positions / daily PnL 明细，再对 `2021-10 -> 2023-10/11`、`2022-07 -> 2023-07` 做产品/方向/持仓路径归因。

## 过拟合反思

- 运行前判断：不过拟合，本阶段只做剩余亏损窗口归因，不产生可交易参数。
- 运行后判断：不过拟合。
- 原因：没有优化阈值，也没有用结果反推新规则；只是暴露当前上界审计缺少 Stage074 明细，防止后续在假精度上调参。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Stage004 直接指出下一步的瓶颈是 Stage074 positions replay，而不是继续浅层扫参；这能减少无效实验。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、重要突破或跨线合入摘要
