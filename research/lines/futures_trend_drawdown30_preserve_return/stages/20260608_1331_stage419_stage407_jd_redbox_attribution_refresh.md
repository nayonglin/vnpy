# Stage419 Stage407 鸡蛋加入后红框增长缺失复核

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 13:31 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：已有 Stage407/Stage705 输出的定点归因复核，不是新回测
- 是否重要突破：否，属于 Stage408 结论的补证
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - AQR `Trend Following`：趋势策略长期收益高度依赖少数右尾趋势段，组合构成和风险预算会决定是否吃到右尾。
  - Man Group `A Trend Following Deep Dive: The Optimal Market Mix for a Trend Follower`：市场池变化会改变趋势跟踪的机会捕捉效率和路径。
  - Hurst/Ooi/Pedersen `A Century of Evidence on Trend-Following Investing`：趋势跟踪需要跨市场分散，但新增市场必须验证其是否改善组合，而不能只看交易次数增加。
- 我的判断：鸡蛋本身不是红框区间亏损来源；问题是鸡蛋参与 AI 排名后改变主账户路径，打破了正式版在 2025 年右尾段的仓位保留结构。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：重点复核 `2025-04-16 -> 2025-07-25`
- 账户规模：20万 Stage372 正式口径
- 成本口径：沿用 Stage705 输出，正常成本
- 样本过滤：只读 Stage705 daily、positions、entry_candidates 明细
- 策略/归因口径：
  - A：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - B：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_ai_rerank_top9_maxpos5`

## 结果

- A 红框窗口增长：`+5,656,270`（按日净值逐日求和口径）
- B 红框窗口增长：`+120,130`（按日净值逐日求和口径）
- A 红框前权益：`3,481,165`
- B 红框前权益：`2,786,870`
- B 在红框内 `jd.DCE` 实际开仓：`0`
- B 在红框内 `jd.DCE` 候选：`2025-07-07 jd2508.DCE short_case2`，因 `short_signal_rejected` 跳过
- 核心缺口：
  - `jm2509`：A `+3,254,640`，B `+207,870`，缺口 `-3,046,770`
  - `si2509`：A `+1,315,650`，B `+73,500`，缺口 `-1,242,150`
  - `lc2507`：A `+671,580`，B `0`，缺口 `-671,580`
  - `fu2509`：A `+303,480`，B `0`，缺口 `-303,480`
  - `FG509`：A `+236,940`，B `+15,840`，缺口 `-221,100`
- 关键手数差异：
  - `2025-06-11 fu2509`：A 开 `281` 手；B 因 `ai_product_pool_blocked` 没开
  - `2025-07-08 jm2509`：A 开 `142` 手、`risk_multiplier=1.0`；B 开 `9` 手、`loss_streak=4`、`risk_multiplier=0.1`
  - `2025-07-09 FG509`：A 开 `359` 手、`risk_multiplier=1.0`；B 开 `24` 手、`loss_streak=4`、`risk_multiplier=0.1`
  - `2025-07-09 si2509`：A 开 `179` 手、`risk_multiplier=1.0`；B 开 `10` 手、`loss_streak=4`、`risk_multiplier=0.1`
  - `2025-06-27 cu2508`：A 开 `29` 手、`risk_multiplier=1.0`；B 开 `2` 手、`loss_streak=3`、`risk_multiplier=0.1`
- 红框窗口资金占用：
  - A 平均活跃品种 `1.19`，最大 `3`，平均 broker10 保证金/权益 `27.52%`
  - B 平均活跃品种 `0.80`，最大 `3`，平均 broker10 保证金/权益 `7.53%`

## 输出文件

- report：沿用 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage705_stage407_jd_independent_sleeve_report_stage705_stage407_jd_independent_sleeve_v1.md`
- summary：沿用 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage705_stage407_jd_independent_sleeve_summary_stage705_stage407_jd_independent_sleeve_v1.csv`
- daily：沿用 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage705_stage407_jd_independent_sleeve_daily_stage705_stage407_jd_independent_sleeve_v1.csv`
- positions：沿用 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage705_stage407_jd_independent_sleeve_positions_stage705_stage407_jd_independent_sleeve_v1.csv`
- entry_candidates：沿用 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage705_stage407_jd_independent_sleeve_entry_candidates_stage705_stage407_jd_independent_sleeve_v1.csv`

## 结论

- 本阶段结论：红框增长消失不是鸡蛋在该区间亏损导致。鸡蛋在红框内没有实际开仓。真实链条是：鸡蛋参与 AI 重排后改变月度入池/排序，`fu` 被阻断，随后主账户路径进入更弱状态；等 `jm/FG/si` 右尾出现时，B 的全局连败状态把风险预算压到 `0.1`，导致手数只有正式版约十分之一到十五分之一，最终大右尾没有吃到。
- 是否进入下一步：不继续救 Stage407 共享 AI 重排版本。
- 下一步：如果还要加鸡蛋，只能走不挤占主池、不污染主账户连败状态的独立小风险槽；Stage418 已验证这种结构能保住正式核心，但鸡蛋自身贡献很小，暂不 promotion。

## 过拟合反思

- 运行前判断：不是过拟合，本次是已有结果的机制复盘，没有按窗口调参。
- 运行后判断：不是过拟合。结论来自候选、持仓、日收益和风险状态四类明细一致指向。
- 原因：如果后续按 `2025`、`fu`、`jm` 做白名单修补，会转为过拟合；当前只保留结构性结论，即“新增品种不能进入共享主排序破坏右尾路径”。

## 继续价值反思

- 运行前判断：有价值，因为用户指出的曲线异常必须解释清楚，否则后续会误以为只是 topN 或 maxpos 没调好。
- 运行后判断：有价值，但 Stage407 本身没有继续优化价值。
- 原因：归因说明正式版的核心脆弱点不是保证金，而是右尾机会被路径和连败风险档共同截断；继续价值应转向简单、隔离、非挤占式风险结构，而不是继续调鸡蛋的 AI 排名。

## 合入建议

- 是否更新本线 `LINE.md`：否，本次是 Stage408 的补证。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，Stage418 已记录主要结论。
