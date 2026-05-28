# Stage110 Stage103商品动量拥挤闸门Scout

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-27 21:00 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：结构性风险叠加审计；固定 Stage103，测试额外商品动量袖子是否能用急涨拥挤闸门修复冷启动风险。
- 是否重要突破：否。短持有体验显著提升，但仍未通过硬约束，因此不晋级。
- 是否触发A/B：是。A=`Stage079`；C0=`Stage103 broker10_guard`；C1=`Stage103+60日商品动量周频`；C2=`C1+急涨拥挤闸门`；C3=`Stage103+120日商品动量月频+急涨拥挤闸门`。

## 外部调研与判断

- 参考资料：
  - 商品期货多因子研究常见组合为趋势、横截面动量和期限结构/Carry，例如 `Tactical allocation in commodity futures markets: Combining momentum and term structure signals`。
  - `Trend Following, Risk Parity and Momentum in Commodity Futures` 强调趋势跟随本身对风险调整收益和下行控制贡献很大，其他动量/风险平价调整的边际价值需要严格复验。
  - GitHub 上 `pysystemtrade`、`trend_following` 等框架强调多市场、多信号、风险预算和可执行复跑，而不是事后窗口补丁。
- 我的判断：Stage106 的商品动量袖子不是垃圾信号，它能明显改善收益与3/6个月体验；问题是同类动量在某些冷启动和高滑点条件下堆风险。Stage110 只允许做一个结构性检查：当 Stage079/C3 最近急涨时，不额外叠第二个商品动量袖子。若仍失败，就停止这条商品动量叠加路线。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage410_stage103_momentum_crowding_gate.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `HOT20_THRESHOLD=0.50`
  - `HOT60_THRESHOLD=0.75`
  - 固定规则：若上一交易日可知的 Stage079 权益20日涨幅 `>50%` 或60日涨幅 `>75%`，当日不叠加第二个商品动量袖子。
  - 商品动量对照：`60日周频top/bottom各3个品种每品种1手`；`120日月频top/bottom各3个品种每品种1手`。
- 修改参数：无。未修改 Stage103 的 `scale>=0.5`、`target_vol=10%`、`63日`、`broker10_guard=1.10`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：`615,000`，不增加资金占用。
- 成本口径：正常成本与 `2x/3x/5x` 滑点压力。
- 样本过滤：无品种、月份、日期过滤。
- 策略/归因口径：真实整数手复放；商品动量袖子受 `1.10` 保证金闸门和急涨拥挤闸门约束。

## 结果

Stage079 基准：

- 期末权益：`31,040,650`
- 总收益：`4947.2602%`
- 最大回撤：`-29.7007%`
- Sharpe：`1.3188`
- Ulcer：`15.0874`
- 总滑点：`1,556,750`
- 总交易次数：`757`
- 胜率：`45.3826%`

Stage103 `broker10_guard`：

- 期末权益：`31,730,915`
- 总收益：`5059.4984%`
- 最大回撤：`-28.9792%`
- Sharpe：`1.3681`
- Ulcer：`14.3132`
- 3个月分：`121.2041`
- 6个月分：`134.4513`
- 总滑点：`1,569,265`
- 总交易次数约：`1217`

`stage103_plus_mom60_weekly_min1_guard`：

- 期末权益：`32,437,815`
- 总收益：`5174.4415%`
- 最大回撤：`-27.3580%`
- Sharpe：`1.4044`
- Ulcer：`13.4922`
- 3个月分：`143.2053`
- 6个月分：`152.0460`
- 失败项：`start_2022` 最大回撤 `-35.3241%`；`5x` 滑点回撤 `-40.9311%`，差于 Stage079 `-40.1055%` 与 Stage103 `-39.1469%`。

`stage103_plus_mom60_weekly_hot_crowding_gate`：

- 期末权益：`32,499,845`
- 总收益：`5184.5276%`
- 最大回撤：`-27.1733%`
- Sharpe：`1.4114`
- Ulcer：`13.3439`
- 3个月分：`145.0161`
- 6个月分：`158.5803`
- 用户目标改善计数：`8/8` 与 `8/8`
- 失败项：`start_2022` 最大回撤仍为 `-35.3241%`；`5x` 滑点回撤 `-40.9311%`，差于 Stage079 与 Stage103。

