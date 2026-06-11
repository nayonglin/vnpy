# Stage802 Stage777候选版 lower-high + 双阴线多头过滤 年度起点回测

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：`2026-06-11 12:45 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 年度起点验证
- 是否重要突破：否
- 是否触发A/B：是，入场过滤规则可能接入 Stage777 官方候选，因此按 A/C 验证

## 外部调研与判断

- 参考资料：
  - Gate Learn：lower highs/lower lows 通常表示动能减弱和下行结构。
  - TradingSim：趋势交易需要趋势过滤、回撤入场和客观退出，不能只靠单个蜡烛形态。
  - GitHub `fmzquant/strategies`：价格结构里的 HH/HL/LH/LL 与蜡烛形态常被组合做视觉标签，但不是天然可推广的硬过滤规则。
- 我的判断：
  - `lower-high` 有结构含义，但 Stage800 已证明单独拦截会砍右尾。
  - 本阶段把用户提出的“双阴线”作为卖压确认，只用于减少误拦截；如果年度起点不能广泛改善收益/回撤，就不能继续调细节救参。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage802_stage777_lower_high_bearish2_yearly.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`block_long_lower_high_bearish2=True`
- 修改参数：相对 Stage800，拦截条件从单纯 `high[t] < high[t-1] < high[t-2]` 收窄为同时要求 `open[t] > close[t]` 且 `open[t-1] > close[t-1]`
- 删除参数：无

## 回测/归因参数

- 数据区间：年度起点 `2018-01-01` 至 `2026-01-01`，统一终点 `2026-05-29`
- 账户规模：`500,000`
- 成本口径：沿用 Stage777 官方候选缓存/回测成本口径
- 样本过滤：全体 `9` 个年度起点；成熟样本剔除 `2026-01`，共 `8` 个年度起点
- 策略/归因口径：
  - A：`official_candidate_stage777_50w_am41_oi08_old_ai_v1`
  - C：A + 多头过滤：若最新三根已完成日线 `high[t] < high[t-1] < high[t-2]`，且最新两根已完成K线均 `open > close`，则不发多头新开/反手/换月重开信号
  - 保持不变：50万、`AM41`、基础风险 `0.40`、OI命中恢复 `0.80`、旧正式AI池、`maxpos4`、关闭连败缩放和 recovery sleeve

## 结果

- 期末权益：多起点对照，不使用单一总期末权益概括；见 yearly comparison
- 总收益：
  - 全体年度起点：C 收益胜出 `2/9`，收益差中位 `-27.920pp`
  - 成熟样本：C 收益胜出 `2/8`，收益差中位 `-85.194pp`
- 最大回撤：
  - 全体年度起点：C 回撤胜出 `3/9`，回撤差中位 `0.0000pp`
  - 成熟样本：C 回撤胜出 `3/8`，回撤差中位 `-0.0638pp`
  - DD40失败：A `4` 个，C `4` 个
  - DD50失败：A `0` 个，C `2` 个
- Sharpe：
  - 全体年度起点：C Sharpe 胜出 `2/9`，Sharpe 差中位 `-0.0418`
  - 成熟样本：C Sharpe 胜出 `2/8`，Sharpe 差中位 `-0.0482`
- 总滑点：成熟样本滑点差中位 `-27,380`
- 总交易次数：成熟样本交易次数差中位 `-7`
- 胜率：详见 summary CSV
- 其他关键指标：
  - C 总共拦截多头信号 `85` 次；成熟样本 `83` 次
  - Stage800 原始 lower-high 拦截年度总数为 `261` 次，Stage802 收窄后降为 `85` 次
  - `2018-01`：收益 `3550.253% -> 2884.452%`，差 `-665.801pp`；回撤 `-49.4213% -> -50.0500%`
  - `2019-01`：收益 `4137.990% -> 3335.132%`，差 `-802.858pp`；回撤 `-49.3661% -> -50.2847%`
  - `2024-01`：收益 `82.388% -> 85.902%`，差 `+3.514pp`
  - `2025-01`：收益 `83.832% -> 87.362%`，差 `+3.530pp`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage802_stage777_lower_high_bearish2_yearly_report_stage802_stage777_lower_high_bearish2_yearly_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage802_stage777_lower_high_bearish2_yearly_summary_stage802_stage777_lower_high_bearish2_yearly_v1.csv`
- orders：无单独订单输出
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage802_stage777_lower_high_bearish2_yearly_curves_stage802_stage777_lower_high_bearish2_yearly_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage802_stage777_lower_high_bearish2_yearly_aggregate_stage802_stage777_lower_high_bearish2_yearly_v1.csv`
- 拦截明细：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage802_stage777_lower_high_bearish2_yearly_blocks_stage802_stage777_lower_high_bearish2_yearly_v1.csv`
- 图表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage802_stage777_lower_high_bearish2_yearly_equity_curves_stage802_stage777_lower_high_bearish2_yearly_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage802_stage777_lower_high_bearish2_yearly_return_delta_bar_stage802_stage777_lower_high_bearish2_yearly_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage802_stage777_lower_high_bearish2_yearly_dd_delta_bar_stage802_stage777_lower_high_bearish2_yearly_v1.png`

## 结论

- 本阶段结论：`stage802_lower_high_bearish2_yearly_not_promoted`
- 是否进入下一步：否
- 下一步：
  - 不把该规则接入官方候选。
  - 不继续扫 `lower-high` 天数、阴线数量、等号、只过滤某个 case 或只过滤某个年份。
  - 如果继续 K 线质量特征，应换成更一阶的顺畅趋势/波动压缩/突破后延续特征，并预声明后再多起点验证。

## 过拟合反思

- 运行前判断：过拟合风险中等。它来自亏损图视觉观察，但“双阴线”是价格行为的结构确认，不是任意小数阈值。
- 运行后判断：继续推进会转为过拟合。
- 原因：收窄后仍不能广泛改善年度起点，且把 `2018/2019` 早期复利路径推过 DD50；若再调天数或局部适配，就是在救一个已被多起点反证的形状。

## 继续价值反思

- 运行前判断：有价值。Stage800 太粗，用户提出的条件能检验“是否只是缺少卖压确认”。
- 运行后判断：该硬过滤继续价值低。
- 原因：它确实减少误拦截数量，但没有把回撤改善转化为稳健收益/风险优势；只在 `2024/2025` 短起点略胜，不足以覆盖早期右尾损失。

## 合入建议

- 是否更新本线 `LINE.md`：否，本阶段不是重要突破。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不更新 `memory.md`。
