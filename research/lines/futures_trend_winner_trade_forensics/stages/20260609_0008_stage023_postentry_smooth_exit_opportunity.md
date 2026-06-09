# Stage023 入场后顺畅K线与正式退出后机会损失审计

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：day
- 记录时间：2026-06-09 00:08 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因、退出/持有质量解释
- 是否重要突破：否，但给出下一步真实 A/C 的固定候选
- 是否触发A/B：否，本阶段不改策略，只做退出后机会归因

## 外部调研与判断

- 参考资料：
  - SIAM `Trend Following Trading under a Regime Switching Model`：趋势跟随的结构目标是较早捕捉趋势、持有趋势，并在趋势结束证据出现时退出。
  - DNS Research `How Trend Following Works in Modern Markets`：退出/跟踪止损决定趋势系统能否让利润奔跑，但过紧会被震荡洗出。
  - NexusFi `Automated Position Management in Futures Trading`：加仓/持仓管理必须避免在接近跟踪止损时增加风险，否则会放大账户风险。
- 我的判断：用户看到的“影线短/走势干净”更像入场后市场给出方向确认，而不是入场前静态筛选。它不能直接扩大初始风险，但可以先验证是否解释正式退出后的机会损失。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage740_postentry_smooth_exit_opportunity.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：退出后观察窗口 `3/5/10/20` 根合约日线；主窗口 `20`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：正式 Stage719 closed lots，2020-01 至 2026-04-30
- 账户规模：参考正式 Stage372/20万
- 成本口径：本阶段不是权益回测，不重算成本
- 样本过滤：读取 Stage735 已通过的 post-entry 质量标签；只观察真实 closed lots 退出后的合约日线
- 策略/归因口径：以正式退出价为锚，计算退出后顺势最大机会 R、反向最大风险 R、20根收盘后净变化 R，以及 `+1R` 与 `-1R` 谁先发生

## 结果

- 正式版参考期末权益：`8,728,285`
- 正式版参考总收益：`4264.1425%`
- 正式版参考最大回撤：`-38.6713%`
- 正式版参考 Sharpe：`1.6279`
- 正式版参考总滑点：`506,220`
- 正式版参考总交易次数：`633`
- 正式版参考胜率：`52.2586%`
- 归因结果：
  - baseline 20根有效样本 `313`，退出后 `>=2R` 顺势机会率 `57.5080%`，`>=1R` 反向风险率 `65.1757%`，clean `>=1R` 率 `32.2684%`，20根收盘后平均 `+1.7354R`
  - `post5_long60_ratio_le20`：`33` 笔，覆盖 `7` 年 `14` 品种，退出后 `>=2R` 率 `72.7273%`，lift `+15.2193pp`；反向 `>=1R` 率 `60.6061%`，lift `-4.5697pp`；clean `>=1R` 率 `39.3939%`，lift `+7.1256pp`
  - `post1_smooth_directional_combo`：`56` 笔，覆盖 `7` 年 `18` 品种，退出后 `>=2R` 率 `66.0714%`，lift `+8.5634pp`；反向 `>=1R` 率 `58.9286%`，lift `-6.2471pp`；clean `>=1R` 率 `37.5000%`，lift `+5.2316pp`
  - 通过观察闸门分组数：`2`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage740_postentry_smooth_exit_opportunity_report_stage740_postentry_smooth_exit_opportunity_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage740_postentry_smooth_exit_opportunity_group_metrics_stage740_postentry_smooth_exit_opportunity_v1.csv`
- daily：无
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage740_postentry_smooth_exit_opportunity_enriched_exit_lots_stage740_postentry_smooth_exit_opportunity_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage740_postentry_smooth_exit_opportunity_chart_stage740_postentry_smooth_exit_opportunity_v1.png`

## 结论

- 本阶段结论：post-entry 顺畅 K 线确实能解释一部分正式退出后的机会损失，但同时反向风险仍高，不能直接当作扩大初始风险的依据。
- 是否进入下一步：是，只允许进入最小化真实 A/C：不加仓、不扩大风险，只测试一次性延迟 `prev2day_stop`。
- 下一步：Stage741 对 `post1_smooth_directional_combo` 与 `post5_long60_ratio_le20` 做真实多起点 A/C。

## 过拟合反思

- 运行前判断：否，本阶段只用 Stage735 已固定标签，不新增阈值。
- 运行后判断：仍否，但只能作为解释，不得把退出后 20 根机会直接当交易收益。
- 原因：退出后窗口是未来信息，只能说明现有退出可能早，不能直接生成规则。

## 继续价值反思

- 运行前判断：有价值，因为真实加仓路线已失败，退出/持有质量是剩下的结构方向。
- 运行后判断：有价值但必须快速进入真实 A/C 反证。
- 原因：两个标签跨年份/品种有观察信号，但真正能否改善权益必须由真实引擎验证。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：后续 Stage741 决策后一并更新
- 是否追加根目录 `memory.md/back_log.md`：后续 Stage741 决策后一并追加
