# Stage420 低风险候选独立补偿槽反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 13:42 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 结构实验；探索更合理的低自由度风控机制
- 是否重要突破：否，但形成关键负结论
- 是否触发A/B：是，已读取并遵循 `skills/version-ab-experiment/SKILL.md`

## 外部调研与判断

- 参考资料：
  - AQR `Trend Following` / managed futures 资料：趋势收益高度依赖少数右尾趋势段，风控应保留右尾参与权。
  - Man Group 趋势跟踪市场组合研究：市场池和风险预算会显著改变趋势捕捉效率。
  - Hurst/Ooi/Pedersen `A Century of Evidence on Trend-Following Investing`：长期趋势跟踪强调跨市场分散和风险控制，而不是按连续亏损机械关闭机会。
- 我的判断：
  - 主账户连续亏损后直接 `0.1` 确实会压低右尾参与，但前序 Stage409/410/411/415/417 已证明主账户内抬倍率、补一手、本地化连败都会破坏全周期。
  - 本阶段采用更简单结构：主账户 `0.1` 防守完全保留，只把源核心自己已经出现的 `risk_multiplier<=0.1` 候选交给 50k 独立补偿槽，检验“被压住的候选集合”是否有正期望。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage706_low_risk_scout_sleeve.py`
- 修改脚本：无正式策略脚本修改；新增脚本内修复合并旧 `sleeve_*` 空列的输出冲突。
- 删除脚本：无
- 新增参数：
  - `SCOUT_CAPITAL=50,000`
  - `SCOUT_MAXPOS=2`
  - `SCOUT_STREAK_MULTIPLIERS=1.0,1.0,1.0,1.0`
  - `SCOUT_GATE_RISK_MULTIPLIER_MAX=0.1000001`
- 修改参数：无正式参数修改；A/B 主路径不改。
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage705 已生成的 `2020-01-02 -> 2026-04-30` 日级输出；补偿槽用同一下一真实窗口成交口径重跑。
- 账户规模：主账户 `200,000`；补偿槽独立 sizing capital `50,000`；合并权益仍按 `200,000 + core/sleeve pnl` 评估。
- 成本口径：正常成本，另做 `2x/3x` 成本压力。
- 样本过滤：
  - 补偿槽只允许交易源核心 entry candidates 中 `entry_context=flat_entry`、`risk_multiplier<=0.1`、通过初筛、且有开仓/正手数/风险预算0但保证金正的候选。
  - 不按品种、年份、红框窗口、收益结果做过滤。
- 策略/归因口径：
  - A：当前正式 Stage372/20w 原版。
  - B：Stage407 共享 AI rerank top9 诊断基准。
  - C1：A 主路径完全不动 + 正式源低风险候选 scout50k。
  - C2：B 主路径完全不动 + Stage407 源低风险候选 scout50k。

## 结果

### 全周期

- A 正式版：期末权益 `8,728,285`，总收益 `4264.1425%`，最大回撤 `-38.6713%`，Sharpe `1.6279`，总滑点 `506,220`，总交易次数 `633`，胜率 `52.2586%`。
- B Stage407：期末权益 `3,284,935`，总收益 `1542.4675%`，最大回撤 `-33.2821%`，Sharpe `1.3858`，总滑点 `298,030`，总交易次数 `688`，胜率 `51.7181%`。
- C1 正式 + scout50k：期末权益 `8,705,625`，总收益 `4252.8125%`，最大回撤 `-39.6009%`，Sharpe `1.6202`，总滑点 `507,070`，总交易次数 `697`，胜率 `51.9332%`，scout PnL `-22,660`。
- C2 Stage407 + scout50k：期末权益 `3,272,220`，总收益 `1536.1100%`，最大回撤 `-34.1587%`，Sharpe `1.3772`，总滑点 `299,360`，总交易次数 `774`，胜率 `51.6579%`，scout PnL `-12,715`。

### 成本压力和保证金

- C1 broker10 最大保证金/权益 `80.2582%`，未穿 `100%`，但 `2x` 成本最大回撤 `-41.6465%`，比正式版 `-40.6555%` 更差。
- C2 broker10 最大保证金/权益 `83.4644%`，未穿 `100%`，`2x` 成本最大回撤 `-36.0512%`。

### 红框窗口 `2025-04-16 -> 2025-07-25`

- A 正式版增长 `+5,605,230`
- B Stage407 增长 `+90,830`
- C1 正式 + scout50k 增长 `+5,605,230`，但窗口起点已因前序 scout 亏损比 A 低 `20,220`
- C2 Stage407 + scout50k 增长 `+99,500`，只比 B 多 `+8,670`

### Gate 触发规模

- 正式源低风险候选 key：`228` 个；补偿槽实际交易 `64` 次，scout PnL `-22,660`。
- Stage407 源低风险候选 key：`199` 个；补偿槽实际交易 `86` 次，scout PnL `-12,715`。

### 补偿槽产品/年度归因

- C1 主要拖累：`fu.SHFE -6,340`、`SM.CZCE -5,960`、`MA.CZCE -4,350`、`rb.SHFE -2,600`、`SA.CZCE -1,840`；少量正贡献仅 `FG.CZCE +500`。
- C1 年度：2020 `-1,420`、2021 `-5,010`、2022 `-14,890`、2023 `+1,620`、2024 `-1,320`、2025 `-40`、2026 `-1,600`。
- C2 主要拖累：`MA.CZCE -5,730`、`rb.SHFE -4,120`、`jd.DCE -3,560`、`SM.CZCE -2,740`；正贡献为 `FG.CZCE +2,840`、`si.GFEX +2,650`、`CF.CZCE +875`。
- C2 年度：2020 `-825`、2021 `-5,450`、2022 `-5,660`、2023 `-1,230`、2024 `-380`、2025 `+3,835`、2026 `-3,005`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage706_low_risk_scout_sleeve_report_stage706_low_risk_scout_sleeve_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage706_low_risk_scout_sleeve_summary_stage706_low_risk_scout_sleeve_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage706_low_risk_scout_sleeve_daily_stage706_low_risk_scout_sleeve_v1.csv`
- sleeve daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage706_low_risk_scout_sleeve_sleeve_daily_stage706_low_risk_scout_sleeve_v1.csv`
- sleeve product：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage706_low_risk_scout_sleeve_sleeve_product_stage706_low_risk_scout_sleeve_v1.csv`
- gate events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage706_low_risk_scout_sleeve_gate_events_stage706_low_risk_scout_sleeve_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage706_low_risk_scout_sleeve_chart_stage706_low_risk_scout_sleeve_v1.png`
- equity chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage706_low_risk_scout_sleeve_equity_only_stage706_low_risk_scout_sleeve_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage706_low_risk_scout_sleeve_decision_stage706_low_risk_scout_sleeve_v1.json`

