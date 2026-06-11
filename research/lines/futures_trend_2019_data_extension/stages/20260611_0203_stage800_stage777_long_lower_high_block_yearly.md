# Stage800：Stage777候选版多头连续lower-high过滤 年度起点回测

- 记录时间：2026-06-11 02:03 CST
- 研究线：`futures_trend_2019_data_extension`
- 当前工作模式：day
- 是否重要突破版本：否
- A/B 触发：是。用户要求在 Stage799 单路径后继续做逐年回测，属于候选版开仓过滤的稳健性验证。

## 本次调研和判断结论

外部快速调研结论与 Stage799 一致：趋势结构资料通常认为 lower highs 是上攻衰减或弱势结构，但也有资料把连续 lower highs 视作可能蓄势反转的形态。因此这条规则不能只靠直觉升级，必须看多起点是否真的减少坏交易且不砍右尾。

参考：

- Britannica Money：Trend Following / higher highs and lower highs trend structure
- OxfordStrat：Dow Theory trend definition
- Reddit/交易社区 lower-high backtest 讨论：提示 lower-high 也可能代表反转蓄势，说明硬过滤有误杀风险

## 候选假设

如果最新三根已完成日线满足 `high[t] < high[t-1] < high[t-2]`，说明多头近期上攻能力递减；此时禁止多头入场，期望减少假突破和趋势末端回抽入场。

## A/C 设计

- A：当前 `official_candidate_stage777_50w_am41_oi08_old_ai_v1`，从 Stage777 月度缓存抽取年度起点。
- C：Stage800，同 A，仅新增多头过滤：
  - 当最新三根已完成日线 `high[t] < high[t-1] < high[t-2]` 时，禁止多头新开/反手/换月重开信号。
- 年度起点：`2018-01`、`2019-01`、`2020-01`、`2021-01`、`2022-01`、`2023-01`、`2024-01`、`2025-01`、`2026-01`
- 终点：`2026-05-29`

## 保持不变

- 初始资金：`500,000`
- AM：`AM41`
- 基础等效风险：`0.40`
- OI命中恢复：`0.80`
- AI：旧正式 AI 品种池启用
- 最大持仓：`maxpos4`
- 连败缩放：关闭
- recovery sleeve：关闭
- 空头逻辑：不变
- 止盈止损：不变

## 新增/修改/删除参数

- 新增参数：
  - `block_long_two_lower_highs=True`
  - 定义：`high[t] < high[t-1] < high[t-2]`
- 修改参数：
  - 无其他策略参数修改
- 删除参数：
  - 无

## 年度聚合结果

| bucket | 样本数 | C收益胜出 | C回撤胜出 | C Sharpe胜出 | 双胜 | 收益差中位pp | 回撤差中位pp | Sharpe差中位 | C拦截多头信号 | A DD40失败 | C DD40失败 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 9 | 1 | 2 | 2 | 0 | -37.7300 | -0.3777 | -0.0621 | 261 | 4 | 4 |
| mature_ex_2026 | 8 | 1 | 2 | 2 | 0 | -114.5445 | -0.4153 | -0.0650 | 254 | 4 | 4 |

## 年度明细

| start | A收益% | C收益% | C-A收益pp | A回撤% | C回撤% | C-A回撤pp | A Sharpe | C Sharpe | C-A Sharpe | 拦截多头 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018-01 | 3550.253 | 2776.602 | -773.651 | -49.4213 | -49.9151 | -0.4938 | 1.3671 | 1.2992 | -0.0679 | 49 |
| 2019-01 | 4137.990 | 2902.961 | -1235.029 | -49.3661 | -49.7438 | -0.3777 | 1.5261 | 1.4275 | -0.0986 | 45 |
| 2020-01 | 2422.962 | 1807.443 | -615.519 | -49.1145 | -49.1189 | -0.0044 | 1.4717 | 1.3929 | -0.0788 | 39 |
| 2021-01 | 1126.727 | 935.368 | -191.359 | -48.6695 | -49.1224 | -0.4529 | 1.3478 | 1.2857 | -0.0621 | 34 |
| 2022-01 | 121.270 | 104.059 | -17.211 | -35.3554 | -34.5980 | +0.7574 | 0.7607 | 0.7115 | -0.0492 | 30 |
| 2023-01 | 179.513 | 141.783 | -37.730 | -22.1100 | -24.3873 | -2.2773 | 1.2604 | 1.1299 | -0.1305 | 27 |
| 2024-01 | 82.388 | 84.600 | +2.212 | -23.3469 | -25.5681 | -2.2212 | 1.0578 | 1.0686 | +0.0108 | 18 |
| 2025-01 | 83.832 | 83.418 | -0.414 | -16.2147 | -15.6452 | +0.5695 | 1.4744 | 1.5266 | +0.0522 | 12 |
| 2026-01 | -4.974 | -4.974 | 0.000 | -15.5310 | -15.5310 | 0.0000 | -0.1741 | -0.1741 | 0.0000 | 7 |

## 结论

- 决策：`stage800_long_lower_high_block_yearly_not_promoted`
- 原因：
  - C 收益胜出只有 `1/9`，成熟样本 `1/8`。
  - C 回撤胜出只有 `2/9`，成熟样本 `2/8`。
  - 双胜为 `0`。
  - DD40 失败没有减少，A/C 都是 `4` 个。
  - 成熟样本收益差中位为 `-114.5445pp`，说明它系统性砍右尾。
- 本质：连续 lower-high 作为硬过滤不是稳健的坏机会识别器，而是把一部分“回调后重新启动”的多头机会过滤掉。

## 输出文件

- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage800_stage777_long_lower_high_block_yearly.py`
- 汇总：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage800_stage777_long_lower_high_block_yearly_summary_stage800_stage777_long_lower_high_block_yearly_v1.csv`
- 对照：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage800_stage777_long_lower_high_block_yearly_comparison_vs_stage777_stage800_stage777_long_lower_high_block_yearly_v1.csv`
- 聚合：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage800_stage777_long_lower_high_block_yearly_aggregate_stage800_stage777_long_lower_high_block_yearly_v1.csv`
- 拦截事件：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage800_stage777_long_lower_high_block_yearly_lower_high_blocks_stage800_stage777_long_lower_high_block_yearly_v1.csv`
- 收益差图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage800_stage777_long_lower_high_block_yearly_return_delta_bar_stage800_stage777_long_lower_high_block_yearly_v1.png`
- 回撤差图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage800_stage777_long_lower_high_block_yearly_dd_delta_bar_stage800_stage777_long_lower_high_block_yearly_v1.png`
- 年度资金曲线图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage800_stage777_long_lower_high_block_yearly_equity_curves_stage800_stage777_long_lower_high_block_yearly_v1.png`

## 反思

- 开始前过拟合判断：中等。规则有趋势结构基础，但来自亏损K线观察，容易把局部坏交易形态硬编码。
- 运行后过拟合判断：不升级，因此没有形成正式过拟合；继续扫 lower-high 天数、是否等号、是否只限 case2 等细节会转入过拟合。
- 开始前继续价值判断：有价值。用户要求逐年验证，且可以检验 2020 单路径是否偶然。
- 运行后继续价值判断：该硬过滤继续价值低。年度验证已证明它不是穿越周期的坏机会过滤器。

## 后续规划和 TODO

1. 不把 Stage800 接入官方候选。
2. 不继续扫 `2/3/4` 天 lower-high、等号/不等号、只过滤某个 case 等参数。
3. 若继续研究K线形态，应该转为“被拦截交易后验分布”只读复盘，而不是继续改规则救参。
