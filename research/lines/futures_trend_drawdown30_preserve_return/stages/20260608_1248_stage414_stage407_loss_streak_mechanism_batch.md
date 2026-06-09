# Stage414 Stage407 连败风控机制批量反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 12:48 CST`
- 阶段范围：Stage412 / Stage413 / Stage414
- 阶段性质：围绕“连败后直接 `0.1` 经常导致开不出仓位”的低自由度机制验证
- 是否重要突破：否，但明确反证三类简单救援机制
- 正式配置：未修改
- CTP/下单：未连接 CTP，未调用 order API

## 外部调研与判断

- 参考资料：
  - Man Group 趋势跟踪市场组合文章：多市场组合的收益来自分散化和右尾捕捉，新增市场/风控必须看是否改变右尾暴露。
  - AQR trend following / managed futures 资料：趋势策略的长期收益来自少数大趋势，风险管理应避免把右尾机会过早压掉。
  - GitHub 公开 futures trend-following 示例：公开实现通常强调可交易市场、风险预算和信号一致性，不支持按单一窗口或单一品种打补丁。
- 我的判断：连败风控应该先解决“账户生存”和“坏状态降暴露”，但不能让近期几笔亏损把所有不相关品种的新趋势机会压到近乎不可交易。本阶段只测试三个结构性单点，不扫小数、不按 `jm/fu/2025` 打补丁。

## 运行前反思

### 是否过拟合

- 判断：否。
- 原因：三个候选都预先用通用风控逻辑定义：
  - Stage412：把三连败 `0.1` 视为临时冷却，60 自然日无新亏损后恢复。
  - Stage413：复用已有 clean-book recovery lift，把适用信号从 `case1a` 扩到所有原生趋势入场 case。
  - Stage414：严重 `0.1` 只有账户回撤超过 `15%` 后生效，15% 是目标 30% 回撤的一半，不扫参。

### 是否有继续价值

- 判断：有。
- 原因：Stage408/409/410/411 已证明红框增长缺失有 `0.1` 仓位过小成分，但简单抬底线和补一手失败；需要验证是否存在更简单、更稳健的结构替代。

## 版本改动

### Stage412 / Script699

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage699_stage407_streak_time_decay60.py`
- 新增参数：`STREAK_DECAY_CALENDAR_DAYS=60`
- 修改参数：不改 `streak_risk_multipliers`，仍为 `1.0,1.0,1.0,0.1`
- 逻辑：三连败后仍先降到 `0.1`；如果之后 60 自然日没有新的已实现亏损，则恢复正常风险。
- 删除参数：无。

### Stage413 / Script700

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage700_stage407_recovery_all_cases.py`
- 新增参数：`RECOVERY_SIGNALS=long_case1a,long_case2,long_case3,short_case1a,short_case2,short_case3`
- 修改参数：已有 `streak_entry_structure_recovery_signals` 从 `long_case1a,short_case1a` 扩展到所有原生趋势入场 case。
- 保留约束：仍要求 `flat_entry`、空组合、同向相关不高于 `0.30`、不要求 RSI 确认。
- 删除参数：无。

