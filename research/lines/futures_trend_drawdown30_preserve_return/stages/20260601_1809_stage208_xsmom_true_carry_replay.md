# Stage208 xsmom真实承载回放

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-06-01 18:09 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实可成交结构候选审计；把 Stage103/xsmom 冻结日级整数手数腿改造成目标持仓、订单、成交、逐日持有 PnL ledger。
- 是否重要突破：是。Stage209 补数后，xsmom 成交 fallback 清零，`risk070_clean + true-carried Stage103 xsmom` 首次在下一真实窗口口径下同时满足 DD40 和收益保留 65%。
- 是否触发A/B：是。A=Stage079 同日 baseline；C1=`risk060_clean`；C2=`risk060_clean + true xsmom`；C3=`risk070_clean + true xsmom`。

## 外部调研与判断

- 参考资料：time-series/cross-sectional momentum、managed futures、trend following 交易成本与跨市场分散文献；外部公开实现多为 Backtrader/pandas 的月度或日度简化回测。
- 我的判断：公开资料支持“独立低相关收益源”比继续在 C3 本体调回撤阈值更有第一性原理；但本仓库已有分钟成交与整数手/保证金约束，所以不能复制简化净值层结果，必须按真实窗口重放。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage508_xsmom_true_carry_replay.py`
- 配套补数脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage509_xsmom_true_carry_fallback_backfill.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无交易参数；新增输出 ledger 与成交来源统计。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至当前 Stage079/Stage506 可比全周期。
- 账户规模：`615,000` 账户口径；C3 仍按 `500,000` 下单口径，Stage079 外部现金 `115,000`。
- 成本口径：沿用本地合约滑点与下一真实窗口分钟成交；xsmom 真实腿总滑点 `15,080`。
- 样本过滤：不筛日期、不筛品种、不筛坏窗口。
- 策略/归因口径：Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard` 冻结规则；不改 `63日/0.5/10%broker/品种池/权重`。

## 结果

| 版本 | 期末权益 | 总收益 | 收益保留 | 最大回撤 | Sharpe | Ulcer | fallback |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 同日 baseline | `31,040,650` | `4947.2602%` | `100.0000%` | `-29.7007%` | `1.3188` | `15.0874` | `0` |
| `risk060_clean` | `20,036,555` | `3157.9764%` | `63.8328%` | `-39.0499%` | `1.1786` | `16.3184` | `0` |
| `risk060_clean + true xsmom` | `20,682,740` | `3263.0472%` | `65.9567%` | `-36.2870%` | `1.2291` | `15.4730` | `0` |
| `risk070_clean` | `20,564,350` | `3243.7967%` | `65.5675%` | `-42.1055%` | `1.1153` | `17.6263` | `0` |
| `risk070_clean + true xsmom` | `21,210,535` | `3348.8675%` | `67.6914%` | `-38.5861%` | `1.1674` | `16.5824` | `0` |

- 总滑点：xsmom 真承载腿 `15,080`；组合滑点见输出 cost/summary。
- 总交易次数：xsmom 真承载腿换手 `460` 手；组合交易次数见 daily 输出。
- 胜率：本阶段重点为账户路径和持有体验，未单独计算逐笔胜率；后续逐笔复盘再补。
- xsmom 腿：true PnL `646,185`，frozen 参考 `690,265`，真实承载少 `44,080`。
- 成交来源：夜盘 `21:00-21:05 first_open` 订单 `275`，日盘 `09:00-09:05 first_open` 订单 `185`，fallback `0`。

## 3个月/6个月体验

- `risk060_clean + true xsmom`：
  - 90日 p05 `-15.8875%`，中位 `12.9473%`，DD30破例 `0.0000%`，Ulcer P95 `17.3253`。
  - 180日 p05 `-7.1371%`，中位 `22.3914%`，DD30破例 `7.6959%`，Ulcer P95 `20.4466`。
- `risk070_clean + true xsmom`：
  - 90日 p05 `-17.7617%`，中位 `12.2465%`，DD30破例 `1.5308%`，Ulcer P95 `19.0093`。
  - 180日 p05 `-7.8275%`，中位 `21.3546%`，DD30破例 `12.0131%`，Ulcer P95 `21.8582`。
- 体验判断：`risk070 + true xsmom` 是收益/回撤主候选；`risk060 + true xsmom` 是更平滑对照。

## 图表视觉复盘

- true xsmom 对 2021-2022 深水段和 2025 二次水下都有可见抬升，不是只靠末端单点收益。
- `risk070 + true xsmom` 最有资本效率，但 2022 初仍贴近 `-40%`；只能作为工程候选，不是安全垫厚的最终部署版本。
- `risk060 + true xsmom` 水下更浅，最大回撤 `-36.2870%`，但收益保留低于 `risk070 + true xsmom`。
- 所有 next-real 版本的 NAV 都显著低于 Stage079 同日 baseline，因此 Stage079 原曲线仍不能作为真实实盘收益承诺。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage508_xsmom_true_carry_replay_report_stage508_xsmom_true_carry_replay_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage508_xsmom_true_carry_replay_chart_stage508_xsmom_true_carry_replay_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage508_xsmom_true_carry_replay_summary_stage508_xsmom_true_carry_replay_v1.csv`
- frontier：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage508_xsmom_true_carry_replay_frontier_stage508_xsmom_true_carry_replay_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage508_xsmom_true_carry_replay_order_ledger_stage508_xsmom_true_carry_replay_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage508_xsmom_true_carry_replay_daily_stage508_xsmom_true_carry_replay_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage508_xsmom_true_carry_replay_fill_source_stage508_xsmom_true_carry_replay_v1.csv`

## 结论

- 本阶段结论：`stage079_next_real_risk070_clean_plus_stage103_xsmom_true` 晋级为真实可成交工程候选。
- 是否进入下一步：是，但不能关账。
- 下一步：做多起点、多周期、保证金压力、成本压力、逐段/逐笔贡献复盘；同时按更新目标另开基本面/舆情可执行数据源调研和策略本体优化调研。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有调交易规则和参数，只把冻结 xsmom 规则按真实窗口成交；Stage209 只补分钟数据并清零 fallback。后续若改 `0.5/63日/10%/risk070` 小数才会变成过拟合。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：Stage206 已反证 C3 本体风控小修，Stage208 证明独立收益源在真实承载后仍能把收益保留推过 65%、最大回撤压回 40% 内。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，属于重要工程候选。
