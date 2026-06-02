# Stage216 保证金感知 sizing 粗前沿

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 19:25 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读结构实验；固定 Stage079/C3 信号、品种池和 Stage103 xsmom 真实腿，只改粗档资金壳、sizing cap 与保证金预算。
- 是否重要突破：否，但是否决一个重要方向：静态 sizing cap / 保证金预算可以让 exact margin 合格，但收益保留严重不足。
- 是否触发A/B：否。本阶段不是准备接入正式版本，而是部署可承载性归因。

## 外部调研与判断

- 参考资料：
  - SHFE investor clearing / settlement 页面：交易保证金、结算准备金和风险处置是交易所层面的真实约束。
  - CFFEX 规则页面：交易保证金、限仓、强平、风险控制同样是实盘约束，不是回测展示指标。
  - vn.py / VeighNa GitHub：框架提供组合策略、风险管理、组合管理等模块，风控应进入下单/持仓管理层，而不是只做事后报表。
- 我的判断：Stage215 之后，任何候选都必须先过 exact position margin；但单纯把 `sizing_equity_cap` 固定到 40万/50万，等于砍掉 no-cap 复利扩张，不是低成本修复。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage516_margin_aware_sizing_frontier.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `sizing_equity_cap=0/400000/500000`
  - `max_capital_usage_ratio=0.70/0.80/0.90`
  - `max_single_trade_capital_usage_ratio=0.45/0.50/0.70`
  - `enable_incremental_margin_budget_gate=True/False`
- 修改参数：无正式策略参数修改；只在实验脚本内使用粗档覆盖。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：`615,000` 账户口径，其中 C3 回测引擎 `500,000`，xsmom true leg 复用 Stage208/209 冻结日度真实成交路径。
- 成本口径：1x/2x/3x 滑点压力；broker10 保证金按 exact position margin 乘 `1.10`。
- 样本过滤：无日期/品种过滤；全周期、起始年、分段、63/126/252/504 任意持有窗口。
- 策略/归因口径：next-real C3 真实引擎重跑 + Stage103 xsmom true daily；所有候选使用 exact position margin 验收。

## 结果

### true no-cap legacy 对照

- `r060_legacy_nocap_u90`：
  - 期末权益 `20,682,740`
  - 总收益 `3263.0472%`
  - 最大回撤 `-36.2870%`
  - Sharpe `1.5114`
  - Ulcer `15.5580`
  - 总滑点 `1,231,020`
  - 总交易次数约 `978`
  - 非零日胜率 `52.8614%`
  - broker10 exact 最大保证金/权益 `138.9327%`
  - 穿 100% 天数 `17`
- `r070_legacy_nocap_u90`：
  - 期末权益 `21,210,535`
  - 总收益 `3348.8675%`
  - 最大回撤 `-38.5861%`
  - Sharpe `1.4353`
  - Ulcer `16.6764`
  - 总滑点 `1,228,400`
  - 总交易次数约 `973`
  - 非零日胜率 `52.4887%`
  - broker10 exact 最大保证金/权益 `140.3161%`
  - 穿 100% 天数 `25`

### 保证金合格但收益塌缩的 cap 版本

- 最优综合候选 `r080_cap400_u80`：
  - 期末权益 `2,859,850`
  - 总收益 `365.0163%`
  - 最大回撤 `-13.6572%`
  - Sharpe `1.8618`
  - Ulcer `4.7679`
  - 总滑点 `95,220`
  - 总交易次数约 `812`
  - 非零日胜率 `53.8961%`
  - broker10 exact 最大保证金/权益 `56.2184%`
  - 穿 100% 天数 `0`
  - 相对 Stage079 部署收益保留 `7.3781%`
- 收益最高 cap 档 `r080_cap500_u80`：
  - 期末权益 `3,001,010`
  - 总收益 `387.9691%`
  - 最大回撤 `-16.4634%`
  - broker10 exact 最大保证金/权益 `61.1048%`
  - 相对 Stage079 部署收益保留 `7.8421%`