### Stage414 / Script701

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage701_stage407_drawdown_gated_streak.py`
- 新增参数：`STREAK_SEVERE_DD_GATE_RATIO=0.15`
- 修改参数：三连败后 `0.1` 严重降仓只有账户回撤超过 `15%` 后才生效；不改倍率表。
- 删除参数：无。

## 回测口径

- A：当前正式 Stage372/20w，正式 AI，`maxpos4`，原连败倍率和正式恢复规则。
- D：A + 当前候选机制。
- B：Stage407 基线，原正式 AI 池 + `jd.DCE` 参与 AI 重排 top9，`maxpos5`，原连败倍率。
- C：B + 当前候选机制。
- 数据区间：沿用 Stage407/Stage696 口径，`2020-01-01` 至仓库当前期货数据末端。
- 样本过滤：不重新训练、不修改正式 AI；2020-2021 full-market AI 预测未覆盖时沿用正式 AI 快照且不放行鸡蛋。

## 新增结果

### Stage412 时间衰减 60 天

- A 当前正式：期末权益 `8,728,285`，总收益 `4264.1425%`，最大回撤 `-38.6713%`，Sharpe `1.6279`，总滑点 `506,220`，总交易次数 `633`，胜率 `52.2586%`，broker10 峰值 `79.6015%`，强制减仓 `6` 次 `299` 手。
- D 正式 + 60 天衰减：期末权益 `8,728,285`，总收益 `4264.1425%`，最大回撤 `-38.6713%`，Sharpe `1.6279`，总滑点 `506,220`，总交易次数 `633`，胜率 `52.2586%`，broker10 峰值 `79.6015%`，强制减仓 `6` 次 `299` 手。
- B Stage407：期末权益 `3,284,935`，总收益 `1542.4675%`，最大回撤 `-33.2821%`，Sharpe `1.3858`，总滑点 `298,030`，总交易次数 `688`，胜率 `51.7181%`。
- C Stage407 + 60 天衰减：期末权益 `3,284,935`，总收益 `1542.4675%`，最大回撤 `-33.2821%`，Sharpe `1.3858`，总滑点 `298,030`，总交易次数 `688`，胜率 `51.7181%`。
- 红框窗口 `2025-04-16` 至 `2025-07-25`：A/D 增长均为 `+5,605,230`；B/C 增长均为 `+90,830`。
- 结论：时间衰减完全不命中。红框不是“几个月前连败粘住”，而是 6 月下旬刚亏完、7 月右尾马上来，60 天来不及触发。

### Stage413 恢复 lift 扩到所有 case

- D 正式 + all cases recovery：期末权益 `7,289,850`，总收益 `3544.9250%`，最大回撤 `-28.6384%`，Sharpe `1.6631`，总滑点 `359,770`，总交易次数 `600`，胜率 `52.0188%`，broker10 峰值 `69.2871%`。
- C Stage407 + all cases recovery：期末权益 `2,878,680`，总收益 `1339.3400%`，最大回撤 `-35.0090%`，Sharpe `1.4425`，总滑点 `188,140`，总交易次数 `653`，胜率 `52.3135%`，broker10 峰值 `62.6582%`。
- C 相对 B：期末权益少 `406,255`，总收益少 `203.1275pp`，最大回撤恶化 `1.7269pp`，Sharpe 提高 `0.0567`，交易少 `35`。
- 红框窗口：B `+90,830`，C `+1,502,100`，多 `+1,411,270`；但仍远低于 A 的 `+5,605,230`。
- 正式版副作用：D 相对 A 期末权益少 `1,438,435`、总收益少 `719.2175pp`，虽回撤改善 `10.0330pp`，但收益损失太大。
- 结论：all-cases recovery 证明 `0.1` 确实压掉了部分红框右尾，但机制全周期和正式版都伤收益，不晋级。

### Stage414 回撤确认式严重降仓

- D 正式 + 15% DD gate：期末权益 `5,677,840`，总收益 `2738.9200%`，最大回撤 `-37.7762%`，Sharpe `1.4743`，总滑点 `379,090`，总交易次数 `629`，胜率 `51.6444%`。
- C Stage407 + 15% DD gate：期末权益 `2,697,675`，总收益 `1248.8375%`，最大回撤 `-33.6516%`，Sharpe `1.2851`，总滑点 `286,870`，总交易次数 `705`，胜率 `51.4461%`。
- C 相对 B：期末权益少 `587,260`，总收益少 `293.6300pp`，最大回撤恶化 `0.3695pp`，Sharpe 少 `0.1007`，交易多 `17`。
- 红框窗口：B `+90,830`，C `+61,020`，反而少 `29,810`；A 为 `+5,605,230`。
- 正式版副作用：D 相对 A 期末权益少 `3,050,445`、总收益少 `1525.2225pp`，回撤只改善 `0.8951pp`。
- 结论：用账户回撤确认 `0.1` 严重降仓不但不修红框，还显著伤害正式版，不晋级。

## 输出文件

- Stage412 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage699_stage407_streak_time_decay60_report_stage699_stage407_streak_time_decay60_v1.md`
- Stage412 chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage699_stage407_streak_time_decay60_equity_only_stage699_stage407_streak_time_decay60_v1.png`
- Stage413 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage700_stage407_recovery_all_cases_report_stage700_stage407_recovery_all_cases_v1.md`
- Stage413 chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage700_stage407_recovery_all_cases_equity_only_stage700_stage407_recovery_all_cases_v1.png`
- Stage414 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage701_stage407_drawdown_gated_streak_report_stage701_stage407_drawdown_gated_streak_v1.md`
- Stage414 chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage701_stage407_drawdown_gated_streak_equity_only_stage701_stage407_drawdown_gated_streak_v1.png`

## 本阶段结论

- 决策：
  - `stage407_streak_time_decay60_not_promoted`
  - `stage407_recovery_all_cases_not_promoted`
  - `stage407_drawdown_gated_streak_not_promoted`
- 本质判断：
  1. `0.1` 风险档确实会让右尾参与不足，Stage413 红框修复 `+1,411,270` 证明这一点。
  2. 但三类简单机制都不能稳定改善全周期；其中 Stage412 不命中，Stage413 局部修复但全周期和正式版伤收益，Stage414 既不修红框又伤正式版。
  3. 当前问题不是单独的“连败机制太严”，而是 Stage407 AI 重排先破坏核心右尾路径，再叠加 `0.1` 风控，后续任何简单补仓/恢复都救不回原正式版右尾。

## 运行后反思

### 是否过拟合

- 判断：否。
- 原因：三个候选都是单点、低自由度、跨品种通用机制，没有按红框品种、月份或年份拟合。
- 但如果继续在 `60/45/90`、`10%/12%/15%`、`case2 only` 这些细节上扫参，就会变成过拟合。

### 是否有继续价值

- 判断：主账户连败机制救 Stage407 的方向暂时没有继续价值。
- 原因：Stage409/410/411/412/413/414 连续证明，改连败倍率、抬底线、补 1 手、时间衰减、扩 recovery case、回撤 gating 都不能把 Stage407 变成可晋级版本。
- 仍有价值的方向：不让新鸡蛋/新扩池品种挤占主账户 AI 排队和核心右尾，改为独立 sleeve 或独立风险预算；主账户保持当前正式 Stage372/20w 风控不动。

## TODO

- 停止围绕主账户 `0.1` 连败机制扫小数或 case。
- 若继续鸡蛋，优先测试非挤占式独立 sleeve / 独立风险预算，不进入主 AI 排名挤占核心池。
- 若继续风控，转向账户层组合治理，而不是继续修 Stage407 的路径后果。
