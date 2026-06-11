# Stage799：Stage777候选版多头连续lower-high过滤 2020单路径回测

- 记录时间：2026-06-11 01:56 CST
- 研究线：`futures_trend_2019_data_extension`
- 当前工作模式：day
- 是否重要突破版本：否
- A/B 触发：是。该规则属于候选版开仓过滤，可能影响官方候选，需按 A/C 验证。

## 本次调研和判断结论

外部快速调研结论：道氏/趋势结构资料通常把上升趋势描述为 higher highs/higher lows，把 lower highs 视作上攻失败或下行结构的一部分。因此“连续两天 high 下降时不做多”有价格结构上的第一性原理，属于合理的趋势质量过滤想法。

我的判断：规则方向合理，但硬过滤风险中等。趋势策略的大赢家经常出现在回调后重新启动，若只看到亏损K线后加硬条件，容易把右尾行情误杀。因此先做 2020 单路径 A/C，不直接进入逐月扫。

参考：

- Britannica Money：Trend Following / higher highs and lower highs trend structure
- OxfordStrat：Dow Theory trend definition

## 候选假设

如果最新三根已完成日线满足 `high[t] < high[t-1] < high[t-2]`，说明多头近期上攻能力递减；此时即使均线/MACD给多头信号，也先不做多，期望减少假突破和趋势末端回抽入场。

## A/C 设计

- A：当前 `official_candidate_stage777_50w_am41_oi08_old_ai_v1`，2020 起点缓存结果。
- C：Stage799，同 A，仅新增多头过滤：
  - 当最新三根已完成日线 `high[t] < high[t-1] < high[t-2]` 时，禁止多头新开/反手/换月重开信号。
- B：无独立 standalone 意义；这是入场过滤，不单独作为策略。

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

## 新增回测结果

| 指标 | A Stage777 | C Stage799 | 差值 |
| --- | ---: | ---: | ---: |
| 期末权益 | 12,614,810 | 9,537,215 | -3,077,595 |
| 总收益 | 2422.9620% | 1807.4430% | -615.5190pp |
| 最大回撤 | -49.1145% | -49.1189% | -0.0044pp |
| Sharpe | 1.4717 | 1.3929 | -0.0788 |
| 总滑点 | 844,660 | 611,860 | -232,800 |
| 总交易次数 | 512 | 476 | -36 |
| 非零日胜率 | 53.6391% | 54.1176% | +0.4786pp |
| broker10最大保证金/权益 | 96.7205% | 90.2962% | -6.4243pp |
| broker10 p95保证金/权益 | 48.8733% | 46.6018% | -2.2715pp |
| 被lower-high规则拦截的多头信号 | 0 | 39 | +39 |

## 结论

- 决策：`stage799_long_lower_high_block_2020_single_path_not_promoted`
- 原因：该规则确实减少交易、滑点和保证金压力，但没有改善最大回撤，反而少赚约 `307.8万`，总收益少 `615.519pp`。
- 本质：硬过滤连续 lower-high 更像砍掉多头右尾机会，而不是识别坏环境。
- 不继续逐月：第一关 A/C 已经显示 C 收益大幅下降、回撤无改善，继续逐月验证的边际价值不高。

## 输出文件

- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage799_stage777_long_lower_high_block_2020.py`
- 汇总：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage799_stage777_long_lower_high_block_2020_summary_stage799_stage777_long_lower_high_block_2020_v1.csv`
- 曲线：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage799_stage777_long_lower_high_block_2020_curves_stage799_stage777_long_lower_high_block_2020_v1.csv`
- 对照：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage799_stage777_long_lower_high_block_2020_comparison_vs_stage777_stage799_stage777_long_lower_high_block_2020_v1.csv`
- 被拦截事件：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage799_stage777_long_lower_high_block_2020_lower_high_blocks_stage799_stage777_long_lower_high_block_2020_v1.csv`
- 图片：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage799_stage777_long_lower_high_block_2020_equity_vs_stage777_stage799_stage777_long_lower_high_block_2020_v1.png`

## 反思

- 开始前过拟合判断：中等。规则有趋势结构基础，但来自亏损K线观察，容易把局部坏交易形态硬编码。
- 运行后过拟合判断：当前不升级，因此未形成过拟合交易规则；如果继续按这个结果微调“2天/3天、最高价/收盘价、只过滤case2”等，就会进入过拟合。
- 开始前继续价值判断：有价值。它是对坏交易K线共性的直接验证。
- 运行后继续价值判断：该硬过滤本身继续价值低。若继续，应转向只读归因：被拦截的39个信号中到底哪些是右尾赢家，避免用简单 lower-high 阈值误杀回调后的趋势重启。

## 后续规划和 TODO

1. 不把 Stage799 接入官方候选。
2. 不继续扫 `2/3/4` 天 lower-high 或改成小阈值救参。
3. 若用户继续关注K线形态，应复盘被拦截信号的后验分布，判断它误杀的是哪些品种/年份/信号类型。