- 126日持有体验：
  - no-cap `r060` 最差126日收益 `-27.9963%`，p10 `-2.9637%`，正收益率 `84.8506%`
  - `r080_cap400_u80` 最差126日收益 `-7.0201%`，p10 `-2.0198%`，正收益率 `85.6330%`
  - cap 版本体验更浅，但收益上限被大幅压低。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage516_margin_aware_sizing_frontier_report_stage516_margin_aware_sizing_frontier_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage516_margin_aware_sizing_frontier_chart_stage516_margin_aware_sizing_frontier_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage516_margin_aware_sizing_frontier_decision_stage516_margin_aware_sizing_frontier_v1.json`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage516_margin_aware_sizing_frontier_summary_stage516_margin_aware_sizing_frontier_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage516_margin_aware_sizing_frontier_cost_stress_stage516_margin_aware_sizing_frontier_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage516_margin_aware_sizing_frontier_rolling_holding_stage516_margin_aware_sizing_frontier_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage516_margin_aware_sizing_frontier_margin_daily_stage516_margin_aware_sizing_frontier_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage516_margin_aware_sizing_frontier_positions_stage516_margin_aware_sizing_frontier_v1.csv`

## 图表视觉复盘

- no-cap legacy 净值线远高于全部 cap 版本，但保证金线多次穿越 100%，散点落在“收益保留高、保证金不合格”右上角。
- cap500/cap400 版本保证金曲线稳定压在 90% 以下，散点落在“可下单、收益保留极低”左下角；净值从 no-cap 的 30倍以上变成约 3-5倍。
- cap 版本水下回撤明显更浅、更平滑，但这主要是降杠杆，不是策略本体 alpha 提升。

## 结论

- 本阶段决策：`margin_aware_sizing_hard_pass_but_return_or_90cap_weak`。
- 静态 sizing cap / 开仓保证金预算能把 exact broker10 保证金压到安全区，但收益保留只有约 `6.54%-7.84%`，不满足“保留大部分收益”。
- true no-cap legacy 复刻了 Stage214 的收益和保证金压力：收益仍强，但 exact margin 不能实盘承载。
- 因此不要继续扫 `sizing_equity_cap=45万/55万`、`risk=0.75/0.85` 或保证金预算小数；这条形状的本质是“用砍复利解决保证金”，不是好解。

## 后续规划和 TODO

- TODO 1：转向持仓期主动 deleveraging，而不是只在开仓时限制保证金；核心问题是 no-cap 持仓随权益扩张后，已持仓保证金会在价格/权益路径中继续上升。
- TODO 2：做“保证金贡献驱动的分层减仓”粗实验，只允许通用规则，例如 broker10 预估超过 90/100% 时按保证金贡献削减新增层或最弱趋势层，不按品种黑名单。
- TODO 3：继续寻找保证金轻、低相关、可真实承载的独立收益源；不要再用外部现金摊薄收益或静态 cap 砍掉复利。

## 过拟合反思

- 运行前判断：否。只测试资金承载结构，不改信号，不按坏窗口筛品种/日期。
- 运行后判断：否。粗档 cap 是工程约束验证，不是收益曲线拟合。
- 原因：实验结论是否决性，且直接来自 exact position margin 与收益保留的基本权衡。

## 继续价值反思

- 运行前判断：是。Stage215 后必须知道保证金感知 sizing 是否能救。
- 运行后判断：继续有价值，但不在静态 cap 方向。
- 原因：本阶段确认“能守保证金但收益塌缩”，下一步价值在主动持仓减风险或新低保证金收益源。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage216 当前状态。
- 是否更新 `research/registry.md`：是，当前研究线最新阶段从 Stage215 更新到 Stage216。
- 是否追加根目录 `memory.md/back_log.md`：是。本阶段否决静态 sizing cap / 保证金预算救援，是后续避免重复试错的重要结论。
