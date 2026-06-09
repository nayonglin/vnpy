# Stage024 入场后顺畅K线一次性延迟 prev2day_stop 真实 A/C

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：day
- 记录时间：2026-06-09 00:20 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：真实 A/C 多起点回测
- 是否重要突破：是，反证退出延迟交易化路线
- 是否触发A/B：是，已读取并遵循 `skills/version-ab-experiment/SKILL.md`

## 外部调研与判断

- 参考资料：
  - SIAM `Trend Following Trading under a Regime Switching Model`：趋势跟随要持有趋势直到趋势结束证据出现，但“结束证据”必须能穿越不同 regime。
  - DNS Research `How Trend Following Works in Modern Markets`：跟踪止损可让利润奔跑，但在震荡市场容易被洗出；退出规则是趋势策略核心风险点。
  - NexusFi `Automated Position Management in Futures Trading`：趋势确认后的持仓管理必须受风险上限约束，不能只因机会看起来高质量就放大风险。
- 我的判断：Stage740 的两个标签有解释力，但真实规则必须证明不是只改善 `2024-2025` 右尾窗口。本阶段只测一次性延迟，不扫延迟天数、阈值、品种或方向。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage741_postentry_quality_prev2day_relax_ac.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无
- 新增参数：
  - `enable_post_entry_quality_prev2day_relax`
  - `post_entry_quality_prev2day_relax_feature`
  - 诊断变量 `post_entry_quality_prev2day_relax_skip_count`
  - `ProductState.post_quality_prev2day_relax_done`
- 修改参数：
  - 修正 `post_quality` 内部 `avg_adverse_wick_pct` 方向口径，使 long 不利影线为上影线、short 不利影线为下影线；该功能默认关闭，不改变正式版默认路径。
- 删除参数：无

## 回测/归因参数

- A：正式 Stage372/20万 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
- C1：`post1_smooth_directional_combo` 出现后，当前持仓最多一次延迟 `prev2day_stop`
- C2：`post5_long60_ratio_le20` 出现后，当前持仓最多一次延迟 `prev2day_stop`
- 数据区间：`full_2020_20260430`、`since_2021` 到 `since_2026`、`phase_2020_2021`、`phase_2022_2023`、`phase_2024_2025`、`phase_2026_latest`
- 账户规模：20万
- 成本口径：正常成本 + 2x/3x 成本压力
- 策略口径：不加仓、不扩大初始风险、不改 AI、不改品种池、不扫延迟天数

## 结果

- A 期末权益：`8,728,285`
- A 总收益：`4264.1425%`
- A 最大回撤：`-38.6713%`
- A Sharpe：`1.6279`
- A 总滑点：`506,220`
- A 总交易次数：`633`
- A 胜率：`52.2586%`
- C1 期末权益：`6,764,990`
- C1 总收益：`3282.4950%`
- C1 最大回撤：`-38.4013%`
- C1 Sharpe：`1.5544`
- C1 总滑点：`398,920`
- C1 总交易次数：`630`
- C1 胜率：`51.9043%`
- C1 触发延迟：`10`
- C1 全周期相对 A：期末权益 `-1,963,295`，Sharpe `-0.0734`，不晋级
- C2 期末权益：`6,117,135`
- C2 总收益：`2958.5675%`
- C2 最大回撤：`-38.3586%`
- C2 Sharpe：`1.5374`
- C2 总滑点：`361,480`
- C2 总交易次数：`615`
- C2 胜率：`50.8913%`
- C2 触发延迟：`36`
- C2 全周期相对 A：期末权益 `-2,611,150`，Sharpe `-0.0904`，不晋级
- 多起点关键归因：
  - `phase_2024_2025`：C1 `+148,455`，C2 `+168,825`，说明特征确实能抓到局部右尾窗口。
  - `phase_2020_2021`：C1 `-208,155`，C2 `-328,830`，早期复利底座被削弱。
  - `since_2022/since_2023`：仅 `+360/+1,620` 和 `+820/+2,010` 的微弱改善，材料性不足。
  - `since_2026`：无材料变化。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage741_postentry_quality_prev2day_relax_ac_report_stage741_postentry_quality_prev2day_relax_ac_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage741_postentry_quality_prev2day_relax_ac_summary_stage741_postentry_quality_prev2day_relax_ac_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage741_postentry_quality_prev2day_relax_ac_curves_stage741_postentry_quality_prev2day_relax_ac_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage741_postentry_quality_prev2day_relax_ac_comparison_stage741_postentry_quality_prev2day_relax_ac_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage741_postentry_quality_prev2day_relax_ac_chart_stage741_postentry_quality_prev2day_relax_ac_v1.png`

## 结论

- 本阶段结论：退出延迟路线不晋级。它能改善 `2024-2025` 局部右尾，但破坏 `2020-2021` 早期复利底座，全周期收益和 Sharpe 明显弱于正式版。
- 是否进入下一步：否。
- 下一步：停止围绕 post-entry 顺畅 K 线做真实加仓或延迟退出救参；该标签只保留为复盘/forward watch。若继续寻找高质量机会，只能换新信息源、账户级 selector 或等待 OOS 样本。

## 过拟合反思

- 运行前判断：中等风险；特征来自 Stage740 固定观察闸门，但退出规则可能拟合 `2024-2025`。
- 运行后判断：继续救参会过拟合。
- 原因：规则在 `phase_2024_2025` 很好，但全周期失败，且失败来自早期复利底座被削弱；如果继续扫延迟 `2/3` 天、放宽/收紧 post 特征、叠品种/方向/年份，就是按局部右尾窗口调参。

## 继续价值反思

- 运行前判断：有价值，因为 Stage740 给出可验证的退出管理候选。
- 运行后判断：本形状没有继续价值。
- 原因：最小低自由度 A/C 已经反证；进一步复杂化只会提高自由度，无法证明普适。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，路线级反证