`stage103_plus_mom120_monthly_hot_crowding_gate`：

- 期末权益：`32,227,670`
- 总收益：`5140.2715%`
- 最大回撤：`-28.4636%`
- Sharpe：`1.3836`
- Ulcer：`13.7637`
- 3个月分：`149.9587`
- 6个月分：`159.7414`
- 用户目标改善计数：`8/8` 与 `8/8`
- 失败项：`start_2022` 最大回撤 `-39.7689%`，10%保证金上浮下 `start_2022/start_2025` 有拒单风险；`5x` 滑点回撤 `-40.4304%`，差于 Stage079 与 Stage103。

急涨拥挤闸门归因：

- 急涨闸门触发 `418` 个交易日。
- `60日周频+急涨闸门` 的商品动量袖子 PnL 为 `3,760,190`，高于未加闸门的 `3,237,925`，说明闸门本身并非纯削弱收益。
- 但它没有修复真正的硬失败：`start_2022` 仍穿30，5倍滑点仍比基准差。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage410_stage103_momentum_crowding_gate_report_stage410_stage103_momentum_crowding_gate_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage410_stage103_momentum_crowding_gate_chart_stage410_stage103_momentum_crowding_gate_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage410_stage103_momentum_crowding_gate_summary_stage410_stage103_momentum_crowding_gate_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage410_stage103_momentum_crowding_gate_horizon_stage410_stage103_momentum_crowding_gate_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage410_stage103_momentum_crowding_gate_score_stage410_stage103_momentum_crowding_gate_v1.csv`
- fresh_start：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage410_stage103_momentum_crowding_gate_fresh_start_stage410_stage103_momentum_crowding_gate_v1.csv`
- cost_stress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage410_stage103_momentum_crowding_gate_cost_stress_stage410_stage103_momentum_crowding_gate_v1.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage410_stage103_momentum_crowding_gate_gate_stage410_stage103_momentum_crowding_gate_v1.csv`
- overlay_daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage410_stage103_momentum_crowding_gate_overlay_daily_stage410_stage103_momentum_crowding_gate_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage410_stage103_momentum_crowding_gate_decision_stage410_stage103_momentum_crowding_gate_v1.json`

## 结论

- 本阶段结论：`no_new_promotion`。
- 是否进入下一步：不进入当前正式优化候选；只保留为 paper 线索和经验。
- 我的判断：这几个商品动量叠加版本在正常路径下非常漂亮，甚至 3/6个月体验已经超过目标，但不值得放宽目标晋级。原因是它们失败在目标最核心的地方：`start_2022` 冷启动和 `5x` 高滑点压力，这不是小问题。
- 下一步：停止围绕商品动量 `60/120日`、周频/月频、急涨阈值或 top/bottom 数量继续救援。若继续追求目标，应转向真正不同风险暴露，而不是继续堆商品动量。

## 过拟合反思

- 运行前判断：不是过拟合。原因是只做一个固定结构性闸门，不扫描阈值、品种、月份或日期。
- 运行后判断：当前版本不构成新增过拟合，但若继续围绕急涨阈值救 `start_2022`，会转向过拟合。
- 原因：急涨闸门已经改善了全周期和短持有分，却没有碰到核心失败窗口；继续调阈值大概率只是拟合 `start_2022`。

## 继续价值反思

- 运行前判断：有价值。原因是 Stage106/109 都说明商品动量有收益，但需要确认是否能用低自由度拥挤控制解决硬失败。
- 运行后判断：这条子路线继续价值低；总目标仍有价值。
- 原因：额外商品动量袖子能显著提升体验，但硬约束失败，说明它不是当前目标的低过拟合解法。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加停止商品动量叠加救援边界。
- 是否更新 `research/registry.md`：是，最新阶段更新到 Stage110。
- 是否追加根目录 `memory.md/back_log.md`：建议只追加 `back_log.md`。