## 结论

- 本阶段结论：`low_risk_scout_sleeve_not_promoted`。
- 是否进入下一步：不晋级，不继续调 scout 资金、maxpos、品种、方向或日期。
- 核心判断：
  - `0.1` 连败机制确实粗糙，但“源核心处在 0.1 低风险档时出现的候选”不是一个有正期望的候选集合。
  - 在正式版上，独立补偿槽全周期亏 `-22,660`，还把 `2x` 成本回撤打到 `-41.6465%`。
  - 在 Stage407 上，补偿槽几乎不能修复红框，说明红框主因仍是 AI 共享重排破坏 `fu/jm/si/FG` 路径，而不是低风险候选缺少一个独立槽。
  - 因此当前更合理的结论不是“关掉连败风控”，而是保留正式 `1,1,1,0.1 + recovery_sleeve`，停止主账户连败机制救援；未来若继续，只能研究更上游的账户级 selector 或真正独立、事前有正期望的收益源。

## 过拟合反思

- 运行前判断：否。候选是预声明结构，不按品种、年份、红框窗口和收益结果筛选。
- 运行后判断：否，但继续救它会过拟合。
- 原因：结果表明结构本身没有携带收益；如果继续调 `50k -> 30k/80k`、`maxpos=1/3`、只保留 2025 或只保留 `FG/si`，就是在历史结果上找补丁。

## 继续价值反思

- 运行前判断：有价值，因为它是比主账户抬倍率更干净的风险隔离实验。
- 运行后判断：该形状继续价值低；总目标仍有价值。
- 原因：本阶段反证了“低风险候选补偿槽”这个简单结构。目标应继续，但方向要从连败倍率/补偿槽转向更本质的事前质量识别，或保留正式主账户、寻找真正独立的正期望 sleeve。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage420 负结论。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，追加 back_log；memory 追加“停止低风险候选补偿槽调参”的长期边界。
