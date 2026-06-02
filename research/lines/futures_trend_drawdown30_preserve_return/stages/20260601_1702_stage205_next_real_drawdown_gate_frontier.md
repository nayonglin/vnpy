# Stage205 下一真实窗口组合回撤门控前沿

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 17:02 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实可成交低自由度风险结构；只使用上一日可见组合权益回撤状态
- 是否重要突破：否，形成明确反证
- 是否触发A/B：是，按 `skills/version-ab-experiment/SKILL.md` 执行；A 为 Stage079 原始日线 baseline，B 无独立意义，C 为 Stage079 下一真实窗口 + 固定风险预算 + 组合回撤门控/降仓

## 外部调研与判断

- 参考资料：
  - Backtrader Orders：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - QuantConnect Understanding Time：https://www.quantconnect.com/docs/v1/key-concepts/understanding-time
  - Kim, Tse, Wald, Time series momentum and volatility scaling：https://doi.org/10.1016/j.finmar.2016.05.003
- 我的判断：
  - 组合回撤门控是低自由度、可解释的风险状态结构，值得测试。
  - 但它是滞后降风险，若结果主要靠长期降仓压回撤，就不能晋级。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage505_next_real_drawdown_gate_frontier.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `base_risk_multiplier=0.7/0.8`
  - `portfolio_drawdown_gate_start_pct=0.15/0.20`
  - `portfolio_drawdown_gate_full_pct=0.30`
  - `portfolio_drawdown_gate_weight_floor=0.50`
  - `enable_portfolio_drawdown_deleverage=True`
  - 同时保留 `risk060_clean/risk070_clean` 作为对照
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：`615,000`
- 策略规则、品种池、AI池、入场/出场逻辑：不变
- 成交口径：完整日K确认后，所有订单在下一真实窗口成交
- 补数口径：自动补新成交键，最终 fallback `0`
- 样本过滤：无日期、品种、坏窗口过滤

## 结果

| 版本 | 总收益 | 收益保留 | 最大回撤 | Sharpe | Ulcer | fallback |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `risk060_clean` | `3157.9764%` | `63.8328%` | `-39.0499%` | `1.1786` | `16.3184` | `0` |
| `risk070_clean` | `3243.7967%` | `65.5675%` | `-42.1055%` | `1.1153` | `17.6263` | `0` |
| `r070_dd20_30_f50_delev` | `881.8780%` | `17.8256%` | `-38.2328%` | `0.9078` | `22.2293` | `0` |
| `r070_dd15_30_f50_delev` | `752.3569%` | `15.2075%` | `-39.6735%` | `0.9526` | `20.6580` | `0` |
| `r080_dd15_30_f50_delev` | `655.8480%` | `13.2568%` | `-38.9560%` | `0.9351` | `21.0462` | `0` |
| `r080_dd20_30_f50_delev` | `722.0967%` | `14.5959%` | `-43.1274%` | `0.8918` | `23.2655` | `0` |

- 最佳 clean DD40 版本仍是 `risk060_clean`：
  - 期末权益：`20,036,555`
  - 总收益：`3157.9764%`
  - 最大回撤：`-39.0499%`
  - Sharpe：`1.1786`
  - 总滑点：`1,215,940`
  - 总交易次数：`760`
  - 非零日胜率：`51.7536%`
- 门控版本交易次数反而上升到 `951-1005`，总滑点下降是因为大量降仓，不是效率提升。
- 成本压力：门控版本在 `2x/3x/5x` 下依然不稳，且收益大幅低于目标。

## 图表视觉复盘

- 图上门控线没有把 `risk070_clean` 改造成高收益低回撤版本，而是在 2021-2023 深水区持续降仓，复利基数被压扁。
- 橙/绿门控线多数压住 `-40%`，但 NAV 长期贴近低位，最终收益保留只有 `15%-18%` 左右。
- 紫色 `risk070_clean` 收益保留过 `65%`，但 2022 初穿 `-40%`；红色 `risk060_clean` 是唯一有意义边界，但收益保留仍只有 `63.8328%`。
- 视觉结论：组合回撤门控/降仓这条形状过于滞后，不值得继续调 `15/20/30` 附近阈值。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage505_next_real_drawdown_gate_frontier_report_stage505_next_real_drawdown_gate_frontier_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage505_next_real_drawdown_gate_frontier_summary_stage505_next_real_drawdown_gate_frontier_v1.csv`
- frontier：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage505_next_real_drawdown_gate_frontier_frontier_stage505_next_real_drawdown_gate_frontier_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage505_next_real_drawdown_gate_frontier_daily_stage505_next_real_drawdown_gate_frontier_v1.csv`
- trade usage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage505_next_real_drawdown_gate_frontier_trade_usage_stage505_next_real_drawdown_gate_frontier_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage505_next_real_drawdown_gate_frontier_chart_stage505_next_real_drawdown_gate_frontier_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage505_next_real_drawdown_gate_frontier_decision_stage505_next_real_drawdown_gate_frontier_v1.json`

## 结论

- 决策：`drawdown_gate_clean_dd40_but_return_retention_short`。
- 不晋级。组合回撤门控能压回撤，但收益保留过低，且风险控制太滞后。
- 不按目标独立判断：也不晋级。它牺牲复利过多，且没有改善到可部署体验。
- 下一步：停止该门控形状，不继续扫 `0.15/0.20/0.30` 附近阈值；若继续目标，应寻找更前置的风险信号或独立收益源。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但若继续调阈值会转为过拟合。
- 原因：本阶段只测试粗档组合回撤状态，没有按品种/日期/坏窗口筛选；失败后应停止。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：该形状继续价值低，总目标仍有价值。
- 原因：回撤门控已经证明滞后；后续需要更前置的风险状态，或接受 `risk060_clean` 作为收益不足但真实的边界参考。

## TODO

- 不继续该组合回撤门控阈值扫描。
- 下一步若继续，应先定义前置风险信号，例如开仓前波动/相关性/拥挤度，而不是亏损后才降仓。
