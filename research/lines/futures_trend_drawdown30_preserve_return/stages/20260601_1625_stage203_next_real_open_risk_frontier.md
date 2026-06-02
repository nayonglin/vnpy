# Stage203 下一真实窗口固定风险预算前沿

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 16:25 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实可成交风险结构探索；不改入场/出场信号，只调全局风险预算
- 是否重要突破：边界突破。首次在下一真实窗口口径下找到 DD40 内的粗档位，但未达到最终晋级
- 是否触发A/B：否。仍有 fallback，且收益保留/成本压力未形成正式候选

## 外部调研与判断

- 参考资料：
  - Backtrader Orders：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - QuantConnect Understanding Time：https://www.quantconnect.com/docs/v1/key-concepts/understanding-time
  - Kim, Tse, Wald, Time series momentum and volatility scaling：https://doi.org/10.1016/j.finmar.2016.05.003
- 我的判断：
  - 固定风险预算属于事前账户结构，理论上不引入未来函数。
  - 但如果只靠 `0.61/0.62` 这种相邻小数跨线，就属于救历史；本阶段只看 `1.0/0.9/0.8/0.7/0.6/0.5` 粗前沿。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage503_next_real_open_risk_frontier.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `risk_multiplier=1.0/0.9/0.8/0.7/0.6/0.5`
  - 所有订单仍按 Stage202 下一真实窗口成交
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：`615,000`
- 策略规则、品种池、AI池、入场/出场逻辑：不变
- 成本口径：沿用 C3/Stage079 原始手续费、滑点、合约乘数、保证金设置；另做 `1x/2x/3x/5x` 滑点压力
- 样本过滤：无日期、品种、坏窗口过滤

## 前沿结果

| 版本 | 风险倍率 | 总收益 | 最大回撤 | 收益保留 | Sharpe | Ulcer | fallback |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `risk100` | `1.0` | `5139.1211%` | `-52.7518%` | `103.8781%` | `1.2077` | `19.3997` | `54` |
| `risk090` | `0.9` | `3539.6154%` | `-49.4887%` | `71.5470%` | `1.1365` | `20.7048` | `67` |
| `risk080` | `0.8` | `3505.9244%` | `-44.9640%` | `70.8660%` | `1.1253` | `17.4647` | `60` |
| `risk070` | `0.7` | `3237.2130%` | `-42.1055%` | `65.4345%` | `1.1126` | `18.1975` | `68` |
| `risk060` | `0.6` | `3192.2041%` | `-39.0499%` | `64.5247%` | `1.1798` | `16.6859` | `69` |
| `risk050` | `0.5` | `2213.1854%` | `-35.0695%` | `44.7356%` | `1.1996` | `15.0187` | `69` |

## risk060 关键结果

- 期末权益：`20,247,055`
- 总收益：`3192.2041%`
- 相对 Stage079 收益保留：`64.5247%`
- 最大回撤：`-39.0499%`
- Sharpe：`1.1798`
- Ulcer：`16.6859`
- 总滑点：`1,209,320`
- 总交易次数：`760`
- 非零日胜率：`51.6681%`
- 3个月体验：p05 `-17.3202%`，中位 `12.7351%`，DD30破例 `3.1968%`
- 6个月体验：p05 `-8.2948%`，中位 `23.0529%`，DD30破例 `19.2867%`
- 成本压力：`2x` 最大回撤 `-41.9536%`，`3x` `-46.7950%`，`5x` `-65.3081%`

## 图表视觉复盘

- 视觉上 `risk060` 确实把 `risk100` 的 2021-2022 深坑抬到 DD40 内，说明暴露压缩方向有效。
- 但 `risk060` 只是贴线通过，水下图仍有长时间低于 `-30%` 的区域，2025/2026 也有明显水下簇；它不是舒适曲线。
- `risk070` 保留收益略过 `65%`，但图形和指标都显示仍穿 `-40%`；因此不能把 `risk070` 晋级。
- `risk050` 最平滑但收益下降太多，不符合“保留大部分收益”。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage503_next_real_open_risk_frontier_report_stage503_next_real_open_risk_frontier_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage503_next_real_open_risk_frontier_summary_stage503_next_real_open_risk_frontier_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage503_next_real_open_risk_frontier_daily_stage503_next_real_open_risk_frontier_v1.csv`
- trade usage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage503_next_real_open_risk_frontier_trade_usage_stage503_next_real_open_risk_frontier_v1.csv`
- frontier：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage503_next_real_open_risk_frontier_frontier_stage503_next_real_open_risk_frontier_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage503_next_real_open_risk_frontier_chart_stage503_next_real_open_risk_frontier_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage503_next_real_open_risk_frontier_decision_stage503_next_real_open_risk_frontier_v1.json`

## 结论

- 决策：`risk_frontier_no_dd40_return65_candidate`。
- `risk060` 是当前最接近目标的真实执行边界：DD40 通过，但收益保留 `64.5247%`，略低于 `65%` 可继续研究线，且仍有 `69` 笔 fallback。
- 不按目标独立判断：不晋级，但值得继续作为边界版本清理 fallback 和做状态风险结构尝试。
- 下一步：
  - 优先审计并清理 `risk060/risk070` 的下一真实窗口 fallback。
  - 不调 `0.61/0.62` 小数救线。
  - 若 fallback 清理后仍卡在边界，尝试极少自由度的状态依赖风险预算，例如上一日账户回撤触发风险降档。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但不能用相邻小数救结果。
- 原因：本阶段只跑粗档位固定前沿，没有按日期、品种、坏窗口或贡献日筛选。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但目标未完成。
- 原因：已经找到 DD40 内的真实执行边界；下一步的价值在清理无偏成交证据和寻找比纯降杠杆更聪明的低自由度风险结构。

## TODO

- 做 Stage204 fallback 来源审计，判断是数据缺口、夜盘识别缺口还是日线 fallback。
- 若能清零 fallback，重跑 `risk060/risk070` 并复核图形。
- 若无法清零，`risk060` 不得作为最终“真实交易不存在偏差”候选。
